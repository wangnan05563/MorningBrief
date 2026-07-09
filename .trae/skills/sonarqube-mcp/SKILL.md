---
name: "sonarqube-mcp"
description: "通用 SonarQube 代码质量闭环：扫描→分类→并行修复→验证→报告。适用于任何有 SonarQube 服务的项目（Python/TypeScript/Java/Go）。调用时机：用户要求修复 SonarQube 问题、代码质量检测、扫描问题修复、代码质量问题闭环处理，或提到 'sonarqube'、'sonar'、'代码扫描修复'、'代码检测' 等关键词时。"
whenToUse: "编码/开发/缺陷修复后调用、用户要求代码质量检查、CI/CD 质量门禁验证、提交前扫描、技术债清理、用户想要分析 SonarQube 规则或误报、用户想要修复特定严重级别的问题、用户请求提交前或推送前的质量反馈"
triggers:
  - "sonar/sonarqube/sonarcloud/质量门禁/代码质量"
  - "增量/全量/代码/sonar 扫描"
  - "quality gate"
  - "sonar issues"
  - "analyze with sonar"
  - "check sonar"
  - "sonar rule"
  - "pre-push analysis"
  - "代码扫描修复"
  - "修复扫描问题"
  - "sonar fix"
---

# SonarQube MCP 技能（v2.1 通用化 + 弹性恢复）

通用 SonarQube 代码质量闭环技能，对 SonarQube 扫描出的所有问题进行**服务器检测→ES 弹性预检→连接验证→扫描→分类→并行修复→NOSONAR 位置校验→报告**的完整修复流程。支持任意项目 + 任意语言 + 任意框架组合，内置 ES read-only 锁自愈、CE 报告轮询、NOSONAR 位置校验三大弹性机制。

## 复盘声明（v2.1 沉淀）

> 本节内容基于 2026-07-07 一次完整闭环实战（336 → 0 OPEN，4 轮扫描-修复循环）沉淀。

### 成功执行任务的完整步骤

1. **Phase -1**：SonarQube 服务器检测与启动
2. **Phase -0.5**：Elasticsearch 弹性预检与解锁（防 CE 报告 FAILED）
3. **Phase 0**：前置检查（5 项预检 + 失败恢复动作映射）
4. **Phase 1**：MCP 可用性检测与降级处理
5. **Phase 2**：功能模块代码定位
6. **Phase 3**：质量门禁检查
7. **Phase 4**：问题扫描（含分页/过滤/排序）
8. **Phase 4.5**：Compute Engine 报告轮询（防读取旧数据）
9. **Phase 5**：并行修复（含 NOSONAR 位置判断）
10. **Phase 6**：验证（重扫 + 测试 + NOSONAR 位置校验 + 硬约束 + 收敛判断）
11. **Phase 7**：报告
12. **Phase 8**：问题状态管理（需用户确认）

### 任务执行过程中的不确定性与失败点

| 失败点 | 不确定性 | 配置化恢复动作 |
|--------|---------|---------------|
| 磁盘超 flood_stage → ES 锁定 | 开发机磁盘紧张时高发 | `unlock_es_and_persist_watermark` |
| CE 报告处理 FAILED | 报告上传后异步处理可能失败 | `check_es_read_only_block` + 重试 |
| NOSONAR 位置错误 | 不同规则报的物理行不同 | `reposition_nosonar`（按位置规则表查表） |
| Java 版本不匹配 | SonarQube 26 需 Java 17+ | `guide_set_java_home`（不重试） |
| SCM blame 缺失 | 44+ 文件时出现 | `warn_only`（不阻塞） |
| sonar-scanner 路径错误 | 跨平台路径差异 | 通过环境变量 + 配置占位符解析 |

### 可抽象的固定流程与判断逻辑

1. **预检 → 失败映射 → 恢复动作**：`precheck.checks` × `failure_recovery.mappings` 配置驱动，所有失败场景可枚举
2. **修复策略分类**：`fix_strategies.json` 三档（auto_fix / manual_review / skip），按 rule ID 查表
3. **NOSONAR 位置规则**：`nosonar_position_rules` 9 条规则，按 rule ID 查表确定物理行（issue_line / first_param_line / def_line）
4. **收敛判断**：`scan.max_scan_iterations` × `scan.target_open_count` 双重控制，避免无限循环
5. **配置占位符**：`${ENV:VAR|default}` 统一占位符语法，运行时解析

