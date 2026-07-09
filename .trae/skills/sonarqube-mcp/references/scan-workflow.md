# SonarQube 扫描工作流程（通用版）

> 本文件是 SonarQube 扫描工作流的单一信息源，整合了工具选择决策树、参数映射、API 错误表、ES 弹性恢复、报告轮询、NOSONAR 位置判断等内容。SKILL.md Phase -1 ~ Phase 8 的详细步骤均见本文件。
>
> **配置文件分层**（v2.0+）：
> - `config/core_config.json` — 通用配置（与项目无关），所有 `${ENV:VAR|default}` 占位符运行时解析
> - `config/project_config.json` — 项目特定配置（项目 key、模块、测试命令等）
> - `config/fix_strategies.json` — 修复策略表 + NOSONAR 位置规则表
> - 旧文件 `config/scan_config.json` 已废弃，仅作兼容

---

## 工具选择决策树

```
用户想要...
├── 验证 MCP 连接是否可用
│   └── search_my_sonarqube_projects (q="xianyu")
│
├── 检查项目是否通过质量门禁
│   └── get_project_quality_gate_status (projectKey="xianyu_hunter")
│
├── 扫描项目中的问题
│   ├── 按严重级别扫描
│   │   └── search_sonar_issues_in_projects (projects + severities)
│   ├── 按文件扫描
│   │   └── search_sonar_issues_in_projects (projects + files)
│   ├── 按类型扫描
│   │   └── search_sonar_issues_in_projects (projects + types)
│   └── 按PR扫描
│       └── search_sonar_issues_in_projects (projects + pullRequestId)
│
├── 分析代码片段
│   └── analyze_code_snippet (projectKey + fileContent + language)
│
├── 查看规则详情
│   └── show_rule (key)
│
├── 获取项目度量
│   └── get_component_measures (projectKey + metricKeys)
│
├── 变更问题状态
│   └── change_sonar_issue_status (key + status + comment)
│
├── 查看质量门禁列表
│   └── list_quality_gates
│
├── 安全热点相关
│   ├── 搜索安全热点
│   │   └── search_security_hotspots (projectKey)
│   └── 查看安全热点详情
│       └── show_security_hotspot (hotspotKey)
│
├── 代码覆盖率相关
│   ├── 按文件搜索覆盖率
│   │   └── search_files_by_coverage (projectKey)
│   └── 获取文件覆盖率详情
│       └── get_file_coverage_details (projectKey + file)
│
├── 重复代码相关
│   ├── 搜索重复代码块
│   │   └── get_duplications (projectKey + file)
│   └── 搜索重复文件
│       └── search_duplicated_files (projectKey)
│
└── PR 相关
    ├── 列出 PR
    │   └── list_pull_requests (projectKey)
    └── 分析代码片段（PR 上下文）
        └── analyze_code_snippet (projectKey + fileContent + language)
```

---

## 项目参数映射

### 项目 Key

项目 Key 通过 `config/project_config.json -> project.key` 配置，支持环境变量占位符 `${ENV:SONAR_PROJECT_KEY|default}`。

| 项目 | Key | 用途 |
|------|-----|------|
| Xianyu Hunter | `${ENV:SONAR_PROJECT_KEY|xianyu_hunter}` | 示例项目（FastAPI 后端 + React 前端） |

> **通用化说明**：本文档示例以 Xianyu Hunter 为参考，但所有项目特定的 key/path 都通过 `project_config.json` 注入，复用此工作流时仅需修改 `project_config.json`，无需改动本文档。

### 常用度量指标组合

**项目健康度**：`["coverage", "bugs", "vulnerabilities", "code_smells", "ncloc", "duplicated_lines_density"]`

**新代码质量**：`["new_coverage", "new_bugs", "new_vulnerabilities", "new_duplicated_lines_density", "new_violations"]`

**复杂度评估**：`["complexity", "cognitive_complexity", "ncloc", "functions"]`

**安全指标**：`["security_rating", "security_hotspots", "vulnerabilities", "new_security_violations"]`

### 严重级别过滤值映射

**API参数只接受以下值**：`["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]`

