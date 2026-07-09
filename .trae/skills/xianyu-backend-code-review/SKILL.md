---
name: "xianyu-backend-code-review"
description: "对闲鱼猎人项目后端代码（src/xianyu_hunter/ 下 Python/FastAPI/SQLAlchemy 文件）进行全面评审与逻辑审查，覆盖分层架构、异步并发、数据库规约、安全、性能、错误处理、日志规范、配置驱动、注册式资源 endpoint 契约、编码规范防御性复盘、跨层契约与测试同步等 36 个维度。当用户要求'审查/检查/走查/把关/review/评估/看看对不对/规范不规范'后端 Python 代码、'.py 文件修改'、'迭代发布前后端走查'，或提到'后端评审/backend review/Python 代码审查/FastAPI 评审/SQLAlchemy 评审'时调用。仅审查后端 .py 文件；纯前端 .tsx/.ts 文件审查请改用 xianyu-frontend-code-review。"
whenToUse: "需要审查闲鱼猎人后端代码（src/xianyu_hunter/ 下 .py 文件，含路由 routes/、仓储 infra/repo_*.py、领域模型 domain/、调度器 scheduler、配置 yaml_config、异步并发代码）是否符合项目规范"
triggers: "后端代码 走查/审查/审核/把关/review/检查/评估 | 后端评审/backend review/Python 代码审查/FastAPI 评审/SQLAlchemy 评审 | .py 文件 修改/变更/迭代 走查 | 迭代发布前 后端 代码 走查 | 这段后端代码 写得对不对/规范不规范 | 闲鱼 后端 代码 review | 路由/仓储/领域模型/调度器 代码 审查"
version: "4.39.0"
updated: "2026-07-09"
config: "config.yaml"
scripts: "scripts/auto-scan.ps1"
template: "templates/report-template.md"
---

# 闲鱼猎人后端代码审查

对闲鱼猎人项目后端代码（`src/xianyu_hunter/` 下的 Python/FastAPI/SQLAlchemy 文件）进行全面的代码评审及逻辑审查。评审涵盖**36 个维度**，包括分层架构、命名规范、异步并发、数据库规约、安全约束、性能优化、错误处理、日志规约、配置管理、智能客服专项、Git 操作规范、跨字段一致性与硬编码属性禁用、LLM 端点能力派发、端到端失败原因链与数据完整性闭环、多用户资源隔离与身份识别、业务关键字常量集中管理与跨端契约对齐、数据契约与时序（meta-rules #25-30 落地）、状态恢复前置校验与降级链日志合并（meta-rules #31-32 落地）、注册式资源 endpoint 契约 + 修复前全链路根因扫描协议 + 前后端字段契约单一可信源（meta-rules #33-35 落地）、规范治理（meta-rules #36-37 落地）、列表聚合与状态联动（meta-rules #38-42 落地）、编码规范防御性复盘（meta-rules #57-63 落地）、跨层契约与测试同步（meta-rules #47-51 落地）等。

> **v4.29.0 数据契约与时序复盘（meta-rules #25-30 后端落地）**：基于 2026-07-05 解决的 6 类问题（batch_refresh_scheduler 断路器未保存进度/启动钩子 traceback 丢失/naive-aware 混用/跨进程状态同步缺 marker/前后端 error_code 契约缺失/业务关键字散落），使用 Sequential Thinking 4 维度复盘法，新增 6 项 B-REVIEW 检查点（B-REVIEW-151~156），自动化扫描从 155 项扩展到 161 项。**B-REVIEW-151 批量断路器四要素**（meta-rule #25：失败计数+进度持久化+续传入口+日志对称，参数在 `batch_circuit_breaker` 节点管理）、**B-REVIEW-152 关键路径异常保留 traceback**（meta-rule #26：`_on_startup`/`run_migrations`/`_init_*` 外层 except 必 `logger.exception()`，参数在 `critical_path` 节点管理）、**B-REVIEW-153 datetime 统一时区策略**（meta-rule #27：存储 UTC、算术前 unify tzinfo、序列化带 tzinfo，禁 `datetime.now()` 无 tzinfo 与 `utcnow()`，参数在 `datetime` 节点管理）、**B-REVIEW-154 跨进程状态同步六步法**（meta-rule #28：写端+同步器+读端+启动检查+异常保留+配置驱动，参数在 `state_sync_marker` 节点管理）、**B-REVIEW-155 前后端错误码契约**（meta-rule #29：HTTPException 必含 `error_code` 字段，参数在 `error_code` 节点管理）、**B-REVIEW-156 业务关键字集中管理**（meta-rule #30：业务关键字禁散落代码，参数在 `business_keyword` 节点管理）。所有新检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.30.0 的 meta-rules #25-30。前端对应规范为 `xianyu-frontend-code-review` v4.34.0 的 F-REVIEW-110~115。

> **v4.30.0 状态恢复前置校验 + 降级链日志合并复盘（meta-rules #31-32 后端落地）**：基于日志排查报告发现的两类高频问题（异常 pause 后 resume 未校验根因消除形成"恢复→失效→暂停"无效循环、多阶段降级链每步独立 WARNING 淹没真实告警），使用 Sequential Thinking 4 维度复盘法，新增 1 项维度 32（状态恢复与日志规范）+ 2 项 B-REVIEW 检查点（B-REVIEW-157~158），自动化扫描从 161 项扩展到 163 项。**B-REVIEW-157 RESUME-PRECHECK 状态恢复前置校验**（meta-rule #31：具有 pause/resume 语义的组件 resume 前必须 precheck 校验 root_cause 消除，校验失败返回结构化拒绝 `{resume_blocked, reason_code, user_hint, retry_after}`，异常 pause 后设冷却期，参数在 `resume_policy` 节点管理）、**B-REVIEW-158 LOG-MERGE 多阶段降级链日志合并**（meta-rule #32：同一逻辑链多阶段日志合并为 1 条结构化 WARNING，中间步骤 DEBUG 化，结果含 `extra={stages, final_reason, keyword, attempts}`，参数在 `log_merge` 节点管理）。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `resume_policy` / `log_merge` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.31.0 的 meta-rules #31/#32。前端对应规范为 `xianyu-frontend-code-review` v4.35.0 的 F-REVIEW-116（状态恢复前置校验前端侧）；前端无降级链日志场景，不新增 LOG-MERGE 对应检查点。

> **v4.31.0 注册式资源 endpoint 契约 + 修复前根因扫描协议 + 前后端字段契约单一可信源复盘（meta-rules #33-35 后端落地）**：基于 2026-07-06 解决的"通知中心菜单点击无反应"问题复盘（`config/menu_registry.yaml` 已注册 `path=/notifications`，但 `frontend/src/App.tsx` 无对应 `<Route>`、`pages/Notifications/index.tsx` 不存在、`api/notifications.ts` 不存在，路由 fallback `<Route path="*" element={<Navigate to="/" replace />} />` 静默重定向到首页），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，新增 3 项维度（32-34）+ 3 项 B-REVIEW 检查点（B-REVIEW-159~161），自动化扫描从 163 项扩展到 166 项。**B-REVIEW-159 REGISTRATION-ENDPOINT-CHECK 注册式资源 endpoint 契约**（meta-rule #33 后端落地——前端已在 `menu_registry`/`router`/`page`/`api_wrapper` 注册的资源，后端必须在 `src/xianyu_hunter/web/routes/api_<domain>.py` 提供对应 `@router.<method>` endpoint；缺一即视为 CRITICAL；自动化校验脚本 `python scripts/check_registration.py` 退出码 0 才算通过，参数在 `backend_registration_endpoint` 节点管理）、**B-REVIEW-160 ROOT-CAUSE-CHAIN-CHECK 修复前全链路根因扫描协议**（meta-rule #34 后端落地——修复非平凡 bug 前必须先列 ≥3 个根因覆盖用户层/接口层/数据层/配置层/历史层；PR 描述必须含"≥3 根因列表"段；git diff 涉及 ≥3 个无关文件视为违反最小修改原则；新增逻辑无 unit test 视为 WARNING；参数在 `root_cause_chain_check` 节点管理）、**B-REVIEW-161 CONTRACT-OWNER-MARKER 前后端字段契约单一可信源**（meta-rule #35 后端落地——后端 Pydantic/DB Row 字段 = 权威源；后端 `BaseModel` 字段必须显式标注 `@field_validator` / `Field(..., description=...)` 标明"权威源"角色；后端字段变更必须同步通知前端 + 在 `contract_owner_marker` 节点更新 `affected_frontend_types_files` 列表；snake_case 严格透传禁止转 camelCase；参数在 `contract_owner_marker` 节点管理）。所有新检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.32.0 的 meta-rules #33-35 与 step 181-183。前端对应规范为 `xianyu-frontend-code-review` v4.36.0 的 F-REVIEW-117/118/119。

> **v4.34.0 列表聚合与状态联动复盘（meta-rules #38-42 后端落地）**：基于本轮对话解决的 5 类问题复盘（全局聚合视图未按任务个体配置范围过滤导致越界数据 / 列表交叉数据源 N+1 单条查询性能退化 / 多字段联动开关无优先级矩阵导致主开关失效后子过滤器仍生效 / precheck 抛异常而非结构化响应导致 API 层难以处理 / 配置化阈值缺失兜底导致配置缺失即崩溃），使用 Sequential Thinking 8 步复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景/落地映射/配置节点设计/执行计划/验证，新增 5 项 B-REVIEW 检查点（B-REVIEW-164~168），自动化扫描从 163 项扩展到 168 项。**B-REVIEW-164 GLOBAL-AGGREGATE-TASK-FILTER**（meta-rule #38 后端落地——全局视图（无 task_id）列表查询必须按各任务个体配置范围过滤，禁止只用全局默认范围，参数在 `global_aggregate_filter` 节点管理）、**B-REVIEW-165 LIST-CROSS-DOMAIN-INJECT**（meta-rule #39 后端落地——列表交叉其他数据源必须批量查询 + TTL 缓存，禁止 N+1 单条查询，参数在 `cross_domain_inject` 节点管理）、**B-REVIEW-166 MULTI-FIELD-LINKED-SWITCH**（meta-rule #40 后端落地——联动字段必须声明「主开关→过滤器」优先级矩阵，主开关失效时子过滤器自动禁用，参数在 `linked_switch_priority` 节点管理）、**B-REVIEW-167 RESUME-PRECHECK-STRUCTURED**（meta-rule #41 后端落地——precheck 必须返回 5 字段结构化 dict `{resume_blocked, reason_code, user_hint, retry_after, task_registered}` 不抛异常，API 层直接透传，参数在 `precheck_structured_fields` 节点管理）、**B-REVIEW-168 CONFIG-DRIVEN-THRESHOLD-FALLBACK**（meta-rule #42 后端落地——从 config 读取的阈值必须有 try/except 兜底默认值，禁止配置缺失即崩溃，参数在 `config_fallback_defaults` 节点管理）。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `meta_rules_38_42` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.34.0 的 meta-rules #38-42 与 step 184-188。前端对应规范为 `xianyu-frontend-code-review` v4.38.0 的 F-REVIEW-122~126。

> **v4.35.0 跨层契约与测试同步复盘（meta-rules #43-#47 后端落地）**：基于 2026-07-07 解决的 5 类问题复盘（SEMI_AUTO 模式通知未触发确认 / EVAL_PASSED 事件三处发布点 task_mode 字段不对齐 / 前端路由注册与后端 endpoint 契约缺失 / 回链 URL query string 构造与消费不一致 / 历史测试 mock 类型不匹配 + keyring fallback + 接口签名变更未同步测试），使用 Sequential Thinking 4 维度复盘法，新增 1 项维度 36（跨层契约与测试同步）+ 5 项 B-REVIEW 检查点（B-REVIEW-173~177）。所有检查点强调配置驱动（参数在 config.yaml 对应节点管理，不硬编码）与适用/不适用场景说明。详细编码规范整合到 xianyu-hunter-dev v4.35.0 meta-rules #43-#47。前端对应规范为 xianyu-frontend-code-review v4.39.0 的 F-REVIEW-131~135。

> **v4.37.0 调度器运行时治理复盘（meta-rules #48-#51 后端落地）**：基于 2026-07-08 解决的 5 类调度器运行时治理问题复盘（BatchRefreshScheduler 运行时禁用无效 / CookieSyncScheduler 无法运行时禁用 / scheduler.py 异常重试等待硬编码 300s / _resume_cooldown 字典内存泄漏 / cron 模式无最小间隔校验），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，新增 4 项 B-REVIEW 检查点（B-REVIEW-178~181），自动化扫描从 177 项扩展到 181 项。**B-REVIEW-178 SCHEDULER-RUNTIME-TOGGLE-SYMMETRY**（meta-rule #48 后端落地——调度器 `update_config(enabled=False)` 必须 remove_job + 入口 double-check + `is_enabled()` 方法 + 配置持久化，参数在 `meta_rules_48_51.scheduler_runtime_toggle` 节点管理）、**B-REVIEW-179 TIME-PARAM-CONFIG-DRIVEN**（meta-rule #49 后端落地——异常重试等待/轮询间隔/超时秒数等时间参数必须从 config 读取，禁止硬编码字面量，参数在 `meta_rules_48_51.time_param_config_driven` 节点管理）、**B-REVIEW-180 LIFECYCLE-RESOURCE-CLEANUP**（meta-rule #50 后端落地——长生命周期对象的状态字典必须提供 `drop_task_state(task_id)` 方法，DELETE API 必须调用清理，参数在 `meta_rules_48_51.lifecycle_resource_cleanup` 节点管理）、**B-REVIEW-181 CRON-MIN-INTERVAL-CHECK**（meta-rule #51 后端落地 experimental——用户输入 cron 表达式必须有最小执行间隔校验，解析失败返回结构化错误不抛异常，参数在 `meta_rules_48_51.cron_min_interval_check` 节点管理）。所有检查点强调配置驱动（参数在 config.yaml 对应节点管理，不硬编码）与适用/不适用场景说明。详细编码规范整合到 xianyu-hunter-dev v4.36.0 meta-rules #48-#51 与 step 194-197。前端对应规范为 xianyu-frontend-code-review v4.40.0 的 F-REVIEW-136~139。同时修复 v4.35 B-REVIEW-173~177 的 meta-rule 引用编号错位（#47-#51 → #43-#47）与配置节点名（`meta_rules_47_51` → `meta_rules_43_47`）。

> **v4.39.0 experimental 元规范同步（meta-rules #64-#65 前端侧）**：基于 2026-07-08 解决的 2 类问题复盘（URL↔状态同步失败回退 / Service Worker 缓存版本同步），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，**后端无新增 B-REVIEW 检查点**（自动化扫描项保持 188 项不变）。原因：meta-rule #64（URL↔状态同步失败回退）和 #65（Service Worker 缓存版本同步）均为纯前端场景（SheetWorkspace 多页签应用 / PWA 应用），后端不直接处理前端 URL 状态同步或 Service Worker 缓存。仅在 backend 层面同步以下原则：(1) 后端 API 返回的 URL 相关字段（如重定向路径）必须与前端 basename 配置一致；(2) 后端若提供版本号 API（如 `/api/about`），必须确保版本号唯一可信源，避免前端缓存旧版本时版本检测不一致。本次复盘的详细编码规范整合到 `xianyu-hunter-dev` v4.39.0 的 experimental meta-rules #64/#65。前端对应规范为 `xianyu-frontend-code-review` v4.44.0 的 F-REVIEW-152/153（experimental）。
>
> **v4.38.0 异步同步性/资源池基准/HTTP状态码映射/CSS选择器降级/异常日志语义/外部资源生命周期/数据库写入身份追溯复盘（meta-rules #57-#63 后端落地）**：基于 2026-07-08 解决的 7 类问题复盘（async/await 误用导致 Python 3.14 兼容性风险 / NullPool 性能问题导致慢查询 231ms / HTTP 状态码语义模糊导致用户误判商品下架 / CSS 选择器单一改版即失效 / 异常日志丢失 traceback 定位耗时 30+ 分钟 / 并发采集时 page 被误关导致 TargetClosedError / 数据库写入缺 user_id 导致跨用户数据风险 + converter 处理 re.Match 报 TypeError），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，新增 7 项 B-REVIEW 检查点（B-REVIEW-182~188），自动化扫描从 181 项扩展到 188 项。**B-REVIEW-182 ASYNC-AWAIT-SYNC-CHECK**（meta-rule #57 后端落地——`async def` 方法体内若不含 `await` 表达式，必须改为同步 `def`；调用点同步移除 `await`，白名单豁免 `@abstractmethod`/`__aenter__`/`__aexit__`/async generator，参数在 `meta_rules_57_63.async_await_check` 节点管理）、**B-REVIEW-183 RESOURCE-POOL-BENCHMARK**（meta-rule #58 后端落地——资源池配置必须有性能基准数据支持，docstring 记录选择理由与对比数据，系统层开销 > 50ms 时禁止用 NullPool，参数在 `meta_rules_57_63.resource_pool_benchmark` 节点管理）、**B-REVIEW-184 HTTP-STATUS-CODE-MAPPING**（meta-rule #59 后端落地——底层模块返回多原因的 None/错误时，必须建立 `reason_code → status_code` 映射表，底层设置 `last_*_failure_reason`，上游按映射查找状态码，参数在 `meta_rules_57_63.http_status_code_mapping` 节点管理）、**B-REVIEW-185 CSS-SELECTOR-FALLBACK**（meta-rule #60 后端落地——依赖第三方网站 DOM 的选择器必须有 ≥3 级降级（业务语义 className → HTML role 属性 → 文本内容前缀扫描），dump 触发条件收窄到核心字段失败，参数在 `meta_rules_57_63.css_selector_fallback` 节点管理）、**B-REVIEW-186 EXCEPTION-LOG-SEMANTIC**（meta-rule #61 后端落地——`except` 块内必须用 `logger.exception('描述')` 保留完整 traceback，禁用 `logger.warning(f'...{e}')` 丢失堆栈，非 except 块用 `exc_info=True`，参数在 `meta_rules_57_63.exception_log_semantic` 节点管理）、**B-REVIEW-187 EXTERNAL-RESOURCE-LIFECYCLE**（meta-rule #62 后端落地——外部传入的资源（Page/Connection/Lock）必须配对调用 `register`/`unregister`，且在 `finally` 块 `unregister` 避免泄漏，引用计数管理，参数在 `meta_rules_57_63.external_resource_lifecycle` 节点管理）、**B-REVIEW-188 DB-WRITE-IDENTITY-TRACE**（meta-rule #63 后端落地——数据库写入函数必须含 `user_id` 参数用于跨用户隔离；converter 函数处理 `re.Match` 对象必须显式调用 `m.group(1)` 再转型，禁用 `int(m)`，参数在 `meta_rules_57_63.db_write_identity_trace` 节点管理）。所有检查点强调配置驱动（参数在 config.yaml 的 `meta_rules_57_63` 节点管理，不硬编码）与适用/不适用场景说明。详细编码规范整合到 xianyu-hunter-dev v4.38.0 meta-rules #57-#63。

> **v4.31.0 业务关键字常量集中管理与跨端契约对齐复盘（后端侧）**：基于本轮对话解决的 5 个问题复盘（业务关键字散落导致已售状态未采集、事件类型 startswith 过滤误包含通知事件、Python 私有属性大小写不一致 AttributeError、服务未重启导致修复无效、PowerShell 编码与 shell 语法兼容问题），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，新增 1 项维度 30（业务关键字常量集中管理与跨端契约对齐）+ 5 项 B-REVIEW 检查点：B-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION（业务关键字常量集中管理——外部平台文本特征集中到单一模块的 `*_TEXT_KEYWORDS` 常量，统一访问函数 `check_text_sold` 调用，禁止散落字面量，配置参数在 `business_keyword_centralization` 节点管理）、B-REVIEW-EVENT-TYPE-EXACT-MATCH（事件类型过滤精确匹配——业务查询事件类型必须用 `==` 精确匹配，禁止 `startswith`/`endswith` 前缀过滤，通知事件与业务事件必须使用不同命名空间，配置参数在 `event_type_exact_match` 节点管理）、B-REVIEW-FIELD-NAME-CASE-SENSITIVE（前后端字段名大小写敏感检查——Python 类私有属性 `_session` vs `_Session` 严格大小写一致，API 响应字段名前后端严格一致含大小写下划线前后缀，配置参数在 `field_name_case_sensitive` 节点管理）、B-REVIEW-SERVICE-RESTART-VERIFICATION（服务重启验证清单——Python 后端代码修改后必须重启服务，重启后按清单验证端口监听/健康检查/数据状态/启动日志，配置参数在 `post_restart` 节点管理）、B-REVIEW-WINDOWS-TERMINAL-ENCODING（Windows 终端编码与 Shell 语法兼容——PowerShell 脚本显式设置 UTF-8 编码，命令拼接用 `;` 而非 `&&`，`stash@{0}` 加引号，Python 脚本设置 stdout 编码，配置参数在 `cross_platform` 节点管理）；审查流程新增「配置驱动检查」子阶段（3 步顺序扫描：读取配置节点清单 → 逐节点扫描代码 → 配置节点缺失检测）；Template A 新增「⚙️ Config Node Missing (v4.31)」分类（CRITICAL 级别，配置节点缺失会导致配置驱动检查无法生效）；所有新检查点强调配置驱动（参数在 `config.yaml` 的 `business_keyword_centralization` / `event_type_exact_match` / `field_name_case_sensitive` / `post_restart` / `cross_platform` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.29.0 的 step 129-133。前端对应规范为 `xianyu-frontend-code-review` v4.31.0 的维度 27（业务关键字常量集中管理与字段名大小写敏感）。

> **v4.25.0 数据库迁移块独立容错与关键路径异常可见性复盘**：基于本轮对话解决的 `sqlite3.OperationalError: no such column: notifications.read_at` 问题复盘（使用 Sequential Thinking 6 步复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景/落地映射/配置节点设计），新增 2 项 B-REVIEW 检查点：B-REVIEW-MIGRATION-BLOCK-ISOLATION（维度 6 SQLite 优化——迁移函数内多个独立迁移块必须各自 try/except，禁止外层统一 try/except 吞掉异常导致后续块跳过；强依赖场景允许合并；块边界标识符（如 C-01/C-02 注释）在配置管理；配置参数在 `migration_block_isolation` 节点管理）、B-REVIEW-CRITICAL-PATH-NO-SWALLOW（维度 11 错误处理——启动钩子/迁移/初始化等关键路径的外层 except 必须用 `logger.exception()` 输出完整 traceback，禁止 `logger.warning(f"...{e}")` 丢失堆栈；关键路径函数清单与禁止日志模式在配置管理；配置参数在 `critical_path_no_swallow` 节点管理），自动化扫描从 109 项扩展到 111 项；同时补齐 v4.22/v4.23 遗漏未录入检查点清单的 7 项（#103-109）；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `migration_block_isolation` / `critical_path_no_swallow` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.25.0 的 step 116。前端本次为纯后端问题，参照 v4.7.0/v4.24.0 的"后端同步原则"模式，不新增 F-REVIEW 检查点，仅同步原则。

> **v4.24.0 用户偏好类 UI 状态持久化复盘（后端侧同步原则）**：基于本轮对话解决的「批量采集菜单相关参数开关应支持持久化」需求复盘（使用 Sequential Thinking 7 步复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景/落地映射/配置节点设计/执行计划细化），**不新增 B-REVIEW 检查点**（自动化扫描项保持 109 项不变）。原因：本次问题为纯前端 UI 状态持久化（用户偏好类 UI 状态使用 usePersistentState 而非 useState），后端不直接处理前端 UI 状态，业务场景过于狭窄。仅在 backend 层面同步以下原则：(1) 若后端提供用户偏好类 API（如 `/api/user/preferences`），所有偏好字段的存储格式、序列化策略、默认值、校验逻辑应在 `config.yaml` 管理，不硬编码；(2) 后端持久化的字段（如批量采集的 `enabled` / `interval_minutes` 已通过 `PATCH /api/batch-refresh/config` 持久化）必须与前端保持单一可信源，前端不得再用 `usePersistentState` 重复持久化（避免前后端不一致），后端 `GET /status` 返回值必须是前端唯一可信源；(3) 后端若涉及"用户偏好"语义的接口（如 `/api/user/preferences`、`/api/profile/settings`），必须遵循 B-REVIEW-CONFIG-DRIVEN-TOGGLE（v4.3.0）的配置驱动开关原则 + B-REVIEW-NO-HARDCODED-THRESHOLD（v4.4.0）的禁止硬编码阈值原则。本次复盘的详细编码规范整合到 `xianyu-hunter-dev` v4.24.0 的 step 115（仅前端规范），前端审查规则落地到 `xianyu-frontend-code-review` v4.24.0 的 F-REVIEW-UI-PREFERENCE-PERSISTENCE（第 77 项）。后端自动化扫描项保持 109 项不变。

> **v4.26.0 API三态语义/NOT NULL防御/共享单例污染复盘（后端侧）**：基于本轮对话解决的「任务级配置覆盖功能开发 + 代码审查」复盘（使用 Sequential Thinking 8 步复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景/提炼编码规范/设计检查点/配置驱动方案/执行计划），新增 3 项 B-REVIEW 检查点：B-REVIEW-EXCLUDE-UNSET-CHECK（维度 19 状态管理与日志治理——PATCH/PUT 接口必须用 model_dump(exclude_unset=True) 区分未传/传null/传值三态，禁止手动循环跳过 None，配置参数在 api_update_semantics 节点管理）、B-REVIEW-NOT-NULL-NONE-DEFENSE（维度 6 SQLite 优化——NOT NULL 字段传 null 时必须防御性 pop 而非直接写入 DB 触发 IntegrityError，覆盖字段传 null 表示清除覆盖应正常写入 None，配置参数在 api_update_semantics 节点管理）、B-REVIEW-SHARED-SINGLETON-POLLUTION（维度 9 异步与调度器——循环中创建任务级覆盖对象必须用局部变量 worker_xxx，禁止直接修改 container 单例，配置参数在 shared_singleton_protection 节点管理），自动化扫描从 111 项扩展到 114 项；所有新检查点强调配置驱动（参数在 config.yaml 的 api_update_semantics / shared_singleton_protection 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 xianyu-hunter-dev v4.26.0 的 step 117-122。前端对应规范为 xianyu-frontend-code-review v4.26.0 的 F-REVIEW-THREE-STATE-NULL-SEMANTICS（三态语义前端侧）。

> **v4.28.0 全量复盘与审查要点同步（后端侧）**：基于 2026-07-03 至 2026-07-05 全量问题复盘（使用 Sequential Thinking 18 步四维度复盘法——成功步骤/任务执行过程中的不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景/落地映射/配置节点设计/执行计划/验证/规范源联动），复盘范围覆盖 80+ topics，问题归纳为 7 大类（A 时区/B 命名/C 状态持久化/D Cookie 认证/E 前端交互/F 数据传递/G 鲁棒性），新增 30 项 B-REVIEW 检查点（B-REVIEW-121 ~ B-REVIEW-150）：数据库维度 6 条（B-REVIEW-121~126，时区一致性/原生 SQL 类型防御/迁移步骤独立性/NOT NULL 字段防御/查询过滤条件精确性/状态值枚举一致性）、错误处理维度 5 条（B-REVIEW-127~131，错误归因精细化/异常传播完整性/错误消息透传/重试策略配置化/已知场景日志降噪）、状态管理维度 6 条（B-REVIEW-132~137，熔断器持久化对称性/状态切换原子性/多源失效判定一致性/缺失数据回退策略/多源状态同步标记机制/异步竞态防护）、配置管理维度 4 条（B-REVIEW-138~141，参数传递链完整性/业务关键词配置化/开关持久化/凭证多存储同步）、通用工程维度 5 条（B-REVIEW-142~146，属性调用一致性/API 契约一致性/命名语义清晰性/重复逻辑抽取/跨进程编码一致性）、数据类与启动维度 2 条（B-REVIEW-147~148，dataclass 字段显式声明/启动钩子完整性）、测试维度 1 条（B-REVIEW-149，测试 Mock 类型匹配）、浏览器自动化维度 1 条（B-REVIEW-150，Cookie 完整性管理），自动化扫描从 125 项扩展到 155 项；**审查流程优化**：4 阶段流水线（上下文加载 → 分层扫描 → 优先级分类 → 结果呈现），替代原 5 阶段闭环；**结果呈现优化**：结构化报告模板（概览 + 问题详情，含规范引用/配置节点/反模式示例）；**配置化**：新增 `coding_standards` 节点（覆盖 datetime/migration/null_defense/query_filter/enum_consistency/error_attribution/log_noise/circuit_breaker/state_sync/credential_stores/retry/param_chain/dataclass/startup/mock/cookie/parser/encoding/dry/contract/persist/race/keywords 23 个子节点），所有参数通过 config.yaml 管理；**规范源联动**：每个 checkpoint 引用 xianyu-hunter-dev 中的规范编号（如 DATETIME-TZ-01/MIGRATE-01/NULL-01/QUERY-01/ENUM-01/ATTRIB-01/EXCEPT-01/ERROR-01/RETRY-01/LOG-NOISE-01/CIRCUIT-01/STATE-01/CONSISTENCY-01/FALLBACK-01/SYNC-01/RACE-01/PARAM-CHAIN-01/KEYWORD-01/PERSIST-01/CREDENTIAL-01/NAMING-01/CONTRACT-01/SEMANTICS-01/DRY-01/ENCODING-01/DATACLASS-01/STARTUP-01/MOCK-01/COOKIE-01），确保审查规则与编码规范单一可信源对齐。

> **v4.28.0 多用户资源隔离/认证中间件多路校验/会话token安全/快照覆盖决策/用户身份优先级复盘（后端侧）**：基于 MU1 多用户数据层 + MU2 认证中间件改造复盘（使用 Sequential Thinking 8 步复盘法——成功步骤/不确定性与失败点/可抽象流程/适用场景/落地映射/配置节点设计/执行计划/验证），新增维度 21（多用户隔离）+ 5 项 B-REVIEW 检查点：B-REVIEW-MULTI-USER-RESOURCE-ISOLATION（多用户资源隔离——全局单例资源必须按 user_id 隔离，文件路径 cookies_{uid}.json，缓存分桶 dict[str, tuple]，user_id 白名单校验防路径遍历，SQLite 兜底判断 default，配置参数在 multi_user_resource_isolation 节点管理）、B-REVIEW-AUTH-MULTI-PATH-VALIDATION（认证中间件多路校验——WEB_TOKEN 直通→session_token 查库→401，hmac.compare_digest 防时序攻击，异常降级 warning 不 debug，user_id 注入 request.state，日志脱敏，配置参数在 auth_multi_path_validation 节点管理）、B-REVIEW-SESSION-TOKEN-SECURITY（会话 token 安全——secrets.token_urlsafe 生成，sha256 存储，hmac.compare_digest 校验，滑动续期，撤销清缓存+标记失效，缓存与撤销互斥，会话固定防护，配置参数在 session_token_security 节点管理）、B-REVIEW-SNAPSHOT-REALTIME-OVERWRITE（快照与实时数据覆盖决策——字段分四档：非空字段覆写/数值字段>0才覆写/状态字段始终覆写/标识字段只填缺失，每档有单元测试，配置参数在 snapshot_realtime_overwrite 节点管理）、B-REVIEW-USER-IDENTITY-PRIORITY（用户身份识别优先级——unb>cookie2哈希>default 优先级链，每级有正则/哈希校验，配置化，最终降级 default，配置参数在 user_identity_priority 节点管理），自动化扫描从 120 项扩展到 125 项；所有新检查点强调配置驱动（参数在 config.yaml 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 xianyu-hunter-dev v4.30.0 的 step 134-137。

> **v4.27.0 端到端失败原因链与数据完整性闭环复盘（后端侧）**：基于本轮对话解决的「Failed to collect item detail: page unavailable or login expired」根因复盘（代码被回退 + 服务未重启双重原因导致修复未生效，重新实施 4 个文件修复：错误语义优化 401/429/502/503 细粒度映射、merge_cookies 合并写入避免部分 cookie 覆盖完整集、cookie 完整性预检 22 个 cookie 双阈值 AND 判断、test mock 同步更新），使用 Sequential Thinking 4 维度复盘法——成功步骤/任务执行过程中的不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，新增 1 项维度 29（端到端失败原因链与数据完整性闭环）+ 6 项 B-REVIEW 检查点：B-REVIEW-FAILURE-REASON-PROPAGATION（失败原因传递链——底层设置 `last_*_failure_reason` → 中层映射 status_code → 文案与根因匹配 → reason 值可枚举集中管理，禁止用字符串子串做日志降级 marker，配置参数在 `failure_reason_propagation` 节点管理）、B-REVIEW-DATA-COMPLETENESS-PRECHECK（数据完整性预检——预检方法签名 `async def _check_xxx_completeness(self) -> str | None`、双阈值 AND 判断（总数 + 关键项命中数）、调用前预检 + 调用后二次检查、错误信息含具体缺失清单，配置参数在 `data_completeness_precheck` 节点管理）、B-REVIEW-MERGE-VS-OVERWRITE-WRITE（合并写入 vs 覆盖写入决策——写入策略决策矩阵（按数据来源选择策略）、合并写方法签名 `def merge_xxx(self, new_items: list[dict]) -> bool`、合并后日志输出、覆盖写必须先验证新集完整，配置参数在 `write_strategy_decision` 节点管理）、B-REVIEW-ERROR-MESSAGE-CONSTANT（文案常量集中管理——文案常量集中定义、跨模块引用必须 import、禁止用字符串子串做 marker、错误响应增加 error_code 字段，配置参数在 `error_message_centralization` 节点管理）、B-REVIEW-EDIT-VERIFY-DEPLOY-LOOP（修改-验证-部署闭环——修改后立即 grep 验证、全局 grep 旧文案、Python 修改后必须重启服务、重启后验证端口+数据状态、git stash 前先 commit 保底，配置参数在 `edit_verify_deploy_loop` 节点管理）、B-REVIEW-TEST-MOCK-SYNC（测试 mock 同步——修改前置条件时同步更新测试 mock、mock 数据必须覆盖完整字段集、测试失败时优先检查前置条件变更、mock 数据集中管理，配置参数在 `test_mock_synchronization` 节点管理），自动化扫描从 114 项扩展到 120 项；所有新检查点强调配置驱动（参数在 config.yaml 的 `failure_reason_propagation` / `data_completeness_precheck` / `write_strategy_decision` / `error_message_centralization` / `edit_verify_deploy_loop` / `test_mock_synchronization` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 xianyu-hunter-dev v4.27.0 的 step 123-128。前端对应规范为 xianyu-frontend-code-review v4.27.0 的 F-REVIEW-FAILURE-REASON-UI-SYNC 等（前端侧同步原则）。

> **v4.23.0 能力驱动派发 / 共享工具函数 / 静默降级预检复盘（后端侧）**：基于本轮对话解决的"LLM 深度分析因 vision 模型不支持 image_url 触发 400"问题复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景），新增 1 项维度 28（LLM 端点能力派发与共享工具函数）+ 3 项 B-REVIEW 检查点：B-REVIEW-LLM-CAPABILITY-DISPATCH（能力驱动派发——任何 LLM/多模态/function_call/json_mode 调用必须在构造 payload 前预检目标模型能力，能力校验函数必须共享（`api_ai._is_vision_capable`），关键字白名单配置化（`config.yaml` 的 `llm_capability_keywords` 节点），散落内联即违规）、B-REVIEW-SHARED-UTIL-CENTRALIZATION（共享工具函数规范——跨 ≥2 模块复用的判断逻辑/关键字白名单/常量必须抽取为"被依赖方"模块顶层的纯函数或模块级常量，导入方只能 `from <source> import <shared>`，审查场景：跨 ≥2 文件出现相同关键字/正则/常量字面量必须触发"抽取共享"建议，配置参数在 `shared_util_rules` 节点管理）、B-REVIEW-SILENT-DOWNGRADE-PRECHECK（静默降级预检——可选增强能力（vision/function_call/json_mode）调用前必须预检，失败时降级为等价文本表达（如 prompt 追加"图片 URL + 描述"）而非抛错，预检失败日志级别 `logger.warning`（与 v4.9 B-REVIEW-LOG-DOWNGRADE-STABILITY 一致），降级 prompt 模板集中管理（`config.yaml` 的 `llm_downgrade` 节点），区分"可选增强"与"核心能力"（核心能力缺失必须报错）），自动化扫描从 106 项扩展到 109 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `llm_capability_keywords` / `shared_util_rules` / `llm_downgrade` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.21.0 的 step 112-114。前端对应规范为 `xianyu-frontend-code-review` v4.23.0 的 `F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION`。

> **v4.22.0 启动钩子完整性/任务历史三层保护/计数器DB MAX/interval首次执行复盘（后端侧）**：基于本轮对话解决的 4 个问题（反爬会话管理未自动启动、批量采集历史残留running状态、task_id跨进程重启重置、interval触发器首次执行延迟30分钟）复盘（使用 Sequential Thinking 6 步复盘法——成功步骤/失败点/可抽象流程/适用场景/元规范提炼与落地映射），新增 4 项 B-REVIEW 检查点：B-REVIEW-STARTUP-HOOK-COMPLETENESS（维度 9 异步与调度器——所有依赖 container.browser/collector 的组件必须在 startup.py _on_startup 中有对应 start_xxx() 启动钩子，启动钩子必须用 if _should_start_scheduler() 包裹，放在依赖的调度器之后，启动失败 try/except 兜底仅 warning 不阻断主服务，验证方法 grep container.browser/collector 找所有依赖点逐个检查，配置参数在 startup_hook_completeness 节点管理）、B-REVIEW-TASK-HISTORY-THREE-LAYER-PROTECTION（维度 9 异步与调度器——写入 running 状态的代码路径必须有对应 finalize 调用更新为终态，必须覆盖正常结束/future.result超时/协程异常三条路径，错误消息累积设FIFO上限避免JSON字段无限膨胀，状态语义区分 circuit_broken→failed / _stop_flag→cancelled / 正常→completed，配置参数在 task_history_protection 节点管理）、B-REVIEW-COUNTER-DB-MAX-INIT（维度 6 SQLite 优化——业务自增ID如 task_id/batch_id/run_id 不能依赖内存初始化（进程重启会重置），调度器 __init__ 时必须从 DB SELECT MAX(id) 初始化，查询失败回退到0+warning不阻断启动，trigger_now 时 +1 立即返回前端不等待DB写入，配置参数在 counter_db_max_init 节点管理）、B-REVIEW-APSCHEDULER-INTERVAL-FIRST-RUN（维度 9 异步与调度器——APScheduler interval 触发器默认首次执行时间为 start+interval（即启动后等完整间隔），需要启动后快速反馈的场景必须设 next_run_time=now+delay，delay 建议5-10秒给初始化依赖就绪，日志必须输出间隔+首次执行时间，配置参数在 apscheduler_interval_first_run 节点管理），自动化扫描从 102 项扩展到 106 项；所有新检查点均强调配置驱动（参数在 config.yaml 的 startup_hook_completeness / task_history_protection / counter_db_max_init / apscheduler_interval_first_run 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 xianyu-hunter-dev v4.20.0 的 step 107-110。前端对应规范为 xianyu-frontend-code-review v4.22.0 的 F-REVIEW-PWA-CACHE-VERIFY（PWA 缓存验证）。

> **v4.19.0 DOM 选择器同步/外部文案集中管理/调度器启动可见性复盘**：基于本次对话解决的 3 个核心问题复盘（使用 Sequential Thinking 12 步复盘法——成功步骤/失败点/可抽象流程/适用场景/元规范提炼/落地映射/配置节点设计），新增 3 项 B-REVIEW 检查点：B-REVIEW-SELECTOR-REPOSITORY-SYNC（维度 11 错误处理——同一 DOM 数据源的所有解析路径（主解析 `_find_cards` / 批量解析 `_BATCH_PARSE_SCRIPT` / 降级解析）必须引用同一选择器仓库，JS 脚本必须动态拼接选择器字符串（禁止内联 CSS 选择器），ID 提取必须有 3 层兜底（data-* 属性 → 内部任意 a[href] → /item/数字 路径），配置参数在 `selector_repository_sync` 节点管理）、B-REVIEW-EXTERNAL-TEXT-PATTERN-CENTRALIZE（维度 13 代码质量——外部系统（闲鱼/淘宝/第三方 API）的文本特征（已售关键词/错误码/状态文案）必须提取为模块级常量（`tuple[str, ...]` 或 `frozenset[str]`），多处消费点必须复用同一纯函数（`check_xxx(text) -> bool`），禁止在消费点内联关键词列表，配置参数在 `external_text_pattern_centralize` 节点管理）、B-REVIEW-SCHEDULER-STARTUP-VISIBILITY（维度 9 异步与调度器——关键后台调度器（影响业务正确性的，如批量采集/状态回查/数据同步）启动时输出 INFO + 间隔，未启动时输出 WARNING + 醒目提示 + 启动命令 + 影响范围，`--help` 必须说明启动参数影响范围，`/api/about` 端点必须返回调度器状态，配置参数在 `scheduler_startup_visibility` 节点管理），自动化扫描从 98 项扩展到 101 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `selector_repository_sync` / `external_text_pattern_centralize` / `scheduler_startup_visibility` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.19.0 的 step 99-101。前端对应规范为 `xianyu-frontend-code-review` v4.19.0 的 `F-REVIEW-SCHEDULER-STATUS-DISPLAY`。遗留待办：v4.17.0/v4.18.0 的 VERSION-SOURCE 规范（B-REVIEW-VERSION-SOURCE-SINGLE）尚未在本 skill 落地，需后续补充。

> **v4.20.0 版本号源管理复盘（后端侧）**：基于本轮解决的"版本管理菜单持续显示 V10"问题复盘（使用 Sequential Thinking 6 步复盘法——成功步骤/失败点/可抽象流程/适用场景），落地 v4.19.0 遗留待办，新增 1 项 B-REVIEW 检查点：B-REVIEW-VERSION-SOURCE-SINGLE（维度 14 配置管理——构建期元数据必须有唯一源头文件 `__init__.py: __version__`，构建期元数据由 `scripts/build_info.py` 自动生成 `_build_info.py`；多端点读取同一元数据必须封装 `_safe_xxx()` 三层 try/except 回退辅助函数（源头 → 生成文件 → 默认值 `'unknown'`）；export_config / about / health 等多端点响应中涉及版本号字段必须调用 `_safe_app_version()` 而非硬编码占位符 `"1.0"` / `"0.0.0"` / `"unknown version"`；端点命名相似不等于语义对齐，`/api/config/version` 名称含 "version" 但实际返回 `len(backups)`，应在端点命名或 docstring 中明确语义），自动化扫描从 101 项扩展到 102 项；新检查点强调配置驱动（参数在 `config.yaml` 的 `version_source_management` 节点管理，包含 `single_source_file` / `auto_generated_file` / `safe_helper_function` / `fallback_default` / `forbidden_placeholders` / `forbidden_version_endpoints` 等，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.18.0 的 step 98。前端对应规范为 `xianyu-frontend-code-review` v4.20.0 的 `F-REVIEW-VERSION-SOURCE-ALIGN`。

> **v4.16.0 字段归一化文档化 + 除零兜底禁止凑数复盘**：基于本次对话解决的「前端接入 api_ai_deep 端点 + 后端贩子识别维度 3/4 实现」代码审查复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 2 项 B-REVIEW 检查点：B-REVIEW-FIELD-NORMALIZE-DOC（维度 18 跨字段一致性与硬编码属性禁用——后端对 LLM/外部响应做归一化（合并/重命名/转换字段）时必须在前端 types.ts 对应字段声明中加注释「后端已归一化，前端消费 X 字段」，types.ts 中保留旧字段名必须标 optional 并注释「仅作兼容保留，后端不返回」，前端禁止通过动态 key 取归一化字段必须直接用归一化后字段名，配置参数在 `field_normalize_doc` 节点管理）、B-REVIEW-DIVZERO-FALLBACK（维度 13 代码质量——除零/空值兜底禁止用凑数小数 `x / 0.1` 伪装比值，比值/比率/百分比计算中 previous_count/baseline 可能为 0 时直接置为 0.0 或 float('inf')，写入 reason/log 展示给用户的数值无意义时用字符串 "N/A" 而非数字，配置参数在 `divzero_fallback` 节点管理），自动化扫描从 96 项扩展到 98 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `field_normalize_doc` / `divzero_fallback` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.17.0 的 step 94-97。前端对应规范为 `xianyu-frontend-code-review` v4.16.0 的 `F-REVIEW-FIELD-CONTRACT-ALIGN` / `F-REVIEW-ERROR-HANDLER-EXTRACT`。

> **v4.15.0 Cookie 层状态管理 + 代码变更逻辑审查复盘（后端侧）**：基于本轮解决的"功能正常但状态显示失效"问题（用户反馈：实时查询、官方采集等功能均能正常运行，但 identity、session、tracking 状态持续显示失效）+ 代码变更逻辑审查（发现 2 个 Critical / 3 个 Suggestion / 2 个 Nit）复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 3 项 B-REVIEW 检查点：B-REVIEW-CACHE-INVALIDATION（维度 14 配置管理——任何持久化层（JSON/SQLite/外部配置）变更后必须**显式调用**对应缓存对象的 `invalidate_cache()` 或等价方法，TTL 兜底不替代主动失效，跨进程变更必须主动通知主进程，配置参数在 `cache_invalidation` 节点管理）、B-REVIEW-STATE-DETECTION-BOOTSTRAP（维度 9 异步与调度器——任何"功能信号"字段不能仅用布尔初始值代表"未检测"，必须配合"已发生过检测"标记（时间戳/计数器/标志位），强制恢复需白名单（信号只能恢复其能证明有效的层范围），配置参数在 `state_detection_bootstrap` 节点管理）、B-REVIEW-MIGRATION-TRANSACTION（维度 6 SQLite 优化——SQLite 不支持 ALTER COLUMN，修改列约束必须用 `engine.begin()` 单事务 + 残留清理 + 数据复制 + 异常恢复模式，禁止分散 commit 或裸 ALTER，配置参数在 `migration_transaction` 节点管理），自动化扫描从 93 项扩展到 96 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `cache_invalidation` / `state_detection_bootstrap` / `migration_transaction` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.16.0 的 step 91-93。前端对应规范为 `xianyu-frontend-code-review` v4.16.0 的 `F-REVIEW-STATE-FUNCTIONAL-ALIGN`。

> **v4.9.0 双链路一致性/状态机/资源生命周期/并发安全/Python 现代化复盘**：基于本次对话解决的 5 类问题复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 5 项 B-REVIEW 检查点：B-REVIEW-STATE-MACHINE-WHITELIST（维度 11 状态机白名单转换——业务对象有状态字段且会变化时必须按枚举穷举/白名单转换/终态不可复活/中间态超时清理/deadline 不可无限重置/前后端枚举值统一 6 步流程设计）、B-REVIEW-RESOURCE-CLEANUP-HOOK（维度 9 资源生命周期——可注册组件必须实现 cleanup() 钩子，asyncio.Task 引用保留防 GC，取消+gather 模式，try/finally 初始化）、B-REVIEW-DUAL-LINK-CONSISTENCY（维度 18 双链路一致性——同一业务目标有 ≥2 条链路时共用前置条件必须提取为独立函数两链路调用同一函数，grep 验证+测试覆盖）、B-REVIEW-CONCURRENT-STATE-LOCK（维度 9 并发安全——共享状态检查+更新必须在同一锁内，dataclass 字段显式声明禁止 getattr 兜底）、B-REVIEW-PYTHON-MODERN-ASYNCIO（维度 9 Python 现代化——asyncio.create_task 替代 get_event_loop，模块级 import，CancelledError 传播），自动化扫描从 69 项扩展到 74 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `state_machine` / `resource_lifecycle` / `dual_link_consistency` / `concurrency_safety` / `python_modern` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.10.0 的 step 60-64。
>
> **v4.11.0 配置校验/迁移失败处理/状态码语义/LLM 防御解析/调度器 DB 同步/后台任务监控/数值提取复盘**：基于本轮对话解决的 7 类问题复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 7 项 B-REVIEW 检查点：B-REVIEW-CONFIG-VALIDATION（维度 14 配置管理——数值型配置项必须有边界值校验 min/max/non_zero/range，加载时主动校验无效值用默认值+warning，禁止直接用于算术运算导致 ZeroDivisionError）、B-REVIEW-MIGRATION-FAILURE-HANDLING（维度 6 SQLite 优化——`_migrate_*` 函数失败必须明确策略，关键迁移 raise RuntimeError 中断启动，非关键 warning+继续，禁止 `except: pass` 静默吞掉）、B-REVIEW-STATUS-CODE-SEMANTICS（维度 7 安全性——HTTP 状态码按语义精细化区分 401 未登录/403 权限不足/440 Cookie 过期/441 Token 过期/504 网关超时，禁止所有认证失败都映射为 401）、B-REVIEW-LLM-DEFENSIVE-PARSING（维度 11 错误处理——LLM API 响应必须三层级防御性解析 choices→message→content，每层用 .get()+isinstance+长度检查，禁止链式访问导致 KeyError/IndexError）、B-REVIEW-SCHEDULER-DB-SYNC（维度 9 异步与调度器——调度器内存状态变更必须同步 DB（update_task_status），禁止只在内存变更导致 API 返回与实际不一致）、B-REVIEW-BACKGROUND-TASK-MONITOR（维度 9 异步与调度器——后台 asyncio.Task 必须用轮询监控 task.done()，禁止 asyncio.Event().wait() 静默等待导致任务异常退出无感知）、B-REVIEW-NUMERIC-EXTRACTION（维度 13 代码质量——多数字文本必须用 re.findall 取 numbers[-1]，禁止 re.search 取第一个数字误取原价），自动化扫描从 75 项扩展到 82 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `config_validation` / `migration_failure_strategy` / `status_code_semantics` / `llm_defensive_parsing` / `scheduler_db_sync` / `background_task_monitor` / `numeric_extraction_strategy` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.12.0 的 step 69-75。前端对应规范为 `xianyu-frontend-code-review` v4.12.0 的 `F-REVIEW-INPUT-NUMBER-BOUNDS` / `F-REVIEW-XSS-ESCAPE`。

> **v4.12.0 官方采集失败复盘（后端侧）**：基于本轮对话解决的「官方采集失败」P0-P3 优化工作复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 4 项 B-REVIEW 检查点：B-REVIEW-DOM-FALLBACK-CHAIN（维度 11 错误处理——SPA 数据提取必须 DOM → og:meta → document.title 多层兜底，与 v4.3 B-REVIEW-FALLBACK-CHAIN 多方案降级语义不同，本节点专指 DOM 提取兜底，禁止单一选择器失败即整体失败）、B-REVIEW-FAILURE-DUMP（维度 11 错误处理——关键选择器失败必须 dump `page.content()` 到 `logs/<scenario>_<id>_<timestamp>.html` 用于事后取证，dump 用 `asyncio.create_task` fire-and-forget 不阻塞主流程，敏感字段需脱敏）、B-REVIEW-TIMING-INSTRUMENTATION（维度 8 性能——关键路径 `page.goto`/`wait_for_selector`/HTTP/DB 必须用 `time.perf_counter()` 计时并按阈值告警，禁止仅用 `logger.info("开始")/logger.info("结束")` 文本日志难以聚合分析）、B-REVIEW-PRECHECK-AND-PARALLEL（维度 9 异步与调度器——高开销操作前必须前置校验 Cookie 凭证 `expires` 字段，session cookie `expires=-1` 跳过预校验，persistent cookie 过期直接返回 440 不启动浏览器；独立 IO 任务必须用 `asyncio.gather(*tasks, return_exceptions=True)` 并行执行，禁止 `for task in tasks: await task` 串行），自动化扫描从 82 项扩展到 86 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `dom_fallback_chain` / `failure_dump` / `timing_instrumentation` / `precheck_parallel` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.13.0 的 step 76-81。前端对应规范为 `xianyu-frontend-code-review` v4.13.0 的 `F-REVIEW-ERROR-CONTRACT-TIMEOUT` / `F-REVIEW-RETRY-BACKOFF`。
>
> **v4.13.0 统计分类互斥性复盘（后端侧）**：基于本轮对话解决的「评估明细页面优化」工作复盘（使用 Sequential Thinking 5 步系统分析——成功步骤/失败点/可抽象流程/适用场景/落地映射），新增 1 项 B-REVIEW 检查点：B-REVIEW-STATS-EXCLUSIVE（维度 19 API 设计规范——统计接口返回的分类计数必须互斥，total = sum(各分类计数)，insufficient(score==null) 与 score-based 分类(auto/pass/fail) 互斥，禁止一个记录同时计入两个分类导致统计数量与实际不符），自动化扫描从 89 项扩展到 90 项；新检查点强调配置驱动（参数在 `config.yaml` 的 `stats_exclusive` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.14.0 的 step 82。前端对应规范为 `xianyu-frontend-code-review` v4.14.0 的 `F-REVIEW-FILTER-BACKEND-ALIGN`。
>
> **v4.14.0 登录流程性能优化/Cookie层同步测试修复/代码变更逻辑审查复盘（后端侧）**：基于本次会话解决的 4 个问题（登录流程性能优化、Cookie层同步测试修复、代码变更逻辑审查）复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 3 项 B-REVIEW 检查点：B-REVIEW-ROUTE-BLOCK-TYPES（维度 9 异步与调度器——浏览器自动化资源拦截必须考虑业务关键资源，禁止盲目拦截 image/font/media，拦截前必须检查页面是否依赖图片渲染关键内容如二维码图片，配置参数在 `browser.route_block_types` 节点管理）、B-REVIEW-SIGNAL-LAYER-MAPPING（维度 10 事件总线——层恢复信号必须与层范围匹配，SESSION层信号不能恢复IDENTITY层，信号只能恢复其所属层及以下层，配置参数在 `cookie_layers.signal_layer_mapping` 节点管理）、B-REVIEW-DEBUG-CODE-CLEANUP（维度 13 代码质量——临时DEBUG代码在问题修复后必须移除，禁止留在生产代码中，配置参数在 `debug` 节点管理），自动化扫描从 90 项扩展到 93 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.15.0 的 step 86-88。前端对应规范为 `xianyu-frontend-code-review` v4.15.0 的 `F-REVIEW-DEBUG-CODE-CLEANUP`。
> **v4.10.0 过滤结果可见性/pytest 模块重复 import 隔离/日志库占位符一致性/测试 fixture 生产隔离复盘**：基于本轮对话解决的 4 类问题复盘（使用 Sequential Thinking 8 步系统分析——成功步骤/失败点/可抽象流程/适用场景/落地映射），新增 4 项 B-REVIEW 检查点：B-REVIEW-FILTER-VISIBILITY（维度 19 API 设计规范——含过滤链路的查询接口必须输出完整 `filter_summary` 含 raw/各阶段 skipped/final_total/filtered_out，filtered_out 项含 link_type/link_key/display/filter_reason/filter_detail 5 字段，max_filtered_out_items 上限从 config 读取禁止硬编码 50）、B-REVIEW-PYTEST-MODULE-REIMPORT（维度 20 测试建议——conftest.py patch 模块属性时必须遍历 sys.modules 找所有持目标属性的模块全部 patch，禁止硬编码模块名列表，禁止用 `__import__` 必须用 `importlib.import_module`）、B-REVIEW-LOGURU-PLACEHOLDER（维度 12 日志规约——loguru 项目所有 logger.xxx() 必须用 `{}` 占位符，grep `%[sdrf]` 在 logger 调用行附近即发现违规，混用不抛异常但显示 %s 字面量极难发现）、B-REVIEW-TEST-FIXTURE-ISOLATION（维度 20 测试建议——conftest.py 必须 patch 生产路径到 tmp_path，fixture 数据需带可识别特征如 `test_fixture_` 前缀，数据污染应急 5 步流程停止服务→删除污染文件→修复 conftest→重跑测试→通知用户），自动化扫描从 71 项扩展到 75 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `filter_summary` / `pytest_isolation` / `log_placeholder` / `test_isolation` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.11.0 的 step 65-68。前端对应规范为 `xianyu-frontend-code-review` v4.10.0 的 `F-REVIEW-FILTER-VISIBILITY`。
>
> **v2.0.0 知识点整合**：整合 `xianyu-hunter-dev` 技能的 `backend-guide.md`、`database-guide.md`、`chatbot-guide.md` 与 `project-rules.md` 硬约束，新增维度 1（分层架构）、4（Pydantic 2.x）、5（SQLAlchemy 2.0）、6（SQLite 优化）、9（异步与调度器）、10（事件总线）、16（Composition Root）、17（智能客服专项），扩展安全/性能/日志维度，自动化扫描 14 项。
>
> **v2.1.0 新增维度 23（Git 操作规范）**：基于多分支合并实战复盘，新增 `.git/index.lock` 残留检测、产物文件 untrack、cherry-pick 冲突保留策略、async/await 一致性等检查项，自动化扫描从 12 项扩展到 14 项。
>
> **v3.0.0 SonarQube 规则增强**：基于 SonarQube 修复实战复盘，扩展维度 9（异步与调度器）新增 S7503 规则检查、维度 13（代码质量）新增 S3776（认知复杂度）、S6767（未使用参数）、S1192（重复字符串）、S5843（正则复杂度）规则，补充实战案例（`login_orchestrator.start_session` 7 步拆分模式、`scheduler.start_all` 同步化），自动化扫描从 14 项扩展到 24 项；新增 Evaluator 构造检查（禁止接受覆盖参数）、KB 白名单检查、`CancelledError` 传播检查。
>
> **v4.0.0 事件时机/字段覆盖/幂等性/搜索标准化复盘**：基于 DingTalk 通知事件时机修复 + 评估详情字段覆盖策略 + 反爬登录幂等性 + 实时搜索标准化 + 代码评审通用规范复盘，新增维度 9（事件触发时机）、维度 13（注释一致性）、维度 17（字段覆盖策略）、维度 19（幂等性设计 + 搜索接口标准化）补充检查项，自动化扫描从 24 项扩展到 34 项。
>
> **v4.1.0 会话失效处理复盘**：基于"实时搜索会话失效未推送明确错误提示"问题复盘，新增维度 11（重试失败后状态信号传递）+ 维度 7（Cookie 检查全面性）补充检查项，自动化扫描从 34 项扩展到 36 项；新增错误粒度三类区分（503/504 稍后重试、401/403 需用户介入、502 需重启服务）、对照证据定位法（用户反馈业务查不到时首要排查步骤）。
>
> **v4.3.0 浏览器 Cookie 导入增强复盘**：基于"浏览器 Cookie 导入增强（v20 加密 + 多 Profile + 自动同步）"复盘（使用 Sequential Thinking 4 维度分析），新增 9 项 B-REVIEW 检查点：B-REVIEW-ENCRYPTION-DEGRADATION（维度 7 加密升级退化策略）、B-REVIEW-MULTI-PROFILE-DISCOVERY（维度 16 多配置文件发现）、B-REVIEW-FILE-LOCK-BYPASS（维度 6 SQLite immutable 文件锁绕过）、B-REVIEW-SCHEDULER-ISOLATION（维度 9 独立调度器隔离）、B-REVIEW-CONFIG-DRIVEN-TOGGLE（维度 14 配置驱动功能开关）、B-REVIEW-FALLBACK-CHAIN（维度 11 降级链模式）、B-REVIEW-CHROME-136-ADAPTATION（维度 15 Chrome 136+ 限制适配）、B-REVIEW-WINDOWS-TEST-MOCK（维度 20 Windows 测试环境 Mock）、B-REVIEW-PLUGIN-DEPENDENCY-PRECHECK（维度 20 第三方插件依赖预检），自动化扫描从 42 项扩展到 51 项；所有新检查点均强调配置驱动（参数在 config/*.yaml 管理，不硬编码）与适用/不适用场景说明（确保通用性）。
>
> **v4.4.0 搜索参数链路 + 错误语义 + 硬编码阈值复盘**：基于"实时搜索错误提示语义偏差 + fast 模式跳过恢复机制 + 搜索参数配置不生效"三个问题复盘（使用 Sequential Thinking 4 维度分析），新增 5 项 B-REVIEW 检查点：B-REVIEW-ERROR-SEMANTICS（维度 7 错误提示语义准确性——RGV587=token 过期不应映射为 401 登录失效）、B-REVIEW-CONFIG-LINKAGE（维度 14 配置全链路生效验证——config.yaml→Config→TaskConfig→Worker→方法参数→URL 构建逐层追踪）、B-REVIEW-FAST-DEGRADATION（维度 11 快速模式降级重试——fast=True 跳过恢复机制时调用方应自动以非 fast 模式重试一次）、B-REVIEW-NO-HARDCODED-THRESHOLD（维度 9 硬编码阈值禁用——MAX_CONSECUTIVE_ERRORS=10 改为读取 fail_pause_threshold 配置）、B-REVIEW-PARAM-PASS-THROUGH（维度 5 参数透传链路完整性——方法签名新增参数后必须 grep 所有调用点确认传递），自动化扫描从 51 项扩展到 56 项。
>
> **v4.5.0 Cookie 分层管理架构修复复盘**：基于"5 个登录路径不更新 CookieRotator 层状态 + cookie_checker 覆盖手动失效 + MTOP Set-Cookie 不回写 JSON + update_cookie_values 并发非原子"问题复盘（使用 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 6 项 B-REVIEW 检查点：B-REVIEW-MULTI-WRITE-ENTRY（维度 10 状态同步统一入口——多入口写入同一份状态时必须有显式同步函数，禁止依赖未触发回调）、B-REVIEW-INACTIVE-STATE-PRESERVE（维度 10 状态条件区分——用 `updated_at == 0.0` 区分"从未初始化"与"主动失效"，避免补救逻辑覆盖手动失效）、B-REVIEW-BROWSER-FALLBACK-SYNC（维度 10 浏览器内存兜底——`/cookies/layers` 等状态查询端点两步同步，先从 JSON 补救仍有层未恢复时从浏览器内存兜底并回写）、B-REVIEW-UPDATE-VS-UPSERT（维度 6 持久化语义区分——`update_*` 只更新已存在、`upsert_*` 更新+添加，concurrent 场景必须在 RLock 内完成读-改-写）、B-REVIEW-POST-WRITE-HOOK（维度 14 写后钩子——写主数据源后必须显式调用同步钩子，失败仅记录日志不抛异常）、B-REVIEW-DEAD-CODE-CLEANUP（维度 13 死代码清理——大版本时主动 grep "定义未调用"的函数/回调并清理），自动化扫描从 56 项扩展到 62 项。
>
> **v4.6.0 异步超时 / 数据流转 / 过滤场景 / 复用模式复盘**：基于"评估明细标题采集超时 + 订单字段为空根因定位 + 一刀切过滤导致展示缺失"三个问题复盘（使用 Sequential Thinking 5 步系统分析——成功步骤 / 失败点 / 可抽象流程 / 适用场景 / 落地映射），新增 4 项 B-REVIEW 检查点：B-REVIEW-ASYNC-TIMEOUT（维度 9 异步操作整体超时保护——`await` 外部资源必须在调用层用 `asyncio.wait_for(coro, timeout=N)` 包装，超时返回 504 状态码，禁止依赖被调用方内部 timeout 参数）、B-REVIEW-DATA-FLOW-TRACE（维度 18 字段为空 5 点追踪——"字段为空"类问题必须按 DB schema → Repo 查询过滤 → API 注入 → 前端 types → render 取值 5 点逐层追踪）、B-REVIEW-FILTER-SCENARIO（维度 6 过滤逻辑场景区分——同一查询被多场景复用时必须参数化场景标志 `include_failed`，操作判断与展示历史场景区分）、B-REVIEW-REUSE-PATTERN（维度 13 复用既有模式——新增功能前必须 grep 项目内相似实现，复用既有 helper/工具函数/模式 `asyncio.wait_for` / `hmac.compare_digest` / `_escape_like` / `_utcnow`），自动化扫描从 62 项扩展到 66 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `async_timeout` / `data_flow_trace` / `filter_scenario` / `reuse_pattern` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。
>
> **v4.8.0 频率伪装统计孤岛复盘**：基于"反爬登录管理菜单的频率伪装统计持续为 0 且无变化"问题复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤 / 失败点 / 可抽象流程 / 适用场景），新增 3 项 B-REVIEW 检查点：B-REVIEW-ISLAND-MODULE（维度 13 孤岛模块检测——统计/计数器/采样类模块必须有业务调用方，否则视为孤岛，修复模式 grep 检测调用方 + Orchestrator 入口封装 + 业务模块集成 + 前端定时刷新）、B-REVIEW-TIME-SENSITIVE-SPLIT（维度 11 时间敏感场景的延迟/统计分离——业务操作存在延迟容忍度差异时核心模块必须提供"延迟+统计"与"仅统计"两种入口，fast 模式仅跳过 sleep 保持统计连续）、B-REVIEW-AUX-LOG-LEVEL（维度 12 辅助功能异常日志级别——辅助功能失败必须用 `logger.warning` 记录，禁止 `logger.debug`（默认不输出）和 `logger.error`（过度严重）），自动化扫描从 66 项扩展到 69 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `freq_disguise_stats` / `freq_disguise_time_sensitive` / `log_level_strategy` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.9.0 的 step 56-59。
>
> **v4.7.0 AntD 主题 token 动态覆盖复盘（后端同步原则）**：基于前端"暗色主题下 Table hover 高亮色与文字色一致导致不可见"问题复盘（使用 Sequential Thinking 5 步系统分析——成功步骤 / 失败点 / 可抽象流程 / 适用场景 / 落地映射），**未新增 B-REVIEW 检查点**。原因：后端不直接处理 antd 主题 token，业务场景过于狭窄。仅在后端层面同步以下原则：(1) 后端若提供"主题配置 API"（如 `/api/config/theme` 返回主题相关 token），所有 token 默认值应在 `config.yaml` 管理，不硬编码；(2) API 返回的 token 字段需与前端 `ConfigProvider` 中的 token 名保持一致（文档同步）；(3) 新增 token 字段时需提供默认值，避免前端取不到值（向后兼容）。本次复盘的详细编码规范整合到 `xianyu-hunter-dev` v4.8 的 step 55，前端审查规则落地到 `xianyu-frontend-code-review` v4.8.0 的 F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE（第 52 项）。后端自动化扫描项保持 66 项不变。
>
> **v4.8.0 状态管理与日志治理复盘**：基于"日志分析优化 + 代码评审复盘"（使用 Sequential Thinking 4 维度分析——成功步骤/失败点/可抽象流程/适用场景），新增 3 项 B-REVIEW 检查点：B-REVIEW-STATE-FLAG-PRECHECK（维度 9 状态标志前置检查完整性——检测到异常状态后后续操作入口必须有前置检查）、B-REVIEW-LOG-DOWNGRADE-STABILITY（维度 12 日志降级判断稳定性——判断字符串提取为模块级常量）、B-REVIEW-EDIT-VERIFY（维度 13 修改生效验证——Edit 后用 Grep 验证），自动化扫描从 86 项扩展到 89 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `state_flag_precheck` / `log_downgrade` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。
>
> **v4.5.0 Cookie 分层管理架构修复复盘**：基于"5 个登录路径不更新 CookieRotator 层状态 + cookie_checker 覆盖手动失效 + MTOP Set-Cookie 不回写 JSON + update_cookie_values 并发非原子"问题复盘（使用 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 6 项 B-REVIEW 检查点：B-REVIEW-MULTI-WRITE-ENTRY（维度 10 状态同步统一入口——多入口写入同一份状态时必须有显式同步函数，禁止依赖未触发回调）、B-REVIEW-INACTIVE-STATE-PRESERVE（维度 10 状态条件区分——用 `updated_at == 0.0` 区分"从未初始化"与"主动失效"，避免补救逻辑覆盖手动失效）、B-REVIEW-BROWSER-FALLBACK-SYNC（维度 10 浏览器内存兜底——`/cookies/layers` 等状态查询端点两步同步，先从 JSON 补救仍有层未恢复时从浏览器内存兜底并回写）、B-REVIEW-UPDATE-VS-UPSERT（维度 6 持久化语义区分——`update_*` 只更新已存在、`upsert_*` 更新+添加，concurrent 场景必须在 RLock 内完成读-改-写）、B-REVIEW-POST-WRITE-HOOK（维度 14 写后钩子——写主数据源后必须显式调用同步钩子，失败仅记录日志不抛异常）、B-REVIEW-DEAD-CODE-CLEANUP（维度 13 死代码清理——大版本时主动 grep "定义未调用"的函数/回调并清理），自动化扫描从 56 项扩展到 62 项。
>
> **v4.4.0 搜索参数链路 + 错误语义 + 硬编码阈值复盘**：基于"实时搜索错误提示语义偏差 + fast 模式跳过恢复机制 + 搜索参数配置不生效"三个问题复盘（使用 Sequential Thinking 4 维度分析），新增 5 项 B-REVIEW 检查点：B-REVIEW-ERROR-SEMANTICS（维度 7 错误提示语义准确性——RGV587=token 过期不应映射为 401 登录失效）、B-REVIEW-CONFIG-LINKAGE（维度 14 配置全链路生效验证——config.yaml→Config→TaskConfig→Worker→方法参数→URL 构建逐层追踪）、B-REVIEW-FAST-DEGRADATION（维度 11 快速模式降级重试——fast=True 跳过恢复机制时调用方应自动以非 fast 模式重试一次）、B-REVIEW-NO-HARDCODED-THRESHOLD（维度 9 硬编码阈值禁用——MAX_CONSECUTIVE_ERRORS=10 改为读取 fail_pause_threshold 配置）、B-REVIEW-PARAM-PASS-THROUGH（维度 5 参数透传链路完整性——方法签名新增参数后必须 grep 所有调用点确认传递），自动化扫描从 51 项扩展到 56 项。
>
> **v4.3.0 浏览器 Cookie 导入增强复盘**：基于"浏览器 Cookie 导入增强（v20 加密 + 多 Profile + 自动同步）"复盘（使用 Sequential Thinking 4 维度分析），新增 9 项 B-REVIEW 检查点：B-REVIEW-ENCRYPTION-DEGRADATION（维度 7 加密升级退化策略）、B-REVIEW-MULTI-PROFILE-DISCOVERY（维度 16 多配置文件发现）、B-REVIEW-FILE-LOCK-BYPASS（维度 6 SQLite immutable 文件锁绕过）、B-REVIEW-SCHEDULER-ISOLATION（维度 9 独立调度器隔离）、B-REVIEW-CONFIG-DRIVEN-TOGGLE（维度 14 配置驱动功能开关）、B-REVIEW-FALLBACK-CHAIN（维度 11 降级链模式）、B-REVIEW-CHROME-136-ADAPTATION（维度 15 Chrome 136+ 限制适配）、B-REVIEW-WINDOWS-TEST-MOCK（维度 20 Windows 测试环境 Mock）、B-REVIEW-PLUGIN-DEPENDENCY-PRECHECK（维度 20 第三方插件依赖预检），自动化扫描从 42 项扩展到 51 项；所有新检查点均强调配置驱动（参数在 config/*.yaml 管理，不硬编码）与适用/不适用场景说明（确保通用性）。
>
> **v4.2.0 反爬模块代码审查复盘**：基于反爬模块全面评估复盘，新增维度 24（跨字段一致性与硬编码属性禁用），补充检查项：dataclass 相关字段一致性校验、Cookie/HTTP 属性硬编码、`run_coroutine_threadsafe`+`future.result()` 跨线程死锁组合、try/finally 变量未初始化、跨组件状态双向同步、错误提示端点可操作性验证，自动化扫描从 36 项扩展到 42 项。
>
> **v4.1.0 会话失效处理复盘**：基于"实时搜索会话失效未推送明确错误提示"问题复盘，新增维度 11（重试失败后状态信号传递）+ 维度 7（Cookie 检查全面性）补充检查项，自动化扫描从 34 项扩展到 36 项；新增错误粒度三类区分（503/504 稍后重试、401/403 需用户介入、502 需重启服务）、对照证据定位法（用户反馈业务查不到时首要排查步骤）。
>
> **v4.0.0 事件时机/字段覆盖/幂等性/搜索标准化复盘**：基于 DingTalk 通知事件时机修复 + 评估详情字段覆盖策略 + 反爬登录幂等性 + 实时搜索标准化 + 代码评审通用规范复盘，新增维度 9（事件触发时机）、维度 13（注释一致性）、维度 17（字段覆盖策略）、维度 19（幂等性设计 + 搜索接口标准化）补充检查项，自动化扫描从 24 项扩展到 34 项。
>
> **v3.0.0 SonarQube 规则增强**：基于 SonarQube 修复实战复盘，扩展维度 9（异步与调度器）新增 S7503 规则检查、维度 13（代码质量）新增 S3776（认知复杂度）、S6767（未使用参数）、S1192（重复字符串）、S5843（正则复杂度）规则，补充实战案例（`login_orchestrator.start_session` 7 步拆分模式、`scheduler.start_all` 同步化），自动化扫描从 14 项扩展到 24 项；新增 Evaluator 构造检查（禁止接受覆盖参数）、KB 白名单检查、`CancelledError` 传播检查。
>
> **v2.1.0 新增维度 23（Git 操作规范）**：基于多分支合并实战复盘，新增 `.git/index.lock` 残留检测、产物文件 untrack、cherry-pick 冲突保留策略、async/await 一致性等检查项，自动化扫描从 12 项扩展到 14 项。
>
> **v2.0.0 知识点整合**：整合 `xianyu-hunter-dev` 技能的 `backend-guide.md`、`database-guide.md`、`chatbot-guide.md` 与 `project-rules.md` 硬约束，新增维度 1（分层架构）、4（Pydantic 2.x）、5（SQLAlchemy 2.0）、6（SQLite 优化）、9（异步与调度器）、10（事件总线）、16（Composition Root）、17（智能客服专项），扩展安全/性能/日志维度，自动化扫描 14 项。

## 配置驱动

**核心原则**：所有评审规则、硬约束、项目规范均通过 `config.yaml` 管理，技能本身不含任何业务参数或硬编码值。新增规则只需修改配置文件，无需改动技能本身。

配置文件位置：`.trae/skills/xianyu-backend-code-review/config.yaml`

首次使用时，从同目录的 `config.example.yaml` 复制并按项目实际情况修改。配置项分为 10 大类：

| 配置类 | 职责 | 关键参数 |
|--------|------|----------|
| `scope` | 评审范围 | include_paths, exclude_paths, file_extensions, max_files_per_run |
| `priority` | 优先级排序 | severity_order, category_order, report_threshold |
| `hard_constraints` | 硬约束规则 | rules（可扩展列表，每条含 name/pattern/message/severity/auto_fix） |
| `checklist` | 评审检查清单 | 35 大类开关 |
| `report` | 报告生成 | output_dir, format, include_good_practices, max_suggestions |
| `verify` | 验证配置 | run_tests_after_review, test_command, fail_on_critical |
| `project_conventions` | 项目专属规范参考 | auth_whitelist, required_indexes, webview2_config, kb_index, hf_endpoint |
| `meta_rules_33_35` | 🆕v4.31 注册式/根因扫描/字段契约配置节点 | backend_registration_endpoint / root_cause_chain_check / contract_owner_marker |
| `meta_rules_governance` | 🆕v4.33 规范治理配置节点 | sedimentation_threshold / degradation_threshold / observation_period_quarters / sedimentation_exemption_categories / degradation_exemption_categories |
| `meta_rules_38_42` | 🆕v4.34 列表聚合与状态联动配置节点 | global_aggregate_filter / cross_domain_inject / linked_switch_priority / precheck_structured_fields / config_fallback_defaults |

## 审查模式

| 模式 | 扫描范围 | 触发 |
|------|---------|------|
| 快速自检 | 仅阻塞级 | `pwsh .trae/skills/xianyu-backend-code-review/scripts/auto-scan.ps1` |
| 增量审查 | `git diff --name-only` 变更文件 | 粘贴变更文件列表 |
| 指定文件审查 | 用户明确列出的文件 | 用户指定路径 |
| 片段评审 | 用户粘贴代码片段 | 无文件路径时仅输出建议 |
| 全量审查 | `src/xianyu_hunter/**/*.py` | 默认 |

---

## 审查规则（30 项维度）

### 1. 分层架构 🆕v2.0

- 【强制】依赖单向 `web → modules → infra → domain`，`domain` 不依赖任何层
- 【强制】`container.py` 是唯一 Composition Root，合法依赖所有层
- 【强制】路由层文件命名为 `api_<域>.py`（如 `api_tasks.py`、`api_items.py`）
- 【强制】仓储层文件命名为 `repo_<域>.py`（Mixin 模式组合为 `repository.py`）
- 【强制】领域模型用 `@dataclass`，Web 层用 `pydantic.BaseModel`
- 【禁止】跨层调用：路由直接访问 ORM 对象、领域包引入框架注解
- 【禁止】循环依赖：A → B → C → A

**判断规则**：
- `web/routes/` → 仅 HTTP 解析与响应组装，业务逻辑下沉到 `modules/` 或 `web/services/`
- `modules/` → 业务编排，可调用 `infra/` 与 `domain/`
- `infra/` → 基础设施（DB、浏览器、密钥、日志），不感知业务
- `domain/` → 纯数据结构 + Enum，无 IO 依赖

### 2. 命名规范

- 【强制】模块：snake_case（如 `price_strategy.py`）
- 【强制】类：PascalCase（如 `TaskMode`、`Task`、`TaskRow`、`TaskCreate`）
- 【强制】DB Row 类：`*Row` 后缀（如 `TaskRow`、`ItemRow`、`OrderRow`）
- 【强制】配置类：`*Config` 后缀（如 `AppConfig`、`BrowserConfig`）
- 【强制】函数/方法：snake_case（如 `build_default_container`、`list_tasks_with_last_seen`）
- 【强制】常量：UPPER_SNAKE_CASE（如 `_IDENT_RE`、`_TASK_NOT_FOUND`）
- 【强制】私有辅助：`_` 前缀（如 `_load_secrets_from_keyring`、`_migrate_add_column`、`_escape_like`、`_utcnow`）
- 【推荐】文案常量提取到模块级（SonarQube S1192），如 `_TASK_NOT_FOUND = "任务不存在"`

### 3. 类型注解

- 【强制】全面使用类型注解，采用 Python 3.10+ 现代语法（`X | None` 而非 `Optional[X]`）
- 【强制】函数签名标注参数与返回类型
- 【推荐】复杂类型用 `TypeAlias` 提升可读性
- 【禁止】滥用 `Any`，必要时用 `Unknown` + 类型守卫
- 【强制】泛型容器标注元素类型（`dict[str, Any]` 而非 `dict`，`list[int]` 而非 `list`）

```python
# ✅ 推荐：Python 3.10+ 现代语法
@dataclass
class Task:
    search_config: dict[str, Any] | None  # None 表示沿用全局配置
    price_config: dict[str, Any] | None
```

### 4. Pydantic 2.x 模型 🆕v2.0

- 【强制】Web 层请求/响应模型继承 `pydantic.BaseModel`
- 【强制】使用 `Field(..., min_length=N, max_length=N)` 约束
- 【强制】区分"未传"与"传 null"：用 `model_dump(exclude_unset=True)`
- 【强制】Pydantic 2.x 写法（`model_dump` / `model_validate`），禁止 Pydantic 1.x 的 `.dict()` / `.json()`
- 【推荐】响应模型显式声明 `response_model`，避免返回 `dict | JSONResponse` 联合类型（兼容性需设为 `None`）
- 【强制】领域模型用 `@dataclass`，**不**用 Pydantic

```python
# ✅ 推荐：Pydantic 2.x 风格
class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    search_config: dict[str, Any] | None = None

data = task_create.model_dump(exclude_unset=True)
```

### 5. SQLAlchemy 2.0 规范 🆕v2.0

- 【强制】使用 DeclarativeBase + `Mapped` + `mapped_column` 风格（禁止 1.x 的 `Column(Integer)` 风格）
- 【强制】所有时间字段统一 UTC，用 `_utcnow = lambda: datetime.now(timezone.utc)`（禁止已弃用的 `datetime.utcnow()`）
- 【强制】所有 schema 变更必须**幂等**：`_migrate_add_column`、`_migrate_create_index`（`IF NOT EXISTS`）、`_migrate_make_column_nullable`（SQLite 表重建）
- 【强制】SQL 注入防护：
  - LIKE 查询必须用 `_escape_like()` 转义 `%` 和 `_`
  - 表名/列名用 `_IDENT_RE = re.compile(r'^[A-Za-z_]\w*$', re.ASCII)` 白名单校验
  - 用户 ID 用 `_USER_ID_RE`（`^[A-Za-z0-9_-]+$`）校验，防路径遍历
- 【推荐】UPSERT 用 `sqlite_insert(...).on_conflict_do_update(index_elements=[...], set_=...)`
- 【推荐】软删除在 SQL 层过滤（避免 limit/offset 截断）

```python
# ✅ 推荐：SQLAlchemy 2.0 风格
class Base(DeclarativeBase): ...

class TaskRow(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
```
- 🆕v4.4【强制】**B-REVIEW-PARAM-PASS-THROUGH：参数透传链路完整性**
  - 方法签名新增参数时，必须同步更新所有内部调用点传递该参数，**禁止**只在外层方法签名添加而内部调用点遗漏
  - **判断信号**：`git diff` 显示方法签名新增参数 → 必须 grep 方法名检查所有调用点（包括内部 `_private` 方法的调用）是否传递新参数
  - **检查方法**：从方法签名 → 内部调用 `_call_xxx(new_param=new_param)` → 内部调用 `build_url(new_param=new_param)` → 最终 URL 查询参数追加，逐层验证
  - **配置参数**：无（纯代码审查检查项）
  - **适用**：方法签名新增参数后的所有内部调用点，尤其是跨层参数传递（API → Module → Domain → URL Builder）
  - **不适用**：向后兼容的可选参数（有默认值且不影响现有行为）
  - **历史教训**：`search()` 方法新增 `sort_type`/`regions` 参数后，`_call_search_api()` 内部 `build_search_url(keyword)` 未传这两个参数，导致 RGV587 重试时 URL 中丢失排序和地区参数

### 6. SQLite 优化与索引规约 🆕v2.0

- 【强制】引擎创建必须配置：
  - `poolclass=NullPool`（避免跨线程 cursor 竞争，**禁止** StaticPool）
  - `connect_args={"timeout": 10, "check_same_thread": False}`
  - `PRAGMA journal_mode=WAL`
  - `PRAGMA busy_timeout=10000`
  - `PRAGMA cache_size=-20000`
- 【强制】以下字段必须建索引：`task_id`、`seller_id`、`first_seen`、`publish_time`、`created_at`、`request_id`
- 【强制】必须建立复合索引以优化 Dashboard 查询
- 【强制】`_overview()` 中的 COUNT 查询必须用 `CASE WHEN` 聚合合并，减少 DB 调用 67%
- 【强制】函数内冗余导入必须移至模块级别
- 【推荐】批量操作用 `session.bulk_insert_mappings` / `session.bulk_update_mappings`
- 【推荐】大结果集用 `yield_per(N)` 流式加载，禁止全表加载到内存
- 【强制】**索引一致性双写**：ORM `__table_args__` 中的 `Index(...)` 必须与 `init_db()` 中的 `_migrate_create_index(...)` 双向同步
  - ORM 有定义但 init_db 无迁移调用 → 已有数据库缺失索引（全表扫描）
  - init_db 有迁移调用但 ORM 无定义 → 新建数据库缺失索引
  - 两者索引名必须一致
- 【强制】复合索引按"过滤列 + 排序列"顺序设计：`(task_id, link_type, created_at)` 而非 `(created_at, task_id, link_type)`
- 🆕v4.3【强制】**B-REVIEW-FILE-LOCK-BYPASS：文件锁绕过模式（SQLite immutable）**
  - 并发访问被锁文件时，使用 SQLite URI `immutable=1` 参数打开只读数据库，绕过 Windows 文件锁机制
  - **判断信号**：Windows 文件锁报错（`database is locked` / `unable to open database`）+ 只读访问需求 + SQLite 数据库
  - **修复模式**：构建 URI `file:./Cookies?immutable=1` → 用 `sqlite3.connect(uri=True)` 打开 → 仅执行 SELECT 查询
  - **配置参数**：`immutable_flag` 默认 `true`，`lock_timeout_ms` 在 `config.yaml` 的 `sqlite_file_lock` 节点管理
  - **适用**：浏览器 cookie 数据库并发访问、Windows 文件锁定机制、需要只读访问的共享资源
  - **不适用**：需要写入的场景、Linux 文件锁（建议用 `flock`）、原子写场景
  - **历史教训**：浏览器运行时持有 `Cookies` 数据库写锁，传统 `sqlite3.connect()` 打开失败，改用 `immutable=1` 后可并发读取
- 🆕v4.5【强制】**B-REVIEW-UPDATE-VS-UPSERT：Update vs Upsert 语义区分**
  - 持久化层（CookieStore / Repository）必须明确区分"Update"和"Upsert"两类操作，**禁止**用一个方法兼顾两种语义
  - **判断信号**：函数命名含 `update` 但实际行为是"更新或新增"，或反之 → 维护者无法从命名判断行为
  - **修复模式**：
    - **`update_cookie_values(updates)`**：只更新已存在的 cookie（name 在 JSON 中存在 → 替换 value；不存在 → 跳过）。用于 token 刷新场景
    - **`upsert_cookie_values(upserts)`**：更新已存在 + 添加不存在（name 在 JSON 中存在 → 替换 value；不存在 → 追加新条目）。用于浏览器兜底回写场景
  - **关键约束**：upsert 必须携带完整属性（`value`/`domain`/`path`/`expires`），不能只传 value 因为新条目需要完整字段
  - **并发安全**：读-改-写必须在 `self._lock`（`RLock`）内完成，避免与并发 `export_cookies` 交错导致数据丢失
  - **元数据保护**：方法标签（如 `data["method"]`）必须用 `if "mtop_refresh" not in existing_method: data["method"] = existing_method + "+mtop_refresh"` 避免无限追加
  - **配置参数**：`update_methods`（只更新已存在）、`upsert_methods`（更新+添加）方法名列表在 `config.yaml` 的 `persistence_semantics` 节点管理
  - **适用**：所有持久化层的数据合并操作（Cookie / 缓存 / 索引）
  - **不适用**：纯 add-only 日志、纯 replace 全量覆盖
  - **历史教训**：MTOP 刷新 `_m_h5_tk` 时若用 `update_*` 但 JSON 中没有该条目 → 静默丢失；反之若用 `upsert_*` 但 JSON 中已有 → 字段被覆盖（如 `expires`）→ 下次过滤过期逻辑失效
- 🆕v4.6【强制】**B-REVIEW-FILTER-SCENARIO：过滤逻辑场景区分**
  - 同一查询函数被多个场景复用时，过滤逻辑必须**参数化场景标志**（如 `include_failed` / `include_deleted` / `scope`），调用方按使用场景传值，**禁止**一刀切过滤导致展示页看不到完整数据
  - **判断信号**：函数命名含 `list_*` / `get_*` / `query_*` 且 `grep` 多个调用点 → 检查过滤逻辑是否硬编码（如 `if status == 'failed': continue`）→ 必须改为参数化
  - **修复模式**：增加 `include_failed: bool = False` 参数 → 默认安全（跳过失败数据，不影响现有逻辑）→ 调用方按场景显式传值（操作判断场景 False / 展示历史场景 True）→ 函数 docstring 说明两种场景用途 → 新增回归测试覆盖两种场景
  - **关键约束**：
    - 场景标志必须**默认安全**（`include_failed=False` 默认跳过失败，避免影响现有逻辑）
    - 调用方必须**显式传值**（如 `include_failed=True`），不依赖默认值
    - 必须新增**回归测试**覆盖两种场景
  - **配置参数**：`scenario_flag_field`（默认 `include_failed`）、`status_whitelist`（默认 `['succeeded', 'pending']`）、`multi_scene_callsites`（多场景调用点列表）在 `config.yaml` 的 `filter_scenario` 节点管理
  - **适用**：同一查询被"操作判断"与"展示历史"两种场景复用，尤其是订单/任务/日志类查询
  - **不适用**：单一场景的查询（如报表统计只看成功）、有独立 Repo 方法的查询、权限过滤（应单独抽取）
  - **历史教训**：`list_orders_by_item_ids` 无条件 `if status == 'failed': continue`，导致评估明细页看不到失败订单记录，用户点击抢单失败后刷新页面看到 "—"，误以为没下过单而反复触发抢单。修复后增加 `include_failed` 参数，评估明细调用传 `True`
- 🆕v4.11【强制】**B-REVIEW-MIGRATION-FAILURE-HANDLING：DB 迁移失败处理**
  - `_migrate_*` 函数失败必须明确处理策略：关键迁移（schema 变更/列类型修改）失败 `raise RuntimeError` 中断启动；非关键迁移（索引补建/数据回填）失败 `logger.warning` + 继续启动，**禁止** `except: pass` 静默吞掉
  - **核心机制**（审查时必须理解）：
    - 关键迁移失败会导致后续代码访问不存在的列/表，应立即中断启动而非带病运行
    - 非关键迁移失败（如索引补建）不影响功能，仅影响性能，应记录日志后继续启动
    - `except: pass` 会吞掉所有异常（包括 KeyError、AttributeError 等编程错误），导致问题隐藏
    - 幂等性检查（如 "duplicate column" 错误）应识别并跳过，不视为失败
  - **判断信号**：
    - 代码含 `def _migrate_*` 函数 + `try/except` 块 → except 块必须明确记录日志或抛出，禁止 `pass`
    - 代码含 `except: pass` 或 `except Exception: pass` 在 `_migrate_*` 函数中 → 视为违规
    - 代码含 `except Exception as e: logger.debug(...)` 在 `_migrate_*` 函数中 → 视为违规（debug 默认不输出）
  - **修复模式**：
    ```python
    # ✅ 关键迁移：失败必须中断
    def _migrate_add_column(conn, table: str, column: str, sql_type: str) -> None:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                return  # 幂等，已存在则跳过
            raise RuntimeError(f"关键迁移失败 {table}.{column}: {e}") from e

    # ✅ 非关键迁移：失败 warning + 继续
    def _migrate_create_index(conn, name: str, table: str, columns: list[str]) -> None:
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({', '.join(columns)})")
        except Exception as e:
            logger.warning("非关键索引迁移失败 {}：{}（不影响启动）", name, e)

    # ❌ 错误：silent pass 吞掉所有异常
    # def _migrate_create_index(conn, name, table, columns):
    #     try:
    #         conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({', '.join(columns)})")
    #     except: pass  # 关键迁移失败也被吞掉
    ```
  - **配置参数**：`migration_failure_strategy.critical_migrations`（关键迁移函数名列表，如 `["_migrate_add_column", "_migrate_make_column_nullable"]`，失败 raise）、`migration_failure_strategy.non_critical_migrations`（非关键迁移函数名列表，如 `["_migrate_create_index", "_migrate_backfill_data"]`，失败 warn）、`migration_failure_strategy.default_strategy`（默认 `warn`，可选 `raise`）在 `config.yaml` 的 `migration_failure_strategy` 节点管理
  - **适用**：所有 `_migrate_*` 函数（_migrate_add_column / _migrate_create_index / _migrate_make_column_nullable / _migrate_backfill_data）；数据库 schema 变更
  - **不适用**：迁移幂等性检查（已通过"duplicate column"等错误识别处理）；测试代码中的迁移；运行时数据修复（非迁移）
  - **历史教训**：`_migrate_create_index` 失败被 `except: pass` 吞掉，生产数据库索引长期缺失导致 Dashboard 查询慢 10 倍，但日志无任何记录
- 🆕v4.25【强制】**B-REVIEW-MIGRATION-BLOCK-ISOLATION：迁移块独立容错**
  - 迁移函数（如 `run_migrations`）内含多个独立迁移块（如 C-01 task_links 重建 / C-02 orders.task_id 添加列 / C-03/C-04/C-05 等）时，**每个迁移块必须各自 try/except**，禁止外层统一 try/except 吞掉异常导致后续迁移块全部跳过
  - **核心机制**（审查时必须理解）：
    - 迁移块之间通常是**逻辑独立**的（C-01 重建 task_links 表与 C-04 添加 notifications.read_at 列无依赖关系），一个块失败不应影响其他块
    - 外层统一 try/except 会让第一个失败的块中断所有后续迁移，导致数据库 schema 与 ORM 不一致，运行时 INSERT/SELECT 才报 "no such column"
    - 外层 try/except 还会**吞掉异常**（仅记录 warning），使问题隐藏在日志中难以发现
    - **强依赖场景**允许合并：如 C-01 task_links 表重建 + 历史数据回填必须在同一事务内完成（回填依赖表存在），此时可合并为一个 try/except
  - **判断信号**：
    - 代码含 `def run_migrations` / `def _migrate_*` 函数 + 内含多个 `# C-01` / `# C-02` 注释块 → 检查每个块是否各自 try/except
    - 代码含外层 `try: ... except Exception as e: logger.warning(f"启动迁移钩子失败: {e}")` 包裹多个迁移块 → 视为违规
    - 代码含 `auto_migrate_task_links()` 等可能抛异常的调用 + 后续迁移块在同一 try 内 → 视为违规
  - **修复模式**：
    ```python
    # ✅ 每个迁移块各自 try/except
    def run_migrations(container: Any) -> None:
        insp = sa_inspect(container.repo.engine)
        # C-01: task_links 表重建 + 历史数据回填（强依赖，合并为一个 try）
        try:
            _rebuild_task_links_table(insp, container)
            inserted = container.repo.auto_migrate_task_links()
            logger.info(f"task_links auto-migrate: 新增 {inserted} 条")
        except Exception as e:
            logger.warning(f"C-01 task_links 迁移失败（忽略，不影响后续迁移）: {e}")

        # C-02: orders.task_id 列添加（独立）
        try:
            _ensure_orders_task_id_column(insp, container)
        except Exception as e:
            logger.warning(f"C-02 orders.task_id 迁移失败（忽略）: {e}")

        # C-03/C-04/C-05 同样各自独立 try/except...

    # ❌ 错误：外层统一 try/except 吞掉异常
    # def run_migrations(container):
    #     try:
    #         _rebuild_task_links_table(...)  # C-01 失败 → C-04 被跳过
    #         _ensure_orders_task_id_column(...)  # C-02
    #         _add_notifications_read_at_column(...)  # C-04 被跳过 → read_at 列不存在
    #     except Exception as e:
    #         logger.warning(f"启动迁移钩子失败: {e}")  # 异常被吞掉
    ```
  - **关键约束**：
    - 迁移块边界标识符（如 `C-01`/`C-02` 注释）应在 `config.yaml` 的 `migration_block_isolation.block_markers` 管理，便于自动化扫描识别块边界
    - 强依赖场景（如表重建 + 数据回填）允许合并为一个 try/except，但必须在注释中说明合并原因
    - 每个块的 except 必须用 `logger.warning` 或 `logger.exception` 记录（与 B-REVIEW-MIGRATION-FAILURE-HANDLING 一致），禁止 `except: pass`
    - 与 B-REVIEW-CRITICAL-PATH-NO-SWALLOW 联动：外层启动钩子的 except 必须用 `logger.exception()` 输出完整 traceback
  - **配置参数**：`migration_block_isolation.function_patterns`（迁移函数名模式，如 `["run_migrations", "_migrate_*"]`）、`migration_block_isolation.block_markers`（块边界标识符，如 `["C-01", "C-02", "C-03", "C-04", "C-05"]`）、`migration_block_isolation.require_independent_try`（是否要求各自 try/except，默认 `true`）、`migration_block_isolation.allow_merge_when_dependent`（强依赖时允许合并，默认 `true`）、`migration_block_isolation.violation_message`（违规提示模板）在 `config.yaml` 的 `migration_block_isolation` 节点管理
  - **适用**：含多个独立迁移块的迁移函数（`run_migrations` / `_migrate_all_*`）；数据库 schema 增量迁移；启动时的初始化迁移
  - **不适用**：单一迁移块（无独立性问题）；强依赖的迁移步骤（如表重建 + 数据回填，允许合并）；事务内 DDL（由 B-REVIEW-MIGRATION-TRANSACTION 管控）
  - **历史教训**：`run_migrations()` 内 C-01 步骤 `auto_migrate_task_links()` 抛异常，外层 `_on_startup` 的 `try/except` 吞掉异常，导致 C-04（添加 `notifications.read_at` 列）被跳过。运行时 `add_notification` 的 UPSERT INSERT 报 `sqlite3.OperationalError: no such column: notifications.read_at`。修复后改为每个迁移块各自 try/except，问题彻底解决
- 🆕v4.25【强制】**B-REVIEW-111: NOT-NULL-NONE-DEFENSE：NOT NULL 字段 None 防御检查**
  - NOT NULL 字段收到 null 时必须**防御性 pop**（从 update_data 中移除），**禁止**直接写入 DB 触发 `IntegrityError`；覆盖字段收到 null 表示"清除覆盖"应正常写入 None
  - **核心机制**（审查时必须理解）：
    - NOT NULL 字段（如 `task_id`/`seller_id`/`created_at`）传 null 是非法操作，应 pop 后记录 WARNING 日志
    - 覆盖字段（如 `price_config`/`score_config` 等 nullable 字段）传 null 是合法的"清除覆盖"语义，应正常写入 None
    - 必须区分"NOT NULL 约束字段"与"可空覆盖字段"，**不能**一刀切 pop 所有 None
  - **判断信号**：
    - 更新逻辑中出现 `await session.execute(update(Task).where(...).values(**update_data))` 但未检查 NOT NULL 字段是否为 None → 视为违规
    - 对所有 None 字段一刀切 `update_data.pop(k)` 导致覆盖字段无法清除 → 视为违规
    - NOT NULL 字段传 null 触发 `sqlite3.IntegrityError: NOT NULL constraint failed` → 视为违规
    - 代码中出现 `try: await session.commit() except IntegrityError: pass` 吞掉 NOT NULL 错误 → 视为违规
  - **修复模式**：
    ```python
    # ✅ 区分 NOT NULL 字段与覆盖字段
    _NOT_NULL_FIELDS = {"task_id", "seller_id", "created_at", "updated_at"}  # 从 schema 定义读取

    async def update_task(task_id: str, update_data: dict):
        # NOT NULL 字段传 null → 防御性 pop + WARNING
        for field in list(update_data.keys()):
            if field in _NOT_NULL_FIELDS and update_data[field] is None:
                logger.warning(f"NOT NULL 字段 {field} 收到 null，已跳过更新 (task_id={task_id})")
                update_data.pop(field)
        # 覆盖字段（nullable）传 null → 正常写入 None（表示清除覆盖）
        await session.execute(update(Task).where(Task.id == task_id).values(**update_data))
        await session.commit()

    # ❌ 违规：直接写入触发 IntegrityError
    async def update_task(task_id: str, update_data: dict):
        await session.execute(update(Task).where(Task.id == task_id).values(**update_data))
        # 若 update_data 含 task_id=None → IntegrityError

    # ❌ 违规：一刀切 pop 所有 None，覆盖字段无法清除
    async def update_task(task_id: str, update_data: dict):
        for k in list(update_data.keys()):
            if update_data[k] is None:
                update_data.pop(k)  # price_config=None 也被 pop，无法清除覆盖
    ```
  - **关键约束**：
    - 必须从 ORM 模型 / DB schema 读取 NOT NULL 字段列表，**禁止**硬编码
    - NOT NULL 字段传 null 时 pop + `logger.warning`（含字段名 + 主键）
    - 覆盖字段（nullable）传 null 时正常写入 None
    - **禁止**用 `except IntegrityError: pass` 吞掉 NOT NULL 错误
    - 配合 B-REVIEW-110 EXCLUDE-UNSET-CHECK：先 `model_dump(exclude_unset=True)` 再 NOT NULL 防御
  - **配置参数**：`api_update_semantics.not_null_fields`（NOT NULL 字段列表，从 ORM 模型自动读取或显式配置）、`api_update_semantics.nullable_override_fields`（可空覆盖字段列表）、`api_update_semantics.require_warning_on_null_pop`（默认 `true`，NOT NULL 字段被 pop 时必须记录 WARNING）在 `config.yaml` 的 `api_update_semantics` 节点管理
  - **适用**：所有含 NOT NULL 约束字段的更新接口；任务级配置覆盖功能；支持"传 null 清除覆盖"语义的接口
  - **不适用**：POST 创建接口（创建时 NOT NULL 字段缺失应被 Pydantic 校验拦截）；无 NOT NULL 约束的表；纯查询接口
  - **历史教训**：任务级配置覆盖功能中，`update_data = body.model_dump(exclude_unset=True)` 后直接 `session.execute(update(...).values(**update_data))`，但用户传 `{"task_id": null}`（误操作）触发 `IntegrityError: NOT NULL constraint failed: tasks.task_id`，导致整个更新事务回滚，合法的 `price_config=null`（清除覆盖）也未生效。修复后增加 NOT NULL 字段防御性 pop + WARNING 日志

### 7. 安全性评审

- 【强制】凭据比较必须使用 `hmac.compare_digest()` 防止时序攻击（**禁止** `==`）
- 【强制】敏感字段（token 长度、密码）避免写入日志，仅记录布尔匹配结果
- 【强制】Token 写入失败必须触发 `logging.warning()` 告警
- 【强制】401 响应必须返回 JSON `{"detail": "Unauthorized"}`（禁止纯文本）
- 【强制】认证白名单端点完整配置（见 `project_conventions.auth_whitelist`）
- 【强制】禁止硬编码凭据（密码、token、API key、钉钉推送 Key）
- 【强制】敏感字段（推送 Key 等）写入 keyring（Windows DPAPI），**不**写入 `.env` 或 `config.yaml` 明文
- 【强制】SQL 注入防护（见维度 5）
- 【强制】智能客服用户输入必须经 `check_user_input_safety()` 检测 Prompt Injection
- 【强制】命令注入防护：`subprocess` 参数用列表形式，禁止 shell=True 拼接用户输入
- 【强制】Chrome Cookie 解密用 `cryptography` AES-256-GCM（49.0.0+）
- 【推荐】CORS 配置收紧 origin，禁止 `*`
- 🆕v4.1【强制】**B-REVIEW-COOKIE-CHECK：Cookie 检查全面性**：依赖多类 Cookie 的接口前置检查必须覆盖**所有**关键 token
  - 检查清单：身份 Cookie（如 `cookie2`/`sgcookie`/`unb`）+ 会话 token（如 `_m_h5_tk`），清单在 `config.yaml` 的 `cookie_check_lists` 节点管理
  - **禁止**只检查身份 Cookie 存在性而忽略会话 token 有效性
  - 失效处理：抛 `HTTPException(401)` + 明确指引（如"会话 token 已过期，请重新登录"）
  - **判断信号**：接口含 `_ensure_*_cookies` 或前置 Cookie 检查函数 → 必须覆盖会话 token
  - **历史教训**：`_ensure_live_search_cookies` 只检查身份 Cookie 存在性，`_m_h5_tk` 已过期但检查通过，导致搜索失败但前端无明确提示
- 🆕v4.3【强制】**B-REVIEW-ENCRYPTION-DEGRADATION：加密升级退化策略模式**
  - 依赖外部进程/资源的加密机制（如 Chrome v20 App-Bound Encryption）无法离线解密时，必须选择运行时接管（CDP/IPC）而非等待离线解密方案
  - **判断信号**：加密依赖外部进程状态 + IElevator/COM 接口 + 本地密钥不可访问 + 文档标注"App-Bound"
  - **修复模式**：检测到 v20 加密 → 探测 CDP 端点可达性 → `Playwright.connect_over_cdp()` 接管运行中浏览器 → 通过 `Network.getAllCookies` 获取解密后 cookie
  - **配置参数**：加密方案识别标志、CDP 端口、降级方案优先级在 `config.yaml` 的 `encryption_solutions` 节点管理（不硬编码）
  - **适用**：依赖外部进程的加密（Chrome v20）、DRM 保护机制、需要在线状态验证的场景
  - **不适用**：可离线解密的加密（v10 AES）、依赖本地密钥的对称加密、静态资源处理
  - **历史教训**：v20 App-Bound Encryption 无法用 `CryptUnprotectData` 离线解密，调研后选择 CDP 接管方案而非 IElevator COM 或智能降级
- 🆕v4.4【强制】**B-REVIEW-ERROR-SEMANTICS：错误提示语义准确性**
  - 面向用户的错误提示必须与实际错误原因语义匹配，**禁止**将特定错误码映射为不相关的语义
  - **判断信号**：后端将特定错误码（如 RGV587）映射为 HTTP 状态码时，状态码语义必须与错误码根因一致
  - **修复模式**：错误码根因分析 → 选择语义匹配的状态码 → 提示文案与根因一致 → 提供正确的操作出口（"稍后重试" vs "重新登录"）
  - **配置参数**：错误码到状态码的映射、提示文案模板在 `config.yaml` 的 `error_code_mappings` 节点管理（不硬编码）
  - **适用**：所有面向用户的错误提示（API 响应 detail、SSE error 事件）
  - **不适用**：内部调试日志、堆栈跟踪
  - **历史教训**：RGV587 是 mtop API 的 `_m_h5_tk` 临时 token 过期（TTL 1 小时），不是浏览器 Cookie/登录态失效，但后端映射为 HTTP 401("闲鱼登录已过期")，前端显示"Cookie 失效或会话过期"。实际多查几次能成功——说明不是登录态失效
- 🆕v4.11【强制】**B-REVIEW-STATUS-CODE-SEMANTICS：状态码语义精细化**
  - HTTP 状态码必须按语义精细化区分：`401` 未登录 / `403` 权限不足 / `440` Cookie 过期（需重新登录）/ `441` Token 过期（需刷新）/ `504` 网关超时，**禁止**所有认证失败都映射为 `401` 导致前端无法区分"未登录"与"登录态过期"
  - **核心机制**（审查时必须理解）：
    - `401 Unauthorized`：完全未登录，前端应跳转登录页
    - `403 Forbidden`：已登录但无权限，前端应提示"权限不足"
    - `440 Login Timeout`（非标准但广泛使用）：Cookie 过期，前端应跳转重新登录页（区别于 401）
    - `441 Token Expired`（项目自定义）：临时 Token（如 `_m_h5_tk`）过期，前端应静默刷新 Token 后重试
    - `504 Gateway Timeout`：网关超时，前端应提示"稍后重试"
    - 所有认证失败都映射为 401 会导致前端无法区分应"跳转登录页"还是"刷新 Token"
  - **判断信号**：
    - 代码含 `raise HTTPException(status_code=401)` 出现在 Cookie 检查 / Token 刷新 / 登录校验等多处 → 必须按语义区分状态码
    - 代码含 `if is_cookie_expired(): raise HTTPException(401, "Cookie 过期")` → 应改为 `raise HTTPException(440, ...)`
    - 代码含 `if is_m5tk_expired(): raise HTTPException(401, "Token 过期")` → 应改为 `raise HTTPException(441, ...)`
    - 前端代码含 `if (status === 401) redirect("/login")` 但实际可能是 Cookie 过期 → 需按状态码区分跳转
  - **修复模式**：
    ```python
    # ✅ 按语义区分状态码
    if not identity_cookies:
        raise HTTPException(401, "未登录，请先登录")  # 完全未登录
    if is_cookie_expired(identity_cookies):
        raise HTTPException(440, "Cookie 已过期，请重新登录")  # 登录态过期
    if is_m5tk_expired(session_cookies):
        raise HTTPException(441, "会话 Token 已过期，请刷新")  # 临时 token 过期
    if not has_permission(user, action):
        raise HTTPException(403, "权限不足")  # 已登录但无权限

    # ❌ 错误：所有认证失败都映射为 401
    # if is_cookie_expired(): raise HTTPException(401, "Cookie 过期")
    # if is_m5tk_expired(): raise HTTPException(401, "Token 过期")
    # if not has_permission(): raise HTTPException(401, "权限不足")
    ```
  - **配置参数**：`status_code_semantics.mapping`（错误场景到状态码的映射，如 `cookie_expired → 440`、`token_expired → 441`、`not_logged_in → 401`、`permission_denied → 403`、`gateway_timeout → 504`）、`status_code_semantics.frontend_actions`（状态码到前端动作的映射，如 `401 → redirect_login`、`440 → redirect_relogin`、`441 → refresh_token`、`504 → retry_later`）在 `config.yaml` 的 `status_code_semantics` 节点管理
  - **适用**：所有认证相关 API（登录/Cookie 校验/Token 刷新/权限检查）；SSE error 事件的状态码字段
  - **不适用**：业务错误（如 404 资源不存在、409 状态冲突、422 参数校验失败）；纯内部 API；健康检查端点
  - **历史教训**：Cookie 过期、Token 过期、未登录全部映射为 `401`，前端无法区分应"跳转登录页"还是"刷新 Token"，导致用户反复被踢出登录

### 8. 性能评审

- 【强制】N+1 查询检测（循环内查询数据库）
- 【强制】批量操作用批量接口（如批量 embedding、`bulk_insert_mappings`）
- 【强制】异步端点必须用 `asyncio.to_thread` 包装同步阻塞操作（如 SQLite 同步仓储在 async 路由中调用）
- 【禁止】async 代码中调用阻塞 IO（如 `requests.get`、`time.sleep`）
- 【推荐】缓存机会识别（`@lru_cache` 配置加载、`functools.cache` 纯函数）
- 【推荐】大文件边读边处理，禁止一次性 `read()` 全部到内存
- 【推荐】正则表达式预编译为模块级 `re.compile`，禁止循环内 `re.match`
- 【强制】关键查询方法必须有性能埋点：方法入口 `time.monotonic()`，出口计算 elapsed_ms，超过阈值 `logger.warning`（Repository 层 100ms，API 层 200ms）
- 【强制】慢查询告警必须包含关键上下文：task_id、查询参数、行数、耗时
- 【推荐】`list_and_count_*` 类方法（单次查询返回列表+计数）应有埋点，替代分别调用 `list_*` + `count_*` 的模式

### 9. 异步与调度器 🆕v2.0

- 【强制】FastAPI 路由全部 `async def`，与 ASGI 兼容
- 【强制】SQLite 仓储同步实现（避免 async 开销，单进程足够）
- 【强制】`asyncio.Task` 必须保留引用防 GC（存入 `set` 或属性）
- 【强制】`asyncio.CancelledError` 必须用 `contextlib.suppress(asyncio.CancelledError)` 包裹 await
- 【强制】5 类调度器（APScheduler）职责清晰：
  1. 主任务调度器
  2. EventBus 后台消费器
  3. Cookie 同步调度器
  4. 批量采集调度器
  5. KB 刷新调度器
  6. 接管超时调度器
- 【强制】`@Async`/`asyncio.create_task` 必须有异常处理（`exceptionally`/`add_done_callback`）
- 🆕【强制】**S7503**：不必要的 `async` 函数（无 await）——同步函数移除 `async` 关键字
  - **实战案例**：`scheduler.start_all` 从 `async def` 改为同步 `def`，避免 SonarQube 误报
  - **判断**：纯编排方法（只调用其他同步方法）应保持同步
- 【推荐】并发请求用 `asyncio.gather`，限制并发数用 `asyncio.Semaphore`
- 【禁止】在 async 函数中用 `loop.run_until_complete`（会死锁）
- 🆕v4.0【强制】**事件触发时机**："已完成"语义事件（`EVAL_PASSED`/`NOTIFY_SENT`/`TASK_COMPLETED`）必须在业务逻辑**完成后**触发
  - **禁止**：在业务逻辑前置条件变更时就触发完成事件（如 DingTalk 通知在 AI 评估前触发 EVAL_PASSED）
  - "开始"语义事件（`TASK_STARTED`/`EVAL_STARTED`）在业务逻辑**开始前**触发
  - **判断信号**：事件名含 PASSED/SENT/COMPLETED → 后置；含 STARTED/BEGIN → 前置
- 🆕v4.3【强制】**B-REVIEW-SCHEDULER-ISOLATION：独立调度器隔离模式**
  - 生命周期/优先级不同的后台任务必须使用独立 APScheduler `BackgroundScheduler`，避免与项目主调度器耦合
  - **判断信号**：后台任务生命周期与应用主调度器不同 + 共享状态有冲突风险 + 任务优先级不同
  - **修复模式**：创建独立 `BackgroundScheduler()` → 独立 `add_job()` 注册 → 独立 `start()`/`shutdown()` 钩子 → 不共享 jobstore
  - **配置参数**：`scheduler_name`、`max_instances`、`coalesce`、`misfire_grace_time` 在 `config.yaml` 的 `isolated_schedulers` 节点管理
  - **适用**：Cookie 同步调度器、健康检查调度器、生命周期不同于主任务调度器的辅助任务
  - **不适用**：紧耦合任务调度、共享状态访问需求、资源限制环境（内存敏感场景应合并调度器）
  - **历史教训**：Cookie 同步任务若复用项目主任务调度器，会与采集任务的优先级产生冲突，且 shutdown 时序复杂；独立调度器后生命周期清晰
- 🆕v4.4【强制】**B-REVIEW-NO-HARDCODED-THRESHOLD：硬编码阈值禁用**
  - 调度器/任务循环中的阈值参数必须从配置读取，**禁止**用硬编码常量替代已有配置项
  - **判断信号**：代码中存在 `MAX_XXX = N` 硬编码常量，且 `config.yaml` 中已有对应的配置项 → 必须改为读取配置
  - **修复模式**：`try: from infra.yaml_config import get_config; threshold = get_config().<section>.<field> except: threshold = <default>`
  - **配置参数**：所有业务阈值的配置字段名在 `config.yaml` 的 `hardcoded_threshold_checks` 节点管理
  - **适用**：所有业务阈值（失败重试次数、超时时间、间隔时间、并发数）
  - **不适用**：语言/框架级常量（如 HTTP 200）、数学常量、协议固定值
  - **历史教训**：Scheduler 用硬编码 `MAX_CONSECUTIVE_ERRORS = 10` 控制连续失败暂停，但 `config.yaml` 的 `antidetect.fail_pause_threshold = 3`。用户设置了失败 3 次后暂停，实际要失败 10 次才暂停
- 🆕v4.6【强制】**B-REVIEW-ASYNC-TIMEOUT：异步操作整体超时保护**
  - 所有 `await` 调用外部资源（浏览器自动化、HTTP 客户端、IO 操作、远程 API）的异步操作，必须在**调用层**用 `asyncio.wait_for(coro, timeout=N)` 包装整体超时，超时后返回语义化状态码（如 504 网关超时），**禁止**依赖被调用方内部 `timeout` 参数作为唯一超时保护
  - **判断信号**：代码含 `await container.<module>.<method>(...)` / `await client.<method>(...)` / `await page.<method>(...)` 调用外部资源 → 必须检查是否被 `asyncio.wait_for` 包裹；被调用方内部 `timeout` 参数不视为整体超时保护
  - **修复模式**：
    ```python
    try:
        detail = await asyncio.wait_for(
            container.collector.detail(item_id), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.warning("[RefreshItem] 采集超时 item=%s（%ss），外部资源可能异常", item_id, timeout_seconds)
        raise HTTPException(status_code=504, detail="采集超时：外部资源异常或被反爬拦截，请稍后重试")
    except Exception as e:
        logger.warning("[RefreshItem] 采集失败 item=%s: %s", item_id, e)
        raise HTTPException(status_code=502, detail=f"采集失败：{e}")
    ```
  - **关键约束**：
    - 超时时间必须从配置读取（`config.async_timeout.<operation>_seconds`），**禁止**硬编码
    - 超时后必须返回明确状态码（504=超时、502=失败、503=稍后重试），便于前端按状态码分类处理
    - 超时日志必须记录操作类型 + 资源 ID + 超时秒数
    - `asyncio.CancelledError` 不应被 `wait_for` 的 `TimeoutError` 吞掉，应单独传播
  - **配置参数**：`timeout_seconds`（默认 60）、`max_retries`（默认 0=不重试）、`status_code_mapping`（超时→504、失败→502）在 `config.yaml` 的 `async_timeout` 节点管理
  - **适用**：所有 `await` 外部资源的异步操作（浏览器自动化、HTTP 请求、远程 API、IO 操作、子进程调用）
  - **不适用**：有内建 timeout 的 HTTP 客户端（`httpx.Timeout` 已配置）、纯计算函数、`asyncio.CancelledError` 传播路径、有 tenacity 等重试机制包裹的场景
  - **历史教训**：`refresh_item` 调用 `collector.detail(item_id)` 时，`page.query_selector` 无 `timeout` 参数，闲鱼反爬 RGV587 拦截后浏览器实例异常导致 `query_selector` 无限挂起，前端 90 秒后客户端超时无任何错误提示。修复后 `refresh_item` 加 `asyncio.wait_for(..., timeout=60.0)` + 504 响应，14.4 秒返回明确错误
- 🆕v4.9【强制】**B-REVIEW-RESOURCE-CLEANUP-HOOK：资源生命周期 cleanup 钩子完整性**
  - 所有可注册的组件（Worker/Adapter/Plugin/Handler）必须实现 `cleanup()` 钩子，由调度器/容器在 `unregister` 时统一调用，确保资源释放
  - **判断信号**：组件类有「注册/注销」生命周期（如 `scheduler.register` / `scheduler.unregister`）+ 持有后台任务/连接/锁/文件句柄 → 必须实现 cleanup()
  - **修复模式**：
    - 即使当前实现为空，也必须保留 `async def cleanup(self) -> None: return None` 方法（为未来扩展预留接入点）
    - 后台 `asyncio.Task` 必须保留引用防 GC（`self._task = asyncio.create_task(...)`），禁止裸 `create_task` 不持有引用
    - 取消后台任务必须 `task.cancel()` + `await asyncio.gather(task, return_exceptions=True)`，确保资源清理完成
    - `try/finally` 块中 `finally` 引用的变量必须在 `try` 之前初始化为 `None`
  - **配置参数**：`cleanup_method_name`（默认 `cleanup`）、`task_cancel_timeout`（默认 5s）、`required_cleanup_components`（必须实现 cleanup 的组件类型列表，如 `["TaskWorker", "Adapter", "Plugin"]`）在 `config.yaml` 的 `resource_lifecycle` 节点管理
  - **适用**：可注册组件（Worker/Adapter/Plugin/Handler）、持有后台任务的组件、持有连接/锁/文件句柄的组件
  - **不适用**：纯函数（无状态无副作用）；一次性脚本（进程结束即释放）；纯数据对象（无生命周期）
  - **历史教训**：`TaskWorker` 缺少 `cleanup()` 方法，`TaskScheduler.unregister` 时无法释放 worker 持有的资源；`_WorkerHandle` 缺少 `loop_task` 字段声明导致 `getattr` 兜底反模式。修复后 `TaskWorker` 实现 cleanup 钩子，`_WorkerHandle` 显式声明所有字段
- 🆕v4.9【强制】**B-REVIEW-CONCURRENT-STATE-LOCK：并发共享状态锁保护**
  - 多线程/协程访问同一共享状态（计数器/冷却时间/最后执行时间）时，「检查+更新」必须在同一锁内完成，避免竞态
  - **判断信号**：代码含 `if self._last_run + interval < now: self._last_run = now()` 模式（检查+更新分离）+ 多线程/协程访问 → 必须加锁
  - **修复模式**：
    ```python
    # ✅ 锁内原子检查+更新
    with self._lock:
        if h.consecutive_errors >= threshold:
            return False
        h.consecutive_errors += 1
        return True
    ```
  - **关键约束**：
    - 锁仅保护临界区（检查+更新），**禁止**用锁保护 IO（如 `await` 网络请求），避免阻塞其他协程
    - `asyncio.Lock` 内禁止 `await` 长时间操作，必要时先释放锁再做 IO
    - 跨线程用 `threading.RLock`（可重入），跨协程用 `asyncio.Lock`，**禁止**混用
    - Dataclass 字段必须显式声明默认值（`consecutive_errors: int = 0`），**禁止**用 `getattr(h, 'consecutive_errors', 0)` 兜底（反模式，掩盖字段未初始化的 bug）；仅在处理「外部输入的动态属性」（如 JSON 解析结果）时才允许 getattr
  - **配置参数**：`lock_type`（默认 `RLock`）、`critical_section_max_await`（默认 `0`，禁止 await）、`required_lock_fields`（必须加锁保护的字段名列表，如 `["last_run", "consecutive_errors", "cooldown_until"]`）在 `config.yaml` 的 `concurrency_safety` 节点管理
  - **适用**：多线程/协程访问同一共享状态；定时任务与 API 请求并发修改同一数据
  - **不适用**：单线程顺序执行；thread-local 数据；不可变对象
  - **历史教训**：`_WorkerHandle` 缺少 `consecutive_errors` 字段声明，代码用 `getattr(h, 'consecutive_errors', 0) + 1` 兜底，掩盖了字段未初始化的 bug；并发场景下「检查+更新」未在锁内可能导致竞态。修复后显式声明字段 + 锁内原子检查
- 🆕v4.9【强制】**B-REVIEW-PYTHON-MODERN-ASYNCIO：Python 现代化 asyncio 用法**
  - Python 3.10+ 项目必须使用现代 asyncio API 与 dataclass 语法，**禁止**使用过时 API
  - **判断信号**：代码含 `asyncio.get_event_loop()` / `getattr(obj, 'field', default)` 兜底 dataclass 字段 / 函数内 `import asyncio` → 视为违规
  - **修复模式**：
    ```python
    # ✅ 现代 asyncio API
    _scheduler_task = asyncio.create_task(_scheduler_loop())  # ✅
    # ❌ loop = asyncio.get_event_loop(); loop.create_task(...)  # 过时

    # ✅ dataclass 字段显式声明
    @dataclass
    class _WorkerHandle:
        consecutive_errors: int = 0  # ✅
    # ❌ h.consecutive_errors = getattr(h, 'consecutive_errors', 0) + 1  # 兜底反模式
    ```
  - **关键约束**：
    - `asyncio.create_task(coro)` 替代 `asyncio.get_event_loop().create_task(coro)`；在协程内获取事件循环用 `asyncio.get_running_loop()`（明确表示运行中循环），**禁止** `asyncio.get_event_loop()`（Python 3.10+ 已弃用，且在无运行循环时会创建新循环导致行为不可预期）
    - dataclass 字段必须显式声明默认值，**禁止**用 `getattr(obj, 'field', default)` 兜底未声明字段；仅在处理「外部输入的动态属性」（如 JSON 解析结果）时才允许 getattr
    - 所有 import 必须在模块顶部，**禁止**函数内重复 import（除非解决循环依赖的延迟导入）
    - `asyncio.CancelledError` 必须用 `contextlib.suppress(asyncio.CancelledError)` 包裹 await 并向上传播，**禁止** `except: pass` 静默吞掉
    - 类型注解现代语法：`X | None` 替代 `Optional[X]`，`list[T]` 替代 `List[T]`，`dict[K, V]` 替代 `Dict[K, V]`
  - **配置参数**：`min_version`（默认 `"3.10"`）、`deprecated_apis`（禁用 API 列表：`get_event_loop`/`utcnow`/`Optional`/`List`/`Dict`）、`required_imports_at_module_level`（强制模块级导入的模块列表，如 `["asyncio", "re", "threading", "logging"]`）在 `config.yaml` 的 `python_modern` 节点管理
  - **适用**：Python 3.10+ 项目；使用 asyncio 的代码；使用 dataclass 的领域模型
  - **不适用**：Python 3.9 及以下（部分语法不支持）；同步代码（无 asyncio）；非 dataclass 类
  - **历史教训**：`startup.py` 用 `asyncio.get_event_loop().create_task()` 创建后台任务（过时 API），且函数内重复 `import asyncio`；`_WorkerHandle` 用 `getattr` 兜底 `consecutive_errors` 字段。修复后改为 `asyncio.create_task()` + 模块级 import + 显式字段声明
- 🆕v4.11【强制】**B-REVIEW-SCHEDULER-DB-SYNC：调度器状态与 DB 同步**
  - 调度器内存状态变更（pause/resume/stop/error_pause）必须同步到 DB（`update_task_status`），**禁止**只在内存变更导致 API 返回的状态与实际运行状态不一致
  - **核心机制**（审查时必须理解）：
    - 调度器内存中维护 `pause_event` / `consecutive_errors` / `_active` 等状态
    - API 端点从 DB 读取 `task.status` 字段返回给前端
    - 若内存状态变更不同步 DB，前端显示"运行中"但任务实际已暂停
    - 自动暂停（连续失败触发）必须同步 DB，否则用户无法感知任务已停止
  - **判断信号**：
    - 调度器代码含 `pause_event.clear()` / `pause_event.set()` / `self._active = False` → 必须同步调用 `self._repo.update_task_status(task_id, "paused"/"running"/"stopped")`
    - 代码含 `if h.consecutive_errors >= threshold: h.pause_event.clear()` → 必须同步 `update_task_status(task_id, "paused")`
    - API 返回 `task.status == "running"` 但调度器内 `pause_event` 已 clear → 状态不一致
  - **修复模式**：
    ```python
    # ✅ 状态变更后同步 DB
    async def _auto_pause_on_errors(self, task_id: str, h: _WorkerHandle) -> None:
        h.pause_event.clear()
        h.consecutive_errors = 0
        # 同步 DB 状态，确保 API 返回与实际一致
        try:
            await self._repo.update_task_status(task_id, "paused")
        except Exception as e:
            logger.warning("[Task {}] DB 状态同步失败：{}", task_id, e)

    # ❌ 错误：只在内存变更，DB 仍为 "running"
    # async def _auto_pause_on_errors(self, task_id, h):
    #     h.pause_event.clear()
    #     h.consecutive_errors = 0
    #     # 缺少 update_task_status 调用
    ```
  - **配置参数**：`scheduler_db_sync.required_transitions`（必须同步 DB 的状态转换列表，如 `["running→paused", "paused→running", "running→stopped", "running→error_paused"]`）、`scheduler_db_sync.sync_failure_strategy`（默认 `warn`，可选 `raise`）、`scheduler_db_sync.status_field`（默认 `status`）在 `config.yaml` 的 `scheduler_db_sync` 节点管理
  - **适用**：所有调度器状态变更（auto_pause / manual_pause / resume / stop / unregister）；任务状态机转换
  - **不适用**：纯计算状态（如 consecutive_errors 计数器）；临时状态（如 pause_event 内部信号）；fire-and-forget 任务
  - **历史教训**：调度器连续失败触发 `pause_event.clear()` 自动暂停，但未调用 `update_task_status("paused")`，API 仍返回 `running`，前端显示"运行中"但任务实际已停止，用户无法察觉
- 🆕v4.11【强制】**B-REVIEW-BACKGROUND-TASK-MONITOR：后台任务健康监控**
  - 后台任务（EventBus 消费者 / 调度器循环 / 健康检查器）必须用轮询监控（`while not stop_event.is_set(): if task.done(): break; await asyncio.wait_for(stop_event.wait(), timeout=N)`），**禁止** `await asyncio.Event().wait()` 静默等待导致任务异常退出时主循环无感知
  - **核心机制**（审查时必须理解）：
    - `asyncio.Event().wait()` 会阻塞直到 event 被 set，期间无法感知其他 task 的退出
    - 后台 task（如 EventBus）异常退出时，主循环仍阻塞在 `stop_event.wait()`，事件推送静默失效
    - 轮询模式每 N 秒检查一次 `task.done()`，能在 10 秒内感知子任务退出
    - `asyncio.wait_for(stop_event.wait(), timeout=N)` 配合 `try/except asyncio.TimeoutError` 是标准轮询模式
  - **判断信号**：
    - 代码含 `bus_task = asyncio.create_task(...)` 后 `await stop_event.wait()` → 视为违规
    - 代码含 `event_bus_task = asyncio.create_task(event_bus.run())` + `await shutdown_event.wait()` → 必须改为轮询
    - 后台 task 异常退出但主循环未感知 → 典型症状
  - **修复模式**：
    ```python
    # ✅ 轮询监控后台任务
    stop_event = asyncio.Event()
    while not stop_event.is_set():
        if bus_task.done():
            exc = bus_task.exception()
            if exc:
                logger.error("EventBus 异常退出：{}", exc)
            else:
                logger.warning("EventBus 已退出")
            break
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            continue  # 超时继续下一轮检查

    # ❌ 错误：Event.wait 静默等待，bus_task 异常退出无感知
    # bus_task = asyncio.create_task(event_bus.run())
    # await stop_event.wait()  # bus_task 死了也不知道
    ```
  - **配置参数**：`background_task_monitor.poll_interval_seconds`（默认 `10`，轮询间隔）、`background_task_monitor.monitored_tasks`（必须监控的后台任务名列表，如 `["event_bus", "scheduler_loop", "health_check", "cookie_sync", "kb_refresh"]`）、`background_task_monitor.on_task_exit`（默认 `log_and_break`，可选 `restart`）、`background_task_monitor.restart_max_attempts`（默认 `3`，restart 策略下的最大重启次数）在 `config.yaml` 的 `background_task_monitor` 节点管理
  - **适用**：所有后台 asyncio.Task（EventBus / Scheduler / Health Checker / Cookie Sync / KB Refresh）；需要在主循环中感知子任务退出的场景
  - **不适用**：fire-and-forget 任务（不需感知退出）；一次性任务（如启动初始化）；有 done_callback 处理的任务
  - **历史教训**：`startup._scheduler_loop` 用 `await stop_event.wait()` 等待关闭信号，EventBus 任务异常退出时主循环无感知，事件推送静默失效 30 分钟才被用户发现
- 🆕v4.14【强制】**B-REVIEW-ROUTE-BLOCK-TYPES：浏览器自动化资源拦截粒度**
  - 浏览器自动化资源拦截必须考虑业务关键资源（二维码图片、关键数据接口），**禁止**盲目拦截 image/font/media。拦截前必须检查页面是否依赖图片渲染关键内容（如二维码图片是登录流程关键资源），若依赖则必须排除或延迟拦截
  - **判断信号**：代码含 `route.abort("image")` 或 `route.abort("font")` 或 `route.abort("media")` → 必须检查页面是否依赖该类型资源渲染关键业务内容；登录流程/二维码页面/图片采集页面 → 禁止拦截 image
  - **修复模式**：
    ```python
    # ✅ 按场景精细化拦截
    async def setup_route_blocking(page, scenario: str):
        block_types = config.browser.route_block_scenarios.get(scenario, ["font", "media"])
        if "login" in scenario or "qrcode" in scenario:
            block_types = []  # 登录流程不拦截任何资源，确保二维码图片正常渲染
        async def route_handler(route):
            if route.request.resource_type in block_types:
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", route_handler)
    ```
  - **配置参数**：`browser.route_block_types`（默认 `["font", "media"]`，不拦截 image）、`browser.route_block_whitelist`（关键资源 URL 白名单，如二维码图片 URL）、`browser.route_block_scenarios`（场景到拦截类型的映射，如 `login → []` 不拦截，`search → ["image", "font", "media"]` 可拦截）在 `config.yaml` 的 `browser.route_block` 节点管理
  - **适用**：浏览器自动化场景的资源拦截优化（减少带宽、加快加载）
  - **不适用**：纯数据抓取页面（无关键图片渲染）、纯 API 请求场景（无需浏览器）
  - **历史教训**：登录流程 `route.abort("image")` 拦截所有图片，导致二维码图片无法渲染，用户看不到二维码无法扫码登录。修复后改为精细化拦截，排除二维码图片 URL
- 🆕v4.19【强制】**B-REVIEW-SCHEDULER-STARTUP-VISIBILITY：关键调度器启动状态可见性**
  - 关键后台调度器（影响业务正确性的，如批量采集/状态回查/数据同步/定时清理）的启动状态必须在启动日志中明确告知用户，未启动时输出 WARNING 级别日志 + 醒目提示（含启动命令样例 + 影响范围），`--help` 输出必须说明启动参数影响范围，`/api/about` 端点必须返回调度器状态，调度器启动参数列表在 config.yaml 集中管理
  - **核心机制**（审查时必须理解）：
    - 关键调度器（如 `BatchRefreshScheduler`）影响业务正确性（已售商品状态回查），未启动时业务表面正常但数据长期不刷新
    - INFO 级别日志用户在终端滚动中容易错过，未启动时必须用 WARNING 级别 + 多行格式（启动命令 + 影响范围）
    - `--help` 输出仅说明参数语法不够，必须说明"启用什么调度器、间隔多少、影响哪些下游功能"
    - `/api/about` 端点返回 `schedulers: [{name, enabled, interval_minutes, last_run_at}]` 供前端"关于"页面展示
  - **判断信号**：
    - 代码含 `asyncio.create_task(...)` 或 `scheduler.start()` 启动调度器但无启动日志 → 视为违规
    - 启动日志仅用 `logger.info("xxx 已启动")` 但未告知用户如何禁用/启用 → 视为可疑
    - 调度器未启动时仅静默跳过（无 WARNING）→ 视为违规
    - `/api/about` 端点未返回调度器状态 → 视为可疑
    - `--help` 输出中启动参数无影响范围说明 → 视为可疑
  - **修复模式**：
    ```python
    # ✅ 未启动时 WARNING + 醒目提示 + 启动命令 + 影响范围
    if not os.environ.get("XH_WITH_SCHEDULER"):
        logger.warning(
            "⚠️ 批量采集调度器未启动，已售商品状态将不刷新。\n"
            "  如需启用：python -m xianyu_hunter web --with-scheduler\n"
            "  影响范围：商品 is_sold 状态回查、已售商品检测"
        )
        return
    # 启动时 INFO + 间隔
    logger.info("✅ 批量采集调度器已启动（间隔 30 分钟，每批 100 条）")

    # ✅ /api/about 返回调度器状态
    @api_router.get("/about")
    async def about():
        return {
            "version": _safe_app_version(),
            "schedulers": [{
                "name": "BatchRefreshScheduler",
                "enabled": scheduler.is_running,
                "interval_minutes": 30,
                "last_run_at": scheduler.last_run_at,
            }],
        }

    # ❌ 错误：未启动时仅 info 静默跳过
    # if not os.environ.get("XH_WITH_SCHEDULER"):
    #     logger.info("批量采集调度器未启动")  # 用户看不到
    #     return
    ```
  - **配置参数**：`scheduler_startup_visibility.critical_schedulers`（关键调度器名单，如 `["BatchRefreshScheduler", "AutoLoginScheduler", "CookieCheckerScheduler"]`）、`scheduler_startup_visibility.require_startup_log`（默认 `true`）、`scheduler_startup_visibility.require_warning_when_disabled`（默认 `true`）、`scheduler_startup_visibility.require_help_doc`（默认 `true`）、`scheduler_startup_visibility.require_about_endpoint`（默认 `true`）、`scheduler_startup_visibility.startup_param_env_mapping`（启动参数与环境变量映射，如 `{"--with-scheduler": "XH_WITH_SCHEDULER"}`）在 `config.yaml` 的 `scheduler_startup_visibility` 节点管理
  - **适用**：关键后台调度器（批量采集/状态回查/数据同步/定时清理）；通过启动参数或环境变量控制的功能开关；影响业务正确性的后台任务
  - **不适用**：调试用的可选功能（如 `--debug` 模式）；默认启动且无法关闭的核心功能；一次性任务（如启动时迁移）
  - **历史教训**：用户启动 web 服务时未加 `--with-scheduler` 参数，`BatchRefreshScheduler`（每 30 分钟回查 `is_sold=0` 商品状态）永远不运行。日志仅输出一条 info"批量采集调度器未启动（需 XH_WITH_SCHEDULER=1）"，用户无感知。导致商品 1058031608014 实际已售但数据库 `is_sold=0` 长期不刷新，用户看到已售商品仍被推荐。修复后调度器未启动时输出 WARNING + 醒目提示 + 启动命令 + 影响范围
- 🆕v4.25【强制】**B-REVIEW-112: SHARED-SINGLETON-POLLUTION：共享单例污染检查**
  - 循环中创建任务级覆盖对象必须使用局部变量 `worker_xxx`，**禁止**直接修改 `container` 单例导致后续任务继承前一任务的覆盖状态
  - **核心机制**（审查时必须理解）：
    - `container` 单例（如 `Container`）在进程生命周期内共享，多个任务/请求复用同一实例
    - 循环中 `container.chatbot = build_chatbot(task_config)` 会污染单例，下一个任务读到的是上一个任务的 chatbot
    - 必须用 `worker_chatbot = build_chatbot(task_config)` 局部变量，任务结束后随栈帧释放
    - 单例只存放"进程级共享配置"（如数据库连接池、全局默认配置），**禁止**存放"任务级覆盖配置"
  - **判断信号**：
    - 循环中出现 `container.xxx = ...` / `self.container.xxx = ...` 赋值 → 视为违规
    - `for task in tasks:` 内部修改单例属性 → 视为违规
    - 任务执行后单例属性未还原导致下一任务读到脏数据 → 视为违规
    - 多任务并发时单例属性被竞态覆盖 → 视为违规
  - **修复模式**：
    ```python
    # ✅ 使用局部变量 worker_xxx，不污染单例
    async def run_batch(tasks: list[Task]):
        for task in tasks:
            # 任务级覆盖配置用局部变量
            worker_chatbot = build_chatbot(task.chatbot_config)
            worker_price_strategy = build_price_strategy(task.price_config)
            await _process_one(task, worker_chatbot, worker_price_strategy)
            # 局部变量随函数栈帧释放，不污染 container

    # ❌ 违规：直接修改 container 单例
    async def run_batch(tasks: list[Task]):
        for task in tasks:
            container.chatbot = build_chatbot(task.chatbot_config)  # 污染单例！
            await _process_one(task)
            # 下一任务读到的是本任务的 chatbot

    # ✅ 若必须通过单例传递（如深层调用链），用 try/finally 还原
    async def run_batch(tasks: list[Task]):
        original = container.chatbot
        try:
            for task in tasks:
                worker = build_chatbot(task.chatbot_config)
                container.chatbot = worker  # 临时设置
                await _process_one(task)
        finally:
            container.chatbot = original  # 还原，避免污染后续批次
    ```
  - **关键约束**：
    - 循环内创建的任务级对象必须用 `worker_xxx` 局部变量
    - **禁止**在循环内 `container.xxx = ...` 修改单例
    - 若深层调用链必须通过单例传递，用 `try/finally` 还原原始值
    - 单例只存"进程级共享配置"，任务级配置用局部变量或函数参数传递
    - 并发场景（`asyncio.gather`）下单例污染会触发竞态，必须用局部变量
    - 修改后必须 `grep` 验证循环内无 `container.xxx =` 赋值
  - **配置参数**：`shared_singleton_protection.singleton_attr_pattern`（单例属性命名模式，如 `container`）、`shared_singleton_protection.worker_var_prefix`（局部变量前缀，默认 `worker_`）、`shared_singleton_protection.require_try_finally_restore`（默认 `true`，若必须修改单例则要求 try/finally 还原）、`shared_singleton_protection.forbid_assign_in_loop`（默认 `true`，禁止循环内赋值单例属性）在 `config.yaml` 的 `shared_singleton_protection` 节点管理
  - **适用**：循环处理多个任务的批量场景（如 `run_batch`/`asyncio.gather`）；任务级配置覆盖功能；通过 container 单例传递依赖的架构
  - **不适用**：单任务处理（无循环无污染风险）；进程级初始化（如 `lifespan` 启动时设置单例）；只读单例（不修改属性）
  - **历史教训**：任务级配置覆盖功能中，`run_batch` 循环内 `container.chatbot = build_chatbot(task.chatbot_config)` 为每个任务构建专属 chatbot，但下一个任务读到的是上一个任务的 chatbot 配置（污染），导致任务 A 的高价策略被任务 B 继承，任务 B 误以高价抢单。修复后改为 `worker_chatbot` 局部变量 + 函数参数传递

### 10. 事件总线 🆕v2.0

- 【强制】EventBus 基于 `asyncio.Queue`
- 【强制】EventType 枚举完整（约 35 种）
- 【强制】EVENT_SEVERITY 三级：INFO / WARN / ERROR
- 【强制】事件消费者必须处理 `asyncio.CancelledError` 与 `QueueEmpty`
- 【推荐】SSE 端点用 `EventSourceResponse` 或手动 `StreamingResponse` + `text/event-stream`
- 【强制】SSE lastEventId 持久化重连：客户端断线重连时从 localStorage 读取作为 `?last_event_id=` 参数
- 🆕v4.5【强制】**B-REVIEW-MULTI-WRITE-ENTRY：多源状态同步统一入口**
  - 同一份状态（如 Cookie 层状态、用户登录态、连接池状态）有 ≥ 2 个写入入口时，必须建立**统一同步入口函数**（如 `sync_cookie_layers_from_json()`），在所有写入路径写完后主动调用
  - **判断信号**：核心状态依赖外部存储（JSON / SQLite / 浏览器内存 / 远程 API），但内存层状态只在某个入口被同步 → 出现"实际有数据但显示失效"的脱节现象
  - **修复模式**：识别所有写入路径（登录 / 注入 / 导入 / 工具刷新）→ 抽取 `sync_xxx_from_<主数据源>()` 公共函数 → 在每个写入路径的成功分支主动调用 → 同步逻辑必须重新读主数据源（而非用调用方传入的列表），避免过滤逻辑不一致
  - **关键约束**：禁止依赖某个回调（如 `on_login_success`）自动触发而无任何调用方——必须显式调用
  - **配置参数**：`sync_entry_functions`（同步入口函数名列表）、`write_entry_paths`（需要调用的写入路径列表）在 `config.yaml` 的 `state_sync` 节点管理
  - **适用**：状态分布在多个存储介质（JSON / SQLite / 浏览器 / 内存）且需保持显示一致；多入口写入同一份状态
  - **不适用**：单一写入入口、状态天然同步（无中间层缓存）、纯计算型状态
  - **历史教训**：`CookieRotator` 的 `on_login_success` 钩子函数被定义后从未被任何调用方触发，导致 5 个登录路径（`browser_login` / `auth_helper` / `cookie_inject` / `browser_import` / `qr_login`）都绕过层状态更新，登录后 `/cookies/layers` 端点始终显示三层失效但功能完全正常
- 🆕v4.5【强制】**B-REVIEW-INACTIVE-STATE-PRESERVE：状态条件区分"从未初始化"与"主动失效"**
  - 当状态字段有"从未初始化 / 已初始化 / 主动失效"三种语义时，**禁止**用 `not state.valid` 笼统判断"该同步了"——必须用 `state.updated_at == 0.0` 区分"从未初始化"和"主动失效后"
  - **判断信号**：状态对象有 `valid` + `updated_at` 两个字段 + 存在"主动失效"语义（如 `invalidate_layer()` 显式置 `valid=False` 但保留 `updated_at`）→ 用 `not valid` 会覆盖手动失效状态
  - **修复模式**：
    - **从未初始化**（`updated_at == 0.0`）：可主动补救同步（读主数据源、读浏览器内存兜底）
    - **主动失效**（`updated_at > 0.0 and not valid`）：保留状态不覆盖（用户/系统已显式标记失效）
    - **已初始化有效**（`updated_at > 0.0 and valid`）：正常返回
  - **配置参数**：`inactive_check_field`（用于判断的字段名，如 `updated_at`）在 `config.yaml` 的 `state_semantics` 节点管理
  - **适用**：所有"状态机 + 主动失效"语义的场景（Cookie 层状态、用户会话状态、健康检查状态）
  - **不适用**：纯二元状态（有效/无效）、无"主动失效"语义的简单标志位
  - **历史教训**：`cookie_checker` 健康检查器用 `not identity_state.valid` 作为"需要同步"的判断条件，导致 collector 检测到 RGV587 主动失效 identity 层后，cookie_checker 在下次 tick 立即从 JSON 重新同步覆盖失效状态，造成"自动失效永远不生效"的死循环
- 🆕v4.5【强制】**B-REVIEW-BROWSER-FALLBACK-SYNC：浏览器内存兜底同步模式**
  - 当主数据源（JSON）可能与运行时状态（浏览器内存、内存缓存）脱节时，状态查询端点必须实现**两步同步**：第一步从主数据源同步；第一步后仍有状态未恢复时，从运行时载体读取作为兜底
  - **判断信号**：主数据源 + 运行时载体共存 + 某些字段（如 MTOP token）只在运行时载体更新（被外部进程 `Set-Cookie`） + 状态查询可能因为 JSON 过期而误报失效
  - **修复模式**：
    1. **第一步（主数据源同步）**：从 JSON 读取、过滤过期、构造 cookie_map、调用 `sync_state_from_cookies()`
    2. **第二步（兜底同步）**：检查仍有 `updated_at==0.0` 的层 → 从 `browser.context.cookies()` 读取对应域 → 重新构造 cookie_map → 同步 → 回写主数据源（避免下次再走兜底）
  - **回写策略**：用 `upsert`（更新 + 添加）而非 `update`（只更新已存在），因 JSON 中可能完全不存在该 cookie 条目
  - **配置参数**：兜底同步开关、读取的 cookie 域列表、回写白名单在 `config.yaml` 的 `cookie_fallback` 节点管理
  - **适用**：浏览器 Cookie 多源持久化、CDP/Playwright 抓取场景、外部进程状态回写
  - **不适用**：无运行时载体的纯文件存储、有强一致要求的场景（应直接报错而非兜底）
  - **历史教训**：`_m_h5_tk` 等 session token 在 MTOP 响应中被 `Set-Cookie` 写入浏览器内存，但 `_sync_response_cookies_to_context` 只调 `add_cookies` 不回写 JSON。重启后浏览器从 JSON 加载旧 token 失败，但功能靠浏览器内存正常工作。`/cookies/layers` 端点增加浏览器内存兜底同步 + 回写 JSON 后彻底解决
- 🆕v4.14【强制】**B-REVIEW-SIGNAL-LAYER-MAPPING：层依赖关系信号匹配**
  - 层恢复信号必须与层范围匹配，SESSION 层信号不能恢复 IDENTITY 层，IDENTITY 无效时 SESSION 也不能恢复。层定义的 `depends_on` 字段指示依赖关系，信号只能恢复其所属层及以下层，**禁止**跨层恢复导致状态不一致
  - **判断信号**：代码含 `sync_cookie_layers_from_json()` 或 `_sync_layers_from_signal()` → 必须检查信号与层的匹配关系；层定义含 `depends_on` 字段 → 信号恢复必须遵循依赖链
  - **修复模式**：
    ```python
    # ✅ 按依赖链恢复层状态
    LAYER_DEPENDS_ON: dict[str, str | None] = {
        "session": "identity",  # session 依赖 identity
        "identity": "base",     # identity 依赖 base
        "base": None,           # base 无依赖
    }

    async def sync_layer_from_signal(signal_type: str, layer_name: str) -> bool:
        # 信号只能恢复其所属层及以下层（依赖链）
        signal_layer_mapping = config.cookie_layers.signal_layer_mapping
        allowed_layer = signal_layer_mapping.get(signal_type)
        if allowed_layer != layer_name:
            logger.warning(f"信号 {signal_type} 不能恢复层 {layer_name}，只能恢复 {allowed_layer} 及其依赖链")
            return False

        # 检查依赖链上层是否有效
        depends_on = LAYER_DEPENDS_ON.get(layer_name)
        if depends_on and not get_layer_state(depends_on).valid:
            logger.warning(f"层 {layer_name} 的依赖层 {depends_on} 无效，无法恢复")
            return False

        # 恢复层状态
        return await _restore_layer_state(layer_name)
    ```
  - **配置参数**：`cookie_layers.signal_layer_mapping`（信号到层的映射表，如 `login_success → identity`，`session_refresh → session`）、`cookie_layers.depends_on_chain`（层依赖链，如 `session → identity → base`）在 `config.yaml` 的 `cookie_layers` 节点管理
  - **适用**：层级依赖的状态恢复、Cookie 层管理、多源状态同步
  - **不适用**：无层级依赖的状态、独立状态恢复、单层状态管理
  - **历史教训**：SESSION 层恢复信号 `sync_from_browser()` 被误用于恢复 IDENTITY 层，导致 IDENTITY 层状态与实际不一致（浏览器已失效但层状态显示有效）
- 🆕v4.21【强制】**B-REVIEW-PYDANTIC-FIELD-DECLARE：Pydantic 模型字段完整性规范**
  - 所有需持久化或回显的字段必须在 Pydantic 模型中显式声明，**禁止**依赖 `extra='allow'`/`extra='ignore'` 处理 yaml 字段（Pydantic v2 默认 `extra='ignore'`，未声明字段在 `model_dump()` 时会被丢弃，导致 API 响应缺失字段）
  - **核心机制**（审查时必须理解）：
    - Pydantic v2 `BaseModel` 默认 `extra='ignore'`，未显式声明的字段在 `model_dump()` 时会被丢弃
    - API 响应若直接返回 `model_dump()`，前端永远拿不到未声明字段，导致凭据/配置回显失败
    - 任何需要持久化或回显的字段，**必须**在 Pydantic 模型中显式声明（哪怕默认空字符串）
  - **判断信号**：
    - yaml 中有某字段但 Pydantic 模型无对应字段定义 → 视为违规
    - API 返回的字典中缺失 yaml 中已有的字段 → 必须检查 Pydantic 模型是否声明
    - 前端"填写后刷新页面变空"问题 → 必查根因是否为 Pydantic 字段未声明
    - 代码用 `model_extra` 或 `__pydantic_extra__` 访问未声明字段 → 视为可疑（应改为显式声明）
    - `grep "extra=.allow." src/xianyu_hunter/` 发现配置模型用 `extra='allow'` → 视为可疑
  - **修复模式**：
    ```python
    # ❌ 错误：依赖 extra='allow' 处理 yaml 字段
    class AppConfig(BaseModel):
        model_config = ConfigDict(extra='allow')
        notifier: NotifierConfig = NotifierConfig()
        # 凭据字段未声明，model_dump() 时被丢弃

    # ✅ 正确：所有需持久化的字段显式声明（哪怕默认空字符串）
    class AppConfig(BaseModel):
        notifier: NotifierConfig = NotifierConfig()
        # 通知渠道凭据（明文存到 yaml，前端用 Input.Password 组件隐藏）
        serverchan_send_key: str = ""
        pushplus_token: str = ""
        bark_server: str = ""
        bark_key: str = ""
        telegram_bot_token: str = ""
        telegram_chat_id: str = ""
        wecom_webhook: str = ""
        dingtalk_webhook: str = ""
        dingtalk_secret: str = ""
        webhook_url: str = ""
    ```
  - **配置参数**：`pydantic_field_integrity.require_explicit_declare`（默认 `true`，所有 yaml 字段必须显式声明）、`pydantic_field_integrity.scan_yaml_keys`（默认 `true`，自动扫描 yaml 字段名与 Pydantic 模型字段对齐）、`pydantic_field_integrity.exceptions`（豁免列表，如运行时计算的临时字段）在 `config.yaml` 的 `pydantic_field_integrity` 节点管理
  - **适用**：所有继承 `BaseModel` 的配置模型（AppConfig / NotifierConfig 等）；需持久化到 yaml/json 的字段；通过 API 回显的字段
  - **不适用**：运行时计算字段（用 `@computed_field`）；显式标注 `exclude=True` 的字段；临时内存对象（无需序列化）
  - **历史教训**：通知渠道凭据字段（`serverchan_send_key` 等 10 个）未在 `AppConfig` 中显式声明，前端写入 yaml 后 `GET /api/config` 调用 `model_dump()` 丢弃这些字段，导致前端"填写后刷新页面变空"
- 🆕v4.21【强制】**B-REVIEW-CREDENTIAL-SYNC-BRIDGE：凭据同步桥接规范（yaml→keyring）**
  - 双存储介质（yaml 写入 + keyring 读取）的凭据必须有显式同步桥接函数，DI 容器初始化 Notifier/Client 之前必须先调用同步函数；keyring KEY 常量名必须与 yaml 字段名 1:1 对齐；同步失败必须 `logging.warning()` 告警
  - **核心机制**（审查时必须理解）：
    - 前端写入 yaml（用户可编辑的明文存储），Notifier 从 keyring 读取（运行时凭证存储）
    - 两个存储介质之间**必须**有显式同步桥接函数，否则 Notifier `is_configured` 永远为 False
    - keyring KEY 常量名**必须**与 yaml 字段名 1:1 对齐，否则同步逻辑会写错位置
    - 同步时机：DI 容器初始化 Notifier 之前必须先调用 `_sync_yaml_credentials_to_keyring()`
  - **判断信号**：
    - 代码有 yaml 字段（`config.dingtalk_webhook`）但无同步到 keyring 的调用 → 视为违规
    - keyring KEY 常量名与 yaml 字段名不一致（如 `KEY_DINGTALK_WEBHOOK = "dingtalk_webhook_url"` 而 yaml 字段为 `dingtalk_webhook`）→ 视为违规
    - Notifier `__init__` 从 keyring 读取但 `is_configured=False` 且无同步逻辑 → 必查同步桥接
    - 测试中 `wire_notifier()` 后单测失败（keyring 被污染）→ 必须在测试 setup/teardown 清理 keyring
    - `grep "secrets.get_secret" src/xianyu_hunter/` 找到读取点但无对应的 `secrets.set_secret()` 同步点 → 视为违规
  - **修复模式**：
    ```python
    # ✅ 1. keyring KEY 常量名与 yaml 字段名 1:1 对齐
    KEY_DINGTALK_WEBHOOK = "dingtalk_webhook"  # ❌ 旧值 "dingtalk_webhook_url"
    KEY_WECOM_WEBHOOK = "wecom_webhook"        # ❌ 旧值 "wecom_webhook_url"

    # ✅ 2. DI 容器初始化 Notifier 之前先同步 yaml → keyring
    def wire_notifier(self) -> None:
        self._sync_yaml_credentials_to_keyring()  # 必须先同步
        self.notifier_hub = NotifierHub(channels=enabled, ...)
        self.notifier_hub.attach(self.event_bus)

    def _sync_yaml_credentials_to_keyring(self) -> None:
        """把 yaml 中的明文凭证同步到 keyring"""
        from xianyu_hunter.infra import secrets
        cred_map = {
            "serverchan_send_key": secrets.KEY_SERVERCHAN,
            "pushplus_token": secrets.KEY_PUSHPLUS,
            "bark_server": secrets.KEY_BARK_SERVER,
            "bark_key": secrets.KEY_BARK_KEY,
            "telegram_bot_token": secrets.KEY_TELEGRAM_TOKEN,
            "telegram_chat_id": secrets.KEY_TELEGRAM_CHAT,
            "wecom_webhook": secrets.KEY_WECOM_WEBHOOK,
            "dingtalk_webhook": secrets.KEY_DINGTALK_WEBHOOK,
            "dingtalk_secret": secrets.KEY_DINGTALK_SECRET,
            "webhook_url": secrets.KEY_WEBHOOK_URL,
        }
        for yaml_attr, keyring_key in cred_map.items():
            yaml_value = getattr(self.config, yaml_attr, "")
            if yaml_value:
                try:
                    secrets.set_secret(keyring_key, yaml_value)
                except Exception as e:
                    logging.warning("同步凭据 %s 到 keyring 失败: %s", yaml_attr, e)

    # ❌ 错误：Notifier 直接从 keyring 读取但 yaml 从未同步
    # class DingTalkNotifier:
    #     def __init__(self):
    #         self.webhook_url = secrets.get_secret(KEY_DINGTALK_WEBHOOK)  # 永远为 None
    ```
  - **配置参数**：`credential_sync_bridge.yaml_to_keyring_map`（yaml 字段名到 keyring KEY 常量的映射表）、`credential_sync_bridge.sync_timing`（默认 `before_notifier_init`，可选 `on_config_update`）、`credential_sync_bridge.require_key_name_align`（默认 `true`，强制 keyring KEY 常量名与 yaml 字段名对齐）在 `config.yaml` 的 `credential_sync_bridge` 节点管理
  - **适用**：双存储介质的凭据/配置同步（yaml ↔ keyring、yaml ↔ env、json ↔ 数据库）；Notifier/Client 从 keyring 读取的场景；多写入入口的状态同步
  - **不适用**：单一存储介质（如纯 yaml 或纯 keyring）；运行时计算字段（无需同步）；外部系统主动推送的状态（无本地写入）
  - **历史教训**：用户在通知渠道菜单填写钉钉 webhook 后，自动抢单成功却未收到钉钉通知。根因：前端写 yaml，`DingTalkNotifier` 从 keyring 读取，但中间无同步桥接，`is_configured=False`，渠道被 `NotifierHub` 静默跳过。同时 `KEY_DINGTALK_WEBHOOK="dingtalk_webhook_url"` 与 yaml 字段 `dingtalk_webhook` 不一致，即使有同步也会写错位置
- 🆕v4.21【强制】**B-REVIEW-REDACT-SCENARIO：脱敏策略场景区分规范**
  - 同一字段在不同 API 场景下脱敏策略必须区分：`GET /api/config`（前端回显，**不脱敏**凭据）vs `/share`/`/export`（分享导出，**必须脱敏**凭据）vs 日志输出（**必须脱敏**凭据）；`_REDACT_KEYS`/`_SHARE_REDACT_PATHS`/`_SENSITIVE_KEYS` 三个集合必须分离；UI 层用 `Input.Password` 组件隐藏敏感内容（前端层防护）
  - **核心机制**（审查时必须理解）：
    - `_REDACT_KEYS`（全局脱敏字段集）会脱敏所有 API 响应，前端无法回显需展示的字段
    - 凭据字段需在前端回显（用户已填写的值），不能加入 `_REDACT_KEYS`
    - 凭据字段在分享/导出场景必须脱敏（防止泄露），需加入 `_SHARE_REDACT_PATHS`
    - 凭据字段在日志输出必须脱敏（防止日志泄露），需加入 `_SENSITIVE_KEYS`
    - UI 层用 `Input.Password` 组件隐藏敏感内容（前端层防护），不依赖后端脱敏
  - **判断信号**：
    - API 返回字段被脱敏但前端需要回显（如 `***` 显示在输入框）→ 必查 `_REDACT_KEYS` 是否包含该字段
    - 分享/导出场景未脱敏凭据字段 → 必查 `_SHARE_REDACT_PATHS` 是否包含该字段
    - 日志中打印凭据明文 → 必查 `_SENSITIVE_KEYS` 是否包含该字段
    - 同一字段在所有 API 场景脱敏策略一致（如所有 API 都脱敏或都不脱敏）→ 视为可疑（未区分场景）
  - **修复模式**：
    ```python
    # ✅ 1. 三个脱敏集合分离
    _REDACT_KEYS = frozenset({
        "cookie", "cookies", "session_id",  # 仅前端无需回显的真正敏感字段
    })
    _SHARE_REDACT_PATHS = [
        ("notifier", "channels"),
        ("serverchan_send_key",),
        ("pushplus_token",),
        ("bark_server",),
        ("bark_key",),
        ("telegram_bot_token",),
        ("telegram_chat_id",),
        ("wecom_webhook",),
        ("dingtalk_webhook",),
        ("dingtalk_secret",),
        ("webhook_url",),
        ("browser", "user_data_dir"),
    ]
    _SENSITIVE_KEYS = frozenset({
        "serverchan_send_key", "pushplus_token", "bark_key", "bark_server",
        "telegram_bot_token", "telegram_chat_id", "wecom_webhook",
        "dingtalk_webhook", "dingtalk_secret", "webhook_url",
        "openai_api_key",
    })

    # ✅ 2. GET /api/config 不脱敏凭据（前端需回显）
    @app.get("/api/config")
    async def get_config():
        return config.model_dump()  # 凭据字段原样返回

    # ✅ 3. /share 端点用 _SHARE_REDACT_PATHS 脱敏
    @app.post("/share")
    async def share_config():
        data = config.model_dump()
        return _redact_paths(data, _SHARE_REDACT_PATHS)

    # ❌ 错误：所有 API 都用 _REDACT_KEYS 脱敏凭据
    # _REDACT_KEYS = frozenset({"cookie", "serverchan_send_key", "dingtalk_webhook", ...})
    # @app.get("/api/config")
    # async def get_config():
    #     return _redact(config.model_dump(), _REDACT_KEYS)  # 前端拿到 ***，无法回显
    ```
  - **配置参数**：`redact_strategy.scenarios`（场景列表，如 `["config_response", "share_response", "export_response", "log_output"]`）、`redact_strategy.scenario_field_map`（场景到字段集的映射，如 `{config_response: [], share_response: ["serverchan_send_key", ...]}`）、`redact_strategy.ui_protection_components`（默认 `["Input.Password", "MaskedText"]`，前端 UI 层防护组件白名单）在 `config.yaml` 的 `redact_strategy` 节点管理
  - **适用**：所有需要脱敏的敏感字段（凭据、Cookie、Token、用户隐私数据）；多场景 API 返回相同字段但脱敏策略不同；前端需回显但分享需脱敏的场景
  - **不适用**：单一场景的字段（所有 API 都需脱敏或都不需脱敏）；非敏感字段（如配置项的开关状态）；前端纯展示字段（无后端写入需求）
  - **历史教训**：通知渠道凭据字段被加入 `_REDACT_KEYS`，导致 `GET /api/config` 返回 `***`，前端无法回显用户已填写的凭据。修复后将凭据字段从 `_REDACT_KEYS` 移除（前端需回显），同时扩展 `_SHARE_REDACT_PATHS` 和 `_SENSITIVE_KEYS`（分享和日志仍脱敏），前端用 `Input.Password` 组件隐藏内容

### 11. 错误处理

- 【禁止】裸 `except:` 或 `except Exception:` 静默吞掉（`except: pass`）
- 【禁止】过宽 `except Exception` / `except BaseException`
- 【强制】捕获异常后保留原始堆栈：`raise NewException("msg") from e`
- 【强制】三层兜底错误处理：
  1. 路由层抛业务异常（如 `ResumeBlockedError`）
  2. `register_exception_handlers` 统一转 JSON 响应
  3. loguru 兜底记录
- 【强制】`asyncio.CancelledError` 是唯一例外，必须向上传播以触发资源清理（**不**静默吞掉）
- 【推荐】重试逻辑用 `tenacity`（退避策略、最大重试次数），禁止 `while True: try`
- 【推荐】资源释放用 `with` 或 `try/finally`
- 🆕v4.1【强制】**B-REVIEW-SESSION-SIGNAL：重试失败后状态信号必须传递**
  - SSE/HTTP 接口包含重试逻辑时，重试代码块结束后必须检查关键状态标志（如 `last_session_invalid`）
  - 状态仍异常则推送明确错误事件并 `return`，**禁止**"重试失败但仍走成功流程"误导用户
  - **判断信号**：代码含 `retry_*` / `raw_results = await retry_*(...)` → 重试后必须检查状态标志
  - **不通过示例**：
    ```python
    raw_results = await retry_search(...)
    logger.info("raw_results={}", len(raw_results))  # 0 商品但未检查 session_invalid
    # 继续走 filtering → 前端误以为"真的没货"
    ```
  - **通过示例**：
    ```python
    raw_results = await retry_search(...)
    if not raw_results and getattr(container.collector, "last_session_invalid", False):
        yield sse({"stage": "error", "detail": "会话已过期，请重新登录", "status": 403})
        return
    ```
- 🆕v4.1【强制】**错误粒度三类区分**：面向用户的错误响应必须按粒度区分（状态码与文案映射在 `config.yaml` 的 `error_status_mapping` + `error_message_templates` 节点管理）
  - `503/504`：稍后重试（网络超时/限流/服务繁忙）
  - `401/403`：需用户介入（登录失效/权限不足）+ 明确指引"请前往 X 重新登录"
  - `502`：需重启服务（浏览器断开/TargetClosed）
  - **判断信号**：错误源于 `_m_h5_tk` 过期/Cookie 失效 → 401/403；`asyncio.TimeoutError` → 503/504；`TargetClosedError` → 502
- 🆕v4.3【强制】**B-REVIEW-FALLBACK-CHAIN：降级链模式**
  - 多重方案按优先级排序，失败后自动降级，3 次失败加倍间隔，最大间隔 2 小时
  - **判断信号**：多方案优先级明确 + 网络不稳定环境 + 外部依赖不可控
  - **修复模式**：方案 A 失败 → 尝试方案 B → 方案 B 失败 N 次后触发 backoff（`interval *= 2`，上限 `max_interval`）→ 记录降级原因到日志
  - **配置参数**：`max_failures=3`、`backoff_multiplier=2`、`max_interval=7200` 在 `config.yaml` 的 `fallback_chain` 节点管理（不硬编码）
  - **适用**：Cookie 同步（offline import → CDP import → backoff）、网络重试、外部 API 调用
  - **不适用**：单一方案场景、降级后体验差于报错（应直接失败）、关键安全场景（必须 fail-fast）
  - **历史教训**：Cookie 同步调度器实现 offline import 优先 → CDP import 次之 → backoff 兜底的降级链，3 次失败后间隔加倍避免无意义重试
- 🆕v4.4【强制】**B-REVIEW-FAST-DEGRADATION：快速模式降级重试**
  - `fast=True` 模式跳过恢复机制（token 刷新、RGV587 重试）时，调用方应在 fast 失败后自动以非 fast 模式重试一次
  - **判断信号**：方法签名含 `fast=True` 参数且 fast 模式跳过 `_ensure_fresh_*` / `*_retry` 逻辑 → 调用方必须检查 fast 返回结果的状态标志，失败时降级重试
  - **修复模式**：`fast=True` 返回空结果且状态标志（如 `last_session_invalid=True`）指示可恢复 → 自动以 `fast=False` 重试 → 重试成功则正常返回，失败才报错 → 重试超时应放宽以容纳 token 刷新 + 搜索
  - **配置参数**：降级重试超时（默认 45s）在 `config.yaml` 的 `search.fast_degradation_timeout` 节点管理
  - **适用**：所有 fast/quick 模式接口（跳过恢复机制的快速路径）
  - **不适用**：纯查询接口（无副作用）、实时性要求极高的接口（如心跳检测）、重试成本过高的操作
  - **历史教训**：实时搜索用 `fast=True` 完全跳过 `_ensure_fresh_m5tk()` 和 RGV587 重试，刚登录后第一次搜索碰巧 token 有效成功，后续连续请求时 token 过期全部失败
- 🆕v4.9【强制】**B-REVIEW-STATE-MACHINE-WHITELIST：状态机白名单转换**
  - 含「状态」字段且状态会变化的业务对象（订单/任务/会话/工作流）必须按 6 步流程设计状态机：枚举穷举 / 转换白名单 / 终态不可复活 / 中间态超时清理 / deadline 不可无限重置 / 前后端枚举值统一
  - **判断信号**：业务对象有 `status` / `state` 字段 + 字段会通过 API / 调度器 / 事件变更 → 必须按 6 步流程设计
  - **修复模式**：
    ```python
    # ✅ 白名单模式：仅允许 pending_pay → takeover_pending
    ALLOWED_TRANSITIONS: dict[str, set[str]] = {
        "pending_pay": {"takeover_pending", "cancelled"},
        "takeover_pending": {"succeeded", "failed"},
        # 终态 succeeded/failed/cancelled 不在 key 中 → 任何转换都被拒绝
    }
    def transition(current: str, target: str) -> None:
        if current not in ALLOWED_TRANSITIONS or target not in ALLOWED_TRANSITIONS[current]:
            raise HTTPException(409, detail=f"非法状态转换: {current} → {target}")

    # ✅ 中间态超时清理：独立调度器 + 一次 SQL 批量更新
    class TakeoverTimeoutScheduler:
        def _scan_and_expire(self) -> None:
            expired_ids = self._select_expired_ids()  # SELECT 在事务内
            if expired_ids:
                self.repo.expire_takeover_pending_orders(self.timeout_min)  # 一次 UPDATE
    ```
  - **关键约束**：
    - 状态变更操作必须用**白名单**（仅允许明确列出的转换）而非黑名单（禁止某些转换）——白名单更安全：新增状态时不会意外允许非法转换
    - `failed`/`succeeded`/`cancelled` 等终态禁止再转换到其他状态，状态变更接口必须前置校验 `if current_status in TERMINAL_STATES: raise HTTPException(409, ...)`
    - `pending_pay`/`takeover_pending` 等中间态必须有超时清理机制——独立 APScheduler `BackgroundScheduler` 定时扫描 + 一次 SQL 批量更新（SELECT + UPDATE 在同一事务），**禁止**逐条更新
    - `takeover_deadline` 等截止时间字段，同一操作（如 `takeover_order`）禁止反复延长，状态机白名单天然保证
    - 后端 `status: str = "pending_pay"` 与前端 `type Status = 'pending_pay' | ...` 必须字面值完全一致，**禁止**后端 snake_case 前端 camelCase 的映射转换
  - **配置参数**：`state_machine.<entity>.timeout_scan_interval`（默认 300s）、`state_machine.<entity>.timeout_threshold`（默认 1800s）、`state_machine.<entity>.terminal_states`（终态列表）、`state_machine.<entity>.allowed_transitions`（白名单映射）在 `config.yaml` 的 `state_machine` 节点管理
  - **适用**：订单/任务/会话/工作流等有状态生命周期的业务对象
  - **不适用**：纯 CRUD 实体（如配置项，无状态流转）；单状态字段（如 `is_active: bool` 用简单 if 判断即可）；一次性事件（如日志记录）
  - **历史教训**：`takeover_order` 接口未校验起始状态，导致 `failed` 终态订单可被接管（终态复活）；`takeover_pending` 超时无清理机制，订单永久卡死；同一订单可被反复 `takeover_order` 延长 deadline（无限重置）。修复后改为白名单 + 独立调度器批量清理 + 终态前置校验
- 🆕v4.11【强制】**B-REVIEW-LLM-DEFENSIVE-PARSING：LLM 响应防御性三层级解析**
  - 调用 LLM API（OpenAI 兼容协议、Anthropic、本地模型）的响应必须按三层级防御性解析：`choices → message → content`，每层用 `.get()` / `isinstance` / 长度检查，**禁止**直接 `response["choices"][0]["message"]["content"]` 链式访问导致 KeyError / IndexError
  - **核心机制**（审查时必须理解）：
    - LLM 服务异常时返回 `{"error": "..."}` 而非 `{"choices": [...]}`
    - 流式响应中 chunk 可能缺少 message 字段（仅含 delta）
    - content 可能为 null（如 function_call 场景）或空字符串
    - 链式访问任一层失败都会抛 KeyError/IndexError，导致 AI 建议任务静默失败
  - **判断信号**：
    - 代码含 `response["choices"]` 或 `response['choices'][0]` → 必须用 `.get()` + 边界检查
    - 代码含 `response["choices"][0]["message"]["content"]` 链式访问 → 视为违规
    - 代码含 `choices = response.get("choices", [])` + `if choices:` → 通过第一层校验
  - **修复模式**：
    ```python
    # ✅ 三层级防御性解析
    def _extract_llm_content(response: dict) -> str | None:
        # 第一层：choices 数组存在且非空
        choices = response.get("choices") if isinstance(response, dict) else None
        if not choices or not isinstance(choices, list):
            logger.warning("LLM 响应缺少 choices 字段：{}", response)
            return None
        # 第二层：message 对象存在
        first = choices[0] if len(choices) > 0 else {}
        message = first.get("message") if isinstance(first, dict) else None
        if not message or not isinstance(message, dict):
            logger.warning("LLM 响应缺少 message 字段")
            return None
        # 第三层：content 字符串非空
        content = message.get("content")
        if not content or not isinstance(content, str):
            logger.warning("LLM 响应 content 为空")
            return None
        return content.strip()

    # ❌ 错误：链式访问任一层失败都会抛异常
    # content = response["choices"][0]["message"]["content"]
    ```
  - **配置参数**：`llm_defensive_parsing.required_layers`（默认 `["choices", "message", "content"]`，必须校验的层级）、`llm_defensive_parsing.allow_empty_content`（默认 `false`，空 content 视为失败）、`llm_defensive_parsing.fallback_strategy`（默认 `return_none`，可选 `raise`）、`llm_defensive_parsing.supported_apis`（默认 `["openai_compatible", "anthropic", "ollama"]`）在 `config.yaml` 的 `llm_defensive_parsing` 节点管理
  - **适用**：所有调用 LLM API 的代码（OpenAI 兼容协议 / Anthropic / 本地 Ollama / sentence-transformers）；流式响应（每个 chunk 也需校验）
  - **不适用**：本地模型直接返回对象（无 JSON 解析）；Embedding API 响应（结构不同）；Mock 测试响应
  - **历史教训**：`_call_ai_suggestion` 直接 `response["choices"][0]["message"]["content"]`，LLM 服务异常时返回 `{"error": "..."}` 导致 KeyError 未捕获，AI 建议任务静默失败
- 🆕v4.19【强制】**B-REVIEW-SELECTOR-REPOSITORY-SYNC：选择器仓库同步与单一数据源**
  - 同一 DOM 数据源的所有解析路径（主解析 `_find_cards` / 批量解析 `_BATCH_PARSE_SCRIPT` / 降级解析）必须引用同一选择器仓库，JS 脚本必须动态拼接选择器字符串（禁止内联 CSS 选择器），ID 提取必须有 3 层兜底（data-* 属性 → 内部任意 a[href] → /item/数字 路径），新增选择器候选时自动同步到所有解析路径
  - **核心机制**（审查时必须理解）：
    - DOM 解析常有多条路径（主流程 `page.query_selector_all` + 批量脚本 `page.evaluate` 嵌入 JS + 降级 og:meta），若各路径独立维护选择器列表，闲鱼前端 DOM 变更时只改主解析器会遗漏批量脚本
    - JS 脚本字符串中硬编码 CSS 选择器无法被 Python 端静态检查，必须通过 f-string 或 `.format()` 动态注入
    - 选择器仓库（selector repository）需提供 `to_js_selector_string()` 方法，将 Python 列表转为 JS `document.querySelectorAll('...')` 可用的字符串
    - ID 提取单层失败即返回 None 会导致大量卡片被丢弃，3 层兜底保证极端 DOM 变更下仍能提取
  - **判断信号**：
    - `grep "document\.querySelectorAll" src/xianyu_hunter/modules/` 发现 JS 字符串中硬编码选择器 → 视为违规
    - 主解析器的 `card_selectors` 列表与 `_BATCH_PARSE_SCRIPT` 内的选择器字符串不一致 → 视为违规
    - 修改主解析器选择器后未同步批量脚本（grep 验证）→ 视为违规
    - DOM 解析脚本中 ID 提取只有单层无兜底 → 视为可疑
    - `grep "_BATCH_PARSE_SCRIPT\|_PARSE_SCRIPT" src/` 发现 JS 字符串中含 `'[class*='` 字面量 → 视为可疑
  - **修复模式**：
    ```python
    # ✅ 选择器仓库提供 Python 与 JS 双端消费形式
    class SelectorRepository:
        def search_card_candidates(self) -> list[str]:
            """搜索卡片候选选择器（单一数据源）"""
            return [
                "[class*='feeds-item-wrap']", "[class*='feeds-item']",
                "[class*='item-card']", "[class*='search-item']",
                "[class*='product-card']", "[data-spm*='item']",
            ]
        def to_js_selector_string(self) -> str:
            """转为 JS document.querySelectorAll 可用的字符串"""
            return ", ".join(self.search_card_candidates())

    # ✅ 批量解析脚本动态拼接选择器
    def _build_batch_parse_script(self) -> str:
        js_selector = self.selectors.to_js_selector_string()
        return f"""
    () => {{
        const cards = document.querySelectorAll({js_selector});
        // ... 3 层 ID 提取兜底
    }}
    """

    # ❌ 错误：JS 脚本硬编码 2 种选择器，与主解析器的 6 种不一致
    # _BATCH_PARSE_SCRIPT = """
    # () => {
    #     const cards = document.querySelectorAll(
    #         "[class*='feeds-item-wrap'], [class*='feeds-item']"
    #     );
    # }
    # """
    ```
  - **配置参数**：`selector_repository_sync.enabled`（默认 `true`）、`selector_repository_sync.require_js_consumer_method`（默认 `true`，选择器仓库必须提供 `to_js_selector_string()` 方法）、`selector_repository_sync.audit_files`（默认 `["_search.py", "_parser.py", "_detail.py"]`，需稽查选择器一致性的文件）、`selector_repository_sync.batch_script_marker`（默认 `"_BATCH_PARSE_SCRIPT"`，批量解析脚本变量名标识）、`selector_repository_sync.require_id_fallback_layers`（默认 `3`，ID 提取兜底层数）在 `config.yaml` 的 `selector_repository_sync` 节点管理
  - **适用**：同一 DOM 数据源有多条解析路径（主解析 + 批量解析 + 降级解析）；DOM 解析脚本嵌入到 Playwright `page.evaluate` 中执行；闲鱼/淘宝/第三方网站前端 DOM 结构频繁变更的场景
  - **不适用**：API 响应解析（结构固定，无 DOM 选择器概念）；单次单卡片解析（无批量场景）；一次性爬虫脚本（无长期维护需求）
  - **历史教训**：DOM 回退模式检测到 31 个卡片，但 `_BATCH_PARSE_SCRIPT` 仅用 2 种选择器（`feeds-item-wrap`/`feeds-item`），与 `_find_cards` 的 6 种选择器（含 `item-card`/`search-item`/`product-card`/`data-spm*='item'`）不一致，导致仅提取到 1 条数据。修复：选择器对齐为 6 种 + 新增 3 层 ID 提取兜底（data-* 属性、内部任意 a[href]、/item/数字 路径）
- 🆕v4.25【强制】**B-REVIEW-CRITICAL-PATH-NO-SWALLOW：关键路径异常可见性**
  - 启动钩子（`_on_startup`）/ 迁移函数（`run_migrations`）/ 初始化函数（`_init_*`）等关键路径的外层 except 必须用 `logger.exception()` 输出完整 traceback，**禁止** `logger.warning(f"...{e}")` 丢失堆栈
  - **核心机制**（审查时必须理解）：
    - 关键路径的异常通常意味着系统无法正常启动或数据库 schema 不一致，必须保留完整堆栈用于事后排查
    - `logger.warning(f"...{e}")` 只输出异常消息字符串（如 "no such column: notifications.read_at"），丢失调用栈（哪一行触发、从哪里调用），难以定位根因
    - `logger.exception()` 自动附加完整 traceback，等同于 `logger.error(..., exc_info=True)`
    - 关键路径的异常**不应被静默吞掉**——即使选择"忽略并继续启动"，也必须输出 ERROR 级别日志（含 traceback）让运维感知
  - **判断信号**：
    - 代码含 `@app.on_event("startup")` / `def _on_startup` / `def run_migrations` / `def _init_*` + 外层 `except Exception as e: logger.warning(f"...{e}")` → 视为违规
    - 代码含 `except Exception as e: logger.warning("...: {}", e)` 在启动钩子中 → 视为违规（loguru 占位符也不保留 traceback）
    - 代码含 `except Exception as e: logger.warning(f"启动迁移钩子失败（忽略）: {e}")` → 视为违规（"忽略"语义 + warning 级别 + 无 traceback 三重问题）
  - **修复模式**：
    ```python
    # ✅ 关键路径：用 logger.exception() 输出完整 traceback
    @app.on_event("startup")
    async def _on_startup() -> None:
        try:
            run_migrations(container)
            await _init_schedulers(container)
        except Exception:
            logger.exception("启动钩子失败，部分功能可能不可用")
            # 选择"忽略并继续启动"而非 raise，让主服务可用

    # ❌ 错误：warning + f-string 丢失堆栈
    # @app.on_event("startup")
    # async def _on_startup():
    #     try:
    #         run_migrations(container)
    #     except Exception as e:
    #         logger.warning(f"启动迁移钩子失败（忽略）: {e}")  # 丢失 traceback

    # ❌ 错误：silent pass 完全吞掉
    # except Exception:
    #     pass  # 无任何日志，问题完全隐藏
    ```
  - **关键约束**：
    - 关键路径函数清单（`_on_startup` / `run_migrations` / `_init_*`）在 `config.yaml` 的 `critical_path_no_swallow.critical_functions` 节点管理，便于自动化扫描识别
    - 禁止日志模式（`logger.warning(f"...{e}")` / `logger.warning("...: {}", e)` / `except: pass`）在 `critical_path_no_swallow.forbidden_patterns` 节点管理
    - 允许的简单 warning 场景（非关键路径，如可选缓存失效）在 `critical_path_no_swallow.allowed_simple_warning` 节点管理，避免误报
    - 与 B-REVIEW-MIGRATION-BLOCK-ISOLATION 联动：迁移块各自 try/except 后，外层启动钩子仍需用 `logger.exception()` 兜底
    - 与 B-REVIEW-MIGRATION-FAILURE-HANDLING 区别：本节点关注**外层**异常可见性，B-REVIEW-MIGRATION-FAILURE-HANDLING 关注**迁移函数内部**的策略（raise vs warn）
  - **配置参数**：`critical_path_no_swallow.critical_functions`（关键路径函数名列表，如 `["_on_startup", "run_migrations", "_init_schedulers", "_init_components"]`）、`critical_path_no_swallow.require_exception_logger`（是否要求 `logger.exception()`，默认 `true`）、`critical_path_no_swallow.forbidden_patterns`（禁止的日志模式正则列表，如 `["logger\\.warning\\(f\".*\\{e\\}\"", "except.*pass"]`）、`critical_path_no_swallow.allowed_simple_warning`（允许简单 warning 的非关键路径函数名列表，如 `["_refresh_cache", "_cleanup_temp"]`）在 `config.yaml` 的 `critical_path_no_swallow` 节点管理
  - **适用**：启动钩子（`@app.on_event("startup")`）；数据库迁移函数（`run_migrations` / `_migrate_*`）；组件初始化函数（`_init_*`）；任何"失败即影响核心功能"的关键路径
  - **不适用**：非关键路径（如可选缓存刷新、临时文件清理）；已由 B-REVIEW-MIGRATION-FAILURE-HANDLING 管控的迁移函数内部策略；用户请求处理（应由路由层异常处理器管控）
  - **历史教训**：`_on_startup` 的外层 `try/except Exception as e: logger.warning(f"启动迁移钩子失败（忽略）: {e}")` 吞掉了 `run_migrations` 内 C-01 `auto_migrate_task_links()` 的异常，日志仅显示 "启动迁移钩子失败（忽略）: ...",无法定位是哪个迁移块失败。修复后改为 `logger.exception("启动钩子失败...")`，完整 traceback 暴露问题根因

### 12. 日志规约

- 【强制】使用 loguru（非 stdlib `logging`）
- 【强制】三 sink 配置：
  - stderr 彩色输出
  - JSON 文件按日滚动（保留 14 天）
  - 纯文本文件
- 【强制】request_id 全链路追踪：`ContextVar` + loguru patcher 钩子
- 【强制】敏感数据脱敏：`_SENSITIVE_HEADERS` 包含 `authorization/cookie/xh_token/set-cookie`
- 【强制】异常必须包含异常对象：`logger.error("msg", e)`（**禁止** `logger.error("msg")`）
- 【强制】token 写入失败必须 `logging.warning()` 告警
- 【禁止】日志记录密码/密钥/Token 明文
- 【推荐】四级日志：ERROR（异常/失败） / WARN（潜在问题） / INFO（关键操作） / DEBUG（调试，生产关闭）
- 【强制】loguru 日志使用 `{}` 占位符，**禁用** `%s`/`%d`/`%f` printf 风格（loguru 不解析，导致参数未替换）
  - ✅ `logger.info("task={} rows={}", task_id, rows)`
  - ❌ `logger.info("task=%s rows=%d", task_id, rows)` → 输出原始 `%s`/`%d`
- 【强制】耗时日志使用 `{:.1f}` 格式化毫秒值，保留一位小数
- 🆕v4.10【强制】**B-REVIEW-LOGURU-PLACEHOLDER：日志库占位符一致性**
  - 项目选定单一日志库后（如 loguru），所有 `logger.xxx()` 调用必须使用该库的占位符语法，**禁止**混用其他日志库的占位符（loguru 用 `{}`，标准 logging 用 `%s`/`%d`）
  - **核心机制**（审查时必须理解）：
    - loguru 不识别 `%s`/`%d` 占位符，但混用**不会抛异常**，会导致日志输出"%s"字面量而非实际值，极难发现
    - 标准 logging 不识别 `{}` 占位符，混用同样不抛异常但输出"{}"字面量
    - f-string 是 Python 原生字符串拼接，与日志库无关，简单拼接可用，但复杂格式推荐用占位符（性能更好，延迟格式化）
  - **判断信号**：
    - 项目用 loguru（`from loguru import logger`）但代码含 `logger.xxx("...%s...", arg)` → 视为违规
    - 项目用标准 logging 但代码含 `logger.xxx("...{}...", arg)` → 视为违规
    - 日志输出含 `%s`/`%d`/`{}` 字面量而非实际值 → 典型症状
    - `grep -nE 'logger\\.(debug|info|warning|error|critical).*%[sdrf]' file.py` 命中 → loguru 项目混用 `%s` 违规
  - **修复模式**：
    ```python
    # ✅ loguru：{} 占位符
    from loguru import logger
    logger.info("用户 {} 登录，耗时 {:.2f}s", user, elapsed)
    logger.warning("Cookie 刷新失败，原因：{}", reason)

    # ❌ 错误：loguru 项目混用 %s（不抛异常但输出 "%s" 字面量）
    logger.info("用户 %s 登录", user)
    logger.warning("Cookie 刷新失败，原因：%s", reason)

    # ✅ 标准 logging：%s 占位符
    import logging
    logger = logging.getLogger(__name__)
    logger.info("用户 %s 登录", user)

    # ✅ f-string 例外（简单拼接可用）
    logger.info(f"用户 {user} 登录")
    ```
  - **配置参数**：`log_placeholder.logger_lib`（默认 `loguru`，可选 `logging`/`structlog`）、`log_placeholder.placeholder_pattern`（默认 `\\{\\}` 对 loguru，`%[sdrf]` 对 logging）、`log_placeholder.forbidden_pattern`（默认 `%[sdrf]` 对 loguru 项目）、`log_placeholder.logger_method_names`（默认 `["debug", "info", "warning", "error", "critical"]`）、`log_placeholder.allow_fstring`（默认 `true`，允许简单 f-string 拼接）在 `config.yaml` 的 `log_placeholder` 节点管理
  - **诊断流程**（出现"日志输出 %s 字面量"类问题时执行）：
    1. `grep -nE 'logger\\.(debug|info|warning|error|critical).*%[sdrf]' src/` 扫描所有 logger 调用
    2. 确认项目使用的日志库（`grep "from loguru" src/` vs `grep "import logging" src/`）
    3. 若是 loguru 项目，所有 `%[sdrf]` 占位符均为违规，改为 `{}`
    4. 若是 logging 项目，所有 `{}` 占位符均为违规，改为 `%[sdrf]`
  - **适用**：所有用 loguru/standard logging/structlog 的项目；混用多个日志库的项目（需统一到单一日志库）
  - **不适用**：未使用日志库的项目（如仅用 print）；自定义日志库（需在配置中声明占位符语法）
  - **历史教训**：`cookie_rotator.py` 第 197、245 行用 `logger.warning("...%s...", reason)`（loguru 项目混用 `%s`），loguru 不识别 `%s` 占位符但不抛异常，导致日志输出"Cookie 刷新失败，原因：%s"字面量。修复后改为 `logger.warning("...{}", reason)`

### 13. 代码质量

- 【强制】缺失导入检查（`re`、`threading`、`logging` 等必须在模块级导入，避免函数内 NameError）
- 【强制】函数内冗余导入移到模块级
- 【强制】异步/同步混用检查（`await` 是否用于同步方法）
- 【强制】`ImportError` 检查（异常类、符号是否正确导入）
- 【强制】**async/await 一致性**：异步方法调用必须保留 `await`，合并冲突时优先保留异步版本
- 🆕【强制】**S3776**：认知复杂度 ≤ 15，拆分大函数为多个小函数
  - **实战案例**：
    - `login_orchestrator.start_session` 拆为 7 个小方法（`_validate_session/_acquire_browser/_navigate_login/_wait_for_qrcode/_poll_session_status/_update_token_store/_emit_started_event`）
    - `cookie_store.upsert_cookie_values` 拆为 4 个小方法（`_resolve_existing_user/_upsert_user_record/_upsert_cookies/_cleanup_orphans`）
- 🆕【强制】**S6767**：未使用的参数/属性/局部变量 ——立即删除或用 `_` 前缀
- 🆕【强制】**S1192**：重复的字符串字面量 ——提取为模块级常量（如 `_TASK_NOT_FOUND = "任务不存在"`）
- 🆕【强制】**S5843**：正则表达式复杂度过高 ——可拆分为多个简单正则或改用字符串方法
- 【推荐】代码重复检查（DRY 违规）
- 【推荐】函数职责单一性（SRP），超长函数拆分
- 【推荐】深层嵌套 ≤ 4 层，复杂条件提取为命名变量或函数
- 【推荐】魔法数字/字符串提取为常量
- 【推荐】注释解释"为什么"而非"做什么"
- 🆕v4.0【强制】**注释与代码一致性**：注释必须与代码逻辑严格一致，禁止误导性注释
  - 防御性说明需明确标注是"防御性"而非"必需"（如"顺序不影响结果，但保留防御性排列"）
- 🆕v4.5【强制】**B-REVIEW-DEAD-CODE-CLEANUP：死代码检测与清理**
  - 业务流程中**未在任何调用点被触发的函数/方法**必须在每次大版本（v4.x → v4.x+1）时主动检测并清理
  - **判断信号**：
    - 函数被定义（如 `def on_login_success(self): ...`）但 `grep -rn "on_login_success" src/` 找不到任何调用
    - 事件订阅被注册但 `grep` 不到发布者
    - 抽象方法被子类实现但从未被子类外部调用
  - **检测方法**：
    1. `git log -p --all -S "<function_name>"` 查看该函数的所有历史变更
    2. `grep -rn "<function_name>" src/ tests/` 确认无任何调用方
    3. 在 PR/Commit 描述中显式标注"删除死代码 X"
  - **修复模式**：
    - **找到调用方**：恢复调用路径（适合误删调用方导致的死代码）
    - **改写为入口函数**：将死代码改写为"统一同步入口"（如 `on_login_success` 改写为 `sync_cookie_layers_from_json`）
    - **直接删除**：无任何依赖时直接删除
  - **配置参数**：`dead_code_check_enabled`（默认 `true`）、`dead_code_ignore_list`（保留作为 API 接口的方法名白名单）在 `config.yaml` 的 `dead_code_cleanup` 节点管理
  - **适用**：所有"定义即遗忘"的函数/回调/事件订阅/类方法
  - **不适用**：保留作为 API 接口的方法（即便未被内部调用）、测试 fixture、抽象基类
  - **历史教训**：`CookieRotator.on_login_success` 方法被定义后从未被任何登录路径调用，"逻辑上应该被触发"但实际是死代码，导致登录后层状态永远不更新
  - 涉及顺序约束、依赖关系的注释需验证是否真实存在该约束
  - **历史教训**：注释称"必须在 X 之前判断避免误匹配"，但实际不存在误匹配风险
- 🆕v4.6【强制】**B-REVIEW-REUSE-PATTERN：复用既有模式原则**
  - 新增功能前必须先 `grep` 项目内相似实现，复用既有 helper / 工具函数 / 模式（如 `_utcnow` / `_escape_like` / `hmac.compare_digest` / `asyncio.wait_for` / `logger.warning`），**禁止**重复造轮子或实现已有模式的变体
  - **判断信号**：新增函数 + `grep` 发现已有相似命名/相似参数/相似功能的函数 → 必须复用而非重复实现；新增异步操作未复用 `asyncio.wait_for` 模式 → 视为违规
  - **修复模式**：
    1. **搜索阶段**：`grep -rn "<相似关键词>" src/` 查找已有实现
    2. **评估阶段**：对比新增函数与已有函数的差异（参数差异 / 返回值差异 / 副作用差异）
    3. **复用阶段**：直接调用已有函数 / 抽取公共部分为 helper / 在已有函数上增加参数
    4. **文档阶段**：在新增函数 docstring 中说明"为什么不复用 X"（如适用）
  - **关键约束**：
    - 复用优先级：**项目内 helper > 标准库 > 第三方库 > 新实现**
    - 复用必须**保持一致性**：调用方式、参数命名、返回值格式与已有函数一致
    - 若已有函数不完全满足需求，应**扩展已有函数**而非新建（参考 B-REVIEW-FILTER-SCENARIO 参数化场景标志）
    - 必须复用的常见模式：`asyncio.wait_for`（异步超时）、`hmac.compare_digest`（凭据比较）、`_escape_like`（SQL LIKE 转义）、`_utcnow`（UTC 时间）、`logger.warning`（告警日志）
  - **配置参数**：`search_keywords`（必须搜索的关键词列表）、`similarity_threshold`（默认 0.7，相似度高于此值时强制复用）、`reuse_priority`（复用优先级顺序）在 `config.yaml` 的 `reuse_pattern` 节点管理
  - **适用**：所有新增功能 / 工具函数 / 帮助类 / 异步操作 / 安全相关代码
  - **不适用**：业务完全独立的全新功能、性能优化重写、技术债清理重构
  - **历史教训**：`refresh_item` 直接 `await collector.detail()` 而未复用 v4.4 的 fast 模式重试机制（`fast=False` 重试一次），也未加 `asyncio.wait_for` 整体超时（B-REVIEW-ASYNC-TIMEOUT 规范），导致浏览器异常时无限挂起。修复时复用 `asyncio.wait_for` 模式 + 504 状态码（与 v4.1 错误粒度三类区分一致）
- 🆕v4.11【强制】**B-REVIEW-NUMERIC-EXTRACTION：文本数值提取模式**
  - 从可能含多个数字的文本中提取数值时，必须用 `re.findall` 取 `numbers[-1]`（最后一个数字），**禁止** `re.search` 取第一个数字，因实际成交价/当前值通常出现在最后（如"原价 1000 现价 500"应取 500）
  - **核心机制**（审查时必须理解）：
    - 自由文本中可能含多个数字（原价/现价、最小值/最大值、原数量/现数量）
    - 实际成交价/当前值通常出现在最后（"原价 X 现价 Y"、"从 X 降到 Y"）
    - `re.search` 只取第一个匹配，会误取原价/最小值
    - `re.findall` 返回所有匹配，取 `[-1]` 获取最后一个（实际值）
  - **判断信号**：
    - 代码含 `re.search(r"\d+", text)` 或 `re.match(r"\d+", text)` 提取数值 → 必须评估文本是否可能含多数字
    - 代码含 `m = re.search(r"\d+(?:\.\d+)?", text)` 后 `float(m.group())` → 多数字场景会误取第一个
    - 用户反馈"价格提取错误"或"数值字段显示为原价而非现价" → 典型症状
  - **修复模式**：
    ```python
    # ✅ 取最后一个数字（实际成交价）
    import re
    text = "原价 1000 现价 500"
    numbers = re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))
    if numbers:
        actual_price = float(numbers[-1])  # 500，正确

    # ❌ 错误：取第一个数字（误取原价）
    # m = re.search(r"\d+(?:\.\d+)?", text)
    # if m: actual_price = float(m.group())  # 1000，错误

    # ✅ 有明确位置的文本用分组提取（例外场景）
    m = re.search(r"价格:\s*(\d+(?:\.\d+)?)", text)
    if m: price = float(m.group(1))  # 分组提取，明确位置
    ```
  - **配置参数**：`numeric_extraction_strategy.default_strategy`（默认 `last`，可选 `first`/`max`/`min`）、`numeric_extraction_strategy.scenarios`（场景到策略的映射，如 `price_extraction → last`、`quantity_extraction → first`、`max_value_extraction → max`）、`numeric_extraction_strategy.regex_pattern`（默认 `r"\d+(?:\.\d+)?"`）在 `config.yaml` 的 `numeric_extraction_strategy` 节点管理
  - **适用**：从自由文本提取数值（价格/数量/评分/版本号）；多数字场景（"原价 X 现价 Y"、"最小 X 最大 Y"）
  - **不适用**：单一数字文本（如纯数字字符串 "123"）；结构化数据（JSON 字段直接取值）；有明确位置的文本（如"价格:X"用 `re.search(r"价格:\s*(\d+)", text)` 分组提取）
  - **历史教训**：`_extract_actual_price` 用 `re.search` 取第一个数字，订单页文本为"原价 1000 现价 500"时误取 1000，导致价格校验失败抢单被拒
- 🆕v4.14【强制】**B-REVIEW-DEBUG-CODE-CLEANUP：临时 DEBUG 代码清理**
  - 临时 DEBUG 代码在问题修复后必须移除，**禁止**留在生产代码中。DEBUG 代码包括：临时 import（如 `import os as _os`）、临时环境变量检查（如 `environ.get("DEBUG")`）、临时日志文件写入（如 `open("debug.log", "w")`）、临时打印语句（如 `print("DEBUG: ...")`）。问题修复后必须 grep 所有 DEBUG 代码并移除，避免污染生产环境
  - **判断信号**：代码含 `import os as _os` / `environ.get("DEBUG")` / `open("debug.log")` / `print("DEBUG")` / `logger.debug` 异常密集 → 必须检查是否为临时 DEBUG 代码；问题修复后 grep 仍有 DEBUG 代码 → 必须移除
  - **修复模式**：
    ```python
    # ❌ 错误：问题修复后仍保留 DEBUG 代码
    import os as _os  # ❌ 临时 import 未移除
    if _os.environ.get("DEBUG"):  # ❌ 临时环境变量检查未移除
        with open("debug.log", "w") as f:  # ❌ 临时日志文件未移除
            f.write(str(response))

    # ✅ 正确：问题修复后移除所有 DEBUG 代码
    # grep -rn "DEBUG\|debug\.log\|import os as _os\|environ.get(\"DEBUG\")" src/
    # 确认无残留 DEBUG 代码
    ```
  - **配置参数**：`debug.enabled`（默认 `false`，生产环境禁止 DEBUG 代码）、`debug.cleanup_after_fix`（默认 `true`，问题修复后自动清理 DEBUG 代码）、`debug.whitelist`（长期监控指标白名单，如 `["performance_metrics", "health_check"]`）在 `config.yaml` 的 `debug` 节点管理
  - **适用**：临时调试代码、排查问题后的清理、开发环境调试
  - **不适用**：日志级别动态降级（需保留配置）、长期监控指标收集（需保留）、性能埋点（需保留）
  - **历史教训**：登录流程问题排查时添加 `import os as _os` 和 `open("debug.log", "w")` 写入调试信息，问题修复后未移除，导致生产环境产生 debug.log 文件污染日志目录

- 🆕v4.16【强制】**B-REVIEW-DIVZERO-FALLBACK：除零兜底禁止凑数**
  - **判断信号**：grep ` / 0\.` 或 `/ 0.1` 或 `/ max(*, 1)` 等可疑除零兜底；比值/比率/百分比计算中 previous_count/baseline 可能为 0
  - **强制规则**：除零/空值兜底禁止用凑数小数（`x / 0.1`）伪装比值；比值/比率/百分比计算中 previous_count/baseline 可能为 0 时直接置为 `0.0` 或 `float('inf')`；写入 reason/log 展示给用户的数值无意义时用字符串 `"N/A"` 而非数字
  - **反例**：`ratio = recent_count / 0.1 if recent_count > 0 else 0.0`（previous=0 时 ratio=100.0 误导用户）
  - **正例**：`if previous_count > 0: ratio = recent_count / previous_count else: ratio = 0.0` + `ratio_str = f"{ratio}x" if previous_count > 0 else "N/A"`
  - **配置参数**：`divzero_fallback` 节点（enabled / detect_patterns / display_value_for_empty_baseline）
  - **适用场景**：比值/比率/百分比计算；previous_count/baseline 可能为 0 的对比场景；写入 reason/log 展示给用户的数值
  - **不适用场景**：内部计算用途的兜底（如 max(prev, 1) 防止除零但结果不展示）；倒计时/计时器场景
- 🆕v4.19【强制】**B-REVIEW-EXTERNAL-TEXT-PATTERN-CENTRALIZE：外部系统文本特征集中管理**
  - 外部系统（闲鱼/淘宝/第三方 API）的文本特征（已售关键词/错误码/状态文案/反爬识别）必须提取为模块级常量（`tuple[str, ...]` 或 `frozenset[str]`），多处消费点必须复用同一纯函数（`check_xxx(text: str) -> bool`），禁止在消费点内联关键词列表（如 `if "已售" in text`），关键词清单变更时只需修改单一常量
  - **核心机制**（审查时必须理解）：
    - 外部系统文案会频繁变更（如闲鱼"已售" → "卖掉了"），分散在多个文件的关键词列表必然漏改
    - 模块级常量（`tuple[str, ...]`）不可变，便于扩展且线程安全
    - 纯函数（`check_xxx(text) -> bool`）无副作用，便于单测，多处消费点 import 同一函数
    - 关键词清单定义处必须注释历史遗漏案例，说明为什么集中维护
  - **判断信号**：
    - `grep "已售\|卖掉了\|已下架\|已删除" src/xianyu_hunter/` 发现同一关键词在多个文件重复 → 视为违规
    - 代码含 `if "xxx" in text` 但未调用统一函数 → 视为违规
    - 关键词以列表字面量出现在函数内部而非模块级常量 → 视为可疑
    - `grep "check_text_sold\|check_item_sold"` 调用点 < 定义点 → 视为可疑（有内联替代）
  - **修复模式**：
    ```python
    # ✅ 单一常量 + 纯函数 + 3 处复用
    # collector_utils.py
    SOLD_TEXT_KEYWORDS: tuple[str, ...] = (
        "已售", "已售出", "已售完", "已售罄", "宝贝已售", "商品已售",
        "已下架", "已卖出",
        "卖掉了",  # 闲鱼新版文案（2026-06-29 发现）
        "宝贝不存在", "宝贝走丢了", "该宝贝不存在", "商品不存在", "已删除", "已被删除",
    )

    def check_text_sold(text: str) -> bool:
        """检测页面文本是否表示商品已售。

        为什么集中维护：闲鱼前端文案多次变更，分散在 3 个文件的关键词列表容易漏改。
        历史遗漏案例：2026-06-29 发现商品 1058031608014 详情页显示"卖掉了"但被误判为在售。
        """
        if not text:
            return False
        return any(kw in text for kw in SOLD_TEXT_KEYWORDS)

    # _detail.py / _parser.py / buyer.py 统一复用
    from xianyu_hunter.modules.collector_utils import check_text_sold
    is_sold = check_text_sold(body_text)

    # ❌ 错误：3 处独立关键词列表，新增文案时漏改
    # _detail.py
    # if any(kw in body_text for kw in ["已售", "已售出", "已售完"]):
    #     is_sold = True
    # _parser.py
    # if "已售" in text or "已售出" in text:  # 漏了"卖掉了"
    #     return True
    # buyer.py
    # SOLD_KEYWORDS = ["已售", "已售出"]  # 漏了"卖掉了"
    ```
  - **配置参数**：`external_text_pattern_centralize.enabled`（默认 `true`）、`external_text_pattern_centralize.require_constant_extraction`（默认 `true`，强制提取为模块级常量）、`external_text_pattern_centralize.require_pure_function`（默认 `true`，强制封装为纯函数）、`external_text_pattern_centralize.audit_keywords`（默认 `["已售", "卖掉了", "已下架", "已删除"]`，需要稽查的关键词样例）、`external_text_pattern_centralize.max_inline_occurrences`（默认 `1`，同一关键词在代码中出现 >1 次且未引用常量 → 违规）、`external_text_pattern_centralize.require_version_comment`（默认 `true`，常量定义处必须注释历史遗漏案例）在 `config.yaml` 的 `external_text_pattern_centralize` 节点管理
  - **适用**：外部系统文案检测（已售/下架/错误状态/异常提示）；错误码识别（HTTP 状态码/业务错误码/反爬识别）；第三方 API 响应文本特征提取；多处消费同一类文本特征的场景
  - **不适用**：内部状态判断（如 `task.status == 'completed'`，前端可控）；单一消费点的临时字符串比较；配置文件中已管理的关键词（无需再提取为代码常量）
  - **历史教训**：商品 1058031608014 实际已售（详情页 body 文本含"卖掉了"），但 3 处独立关键词列表（`_detail.py` / `_parser.py` / `buyer.py`）都未包含"卖掉了"，导致系统误判为在售，用户看到已售商品仍被推荐。Chrome DevTools MCP 实际打开页面取 body 文本才发现该关键词。修复后提取 `SOLD_TEXT_KEYWORDS` 常量 + `check_text_sold()` 函数到 `collector_utils.py`，3 处复用

### 14. 配置管理

- 【强制】使用 `pydantic-settings` + `keyring` + `.env` 三层配置源
- 【强制】`get_settings()` 用 `@lru_cache` 单例
- 【强制】敏感字段（推送 Key 等）写入 keyring，`.env` 仅放占位符
- 【强制】环境变量优先级：env > .env > 配置文件默认值
- 【强制】`update_ai_config()` 热更新：写入 `.env` + keyring
- 【强制】Embedding 配置独立于 LLM 配置
- 【强制】HuggingFace 镜像：`local_embedding.py` 模块顶层（**在** `import sentence_transformers` 之前）`os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")`
- 【强制】sentence-transformers 5.x 兼容：`getattr(model, "get_sentence_embedding_dimension", getattr(model, "get_embedding_dimension", None))()`
- 【强制】当 `EMBEDDING_BASE_URL` 为空或 "local" 时，使用本地 sentence-transformers 后端（BAAI/bge-small-zh-v1.5，dim=512）
- 🆕v4.3【强制】**B-REVIEW-CONFIG-DRIVEN-TOGGLE：配置驱动功能开关模式**
  - 高风险/高资源消耗功能默认关闭，需用户显式启用；所有功能参数集中在 `Config` 类（如 `BrowserConfig`），不硬编码
  - **判断信号**：功能需用户主动选择 + 可能耗资源（CPU/内存/网络） + 多环境部署需求
  - **修复模式**：`Config` 类新增 `enable_flag: bool = False` + 详细参数字段 → `config.yaml` 暴露开关 → 文档明确启用条件与资源消耗
  - **配置参数**：`enable_flag` 默认 `false`，详细参数（interval/threshold/port）集中在相应 `Config` 类，`config.yaml` 的 `feature_toggles` 节点管理开关
  - **适用**：CDP 在线导入、Cookie 自动同步、向量库重建等高风险/高资源消耗功能
  - **不适用**：核心功能（必须默认启用）、性能敏感场景（配置加载延迟不可接受）、简单脚本工具
  - **历史教训**：`auto_sync` 默认 `false`，避免用户不知情下启用自动同步导致浏览器资源被占用；`cdp_port` 通过 `BrowserConfig` 管理而非硬编码
- 🆕v4.4【强制】**B-REVIEW-CONFIG-LINKAGE：配置全链路生效验证**
  - 配置项从定义到消费必须全链路追踪，**禁止**只注入到中间层就认为生效
  - **判断信号**：`config.yaml` 新增字段 → Config 类有字段 → TaskConfig 注入 → 但 Worker/Module/方法参数中从未读取 `self.config.xxx` → 配置无效
  - **检查方法**：grep 每个配置项的字段名，确认从定义到最终消费点（URL 构建方法、SQL 查询、阈值比较）都有读取代码
  - **配置参数**：配置链路追踪检查清单在 `config.yaml` 的 `config_linkage_checks` 节点管理
  - **适用**：所有配置项（搜索参数、阈值、间隔、开关），尤其是新增配置项后
  - **不适用**：编译期常量、安全固定值（如 `path: "/"`）
  - **历史教训**：`search_sort_type` 和 `search_regions` 在 `startup.py` 注入到 TaskConfig，但 `worker.py` 和 `_search.py` 从未读取，`build_search_url` 也不支持这两个参数。用户在配置页设置了排序方式但搜索 URL 中从不包含 `&sortType=...` 参数
- 🆕v4.5【强制】**B-REVIEW-POST-WRITE-HOOK：写后钩子（Post-Write Hook）规范**
  - 所有"写主数据源 + 同步派生状态"的操作必须实现**显式写后钩子**——禁止依赖隐式回调、事件总线自动触发、定时器轮询
  - **判断信号**：派生状态（缓存 / 索引 / 内存模型）需要与主数据源保持一致，但代码中只在某个特定入口同步 → 其他写入路径遗漏
  - **修复模式**：
    - 在每个写入路径的成功分支（`if json_written: ...`）添加显式调用
    - 钩子函数应**幂等**：可重复调用而不会产生副作用
    - 钩子失败必须**仅记录日志不抛异常**：派生状态同步失败不能阻断主写入
    - 钩子逻辑应**重新读主数据源**而非用调用方传入的列表（避免过滤逻辑不一致）
  - **典型实现**：
    ```python
    if json_written:
        try:
            sync_cookie_layers_from_json()
        except Exception as e:
            logger.debug("写后钩子失败（不影响主流程）: %s", e)
    ```
  - **配置参数**：`post_write_hooks`（钩子函数名列表）、`write_entry_paths`（需要触发钩子的写入路径）在 `config.yaml` 的 `post_write_hooks` 节点管理
  - **适用**：所有"写后需要同步派生状态"的场景（Cookie 状态机、缓存失效、索引重建、计数器重置）
  - **不适用**：单写入入口且无派生状态、性能敏感场景（钩子开销不可接受）
  - **历史教训**：登录路径写 JSON 后没有任何钩子触发 `CookieRotator.sync_state_from_cookies()`，导致层状态永远停留在 `valid=False, updated_at=0.0`，`/cookies/layers` 显示三层全部失效
- 🆕v4.11【强制】**B-REVIEW-CONFIG-VALIDATION：配置项边界值校验**
  - 数值型配置项必须有边界值校验（min/max/non_zero/range），加载时主动校验，无效值用默认值并 `logger.warning` 告警，**禁止**直接使用未校验的数值导致运行时 ZeroDivisionError / ValueError
  - **核心机制**（审查时必须理解）：
    - `config.yaml` 数值字段可能被用户设置为 0、负数、极大值等非法值
    - 代码用 `interval / N` 或 `count * factor` 等算术运算时，0 会触发 ZeroDivisionError，负数会触发 ValueError
    - 配置加载时主动校验 + 默认值兜底是防御性编程的最佳实践
  - **判断信号**：
    - `config.yaml` 新增数值字段 + 代码用该字段做算术运算 → 必须校验除数非零、乘数有界
    - 代码含 `interval = config.get("xxx_interval", 60)` 后直接 `await asyncio.sleep(interval / 2)` → 必须校验 interval > 0
    - 代码含 `max_retries = config.get("max_retries", 3)` 后直接 `for _ in range(max_retries)` → max_retries 应为非负整数
  - **修复模式**：
    ```python
    # ✅ 加载时校验 + 默认值兜底
    interval = config.get("ai_suggestion_interval", 60)
    if not isinstance(interval, (int, float)) or interval <= 0:
        logger.warning("ai_suggestion_interval 配置无效（{}），使用默认值 60", interval)
        interval = 60
    # 使用 interval 做算术运算前已校验非零
    await asyncio.sleep(interval / 2)

    # ❌ 错误：未校验直接使用
    # interval = config.get("ai_suggestion_interval", 60)
    # await asyncio.sleep(interval / 2)  # interval=0 时 ZeroDivisionError
    ```
  - **配置参数**：`config_validation.rules`（每条规则含 `field`/`min`/`max`/`non_zero`/`regex`/`default`）、`config_validation.on_invalid`（默认 `warn_and_fallback`，可选 `raise`）在 `config.yaml` 的 `config_validation` 节点管理
  - **适用**：所有数值型配置项（间隔时间/阈值/并发数/超时/重试次数）；字符串枚举值（用 regex 校验）
  - **不适用**：布尔型配置项（无需校验范围）；纯展示型字符串（如标题）；编译期常量
  - **历史教训**：`ai_suggestion_interval=0` 未校验直接用于 `asyncio.sleep(interval / 2)` 导致 ZeroDivisionError，任务循环崩溃
- 🆕v4.12【强制】**B-REVIEW-DOM-FALLBACK-CHAIN：DOM 多层兜底链模式**
  - SPA/动态页面数据提取必须在主路径失败时按序尝试多层兜底（DOM 选择器 → `meta[property='og:title']` → `document.title`），**禁止**单一选择器失败即整体失败
  - **核心机制**（审查时必须理解）：
    - SPA 站点 DOM 结构会随版本迭代变化，单一选择器脆弱性高
    - `og:meta` 与 `document.title` 由网站框架稳定维护，是可靠的兜底层
    - 兜底链按"语义忠实度"递减排序，最终兜底必须保证非空（如 `document.title` 兜底但应标注 `title_source: 'fallback'`）
  - **判断信号**：
    - 代码含 `page.locator(...).text_content()` / `await page.querySelector(...)` 后直接返回结果 → 检查是否有兜底
    - 选择器失败抛 `TimeoutError`/`ElementNotFound` 但代码未捕获 → 违规
    - 数据提取函数返回值可能为 `None` 但调用方未做空值检查 → 违规
  - **修复模式**：
    ```python
    # ✅ 多层兜底链
    title = await page.locator(SELECTORS["title"]).text_content()
    if not title:
        # DOM 主路径失败 → og:meta 兜底
        title = await page.get_attribute("meta[property='og:title']", "content")
    if not title:
        # og:meta 失败 → document.title 最终兜底（保证非空）
        title = await page.title()
        title_source = "fallback"
    else:
        title_source = "primary"
    ```
    ```python
    # ❌ 错误：单一选择器，无兜底
    title = await page.locator(".item-title").text_content()
    return {"title": title}  # 选择器失效即整体失败
    ```
  - **配置参数**：`dom_fallback_chain.strategies`（兜底层级列表，如 `["dom", "og_meta", "document_title"]`）、`dom_fallback_chain.dom_selectors`（主路径选择器集合，业务场景为 key）、`dom_fallback_chain.meta_selectors`（og:meta 选择器集合）、`dom_fallback_chain.final_fallback`（最终兜底函数名）、`dom_fallback_chain.dump_on_all_fail`（全部失败时是否触发 dump，与 `failure_dump` 联动）在 `config.yaml` 的 `dom_fallback_chain` 节点管理（与 v4.3 B-REVIEW-FALLBACK-CHAIN 的"多方案降级"语义不同，本节点专指 DOM 提取兜底）
  - **适用**：SPA 数据采集（标题/价格/卖家/图片）、动态渲染页面的关键字段提取、可能因站点改版失效的 DOM 选择器
  - **不适用**：静态 JSON API（结构稳定，单一解析即可）、写入操作（无兜底语义）、用户输入校验
  - **历史教训**：官方采集仅用 `.item-title` 单一选择器，闲鱼页面改版后选择器失效直接返回 `title=None`，下游字段覆盖逻辑被 None 覆盖历史有效值，最终用户看到"采集失败"
- 🆕v4.12【强制】**B-REVIEW-FAILURE-DUMP：失败诊断 dump 机制**
  - 关键选择器失败或数据提取异常时必须自动 dump `page.content()` 到本地文件，便于离线复现；dump 操作不得阻塞主流程（异步执行或 fire-and-forget）
  - **核心机制**（审查时必须理解）：
    - 采集类 bug 在生产环境难以复现（依赖具体页面状态/Cookie/时序）
    - dump 完整 HTML 后可在本地用 `page.set_content()` 重放调试
    - dump 文件需按场景归档，含时间戳与业务 ID 便于关联日志
  - **判断信号**：
    - 代码含 `except ElementNotFound`/`except TimeoutError` 但未触发 dump → 违规
    - dump 操作用 `await` 阻塞主流程 → 违规（应 fire-and-forget 或 `asyncio.create_task`）
    - dump 文件名不含时间戳或场景标识 → 排查困难，违规
    - dump 文件未做大小限制/数量限制 → 可能撑爆磁盘
  - **修复模式**：
    ```python
    # ✅ 异步 dump，不阻塞主流程
    async def _dump_html(scenario: str, biz_id: str, page: Page) -> None:
        try:
            content = await page.content()
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = Path("logs") / f"{scenario}_{biz_id}_{ts}.html"
            # 异步写入（任何失败仅 debug 日志，不影响主流程）
            await asyncio.to_thread(path.write_text, content, encoding="utf-8")
        except Exception as e:
            logger.debug("dump 失败（不影响主流程）: {}", e)

    # 主流程：选择器失败时 fire-and-forget dump
    try:
        title = await page.locator(SELECTORS["title"]).text_content()
    except (ElementNotFound, TimeoutError):
        asyncio.create_task(_dump_html("official_collect", task_id, page))
        title = None  # 走兜底链
    ```
    ```python
    # ❌ 错误：阻塞主流程 + 无场景标识
    try:
        title = await page.locator(".title").text_content()
    except Exception:
        Path("logs/dump.html").write_text(await page.content())  # 阻塞 + 覆盖
    ```
  - **配置参数**：`failure_dump.enabled`（总开关）、`failure_dump.dump_dir`（输出目录，默认 `logs/`）、`failure_dump.filename_pattern`（文件名模板，如 `{scenario}_{id}_{timestamp}.html`）、`failure_dump.max_file_size_mb`（单文件大小上限）、`failure_dump.max_files_per_scenario`（每场景保留文件数上限）、`failure_dump.scenarios`（启用 dump 的场景列表）、`failure_dump.sensitive_patterns`（需脱敏的正则列表，如 cookie/token）在 `config.yaml` 的 `failure_dump` 节点管理
  - **适用**：所有 Playwright/浏览器自动化采集、DOM 选择器失败时、关键路径异常时
  - **不适用**：纯 API 调用（已有完整请求/响应日志）、本地纯函数（无外部状态）、单测/集成测试场景
  - **历史教训**：官方采集失败时仅日志记录"选择器失效"，无法定位是页面改版还是 Cookie 失效，需用户手动复现；引入 dump 后离线分析即可定位
- 🆕v4.12【强制】**B-REVIEW-TIMING-INSTRUMENTATION：关键路径计时埋点**
  - 关键路径操作（`page.goto`/`wait_for_selector`/HTTP 调用/DB 查询）必须用 `time.perf_counter()` 计时并按阈值告警，**禁止**仅用 `logger.info("开始")`/`logger.info("结束")` 文本日志（难以聚合分析）
  - **核心机制**（审查时必须理解）：
    - 性能问题排查依赖结构化 timing 数据，文本日志需正则解析不可靠
    - `time.perf_counter()` 比 `time.time()` 精度高（纳秒级），不受系统时间回拨影响
    - 超阈值告警便于运维主动发现性能退化，而非用户报障
  - **判断信号**：
    - 代码含 `await page.goto(...)` / `await page.wait_for_selector(...)` / `await http_client.get(...)` 但前后无 `perf_counter()` 计时 → 违规
    - 用 `time.time()` 计时（精度低）→ 建议改为 `perf_counter()`
    - 计时结果仅 `logger.debug` 不做阈值判断 → 超阈值无法告警
    - 计时埋点用 try/finally 包裹但 finally 内引用变量未前置初始化 → 与 B-REVIEW-TRY-FINALLY-INIT 联动违规
  - **修复模式**：
    ```python
    # ✅ perf_counter + 阈值告警
    t0 = time.perf_counter()
    try:
        await page.goto(url, wait_until="domcontentloaded")
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        threshold = config.get("timing.goto_threshold_ms", 5000)
        if elapsed_ms > threshold:
            logger.warning("page.goto 慢: {:.0f}ms > {}ms, url={}", elapsed_ms, threshold, url)
        else:
            logger.debug("page.goto: {:.0f}ms, url={}", elapsed_ms, url)
    ```
    ```python
    # ❌ 错误：无计时 / 文本日志无法聚合
    logger.info("开始 goto")
    await page.goto(url)
    logger.info("结束 goto")
    ```
  - **配置参数**：`timing_instrumentation.thresholds_ms`（按操作类型配置阈值，如 `{goto: 5000, wait_for_selector: 3000, http_request: 2000, db_query: 1000}`）、`timing_instrumentation.log_level_normal`（正常日志级别，默认 `DEBUG`）、`timing_instrumentation.log_level_slow`（超阈值日志级别，默认 `WARNING`）、`timing_instrumentation.enabled_scenarios`（启用计时的场景列表）、`timing_instrumentation.timer_function`（计时函数名，默认 `time.perf_counter`）在 `config.yaml` 的 `timing_instrumentation` 节点管理
  - **适用**：所有 `page.goto`/`wait_for_selector` 操作、HTTP 外部调用、DB 查询、关键 async 任务链
  - **不适用**：单测/集成测试（无需生产级埋点）、纯内存计算（耗时极短）、本地开发调试（临时 print 即可）
  - **历史教训**：官方采集偶发慢，但仅 `logger.info` 无结构化 timing，排查时无法区分是 `page.goto` 慢还是 `wait_for_selector` 慢，需用户多次复现抓包
- 🆕v4.12【强制】**B-REVIEW-PRECHECK-AND-PARALLEL：凭证前置校验与并行采集**
  - 高开销操作（浏览器启动/网络采集）前必须前置校验 Cookie 凭证有效性（`expires` 字段），过期凭证直接返回明确状态码（如 440），**禁止**启动浏览器后才在采集过程中失败浪费资源；独立 IO 任务必须用 `asyncio.gather(*tasks, return_exceptions=True)` 并行执行
  - **核心机制**（审查时必须理解）：
    - 浏览器启动耗时数秒，Cookie 已过期时启动浏览器纯属资源浪费
    - `cookie.expires=-1` 表示 session cookie（浏览器关闭即失效，无法预判），跳过预校验
    - `cookie.expires>0` 且 `< now()` 表示持久 Cookie 已过期，可直接返回 440
    - `asyncio.gather` 默认任一异常即全部取消，`return_exceptions=True` 让独立任务互不影响
  - **判断信号**：
    - 代码含 `async with async_playwright() as p:` 启动浏览器但前置未校验 Cookie → 违规
    - 代码用 `for task in tasks: await task` 串行执行独立 IO → 应改为 `asyncio.gather`
    - `asyncio.gather` 未传 `return_exceptions=True` 且未做异常隔离 → 任一失败导致全部取消
    - Cookie 校验仅检查 `name in cookies` 不检查 `expires` → 违规
  - **修复模式**：
    ```python
    # ✅ 凭证前置校验
    def _cookie_expired(cookie: dict) -> bool:
        expires = cookie.get("expires", -1)
        if expires == -1:
            return False  # session cookie，无法预判
        return expires < time.time()

    identity_cookies = [c for c in cookies if c["name"] in IDENTITY_COOKIE_NAMES]
    expired = [c for c in identity_cookies if _cookie_expired(c)]
    if expired:
        # 前置返回 440，不启动浏览器
        raise HTTPException(status_code=440, detail="Cookie 已过期，请重新登录")

    # ✅ 独立 IO 并行采集
    results = await asyncio.gather(
        *[collect_task(item) for item in items],
        return_exceptions=True,  # 任一失败不影响其他
    )
    for item, result in zip(items, results):
        if isinstance(result, Exception):
            logger.warning("采集失败 item={}: {}", item.id, result)
        else:
            process(result)
    ```
    ```python
    # ❌ 错误：启动浏览器后才发现 Cookie 过期 + 串行采集
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        # 浏览器已启动，此时校验 Cookie 已浪费资源
        if not cookies_valid():
            raise HTTPException(440, "Cookie 过期")
        # 串行采集独立任务
        for item in items:
            await collect_task(item)
    ```
  - **配置参数**：`precheck_parallel.credential_check_enabled`（总开关）、`precheck_parallel.identity_cookies_whitelist`（身份 Cookie 名称列表，如 `["_m_h5_tk", "cookie17", "unb"]`）、`precheck_parallel.skip_session_cookies`（是否跳过 session cookie，默认 `true`）、`precheck_parallel.expiry_status_code`（过期时返回状态码，默认 `440`）、`precheck_parallel.parallel_gather_return_exceptions`（gather 是否传 return_exceptions，默认 `true`）、`precheck_parallel.parallel_gather_max_concurrency`（最大并发数，0 表示不限制）、`precheck_parallel.parallel_scenarios`（启用并行的场景列表，如 `["official_collect", "seller_fetch"]`）在 `config.yaml` 的 `precheck_parallel` 节点管理
  - **适用**：所有需要 Cookie 凭证的外部采集、独立 IO 任务并行（多商品采集/多卖家查询/多 API 调用）、浏览器自动化前置校验
  - **不适用**：有依赖关系的串行任务（B 依赖 A 的结果）、纯本地计算、Cookie 仅用于读操作且无成本（如读本地 JSON）
  - **历史教训**：官方采集启动 Chromium 后才发现 `_m_h5_tk` 过期，浪费 3-5 秒浏览器启动时间；多个商品串行采集 10 个商品耗时 30 秒，并行后降至 5 秒

- 🆕v4.20【强制】**B-REVIEW-VERSION-SOURCE-SINGLE：元数据源单源管理规范**
  - 构建期元数据（版本号/构建时间/git_sha/构建主机）必须有唯一源头文件（如 `__init__.py: __version__ = "x.y.z"`），自动生成文件（如 `_build_info.py`）由专门脚本（如 `scripts/build_info.py`）维护；多端点读取同一元数据必须封装 `_safe_xxx()` 三层 try/except 回退辅助函数（源头 → 生成文件 → 默认值 `'unknown'`）；export_config / about / health 等多端点响应中涉及版本号字段必须调用辅助函数而非硬编码占位符
  - **核心机制**（审查时必须理解）：
    - 构建期元数据必须有唯一源头（Single Source of Truth），自动生成文件是派生产物，多端点响应是消费方
    - 端点命名相似不等于语义对齐：`/api/config/version` 名称含 "version" 但实际返回 `len(backups)`，应在端点命名或 docstring 中明确语义
    - 多端点读取同一元数据若各自直接 `from xianyu_hunter import __version__`，遇到 `__version__` 缺失或 `_build_info.py` 未生成时各自兜底，会导致响应不一致
    - 三层回退保证可用性：源头 import 成功 → 生成文件兜底 → 默认值 `'unknown'` 兜底（禁止使用 `"1.0"` / `"0.0.0"` / `"unknown version"` 等占位符，会误导前端与用户）
    - 占位符必须列为禁止值并通过自动化扫描检查，因为它们看起来像合法版本号，比 `'unknown'` 更具误导性
  - **判断信号**：
    - `grep "from xianyu_hunter import __version__" src/` 出现 ≥ 2 处 → 必须封装辅助函数
    - `grep -E "'(1\.0|0\.0\.0|unknown version)'" src/xianyu_hunter/web/routes/` → 必须改为调用辅助函数
    - `grep -E '"version":\s*"[^"]+"' src/xianyu_hunter/web/routes/` 命中硬编码字符串 → 视为违规（应调用 `_safe_app_version()`）
    - 端点 `/api/config/version` 实际返回 `len(backups)` 而非版本号 → 视为命名误导，应在 docstring 中明确"返回备份数"
    - `grep "_safe_app_version\|_safe_build_info" src/xianyu_hunter/web/routes/` 无匹配 → 视为违规
  - **修复模式**：
    ```python
    # ❌ 错误：硬编码占位符 + 多端点各自直接 import
    # api_config.py
    @router.get("/api/config/export")
    async def export_config(...):
        return {"version": "1.0", ...}  # 占位符，会误导前端

    # api_about.py
    @router.get("/api/about")
    async def about(...):
        from xianyu_hunter import __version__  # 直接 import，遇缺失无兜底
        return {"version": __version__, ...}

    # ✅ 正确：封装 _safe_xxx() 辅助函数 + 多端点复用
    # api_config.py
    def _safe_app_version() -> str:
        """读取系统真实版本号，失败时回退为 'unknown'。"""
        try:
            from xianyu_hunter import __version__
            if __version__:
                return __version__
        except Exception:
            pass
        try:
            from xianyu_hunter import _build_info
            return getattr(_build_info, "__version__", "unknown") or "unknown"
        except Exception:
            return "unknown"

    @router.get("/api/config/export", response_model=ExportConfigResponse)
    async def export_config(...):
        return {"version": _safe_app_version(), ...}  # 调用辅助函数

    # api_about.py 复用同一辅助函数（或在共享模块中定义）
    @router.get("/api/about")
    async def about(...):
        return {"version": _safe_app_version(), ...}
    ```
  - **配置参数**：`version_source_management` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `single_source_file`（默认 `"src/xianyu_hunter/__init__.py"`，元数据唯一源头文件路径）
    - `source_field_name`（默认 `"__version__"`，源头字段名）
    - `auto_generated_file`（默认 `"src/xianyu_hunter/_build_info.py"`，自动生成文件路径）
    - `auto_generator_script`（默认 `"scripts/build_info.py"`，自动生成脚本路径）
    - `safe_helper_function`（默认 `"_safe_app_version"`，多端点读取必须封装的辅助函数名）
    - `fallback_default`（默认 `"unknown"`，三层回退的最终默认值，禁止使用占位符）
    - `forbidden_placeholders`（默认 `["1.0", "0.0.0", "unknown version"]`，禁止作为版本号回退值的占位符列表）
    - `forbidden_version_endpoints`（默认 `["/api/config/version"]`，命名含 "version" 但实际返回业务计数的端点列表，应在 docstring 中明确语义）
    - `helper_threshold`（默认 `2`，grep `from xxx import __version__` 出现 ≥ N 处时必须封装辅助函数）
  - **适用**：版本号/构建时间/git_sha/构建主机等构建期元数据的读取与响应；多端点读取同一元数据的场景；`/api/about` / `/api/config/export` / `/api/health` / `/api/version` 等元数据相关端点
  - **不适用**：业务数据计数（如备份数/任务数/商品数）；临时调试变量；跨服务边界元数据（应通过专门 API 同步）；核心依赖版本（如 FastAPI/SQLAlchemy 版本，由 requirements.txt 管理）；Pydantic 模型字段（由后端类型系统管理）
  - **历史教训**：版本管理菜单持续显示 "V10"。根因链路：①前端 `VersionManager.tsx` 调用 `configApi.getVersion()` 拉取 `/api/config/version`，但该端点实际返回 `len(backups)`，受 `BACKUP_KEEP=10` 上限影响永远卡在 10；②后端 `export_config` 中残留占位符 `"version": "1.0"`，前端拿到虚假版本号。修复：后端 `_safe_app_version()` 辅助函数替代占位符（三层回退：`__version__` → `_build_info.__version__` → `'unknown'`），前端改用 `aboutApi.get()` 调 `/api/about` 拿真实版本号。教训：端点命名相似不等于语义对齐，多端点读取同一元数据必须封装辅助函数避免占位符

- 🆕v4.22【强制】**B-REVIEW-STARTUP-HOOK-COMPLETENESS：启动钩子完整性检查规范**
  - 维度：9 异步与调度器
  - 检查项：所有依赖 `container.browser` 或 `container.collector` 的组件必须在 `startup.py` 的 `_on_startup` 中有对应的 `start_xxx()` 启动钩子
  - 强制要求：
    1. 启动钩子必须用 `if _should_start_scheduler():` 包裹，避免无浏览器时错误启动
    2. 启动钩子必须放在依赖的调度器之后（确保浏览器/collector 已就绪）
    3. 启动失败必须 try/except 兜底，仅记录 warning 不阻断主服务启动
    4. 验证方法：`grep -rn "container.browser\|container.collector" src/xianyu_hunter/` 找所有依赖点，逐个检查 startup.py 是否有对应 start_xxx 调用
  - 配置节点：`startup_hook_completeness`（required_components / dependency_check_fields / startup_order）
  - 适用场景：含 BackgroundScheduler/asyncio.Task 后台任务的项目，特别是依赖浏览器/外部资源的组件
  - 不适用场景：纯 Web 项目无后台任务；单进程无外部依赖项目；纯前端组件
  - 实战案例：反爬会话管理（LoginOrchestrator + TokenRenewer）依赖 container.browser 进行 Cookie 续期，但 startup.py 缺失启动钩子，导致服务重启后 TokenRenewer 不自动启动，用户必须手动点击「启动会话」按钮

- 🆕v4.22【强制】**B-REVIEW-TASK-HISTORY-THREE-LAYER-PROTECTION：任务历史持久化三层状态保护规范**
  - 维度：9 异步与调度器
  - 检查项：写入 running 状态的代码路径必须有对应 finalize 调用更新为终态
  - 强制要求：
    1. 必须覆盖三条路径：正常结束（finally 块）、future.result 超时（except 块调用 _finalize_history_on_exception）、协程异常（except 块）
    2. 错误消息累积必须设上限（FIFO 切片丢弃最旧，默认 50 条），避免 JSON 字段无限膨胀
    3. 状态语义必须区分：circuit_broken（连续失败熔断）→ failed，_stop_flag（用户主动停止）→ cancelled，正常完成 → completed
    4. 业务自增 task_id 不能依赖内存初始化（见 B-REVIEW-COUNTER-DB-MAX-INIT）
  - 配置节点：`task_history_protection`（required_states / exception_fallback_required / max_error_messages / counter_init_query）
  - 适用场景：长时间运行任务的执行历史记录（批量采集/数据同步/批处理/定时任务）
  - 不适用场景：短时间 HTTP 请求；不需要历史记录的任务；一次性脚本任务
  - 实战案例：批量采集任务 _run_batch_async 开始时插入 running 状态，若 future.result(timeout=3600) 超时，历史记录会残留 running 状态，需 _finalize_history_on_exception 兜底

- 🆕v4.22【强制】**B-REVIEW-COUNTER-DB-MAX-INIT：业务自增计数器 DB MAX 初始化规范**
  - 维度：6 SQLite 优化
  - 检查项：业务自增 ID（task_id/batch_id/run_id）必须从 DB MAX 初始化，不能依赖内存初始化
  - 强制要求：
    1. 调度器 `__init__` 时必须从 DB `SELECT MAX(id)` 初始化计数器
    2. 查询失败时回退到 0 + `logger.warning`，不阻断启动
    3. `trigger_now()` 调用时 `+= 1` 后立即返回给前端，不等待 DB 写入
    4. 为什么不用 DB 自增主键：业务自增 ID 需在调度器内存中维护以便 trigger_now 立即返回给前端
  - 配置节点：`counter_db_max_init`（counter_fields / init_query_template / fallback_value / warning_on_failure）
  - 适用场景：业务自增 ID 跨进程重启不能重置的场景
  - 不适用场景：DB 自增主键（autoincrement）；UUID/GUID；临时计数器（无需跨进程持久化）
  - 实战案例：批量采集 task_id 是业务字段（progress 表/历史表/日志均引用），若进程重启后内存计数器从 0 开始，会与历史记录的 task_id 冲突

- 🆕v4.22【强制】**B-REVIEW-APSCHEDULER-INTERVAL-FIRST-RUN：APScheduler interval 触发器首次执行控制规范**
  - 维度：9 异步与调度器
  - 检查项：APScheduler interval 触发器必须明确首次执行时间
  - 强制要求：
    1. 使用 interval 触发器时必须明确首次执行时间
    2. 需要启动后快速反馈的场景，必须设置 `next_run_time` 参数
    3. `next_run_time` 不建议设为 `datetime.now()`（立即执行），应留 5-10 秒延迟给初始化依赖就绪
    4. 日志必须输出间隔 + 首次执行时间：`logger.info("调度器已启动，间隔 %d 分钟，首次执行于 %s", interval, next_run)`
    5. 为什么不设为立即执行：给浏览器/collector 初始化留时间，避免首次采集因浏览器未就绪而连续失败触发熔断
  - 配置节点：`apscheduler_interval_first_run`（default_next_run_delay_seconds / needs_immediate_execution / log_format）
  - 适用场景：APScheduler interval 触发器且需要启动后快速反馈的场景（批量采集/数据同步/定时巡检）
  - 不适用场景：cron 触发器（有明确时间点）；首次执行依赖外部状态需手动触发的场景；纯 Web 请求无定时任务
  - 实战案例：批量采集调度器 interval=30分钟，默认首次执行在启动后30分钟，用户感知不到调度器在工作，误以为功能不生效。加 next_run_time=now+10s 后10秒首次执行

### 15. 进程管理

- 【强制】Web 进程必须 `with_browser=False` 模式（节省内存）
- 【强制】WebView2/Playwright 子进程必须用 `CREATE_NEW_CONSOLE` 标志（**禁止** `CREATE_NO_WINDOW`，防止 GUI 窗口闪退）
- 【强制】WebView2 子进程**不**重定向 stdout/stderr 到 `DEVNULL`（保留调试输出）
- 【强制】WebView2 `webview.start()` 必须设置：
  - `private_mode=False`
  - 唯一 `storage_path`（格式 `webview_data_{pid}_{timestamp}`，持久化 Cookie 防冲突）
- 🆕v4.3【强制】**B-REVIEW-CHROME-136-ADAPTATION：Chrome 136+ 限制适配模式**
  - Chrome/Edge 136+ 版本使用 `--remote-debugging-port` 时必须配合 `--user-data-dir` 指向非标准目录
  - **判断信号**：Chrome/Edge 136+ 版本 + 使用 `--remote-debugging-port` 参数 + 浏览器自动化场景
  - **修复模式**：启动命令同时包含 `--remote-debugging-port=9222` + `--user-data-dir=<unique-path>` → 路径不指向默认 `User Data` 目录
  - **配置参数**：`user_data_dir` 路径模板（`browser_data/debug_{timestamp}`）、`debug_port` 在 `config.yaml` 的 `chrome_debug` 节点管理（不硬编码）
  - **适用**：Chrome/Edge 浏览器自动化、CDP 调试、Playwright `connect_over_cdp`
  - **不适用**：其他浏览器（Firefox/Safari）、旧版 Chrome（< 136）、不使用 remote-debugging 的场景
  - **历史教训**：Chrome 136+ 安全限制要求 `--user-data-dir` 指向非标准目录，否则 `--remote-debugging-port` 不生效；使用独立 `Debug` profile 避免污染用户主 profile

### 16. Composition Root 🆕v2.0

- 【强制】`container.py` 持有全部单例依赖的 `@dataclass Container`
- 【强制】`build_default_container()` 是唯一工厂函数
- 【强制】`PriorityBrowserLock` 用 high/low 优先级（避免低优先级任务长期阻塞）
- 【强制】`ChatbotOrchestrator` 子容器用 `_build_chatbot_container()` **深拷贝**配置，避免污染全局单例
- 【强制】`chromadb` 缺失时返回 `None`（不抛异常）
- 【推荐】Evaluator 构造**不**接受 `thresholds/weights/keywords` 覆盖参数（避免永久覆盖导致用户配置不生效）
- 🆕v4.3【强制】**B-REVIEW-MULTI-PROFILE-DISCOVERY：多配置文件发现模式**
  - 发现多个同名配置/profile 时，优先从结构化元数据（如 `Local State` JSON 的 `profile.info_cache`）读取，失败则 fallback 到目录扫描
  - **判断信号**：需发现多个同名配置/profile + 存在结构化索引文件 + 用户可能使用非默认 profile
  - **修复模式**：读取 `Local State` → 解析 `profile.info_cache` 字典 → 失败则扫描 `User Data/` 子目录匹配 `Profile *` 模式 → 按优先级排序（有目标 cookie → Default → 名称）
  - **配置参数**：主数据源路径、fallback 扫描目录、profile 目录正则模式、优先级排序规则在 `config.yaml` 的 `profile_discovery` 节点管理（不硬编码）
  - **适用**：浏览器多 profile 发现、多账户隔离环境、多环境配置加载
  - **不适用**：单一配置场景、严格顺序访问场景、路径已知且唯一的场景
  - **历史教训**：用户实际使用 `Profile 1` 而非 `Default`，原实现只读取 `Default` 导致 cookie 导入失败

### 17. 智能客服专项 🆕v2.0

- 【强制】`ChatbotOrchestrator` 不持有请求级状态（如当前 `session_id`），保证可被多会话共享
- 【强制】per-session Lock 用 `_locks_guard` 保护 `_session_locks` 字典的并发访问
- 【强制】异常不向外抛出，统一转为 `SSEEvent(ERROR)` 或 `SSEEvent(ESCALATE)`
- 【强制】`asyncio.CancelledError` 向上传播以触发资源清理
- 【强制】`KBManager._scan_and_chunk` 必须排除：
  - `web/static/`、`web/templates/`、`__pycache__/`、`node_modules/`、`.git/`、`dist/`、`build/`
- 【强制】仅索引 `.md`、`.py`、`.jsonl`、`.txt` 文件（白名单）
  - **历史教训**：前端构建产物（packed .js/.css）会产生数千无用 chunk，向量化时间从 5 分钟膨胀到 30+ 分钟
- 【强制】工具注册：`BaseTool` 子类注册到 `tool_registry.py`
- 🆕v4.0【强制】**字段覆盖策略（数据合并）**：数据采集合并时按字段语义分类覆盖策略，**不能一刀切**
  - 基本信息字段（title/url/region/brand/seller_id/publish_time）：新值非空则覆盖
  - 数值类字段（price/want_cnt/view_cnt）：新值 > 0 才覆盖（防止 0 覆盖有效值）
  - 状态类字段（is_sold）：始终覆盖（状态时效性最高）
  - 标识类字段（seller_nick）：只填缺失（稳定性高）
  - **适用**：数据采集合并、缓存更新；**不适用**：审计日志
  - **历史教训**：`_enrich_eval_with_item` 用"只填缺失"策略导致旧价格 905 不被新价格 888 覆盖

### 18. Web 层规范

- 【强制】FastAPI 应用用 `create_app()` 工厂
- 【强制】中间件 LIFO 注册顺序：RequestId → BearerAuth → 路由
- 【强制】SPA catch-all 处理 `/app/{full_path:path}`，返回 `index.html`
- 【强制】`APIRouter(prefix="/api/<域>", tags=["<域>"])`
- 【强制】Swagger UI 自定义 `_SWAGGER_UI_HTML` 注入导航栏
- 【推荐】启动钩子 `startup.py` 管理 `startup`/`shutdown` 事件
- 🆕v4.6【强制】**B-REVIEW-DATA-FLOW-TRACE：字段为空 5 点追踪**
  - 用户反馈"某字段为空 / 显示异常 / 数据丢失"类问题时，必须按 **DB schema → Repo 查询过滤 → API 注入 → 前端 types → render 取值** 5 点逐层追踪根因，**禁止**只看前端代码或只查后端代码
  - **判断信号**：用户反馈"字段为空 / 数据丢失 / 显示异常" → 必须从 DB 原始数据开始逐层验证，每层都打印中间值
  - **追踪流程**：
    1. **DB schema**：用 `sqlite3` / DB 客户端查询原始数据，确认数据是否存在
    2. **Repo 查询过滤**：检查 Repo 层查询是否有 `WHERE` / `if status == 'failed': continue` 等过滤逻辑
    3. **API 注入**：检查 API 路由层是否正确调用 Repo 并将数据注入响应（参数是否正确传递，如 `include_failed=True`）
    4. **前端 types**：检查 `frontend/src/api/types.ts` 中类型定义是否包含该字段
    5. **render 取值**：检查前端组件是否正确从响应中取值并渲染
  - **关键约束**：
    - 5 点必须**逐层验证**，不能跳过任何一层
    - 每层验证必须**打印中间值**（如 `print(order_map)` / `console.log(record.order)`），不能凭推断
    - 找到根因后必须**修复根因**而非绕过（如 Repo 过滤逻辑错误应修 Repo，而非 API 层重新查询）
    - 修复后必须**回归测试**覆盖该场景
  - **配置参数**：`trace_nodes`（5 个节点的标识）、`required_fields`（必检字段列表）、`null_value_check`（是否检查 null 值）在 `config.yaml` 的 `data_flow_trace` 节点管理
  - **适用**：所有"字段为空 / 显示异常 / 数据丢失"类根因定位，尤其是涉及前后端多层的字段
  - **不适用**：UI 样式问题（如颜色/布局错误）、纯前端计算字段（如 `total = price * quantity`）、权限不足导致字段隐藏
  - **历史教训**：评估明细页"订单"列显示 "—"，根因是 `repo_orders.list_orders_by_item_ids` 无条件 `if status == 'failed': continue`，但 API 层评估明细调用未传 `include_failed=True`。数据库中实际有 3 条 failed 订单，但全部被 Repo 层过滤。修复后 API 返回 `order_status=failed`（之前为 `null`）
- 🆕v4.9【强制】**B-REVIEW-DUAL-LINK-CONSISTENCY：双链路前置条件一致性**
  - 同一业务目标有 ≥2 条执行链路时（如 Worker 调度链路 + Live 实时链路都到达「下单」），共用前置条件必须提取为独立函数，两条链路调用同一函数，**禁止**各自实现
  - **判断信号**：同一业务目标（如「下单」「采集」「通知」）有 ≥2 条执行链路（如 Worker 调度 + Live 实时 + API 手动 + CLI 命令）→ 必须提取共用前置条件
  - **修复模式**：
    ```python
    # ✅ 提取共用前置条件为独立函数
    def _build_price_strategy(task: Task) -> PriceStrategy:
        """构建价格策略，Worker 和 Live 链路共用"""
        return PriceStrategy(
            max_price=task.price_config.get("max_price") or 0,
            min_price=task.price_config.get("min_price") or 0,
        )

    # Worker 链路
    class TaskWorker:
        async def run_once(self):
            strategy = _build_price_strategy(self.task)
            if not strategy.is_acceptable(item): return  # 共用过滤

    # Live 链路
    async def _trigger_live_auto_buy(item, task):
        strategy = _build_price_strategy(task)
        if not strategy.is_acceptable(item): return  # 共用过滤
    ```
  - **关键约束**：
    - 共用前置条件（价格过滤/分数校验/库存检查）提取为独立函数（如 `_build_price_strategy(task) -> PriceStrategy`）
    - 两条链路必须调用同一函数，**禁止**各自实现相似逻辑
    - 前置条件过滤仅阻止「执行动作」（如抢单），不阻止「评估写库」（评估结果仍写入 DB 供后续分析）
    - 修改后必须 `grep` 验证两条链路确实调用同一函数，禁止遗漏
    - 必须新增测试覆盖两条链路的前置条件一致性
  - **配置参数**：`target_entities`（业务目标列表，如 `["buy", "collect", "notify"]`）、`shared_predicate_patterns`（共用前置条件函数命名模式，如 `_build_*_strategy`）、`verify_callers`（是否启用 grep 验证，默认 `true`）在 `config.yaml` 的 `dual_link_consistency` 节点管理
  - **适用**：同一业务目标有多个触发入口（如 Worker 调度 + Live 实时 + API 手动 + CLI 命令）
  - **不适用**：单一入口的业务（如只有 API 触发）；链路间业务逻辑本就不同（如 Worker 是异步批量，Live 是同步单条）——此时应抽取「共同部分」为函数，「差异部分」各自处理
  - **历史教训**：Worker 链路调用 `PriceStrategy.is_acceptable()` 做价格过滤，Live 链路只看分数达标不做价格过滤，导致两条链路行为不一致——Worker 链路过滤掉的高价商品在 Live 链路被下单。修复后提取 `_build_live_price_strategy` 共用函数，两链路调用同一函数

### 19. API 设计规范

- 【强制】HTTP 动词语义化（GET=查询、POST=创建、PUT=替换、PATCH=局部更新、DELETE=删除）
- 【禁止】GET 请求引发状态变更（如激活、删除）
- 【强制】集合接口必须支持分页（默认 20 条上限）
- 【强制】URL 使用名词复数（`/tasks` 而非 `/getTasks`）
- 【强制】响应使用 DTO/Pydantic 模型，禁止直接返回 ORM 对象（避免字段泄漏与懒加载 N+1）
- 【强制】错误响应：HTTP 状态码区分 4xx（客户端）/5xx（服务端），禁止 200+error 体
- 【推荐】API 版本化：路径包含 `/v1/`、`/v2/`
- 【强制】向后兼容：同版本内禁止删除接口/字段、变更字段类型、增加必填参数
- 🆕v4.0【强制】**幂等性设计**：资源创建接口（如 `session/start`、`task/create`）必须幂等
  - 重复调用返回当前状态 + `already_active` 标志，不重复创建资源
  - **适用**：资源创建接口、网络重试；**不适用**：纯查询接口（天然幂等）、计数器递增
- 🆕v4.0【强制】**搜索接口标准化**：实时搜索接口统一参数命名与响应结构
  - 统一参数：`keyword/q, page/offset, page_size/limit`
  - 统一响应：`{ items, total, page, page_size }`
  - **适用**：实时搜索（用户输入 + 防抖 + 流式/分页）；**不适用**：主键精确查询
- 🆕v4.10【强制】**B-REVIEW-FILTER-VISIBILITY：过滤结果可见性（后端侧）**
  - 后端过滤链（keyword/price/publish_days/自定义过滤）必须输出完整的 `filter_summary` 结构，**禁止**只返回 final_total 不暴露过滤过程
  - **核心机制**（审查时必须理解）：
    - 过滤链每阶段（keyword/price/publish_days）必须记录跳过数量（`*_skipped`）和详情（`filtered_out`）
    - `filtered_out` 项必须含 `link_type`/`link_key`/`display`/`filter_reason`/`filter_detail`，便于前端按原因分组展示
    - `filtered_out` 数量必须有上限避免响应过大（默认 50，参数在 `config.yaml` 的 `filter_summary.max_filtered_out_items` 节点管理）
    - 前端若只拿到 `final_total` 不展示过滤过程，用户无法判断"无结果"是搜索无果还是被过滤掉
  - **判断信号**：
    - 后端代码含 `if not match_keyword: continue` / `if price > max: continue` 等过滤逻辑但未记录到 `filter_summary` → 视为违规
    - 接口响应只含 `items`/`total` 不含 `filter_summary` → 视为违规
    - `filter_summary` 缺少 `filtered_out` 详情列表 → 视为违规
    - `filtered_out` 项缺少 `filter_reason`/`filter_detail` → 视为违规
  - **修复模式**：
    ```python
    # ✅ filter_summary 完整结构 + 三处过滤记录
    _filter_summary = {
        "raw": 0, "formatted": 0,
        "keyword_skipped": 0, "price_skipped": 0, "publish_days_skipped": 0,
        "final_total": 0, "final_items": 0, "final_sellers": 0,
        "filtered_out": [],  # 限制 max_filtered_out_items 条
    }
    # 读取上限（配置驱动，不硬编码）
    max_filtered_out_items = config.get("filter_summary", {}).get("max_filtered_out_items", 50)

    # keyword 过滤
    if not _match_keyword(r, kw):
        _filter_summary["keyword_skipped"] += 1
        if len(_filter_summary["filtered_out"]) < max_filtered_out_items:
            _filter_summary["filtered_out"].append({
                "link_type": r.get("link_type"), "link_key": r.get("link_key"),
                "display": r.get("display"),
                "filter_reason": "keyword", "filter_detail": f"未匹配关键词 {kw}",
            })
        continue

    # price 过滤
    if price > max_price:
        _filter_summary["price_skipped"] += 1
        if len(_filter_summary["filtered_out"]) < max_filtered_out_items:
            _filter_summary["filtered_out"].append({
                "link_type": r.get("link_type"), "link_key": r.get("link_key"),
                "display": r.get("display"),
                "filter_reason": "price", "filter_detail": f"价格 {price} 超过上限 {max_price}",
            })
        continue

    # publish_days 过滤
    try:
        pub_dt = _dt.fromisoformat(str(pub).replace("Z", "+00:00"))
        if (_now - pub_dt).days > max_publish_days:
            _filter_summary["publish_days_skipped"] += 1
            if len(_filter_summary["filtered_out"]) < max_filtered_out_items:
                _filter_summary["filtered_out"].append({
                    "link_type": r.get("link_type"), "link_key": r.get("link_key"),
                    "display": r.get("display"),
                    "filter_reason": "publish_days",
                    "filter_detail": f"发布 {(_now - pub_dt).days} 天，超过上限 {max_publish_days} 天",
                })
            continue
    except (ValueError, TypeError):
        pass
    ```
  - **配置参数**：`filter_summary.max_filtered_out_items`（默认 `50`，filtered_out 列表长度上限）、`filter_summary.required_fields`（默认 `["raw", "formatted", "keyword_skipped", "price_skipped", "publish_days_skipped", "final_total", "final_items", "final_sellers", "filtered_out"]`，filter_summary 必须包含的字段）、`filter_summary.filtered_out_required_fields`（默认 `["link_type", "link_key", "display", "filter_reason", "filter_detail"]`，filtered_out 项必须包含的字段）、`filter_summary.filter_reason_values`（默认 `["keyword", "price", "publish_days"]`，filter_reason 允许的值列表）在 `config.yaml` 的 `filter_summary` 节点管理
  - **诊断流程**（出现"实时搜索无结果但不知原因"类问题时执行）：
    1. `grep "filter_summary" src/xianyu_hunter/web/routes/` 扫描接口响应组装代码
    2. 检查过滤链每阶段是否记录 `*_skipped` 计数和 `filtered_out` 详情
    3. 验证 `filtered_out` 项是否含完整的 5 个字段（link_type/link_key/display/filter_reason/filter_detail）
    4. 验证 `max_filtered_out_items` 是否从 config 读取（禁止硬编码 50）
    5. 验证接口响应是否包含 `filter_summary` 字段
  - **适用**：所有含过滤链路的查询接口（实时搜索/历史查询/列表过滤）；多阶段过滤的场景；前端需要展示过滤详情的场景
  - **不适用**：无过滤的纯 CRUD 接口；单一阶段过滤且过滤原因明显（如权限过滤）；内部 API 不暴露给前端
  - **历史教训**：实时搜索接口 `final_total=0`（keyword 过滤 32 + price 过滤 27 = 0 最终）但响应只含 `items: []`，前端只显示"实时查询完成"，用户无法判断是搜索无结果还是被过滤掉，反复调整搜索词无果。修复后添加 `filtered_out` 跟踪 + `filter_summary` 完整结构
- 🆕v4.25【强制】**B-REVIEW-110: EXCLUDE-UNSET-CHECK：API 更新接口 exclude_unset 检查**
  - PATCH/PUT 接口必须使用 Pydantic v2 的 `model_dump(exclude_unset=True)` 区分"未传 / 传 null / 传值"三态语义，**禁止**手动循环跳过 None 值
  - **核心机制**（审查时必须理解）：
    - `exclude_unset=True` 只导出客户端**显式传入**的字段（区分"未传"与"传 null"）
    - `exclude_none=True` 会误删"传 null 表示清除"的语义，**禁止**用于更新接口
    - 手动 `for k, v in data.items(): if v is not None: ...` 会丢失"传 null 清除覆盖"的能力，且无法区分"未传"与"传 null"
  - **判断信号**：
    - PATCH/PUT 路由中出现 `for k, v in body.dict().items(): if v is not None: setattr(obj, k, v)` → 视为违规
    - 使用 `body.dict(exclude_none=True)` 而非 `model_dump(exclude_unset=True)` → 视为违规
    - 使用 `body.model_dump(exclude_none=True)` 用于更新逻辑 → 视为违规
    - 直接 `body.dict()` 不带任何 exclude 参数用于更新 → 视为违规
  - **修复模式**：
    ```python
    # ✅ 使用 exclude_unset=True 区分三态
    @router.patch("/tasks/{task_id}")
    async def update_task(task_id: str, body: TaskUpdate):
        update_data = body.model_dump(exclude_unset=True)  # 只含客户端显式传入的字段
        # 未传的字段不在 update_data 中 → 不更新
        # 传 null 的字段在 update_data 中且值为 None → 更新为 None（表示清除）
        # 传值的字段在 update_data 中且有值 → 更新为新值
        await repo.update_task(task_id, update_data)

    # ❌ 违规：手动循环跳过 None，丢失"传 null 清除"语义
    @router.patch("/tasks/{task_id}")
    async def update_task(task_id: str, body: TaskUpdate):
        data = body.dict()
        for k, v in data.items():
            if v is not None:  # 无法区分"未传"与"传 null"
                setattr(obj, k, v)
    ```
  - **关键约束**：
    - 所有 Pydantic BaseModel 的 PATCH/PUT 更新接口必须用 `model_dump(exclude_unset=True)`
    - **禁止**用 `exclude_none=True` 替代 `exclude_unset=True`（前者会误删"传 null 清除"语义）
    - **禁止**手动循环 `if v is not None` 跳过 None
    - 配合 B-REVIEW-111 NOT-NULL-NONE-DEFENSE：NOT NULL 字段传 null 时需防御性 pop
    - Pydantic v1 用 `.dict(exclude_unset=True)`，v2 用 `.model_dump(exclude_unset=True)`
  - **配置参数**：`api_update_semantics.require_exclude_unset`（默认 `true`，强制 PATCH/PUT 用 exclude_unset）、`api_update_semantics.forbid_exclude_none`（默认 `true`，禁止用 exclude_none 替代）、`api_update_semantics.forbid_manual_loop`（默认 `true`，禁止手动循环跳过 None）在 `config.yaml` 的 `api_update_semantics` 节点管理
  - **适用**：所有 PATCH/PUT 接口的可选字段更新；任务级配置覆盖功能；支持"传 null 清除覆盖"语义的接口
  - **不适用**：POST 创建接口（创建时字段未传走默认值）；GET 查询接口（无更新语义）；内部数据转换（非用户输入）
  - **历史教训**：任务级配置覆盖功能中，前端传 `{"price_config": null}` 表示清除该任务的 price_config 覆盖，但后端用 `for k, v in data.items(): if v is not None: setattr(obj, k, v)` 跳过了 None，导致"清除覆盖"操作无效，用户删除的任务级配置实际仍生效。修复后改用 `model_dump(exclude_unset=True)` + 配合 NOT NULL 字段防御性 pop

### 20. 测试建议

审查时建议对以下场景补充单元测试（`tests/test_*.py`）：

- null 输入 / 空集合 / 边界值（0、-1、最大值）
- 异常分支（服务调用失败、参数校验不通过）
- 并发场景（共享缓存、计数器、懒加载初始化）
- 事务边界（跨服务调用、回滚条件）
- SSE 重连（lastEventId 持久化恢复）
- 幂等迁移（重复执行不报错）
- 🆕v4.3【强制】**B-REVIEW-WINDOWS-TEST-MOCK：Windows 测试环境 Mock 模式**
  - 测试代码中 Windows 环境变量（`LOCALAPPDATA`/`APPDATA`/`USERPROFILE`）必须用 `tmp_path` 正确 mock，路径结构需与实现一致
  - **判断信号**：测试涉及 Windows 文件系统路径 + 使用环境变量 + 实现依赖 `Path(LOCALAPPDATA)` 等构造路径
  - **修复模式**：`monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))` → 测试 fixture 创建 `tmp_path / "Microsoft" / "Edge" / "User Data"` 完整路径结构 → 与实现路径完全对齐
  - **配置参数**：测试 fixture 路径模板、环境变量映射在 `tests/conftest.py` 管理
  - **适用**：Windows 文件系统路径测试、浏览器 profile 发现测试、配置文件加载测试
  - **不适用**：Linux/Mac 路径测试、不涉及环境变量的路径测试、纯函数测试
  - **历史教训**：测试代码创建 `tmp_path / "Edge" / "User Data"` 但实现用 `Path(LOCALAPPDATA) / "Microsoft" / "Edge" / "User Data"`，路径结构不一致导致测试失败
- 🆕v4.3【强制】**B-REVIEW-PLUGIN-DEPENDENCY-PRECHECK：第三方插件依赖预检模式**
  - 使用 pytest 插件（如 `pytest-timeout`）前必须验证项目已安装，避免运行时报错；插件依赖列表需在 `pyproject.toml` 显式声明
  - **判断信号**：使用 pytest 命令行参数（如 `--timeout`）+ 依赖第三方插件 + 未在 `pyproject.toml` 声明
  - **修复模式**：`pyproject.toml` `[tool.pytest.ini_options]` 显式声明 `addopts` + `requirements-dev.txt` 列出插件依赖 → 运行前用 `pytest --version` + 插件检查脚本验证
  - **配置参数**：插件依赖列表在 `pyproject.toml` 管理，预检脚本在 `scripts/check-deps.ps1`
  - **适用**：所有 pytest 插件依赖（`pytest-timeout`/`pytest-cov`/`pytest-asyncio`）、tox/nox 多环境测试
  - **不适用**：pytest 内置功能（无需预检）、CI 环境固定镜像（依赖明确）
  - **历史教训**：使用 `pytest --timeout=60` 报错 `unrecognized arguments`，项目未安装 `pytest-timeout` 插件；移除 `--timeout` 标志后通过，但应预检插件依赖
- 🆕v4.10【强制】**B-REVIEW-PYTEST-MODULE-REIMPORT：pytest 模块重复 import 隔离**
  - pytest 在 `sys.modules` 中可能以 `test_xxx`（无包前缀）和 `tests.test_xxx`（带包前缀）两种名字持有同一测试文件的不同模块对象，conftest.py patch 模块属性时**禁止**硬编码模块名列表，必须遍历 `sys.modules` 找所有持目标属性的模块全部 patch
  - **核心机制**（审查时必须理解）：
    - pytest 以两种名字 import 同一测试文件，生成两个不同模块对象在 `sys.modules` 中
    - conftest.py 若只 patch 其中一个模块对象，被测代码读取的是另一个未 patch 的模块对象，导致隔离失败
    - `__import__("a.b")` 返回顶层包 `a` 而非子模块 `a.b`，必须用 `importlib.import_module` 正确返回子模块
  - **判断信号**：
    - conftest.py 含 `for name in ["xxx", "yyy"]: monkeypatch.setattr(sys.modules[name], ...)` 硬编码模块名列表 → 视为违规
    - conftest.py 含 `__import__("a.b")` 且后续操作期望得到子模块 → 视为违规
    - 测试用例 `import tests.test_xxx` 后修改模块属性，但被测代码 `from test_xxx import YYY` 读取的是另一份模块对象 → 典型症状
    - 生产文件含测试数据（如 `data/cookies.json` 含 `test_fixture_` 前缀）→ 隔离失败症状
  - **修复模式**：
    ```python
    # ✅ 正确：遍历 sys.modules 找所有持目标属性的模块
    import sys
    TARGET_ATTR = "_COOKIE_JSON"

    def patch_all_modules_with_cookie(tmp_path):
        patched = []
        for mod in sys.modules.values():
            if mod is None:
                continue
            if hasattr(mod, TARGET_ATTR):
                # patch 到 tmp_path 隔离生产数据
                setattr(mod, TARGET_ATTR, str(tmp_path / "cookies.json"))
                patched.append(mod.__name__)
        assert patched, f"未找到持 {TARGET_ATTR} 属性的模块"
        return patched

    # ✅ 正确：importlib.import_module 替代 __import__
    import importlib
    mod = importlib.import_module("xianyu_hunter.modules.cookie_rotator")

    # ❌ 错误：硬编码模块名列表
    for name in ["cookie_rotator", "api_tasks", "auth_middleware"]:
        monkeypatch.setattr(sys.modules[name], "_COOKIE_JSON", ...)

    # ❌ 错误：__import__ 返回顶层包
    mod = __import__("xianyu_hunter.modules.cookie_rotator")  # 返回 xianyu_hunter 而非 cookie_rotator
    ```
  - **配置参数**：`pytest_isolation.target_attr_pattern`（默认 `_COOKIE_JSON`，支持正则）、`pytest_isolation.module_name_prefixes`（默认 `[]` 表示全扫，可选限制如 `["xianyu_hunter", "tests"]`）、`pytest_isolation.use_importlib`（默认 `true`，强制使用 `importlib.import_module`）、`pytest_isolation.forbid_hardcoded_module_list`（默认 `true`，禁止硬编码模块名列表）在 `config.yaml` 的 `pytest_isolation` 节点管理
  - **诊断流程**（出现"测试数据污染生产文件"类问题时执行）：
    1. `grep "for name in" tests/conftest.py` 扫描硬编码模块名列表
    2. `grep "__import__" tests/` 扫描 `__import__` 使用
    3. 检查 conftest.py 是否遍历 `sys.modules` 动态识别持目标属性的模块
    4. 验证 patch 后 `assert hasattr(mod, TARGET_ATTR)` 确认 patch 生效
    5. 跨模块共享配置路径的测试必须用此模式
  - **适用**：pytest conftest.py 全局 fixture patch 模块属性；多模块共享同一配置文件路径的场景；任何需要 patch 跨模块共享状态的测试
  - **不适用**：单模块测试（直接 monkeypatch 即可）；非 pytest 测试框架；patch 对象属性（非模块属性）
  - **历史教训**：`conftest.py` 硬编码 `[cookie_rotator]` 列表 patch `_COOKIE_JSON`，但 pytest 以 `test_cookie_rotator` 和 `tests.test_cookie_rotator` 两种名字持有同一文件的两个模块对象，patch 只命中其中一个，导致生产 `data/cookies.json` 被测试数据污染。修复后改为遍历 `sys.modules` 找所有持 `_COOKIE_JSON` 属性的模块全部 patch
- 🆕v4.10【强制】**B-REVIEW-TEST-FIXTURE-ISOLATION：测试 fixture 生产隔离与数据污染应急**
  - conftest.py 必须 patch 生产路径（如 `data/cookies.json`、`*.db`）到 `tmp_path`，fixture 数据需带可识别特征（如 `test_fixture_` 前缀），数据污染应急必须按 5 步流程执行
  - **核心机制**（审查时必须理解）：
    - fixture 若直接读写生产路径，测试数据会污染生产文件，导致服务异常
    - 测试数据带可识别特征（前缀/后缀）便于污染后定位与清理
    - 数据污染应急 5 步流程确保污染被发现后系统化处理，避免遗漏
  - **判断信号**：
    - conftest.py 含 `open("data/cookies.json", "w")` / `open("data/*.db", "w")` 直接写生产路径 → 视为违规
    - 测试数据无前缀/后缀特征（如 `user_id = "abc123"` 而非 `user_id = "test_fixture_abc123"`）→ 视为违规
    - 生产文件含测试数据（如 `data/cookies.json` 含 `test_fixture_` 前缀的 cookie）→ 典型污染症状
    - conftest.py 用模块级全局变量持有测试数据路径 → 视为违规（应用 fixture scope）
  - **修复模式**：
    ```python
    # ✅ 正确：tmp_path 隔离 + 可识别特征 + patch 验证
    @pytest.fixture(scope="session")
    def isolated_cookie_path(tmp_path_factory):
        cookie_path = tmp_path_factory.mktemp("data") / "cookies.json"
        # 写入带 test_fixture_ 前缀的测试数据（便于污染后定位）
        cookie_path.write_text('{"token": "test_fixture_token_xxx"}')
        # patch 所有持 _COOKIE_JSON 属性的模块（参考 B-REVIEW-PYTEST-MODULE-REIMPORT）
        patched = []
        for mod in sys.modules.values():
            if mod is not None and hasattr(mod, "_COOKIE_JSON"):
                setattr(mod, "_COOKIE_JSON", str(cookie_path))
                patched.append(mod.__name__)
        assert patched, "未找到持 _COOKIE_JSON 属性的模块"
        # 验证生产路径未被写入
        assert not os.path.exists("data/cookies.json"), "生产路径被写入！"
        return cookie_path

    # 数据污染应急流程（按 config.yaml 的 test_isolation.pollution_recovery_steps 执行）
    # 1. 停止服务：xianyu-automation-startserver stop
    # 2. 删除污染文件：rm data/cookies.json
    # 3. 修复 conftest：参考 B-REVIEW-PYTEST-MODULE-REIMPORT 遍历 sys.modules patch
    # 4. 重跑测试：pytest
    # 5. 通知用户：告知污染文件清单
    ```
  - **配置参数**：`test_isolation.production_path_patterns`（默认 `["data/cookies.json", "data/*.db", "data/*.json"]`，生产路径模式列表）、`test_isolation.test_data_markers`（默认 `["test_fixture_", "__test__"]`，测试数据可识别特征列表）、`test_isolation.pollution_recovery_steps`（默认 5 步流程列表：停止服务/删除污染文件/修复 conftest/重跑测试/通知用户）、`test_isolation.fixture_scope_default`（默认 `function`，fixture 默认作用域）、`test_isolation.assert_no_production_write`（默认 `true`，加载 fixture 后断言生产路径未写入）在 `config.yaml` 的 `test_isolation` 节点管理
  - **诊断流程**（出现"生产文件含测试数据"类问题时执行）：
    1. 检查生产文件是否含 `test_data_markers` 中的特征前缀/后缀
    2. `grep "open\\(['\\\"]data/" tests/` 扫描测试代码直接写生产路径
    3. 检查 conftest.py 是否用 `tmp_path` / `tmp_path_factory` 隔离
    4. 检查 fixture 数据是否带可识别特征
    5. 按 `pollution_recovery_steps` 执行应急流程
  - **适用**：所有 pytest fixture 涉及文件 IO 的场景；conftest.py 全局 fixture；CI/CD 测试环境
  - **不适用**：纯内存测试（无文件 IO）；mock 替代真实文件的测试；一次性脚本测试
  - **历史教训**：`conftest.py` 未隔离 `data/cookies.json`，测试用例直接写入生产文件，导致生产 cookie 被测试数据污染（含 `test_fixture_` 前缀的 token）。应急流程：停止服务 → 删除 `data/cookies.json` → 修复 conftest 遍历 sys.modules patch → 重跑 pytest 全绿 → 通知用户重新初始化 cookie

### 21. 架构与分层

- 【强制】包组织策略明确：按功能分模块（`modules/collector/`、`modules/notifier/`、`modules/buyer/` 等）
- 【禁止】跨层调用：路由直接访问 ORM、领域包引入框架注解
- 【强制】领域包不引入框架注解（不依赖 SQLAlchemy/FastAPI）
- 【禁止】循环依赖 A → B → C → A
- 【推荐】`util/`、`common/` 包不得无限增长，应归属对应功能模块
- 【强制】DTO 在边界处转换，领域对象不出边界
- 【推荐】新增功能应仅影响对应功能包，不应触碰多个包

### 22. 闲鱼项目规范 🆕v2.0

- 【强制】依赖单向 `web → modules → infra → domain`
- 【强制】`container.py` 是唯一 Composition Root
- 【强制】仓储用 Mixin 组合模式（`TasksMixin`、`ItemsMixin` 等），聚合为 `Repository`
- 【强制】Typer CLI 入口（`__main__.py`）支持 `run/add/list/status/pause/resume/stop/login/web/config_show` 命令
- 【强制】Web 进程通过 `os.environ["XH_WITH_SCHEDULER"] = "1"` 控制调度器模式
- 【强制】目录不可移动：`src/xianyu_hunter/`、`config/`、`data/`、`browser-data/`、`frontend/`、`tests/`（代码硬编码引用）
- 【强制】根目录严格遵循 14 个核心文件规范（见 `docs/standards/directory-structure.md §7.1`）
- 【强制】Docker 三阶段构建：`frontend`（node:20-alpine）→ `builder`（python:3.12-slim）→ `runtime`（python:3.12-slim）
- 【强制】runtime 阶段不包含构建工具，减小镜像体积
- 【推荐】`pyproject.toml` 不使用 `dynamic = ["version"]`（About API 需运行时反射）

### 23. Git 操作规范 🆕v2.1

- 【强制】合并前检查 `.git/index.lock` 是否残留（失败 git 操作可能留下锁文件）
- 【强制】产物文件（`.scannerwork/`、`__pycache__/`、`node_modules/`、`dist/`）不应被 git track
- 【强制】发现产物被 track 时用 `git rm -r --cached <dir>` 清理（不删除工作区文件）
- 【强制】`.git` 目录被安全策略保护时，用 Python `os.remove()` 或 git 命令本身操作
- 【强制】冲突解决保留更新版本（如 `await` 异步版本优于同步版本）
- 【强制】cherry-pick 后的合并冲突：main 已有 cherry-pick 改动，feat 有原始改动，保留 main 版本
- 【推荐】stash 前确认无大目录被 modified，避免权限问题导致 stash 失败
- 【推荐】PowerShell 中 `stash@{0}` 必须加引号：`git stash pop 'stash@{0}'`

### 24. 跨字段一致性与硬编码属性禁用 🆕v4.2

- 【强制】**B-REVIEW-CROSS-FIELD：跨字段一致性校验**：同一 dataclass/dict 中语义相关联的字段对必须在构造时校验一致性，禁止出现矛盾组合
  - 检查清单（字段对在 `config.yaml` 的 `cross_field_consistency_checks` 节点管理）：
    - `gpu_vendor` + `gpu_renderer`：厂商与渲染器型号必须匹配（如 `Google Inc. (AMD)` 配 AMD 渲染器）
    - `valid` + `written_count`：层状态标记 valid=True 时写入数量必须 > 0（或 writer 未设置）
    - `layer` + `cookies`：Cookie 分层定义与实际归属必须一致（如 `_m_h5_tk` 属于 session 层而非 identity 层）
  - **判断信号**：同一数据结构中存在语义关联字段对
  - **修复模式**：`__post_init__` / 构造函数 / 工厂函数中校验，不一致时抛 `ValueError`
  - **不适用**：独立无关联字段、运行时动态拼装的临时对象

- 【强制】**B-REVIEW-NO-HARDCODED-PROPS：硬编码属性禁用**：写入外部系统（浏览器 Cookie、HTTP 响应头、数据库列）的属性必须根据数据语义动态设置，禁止硬编码固定值
  - 检查清单（属性映射在 `config.yaml` 的 `hardcoded_property_mappings` 节点管理）：
    - Cookie 属性：`httpOnly`/`secure`/`sameSite` 根据 Cookie 名称和层级动态判断（identity 层 Cookie 是 JS 可读的，不能强制 `httpOnly:True`）
    - HTTP 响应头：`Content-Type`/`Cache-Control` 根据响应内容类型设置
  - **判断信号**：批量构造对象时所有实例使用相同的属性固定值（如所有 Cookie 都设 `httpOnly:True`）
  - **修复模式**：属性值从数据语义派生或通过配置文件管理属性映射
  - **不适用**：项目固定常量（如域名、路径前缀 `path: "/"`）、安全必需的固定值

- 【强制】**B-REVIEW-NO-CROSS-THREAD-ASYNC：跨线程异步调用禁用**：禁止在同步函数中用 `asyncio.run_coroutine_threadsafe()` + `future.result()` 等待异步结果（存在死锁风险）
  - **判断信号**：`run_coroutine_threadsafe` + `future.result(timeout=N)` 组合出现
  - **修复模式**：改为纯异步路径（`async def`）或 fire-and-forget（`asyncio.ensure_future` 不等待结果）+ 同步兜底（如 JSON 持久化）
  - **适用**：FastAPI 同步路由调用 Playwright 等异步 API
  - **不适用**：测试代码中的显式事件循环控制

- 【强制】**B-REVIEW-TRY-FINALLY-INIT：try/finally 变量初始化**：`try/finally` 块中 `finally` 引用的变量必须在 `try` 之前初始化为 `None`
  - **判断信号**：`try:` 块内赋值的变量在 `finally:` 中被引用
  - **修复模式**：`page = None; try: page = await ... finally: if page: await page.close()`

- 【强制】**B-REVIEW-CROSS-COMPONENT-STATE：跨组件状态同步**：多个组件对同一概念做判断时，状态变更必须双向同步
  - 检查清单（跨组件状态概念在 `config.yaml` 的 `cross_component_state_concepts` 节点管理）：
    - "会话有效性"：health_checker（Cookie 存在性）+ worker（API 响应 RGV587_ERROR）+ orchestrator（cookie_rotator 层状态）
  - **判断信号**：两个以上组件各自独立判断"会话有效性"/"登录状态"等同一概念
  - **修复模式**：状态变更方调用 `invalidate_layer()` 通知其他组件；查询方额外检查其他组件的状态标志

- 【强制】**B-REVIEW-ERROR-HINT-ROUTABLE：错误提示端点可操作性**：面向用户的错误提示中引用的 API 端点/方法名必须实际存在
  - **判断信号**：错误信息中包含 `/api/xxx` 或方法名引用
  - **修复模式**：提示中只引用已实现的端点；改为可操作的 UI 指引（如"请调用 POST /api/anticrawl/initialize 重新初始化"）

- 🆕v4.16【强制】**B-REVIEW-FIELD-NORMALIZE-DOC：字段归一化文档化**
  - **判断信号**：后端有 `_normalize` / `_unify` / `_merge` / `_flatten` 等归一化函数 + 前端 types.ts 声明旧字段名 + 前端通过动态 key 取值
  - **强制规则**：后端归一化字段时必须在前端 types.ts 对应字段声明中加注释 `// 后端已归一化，前端消费 X 字段`；保留旧字段名必须标 optional 并注释 `// 仅作兼容保留，后端不返回`；前端禁止通过动态 key 取归一化字段必须直接用归一化后字段名
  - **反例**：后端 `_normalize_deep_result` 将 signals/damages/inconsistencies 归并到 signals，但前端 types.ts 仍声明 damages/inconsistencies，前端通过 `check[signalKey]` 取值永远 undefined
  - **正例**：后端归一化后在前端 types.ts 注释 `// 后端已归一化，前端消费 signals 字段`，前端直接用 `check.signals`
  - **配置参数**：`field_normalize_doc` 节点（enabled / require_doc_comment / detect_dynamic_key_access / fallback_to_legacy_field）
  - **适用场景**：后端有归一化函数 + 前端通过动态 key 取值
  - **不适用场景**：后端直接返回原始响应无转换；前端类型声明与后端 pydantic 模型一一对应

### 25. 状态管理与日志治理 🆕v4.8

- 【强制】**B-REVIEW-STATE-FLAG-PRECHECK：状态标志前置检查完整性**：检测到异常状态（会话失效/Cookie 过期/服务降级/限流）后是否设置状态标志；后续操作入口是否用 `getattr(self, "flag", False)` 检查标志提前返回
  - 检查清单（参数在 `config.yaml` 的 `state_flag_precheck` 节点管理）：
    - `state_flag_names`：状态标志名列表（如 `last_session_invalid` / `degraded_mode` / `cookie_expired`）
    - `require_reset_mechanism`：默认 true，要求必须有重置机制（grep `flag = False` 确认重置点）
  - **判断信号**：代码含 `self.last_session_invalid = True` / `self.degraded_mode = True` 等状态标志设置 → 必须检查后续操作入口是否有前置检查
  - **修复模式**：在操作入口增加 `if getattr(self, "flag", False): return None`；必须有重置机制（grep `flag = False` 确认重置点）；调用方能处理 None 返回值
  - **适用**：会话失效、Cookie 过期、服务降级、限流、依赖不可用
  - **不适用**：一次性错误（单条请求失败）、无恢复机制的场景、高频变化状态
  - **历史教训**：`_detail.py` 检测到 Cookie 失效（首页标题）后设置 `last_session_invalid = True`，但 `detail()` 方法未检查标志，导致 300+ WARNING 日志刷屏

- 【强制】**B-REVIEW-LOG-DOWNGRADE-STABILITY：日志降级判断稳定性**：已知业务场景的错误日志降级时，判断字符串是否提取为模块级常量；常量是否注释标明文案来源；未知错误是否保持 WARNING/ERROR 级别
  - 检查清单（参数在 `config.yaml` 的 `log_downgrade` 节点管理）：
    - `downgrade_rules`：降级规则列表，每条含 `match_pattern` / `target_level` / `detail_marker` / `source_comment`
  - **判断信号**：代码含 `logger.log(log_level, ...)` 动态日志级别 → 必须检查判断条件是否用魔法字符串
  - **修复模式**：将魔法字符串提取为模块级常量（如 `_COOKIE_EXPIRED_DETAIL_MARKER = "Failed to collect item detail"`），注释标明文案来源
  - **适用**：已知业务异常日志治理（Cookie 失效 502、重试中 WARNING）、外部依赖偶发失败
  - **不适用**：未知错误、安全相关错误（不应降级）、首次出现的错误、需用户介入的错误
  - **历史教训**：`exception_handler.py` 用 `"Failed to collect item detail" in str(exc.detail)` 判断是否 Cookie 失效，字符串未提取为常量，文案变更时匹配会失败

- 【强制】**B-REVIEW-EDIT-VERIFY：修改生效验证（针对 AI 辅助开发）**：使用 Edit 工具修改文件后，是否立即用 Grep 或 Read 验证修改是否真正生效
  - **配置参数**：无（纯流程检查项）
  - **判断信号**：代码评审时发现修复代码引用的变量/函数不存在于文件中 → 修改可能未生效
  - **修复模式**：Edit 后立即 Grep 搜索新增代码的标志性标识符（变量名/函数名/常量名），无匹配则重新执行 Edit
  - **适用**：所有使用 Edit 工具的修改场景，尤其是批量修改多个文件时
  - **不适用**：Read/Write 工具（这些工具本身有返回验证）
  - **历史教训**：第一次调用 Edit 修改 `_detail.py` 和 `exception_handler.py` 后工具返回"修改成功"，但后续 Grep 检查发现修改未保存，导致评审了未修改的代码

### 26. 缓存/状态判定/Schema 演进规约 🆕v4.15

- 【强制】**B-REVIEW-CACHE-INVALIDATION：缓存失效传播完整性**：任何持久化层（JSON 文件 / SQLite / 外部配置）变更后，是否**显式调用**对应缓存对象的 `invalidate_cache()` 或等价方法；TTL 兜底不替代主动失效；跨进程变更是否主动通知主进程
  - 检查清单（参数在 `config.yaml` 的 `cache_invalidation` 节点管理）：
    - `enabled`：默认 `true`，强制启用显式失效
    - `ttl_grace_seconds`：默认 `0`，TTL 兜底秒数（0 即不依赖 TTL）
    - `fail_log_level`：默认 `warning`，同步钩子失败的日志级别
    - `cache_field_patterns`：缓存字段正则列表（如 `["_cache", "_cache_time", "_cached_.*"]`）
  - **判断信号**：类含 `_cache`/`_cache_time`/`_cached_*` 字段但无 `invalidate_cache()` 方法 → 必须补齐；写入主数据源的方法（`update_*`/`upsert_*`/`write_*`）未在写后调用同步钩子 → 必须补齐
  - **修复模式**：
    1. 识别共享状态：明确"输入字段"、"派生字段"、"持久化副本"三类
    2. 设计 invalidate 入口：每个缓存对象暴露 `invalidate_cache()` 方法
    3. 写入主路径后必调：所有写主数据源方法在写后**显式**调用 `invalidate_cache()`
    4. 失败降级：同步钩子失败仅 `logger.warning`，不抛异常阻塞主流程
  - **适用**：JSON 持久化层、跨进程 Cookie/状态同步、内存缓存与文件副本同步、登录态多进程写入
  - **不适用**：纯函数、纯计算缓存（如 LRU math 缓存）、无外部数据源同步的内部状态
  - **历史教训**：`CookieStore` 用 30 秒 TTL 兜底缓存，浏览器子进程登录后只更新子进程自己的缓存，主进程仍读到旧缓存，导致 3 个 Cookie 层显示失效（功能实际可用）

- 【强制】**B-REVIEW-STATE-DETECTION-BOOTSTRAP：状态判定需区分"未检测"与"已检测未失效"**：任何"功能信号"字段（`last_session_invalid`/`is_healthy`/`is_connected` 等）不能仅用布尔初始值（如 `False`）代表"未检测"——`False` 与"已检测无失效"语义混淆，会导致刚启动时误判为"功能正常"
  - 检查清单（参数在 `config.yaml` 的 `state_detection_bootstrap` 节点管理）：
    - `required_marker`：前置条件类型（`timestamp`/`counter`/`flag`，默认 `timestamp`）
    - `signal_layer_mapping`：信号到层范围映射（如 `collector_signal → [identity, session, tracking]`、`m5tk_signal → [session]`）
    - `unknown_signal_strategy`：默认 `set()`，未识别信号组合的处理策略
    - `boolean_field_default_pattern`：布尔字段默认值正则（默认 `False`）
  - **判断信号**：布尔字段默认值 `False` + 实际语义是"初始未检测" → 必须增加时间戳/计数器区分；强制恢复/兜底逻辑仅依赖布尔字段 → 必须加前置条件
  - **修复模式**：
    1. 增加"已检测"标记：`_last_m5tk_refresh > 0` / `use_count > 0` / `_has_run = True`
    2. 信号判定前置条件：`if has_searched and session_ok: signals.add(...)`
    3. 强制恢复需白名单：信号 1/2 只能恢复其能证明有效的层范围
    4. 防御性 else：未识别的信号组合不默认恢复所有层，写 `logger.warning` 后 `set()`
  - **适用**：跨进程/跨模块状态判定、Cookie 层状态自愈、容器健康检查、服务可用性兜底
  - **不适用**：纯客户端 UI 状态、单次函数返回值、无初始歧义的开关字段
  - **历史教训**：collector 刚启动还没搜索过任何商品时，`last_session_invalid=False` 被解读为"会话有效"，强制恢复所有 Cookie 层（包括实际已失效的 IDENTITY），导致用户看到"状态闪烁"（失效→恢复→再失效）

- 【强制】**B-REVIEW-MIGRATION-TRANSACTION：SQLite DDL 修改列约束必须用表重建 + 事务安全**：SQLite 不支持 `ALTER COLUMN`，任何修改列约束的操作（NOT NULL→nullable、类型变更）是否通过 `engine.begin()` 单事务 + 残留清理 + 数据复制 + 异常恢复模式；禁止分散 commit 或裸 ALTER
  - 检查清单（参数在 `config.yaml` 的 `migration_transaction` 节点管理）：
    - `require_single_transaction`：默认 `true`，DDL 必须单事务包裹
    - `cleanup_residual_table`：默认 `true`，迁移前 `DROP TABLE IF EXISTS {table}_old`
    - `recover_from_old`：默认 `true`，失败后从 `{table}_old` 恢复
    - `exception_log_level`：默认 `error`，DDL 失败日志级别
    - `unsafe_patterns`：禁用模式正则（如 `["ALTER TABLE.*MODIFY COLUMN", "ALTER TABLE.*ALTER COLUMN"]`）
  - **判断信号**：`_migrate_*` 函数含多个 `conn.commit()` → 拆分为单一事务；`ALTER TABLE ... MODIFY COLUMN` / `ALTER TABLE ... ALTER COLUMN` → SQLite 不支持，需改用表重建；DDL 操作未传 `conn` 给 `orm_table.create` → 必须改为传 `conn`
  - **修复模式**：
    ```python
    with engine.begin() as conn:
        conn.execute(sa_text(f"DROP TABLE IF EXISTS {table}_old"))
        conn.execute(sa_text(f"ALTER TABLE {table} RENAME TO {table}_old"))
        orm_table.create(conn, checkfirst=True)
        old_cols = {c[1] for c in conn.execute(sa_text(f"PRAGMA table_info({table}_old)")).all()}
        common_cols = [c for c in orm_table.columns if c.name in old_cols]
        col_list = ", ".join(f'"{c.name}"' for c in common_cols)
        conn.execute(sa_text(f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM {table}_old"))
        conn.execute(sa_text(f"DROP TABLE {table}_old"))
    ```
  - **适用**：SQLite 修改列约束、表重建、任何不可逆 DDL
  - **不适用**：PostgreSQL/MySQL（有原生 DDL 事务）、新增列（直接 `ADD COLUMN`）、纯查询/插入操作
  - **历史教训**：旧版 `_migrate_make_column_nullable` 用 3 个独立 commit 拆分布骤 1/2/3/4，步骤 2 或 3 失败时旧表已 RENAME 但新表未创建完成，tasks 表变空且 tasks_old 残留，下次启动时 RENAME 因目标已存在永久阻塞；新版改用 `engine.begin()` 单事务 + 残留清理 + 异常恢复，彻底解决该问题

### 27. 多路径数据源一致性与统计聚合校准 🆕v4.17

- 【强制】**B-REVIEW-MULTI-PATH-DATA-SOURCE：同 API 多查询数据源一致性**：同一端点内多处 `select` 查询若服务于同一响应指标，必须共用同一过滤条件；禁止主查询按 `task_id` 过滤、辅助查询全表扫描
  - 检查清单（参数在 `config.yaml` 的 `multi_path_data_source` 节点管理）：
    - `enabled`：默认 `true`
    - `scan_select_count_threshold`：默认 `2`，同一函数内 select 语句数 ≥ 此值时触发检查
    - `ignore_global_scope_queries`：默认 `true`，scope.mode=="all" 时允许辅助查询不过滤 task_id
  - **判断信号**：同一函数内出现 ≥2 个 `select(...)` 且主查询含 `where(task_id==)` 但辅助查询无此条件 → 必须检查辅助查询是否应同源过滤
  - **修复模式**：辅助查询补齐 `where(task_id==task_id)`；或提取公共过滤条件变量；时间对比基线查询必须与价格样本查询同源
  - **适用**：仪表盘统计 API（直方图/趋势/对比）、多查询拼装响应的端点
  - **不适用**：明确需要跨任务聚合的全局统计（scope.mode=="all"）、不同业务含义的同类字段
  - **历史教训**：`price_histogram.py` 的 `prices` 按 task_id 过滤，但 `ts_rows`（用于计算 yesterday/last7d/last30d 均价）全表扫描，导致选定任务时时间对比基线混入其它任务价格，"较7日变化"等表格指标完全失真

- 【强制】**B-REVIEW-STATISTICAL-INPUT-BOUNDARY：统计聚合输入边界校准**：统计/分桶/均价逻辑禁止直接用 `min(prices)`/`max(prices)` 作为范围，必须用百分位裁剪（P5/P95）+ 业务上下文范围融合
  - 检查清单（参数在 `config.yaml` 的 `statistical_input_boundary` 节点管理）：
    - `enabled`：默认 `true`
    - `lower_percentile`：默认 `0.05`（P5）
    - `upper_percentile`：默认 `0.95`（P95）
    - `min_sample_size`：默认 `5`，样本数 < 此值时跳过裁剪（小样本直接用 min/max）
    - `business_range_fields`：业务范围字段映射（如 `{"task": ["min_price", "max_price"]}`）
  - **判断信号**：代码含 `lo, hi = min(prices), max(prices)` 后接等宽分桶 → 必须检查是否有极端值防护；分桶范围未融合业务上下文（如任务定价范围）→ 必须补齐
  - **修复模式**：
    1. 计算 P5/P95 百分位（用线性插值分位数）
    2. 融合业务范围：`lo = min(P5, task_min_price)`, `hi = max(P95, task_max_price)`
    3. `lo = max(0, lo)`；若 `hi <= lo` 则 `hi = lo + 1`
    4. 首桶吸收 `p < lo+step` 的极端低价；尾桶吸收 `p >= lo+(N-1)*step` 的极端高价
    5. 验证 `sum(counts) == len(prices)`（总数守恒）
    6. summary 的 min/max 返回真实极值（非分桶边界）
  - **适用**：直方图分桶、均价计算、趋势对比、任何受极端值污染的聚合
  - **不适用**：需要精确极值的场景（如"最高价商品"列表）、小样本（<5 个数据点）
  - **历史教训**：`price_histogram.py` bins=20 模式用 `min(prices)=50, max(prices)=5000` 作为分桶范围，单个 5000 元极端值导致前 2 个桶装着大部分商品、其余 18 个桶全为 0；改用 P5/P95 裁剪 + 任务定价范围融合后，范围缩小 34%，分布可视化才有参考价值

- 【建议】**B-REVIEW-CONCURRENT-CHECK-ACT：并发 check-then-act 原子化**：并发场景下状态检查（冷却期/锁状态/计数器）必须在持锁状态下进行，禁止 check 后释放锁再 act
  - 检查清单（参数在 `config.yaml` 的 `concurrent_check_act` 节点管理）：
    - `enabled`：默认 `true`
    - `lock_types`：默认 `["asyncio.Lock", "threading.Lock"]`
    - `check_keywords`：默认 `["cooldown", "last_run", "count", "exists"]`
  - **判断信号**：`if self._xxx_ok():` 后接 `async with self._lock:` → check 在锁外，必须移入锁内
  - **修复模式**：将 check 移入 `async with lock:` 上下文内；act 后立即更新状态使后续并发 check 失败
  - **适用**：抢单触发、浏览器操作、定时任务并发
  - **不适用**：纯只读查询、单线程顺序执行
  - **历史教训**：`_trigger_live_auto_buy` 冷却期检查在 `browser_lock` 外，3 个并发协程都通过检查后依次抢锁执行，冷却期失效；修复后将 check 移入锁内

### 28. LLM 端点能力派发与共享工具函数 🆕v4.23

- 🆕v4.23【强制】**B-REVIEW-LLM-CAPABILITY-DISPATCH：能力驱动派发（capability-driven dispatch）**
  - 任何 LLM/多模态/function_call/json_mode 调用必须在**构造 payload 前**预检目标模型能力，禁止"能力-需求"不匹配的无脑发送（典型症状：调用纯文本模型时附带 `image_url` content block → 服务端 400 `unknown variant`）
  - **核心机制**（审查时必须理解）：
    - LLM endpoint 的 schema 由目标模型决定，纯文本模型不支持多模态内容块（image_url/audio_url），调用会被服务端拒绝
    - 能力预检 = 模型名（`settings.openai_vision_model` 等）→ 关键字白名单（vision/function_call/json_mode）→ bool
    - 预检失败时降级为"等价文本表达"（prompt 追加"图片 URL + 描述"），而非抛错
    - 关键字白名单与判断函数必须**共享**（见 B-REVIEW-SHARED-UTIL-CENTRALIZATION），禁止散落
  - **判断信号**：
    - 代码含 `chat(model="xxx", messages=[{"role": "user", "content": [{"type": "text", ...}, {"type": "image_url", ...}]}])` 但未先 `if is_vision_capable(model)` → 视为违规
    - `messages` 中拼接 `image_url` content block 但调用方未校验 vision_capable → 视为违规
    - payload 构造与模型能力校验解耦（一个函数构造 payload，另一个函数调用 LLM）→ 视为高风险
    - 关键字列表（`["vision", "gpt-4o", ...]`）直接出现在调用函数内而非 `import` 共享常量 → 视为违规
  - **修复模式**：
    ```python
    # ✅ 共享判断 + 预检 + 降级
    # api_ai.py（权威源）
    _VISION_CAPABLE_KEYWORDS: tuple[str, ...] = (
        "vision", "gpt-4o", "gpt-4-vision", "qvq", "qwen-vl",
        "glm-4v", "claude-3", "opus", "sonnet", "haiku",
    )

    def _is_vision_capable(model_name: str | None) -> bool:
        if not model_name:
            return False
        return any(kw in model_name.lower() for kw in _VISION_CAPABLE_KEYWORDS)

    # api_ai_deep.py（消费方）
    from xianyu_hunter.web.routes.api_ai import _is_vision_capable

    vision_capable = _is_vision_capable(settings.openai_vision_model)
    if not vision_capable:
        logger.warning("mode=downgrade reason=vision_missing model={}", settings.openai_vision_model)
        user_content = text + f"\n图片 URL: {image_url}（请参考文字描述分析）"
    else:
        user_content = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    ```
    ```python
    # ❌ 错误：无脑拼接 image_url + 关键字白名单散落
    user_content = [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": image_url}},  # 模型不支持 vision 就 400
    ]
    ```
  - **配置参数**：`llm_capability_keywords.vision_keywords`（默认 `["vision", "gpt-4o", "gpt-4-vision", "qvq", "qwen-vl", "glm-4v", "claude-3", "opus", "sonnet", "haiku"]`）、`llm_capability_keywords.function_call_keywords`、`llm_capability_keywords.json_mode_keywords`、`llm_capability_keywords.case_insensitive`（默认 `true`）、`llm_capability_keywords.shared_util_location`（默认 `src/xianyu_hunter/web/routes/api_ai.py`）、`llm_capability_keywords.shared_function_name`（默认 `_is_vision_capable`）在 `config.yaml` 的 `llm_capability_keywords` 节点管理（与 `xianyu-hunter-dev/config/tech-stack.json` 保持单一来源）
  - **适用**：调用外部 LLM endpoint（OpenAI/Claude/通义千问/DeepSeek/Ollama）；多模态调用（Vision/Audio）；function call / tool use；structured output / JSON mode
  - **不适用**：调用固定单一能力的稳定服务；本地固定函数（无外部 endpoint）；已由 SDK 强制约束的调用
  - **历史教训**：深度分析无脑拼接 `image_url` content block，当 `openai_vision_model` 配置为 `qwen-turbo`/`deepseek-chat`（纯文本）时，服务端返回 400 `unknown variant 'image_url'`，触发 WARNING 日志噪音；修复时新增 `_is_vision_capable()` 共享函数 + 预检降级
- 🆕v4.23【强制】**B-REVIEW-SHARED-UTIL-CENTRALIZATION：共享工具函数规范（避免散落内联判断）**
  - 跨 ≥2 模块复用的判断逻辑/关键字白名单/常量必须抽取为"被依赖方"模块顶层的**纯函数**或**模块级常量**，导入方只能 `from <source_module> import <shared_name>`，**禁止**复制粘贴关键字列表或正则字面量到多个调用点
  - **核心机制**（审查时必须理解）：
    - 模型升级 / 协议变更时，散落在多个文件的关键字白名单必然漏改
    - 共享函数位置选择原则：业务最早引入该逻辑的模块作为"权威源"（避免循环依赖）
    - 共享函数必须满足：纯函数（无副作用）+ 类型注解完整 + 单测覆盖 + docstring 注明"为什么是共享的"
  - **判断信号**：
    - `grep -rn "_VISION_CAPABLE_KEYWORDS" src/` 发现定义点 ≥ 2 → 视为违规（应统一为单一权威源）
    - 跨 ≥2 文件出现相同的关键字字面量（`"vision"`, `"gpt-4o"`, `"claude-3"`）→ 视为违规
    - 跨 ≥2 文件出现相同的正则字面量 → 视为违规
    - 跨 ≥2 文件出现相同的魔法数字/字符串（`BATCH_SIZE = 100`）→ 视为可疑
  - **修复模式**：
    ```python
    # ✅ 单一权威源（api_ai.py）
    _VISION_CAPABLE_KEYWORDS: tuple[str, ...] = (
        "vision", "gpt-4o", "gpt-4-vision", "qvq", "qwen-vl",
        "glm-4v", "claude-3", "opus", "sonnet", "haiku",
    )

    def _is_vision_capable(model_name: str | None) -> bool:
        """判断指定模型是否支持多模态（Vision）输入。
        为什么共享：api_ai 成色评估 + api_ai_deep 深度分析 共用此判断，
        避免模型升级时散落修改。
        """
        if not model_name:
            return False
        return any(kw in model_name.lower() for kw in _VISION_CAPABLE_KEYWORDS)

    # api_ai_deep.py（消费方）
    from xianyu_hunter.web.routes.api_ai import _is_vision_capable  # 复用，不重写
    ```
    ```python
    # ❌ 错误：两处独立关键字列表
    # api_ai.py
    VISION_KEYWORDS = ["vision", "gpt-4o", "qwen-vl"]
    def is_vision_capable(model): return any(kw in model for kw in VISION_KEYWORDS)

    # api_ai_deep.py（散落，漏了 glm-4v）
    vision_capable = "vision" in model or "gpt-4o" in model or "qwen-vl" in model
    ```
  - **配置参数**：`shared_util_rules.min_call_sites`（默认 `2`，触发抽取的最小调用点数）、`shared_util_rules.min_module_count`（默认 `2`，触发抽取的最小模块数）、`shared_util_rules.pure_function_required`（默认 `true`）、`shared_util_rules.require_type_annotation`（默认 `true`）、`shared_util_rules.require_unit_test`（默认 `true`）、`shared_util_rules.shared_function_docstring_required`（默认 `true`）在 `config.yaml` 的 `shared_util_rules` 节点管理
  - **适用**：跨模块复用的关键字白名单/正则/常量；模型/接口/协议的版本判断；权限/角色/能力位判断；业务规则判断（如"是否已售"关键词）
  - **不适用**：仅单模块内部使用的 helper（不必抽取）；逻辑需要复用的同时还要扩展（应抽象为基类/策略模式）；性能敏感的 hot path 抽取会带来 import 开销（需评估）
  - **历史教训**：本次 vision_capable 修复初版把判断内联到 `api_ai_deep.py`，与 `api_ai.py` 早已存在的关键字白名单重复 → 后续模型升级需同时改 2 处 → 散落修改风险
- 🆕v4.23【强制】**B-REVIEW-SILENT-DOWNGRADE-PRECHECK：静默降级预检（不支持能力 → 友好降级）**
  - "可选增强"能力（vision / function_call / json_mode）调用前必须预检，失败时降级为"等价文本表达"（如 prompt 追加"图片 URL + 描述"），**禁止**直接抛错。降级路径必须有可观测性（warning 日志 + 降级标记）+ 降级 prompt 模板集中管理
  - **核心机制**（审查时必须理解）：
    - LLM 端点不支持的能力被无脑发送 → 服务端 400 → 调用方 catch + 重试 + 降级 → 链路长 + 日志噪音
    - 预检失败时降级为等价文本表达（如 vision 缺失 → prompt 追加"图片请参考以下文字描述"）可保持主流程继续
    - 核心能力（chat 文本生成）缺失必须报错，不能静默降级
    - 降级 prompt 模板必须集中管理（`config.yaml` 的 `llm_downgrade` 节点），禁止在调用点拼接
  - **判断信号**：
    - 代码构造 payload 时未做能力预检 → 视为违规（与 B-REVIEW-LLM-CAPABILITY-DISPATCH 联动）
    - 预检失败时直接抛异常（`raise ValueError("vision not supported")`）→ 视为违规（应降级）
    - 降级路径无 warning 日志（仅静默跳过）→ 视为违规（不可观测）
    - 降级 prompt 模板以字符串字面量出现在调用函数内（`f"图片请参考以下描述：{url}"`）→ 视为违规
  - **修复模式**：
    ```python
    # ✅ 预检 + 降级 + warning + 集中模板
    # config.yaml
    llm_downgrade:
      prompt_templates:
        vision_missing: "图片请参考以下文字描述：{image_url}"

    # api_ai_deep.py
    vision_capable = _is_vision_capable(settings.openai_vision_model)
    if not vision_capable:
        logger.warning(
            "mode=downgrade reason=vision_missing model={}",
            settings.openai_vision_model,
        )
        downgrade_template = settings.llm_downgrade.prompt_templates["vision_missing"]
        user_content = text + "\n" + downgrade_template.format(image_url=image_url)
    else:
        user_content = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    ```
    ```python
    # ❌ 错误：预检缺失 + 降级模板散落 + 无日志
    user_content = [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": image_url}},  # 模型不支持就 400
    ]
    ```
  - **配置参数**：`llm_downgrade.optional_capabilities`（默认 `["vision", "function_call", "json_mode"]`）、`llm_downgrade.downgrade_log_level`（默认 `warning`）、`llm_downgrade.downgrade_marker_format`（默认 `mode=downgrade reason={capability}_missing model={model_name}`）、`llm_downgrade.prompt_templates`（降级 prompt 模板字典，key 为缺失的能力名）、`llm_downgrade.core_capabilities_not_downgradable`（默认 `["chat", "text_generation", "embedding"]`）在 `config.yaml` 的 `llm_downgrade` 节点管理
  - **适用**：外部 LLM endpoint + payload 含可选能力字段；多模态 / function call / structured output 调用；用户上传图片但模型可能不支持 Vision；用户启用 tool 但模型可能不支持 function call
  - **不适用**：核心能力缺失（chat 文本生成失败必须报错）；用户明确要求某能力（如选择 vision-only 模型）；预检与降级开销大于直接调用（极简场景）
  - **历史教训**：深度分析失败时直接抛 400，调用方需要 catch + 重试 + 降级，链路长且日志噪音大；引入预检 + 降级模板后，warning 降级，prompt 文本补全，warning 计数归零

### 29. 端到端失败原因链与数据完整性闭环 🆕v4.27

基于"Failed to collect item detail: page unavailable or login expired"根因复盘（代码被回退 + 服务未重启双重原因导致修复未生效），系统化梳理端到端失败原因链传递与数据完整性预检的闭环规范。本维度涵盖失败原因传递链、数据完整性预检、合并写入 vs 覆盖写入决策、文案常量集中管理、修改-验证-部署闭环、测试 mock 同步 6 个子节点。

- 🆕v4.27【强制】**B-REVIEW-FAILURE-REASON-PROPAGATION：失败原因传递链（reason propagation chain）**
  - 失败原因必须分三层传递：底层（collector/adapter）设置 `last_*_failure_reason` 属性（如 `last_detail_failure_reason`）→ 中层（service/orchestrator）将 reason 映射为 HTTP status_code → 高层（route/middleware）按 status_code 决定日志级别与降级策略。**禁止**跨层直传字符串、**禁止**用字符串子串做日志降级 marker
  - **核心机制**（审查时必须理解）：
    - 失败原因若只在底层设置，中层不映射 status_code，高层只能用字符串子串判断 → 文案变更即破坏降级逻辑（脆弱耦合）
    - reason 值必须是可枚举的有限集（如 `["cookie_incomplete", "session_expired", "rate_limited", "page_unavailable", "network_timeout"]`），集中定义为模块级常量 `FAILURE_REASONS: tuple[str, ...]`
    - 文案与 reason 的映射必须集中在 `REASON_TO_STATUS_CODE: dict[str, int]` / `REASON_TO_MESSAGE: dict[str, str]` 字典，禁止在多处 if/elif 分支散落映射
    - 错误响应必须含 `error_code` 字段（machine-readable）+ `detail` 字段（human-readable），前端按 `error_code` 分支而非按文案子串
  - **判断信号**：
    - grep `if "expired" in error_message` 或 `if "page unavailable" in detail` → 字符串子串判断违规
    - grep `last_*_failure_reason` 设置点 → 检查是否被中层 status_code 映射消费
    - grep `HTTPException(status_code=` → 检查 status_code 是否根据 reason 映射，而非硬编码 401
    - 错误响应 JSON 不含 `error_code` 字段 → 违规
  - **修复模式**：
    ```python
    # ✅ 三层传递 + reason 枚举 + 字典映射 + error_code 字段
    # config.yaml
    failure_reason_propagation:
      reason_enum: ["cookie_incomplete", "session_expired", "rate_limited", "page_unavailable", "network_timeout"]
      reason_to_status_code:
        cookie_incomplete: 401
        session_expired: 440
        rate_limited: 429
        page_unavailable: 503
        network_timeout: 504

    # collector/_detail.py（底层）
    self.last_detail_failure_reason = "cookie_incomplete"

    # collection_service.py（中层）
    reason = collector.last_detail_failure_reason
    status_code = settings.failure_reason_propagation.reason_to_status_code.get(reason, 500)
    raise HTTPException(status_code=status_code, detail={"error_code": reason, "message": "..."})

    # exception_handler.py（高层）
    if exc.status_code in (429, 503, 504):
        logger.warning("...")  # 降级
    elif exc.status_code == 401:
        logger.error("...")   # 需用户介入
    ```
    ```python
    # ❌ 错误：字符串子串判断 + 硬编码 status_code
    if "expired" in detail:
        return JSONResponse(status_code=401, content={"detail": "..."})
    ```
  - **配置参数**：`failure_reason_propagation.reason_enum`（reason 可枚举集合）、`failure_reason_propagation.reason_to_status_code`（reason → HTTP 状态码映射字典）、`failure_reason_propagation.reason_to_message`（reason → 用户可读文案映射）、`failure_reason_propagation.forbidden_substring_markers`（禁止用作降级判断的字符串子串黑名单）、`failure_reason_propagation.require_error_code_field`（默认 `true`，错误响应必须含 `error_code` 字段）在 `config.yaml` 的 `failure_reason_propagation` 节点管理
  - **适用**：含多层架构（collector → service → route）的失败处理链；多类失败原因需要不同 HTTP 状态码区分的场景；前端需要按 error_code 分支展示不同提示的场景
  - **不适用**：单层函数内部错误（无传递链）；纯输入校验错误（422 直接返回）；不可恢复的系统级错误（500 直接抛出）
  - **历史教训**：v4.27 修复前 `Failed to collect item detail: page unavailable or login expired` 文案同时覆盖"cookie 过期"和"页面不可用"两类语义，前端无法区分需用户重新登录还是稍后重试；reason 链路化后，401（cookie 不完整）+ 503（页面不可用）+ 429（限流）+ 504（超时）四态分明

- 🆕v4.27【强制】**B-REVIEW-DATA-COMPLETENESS-PRECHECK：数据完整性预检（pre-call completeness check）**
  - 调用外部依赖（浏览器、HTTP API、第三方服务）前必须执行数据完整性预检，预检方法签名固定为 `async def _check_xxx_completeness(self) -> str | None`，返回 `None` 表示通过、返回字符串表示错误描述。**禁止**直接调用外部依赖后再发现数据不完整（已消耗资源）
  - **核心机制**（审查时必须理解）：
    - 单一阈值判断不够（如"cookie 数量 ≥ 10"）——可能 10 个全是身份 cookie 缺会话 cookie，必须用**双阈值 AND 判断**：总数阈值 + 关键项命中数阈值
    - 预检必须在调用前 + 调用后各执行一次（调用后二次检查防御外部依赖中途失效）
    - 错误信息必须含具体缺失清单（如"身份 Cookie [cookie2, sgcookie] 存在，会话 Cookie [cna, tracknick, _tb_token_] 不足"），禁止笼统的"数据不完整"
  - **判断信号**：
    - grep `await page.goto` 或 `await client.get` → 检查调用前是否有 `_check_*_completeness` 预检
    - 预检方法签名非 `str | None` 返回类型 → 违规（应统一签名）
    - 预检只用单一阈值（如 `if len(cookies) < 10`）→ 违规（缺关键项命中数判断）
    - 预检错误信息为"数据不完整"/"参数错误"等笼统描述 → 违规
    - 调用后无二次检查 → 违规（外部依赖可能中途失效）
  - **修复模式**：
    ```python
    # ✅ 双阈值 AND 判断 + 调用前预检 + 调用后二次检查 + 具体缺失清单
    _DETAIL_COOKIE_MIN_COUNT = 10  # config: data_completeness_precheck.min_count
    _DETAIL_SESSION_MIN_HITS = 3   # config: data_completeness_precheck.min_key_hits

    async def _check_detail_cookie_completeness(self) -> str | None:
        cookies = await self._get_browser_cookies()
        cookie_names = {c.get("name", "") for c in cookies}
        identity_found = set(_OFFICIAL_COLLECT_IDENTITY_COOKIES) & cookie_names
        session_found = _DETAIL_SESSION_COOKIES & cookie_names
        # 双阈值 AND 判断
        if len(cookies) >= _DETAIL_COOKIE_MIN_COUNT and len(session_found) >= _DETAIL_SESSION_MIN_HITS:
            return None
        # 具体缺失清单
        return (
            f"闲鱼登录 Cookie 不完整（共 {len(cookies)} 个，"
            f"身份 Cookie {sorted(identity_found)} 存在，"
            f"会话 Cookie {sorted(session_found)} 不足），"
            f"请重新登录或从浏览器导出完整 Cookie 导入"
        )

    async def _collect_detail_only(self, item_id: str):
        # 调用前预检
        if reason := await self._check_detail_cookie_completeness():
            raise HTTPException(status_code=401, detail={"error_code": "cookie_incomplete", "message": reason})
        result = await collector.detail(item_id)
        # 调用后二次检查
        if not result and collector.last_detail_failure_reason:
            raise HTTPException(status_code=503, detail={"error_code": collector.last_detail_failure_reason})
    ```
    ```python
    # ❌ 错误：单阈值 + 无签名 + 笼统错误信息 + 无二次检查
    async def _check_cookies(self) -> bool:
        if len(await self._get_cookies()) < 10:
            return False
        return True
    ```
  - **配置参数**：`data_completeness_precheck.method_name_pattern`（预检方法名模式，默认 `_check_*_completeness`）、`data_completeness_precheck.return_type`（默认 `str | None`）、`data_completeness_precheck.require_dual_threshold`（默认 `true`，强制双阈值 AND 判断）、`data_completeness_precheck.require_post_call_check`（默认 `true`，强制调用后二次检查）、`data_completeness_precheck.require_missing_list_in_message`（默认 `true`，错误信息必须含具体缺失清单）、`data_completeness_precheck.min_count`（总数阈值，默认 10）、`data_completeness_precheck.min_key_hits`（关键项命中数阈值，默认 3）在 `config.yaml` 的 `data_completeness_precheck` 节点管理
  - **适用**：调用浏览器自动化（依赖完整 cookie 集）；调用第三方 API（依赖完整请求头/认证 token）；调用本地服务（依赖完整配置文件）；任何"数据不完整即调用失败"的场景
  - **不适用**：幂等查询接口（缺数据可返回空集合，无需预检）；纯计算函数（无外部依赖）；用户输入校验（由 Pydantic 模型校验）
  - **历史教训**：v4.27 修复前仅检查 4 个身份 cookie 存在性，未检查 22 个完整 cookie 集，导致闲鱼详情页 SPA 渲染失败（依赖完整会话 cookie）；双阈值 AND 判断后，38 个 cookie + 5 个关键会话 cookie 命中才放行

- 🆕v4.27【强制】**B-REVIEW-MERGE-VS-OVERWRITE-WRITE：合并写入 vs 覆盖写入决策（merge vs overwrite write strategy）**
  - 持久化层（JSON 文件 / SQLite / 配置文件）写入时必须按数据来源选择策略：新数据是**完整集**（如全量导出）→ 覆盖写；新数据是**部分集**（如增量导入、用户单点更新）→ 合并写。**禁止**对部分集数据使用覆盖写（会丢失旧文件中的其他数据）
  - **核心机制**（审查时必须理解）：
    - 合并写方法签名固定为 `def merge_xxx(self, new_items: list[dict] | dict) -> bool`，返回 `True` 表示合并成功
    - 合并策略：以唯一 key（如 cookie 的 `name` 字段、用户的 `id` 字段）为索引，相同 key 的新值覆盖旧值，旧文件中其他项全部保留
    - 合并后必须日志输出合并前后数量变化（如 `merge_cookies: 4 → 38 (added 34, updated 4)`）
    - 覆盖写必须先验证新集完整（调用 `_check_xxx_completeness` 预检），否则禁止覆盖
  - **判断信号**：
    - grep `json.dump(` 或 `write_text(` → 检查写入策略是否匹配数据来源
    - grep `export_cookies` / `save_config` → 检查是否区分 `merge_*` 与 `overwrite_*` 两个方法
    - 部分集数据（如浏览器导入的 4 个 cookie）调用覆盖写方法 → 违规
    - 合并写方法无日志输出合并前后数量 → 违规
    - 覆盖写前未调用预检验证新集完整 → 违规
  - **修复模式**：
    ```python
    # ✅ 合并写：以 name 为 key 合并，旧文件中其他 cookie 全部保留
    def merge_cookies(self, new_cookies: list[dict]) -> bool:
        old_cookies = self._load_json_cookies()  # 38 个
        old_by_name = {c["name"]: c for c in old_cookies}
        added, updated = 0, 0
        for new_c in new_cookies:  # 4 个新导入
            name = new_c["name"]
            if name in old_by_name:
                old_by_name[name] = new_c
                updated += 1
            else:
                old_by_name[name] = new_c
                added += 1
        merged = list(old_by_name.values())
        self._write_json_cookies(merged)
        logger.info(f"merge_cookies: {len(old_cookies)} → {len(merged)} (added {added}, updated {updated})")
        return True

    # ❌ 错误：覆盖写丢失旧数据
    def save_cookies(self, new_cookies: list[dict]):  # 4 个新导入覆盖 38 个旧数据
        self._write_json_cookies(new_cookies)
    ```
  - **配置参数**：`write_strategy_decision.merge_method_pattern`（合并写方法名模式，默认 `merge_*`）、`write_strategy_decision.overwrite_method_pattern`（覆盖写方法名模式，默认 `save_*` / `export_*`）、`write_strategy_decision.require_log_on_merge`（默认 `true`，合并后必须日志输出合并前后数量）、`write_strategy_decision.require_precheck_before_overwrite`（默认 `true`，覆盖写前必须预检新集完整）、`write_strategy_decision.unique_key_field_examples`（唯一 key 字段示例，如 `["name", "id", "key"]`）在 `config.yaml` 的 `write_strategy_decision` 节点管理
  - **适用**：浏览器 Cookie 导入（部分集，必须合并写）；用户偏好导入（部分集）；配置文件增量更新（部分集）；全量备份恢复（完整集，可覆盖写）；首次初始化（无旧文件，可覆盖写）
  - **不适用**：内存缓存更新（无持久化）；日志文件追加（无合并概念）；临时文件写入（无历史数据需要保留）
  - **历史教训**：v4.27 修复前浏览器 Cookie 导入用 `export_cookies`（覆盖写），4 个新 cookie 覆盖了 38 个旧 cookie，导致 cookie 集从 38 → 4，闲鱼详情页 SPA 渲染失败；改用 `merge_cookies` 后，4 个新 cookie 合并到 38 个旧 cookie，cookie 集从 4 → 38 恢复

- 🆕v4.27【强制】**B-REVIEW-ERROR-MESSAGE-CONSTANT：文案常量集中管理（error message constant centralization）**
  - 错误文案、日志降级 marker、用户提示信息必须提取为模块级常量（`_ERROR_MSG_*` / `_LOG_MARKER_*`），跨模块引用必须 `from <source> import _MSG_*`。**禁止**用字符串子串做日志降级 marker（如 `if "expired" in detail:`），**禁止**在多处内联相同文案
  - **核心机制**（审查时必须理解）：
    - 文案常量集中定义为模块级 `tuple[str, ...]` 或 `dict[str, str]`，并注释文案来源（如 `# 来源：闲鱼详情页错误提示，v4.27 修复时提炼`）
    - 跨模块引用必须 import 常量，禁止重新定义相同字符串
    - 错误响应必须含 `error_code` 字段（machine-readable），前端按 `error_code` 分支而非按文案子串
    - 日志降级判断必须用常量集合（如 `if reason in DOWNGRADE_REASONS:`），禁止字符串子串判断
  - **判断信号**：
    - grep `if "expired" in` / `if "unavailable" in` / `if "rate limited" in` → 字符串子串判断违规
    - 同一文案字符串在代码中出现 ≥ 2 处未提取为常量 → 违规（与 B-REVIEW-LOG-DOWNGRADE-STABILITY 联动）
    - 错误响应 JSON 不含 `error_code` 字段 → 违规
    - 跨模块 import 同一文案常量失败（重新定义相同字符串）→ 违规
  - **修复模式**：
    ```python
    # ✅ 文案常量集中 + error_code 字段 + 常量集合判断
    # collection_service.py
    _ERROR_MSG_COOKIE_INCOMPLETE = "闲鱼登录 Cookie 不完整，请重新登录或从浏览器导出完整 Cookie 导入"
    _ERROR_MSG_PAGE_UNAVAILABLE = "闲鱼详情页暂时不可用，请稍后重试"
    _DOWNGRADE_REASONS = frozenset({"rate_limited", "page_unavailable", "network_timeout"})

    # 跨模块引用
    from .collection_service import _ERROR_MSG_COOKIE_INCOMPLETE

    # 日志降级判断用常量集合
    if reason in _DOWNGRADE_REASONS:
        logger.warning("mode=downgrade reason={}", reason)
    ```
    ```python
    # ❌ 错误：字符串子串判断 + 内联文案 + 无 error_code
    if "expired" in detail:
        logger.warning("Cookie expired, downgrading")
    return JSONResponse(status_code=401, content={"detail": "Cookie expired, please re-login"})
    ```
  - **配置参数**：`error_message_centralization.require_constant_extraction`（默认 `true`，强制提取为模块级常量）、`error_message_centralization.require_version_comment`（默认 `true`，常量定义处必须注释历史来源）、`error_message_centralization.require_error_code_field`（默认 `true`，错误响应必须含 `error_code` 字段）、`error_message_centralization.forbidden_substring_markers`（禁止用作降级判断的字符串子串黑名单，如 `["expired", "unavailable", "rate limited"]`）、`error_message_centralization.max_inline_occurrences`（默认 `1`，同一文案允许内联次数）在 `config.yaml` 的 `error_message_centralization` 节点管理
  - **适用**：错误响应文案（401/403/500 等）；日志降级 marker；用户提示信息（前端 toast/message）；跨模块复用的常量文案
  - **不适用**：一次性临时调试日志（无需提取）；动态生成的文案（如 `f"task {task_id} failed"`）；纯内部断言消息（如 `assert x > 0, "x must be positive"`）
  - **历史教训**：v4.27 修复前 `Failed to collect item detail: page unavailable or login expired` 文案在 collection_service / cookie_inject / exception_handler 三处内联，文案变更需改 3 处；提取为常量后，文案变更只需改 1 处，前端按 `error_code` 分支而非按文案子串

- 🆕v4.27【强制】**B-REVIEW-EDIT-VERIFY-DEPLOY-LOOP：修改-验证-部署闭环（edit-verify-deploy closed loop）**
  - 使用 Edit 工具修改文件后必须立即用 Grep/Read 验证修改是否真正生效（grep 标志性标识符确认无 false positive）；Python 修改后必须重启服务（旧进程仍在运行旧代码）；重启后必须验证端口监听 + 数据状态；`git stash` 前必须先 `git commit` 保底（避免 stash 丢失）。**禁止**修改后直接交付用户验证
  - **核心机制**（审查时必须理解）：
    - Edit 工具可能因 `old_string` 不唯一而失败（返回成功但未修改），必须用 Grep 验证标志性标识符（如新方法名、新常量名）确实存在于文件中
    - 全局 grep 旧文案（如 `Failed to collect item detail`）确认无残留（可能多处内联，必须全部修改）
    - Python 修改后旧进程仍在运行旧代码，必须 `taskkill /F /T /PID` 终止旧进程 + 重启服务
    - 重启后必须验证端口监听（`netstat -ano | findstr :8000`）+ 数据状态（如 cookie 数量、配置文件内容）
    - `git stash` 会丢失未提交的工作区修改，必须先 `git commit -m "wip"` 保底，再 stash
  - **判断信号**：
    - AI 助手修改文件后未 grep 验证 → 违规
    - 用户反馈"还是报错"，排查发现 Python 进程启动时间早于代码修改时间 → 服务未重启违规
    - `git stash` 后工作区修改丢失，无法恢复 → 未先 commit 保底违规
    - 重启后未验证端口监听 → 违规（可能端口被占用，新进程启动失败但未发现）
  - **修复模式**：
    ```powershell
    # ✅ 修改-验证-部署闭环
    # 1. Edit 修改 collection_service.py 新增 _check_detail_cookie_completeness 方法
    # 2. Grep 验证标志性标识符
    Grep _check_detail_cookie_completeness collection_service.py  # 应有匹配
    # 3. 全局 grep 旧文案
    Grep "Failed to collect item detail: page unavailable or login expired"  # 应无匹配
    # 4. 终止旧进程
    taskkill /F /T /PID 27020
    # 5. 重启服务
    .venv\Scripts\python.exe -m xianyu_hunter web
    # 6. 验证端口监听
    netstat -ano | findstr :8000  # 应有 LISTENING
    # 7. 验证数据状态
    Read data\cookies_default.json  # 应有 38 个 cookie
    ```
    ```powershell
    # ❌ 错误：修改后未验证 + 未重启服务
    # Edit 修改文件后直接交付用户验证
    # 用户反馈"还是报错"，排查发现 Python 进程启动时间 17:19 早于代码修改时间 17:30
    ```
  - **配置参数**：`edit_verify_deploy_loop.require_grep_verify_after_edit`（默认 `true`，Edit 后必须 Grep 验证）、`edit_verify_deploy_loop.require_global_grep_old_message`（默认 `true`，全局 grep 旧文案确认无残留）、`edit_verify_deploy_loop.require_restart_python_service`（默认 `true`，Python 修改后必须重启服务）、`edit_verify_deploy_loop.require_port_verify_after_restart`（默认 `true`，重启后必须验证端口监听）、`edit_verify_deploy_loop.require_data_state_verify`（默认 `true`，重启后必须验证数据状态）、`edit_verify_deploy_loop.require_commit_before_stash`（默认 `true`，git stash 前必须先 commit 保底）、`edit_verify_deploy_loop.verify_port`（默认 `8000`）、`edit_verify_deploy_loop.verify_data_file_examples`（验证数据文件示例，如 `["data/cookies_default.json"]`）在 `config.yaml` 的 `edit_verify_deploy_loop` 节点管理
  - **适用**：AI 助手使用 Edit 工具修改代码后；Python 服务代码修改后需重启的场景；多文件修改后需全局验证的场景；使用 git stash 的工作流
  - **不适用**：纯前端修改（前端 vite 热更新，无需重启）；纯文档修改（不影响运行时）；纯测试代码修改（pytest 重新执行即生效）；使用 git worktree 的隔离工作流（无需 stash）
  - **历史教训**：v4.27 修复前 Edit 工具修改 collection_service.py 后未 grep 验证，未重启服务，用户反馈"还是报错"，排查发现 Python 进程（PID 27020）启动时间 17:19:25 早于代码修改时间 17:30，旧进程仍在运行旧代码；闭环规范后，Edit → Grep → taskkill → 重启 → 端口验证 → 数据验证 6 步走

- 🆕v4.27【强制】**B-REVIEW-TEST-MOCK-SYNC：测试 mock 同步（test mock synchronization）**
  - 修改前置条件（如新增 cookie 完整性预检、新增配置项、新增方法参数）时必须同步更新测试 mock 数据，mock 数据必须覆盖完整字段集（如 22 个 cookie 而非 4 个）。**禁止**修改前置条件后不更新测试 mock（测试会因前置条件不满足而失败，但开发者可能误以为是 mock 不全而非前置条件变更）
  - **核心机制**（审查时必须理解）：
    - 修改前置条件（如新增 `_check_detail_cookie_completeness` 方法）后，原测试 mock 仅 4 个 cookie，预检读不到完整 cookie 集抛 401，测试失败
    - mock 数据必须覆盖完整字段集（如 22 个 cookie：4 个身份 + 5 个会话 + 13 个其他），而非最小集
    - 测试失败时必须优先检查前置条件变更（grep 最近修改的方法签名、新增的预检方法），而非盲目调整 mock
    - mock 数据集中管理（如 `tests/conftest.py` 的 `MOCK_COOKIES` 常量），禁止在多个测试文件中重复定义
  - **判断信号**：
    - grep 测试文件中的 mock 数据（如 `MOCK_COOKIES = [...]`）→ 检查是否覆盖完整字段集
    - 测试失败时错误信息为 `AssertionError: expected 401 but got 200` 或 `KeyError: 'cna'` → 优先检查前置条件变更
    - 同一 mock 数据在多个测试文件中重复定义 → 违规（应集中管理）
    - 修改前置条件后未同步更新测试 mock → 违规
  - **修复模式**：
    ```python
    # ✅ mock 数据集中管理 + 完整字段集 + 同步更新
    # tests/conftest.py
    MOCK_COOKIES = [
        {"name": n, "value": "v"} for n in [
            # 身份 Cookie（4 个）
            "cookie2", "sgcookie", "unb", "_m_h5_tk",
            # 会话 Cookie（5 个）
            "cna", "tracknick", "_tb_token_", "t", "tfstk",
            # 其他 Cookie（13 个）
            "xlly_s", "_samesite_flag_", "KLNotice", "isg", "tfstk",
            # ... 共 22 个
        ]
    ]

    # tests/test_collection_service.py
    container.browser.get_cookies = AsyncMock(return_value=MOCK_COOKIES)
    ```
    ```python
    # ❌ 错误：mock 数据不完整 + 修改前置条件后未同步更新
    # 新增 _check_detail_cookie_completeness 方法后，原 mock 仅 4 个 cookie
    container.browser.get_cookies = AsyncMock(return_value=[
        {"name": "cookie2", "value": "v"},
        {"name": "sgcookie", "value": "v"},
        {"name": "unb", "value": "v"},
        {"name": "_m_h5_tk", "value": "v"},
    ])  # 预检失败：缺会话 cookie
    ```
  - **配置参数**：`test_mock_synchronization.require_full_field_set`（默认 `true`，mock 数据必须覆盖完整字段集）、`test_mock_synchronization.require_centralized_management`（默认 `true`，mock 数据集中管理在 conftest.py）、`test_mock_synchronization.require_sync_on_precondition_change`（默认 `true`，修改前置条件时必须同步更新 mock）、`test_mock_synchronization.priority_check_on_failure`（默认 `precondition_change`，测试失败时优先检查前置条件变更）、`test_mock_synchronization.min_cookie_count_for_detail_test`（默认 `22`，详情采集测试 mock cookie 最小数量）、`test_mock_synchronization.mock_data_location`（默认 `tests/conftest.py`）在 `config.yaml` 的 `test_mock_synchronization` 节点管理
  - **适用**：修改前置条件（新增预检方法、新增配置项、新增方法参数）后；测试失败时优先排查方向；mock 数据管理；新增测试用例时参考完整字段集
  - **不适用**：纯 UI 测试（无前置条件依赖）；一次性临时测试（无需集中管理）；纯函数测试（无外部依赖 mock）
  - **历史教训**：v4.27 修复前新增 `_check_detail_cookie_completeness` 方法后，原测试 mock 仅 4 个 cookie，预检失败抛 401，测试用例 `test_collection_service.py` 3/3 失败；同步更新 mock 为 12 个 cookie（4 身份 + 5 会话 + 3 其他）后，3/3 通过

- 🆕v4.28【强制】**B-REVIEW-121: 时区一致性检查（timezone consistency）**
  - 规范引用：DATETIME-TZ-01 时区一致性三步检查法
  - datetime 减法/比较前必须统一 tzinfo，禁止 aware 与 naive 混用导致 `TypeError: can't subtract offset-naive and offset-aware datetimes`。**核心机制**：项目内统一时区策略（naive 或 aware），`_utcnow()` 返回 aware 时所有 DB 字段也必须 aware；DB 字段为 naive 时调用方必须 `.replace(tzinfo=None)` 统一。**判断信号**：grep `_utcnow() - row\.` / `_utcnow() < row\.` 检查右侧是否同 tzinfo；`TypeError: offset-naive vs aware` 异常即违反。**修复模式**：`diff = _utcnow().replace(tzinfo=None) - row.created_at`（naive 策略）或 `diff = _utcnow() - row.created_at.replace(tzinfo=timezone.utc)`（aware 策略）。**配置参数**：`coding_standards.datetime.default_timezone`（默认 `naive`）在 `config.yaml` 管理。**适用**：所有 datetime 减法/比较场景；定时任务计算下次执行时间；过期判断。**不适用**：纯日期字段（无时间）；UTC 时间戳数值比较。**历史教训**：v4.28 修复前 `_utcnow()` 返回 aware，`row.created_at` 为 naive，`diff = _utcnow() - row.created_at` 抛 TypeError 导致任务调度失败

- 🆕v4.28【强制】**B-REVIEW-122: 原生 SQL 返回值类型防御（raw SQL return type defense）**
  - 规范引用：DATETIME-TZ-02 原生 SQL 类型强制转换
  - `text()` 查询返回的标量值必须做类型转换，禁止直接调用 `.isoformat()` / `.timestamp()` 等方法（不同 SQLite 驱动返回 `str` / `datetime` / `bytes` 不一致）。**核心机制**：raw SQL 结果集类型不确定，必须用 `_coerce_datetime(value)` 等强制转换函数包裹；转换函数检测 `isinstance(value, datetime)` 直返、`isinstance(value, str)` 解析、其他类型 fallback。**判断信号**：grep `text\(.*\).*\.isoformat\(\)` / `result\.scalar\(\)\.isoformat` 检查是否漏类型转换；`AttributeError: 'str' object has no attribute 'isoformat'` 即违反。**修复模式**：`dt = _coerce_datetime(value); dt.isoformat()`（强制转换）vs `value.isoformat()`（直接调用，违规）。**配置参数**：`coding_standards.datetime.raw_sql_coerce`（默认 `true`）在 `config.yaml` 管理。**适用**：所有 `session.execute(text(...))` 标量查询；ORM `column_property` 派生字段；自定义聚合查询。**不适用**：ORM 模型字段（已有类型声明）；纯数值/字符串查询。**历史教训**：v4.28 修复前 `text("SELECT MAX(created_at) FROM events")` 返回 str，调用 `.isoformat()` 抛 AttributeError

- 🆕v4.28【强制】**B-REVIEW-123: 迁移步骤独立性（migration step independence）**
  - 规范引用：MIGRATE-01 迁移块独立容错
  - 多个迁移步骤（C-01/C-02/C-03/C-04/C-05）必须各自 try/except，禁止外层统一 try/except 吞掉异常导致后续步骤跳过。**核心机制**：每个迁移步骤独立 try/except + warning 日志，单步失败不阻断后续；强依赖场景（C-02 依赖 C-01 的列存在）允许合并；步骤边界用注释 `# C-01: xxx` 标识。**判断信号**：grep `try:.*C-01.*C-02.*C-03` 单 try 多步骤即违规；`except: pass` 包裹多个迁移步骤即违规。**修复模式**：每个步骤独立 `try: ... except Exception as e: logger.warning(...)`（正确）vs `try: C-01; C-02; C-03; except: pass`（错误，C-01 失败导致 C-02/C-03 跳过）。**配置参数**：`coding_standards.migration.independent_steps`（默认 `[C-01, C-02, C-03, C-04, C-05]`）、`coding_standards.migration.allow_merge_when`（默认 `strong_dependency`）在 `config.yaml` 管理。**适用**：所有 `_migrate_*` 函数；多步骤数据迁移；schema 演进。**不适用**：单步骤迁移；强依赖迁移链（C-02 必须在 C-01 后）。**历史教训**：v4.28 修复前 5 个迁移步骤被外层 try/except 包裹，C-01 失败导致 C-04 未执行，列缺失

- 🆕v4.28【强制】**B-REVIEW-124: NOT NULL 字段防御（NOT NULL field defense）**
  - 规范引用：NULL-01 NOT NULL 字段 API 层防御
  - NOT NULL 字段在 API 层必须有 null 防御，禁止 `data.get('field')` 直接赋值（可能返回 None 触发 IntegrityError）。**核心机制**：API 层校验 `if data.get('field') is None: raise HTTPException(422, detail="field 不能为空")`；与 B-REVIEW-111 NOT-NULL-NONE-DEFENSE 配合（B-REVIEW-111 是 DB 写入层 pop，本检查是 API 层前置校验）。**判断信号**：grep `task\.\w+ = data\.get\(` 检查字段是否为 NOT NULL；`IntegrityError: NOT NULL constraint failed` 即违反。**修复模式**：`if data.get('interval_seconds') is None: raise HTTPException(422)`（防御）vs `task.interval_seconds = data.get('interval_seconds')`（直接赋值，可能 None）。**配置参数**：`coding_standards.null_defense.check_fields`（默认 `[interval_seconds, use_cron]`）在 `config.yaml` 管理。**适用**：所有 PATCH/PUT 接口；NOT NULL 字段更新；用户输入写入 DB。**不适用**：可空字段；有默认值字段；系统自动填充字段。**历史教训**：v4.28 修复前 `task.interval_seconds = data.get('interval_seconds')` 在用户未传字段时写入 None，触发 IntegrityError

- 🆕v4.28【强制】**B-REVIEW-125: 查询过滤条件精确性（query filter precision）**
  - 规范引用：QUERY-01 过滤条件精确性检查
  - 查询过滤条件必须精确匹配业务语义，禁止 `startswith` / `contains` 等模糊匹配引入噪声数据。**核心机制**：业务需要精确匹配时必须用 `==`，需要前缀匹配时评估是否会引入无关数据；`startswith('eval.')` 会同时匹配 `eval.scored` 和 `eval.passed`，若只需 `eval.scored` 必须用 `==`。**判断信号**：grep `filter\(.*startswith\(` 评估是否应改 `==`；统计结果与预期不符时优先排查过滤条件。**修复模式**：`filter(events.type == 'eval.scored')`（精确）vs `filter(events.type.startswith('eval.'))`（模糊，引入 `eval.passed` 噪声）。**配置参数**：`coding_standards.query_filter.precision_check`（默认 `true`）在 `config.yaml` 管理。**适用**：所有 ORM 查询；统计聚合；分页查询。**不适用**：模糊搜索场景（用户输入关键词）；日志查询。**历史教训**：v4.28 修复前 `filter(events.type.startswith('eval.'))` 同时匹配 `eval.scored` 和 `eval.passed`，导致评分统计翻倍

- 🆕v4.28【强制】**B-REVIEW-126: 状态值枚举一致性（enum value consistency）**
  - 规范引用：ENUM-01 状态值枚举一致性
  - 业务逻辑中的状态值字符串必须与 DB 存储值一致，禁止硬编码字符串导致前后端/DB 不一致。**核心机制**：状态值必须集中定义为枚举常量（如 `class OrderStatus(str, Enum): SUCCEEDED = 'succeeded'`），业务代码引用常量而非字面量；DB 存储值、API 响应值、业务判断值三者必须引用同一常量。**判断信号**：grep `filter\(.*status == ['"]` 检查是否硬编码字符串；状态值与 DB 实际存储不符的查询返回空结果。**修复模式**：`query.filter(Order.status == OrderStatus.SUCCEEDED)`（常量引用）vs `query.filter(Order.status == 'paid')`（硬编码，DB 实际存 `succeeded`）。**配置参数**：`coding_standards.enum_consistency.status_fields`（默认 `[order_status, eval_status, notify_status]`）在 `config.yaml` 管理。**适用**：所有状态字段查询；状态转换逻辑；前后端状态同步。**不适用**：临时调试查询；一次性数据修复脚本。**历史教训**：v4.28 修复前 `Order.status == 'paid'` 硬编码，DB 实际存 `succeeded`，查询永远返回空

- 🆕v4.28【强制】**B-REVIEW-127: 错误归因精细化（error attribution refinement）**
  - 规范引用：ATTRIB-01 错误归因精细化
  - 外部调用失败必须根据 failure_reason 映射具体 HTTP 状态码，禁止统一返回 502 无具体原因。**核心机制**：failure_reason 字段必须可枚举（token_expired/anti_crawler/page_unavailable/other），每个 reason 映射到具体状态码（401/429/503/502）；与 B-REVIEW-FAILURE-REASON-PROPAGATION 配合（v4.27 失败原因传递链）。**判断信号**：grep `raise HTTPException\(502` 检查是否无具体原因；前端无法区分错误类型即违反。**修复模式**：`status_map = {'token_expired': 401, 'anti_crawler': 429, 'page_unavailable': 503, 'other': 502}; raise HTTPException(status_map.get(reason, 502))`（精细化映射）vs `raise HTTPException(502)`（无具体原因）。**配置参数**：`coding_standards.error_attribution.status_mapping`（默认 `{token_expired: 401, anti_crawler: 429, page_unavailable: 503, other: 502}`）在 `config.yaml` 管理。**适用**：所有外部调用失败的 HTTP 响应；LLM API 调用；浏览器自动化失败。**不适用**：内部业务逻辑错误（用 400/422）；认证授权错误（用 401/403）。**历史教训**：v4.28 修复前所有外部失败统一返回 502，前端无法区分 token 过期（需重新登录）与反爬（需等待重试）

- 🆕v4.28【强制】**B-REVIEW-128: 异常传播完整性（exception propagation integrity）**
  - 规范引用：EXCEPT-01 异常传播完整性
  - 禁止 `except: return False` 吞掉异常返回默认值，必须检测具体异常类型并重新抛出关键异常。**核心机制**：except 块必须区分"预期异常"（可降级处理）与"非预期异常"（必须重新抛出）；浏览器自动化场景必须检测 `page.is_closed()` 并重新抛出 `TargetClosedError`。**判断信号**：grep `except.*:\s*return False` 检查是否吞掉异常；`except Exception: pass` 无日志即违反。**修复模式**：`try: ... except TargetClosedError: raise  # 重新抛出关键异常 except Exception as e: logger.warning(...); return False  # 降级处理`（正确）vs `try: ... except: return False  # 隐藏问题`（错误）。**适用**：所有 try/except 块；浏览器自动化异常处理；外部 API 调用。**不适用**：清理代码（finally 中的异常可降级）；日志记录失败（不应阻断主流程）。**历史教训**：v4.28 修复前浏览器页面关闭后被 `except: return False` 吞掉，下游误以为采集成功

- 🆕v4.28【强制】**B-REVIEW-129: 错误消息透传（error message transparency）**
  - 规范引用：ERROR-01 错误消息透传
  - HTTPException 必须返回具体 detail，禁止用"操作失败"等通用文案掩盖根因。**核心机制**：detail 字段必须包含具体错误原因（含字段名/值/约束），用 f-string 拼接上下文信息；与 B-REVIEW-ERROR-MESSAGE-CONSTANT 配合（v4.27 文案常量集中管理，本检查关注 detail 透传）。**判断信号**：grep `HTTPException\(400,\s*['"]操作失败` / `HTTPException\(.*,\s*['"]失败['"]` 检查通用文案；前端无法定位问题即违反。**修复模式**：`raise HTTPException(400, detail=f"配置校验失败：{e}")`（透传根因）vs `raise HTTPException(400, "操作失败")`（通用文案）。**适用**：所有 HTTPException 抛出；API 参数校验；业务逻辑错误。**不适用**：敏感信息错误（需脱敏）；安全相关错误（不应透露内部状态）。**历史教训**：v4.28 修复前所有配置错误返回"操作失败"，用户无法定位是哪个字段校验失败

- 🆕v4.28【强制】**B-REVIEW-130: 重试策略配置化（retry strategy configuration）**
  - 规范引用：RETRY-01 重试策略配置化
  - 重试次数必须从 config 读取，禁止硬编码 `for i in range(10)`。**核心机制**：重试次数、间隔、退避策略（固定/指数）必须集中在 config.yaml 管理；与 B-REVIEW-FALLBACK-CHAIN 配合（v4.3 降级链模式，本检查关注重试次数配置化）。**判断信号**：grep `for i in range\(\d+\)` 在重试场景检测硬编码；grep `retry_count` / `max_retries` 检查是否从 config 读取。**修复模式**：`for i in range(config.retry_count):`（配置化）vs `for i in range(10):`（硬编码）。**配置参数**：`coding_standards.retry.default_count`（默认 `3`）、`coding_standards.retry.default_interval`（默认 `1.0`）、`coding_standards.retry.backoff`（默认 `exponential`）在 `config.yaml` 管理。**适用**：所有重试循环；外部 API 调用重试；网络请求重试。**不适用**：固定次数的批量处理（非重试）；测试用例中的 mock 循环。**历史教训**：v4.28 修复前硬编码 `range(10)` 重试 10 次，生产环境反爬触发后请求量暴增被封禁

- 🆕v4.28【强制】**B-REVIEW-131: 已知场景日志降噪（log noise suppression）**
  - 规范引用：LOG-NOISE-01 已知场景日志降噪
  - 高频已知错误必须聚合/降级，禁止每次都输出 WARNING 导致日志爆炸。**核心机制**：首次出现输出 WARNING，后续在冷却期内（如 300s）降级为 DEBUG；降噪模式按 pattern 匹配（如 `cookie_expired`）；与 B-REVIEW-LOGURU-PLACEHOLDER 配合（v4.10 占位符一致性，本检查关注降噪）。**判断信号**：grep `logger.warning.*cookie.*expired` 检查是否无降噪；同一 WARNING 出现 300+ 次即违反。**修复模式**：首次 WARNING + 后续 DEBUG + 冷却期 300s（正确）vs `logger.warning(f'Cookie expired: {e}')` 每次都 WARNING（错误）。**配置参数**：`coding_standards.log_noise.suppress_patterns`（默认 `[{pattern: 'cookie_expired', first_level: WARNING, repeat_level: DEBUG, cooldown_seconds: 300}]`）在 `config.yaml` 管理。**适用**：高频已知错误（cookie 过期/反爬触发/页面不可用）；定时任务日志；外部 API 失败日志。**不适用**：未知错误（必须 WARNING+）；首次出现的错误；关键路径错误。**历史教训**：v4.28 修复前 cookie 过期 WARNING 输出 300+ 次，淹没真正关键日志

- 🆕v4.28【强制】**B-REVIEW-132: 熔断器持久化对称性（circuit breaker cleanup symmetry）**
  - 规范引用：CIRCUIT-01 熔断器持久化对称性
  - 熔断分支与停止分支的清理逻辑必须对称，禁止熔断分支 break 但未调用 `_save_progress()` 导致状态丢失。**核心机制**：所有退出循环的分支（熔断/停止/正常完成）必须执行相同的持久化流程（save_progress + record_state + notify_downstream）；用 cleanup_checklist 清单核对。**判断信号**：grep `break` 在循环内检查是否调用 `_save_progress()`；熔断后重启状态丢失即违反。**修复模式**：熔断分支与停止分支执行相同的 `_save_progress(); _record_state(); _notify_downstream()`（对称）vs 熔断分支仅 `break`（不对称，状态丢失）。**配置参数**：`coding_standards.circuit_breaker.cleanup_checklist`（默认 `[save_progress, record_state, notify_downstream]`）在 `config.yaml` 管理。**适用**：所有熔断器逻辑；批量采集循环；定时任务循环。**不适用**：无状态循环（无需持久化）；单次执行任务。**历史教训**：v4.28 修复前熔断分支 break 但未保存进度，重启后从 0 开始，已采集数据丢失

- 🆕v4.28【强制】**B-REVIEW-133: 状态切换原子性（state transition atomicity）**
  - 规范引用：STATE-01 状态切换原子性
  - 多字段状态切换必须同步更新，禁止只更新一个字段导致状态不一致。**核心机制**：语义关联字段（如 active/minimized/enabled）必须封装 transition 方法同步更新；禁止外部直接赋值单个字段。**判断信号**：grep `\.\w+ = True` / `\.\w+ = False` 检查是否漏更新关联字段；状态字段组合非法（如 active=True + minimized=True）即违反。**修复模式**：`def activate(self): self.active = True; self.minimized = False; self.enabled = True`（封装 transition）vs `sheet.active = True  # 忘了 sheet.minimized = False`（直接赋值，状态不一致）。**适用**：所有多字段状态切换；UI 状态管理；业务对象状态机。**不适用**：独立字段（无关联）；单字段状态。**历史教训**：v4.28 修复前 `sheet.active = True` 但 `sheet.minimized` 仍为 True，UI 显示异常

- 🆕v4.28【强制】**B-REVIEW-134: 多源失效判定一致性（multi-source failure consistency）**
  - 规范引用：CONSISTENCY-01 多源失效判定一致性
  - 多个组件判定同一状态必须使用一致的标准，禁止健康检查器用本地存在性、worker 用 RGV587_ERROR 导致判定不一致。**核心机制**：失效判定函数必须统一（如 `is_cookie_valid(cookie) -> bool`），所有组件引用同一函数；禁止各组件自行实现判定逻辑。**判断信号**：grep `os.path.exists.*cookie` / `RGV587_ERROR` 检查是否有多个判定标准；同一状态在不同组件返回不同结果即违反。**修复模式**：统一失效判定函数 `is_cookie_invalid(reason) -> bool`（一致）vs 健康检查器用本地存在性、worker 用 RGV587_ERROR（不一致）。**适用**：所有跨组件状态判定；健康检查；故障检测。**不适用**：组件内部私有状态；不同语义的状态。**历史教训**：v4.28 修复前健康检查器认为 cookie 有效（文件存在），worker 认为 cookie 无效（RGV587_ERROR），状态显示矛盾

- 🆕v4.28【强制】**B-REVIEW-135: 缺失数据回退策略（missing data fallback strategy）**
  - 规范引用：FALLBACK-01 缺失数据回退策略
  - 主数据源缺失时必须有回退数据源，禁止直接标记无效导致功能不可用。**核心机制**：主数据源（如 JSON 文件）缺失时从备用数据源（如浏览器内存）回退，并写回主数据源；与 B-REVIEW-BROWSER-FALLBACK-SYNC 配合（v4.5 浏览器内存兜底同步，本检查关注回退策略完整性）。**判断信号**：grep `if not.*json.*invalid` 检查是否有回退；主数据源缺失直接标记无效即违反。**修复模式**：JSON 缺失时从浏览器内存回退 + 写回 JSON（正确）vs JSON 缺失 cookie 时直接标记无效（错误，功能不可用）。**适用**：所有多数据源场景；cookie 管理；配置加载。**不适用**：单数据源；关键安全数据（缺失即失效）。**历史教训**：v4.28 修复前 JSON 文件被误删，cookie 直接标记无效，用户需重新登录；回退到浏览器内存 + 写回 JSON 后无需重新登录

- 🆕v4.28【强制】**B-REVIEW-136: 多源状态同步标记机制（multi-source sync marker）**
  - 规范引用：SYNC-01 多源状态同步标记机制
  - 写入方/消费方必须有 marker 机制，禁止 auto_sync=false 时不检查 pending markers 导致状态丢失。**核心机制**：写入方写入数据后设置 pending marker 文件，消费方启动时必须检查 marker 目录并同步；auto_sync=false 仅控制自动同步，不控制启动时检查。**判断信号**：grep `auto_sync.*False` 检查是否漏检查 marker；启动后状态未同步即违反。**修复模式**：启动时检查 pending markers 并同步（正确）vs auto_sync=false 时不检查 pending markers（错误，状态丢失）。**配置参数**：`coding_standards.state_sync.pending_marker_dir`（默认 `data/markers`）、`coding_standards.state_sync.check_on_startup`（默认 `true`）在 `config.yaml` 管理。**适用**：所有多进程状态同步；跨组件数据传递；配置变更通知。**不适用**：单进程应用；实时同步场景（无需 marker）。**历史教训**：v4.28 修复前 auto_sync=false 时启动不检查 marker，用户配置变更未生效

- 🆕v4.28【强制】**B-REVIEW-137: 异步竞态防护（async race condition protection）**
  - 规范引用：RACE-01 异步竞态防护
  - 异步请求完成时必须对比请求 ID，禁止旧请求响应覆盖新请求状态。**核心机制**：用 useRef（前端）/ dict[request_id]（后端）维护最新请求 ID，响应回来时对比 ID，ID 不匹配则丢弃响应；与 B-REVIEW-CONCURRENT-STATE-LOCK 配合（v4.9 并发共享状态锁，本检查关注请求 ID 对比）。**判断信号**：grep `async.*await.*update` 检查是否有请求 ID 对比；快速切换后状态显示旧数据即违反。**修复模式**：useRef 维护最新请求 ID + 响应回来时对比（正确）vs 异步请求完成直接更新状态（错误，旧响应覆盖新状态）。**配置参数**：`coding_standards.race.check_request_id`（默认 `true`）在 `config.yaml` 管理。**适用**：所有异步请求场景；快速切换 UI；搜索建议。**不适用**：单次请求；同步请求；幂等请求。**历史教训**：v4.28 修复前用户快速切换任务，旧任务响应后覆盖新任务状态，显示错误数据

- 🆕v4.28【强制】**B-REVIEW-138: 参数传递链完整性（parameter chain integrity）**
  - 规范引用：PARAM-CHAIN-01 参数传递链完整性
  - 配置项必须在每一层都读取并传递，禁止中间层漏传参数导致末端拿不到配置。**核心机制**：config.yaml → AppConfig → API → 业务逻辑 → 外部调用全链路传递；新增配置项时必须同步更新所有中间层签名；与 B-REVIEW-PARAM-PASS-THROUGH 配合（v4.4 参数透传链路完整性，本检查关注全链路完整性）。**判断信号**：grep 配置项名称检查每一层是否读取；新增配置项后末端拿不到值即违反。**修复模式**：config.yaml → AppConfig → API → 业务逻辑 → 外部调用全链路传递（正确）vs build_search_url 缺少 sort/region 参数（错误，末端拿不到）。**配置参数**：`coding_standards.param_chain.required_fields`（默认 `[sort_type, region, fail_pause_threshold]`）在 `config.yaml` 管理。**适用**：所有配置项；新增配置项；多层级架构。**不适用**：单层应用；动态配置（运行时获取）。**历史教训**：v4.28 修复前 `build_search_url` 缺少 sort/region 参数，搜索结果排序错误

- 🆕v4.28【强制】**B-REVIEW-139: 业务关键词配置化（business keyword configuration）**
  - 规范引用：KEYWORD-01 业务关键词配置化
  - 业务关键词必须集中定义并配置化，禁止分散硬编码导致维护困难。**核心机制**：关键词集中定义为模块级常量（如 `SOLD_TEXT_KEYWORDS: tuple[str, ...] = ('卖掉了', '已售', ...)`)，并在 config.yaml 暴露可配置列表；与 B-REVIEW-EXTERNAL-TEXT-PATTERN-CENTRALIZE 配合（v4.19 外部系统文本特征集中管理，本检查关注配置化）。**判断信号**：grep `'卖掉了'` / `'宝贝不存在'` 检查是否分散硬编码；同一关键词在多处出现即违反。**修复模式**：集中定义 `SOLD_TEXT_KEYWORDS` 常量 + config.yaml 配置化列表（正确）vs 分散硬编码 '卖掉了'、'宝贝不存在'（错误，维护困难）。**配置参数**：`coding_standards.keywords.sold`（默认 `['卖掉了', '已售', '已售罄', '宝贝不存在', '宝贝走丢了', '该宝贝不存在', '商品不存在', '已删除', '已被删除']`）、`coding_standards.keywords.deleted`（默认 `['宝贝不存在', '宝贝走丢了', '该宝贝不存在', '商品不存在', '已删除', '已被删除']`）在 `config.yaml` 管理。**适用**：所有业务关键词；外部系统文本特征；状态判断关键词。**不适用**：一次性字符串；调试日志文本。**历史教训**：v4.28 修复前 '卖掉了' 关键词在 5 个文件硬编码，新增关键词需改 5 处

- 🆕v4.28【强制】**B-REVIEW-140: 开关持久化（switch persistence）**
  - 规范引用：PERSIST-01 开关持久化
  - 业务开关必须持久化到 DB 字段或 localStorage，禁止仅内存 useState 导致刷新后丢失。**核心机制**：业务开关（如自动采集/通知静默）必须持久化到 DB 字段或 localStorage；与 B-REVIEW-CACHE-INVALIDATION 配合（v4.15 缓存失效，本检查关注开关持久化）。**判断信号**：grep `useState.*True` 检查业务开关是否持久化；刷新后开关状态丢失即违反。**修复模式**：业务开关持久化到 DB 字段或 localStorage（正确）vs 业务开关仅内存 useState（错误，刷新后丢失）。**配置参数**：`coding_standards.persist.business_switch_must_persist`（默认 `true`）在 `config.yaml` 管理。**适用**：所有业务开关；用户偏好设置；功能开关。**不适用**：临时 UI 状态（如 loading）；会话级状态（如当前选中项）。**历史教训**：v4.28 修复前自动采集开关仅内存 useState，刷新后丢失，用户需重新开启

- 🆕v4.28【强制】**B-REVIEW-141: 凭证多存储同步（credential multi-store sync）**
  - 规范引用：CREDENTIAL-01 凭证多存储同步
  - yaml/keyring 凭证必须同步，禁止 yaml 凭证不同步到 keyring 导致渠道静默跳过。**核心机制**：启动时 yaml → keyring 同步，确保两个存储一致；与 B-REVIEW-CREDENTIAL-SYNC-BRIDGE 配合（v4.21 凭证同步桥接规范，本检查关注启动时同步）。**判断信号**：grep `keyring.*get` 检查是否 fallback 到 yaml；凭证缺失导致渠道静默跳过即违反。**修复模式**：启动时 yaml → keyring 同步（正确）vs yaml 凭证不同步到 keyring，渠道静默跳过（错误）。**配置参数**：`coding_standards.credential_stores`（默认 `[yaml, keyring]`）在 `config.yaml` 管理。**适用**：所有凭证管理；多存储后端；敏感信息同步。**不适用**：单一存储；明文配置（无敏感信息）。**历史教训**：v4.28 修复前 yaml 凭证未同步到 keyring，通知渠道静默跳过，用户未收到通知

- 🆕v4.28【强制】**B-REVIEW-142: 属性调用一致性（property naming consistency）**
  - 规范引用：NAMING-01 属性调用一致性
  - 属性大小写必须与定义一致，禁止 `self._Session()` 但实际定义是 `_session` 导致 AttributeError。**核心机制**：从类定义复制粘贴属性名，禁止手写；IDE 自动补全必须基于定义而非记忆；与 B-REVIEW-NO-HARDCODED-PROPS 配合（v4.2 硬编码属性，本检查关注命名一致性）。**判断信号**：grep `AttributeError.*has no attribute` 检查命名错误；属性大小写与定义不符即违反。**修复模式**：从类定义复制粘贴属性名（正确）vs `self._Session()  # 实际定义是 _session`（错误，AttributeError）。**适用**：所有属性访问；方法调用；类成员引用。**不适用**：动态属性（getattr/setattr）；第三方库属性。**历史教训**：v4.28 修复前 `self._Session()` 但实际定义是 `_session`，运行时 AttributeError

- 🆕v4.28【强制】**B-REVIEW-143: API 契约一致性（API contract consistency）**
  - 规范引用：CONTRACT-01 API 契约一致性
  - response_model 字段名必须与前端 TS interface 完全一致，禁止后端返回 `total` 前端期望 `total_for_type` 导致字段未定义。**核心机制**：response_model 字段名与 TS interface 字段名必须完全一致（含大小写/下划线/驼峰）；新增字段时必须同步更新前后端。**判断信号**：grep response_model 字段名 + 前端 TS interface 检查一致性；前端 `undefined` 字段即违反。**修复模式**：response_model 字段名与 TS interface 完全一致（正确）vs 后端返回 `total`，前端期望 `total_for_type`（错误，前端 undefined）。**配置参数**：`coding_standards.contract.check_ts_interface_match`（默认 `true`）在 `config.yaml` 管理。**适用**：所有 API 响应；前后端数据交换；DTO 设计。**不适用**：内部 API（无前端消费）；遗留 API（无法修改）。**历史教训**：v4.28 修复前后端返回 `total`，前端期望 `total_for_type`，统计页面显示 undefined

- 🆕v4.28【强制】**B-REVIEW-144: 命名语义清晰性（naming semantics clarity）**
  - 规范引用：SEMANTICS-01 命名语义清晰性
  - 字段名必须准确反映业务语义，禁止 `search_interval` 实际是操作延迟导致理解错误。**核心机制**：字段名必须与业务语义一致，禁止用相似但不准确的名称；命名应反映"是什么"而非"怎么用"。**判断信号**：grep 字段名 + 业务逻辑检查语义一致性；字段名与实际含义不符即违反。**修复模式**：`operation_delay  # 准确反映语义`（正确）vs `search_interval  # 实际是操作延迟`（错误，理解偏差）。**适用**：所有字段命名；变量命名；函数命名。**不适用**：遗留命名（兼容性考虑）；第三方库命名。**历史教训**：v4.28 修复前 `search_interval` 实际是操作延迟，开发者误以为是搜索间隔，配置错误

- 🆕v4.28【强制】**B-REVIEW-145: 重复逻辑抽取（duplicate logic extraction）**
  - 规范引用：DRY-01 重复逻辑抽取
  - 重复代码必须抽取为公共函数，禁止在多个文件中复制粘贴相同逻辑。**核心机制**：跨 ≥2 文件出现相同逻辑（≥3 行）必须抽取为公共函数；与 B-REVIEW-SHARED-UTIL-CENTRALIZATION 配合（v4.23 共享工具函数规范，本检查关注重复检测）；与 B-REVIEW-S1192 配合（重复字符串字面量）。**判断信号**：grep 相同代码片段检查重复；同一逻辑在多处出现即违反。**修复模式**：抽取 `_is_vision_capable()` 公共函数（正确）vs 视觉能力检测逻辑在 api_ai.py 和 api_ai_deep.py 重复（错误）。**配置参数**：`coding_standards.dry.threshold_lines`（默认 `3`）、`coding_standards.dry.threshold_occurrences`（默认 `2`）在 `config.yaml` 管理。**适用**：所有重复代码；跨文件相同逻辑；相似业务流程。**不适用**：一次性代码；测试用例（允许重复 setup）；平台特定代码。**历史教训**：v4.28 修复前视觉能力检测逻辑在 api_ai.py 和 api_ai_deep.py 重复，修改时漏改一处导致行为不一致

- 🆕v4.28【强制】**B-REVIEW-146: 跨进程编码一致性（cross-process encoding consistency）**
  - 规范引用：ENCODING-01 跨进程编码一致性
  - 跨进程通信必须显式设置 UTF-8，禁止 PowerShell 默认 cp936 导致中文变 `?`。**核心机制**：跨进程通信（HTTP/管道/文件）必须显式设置 `Content-Type: application/json; charset=utf-8`；PowerShell 脚本必须设置 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`。**判断信号**：grep `Content-Type.*json` 检查是否含 charset；中文变 `?` 即违反。**修复模式**：显式设置 `Content-Type: application/json; charset=utf-8`（正确）vs PowerShell 脚本默认 cp936，中文变 ?（错误）。**配置参数**：`coding_standards.encoding.default`（默认 `utf-8`）在 `config.yaml` 管理。**适用**：所有跨进程通信；HTTP 响应；子进程调用。**不适用**：进程内通信；纯 ASCII 内容。**历史教训**：v4.28 修复前 PowerShell 脚本默认 cp936，中文通知内容变 `?`，用户无法阅读

- 🆕v4.28【强制】**B-REVIEW-147: dataclass 字段显式声明（dataclass explicit field declaration）**
  - 规范引用：DATACLASS-01 dataclass 字段显式声明
  - dataclass 必须显式声明所有字段，禁止 `getattr(self, 'field', default)` 兜底未声明字段。**核心机制**：dataclass 必须显式声明所有字段（含默认值），未声明字段不能用 getattr 兜底；与 B-REVIEW-CONCURRENT-STATE-LOCK 配合（v4.9 并发共享状态锁，本检查关注 dataclass 字段完整性）。**判断信号**：grep `getattr\(self,` 检查是否兜底未声明字段；`getattr(self, 'consecutive_errors', 0)` 即违反。**修复模式**：dataclass 显式声明 `consecutive_errors: int = 0`（正确）vs `getattr(self, 'consecutive_errors', 0)  # 字段未声明`（错误，绕过类型检查）。**配置参数**：`coding_standards.dataclass.disallow_getattr_fallback`（默认 `true`）在 `config.yaml` 管理。**适用**：所有 dataclass；typeddict；pydantic 模型。**不适用**：动态属性（如 ORM 模型）；第三方库类。**历史教训**：v4.28 修复前 `getattr(self, 'consecutive_errors', 0)` 兜底未声明字段，类型检查器无法检测，运行时字段类型错误

- 🆕v4.28【强制】**B-REVIEW-148: 启动钩子完整性（startup hook completeness）**
  - 规范引用：STARTUP-01 启动钩子完整性
  - 启动钩子必须覆盖所有必要组件，禁止 `_on_startup` 缺少反爬会话管理启动导致功能不可用。**核心机制**：启动钩子必须用清单核对（如 `[scheduler, session_manager, migration, cookie_sync, embedding]`）；与 B-REVIEW-STARTUP-HOOK-COMPLETENESS 配合（v4.22 启动钩子完整性，本检查关注清单核对）。**判断信号**：grep `_on_startup` 检查是否启动所有必要组件；启动后功能不可用即违反。**修复模式**：清单核对 `[scheduler, session_manager, migration, cookie_sync, embedding]`（正确）vs `_on_startup` 缺少反爬会话管理启动（错误，反爬功能不可用）。**配置参数**：`coding_standards.startup.components`（默认 `[scheduler, session_manager, migration, cookie_sync, embedding]`）在 `config.yaml` 管理。**适用**：所有启动钩子；服务初始化；组件依赖管理。**不适用**：按需启动组件；延迟加载组件。**历史教训**：v4.28 修复前 `_on_startup` 缺少反爬会话管理启动，反爬功能运行时报错"会话未初始化"

- 🆕v4.28【强制】**B-REVIEW-149: 测试 Mock 类型匹配（test mock type matching）**
  - 规范引用：MOCK-01 测试 Mock 类型匹配
  - AsyncMock/MagicMock 必须与 async/sync 函数一致，禁止同步函数用 AsyncMock、`assert_awaited` 用于 sync。**核心机制**：异步函数用 `AsyncMock` + `assert_awaited`，同步函数用 `MagicMock` + `assert_called`；与 B-REVIEW-TEST-MOCK-SYNC 配合（v4.27 测试 mock 同步，本检查关注 Mock 类型匹配）。**判断信号**：grep `AsyncMock` 检查对应函数是否 async；`AssertionError: coroutines not awaited` 即违反。**修复模式**：异步用 `AsyncMock + assert_awaited`，同步用 `MagicMock + assert_called`（正确）vs 同步函数用 AsyncMock，assert_awaited 用于 sync（错误，类型不匹配）。**配置参数**：`coding_standards.mock.async_check_enabled`（默认 `true`）在 `config.yaml` 管理。**适用**：所有测试 mock；异步函数测试；同步函数测试。**不适用**：mock 对象（非函数）；属性 mock。**历史教训**：v4.28 修复前同步函数用 AsyncMock，`assert_awaited` 失败，测试报错但实际功能正常

- 🆕v4.28【强制】**B-REVIEW-150: Cookie 完整性管理（cookie integrity management）**
  - 规范引用：COOKIE-01 Cookie 完整性管理
  - 登录后必须验证关键 cookie 齐全，禁止登录后未验证 'unb' cookie 导致后续请求失败。**核心机制**：维护必要 cookie 清单（如 `[unb, _m_h5_tk, cookie2, t, _tb_token_]`），登录后校验清单完整性，缺失则报错；`import_full=true` 时必须导入完整 cookie 集而非子集；与 B-REVIEW-COOKIE-CHECK 配合（v4.1 Cookie 检查全面性，本检查关注登录后校验）。**判断信号**：grep `login.*success` 后检查是否校验 cookie 清单；登录后请求失败即违反。**修复模式**：维护必要 cookie 清单 + 登录后校验 + `import_full=true`（正确）vs 登录后未验证 'unb' cookie，导致后续请求失败（错误）。**配置参数**：`coding_standards.cookie.required_cookies`（默认 `[unb, _m_h5_tk, cookie2, t, _tb_token_]`）、`coding_standards.cookie.import_full`（默认 `true`）在 `config.yaml` 管理。**适用**：所有登录流程；cookie 导入；会话管理。**不适用**：匿名访问；公开 API。**历史教训**：v4.28 修复前登录后未验证 'unb' cookie，后续请求失败，用户误以为登录成功但功能不可用

---

### 30. 数据契约与时序（meta-rules #25-30 落地）🆕v4.29

> 本维度整合 `xianyu-hunter-dev` v4.30.0 的 meta-rules #25-30 后端侧审查要点，新增 6 项 B-REVIEW 检查点（B-REVIEW-151~156）。所有检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明。前端对应规范为 `xianyu-frontend-code-review` v4.34.0 的 F-REVIEW-110~115。

- 🆕v4.29【强制】**B-REVIEW-151: 批量断路器四要素（batch circuit breaker 4 elements）**
  - 维度：31 数据契约与时序
  - 严重等级：error
  - 规范引用：meta-rule #25 批量处理四要素
  - **检查点**：批量处理触发熔断时必须满足四要素——(1) 失败计数 + 滑动窗口双条件（`failure_threshold` + `failure_window_sec`）、(2) 进度持久化（`save_progress()`，cursor/completed_ids/remaining_ids 三键齐全）、(3) 续传入口（启动时检查 pending_marker）、(4) 日志对称（`log_phrasing.paused/stopped/failed` 三套文案与动作一致）
  - **判断信号**：
    - `grep "consecutive failure" <file>` 出现但同函数内无 `save_progress()` → 视为**必修 P0 缺陷**
    - `grep "break" <file>` 后紧跟 `mark.*skipped` 但无 `save_progress` → 视为违规
    - `grep "paused" <file>` 但实际 `return`/`break` 跳出循环 → 视为日志语义不一致
  - **配置参数**：`coding_standards.batch_circuit_breaker.failure_threshold`（默认 `3`）、`coding_standards.batch_circuit_breaker.failure_window_sec`（默认 `3600`）、`coding_standards.batch_circuit_breaker.log_phrasing`（`{paused/stopped/failed}` 三套文案）、`coding_standards.batch_circuit_breaker.mark_remaining_as`（默认 `pending`）、`coding_standards.batch_circuit_breaker.persist_keys`（默认 `[cursor, completed_ids, remaining_ids]`）在 `config.yaml` 管理
  - **适用**：批量采集、批量导入、批量上报、长任务重试
  - **不适用**：单次 API 调用、≤3 个 item 的小批量操作、性能 hot path（持久化开销不可接受）
  - **历史教训**：`batch_refresh_scheduler.py` 的 BatchRefresh#95 连续失败 3 次后 `break` 跳出循环，将剩余商品标记为 `skipped`，但**未调用 `_save_progress()`**。结果：(1) 下次启动无法加载 `remaining_ids` 触发续传；(2) 剩余商品被永久跳过且日志无任何持久化记录

- 🆕v4.29【强制】**B-REVIEW-152: 关键路径异常保留完整 traceback（critical path exception log）**
  - 维度：31 数据契约与时序
  - 严重等级：error
  - 规范引用：meta-rule #26 关键路径异常保留完整 traceback
  - **检查点**：`_on_startup` / `run_migrations` / `_init_*` / `_on_close` / `_shutdown` / `_register_signal_handlers` 外层 except **必须**使用 `logger.exception()` 输出完整 traceback，**禁止** `logger.warning(f"...{e}")` 丢堆栈
  - **判断信号**：
    - `grep "except Exception" <file>` 关键路径缺 `logger.exception()` → 视为违规
    - `grep "logger.warning.*f\".*{e}\"\|logger.error.*f\".*{e}\"" <file>` 在关键路径 → 视为违规
  - **配置参数**：`coding_standards.critical_path.patterns`（关键路径函数名模式列表，如 `["_on_startup", "run_migrations", "_init_db"]`）、`coding_standards.critical_path.require_logger_exception`（默认 `true`）、`coding_standards.critical_path.forbidden_log_patterns`（禁用的丢堆栈日志模式正则）在 `config.yaml` 管理
  - **适用**：启动钩子、迁移函数、初始化函数、关闭钩子、信号处理器注册
  - **不适用**：常规业务函数（用 `logger.error(f"...{e}")` 即可）、测试代码、性能 hot path
  - **历史教训**：`run_migrations()` 用外层 `try/except Exception as e: logger.warning(f"迁移失败: {e}")` → 后续 5 个迁移块 C-01~C-05 全部跳过（异常被吞）→ 启动时表缺列触发 `OperationalError: no such column`

- 🆕v4.29【强制】**B-REVIEW-153: datetime 统一时区策略（datetime timezone strategy）**
  - 维度：31 数据契约与时序
  - 严重等级：warning
  - 规范引用：meta-rule #27 datetime 统一时区策略
  - **检查点**：涉及跨时区/跨进程/跨服务的 `datetime` 算术与序列化必须满足——(1) 存储一律 UTC（`datetime.now(timezone.utc)`），(2) 算术前显式 unify tzinfo（与 DB naive 算术用 `_utcnow().replace(tzinfo=None)`），(3) 序列化时显式带 tzinfo（ISO 8601 with tz）
  - **判断信号**：
    - `grep "datetime.now()" <file>` 无 `tzinfo` 参数 → 视为违规
    - `grep "datetime.utcnow()" <file>` → 视为**反模式**（Python 3.12+ 弃用）
    - `grep "\.isoformat()\[:19\]" <file>` → 视为序列化不规范
  - **配置参数**：`coding_standards.datetime.storage_timezone`（默认 `UTC`）、`coding_standards.datetime.preferred_now`（默认 `datetime.now(timezone.utc)`）、`coding_standards.datetime.forbidden_now_patterns`（禁用的 now 模式正则）、`coding_standards.datetime.serialization_format`（默认 `iso8601_with_tz`）、`coding_standards.datetime.naive_unify_helper`（默认 `_utcnow().replace(tzinfo=None)`）在 `config.yaml` 管理
  - **适用**：所有 `created_at` / `updated_at` / `expires_at` 字段的算术运算、跨服务时间比较、ISO 序列化
  - **不适用**：纯展示（前端用 `dayjs` 解析）、同函数内的 local variable 计算、纯日期不含时间
  - **历史教训**：`repo_chatbot.py:478` 报 `TypeError: can't subtract offset-naive and offset-aware datetimes`：`datetime.utcnow() - row.created_at`，其中 `row.created_at` 是 SQLAlchemy 从 SQLite 读出的 naive datetime。修复：用 `_utcnow().replace(tzinfo=None) - row.created_at` 统一为 naive

- 🆕v4.29【强制】**B-REVIEW-154: 跨进程状态同步六步法（cross-process state sync 6 steps）**
  - 维度：31 数据契约与时序
  - 严重等级：warning
  - 规范引用：meta-rule #28 跨进程状态同步六步法
  - **检查点**：需要多源写入的状态（如 Cookie 多层管理）必须满足六步——(1) 写端：业务变更后写状态 + 写 `pending_marker`、(2) 同步端：独立调度器扫描 marker、(3) 读端：仅读最新状态、(4) 启动时：检查未处理 marker 强制触发同步、(5) 异常时：保留 marker 不删除、(6) 配置：同步开关/间隔/批次大小均通过配置
  - **判断信号**：
    - `grep "write_marker" <file>` 但无 `scan_marker` 同步器 → 视为违规（marker 永不被消费）
    - 启动函数（匹配 `critical_path_patterns`）无 `process_pending_markers` 但有 marker 写入端 → 视为违规（重启时积压 marker 丢失）
    - `grep "os.unlink.*marker" <file>` 在 try 块内但无异常分支 → 视为违规（失败时 marker 丢失）
  - **配置参数**：`coding_standards.state_sync_marker.marker_dir`（默认 `data/markers`）、`coding_standards.state_sync_marker.startup_check_required`（默认 `true`）、`coding_standards.state_sync_marker.scan_interval_sec`（默认 `60`）、`coding_standards.state_sync_marker.max_retry_count`（默认 `5`）、`coding_standards.state_sync_marker.marker_format`（默认 `{category}_{user_id}_{timestamp}.json`）在 `config.yaml` 管理
  - **适用**：Cookie 多层同步、配置变更广播、跨 Tab 状态共享、用户偏好同步
  - **不适用**：单写单读的临时状态、纯 UI 状态、性能 hot path、无跨进程边界的纯函数计算
  - **历史教训**：Cookie 自愈系统涉及 3 个写端（`auth_helper.py` / `browser_login.py` / 外部 API 调用）与 1 个同步器（`cookie_sync_scheduler.py`）。修复前：写端无 marker → 同步器无法被触发；启动时不检查 marker → 重启时积压 marker 永久丢失。修复：补全 6 步后，Cookie 自愈成功率从 65% 提升到 92%

- 🆕v4.29【强制】**B-REVIEW-155: 前后端错误码契约（frontend-backend error code contract）**
  - 维度：31 数据契约与时序
  - 严重等级：warning
  - 规范引用：meta-rule #29 前端错误按 error_code 分支
  - **检查点**：`raise HTTPException` 必须包含 `error_code` 字段（来自 `reason_enum`），错误响应统一结构为 `{ "error_code": "<reason>", "user_message": "<人类可读>", "detail": "<技术细节>" }`。`reason_enum` 包含 `token_expired/anti_crawler/page_unavailable/rate_limited/login_expired/session_invalid/permission_denied/validation_error/internal_error/service_unavailable`
  - **判断信号**：
    - `grep "raise HTTPException" <file>` 无 `error_code` 字段 → 视为违规
    - 后端响应缺 `error_code` 字段 → 视为**必修 P0 缺陷**（前端无法分支）
  - **配置参数**：`coding_standards.error_code.reason_enum`（10 个 reason 值列表）、`coding_standards.error_code.response_schema`（字段定义）、`coding_standards.error_code.require_in_http_exception`（默认 `true`）在 `config.yaml` 管理
  - **适用**：所有后端 4xx/5xx 响应（除 401/440/441 走认证拦截器外）
  - **不适用**：开发环境 `console.error`、本地输入校验、HTTP 5xx 网络层错误
  - **历史教训**：多个前端组件用 `if (err.message.includes('expired'))` 判断 Cookie 过期 → 后端文案从「登录已过期」改为「会话已失效」后，所有页面判断失效，统一显示「未知错误」。修复：建立前后端 `error_code` 契约，前端 `switch` 分支

- 🆕v4.29【强制】**B-REVIEW-156: 业务关键字常量集中管理（business keyword centralization）**
  - 维度：31 数据契约与时序
  - 严重等级：warning
  - 规范引用：meta-rule #30 业务关键字常量集中管理
  - **检查点**：业务关键字（已售、已删除、宝贝不存在等需正则匹配/includes 判断的字符串）必须集中到 `config.yaml#business_keywords` 或专用常量文件，业务代码中禁止硬编码关键字字符串
  - **判断信号**：
    - `grep "['\"](已售|已删除|宝贝不存在|卖掉了|已售罄)['\"]" src/xianyu_hunter/` → 视为硬编码（应从 config 读）
    - 业务代码 `grep "if.*['\"].*['\"].*in.*text" <file>` → 视为可能硬编码
  - **配置参数**：`coding_standards.business_keyword.sold`（已售关键字列表）、`coding_standards.business_keyword.deleted`（已删除关键字列表）、`coding_standards.business_keyword.frontend_constants_file`（前端常量文件路径）、`coding_standards.business_keyword.consistency_test`（前后端一致性测试路径）在 `config.yaml` 管理
  - **适用**：商品状态识别（已售/已删/在售）、错误提示文案匹配、风控标签识别、敏感词过滤
  - **不适用**：日志/异常消息中的自由文本、配置文件中的连接信息、测试用例中的 mock 数据
  - **历史教训**：Cookie 自愈系统的 `sold` 关键字集合在 3 处独立维护，新增「宝贝走丢了」时只更新了 2 处，第 3 处漏更新导致「已售商品」被误判为「在售」继续抢单。修复：抽取到 `config.yaml#business_keywords.sold` 集中管理

---

### 31. 业务关键字常量集中管理与跨端契约对齐 🆕v4.31

> 本维度整合 v4.29 step 129-133 的后端侧审查要点，新增 5 项 B-REVIEW 检查点，对应 `xianyu-hunter-dev` v4.29.0 的 step 129-133。所有检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。前端对应规范为 `xianyu-frontend-code-review` v4.31.0 的维度 27（业务关键字常量集中管理与字段名大小写敏感）。

- 🆕v4.31【强制】**B-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION：业务关键字常量集中管理**
  - 维度：31 业务关键字常量集中管理与跨端契约对齐
  - 严重等级：error
  - 规范引用：KEYWORD-CENTRAL-01 业务关键字常量集中管理
  - **检查点**：外部平台文本特征（已售/已下单/区域/状态文案）必须集中到单一模块的 `*_TEXT_KEYWORDS` 常量，业务代码必须通过统一访问函数（如 `check_text_sold`）调用，**禁止**在各业务文件内散落中文字面量
  - **判断信号**：
    - `grep "已售\|已下架\|卖掉了" src/xianyu_hunter/` 中文字面量散落多个文件 → 视为违规
    - `grep "in text" src/xianyu_hunter/` 出现内联关键字判断而非调用统一函数 → 视为可疑
    - 多个文件维护同一业务概念的关键字列表 → 视为违规
  - **配置参数**：`business_keyword_centralization.keyword_categories`（关键字分类清单，如 `["sold", "ordered", "region"]`）、`business_keyword_centralization.centralized_module`（集中模块路径，如 `collector_utils.py`）、`business_keyword_centralization.unified_function_pattern`（统一访问函数命名模式，如 `check_text_*`）、`business_keyword_centralization.forbidden_inline_patterns`（禁止的内联判断模式，如 `any\(kw in text for kw in`）在 `config.yaml` 的 `business_keyword_centralization` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` step 129
  - **适用**：外部平台文本特征识别（已售/已下单/区域/状态文案）、第三方系统响应文案解析、任何需要全链路同步更新的关键字常量
  - **不适用**：框架内部固定文案（如 antd 默认 placeholder）、单次使用的字符串字面量（无复用需求）、协议固定值（如 HTTP method）
  - **历史教训**：闲鱼前端将「已售」文案改为「卖掉了」，但 `SOLD_TEXT_KEYWORDS` 只在 `_detail.py` 部分文件中维护，`_parser.py` 和 `buyer.py` 未同步更新，导致商品 1058031608014 已售但状态未采集。修复：抽取统一 `SOLD_TEXT_KEYWORDS` 常量和 `check_text_sold()` 函数到 `collector_utils.py`，三个文件统一调用

- 🆕v4.31【强制】**B-REVIEW-EVENT-TYPE-EXACT-MATCH：事件类型过滤精确匹配**
  - 维度：31 业务关键字常量集中管理与跨端契约对齐
  - 严重等级：error
  - 规范引用：EVENT-MATCH-01 事件类型过滤精确匹配
  - **检查点**：业务查询事件类型时必须用 `==` 精确匹配，**禁止**用 `startswith` / `endswith` / `in` 做前缀/后缀/子串过滤（统计聚合场景除外）；通知事件与业务事件必须使用不同的 type 前缀或命名空间
  - **判断信号**：
    - `grep "startswith\|endswith" src/xianyu_hunter/` 出现在事件/记录过滤逻辑中 → 视为可疑
    - 业务列表混入 `payload=None` 的空记录 → 必然违规
    - 事件 type 命名空间冲突（通知事件与业务事件同前缀，如 `eval.passed` 通知事件与 `eval.scored` 业务事件同前缀）→ 视为违规
  - **配置参数**：`event_type_exact_match.forbidden_prefix_patterns`（禁止的前缀过滤模式，如 `startswith\(['\"]\w+\.`）、`event_type_exact_match.required_match_pattern`（要求的精确匹配模式，如 `==` / `Set.has()` / `switch.*case`）、`event_type_exact_match.allowed_prefix_grouping_scenarios`（允许前缀分组场景白名单，如 `["statistics_aggregation", "log_filtering"]`）、`event_type_exact_match.event_type_categories`（事件类型分类清单，含业务事件与通知事件命名空间）在 `config.yaml` 的 `event_type_exact_match` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` step 130
  - **适用**：业务事件查询（评估明细/订单列表/任务列表）、KPI 统计（按事件类型计数）、事件订阅（EventBus 订阅特定事件）
  - **不适用**：全量事件导出（无需过滤）、日志搜索（模糊匹配是预期行为）、调试查询（临时性，非生产代码）
  - **历史教训**：`NotifierHub` 写入 `type='eval.passed'`、`payload=None` 的事件用于 KPI 统计，但 `api_evaluations.py` 用 `startswith('eval.')` 过滤评估明细列表，误包含 227+ 条通知事件，用户看到「213 条仅基于价格的评估记录」和大量空行。修复：将过滤条件改为 `== 'eval.scored'`，评估明细从 280 条减到 47 条有效记录

- 🆕v4.31【强制】**B-REVIEW-FIELD-NAME-CASE-SENSITIVE：前后端字段名大小写敏感检查**
  - 维度：31 业务关键字常量集中管理与跨端契约对齐
  - 严重等级：error
  - 规范引用：FIELD-CASE-01 前后端字段名大小写敏感检查
  - **检查点**：Python 类私有属性命名（`_session` vs `_Session`）和 API 字段名（`total_for_type` vs `totalForType`）必须在赋值和引用处严格大小写一致，API 响应字段名必须前后端严格一致（含大小写、下划线、前后缀）
  - **判断信号**：
    - `grep "_[A-Z]" src/xianyu_hunter/` 出现大写开头的私有属性 → 视为可疑（Python 约定为小写）
    - 后端返回字段名与前端 types.ts 字段名不一致（含大小写差异）→ 视为违规
    - 前端用 `as any` / `as unknown as` 绕过字段名检查 → 视为违规
  - **配置参数**：`field_name_case_sensitive.backend_field_naming_style`（后端字段命名风格，默认 `snake_case`）、`field_name_case_sensitive.forbidden_bypass_patterns`（禁止的绕过模式，如 `as\s+any\b` / `as\s+unknown\s+as`）、`field_name_case_sensitive.known_case_sensitive_fields`（已知大小写敏感字段清单，含 `backend` 与 `frontend_wrong` 对照）、`field_name_case_sensitive.bidirectional_match_required`（是否要求前后端双向 grep 匹配，默认 `true`）在 `config.yaml` 的 `field_name_case_sensitive` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` step 131
  - **适用**：Python 类私有属性（`_xxx` 命名）、API 请求/响应字段名（前后端契约）、DB schema 字段名与 ORM model 字段名对齐、TypeScript interface 与 Python Pydantic model 字段对齐
  - **不适用**：框架内置属性（如 `__init__`/`__str__`，由 Python 规范保证）、第三方库字段名（无法控制）
  - **历史教训**：`api_chatbot_config.py` line 343 使用 `self._Session()` 但类中定义的是 `self._session`（小写 s），运行时抛 `AttributeError: 'ChatbotRepository' object has no attribute '_Session'`；`api_task_links.py` 返回 `total` 字段，但前端 `ItemList.tsx` 期望 `total_for_type`，导致前端「0 条」显示

- 🆕v4.31【强制】**B-REVIEW-SERVICE-RESTART-VERIFICATION：服务重启验证清单**
  - 维度：31 业务关键字常量集中管理与跨端契约对齐
  - 严重等级：warning
  - 规范引用：RESTART-01 服务重启验证清单
  - **检查点**：Python 后端代码修改后必须重启服务（除非启用 `--reload`），重启后必须按清单验证服务状态（端口监听/健康检查/关键数据状态/启动日志无异常）
  - **判断信号**：
    - 代码 review 中修改了 `.py` 文件但未提供重启命令 → 视为可疑
    - 用户反馈「修复无效」但代码已修复 → 必然未重启服务
    - 重启后未验证端口监听 → 视为可疑
    - 重启后未查看启动日志确认无 `ImportError`/`OperationalError`/`AttributeError` → 视为可疑
  - **配置参数**：`post_restart.checklist`（重启验证清单，含端口监听/健康检查/数据状态/日志确认）、`post_restart.health_check_endpoints`（健康检查端点清单，如 `/api/about`/`/api/tasks`/`/api/scheduler/status`）、`post_restart.startup_log_keywords`（启动日志关键词，如 `Application startup complete`/`Scheduler started`）、`post_restart.frontend_build_required`（前端是否需要重新构建，默认 `true`）在 `config.yaml` 的 `post_restart` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` step 132
  - **适用**：Python 后端代码修改后（任何 .py 文件）、前端代码修改后（需 `npm run build` + 浏览器强制刷新）、数据库迁移后
  - **不适用**：开发模式 `--reload` 启用（自动热重载）、纯文档修改（无代码变更）、配置文件修改（部分配置支持热加载）
  - **历史教训**：修改 `api_anticrawl.py` 后未重启服务，用户反馈「会话管理仍未自动启动」，实际代码已修复但服务跑的是旧代码；重启后未验证端口监听，导致 uvicorn 启动失败但用户以为服务正常运行

- 🆕v4.31【强制】**B-REVIEW-WINDOWS-TERMINAL-ENCODING：Windows 终端编码与 Shell 语法兼容**
  - 维度：31 业务关键字常量集中管理与跨端契约对齐
  - 严重等级：warning
  - 规范引用：ENCODING-SHELL-01 Windows 终端编码与 Shell 语法兼容
  - **检查点**：Windows PowerShell 脚本必须显式设置 UTF-8 编码，命令拼接必须用 `;` 而非 `&&`，含特殊字符的参数（如 `stash@{0}`）必须加引号，Python 脚本在 Windows 环境必须显式设置 stdout 编码
  - **判断信号**：
    - `grep "cp936\|gbk" *.ps1` 出现编码硬编码 → 视为可疑
    - `grep "&&" *.ps1` PowerShell 脚本含 `&&` → 视为违规
    - `grep "stash@" *.ps1` 不加引号的 `stash@{N}` → 视为违规
    - 数据库存储中文为 `?` → 编码问题可疑
    - 日志文件中文乱码 → 编码问题可疑
  - **配置参数**：`cross_platform.encoding`（编码设置，默认 `UTF-8`）、`cross_platform.shell_quoting`（shell 参数引用规则，如 `stash@{N}` 必须加引号）、`cross_platform.path_separator`（路径分隔符处理，默认 `pathlib`/`os.path`）、`cross_platform.command_separator`（命令分隔符，PowerShell 用 `;`，Linux 用 `&&`）在 `config.yaml` 的 `cross_platform` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` step 133
  - **适用**：Windows PowerShell 脚本调用 API（含中文 body）、Python 脚本在 Windows 环境输出中文到日志、git 操作（stash/branch 等含特殊字符的参数）、跨平台部署的脚本（Windows + Linux）
  - **不适用**：Linux/Mac 环境的 shell 脚本（默认 UTF-8）、Docker 容器内脚本（容器内默认 UTF-8）、纯英文内容的脚本（无编码问题）
  - **历史教训**：外部脚本批量调用 `POST /api/chatbot/faq` 时 PowerShell 默认 cp936 编码，中文 body 被转换为 `?`，导致数据库存储 3 条乱码记录（id=1/2/3）；`git stash apply stash@{0}` 在 PowerShell 中报错「解析为哈希表」，修复：加引号 `'stash@{0}'`；`cd frontend && npm run build` 报错「`&&` 不是有效的语句分隔符」，修复：改用 `;`

---

### 32. 状态恢复与日志规范 🆕v4.30

> 本维度对应 `xianyu-hunter-dev` v4.31.0 meta-rules #31/#32，新增 2 项 B-REVIEW 检查点（B-REVIEW-157~158）。所有检查点强调配置驱动（参数在 `config.yaml` 的 `resume_policy` / `log_merge` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。前端对应规范为 `xianyu-frontend-code-review` v4.35.0 的 F-REVIEW-116（状态恢复前置校验前端侧）；前端无降级链日志场景，不新增 LOG-MERGE 对应检查点。

- 🆕v4.30【强制】**B-REVIEW-157：RESUME-PRECHECK 状态恢复前置校验**
  - 维度：32 状态恢复与日志规范
  - 严重等级：error（P0，无效循环风险）
  - 规范引用：meta-rule #31 状态恢复前置校验（pause→resume 根因消除校验）
  - **检查点**：具有 pause/resume 语义的组件（任务调度器/登录会话/连接池/断路器）在 resume 操作前必须调用 precheck 函数校验导致 pause 的 root_cause 是否已消除，未消除时拒绝恢复并返回结构化响应
  - **检查项**：
    1. 异常 pause 时必须记录 `root_cause`（含 `reason_code` + 失效层标识 + 时间戳）持久化到任务/会话状态，而非仅记日志
    2. resume 操作前必须调用 precheck 函数校验 `root_cause` 对应的前置条件是否已恢复（如 Cookie 层 valid、连接可达、配额充足）
    3. 校验失败时返回结构化拒绝 `{resume_blocked: true, reason_code, user_hint, retry_after}`，禁止静默失败或无条件放行
    4. 异常 pause 后设置冷却期（`config.yaml#resume_policy.cooldown_seconds`），期间拒绝 resume，避免"恢复→失效→暂停"无效循环
    5. 冷却期时长、前置校验开关、`reason_code` → precheck 函数映射表均从 config 读取，禁止硬编码
  - **判断信号**：
    - `grep "def resume\|def start\|def unpause\|def activate" <file>` 缺 `precheck`/`_check_prerequisite` 调用 → 视为违规
    - `grep "pause\|paused\|should_pause"` 无 `root_cause` 字段赋值 → 视为违规（无法校验根因消除）
    - resume 接口 `grep "return.*True\|return.*ok"` 无 `if not precheck` 拒绝分支 → 视为违规（无条件放行）
    - `grep "cooldown\|cool_down"` 时长为字面量数字而非 config 引用 → 视为硬编码
  - **配置参数**：`resume_policy.cooldown_seconds`（冷却期时长，默认 300 秒）、`resume_policy.precheck_enabled`（前置校验开关，默认 true）、`resume_policy.reason_to_precheck_map`（reason_code → precheck 函数映射表，如 `{"cookie_invalid": "_check_cookie_layers_valid", "session_expired": "_check_session_active", "connection_lost": "_check_pool_alive"}`）、`resume_policy.applicable_components`（适用组件清单，如 `["task_scheduler", "login_session", "connection_pool", "circuit_breaker"]`）在 `config.yaml` 的 `resume_policy` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.31.0 meta-rules #31
  - **适用**：任务调度器 pause/resume（如搜索任务会话失效暂停）、登录会话失效/恢复（Cookie 层失效后重新登录）、连接池断连/重连、断路器开/闭、限流配额耗尽/恢复
  - **不适用**：用户主动 pause（非异常触发，无 root_cause）、一次性任务（无 resume 语义）、纯函数重试（无状态持久化）、开发调试手动 resume
  - **历史教训**：搜索任务 `t68bc149b` 因闲鱼会话失效（RGV587_ERROR）被自动暂停后，用户/系统在 30 分钟内连续 4 次恢复任务，但 Cookie 未重新登录刷新，每次恢复后 13~22 秒内再次触发会话失效检测并暂停，形成"恢复→失效→暂停"无效循环，浪费浏览器资源并产生 555 条冗余 WARNING。修复：resume 前校验 `cookie_rotator` 的 identity/session 层 `valid` 状态，失效时拒绝恢复并提示"请先重新登录闲鱼"；异常 pause 后设 5 分钟冷却期（config 可配），彻底消除无效循环

- 🆕v4.30【强制】**B-REVIEW-158：LOG-MERGE 多阶段降级链日志合并**
  - 维度：32 状态恢复与日志规范
  - 严重等级：warning（P1，可观测性噪音）
  - 规范引用：meta-rule #32 多阶段降级链日志合并
  - **检查点**：同一逻辑链的多个中间阶段（降级/重试/回退/多策略尝试）日志必须合并为 1 条结构化结果日志（WARNING/ERROR），中间步骤使用 `logger.debug()`，禁止每个中间步骤独立输出 WARNING
  - **检查项**：
    1. 降级/重试链的中间步骤（如"尝试刷新 token""尝试 DOM 回退"）使用 `logger.debug()`，最终结果使用 `logger.warning()` 或 `logger.error()`
    2. 最终结果日志必须含结构化 `extra` 字段：`{stages: [...], final_reason, keyword/context, attempts}`，其中 `stages` 为各中间步骤的简述数组
    3. 同一逻辑链内 ≥2 个阶段则必须合并（`config.yaml#log_merge.min_stages_to_merge` 可配），单阶段无需合并
    4. 合并阈值、中间步骤 DEBUG 开关、保留的中间步骤白名单均从 config 读取，禁止硬编码
  - **判断信号**：
    - `grep -c "logger.warning" <file>` 同一函数内 ≥3 条且属于同一 try/降级链 → 视为违规（应合并为 1 条）
    - `grep "logger.warning.*尝试\|logger.warning.*刷新\|logger.warning.*回退\|logger.warning.*重试" <file>` 多条且无结构化合并 → 视为冗余告警
    - 降级链结果日志 `grep "logger.warning"` 缺 `extra=` 参数 → 视为不规范（无法聚合分析）
    - 合并阈值硬编码为字面量数字 → 视为违规（应从 config 读）
  - **配置参数**：`log_merge.min_stages_to_merge`（合并阈值，默认 2，≥该值则必须合并）、`log_merge.intermediate_step_level`（中间步骤日志级别，默认 `debug`）、`log_merge.result_level`（结果日志级别，默认 `warning`）、`log_merge.required_extra_fields`（结果日志必须包含的 extra 字段，如 `["stages", "final_reason", "keyword", "attempts"]`）、`log_merge.whitelist_intermediate_warning`（保留为 WARNING 的中间步骤白名单，默认空）在 `config.yaml` 的 `log_merge` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.31.0 meta-rules #32
  - **适用**：降级链（API→DOM→缓存）、重试链（指数退避多轮）、多策略回退（多 selector 候选）、浏览器自动化多策略尝试、批处理多阶段校验
  - **不适用**：独立的一次性告警（不同业务流程）、用户操作触发的即时反馈、关键路径异常的 `logger.exception()`（需完整堆栈）、不同函数/模块的告警
  - **历史教训**：搜索 API 会话失效时，`_search.py` 在同一次搜索失败中输出 5 条 WARNING（FAIL_SYS_ILLEGAL_ACCESS → 尝试强制刷新 _m_h5_tk → 刷新失败 → 尝试 DOM 回退 → DOM 回退超时），单次搜索失效产生 5 条噪音日志，12 小时内累积 555 条冗余 WARNING（占总 WARNING 88%），淹没真正需要关注的告警。修复：中间步骤降为 DEBUG，最终合并为 1 条结构化 WARNING（含 `stages`/`final_reason`/`keyword`），告警量从 628 降至 ~80，可观测性显著提升

---

### 33. 修复前全链路根因扫描协议 🆕v4.31

> 本维度对应 `xianyu-hunter-dev` v4.32.0 meta-rule #34，新增 1 项 B-REVIEW 检查点（B-REVIEW-160）。所有检查点强调配置驱动（参数在 `config.yaml` 的 `root_cause_chain_check` 节点管理，不硬编码）与适用/不适用场景说明。前端对应规范为 `xianyu-frontend-code-review` v4.36.0 的 F-REVIEW-118。

- 🆕v4.31【强制】**B-REVIEW-160：ROOT-CAUSE-CHAIN-CHECK 修复前全链路根因扫描协议**
  - 维度：33 修复前全链路根因扫描协议
  - 严重等级：error（P0，修复漏根因风险）
  - 规范引用：meta-rule #34 修复前全链路根因扫描协议
  - **检查点**：修复非平凡 bug 前必须先列 ≥3 个根因覆盖用户层/接口层/数据层/配置层/历史层；PR 描述必须含"≥3 根因列表"段；git diff 涉及 ≥3 个无关文件视为违反最小修改原则；新增逻辑无 unit test 视为 WARNING
  - **检查项**：
    1. 修复前必须列出 ≥3 个候选根因，覆盖用户层/接口层/数据层/配置层/历史层 5 个维度
    2. PR 描述必含"≥3 根因列表"段 + 验证工具 + 最小修改清单 + 全链路反查 + 防回归测试
    3. git diff 涉及 ≥3 个无关文件视为违反最小修改原则（WARNING）
    4. 新增逻辑无 unit test 视为 WARNING
    5. 链式检查 5 维度 menu_registry/router/page/api_wrapper/backend_endpoint 与 B-REVIEW-159 5 层契约呼应
  - **判断信号**：
    - `git diff --name-only | wc -l` ≥ 3 个无关文件 → 视为违规
    - PR 描述 `grep "根因列表\|root cause"` 缺失 → 视为违规
    - 新增函数 `grep "def test_"` 无对应测试 → 视为 WARNING
  - **配置参数**：`root_cause_chain_check.min_root_causes`（最小根因数，默认 3）、`root_cause_chain_check.coverage_layers`（必须覆盖的层，默认 `["user", "api", "data", "config", "history"]`）、`root_cause_chain_check.max_unrelated_files`（最大无关文件数，默认 3）、`root_cause_chain_check.require_unit_test`（新增逻辑是否必须含 unit test，默认 true）在 `config.yaml` 的 `root_cause_chain_check` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.32.0 meta-rule #34
  - **适用**：非平凡 bug 修复（≥2 个根因可能）、跨层级问题（前端+后端+DB）、回归 bug（修复过但又复发）、生产事故复盘
  - **不适用**：typo/文案修改（单根因明确）、单测失败修复（根因在测试代码）、配置调整（无代码变更）、首次开发新功能（无 bug 历史）
  - **历史教训**：通知中心菜单点击无反应问题，初次修复仅改前端 Route，未发现后端 endpoint 也不存在，导致修复后仍无法访问；按 ≥3 根因列表扫描后发现 5 层契约缺 3 层（router/page/api_wrapper/backend_endpoint），逐层补齐才彻底修复

---

### 34. 前后端字段契约单一可信源 🆕v4.31

> 本维度对应 `xianyu-hunter-dev` v4.32.0 meta-rule #35，新增 1 项 B-REVIEW 检查点（B-REVIEW-161）。所有检查点强调配置驱动（参数在 `config.yaml` 的 `contract_owner_marker` 节点管理，不硬编码）与适用/不适用场景说明。前端对应规范为 `xianyu-frontend-code-review` v4.36.0 的 F-REVIEW-119。

- 🆕v4.31【强制】**B-REVIEW-161：CONTRACT-OWNER-MARKER 前后端字段契约单一可信源**
  - 维度：34 前后端字段契约单一可信源
  - 严重等级：error（P0，前后端字段漂移风险）
  - 规范引用：meta-rule #35 前后端字段契约单一可信源
  - **检查点**：后端 Pydantic/DB Row 字段 = 权威源；后端 `BaseModel` 字段必须显式标注 `@field_validator` / `Field(..., description=...)` 标明"权威源"角色；后端字段变更必须同步通知前端 + 在 `contract_owner_marker` 节点更新 `affected_frontend_types_files` 列表；snake_case 严格透传禁止转 camelCase
  - **检查项**：
    1. 后端 `BaseModel` 字段必须显式标注 `@field_validator` 或 `Field(..., description=...)` 标明"权威源"角色
    2. 后端字段变更必须同步通知前端 + 在 `contract_owner_marker` 节点更新 `affected_frontend_types_files` 列表
    3. snake_case 严格透传禁止转 camelCase（命名漂移检测：后端 `xxx_yyy` + 前端 `xxxYyy` = CRITICAL）
    4. 前端 `types.ts` 字段必须与后端 `BaseModel` 字段一一对齐（含可选/必填/默认值）
    5. 后端字段废弃必须先标 `deprecated` 注释，1 个版本后再删除
  - **判断信号**：
    - `grep "class.*BaseModel" <file>` 后检查字段是否含 `Field(..., description=...)` → 缺失视为违规
    - 后端 `xxx_yyy` 字段 vs 前端 `xxxYyy` 字段 → 视为命名漂移（CRITICAL）
    - `grep "camelCase\|to_camel\|camelize"` 在序列化路径 → 视为违规
  - **配置参数**：`contract_owner_marker.authority_source`（权威源标识，默认 `"backend"`）、`contract_owner_marker.required_marker_fields`（必须标注的字段，如 `["id", "user_id", "created_at", "updated_at"]`）、`contract_owner_marker.affected_frontend_types_files`（受影响前端 types 文件列表）、`contract_owner_marker.naming_drift_patterns`（命名漂移模式库，如 `["snake_case_to_camelCase", "snake_case_to_PascalCase"]`）、`contract_owner_marker.deprecation_grace_versions`（废弃字段保留版本数，默认 1）在 `config.yaml` 的 `contract_owner_marker` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.32.0 meta-rule #35
  - **适用**：所有后端 `BaseModel`/DB Row 字段定义、前后端 API 契约接口、跨端字段映射、字段废弃流程
  - **不适用**：内部数据结构（不向前端暴露）、临时调试字段、测试 mock 数据、纯前端 UI 状态字段
  - **历史教训**：通知中心前后端字段不对齐，后端 `NotificationRow.read_at` 字段 vs 前端 `Notification.readAt` 字段，导致前端始终读 `undefined`，通知状态永远显示"未读"

---

### 35. 列表聚合与状态联动 🆕v4.34

> 本维度对应 `xianyu-hunter-dev` v4.34.0 meta-rules #38-42，新增 5 项 B-REVIEW 检查点（B-REVIEW-164~168）。同时整合 v4.33 规范治理（B-REVIEW-162/163，meta-rules #36-37）。所有检查点强调配置驱动（参数在 `config.yaml` 的 `meta_rules_38_42` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。前端对应规范为 `xianyu-frontend-code-review` v4.38.0 的 F-REVIEW-122~126。

- 🆕v4.33【强制】**B-REVIEW-162：SEDIMENTATION-THRESHOLD 规范立项前置计数**
  - 维度：35 编码规范防御性复盘
  - 严重等级：major（P1，过度规范化风险）
  - 规范引用：meta-rule #36 规范沉淀门槛（防过度规范化）
  - **检查点**：新立 meta-rule/step/B-REVIEW 必须满足 ≥3 个相似 bug 门槛，单一 bug 立规范需标 experimental 标签 + 1 季度观察期，安全/数据丢失/付费受损豁免
  - **配置参数**：`meta_rules_governance.sedimentation_threshold`（默认 3）、`meta_rules_governance.sedimentation_time_window_months`（默认 6）、`meta_rules_governance.experimental_observation_quarters`（默认 1）、`meta_rules_governance.sedimentation_exemption_categories`（默认 `["security_vulnerability", "data_loss", "payment_damage"]`）在 `config.yaml` 的 `meta_rules_governance` 节点管理
  - **适用**：所有新立 meta-rule/step/B-REVIEW 检查点
  - **不适用**：安全漏洞/数据丢失/付费受损豁免类别（无需 ≥3 次即可立即立规范）

- 🆕v4.33【建议】**B-REVIEW-163：DEGRADATION-CLEANUP 规范退化清理**
  - 维度：35 编码规范防御性复盘
  - 严重等级：minor（P2，规范膨胀风险）
  - 规范引用：meta-rule #37 规范退化机制（防规范膨胀）
  - **检查点**：利用率 < 3 次/季度则标记待合并/待废弃，1 季度观察期后废弃并移入 version-history.md Deprecated 章节，安全类规范永不退化
  - **配置参数**：`meta_rules_governance.degradation_threshold`（默认 3）、`meta_rules_governance.observation_period_quarters`（默认 1）、`meta_rules_governance.degradation_exemption_categories`（默认 `["security", "config_driven"]`）在 `config.yaml` 的 `meta_rules_governance` 节点管理
  - **适用**：所有已立的 meta-rule/step/B-REVIEW 检查点
  - **不适用**：安全类规范（永不退化）、config_driven 类规范（依赖 config 存在）

- 🆕v4.34【强制】**B-REVIEW-164：GLOBAL-AGGREGATE-TASK-FILTER 全局聚合任务级过滤**
  - 维度：19 API 设计规范 / 35 列表聚合与状态联动
  - 严重等级：critical（P0，越界数据风险）
  - 规范引用：meta-rule #38 全局聚合任务级过滤
  - **检查点**：全局视图（无 task_id）列表查询必须按各任务个体配置范围过滤，禁止只用全局默认范围；必须实现 `_filter_by_per_task_range` 类似函数按各任务个体 price_range/market_ratio 过滤
  - **检查项**：
    1. 全局视图（无 task_id）列表查询必须调用 `_filter_by_per_task_range` 按各任务个体配置范围过滤
    2. 禁止只用全局默认范围（如全局 min/max）过滤所有任务的数据
    3. 各任务的个体配置范围（price_range/market_ratio）必须从 task config 读取
    4. 过滤后数据不得超出任一任务的个体配置范围
  - **判断信号**：
    - `grep "task_id.*None" <file>` 但无 `_filter_by_per_task` 调用 → 视为违规
    - `grep "global_min\\|global_max" <file>` 在列表查询函数 → 视为违规
  - **反模式**：
    ```python
    def list_evaluations(task_id: str | None = None):
        # 全局视图只用全局默认范围，未按各任务个体配置过滤
        items = db.query(...).filter(Item.price >= global_min, Item.price <= global_max).all()
        return items
    ```
  - **正确模式**：
    ```python
    def list_evaluations(task_id: str | None = None):
        items = db.query(...).all()
        if task_id is None:
            # 全局视图按各任务个体配置范围过滤
            items = _filter_by_per_task_range(items, task_configs)
        return items
    ```
  - **配置参数**：`meta_rules_38_42.global_aggregate_filter.enabled`（默认 true）、`meta_rules_38_42.global_aggregate_filter.severity`（默认 CRITICAL）、`meta_rules_38_42.global_aggregate_filter.required_filter_function`（默认 `"_filter_by_per_task_range"`）、`meta_rules_38_42.global_aggregate_filter.task_config_fields`（默认 `["price_range", "market_ratio"]`）在 `config.yaml` 的 `meta_rules_38_42.global_aggregate_filter` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #38 step 184
  - **适用**：全局视图列表查询（无 task_id 参数）、跨任务聚合查询、Dashboard 全局统计
  - **不适用**：指定 task_id 的列表查询、单一任务详情页、无配置范围的全局统计
  - **历史教训**：`evaluations_list.py` 全局视图只用全局默认 price_range 过滤，导致 task 上限 800 的商品在"捡漏价格参考"中显示 ¥2,988.00 越界数据

- 🆕v4.34【强制】**B-REVIEW-165：LIST-CROSS-DOMAIN-INJECT 列表交叉数据批量注入**
  - 维度：8 性能 / 35 列表聚合与状态联动
  - 严重等级：warning（P1，性能退化风险）
  - 规范引用：meta-rule #39 列表交叉数据批量注入
  - **检查点**：列表交叉其他数据源必须批量查询 + TTL 缓存，禁止 N+1 单条查询；批量查询函数签名必须接受 `list[str]` 参数返回 `dict[str, T]` 映射
  - **检查项**：
    1. 列表交叉其他数据源（如 items 交叉 prices）必须用批量查询（`WHERE id IN (...)`）
    2. 批量查询结果必须用 TTL 缓存（默认 5 分钟），缓存 key 含数据源标识
    3. 禁止在循环中单条查询（`for item in items: db.query(...).filter(id == item.id)`）
    4. 批量查询函数签名必须接受 `list[str]` 参数返回 `dict[str, T]` 映射
  - **判断信号**：
    - `grep "for.*in.*items:" <file>` 后跟 `db.query` 单条查询 → 视为违规
    - `grep "db.query.*filter.*==.*item\\." <file>` 在循环内 → 视为违规
  - **反模式**：
    ```python
    def list_items_with_prices(item_ids: list[str]):
        result = []
        for item_id in item_ids:
            price = db.query(Price).filter(Price.item_id == item_id).first()  # N+1 查询
            result.append({"item": item, "price": price})
        return result
    ```
  - **正确模式**：
    ```python
    def list_items_with_prices(item_ids: list[str]):
        prices = _batch_load_prices(item_ids)  # 批量查询 + TTL 缓存
        return [{"item": item, "price": prices.get(item.id)} for item in items]
    ```
  - **配置参数**：`meta_rules_38_42.cross_domain_inject.enabled`（默认 true）、`meta_rules_38_42.cross_domain_inject.severity`（默认 WARNING）、`meta_rules_38_42.cross_domain_inject.cache_ttl_seconds`（默认 300）、`meta_rules_38_42.cross_domain_inject.batch_size_limit`（默认 500）、`meta_rules_38_42.cross_domain_inject.forbidden_loop_patterns`（默认 `["for.*in.*items:.*db.query"]`）在 `config.yaml` 的 `meta_rules_38_42.cross_domain_inject` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #39 step 185
  - **适用**：列表交叉数据源（items × prices、tasks × configs、orders × users）、Dashboard 聚合查询、批量统计
  - **不适用**：单条详情查询（无交叉）、实时性要求高的查询（缓存不一致）、小批量（≤3 个）查询
  - **历史教训**：`price_dashboard.py` 在循环中单条查询每个 item 的 price，100 个 item 触发 100 次 DB 查询，批量查询 + TTL 缓存后降至 1 次

- 🆕v4.34【强制】**B-REVIEW-166：MULTI-FIELD-LINKED-SWITCH 多字段联动开关范式**
  - 维度：11 错误处理 / 14 配置管理 / 35 列表聚合与状态联动
  - 严重等级：major（P1，逻辑错误风险）
  - 规范引用：meta-rule #40 多字段联动开关范式
  - **检查点**：联动字段必须声明「主开关→过滤器」优先级矩阵，主开关失效时子过滤器自动禁用；mode 是主开关，*_bargain_only 是过滤器
  - **检查项**：
    1. 联动字段（如 mode + bargain_only）必须声明优先级矩阵注释
    2. 主开关（mode）失效时子过滤器（*_bargain_only）自动禁用
    3. 子过滤器不得独立于主开关生效（如 mode=notify 时 bargain_only 不得过滤）
    4. 优先级矩阵必须从 config 读取，禁止硬编码
  - **判断信号**：
    - `grep "mode.*notify\\|mode.*auto_buy" <file>` 但无优先级矩阵注释 → 视为违规
    - `grep "bargain_only" <file>` 但无 `if mode ==` 前置判断 → 视为违规
  - **反模式**：
    ```python
    # 无优先级矩阵，bargain_only 在 mode=notify 时仍过滤
    if item.bargain_only and not _is_bargain(item):
        continue
    ```
  - **正确模式**：
    ```python
    # 优先级矩阵：mode 是主开关，*_bargain_only 是过滤器
    # mode=auto_buy: bargain_only 生效；mode=semi_auto: bargain_only 生效；mode=notify: bargain_only 不生效
    if mode in ("auto_buy", "semi_auto") and item.bargain_only and not _is_bargain(item):
        continue
    ```
  - **配置参数**：`meta_rules_38_42.linked_switch_priority.enabled`（默认 true）、`meta_rules_38_42.linked_switch_priority.severity`（默认 MAJOR）、`meta_rules_38_42.linked_switch_priority.main_switch_field`（默认 `"mode"`）、`meta_rules_38_42.linked_switch_priority.filter_suffix`（默认 `"_bargain_only"`）、`meta_rules_38_42.linked_switch_priority.priority_matrix`（默认 `{"auto_buy": "filter_active", "semi_auto": "filter_active", "notify": "filter_disabled"}`）在 `config.yaml` 的 `meta_rules_38_42.linked_switch_priority` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #40 step 186
  - **适用**：联动字段场景（mode + bargain_only、enabled + threshold、auto + limit）、配置驱动的业务逻辑、多字段组合判断
  - **不适用**：独立字段（无联动关系）、单一开关（无子过滤器）、运行时动态字段（无固定优先级）
  - **历史教训**：TaskEditor 中 mode=notify 时 bargain_only 仍过滤，导致通知模式下用户看不到符合条件的商品

- 🆕v4.34【强制】**B-REVIEW-167：RESUME-PRECHECK-STRUCTURED 状态恢复前置校验结构化响应**
  - 维度：11 错误处理 / 9 异步与调度器 / 35 列表聚合与状态联动
  - 严重等级：critical（P0，API 层处理困难风险）
  - 规范引用：meta-rule #41 状态恢复前置校验结构化响应
  - **检查点**：precheck 必须返回 5 字段结构化 dict `{resume_blocked, reason_code, user_hint, retry_after, task_registered}` 不抛异常，API 层直接透传；自定义 ResumeBlockedError 异常在 API 层转换为 400 响应
  - **检查项**：
    1. precheck 函数必须返回 5 字段结构化 dict（不抛异常）
    2. 5 字段：`resume_blocked`（bool）、`reason_code`（str）、`user_hint`（str）、`retry_after`（int|None）、`task_registered`（bool）
    3. precheck 函数体内禁止 `raise`（用 try/except 兜底返回结构化 dict）
    4. API 层直接透传 precheck 结果，自定义 ResumeBlockedError 转换为 400 响应
  - **判断信号**：
    - `grep "def precheck_" <file>` 函数体内含 `raise` → 视为违规
    - `grep "def precheck_" <file>` 返回值缺 5 字段任一 → 视为违规
    - `grep "raise ResumeBlockedError" <file>` 不在 API 层 → 视为违规
  - **反模式**：
    ```python
    def precheck_resume(self, task_id: str) -> dict:
        if not self._is_root_cause_resolved(task_id):
            raise ResumeBlockedError("root cause not resolved")  # 抛异常，API 层难以处理
        return {"resume_blocked": False}
    ```
  - **正确模式**：
    ```python
    def precheck_resume(self, task_id: str) -> dict:
        try:
            if not self._is_root_cause_resolved(task_id):
                return {
                    "resume_blocked": True,
                    "reason_code": "root_cause_unresolved",
                    "user_hint": "请先修复根因后再恢复",
                    "retry_after": 30,
                    "task_registered": True,
                }
            return {"resume_blocked": False, "reason_code": "", "user_hint": "", "retry_after": None, "task_registered": True}
        except Exception:
            logger.exception("precheck_resume failed")
            return {"resume_blocked": True, "reason_code": "precheck_error", "user_hint": "校验失败", "retry_after": 60, "task_registered": True}
    ```
  - **配置参数**：`meta_rules_38_42.precheck_structured_fields.enabled`（默认 true）、`meta_rules_38_42.precheck_structured_fields.severity`（默认 CRITICAL）、`meta_rules_38_42.precheck_structured_fields.required_fields`（默认 `["resume_blocked", "reason_code", "user_hint", "retry_after", "task_registered"]`）、`meta_rules_38_42.precheck_structured_fields.forbid_raise`（默认 true）、`meta_rules_38_42.precheck_structured_fields.api_error_status`（默认 400）在 `config.yaml` 的 `meta_rules_38_42.precheck_structured_fields` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #41 step 187
  - **适用**：pause/resume 语义的组件（scheduler/task/session）、状态恢复前置校验、API 层 precheck endpoint
  - **不适用**：无 pause/resume 语义的组件、一次性校验（无状态恢复）、同步阻塞校验（无 API 透传需求）
  - **历史教训**：`scheduler.py` precheck_resume 抛异常，`api_tasks.py` 无法透传结构化响应，前端无法显示具体阻塞原因

- 🆕v4.34【强制】**B-REVIEW-168：CONFIG-DRIVEN-THRESHOLD-FALLBACK 配置化阈值兜底范式**
  - 维度：14 配置管理 / 35 列表聚合与状态联动
  - 严重等级：major（P1，配置缺失即崩溃风险）
  - 规范引用：meta-rule #42 配置化阈值兜底范式
  - **检查点**：从 config 读取的阈值必须有 try/except 兜底默认值，禁止配置缺失即崩溃；兜底默认值必须从 config 的 fallback_defaults 节点读取
  - **检查项**：
    1. 从 config 读取的阈值（如 P10 分位数）必须用 try/except 包裹
    2. 配置缺失时必须回退到兜底默认值（如 P10 默认 0.10）
    3. 兜底默认值必须从 config 的 `fallback_defaults` 节点读取，禁止硬编码
    4. 兜底触发时必须 `logger.warning` 记录（不静默）
  - **判断信号**：
    - `grep "get_config\\(\\)\\.\\w+\\.\\w+" <file>` 但无 `try.*except` 包裹 → 视为违规
    - `grep "config\\.bargain_price\\.p10" <file>` 但无兜底 → 视为违规
  - **反模式**：
    ```python
    p10 = config.bargain_price.p10_percentile  # 配置缺失即 AttributeError 崩溃
    ```
  - **正确模式**：
    ```python
    try:
        p10 = config.bargain_price.p10_percentile
    except (AttributeError, KeyError):
        p10 = fallback_defaults.get("p10_percentile", 0.10)
        logger.warning("config.bargain_price.p10_percentile 缺失，回退到默认值 {}", p10)
    ```
  - **配置参数**：`meta_rules_38_42.config_fallback_defaults.enabled`（默认 true）、`meta_rules_38_42.config_fallback_defaults.severity`（默认 MAJOR）、`meta_rules_38_42.config_fallback_defaults.fallback_defaults`（默认 `{"p10_percentile": 0.10, "market_ratio_threshold": 0.85, "price_range_tolerance": 0.05}`）、`meta_rules_38_42.config_fallback_defaults.require_warning_log`（默认 true）在 `config.yaml` 的 `meta_rules_38_42.config_fallback_defaults` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #42 step 188
  - **适用**：从 config 读取的阈值/参数（P10 分位数/market_ratio/price_range）、配置驱动的业务逻辑、可选配置项
  - **不适用**：必需配置项（缺失应崩溃）、硬编码常量（非配置驱动）、启动时配置校验（一次性）
  - **历史教训**：`price_dashboard.py` 直接读取 `config.bargain_price.p10_percentile`，配置缺失时 AttributeError 导致 P10 计算崩溃

---

## 维度 36：跨层契约与测试同步（meta-rules #43-#47 落地）

- 🆕v4.35【强制】**B-REVIEW-173：EVENT-MULTI-EMIT-ALIGN 事件多发布点字段对齐**
  - 维度：22 业务事件 / 36 跨层契约与测试同步
  - 严重等级：critical（P0，事件消费方字段缺失导致业务流程断裂）
  - 规范引用：meta-rule #43 事件多发布点字段对齐
  - **检查点**：后端业务事件在多个层（worker/service/route/SSE 推送器）有发布点时，每处 payload 字段集必须一致；同一事件类型所有发布点必须使用统一的 payload 构造函数，禁止散落字典字面量
  - **检查项**：
    1. 同一事件类型所有发布点必须使用统一 payload 构造函数（如 `build_event_payload`）
    2. 必填字段（如 `task_mode`/`task_id`/`event_type`）在所有发布点必须存在
    3. 新增字段时必须同步更新所有发布点（含 SSE 推送器/worker 事件循环/route 钩子）
    4. payload 构造函数必须有单元测试覆盖所有事件类型的字段完整性
  - **判断信号**：
    - `grep "EVAL_PASSED\|task\.started\|task\.completed" src/` 后逐处人工核对字段集 → 字段不一致视为违规
    - `grep "payload = {" src/` 检查是否直接构造字典字面量而非调用统一函数 → 视为违规
  - **反模式**：
    ```python
    # 事件发布点 A（worker）
    await event_bus.emit("EVAL_PASSED", {"task_id": tid, "score": s})
    # 事件发布点 B（route 钩子）
    await event_bus.emit("EVAL_PASSED", {"task_id": tid, "score": s, "task_mode": mode})  # 缺 task_mode 在 A
    ```
  - **正确模式**：
    ```python
    # 统一构造函数
    def build_eval_passed_payload(task_id: str, score: float, task_mode: str) -> dict:
        return {"task_id": task_id, "score": score, "task_mode": task_mode}
    # 所有发布点统一调用
    await event_bus.emit("EVAL_PASSED", build_eval_passed_payload(tid, s, mode))
    ```
  - **配置参数**：`meta_rules_43_47.event_multi_emit_alignment.enabled`（默认 true）、`meta_rules_43_47.event_multi_emit_alignment.severity`（默认 CRITICAL）、`meta_rules_43_47.event_multi_emit_alignment.emit_points`（默认 `["worker", "service", "route", "sse_pusher"]`）、`meta_rules_43_47.event_multi_emit_alignment.required_fields`（默认 `["task_id", "task_mode", "event_type"]`）、`meta_rules_43_47.event_multi_emit_alignment.event_types`（默认 `["EVAL_PASSED", "task.started", "task.completed"]`）在 `config.yaml` 的 `meta_rules_43_47.event_multi_emit_alignment` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #43
  - **适用**：业务事件多层发布（worker/service/route/SSE 推送器）、跨进程事件传递、通知中心事件触发
  - **不适用**：单一发布点的内部事件、调试日志事件、单元测试 mock 事件
  - **历史教训**：SEMI_AUTO 模式下 EVAL_PASSED 事件三处发布点中 task_mode 字段不一致，导致通知模板渲染时 task_mode 为 None，前端未渲染"确认下单"链接，用户无法触发确认流程

- 🆕v4.35【强制】**B-REVIEW-174：ROUTE-REGISTRY-BACKEND-SYNC 路由注册表与后端 endpoint 契约**
  - 维度：19 API 契约 / 36 跨层契约与测试同步
  - 严重等级：critical（P0，路由无后端支持时静默 fallback 到首页）
  - 规范引用：meta-rule #44 路由注册表与后端 endpoint 契约
  - **检查点**：前端路由注册表中的每条路由，后端必须提供对应 endpoint；新增前端路由必须同步在后端注册对应 API endpoint，且路由 fallback 不应静默重定向，应返回 404 显式提示
  - **检查项**：
    1. 前端路由注册表中每条路由必须有后端对应 endpoint
    2. 路由 fallback 必须显式提示"路由未注册"而非静默重定向首页
    3. 新增路由时 PR 必须同时修改前后端，git diff 仅含前端路由无后端 endpoint 视为违规
    4. 路由注册校验脚本退出码 0 才算通过
  - **判断信号**：
    - `grep "path:" frontend/src/.../sheetRegistry` 后逐条与后端 endpoint 比对 → 缺失视为违规
    - 路由 fallback 配置为 `<Navigate to="/" replace />` 静默重定向 → 视为违规
  - **反模式**：
    ```typescript
    // 前端注册新路由但后端无对应 endpoint
    { path: "/confirm-buy", element: <ConfirmBuy /> }
    // 后端缺 @router.get("/confirm-buy") endpoint
    // 路由 fallback 静默重定向
    <Route path="*" element={<Navigate to="/" replace />} />
    ```
  - **正确模式**：
    ```typescript
    // 前端路由注册
    { path: "/confirm-buy", element: <ConfirmBuy /> }
    // 后端同步提供 endpoint
    @router.get("/api/confirm-buy/{task_id}")
    async def confirm_buy(task_id: str, request: Request): ...
    // 路由 fallback 显式 404
    <Route path="*" element={<NotFound />} />
    ```
  - **配置参数**：`meta_rules_43_47.frontend_route_registration.enabled`（默认 true）、`meta_rules_43_47.frontend_route_registration.severity`（默认 CRITICAL）、`meta_rules_43_47.frontend_route_registration.route_list`（默认从 `menu_registry.yaml` 读取）、`meta_rules_43_47.frontend_route_registration.endpoint_mapping`（默认 `{"confirm-buy": "/api/confirm-buy/{task_id}"}`）、`meta_rules_43_47.frontend_route_registration.silent_redirect_forbidden`（默认 true）在 `config.yaml` 的 `meta_rules_43_47.frontend_route_registration` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #44
  - **适用**：所有前端路由、新增前端页面、SPA 路由变更
  - **不适用**：纯前端 SPA 路由无后端数据（如静态帮助页）、纯客户端状态路由
  - **历史教训**：新增 SEMI_AUTO 确认路由 `/confirm-buy` 时，前端 sheetRegistry 已注册但后端未提供对应 endpoint，导致路由 fallback `<Navigate to="/" replace />` 静默重定向到首页，用户点击确认链接无反应

- 🆕v4.35【强制】**B-REVIEW-175：CALLBACK-URL-QUERY-CONSTRUCTION 回链 URL query string 构造**
  - 维度：22 业务事件 / 36 跨层契约与测试同步
  - 严重等级：critical（P0，query string 缺失导致前端无法恢复上下文）
  - 规范引用：meta-rule #45 回链 URL query string 构造
  - **检查点**：后端构造的回链 URL 必须包含前端所需的所有 query string 参数；前端解析 URL 时必须保留完整 query string，禁止使用 `pathname` 单独取值而丢弃 search 部分
  - **检查项**：
    1. 回链 URL 模板必须显式声明所需 query 参数清单
    2. 后端构造 URL 时必须使用 urlencode 而非 f-string 拼接
    3. 前端路由查找逻辑（如 `findSheetMeta`）必须剥离 query string 仅取 pathname
    4. 前端路由跳转逻辑（如 `useSheetSync`）必须保留完整 query string
  - **判断信号**：
    - `grep "f\".*task_id\|f\".*item_id\" src/"` 检查 URL 拼接是否用 urlencode → 用 f-string 视为违规
    - `grep "useLocation\|useNavigate" frontend/src/` 后检查 pathname 是否剥离 query → 未剥离视为违规
  - **反模式**：
    ```python
    # 后端用 f-string 拼接 URL 缺参数
    callback_url = f"/confirm-buy?task_id={tid}"  # 缺 item_id 等参数
    ```
    ```typescript
    // 前端用 pathname 单独取值丢弃 query string
    const meta = findSheetMeta(location.pathname);  // 丢弃了 ?task_id=xxx
    navigate(location.pathname);  // 丢失 query string
    ```
  - **正确模式**：
    ```python
    # 后端用 urlencode 构造完整 query string
    from urllib.parse import urlencode
    params = {"task_id": tid, "item_id": iid, "task_mode": mode}
    callback_url = f"/confirm-buy?{urlencode(params)}"
    ```
    ```typescript
    // 前端剥离 query 仅用于路由查找，跳转时保留完整 URL
    const meta = findSheetMeta(location.pathname);  // pathname 用于查找
    navigate(`${location.pathname}${location.search}`);  // search 保留
    ```
  - **配置参数**：`meta_rules_43_47.external_callback_query_retention.enabled`（默认 true）、`meta_rules_43_47.external_callback_query_retention.severity`（默认 CRITICAL）、`meta_rules_43_47.external_callback_query_retention.callback_routes`（默认 `["/confirm-buy", "/notifications/{id}"]`）、`meta_rules_43_47.external_callback_query_retention.required_params`（默认 `["task_id", "item_id", "task_mode"]`）、`meta_rules_43_47.external_callback_query_retention.urlencode_required`（默认 true）在 `config.yaml` 的 `meta_rules_43_47.external_callback_query_retention` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #45
  - **适用**：通知/邮件中的回链 URL、SSE 推送中的跳转链接、消息卡片中的按钮链接
  - **不适用**：纯内部 API 调用、后端服务间调用的内部 URL、静态资源 URL
  - **历史教训**：后端构造的确认链接 `/confirm-buy?task_id=xxx` 缺少 `task_mode` 参数，前端 `findSheetMeta` 用 `location.pathname` 取值但 `useSheetSync` 跳转时丢失 query string，导致用户从通知点击确认链接后页面无法加载任务数据

- 🆕v4.35【强制】**B-REVIEW-176：TEST-SIGNATURE-SYNC 接口签名变更测试同步**
  - 维度：24 测试规范 / 36 跨层契约与测试同步
  - 严重等级：major（P1，测试与生产代码不一致导致 CI 通过但生产故障）
  - 规范引用：meta-rule #46 接口签名变更测试同步
  - **检查点**：后端接口签名变更后必须同步更新所有测试调用；mock 类型必须与实际返回类型匹配（AsyncMock vs MagicMock）；新增参数必须有测试覆盖
  - **检查项**：
    1. 生产代码方法签名变更时同 PR 必须修改 tests/ 目录下相关测试
    2. 测试中 mock 对象类型必须与实际返回类型匹配（async 函数用 AsyncMock，同步函数用 MagicMock）
    3. 接口新增参数必须有测试覆盖默认值与边界值
    4. 测试中 mock 字段集必须与生产代码字段集一致
  - **判断信号**：
    - `git diff` 生产代码方法签名变更但同 PR `tests/` 目录无修改 → 视为违规
    - `grep "AsyncMock\|MagicMock" tests/` 后核对与被 mock 函数 async/同步属性是否匹配 → 不匹配视为违规
    - `grep "def test_" tests/` 后检查 mock 字段集是否覆盖生产代码新增字段 → 缺失视为违规
  - **反模式**：
    ```python
    # 生产代码 async 函数
    async def manual_takeover(task_id: str, request: Request): ...
    # 测试用 MagicMock（应 AsyncMock）
    mock_takeover = MagicMock()
    # 测试缺 request 参数（接口已新增）
    result = await manual_takeover("tid")  # 缺 request 参数
    ```
  - **正确模式**：
    ```python
    # 生产代码 async 函数
    async def manual_takeover(task_id: str, request: Request): ...
    # 测试用 AsyncMock
    mock_takeover = AsyncMock()
    # 测试同步更新参数
    mock_request = MagicMock()
    mock_request.state.user_id = "uid123"
    result = await manual_takeover("tid", mock_request)
    ```
  - **配置参数**：`meta_rules_43_47.test_synchronization.enabled`（默认 true）、`meta_rules_43_47.test_synchronization.severity`（默认 MAJOR）、`meta_rules_43_47.test_synchronization.signature_check_patterns`（默认 `["def .*\\(.*\\):", "async def .*\\(.*\\):"]`）、`meta_rules_43_47.test_synchronization.mock_type_mapping`（默认 `{"async": "AsyncMock", "sync": "MagicMock"}`）、`meta_rules_43_47.test_synchronization.require_test_diff`（默认 true）在 `config.yaml` 的 `meta_rules_43_47.test_synchronization` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #46
  - **适用**：所有接口签名重构、async/同步属性变更、新增/移除参数、字段集变更
  - **不适用**：纯内部实现重构（不改变签名）、私有方法重构、注释/文档更新
  - **历史教训**：`manual_takeover` 接口新增 `request` 参数后测试未同步更新，导致测试调用缺参数报错；`mock_dedup.filter_new` 用 AsyncMock 但生产代码改为同步函数，导致 await 同步返回值报错

- 🆕v4.35【强制】**B-REVIEW-177：EXTERNAL-DEP-ISOLATION 外部依赖隔离与测试可重复性**
  - 维度：24 测试规范 / 36 跨层契约与测试同步
  - 严重等级：major（P1，外部依赖未隔离导致测试不稳定与误报）
  - 规范引用：meta-rule #51 外部依赖隔离与测试可重复性
  - **检查点**：测试中依赖 keyring/env/file/network 必须显式 patch；patch 必须返回确定性值（如 `return_value=None` 表示"无配置"）；禁止依赖外部资源真实状态
  - **检查项**：
    1. 测试中调用 `get_secret`/`os.environ[...]`/文件读取/网络请求的位置必须有显式 patch
    2. patch 必须返回确定性值（如 `return_value=None` 表示"无配置"场景）
    3. keyring fallback 必须显式测试（mock keyring.get_password 返回 None 时降级到 env/file）
    4. 测试不得依赖外部文件系统状态（如 `~/.config/xxx` 是否存在）
  - **判断信号**：
    - `grep "get_secret\|os\.environ\[" tests/` 但同函数无 `patch(..., return_value=None)` → 视为违规
    - `grep "keyring" tests/` 但无 `patch("keyring.get_password", return_value=None)` → 视为违规
    - `grep "open(" tests/` 但无 `mock_open` → 视为违规
  - **反模式**：
    ```python
    # 测试调用 get_secret 但无 patch（依赖真实 keyring/env 状态）
    def test_dingtalk_send_without_secret():
        # 缺 patch get_secret → 测试依赖真实环境变量
        result = send_dingtalk("msg")
        assert result is False  # 可能因环境变量存在而失败
    ```
  - **正确模式**：
    ```python
    # 测试显式 patch get_secret 返回 None
    @patch("xianyu_hunter.config.get_secret", return_value=None)
    def test_dingtalk_send_without_secret(mock_secret):
        result = send_dingtalk("msg")
        assert result is False  # 确定性：无 secret 时返回 False
    # keyring fallback 显式测试
    @patch("keyring.get_password", return_value=None)
    def test_keyring_fallback_to_env(mock_keyring):
        os.environ["XX_TOKEN"] = "from_env"
        result = get_token()
        assert result == "from_env"
    ```
  - **配置参数**：`meta_rules_43_47.external_dependency_isolation.enabled`（默认 true）、`meta_rules_43_47.external_dependency_isolation.severity`（默认 MAJOR）、`meta_rules_43_47.external_dependency_isolation.dependency_types`（默认 `["keyring", "env", "file", "network"]`）、`meta_rules_43_47.external_dependency_isolation.isolation_strategies`（默认 `{"keyring": "patch return_value=None", "env": "patch.dict os.environ", "file": "mock_open", "network": "responses_mock"}`）、`meta_rules_43_47.external_dependency_isolation.require_deterministic`（默认 true）在 `config.yaml` 的 `meta_rules_43_47.external_dependency_isolation` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #47
  - **适用**：所有依赖外部资源的测试（keyring/env/file/network）、CI 环境、跨平台测试
  - **不适用**：纯函数测试（无外部依赖）、单元测试 mock 内部对象、集成测试显式需要真实资源
  - **历史教训**：钉钉通知测试中 `get_secret` 未 patch，CI 环境存在真实 webhook_url 导致测试发送真实请求；keyring fallback 未测试，本地 keyring 有缓存导致 CI 与本地测试结果不一致

- 🆕v4.36【强制】**B-REVIEW-178：SCHEDULER-RUNTIME-TOGGLE-SYMMETRY 调度器运行时开关对称性**
  - 维度：9 异步与调度器 / 36 跨层契约与测试同步
  - 严重等级：critical（P0，配置开关无效导致禁用后仍持续执行）
  - 规范引用：meta-rule #48 调度器运行时开关对称性
  - **检查点**：调度器 `update_config(enabled=False)` 必须在同一个方法内完成"设标志位 + remove_job"两步操作；`update_config(enabled=True)` 必须调用 `add_job(...)` 或 `resume_job(job_id)` 重新注册/恢复 job；job 函数入口必须 `if not self._enabled: return` 作为 double-check；调度器必须提供 `is_enabled() -> bool` 方法供 API 层查询
  - **检查项**：
    1. `update_config(enabled=False)` 必须调用 `scheduler.remove_job(job_id)`，禁止只设标志位
    2. `update_config(enabled=True)` 必须调用 `scheduler.add_job(...)` 或 `resume_job(job_id)`
    3. job 函数入口必须有 `if not self._enabled: return` double-check
    4. 调度器必须提供 `is_enabled() -> bool` 公共方法
    5. `enabled` 字段必须从 `config.yaml` 读取，`update_config` 修改后必须同步写回 config
  - **判断信号**：
    - `grep "update_config" src/` 后检查 `enabled=False` 分支是否有 `remove_job` → 缺失视为违规
    - `grep "_enabled" src/` 后检查 job 函数入口是否有 double-check → 缺失视为违规
    - `grep "is_enabled" src/` 无对应方法定义 → 视为违规
  - **反模式**：
    ```python
    # 只设标志位不移除 job，APScheduler 已注册的 job 仍按 trigger 触发
    def update_config(self, *, enabled: bool | None = None) -> None:
        if enabled is not None:
            self._enabled = enabled  # remove_job 缺失
    ```
  - **正确模式**：
    ```python
    def update_config(self, *, enabled: bool | None = None) -> None:
        if enabled is not None:
            self._enabled = enabled
            if not enabled:
                try:
                    self._scheduler.remove_job(self._job_id)
                except Exception as e:
                    logger.warning("移除 job 失败: {}", e)
            else:
                self._scheduler.add_job(self._run_job, trigger=..., id=self._job_id)

    def _run_job(self):
        if not self._enabled:
            logger.warning("调度器已禁用但 job 仍触发，检查 update_config 实现")
            return
        # ... 业务逻辑

    def is_enabled(self) -> bool:
        return self._enabled
    ```
  - **配置参数**：`meta_rules_48_51.scheduler_runtime_toggle.enabled`（默认 true）、`meta_rules_48_51.scheduler_runtime_toggle.severity`（默认 CRITICAL）、`meta_rules_48_51.scheduler_runtime_toggle.require_remove_job`（默认 true）、`meta_rules_48_51.scheduler_runtime_toggle.require_entry_check`（默认 true）、`meta_rules_48_51.scheduler_runtime_toggle.require_is_enabled_method`（默认 true）、`meta_rules_48_51.scheduler_runtime_toggle.require_config_persist`（默认 true）在 `config.yaml` 的 `meta_rules_48_51.scheduler_runtime_toggle` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.36.0 meta-rule #48
  - **适用**：所有 APScheduler 调度器（BackgroundScheduler/AsyncIOScheduler）；具有 `enabled` 配置开关的后台任务；运行时可动态启停的调度器
  - **不适用**：一次性任务（无 `enabled` 字段）；启动时确定整个生命周期不启停的调度器；外部托管调度器（如 celery beat）
  - **历史教训**：`BatchRefreshScheduler` 禁用后批量采集仍持续执行，用户反馈「关闭开关后任务还在跑」。排查发现 `update_config` 只设标志位未 remove_job，APScheduler 已注册的 job 仍按 trigger 触发

- 🆕v4.36【强制】**B-REVIEW-179：TIME-PARAM-CONFIG-DRIVEN 时间参数配置化**
  - 维度：14 配置管理 / 36 跨层契约与测试同步
  - 严重等级：major（P1，硬编码时间参数无法根据业务场景调整）
  - 规范引用：meta-rule #49 时间参数配置化
  - **检查点**：异常重试等待秒数、轮询间隔、超时秒数等时间参数必须从 `config.yaml` 读取，禁止硬编码字面量数字；配置节点必须提供合理的默认值与边界校验
  - **检查项**：
    1. `grep "return 300\\|return 600\\|sleep(300)\\|sleep(600)" src/` 检查是否有硬编码时间字面量
    2. 时间参数必须从 `config.yaml` 的对应节点读取（如 `task_scheduler.exception_retry_wait_seconds`）
    3. 配置节点必须提供默认值（在 `config.example.yaml` 中声明）
    4. 配置加载时必须有边界校验（min/max/non_negative）
  - **判断信号**：
    - `grep "\\b\\d{3,}\\b" src/xianyu_hunter/modules/scheduler.py` 后人工核对是否为时间参数字面量 → 是则视为违规
    - `grep "time\\.sleep\\|asyncio\\.sleep" src/` 后检查参数来源是否为 config 引用 → 字面量视为违规
  - **反模式**：
    ```python
    # 异常重试等待硬编码 300 秒
    def _compute_next_wait_seconds(self, consecutive_errors: int) -> int:
        return 300  # 硬编码，无法根据业务场景调整
    ```
  - **正确模式**：
    ```python
    def _compute_next_wait_seconds(self, consecutive_errors: int) -> int:
        # 从 config 读取，提供默认值兜底
        base_wait = getattr(self._config, 'exception_retry_wait_seconds', 300)
        max_wait = getattr(self._config, 'exception_retry_max_seconds', 1800)
        wait = min(base_wait * (2 ** min(consecutive_errors - 1, 5)), max_wait)
        return wait
    ```
  - **配置参数**：`meta_rules_48_51.time_param_config_driven.enabled`（默认 true）、`meta_rules_48_51.time_param_config_driven.severity`（默认 MAJOR）、`meta_rules_48_51.time_param_config_driven.param_patterns`（默认 `["exception_retry_wait", "polling_interval", "timeout_seconds", "cooldown_seconds"]`）、`meta_rules_48_51.time_param_config_driven.forbidden_literals`（默认 `[300, 600, 1800, 3600]`）、`meta_rules_48_51.time_param_config_driven.require_default_value`（默认 true）、`meta_rules_48_51.time_param_config_driven.require_boundary_check`（默认 true）在 `config.yaml` 的 `meta_rules_48_51.time_param_config_driven` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.36.0 meta-rule #49
  - **适用**：所有时间参数（重试等待/轮询间隔/超时秒数/冷却期）；调度器配置；异步任务等待时间
  - **不适用**：测试代码中的固定时间参数（如 `await asyncio.sleep(0.1)`）；性能优化中的微秒级 sleep（如 `asyncio.sleep(0)` 让出控制权）；日志输出间隔（如每 100 条日志输出一次）
  - **历史教训**：`scheduler.py` 的 `_compute_next_wait_seconds` 异常重试等待硬编码 `return 300`，所有任务异常后必须等 5 分钟才能重试，无法根据业务场景调整

- 🆕v4.36【强制】**B-REVIEW-180：LIFECYCLE-RESOURCE-CLEANUP 长生命周期对象状态清理**
  - 维度：9 异步与调度器 / 36 跨层契约与测试同步
  - 严重等级：major（P1，状态字典无限增长导致内存泄漏）
  - 规范引用：meta-rule #50 长生命周期对象状态清理
  - **检查点**：长生命周期对象（scheduler/container/registry/manager）的 `__init__` 中所有 `dict[str, ...]` 类型字段必须支持按 task_id 清理；DELETE API 删除 task 时必须调用 `drop_task_state(task_id)` 清理内存状态
  - **检查项**：
    1. 长生命周期对象的 `__init__` 中所有 `dict[str, ...]` 字段视为状态字典，必须支持按 task_id 清理
    2. 必须提供 `drop_task_state(self, task_id: str) -> None` 方法，内部遍历所有状态字典 `pop(task_id, None)`
    3. `DELETE /api/tasks/{task_id}` 和 `DELETE /api/tasks/batch` 路由必须调用 `container.scheduler.drop_task_state(task_id)`
    4. `drop_task_state` 内部 `pop` 操作必须 `try/except Exception: logger.debug(...)` 容错，不阻断主流程
  - **判断信号**：
    - `grep "self\\._\\w+: dict\\[str," src/xianyu_hunter/modules/scheduler.py` 后检查是否有 `drop_task_state` 方法 → 缺失视为违规
    - `grep "delete_task\\|delete.*task" src/xianyu_hunter/web/routes/api_tasks.py` 后检查是否调用 `drop_task_state` → 缺失视为违规
  - **反模式**：
    ```python
    # 状态字典无清理方法，DELETE API 不调用清理
    class TaskScheduler:
        def __init__(self):
            self._resume_cooldown: dict[str, float] = {}  # 无 drop_task_state 方法
            self._last_failure_reason: dict[str, str] = {}

    # DELETE API 只删 DB 不清理内存状态
    @router.delete("/{task_id}")
    async def delete_task(task_id: str):
        await task_store.delete(task_id)  # 缺 drop_task_state 调用
        return {"deleted": task_id}
    ```
  - **正确模式**：
    ```python
    class TaskScheduler:
        def __init__(self):
            self._resume_cooldown: dict[str, float] = {}
            self._last_failure_reason: dict[str, str] = {}

        def drop_task_state(self, task_id: str) -> None:
            """清理指定 task 的所有状态字典"""
            try:
                self._resume_cooldown.pop(task_id, None)
                self._last_failure_reason.pop(task_id, None)
            except Exception as e:
                logger.debug("清理 task 状态失败（忽略）: {}", e)

    @router.delete("/{task_id}")
    async def delete_task(task_id: str):
        await task_store.delete(task_id)
        try:
            container.scheduler.drop_task_state(task_id)
        except Exception as e:
            logger.debug("清理 scheduler 任务状态失败（忽略）: {}", e)
        return {"deleted": task_id}
    ```
  - **配置参数**：`meta_rules_48_51.lifecycle_resource_cleanup.enabled`（默认 true）、`meta_rules_48_51.lifecycle_resource_cleanup.severity`（默认 MAJOR）、`meta_rules_48_51.lifecycle_resource_cleanup.state_dict_pattern`（默认 `"self\\._\\w+: dict\\[str,"`）、`meta_rules_48_51.lifecycle_resource_cleanup.require_drop_method`（默认 true）、`meta_rules_48_51.lifecycle_resource_cleanup.require_delete_api_call`（默认 true）、`meta_rules_48_51.lifecycle_resource_cleanup.cleanup_strategy`（默认 `lazy`）、`meta_rules_48_51.lifecycle_resource_cleanup.cleanup_triggers`（默认 `["delete_api", "scheduler_shutdown"]`）在 `config.yaml` 的 `meta_rules_48_51.lifecycle_resource_cleanup` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.36.0 meta-rule #50
  - **适用**：长生命周期对象（scheduler/container/registry/manager/singleton service）；持有 `dict[str, ...]` 状态字段的组件；task 级或 session 级状态缓存；DELETE API 删除资源的场景
  - **不适用**：短生命周期对象（请求级/函数级局部变量）；无状态服务（stateless）；只读缓存（never expire）；测试 fixture（测试结束自动清理）
  - **历史教训**：`scheduler.py` 的 `_resume_cooldown` 字典在 task 异常 pause 后写入冷却时间戳，DELETE API 删除 task 时未清理，长期运行后字典无限增长，服务运行 7 天后内存从 200MB 涨到 1.5GB

- 🆕v4.36 experimental【强制】**B-REVIEW-181：CRON-MIN-INTERVAL-CHECK 用户输入时间表达式校验**
  - 维度：14 配置管理 / 36 跨层契约与测试同步
  - 严重等级：major（P1，cron 表达式无最小间隔校验触发反爬封禁）
  - 规范引用：meta-rule #51 用户输入时间表达式校验（experimental，1 季度观察期）
  - **检查点**：用户输入的 cron 表达式必须有最小执行间隔校验；解析失败的 cron 表达式必须返回结构化错误不抛异常；最小间隔阈值从 `config.yaml` 读取不硬编码
  - **检查项**：
    1. 用户输入的 cron 表达式必须用 `apscheduler.triggers.cron.CronTrigger.from_crontab(cron_expr)` 解析
    2. 解析后必须计算最小执行间隔，低于阈值的拒绝并返回结构化错误 `{valid, reason_code, user_hint, min_interval_seconds}`
    3. 最小间隔阈值从 `config.yaml` 的 `cron_min_interval_check.min_interval_seconds` 节点读取（默认 60 秒）
    4. 解析失败必须返回结构化错误不抛异常
  - **判断信号**：
    - `grep "schedule_cron\\|cron_expr" src/` 后检查是否有最小间隔校验 → 缺失视为违规
    - `grep "CronTrigger\\.from_crontab" src/` 后检查是否有 try/except 容错 → 缺失视为违规
  - **反模式**：
    ```python
    # 接受任意 cron 表达式，无最小间隔校验
    def validate_cron(cron_expr: str) -> bool:
        try:
            CronTrigger.from_crontab(cron_expr)
            return True  # 接受 "* * * * *"（每分钟执行）
        except Exception:
            return False
    ```
  - **正确模式**：
    ```python
    from apscheduler.triggers.cron import CronTrigger
    from datetime import datetime, timedelta

    def validate_cron_with_min_interval(cron_expr: str, min_interval: int = 60) -> dict:
        """校验 cron 表达式并检查最小间隔"""
        try:
            trigger = CronTrigger.from_crontab(cron_expr)
        except Exception as e:
            return {"valid": False, "reason_code": "PARSE_ERROR",
                    "user_hint": f"cron 表达式格式错误: {e}", "min_interval_seconds": None}
        # 计算连续两次触发的最小间隔
        now = datetime.now()
        next_runs = []
        current = now
        for _ in range(10):  # 采样 10 次取最小间隔
            current = trigger.get_next_fire_time(current, current)
            if current is None:
                break
            next_runs.append(current)
        if len(next_runs) >= 2:
            intervals = [(next_runs[i+1] - next_runs[i]).total_seconds() for i in range(len(next_runs)-1)]
            min_interval_actual = min(intervals)
            if min_interval_actual < min_interval:
                return {"valid": False, "reason_code": "INTERVAL_TOO_SHORT",
                        "user_hint": f"最小执行间隔 {min_interval_actual}s 低于阈值 {min_interval}s",
                        "min_interval_seconds": min_interval_actual}
        return {"valid": True, "reason_code": None, "user_hint": None,
                "min_interval_seconds": None}
    ```
  - **配置参数**：`meta_rules_48_51.cron_min_interval_check.enabled`（默认 true）、`meta_rules_48_51.cron_min_interval_check.severity`（默认 MAJOR）、`meta_rules_48_51.cron_min_interval_check.min_interval_seconds`（默认 60）、`meta_rules_48_51.cron_min_interval_check.sample_count`（默认 10）、`meta_rules_48_51.cron_min_interval_check.require_structured_error`（默认 true）在 `config.yaml` 的 `meta_rules_48_51.cron_min_interval_check` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.36.0 meta-rule #51（experimental）
  - **适用**：所有接受用户输入 cron 表达式的场景（任务调度/定时采集/状态回查）；APScheduler CronTrigger 场景
  - **不适用**：系统内部固定 cron 表达式（非用户输入）；interval 触发器（已有 interval 参数）；一次性任务（无重复执行）
  - **历史教训**：task 的 `schedule_cron` 字段接受任意 cron 表达式，用户配置 `* * * * *`（每分钟执行）导致批量采集每分钟触发一次，远低于反爬最小延迟（10 秒），触发闲鱼反爬封禁

- 🆕v4.38【强制】**B-REVIEW-182：ASYNC-AWAIT-SYNC-CHECK async/await 同步性静态检查**
  - 维度：9 异步与调度器
  - 严重等级：critical（P0，Python 3.14 兼容性风险）
  - 规范引用：meta-rule #57 async/await 同步性静态检查
  - **检查点**：`async def` 方法体内若不含 `await` 表达式，必须改为同步 `def`；调用点同步移除 `await`
  - **检查项**：
    1. 所有 `async def` 方法必须检查方法体内是否含 `await` 表达式，无 `await` 则改为 `def`
    2. 方法从 `async def` 改为 `def` 后，所有调用点必须同步移除 `await`
    3. 白名单豁免：`@abstractmethod` 纯接口定义、`__aenter__`/`__aexit__` 上下文管理器、async generator（含 `yield`）可保留 `async def` 无 `await`
    4. 推荐用 AST 分析而非正则，准确识别方法体内是否含 `await` 节点
  - **判断信号**：
    - `grep "async def" <file>` 后检查方法体内是否含 `await`
    - `grep "await self._finalize_run\|await self._simple_method" <file>` 但方法体全同步 → 违规
    - 方法从 async 改为 sync 但 `grep "await <method_name>"` 仍有命中 → 调用点未同步
  - **反模式**：
    ```python
    # async def 方法体全同步，Python 3.14 优化后返回 None，await None 触发 TypeError
    async def _finalize_run(self, stats):
        self._stats = stats
        self._persist_to_db(stats)

    # 调用点仍用 await
    await self._finalize_run(stats)  # TypeError in Python 3.14
    ```
  - **正确模式**：
    ```python
    # 改为同步 def
    def _finalize_run(self, stats):
        self._stats = stats
        self._persist_to_db(stats)

    # 调用点同步移除 await
    self._finalize_run(stats)
    ```
  - **配置参数**：`meta_rules_57_63.async_await_check.enabled`（默认 true）、`meta_rules_57_63.async_await_check.severity`（默认 CRITICAL）、`meta_rules_57_63.async_await_check.whitelist_decorators`（默认 `["@abstractmethod", "__aenter__", "__aexit__"]`）、`meta_rules_57_63.async_await_check.use_ast_analysis`（默认 true）在 `config.yaml` 的 `meta_rules_57_63.async_await_check` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.38.0 meta-rule #57
  - **适用**：Python 3.11+ 异步代码；使用 asyncio 的 FastAPI/uvicorn 项目；含 `async def` 的 worker/scheduler/service 层
  - **不适用**：纯接口定义（`@abstractmethod`）；上下文管理器；async generator；测试代码中的 `async def test_*`
  - **历史教训**：`worker.py` 的 `_finalize_run` 标记为 `async def` 但方法体全同步，Python 3.14 优化后返回 None，`await None` 触发 TypeError 导致调度器崩溃。同期发现 3 处类似问题（`_save_progress` / `_update_status` / `_notify_done`），均改为同步

- 🆕v4.38【强制】**B-REVIEW-183：RESOURCE-POOL-BENCHMARK 资源池配置性能基准**
  - 维度：15 数据库 / 16 性能
  - 严重等级：major（P1，NullPool 导致每次连接执行 PRAGMA 开销 ~100ms）
  - 规范引用：meta-rule #58 资源池配置性能基准与决策
  - **检查点**：资源池配置（`poolclass=NullPool`/`QueuePool`/`StaticPool`）必须有性能基准数据支持，docstring 记录选择理由与对比数据
  - **检查项**：
    1. 资源池选择必须有性能基准数据支持，记录"NullPool vs QueuePool"的连接建立/复用/销毁开销对比
    2. 资源池配置代码必须有 docstring 说明选择理由、对比数据、适用场景
    3. 系统层开销（连接建立 + PRAGMA + init SQL）> 50ms 时禁止用 NullPool
    4. 测试环境可用 StaticPool 但需 docstring 标注"仅测试用"
  - **判断信号**：
    - `grep "poolclass=" <file>` 无 docstring 说明 → WARNING
    - `grep "poolclass=NullPool" <file>` 但无性能基准 docstring → 违规
    - 慢查询日志中系统层开销 > 50ms 且使用 NullPool → CRITICAL
  - **反模式**：
    ```python
    # 无 docstring 说明，生产环境用 NullPool 每次连接执行 PRAGMA 开销 ~100ms
    engine = create_engine("sqlite:///data/xianyu.db", poolclass=NullPool)
    ```
  - **正确模式**：
    ```python
    # QueuePool 复用连接，性能提升 10-50x；docstring 记录选择理由
    engine = create_engine(
        "sqlite:///data/xianyu.db",
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
    )
    # 性能基准：NullPool 每次新建连接执行 PRAGMA 开销 ~100ms，
    # QueuePool 复用连接后 list_and_count_task_links 从 231ms 降至 11.9ms（19x 提升）
    ```
  - **配置参数**：`meta_rules_57_63.resource_pool_benchmark.enabled`（默认 true）、`meta_rules_57_63.resource_pool_benchmark.overhead_threshold_ms`（默认 50）、`meta_rules_57_63.resource_pool_benchmark.forbidden_pool_types_in_prod`（默认 `["NullPool", "StaticPool"]`）在 `config.yaml` 的 `meta_rules_57_63.resource_pool_benchmark` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.38.0 meta-rule #58
  - **适用**：所有资源池选择；含 PRAGMA/init/重试开销的资源初始化；数据库连接池、HTTP 连接池、浏览器实例池
  - **不适用**：测试环境（用 StaticPool 保证隔离）；单次请求资源；内存数据结构；CLI 一次性脚本
  - **历史教训**：`db_models.py` 使用 `NullPool` 导致 `list_and_count_task_links` 慢查询 231ms（其中 ~100ms 是 PRAGMA 开销）。改为 `QueuePool(pool_size=5, max_overflow=5, pool_pre_ping=True)` 后降至 11.9ms（19x 提升）

- 🆕v4.38【强制】**B-REVIEW-184：HTTP-STATUS-CODE-MAPPING HTTP 状态码精细化映射**
  - 维度：13 错误处理 / 7 API 契约
  - 严重等级：major（P1，多原因汇聚同一状态码导致用户无法区分错误类型）
  - 规范引用：meta-rule #59 HTTP 状态码精细化映射表
  - **检查点**：底层模块返回多原因的 None/错误时，必须建立 `reason_code → status_code` 映射表；底层设置 `last_*_failure_reason`；上游按映射查找状态码
  - **检查项**：
    1. 底层模块返回 None 时必须设置 `self.last_*_failure_reason`，记录具体原因
    2. 上游必须建立 `_FAILURE_STATUS_MAP = {reason_code: status_code}` 映射表
    3. 未知 reason 用默认状态码（如 410），但必须 `logger.warning` 记录未知 reason
    4. 前端按状态码提供本地化消息，禁止 `detail.includes(...)` substring 判断
  - **判断信号**：
    - `grep "raise HTTPException(410\|raise HTTPException(502" <file>` 多原因汇聚同一码 → WARNING
    - `grep "last_.*_failure_reason" <file>` 与 `grep "is None" <file>` 配对检查
    - `grep "_FAILURE_STATUS_MAP\|_STATUS_MAP" <file>` 无映射表 → 违规
  - **反模式**：
    ```python
    # 多原因汇聚同一状态码，用户无法区分错误类型
    if detail is None:
        raise HTTPException(status_code=410, detail="商品详情页加载失败或已下架")
    # 实际原因可能是 cookie 过期（应 403）、反爬（应 429）、网络超时（应 504）
    ```
  - **正确模式**：
    ```python
    # 底层设置具体失败原因
    class DetailParser:
        def parse(self, html):
            if not html:
                self.last_detail_failure_reason = "network_timeout"
                return None
            # ...

    # 上游建立映射表
    _DETAIL_FAILURE_STATUS_MAP = {
        "home_title_redirect": 403,
        "login_redirect": 403,
        "verify_redirect": 441,
        "item_not_found": 410,
        "item_removed": 410,
        "anti_crawler": 429,
        "network_timeout": 504,
    }

    if detail is None:
        reason = parser.last_detail_failure_reason or "unknown"
        status = _DETAIL_FAILURE_STATUS_MAP.get(reason, 410)
        if reason not in _DETAIL_FAILURE_STATUS_MAP:
            logger.warning(f"未知 detail failure reason: {reason}")
        raise HTTPException(status_code=status, detail=f"detail failed: {reason}")
    ```
  - **配置参数**：`meta_rules_57_63.http_status_code_mapping.enabled`（默认 true）、`meta_rules_57_63.http_status_code_mapping.default_status_code`（默认 410）、`meta_rules_57_63.http_status_code_mapping.require_reason_field`（默认 true）、`meta_rules_57_63.http_status_code_mapping.mapping_table_example`（含 7 个 reason_code → status_code 示例）在 `config.yaml` 的 `meta_rules_57_63.http_status_code_mapping` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.38.0 meta-rule #59
  - **适用**：所有 HTTP 错误响应；多原因返回 None/错误的底层模块（如 detail() 返回 None 有 10+ 原因）
  - **不适用**：唯一原因的错误码（如 404 仅表示资源不存在）；内部异常不向用户暴露；健康检查端点
  - **历史教训**：`collection_service.py` 将所有 `detail() is None` 映射为 410 Gone，用户看到"已下架"后误以为商品真的下架，实际重新登录后商品仍在。修复：建立映射表 + 底层设置 failure_reason + 前端按状态码提供本地化消息

- 🆕v4.38【强制】**B-REVIEW-185：CSS-SELECTOR-FALLBACK CSS 选择器多级降级**
  - 维度：19 浏览器自动化
  - 严重等级：critical（P0，第三方网站改版即失效）
  - 规范引用：meta-rule #60 CSS 选择器多级降级策略
  - **检查点**：依赖第三方网站 DOM 的选择器必须有 ≥3 级降级（业务语义 className → HTML role 属性 → 文本内容前缀扫描）；dump 触发条件收窄到核心字段失败
  - **检查项**：
    1. 选择器必须按"业务语义 className → HTML role 属性 → 文本内容前缀扫描"顺序尝试，每级失败自动降级
    2. 调试 dump 仅在核心字段（如 `on_sale`）失败时触发，非核心字段（如 `sold`）失败不 dump
    3. 所有 selector 字符串在 `config.yaml` 管理，禁止硬编码
    4. 多 selector 尝试的中间步骤 DEBUG 化，最终失败 WARNING
  - **判断信号**：
    - `grep "querySelectorAll\|querySelector" <file>` 选择器单一无 fallback → CRITICAL
    - `grep "tabItem\|tab.*class.*tab" <file>` 无 `try/except` 或 `or []` fallback → 违规
    - `grep "dump.*html\|page.content" <file>` 触发条件含非核心字段 → WARNING
  - **反模式**：
    ```python
    # 单一选择器无 fallback，改版后 on_sale=0 sold=0 误报
    tabs = page.querySelectorAll('[class*="tabItem"]')
    # dump 触发条件含非核心字段（sold），导致 12 小时累积 500+ dump 文件
    if on_sale == 0 or sold == 0:
        self._dump_html(page)
    ```
  - **正确模式**：
    ```python
    # 三级降级：业务 className → role 属性 → 文本前缀扫描
    tabs = (
        page.querySelectorAll('[class*="tabItem"]')
        or page.querySelectorAll('[class*="tab"][role="tab"]')
        or self._scan_text_prefix(page, prefix_texts=["在售", "已售"])
    )
    # dump 仅在核心字段 on_sale 失败时触发
    if on_sale == 0:
        self._dump_html(page)
    ```
  - **配置参数**：`meta_rules_57_63.css_selector_fallback.enabled`（默认 true）、`meta_rules_57_63.css_selector_fallback.min_fallback_levels`（默认 3）、`meta_rules_57_63.css_selector_fallback.dump_trigger_fields`（默认 `["on_sale"]`）、`meta_rules_57_63.css_selector_fallback.dump_max_per_hour`（默认 10）在 `config.yaml` 的 `meta_rules_57_63.css_selector_fallback` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.38.0 meta-rule #60
  - **适用**：第三方网站 DOM 解析（闲鱼/淘宝/天猫/京东）；依赖 className 的选择器；Playwright `page.querySelectorAll` 返回值解析
  - **不适用**：自有代码 DOM；ID 选择器；`data-*` 属性选择器；后端 API JSON 解析；SSR 页面
  - **历史教训**：`_detail.py` 的 `_parse_sale_counts_from_tabs` 仅依赖 `tabItem` class 名，闲鱼页面 DOM 结构变化后失效。dump 触发条件 `on_sale==0 or sold==0` 导致 12 小时内累积 500+ dump 文件。修复：三级 fallback + 收紧 dump 触发条件为 `on_sale==0`

- 🆕v4.38【强制】**B-REVIEW-186：EXCEPTION-LOG-SEMANTIC 异常日志语义保留**
  - 维度：13 错误处理
  - 严重等级：critical（P0，丢失 traceback 导致问题定位耗时 30+ 分钟）
  - 规范引用：meta-rule #61 异常日志语义保留规范
  - **检查点**：`except` 块内必须用 `logger.exception('描述')` 保留完整 traceback，禁用 `logger.warning(f'...{e}')` 丢失堆栈
  - **检查项**：
    1. `except` 块内必须用 `logger.exception("描述")` 自动保留完整 traceback
    2. 禁止 `except` 块内 `logger.warning(f"操作失败: {e}")`（仅打印异常对象，丢失堆栈）
    3. 非 except 块需记录异常信息时用 `logger.warning("描述", exc_info=True)`
    4. 多阶段降级链合并为单条结构化 WARNING（参考 meta-rule #32）
  - **判断信号**：
    - `grep "logger.warning.*f\".*{e}\"" <file>` 或 `grep "logger.exception.*f\"" <file>` 在 except 块内 → 违规
    - `grep "except.*as e:" <file>` 后跟 `logger.warning\|logger.error` 但无 `logger.exception` → 违规
  - **反模式**：
    ```python
    # except 块内用 logger.warning 丢失 traceback，定位耗时 30+ 分钟
    try:
        result = await self._fetch_detail(item_id)
    except Exception as e:
        logger.warning(f"获取详情失败: {e}")  # 仅打印异常对象，丢失堆栈
    ```
  - **正确模式**：
    ```python
    # logger.exception 自动保留完整 traceback
    try:
        result = await self._fetch_detail(item_id)
    except Exception:
        logger.exception(f"获取详情失败, item_id={item_id}")
    ```
  - **配置参数**：`meta_rules_57_63.exception_log_semantic.enabled`（默认 true）、`meta_rules_57_63.exception_log_semantic.forbidden_patterns`（默认 `["logger.warning.*f\".*{e}\"", "logger.error.*f\".*{e}\""]`）、`meta_rules_57_63.exception_log_semantic.required_pattern`（默认 `"logger.exception"`）、`meta_rules_57_63.exception_log_semantic.critical_path_functions`（默认 `["_on_startup", "run_migrations", "_init_db", "_init_scheduler"]`）在 `config.yaml` 的 `meta_rules_57_63.exception_log_semantic` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.38.0 meta-rule #61
  - **适用**：所有异常处理代码；关键路径（启动/迁移/初始化）；多阶段降级链路；后台任务异常处理；API 路由异常处理
  - **不适用**：纯性能日志；DEBUG 级别日志；非 except 块的 warning（用 exc_info=True）；测试代码
  - **历史教训**：关键路径用 `logger.warning(f"操作失败: {e}")` 丢失 traceback，排查问题只能看到异常消息但无法定位行号，定位耗时 30+ 分钟。修复后定位时间缩短到 5 分钟。同期发现 15+ 处类似问题

- 🆕v4.38【强制】**B-REVIEW-187：EXTERNAL-RESOURCE-LIFECYCLE 外部资源生命周期配对**
  - 维度：9 异步与调度器 / 19 浏览器自动化
  - 严重等级：critical（P0，并发采集时 page 被误关导致 TargetClosedError）
  - 规范引用：meta-rule #62 外部资源生命周期配对管理
  - **检查点**：外部传入的资源（Page/Connection/Lock）必须配对调用 `register`/`unregister`，且在 `finally` 块 `unregister` 避免泄漏
  - **检查项**：
    1. 外部传入资源必须调用 `register_external_page(page)` 注册，使用完毕在 `finally` 块调用 `unregister_external_page(page)` 注销
    2. `unregister` 必须在 `finally` 块中调用，确保异常时也能注销
    3. 并发采集时，资源不被主流程误关（通过 register 标记"资源正在使用"）
    4. `register` 时引用计数 +1，`unregister` 时 -1，计数为 0 时才允许关闭资源
  - **判断信号**：
    - `grep "reuse_page\|external_page\|register_external" <file>` 后检查是否配对 register/unregister
    - `grep "def.*page.*Page" <file>` 参数含 Page 但无 `register_external_page` → 违规
    - `grep "register_external_page" <file>` 但无 `finally.*unregister` → 配对缺失
  - **反模式**：
    ```python
    # 未注册外部传入的 page，主流程可能误关导致 TargetClosedError
    async def collect_items(self, page: Page, item_ids):
        for item_id in item_ids:
            await self._collect_one(page, item_id)
    # 主流程 _cleanup_idle_pages 检测到 page 空闲后关闭 → TargetClosedError
    ```
  - **正确模式**：
    ```python
    # 入口 register + finally unregister + 引用计数管理
    async def collect_items(self, page: Page, item_ids):
        self._register_external_page(page)  # 引用计数 +1
        try:
            for item_id in item_ids:
                await self._collect_one(page, item_id)
        finally:
            self._unregister_external_page(page)  # 引用计数 -1，为 0 才允许关闭
    ```
  - **配置参数**：`meta_rules_57_63.external_resource_lifecycle.enabled`（默认 true）、`meta_rules_57_63.external_resource_lifecycle.resource_types`（默认 `["Page", "Connection", "Lock"]`）、`meta_rules_57_63.external_resource_lifecycle.require_finally_block`（默认 true）、`meta_rules_57_63.external_resource_lifecycle.use_reference_counting`（默认 true）在 `config.yaml` 的 `meta_rules_57_63.external_resource_lifecycle` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.38.0 meta-rule #62
  - **适用**：外部资源传入（Page/Connection/Lock/SSE 连接）；并发采集场景；Playwright Page 共享；跨函数/跨模块资源传递
  - **不适用**：内部创建的资源；单线程使用；一次性资源；`with` 语句管理的资源
  - **历史教训**：`collection_service.py` 接收外部传入的 `page` 但未调用 `register_external_page`，并发采集时主流程 `_cleanup_idle_pages` 检测到 page 空闲后关闭，导致 `TargetClosedError`。修复：入口 register + finally unregister + 引用计数判断

- 🆕v4.38【强制】**B-REVIEW-188：DB-WRITE-IDENTITY-TRACE 数据库写入身份追溯**
  - 维度：15 数据库 / 5 安全
  - 严重等级：major（P1，跨用户写入风险 + converter TypeError）
  - 规范引用：meta-rule #63 数据库写入函数身份追溯与类型安全
  - **检查点**：数据库写入函数必须含 `user_id` 参数用于跨用户隔离；converter 函数处理 `re.Match` 对象必须显式调用 `m.group(1)` 再转型，禁用 `int(m)`
  - **检查项**：
    1. 所有数据库写入函数（`upsert_*` / `insert_*` / `update_*` / `create_*`）必须含 `user_id: str` 参数
    2. 写入 SQL 的 WHERE 子句必须含 `user_id` 条件，禁止跨用户写入
    3. 正则 converter 函数处理 `re.Match` 对象必须显式调用 `m.group(1)` 获取字符串再转型（`int(m.group(1))`），禁用 `int(m)`
    4. Pydantic 模型入口已校验的函数可豁免 user_id（但需注释标注"入口已校验"）
  - **判断信号**：
    - `grep "def upsert_\|def insert_\|def update_\|def create_" <file>` 无 `user_id` 参数 → WARNING
    - `grep "lambda m: int" <file>` 无 `group(1)` → CRITICAL
    - `grep "WHERE.*task_id" <file>` 但无 `AND user_id` → WARNING
  - **反模式**：
    ```python
    # 反模式 1：缺 user_id 参数，跨用户写入风险
    def upsert_eval_event(event: EventRow):
        session.execute(text("INSERT INTO evaluations (task_id, score) VALUES (...)"))

    # 反模式 2：converter 函数直接对 re.Match 调用 int()，TypeError
    _SELLER_LABEL_PATTERNS = {
        "follower_count": (re.compile(r"关注(\d+)"), lambda m: int(m)),
    }
    # TypeError: int() argument must be a string, not 're.Match'
    ```
  - **正确模式**：
    ```python
    # 正确模式 1：写入函数含 user_id 参数，WHERE 子句含 user_id 条件
    def upsert_eval_event(event: EventRow, user_id: str):
        session.execute(text(
            "INSERT INTO evaluations (task_id, user_id, score) VALUES (:task_id, :user_id, :score)"
        ), {"task_id": event.task_id, "user_id": user_id, "score": event.score})

    # 正确模式 2：converter 显式调用 m.group(1) 获取字符串再转型
    _SELLER_LABEL_PATTERNS = {
        "follower_count": (re.compile(r"关注(\d+)"), lambda m: int(m.group(1))),
    }
    ```
  - **配置参数**：`meta_rules_57_63.db_write_identity_trace.enabled`（默认 true）、`meta_rules_57_63.db_write_identity_trace.required_param_name`（默认 `"user_id"`）、`meta_rules_57_63.db_write_identity_trace.function_name_patterns`（默认 `["def upsert_", "def insert_", "def update_", "def create_"]`）、`meta_rules_57_63.db_write_identity_trace.forbidden_converter_patterns`（默认 `["lambda m: int(m)", "lambda m: float(m)"]`）在 `config.yaml` 的 `meta_rules_57_63.db_write_identity_trace` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.38.0 meta-rule #63
  - **适用**：所有数据库写入函数；正则 converter 函数；跨用户系统；含 `re.findall` + converter 的解析逻辑
  - **不适用**：系统级写入（日志表/统计表/全局配置表）；单一调用点的函数；Pydantic 入口校验后的函数；纯查询函数
  - **历史教训**：`_SELLER_LABEL_PATTERNS` 的 converter `lambda m: int(m)` 报 `int() argument must be a string, not 're.Match'`。修复：改为 `lambda m: int(m.group(1))`。同期发现 `upsert_eval_event` 缺 `user_id` 参数导致跨用户写入风险

---

## 快速自检

执行 `pwsh .trae/skills/xianyu-backend-code-review/scripts/auto-scan.ps1` 自动检查以下阻塞项：

1. Token 比较是否使用 `hmac.compare_digest()`（非 `==`）
2. 是否存在硬编码凭据（password/secret/token/api_key）
3. WebView2 子进程是否重定向到 `DEVNULL`
4. WebView2/Playwright 子进程是否使用 `CREATE_NO_WINDOW`（应用 `CREATE_NEW_CONSOLE`）
5. `re`/`threading`/`logging` 是否在模块级导入
6. 是否存在裸 `except:` + `pass`
7. 是否存在已弃用的 `datetime.utcnow()`（应用 `_utcnow = lambda: datetime.now(timezone.utc)`）
8. SQLite 引擎是否使用 `StaticPool`（应用 `NullPool`）
9. `local_embedding.py` 是否设置 `HF_ENDPOINT` 镜像
10. 是否存在 `e.printStackTrace()` 等价（`print(traceback.format_exc())` 替代日志）
11. 是否存在 Pydantic 1.x 的 `.dict()` / `.json()`（应用 `model_dump` / `model_dump_json`）
12. `config/config.yaml` 是否明文暴露敏感凭据（如钉钉推送 Key）
13. `.scannerwork/`、`__pycache__/`、`node_modules/`、`dist/` 等产物是否被 git track（应用 `git rm -r --cached` 清理）
14. 异步方法调用是否遗漏 `await`（合并冲突时优先保留异步版本，禁止同步调用异步方法）
15. 🆕 **S7503**：是否存在无 `await` 的 `async` 函数（应改同步函数）
16. 🆕 **S3776**：是否存在认知复杂度 > 15 的大函数（应拆分；可参考 `login_orchestrator.start_session` 拆分模式）
17. 🆕 **S6767**：是否存在未使用的函数参数/属性/局部变量（应删除或用 `_` 前缀）
18. 🆕 **S1192**：是否存在重复的字符串字面量 ≥ 2 处（应提取为模块级常量）
19. 🆕 **S5843**：是否存在复杂度过高的正则（应拆分或改字符串方法）
20. 🆕 `asyncio.CancelledError` 是否用 `suppress(...)` 包裹并向上传播（禁止 `except: pass`）
21. 🆕 任务函数（`start_all` 等纯编排）是否保留 `async` 关键字而无 await（应改同步）
22. 🆕 `Evaluator` 构造是否接受 `thresholds/weights/keywords` 覆盖参数（会导致用户配置不生效）
23. 🆕 `ChatbotOrchestrator` 是否持有请求级状态（如 `session_id`）（应用 per-session Lock + 无状态设计）
24. 🆕 KB 索引是否仅白名单 `.md/.py/.jsonl/.txt`（应用 `EXCLUDE_DIRS` + `INCLUDE_EXTENSIONS`）
25. 🆕 【强制】ORM `__table_args__` 中的 `Index(...)` 与 `init_db()` 中的 `_migrate_create_index` 一致性（grep 双向比对）
26. 🆕 【强制】`logger.xxx(...)` 调用中不包含 `%s`/`%d`/`%f` 占位符（grep 检测 printf 风格）
27. 🆕 【强制】关键查询方法（`list_*`、`count_*`、`list_and_count_*`）包含 `time.monotonic()` 耗时埋点
28. 🆕 【强制】Repository 层查询方法不在 Python 层做全量加载 + 过滤 + 切片（检测 `SELECT *` 后 `[r for r in rows if ...]` 模式）
29. 🆕v4.0 【强制】"已完成"语义事件（EVAL_PASSED/NOTIFY_SENT）是否在业务逻辑完成后触发（禁止前置触发）
30. 🆕v4.0 【强制】字段覆盖是否按语义分类（基本信息/数值/状态/标识），非一刀切"只填缺失"
31. 🆕v4.0 【强制】资源创建接口（session/start 等）是否幂等（返回 already_active 标志）
32. 🆕v4.0 【强制】搜索接口参数命名是否统一（keyword/page/page_size），响应结构是否统一（items/total/page）
33. 🆕v4.0 【强制】注释是否与代码逻辑一致（无误导性顺序/依赖约束说明）
34. 🆕v4.0 【强制】动态资源映射是否映射表+推断函数分离，业务参数是否通过配置管理
35. 🆕v4.1 【强制】**B-REVIEW-SESSION-SIGNAL**：含重试逻辑的 SSE/HTTP 接口，重试代码块结束后是否检查关键状态标志（如 `last_session_invalid`），状态仍异常是否推送明确错误事件并 return（禁止"重试失败但仍走成功流程"）
36. 🆕v4.1 【强制】**B-REVIEW-COOKIE-CHECK**：依赖多类 Cookie 的接口前置检查是否覆盖所有关键 token（身份 Cookie + 会话 token 如 `_m_h5_tk`），清单是否在 `config.yaml` 的 `cookie_check_lists` 节点管理（禁止只检查身份 Cookie 存在性）
37. 🆕v4.2 【强制】**B-REVIEW-CROSS-FIELD**：dataclass/dict 中语义关联字段对（如 gpu_vendor+gpu_renderer、valid+written_count）是否在构造时校验一致性
38. 🆕v4.2 【强制】**B-REVIEW-NO-HARDCODED-PROPS**：Cookie/HTTP头/DB列属性是否根据数据语义动态设置（禁止批量硬编码 httpOnly:True/secure:True）
39. 🆕v4.2 【强制】**B-REVIEW-NO-CROSS-THREAD-ASYNC**：是否存在 `run_coroutine_threadsafe` + `future.result()` 组合（跨线程死锁风险，应改异步或 fire-and-forget）
40. 🆕v4.2 【强制】**B-REVIEW-TRY-FINALLY-INIT**：try/finally 块中 finally 引用的变量是否在 try 之前初始化为 None
41. 🆕v4.2 【强制】**B-REVIEW-CROSS-COMPONENT-STATE**：多个组件对同一概念（会话有效性/登录状态）做判断时，状态变更是否双向同步
42. 🆕v4.2 【强制】**B-REVIEW-ERROR-HINT-ROUTABLE**：错误提示中引用的 API 端点/方法名是否实际存在
43. 🆕v4.3 【强制】**B-REVIEW-ENCRYPTION-DEGRADATION**：依赖外部进程的加密（如 v20 App-Bound）是否选择运行时接管（CDP/IPC）而非等待离线解密（检测 `CryptUnprotectData` 调用失败的 fallback 逻辑）
44. 🆕v4.3 【强制】**B-REVIEW-FILE-LOCK-BYPASS**：并发访问被锁 SQLite 文件是否使用 `immutable=1` URI 模式（检测 `database is locked` 错误处理逻辑）
45. 🆕v4.3 【强制】**B-REVIEW-SCHEDULER-ISOLATION**：生命周期不同的后台任务是否使用独立 `BackgroundScheduler`（检测 `BackgroundScheduler()` 实例化是否在独立变量中）
46. 🆕v4.3 【强制】**B-REVIEW-CONFIG-DRIVEN-TOGGLE**：高风险功能是否默认关闭 + 参数集中在 `Config` 类（检测 `enable_flag: bool = False` 模式 + `config.yaml` 暴露开关）
47. 🆕v4.3 【强制】**B-REVIEW-FALLBACK-CHAIN**：多重方案是否按优先级降级 + backoff 策略（检测 `max_failures`/`backoff_multiplier`/`max_interval` 是否在配置管理）
48. 🆕v4.3 【强制】**B-REVIEW-CHROME-136-ADAPTATION**：`--remote-debugging-port` 是否配合 `--user-data-dir` 指向非标准目录（检测启动命令参数完整性）
49. 🆕v4.3 【强制】**B-REVIEW-MULTI-PROFILE-DISCOVERY**：多 profile 发现是否优先读结构化元数据 fallback 到目录扫描（检测 `profile.info_cache` 读取逻辑 + 目录扫描 fallback）
50. 🆕v4.3 【强制】**B-REVIEW-WINDOWS-TEST-MOCK**：测试中 Windows 环境变量是否用 `tmp_path` 正确 mock（检测 `monkeypatch.setenv` + 路径结构与实现对齐）
51. 🆕v4.3 【强制】**B-REVIEW-PLUGIN-DEPENDENCY-PRECHECK**：使用 pytest 插件前是否验证项目已安装（检测 `pyproject.toml` 的 `addopts` + `requirements-dev.txt` 声明）
52. 🆕v4.4 【强制】**B-REVIEW-ERROR-SEMANTICS**：错误码到 HTTP 状态码映射是否语义匹配（如 RGV587=token 过期不应映射为 401 登录失效，应映射为 408/503 稍后重试）（检测 `if "RGV587" in error` → 映射状态码的逻辑）
53. 🆕v4.4 【强制】**B-REVIEW-CONFIG-LINKAGE**：config.yaml 新增配置项是否从定义到最终消费点全链路可追踪（grep 字段名确认每层都有读取代码，禁止只注入到 TaskConfig 就认为生效）
54. 🆕v4.4 【强制】**B-REVIEW-FAST-DEGRADATION**：含 `fast=True` 参数的方法，调用方是否在 fast 返回空结果+状态标志异常时自动以 `fast=False` 重试一次（检测 `fast=True` 调用点是否有降级重试逻辑）
55. 🆕v4.4 【强制】**B-REVIEW-NO-HARDCODED-THRESHOLD**：代码中是否存在 `MAX_XXX = N` 硬编码常量且 config.yaml 中已有对应配置项（如 `MAX_CONSECUTIVE_ERRORS` vs `fail_pause_threshold`），应改为读取配置
56. 🆕v4.4 【强制】**B-REVIEW-PARAM-PASS-THROUGH**：方法签名新增参数后是否 grep 所有调用点（含内部 `_private` 方法）确认参数传递（检测 `build_search_url` 新增参数后 `_call_search_api` 内部 URL 构建是否也传递）
57. 🆕v4.5 【强制】**B-REVIEW-MULTI-WRITE-ENTRY**：核心状态（Cookie 层、登录态、连接池）有 ≥ 2 个写入入口时是否有统一同步入口函数（grep `sync_xxx_from_<主数据源>` 模式 + 检测 `on_login_success` 等"被定义未调用"回调）
58. 🆕v4.5 【强制】**B-REVIEW-INACTIVE-STATE-PRESERVE**：状态补救同步条件是否区分"从未初始化"与"主动失效"（检测 `not state.valid` 是否作为补救触发条件，应改为 `state.updated_at == 0.0`）
59. 🆕v4.5 【强制】**B-REVIEW-BROWSER-FALLBACK-SYNC**：状态查询端点（如 `/cookies/layers`）是否实现两步同步（先从主数据源补救 + 后从浏览器内存兜底并回写 JSON）
60. 🆕v4.5 【强制】**B-REVIEW-UPDATE-VS-UPSERT**：持久化层方法命名是否语义清晰（`update_*` 只更新已存在 vs `upsert_*` 更新+添加，检测是否有一个方法兼顾两种语义）；并发场景读-改-写是否在 `RLock` 内完成
61. 🆕v4.5 【强制】**B-REVIEW-POST-WRITE-HOOK**：写主数据源成功后是否显式调用同步钩子（检测 `if json_written: try: sync_xxx_from_json()` 模式；钩子失败是否仅记录日志不抛异常）
62. 🆕v4.5 【强制】**B-REVIEW-DEAD-CODE-CLEANUP**：是否存在"定义未调用"的函数/回调/事件订阅（`grep -rn "<func_name>" src/ tests/` 无结果时必须清理或恢复调用路径）
63. 🆕v4.6 【强制】**B-REVIEW-FILTER-SCENARIO**：同一查询函数被多场景复用时是否参数化场景标志（如 `include_failed`），调用方是否显式传值（操作判断场景 False / 展示历史场景 True），是否新增回归测试覆盖两种场景（检测 `list_*`/`get_*`/`query_*` 函数内硬编码 `if status == 'failed': continue` 模式）
64. 🆕v4.6 【强制】**B-REVIEW-ASYNC-TIMEOUT**：`await` 外部资源（浏览器 `page.query_selector` / HTTP 请求 / 文件 IO）是否在调用层用 `asyncio.wait_for(coro, timeout=N)` 包装（禁止依赖被调用方内部 timeout 参数，如 `page.query_selector` 无 timeout 参数会无限挂起），超时是否返回 504 状态码（参数在 `config.yaml` 的 `async_timeout` 节点管理）
65. 🆕v4.6 【强制】**B-REVIEW-REUSE-PATTERN**：新增功能前是否 grep 项目内相似实现（如 `asyncio.wait_for` / `hmac.compare_digest` / `_escape_like` / `_utcnow`），是否复用既有 helper/工具函数/模式而非重新实现（检测新增函数与既有函数语义重复）
66. 🆕v4.6 【强制】**B-REVIEW-DATA-FLOW-TRACE**：用户反馈"字段为空"时是否按 5 点逐层追踪（DB schema 字段存在 → Repo 查询未过滤 → API 响应注入字段 → 前端 types 声明字段 → render 取值正确），禁止仅查单层就下结论（检测 `list_orders_by_item_ids` 等查询是否在 Repo 层 `if status == 'failed': continue` 一刀切过滤）
67. 🆕v4.9 【强制】**B-REVIEW-STATE-MACHINE-WHITELIST**：业务对象有状态字段且会变化时（如 task.status / session.state / order.status）是否按 6 步流程设计：枚举穷举所有状态值、白名单显式列出允许的转换、终态（completed/failed/cancelled）不可复活、中间态（pending/running）有超时清理、deadline 不可无限重置、前后端枚举值统一（检测 `if status == 'X': status = 'Y'` 散落式转换，应改为 `TRANSITIONS: dict[str, set[str]]` 集中管理；参数在 `config.yaml` 的 `state_machine` 节点管理）
68. 🆕v4.9 【强制】**B-REVIEW-RESOURCE-CLEANUP-HOOK**：可注册组件（BackgroundScheduler / EventBus 消费者 / asyncio.Task / Playwright page / 浏览器实例）是否实现 `cleanup()` / `close()` / `shutdown()` 钩子并在 shutdown 事件中调用；`asyncio.create_task(...)` 返回的 Task 是否保留引用到实例属性防 GC（检测 `asyncio.create_task(...)` 未赋值的 fire-and-forget 模式 + `task.add_done_callback` 未取消模式）；取消+gather 模式是否正确（`await asyncio.gather(*tasks, return_exceptions=True)`）；try/finally 初始化模式是否完整（资源在 try 之前 `= None`，finally 中 `if resource: await resource.close()`）
69. 🆕v4.9 【强制】**B-REVIEW-DUAL-LINK-CONSISTENCY**：同一业务目标（如"刷新会话" / "更新任务状态"）有 ≥ 2 条链路（API 路由 + WebSocket 推送 + 定时任务）时，共用前置条件（如校验登录态/锁竞争/参数合法性）是否提取为独立函数两链路调用同一函数（检测 `api_xxx.py` 与 `scheduler_xxx.py` 中重复的校验代码块，应抽离为 `def _validate_xxx(...): ...` 共享调用）；是否 grep 验证两链路都调用了同一函数；是否新增测试覆盖两链路
70. 🆕v4.9 【强制】**B-REVIEW-CONCURRENT-STATE-LOCK**：共享状态（会话有效性 / 任务列表 / 连接池 / Cookie 层）的"检查 + 更新"是否在同一 `asyncio.Lock` / `threading.RLock` 内完成（检测 `if not self._active: self._start()` 错误模式，应改为 `async with self._lock: if not self._active: await self._start()`）；锁粒度是否最小化（不包裹 IO 密集操作）；锁内是否禁止 `await`（除非使用 `asyncio.Lock`）；dataclass 字段是否显式声明禁止 `getattr(self, 'xxx', default)` 兜底（应 `field1: str = ""` 显式声明默认值）；锁类型选择是否正确（`Lock` 不可重入 vs `RLock` 可重入）
71. 🆕v4.9 【强制】**B-REVIEW-PYTHON-MODERN-ASYNCIO**：是否使用 `asyncio.create_task(coro)` 替代 `asyncio.get_event_loop().create_task(coro)`（Python 3.10+ 推荐做法，避免在无运行循环时抛 DeprecationWarning）；是否避免 `getattr(obj, 'method', fallback)` 兜底（应直接调用 `obj.method()`，缺失方法应在类型层面解决）；模块级 import 是否完整（禁止函数内 `import asyncio` 的延迟导入）；`CancelledError` 是否向上传播（`except BaseException: ...` 应改为 `except Exception: ...` 或显式 `except asyncio.CancelledError: raise`）；类型注解是否用现代语法（`dict[str, str]` 替代 `Dict[str, str]`，`int | None` 替代 `Optional[int]`，需 Python 3.10+）
72. 🆕v4.10 【强制】**B-REVIEW-FILTER-VISIBILITY**：含过滤链路的查询接口（实时搜索/历史查询/列表过滤）是否输出完整 `filter_summary`（含 `raw`/各阶段 `*_skipped`/`final_total`/`filtered_out`）；`filtered_out` 项是否含 `link_type`/`link_key`/`display`/`filter_reason`/`filter_detail` 5 个字段；`max_filtered_out_items` 上限是否从 `config.yaml` 的 `filter_summary` 节点读取（禁止硬编码 50）；过滤链每阶段（keyword/price/publish_days）是否记录跳过计数和详情（检测 `if not match: continue` 未记录到 `filter_summary` 模式）
73. 🆕v4.10 【强制】**B-REVIEW-PYTEST-MODULE-REIMPORT**：conftest.py patch 模块属性时是否遍历 `sys.modules` 找所有持目标属性的模块全部 patch（检测 `for name in ["xxx", "yyy"]: monkeypatch.setattr(...)` 硬编码模块名列表违规模式）；是否使用 `importlib.import_module` 替代 `__import__`（后者返回顶层包而非子模块）；patch 后是否 `assert hasattr(mod, TARGET_ATTR)` 验证生效；跨模块共享配置路径的测试是否用此模式（参数在 `config.yaml` 的 `pytest_isolation` 节点管理）
74. 🆕v4.10 【强制】**B-REVIEW-LOGURU-PLACEHOLDER**：loguru 项目所有 `logger.xxx()` 调用是否使用 `{}` 占位符（检测 `grep -nE 'logger\.(debug|info|warning|error|critical).*%[sdrf]' src/` 命中违规）；混用 `%s`/`%d` 不抛异常但输出字面量极难发现；f-string 简单拼接可用但复杂格式推荐 `{}` 占位符；项目使用的日志库（loguru/logging/structlog）是否在 `config.yaml` 的 `log_placeholder.logger_lib` 节点声明
75. 🆕v4.10 【强制】**B-REVIEW-TEST-FIXTURE-ISOLATION**：conftest.py 是否用 `tmp_path` / `tmp_path_factory` 隔离生产路径（`data/cookies.json`/`*.db`）（检测 `open("data/cookies.json", "w")` 直接写生产路径违规模式）；fixture 数据是否带可识别特征（`test_fixture_` 前缀/`__test__` 后缀，便于污染后定位）；fixture 作用域是否正确（`scope="session"` 跨测试共享 / `scope="function"` 单测试，禁止模块级全局变量持有测试数据）；数据污染应急 5 步流程是否在 `config.yaml` 的 `test_isolation.pollution_recovery_steps` 节点管理
76. 🆕v4.11 【强制】**B-REVIEW-CONFIG-VALIDATION**：数值型配置项是否有边界值校验（min/max/non_zero/range），加载时是否主动校验无效值用默认值+warning（检测 `interval = config.get(...)` 后直接 `interval / N` 算术运算未校验 interval>0 模式，参数在 `config.yaml` 的 `config_validation` 节点管理）
77. 🆕v4.11 【强制】**B-REVIEW-MIGRATION-FAILURE-HANDLING**：`_migrate_*` 函数失败是否明确处理策略（关键迁移 raise RuntimeError 中断启动，非关键 warning+继续），是否含 `except: pass` 静默吞掉违规模式（检测 `_migrate_*` 函数中的 `except.*pass` 模式，参数在 `config.yaml` 的 `migration_failure_strategy` 节点管理）
78. 🆕v4.11 【强制】**B-REVIEW-STATUS-CODE-SEMANTICS**：HTTP 状态码是否按语义精细化区分（401 未登录/403 权限不足/440 Cookie 过期/441 Token 过期/504 网关超时），是否所有认证失败都映射为 401 导致前端无法区分（检测 `raise HTTPException(status_code=401, ".*过期")` 模式，参数在 `config.yaml` 的 `status_code_semantics` 节点管理）
79. 🆕v4.11 【强制】**B-REVIEW-LLM-DEFENSIVE-PARSING**：LLM API 响应是否按三层级防御性解析（choices→message→content，每层用 .get()+isinstance+长度检查），是否含 `response["choices"][0]["message"]["content"]` 链式访问违规模式（参数在 `config.yaml` 的 `llm_defensive_parsing` 节点管理）
80. 🆕v4.11 【强制】**B-REVIEW-SCHEDULER-DB-SYNC**：调度器内存状态变更（pause/resume/stop/error_pause）是否同步 DB（update_task_status），是否只在内存变更导致 API 返回与实际不一致（检测 `pause_event.clear()` 后未调 `update_task_status` 模式，参数在 `config.yaml` 的 `scheduler_db_sync` 节点管理）
81. 🆕v4.11 【强制】**B-REVIEW-BACKGROUND-TASK-MONITOR**：后台 asyncio.Task 是否用轮询监控（task.done() 检查），是否含 `await stop_event.wait()` 静默等待导致任务异常退出无感知违规模式（参数在 `config.yaml` 的 `background_task_monitor` 节点管理）
82. 🆕v4.11 【强制】**B-REVIEW-NUMERIC-EXTRACTION**：多数字文本是否用 `re.findall` 取 `numbers[-1]`（实际成交价通常在最后），是否含 `re.search` 取第一个数字误取原价违规模式（参数在 `config.yaml` 的 `numeric_extraction_strategy` 节点管理）
83. 🆕v4.12 【强制】**B-REVIEW-DOM-FALLBACK-CHAIN**：SPA 数据提取是否实现 DOM → og:meta → document.title 多层兜底（检测 `await page.locator(...).text_content()` 后直接 `return` 无兜底模式）；兜底层级顺序与选择器集合是否在 `config.yaml` 的 `dom_fallback_chain` 节点管理（与 v4.3 B-REVIEW-FALLBACK-CHAIN 的"多方案降级"语义不同，本节点专指 DOM 提取兜底）
84. 🆕v4.12 【强制】**B-REVIEW-FAILURE-DUMP**：关键选择器失败或数据提取异常时是否自动 dump `page.content()` 到 `logs/<scenario>_<id>_<timestamp>.html`（检测 `except ElementNotFound: pass` 或 `except TimeoutError: return None` 无 dump 模式）；dump 是否用 `asyncio.create_task` fire-and-forget 不阻塞主流程；dump 文件名是否含场景标识+时间戳+业务 ID；是否对敏感字段（cookie/token）脱敏；参数在 `config.yaml` 的 `failure_dump` 节点管理
85. 🆕v4.12 【强制】**B-REVIEW-TIMING-INSTRUMENTATION**：关键路径（`page.goto`/`wait_for_selector`/HTTP/DB 查询）是否用 `time.perf_counter()` 计时并按阈值告警（检测 `logger.info("开始")/logger.info("结束")` 文本日志违规模式，应用结构化 timing）；超阈值是否升 `WARNING` 日志级别；阈值与场景白名单是否在 `config.yaml` 的 `timing_instrumentation` 节点管理
86. 🆕v4.12 【强制】**B-REVIEW-PRECHECK-AND-PARALLEL**：高开销操作（浏览器启动/网络采集）前是否前置校验 Cookie 凭证 `expires` 字段（检测 `async with async_playwright()` 后才校验 Cookie 的违规模式，应前置校验过期直接返回 440）；session cookie（`expires=-1`）是否跳过预校验；独立 IO 任务是否用 `asyncio.gather(*tasks, return_exceptions=True)` 并行（检测 `for task in tasks: await task` 串行违规模式）；`gather` 是否传 `return_exceptions=True` 隔离异常；身份 Cookie 白名单与并发上限是否在 `config.yaml` 的 `precheck_parallel` 节点管理
87. 🆕v4.8 【强制】**B-REVIEW-STATE-FLAG-PRECHECK**：状态标志设置后是否有前置检查（grep `self.*= True` 状态标志 → 检查操作入口是否有 `getattr(self, "flag", False)` 检查）；是否有重置机制（grep `flag = False`）（参数在 `config.yaml` 的 `state_flag_precheck` 节点管理）
88. 🆕v4.8 【强制】**B-REVIEW-LOG-DOWNGRADE-STABILITY**：日志降级判断是否用模块级常量（检测 `logger.log(log_level` 动态级别 → 检查判断条件是否含魔法字符串，应提取为模块级常量并注释文案来源）（参数在 `config.yaml` 的 `log_downgrade` 节点管理）
89. 🆕v4.8 【强制】**B-REVIEW-EDIT-VERIFY**：修复代码中引用的变量/函数是否真正存在于文件中（grep 标志性标识符确认无 false positive，无匹配则重新执行 Edit）；适用所有使用 Edit 工具的修改场景
90. 🆕v4.13 【强制】**B-REVIEW-STATS-EXCLUSIVE**：统计接口返回的分类计数是否互斥（`total = sum(各分类计数)`，如 `api_evaluations.py` 的 dist 统计中 insufficient(score==null) 与 auto/pass/fail(有评分) 互斥，`total = insufficient_count + auto + pass + fail`）；是否 grep 后端统计代码确认分类逻辑互斥；是否验证 total 等于各分类之和（禁止一个记录同时计入两个分类导致统计数量与实际不符）；非互斥分类（如标签统计，一个记录可属于多个分类）是否排除；适用场景：评分分布统计、状态分组统计、任何返回分类计数的 API；不适用场景：非互斥分类（如标签统计）；分类定义和互斥规则是否在 `config.yaml` 的 `stats_exclusive` 节点管理
91. 🆕v4.15 【强制】**B-REVIEW-CACHE-INVALIDATION**：任何持久化层（JSON 文件 / SQLite / 外部配置）变更后是否**显式调用**对应缓存对象的 `invalidate_cache()` 或等价方法（检测类含 `_cache`/`_cache_time`/`_cached_*` 字段但无 `invalidate_cache()` 方法的违规模式）；是否仅依赖 TTL 兜底（`time.time() - self._cache_time < 30` 模式违规，跨进程不一致）；跨进程变更（子进程写、主进程读）是否主动通知主进程失效缓存（检测子进程 `write_json()` 后只更新自己缓存未通知主进程的模式）；同步钩子失败是否仅 `logger.warning` 不抛异常；适用场景：JSON 持久化层、跨进程 Cookie/状态同步、内存缓存与文件副本同步、登录态多进程写入；不适用场景：纯函数、纯计算缓存（LRU math）、无外部数据源同步的内部状态；参数在 `config.yaml` 的 `cache_invalidation` 节点管理
92. 🆕v4.15 【强制】**B-REVIEW-STATE-DETECTION-BOOTSTRAP**：任何"功能信号"字段（`last_session_invalid`/`is_healthy`/`is_connected` 等）默认值 `False` 是否被用作"功能正常"的判定条件（检测 `if not collector.last_session_invalid:` 误用初始 False 模式）；强制恢复/兜底逻辑是否仅依赖布尔字段未配合"已发生过检测"标记（`_last_m5tk_refresh > 0` / `use_count > 0` / `_has_run`）；强制恢复范围是否超出信号能证明有效的层（如 `m5tk_signal` 恢复 IDENTITY 层违规）；未识别的信号组合是否默认恢复所有层（应 `logger.warning` 后 `set()`）；适用场景：跨进程/跨模块状态判定、Cookie 层状态自愈、容器健康检查、服务可用性兜底；不适用场景：纯客户端 UI 状态、单次函数返回值、无初始歧义的开关字段；参数在 `config.yaml` 的 `state_detection_bootstrap` 节点管理
93. 🆕v4.15 【强制】**B-REVIEW-MIGRATION-TRANSACTION**：SQLite `_migrate_*` 函数是否用 `engine.begin()` 单事务包裹整个 DDL 过程（检测多个 `conn.commit()` 拆分布骤违规模式）；迁移前是否 `DROP TABLE IF EXISTS {table}_old` 清理残留（避免上次失败导致 RENAME 阻塞）；`orm_table.create(...)` 是否传入 `conn` 而非 `engine`（确保 DDL 纳入事务）；数据复制是否用列名交集（防止列差异导致 INSERT 失败）；失败后是否从 `{table}_old` RENAME 恢复（异常路径完整性）；是否含 SQLite 不支持的 `ALTER TABLE ... MODIFY COLUMN` / `ALTER TABLE ... ALTER COLUMN` 违规模式（应改用表重建）；适用场景：SQLite 修改列约束、表重建、任何不可逆 DDL；不适用场景：PostgreSQL/MySQL（有原生 DDL 事务）、新增列（直接 `ADD COLUMN`）、纯查询/插入操作；参数在 `config.yaml` 的 `migration_transaction` 节点管理
102. 🆕v4.20 【强制】**B-REVIEW-VERSION-SOURCE-SINGLE**：构建期元数据（版本号/构建时间/git_sha）是否有唯一源头文件（`__init__.py: __version__`）+ 自动生成文件（`_build_info.py` 由 `scripts/build_info.py` 维护）；多端点读取同一元数据是否封装 `_safe_xxx()` 三层 try/except 回退辅助函数（源头 → 生成文件 → 默认值 `'unknown'`）；`export_config`/`about`/`health` 等多端点响应中版本号字段是否调用辅助函数（检测 `grep -E '"version":\s*"[^"]+"' src/xianyu_hunter/web/routes/` 命中硬编码字符串的违规模式，应改为 `_safe_app_version()`）；是否使用 `"1.0"`/`"0.0.0"`/`"unknown version"` 等占位符（违规，应改为 `'unknown'`）；`grep "from xianyu_hunter import __version__" src/` 出现 ≥ 2 处时是否封装辅助函数；端点命名含 "version" 但实际返回业务计数的（如 `/api/config/version` 返回 `len(backups)`）是否在 docstring 中明确语义，参数在 `config.yaml` 的 `version_source_management` 节点管理（`single_source_file` / `auto_generated_file` / `safe_helper_function` / `fallback_default` / `forbidden_placeholders` / `forbidden_version_endpoints` / `helper_threshold`）
103. 🆕v4.22 【强制】**B-REVIEW-STARTUP-HOOK-COMPLETENESS**：所有依赖 `container.browser`/`container.collector` 的组件是否在 `startup.py _on_startup` 中有对应 `start_xxx()` 启动钩子（检测 `grep container.browser/collector` 找所有依赖点逐个检查是否有对应启动调用）；启动钩子是否用 `if _should_start_scheduler()` 包裹；是否放在依赖的调度器之后；启动失败 try/except 兜底是否仅 warning 不阻断主服务；参数在 `config.yaml` 的 `startup_hook_completeness` 节点管理
104. 🆕v4.22 【强制】**B-REVIEW-TASK-HISTORY-THREE-LAYER-PROTECTION**：写入 `running` 状态的代码路径是否有对应 `finalize` 调用更新为终态；是否覆盖正常结束/future.result超时/协程异常三条路径；错误消息累积是否设 FIFO 上限避免 JSON 字段无限膨胀；状态语义是否区分 `circuit_broken→failed` / `_stop_flag→cancelled` / 正常→completed；参数在 `config.yaml` 的 `task_history_protection` 节点管理
105. 🆕v4.22 【强制】**B-REVIEW-COUNTER-DB-MAX-INIT**：业务自增 ID（如 `task_id`/`batch_id`/`run_id`）是否在调度器 `__init__` 时从 DB `SELECT MAX(id)` 初始化（禁止依赖内存初始化，进程重启会重置）；查询失败是否回退到 0+warning 不阻断启动；`trigger_now` 时是否 +1 立即返回前端不等待 DB 写入；参数在 `config.yaml` 的 `counter_db_max_init` 节点管理
106. 🆕v4.22 【强制】**B-REVIEW-APSCHEDULER-INTERVAL-FIRST-RUN**：APScheduler interval 触发器是否设 `next_run_time=now+delay`（默认首次执行时间为 start+interval，启动后等完整间隔）；delay 建议 5-10 秒给初始化依赖就绪；日志是否输出间隔+首次执行时间；参数在 `config.yaml` 的 `apscheduler_interval_first_run` 节点管理
107. 🆕v4.23 【强制】**B-REVIEW-LLM-CAPABILITY-DISPATCH**：任何 LLM/多模态/function_call/json_mode 调用是否在构造 payload 前预检目标模型能力（检测直接构造 `messages=[{"type": "image_url", ...}]` 无能力预检的违规模式）；能力校验函数是否共享（`api_ai._is_vision_capable`，禁止散落内联判断）；关键字白名单是否配置化（`config.yaml` 的 `llm_capability_keywords` 节点）；参数在 `config.yaml` 的 `llm_capability_keywords` 节点管理
108. 🆕v4.23 【强制】**B-REVIEW-SHARED-UTIL-CENTRALIZATION**：跨 ≥2 模块复用的判断逻辑/关键字白名单/常量是否抽取为"被依赖方"模块顶层的纯函数或模块级常量（检测跨 ≥2 文件出现相同关键字/正则/常量字面量必须触发"抽取共享"建议）；导入方是否只能 `from <source> import <shared>`；参数在 `config.yaml` 的 `shared_util_rules` 节点管理
109. 🆕v4.23 【强制】**B-REVIEW-SILENT-DOWNGRADE-PRECHECK**："可选增强"能力（vision/function_call/json_mode）调用前是否预检（检测代码构造 payload 时未做能力预检的违规模式）；失败时是否降级为等价文本表达（如 prompt 追加"图片 URL + 描述"）而非抛错；预检失败日志级别是否 `logger.warning`（与 v4.9 B-REVIEW-LOG-DOWNGRADE-STABILITY 一致）；降级 prompt 模板是否集中管理（`config.yaml` 的 `llm_downgrade` 节点）；是否区分"可选增强"与"核心能力"（核心能力缺失必须报错）；参数在 `config.yaml` 的 `llm_downgrade` 节点管理
110. 🆕v4.25 【强制】**B-REVIEW-MIGRATION-BLOCK-ISOLATION**：迁移函数（如 `run_migrations`）内含多个独立迁移块（C-01/C-02/C-03/C-04/C-05）时是否各自 try/except（检测外层 `try: ... except Exception as e: logger.warning(f"启动迁移钩子失败: {e}")` 包裹多个迁移块的违规模式）；强依赖场景（如表重建+数据回填）允许合并但必须在注释中说明合并原因；每个块的 except 是否用 `logger.warning` 或 `logger.exception` 记录（禁止 `except: pass`）；块边界标识符是否在 `config.yaml` 的 `migration_block_isolation.block_markers` 节点管理；参数在 `config.yaml` 的 `migration_block_isolation` 节点管理（`function_patterns` / `block_markers` / `require_independent_try` / `allow_merge_when_dependent` / `violation_message`）
111. 🆕v4.25 【强制】**B-REVIEW-CRITICAL-PATH-NO-SWALLOW**：启动钩子（`_on_startup`）/迁移函数（`run_migrations`）/初始化函数（`_init_*`）等关键路径的外层 except 是否用 `logger.exception()` 输出完整 traceback（检测 `except Exception as e: logger.warning(f"...{e}")` 丢失堆栈的违规模式，检测 `except Exception as e: logger.warning("...: {}", e)` loguru 占位符也不保留 traceback 的违规模式，检测 `except: pass` 完全吞掉的违规模式）；关键路径函数清单是否在 `config.yaml` 的 `critical_path_no_swallow.critical_functions` 节点管理；禁止日志模式是否在 `critical_path_no_swallow.forbidden_patterns` 节点管理；允许的简单 warning 场景（非关键路径）是否在 `critical_path_no_swallow.allowed_simple_warning` 节点管理；参数在 `config.yaml` 的 `critical_path_no_swallow` 节点管理
112. 🆕v4.26 【强制】**B-REVIEW-EXCLUDE-UNSET-CHECK**：PATCH/PUT 接口是否用 `model_dump(exclude_unset=True)` 区分未传/传null/传值三态（检测 `for k, v in data.items(): if v is not None: ...` 手动循环跳过 None 的违规模式，会丢失"传 null 表示清除覆盖"的语义）；是否覆盖字段传 null 表示清除覆盖应正常写入 None；参数在 `config.yaml` 的 `api_update_semantics` 节点管理
113. 🆕v4.26 【强制】**B-REVIEW-NOT-NULL-NONE-DEFENSE**：NOT NULL 字段传 null 时是否防御性 pop 而非直接写入 DB 触发 IntegrityError（检测 `model_dump(exclude_unset=True)` 后未对 NOT NULL 字段做 None 检查的违规模式）；覆盖字段传 null 表示清除覆盖应正常写入 None（与 B-REVIEW-EXCLUDE-UNSET-CHECK 联动）；参数在 `config.yaml` 的 `api_update_semantics` 节点管理
114. 🆕v4.26 【强制】**B-REVIEW-SHARED-SINGLETON-POLLUTION**：循环中创建任务级覆盖对象是否用局部变量 `worker_xxx`（检测 `container.config = new_config` 直接修改 container 单例的违规模式，会污染下一轮迭代）；任务级覆盖对象生命周期是否与循环迭代绑定（迭代结束后自动释放）；参数在 `config.yaml` 的 `shared_singleton_protection` 节点管理
115. 🆕v4.27 【强制】**B-REVIEW-FAILURE-REASON-PROPAGATION**：失败原因是否分三层传递（底层 `last_*_failure_reason` → 中层 status_code 映射 → 高层日志降级，检测 `if "expired" in detail` 字符串子串判断违规模式）；reason 值是否可枚举集中管理（`FAILURE_REASONS: tuple[str, ...]`，禁止散落字符串）；错误响应是否含 `error_code` 字段（前端按 error_code 分支而非按文案子串）；参数在 `config.yaml` 的 `failure_reason_propagation` 节点管理
116. 🆕v4.27 【强制】**B-REVIEW-DATA-COMPLETENESS-PRECHECK**：调用外部依赖前是否执行数据完整性预检（预检方法签名 `async def _check_xxx_completeness(self) -> str | None`，检测 `if len(cookies) < 10` 单阈值违规模式）；是否用双阈值 AND 判断（总数 + 关键项命中数）；调用后是否二次检查（防御外部依赖中途失效）；错误信息是否含具体缺失清单（禁止笼统"数据不完整"）；参数在 `config.yaml` 的 `data_completeness_precheck` 节点管理
117. 🆕v4.27 【强制】**B-REVIEW-MERGE-VS-OVERWRITE-WRITE**：持久化层写入策略是否匹配数据来源（部分集→合并写 `merge_*`，完整集→覆盖写 `save_*`/`export_*`，检测浏览器 Cookie 导入用覆盖写丢失旧数据的违规模式）；合并写方法签名是否为 `def merge_xxx(self, new_items: list[dict] | dict) -> bool`；合并后是否日志输出合并前后数量；覆盖写前是否预检新集完整；参数在 `config.yaml` 的 `write_strategy_decision` 节点管理
118. 🆕v4.27 【强制】**B-REVIEW-ERROR-MESSAGE-CONSTANT**：错误文案/日志降级 marker/用户提示信息是否提取为模块级常量（`_ERROR_MSG_*` / `_LOG_MARKER_*`，检测 `if "expired" in` / `if "unavailable" in` 字符串子串判断违规模式）；跨模块引用是否 `from <source> import _MSG_*`；错误响应是否含 `error_code` 字段；同一文案在代码中出现 ≥ 2 处未提取为常量即违规（与 B-REVIEW-LOG-DOWNGRADE-STABILITY 联动）；参数在 `config.yaml` 的 `error_message_centralization` 节点管理
119. 🆕v4.27 【强制】**B-REVIEW-EDIT-VERIFY-DEPLOY-LOOP**：Edit 工具修改文件后是否立即用 Grep/Read 验证标志性标识符确实存在（检测 AI 助手修改后未 grep 验证的违规模式）；Python 修改后是否重启服务（检测用户反馈"还是报错"且 Python 进程启动时间早于代码修改时间的违规模式）；重启后是否验证端口监听 + 数据状态；`git stash` 前是否先 `git commit` 保底；参数在 `config.yaml` 的 `edit_verify_deploy_loop` 节点管理
120. 🆕v4.27 【强制】**B-REVIEW-TEST-MOCK-SYNC**：修改前置条件（新增预检方法/配置项/方法参数）时是否同步更新测试 mock 数据（检测新增 `_check_*_completeness` 后原 mock 数据不完整导致测试失败的违规模式）；mock 数据是否覆盖完整字段集（如 22 个 cookie 而非 4 个）；mock 数据是否集中管理在 `conftest.py`；测试失败时是否优先检查前置条件变更（grep 最近修改的方法签名）；参数在 `config.yaml` 的 `test_mock_synchronization` 节点管理
121. 🆕v4.28 【强制】**B-REVIEW-MULTI-USER-RESOURCE-ISOLATION**：单用户系统升级到多用户时，全局单例资源是否按 `user_id` 维度隔离（检测 `cookies.json` 单例路径、`_cache: dict` 全局缓存变量、公共方法签名无 `user_id` 参数的违规模式）；文件路径是否加 `user_id` 维度（`cookies_{uid}.json`）；缓存是否分桶（`dict[str, tuple[dict, float]]`，按 user_id 取桶）；公共方法是否有 `user_id="default"` 默认参数；`user_id` 拼接文件路径前是否做白名单校验（正则 `^[A-Za-z0-9_-]{1,64}$` 防路径遍历）；SQLite 兜底是否判断 `user_id == default`；**适用**：单用户→多用户升级、多租户、多账号管理；**不适用**：纯内部工具、单租户 SaaS、用户数固定为 1；参数在 `config.yaml` 的 `multi_user_resource_isolation` 节点管理（`user_id_pattern` / `default_user_id` / `isolation_dimensions` / `exclude_paths`）
122. 🆕v4.28 【强制】**B-REVIEW-AUTH-MULTI-PATH-VALIDATION**：多种认证方式（管理令牌 + 用户会话）时，中间件是否按优先级链式校验（检测中间件单一 token 校验、无 `user_id` 注入、异常静默降级的违规模式）；是否实现三路校验顺序（`WEB_TOKEN` 直通 → `session_token` 查库 → 401）；token 比较是否用 `hmac.compare_digest` 防时序攻击（禁止 `==` 直接比较）；异常降级是否用 `logger.warning`（禁止 `logger.debug` 静默）；是否将 `user_id` 注入 `request.state` 供下游使用；日志是否禁止泄露 token 明文（必须脱敏）；公开路径白名单是否放行（白名单来自 `auth.public_prefixes` 配置）；**适用**：管理后台+用户前台混合认证、多角色系统；**不适用**：单一认证方式、纯 API 网关、内部微服务；参数在 `config.yaml` 的 `auth_multi_path_validation` 节点管理（`web_token_compare_func` / `session_verify_method` / `exception_log_level` / `public_prefixes_config` / `forbidden_log_levels`）
123. 🆕v4.28 【强制】**B-REVIEW-SESSION-TOKEN-SECURITY**：会话 token 的生成、存储、校验、撤销是否遵循安全最佳实践（检测 token 明文存库、用 `==` 比较、无滑动续期、撤销不清缓存的违规模式）；是否用 `secrets.token_urlsafe` 生成（禁止 `random.choices` / `uuid.uuid4` 截断）；是否用 `sha256` 存储哈希（禁止存明文）；校验是否用 `hmac.compare_digest`；是否实现滑动续期（距过期不足 `renewal_threshold_days` 天时延长 `ttl_days`）；撤销是否清缓存 + 标记 `is_active=0`；缓存与撤销是否互斥（同一 `RLock` 内完成读-改-写）；是否实现会话固定防护（签发新 session 前失效旧 session）；**适用**：涉及用户会话的系统、需防时序攻击、需滑动续期；**不适用**：无状态 JWT、一次性 token、内部服务通信；参数在 `config.yaml` 的 `session_token_security` 节点管理（`token_generate_func` / `token_generate_length` / `token_hash_algo` / `compare_func` / `ttl_days` / `renewal_threshold_days` / `revoke_clear_cache` / `session_fixation_protection`）
124. 🆕v4.28 【强制】**B-REVIEW-SNAPSHOT-REALTIME-OVERWRITE**：历史快照与实时采集数据合并时是否按字段类型分档覆盖（检测 `_enrich_*` 函数所有字段都用 `if not existing: existing = new` 的违规模式，会丢失实时更新）；非空字段（`title` / `url` / `id` / `region` / `brand` / `seller_id` / `publish_time`）是否新值存在则覆写；数值字段（`price` / `count` / `view_cnt` / `want_cnt`）是否新值 > 0 才覆写（防止 0 误覆盖真实数据）；状态字段（`is_sold` / `is_deleted`）是否始终覆写（实时性最高）；标识字段（`seller_nick` / `nickname`）是否只填缺失（标识稳定不变）；每档覆盖策略是否有单元测试覆盖；覆盖策略是否有注释说明每档判断依据；**适用**：数据采集系统、缓存与源数据同步、历史快照与实时更新并存；**不适用**：纯实时系统、纯审计系统、纯日志系统；参数在 `config.yaml` 的 `snapshot_realtime_overwrite` 节点管理（`overwrite_strategy.non_empty_fields` / `overwrite_strategy.positive_numeric_fields` / `overwrite_strategy.state_fields` / `overwrite_strategy.identity_fields` / `require_unit_test`）
125. 🆕v4.28 【强制】**B-REVIEW-USER-IDENTITY-PRIORITY**：用户身份识别是否有明确优先级链且配置化管理（检测硬编码身份识别逻辑、无优先级链、无降级策略的违规模式）；是否实现优先级链（`unb` > `cookie2` 哈希 > `default`）；每级是否有正则/哈希校验（如 `unb` 匹配 `^\d{8,}$`、`cookie2` 用 `sha256` 取前 16 位）；优先级链是否配置化（`config.yaml` 的 `user_identity_priority.priority_chain`）；最终是否降级到 `default` 用户（禁止抛错阻断流程）；识别后是否调用 `identify_or_create` 确保库内有记录（避免后续查询空指针）；**适用**：多用户系统、Cookie 认证、多账号管理；**不适用**：无用户概念的工具、固定用户系统；参数在 `config.yaml` 的 `user_identity_priority` 节点管理（`priority_chain[].source` / `priority_chain[].pattern` / `priority_chain[].hash` / `priority_chain[].length` / `require_identify_or_create`）

---

## 审查流程（4 阶段流水线）

> v4.28.0 优化：从 5 阶段闭环精简为 4 阶段流水线，合并前置检查与上下文收集为"上下文加载"，新增"优先级分类"阶段（P0/P1/P2/P3 四级），结果呈现改为结构化报告模板。

### 阶段 1：上下文加载

1. **加载配置**：读取 `config.yaml`（含 v4.28.0 新增的 `coding_standards` 节点，覆盖 datetime/migration/null_defense/query_filter/enum_consistency/error_attribution/log_noise/circuit_breaker/state_sync/credential_stores/retry/param_chain/dataclass/startup/mock/cookie/parser/encoding/dry/contract/persist/race/keywords 23 个子节点）
2. **确定评审范围**：
   - **待提交变更模式**：`git diff HEAD` + `git status` 提取改动的 `.py` 文件
   - **指定文件模式**：用户明确指定的文件列表
   - **片段评审模式**：用户粘贴的代码片段（无文件路径时仅输出建议）
   - 应用 `scope.include_paths` / `scope.exclude_paths` 过滤，截取 `scope.max_files_per_run` 个文件
3. **识别任务类型**：前端 / 后端 / 全栈（本技能专注后端，前端由 `xianyu-frontend-code-review` 处理）
4. **加载对应 coding-rules/ 主题文件**：根据评审范围加载 `references/` 下的架构/异步并发/SQLAlchemy/安全/性能/缓存状态/编码 IO/可维护性/YAML 配置等主题文件
5. **收集文件上下文**：对每个待评审文件，使用 Read 读取完整内容，使用 Grep 查找关键依赖（导入模块/项目内调用/DB 表引用），使用 Grep 查找相关测试文件评估测试覆盖，记录 `git log --oneline -5 -- <file>` 修改历史

**判断逻辑**：范围必须收紧——只评审用户提供的或明确引用的文件，不顺便审查旁边代码。

### 阶段 2：分层扫描

按 `checklist` 配置的 29 大类逐层扫描（见上文"审查规则"章节），每个维度引用对应 B-REVIEW checkpoints：

1. **维度 1-6（架构/Pydantic/SQLAlchemy/SQLite）**：引用 B-REVIEW-121~126（时区一致性/原生 SQL 类型防御/迁移步骤独立性/NOT NULL 字段防御/查询过滤条件精确性/状态值枚举一致性）
2. **维度 7-12（安全/性能/异步/事件总线/错误处理/日志）**：引用 B-REVIEW-127~131（错误归因精细化/异常传播完整性/错误消息透传/重试策略配置化/已知场景日志降噪）
3. **维度 13-19（代码质量/配置管理/智能客服/Git/Chrome 适配/跨字段/API 设计）**：引用 B-REVIEW-138~146（参数传递链/业务关键词配置化/开关持久化/凭证多存储同步/属性调用一致性/API 契约一致性/命名语义清晰性/重复逻辑抽取/跨进程编码一致性）
4. **维度 9（异步与调度器）扩展**：引用 B-REVIEW-132~137（熔断器持久化对称性/状态切换原子性/多源失效判定一致性/缺失数据回退策略/多源状态同步标记机制/异步竞态防护）
5. **维度 20-29（测试/Composition Root/多用户隔离/LLM 能力派发/端到端失败原因链）**：引用 B-REVIEW-147~150（dataclass 字段显式声明/启动钩子完整性/测试 Mock 类型匹配/Cookie 完整性管理）

**扫描方法**：对每个维度，使用 Grep 工具扫描代码库（pattern 字段），对比反模式示例识别问题，匹配到的违规项记录到报告。**硬约束违规优先级最高**，无论 severity 如何，必须在报告中突出显示。

### 阶段 3：优先级分类

按问题严重程度分为 4 级（替代原 severity_order × category_order 矩阵）：

- **P0 阻塞性**：安全漏洞 / 数据丢失 / 崩溃 / 硬约束违规（必须修复才能合并）
  - 示例：Token 比较用 `==`（B-REVIEW 硬约束）、SQLite 用 `StaticPool`、`datetime.utcnow()` 弃用、敏感字段明文存储
- **P1 严重**：逻辑错误 / 性能问题 / 状态不一致 / 异常吞掉（应该修复）
  - 示例：B-REVIEW-121 时区一致性（TypeError 崩溃）、B-REVIEW-128 异常传播完整性（隐藏问题）、B-REVIEW-132 熔断器持久化对称性（状态丢失）
- **P2 改进**：代码质量 / 可维护性 / 配置化 / 重复逻辑（建议修复）
  - 示例：B-REVIEW-130 重试策略配置化、B-REVIEW-139 业务关键词配置化、B-REVIEW-145 重复逻辑抽取
- **P3 微调**：风格 / 注释 / 命名优化（可选修复）
  - 示例：B-REVIEW-144 命名语义清晰性、注释一致性、变量名优化

**分类规则**：硬约束违规统一为 P0；影响功能正确性/稳定性为 P1；影响可维护性/配置化为 P2；纯风格为 P3。

### 阶段 4：结果呈现

按结构化报告模板生成报告（见下文"输出模板"章节）。报告内容包括：
1. **审查概览**：审查范围/审查维度/问题统计（P0/P1/P2/P3 数量）/规范版本
2. **问题详情**：每个问题含编号/维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示例/优先级
3. **与上次审查对比**：🆕新增 / ✅已修复 / ⚠️仍存在
4. **好的实践**：正面反馈
5. **测试运行结果**（若 `verify.run_tests_after_review=true`）
6. **审查结论与修复验证指引**

---

## 评审范围判断

- **待提交变更模式**：`git diff HEAD --name-only` + 过滤 `.py` 文件
- **指定文件模式**：用户明确列出文件路径
- **片段模式**：用户粘贴代码但无文件路径（仅输出建议，不输出 File:Line）
- **范围必须收紧**：不顺便审查旁边代码，不主动扩展到未提及的文件

## 误报识别判断

- 路径匹配 `scope.exclude_paths`：跳过
- 测试文件中的规范类问题：降级处理
- 生成代码（含 `# @generated` 注释或 `__pycache__` 路径）：跳过
- 第三方库代码：跳过
- 迁移文件（`_migrate_*` 函数）：幂等性已保证，不再要求事务包裹

## 修复建议判断

- 必须提供可操作的修复建议（含代码示例）
- 建议必须解释"为什么"而非仅"做什么"
- 若问题需要代码修改，在报告末尾询问用户是否应用修复

## 失败恢复机制

1. **文件读取失败**：记录跳过原因，继续评审其他文件
2. **Grep 超时**：缩小搜索范围或跳过该检查项
3. **测试运行失败**：输出测试失败信息，不阻止报告生成
4. **配置文件缺失**：使用内置默认配置并提示用户创建 `config.yaml`

---

## 审查判断标准

| 🟠阻塞(必须修复) | 🟠严重(强烈建议) | 🟡警告(建议) |
|-----------------|-----------------|-------------|
| 违反分层架构（跨层调用） | 服务调用缺必需字段 | 格式化不规范 |
| 缺失模块级导入（re/threading/logging） | 未查看服务方法实现 | 变量命名不规范 |
| Token 比较未用 `hmac.compare_digest()` | 异常处理不完善（吞异常/丢堆栈） | 冗余代码 |
| 硬编码密码/密钥/钉钉推送 Key | 空指针风险（链式调用未判空） | 注释不清晰 |
| SQL 字符串拼接（未用 `_escape_like`） | N+1 查询/循环调 DB | 魔法数字未提取常量 |
| 凭据明文写入 `config.yaml` | 日志含敏感信息 | 函数过长 |
| 使用已弃用 `datetime.utcnow()` | async 代码中阻塞 IO | 缺少类型注解 |
| SQLite 引擎用 `StaticPool`（应用 `NullPool`） | `asyncio.Task` 未保留引用 | 缺少测试 |
| WebView2 用 `CREATE_NO_WINDOW` | `CancelledError` 被静默吞掉 | 嵌套层级过深 |
| WebView2 重定向到 `DEVNULL` | `EventBus` 消费者未处理 `QueueEmpty` | 注释复述代码 |
| 裸 `except:` + `pass` | 未设置 `HF_ENDPOINT` 镜像 | DTO 未实现 Serializable（Pydantic 默认） |
| Pydantic 1.x `.dict()` / `.json()` | `sentence-transformers` 跨版本未 fallback | 路由缺少 tags |
| `config/config.yaml` 明文暴露凭据 | `ChatbotOrchestrator` 持有请求级状态 | 缺少文档字符串 |
| GET 请求引发状态变更 | `_scan_and_chunk` 未排除 `web/static/` | 缺少 `__all__` |
| 响应返回 ORM 对象（非 DTO） | `_overview()` 未用 CASE WHEN 合并 | 魔法字符串 |
| 必填字段缺失索引 | Web 进程未用 `with_browser=False` | - |
| `webview.start()` 未设 `private_mode=False` | `PriorityBrowserLock` 优先级缺失 | - |
| 循环依赖 A→B→C→A | `Container` 未深拷贝 chatbot 配置 | - |
| `local_embedding.py` 未设 HF 镜像 | Evaluator 接受覆盖参数 | - |
| 产物文件（`.scannerwork/` 等）被 git track | 异步方法调用遗漏 `await` | - |
| 🆕 无 `await` 的 `async` 函数（S7503） | 🆕 重复字符串字面量 ≥ 2 处未提取为常量（S1192） | - |
| 🆕 认知复杂度 > 15 未拆分（S3776） | 🆕 复杂正则未拆分（S5843） | - |
| 🆕 未使用的参数/属性/局部变量（S6767） | 🆕 `Evaluator` 接受 `thresholds/weights/keywords` 覆盖参数 | - |
| 🆕 `asyncio.CancelledError` 被 `except: pass` 静默吞掉 | 🆕 KB 索引未排除 `web/static/` 等前端构建产物 | - |
| 🆕v4.0 "已完成"事件在业务逻辑前触发（EVAL_PASSED 前置） | 🆕v4.0 字段覆盖一刀切"只填缺失"（应按语义分类） | - |
| 🆕v4.0 资源创建接口非幂等（重复调用重复创建） | 🆕v4.0 搜索接口参数/响应结构不统一 | - |
| 🆕v4.0 注释与代码逻辑不一致（误导性约束说明） | 🆕v4.0 动态资源映射表与推断函数混合 | - |
| 🆕v4.1 重试失败后未检查状态标志直接走成功流程（B-REVIEW-SESSION-SIGNAL） | 🆕v4.1 Cookie 检查只覆盖身份 Cookie，忽略会话 token（B-REVIEW-COOKIE-CHECK） | - |
| 🆕v4.1 错误粒度不区分（401/403/502/503/504 混用） | - | - |
| 🆕v4.2 语义关联字段矛盾（如 gpu_vendor 配不匹配的 gpu_renderer） | 🆕v4.2 跨组件对同一概念判断维度未同步 | - |
| 🆕v4.2 Cookie/HTTP属性硬编码（批量 httpOnly:True） | 🆕v4.2 错误提示引用不存在的端点 | - |
| 🆕v4.2 run_coroutine_threadsafe + future.result() 死锁组合 | - | - |
| 🆕v4.2 try/finally 变量未初始化为 None | - | - |
| 🆕v4.3 v20 加密用 `CryptUnprotectData` 离线解密（应 CDP 接管）（B-REVIEW-ENCRYPTION-DEGRADATION） | 🆕v4.3 多 profile 发现只读 Default（应读 `profile.info_cache`+fallback 扫描）（B-REVIEW-MULTI-PROFILE-DISCOVERY） | - |
| 🆕v4.3 SQLite 文件锁报错未用 `immutable=1` URI 绕过（B-REVIEW-FILE-LOCK-BYPASS） | 🆕v4.3 高风险功能默认启用（应默认关闭+配置驱动）（B-REVIEW-CONFIG-DRIVEN-TOGGLE） | - |
| 🆕v4.3 后台任务复用主调度器（应独立 BackgroundScheduler）（B-REVIEW-SCHEDULER-ISOLATION） | 🆕v4.3 多方案失败无 backoff 策略（应配置驱动 max_failures/max_interval）（B-REVIEW-FALLBACK-CHAIN） | - |
| 🆕v4.3 Chrome 136+ 用 `--remote-debugging-port` 缺 `--user-data-dir` 非标准目录（B-REVIEW-CHROME-136-ADAPTATION） | 🆕v4.3 测试 Windows 环境变量未用 `tmp_path` mock（路径结构与实现不一致）（B-REVIEW-WINDOWS-TEST-MOCK） | - |
| 🆕v4.3 使用 pytest 插件未在 `pyproject.toml` 声明（运行时报 unrecognized arguments）（B-REVIEW-PLUGIN-DEPENDENCY-PRECHECK） | - | - |
| 🆕v4.4 错误码映射语义不匹配（如 RGV587=token 过期映射为 401 登录失效）（B-REVIEW-ERROR-SEMANTICS） | - | - |
| 🆕v4.4 配置项注入到中间层但消费层未读取（配置无效化）（B-REVIEW-CONFIG-LINKAGE） | - | - |
| - | 🆕v4.4 fast=True 失败后无降级重试（B-REVIEW-FAST-DEGRADATION） | - |
| - | 🆕v4.4 硬编码阈值替代已有配置项（B-REVIEW-NO-HARDCODED-THRESHOLD） | - |
| - | 🆕v4.4 方法签名新增参数后内部调用点遗漏传递（B-REVIEW-PARAM-PASS-THROUGH） | - |
| 🆕v4.9 状态机无白名单转换规则，散落式 `if status=='X': status='Y'`（B-REVIEW-STATE-MACHINE-WHITELIST） | 🆕v4.9 终态可复活 / 中间态无超时清理 / deadline 无限重置（B-REVIEW-STATE-MACHINE-WHITELIST） | - |
| 🆕v4.9 可注册组件无 cleanup 钩子 / asyncio.Task 未保留引用被 GC（B-REVIEW-RESOURCE-CLEANUP-HOOK） | 🆕v4.9 try/finally 资源未前置初始化为 None / gather 未用 return_exceptions（B-REVIEW-RESOURCE-CLEANUP-HOOK） | - |
| - | 🆕v4.9 双链路共用前置条件重复实现，未抽离为共享函数（B-REVIEW-DUAL-LINK-CONSISTENCY） | - |
| 🆕v4.9 共享状态检查+更新未在同一锁内（`if not active: start()` 错误模式）（B-REVIEW-CONCURRENT-STATE-LOCK） | 🆕v4.9 dataclass 字段用 `getattr` 兜底 / 锁内 `await` / 锁粒度过大（B-REVIEW-CONCURRENT-STATE-LOCK） | - |
| - | 🆕v4.9 用 `get_event_loop().create_task` 替代 `asyncio.create_task` / `except BaseException` 吞 CancelledError（B-REVIEW-PYTHON-MODERN-ASYNCIO） | - |
| 🆕v4.8 状态标志设置后无前置检查（B-REVIEW-STATE-FLAG-PRECHECK） | 🆕v4.8 日志降级判断用魔法字符串（B-REVIEW-LOG-DOWNGRADE-STABILITY） | - |
| 🆕v4.8 状态标志无重置机制（等于永久禁用） | 🆕v4.8 修改后未验证生效（B-REVIEW-EDIT-VERIFY） | - |

---

## 与现有工具的关系

- **xianyu-hunter-dev**：开发技能，本技能与之配合（开发完成后用本技能审查）
- **backend-code-review**（全局技能）：本技能参考其输出模板，但增加了闲鱼项目专属的硬约束和 24 维度检查清单
- **xianyu-frontend-code-review**：前后端协同评审时配合使用
- **xianyu-sonarqube-mcp**：SonarQube 修复后的二次人工评审使用本技能
- **xianyu-logs-review**：运行时日志分析使用该技能，不使用本技能
- **systematic-debugging**：纯调试场景使用该技能，不使用本技能
- **skill-creator**：本技能由 skill-creator 创建

---

## 安全注意事项

1. **凭据**：报告中不包含任何 token、密码等敏感信息
2. **硬编码检测**：硬约束规则 `no_hardcoded_credentials` 会扫描代码库
3. **凭据泄露建议**：若发现已泄露凭据（如 `config/config.yaml` 明文），建议立即吊销并提示操作步骤
4. **报告脱敏**：日志/报告中的 token、cookie 必须用 `***` 占位

---

## 示例用法

### 场景1：迭代发布前评审

用户："对这次迭代的后端修改进行代码评审"

技能执行：
1. 读取 `config.yaml`
2. `git diff HEAD --name-only` 提取改动的 `.py` 文件
3. 逐文件读取并按 29 大类检查
4. 硬约束合规性扫描
5. 生成评审报告

### 场景2：指定文件评审

用户："评审 src/xianyu_hunter/web/routes/api_tasks.py"

技能执行：
1. 读取 `config.yaml`
2. 读取指定文件
3. 按检查清单评审
4. 生成评审报告

### 场景3：仅评审安全问题

用户修改 `config.yaml`：
```yaml
checklist:
  security: true
  architecture: false
  type_annotation: false
  pydantic: false
  sqlalchemy: false
  sqlite_optimization: false
  performance: false
  async_scheduler: false
  event_bus: false
  error_handling: false
  logging: false
  code_quality: false
  config_management: false
  process_management: false
  composition_root: false
  chatbot: false
  web_layer: false
  api_design: false
  testing: false
  naming: false
  layering: false
  project_specific: false
  git_ops: false
```

技能执行：只检查安全类问题。

---

## 输出模板

当本技能被调用时，响应必须严格遵循以下模板之一：

### Template A（有问题）

```markdown
# Code Review Summary

Found <X> critical issues need to be fixed:

## 🔴 Critical (Must Fix)

### 1. <brief description of the issue>

FilePath: <path> line <line>
<relevant code snippet or pointer>

#### Explanation

<detailed explanation and references of the issue>

#### Suggested Fix

1. <brief description of suggested fix>
2. <code example> (optional, omit if not applicable)

---
... (repeat for each critical issue) ...

Found <Y> suggestions for improvement:

## 🟡 Suggestions (Should Consider)

### 1. <brief description of the suggestion>

FilePath: <path> line <line>
<relevant code snippet or pointer>

#### Explanation

<detailed explanation and references of the suggestion>

#### Suggested Fix

1. <brief description of suggested fix>
2. <code example> (optional, omit if not applicable)

---
... (repeat for each suggestion) ...

Found <Z> optional nits:

## 🟢 Nits (Optional)
### 1. <brief description of the nit>

FilePath: <path> line <line>
<relevant code snippet or pointer>

#### Explanation

<explanation and references of the optional nit>

#### Suggested Fix

- <minor suggestions>

---
... (repeat for each nits) ...

Found <W> config node missing issues (🆕v4.31):

## ⚙️ Config Node Missing (v4.31)

> 本分类专门记录 v4.31+ 配置驱动检查发现的配置节点缺失问题。当代码中引用了 v4.31+ 检查点但 `config.yaml` 中对应配置节点缺失或 `enabled: false` 时，记录在此分类。配置节点缺失会导致配置驱动检查无法生效，必须补充配置才能启用对应审查能力。

### 1. <brief description of the missing config node>

Config Node: `<node_path>` (expected in `config.yaml`)
Related B-REVIEW: <B-REVIEW-XXX-XXX>
Current State: <missing | enabled: false | incomplete>

#### Explanation

<detailed explanation of why this config node is required and what B-REVIEW checkpoint it enables>

#### Suggested Fix

1. 在 `config.yaml` 的 `<node_path>` 节点下补充以下配置：
```yaml
<node_path>:
  enabled: true
  <parameter1>: <value1>
  <parameter2>: <value2>
```
2. 参考 `config.example.yaml` 的 `<node_path>` 节点获取完整参数清单

---
... (repeat for each config node missing) ...

## ✅ What's Good

- <Positive feedback on good patterns>
```

- 若某分类无问题，省略该分类的整个 section
- 若问题数超过 10 个，概括为 "Found 10+ critical issues/suggestions/optional nits/config node missing" 并仅输出前 10 项
- 不要压缩 section 之间的空行，保持可读性
- 🆕v4.31 配置节点缺失分类为 CRITICAL 级别，必须修复才能启用对应审查能力
- 若有任何问题需要代码修改，在结构化输出后追加简短的后续问题，询问用户是否应用修复。例如："是否需要我使用 Suggested Fix 来修复这些问题？"

### Template B（无问题）

```markdown
## Code Review Summary
✅ No issues found.
```

### Template C（v4.28.0 结构化报告，推荐）

> v4.28.0 新增：结构化报告模板，含审查概览 + 问题详情，每个问题包含编号/维度/规范引用/代码位置/修复建议/配置节点/反模式示例/优先级。优先使用此模板。

```markdown
## 代码审查报告

### 审查概览
- 审查范围：[文件列表]
- 审查维度：[命中的维度列表，如 6 SQLite 优化 / 9 异步与调度器 / 11 错误处理]
- 问题统计：P0=[n] P1=[n] P2=[n] P3=[n]
- 规范版本：xianyu-backend-code-review v4.28.0
- 配置版本：config.yaml coding_standards 节点 v4.28.0

### 问题详情

#### [P0] B-REVIEW-121 时区一致性
- **规范引用**: DATETIME-TZ-01 时区一致性三步检查法
- **维度**: 6 SQLite 优化
- **代码位置**: repo_chatbot.py:478
- **问题描述**: `_utcnow()` 返回 aware，`row.created_at` 为 naive，减法报错 `TypeError: can't subtract offset-naive and offset-aware datetimes`
- **修复建议**: 使用 `_utcnow().replace(tzinfo=None) - row.created_at` 统一为 naive（项目默认策略）
- **配置节点**: `coding_standards.datetime.default_timezone`（默认 `naive`）
- **反模式示例**:
  ```python
  # ❌ 错误：aware 与 naive 混用
  diff = _utcnow() - row.created_at  # TypeError
  ```
- **正确模式**:
  ```python
  # ✅ 正确：统一为 naive
  diff = _utcnow().replace(tzinfo=None) - row.created_at
  ```

---

#### [P1] B-REVIEW-127 错误归因精细化
- **规范引用**: ATTRIB-01 错误归因精细化
- **维度**: 11 错误处理
- **代码位置**: api_collection.py:234
- **问题描述**: 所有外部调用失败统一返回 502，前端无法区分 token 过期（需重新登录）与反爬（需等待重试）
- **修复建议**: 根据 `failure_reason` 映射具体状态码（401/429/503/502）
- **配置节点**: `coding_standards.error_attribution.status_mapping`
- **反模式示例**:
  ```python
  # ❌ 错误：无具体原因
  raise HTTPException(502)
  ```
- **正确模式**:
  ```python
  # ✅ 正确：精细化映射
  status_map = {'token_expired': 401, 'anti_crawler': 429, 'page_unavailable': 503, 'other': 502}
  raise HTTPException(status_map.get(reason, 502))
  ```

---

... (repeat for each issue,按 P0 → P1 → P2 → P3 顺序排列) ...

### 与上次审查对比
- 🆕 新增：[新增问题列表]
- ✅ 已修复：[已修复问题列表]
- ⚠️ 仍存在：[未修复问题列表]

### 好的实践
- <Positive feedback on good patterns>

### 审查结论
- 阻塞合并：[是/否]（P0 问题数 > 0 时阻塞）
- 修复优先级：先修复 P0，再 P1，P2/P3 可后续迭代
- 修复验证：修复后重新执行本技能审查，确认 P0/P1 问题已解决
```

**Template C 使用规则**：
- v4.28.0 起优先使用 Template C（结构化报告）
- 每个问题必须包含 8 个字段：编号/维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示例
- 问题按 P0 → P1 → P2 → P3 顺序排列
- 若某优先级无问题，省略该优先级的所有问题
- 若问题数超过 10 个，在审查概览中标注 "10+ issues" 并仅输出前 10 项
- 若有任何问题需要代码修改，在报告末尾询问用户是否应用修复

---

## 重要提醒

1. 【强制】所有时间字段用 `_utcnow = lambda: datetime.now(timezone.utc)`，禁止 `datetime.utcnow()`
2. 【强制】SQLite 引擎用 `NullPool`，禁止 `StaticPool`
3. 【强制】Token 比较用 `hmac.compare_digest()`，禁止 `==`
4. 【强制】敏感字段写入 keyring，禁止 `config/config.yaml` 明文
5. 【强制】`local_embedding.py` 模块顶层设 `HF_ENDPOINT` 镜像
6. 【强制】提交前执行 `auto-scan.ps1`；完成后调用本技能走查

---

## 快速问题定位

| 现象 | 原因 | 方案 |
|------|------|------|
| `NameError: name 're' is not defined` | 模块级导入缺失 | 在文件顶部 `import re` |
| `NameError: name 'threading' is not defined` | 同上 | `import threading` |
| WebView2 GUI 窗口闪退 | 使用 `CREATE_NO_WINDOW` | 改为 `CREATE_NEW_CONSOLE` |
| HuggingFace.co 连接超时 | 未设 `HF_ENDPOINT` 镜像 | 模块顶层 `os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")` |
| 向量化时间 30+ 分钟 | `_scan_and_chunk` 未排除前端构建产物 | 加入 `web/static/`、`web/templates/` 等到排除列表 |
| SQLite "database is locked" | `poolclass` 用 `StaticPool` | 改为 `NullPool` + `check_same_thread=False` |
| Token 比较被时序攻击 | 用 `==` 比较 | 改用 `hmac.compare_digest()` |
| 401 响应解析失败（前端） | 返回纯文本非 JSON | 返回 `JSONResponse({"detail": "Unauthorized"}, status_code=401)` |
| Chatbot 并发会话状态污染 | Orchestrator 持有请求级状态 | 改为 per-session Lock + 无状态设计 |
| `CancelledError` 被吞，资源泄漏 | `except: pass` | 用 `suppress(asyncio.CancelledError)` 包裹并向上传播 |
| SQLite `utcnow` 弃用警告 | `datetime.utcnow()` | `datetime.now(timezone.utc)` |
| Pydantic `model_dump` 不存在 | 用了 1.x 的 `.dict()` | 升级到 2.x，用 `model_dump()` |
| `git` 操作报 `index.lock exists` | 失败 stash/merge 留下 `.git/index.lock` | 用 `python -c "import os; os.remove('.git/index.lock')"` 删除（PowerShell/cmd 被安全策略阻止时） |
| `git status` 卡死或极慢 | 产物文件（`.scannerwork/`、`__pycache__/`）被 git track（数千文件） | `git rm -r --cached <dir>` 清理并加入 `.gitignore` |
| 🆕 SonarQube S7503 报错 | `async` 函数无 `await` | 改同步函数，或确认需要异步上下文 |
| 🆕 SonarQube S3776 报错 | 认知复杂度 > 15 | 拆分为多个小函数（参考 `login_orchestrator.start_session` 7 步拆分模式） |
| 🆕 SonarQube S6767 报错 | 未使用的参数/属性/局部变量 | 删除未使用项，或用 `_` 前缀 |
| 🆕 SonarQube S1192 报错 | 重复字符串字面量 ≥ 2 处 | 提取为模块级常量（如 `_TASK_NOT_FOUND`） |
| 🆕 SonarQube S5843 报错 | 复杂正则表达式 | 拆分为多个简单正则或改用字符串方法 |
| 🆕 纯编排函数被误报 async | 函数无 await 但标注 async | 改同步 `def`（如 `scheduler.start_all`） |
| 🆕 用户配置修改不生效 | Evaluator 接受 `thresholds/weights/keywords` 覆盖参数 | 移除覆盖参数，每次 `evaluate()` 从 `get_config()` 实时读取 |
| 🆕 知识库构建回滚失败 | 失败率阈值未触发回滚 | 确认 `_PARTIAL_FAIL_RATE=0.10` + `_FAILED_FAIL_RATE=0.50` 触发条件 |
| 查询慢但数据量小 | ORM 索引定义与 init_db 迁移不一致 | 比对 `__table_args__` 与 `_migrate_create_index`，补建缺失索引 |
| 日志参数未替换显示 %s | loguru 使用了 printf 风格占位符 | 改用 `{}` 占位符：`logger.info("task={}", id)` |
| 商品列表刷新卡顿 | 全量加载到 Python 层过滤后切片 | 将过滤条件下推到 SQL WHERE + json_extract |
| 🆕v4.0 钉钉通知在状态未变前触发 | "已完成"事件在业务逻辑前置触发（EVAL_PASSED 前置） | 事件触发时机应在业务逻辑完成之后（如 `update_eval_result()` 后再触发 EVAL_PASSED） |
| 🆕v4.0 评估详情字段被空值覆盖 | 字段覆盖策略一刀切"只填缺失" | 按语义分类：基本信息仅填缺失、数值取较大值、状态按优先级、标识符仅在原值为空且新值非空时覆盖 |
| 🆕v4.0 重复登录创建多个会话 | 资源创建接口非幂等 | 引入 `already_active` 标志，检测到已激活资源时直接返回，避免重复创建 |
| 🆕v4.0 搜索接口参数混乱 | 多个搜索接口参数命名/响应结构不统一 | 统一参数命名（`keyword/page/page_size`）与响应结构（`items/total/page/page_size`），引入 400ms 防抖 + requestId 竞态保护 |
| 🆕v4.0 注释误导维护者 | 注释描述的约束与代码逻辑不一致 | 修改代码时同步更新注释；评审时校验注释中"必须 X 否则 Y"的真实性 |
| 🆕v4.0 动态资源映射难扩展 | 映射表与推断逻辑混合在 IIFE 中 | 抽离为模块级映射表（如 `API_KEY_URLS`）+ 推断函数（如 `getApiKeyUrlByBaseUrl`），便于单测与扩展 |
| 🆕v4.1 实时搜索返回 0 商品但实际是登录失效 | 重试失败后未检查 `last_session_invalid` 状态，仍走成功流程 | 重试代码块结束后检查状态标志，若仍为 True 则推送 SSE error 事件并 `return`（参考 `api_task_links.py` 修复） |
| 🆕v4.1 健康检查显示 Cookie 有效但业务调用失败 | Cookie 检查只覆盖身份 Cookie（`cookie2/sgcookie/unb`），忽略会话 token（`_m_h5_tk`） | Cookie 检查清单必须覆盖**所有**关键 token（身份 + 会话），清单在 `config.yaml` 的 `cookie_check_lists` 节点管理 |
| 🆕v4.1 前端用户无法区分"稍后重试"还是"前往登录" | 错误响应粒度未区分（401/403/502/503/504 混用） | 按错误粒度三类区分：`503/504` 稍后重试、`401/403` 需用户介入+指引、`502` 需重启服务 |
| 🆕v4.2 指纹被 AWSC fireyejs 识破 | GPU vendor 与 renderer 矛盾（如 Intel Inc. 配 AMD 渲染器） | 校验字段一致性：`Google Inc. (AMD)` 配 AMD 渲染器 |
| 🆕v4.2 页面 JS 读取 Cookie 失败 | Cookie 批量硬编码 `httpOnly:True`，JS 可读 Cookie 被禁 | 根据 Cookie 名称动态设置 `httpOnly`（identity 层设 False） |
| 🆕v4.2 验证码事件永远不触发 | `new Proxy()` 赋值给局部变量后丢弃 | 赋值给实例属性或用 `Object.defineProperty` 重写 setter |
| 🆕v4.2 API 请求死锁 | 同步函数中 `run_coroutine_threadsafe` + `future.result()` 等待异步结果 | 改纯异步路径或 fire-and-forget + 同步兜底（JSON 持久化） |
| 🆕v4.2 finally 块报 UnboundLocalError | try 内赋值的变量在 finally 中引用，但 try 抛异常 | 前置初始化 `page = None`，finally 中 `if page: await page.close()` |
| 🆕v4.2 健康检查显示有效但任务自动暂停 | 健康检查器与 worker 对"会话有效性"判断维度不同 | 状态变更双向同步：worker 检测到失效时 `invalidate_layer(IDENTITY)`，health_checker 查询时检查 `collector.last_session_invalid` |
| 🆕v4.2 用户按错误提示操作但端点不存在 | 错误提示引用了未实现的 API 端点 | 提示中只引用已实现的端点（如改为"请调用 POST /api/anticrawl/initialize"） |
| 🆕v4.3 Chrome v20 Cookie 解密失败 | v20 App-Bound Encryption 无法离线解密 | 改用 CDP 接管运行中浏览器：`Playwright.connect_over_cdp()` + `Network.getAllCookies` |
| 🆕v4.3 SQLite "database is locked" | 浏览器运行时持有 Cookies 数据库写锁 | 用 SQLite URI `file:./Cookies?immutable=1` + `connect(uri=True)` 只读打开 |
| 🆕v4.3 Cookie 同步任务与采集任务冲突 | 复用项目主调度器导致优先级与生命周期冲突 | 创建独立 `BackgroundScheduler()` + 独立 `start()`/`shutdown()` 钩子 |
| 🆕v4.3 用户不知情下浏览器资源被占用 | `auto_sync` 默认启用 | `auto_sync: bool = False` 默认关闭，需用户在 `config.yaml` 显式启用 |
| 🆕v4.3 Cookie 同步无意义重试 | 多方案失败无 backoff 策略 | 3 次失败后 `interval *= 2`，上限 2 小时（参数在 `config.yaml` 的 `fallback_chain` 管理） |
| 🆕v4.3 Chrome 136+ CDP 端口不生效 | `--remote-debugging-port` 缺 `--user-data-dir` 非标准目录 | 启动命令同时包含两参数，`user_data_dir` 指向 `browser_data/debug_{timestamp}` |
| 🆕v4.3 用户 Profile 1 的 Cookie 导入失败 | 实现只读 Default profile | 读 `Local State` 的 `profile.info_cache` + fallback 目录扫描 `Profile *` |
| 🆕v4.3 测试报路径不存在 | 测试 fixture 路径结构与实现不一致 | `monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))` + 创建 `tmp_path / "Microsoft" / "Edge" / "User Data"` 完整路径 |
| 🆕v4.3 `pytest --timeout=60` 报 unrecognized arguments | 项目未安装 `pytest-timeout` 插件 | 移除 `--timeout` 标志，或在 `pyproject.toml` 声明插件依赖 + `requirements-dev.txt` 列出 |
| 🆕v4.4 用户设置了排序方式但搜索结果无变化 | sort_type 配置注入到 TaskConfig 但 Worker 未读取 self.config.search_sort_type | 从 config.yaml→Config→TaskConfig→Worker→search()→build_search_url() 全链路追踪，确认每层都读取并传递参数 |
| 🆕v4.4 刚登录后搜索偶尔成功偶尔失败 | fast=True 模式跳过 token 刷新，token 过期时搜索失败 | fast 失败后自动以 fast=False 重试一次（含 token 刷新） |
| 🆕v4.4 连续失败 10 次才暂停但配置设为 3 次 | Scheduler 用硬编码 MAX_CONSECUTIVE_ERRORS=10 替代 fail_pause_threshold 配置 | 改为 `get_config().antidetect.fail_pause_threshold` |
| 🆕v4.4 RGV587 重试时 URL 丢失排序参数 | search() 新增 sort_type 参数后 _call_search_api 内部 build_search_url 未传递 | grep 方法名检查所有调用点，同步更新内部调用传递新参数 |
| 🆕v4.9 任务状态出现非法转换（如 failed → running） | 状态机无白名单转换规则，散落式 `if status=='X': status='Y'` | 集中定义 `TRANSITIONS: dict[str, set[str]]` 显式列出允许的转换；终态不可复活；中间态有超时清理；deadline 不可无限重置；前后端枚举值统一（参数在 `config.yaml` 的 `state_machine` 节点管理） |
| 🆕v4.9 服务关闭后 asyncio.Task 资源泄漏 / 警告 "Task was destroyed but it is pending" | `asyncio.create_task(...)` 未保留引用被 GC，组件无 cleanup 钩子 | 可注册组件实现 `cleanup()` 钩子并在 shutdown 事件调用；Task 保留到实例属性 `self._task = asyncio.create_task(...)`；取消用 `await asyncio.gather(*tasks, return_exceptions=True)`；try/finally 资源前置 `= None` |
| 🆕v4.9 同一业务目标两条链路行为不一致（API 路由能正确校验，定时任务跳过校验） | 双链路共用前置条件重复实现，未抽离为共享函数 | 抽离共用前置条件为 `def _validate_xxx(...): ...`，两链路调用同一函数；grep 验证两链路都调用；新增测试覆盖两链路 |
| 🆕v4.9 并发场景下"检查通过但更新前状态已变"导致重复启动 | 共享状态检查+更新未在同一锁内（`if not self._active: self._start()` 错误模式） | 改为 `async with self._lock: if not self._active: await self._start()` 同一锁内完成检查+更新；dataclass 字段显式声明默认值禁 `getattr` 兜底；锁粒度最小化；锁内禁止 `await`（除非 asyncio.Lock） |
| 🆕v4.9 Python 3.12+ 报 DeprecationWarning: There is no current event loop | 用 `asyncio.get_event_loop().create_task(coro)` 替代 `asyncio.create_task(coro)` | 改为 `asyncio.create_task(coro)`（3.10+ 推荐）；避免 `getattr` 兜底；模块级 import；`except BaseException` 改为 `except Exception` 或显式 `except asyncio.CancelledError: raise`；类型注解用现代语法 `dict[str, str]` / `int \| None` |
| 🆕v4.8 WARNING 日志刷屏（300+条/小时） | 检测到异常状态后后续操作仍重复尝试 | 设置状态标志 + 操作入口增加 `getattr(self, "flag", False)` 前置检查 + 重置机制（`flag = False`）（B-REVIEW-STATE-FLAG-PRECHECK） |
| 🆕v4.8 日志降级文案变更后失效 | 判断字符串硬编码未提取为常量 | 提取为模块级常量（如 `_COOKIE_EXPIRED_DETAIL_MARKER`）并注释文案来源（B-REVIEW-LOG-DOWNGRADE-STABILITY） |
| 🆕v4.8 代码评审发现修改未生效 | Edit 工具返回成功但修改未保存 | Edit 后立即 Grep 验证标志性标识符（变量名/函数名/常量名），无匹配则重新执行 Edit（B-REVIEW-EDIT-VERIFY） |

---

## 附录A：硬约束来源

本技能的硬约束规则来源于：
- `c:\Users\hspcadmin\.trae-cn\memory\projects\-d-code-otherProjects-17-xianyu\project_memory.md`
- `.trae/skills/xianyu-hunter-dev/references/project-rules.md`
- `.trae/skills/xianyu-backend-code-review/references/encoding-and-io.md` —— 字符编码与 I/O 边界审查要点（FAQ 乱码复盘提炼，ENC-01 ~ ENC-08）
- `.trae/skills/xianyu-backend-code-review/references/consistency-and-state-checks.md` —— 多入口参数一致性、价格采集字段优先级、DOM 选择器排除、N+1 查询、json_extract vs LIKE、异常消息脱敏、计数器语义、状态检测关键词覆盖（实时搜索/价格不一致/商品删除复盘提炼，13 项 B-REVIEW 检查点）
- 历史代码评审记录（如 `config/config.yaml` 明文暴露钉钉凭据 Critical 安全事件）

## 附录B：项目专属规范

以下规范在 `config.yaml` 的 `project_conventions` 节点维护：

| 规范 | 说明 |
|------|------|
| `auth_whitelist` | 认证白名单端点（必须放行，不要求 token） |
| `required_indexes` | 必须有索引的数据库字段 |
| `count_query_optimization` | COUNT 查询合并要求 |
| `webview2_config` | WebView2 配置要求 |
| `kb_index_whitelist` | 知识库索引白名单 |
| `kb_index_excludes` | 知识库索引排除路径 |
| `hf_endpoint` | HuggingFace 镜像 |
| `layering` | 分层依赖方向 |
| `immutable_dirs` | 不可移动目录 |
| `docker_stages` | Docker 三阶段构建 |
| `git_artifact_dirs` | 不应被 git track 的产物目录（如 `.scannerwork/`、`__pycache__/`） |
| `git_conflict_strategy` | 合并冲突保留策略（如 `await` 异步版本优先） |

## 附录C：35 维度对照表

| # | 维度 | 核心规则 |
|:--|:---|:---|
| 1 | 分层架构 | `web → modules → infra → domain` 单向依赖 |
| 2 | 命名规范 | snake_case/PascalCase/*Row/*Config/_前缀 |
| 3 | 类型注解 | Python 3.10+ `X \| None`，全面注解 |
| 4 | Pydantic 2.x | `model_dump`、`Field` 约束、领域用 dataclass |
| 5 | SQLAlchemy 2.0 | `Mapped`、`_utcnow`、幂等迁移、`_escape_like` |
| 6 | SQLite 优化 | `NullPool`、WAL、busy_timeout、索引规约、🆕v4.3 文件锁绕过（SQLite immutable=1）、🆕v4.25 NOT NULL 字段 None 防御（B-REVIEW-111，区分 NOT NULL 字段防御性 pop 与覆盖字段写 None） |
| 7 | 安全性 | `hmac.compare_digest`、keyring、SQL 注入防护、🆕v4.1 Cookie 检查全面性（身份 Cookie + 会话 token）、🆕v4.3 加密升级退化策略（v20 用 CDP 接管） |
| 8 | 性能 | N+1 检测、`asyncio.to_thread`、缓存 |
| 9 | 异步与调度器 | `async def` 路由、5 类调度器、CancelledError、🆕v4.0 事件触发时机（"已完成"事件在业务逻辑完成后触发）、🆕v4.3 独立调度器隔离模式、🆕v4.25 共享单例污染防护（B-REVIEW-112，循环中任务级覆盖用 worker_xxx 局部变量） |
| 10 | 事件总线 | `asyncio.Queue`、35 种 EventType、SSE lastEventId |
| 11 | 错误处理 | 三层兜底、保留堆栈、tenacity 重试、🆕v4.1 重试失败后状态信号传递 + 错误粒度三类区分（503/504/401/403/502）、🆕v4.3 降级链模式（多方案+backoff） |
| 12 | 日志规约 | loguru 三 sink、request_id 追踪、脱敏 |
| 13 | 代码质量 | 模块级导入、SRP、嵌套 ≤ 4、async/await 一致性、🆕v4.0 注释与代码一致性 |
| 14 | 配置管理 | pydantic-settings + keyring + .env 三层、🆕v4.3 配置驱动功能开关模式（高风险默认关闭） |
| 15 | 进程管理 | `CREATE_NEW_CONSOLE`、`private_mode=False`、🆕v4.3 Chrome 136+ 限制适配（remote-debugging-port + 非标准 user-data-dir） |
| 16 | Composition Root | `Container` 单例、深拷贝 chatbot 配置、🆕v4.3 多配置文件发现模式（结构化元数据+fallback 扫描） |
| 17 | 智能客服专项 | Orchestrator 无状态、KB 白名单、🆕v4.0 字段覆盖策略（按语义分类） |
| 18 | Web 层规范 | `create_app` 工厂、LIFO 中间件 |
| 19 | API 设计 | HTTP 语义、分页、DTO 响应、🆕v4.0 幂等性设计 + 搜索接口标准化、🆕v4.25 API 三态语义（B-REVIEW-110，PATCH/PUT 用 model_dump(exclude_unset=True) 区分未传/传null/传值） |
| 20 | 测试建议 | null/空集合/边界值/并发/事务、🆕v4.3 Windows 测试环境 Mock + 第三方插件依赖预检 |
| 21 | 架构与分层 | 无循环依赖、领域纯净性 |
| 22 | 闲鱼项目规范 | Mixin 仓储、Typer CLI、Docker 三阶段 |
| 23 | Git 操作规范 | `index.lock` 检测、产物 untrack、cherry-pick 保留策略 |
| 24 | 跨字段一致性与硬编码属性禁用 | 字段一致性校验、Cookie/HTTP属性动态设置、跨线程异步禁用、try/finally初始化、跨组件状态同步、错误提示端点可操作性 |
| 25 | 错误提示语义 + 配置链路 + 快速模式降级 + 硬编码阈值禁用 + 参数透传完整性 | 🆕v4.4 错误码映射语义匹配、配置全链路追踪、fast 降级重试、阈值配置化、参数传递无遗漏 |
| 26 | 异步超时 + 数据流转 + 过滤场景 + 复用模式 | 🆕v4.6 异步操作整体超时保护（asyncio.wait_for）、字段为空 5 点追踪、过滤逻辑场景区分（include_failed 参数化）、复用既有模式原则 |
| 27 | 状态管理与日志治理 | 🆕v4.8 状态标志前置检查（B-REVIEW-STATE-FLAG-PRECHECK，检测异常状态后操作入口必须有 `getattr(self, "flag", False)` 前置检查 + 重置机制）；日志级别动态降级（B-REVIEW-LOG-DOWNGRADE-STABILITY，判断字符串提取为模块级常量并注释文案来源）；修改后验证流程（B-REVIEW-EDIT-VERIFY，Edit 后用 Grep 验证标志性标识符）；参数分别在 `state_flag_precheck`/`log_downgrade` 节点管理 |
| 28 | LLM 端点能力派发与共享工具函数 | 🆕v4.23 能力驱动派发（B-REVIEW-LLM-CAPABILITY-DISPATCH，LLM/多模态/function_call 调用必须在构造 payload 前预检目标模型能力，失败时降级为等价文本表达）；共享工具函数（B-REVIEW-SHARED-UTIL-CENTRALIZATION，跨 ≥2 模块复用的判断逻辑/关键字白名单/常量必须抽取为"被依赖方"模块顶层的纯函数或模块级常量，禁止散落）；静默降级预检（B-REVIEW-SILENT-DOWNGRADE-PRECHECK，"可选增强"能力调用前必须预检，失败时降级为等价文本表达而非抛错，降级 prompt 模板集中管理）；参数分别在 `llm_capability_keywords`/`shared_util_rules`/`llm_downgrade` 节点管理 |
| 29 | 端到端失败原因链与数据完整性闭环 | 🆕v4.27 失败原因传递链（B-REVIEW-FAILURE-REASON-PROPAGATION，底层 `last_*_failure_reason` → 中层 status_code 映射 → 高层日志降级，禁止字符串子串判断，错误响应必须含 `error_code` 字段）；数据完整性预检（B-REVIEW-DATA-COMPLETENESS-PRECHECK，调用外部依赖前预检 + 调用后二次检查，双阈值 AND 判断，错误信息含具体缺失清单）；合并写入 vs 覆盖写入决策（B-REVIEW-MERGE-VS-OVERWRITE-WRITE，部分集→合并写 `merge_*`，完整集→覆盖写 `save_*`/`export_*`，覆盖写前必须预检新集完整）；文案常量集中管理（B-REVIEW-ERROR-MESSAGE-CONSTANT，错误文案/日志降级 marker 提取为模块级常量，跨模块引用必须 import，禁止字符串子串做 marker）；修改-验证-部署闭环（B-REVIEW-EDIT-VERIFY-DEPLOY-LOOP，Edit 后 Grep 验证、Python 修改后重启服务、重启后验证端口+数据状态、git stash 前先 commit 保底）；测试 mock 同步（B-REVIEW-TEST-MOCK-SYNC，修改前置条件时同步更新 mock 数据，mock 数据覆盖完整字段集，集中管理在 conftest.py）；参数分别在 `failure_reason_propagation`/`data_completeness_precheck`/`write_strategy_decision`/`error_message_centralization`/`edit_verify_deploy_loop`/`test_mock_synchronization` 节点管理 |
| 30 | 业务关键字常量集中管理与跨端契约对齐 | 🆕v4.31 业务关键字常量集中管理（B-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION，外部平台文本特征集中到单一模块的 `*_TEXT_KEYWORDS` 常量，统一访问函数 `check_text_sold` 调用，禁止散落字面量）；事件类型过滤精确匹配（B-REVIEW-EVENT-TYPE-EXACT-MATCH，业务查询事件类型必须用 `==` 精确匹配，禁止 `startswith`/`endswith` 前缀过滤，通知事件与业务事件必须使用不同命名空间）；前后端字段名大小写敏感检查（B-REVIEW-FIELD-NAME-CASE-SENSITIVE，Python 类私有属性 `_session` vs `_Session` 严格大小写一致，API 响应字段名前后端严格一致含大小写下划线前后缀）；服务重启验证清单（B-REVIEW-SERVICE-RESTART-VERIFICATION，Python 后端代码修改后必须重启服务，重启后按清单验证端口监听/健康检查/数据状态/启动日志）；Windows 终端编码与 Shell 语法兼容（B-REVIEW-WINDOWS-TERMINAL-ENCODING，PowerShell 脚本显式设置 UTF-8 编码，命令拼接用 `;` 而非 `&&`，`stash@{0}` 加引号，Python 脚本设置 stdout 编码）；参数分别在 `business_keyword_centralization`/`event_type_exact_match`/`field_name_case_sensitive`/`post_restart`/`cross_platform` 节点管理 |
| 31 | 状态恢复与日志规范 | 🆕v4.30 状态恢复前置校验（B-REVIEW-157 RESUME-PRECHECK，具有 pause/resume 语义的组件 resume 前必须 precheck 校验 root_cause 消除，校验失败返回结构化拒绝 `{resume_blocked, reason_code, user_hint, retry_after}`，异常 pause 后设冷却期）；多阶段降级链日志合并（B-REVIEW-158 LOG-MERGE，同一逻辑链多阶段日志合并为 1 条结构化 WARNING，中间步骤 DEBUG 化，结果含 `extra={stages, final_reason, keyword, attempts}`，禁止降级链每步独立 WARNING 淹没真实告警）；参数分别在 `resume_policy` / `log_merge` 节点管理 |
| 32 | 注册式资源 endpoint 契约 | 🆕v4.31 注册式资源 endpoint 契约（B-REVIEW-159 REGISTRATION-ENDPOINT-CHECK，meta-rule #33 后端落地——前端已在 `menu_registry`/`router`/`page`/`api_wrapper` 注册的资源，后端必须在 `src/xianyu_hunter/web/routes/api_<domain>.py` 提供对应 `@router.<method>` endpoint；缺一即视为 CRITICAL；5 层契约：L1 menu_registry / L2 router / L3 page / L4 api_wrapper / L5 backend_endpoint；自动化校验 `python scripts/check_registration.py` 退出码 0 才算通过）；参数在 `backend_registration_endpoint` 节点管理（含 precheck_layers 五层、required_field_mapping 跨层字段映射、fail_on_missing_layer CRITICAL、known_complete_resources 参考基线） |
| 33 | 修复前全链路根因扫描协议 | 🆕v4.31 修复前根因扫描协议（B-REVIEW-160 ROOT-CAUSE-CHAIN-CHECK，meta-rule #34 后端落地——修复非平凡 bug 前必须先列 ≥3 个根因覆盖用户层/接口层/数据层/配置层/历史层；PR 描述必含"≥3 根因列表"段 + 验证工具 + 最小修改清单 + 全链路反查 + 防回归测试；git diff 涉及 ≥3 个无关文件视为违反最小修改原则；新增逻辑无 unit test 视为 WARNING；链式检查 5 维度 menu_registry/router/page/api_wrapper/backend_endpoint 与 B-REVIEW-159 5 层契约呼应）；参数在 `root_cause_chain_check` 节点管理 |
| 34 | 前后端字段契约单一可信源 | 🆕v4.31 前后端字段契约单一可信源（B-REVIEW-161 CONTRACT-OWNER-MARKER，meta-rule #35 后端落地——后端 Pydantic/DB Row 字段 = 权威源；后端 `BaseModel` 字段必须显式标注 `@field_validator` / `Field(..., description=...)` 标明"权威源"角色；后端字段变更必须同步通知前端 + 在 `contract_owner_marker` 节点更新 `affected_frontend_types_files` 列表；snake_case 严格透传禁止转 camelCase；命名漂移检测：后端 `xxx_yyy` + 前端 `xxxYyy` = CRITICAL）；参数在 `contract_owner_marker` 节点管理（含 authority_source 唯一可信源、required_marker_fields 必填标注、affected_frontend_types_files 受影响前端 types、naming_drift_patterns 命名漂移模式库） |
| 35 | 编码规范防御性复盘 | 🆕v4.33 规范沉淀门槛（B-REVIEW-162 SEDIMENTATION-THRESHOLD，meta-rule #36 落地——新立 meta-rule/step/B-REVIEW 必须满足 ≥3 个相似 bug 门槛，单一 bug 立规范需标 experimental 标签 + 1 季度观察期，安全/数据丢失/付费受损豁免）；规范退化机制（B-REVIEW-163 DEGRADATION-CLEANUP，meta-rule #37 落地——利用率 < 3 次/季度则标记待合并/待废弃，1 季度观察期后废弃并移入 version-history.md Deprecated 章节，安全类规范永不退化）；参数在 `meta_rules_governance` 节点管理（含 sedimentation_threshold 沉淀门槛、degradation_threshold 退化阈值、observation_period_quarters 观察期、sedimentation_exemption_categories 豁免类别、degradation_exemption_categories 安全类豁免）；🆕v4.34 全局聚合任务级过滤（B-REVIEW-164 GLOBAL-AGGREGATE-TASK-FILTER，meta-rule #38 落地——全局视图（无 task_id）列表查询必须按各任务个体配置范围过滤，禁止只用全局默认范围）；列表交叉数据批量注入（B-REVIEW-165 LIST-CROSS-DOMAIN-INJECT，meta-rule #39 落地——列表交叉其他数据源必须批量查询 + TTL 缓存，禁止 N+1 单条查询）；多字段联动开关范式（B-REVIEW-166 MULTI-FIELD-LINKED-SWITCH，meta-rule #40 落地——联动字段必须声明「主开关→过滤器」优先级矩阵，主开关失效时子过滤器自动禁用）；状态恢复前置校验结构化响应（B-REVIEW-167 RESUME-PRECHECK-STRUCTURED，meta-rule #41 落地——precheck 必须返回 5 字段结构化 dict 不抛异常，API 层直接透传）；配置化阈值兜底范式（B-REVIEW-168 CONFIG-DRIVEN-THRESHOLD-FALLBACK，meta-rule #42 落地——从 config 读取的阈值必须有 try/except 兜底默认值，禁止配置缺失即崩溃）；参数在 `meta_rules_38_42` 节点管理（含 global_aggregate_filter/cross_domain_inject/linked_switch_priority/precheck_structured_fields/config_fallback_defaults 5 个子节点） |

### 36. 工程闭环元规范（meta-rules #52-#55 落地）🆕v4.34

> 基于 2026-07-07 修复的「价格过滤失效 / SEMI_AUTO 模式退化 / 外部 DOM 解析失败 / 测试 mock 错配」4 类问题复盘，使用 Sequential Thinking 4 维度复盘法，新增 4 项 B-REVIEW 检查点（B-REVIEW-177~180），自动化扫描从 168 → 172 项。所有新检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明。详细编码规范整合到 `xianyu-hunter-dev` v4.37.0 的 meta-rules #52-#55 与 step 189-192。前端对应规范为 `xianyu-frontend-code-review` v4.40.0 的 F-REVIEW-131~133（#56 过滤透明化 UI 仅前端适用）。

- 🆕v4.34【强制】**B-REVIEW-177：PARAM-CHAIN-EXEC 参数链闭环验证**
  - 维度：19 API 设计与契约
  - 严重等级：critical（P0，过滤参数失效导致数据泄露）
  - 规范引用：meta-rule #52 参数链闭环验证
  - **检查点**：过滤类参数（filter / constraint 语义）从 API 接收后必须存在对应的消费点（函数调用 / SQL WHERE / 条件分支），禁止"参数已接收但未被消费"
  - **检查项**：
    1. API endpoint 函数签名声明参数后，函数体内必须存在该参数的消费逻辑
    2. 参数必须实际参与过滤条件构建（WHERE 子句 / 条件分支 / 函数调用参数）
    3. 必须存在单元测试验证"传参 vs 不传参"结果集差异
    4. 元数据参数白名单（page / page_size / limit / offset / sort / order / fields / select）在 config 管理
  - **判断信号**：
    - `grep "<param_name>" <file>` 仅命中函数签名和 return 语句但未命中函数调用 → 视为可疑
    - API 接收 `market_ratio` 参数但未调用 `PriceStrategy.check(market_ratio=...)` → 违规
    - 单元测试无 `with_param` / `without_param` 对比用例 → 视为闭环验证缺失
  - **配置参数**：`param_chain_exec.enabled`（默认 true）、`param_chain_exec.metadata_whitelist`（默认 `["page", "page_size", "limit", "offset", "sort", "order", "order_by", "fields", "select"]`）、`param_chain_exec.filter_param_prefixes`（默认 `["filter_", "range_", "min_", "max_", "ratio_"]`）在 `config.yaml` 的 `param_chain_exec` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.37.0 meta-rules #52 / step 189
  - **适用**：所有有过滤参数的列表查询 API（list_evaluations / list_items / search_* / list_orders）、PATCH/PUT 接口的可空字段
  - **不适用**：GET 单个资源详情（无过滤）、DELETE 接口（参数仅定位资源）、仅作元数据返回的字段（total_count）、创建类 POST 接口
  - **历史教训**：`evaluations_list.py` 接收 `market_ratio=0.85` 参数但未调用 `PriceStrategy.check`，导致调整到 0.85 后仍能查出价格上限 800 的商品。修复：新增 `_resolve_market_ratio` / `_compute_eval_market_median` / `_filter_market_ratio` 三个辅助函数形成闭环。

- 🆕v4.34【强制】**B-REVIEW-178：MODE-VERTICAL-CHAIN 业务模式纵向链路一致性**
  - 维度：27 状态管理与日志治理
  - 严重等级：critical（P0，模式退化导致功能失效）
  - 规范引用：meta-rule #53 业务模式纵向链路一致性
  - **检查点**：业务模式枚举（如 AUTO / SEMI_AUTO / MANUAL）必须在 6 个层纵向一致传递：决策层 → 事件层 → 通知层 → 路由层 → 接口层 → 状态机层，任一层缺失即模式退化
  - **检查项**：
    1. 决策层：`_should_buy()` 等决策函数必须根据 mode 返回不同决策
    2. 事件层：业务事件 payload 必含 mode 字段（如 `EVAL_PASSED` 事件含 `task_mode`）
    3. 通知层：不同 mode 渲染不同模板（SEMI_AUTO 必含确认链接）
    4. 路由层：前端为每个 mode 的后续动作提供对应路由（如 `/confirm-buy`）
    5. 接口层：后端为每个 mode 的后续动作提供 endpoint
    6. 状态机层：必要时引入中间状态（如 `pending_confirm`）防越权
  - **判断信号**：
    - `grep "task_mode\|mode.*AUTO\|mode.*MANUAL"` 在事件 payload / 通知模板 / 路由 / endpoint 中未命中 → 链路断裂
    - 决策函数返回值与 mode 无关 → 决策层未实现
    - 通知模板对所有 mode 渲染相同内容 → 通知层未实现
  - **配置参数**：`mode_vertical_chain.enabled`、`mode_vertical_chain.required_layers`（默认 `["decision", "event", "notification", "router", "endpoint", "state_machine"]`）、`mode_vertical_chain.mode_field_names`（默认 `["task_mode", "execution_mode", "notification_mode"]`）在 `config.yaml` 的 `mode_vertical_chain` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.37.0 meta-rules #53 / step 190
  - **适用**：所有引入 mode 枚举且影响后续行为的业务（任务执行模式、采集模式、通知模式、订单确认模式）
  - **不适用**：纯展示型 mode 字段（仅日志记录不影响流转）、内部状态字段（不跨层传递）、单一布尔开关（无枚举语义，归 #40 MULTI-FIELD-LINKED-SWITCH）
  - **历史教训**：SEMI_AUTO 模式退化为 CONFIRM/NOTIFY，因为：`_should_buy()` 返回 False / 通知模板缺确认链接 / 事件 payload 缺 `task_mode` / 缺 `pending_confirm` 中间状态 / 缺确认接口。修复：5 层全补齐 + 引入 `pending_confirm` 状态。

- 🆕v4.34【强制】**B-REVIEW-179：PARSER-FALLBACK-CHAIN 外部页面解析容错**
  - 维度：13 浏览器自动化
  - 严重等级：warning（P1，外部 DOM 变化导致解析失败）
  - 规范引用：meta-rule #54 外部页面解析容错
  - **检查点**：解析不受控的第三方页面 DOM 必须采用多级 fallback selector 策略，任一 selector 命中即返回，全部失败才触发 debug dump
  - **检查项**：
    1. 三级 fallback：按"结构化 selector → 属性 selector → 文本扫描"顺序尝试
    2. debug dump 触发条件基于业务语义（如 `on_sale == 0`）而非实现细节（如 `sold == 0`）
    3. selector 列表配置化，禁止硬编码
    4. 降级链日志合并（与 B-REVIEW-158 LOG-MERGE 一致），中间步骤 DEBUG 化
  - **判断信号**：
    - `grep "querySelector\|querySelectorAll\|select\|css"` 在外部页面解析上下文，无 `try/except` 或 `or []` fallback → 违规
    - `grep "tabItem\|tab.*role.*tab\|tab.*class"` selector 字符串硬编码 → 违规
    - debug dump 条件含 `sold == 0`（实现细节）而非 `on_sale == 0`（业务语义）→ 违规
  - **配置参数**：`parser_fallback.enabled`、`parser_fallback.fallback_levels`（默认 3）、`parser_fallback.selectors`（默认 `["[class*='tabItem']", "[class*='tab'][role='tab']", "text_prefix_scan"]`）、`parser_fallback.debug_dump_trigger`（默认 `on_sale == 0`）在 `config.yaml` 的 `parser_fallback` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.37.0 meta-rules #54 / step 191
  - **适用**：所有解析闲鱼 / 淘宝 / 天猫 / 京东等第三方页面的代码（`_detail.py` / `_parse_*` 函数 / Playwright page.evaluate 返回值解析）
  - **不适用**：解析自己生成的内容（本地 HTML 模板）、解析 API 返回的 JSON（结构稳定）、解析固定 schema 的 XML/YAML
  - **历史教训**：`_parse_sale_counts_from_tabs` 仅依赖 `tabItem` class 名，闲鱼页面 DOM 结构变化导致 `on_sale=0` 和 `sold=0`。修复：实现三级 fallback（`[class*='tabItem']` → `[class*='tab'][role='tab']` → 文本前缀扫描 div/span/a），收紧 debug dump 触发条件从 `on_sale==0 or sold==0` 改为 `on_sale==0`。

- 🆕v4.34【强制】**B-REVIEW-180：MOCK-SYNC-BOUNDARY mock 同步与边界精确性**
  - 维度：20 测试建议
  - 严重等级：critical（P0，mock 类型错配导致测试失败或假阳性）
  - 规范引用：meta-rule #55 mock 同步与边界精确性
  - **与 B-REVIEW-TEST-MOCK-SYNC（v4.27）的边界**：B-REVIEW-TEST-MOCK-SYNC 关注"修改前置条件时同步更新测试 mock"，本规范关注"mock 的类型/边界/字段/副作用精确性"
  - **检查点**：修改被测代码后必须同步 mock：mock 类型与被 mock 对象的同步/异步特性必须一致，patch 必须 patch 实际调用点而非定义点
  - **检查项**：
    1. 类型匹配：同步函数用 `MagicMock`，异步函数用 `AsyncMock`，禁止混用
    2. patch 边界：patch 实际调用点（如 `worker.get_secret`）而非定义点（如 `secrets.get_secret`）
    3. 字段完整性：mock 数据覆盖被测代码访问的所有字段，禁止部分 mock
    4. 副作用验证：测试必须断言"副作用未发生"（如未发起真实网络请求 / 未写文件 / 未发邮件）
  - **判断信号**：
    - `grep "AsyncMock" <test_file>` 但被 mock 函数是同步函数（无 `async def`）→ 违规
    - `grep "MagicMock" <test_file>` 但被 mock 函数是 `async def` → 违规
    - `patch("module.function")` 但实际调用是 `from module import function; function()` → patch 边界错误
  - **配置参数**：`mock_sync.enabled`、`mock_sync.type_mapping`（默认 `{"sync": "MagicMock", "async": "AsyncMock"}`）、`mock_sync.required_assertions`（默认 `["no_real_network_request", "no_file_write", "no_email_send"]`）在 `config.yaml` 的 `mock_sync` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.37.0 meta-rules #55 / step 192
  - **适用**：所有 unit test / 集成测试中的 mock 替身
  - **不适用**：E2E 测试（应使用真实环境）、快照测试（snapshot test）
  - **历史教训**：`test_dingtalk_notify_integration.py` 用 `AsyncMock` 但 `worker.py` 的 `filter_new` 已改为同步实现，导致 `await` 在同步对象上失败。`test_notifier_new_channels.py` patch `get_secret` 位置错误导致 webhook_url/secret 实际不为空，测试发起真实钉钉请求。修复：AsyncMock 改 MagicMock / patch get_secret 返回 None / test_manual_takeover_lock 构造 mock request 含 user_id。