### 适用场景与不适用场景

**适用**：
- 中大型项目（> 500 行）持续维护
- 多语言/多框架组合项目
- 本地或自建 SonarQube 服务（含 ES 弹性需求）
- CI/CD 质量门禁集成
- 大规模代码质量清零（如 336 → 0）

**不适用**：
- 极小型脚本/原型项目（< 500 行）
- 一次性 MVP（无持续维护需求）
- 高度依赖代码生成器的项目（生成代码噪声过高）
- 紧急热修复（全量扫描太慢）
- 未部署 SonarQube 服务且无降级能力的环境
- SonarCloud SaaS（ES 由 SonarSource 托管，无需 ES 解锁）

## 适用场景

| 场景 | 支持 | 说明 |
|------|------|------|
| Python/TypeScript/Java/Go 多语言项目 | ✅ | 通过 `core_config.json -> scan.languages` 配置 |
| FastAPI/React/Vue/Django/Spring 等常见框架 | ✅ | 通过 `framework_patterns.json` 自动识别误报 |
| 任意 SonarQube 服务（本地/SonarCloud/自建） | ✅ | 通过 `core_config.json -> sonarqube_server` 配置 |
| Windows/Linux/macOS 跨平台 | ✅ | 通过 `scripts/detect-platform.ps1` 自动适配 |
| MCP 工具不可用时的降级扫描 | ✅ | 通过 `scripts/invoke-api.ps1` + `run-sonar-scanner.ps1` |
| CI/CD 集成（提交前/合并前） | ✅ | 通过环境变量配置 + `verify.fail_on_new_issues` |
| 本地 SonarQube ES 弹性自愈 | ✅ | 通过 `core_config.json -> es_resilience` 自动解锁 + 持久化 watermark |
| 大规模 OPEN 问题清零 | ✅ | 通过 `scan.max_scan_iterations` × `target_open_count` 收敛控制 |

## 不适用场景

- 极小型脚本/原型项目（< 500 行）
- 一次性 MVP（无持续维护需求）
- 高度依赖代码生成器的项目（生成代码噪声过高）
- 紧急热修复（全量扫描太慢，应直接针对性修复）
- 未部署 SonarQube 服务且无降级能力的环境
- SonarCloud SaaS（ES 由 SonarSource 托管，ES 解锁流程不适用，但其他流程仍可用）

## Skill 职责

1. **服务器检测与启动**：跨平台自动检测/启动 SonarQube 服务
2. **ES 弹性预检**：扫描前检测并解除 ES read-only 锁，持久化 watermark 阈值
3. **连接验证**：MCP 工具 + HTTP API 双通道验证
4. **代码定位**：根据功能模块自动定位文件
5. **质量门禁检查**：验证项目是否通过质量门禁
6. **问题扫描**：按严重级别/类型/规则扫描
7. **CE 报告轮询**：等待 Compute Engine 处理完成，避免读取旧数据
8. **问题分类**：自动识别误报（基于框架模式库）
9. **并行修复**：按文件分组并行执行（Task 工具），含 NOSONAR 位置判断
10. **修复验证**：重新扫描 + 测试运行 + NOSONAR 位置校验 + 硬约束检查 + 收敛判断
11. **报告生成**：标准化 Markdown 报告

## 配置文件分层（v2.1 核心架构）

> **关键设计**：技能本身不包含任何项目特定配置，所有配置都通过分层文件管理。所有可变参数（端口/路径/阈值/动作）均通过配置文件管理，无硬编码。