> **重要**：HIGH/MEDIUM/LOW 是旧版标签，不能用于 API 参数过滤。
> - HIGH → 使用 CRITICAL
> - MEDIUM → 使用 MAJOR
> - LOW → 使用 MINOR

### 问题类型过滤值

`["BUG", "VULNERABILITY", "CODE_SMELL", "SECURITY_HOTSPOT"]`

### 问题状态过滤值

`["OPEN", "CONFIRMED", "REOPENED", "RESOLVED", "CLOSED"]`

---

## analyze_code_snippet 注意事项

### scope 参数

只接受以下两个值（注意不能有空格或换行）：
- `MAIN` — 主代码
- `TEST` — 测试代码

### language 参数

Xianyu 项目使用：
- `python` — 后端代码
- `typescript` — 前端代码
- `javascript` — 前端代码（部分）

### 常见错误

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| Invalid scope | scope 值包含空格或换行 | 确保值为纯 `MAIN` 或 `TEST` |
| Insufficient privileges | Token 权限不足 | 检查 SONAR_TOKEN 权限 |
| Project not found | 项目 Key 错误 | 确认项目 Key 为 `xianyu_hunter` |
| Language not supported | language 值错误 | 使用 `python` 或 `typescript` |

---

## 搜索问题参数速查

### 按文件过滤

```json
{
  "projects": ["xianyu_hunter"],
  "files": ["xianyu_hunter:api/evaluations.py"],
  "issueStatuses": ["OPEN"],
  "severities": ["BLOCKER", "CRITICAL", "MAJOR"]
}
```

### 按规则类型过滤

```json
{
  "projects": ["xianyu_hunter"],
  "types": ["VULNERABILITY", "BUG"],
  "issueStatuses": ["OPEN"]
}
```

### 按严重级别分页查询

```json
{
  "projects": ["xianyu_hunter"],
  "severities": ["BLOCKER", "CRITICAL"],
  "issueStatuses": ["OPEN"],
  "p": 1,
  "ps": 500
}
```

检查 `paging.hasNextPage` 判断是否需要继续翻页。

### 仅扫描前端问题

```json
{
  "projects": ["xianyu_hunter"],
  "files": ["xianyu_hunter:frontend/src/**"],
  "issueStatuses": ["OPEN"]
}
```

### 仅扫描后端问题

```json
{
  "projects": ["xianyu_hunter"],
  "files": ["xianyu_hunter:api/**", "xianyu_hunter:services/**", "xianyu_hunter:core/**"],
  "issueStatuses": ["OPEN"]
}
```

---

## Phase -1: SonarQube 服务器检测与启动（前置条件）

**目标**：确保本地 SonarQube 服务已启动，这是所有后续扫描操作的前置条件

### -1.1 读取服务器配置

读取 `config/core_config.json` → `sonarqube_server` 节点，获取：java_home、install_path、start_script、port、host、startup_timeout_seconds。所有 `${ENV:VAR_NAME|default}` 占位符运行时从环境变量解析，未设置时使用 default。

### -1.2 检测服务状态

**方式一：Agent 自动检测（推荐）**

```powershell
cd d:\code\otherProjects\17_xianyu\.trae\skills\sonarqube-mcp\scripts
.\start-sonarqube.ps1 -StatusOnly
```

退出码 0 = 服务已运行且健康；退出码 1 = 服务未运行或不健康。

**方式二：手动检测**

```powershell
# 端口检测
Test-NetConnection -ComputerName localhost -Port 9000

# 健康检查
Invoke-WebRequest -Uri "http://localhost:9000/api/system/status" -UseBasicParsing
```

### -1.3 自动启动流程

如果服务未运行，Agent 执行：

```powershell
cd d:\code\otherProjects\17_xianyu\.trae\skills\sonarqube-mcp\scripts
.\start-sonarqube.ps1
```

脚本内部流程：
1. 解析 `${ENV:JAVA_HOME_SONAR}` 设置 JAVA_HOME
2. 设置 PATH = %JAVA_HOME%\bin;%PATH%
3. 启动 StartSonar.bat（在新窗口中）
4. 轮询健康检查接口，最长等待 startup_timeout_seconds
5. 返回启动结果

