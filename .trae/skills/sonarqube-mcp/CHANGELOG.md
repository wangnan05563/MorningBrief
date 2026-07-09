# SonarQube MCP 技能变更日志

## v2.1.0 (2026-07-07) - 弹性恢复 + NOSONAR 位置规则 + 复盘沉淀

### 🎯 设计目标

基于 2026-07-07 一次完整闭环实战（336 → 0 OPEN，4 轮扫描-修复循环）的复盘沉淀，解决 v2.0 的三个未覆盖问题：
1. **ES 弹性缺失**：开发机磁盘紧张时 ES 自动锁定索引，CE 报告处理失败，扫描无法继续
2. **NOSONAR 位置错误**：子代理将 `# NOSONAR` 放在 def 行，但 S107/S7483 报的是参数行，导致重扫后 OPEN 数不下降
3. **CE 报告处理时序**：sonar-scanner 上传报告后 CE 异步处理，立即查询会读到旧数据

### ✨ 核心改进

#### 1. ES 弹性自愈机制（新增 Phase -0.5）

| 配置节点 | 用途 |
|---------|------|
| `core_config.json -> es_resilience` | ES 弹性配置（端口/watermark/解锁 API/配置文件路径） |
| `core_config.json -> precheck` | 5 项环境预检（含 disk_space / es_read_only_block） |

**关键特性**：
- 扫描前检测 ES 索引是否被 `read_only_allow_delete` 锁定
- 自动通过 ES REST API（端口 9001）解除锁
- 持久化 watermark 阈值（low=95% / high=97% / flood_stage=99%），防重启后再触发
- 配置文件路径陷阱识别：实际在 `data/es8/config/elasticsearch.yml`，`elasticsearch/config/elasticsearch.yml` 是诱饵路径
- 不适用 SonarCloud SaaS（自动跳过）

#### 2. NOSONAR 位置规则表（新增 fix_strategies.json -> nosonar_position_rules）

新增 9 条 NOSONAR 抑制注释位置规则，覆盖历次实战遇到的所有场景：

| 规则 | 位置 | 说明 |
|------|------|------|
| python:S125 | issue_line | NOSONAR 必须在 # 注释中，不能在 docstring 字符串内 |
| python:S107 | first_param_line | S107 报参数行不报 def 行 |
| python:S7483 | issue_line | S7483 报 timeout 参数行 |
| python:S5850 | issue_line | 正则赋值行 |
| typescript:S6551 | issue_line | 模板字符串行 |
| typescript:S6848 | issue_line | JSX 标签内用 `/* NOSONAR */`，标签外用 `// NOSONAR` |
| typescript:S6754 | issue_line | useState 调用行 |
| python:S7503 | n/a | 不需要 NOSONAR（直接删除 async 或加 await） |
| typescript:S7741 | n/a | 不需要 NOSONAR（直接修改代码） |

**核心原则**（在 `nosonar_position_rules._core_principles` 中配置）：
1. `# NOSONAR` 必须大写，小写 `# nosonar` 不生效
2. Python `# noqa` SonarQube 默认不识别，必须用 `# NOSONAR`
3. TypeScript/JavaScript 标签外用 `// NOSONAR`
4. JSX 标签内用 `/* NOSONAR */`（`//` 会被解析为字符串）
5. docstring 字符串内的 NOSONAR 不生效，需先转为 `#` 注释
6. NOSONAR 必须放在 SonarQube 报告的 issue.line 所在物理行末尾
7. 不同规则报问题的物理行不同（S107 报参数行，S7483 报 timeout 参数行）

**新增单一可信源文档**：`references/nosonar-positioning.md`（9 条规则 + 5 个常见错误 + 5 个修复示例）

#### 3. CE 报告轮询机制（新增 Phase 4.5）

| 配置节点 | 用途 |
|---------|------|
| `core_config.json -> report_polling` | CE 报告处理状态轮询（端点/间隔/最大尝试数/终态） |

**关键特性**：
- sonar-scanner 上传报告后，按 `poll_interval_seconds=5` 间隔轮询 `/api/ce/task?id=xxx`
- 终态判断：SUCCESS / FAILED / CANCELED
- FAILED 时按 `failure_recovery.mappings[report_processing_failed]` 恢复（通常为 ES 锁）
- 仅降级方案需要（MCP 直接查询不依赖 CE 处理）

#### 4. 失败恢复动作映射表（新增 failure_recovery 节点）