```
config/
├── core_config.json                    # 通用配置（与项目无关，v2.1.0）
│   ├── sonarqube_server               # 服务器连接（host/port/java_home/启动超时）
│   ├── es_resilience                  # ES 弹性配置（端口/watermark/解锁 API/配置文件路径）★ v2.1 新增
│   ├── precheck                       # 环境预检（5 项检查 + on_failure 动作映射）★ v2.1 新增
│   ├── sonar_scanner                  # 降级扫描器（路径/超时）
│   ├── mcp_check                      # MCP 能力要求
│   ├── scan                           # 扫描参数（严重级别/分页/并行数/迭代上限/收敛目标）
│   ├── report_polling                 # CE 报告轮询（端点/间隔/最大尝试数/终态）★ v2.1 新增
│   ├── priority                       # 修复优先级（severity_order/type_order）
│   ├── filters                        # 通用过滤（路径/规则/严重级别）
│   ├── verify                         # 修复后验证（rescan/test/fail_on_new/nosonar 校验）
│   ├── nosonar_validation             # NOSONAR 位置校验（开关/位置规则源/常见错误）★ v2.1 新增
│   ├── failure_recovery               # 失败场景→恢复动作映射表（8 个场景）★ v2.1 新增
│   ├── report                         # 报告输出
│   └── environment_variables           # 环境变量说明
│
├── project_config.json                # 项目特定配置（Xianyu 业务配置）
│   ├── project                        # 项目信息（key/name/base_path）
│   ├── modules                        # 模块路径与层级（backend/frontend）
│   ├── verify.test_commands           # 分模块测试命令（backend/frontend）
│   └── framework_extensions           # 项目启用的框架（fastapi_decorators/react_patterns）
│
├── fix_strategies.json                # 修复策略表 + NOSONAR 位置规则（v2.2.0）
│   ├── strategies.auto_fix            # 可自动修复的规则（45+ 条）
│   ├── strategies.manual_review       # 需人工审查的规则（10 条）
│   ├── strategies.skip                # 已知误报（4 条）
│   └── nosonar_position_rules         # NOSONAR 抑制注释位置规则表（9 条）★ v2.2 新增
│
├── framework_patterns.json            # 框架模式库（多框架支持）
│   ├── fastapi                        # 装饰器 + 已知误报
│   ├── react                          # Hooks + 已知误报
│   ├── vue/django/spring/express      # 其他框架
│   └── selection_logic                # 框架自动识别逻辑
│
└── hard_constraints/                  # 硬约束（分通用 + 业务两层）
    ├── core.json                      # 通用安全规则（任何项目都该有）
    │   ├── no_hardcoded_credentials
    │   ├── no_sql_injection
    │   ├── no_command_injection
    │   ├── no_dangerously_set_inner_html
    │   ├── secure_random_for_secrets
    │   └── ...
    └── business/                      # 项目特有硬约束
        └── xianyu.json                # Xianyu 特有（WebView2/HF_ENDPOINT/HMAC）
```

## 快速开始

### 1. 准备配置

```bash
# 复制核心配置（v2.0 已内置）
# 复制项目配置模板
cp examples/xianyu-hunter/config/project_config.json my-project/config/

# 修改 project_config.json 适配你的项目
```

### 2. 设置环境变量

```powershell
# 必需
$env:SONAR_TOKEN = "squ_xxxxxxxx"

# 可选
$env:SONARQUBE_URL = "http://localhost:9000"
$env:SONARQUBE_PORT = "9000"
$env:SONARQUBE_HOME = "D:\tools\sonarqube"
$env:JAVA_HOME_SONAR = "D:\tools\jdk17"
$env:SONAR_PROJECT_KEY = "my_project"
$env:SONAR_ES_PORT = "9001"              # ES REST API 端口（默认 9001，v2.1 新增）
$env:SONAR_SCANNER_HOME = "D:\tools\sonar-scanner"
$env:SONAR_MCP_SERVER_NAME = "mcp_sonarqube"
$env:SONAR_JAVA_MIN_VERSION = "17"
```

### 3. 验证环境

```powershell
.\scripts\verify-connection.ps1
```

### 4. 触发扫描

**MCP 模式**（推荐）：
```
调用 Search-SonarIssues -Projects "my_project" -Severities "BLOCKER","CRITICAL"
```

**降级模式**（MCP 不可用）：
```powershell
.\scripts\run-sonar-scanner.ps1
```

### 5. 并行修复

```
按 fix_strategies.json 配置自动处理：
- auto_fix  → 子代理直接执行
- manual_review → 输出建议给用户决策
- skip → 标记为误报
```

### 6. 验证 + 报告