**启动脚本核心逻辑**：
- 端口检测：优先 `Get-NetTCPConnection`，回退 `netstat`
- 进程验证：检测端口占用的进程名是否为 java
- 健康检查：HTTP GET `/api/system/status`，判断 `status == "UP"`
- 超时机制：默认 120 秒，每 5 秒检查一次
- 进度显示：实时显示启动进度百分比

### -1.4 启动验证标准

| 检查项 | 预期结果 | 判定 |
|--------|----------|------|
| 端口 9000 监听 | LISTENING | ✅/❌ |
| 健康检查接口 | status: "UP" | ✅/❌ |
| MCP 工具可用 | search_my_sonarqube_projects 返回正常 | ✅/❌ |

### -1.5 启动失败排查

| 现象 | 可能原因 | 排查方法 |
|------|----------|----------|
| 端口未监听 | Java 未安装或路径错误 | 检查 `JAVA_HOME_SONAR` 环境变量是否设置 |
| 端口被占用 | 其他程序占用 9000 端口 | `netstat -ano \| findstr 9000` |
| 健康检查失败 | SonarQube 正在启动中 | 等待更长时间或查看日志 |
| 启动超时 | 内存不足或配置错误 | 查看 `install_path/logs/sonar.log` |

**日志路径**：`{install_path}/logs/sonar.log`

### -1.6 强制重启

当 SonarQube 状态异常需要重启时：

```powershell
.\start-sonarqube.ps1 -ForceRestart
```

脚本会先停止现有进程，再重新启动。

---

## Phase -0.5: Elasticsearch 弹性预检与解锁

**目标**：在扫描前检测并解除 ES read-only 锁，防止 Compute Engine 报告处理失败

> **背景**：SonarQube 内嵌 Elasticsearch 在磁盘使用率超过 `flood_stage` watermark 时，会自动将索引标记为 `read_only_allow_delete`，导致后续扫描的报告处理失败（CE task FAILED）。本阶段作为弹性预检，在每次扫描前执行。

### -0.5.1 读取 ES 弹性配置

读取 `config/core_config.json` → `es_resilience` 节点：
- `es_api_port`（默认 `${ENV:SONAR_ES_PORT|9001}`）
- `es_api_host`（默认 `127.0.0.1`）
- `watermark`（low/high/flood_stage 阈值）
- `unlock_apis`（解锁 API 调用配置）
- `auto_unlock_on_failure`（失败时是否自动解锁）

### -0.5.2 检测 ES read-only 锁

```powershell
# 通过 ES REST API 检查索引是否被锁
$esPort = "9001"  # 从 core_config.json -> es_resilience.es_api_port 解析
$esHost = "127.0.0.1"
$response = Invoke-RestMethod -Uri "http://${esHost}:${esPort}/_cluster/health"
if ($response.blocks -match "read_only_allow_delete") {
    # 索引被锁，需解锁
}
```

### -0.5.3 解除 read-only 锁

按 `es_resilience.unlock_apis.remove_read_only_block` 配置执行：

```powershell
$esPort = "9001"
$body = @{ "index.blocks.read_only_allow_delete" = $null } | ConvertTo-Json
Invoke-RestMethod -Method PUT -Uri "http://127.0.0.1:${esPort}/_settings" -Body $body -ContentType "application/json"
```

### -0.5.4 持久化 watermark 阈值

按 `es_resilience.unlock_apis.persist_watermark` 配置执行（避免重启后再次触发锁）：

```powershell
$body = @{
    persistent = @{
        "cluster.routing.allocation.disk.watermark.low" = "95%"
        "cluster.routing.allocation.disk.watermark.high" = "97%"
        "cluster.routing.allocation.disk.watermark.flood_stage" = "99%"
    }
} | ConvertTo-Json -Depth 3
Invoke-RestMethod -Method PUT -Uri "http://127.0.0.1:${esPort}/_cluster/settings" -Body $body -ContentType "application/json"
```

> **注意**：阈值从 `es_resilience.watermark` 读取，不要硬编码。开发机磁盘紧张时建议提高到 95%/97%/99%。

### -0.5.5 配置文件路径陷阱

