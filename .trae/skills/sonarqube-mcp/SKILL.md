---
name: "sonarqube-mcp"
description: "通用 SonarQube 代码质量闭环：扫描→分类→并行修复→验证→报告。适用于任何有 SonarQube 服务的项目（Python/TypeScript/Java/Go）。"
whenToUse: "编码/开发/缺陷修复后调用、用户要求代码质量检查、CI/CD 质量门禁验证、提交前扫描、技术债清理"
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

通用 SonarQube 代码质量闭环技能，对 SonarQube 扫描出的所有问题进行**服务器检测→ES弹性预检→连接验证→扫描→分类→并行修复→NOSONAR位置校验→报告**的完整修复流程。支持任意项目 + 任意语言 + 任意框架组合，内置 ES read-only 锁自愈、CE 报告轮询、NOSONAR 位置校验三大弹性机制。

## 复盘声明（v2.1 沉淀）
> 本节内容基于 2026-07-07 一次完整闭环实战（336 → 0 OPEN，4 轮扫描-修复循环）沉淀。
> 完整复盘与历史案例详见 [CHANGELOG.md](CHANGELOG.md)。

### 12 阶段流程
1. **Phase -1** 服务器检测与启动 → 2. **Phase -0.5** ES 弹性预检 → 3. **Phase 0** 前置检查（5 项预检 + 失败恢复映射） → 4. **Phase 1** MCP 可用性检测与降级 → 5. **Phase 2** 功能模块代码定位 → 6. **Phase 3** 质量门禁检查 → 7. **Phase 4** 问题扫描（分页/过滤/排序） → 8. **Phase 4.5** CE 报告轮询 → 9. **Phase 5** 并行修复（含 NOSONAR 位置判断） → 10. **Phase 6** 验证（重扫+测试+NOSONAR校验+硬约束+收敛判断） → 11. **Phase 7** 报告 → 12. **Phase 8** 问题状态管理（需用户确认）

| 失败场景 | 恢复动作 | 重试 |
|----------|----------|------|
| ES flood_stage → 锁定 | `unlock_es_and_persist_watermark` | ✅ |
| CE 报告 FAILED | `check_es_read_only_block` → 解锁重试 | ✅ |
| NOSONAR 位置错误 | `reposition_nosonar`（按规则表查表） | ✅ |
| Java 版本不匹配 | 提示设置 `JAVA_HOME_SONAR` | ❌ |
| SCM blame 缺失 | `warn_only`（不阻塞） | ❌ |
| sonar-scanner 路径错误 | 环境变量 + 配置占位符解析 | — |

### 关键判断逻辑
1. **预检 → 失败映射 → 恢复**：`precheck.checks` × `failure_recovery.mappings` 配置驱动
2. **修复策略**：`fix_strategies.json` 三档（auto_fix / manual_review / skip），按 rule ID 查表
3. **NOSONAR 位置**：`nosonar_position_rules` 9 条规则，按 rule ID 查表（issue_line / first_param_line / n/a）
4. **收敛判断**：`scan.max_scan_iterations` × `scan.target_open_count` 双重控制
5. **配置占位符**：`${ENV:VAR|default}` 统一语法，运行时解析

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
- 紧急热修复（全量扫描太慢）
- 未部署 SonarQube 服务且无降级能力的环境
- SonarCloud SaaS（ES 由 SonarSource 托管，无需 ES 解锁）

## Skill 职责

| 职责 | 说明 |
|------|------|
| 服务器检测 | 检测 SonarQube 服务状态，自动启动（如需） |
| 弹性预检 | 检测 ES 磁盘水位，自动解锁 read-only 索引 |
| 连接验证 | 验证端口、环境变量、MCP 工具可用性、扫描器 |
| 问题扫描 | 调用 MCP 或降级方案扫描项目，分页获取所有 OPEN 问题 |
| 问题分类 | 按质量维度（SECURITY/RELIABILITY/MAINTAINABILITY）分类 |
| 修复策略 | 按 rule ID 查 `fix_strategies.json` 确定修复策略 |
| 并行修复 | 按文件分组启动子代理，同文件串行防冲突 |
| NOSONAR 校验 | 修复后验证 NOSONAR 位置是否正确 |
| 质量门禁 | 检查 Quality Gate 状态 |
| 报告生成 | 生成 Markdown 报告（含动态压缩） |

## 配置文件分层（v2.1 核心架构）

| 层级 | 文件 | 用途 |
|------|------|------|
| 核心配置 | `config/core_config.json` | 服务器连接/ES弹性/预检/扫描/过滤/验证/失败恢复（所有项目复用） |
| 修复策略 | `config/fix_strategies.json` | 30+ 规则修复模板 + NOSONAR 位置规则表（v2.2.0） |
| 框架模式 | `config/framework_patterns.json` | 6 大框架误报模式库（FastAPI/React/Vue/Django/Spring/Express） |
| 硬约束 | `config/hard_constraints/core.json` | 通用安全规则（14 条） |
| 业务约束 | `config/hard_constraints/business/*.json` | 项目特定业务规则（如 Xianyu） |
| 项目配置 | `config/project_config.json` | 项目特定配置（模块/语言/框架/测试命令） |