```
重扫对比 → 运行测试 → 硬约束检查 → 生成 reports/sonar-fix-report-YYYYMMDD.md
```

## 工作流（8 阶段闭环 + 弹性预检）

> **执行原则**：智能体按当前 Phase 按需 Read 对应 reference 文档。详细步骤见 [references/scan-workflow.md](references/scan-workflow.md)。

### Phase -1: Server Detection（服务器检测与启动）

- 自动检测 SonarQube 服务状态（`start-sonarqube.ps1 -StatusOnly`）
- 未运行则自动启动（`start-sonarqube.ps1`）
- 失败时按 `failure_recovery.mappings[server_status]` 恢复

### Phase -0.5: ES Resilience（ES 弹性预检与解锁）★ v2.1 新增

- 读取 `core_config.json -> es_resilience` 配置
- 检测 ES 索引是否被 `read_only_allow_delete` 锁定
- 若被锁，按 `unlock_apis` 解除锁 + 持久化 watermark 阈值（防重启后再触发）
- 不适用 SonarCloud SaaS（自动跳过）

### Phase 0: Pre-flight（前置检查）

- 执行 `precheck.checks` 中 5 项检查（server_status / java_version / disk_space / es_read_only_block / sonar_token）
- 任一失败时按 `failure_recovery.mappings` 查找恢复动作并执行
- 凭据必须从环境变量读取，禁止硬编码

### Phase 1: Verification（MCP 可用性检测与降级）

- 检测 MCP 工具可用性
- MCP 不可用时降级到 `scripts/run-sonar-scanner.ps1`
- 降级方案限制：无法使用 `analyze_code_snippet` / `change_sonar_issue_status`

### Phase 2: Scan & Triage（扫描与分类）

- 调用 `Search-SonarIssuesAll` 全量拉取问题（含分页处理）
- 按 `priority.severity_order` × `priority.type_order` 排序
- 应用 `filters`（ignore_paths/ignore_rules/ignore_severity_in_tests）
- 按文件分组（用于并行修复）

### Phase 2.5: CE Report Polling（Compute Engine 报告轮询）★ v2.1 新增

- 仅降级方案需要：sonar-scanner 上传报告后，CE 异步处理
- 按 `report_polling` 节点配置轮询 `/api/ce/task?id=xxx`
- FAILED 时按 `failure_recovery.mappings[report_processing_failed]` 恢复（通常为 ES 锁）

### Phase 3: Classification（问题分类）

- 加载 `framework_patterns.json`（根据 `project_config.json -> modules.frameworks`）
- 自动识别框架误报（FastAPI 装饰器、React Hook 依赖等）
- 匹配 `fix_strategies.json` 的 auto_fix/manual_review/skip

### Phase 4: Parallel Fix（并行修复）

- 子代理数：`scan.parallel_agents`
- 每个子代理处理 `scan.files_per_agent` 个文件
- 同一文件内 issue 串行处理（避免 Edit 冲突）
- 子代理 prompt 模板：`assets/subagent-task-template.md`
- **NOSONAR 位置判断**：使用 NOSONAR 抑制时，按 `fix_strategies.json -> nosonar_position_rules` 查表确定物理行

### Phase 5: Verify & Report（验证与报告）

- 重新扫描（`verify.rescan_after_fix`）
- **NOSONAR 位置校验**（`verify.validate_nosonar_position`）：若 OPEN 数未下降，按 `nosonar_validation` 检查位置错误并重放置
- 运行测试（`project_config.json -> verify.test_commands` 分模块执行）
- 硬约束合规性检查（`hard_constraints/core.json` + `hard_constraints/business/*.json`）
- **收敛判断**：未达 `scan.target_open_count` 且未超 `scan.max_scan_iterations` 时回到 Phase 2
- 生成报告：`assets/report-template.md` → `report.output_dir`

## 前置要求

### 必需

1. **SonarQube 服务**：可访问的 SonarQube 实例（本地或 SonarCloud）
2. **SONAR_TOKEN 环境变量**：在 SonarQube Web 界面生成 Global Analysis Token
3. **配置文件**：
   - `config/core_config.json`（v2.0 已内置）
   - `config/project_config.json`（需根据项目定制）
   - `config/fix_strategies.json`（v2.0 已内置）
   - `config/framework_patterns.json`（v2.0 已内置）