SonarQube 内嵌 ES 的配置文件实际位置在 `data/es8/config/elasticsearch.yml`，而非传统的 `elasticsearch/config/elasticsearch.yml`（后者是诱饵路径，启动时被覆盖）。**因此 watermark 设置必须通过 ES REST API 持久化，不能直接改 yml 文件**。详细路径见 `es_resilience.config_file_paths`。

### -0.5.6 失败恢复动作映射

按 `core_config.json -> failure_recovery.mappings` 查找：

| 失败场景 | 恢复动作 | 是否重试 |
|---------|---------|---------|
| `disk_space`（磁盘超 flood_stage） | `unlock_es_and_persist_watermark` | ✅ |
| `es_read_only_block`（索引被锁） | `unlock_es_read_only_block` | ✅ |
| `report_processing_failed`（CE 报告 FAILED） | `check_es_read_only_block` | ✅ |

### -0.5.7 不适用场景

- SonarCloud SaaS：ES 由 SonarSource 托管，无需解锁
- 远程 SonarQube 服务（无本地 ES 访问权限）：仅记录警告，提示联系管理员
- 首次扫描且磁盘空间充足：跳过本阶段（通过 `precheck.checks[disk_space]` 判断）

---

## Phase 0: 前置检查（Pre-flight）

**目标**：验证环境与连接就绪

1. 读取 `config/core_config.json` 通用配置 + `config/project_config.json` 项目配置
2. 执行 `precheck.checks` 中的 5 项预检（server_status / java_version / disk_space / es_read_only_block / sonar_token）
3. 任一预检失败时，按 `failure_recovery.mappings` 查找恢复动作并执行
4. 验证 SONAR_TOKEN 环境变量存在（不存在则 `terminate_with_guide`，绝不能硬编码 token）
5. 验证 sonarqube_server.host 可达（GET /api/system/status）
6. 验证 sonar_scanner.scanner_bin 可执行（降级方案需要）

**连接验证脚本**：

```powershell
cd d:\code\otherProjects\17_xianyu\.trae\skills\sonarqube-mcp\scripts
.\verify-connection.ps1
```

**判断逻辑**：凭据必须从环境变量读取，禁止从配置文件硬编码。

---

## Phase 1: MCP 可用性检测与降级处理

> **重要**：当 SonarQube MCP 工具不可用时，不得跳过智能体，必须执行降级处理。

### 1.1 检测 MCP 可用性

1. 检查当前项目 MCP 服务器列表是否包含 `mcp_sonarqube`
2. MCP 可用 → 使用 MCP 工具执行扫描
3. MCP 不可用 → 执行降级处理

### 1.2 MCP 可用时的操作

- 调用 `search_my_sonarqube_projects` 确认 MCP 连接
- 确认目标项目存在（项目 key 从 `project_config.json -> project.key` 读取）
- 读取 `config/core_config.json` + `config/project_config.json` 获取配置

### 1.3 MCP 不可用时（降级处理）

```
1. 输出 core_config.json -> mcp_check.fallback_message 配置的警告
2. 读取 core_config.json -> sonar_scanner 获取 scanner 配置
3. 生成 sonar-project.properties 配置文件
4. 执行 scripts/run-sonar-scanner.ps1 作为降级方案
5. 扫描完成后，通过 HTTP API 验证结果上传到 SonarQube Web 界面
6. 输出引导用户配置 MCP 的建议
```

**降级执行命令（Agent 执行）**：

```powershell
cd d:\code\otherProjects\17_xianyu\.trae\skills\sonarqube-mcp\scripts
.\run-sonar-scanner.ps1 -ProjectKey "${ENV:SONAR_PROJECT_KEY|xianyu_hunter}" -Sources "."
```

### 1.4 降级方案限制

降级方案（sonar-scanner 命令行）相比 MCP 方案的限制：
- 无法使用 `analyze_code_snippet` 进行代码片段分析
- 无法使用 `change_sonar_issue_status` 变更问题状态
- 需要通过 HTTP API 模拟 MCP 工具调用
- 并行修复能力受限（需通过 HTTP API 获取问题列表）

---

## Phase 2: 功能模块代码定位