> v1.0 `config/scan_config.json` 已标记 deprecated，脚本自动检测并 fallback。

## 快速开始

### 1. 配置环境变量
```powershell
$env:SONAR_TOKEN = "squ_xxxxxxxxxxxxxxxxxx"
$env:SONARQUBE_URL = "http://localhost"  # 可选
$env:SONARQUBE_PORT = "9000"             # 可选
$env:SONAR_PROJECT_KEY = "xianyu_hunter" # 可选
```

### 2. 验证连接
```powershell
.\scripts\verify-connection.ps1
```

### 3. 执行扫描
```powershell
.\scripts\run-sonar-scanner.ps1
```

### 4. 查看报告
报告自动生成在 `docs/sonar-reports/sonar-fix-report-YYYYMMDD-HHmmss.md`

## 工作流（8 阶段闭环 + 弹性预检）

### Phase -1：SonarQube 服务器检测与启动
- 调用 `start-sonarqube.ps1` 检测服务状态
- 如未运行，自动启动（跨平台适配）
- 健康检查端点：`/api/system/status`
- 超时：`core_config.json -> sonarqube_server.startup_timeout_seconds`

### Phase -0.5：Elasticsearch 弹性预检
> v2.1 新增。开发机磁盘紧张时 ES 自动锁定索引，导致 CE 报告 FAILED。
- 检测磁盘水位：`core_config.json -> es_resilience.watermark`
- 如触发 flood_stage，自动解锁 ES 索引 + 持久化 watermark
- API 端口：`core_config.json -> es_resilience.es_api_port`（默认 9001）
- 自动解锁：`core_config.json -> es_resilience.auto_unlock_on_failure`

### Phase 0：前置检查
5 项预检（端口/Java/磁盘/ES状态/配置），失败时按 `failure_recovery.mappings` 自动恢复。

### Phase 1：MCP 可用检测
- 如 MCP 工具不可用，自动降级到 `scripts/run-sonar-scanner.ps1`
- 降级方案同样支持全部 12 阶段流程

### Phase 2：功能模块代码定位
- 从 `project_config.json -> modules` 读取模块定义
- 按 `framework_patterns.json` 识别误报模式
- 支持增量扫描（按功能关键词或路径）

### Phase 3：质量门禁检查
- 调用 `/api/qualitygates/project_status` 检查 Quality Gate
- 阈值配置：`core_config.json -> scan.quality_gate`

### Phase 4：问题扫描
- 调用 MCP 工具或 API 获取所有 OPEN 问题
- 分页处理：`core_config.json -> scan.page_size`
- 过滤：按严重级别/类型/文件路径
- 排序：按 `core_config.json -> priority` 权重

### Phase 4.5：Compute Engine 报告轮询
> v2.1 新增。sonar-scanner 上传报告后 CE 异步处理。
- 轮询间隔：`core_config.json -> report_polling.poll_interval_seconds`
- 最大尝试：`core_config.json -> report_polling.max_attempts`
- 终态：SUCCESS / FAILED / CANCELED
- FAILED 时触发 `failure_recovery.mappings[report_processing_failed]`

### Phase 5：并行修复
- 按文件分组，每组启动一个子代理
- 同文件内多个 issue 串行处理（防 Edit 冲突）
- 每个子代理分配 `core_config.json -> scan.files_per_agent` 个文件
- 修复策略从 `fix_strategies.json` 查表确定

### Phase 6：验证
1. **重扫**：调用 `/api/ce/create` 重新扫描修复后的代码
2. **测试**：执行 `project_config.json -> verify.test_command`
3. **NOSONAR 校验**：如 OPEN 数未下降，按 `nosonar_position_rules` 重新定位
4. **硬约束检查**：扫描 `hard_constraints/core.json` 中的所有 pattern
5. **收敛判断**：如达到 `scan.max_scan_iterations` 或 `scan.target_open_count`，终止循环

### Phase 7：报告
- 生成 Markdown 报告，保存到 `core_config.json -> report.output_dir`
- 报告模板：`assets/report-template.md`
- 动态生成规则见下文

### Phase 8：问题状态管理
- 对确认误报的问题，调用 `change_sonar_issue_status(issueKey, "falsepositive", comment)`
- 对可接受债务的问题，调用 `change_sonar_issue_status(issueKey, "accept", comment)`
- 需用户确认后才执行状态变更

## 前置要求

- SonarQube 服务（本地/云端/SonarCloud）
- SONAR_TOKEN 环境变量
- sonar-scanner（MCP 不可用时作为降级方案）
- Java 17+（SonarQube 26 需要）
- 项目代码已检出到工作目录

## 关键设计原则

1. **配置驱动**：所有参数通过配置文件管理，无硬编码
2. **环境隔离**：凭据从环境变量读取，不写入配置文件
3. **降级容错**：MCP 不可用时自动降级到命令行方案
4. **弹性恢复**：失败时按映射表自动恢复，不阻塞流程
5. **跨平台**：支持 Windows/Linux/macOS，自动适配路径和命令
6. **渐进式**：支持增量扫描和模块化配置