### 可选

4. **sonar-scanner**（降级方案需要）
5. **MCP 工具**（推荐，效率更高）
6. **JDK**（自动启动 SonarQube 需要）

## 关键设计原则

1. **零硬编码**：所有项目参数（端口/路径/阈值/动作）通过配置文件管理，技能本身不含业务参数，所有可变值通过 `${ENV:VAR|default}` 占位符解析
2. **配置分层**：核心通用（core）+ 项目特定（project）+ 业务规则（business）
3. **跨平台**：Windows/Linux/macOS 自动适配
4. **降级保障**：MCP 不可用时自动降级到 sonar-scanner
5. **向后兼容**：旧版 `config/scan_config.json` 自动 fallback
6. **硬约束强制**：通用安全规则（core.json）+ 业务规则（business/*.json）双重保护
7. **框架感知**：通过 `framework_patterns.json` 自动识别 FastAPI/React 等常见框架的误报
8. **修复策略可配置**：按 rule ID 配置 auto_fix/manual_review/skip
9. **不自动变更问题状态**：标记 falsepositive/accept 前必须用户确认
10. **增量扫描**：只扫描新增/修改的文件，不重复扫描全量代码
11. **ES 弹性自愈**：扫描前检测 ES read-only 锁并自动解锁 + 持久化 watermark（v2.1 新增）
12. **NOSONAR 位置查表**：使用 NOSONAR 抑制时按 `nosonar_position_rules` 表查物理行，避免位置错误导致重扫无变化（v2.1 新增）
13. **收敛控制**：`max_scan_iterations` × `target_open_count` 双重控制，避免无限循环（v2.1 新增）
14. **失败映射配置化**：所有失败场景与恢复动作在 `failure_recovery.mappings` 中配置，无硬编码（v2.1 新增）

## 自动化脚本

| 脚本 | 用途 |
|------|------|
| `scripts/detect-platform.ps1` | 平台检测（Windows/Linux/macOS），输出工具可用性 |
| `scripts/invoke-api.ps1` | API 抽象层，封装所有 SonarQube HTTP API 调用 |
| `scripts/start-sonarqube.ps1` | 跨平台服务器检测与启动（-StatusOnly / -ForceRestart） |
| `scripts/verify-connection.ps1` | MCP + 环境变量连接验证 |
| `scripts/run-sonar-scanner.ps1` | MCP 不可用时的降级扫描方案 |
| `scripts/generate-scan-scope.ps1` | 扫描范围自动生成（按关键词与模块） |

## 模板文件

| 模板 | 用途 |
|------|------|
| `assets/subagent-task-template.md` | 并行修复子代理任务模板 |
| `assets/report-template.md` | 标准化扫描报告模板 |
| `assets/issue-tracker-template.md` | 问题跟踪记录模板 |

## 示例项目

| 示例 | 说明 |
|------|------|
| `examples/xianyu-hunter/` | Xianyu Hunter 完整配置（FastAPI + React） |
| `examples/basic-python/` | 最小 Python 项目示例（仅启用 core 硬约束） |
| `examples/react-frontend/` | 纯 React 前端项目示例 |

## 参考文档

| 文档 | 说明 |
|------|------|
| [references/scan-workflow.md](references/scan-workflow.md) | 完整扫描工作流程（含工具选择决策树、API 参数映射、ES 弹性预检、CE 报告轮询、NOSONAR 位置判断、7 种调用模式） |
| [references/issue-classification.md](references/issue-classification.md) | 问题分类与判断标准（按质量维度 + 框架） |
| [references/rule-overrides.md](references/rule-overrides.md) | 规则豁免与误报处理 |
| [references/nosonar-positioning.md](references/nosonar-positioning.md) | NOSONAR 抑制注释位置规则单一可信源（v2.1 新增，9 条规则 + 5 个常见错误 + 修复示例） |

## 配置文件

| 文件 | 说明 |
|------|------|
| `config/core_config.json` | 核心通用配置（v2.1.0，所有项目复用，含 ES 弹性/预检/报告轮询/NOSONAR 校验/失败恢复 5 个新节点） |
| `config/project_config.json` | 项目特定配置（Xianyu 业务配置） |
| `config/fix_strategies.json` | 修复策略表 + NOSONAR 位置规则（v2.2.0，覆盖 top 45+ 规则） |
| `config/framework_patterns.json` | 框架模式库（FastAPI/React/Vue/Django/Spring/Express） |
| `config/hard_constraints/core.json` | 通用安全硬约束 |
| `config/hard_constraints/business/xianyu.json` | Xianyu 业务硬约束 |

## 失败恢复机制

> 所有失败场景与恢复动作的映射在 `core_config.json -> failure_recovery.mappings` 中配置，无硬编码。

1. **服务器启动失败**（`server_status`）：检查 `JAVA_HOME_SONAR`/`SONARQUBE_HOME` 环境变量，恢复后重试
2. **Java 版本不匹配**（`java_version`）：提示用户设置 `JAVA_HOME_SONAR` 指向 Java 17+，不重试
3. **磁盘超 flood_stage**（`disk_space`）：执行 `unlock_es_and_persist_watermark`，恢复后重试
4. **ES 索引被锁**（`es_read_only_block`）：执行 `unlock_es_read_only_block`，恢复后重试
5. **CE 报告处理 FAILED**（`report_processing_failed`）：执行 `check_es_read_only_block`（通常为 ES 锁导致），恢复后重试
6. **SCM blame 缺失**（`scm_blame_missing`）：仅警告，不阻塞扫描
7. **NOSONAR 未生效**（`nosonar_not_effective`）：按 `nosonar_position_rules` 表重新放置 NOSONAR 到正确物理行
8. **SONAR_TOKEN 缺失**（`sonar_token`）：立即终止，输出配置指南（绝不能硬编码）
9. **MCP 连接失败**：自动降级到 `scripts/run-sonar-scanner.ps1`
10. **子代理超时**：主代理接管未完成任务
11. **Edit 冲突**：子代理串行处理同一文件内的多个 issue
12. **验证失败**：输出 diff 供用户决策，不自动回滚

## 与现有工具的关系

- **mcp_sonarqube**：提供 MCP 工具调用（推荐方式）
- **scripts/invoke-api.ps1**：HTTP API 降级方案
- **Task 工具**：用于启动并行修复子代理
- **SearchCodebase**：用于按语义搜索定位代码文件
- **PowerShell 脚本**：提供服务器管理、连接验证、降级扫描等自动化能力

## 安全注意事项

1. **凭据**：SONAR_TOKEN 必须从环境变量读取，禁止写入配置文件
2. **硬编码检测**：`hard_constraints/core.json` 扫描所有项目通用凭据模式
3. **凭据吊销**：若发现已泄露凭据，技能会建议立即吊销并提示操作步骤
4. **报告脱敏**：报告中不包含任何 token、密码等敏感信息
5. **日志脱敏**：敏感字段（如 token 长度）不得记录日志，仅记录布尔匹配结果

## 迁移指南（v1.0 → v2.0）

旧版 `config/scan_config.json` 已标记 deprecated，新版按以下方式迁移：

| v1.0 字段 | v2.0 位置 |
|-----------|-----------|
| `project` | `project_config.json -> project` |
| `sonarqube_server` | `core_config.json -> sonarqube_server` |
| `sonar_scanner` | `core_config.json -> sonar_scanner` |
| `modules` | `project_config.json -> modules` |
| `scan` | `core_config.json -> scan` |
| `priority` | `core_config.json -> priority` |
| `filters` | `core_config.json -> filters` |
| `verify` | `core_config.json -> verify` + `project_config.json -> verify` |
| `report` | `core_config.json -> report` + `project_config.json -> report` |
| `hard_constraints.rules` | `hard_constraints/core.json`（通用）+ `hard_constraints/business/*.json`（业务） |
| `fix_strategies` | `fix_strategies.json`（扩展到 30+ 规则） |
| `xianyu_framework_patterns` | `framework_patterns.json`（多框架支持） |

**脚本行为**：所有脚本自动检测 v1/v2 配置格式，v1 文件存在时输出警告并 fallback。