**目标**：根据用户描述的功能模块，定位需要扫描的 Python/TypeScript 文件

### 2.1 使用 SearchCodebase

```
调用 SearchCodebase(information_request="功能关键词", target_directories=[".", "frontend/src"])
```

### 2.2 或使用扫描范围生成脚本

```powershell
cd d:\code\otherProjects\17_xianyu\.trae\skills\sonarqube-mcp\scripts
.\generate-scan-scope.ps1 -Keyword "evaluation" -Module "all"
.\generate-scan-scope.ps1 -Keyword "auth" -Module "backend"
.\generate-scan-scope.ps1 -Keyword "useAutoLiveSearch" -Module "frontend"
```

### 2.3 文件分类标准

#### 后端（Python / FastAPI）

| 层级 | 路径模式 | 扫描优先级 |
|------|----------|-----------|
| api | `api/**/*.py` | 高 |
| services | `services/**/*.py` | 高 |
| core | `core/**/*.py` | 高 |
| models | `models/**/*.py` | 中 |
| web | `web/**/*.py` | 中 |
| utils | `utils/**/*.py` | 中 |
| config | `config/**/*.py` | 低 |

#### 前端（TypeScript / React）

| 层级 | 路径模式 | 扫描优先级 |
|------|----------|-----------|
| pages | `frontend/src/pages/**/*.tsx` | 高 |
| components | `frontend/src/components/**/*.tsx` | 高 |
| hooks | `frontend/src/hooks/**/*.ts` | 高 |
| services | `frontend/src/services/**/*.ts` | 中 |
| store | `frontend/src/store/**/*.ts` | 中 |
| utils | `frontend/src/utils/**/*.ts` | 中 |
| types | `frontend/src/types/**/*.ts` | 低 |

**输出**：文件清单表格，包含文件路径、行数、层级、模块

---

## Phase 3: 质量门禁检查

**目标**：验证项目整体是否通过质量门禁

```
调用 get_project_quality_gate_status(projectKey="xianyu_hunter")
```

**门禁条件解读**：

| 条件指标 | 含义 | 阈值 | 判定逻辑 |
|----------|------|------|----------|
| new_coverage | 新代码测试覆盖率 | ≥80% | 低于阈值失败 |
| new_duplicated_lines_density | 新代码重复率 | ≤3% | 高于阈值失败 |
| new_violations | 新增问题数 | 0 | 大于阈值失败 |
| new_security_violations | 新增安全问题数 | 0 | 大于阈值失败 |

**输出格式**：

```
## 质量门禁状态：✅ 通过 / ❌ 未通过

| 指标 | 当前值 | 阈值 | 状态 |
|------|--------|------|------|
| 新代码覆盖率 | 0.0% | ≥80% | ❌ |
| 新代码重复率 | 18.6% | ≤3% | ❌ |
| 新增问题数 | 48 | 0 | ❌ |
```

---

## Phase 4: 问题扫描

**目标**：扫描新增代码中的 SonarQube 问题

### 4.1 项目级问题搜索

```
调用 search_sonar_issues_in_projects(
  projects=["${ENV:SONAR_PROJECT_KEY|xianyu_hunter}"],
  severities=["BLOCKER", "CRITICAL", "MAJOR"],
  issueStatuses=["OPEN"],
  ps=500,
  p=1
)
```

> 项目 key 通过 `project_config.json -> project.key` 注入，severities/types/statuses 通过 `core_config.json -> scan` 节点配置。

### 4.2 文件级代码片段分析

```
对每个核心文件：
1. 读取文件内容
2. 调用 analyze_code_snippet(
     projectKey="${ENV:SONAR_PROJECT_KEY|xianyu_hunter}",
     fileContent=<文件内容>,
     language="python" 或 "typescript"
   )
```

**注意**：`analyze_code_snippet` 的 `scope` 参数只接受 `MAIN` 或 `TEST`，不能有空格或换行。

### 4.3 分页处理

```
如果返回结果中 paging.hasNextPage == true：
  继续调用 search_sonar_issues_in_projects(p=下一页码)
```

### 4.4 严重级别过滤值映射

**API参数只接受以下值**：`["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]`