## 自动化脚本

| 脚本 | 用途 | 入口 |
|------|------|------|
| `scripts/start-sonarqube.ps1` | 服务器检测与启动 | `.\scripts\start-sonarqube.ps1` |
| `scripts/verify-connection.ps1` | 连接验证（端口/环境变量/MCP/扫描器） | `.\scripts\verify-connection.ps1` |
| `scripts/run-sonar-scanner.ps1` | 降级扫描器 | `.\scripts\run-sonar-scanner.ps1` |
| `scripts/generate-scan-scope.ps1` | 扫描范围生成 | `.\scripts\generate-scan-scope.ps1 -Keyword "xxx"` |
| `scripts/invoke-api.ps1` | API 抽象层 | `.\scripts\invoke-api.ps1; Invoke-SonarApi -Endpoint ...` |
| `scripts/detect-platform.ps1` | 平台检测 | `.\scripts\detect-platform.ps1; Get-Platform` |

## 模板文件

| 模板 | 用途 |
|------|------|
| [assets/report-template.md](assets/report-template.md) | 扫描报告模板（含动态生成规则） |
| [assets/issue-tracker-template.md](assets/issue-tracker-template.md) | 问题追踪记录模板 |
| [assets/subagent-task-template.md](assets/subagent-task-template.md) | 并行修复子代理任务模板 |

## 示例项目

| 项目 | 说明 |
|------|------|
| [examples/xianyu-hunter/](examples/xianyu-hunter/) | Xianyu Hunter（FastAPI + React，完整配置） |
| [examples/basic-python/](examples/basic-python/) | 最简 Python 项目配置 |
| [examples/react-frontend/](examples/react-frontend/) | 纯前端 React 项目配置 |

## 参考文档

| 文档 | 说明 |
|------|------|
| [references/scan-workflow.md](references/scan-workflow.md) | 完整扫描工作流程（含工具选择决策树、API 参数映射、ES 弹性预检、CE 报告轮询、NOSONAR 位置判断、7 种调用模式） |
| [references/issue-classification.md](references/issue-classification.md) | 问题分类与判断标准（按质量维度 + 框架） |
| [references/rule-overrides.md](references/rule-overrides.md) | 规则豁免与误报处理 |
| [references/nosonar-positioning.md](references/nosonar-positioning.md) | NOSONAR 抑制注释位置规则单一可信源（v2.1 新增，9 条规则 + 5 个常见错误 + 修复示例） |

## 上下文加载规则（Token 优化）

> 以下规则指导智能体在不同阶段加载哪些参考文档，避免全量加载到初始上下文窗口。

| 阶段 | 加载内容 | 跳过内容 |
|------|----------|----------|
| Phase -1 ~ 1 | SKILL.md + core_config.json | references/ 目录 |
| Phase 2 ~ 3 | + framework_patterns.json（按项目模块） | fix_strategies.json 全文 |
| Phase 4 | + issue-classification.md | nosonar-positioning.md |
| Phase 4.5 | + report_polling 配置 | 其他 |
| Phase 5 | + fix_strategies.json（仅 active_rules）+ nosonar-positioning.md | scan-workflow.md 全文 |
| Phase 6 | + hard_constraints/core.json | 其他 |
| Phase 7 | + report-template.md（条件化） | 其他 |
| Phase 8 | 按需加载 | 其他 |

### fix_strategies.json 子集加载
Phase 5 修复时，仅加载与当前扫描结果相关的规则：
1. 从扫描结果中提取涉及的 rule ID 集合
2. 从 fix_strategies.json 中仅提取这些 rule 对应的策略条目
3. 将子集注入子代理 prompt

示例：若扫描结果涉及 python:S1481, python:S125, typescript:S6488
则 fix_strategies.json 加载内容从 528 行缩减至 ~30 行。

## 报告动态生成规则（Token 优化）

> 报告只输出有实际内容的部分，空表格和未触发的检查项不生成。

### 生成规则
1. **质量门禁**：所有指标达标时，输出一行摘要；仅当有未达标项时展开详细表格
2. **问题统计**：仅输出有实际数据的严重级别和维度
3. **问题详情**：BLOCKER/CRITICAL 级别单独成节；MINOR/INFO 合并为一节
4. **硬约束合规**：全部通过时输出 `✅ 硬约束: N/N 通过`；有违规时展开检查表
5. **修复建议**：使用紧凑格式（规则ID + 文件:行 + 级别 + 策略 + 状态）
6. **修复结果**：仅输出实际修复/跳过的问题，不输出空表格

### 紧凑格式示例
| # | 规则 | 文件:行 | 级别 | 策略 | 状态 |
|---|------|---------|------|------|------|
| 1 | python:S1481 | src/api/routes.py:42 | MAJOR | auto_fix | ✅ 已修复 |
| 2 | python:S125 | src/services/collector.py:15 | MINOR | auto_fix | ✅ 已修复 |
| 3 | typescript:S6488 | frontend/App.tsx:23 | MAJOR | manual_review | ⏳ 待审核 |

**总计**：修复 2/3，待审 1/3，跳过 0/3

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
