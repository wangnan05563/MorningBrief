# MorningBrief SonarQube 扫描报告（修复前基线）

- 生成时间：2026-11-14 17:13（UTC+8）
- 项目：MorningBrief（`20 News`）
- 项目 Key：`20_news`
- 服务：SonarQube Community Build 26.1.0.118079 · http://127.0.0.1:9000
- 扫描方式：sonar-scanner CLI 8.0.1（MCP 工具在本机不可用，按技能 Phase 1 降级）
- 扫描器 JRE：Eclipse Adoptium 21.0.9；`JAVA_HOME` 指向 Zulu 17（兼容）
- 基线 CE 任务：`02632a4c-7cb0-4629-b27a-f2c978436c1e`（SUCCESS）
- 原始日志：`docs/sonar-reports/scan-baseline.log`
- 原始问题 JSON：`docs/sonar-reports/baseline-issues.json`

## 1. 扫描范围

| 项 | 值 |
|---|---|
| 源码目录 | `backend/app` |
| 测试目录 | `backend/tests`（仅扫描，不计入覆盖率分母的样式问题） |
| 语言 | Python（`sonar.python.version=3.12`）、JSON、YAML |
| 索引文件 | 408（其中 Python 源文件 394） |
| 代码行（ncloc） | 32,979 |
| 排除 | `.trae`、`node_modules`、`__pycache__`、`dist`、`build`、`.cache`、`*.min.js/css`、`playwright-report`、`test-results`、`package-lock.json`、`news.db*`、`*.log` |

> 说明：仓库 `sonar-project.properties` 明确只扫描后端（原注释为 Node v24 与 SonarJS bridge 不兼容；本机 Node 实为 v22.23.2）。前端 `apps/admin-web`、小程序 `apps/miniprogram`、云函数 `apps/scf` 未纳入本次质量门，见报告末尾「范围与残留」。

## 2. 质量门与总体指标

| 指标 | 基线值 | 评级/说明 |
|---|---|---|
| Quality Gate | OK | Sonar way（当时无「新代码」条件被触发） |
| Bugs | 1 | Reliability 3.0（C） |
| Vulnerabilities | 0 | Security 1.0（A） |
| Code Smells | 7 | Maintainability 1.0（A），技术债 53min |
| Security Hotspots | 25 | 无权限读取明细（`/api/hotspots/search` 返回 Insufficient privileges） |
| 覆盖率 | 0.0% | 未配置覆盖率报告 |
| 重复行密度 | 0.6% | — |
| 认知复杂度合计 | 5,789 | — |
| ncloc | 32,979 | — |

## 3. OPEN 问题清单（8 项）

| # | 规则 | 严重度 | 类型 | 文件:行 | 消息 |
|---|---|---|---|---|---|
| 1 | `python:S3776` | CRITICAL | CODE_SMELL | `backend/app/services/ai_config_service.py:1033` | 认知复杂度 17 > 15 |
| 2 | `python:S125` | MAJOR | CODE_SMELL | `backend/app/services/ai_config_service.py:1049` | 注释掉的代码 |
| 3 | `python:S3776` | CRITICAL | CODE_SMELL | `backend/app/workflow/crawler/search_collector.py:103` | 认知复杂度 18 > 15 |
| 4 | `python:S3776` | CRITICAL | CODE_SMELL | `backend/app/workflow/crawler/search_collector.py:305` | 认知复杂度 22 > 15 |
| 5 | `python:S6019` | MAJOR | CODE_SMELL | `backend/app/workflow/crawler/web_search.py:78` | 惰性量词只可能匹配 0 次 |
| 6 | `python:S5850` | MAJOR | **BUG** | `backend/app/workflow/crawler/web_search.py:78` | 正则分组优先级不明确 |
| 7 | `python:S7483` | MAJOR | CODE_SMELL | `backend/app/workflow/crawler/web_search.py:224` | async 函数带 `timeout` 参数，应改用超时上下文 |
| 8 | `python:S3776` | CRITICAL | CODE_SMELL | `backend/app/workflow/crawler/web_search.py:250` | 认知复杂度 16 > 15 |

按严重度：CRITICAL 4、MAJOR 4；按类型：CODE_SMELL 7、BUG 1。

## 4. 规则覆盖合理性校验

- 生效质量配置：Python `Sonar way`（306 条规则）。
- `S1128`（未使用 import）未启用；`S1481`（未使用局部变量）、`S1192`（重复字面量）、`S1854`（无效赋值）已启用且命中 0。
- 结论：8 项为真实基线，非分析器失效或规则缺失导致。

## 5. 修复方向（按技能决策矩阵，不允许 NOSONAR 抑制）

| 规则 | 处理方式 |
|---|---|
| `S3776`（4 处） | 代码拆分：抽小函数 / 引入状态对象，保持行为等价 |
| `S125` | 删除注释代码，必要说明改写进 docstring |
| `S6019` + `S5850` | 重写正则：用「标题正则 + 切片」替代惰性量词与歧义分组 |
| `S7483` | 去掉 async 函数的 `timeout` 形参，改用 `asyncio.timeout` 上下文管理器 |