> 注意：HIGH/MEDIUM/LOW 是旧版标签，不能用于 API 参数过滤。
> HIGH → 使用 CRITICAL，MEDIUM → 使用 MAJOR，LOW → 使用 MINOR

### 4.5 误报过滤

应用 `core_config.json` → `filters`：
- 路径过滤：ignore_paths 匹配的文件跳过
- 规则过滤：ignore_rules 中的规则 ID 跳过
- 测试文件降级：测试文件中 ignore_severity_in_tests 内的 severity 跳过
- 生成代码过滤：含 `// @generated` 或 `# @generated` 注释的文件跳过

### 4.6 排序与截取

1. 按 `priority.severity_order` 和 `priority.type_order` 排序
2. 按文件路径分组（同目录的文件分到同组，便于上下文复用）
3. 截取 `priority.max_fix_per_run` 个最高优先级问题
4. 过滤掉 `priority.fix_threshold` 以下的问题（仅记录不修复）

---

## Phase 4.5: Compute Engine 报告轮询

**目标**：sonar-scanner 上传报告后，等待 Compute Engine 异步处理完成，避免读取到旧数据

> **背景**：sonar-scanner 完成代码分析后，将报告上传到 SonarQube，由 Compute Engine 异步处理。若立即查询 issues API，可能读取到处理前的旧数据，导致 OPEN 数与实际不符。

### 4.5.1 获取 CE task ID

sonar-scanner 命令行输出末尾会包含 `task?id=AXxxxxxxx` 形式的 task ID。降级方案通过 HTTP API 触发扫描时，从响应体中提取。

### 4.5.2 轮询 CE task 状态

按 `core_config.json` → `report_polling` 节点配置执行：

```powershell
$taskId = "AXxxxxxxx"
$pollInterval = 5  # poll_interval_seconds
$maxAttempts = 80  # max_poll_attempts
$terminalStatuses = @("SUCCESS", "FAILED", "CANCELED")

for ($i = 0; $i -lt $maxAttempts; $i++) {
    $resp = Invoke-RestMethod -Uri "http://localhost:9000/api/ce/task?id=$taskId"
    $status = $resp.task.status
    if ($terminalStatuses -contains $status) {
        if ($status -eq "SUCCESS") { break }
        elseif ($status -eq "FAILED") {
            # 按 failure_recovery.mappings[report_processing_failed] 处理
            # 通常是 ES read-only 锁导致，触发 -0.5 阶段的解锁流程
        }
        elseif ($status -eq "CANCELED") { throw "扫描被取消" }
    }
    Start-Sleep -Seconds $pollInterval
}
```

### 4.5.3 FAILED 时的恢复动作

按 `failure_recovery.mappings` 中 `report_processing_failed` 条目：
1. 执行 `check_es_read_only_block` 动作
2. 若发现锁，回到 Phase -0.5 执行解锁流程
3. 解锁后重试扫描（`retry_after: true`）

### 4.5.4 不适用场景

- 使用 MCP `search_sonar_issues_in_projects` 直接查询（不依赖 CE 处理）：跳过本阶段
- 项目极小（< 10 文件），CE 处理 < 5 秒：可一次轮询后立即查询

---

## Phase 5: 并行修复

**目标**：对扫描到的问题进行并行修复

### 5.1 并行判断逻辑

- 文件组数 > 1 且 `scan.parallel_agents` > 1：启用并行子代理
- 文件组之间无依赖（不同模块/目录）：可并行
- 同一文件内多个 issue：串行处理（避免 Edit 冲突）

### 5.2 子代理任务模板

详见 [assets/subagent-task-template.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/sonarqube-mcp/assets/subagent-task-template.md)。

### 5.3 修复策略

按 rule ID 配置（`config/fix_strategies.json` → `strategies`）：
- `auto_fix`：可自动修复，子代理直接执行
- `manual_review`：需人工审查，子代理输出建议供用户决策
- `skip`：跳过修复，仅记录

### 5.4 NOSONAR 位置判断（抑制注释场景）

当修复策略为"使用 NOSONAR 抑制"时，子代理必须先查表确定 NOSONAR 应放置的物理行，否则会因位置错误导致重扫后 OPEN 数不下降。