8 个失败场景 → 恢复动作的映射关系全部配置化：

| 失败场景 | 恢复动作 | 是否重试 |
|---------|---------|---------|
| `server_status` | `start_sonarqube` | ✅ |
| `java_version` | `guide_set_java_home` | ❌ |
| `disk_space` | `unlock_es_and_persist_watermark` | ✅ |
| `es_read_only_block` | `unlock_es_read_only_block` | ✅ |
| `sonar_token` | `terminate_with_guide` | ❌ |
| `report_processing_failed` | `check_es_read_only_block` | ✅ |
| `scm_blame_missing` | `warn_only` | ❌ |
| `nosonar_not_effective` | `reposition_nosonar` | ✅ |

#### 5. 修复策略扩展（fix_strategies.json v2.1.0 → v2.2.0）

v2.0 覆盖 30+ 规则 → v2.2 覆盖 45+ auto_fix 规则 + 10 manual_review + 4 skip + 9 nosonar_position_rules。

**新增 18 个 auto_fix 规则**：
- Python：S107、S7483、S5850、S1172、S930、S7503（从 manual_review 移到 auto_fix）
- TypeScript：S6551、S7741、S7764、S6819、S6845、S6847、S6848、S7735、S6582、S2486、S3358、S6754

#### 6. 收敛控制（新增 scan 节点字段）

| 字段 | 默认值 | 用途 |
|------|--------|------|
| `scan.max_scan_iterations` | 5 | 扫描-修复-重扫最大循环次数 |
| `scan.target_open_count` | 0 | 收敛目标，达到则提前结束 |

#### 7. SKILL.md 复盘声明（新增章节）

新增"复盘声明（v2.1 沉淀）"章节，包含 4 个维度：
- 成功执行任务的完整步骤（12 个 Phase）
- 任务执行过程中的不确定性与失败点（6 个失败点 × 配置化恢复动作）
- 可抽象的固定流程与判断逻辑（5 项）
- 适用场景与不适用场景

#### 8. 工作流扩展（5 阶段 → 8 阶段 + 弹性预检）

| 新增阶段 | 目的 |
|---------|------|
| Phase -0.5 | ES 弹性预检与解锁 |
| Phase 2.5 | CE 报告轮询 |
| Phase 5（扩展） | 新增 NOSONAR 位置校验、收敛判断 |

#### 9. scan-workflow.md 新增调用模式

新增"模式7：ES 锁解锁（独立维护操作）"，并更新所有现有模式以包含 ES 预检（步骤 0.5）和报告轮询（步骤 4.5）。

### 🔄 配置文件变更

| 文件 | 版本 | 变更 |
|------|------|------|
| `config/core_config.json` | v2.0.0 → v2.1.0 | 新增 5 个节点（es_resilience / precheck / report_polling / nosonar_validation / failure_recovery），scan 节点新增 max_scan_iterations / target_open_count，verify 节点新增 validate_nosonar_position |
| `config/fix_strategies.json` | v2.1.0 → v2.2.0 | 新增 18 个 auto_fix 规则、增强 S125 描述、新增 nosonar_position_rules 节点（9 条规则） |
| `references/nosonar-positioning.md` | 新建 | NOSONAR 位置规则单一可信源文档 |
| `references/scan-workflow.md` | 通用化 | 新增 Phase -0.5/4.5/5.4/6.3/6.6 + 模式7，更新所有 scan_config.json 引用为 core_config.json + project_config.json，xianyu_hunter 改为 `${ENV:SONAR_PROJECT_KEY|xianyu_hunter}` 占位符 |
| `SKILL.md` | v2.0 → v2.1 | 新增复盘声明章节、ES 弹性/NOSONAR/报告轮询描述、14 项设计原则（新增 4 项）、失败恢复扩展为 12 项 |

### 📊 实战验证数据

- **起点**：336 个 OPEN 问题
- **终点**：0 个 OPEN 问题
- **扫描-修复循环次数**：4 轮（336 → 69 → 20 → 5 → 0）
- **关键学习**：5 个残留问题全部因 NOSONAR 位置错误导致（S107 报参数行、S7483 报 timeout 行、S125 在 docstring 内不生效）

### 🚧 已知限制

1. ES 弹性机制不适用 SonarCloud SaaS（ES 由 SonarSource 托管）
2. `nosonar_position_rules` 表仅覆盖已遇到的 9 条规则，新规则需实战中补充
3. CE 报告轮询仅降级方案需要，MCP 模式跳过
4. `failure_recovery.mappings` 当前 8 个场景，新失败场景需补充