**判断流程**：

1. 读取 `config/fix_strategies.json` → `nosonar_position_rules`，查找 issue.rule 对应的位置规则
2. 按规则确定 NOSONAR 应放置的物理行：
   - `issue_line`：放在 SonarQube 报告的 issue.line 所在物理行末尾
   - `first_param_line`：放在函数第一个参数所在物理行末尾（S107 报参数行不报 def 行）
   - `def_line`：放在函数定义行末尾
3. 确定注释格式（语言相关）：
   - Python：`# NOSONAR`（必须大写）
   - TypeScript/JavaScript 标签外：`// NOSONAR`
   - JSX 标签内：`/* NOSONAR */`（`//` 会被解析为字符串）
4. 子代理修复后，主代理在 Phase 6 验证 NOSONAR 是否生效；若未生效（OPEN 数未下降），按 `failure_recovery.mappings[nosonar_not_effective]` → `reposition_nosonar` 重新放置

**单一可信源文档**：完整的 NOSONAR 位置规则、常见错误、修复示例见 [references/nosonar-positioning.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/sonarqube-mcp/references/nosonar-positioning.md)。

**关键约束**（来自历次扫描的实战经验）：
- `# NOSONAR` 必须大写，小写 `# nosonar` 不生效
- Python 的 `# noqa` SonarQube 默认不识别，必须用 `# NOSONAR`
- docstring 字符串内的 NOSONAR 不生效，需先转为 `#` 注释
- S107 报的是参数行不是 def 行，S7483 报的是 timeout 参数行

---

## Phase 6: 验证（Verify）

**目标**：修复后验证修复效果

### 6.1 重新扫描验证

```
若 verify.rescan_after_fix=true：重新执行扫描
对比修复前后的 issue 数量
```

### 6.2 测试运行

```
若 verify.run_tests_after_fix=true：
  - 后端测试：运行 project_config.json -> verify.test_commands.backend（如 pytest tests/）
  - 前端测试：运行 project_config.json -> verify.test_commands.frontend（如 cd frontend && npm test）
```

> 注意：PowerShell 用 `;` 分隔命令，不支持 `&&`。test_commands 分模块配置，避免单一命令拼接。

### 6.3 NOSONAR 位置校验

```
若 verify.validate_nosonar_position=true 且重扫后 OPEN 数未下降：
1. 按 nosonar_validation.common_mistakes 检查 NOSONAR 是否放错位置
2. 按 fix_strategies.json -> nosonar_position_rules 查表确定正确位置
3. 重新放置 NOSONAR 到正确物理行
4. 重新扫描验证
```

### 6.4 硬约束合规性检查

```
遍历 config/hard_constraints/*.json，对每条规则扫描代码库
违规项写入报告，若 block_on_violation=true 则阻止合并
```

### 6.5 新问题处理

```
若 verify.fail_on_new_issues=true 且发现新问题：
  - 输出新问题清单
  - 建议回滚或继续修复
```

### 6.6 收敛判断

按 `core_config.json -> scan` 节点配置：
- `target_open_count`：收敛目标（默认 0），达到则提前结束
- `max_scan_iterations`：扫描-修复-重扫最大循环次数（默认 5），超过则输出剩余问题清单并终止

---

## Phase 7: 报告

**目标**：输出标准化扫描报告

**使用模板**：`assets/report-template.md`

**报告结构**（详细字段映射见模板内注释）：
1. 扫描概览（项目、扫描范围、时间）
2. 质量门禁状态
3. 问题统计（按类别/级别汇总）
4. 问题详情列表
5. 修复建议
6. 硬约束合规性检查
7. 代码亮点（零问题文件值得表扬）

---

## Phase 8: 问题状态管理

**目标**：对确认的误报或可接受债务进行状态变更

```
调用 change_sonar_issue_status(
  key=问题ID,
  status="falsepositive" | "accept",
  comment="变更原因说明"
)
```

**原则**：
- 必须用户明确确认后才能变更状态
- 必须填写 comment 说明原因
- 安全类问题（SECURITY）不得标记为 falsepositive，除非经过团队评审

---

## 工具调用顺序模式

> 以下示例中 `${PROJECT_KEY}` 代表 `project_config.json -> project.key` 解析后的项目 key。

### 模式1：功能模块扫描（最常用）

```
0. 执行 scripts/start-sonarqube.ps1 → 确保服务器已启动
0.5. 执行 ES 弹性预检（Phase -0.5）→ 解除 read-only 锁（如需要）
1. search_my_sonarqube_projects → 验证连接
2. SearchCodebase 或 generate-scan-scope.ps1 → 定位文件
3. get_project_quality_gate_status → 检查门禁
4. search_sonar_issues_in_projects → 扫描问题
4.5. 轮询 CE task 状态（若使用 sonar-scanner 降级方案）
5. analyze_code_snippet → 逐文件分析
6. show_rule → 查看规则详情（可选）
7. 输出报告
```

### 模式2：提交前快速检查

```
0. 执行 scripts/start-sonarqube.ps1 -StatusOnly → 检查服务器状态
1. get_project_quality_gate_status → 检查门禁
2. search_sonar_issues_in_projects(severities=["BLOCKER","CRITICAL"]) → 扫描高危问题
3. 输出结果
```

### 模式3：问题修复验证

```
0. 执行 scripts/start-sonarqube.ps1 -StatusOnly → 检查服务器状态
1. analyze_code_snippet → 分析修复后的代码
2. search_sonar_issues_in_projects → 确认问题已关闭
3. get_project_quality_gate_status → 验证门禁改善
4. 输出对比报告
```

### 模式4：安全审计

```
0. 执行 scripts/start-sonarqube.ps1 → 确保服务器已启动
1. search_sonar_issues_in_projects(types=["VULNERABILITY"]) → 扫描安全漏洞
2. search_security_hotspots → 检查安全热点
3. show_rule → 获取每个漏洞的详情
4. 输出安全报告
```

### 模式5：并行修复（推荐用于大规模清零）

```
0. 执行 scripts/start-sonarqube.ps1 → 确保服务器已启动
0.5. 执行 ES 弹性预检 → 解除 read-only 锁（如需要）
1. search_sonar_issues_in_projects → 拉取所有 OPEN 问题
2. 按文件路径分组，应用 filters 过滤误报
3. 按 priority 排序，截取 max_fix_per_run 个
4. 启动 parallel_agents 个子代理（Task 工具）
   - 子代理修复前查 nosonar_position_rules 确定注释位置（若用 NOSONAR 抑制）
5. 每个子代理修复 files_per_agent 个文件
6. 等待所有子代理完成
7. 重新扫描验证（含 NOSONAR 位置校验）
8. 若 OPEN 数未达 target_open_count 且未超 max_scan_iterations，回到步骤 1
9. 生成报告
```

### 模式6：降级扫描（MCP 不可用）

```
0. 执行 scripts/start-sonarqube.ps1 → 确保服务器已启动
1. 检测 MCP 工具不可用
2. 执行 scripts/run-sonar-scanner.ps1 → 使用命令行工具扫描
3. 轮询 CE task 状态直到 SUCCESS（Phase 4.5）
4. 通过 HTTP API 获取质量门禁状态：
   GET /api/qualitygates/project_status?projectKey=${PROJECT_KEY}
5. 通过 HTTP API 搜索问题：
   GET /api/issues/search?componentKeys=${PROJECT_KEY}&severities=BLOCKER,CRITICAL
6. 输出报告
7. 提示用户配置 MCP 以获得更好体验
```

### 模式7：ES 锁解锁（独立维护操作）

```
1. 检测 ES 索引是否被 read_only_allow_delete 锁定
   GET http://127.0.0.1:${SONAR_ES_PORT|9001}/_cluster/health
2. 若被锁，执行解锁
   PUT http://127.0.0.1:${SONAR_ES_PORT|9001}/_settings
   Body: {"index.blocks.read_only_allow_delete": null}
3. 持久化 watermark 阈值
   PUT http://127.0.0.1:${SONAR_ES_PORT|9001}/_cluster/settings
   Body: {"persistent": {"cluster.routing.allocation.disk.watermark.low": "95%", ...}}
4. 验证锁已解除
```