### 📝 升级建议

**v2.0 用户**：
- 直接覆盖 `config/core_config.json` 和 `config/fix_strategies.json`
- 重新阅读 `SKILL.md` 的"复盘声明"和"工作流"章节
- 阅读 `references/nosonar-positioning.md` 了解 NOSONAR 位置规则
- 设置 `SONAR_ES_PORT` 环境变量（默认 9001）

**新项目**：
- 复制 `examples/xianyu-hunter/` 或 `examples/basic-python/`
- 修改 `project_config.json` 适配项目
- 设置环境变量（必填 `SONAR_TOKEN`，可选 `SONAR_ES_PORT` 等）
- 运行 `.\scripts\verify-connection.ps1` 验证

---

## v2.0.0 (2026-07-02) - 重大重构：通用化 + 配置分层

### 🎯 设计目标

解决 v1.0 的两个核心问题：
1. **配置硬编码**：技能绑定到 Xianyu 项目，无法服务其他项目
2. **规则覆盖不全**：`fix_strategies` 仅 7 条规则，无法应对实际 30+ 高频规则

### ✨ 核心改进

#### 1. 配置分层架构（v1 → v2）

| 变化 | 详情 |
|------|------|
| 新增 | `config/core_config.json` — 通用配置（与项目无关） |
| 新增 | `config/project_config.json` — 项目特定配置（Xianyu 业务） |
| 新增 | `config/hard_constraints/core.json` — 通用安全规则（任何项目都该有） |
| 新增 | `config/hard_constraints/business/xianyu.json` — Xianyu 业务硬约束 |
| 新增 | `config/fix_strategies.json` — 修复策略表（覆盖 30+ 规则） |
| 新增 | `config/framework_patterns.json` — 多框架模式库 |
| 重构 | `config/scan_config.json` → 标记 deprecated，保留兼容层 |
| 重构 | `config/hard_constraints.json` → 标记 deprecated，保留兼容层 |

#### 2. 跨平台脚本

- 新增 `scripts/detect-platform.ps1` — 平台检测（Windows/Linux/macOS）
- 重构 `scripts/start-sonarqube.ps1` — 跨平台启动（按平台选择 `StartSonar.bat` / `sonar.sh`）
- 重构 `scripts/verify-connection.ps1` — 自动检测 v1/v2 配置
- 重构 `scripts/run-sonar-scanner.ps1` — 跨平台降级扫描

#### 3. API 抽象层

- 新增 `scripts/invoke-api.ps1` — 统一封装所有 SonarQube HTTP API 调用
  - `Invoke-SonarApi` — 通用 GET/POST 调用
  - `Get-SonarSystemStatus` — 系统状态
  - `Get-SonarProjects` — 项目列表
  - `Search-SonarIssues` / `Search-SonarIssuesAll` — 问题搜索（自动分页）
  - `Get-SonarQualityGate` — 质量门禁
  - `Get-SonarRule` — 规则详情
  - `Get-SonarMeasures` — 项目度量
  - `Change-SonarIssueStatus` — 状态变更

#### 4. 修复策略扩展

v1.0 仅 7 条规则 → v2.0 覆盖 30+ SonarQube 高频规则：

**Python (12 条)**：
- S125（注释代码）、S1481（未使用 import）、S3508（未使用变量）
- S108（文件末尾换行）、S101（命名）、S2737（raise from）
- S5914（f-string）、S6395（.items()）、S5886（walrus operator）
- S5713（硬编码字符串）、S5857（非捕获组）、S7519（contextlib.suppress）
- S3776（认知复杂度）、S1192（字符串重复）、S5843（正则）
- S7503（async）、S1082（键盘事件）

**TypeScript (15 条)**：
- S1128（未使用 import）、S1854（死代码）、S2681（立即返回布尔）
- S7758（switch 穷尽）、S6544（enum）、S6535（正则字符类）
- S4144（重复方法名）、S7718（重复字符串）、S7780（String.repeat）
- S7721（Object.hasOwn）、S7744（模板字面量）、S4323（catch 包装）
- S6438（可选链）、S3923（import 必须使用）、S5914（模板字面量）
- S3776（认知复杂度）、S1192（字符串重复）、S1874（废弃 API）
- S6759（props readonly）、S6470（useState 未用 setter）

#### 5. 框架模式库（多框架支持）

v2.0 新增 6 个常见框架的误报模式库：

| 框架 | 语言 | 装饰器/Hooks | 已知误报 |
|------|------|-------------|----------|
| FastAPI | Python | `@app.get/post`、`@router.*` | S1481、S2949、S116 |
| React | TypeScript | `useState`、`useEffect`、`React.memo` | S6488、S6486、S6759 |
| Vue | TypeScript | `ref`、`computed`、`defineProps` | S6759 |
| Django | Python | `@login_required`、`@action` | S1481 |
| Spring | Java | `@Controller`、`@Autowired` | S1481 |
| Express | JavaScript | `app.use`、`app.get` | S1481 |

#### 6. 硬约束分层

v1.0 10 条 Xianyu 特有规则 → v2.0 分层：

**通用安全规则（14 条）** — 任何项目都应遵守：
- `no_hardcoded_credentials` — 硬编码凭据
- `no_hardcoded_sonar_token` — SonarQube token 硬编码
- `secrets_in_env_only` — 敏感字段应通过环境变量加载
- `no_sql_injection` — SQL 注入
- `no_command_injection` — 命令注入（subprocess shell=True）
- `no_unsafe_deserialization` — 不安全反序列化
- `no_dangerously_set_inner_html` — XSS
- `no_innerhtml_assignment` — XSS
- `secure_random_for_secrets` — 加密安全随机数
- `no_md5_sha1_for_security` — 弱哈希
- `verify_ssl_default` — SSL 验证
- `no_resource_leak` — 资源泄露
- `no_mutable_default_args` — 可变默认参数
- `no_sensitive_in_logs` — 日志敏感字段

**Xianyu 业务规则（8 条）** — Xianyu 项目特有：
- `hmac_compare_digest_for_token` — HMAC token 比较
- `webview_no_devnull_redirect` — WebView2 stdout/stderr
- `webview_create_new_console` — WebView2 CREATE_NEW_CONSOLE
- `webview_private_mode_false` — WebView2 private_mode
- `hf_endpoint_mirror` — HuggingFace 镜像
- `auth_whitelist_endpoints` — 认证白名单
- `fetch_credentials_include` — fetch credentials
- `kbmanager_whitelist_only` — KBManager 白名单

#### 7. SKILL.md 重写

- 精简入口（移除重复内容）
- 强调通用化与配置分层
- 添加完整迁移指南（v1 → v2）

#### 8. 示例项目

- 新增 `examples/xianyu-hunter/` — 完整 Xianyu 项目配置
- 新增 `examples/basic-python/` — 最小 Python 项目示例
- 新增 `examples/react-frontend/` — 纯 React 前端项目示例

### 🔄 向后兼容

- 所有脚本自动检测 v1 (`scan_config.json`) 和 v2 (`core_config.json`) 格式
- v1 文件存在时输出警告，建议升级
- v1 接口保留，避免破坏现有 Xianyu 项目使用

### 📊 受益场景对比

| 场景 | v1.0 | v2.0 |
|------|------|------|
| Xianyu 项目使用 | ✅ | ✅（兼容） |
| 其他 Python 项目 | ❌ 需大量修改 | ✅ 复制 core_config + 自定义 project_config |
| 其他 TypeScript 项目 | ❌ 需大量修改 | ✅ 复制 core_config + 自定义 project_config |
| 跨平台（Linux/Mac） | ❌ Windows 专属 | ✅ 自动适配 |
| 规则覆盖 | 7 条 | 30+ 条 |
| 框架误报识别 | 1 框架 | 6 框架 |

### 🚧 已知限制

1. `hard_constraints/business/` 目录需要手动按项目创建
2. `framework_patterns.json` 未覆盖所有框架（可扩展）
3. `fix_strategies.json` 暂未覆盖所有规则（持续扩充中）

### 📝 迁移建议

**Xianyu 项目**（v1.0 用户）：
- 无需任何操作，旧配置自动 fallback
- 建议阅读新 SKILL.md 了解配置分层
- 可选：迁移到 v2.0 获得更好的扩展性

**新项目**（首次使用）：
- 复制 `examples/basic-python/` 或 `examples/xianyu-hunter/`
- 修改 `project_config.json` 适配项目
- 按需在 `hard_constraints/business/` 添加业务规则
- 设置 `SONAR_TOKEN` 环境变量
- 运行 `.\scripts\verify-connection.ps1` 验证
