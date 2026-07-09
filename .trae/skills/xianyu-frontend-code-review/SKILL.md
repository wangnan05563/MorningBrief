---
name: "xianyu-frontend-code-review"
description: "对闲鱼猎人项目前端代码（frontend/src/ 下 React/TypeScript/Ant Design/Zustand 文件）进行全面评审与逻辑审查，覆盖类型安全、业务逻辑、Zustand 状态管理、API 契约、Hooks 设计、路由懒加载、AntD 主题、性能、可访问性、可测试性、认证规范、SonarQube 合规、注册式资源三件套契约等 36 个维度。当用户要求'审查/检查/走查/把关/review/评估/看看对不对/规范不规范'前端 React/TS 代码、'.tsx/.ts 文件修改'、'迭代发布前前端走查'，或提到'前端评审/frontend review/React 代码审查/TypeScript 评审/组件代码走查'时调用。仅审查前端 .tsx/.ts 文件；纯后端 .py 文件审查请改用 xianyu-backend-code-review。"
whenToUse: "需要审查闲鱼猎人前端代码（frontend/src/ 下 .tsx/.ts 文件，含 pages/页面、components/组件、hooks/、stores/Zustand、api/、routes/路由、App.tsx、main.tsx）是否符合项目规范"
triggers: "前端代码 走查/审查/审核/把关/review/检查/评估 | 前端评审/frontend review/React 代码审查/TypeScript 评审/组件代码走查/AntD 评审/Zustand 评审 | .tsx/.ts 文件 修改/变更/迭代 走查 | 迭代发布前 前端 代码 走查 | 这段前端代码/组件/Hook 写得对不对/规范不规范 | 闲鱼 前端 代码 review | 页面/组件/Hook/Store/路由 代码 审查"
version: "4.44.0"
updated: "2026-07-09"
config: "config.yaml"
scripts: "scripts/auto-scan.ps1"
template: "templates/report-template.md"
---

# 闲鱼猎人前端代码审查

对闲鱼猎人项目前端代码（`frontend/src/` 下的 React/TypeScript/Ant Design/Zustand 文件）进行全面的代码评审及逻辑审查。评审涵盖**36 个维度**，包括类型安全、业务逻辑、Zustand 状态管理、API 契约、Hooks 设计、路由与懒加载、AntD 主题、性能、可访问性、可测试性、认证规范、SonarQube 合规、模型能力集中展示、端到端失败原因链前端侧同步原则、跨边界访问契约前端侧、业务关键字常量集中管理与字段名大小写敏感、多用户认证上下文隔离、数据契约与时序（meta-rules #25-30 落地）、状态恢复前置校验前端侧（meta-rules #31 落地）、注册式资源三件套契约（meta-rules #33 落地）、修复前全链路根因扫描协议（meta-rules #34 落地）、前后端字段契约单一可信源（meta-rules #35 落地）、规范治理（meta-rules #36-37 落地）、列表聚合与状态联动（meta-rules #38-42 落地）、跨层契约与测试同步（meta-rules #43-47 落地）、调度器运行时治理前端侧（meta-rules #48-51 落地）。

## 版本演进索引

> 各版本的完整复盘详情（Sequential Thinking 复盘法、根因分析、检查点详情、对应后端规范）已外部化至 [references/version-changelog.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/version-changelog.md)。本表仅作索引，需查阅历史决策与根因时再读取该文件。

| 版本 | 新增检查点 | 维度 | 扫描项 | 核心变化 |
|---|---|---|---|---|
| v2.0.0 | — | 1,3,4,5,6,7,8,9,10,12,13,14,15,17,18 | 0→12 | 知识点整合（frontend-guide.md + project-rules.md） |
| v3.0.0 | — | 12 | 14→26 | SonarQube 规则从 8 条扩展到 16 条（S7503/S6767/S6819 等） |
| v4.0.0 | — | 3,10,11,17,18 | 26→36 | Tab 布局重构 + 实时搜索标准化 + 代码评审通用规范 |
| v4.1.0 | F-REVIEW-SSE-ERROR-HANDLING | 15 | 36→38 | SSE 错误事件状态码分类处理 |
| v4.2.0 | F-REVIEW-UI-STATE-INDEPENDENCE | 3 | 38→39 | 受控 UI 状态不应通过 useEffect 联动路由 |
| v4.3.0 | 维度 19（跨组件状态同步与死代码检测） | 19 | 39→43 | 反爬模块代码审查复盘 |
| v4.4.0 | F-REVIEW-CONFIG-DRIVEN-TOGGLE | 11 | 43→44 | 高风险功能必须配置驱动 |
| v4.5.0 | F-REVIEW-ERROR-SEMANTICS / F-REVIEW-CONFIG-LINKAGE | 11,7 | 44→46 | 错误语义匹配 + 配置链路追踪 |
| v4.6.0 | F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND | 6 | 46→47 | 多写入入口统一 updateState |
| v4.7.0 | F-REVIEW-ASYNC-FEEDBACK / DATA-FLOW-TRACE / FILTER-SCENARIO / REUSE-PATTERN | 10,11,7,18 | 47→51 | 异步三态反馈 + 数据流转追踪 + 场景标志 + 复用模式 |
| v4.8.0 | F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE | 5 | 51→52 | 暗色主题 token 动态覆盖 |
| v4.9.0 | F-REVIEW-FREQ-STATS-POLLING | 10 | 52→53 | 累计统计类 API 前端定时刷新 |
| v4.10.0 | F-REVIEW-FILTER-VISIBILITY | 7 | 53→54 | filter_summary 三态提示策略 |
| v4.11.0 | F-REVIEW-STATE-ENUM-ALIGN / STATE-MACHINE-UI / DUAL-LINK-CACHE-CONSISTENCY | 4,3,6 | 54→57 | 状态机/双链路/缓存一致性 |
| v4.12.0 | F-REVIEW-ASYNC-CONFIG-LOAD / INPUT-NUMBER-BOUNDS / NULL-SEMANTICS / XSS-ESCAPE / BATCH-OPERATION | 10,4,11,7 | 57→62 | 配置加载/输入边界/null 语义/XSS/批量操作 |
| v4.13.0 | F-REVIEW-ERROR-CONTRACT-TIMEOUT / RETRY-BACKOFF | 7,7 | 62→64 | 错误契约映射表 + 退避重试策略 |
| v4.14.0 | F-REVIEW-FILTER-BACKEND-ALIGN / FILTER-PAGINATION-ADAPT / FILTER-EMPTY-STATE | 7,10,3 | 64→67 | 评估明细过滤/分页/空状态 |
| v4.15.0 | F-REVIEW-DEBUG-CODE-CLEANUP | 11 | 67→68 | 临时 DEBUG 代码必须移除 |
| v4.16.0 | F-REVIEW-STATE-FUNCTIONAL-ALIGN / FIELD-CONTRACT-ALIGN / ASYNC-RACE-CONDITION / ERROR-HANDLER-EXTRACT | 3,11,10,11 | 68→72 | Cookie 层状态管理 + api_ai_deep 接入复盘 |
| v4.19.0 | F-REVIEW-SCHEDULER-STATUS-DISPLAY | 18 | 72→73 | 关于页展示调度器启动状态 |
| v4.20.0 | F-REVIEW-VERSION-SOURCE-ALIGN | 7 | 73→74 | 版本号源语义对齐 API |
| v4.22.0 | F-REVIEW-PWA-CACHE-VERIFY | 13 | 74→75 | PWA 三层缓存验证 |
| v4.23.0 | F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION | 11 | 75→76 | LLM 模型能力集中展示与降级可视化 |
| v4.24.0 | F-REVIEW-UI-PREFERENCE-PERSISTENCE | 10 | 76→77 | 用户偏好类 UI 状态必须用 usePersistentState |
| v4.25.0 | 无新增（仅同步原则） | — | 77 | 数据库迁移块独立容错（前端仅同步原则，纯后端问题） |
| v4.26.0 | F-REVIEW-THREE-STATE-NULL-SEMANTICS / ERROR-HANDLING-CONSISTENCY / DEFAULT-OPERATOR-CONSISTENCY | 7,20,4 | 77→80 | API 三态语义 + 错误处理 + 默认值操作符 |
| v4.27.0 | F-REVIEW-ERROR-CODE-BRANCH / PRECHECK-API-DELEGATION / MOCK-FIELD-SET-SYNC | 25 | 80→83 | 端到端失败原因链前端侧同步（新增维度 25） |
| v4.28.0 | F-REVIEW-WF-ERROR-HANDLING / WF-BATCH-CIRCUIT-BREAKER / WF-RESOURCE-LIFECYCLE / WF-STATE-SYNC | 19,6,10,11 | 83→87 | 工作流元规范硬约束（与 xianyu-hunter-dev meta-rules #21-24 对应） |
| v4.30.0 | F-REVIEW-DATETIME-RENDER-CONTRACT / PRIVATE-HOOK-ENCAPSULATION / NAMING-CONSISTENCY-FRONTEND | 26 | 87→90 | 跨边界访问契约前端侧（新增维度 26） |
| v4.31.0 | F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION / EVENT-TYPE-EXACT-MATCH / FIELD-NAME-CASE-SENSITIVE | 27 | 90→93 | 业务关键字常量集中管理 + 事件类型过滤精确匹配 + 前后端字段名大小写敏感（新增维度 27） |
| v4.32.0 | F-REVIEW-MULTI-USER-CONTEXT-ISOLATION / AUTH-TOKEN-COOKIE-HANDLING | 28 | 93→95 | 多用户认证上下文隔离（新增维度 28，与 xianyu-hunter-dev step 134-137 对应） |
| v4.33.0 | F-REVIEW-EFFECT-MINIMIZE / STATE-ATOMICITY / SSE-CONN-MGMT / ASYNC-RACE-GUARD / THEME-DYNAMIC-ADAPT / EMBEDDED-LAYOUT-HEIGHT / COMPONENT-REGISTRY / FILTER-TRANSPARENCY / DATA-SOURCE-VERIFY / STATS-RANGE-CALIBRATE / UI-SEMANTICS-SPLIT / PERSIST-BUSINESS-SWITCH / ERROR-MESSAGE-PASS / API-CONTRACT-CONSISTENCY | 3,15,5,10,7 | 95→109 | 全量复盘与审查要点同步：新增 14 项 F-REVIEW（覆盖 useEffect 副作用/状态原子性/SSE 三要素/竞态防护/主题动态适配/嵌入式布局/组件注册/过滤透明化/数据源校验/统计范围/UI 语义/状态持久化/错误透传/API 契约），4 阶段流水线审查流程 + 结构化报告模板 |
| v4.34.0 | F-REVIEW-110~115（meta-rules #25-30 落地） | 29 | 109→115 | 数据契约与时序（新增维度 29，对应 xianyu-hunter-dev v4.30.0 meta-rules #25-30 与后端 v4.29.0 维度 31 的 B-REVIEW-151~156，前端 6 项检查点：批量断路器 UI 反馈/ErrorBoundary 完整 traceback/ISO datetime 渲染/跨进程 SSE 同步/error_code 分支/业务关键字常量集中管理） |
| v4.35.0 | F-REVIEW-116 RESUME-PRECHECK-FRONTEND | 30 | 115→116 | 状态恢复前置校验前端侧（对应 xianyu-hunter-dev v4.31.0 meta-rules #31 与后端 B-REVIEW-157） |
| v4.36.0 | F-REVIEW-117 REGISTRATION-COMPLETENESS / F-REVIEW-118 ROOT-CAUSE-MIN-COUNT / F-REVIEW-119 CONTRACT-SINGLE-SOURCE | 31,32,33 | 116→119 | 注册式资源三件套契约 + 修复前根因扫描协议 + 前后端字段契约单一可信源（新增维度 31-33，对应 xianyu-hunter-dev v4.32.0 meta-rules #33-35 与后端 B-REVIEW-159/160/161） |
| v4.37.0 | F-REVIEW-120 SEDIMENTATION-THRESHOLD / F-REVIEW-121 DEGRADATION-CLEANUP | 34 | 119→121 | 规范沉淀门槛与退化机制（新增维度 34，对应 xianyu-hunter-dev v4.33.0 meta-rules #36-37 与后端 B-REVIEW-162/163，防过度规范化与规范膨胀） |
| v4.38.0 | F-REVIEW-122 GLOBAL-AGGREGATE-TASK-FILTER / F-REVIEW-123 LIST-CROSS-DOMAIN-INJECT / F-REVIEW-124 MULTI-FIELD-LINKED-SWITCH / F-REVIEW-125 RESUME-PRECHECK-STRUCTURED / F-REVIEW-126 CONFIG-DRIVEN-THRESHOLD-FALLBACK | 34 | 121→126 | 列表聚合与状态联动（维度 34 扩展，对应 xianyu-hunter-dev v4.34.0 meta-rules #38-42 与 step 184-188，前端侧 5 项检查点：全局聚合任务级过滤 / 列表交叉数据批量注入 / 多字段联动开关 / 状态恢复前置校验结构化 / 配置化阈值兜底） |
| v4.39.0 | F-REVIEW-131 EVENT-MULTI-EMIT-ALIGN / F-REVIEW-132 ROUTE-TRIPLE-REGISTRATION / F-REVIEW-133 QUERY-STRING-RETAIN / F-REVIEW-134 TEST-SYNC-RESPONSIBILITY / F-REVIEW-135 EXTERNAL-DEP-ISOLATION | 35 | 126→131 | 跨层契约与测试同步（新增维度 35，对应 xianyu-hunter-dev v4.35.0 meta-rules #43-#47 与后端 B-REVIEW-169~173，前端 5 项检查点：事件多发布点字段对齐 / 路由三重注册同步 / query string 保留 / 测试同步责任 / 外部依赖隔离） |
| v4.42.0 | F-REVIEW-144 PARAM-CHAIN-EXEC-FRONTEND / F-REVIEW-145 MODE-VERTICAL-CHAIN-FRONTEND / F-REVIEW-146 MOCK-SYNC-BOUNDARY-FRONTEND / F-REVIEW-147 FILTER-RESULT-TRANSPARENCY-UI | 7,4,12,7 | 131→135 | 参数链闭环 / 业务模式纵向链路 / mock 同步边界 / 过滤结果透明化 UI（对应 `xianyu-hunter-dev` v4.37.0 meta-rules #52/#53/#55/#56 前端侧；meta-rule #54 外部页面解析容错仅后端适用不新增前端检查点） |
| v4.43.0 | F-REVIEW-148 ASYNC-AWAIT-SYNC-CHECK-FRONTEND / F-REVIEW-149 HTTP-ERROR-LOCALIZATION / F-REVIEW-150 ERROR-CHAIN-TRANSPARENT / F-REVIEW-151 EXTERNAL-RESOURCE-CLEANUP-FRONTEND | 10,7,7,10 | 135→139 | async/await 同步性检查 / HTTP 错误本地化 / 错误链透明化 / 外部资源清理（对应 `xianyu-hunter-dev` v4.38.0 meta-rules #57/#59/#61/#62 前端侧；#58/#60/#63 纯后端不新增前端检查点） |
| v4.44.0 experimental | F-REVIEW-152 URL-STATE-SYNC-FALLBACK / F-REVIEW-153 SW-CACHE-VERSION-SYNC | 3,13 | 139→141 experimental | URL↔状态同步失败回退 / SW 缓存版本同步（experimental 预沉淀，对应 `xianyu-hunter-dev` v4.39.0 meta-rules #64/#65 前端侧；案例数<3 次，按 meta-rule #36 门槛规则标 experimental，观察期 2026-07-08 至 2026-10-08） |

## 配置驱动

**核心原则**：所有评审规则、硬约束、项目规范均通过 `config.yaml` 管理，技能本身不含任何业务参数或硬编码值。新增规则只需修改配置文件，无需改动技能本身。

配置文件位置：`.trae/skills/xianyu-frontend-code-review/config.yaml`

首次使用时，从同目录的 `config.example.yaml` 复制并按项目实际情况修改。配置项分为 9 大类：

| 配置类 | 职责 | 关键参数 |
|--------|------|----------|
| `scope` | 评审范围 | include_paths, exclude_paths, file_extensions, max_files_per_run |
| `priority` | 优先级排序 | severity_order, category_order, report_threshold |
| `hard_constraints` | 硬约束规则 | rules（可扩展列表，每条含 name/pattern/message/severity/auto_fix） |
| `checklist` | 评审检查清单 | 19 大类开关 |
| `abstraction_thresholds` | 抽象建议阈值 | inline_style_repeat, text_literal_repeat, function_max_lines 等 |
| `report` | 报告生成 | output_dir, format, include_good_practices, max_suggestions |
| `verify` | 验证配置 | run_tests_after_review, test_command, fail_on_critical |
| `project_conventions` | 项目专属规范参考 | ui_library, visual_style, auth_requirements, test_framework 等 |
| `meta_rules_38_42_frontend` | 列表聚合与状态联动（meta-rules #38-42 前端侧，🆕v4.38） | global_aggregate_filter, cross_domain_inject, linked_switch_priority, precheck_structured_fields, config_fallback_defaults |
| `cross_layer_contract_test_sync` | 跨层契约与测试同步（meta-rules #43-47 前端侧，🆕v4.39） | event_multi_emit_alignment, frontend_route_registration, external_callback_query_retention, test_synchronization, external_dependency_isolation |
| `scheduler_runtime_governance_frontend` | 调度器运行时治理前端侧（meta-rules #48-51 前端侧，🆕v4.40） | scheduler_status_sync, polling_interval_config, hook_cleanup_completeness, cron_expr_frontend_validate |

## 审查模式

| 模式 | 扫描范围 | 触发 |
|------|---------|------|
| 快速自检 | 仅阻塞级 | `pwsh .trae/skills/xianyu-frontend-code-review/scripts/auto-scan.ps1` |
| 增量审查 | `git diff --name-only` 变更文件 | 粘贴变更文件列表 |
| 指定文件审查 | 用户明确列出的文件 | 用户指定路径 |
| 片段评审 | 用户粘贴代码片段 | 无文件路径时仅输出建议 |
| 全量审查 | `frontend/src/**/*.{tsx,ts,js}` | 默认 |

---

> **v4.36.0 注册式资源三件套契约 + 修复协议 + 前后端字段契约复盘（meta-rules #33-35 前端落地）**：基于"通知中心菜单点击无反应"等历史问题复盘（用户报告"通知中心"菜单点击后 URL 不变、内容不变；根因是 `config/menu_registry.yaml` 已注册 `path=/notifications`，但 `frontend/src/App.tsx` 无对应 `<Route>`、`pages/Notifications/index.tsx` 不存在、`api/notifications.ts` 不存在，路由 fallback `<Route path="*" element={<Navigate to="/" replace />} />` 静默重定向到首页），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，新增 3 项维度（31-33）+ 3 项 F-REVIEW 检查点：**F-REVIEW-117 REGISTRATION-COMPLETENESS 注册式资源三件套契约**（meta-rule #33 落地——5 层契约：L1 menu_registry/L2 router/L3 page/L4 api_wrapper/L5 backend_endpoint 缺一即视为 CRITICAL，自动化校验 `python scripts/check_registration.py` 退出码 0 才算通过，参数在 `frontend_registration_completeness` 节点管理）、**F-REVIEW-118 ROOT-CAUSE-MIN-COUNT 修复前根因扫描协议**（meta-rule #34 落地——修复非平凡 bug 前必须先列 ≥3 个根因覆盖用户层/接口层/数据层/配置层/历史层；PR 描述必须含"≥3 根因列表"段；git diff 涉及 ≥3 个无关文件视为违反最小修改原则；新增逻辑无 unit test 视为 WARNING；参数在 `root_cause_protocol` 节点管理）、**F-REVIEW-119 CONTRACT-SINGLE-SOURCE 前后端字段契约单一可信源**（meta-rule #35 落地——后端 Pydantic/DB Row 字段 = 权威源；前端 `types.ts` 必须显式标注"派生来源"+ "Pydantic 字段"+ "变更日期"+ "约束" 4 段注释；snake_case 严格透传禁止转 camelCase；后端 Pydantic 字段 `xxx_yyy` + 前端 types.ts 字段 `xxxYyy` = CRITICAL 命名漂移；参数在 `contract_single_source` 节点管理）。所有新检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.32.0 的 meta-rules #33-35 与 step 181-183。后端对应规范为 `xianyu-backend-code-review` v4.31.0 的 B-REVIEW-159/160/161。

---

> **v4.38.0 列表聚合与状态联动复盘（meta-rules #38-42 前端落地）**：基于本轮对话解决的"捡漏价格参考"等列表聚合类问题复盘（全局聚合未按任务级 price_range/market_ratio 过滤导致越界数据 / 列表交叉数据 N+1 查询 / 多字段联动开关逻辑错误 / 状态恢复 precheck 抛异常 / 配置缺失即崩溃），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，在维度 34（规范治理）下追加 5 项 F-REVIEW 检查点（F-REVIEW-122~126），自动化扫描从 121 项扩展到 126 项。新增检查点：**F-REVIEW-122 GLOBAL-AGGREGATE-TASK-FILTER 全局聚合任务级过滤**（meta-rule #38 前端侧——前端聚合统计（如 Dashboard 价格区间分布、市场价比率分布）必须按当前任务的 `price_range`/`market_ratio` 配置过滤，禁止展示越界数据；前端展示聚合数据前必须确认后端已调用 `_filter_by_per_task_range` 过滤；参数在 `meta_rules_38_42_frontend.global_aggregate_filter` 节点管理）、**F-REVIEW-123 LIST-CROSS-DOMAIN-INJECT 列表交叉数据批量注入**（meta-rule #39 前端侧——列表渲染交叉数据（如商品列表注入最新评估价/订单状态）必须用批量 API 一次性获取，禁止循环中逐项 fetch；前端必须支持批量响应的 `id → value` 映射结构；参数在 `meta_rules_38_42_frontend.cross_domain_inject` 节点管理）、**F-REVIEW-124 MULTI-FIELD-LINKED-SWITCH 多字段联动开关范式**（meta-rule #40 前端侧——多字段联动开关（如 mode + bargain_only）必须遵循"主开关决定副开关可见性"范式，副开关值在主开关关闭时必须清零而非保留；前端 UI 必须根据主开关状态动态显示/隐藏副开关；参数在 `meta_rules_38_42_frontend.linked_switch_priority` 节点管理）、**F-REVIEW-125 RESUME-PRECHECK-STRUCTURED 状态恢复前置校验结构化响应**（meta-rule #41 前端侧——前端调用 resume/start 接口必须处理结构化 precheck 响应（`{resume_blocked, reason_code, user_hint, retry_after, task_registered}`），禁止假设接口直接成功；precheck 失败时必须展示 `user_hint` 与 `retry_after` 倒计时；参数在 `meta_rules_38_42_frontend.precheck_structured_fields` 节点管理）、**F-REVIEW-126 CONFIG-DRIVEN-THRESHOLD-FALLBACK 配置化阈值兜底范式**（meta-rule #42 前端侧——前端使用的阈值参数（如 p10 百分位、market_ratio_threshold、price_range_tolerance）必须从后端配置 API 获取，禁止前端硬编码；配置 API 失败时必须用兜底默认值并 `console.warn`，禁止抛异常导致页面崩溃；参数在 `meta_rules_38_42_frontend.config_fallback_defaults` 节点管理）。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `meta_rules_38_42_frontend` 节点管理，不硬编码业务参数）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.34.0 的 meta-rules #38-42 与 step 184-188。后端对应规范为 `xianyu-backend-code-review` v4.34.0 的 B-REVIEW-164~168。

---

## 审查规则（29 项维度）

### 1. 目录结构 🆕v2.0

- 【强制】所有代码在 `frontend/src/` 下开发
- 【强制】业务页面位于 `frontend/src/pages/<业务域>/`（如 `Dashboard/`、`Tasks/`、`Items/`、`Orders/`、`Evaluations/`、`Chatbot/`、`Config/`、`Logs/`、`Timeline/`、`Maintenance/`、`About/`、`Onboarding/`、`Login/`）
- 【强制】公共组件位于 `frontend/src/components/`（如 `SheetWorkspace/`、`layout/`、`charts/`、`editors/`、`icons/`、`ErrorBoundary.tsx`）
- 【强制】API 模块位于 `frontend/src/api/`，新增 API 归入子模块而非扩展 `index.ts`
- 【强制】自定义 Hook 位于 `frontend/src/hooks/`
- 【强制】状态管理位于 `frontend/src/stores/`
- 【强制】常量位于 `frontend/src/constants/`
- 【强制】类型定义位于 `frontend/src/api/types.ts`（统一出口）
- 【强制】工具函数位于 `frontend/src/utils/`

### 2. 命名规范

- 【强制】组件文件：PascalCase（如 `MainLayout.tsx`、`ErrorBoundary.tsx`）
- 【强制】API 模块文件：camelCase（如 `task.ts`、`about.ts`）
- 【强制】Hook 文件：`use<X>.ts`（如 `useAutoRefresh.ts`、`useSheetSync.ts`）
- 【强制】Store 文件：`<域>Store.ts`（如 `sheetStore.ts`、`configStore.ts`）
- 【强制】常量文件：按业务域分文件（`frontend/src/constants/`）
- 【强制】CSS 文件：camelCase + `.css` 后缀，与组件同目录（如 `chatbot.css`、`about.css`）
- 【强制】测试文件：`__tests__/<Component>.test.tsx`，与组件同级
- 【强制】常量：UPPER_SNAKE_CASE（如 `SSE_LAST_EVENT_ID_KEY`、`MIN_INTERVAL`、`MAX_RETRIES`）

### 3. React 组件规范 🆕v2.0

- 【强制】使用 `function` 关键字定义组件（**非**箭头函数）
- 【强制】Props 用 `type` 关键字定义（**非** `interface`，项目规范）
- 【强制】Hooks 调用顺序：所有 hooks 必须在条件性 return 之前调用（避免 React Hooks 规则违规）
- 【强制】双层 ErrorBoundary 容错：`LazyErrorBoundary` + `Suspense`
- 【强制】路由切换用 `requestAnimationFrame` 重置滚动位置
- 【强制】**容器适配**：被嵌入到 SheetWorkspace/MainLayout 等固定高度容器的页面组件，用 `height: 100%` 适应父容器
- 【禁止】在嵌入场景使用 `minHeight: 100vh` 或 `height: 100vh`（溢出容器导致全屏显示）
- 【强制】flex 布局中 Header 用 `flex: '0 0 auto'`，Content 用 `flex: 1` + `overflow: auto`
- 【推荐】独立路由页面（未进 MainLayout，如 `/login`）可用 `100vh`
- 🆕v4.0【强制】**多视图 state 提升**：Tab/Accordion/Collapse/Drawer 多视图共享同一数据源时，state 必须提升至最近共同父组件
- 🆕v4.0【强制】`destroyInactiveTabPane={false}` 保留 DOM（表单类避免输入焦点丢失）
- 🆕v4.0【强制】标题职责归容器（如 Tab label），子组件只保留功能说明文字，禁止标题重复
  - **判断信号**：两个子组件的 props 来自同一 config/state → 应提升
- 🆕v4.2【强制】**F-REVIEW-UI-STATE-INDEPENDENCE：UI 状态独立性原则**
  - 受控 UI 状态（`openKeys`/`expandedKeys`/`activeKey`/`Drawer open` 等）不应通过 `useEffect` 联动路由变化（`location.pathname`/`useNavigate`）
  - 路由变化只应更新**派生状态**：`selectedKeys`（高亮当前项）、breadcrumb（面包屑）、页面标题
  - **判断信号**：代码含 `useEffect(() => setOpenKeys(...), [autoOpenKeys])` 或 `useEffect(() => setExpandedKeys(...), [location.pathname])` → 视为违规
  - **修复模式**：`openKeys` 仅在首次挂载时按当前路由初始化（`useState(() => autoOpenKeys)`），之后完全由用户通过 `onOpenChange` 控制，移除 `useEffect` 联动
  - **适用**：Menu `openKeys`、Tree `expandedKeys`、Collapse `activeKey`、Tabs `activeKey`、Drawer `open` 等用户手动控制的 UI 状态
  - **不适用**：`selectedKeys`（应联动路由高亮）、breadcrumb（应联动路由）、页面标题（应联动路由）
  - **历史教训**：MainLayout 的 `openKeys` 通过 `useEffect` 联动 `autoOpenKeys`，sheet 切换触发 `navigate` → URL 变化 → `autoOpenKeys` 重算 → `setOpenKeys` 重置 → SubMenu 展开/折叠动画遮挡内容。第一次修复用"合并"策略仍会展开新 SubMenu，最终改为完全移除 `useEffect` 联动才彻底解决

```typescript
// ✅ 推荐：function 关键字 + type Props
type MainLayoutProps = {
  children: React.ReactNode
}

function MainLayout({ children }: MainLayoutProps) {
  return (
    <ConfigProvider>
      <LayoutContent />
    </ConfigProvider>
  )
}
```

```typescript
// ✅ 推荐：双层 ErrorBoundary + Suspense
const LazyRoute = ({ children }) => (
  <LazyErrorBoundary>
    <Suspense fallback={<Spin />}>
      {children}
    </Suspense>
  </LazyErrorBoundary>
)
```

- 🆕v4.11【强制】**F-REVIEW-STATE-MACHINE-UI：状态机 UI 视觉标识完整性**
  - 业务对象有状态字段（如 `task.status` / `session.state` / `order.status`）时，每个状态值必须有对应的 UI 视觉标识：颜色 Tag / 图标 / 文案 / 操作按钮，**禁止**终态显示"进行中"类动画，中间态必须有 loading 反馈
  - **核心机制**（审查时必须理解）：
    - 后端状态机有白名单转换规则（B-REVIEW-STATE-MACHINE-WHITELIST），前端 UI 必须为每个状态值提供明确的视觉标识
    - 终态（`completed` / `failed` / `cancelled`）禁止显示 loading 动画或"进行中"文案，应显示最终结果的静态标识（成功/失败/已取消）
    - 中间态（`pending` / `running` / `processing`）必须有 loading 反馈（Spin / 进度条 / 动画图标），让用户感知任务正在进行
    - 状态对应的操作按钮必须与状态机白名单转换一致（如 `running` 状态显示"暂停"按钮，`paused` 状态显示"恢复"按钮，`completed` 状态不显示任何操作按钮）
  - **判断信号**：
    - `grep "status" frontend/src/` 发现状态值但无对应 Tag/图标/文案映射 → 视为违规
    - 终态状态（`completed`/`failed`/`cancelled`）仍显示 loading 动画 → 视为违规
    - 中间态状态（`pending`/`running`）无 loading 反馈 → 视为违规
    - 操作按钮与状态机白名单不一致（如 `completed` 状态仍显示"暂停"按钮）→ 视为违规
    - 后端新增状态值但前端 UI 无对应视觉标识 → 视为违规
  - **修复模式**（状态 → 视觉标识映射表 + 操作按钮白名单）：
    ```typescript
    // ✅ 状态视觉标识映射表（集中管理）
    const TASK_STATUS_UI: Record<TaskStatus, { color: string; text: string; icon: ReactNode; loading: boolean }> = {
      pending: { color: 'default', text: '待开始', icon: <ClockCircleOutlined />, loading: false },
      running: { color: 'processing', text: '运行中', icon: <LoadingOutlined />, loading: true },
      paused: { color: 'warning', text: '已暂停', icon: <PauseCircleOutlined />, loading: false },
      completed: { color: 'success', text: '已完成', icon: <CheckCircleOutlined />, loading: false },
      failed: { color: 'error', text: '已失败', icon: <CloseCircleOutlined />, loading: false },
    }
    // ✅ 操作按钮白名单（与后端状态机 TRANSITIONS 一致）
    const TASK_ACTIONS: Partial<Record<TaskStatus, Action[]>> = {
      pending: [{ key: 'start', label: '开始' }],
      running: [{ key: 'pause', label: '暂停' }],
      paused: [{ key: 'resume', label: '恢复' }, { key: 'stop', label: '停止' }],
      // completed / failed 无操作按钮（终态不可复活）
    }
    // 消费方
    const ui = TASK_STATUS_UI[task.status]
    <Tag color={ui.color} icon={ui.icon}>{ui.text}</Tag>
    {ui.loading && <Spin size="small" />}
    {TASK_ACTIONS[task.status]?.map(a => <Button key={a.key} onClick={() => handleAction(a.key)}>{a.label}</Button>)}
    ```
  - **配置参数**：`status_ui_mapping`（状态 → 视觉标识映射表，含 color/text/icon/loading 字段）、`terminal_states`（终态列表，默认 `['completed', 'failed', 'cancelled']`，禁止 loading 动画）、`intermediate_states`（中间态列表，默认 `['pending', 'running', 'processing']`，必须 loading 反馈）、`action_whitelist`（状态 → 允许的操作按钮白名单，与后端 TRANSITIONS 一致）在 `config.yaml` 的 `state_machine_ui` 节点管理
  - **适用**：所有有状态字段的业务对象（任务/会话/订单/评估）；后端有状态机白名单转换的场景
  - **不适用**：纯前端 UI 状态（如 `loading` / `open` / `active`）；无状态机的 CRUD 实体；状态值不展示给用户的内部状态
  - **历史教训**：任务状态 `completed` 仍显示 loading 动画（因为前端 `TASK_STATUS_UI` 映射表未区分终态与中间态），用户以为任务还在运行反复刷新页面。且 `failed` 状态仍显示"暂停"按钮（操作按钮未与后端状态机白名单一致），用户点击后后端返回 400 错误。修复后映射表区分终态/中间态 + 操作按钮按白名单显示

- 🆕v4.16【强制】**F-REVIEW-STATE-FUNCTIONAL-ALIGN：状态显示与功能可用性一致**
  - 前端 UI 显示的"功能/会话/服务状态"（如 Cookie 层状态：`identity` / `session` / `tracking` 是否失效；服务可用性：SSE 连接、API 健康度、采集器运行状态）必须与"功能实际可用性"保持一致；**禁止**仅依据后端返回的"初始值"或"短期缓存"判定 UI 状态显示为"失效/异常"
  - **核心机制**（审查时必须理解）：
    - 后端"功能信号"字段（如 `last_session_invalid` / `is_healthy` / `is_connected`）的初始值（默认 `False`）表示"未检测"，**不能**被解读为"功能正常"
    - 后端"功能信号"必须配合"已发生过检测"标记（首次成功时间戳 `_last_check_at > 0`、计数器 `use_count > 0`、首次成功标志 `_has_run`）才有"已检测"语义
    - 前端 UI 状态显示"有效/正常"前必须先确认"已发生过真实调用且成功"，**禁止**仅看后端初始 `False` → 误判为"正常"→ 显示绿色有效标识
    - 跨进程/跨模块场景下，子进程已检测成功的状态变更必须通过 SSE / 状态广播实时同步到前端，**禁止**前端用 30 秒 TTL 缓存兜底（子进程状态变更后 30 秒内前端仍显示旧状态）
  - **判断信号**：
    - `grep "state === 'valid'\\|state === 'normal'\\|state === 'healthy'" frontend/src/` 出现不配合"已检测"标记的硬编码布尔判定 → 视为违规
    - `grep "sessionInvalid\\|isInvalid\\|isExpired" frontend/src/` 仅依据后端单次返回值更新 UI 状态（无首次成功时间戳、计数器辅助）→ 视为违规
    - UI 状态显示组件（如 `<StatusTag>` / `<LayerStatusBadge>`）的 props 来自未校验的布尔字段（如 `valid` 默认 `false`）→ 视为可疑
    - 跨进程状态同步依赖 `setInterval` 轮询（30s/60s TTL）而未使用 SSE 推送 → 视为可疑（同步不及时）
  - **修复模式**：
    ```typescript
    // ✅ 后端 types.ts 显式区分"未检测" / "已检测有效" / "已检测无效"
    // 与后端 xianyu-backend-code-review v4.15.0 的 B-REVIEW-STATE-DETECTION-BOOTSTRAP 对齐
    export type LayerStatus =
      | 'unknown'      // 初始未检测（前端必须显示灰色/未检测，不显示"失效"）
      | 'valid'        // 已检测且有效
      | 'invalid'      // 已检测且失效
      | 'stale'        // 已检测但超时（>last_check_threshold_seconds）

    // ✅ 接收后端"已检测"标记
    interface LayerState {
      status: LayerStatus
      lastCheckedAt: number    // 0 = 未检测
      useCount: number         // 0 = 未检测
      lastError?: string
    }

    // ✅ UI 渲染：仅当 lastCheckedAt > 0 时才显示"已检测"状态
    function LayerStatusBadge({ state }: { state: LayerState }) {
      if (state.lastCheckedAt === 0 && state.useCount === 0) {
        return <Tag color="default">未检测</Tag>   // 必须明确区分"未检测"与"已失效"
      }
      if (state.status === 'valid') {
        return <Tag color="success">有效</Tag>
      }
      if (state.status === 'invalid') {
        return <Tag color="error">失效</Tag>
      }
      if (state.status === 'stale') {
        return <Tag color="warning">检测超时</Tag>
      }
      return <Tag color="default">未知</Tag>
    }

    // ❌ 违规：仅依据布尔 initial=false 判定"有效"
    // function LayerStatusBadge({ valid }: { valid: boolean }) {
    //   return <Tag color={valid ? 'success' : 'error'}>{valid ? '有效' : '失效'}</Tag>
    // }
    // 问题：刚启动时 valid=false 被解读为"失效"，但实际语义是"未检测"
    ```
  - **配置参数**：
    - `state_functional_align.required_check_marker`：默认 `true`，必须有"已检测"标记（`lastCheckedAt > 0` / `useCount > 0` / `hasRun` 至少一个）
    - `state_functional_align.unknown_status_display`：默认 `'未检测'`，未检测状态的 UI 文案
    - `state_functional_align.sse_push_required`：默认 `true`，跨进程状态变更必须 SSE 推送（禁止 TTL 兜底）
    - `state_functional_align.ttl_grace_seconds`：默认 `0`，跨进程同步的 TTL 兜底秒数（0 即不依赖 TTL）
    - `state_functional_align.stale_threshold_seconds`：默认 `3600`，已检测状态超过该秒数视为 `stale`（检测超时）
    - `state_functional_align.status_field_mapping`：状态字段到判定逻辑的映射（如 `cookie_layer → {required: ['lastCheckedAt', 'useCount'], initialValue: 'unknown'}`）
    - `state_functional_align.status_color_mapping`：状态值到 UI 颜色/文案的映射（如 `{valid: 'success', invalid: 'error', unknown: 'default', stale: 'warning'}`）
    在 `config.yaml` 的 `state_functional_align` 节点管理
  - **适用**：所有"功能/会话/服务状态"显示（Cookie 层有效性 / SSE 连接状态 / API 健康度 / 采集器运行状态 / 第三方服务可达性 / 任务调度器状态）；跨进程/跨模块状态同步（子进程→主进程→前端）；状态自愈（容器健康检查、服务可用性兜底）
  - **不适用**：纯前端 UI 状态（如 `loading` / `open` / `active` 开关）；单次函数返回值（无状态延续语义）；无初始歧义的纯布尔开关（如 `enableNotification: boolean`）；后端已用布尔 `True/False` 明确表达"有效/失效"且前端仅做展示映射的场景
  - **历史教训**：用户反馈"实时查询、官方采集均能正常运行，但反爬登录管理页的 `identity` / `session` / `tracking` 状态持续显示为失效（红 X 标签）"，根因：后端 `CookieStore` 用 30 秒 TTL 兜底缓存子进程状态，浏览器子进程登录后只更新子进程自己的内存缓存，主进程读时仍取到 TTL 内的旧"失效"状态（30 秒后才自动恢复），同时前端 `LayerStatusBadge` 仅依据 `valid: boolean` 显示（无"未检测"区分），导致用户看到"功能可用但状态持续失效"长达 30 秒，体感"明明能跑却一直报错"。修复后三层：①后端 `sync_cookie_layers_from_json()` 显式调用 `invalidate_cache()`（B-REVIEW-CACHE-INVALIDATION）②后端 `collector.last_session_invalid=False` 仅在 `_last_m5tk_refresh > 0` 时才恢复所有层（B-REVIEW-STATE-DETECTION-BOOTSTRAP）③前端 `LayerStatusBadge` 区分 `unknown` / `valid` / `invalid` / `stale` 四态，无"已检测"标记时显示灰色"未检测"而非"失效"

### 4. TypeScript 严格规范 🆕v2.0

- 【强制】`tsconfig.json` 严格配置（`strict: true`、`noFallthroughCasesInSwitch: true`、`isolatedModules: true`）
- 【强制】`moduleResolution: bundler`（Vite 兼容）
- 【强制】路径别名 `@/* → src/*`
- 【强制】`target: ES2020`，`jsx: react-jsx`（React 18 自动 runtime）
- 【强制】优先 `type` 而非 `interface`（项目规范）
- 【强制】字符串字面量联合而非 enum（如 `type TaskStatus = 'active' | 'paused' | 'stopped'`）
- 【强制】可选字段用 `?` 而非 `| undefined`
- 【禁止】使用 `any` 类型（SonarQube S4325），必要时用 `unknown` + 类型守卫
- 【强制】前后端字段类型对齐：`interface Task` 与后端 `TaskRow` 字段一致
- 【推荐】复杂类型用 `TypeAlias` 提升可读性

```typescript
// ✅ 推荐：字符串字面量联合 + type
type TaskStatus = 'active' | 'paused' | 'stopped'

// ❌ 错误：enum
enum TaskStatus { Active, Paused, Stopped }
```

- 🆕v4.11【强制】**F-REVIEW-STATE-ENUM-ALIGN：前后端状态枚举值对齐**
  - 业务对象有状态字段（如 `task.status` / `session.state` / `order.status`）时，前端 `types.ts` 必须导出与后端严格对齐的状态联合类型，**禁止**前端硬编码状态字符串
  - **核心机制**（审查时必须理解）：
    - 后端 Python `Enum` 或字符串常量定义的状态值，前端必须 1:1 对齐（包括大小写、下划线、空格）
    - 状态值变更（如后端 `paused` 改为 `suspended`）必须同步 grep 前端所有消费点（`types.ts` + 组件 + Hook + Store）并更新
    - 前端禁止用 `as TaskStatus` 强制类型转换绕过 TS 检查（会掩盖类型不匹配 bug）
  - **判断信号**：
    - `grep "status ===" frontend/src/` 发现硬编码字符串字面量（如 `status === 'running'`）而非引用常量 → 视为可疑
    - `types.ts` 中状态联合类型与后端 `domain/<域>.py` 的 `Enum` 成员不一致 → 视为违规
    - 后端新增状态值但前端 `types.ts` 未同步更新 → 视为违规
    - 前端代码含 `as TaskStatus` 强制类型转换 → 视为违规
  - **修复模式**（集中定义 + 引用常量 + 同步更新）：
    ```typescript
    // ✅ types.ts 集中导出，与后端 domain/task.py 的 TaskStatus 严格对齐
    export type TaskStatus = 'active' | 'paused' | 'stopped' | 'completed' | 'failed'
    export const TASK_STATUS_VALUES = ['active', 'paused', 'stopped', 'completed', 'failed'] as const
    // 消费方引用常量，禁止硬编码字符串
    if (task.status === 'completed') { ... }  // ✅ 字面量受联合类型保护
    ```
  - **配置参数**：`status_fields`（需要状态对齐的字段列表，如 `['task.status', 'session.state', 'order.status']`）、`forbid_as_cast`（默认 `true`，禁止 `as TaskStatus` 强制转换）、`sync_check_dirs`（同步检查目录，默认 `['frontend/src/', 'src/xianyu_hunter/domain/']`）在 `config.yaml` 的 `state_enum_align` 节点管理
  - **适用**：所有有状态字段的业务对象（任务/会话/订单/评估）；后端用 Enum 或常量定义状态值的场景
  - **不适用**：纯前端 UI 状态（如 `loading` / `open` / `active`）；无状态机的 CRUD 实体（如配置项）
  - **历史教训**：后端 `task.status` 新增 `suspended` 状态但前端 `types.ts` 仍为 `'active' | 'paused' | 'stopped'`，导致前端收到 `suspended` 状态时 TypeScript 不报错（因为用了 `as TaskStatus` 转换），UI 显示为默认的"未知状态"。修复后 `types.ts` 同步新增 `suspended` + 移除所有 `as TaskStatus` 转换 + grep 所有消费点确认

- 🆕v4.12【强制】**F-REVIEW-INPUT-NUMBER-BOUNDS：InputNumber 边界约束**
  - `<InputNumber>` 组件必须设置 `min` 和 `max` 属性，禁止无边界输入导致 0/负数传入后端触发 ZeroDivisionError 或负数索引导致越界
  - **核心机制**（审查时必须理解）：
    - AntD InputNumber 默认无 min/max，用户可输入任意数值（包括 0、负数、极大值）
    - 后端配置项通常无边界校验（参考 B-REVIEW-CONFIG-VALIDATION），前端必须兜底
    - 0 值传入 `interval / N` 会触发 ZeroDivisionError；负数传入数组索引会导致 undefined
  - **判断信号**：
    - 代码含 `<InputNumber` 但无 `min=` 属性 → 视为违规
    - 代码含 `<InputNumber min={0}` 但实际语义要求 `min={1}`（如间隔时间、重试次数）→ 视为违规
    - 配置项含 `interval` / `count` / `retry` 等数值字段但前端 InputNumber 无边界 → 视为违规
  - **修复模式**：
    ```typescript
    // ✅ 间隔时间类（必须 min=1，禁止 0/负数）
    <InputNumber min={1} max={3600} addonAfter="秒" value={interval} onChange={setInterval} />

    // ✅ 重试次数类（必须 min=0，允许 0 表示不重试）
    <InputNumber min={0} max={10} value={retryCount} onChange={setRetryCount} />

    // ❌ 错误：无 min 边界，用户可输入 0/负数
    // <InputNumber value={interval} onChange={setInterval} />
    ```
  - **配置参数**：`input_number_bounds.required_min`（默认 `true`，必须有 min）、`input_number_bounds.required_max`（默认 `true`，必须有 max）、`input_number_bounds.scenario_min_values`（场景到 min 值的映射，如 `interval → 1`、`retry_count → 0`、`page_size → 1`）在 `config.yaml` 的 `input_number_bounds` 节点管理
  - **适用**：所有 `<InputNumber>` 组件；配置页面数值字段；表单数值输入
  - **不适用**：纯展示型数值（disabled InputNumber）；无业务语义的数值（如 ID 输入，应用其他校验）
  - **历史教训**：配置页 `<InputNumber>` 无 min 边界，用户输入 `ai_suggestion_interval=0`，后端 `asyncio.sleep(interval / 2)` 触发 ZeroDivisionError，任务循环崩溃

- 🆕v4.12【强制】**F-REVIEW-NULL-SEMANTICS：null/undefined/空字符串语义区分**
  - TypeScript 类型必须明确区分 `null`（显式空值）、`undefined`（未定义）、`""`（空字符串）三种语义，**禁止** `value: string` 实际可能为 null 的类型欺骗，**禁止** `value: string | null` 但代码用 `if (value)` 同时判断三种语义
  - **核心机制**（审查时必须理解）：
    - `null`：显式表示"无值"（后端返回 null）
    - `undefined`：变量未初始化或属性不存在
    - `""`：空字符串（用户主动输入空）
    - 后端 JSON 返回 `null` → 前端解析为 `null`（非 undefined）；API 字段缺失 → 前端为 `undefined`
    - `if (value)` 同时判断三种语义会导致逻辑混乱（如 `""` 被视为 falsy 但实际是有效输入）
  - **判断信号**：
    - 类型声明 `value: string` 但后端 API 可能返回 `null` → 视为违规（应为 `value: string | null`）
    - 代码含 `if (value)` 判断 string 类型 → 必须明确区分 `value === null` / `value === undefined` / `value === ""`
    - 代码含 `value ?? defaultValue` 但 `""` 应保留而非替换为默认值 → 视为违规（应用 `value ?? defaultValue` 仅在 null/undefined 时替换，""保留）
  - **修复模式**：
    ```typescript
    // ✅ 类型明确区分三种语义
    type TaskStatus = {
      name: string                    // 必有，非空字符串
      description: string | null      // 可能为 null（后端显式返回 null）
      deletedAt: string | null        // null 表示未删除
      parentTaskId?: string           // 可选属性，未传时为 undefined
    }

    // ✅ 判断时明确区分
    if (description === null) {
      // 后端显式返回 null，表示"无描述"
      return '无描述'
    }
    if (description === '') {
      // 空字符串，用户主动输入空
      return '（空）'
    }
    return description

    // ❌ 错误：if (value) 同时判断三种语义
    // if (description) { return description }
    // return '无描述'  // "" 也被显示为"无描述"，语义错误
    ```
  - **配置参数**：`null_semantics.strict_mode`（默认 `true`，严格区分三种语义）、`null_semantics.forbidden_union_types`（禁止的联合类型列表，如 `["string | null | undefined"]` 应用 `string | null` + 可选属性）、`null_semantics.if_check_pattern`（检测 `if (value)` 同时判断 string 类型的模式）在 `config.yaml` 的 `null_semantics` 节点管理
  - **适用**：所有 TypeScript 类型声明；后端 API 返回字段的类型定义；表单字段的类型与判断逻辑
  - **不适用**：纯前端计算字段（无 null 语义）；布尔类型（true/false 已明确）
  - **历史教训**：API 返回 `parentTaskId: null` 但前端类型声明为 `parentTaskId?: string`，代码用 `if (task.parentTaskId)` 判断导致 null 被视为 falsy 与 undefined 行为一致，但实际语义不同（null 表示"曾有父任务但已解除" vs undefined 表示"从未有父任务"）

- 🆕v4.25【建议】**F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY：默认值操作符一致性检查**
  - 维度：4 TypeScript 严格规范
  - 严重等级：info
  - **检查点**：默认值场景是否统一使用 `??` 而非 `||`
  - **判定标准**：InputNumber/Select 的 `onChange` 默认值必须用 `??`（nullish coalescing）。`||` 会将 `0`/`''`/`false` 也视为 falsy，可能导致意外行为（如 qps=0 被替换为默认值 1）。只有需要同时过滤 `0`/`''`/`false` 的场景才允许用 `||`
  - **检查范围**：所有 `onChange` 中的默认值表达式、函数参数默认值、变量初始化
  - **核心机制**（审查时必须理解）：
    - `??` 仅在左侧为 `null`/`undefined` 时返回右侧值（语义清晰：缺失时给默认）
    - `||` 在左侧为任意 falsy 值（`null`/`undefined`/`0`/`''`/`false`/`NaN`）时返回右侧值（语义模糊：可能误伤合法的 0/''/false）
    - 数值类字段（qps、interval、timeout、retryCount）的 `0` 是合法值，不能用 `||` 替换为默认值
    - 字符串类字段（label、description）的 `''` 是合法值（用户主动清空），不能用 `||` 替换为默认值
    - 布尔类字段（enabled、silent）的 `false` 是合法值，不能用 `||` 替换为默认值
  - **判断信号**（grep 检测）：
    - `grep -nE "onChange=\{\(v\) => .* \|\| " frontend/src/pages/**/*.tsx` 命中 → 检查是否应改为 `??`
    - `grep -nE "value \|\| [0-9]+" frontend/src/pages/**/*.tsx` 命中 → 数值默认值场景必查
    - `grep -nE "const \w+ = \w+ \|\| '" frontend/src/pages/**/*.tsx` 命中 → 字符串默认值场景必查
    - 用户反馈"qps=0 无法保存，被强制改为 1" → 必查 `||` 误用
  - **修复模式**：
    ```typescript
    // ✅ 正确：数值默认值用 ??，0 是合法值
    <InputNumber onChange={(v) => update({ qps: v ?? 1 })} />

    // ❌ 错误：用 || 会把 0 也视为 falsy，qps=0 被替换为 1
    <InputNumber onChange={(v) => update({ qps: v || 1 })} />

    // ✅ 正确：字符串默认值用 ??，'' 是合法值（用户主动清空）
    const label = formData.label ?? '默认标签'

    // ❌ 错误：用 || 会把 '' 也视为 falsy，用户清空后被强制改回默认值
    const label = formData.label || '默认标签'

    // ✅ 例外：需要同时过滤 0/''/false 时允许用 ||
    const displayName = user.nickname || user.username || '匿名'  // 空字符串视为"未设置"
    ```
  - **配置参数**：`default_operator` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `preferred_operator`（默认 `"??"`，推荐使用的默认值操作符）
    - `logical_or_exceptions`（默认 `["displayName = nickname || username", "fallback chain"]`，允许使用 `||` 的场景白名单）
    - `detection_patterns`（默认 `["onChange={(v) => ... || ", "value || 0", "value || ''"]`，触发检查的代码模式）
    - `forbidden_in_numeric_context`（默认 `true`，数值类字段禁止用 `||`）
    - `forbidden_in_string_context`（默认 `true`，字符串类字段禁止用 `||`）
    - `forbidden_in_boolean_context`（默认 `true`，布尔类字段禁止用 `||`）
  - **适用场景**：所有提供默认值的表达式（onChange 默认值、变量初始化、函数参数默认值、对象属性默认值）
  - **不适用场景**：需要同时过滤 `0`/`''`/`false` 的场景（如空字符串转默认值的 fallback 链、用户昵称缺失时回退到用户名）；布尔条件判断（`if (a || b)` 是逻辑或，不是默认值）；React 组件条件渲染（`{a || <Fallback/>}` 是逻辑或渲染）
  - **历史教训**：任务级配置覆盖功能开发时，`InputNumber` 的 `onChange` 用 `v || 1`，导致用户输入 0 时被强制改为 1（qps=0 是合法值，表示"不限制速率"）。修复方式：改为 `v ?? 1`，仅在 v 为 null/undefined（用户未输入）时给默认值 1
  - **对应后端原则**：后端 Python 使用 `or` 时同样存在类似问题（`0`/`''`/`False` 被 falsy），详见 `xianyu-backend-code-review` 的 `B-REVIEW-DEFAULT-OPERATOR`（如有）

### 5. AntD 5 主题规范 🆕v2.0

- 【强制】使用 Ant Design 5.21+ + `ConfigProvider` 主题化
- 【强制】基础 token 包含 `colorPrimary: '#FF6200'`（闲鱼品牌橙）、`borderRadius: 8`
- 【强制】暗色主题用 `theme.darkAlgorithm`，亮色用 `theme.defaultAlgorithm`
- 【强制】`ConfigProvider` 必须在 `BrowserRouter` 外层（让独立路由如 `/login` 也能切换主题）
- 【强制】`theme.useToken()` 在 ConfigProvider 内部消费
- 【强制】组件级主题覆盖（如 `Table.rowHoverBg`）需响应 `isDark` 状态
- 【强制】**交互元素颜色对比度**：可点击的文字、图标、提示用 `colorPrimary`（即 `activeColor`），确保对比度
- 【禁止】交互元素文字用 `colorBorder`（对比度不足，浅色/深色主题下均难辨识）
- 【推荐】装饰性元素（边框、背景、分隔线）可用 `colorBorder`，交互元素不可
- 🆕v4.8【强制】**F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE：AntD 主题 token 动态覆盖模式**
  - 项目支持暗色主题（`theme.darkAlgorithm`）时，`baseTheme.components.<Component>.<token>` 中**显式指定**的主题相关 token（token 名含 `Color` / `Bg` / `Border` / `Hover` / `Active` / `Focus` 后缀）必须根据 `isDark` 状态在能读取 `useTheme()` 的组件（通常是 `ThemedRoot`）内**动态覆盖**，**禁止**依赖 `darkAlgorithm` 自动重算或 `index.css` 中的 `--ant-*` CSS 变量
  - **核心机制**（审查时必须理解）：
    - antd v5 的 `darkAlgorithm` **仅重算未指定的 token**，显式指定的 token 会被原样继承 → 这是 `baseTheme` 中显式指定的亮色值在暗色主题下失效的根因
    - antd v5 的 `cssVar` 模式**默认未启用**，手动在 `index.css` 中写的 `--ant-*` CSS 变量不被组件引用，是死代码 → 不能依赖 CSS 变量覆盖 token，必须改 `ConfigProvider`
  - **判断信号**：
    - `grep "components\\." main.tsx` 发现 `baseTheme.components.<Component>.<token>: '<value>'` 显式指定了主题相关 token（token 名含 `Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus` 后缀）
    - 项目使用 `algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm`（支持暗色主题）
    - 该 token 在 `ThemedRoot` 内**未根据 `isDark` 动态覆盖**（直接 spread `baseTheme` 后未覆盖 `components.<Component>.<token>`）→ 视为违规
    - `index.css` 中存在 `--ant-*` CSS 变量定义（`grep "\\-\\-ant-" index.css`）→ 视为可疑死代码，需确认是否启用 `cssVar` 模式，未启用则清理
  - **修复模式**（在 `ThemedRoot` 内 spread `baseTheme` 后动态覆盖）：
    ```typescript
    function ThemedRoot() {
      const { isDark } = useTheme()
      return (
        <ConfigProvider
          theme={{
            ...baseTheme,
            algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
            components: {
              ...baseTheme.components,
              Table: {
                ...baseTheme.components.Table,
                // darkAlgorithm 不会重算显式指定的 token，故必须在此处动态覆盖
                // 暗色用品牌色淡橙透明叠加，与卡片背景 #1f1f1f 形成明显对比且与亮色 #fff7f0 调性一致
                rowHoverBg: isDark ? 'rgba(255, 98, 0, 0.08)' : '#fff7f0',
              },
            },
          }}
        >
          <BrowserRouter basename="/app">
            <App />
          </BrowserRouter>
        </ConfigProvider>
      )
    }
    ```
  - **暗色值选择原则**（与品牌色 `#FF6200` 保持视觉一致性，参数在 `config.yaml` 的 `antd_theme_override` 节点管理）：
    - `Hover` / `Active` 状态色：优先用「品牌色 + 低透明度」叠加（如 `rgba(255, 98, 0, 0.08)`），避免硬编码纯色或过深色
    - 背景色（`Bg` 后缀）：用暗色阶梯色（如 `#1f1f1f` / `#141414`）
    - 文字色（`Color` 后缀）：用 `rgba(255, 255, 255, 0.88)` 或 `#e0e0e0`
    - 边框色（`Border` 后缀）：用 `rgba(255, 255, 255, 0.15)` 等半透明白
  - **注释要求**（注释必须解释「为什么」而非「做什么」，参考用户编程原则）：
    1. 说明 `darkAlgorithm` 不会重算显式 token（避免后续维护者误以为会自动适配）
    2. 说明 WCAG 对比度计算（暗色文字与 hover 背景的对比度需满足 AA 级 ≥ 4.5:1）
    3. 说明品牌色一致性（暗色值与亮色值在视觉调性上保持一致，如都是淡橙调）
  - **配置参数**：`theme_token_whitelist`（主题相关 token 名称后缀白名单：`Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus`）、`dark_value_strategy`（暗色值生成策略：`hover_active=brand_overlay` / `background=dark_step` / `text=white_alpha`）、`brand_color`（默认 `#FF6200`）、`brand_overlay_alpha`（默认 `0.08`）、`wcag_level`（默认 `AA`）、`cssvar_enabled`（默认 `false`，用于判断 `--ant-*` 变量是否为死代码）在 `config.yaml` 的 `antd_theme_override` 节点管理
  - **诊断流程**（出现「暗色主题下文字看不见/对比度低」类问题时执行）：
    1. `grep "components\\." main.tsx` 扫描所有显式指定的 token
    2. 逐个检查 token 名是否含主题相关后缀（`Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus`）
    3. 对每个主题相关 token，验证是否响应了 `isDark` 动态切换
    4. 若未响应 → 判定为违规，按修复模式动态覆盖
    5. 顺手 `grep "\\-\\-ant-" index.css` 检查是否有死代码 CSS 变量，确认后清理
  - **适用**：AntD 5.x 项目 + 多主题支持（`darkAlgorithm` / `defaultAlgorithm` 切换）+ `baseTheme.components.<Component>.<token>` 显式指定主题相关 token 的场景；WCAG 可访问性合规场景
  - **不适用**：未启用多主题的项目（仅默认亮色）；antd v4 及以下（主题机制不同）；启用了 antd v5 `cssVar: true` 的项目（CSS 变量会生效，可优先用 CSS 变量方案）；非 antd UI 库；与主题无关的 token（`borderRadius`/`fontSize`/`lineHeight` 等 `darkAlgorithm` 会自动适配）
  - **历史教训**：`baseTheme.components.Table.rowHoverBg` 显式指定为 `#fff7f0`（接近白色的淡橙），暗色主题下被原样继承，与暗色文字 `rgba(255, 255, 255, 0.88)≈#e0e0e0`（也接近白色）对比度近乎为零，hover 时文字几乎看不见。同时 `index.css` 中残留的 `--ant-table-row-hover-bg: #262626` 是死代码（未启用 cssVar 模式，不被组件引用）误导了初版诊断。修复后在 `ThemedRoot` 内根据 `isDark` 动态覆盖为 `rgba(255, 98, 0, 0.08)`

```typescript
// ✅ 推荐：ConfigProvider 在 BrowserRouter 外层
// 注意：baseTheme 中显式指定的主题相关 token（含 Color/Bg/Border/Hover/Active/Focus 后缀）
// 必须在 ThemedRoot 内根据 isDark 动态覆盖（darkAlgorithm 不会重算显式 token）
const baseTheme = {
  token: { colorPrimary: '#FF6200', borderRadius: 8 },
  components: {
    Table: { rowHoverBg: '#fff7f0' },  // 亮色值，暗色需在 ThemedRoot 动态覆盖
  },
}

function ThemedRoot() {
  const { isDark } = useTheme()
  return (
    <ConfigProvider
      theme={{
        ...baseTheme,
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        components: {
          ...baseTheme.components,
          Table: {
            ...baseTheme.components.Table,
            rowHoverBg: isDark ? 'rgba(255, 98, 0, 0.08)' : baseTheme.components.Table.rowHoverBg,
          },
        },
      }}
    >
      <BrowserRouter basename="/app">
        <App />
      </BrowserRouter>
    </ConfigProvider>
  )
}
```

### 6. Zustand 状态管理 🆕v2.0

- 【强制】使用 Zustand 4.5（轻量状态管理）
- 【强制】`persist` 中间件 + `partialize` 只存必要字段（过滤 ReactNode 等不可序列化字段）
- 【强制】store 是纯逻辑层（不感知路由库）
- 【强制】`_navigator` 由组件通过 `useNavigate` 注入，不直接依赖 `react-router-dom`
- 【强制】防抖持久化（300ms）
- 【强制】`hydrate()` 恢复时丢弃失效 path
- 【推荐】`replacedHistory` 回收栈最多 5 条 FIFO
- 【强制】`openSheet()` 四分支决策：
  1. `activateExistingSheet`：已存在则激活
  2. `performCircularReplace`：达到 maxSheets 上限时循环替换
  3. `replaceMobileActiveSheet`：移动端替换当前活动
  4. `createNewSheet`：创建新页签
- 【强制】**状态变更操作一致性**：每个状态变更函数必须同步更新所有相关字段
  - `activateSheet` 激活最小化 sheet 时必须同时设 `minimized: false`
  - `closeSheet` 关闭激活项时必须同步切换 `activeId` 到相邻项
  - `minimizeSheet` 最小化激活项时必须同步切换 `activeId` 到下一个非最小化项
  - 检查方法：列出操作影响的所有字段，确认全部同步更新
- 🆕v4.6【强制】**F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND：多源状态同步统一入口（前端侧）**
  - 前端调用同一后端写入接口的不同代码路径时，状态更新必须统一通过单一 `updateState` / `refetchState` 函数而非各路径独立更新
  - **判断信号**：
    - 多个组件 / Hook 各自调用后端 GET 接口获取同一份状态（如 `/cookies/layers` / `/api/auth/me` / `/api/about`）
    - 各组件独立 setState 但缺少统一 refetch 入口
    - 一个组件更新状态后，其他依赖同一状态的组件不会自动刷新（需要手动刷新页面）
  - **修复模式**：
    - 抽取 `useXxxState()` Hook + 内部 `refetch()` 方法 + 写入路径统一调用 `refetch()`
    - 复杂场景用 Zustand 集中管理（`setXxxState(newData)`），写入路径统一 `setXxxState`
    - **禁止**每个组件独立 `useEffect(() => fetch(...), [])` 重复拉取
  - **关键约束**：写入路径调用 refetch 后，**禁止**再独立 setState 旧值（避免回退）；refetch 失败应保留旧状态并 `message.warning`
  - **配置参数**：`unified_state_hooks`（统一状态 Hook 列表）、`write_entry_paths`（需要触发 refetch 的写入路径）在 `config.yaml` 的 `state_sync_frontend` 节点管理
  - **适用**：后端有"主数据源"概念 + 多入口更新同一份状态 + 前端需要展示最新状态
  - **不适用**：纯客户端状态（localStorage 独占）、只读状态（一次性拉取）
  - **历史教训**：后端 `/cookies/layers` 端点修复统一同步入口后，前端若仍用 `useEffect` 在各组件独立调用 + 不同步 refetch，会出现"某些页面显示失效、另一些页面显示有效"的不一致现象。统一通过 `useCookieLayersStore` 集中管理 + 各写入路径 refetch 后彻底一致
- 🆕v4.11【强制】**F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY：前端缓存与后端状态机一致性**
  - 同一业务目标（如"刷新会话" / "更新任务状态"）有 ≥ 2 条链路（API 路由 + WebSocket 推送 + 定时任务 + 手动操作）触发同一状态变更时，前端必须通过**统一 refetch 入口**刷新缓存，**禁止**各链路独立 `setState` 导致缓存不一致
  - **核心机制**（审查时必须理解）：
    - 后端状态机有白名单转换规则（B-REVIEW-STATE-MACHINE-WHITELIST），前端缓存必须与后端状态机保持一致
    - 多链路触发同一状态变更时（如 API 调用 + SSE 推送 + 定时轮询），若各链路独立 `setState`，会出现"页面 A 显示新状态、页面 B 显示旧状态"的不一致
    - 前端缓存（Zustand store / useState / useRef）必须通过统一 `refetch()` 入口从后端拉取最新状态，而非各链路独立推断
  - **判断信号**：
    - 多个组件 / Hook 各自调用后端 GET 接口获取同一份状态 + 各自 `setState` → 视为违规
    - API 调用成功后前端 `setState(newStatus)` 但未触发其他依赖同一状态的组件刷新 → 视为违规
    - SSE 推送状态变更但前端只更新当前组件 `setState` 未刷新全局缓存 → 视为违规
    - 定时轮询拉取状态后前端 `setState` 与 API 调用路径的 `setState` 逻辑不一致 → 视为违规
  - **修复模式**（统一 refetch 入口 + 集中状态管理）：
    ```typescript
    // ✅ 抽取 useXxxState() Hook + 内部 refetch() + 多链路统一调用 refetch()
    function useTaskState() {
      const [task, setTask] = useState<Task | null>(null)
      const refetch = useCallback(async (taskId: number) => {
        const data = await taskApi.get(taskId)
        setTask(data)  // 统一 setState 入口
      }, [])
      return { task, refetch, setTask }
    }
    // API 调用路径
    const handleControl = async (action) => {
      await taskApi.control(taskId, action)
      await refetch(taskId)  // ✅ 统一 refetch
    }
    // SSE 推送路径
    useEffect(() => {
      const es = new EventSource(...)
      es.onmessage = (e) => {
        const data = JSON.parse(e.data)
        if (data.task_id === taskId) refetch(taskId)  // ✅ 统一 refetch，禁止独立 setState
      }
    }, [taskId, refetch])
    ```
  - **关键约束**：
    - 多链路触发同一状态变更时，**必须**调用统一 `refetch()` 从后端拉取最新状态，**禁止**各链路独立 `setState` 推断新状态
    - `refetch()` 失败应保留旧状态并 `message.warning`，**禁止**清空缓存
    - SSE 推送 + 定时轮询 + API 调用三链路必须共享同一 `refetch()` 入口
  - **配置参数**：`unified_refetch_hooks`（统一 refetch Hook 列表）、`multi_link_state_fields`（多链路状态字段列表，如 `['task.status', 'session.state']`）、`forbid_independent_setstate`（默认 `true`，多链路场景禁止独立 setState）在 `config.yaml` 的 `dual_link_cache_consistency` 节点管理
  - **适用**：同一业务目标有 ≥ 2 条链路触发状态变更的场景（API + SSE + 轮询）；后端有状态机白名单转换的场景
  - **不适用**：单链路状态变更（只有 API 调用，无 SSE/轮询）；纯前端 UI 状态（不依赖后端）；只读状态（无写入操作）
  - **历史教训**：任务详情页通过 API 调用 `taskApi.control(taskId, 'pause')` 后 `setTask({ ...task, status: 'paused' })` 独立推断状态，但任务列表页通过定时轮询拉取最新状态显示 `running`（后端实际状态已为 `paused`，但列表页缓存未刷新），导致"详情页显示已暂停、列表页显示运行中"的不一致。修复后两页统一通过 `useTaskState().refetch(taskId)` 刷新缓存

```typescript
// ✅ 推荐：persist + partialize
export const useSheetStore = create<SheetState>()(
  persist(
    (set, get) => ({
      sheets: [],
      openSheet: (path, title, icon) => { ... },
    }),
    {
      name: 'sheet-storage',
      partialize: (state) => ({ /* 只存必要字段，过滤 ReactNode */ }),
    }
  )
)
```

### 7. API 调用规范 🆕v2.0

- 【强制】使用 axios 单例 + 拦截器（`frontend/src/api/client.ts`）
- 【强制】`baseURL: '/api'` + `withCredentials: true`（**硬约束**：所有请求携带 cookie 通过后端认证）
- 【强制】请求拦截器附加 `Authorization: Bearer <token>`
- 【强制】响应拦截器 401 防抖跳转（`isRedirecting` 标志位防重复跳转）
- 【强制】业务 API 模块导出 `<域>Api` 对象（**禁止**默认导出）
- 【强制】API 统一出口 `frontend/src/api/index.ts`，新增 API 归入子模块
- 【强制】SSE 流式请求用 `fetch + ReadableStream`（axios 不支持流式）
- 【强制】SSE 请求必须包含 `credentials: 'include'`
- 【强制】错误抛 axios 兼容格式：`Object.assign(new Error(msg), { response: { status, data } })`

```typescript
// ✅ 推荐：业务 API 模块导出对象
export const taskApi = {
  list: () => client.get('/tasks'),
  get: (id: number) => client.get(`/tasks/${id}`),
  create: (data: TaskCreate) => client.post('/tasks', data),
  control: (id: number, action: string) => client.post(`/tasks/${id}/control`, { action }),
}

// ✅ 推荐：SSE 用 fetch + ReadableStream
live: async () => {
  const response = await fetch('/api/tasks/live', {
    credentials: 'include',  // 【硬约束】
  })
  const reader = response.body!.getReader()
  // ... 解析 SSE 事件
}
```

- 🆕v4.5【强制】**F-REVIEW-CONFIG-LINKAGE：配置全链路生效验证（前端侧）**
  - 前端配置项（如搜索间隔、防抖间隔、排序方式）从定义到消费必须全链路追踪，**禁止**只在配置页设置但不传递给后端 API
  - **判断信号**：前端配置页有某配置项 → 但对应的 API 请求参数中不包含该字段 → 配置无效
  - **检查方法**：从前端配置页表单 → 提交 API → 后端 config.yaml → 后端 Config 类 → 后端方法参数 → 最终 URL/SQL，确认每层都读取并传递
  - **适用**：所有前端可配置的参数（搜索参数、间隔、阈值），尤其是新增配置项后
  - **不适用**：前端纯 UI 配置（如主题色、页签数量）
  - **历史教训**：前端配置页显示"排序方式：默认综合"，用户可以设置排序方式，但后端 `build_search_url` 不支持 sort_type 参数，搜索 URL 中从不包含 `&sortType=...`。前端"搜索间隔"文案也混淆了"操作延迟"与"任务循环间隔"两个概念
- 🆕v4.7【强制】**F-REVIEW-FILTER-SCENARIO-FRONTEND：过滤逻辑场景区分（前端侧）**
  - 前端调用后端查询接口时，必须按使用场景显式传递场景标志（如 `include_failed` / `include_deleted`），**禁止**所有调用点使用默认值导致展示页看不到完整数据
  - **判断信号**：前端调用 `list_orders` / `list_tasks` 等查询接口时 → 检查是否传递 `include_failed` 参数 → 展示历史场景（评估明细页、历史记录页）必须传 `True` → 操作判断场景（抢单按钮、状态判断）传 `False` 或默认值
  - **修复模式**：识别接口的所有前端调用点 → 按场景分类（展示历史 vs 操作判断）→ 展示历史场景显式传 `include_failed: true` → 操作判断场景显式传 `include_failed: false` → 添加注释说明为何该场景需要/不需要失败数据
  - **配置参数**：`scenario_flag_field`（默认 `include_failed`）、`display_history_routes`（展示历史场景路由列表）、`operation_judge_routes`（操作判断场景路由列表）在 `config.yaml` 的 `filter_scenario_frontend` 节点管理
  - **关键约束**：
    - 展示历史场景**必须显式传 `True`**，不依赖后端默认值（后端默认安全为 `False`）
    - 前端调用点必须有注释说明为何该场景需要/不需要失败数据
    - 新增查询接口调用点时，必须评估属于哪种场景
  - **适用**：调用后端 `list_*` / `get_*` 查询接口的所有前端代码路径，尤其是订单/任务/日志类查询
  - **不适用**：纯前端筛选（如 Table 组件的 filter）、单一场景的查询（如报表统计只看成功）
  - **历史教训**：评估明细页调用 `list_orders_by_item_ids` 时未传 `include_failed`，后端默认跳过 failed 订单，导致用户点击抢单失败后刷新页面看到 "—"，误以为没下过单而反复触发抢单。修复后评估明细页显式传 `include_failed: true`
- 🆕v4.10【强制】**F-REVIEW-FILTER-VISIBILITY：过滤结果可见性（前端侧）**
  - 后端返回 `filter_summary` 时前端必须实现三态提示策略 + "查看被过滤结果"入口，**禁止**只显示"查询完成"不暴露过滤过程
  - **核心机制**（审查时必须理解）：
    - 后端过滤链（keyword/price/publish_days/自定义）会输出 `filter_summary` 含 `raw`/各阶段 `*_skipped`/`final_total`/`filtered_out` 详情
    - 前端若只看 `final_total` 不展示过滤过程，用户无法判断"无结果"是搜索无果还是被过滤掉，反复调整搜索词无果
    - TypeScript 类型必须显式声明 `filter_summary?: LiveFilterSummary`，**禁止**用 `as { filter_summary?: ... }` 强制类型转换绕过 TS 检查（会掩盖类型不匹配 bug）
  - **判断信号**：
    - 前端代码含 `(res as { filter_summary?: ... })` 强制类型转换 → 视为违规
    - 实时搜索/列表查询结果 `final_total == 0` 但前端只显示"查询完成"无任何过滤提示 → 视为违规
    - 后端返回 `filtered_out` 非空但前端无"查看被过滤结果"入口 → 视为违规
    - `grep "filter_summary" frontend/src/` 发现类型定义或消费逻辑缺失 → 视为违规
  - **修复模式**（三态提示 + 按钮入口 + Modal 详情）：
    ```typescript
    // ✅ API 类型显式声明
    export interface LiveFilterSummary {
      raw: number; formatted: number;
      keyword_skipped: number; price_skipped: number; publish_days_skipped: number;
      final_total: number; final_items: number; final_sellers: number;
      filtered_out: LiveFilteredItem[];
    }
    export interface LiveFilteredItem {
      link_type: string; link_key: string;
      display?: Partial<TaskLink['display']> & Record<string, any>;
      filter_reason: 'keyword' | 'price' | 'publish_days';
      filter_detail: string;
    }
    // live() 返回类型显式声明 filter_summary
    async function live(): Promise<{ items: TaskLink[]; filter_summary?: LiveFilterSummary; ... }>

    // ✅ 三态提示策略
    const fs = res.filter_summary  // 类型已在 live() 声明，无需 as 转换
    setLiveFilterSummary(fs || null)
    const itemCount = res.items?.length || 0
    if (itemCount > 0) {
      message.success(`实时查询完成，获取 ${itemCount} 条`)
    } else if (fs && fs.raw > 0) {
      // warning 必须列出各过滤原因计数
      const reasons: string[] = []
      if (fs.keyword_skipped) reasons.push(`关键词 ${fs.keyword_skipped}`)
      if (fs.price_skipped) reasons.push(`价格 ${fs.price_skipped}`)
      if (fs.publish_days_skipped) reasons.push(`发布时间 ${fs.publish_days_skipped}`)
      message.warning(`搜索到 ${fs.raw} 条，但全部被过滤条件筛掉（${reasons.join('、') || '未知原因'}），请调整任务过滤配置`)
    } else {
      message.info('实时查询完成，未找到匹配商品')
    }

    // ✅ "查看被过滤结果"按钮 + Modal（仅 filtered_out 非空时显示）
    {liveFilterSummary && liveFilterSummary.filtered_out.length > 0 && (
      <Button onClick={() => setFilteredModalOpen(true)}>
        查看被过滤的 {liveFilterSummary.filtered_out.length} 条结果
      </Button>
    )}
    <Modal open={filteredModalOpen} onCancel={() => setFilteredModalOpen(false)}>
      <Alert message={`过滤链路：原始 ${fs.raw} → 关键词 ${fs.keyword_skipped} → 价格 ${fs.price_skipped} → 发布时间 ${fs.publish_days_skipped} → 最终 ${fs.final_total}`} />
      <Table dataSource={fs.filtered_out} columns={[
        { title: '商品', dataIndex: 'display' },
        { title: '过滤原因', dataIndex: 'filter_reason', render: (v) => <Tag>{v}</Tag> },
        { title: '详情', dataIndex: 'filter_detail' },
      ]} />
    </Modal>
    ```
  - **三态判定阈值**（参数在 `config.yaml` 的 `filter_visibility` 节点管理）：
    - `success`：`raw >= success_raw_min`（默认 1）且 `final_total >= success_final_min`（默认 1）
    - `warning`：`raw >= warning_raw_min`（默认 1）且 `final_total <= warning_final_max`（默认 0）
    - `info`：`raw <= info_raw_max`（默认 0）
  - **配置参数**：`filter_visibility.three_state_thresholds`（三态判定阈值，如上）、`filter_visibility.modal_required_min_items`（默认 1，filtered_out 长度 ≥ 此值时必须提供 Modal 入口）、`filter_visibility.filter_reason_labels`（过滤原因中文标签映射，如 `{ keyword: "关键词", price: "价格", publish_days: "发布时间" }`）、`filter_visibility.forbid_as_cast`（默认 `true`，禁止 `as { filter_summary?: ... }` 强制类型转换）在 `config.yaml` 的 `filter_visibility` 节点管理
  - **诊断流程**（出现"实时搜索无结果但不知原因"类问题时执行）：
    1. `grep "filter_summary" frontend/src/` 扫描类型定义与消费逻辑
    2. 检查 API 返回类型是否显式声明 `filter_summary?` 字段
    3. 检查消费代码是否含 `as { filter_summary?: ... }` 强制转换（违规信号）
    4. 检查 `final_total == 0` 分支是否实现三态提示
    5. 检查 `filtered_out` 非空时是否提供"查看被过滤结果"按钮+Modal
  - **适用**：所有调用后端含过滤链路查询接口（实时搜索/历史查询/列表过滤）的前端代码；后端返回 `filter_summary` 结构的场景
  - **不适用**：无过滤的纯 CRUD 接口；前端纯前端过滤（如 Table 自带筛选）；过滤结果不影响用户体验的场景（如后台日志查询）
  - **历史教训**：实时搜索接口 `final_total=0`（keyword 过滤 32 + price 过滤 27 = 0 最终）但前端只显示"实时查询完成"，用户无法判断是搜索无结果还是被过滤掉，反复调整搜索词无果。且 `task.ts` 中 `live()` 返回类型未声明 `filter_summary`，前端用 `(res as { filter_summary?: LiveFilterSummary })` 强制转换绕过 TS 检查。修复后 `live()` 显式声明返回类型 + 三态提示 + "查看被过滤结果"Modal + api/index.ts re-export 新类型

- 🆕v4.12【强制】**F-REVIEW-BATCH-OPERATION：批量操作完整流程**
  - 批量操作（一键启动/停止/删除所有任务等）必须实现完整流程：`Modal.confirm` 确认 + loading 状态 + success/error message 反馈 + 异常处理 + 状态刷新，**禁止**只调 API 不反馈或只反馈不刷新
  - **核心机制**（审查时必须理解）：
    - 批量操作影响多个资源，必须用户显式确认（Modal.confirm）防止误触
    - 操作期间必须显示 loading 状态防止重复点击
    - 操作成功/失败必须明确反馈（message.success/error）
    - 部分失败时必须告知用户跳过数量和失败原因
    - 操作完成后必须刷新状态（loadTasks）确保 UI 与后端一致
  - **判断信号**：
    - 代码含 `taskApi.batchControl` / `Promise.all(ids.map(...))` 等批量调用 → 必须有完整流程
    - 代码含 `<Button onClick={() => taskApi.batchControl(...)}>` 无 Modal.confirm → 视为违规
    - 代码含批量 API 调用但无 loading 状态 → 视为违规
    - 代码含批量 API 调用但无 try/catch → 视为违规
  - **修复模式**：
    ```typescript
    const [startAllLoading, setStartAllLoading] = useState(false)

    const handleStartAll = useCallback(() => {
      // 过滤出需要启动的任务（跳过已运行）
      const toStart = tasks.filter((t) => t.status !== 'running')
      const skipped = tasks.length - toStart.length
      if (toStart.length === 0) {
        message.info(skipped > 0 ? `所有 ${skipped} 个任务已在运行中` : '暂无任务可启动')
        return
      }
      // 确认对话框
      const taskNames = toStart.map((t) => t.name || t.keyword).slice(0, 5).join('、')
      const more = toStart.length > 5 ? ` 等 ${toStart.length} 个任务` : ''
      Modal.confirm({
        title: '确认启动所有任务？',
        content: `将启动 ${toStart.length} 个任务（${taskNames}${more}）` +
          (skipped > 0 ? `，跳过 ${skipped} 个已运行任务` : ''),
        okText: '启动',
        cancelText: '取消',
        onOk: async () => {
          setStartAllLoading(true)
          try {
            await taskApi.batchControl(toStart.map((t) => t.id), 'restart')
            message.success(`已启动 ${toStart.length} 个任务` + (skipped > 0 ? `，跳过 ${skipped} 个` : ''))
            await loadTasks()  // 刷新状态
          } catch (err: unknown) {
            const detail = err instanceof Error ? err.message : String(err)
            message.error(`启动失败: ${detail.slice(0, 100)}`)
          } finally {
            setStartAllLoading(false)
          }
        },
      })
    }, [tasks, loadTasks])

    // ❌ 错误：无确认 + 无 loading + 无反馈
    // const handleStartAll = () => { taskApi.batchControl(tasks.map(t => t.id), 'restart') }
    ```
  - **配置参数**：`batch_operation.required_steps`（默认 `["confirm", "loading", "feedback", "refresh"]`，必须的步骤）、`batch_operation.confirm_component`（默认 `Modal.confirm`）、`batch_operation.max_preview_items`（默认 `5`，确认框中预览的任务名数量上限）、`batch_operation.error_message_max_length`（默认 `100`，错误消息截断长度）在 `config.yaml` 的 `batch_operation` 节点管理
  - **适用**：所有批量操作（一键启动/停止/删除/导出所有任务）；影响多个资源的操作；不可逆操作（删除/归档）
  - **不适用**：单个资源操作（如启动单个任务）；纯查询操作（无副作用）；用户已通过其他方式确认的操作（如表单提交）
  - **历史教训**：`TaskContentMenu` 一键启动按钮直接调 `taskApi.batchControl` 无确认无 loading 无反馈，用户点击后无任何反应以为没生效重复点击，导致同一任务被启动多次

- 🆕v4.20【强制】**F-REVIEW-VERSION-SOURCE-ALIGN：元数据源显示对齐规范**
  - 前端显示构建期元数据（版本号/构建时间/git_sha 等）必须调用**语义对齐**的 API 端点（如 `aboutApi.get()` → `/api/about`），**禁止**将返回 `len(backups)` / `count` / `size` / `length` 等业务计数端点当作版本号使用；新增元数据 API 调用必须通过 `Promise.all` 与既有 API 并行化避免瀑布请求；修复时必须同步清理只 `set` 不 `read` 的死代码 state
  - **核心机制**（审查时必须理解）：
    - 构建期元数据必须有唯一源头（Single Source of Truth），前端只是消费方，不能从同名但语义不同的端点推断
    - 端点命名相似不等于语义对齐：`/api/config/version` 名称含 "version" 但实际返回 `len(backups)`，受 `BACKUP_KEEP` 上限影响会卡在上限值
    - 显示元数据的组件（`<Statistic>` / `<Tag>` / `<Descriptions.Item>`）必须 grep `value=` 字段来源，确认来自语义对齐 API
    - 新增独立 API 调用必须 `Promise.all` 并行化（与既有 configApi 调用同时发起），避免串行瀑布请求导致加载时间翻倍
    - 修复 bug 时发现只 `set` 不 `read` 的 state（如 `const [, setXxx] = useState(0)`）必须同步清理，避免遗留死代码
  - **判断信号**：
    - `grep "getVersion\\(\\)" frontend/src/` 用于版本号显示 → 视为违规（应改用 `aboutApi.get()`）
    - `grep "Statistic.*title=.*version" frontend/src/` 的 `value=` 字段来自 `length` / `count` / `size` → 视为违规
    - `grep "Tag.*color=.*version" frontend/src/` 的 `children` 字段来自计数端点 → 视为违规
    - `grep "configApi\\.getVersion" frontend/src/` 同时 grep 不到 `aboutApi.get` → 视为违规
    - `const [, setXxx] = useState` 解构出 setter 但无 getter 使用 → 死代码信号
    - 新增 `aboutApi.get()` 调用未与既有 `configApi.getXxx()` `Promise.all` 并行 → 性能违规
  - **修复模式**：
    ```typescript
    // ❌ 错误：getVersion() 实际返回 len(backups)，受 BACKUP_KEEP=10 上限永远卡在 10
    const [version, setVersion] = useState('')
    useEffect(() => {
      configApi.getVersion().then(v => setVersion(String(v)))  // v 是数字 10
    }, [])
    return <Statistic title="version" value={`v${version}`} />  // 永远显示 V10

    // ✅ 正确：调用语义对齐的 /api/about 端点 + Promise.all 并行化
    const [buildInfo, setBuildInfo] = useState<BuildInfo | null>(null)
    const [backups, setBackups] = useState<BackupItem[]>([])

    useEffect(() => {
      // 并行化：aboutApi 提供版本号 + configApi 提供备份数（语义分离）
      Promise.all([aboutApi.get(), configApi.listBackups()])
        .then(([info, bks]) => {
          setBuildInfo(info)
          setBackups(bks)
        })
        .catch(err => message.error(`加载失败: ${err.message}`))
    }, [])

    return (
      <>
        <Statistic title="version" value={`v${buildInfo?.version ?? 'unknown'}`} />
        <Statistic title="backups" value={backups.length} />
      </>
    )

    // ✅ 死代码清理：发现 const [, setConfigVersion] = useState(0) 只 set 不 read → 删除
    ```
  - **配置参数**：`version_source_management` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `forbidden_version_endpoints`（默认 `["/api/config/version"]`，禁止当作版本号使用的端点列表）
    - `forbidden_placeholders`（默认 `["1.0", "0.0.0", "unknown version"]`，禁止作为版本号回退值的占位符）
    - `required_semantic_api`（默认 `"/api/about"`，版本号必须来自的语义对齐 API）
    - `parallel_fetch_required`（默认 `true`，新增元数据 API 调用必须 Promise.all 并行化）
    - `dead_code_cleanup_required`（默认 `true`，修复时必须同步清理只 set 不 read 的 state）
  - **适用**：构建期元数据（版本号/构建时间/git_sha/构建主机）的前端显示；多端点读取同一元数据的场景；前端"版本管理"/"关于"/"系统信息"页面
  - **不适用**：业务数据计数（如备份数/任务数/商品数）；临时调试变量；跨服务边界元数据（应通过专门 API 同步）；核心依赖版本（如 React/AntD 版本，由 package.json 管理）；Pydantic 模型字段（由后端类型系统管理）
  - **历史教训**：版本管理菜单持续显示 "V10"。根因链路：前端 `VersionManager.tsx` 调用 `configApi.getVersion()` 拉取 `/api/config/version`，但该端点实际返回 `len(backups)`，受 `BACKUP_KEEP=10` 上限影响永远卡在 10；同时后端 `export_config` 中残留占位符 `"version": "1.0"`。修复：前端改用 `aboutApi.get()` 调 `/api/about` 拿真实 `__version__`，`Promise.all` 并行化避免瀑布；后端 `_safe_app_version()` 辅助函数替代占位符；同步清理 Dashboard 中 `const [, setConfigVersion] = useState(0)` 死代码

- 🆕v4.22【强制】**F-REVIEW-PWA-CACHE-VERIFY：PWA 缓存验证规范**
  - 维度：13 PWA 配置
  - 检查项：前端功能不可见时必须从源码→构建产物→sw.js 预缓存清单三层验证
  - 强制要求：
    1. `vite-plugin-pwa` 的 `registerType: 'prompt'` 模式检测到新版本仅弹通知不自动刷新，必须实现 `ReloadPrompt` 组件提示用户刷新
    2. 或改用 `registerType: 'autoUpdate'` 自动激活新版本（无需用户确认）
    3. 部署后必须验证 `sw.js` 预缓存清单包含新 chunk 文件名（如 `BatchRefresh-xxx.js`）
    4. 构建产物必须包含新功能标识（如中文文案「执行历史」），用 `Select-String` 或 `grep` 验证
    5. 构建时间必须晚于源码修改时间，确保构建是最新的
    6. 用户反馈「看不到新功能」时，排查顺序：源码 → 构建产物 → sw.js 预缓存清单 → Service Worker 缓存 → 浏览器缓存
  - 配置节点：`pwa_cache_verify`（verify_layers / register_type / prompt_fallback_required / reload_prompt_component / build_time_check）
  - 适用场景：PWA 项目（vite-plugin-pwa/Workbox）部署后用户反馈「看不到新功能」
  - 不适用场景：无 PWA 的传统部署；htmx 服务端渲染；CSR 无 Service Worker
  - 实战案例：批量采集执行历史 Tab2 已在源码和构建产物中正确实现，但用户看不到，原因是 PWA Service Worker 缓存了旧版本 JS 资源，registerType: 'prompt' 模式只弹通知不自动刷新，用户需手动 Ctrl+Shift+R 硬刷新

- 🆕v4.25【强制】**F-REVIEW-THREE-STATE-NULL-SEMANTICS：API 更新接口三态语义检查**
  - 维度：7 API 调用规范
  - 严重等级：warning
  - **检查点**：PATCH/PUT 请求是否正确处理 null 语义
  - **判定标准**：前端发送更新请求时，**清除覆盖字段必须显式传 null（不能省略字段）**，更新字段必须传具体值。**禁止**用"省略字段"代替"传 null"——后端 `exclude_unset=True` 会把省略字段视为"未提供"（保持原值），而 `null` 才是"显式清除覆盖"的语义
  - **检查范围**：所有 `taskApi.update` / `configApi.update` 等 PATCH/PUT 调用
  - **核心机制**（审查时必须理解）：
    - 后端 Pydantic + `exclude_unset=True` 模式下，请求体省略字段 = "未提供" = 保持原值；显式传 `null` = "显式清除覆盖"
    - 前端 `FormData`/payload 构造时，已勾选"恢复默认"或"清除覆盖"的字段必须显式赋 `null`，不能依赖字段省略
    - 后端配合使用 `Optional[T] = None` 但区分"未传"（保持原值）与"传 null"（清除），需要 `model_dump(exclude_unset=True)` 而非 `exclude_none=True`
  - **判断信号**（grep 检测）：
    - `grep -nE "delete formData\[" frontend/src/pages/**/*.tsx` 命中 → 检查是否应改为 `formData[x] = null`
    - `grep -nE "if \(value\) \{ formData\[` frontend/src/pages/**/*.tsx` 命中 → 检查 else 分支是否补 `formData[x] = null`
    - 用户反馈"清除覆盖不生效，覆盖值仍存在" → 必查前端是否省略字段而非传 null
  - **修复模式**：
    ```typescript
    // ✅ 正确：清除覆盖字段显式传 null
    const payload: Partial<TaskConfig> = { search_config: null }  // 显式 null 清除覆盖
    await taskApi.update(taskId, payload)

    // ❌ 错误：省略字段，后端 exclude_unset=True 视为"未提供"，覆盖不会被清除
    const payload: Partial<TaskConfig> = {}
    // search_config 字段被省略，后端不会清除覆盖
    await taskApi.update(taskId, payload)

    // ❌ 错误：用 undefined 也会被 exclude_unset 过滤掉
    const payload = { search_config: undefined }
    await taskApi.update(taskId, payload)
    ```
  - **配置参数**：`api_update_semantics` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `three_state_fields`（默认 `["search_config", "filter_config", "score_override", "notify_config"]`，必须显式传 null 才能清除覆盖的字段列表）
    - `clear_override_fields`（默认 `["search_config"]`，"清除覆盖"语义的字段列表）
    - `detection_signals`（默认 `["delete formData[", "omit field in PATCH", "undefined in PATCH payload"]`，触发检查的代码模式）
    - `forbidden_omit_fields`（默认同 `three_state_fields`，禁止在 PATCH 中省略的字段列表）
  - **适用场景**：所有 PATCH/PUT 接口的可选字段（任务级配置覆盖、用户偏好覆盖、商品级配置覆盖、批量配置覆盖）
  - **不适用场景**：POST 创建接口（所有字段都显式传，不存在"省略 = 保持原值"语义）；GET 查询接口（无写入语义）；DELETE 接口（无字段语义）
  - **历史教训**：任务级配置覆盖功能开发时，前端 FormData 中"清除 search_config 覆盖"操作通过 `delete formData.search_config` 实现，导致后端 `exclude_unset=True` 把该字段视为"未提供"，覆盖未被清除，用户反馈"清除不生效"。修复方式：改为 `formData.search_config = null` 显式传 null，后端识别 null 后调用 `clear_override()` 清除覆盖
  - **对应后端原则**：后端 PATCH/PUT 接口必须用 `model_dump(exclude_unset=True)` 区分"未提供"与"显式 null"，禁止用 `exclude_none=True`（会吞掉 null 语义），详见 `xianyu-backend-code-review` v4.26.0 的 `B-REVIEW-EXCLUDE-UNSET-CHECK` / `B-REVIEW-NOT-NULL-NONE-DEFENSE`

### 8. 路由与懒加载 🆕v2.0

- 【强制】使用 `react-router-dom` 6.26+ + `BrowserRouter basename="/app"`
- 【强制】约 26 条业务路由（`App.tsx`）
- 【强制】所有业务页面用 `lazy(() => lazyRetry(() => import('./pages/<域>')))` 懒加载
- 【强制】`lazyRetry` 包装 chunk 失败重试：`MAX_RETRIES=3`，1s/2s/4s 指数退避
- 【强制】独立路由（不进 MainLayout）：`/login`、`/onboarding`、`/help`、`/about`
- 【强制】双层 ErrorBoundary：`LazyErrorBoundary`（路由级）+ 顶层 ErrorBoundary
- 【强制】路由切换用 `requestAnimationFrame` 重置滚动位置

### 9. SheetWorkspace 多页签系统 🆕v2.0

- 【强制】多页签系统位于 `frontend/src/components/SheetWorkspace/`，6 文件组织
- 【强制】`SheetPreferences` 字段：
  - `maxSheets`: [1, 10]
  - `enableAnimation`: boolean
  - `minimizeInsteadOfClose`: boolean
  - `doubleClickCloseEnabled`: boolean
  - `doubleClickInterval`: [200, 800]
  - `thumbnailMode`: boolean
  - `circularReplaceEnabled`: boolean
- 【强制】`activateSheet` 激活最小化 sheet 时必须同时恢复（`minimized: false`），否则 SheetContent 显示空状态
- 【强制】最小化标识和"恢复"提示文字用 `colorPrimary`（`activeColor`），禁止用 `colorBorder`
- 【强制】页面组件嵌入 SheetContent 时用 `height: 100%`，禁止 `minHeight: 100vh`

### 10. Hooks 设计模式 🆕v2.0

- 【强制】常量提取到模块级（SonarQube S2004）：`MIN_INTERVAL`、`MAX_INTERVAL`、`DEFAULT_INTERVAL`、`MAX_RETRIES`、`RETRY_BASE_MS`、`DEBOUNCE_MS`、`BACKGROUND_SLOWDOWN`
- 【强制】`ref` 持有最新闭包（避免 setInterval 陷阱）：`refreshRef`、`enabledRef`、`pausedRef`、`intervalRef`、`scheduleNextRef`
- 【强制】页面不可见降频：×3（`BACKGROUND_SLOWDOWN`）
- 【强制】防抖：300/400/500ms（按场景）
- 【强制】`requestId` 竞态保护：每次请求生成 requestId，丢弃过期响应
- 🆕v4.0【强制】**搜索场景防抖间隔统一 400ms**（通过配置管理，非硬编码）
- 🆕v4.0【强制】**搜索响应结构统一**：`{ items, total, page, page_size }`，参数命名 `keyword/q, page/offset, page_size/limit`
- 【强制】`mountedRef` 防止卸载后 setState
- 【强制】`refreshingRef` 并发保护
- 【强制】`async/await` 或 `.then().catch()` 错误处理；禁止遗漏 `this` 上下文绑定
- 【强制】每个异步请求有错误处理分支
- 【强制】提交按钮异步期间设 `loading`/`disabled` 防重复提交
- 【强制】**测试环境准备**：antd 组件（Drawer/Grid/Skeleton）测试必须 mock `window.matchMedia`
- 【强制】vitest 测试命令必须加 `--no-isolate`（Node v24 + vitest 4.x worker 启动兼容性）
- 【强制】测试文件扩展名跟随被测文件：组件测试用 `.test.tsx`，Hook/纯逻辑用 `.test.ts`
- 【强制】全局事件监听（`visibilitychange`、`resize`、`scroll` 等）必须在 useEffect 中注册，并在 cleanup 中移除
- 【强制】`visibilitychange` 监听用于：页面不可见时暂停网络连接（SSE/WebSocket），恢复可见时自动重建
- 【推荐】useEffect 中同时管理 SSE 连接和 visibilitychange 监听，确保两者生命周期一致
- 🆕v4.7【强制】**F-REVIEW-ASYNC-FEEDBACK：异步操作用户反馈三态**
  - 前端异步操作（API 请求、文件上传、批量操作）必须实现 loading → success → error 三态用户反馈，**禁止** `.catch(() => {})` 静默吞错误
  - **判断信号**：`await fetch(...)` / `await axios(...)` / `useEffect` 中的异步操作 → 检查是否有 `message.loading` / `setLoading(true)` → 检查成功分支是否有 `message.success` → 检查 catch 分支是否有 `message.error` 或 `notification.error`
  - **修复模式**（三态反馈标准模式）：
    ```typescript
    // ✅ 标准三态反馈模式
    const hide = message.loading('正在采集评估明细...', 0)
    try {
      const result = await fetchEvaluationDetail(itemIds)
      hide()
      message.success(`采集完成，共 ${result.length} 条`)
      setData(result)
    } catch (err) {
      hide()
      message.error(err instanceof Error ? err.message : '采集失败，请稍后重试')
      // 错误状态必须显式设置，不能只靠 catch 不做事
      setError(err instanceof Error ? err.message : '未知错误')
    }
    ```
  - **禁止模式**：
    ```typescript
    // ❌ 静默吞错误
    fetchEvaluationDetail(itemIds).then(setData).catch(() => {})
    // ❌ 只有 loading 没有 success/error 反馈
    setLoading(true)
    const result = await fetchEvaluationDetail(itemIds)
    setData(result)
    setLoading(false)
    ```
  - **配置参数**：`loading_duration`（loading 提示展示时长，默认 0 表示持续到手动关闭）、`success_auto_hide_ms`（成功提示自动关闭时长，默认 3000）、`error_auto_hide_ms`（错误提示自动关闭时长，默认 5000）、`feedback_components`（反馈组件映射，默认 `message`）在 `config.yaml` 的 `async_feedback` 节点管理
  - **关键约束**：
    - loading 提示必须在 await 之前触发，在 finally 或 success/error 分支中关闭
    - 错误信息必须面向用户友好（避免堆栈跟踪、错误码直接展示）
    - 批量操作必须显示进度（如"3/10 完成"）
    - 网络错误与业务错误区分显示（网络错误提示"网络异常"，业务错误显示后端返回的 detail）
  - **适用**：所有前端异步操作（API 请求、文件上传、批量操作、长时间计算）
  - **不适用**：后台同步任务（如 SSE 心跳、定时轮询）、纯展示组件的初始数据加载（可用 Skeleton 占位）
  - **历史教训**：评估明细采集按钮点击后无任何反馈，用户不知道是否在执行；采集失败后页面无变化，用户反复点击导致多次请求。修复后改为 `message.loading` → `message.success/error` 三态反馈
- 🆕v4.9【强制】**F-REVIEW-FREQ-STATS-POLLING：累计统计类 API 定时刷新**
  - 累计统计类 API（频率伪装统计 / 采样器 / 计数器 / 令牌桶 / 健康评分 等"内部状态持续累加"的接口）必须在前端页面通过 `setInterval` **定时刷新**，**禁止**只依赖"页面加载时拉一次"。定时器间隔、清理策略、失败兜底必须在 `config.yaml` 的 `freq_stats_polling` 节点管理，不硬编码
  - **核心机制**（审查时必须理解）：
    - 业务模块（collector / buyer / notifier 等）持续调用后端核心模块（如 `FreqDisguise.record_request`）累加统计
    - 前端 `useEffect` 初始化时只 `fetch` 一次 → 拿到的是某个时刻的快照
    - 用户停留在页面期间，后端统计持续累加但 UI 永远停留在初始值（甚至永远是 0）
    - 表现：用户反馈"统计数据持续为 0 且无变化"，但后端 API 与业务调用方均正确
  - **判断信号**：
    - `grep "loadFreqStats\|loadStats\|fetchStats" <page>.tsx` 发现页面有加载函数
    - `grep "setInterval" <page>.tsx` **没有**对应的 `setInterval` 定时器
    - 累计统计类 API 名称含 `stats` / `metrics` / `count` / `health_score` / `token_bucket` 等关键词
    - 后端核心模块（如 `FreqDisguise` / `MetricsCollector` / `Sampler`）有 `_total_count` / `_history` 等内部状态
  - **修复模式**（在页面 useEffect 中加 `setInterval` + 清理）：
    ```typescript
    useEffect(() => {
      loadAll()
      // 频率伪装统计定时刷新：业务模块持续调用 apply_freq_delay/record_freq_request，
      // 前端需定时拉取才能反映最新请求节奏
      const freqInterval = setInterval(() => {
        loadFreqStats()
      }, POLL_INTERVALS.freqStats)  // 10000ms 来自 config.yaml
      return () => {
        clearInterval(freqInterval)  // 卸载时必须清理
      }
    }, [loadAll])
    ```
  - **关键约束**：
    - **必须清理定时器**：`useEffect` cleanup 中 `clearInterval`，避免组件卸载后定时器仍触发 `setState`（内存泄漏 + 警告）
    - **间隔配置化**：`10000` / `30000` 等间隔值必须来自 `config.yaml` 的 `freq_stats_polling.interval_ms` 或 `POLL_INTERVALS` 常量，禁止在组件内硬编码数字
    - **轮询失败静默**：累计统计轮询失败应 `console.error` 而非 `message.error`（避免用户被频繁弹窗骚扰）
    - **可独立刷新**：每个累计统计 API 可独立设置 `setInterval`，无需等待 `loadAll()`
  - **配置参数**：`enabled`（默认 `true`）、`interval_ms`（默认 `10000`）、`slow_interval_ms`（变化缓慢的统计如 Cookie 层，默认 `30000`）、`fail_silent`（轮询失败是否仅 console 不弹错，默认 `true`）、`applicable_pages`（适用页面列表如 `AntiCrawl` / `Dashboard`）、`exempt_apis`（豁免的 API 列表如已用 SSE 推送的接口）在 `config.yaml` 的 `freq_stats_polling` 节点管理
  - **诊断流程**（用户反馈"统计数据持续为 0 且无变化"时执行）：
    1. 定位页面对应的 `loadXxx` 函数 → 检查页面 useEffect 是否调用了 `loadAll()` 初始化
    2. `grep "setInterval" <page>.tsx` 检查是否有定时刷新
    3. 若无 → 判定为孤岛（前端未轮询）→ 按修复模式增加 `setInterval`
    4. 验证后端 API 端点是否被业务模块持续调用（`grep "apply_freq_delay\|record_request"` 后端）
    5. 三层验证：API 端点存在 ✓ + 业务模块调用 ✓ + 前端轮询 ✓ → 数据应开始累加
  - **适用**：
    - 反爬登录管理页面的频率伪装统计（业务模块持续调用 `apply_freq_delay` / `record_request`）
    - Dashboard 的实时统计（任务数 / 评估数 / 订单数等持续累加指标）
    - 健康检查页面的健康评分（持续变化）
    - 任何后端有"内部状态持续累加"特征的 API
  - **不适用**：
    - 纯客户端状态（localStorage 独占，无后端状态）
    - 只读快照类统计（后端一次性生成数据，无需轮询，如日报表）
    - Chart 库内置轮询（echarts / recharts 已有 setInterval 机制）
    - 已有 SSE 推送的实时数据流（避免与 SSE 重复）
  - **历史教训**：`AntiCrawl` 页面的 `loadFreqStats` 仅在 `useEffect` 初始化时调用一次，**没有 `setInterval` 定时刷新**。后端 `FreqDisguise.record_request` 被 collector/buyer 持续调用累加统计正确，但前端 UI 永远显示初始值（0）。用户反馈"频率伪装统计持续为 0 且无变化"持续数天。修复后在 `useEffect` 中加 `setInterval(loadFreqStats, 10000)` + cleanup `clearInterval`，数据立即开始正常累加

- 🆕v4.12【强制】**F-REVIEW-ASYNC-CONFIG-LOAD：异步配置加载与竞态保护**
  - 使用 `usePersistentState` 等 localStorage 持久化 hook 时，若初始值需从异步 API（如 `configApi.get()`）加载，必须实现双重检查防止竞态：第一次检查 localStorage 是否已有用户偏好，第二次检查在 API 返回后再次确认 localStorage 未被 usePersistentState 防抖写入抢先
  - **核心机制**（审查时必须理解）：
    - `usePersistentState` 同步初始化无法等待异步 API
    - 用户偏好优先级 > 全局配置默认值，不能直接覆盖已有用户偏好
    - 组件卸载后 API 返回仍调 setState 会触发 React 警告（Can't perform a React state update on an unmounted component）
  - **判断信号**：
    - 代码含 `configApi.get().then(cfg => setXxx(cfg.xxx))` 模式 → 必须有 cancelled 标志和双重检查
    - `useEffect` 依赖数组为 `[]` 但调用了异步 API + setState → 必须实现清理函数 `return () => { cancelled = true }`
    - 代码含 `if (localStorage.getItem(KEY) !== null) return` 短路 → 必须在 API then 回调中再次检查
  - **修复模式**：
    ```typescript
    // ✅ 双重检查 + cancelled 标志
    const [autoSearchEnabled, setAutoSearchEnabled] = usePersistentState<boolean>(
      'xh.tasks.autoSearchEnabled',
      false,
    )

    useEffect(() => {
      // 第一次检查：localStorage 已有值（用户偏好优先），不覆盖
      if (localStorage.getItem('xh.tasks.autoSearchEnabled') !== null) return
      let cancelled = false
      configApi.get()
        .then(cfg => {
          if (cancelled) return
          // 第二次检查：防止 usePersistentState 防抖写入抢先
          if (localStorage.getItem('xh.tasks.autoSearchEnabled') !== null) return
          setAutoSearchEnabled(cfg.task_scheduler?.auto_search_enabled ?? false)
        })
        .catch(() => { /* config 加载失败保持默认 false */ })
      return () => { cancelled = true }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])
    ```
  - **配置参数**：`async_config_load.required_double_check`（默认 `true`，必须双重检查 localStorage）、`async_config_load.required_cancelled_flag`（默认 `true`，必须有 cancelled 标志）、`async_config_load.user_preference_priority`（默认 `true`，用户偏好优先于全局配置）、`async_config_load.fallback_default_value`（默认 `false`，config 加载失败时的兜底值）在 `config.yaml` 的 `async_config_load` 节点管理
  - **适用**：所有从异步 API 加载初始值的 usePersistentState/useState 场景；用户偏好与全局配置合并的场景
  - **不适用**：纯同步初始值（直接 useState(initialValue)）；非持久化的 useState；无异步 API 调用的场景
  - **历史教训**：`usePersistentState('xh.tasks.autoSearchEnabled', false)` 直接用 false 初始化，然后 useEffect 异步加载 configApi.get() 设置默认值，但用户已手动关闭开关（localStorage 有 false 值）时被 API 返回的 true 覆盖，导致用户偏好丢失

- 🆕v4.16【强制】**F-REVIEW-ASYNC-RACE-CONDITION：长耗时异步请求 race condition 防护**
  - **判断信号**：`client.post` / `client.get` 调用含 `timeout >= 3000` 参数；或调用方为 LLM/批量类（`aiApi.deepAnalyze` / `aiApi.evaluateCondition` / `evalApi.batchEvaluate`）；用户可触发多次切换商品/任务/对象的 Modal 内异步或列表行按钮异步
  - **强制规则**：任何 > 3s 的异步请求必须用 `useRef` 跟踪最新请求 ID；旧请求的 result/error/loading 三态在 setState 前必须校验 `ref.current === itemId`，不匹配则丢弃；finally 块同样校验，避免提前关闭新请求的 loading
  - **代码模板**：
    ```typescript
    const itemIdRef = useRef('')
    const onXxx = async (itemId: string) => {
      itemIdRef.current = itemId
      setLoading(true); setResult(null)
      try {
        const result = await api.fetch(itemId)
        if (itemIdRef.current !== itemId) return  // 丢弃过期结果
        setResult(result)
      } catch (err) {
        if (itemIdRef.current !== itemId) return  // 丢弃过期错误
        handleError(err)
      } finally {
        if (itemIdRef.current === itemId) setLoading(false)  // 仅最新请求结束 loading
      }
    }
    ```
  - **配置参数**：`async_race_condition` 节点（enabled / threshold_ms / detect_patterns / abort_controller_preferred）
  - **适用场景**：timeout >= 3s 的异步请求 + 用户可触发多次切换商品/任务/对象
  - **不适用场景**：同步请求（< 1s）；一次性请求（页面加载）；用户无法重复触发（如表单提交后禁用按钮）；请求顺序由用户显式控制（如分页加载）
  - 注：`AbortController` 是更优解但需后端支持取消；`useRef` 方案是通用轻量解
- 🆕v4.24【强制】**F-REVIEW-UI-PREFERENCE-PERSISTENCE：用户偏好类 UI 状态持久化强制复用 usePersistentState**
  - 用户偏好类 UI 状态（自动刷新开关、视图模式、列显隐、折叠/展开状态、主题偏好、最近使用列表、记住上次选中项等）必须使用项目既有 `frontend/src/hooks/usePersistentState.ts` 持久化，**禁止**裸 `useState` 存储（判别信号：刷新页面/路由切换后状态丢失即违规）、**禁止**各组件自行实现 `localStorage.getItem/setItem` 逻辑、**禁止**引入第三方持久化库
  - **核心机制**（审查时必须理解）：
    - 项目已有统一封装的 `usePersistentState` hook（位于 `frontend/src/hooks/usePersistentState.ts`），内置防抖写入、数据验证、localStorage 不可用回退到内存 Map
    - 业务方未使用既有 hook 而裸 `useState` 会导致用户偏好类状态在页面刷新/路由切换后丢失
    - 各组件自行实现 localStorage 读写会导致错误处理不一致、key 命名混乱、无防抖、无内存回退
    - 已通过后端 API 持久化的字段（如批量采集的 `enabled` / `interval_minutes`）不得再用 `usePersistentState` 重复持久化，否则前后端不一致
  - **判断信号**（grep 检测）：
    - `grep -E "const\s+\[\s*(autoRefresh|viewMode|columnConfig|density|collapsed|expandedKeys|themePreference|recentItems|rememberLast)\s*,\s*\w+\]\s*=\s*useState" frontend/src/pages/**/*.tsx` 命中 → 违规
    - `grep "localStorage.getItem\|localStorage.setItem" frontend/src/pages/**/*.tsx` 命中 → 检查是否应改用 `usePersistentState`
    - 用户反馈"刷新页面后开关/设置丢失"或"每次进入页面都需要重新设置" → 必查
  - **修复模式**（用 usePersistentState 替换 useState）：
    ```typescript
    // ✅ 正确：使用 usePersistentState + key 命名规范 + validator
    import { usePersistentState } from '../../hooks/usePersistentState'
    
    const [autoRefresh, setAutoRefresh] = usePersistentState<boolean>(
      'xh.batchRefresh.autoRefresh',  // key 遵循 xh.<page>.<field> 命名
      false,
      { validator: (v): v is boolean => typeof v === 'boolean' },  // validator 必填防脏数据
    )
    
    // ❌ 错误：裸 useState，刷新页面后状态丢失
    const [autoRefresh, setAutoRefresh] = useState(false)
    
    // ❌ 错误：自行实现 localStorage 读写
    const [autoRefresh, setAutoRefresh] = useState(() => localStorage.getItem('xxx') === 'true')
    ```
  - **状态分类识别**（新增 state 时必须先识别归属类别）：
    | 类别 | 持久化方式 | 示例 |
    |---|---|---|
    | 用户偏好类 | `usePersistentState` | 自动刷新、视图模式、列显隐、折叠/展开、主题偏好、最近使用列表 |
    | 业务数据类 | 后端 API | 任务列表、订单状态、配置项（已通过后端持久化） |
    | 会话状态类 | Zustand store | 登录态、当前选中项、跨页共享状态 |
    | 临时状态类 | `useState` | loading、modal open、按钮 submitting、表单 dirty |
    | 敏感数据类 | secure storage / httpOnly cookie | token、密码、API key |
  - **配置参数**：`ui_preference_persistence` 节点（enabled / preference_keywords / required_hook / prefer_state_storage_patterns / skip_scenarios / require_validator / require_key_naming / require_memory_fallback / detection_signals）
  - **关键约束**：
    - localStorage key 必须遵循 `xh.<page>.<field>` 命名模式
    - validator 必填，防止 localStorage 脏数据（旧版本数据/用户手动修改/其他项目同名 key）导致 UI 异常
    - 不重复持久化后端已通过 PATCH /config 持久化的字段（避免前后端不一致）
    - localStorage 不可用（隐私模式/存储已满/被禁用）时依赖 hook 内置的内存回退机制，业务代码不再 try-catch
  - **适用**：用户偏好类 UI 状态（开关类、视图模式、列显隐、折叠/展开、主题偏好、最近使用列表、记住上次选中项）；跨会话需要保留的 UI 偏好
  - **不适用**：业务数据（必须走后端 API）；会话状态（必须走 Zustand store）；临时状态如 loading/modal open（必须用 useState）；敏感数据（必须走 secure storage）；已通过后端持久化的字段（不重复持久化）
  - **历史教训**：`Maintenance/BatchRefresh.tsx` 的「自动刷新」开关使用 `useState(false)`，每次刷新页面或重新进入页面开关重置为关闭，用户需要反复手动开启。修复方式：替换为 `usePersistentState<boolean>('xh.batchRefresh.autoRefresh', false, { validator: ... })`，复用项目既有 `hooks/usePersistentState.ts`（含防抖写入、数据验证、localStorage 不可用回退到内存 Map）。本次同时验证「启用批量采集」与「触发间隔」字段已通过后端 `PATCH /api/batch-refresh/config` 持久化，无需重复持久化。
  - **对应后端原则**：若后端提供用户偏好 API（如 `/api/user/preferences`），同样必须复用同一持久化策略与配置驱动，不硬编码（详见 `xianyu-backend-code-review` v4.24.0 复盘记录同步原则）

### 11. 类型安全评审

- 【强制】前后端字段类型一致性（如 `is_sold?: boolean` 与后端 `bool(raw_sold)` 匹配）
- 【强制】可选链使用（`?.`）处理可能缺失的字段
- 【强制】联合类型和 `Exclude`/`Omit` 等高级类型的使用
- 【强制】避免 `any` 类型（必要时用 `unknown` + 类型守卫）
- 【强制】`as` 断言的合理性（是否有更安全的类型收窄方式）
- 【强制】TypeScript 严格模式合规（`strictNullChecks` 等）
- 🆕v4.0【强制】**IIFE 反模式禁止**：JSX 内禁止 `{(() => { ... })()}`，提取为组件顶部变量
  - ✅ `const apiKeyUrl = getApiKeyUrl(config.base_url)` → JSX: `{apiKeyUrl ? <Link/> : null}`
  - ❌ `{(() => { const url = getApiKeyUrl(config.base_url); return url ? <Link/> : null })()}`
- 🆕v4.0【强制】**动态资源映射分离**：映射表（`Record<string, string>`）与推断函数分离，不混合
  - 推断函数返回 `null` 表示无匹配，调用方条件渲染
  - 业务参数（URL、阈值）通过配置文件管理，不硬编码
- 🆕v4.4【强制】**F-REVIEW-CONFIG-DRIVEN-TOGGLE：配置驱动功能开关模式**
  - 高风险/高资源消耗的前端功能（如自动同步开关、CDP 调试触发按钮、批量操作）必须配置驱动，参数集中在 `constants.ts` 或 config 文件管理（不硬编码），默认关闭需用户显式启用
  - **判断信号**：功能需用户主动选择 + 可能耗资源（CPU/内存/网络） + 多环境部署需求 + 涉及浏览器/系统资源调用
  - **修复模式**：`constants.ts` 定义 `FEATURE_TOGGLES` 映射表 + 默认值 `false` → 组件通过 `useFeatureToggle(name)` Hook 读取 → 设置页提供 Switch 开关 + 资源消耗提示文案
  - **配置参数**：`enable_flag` 默认 `false`，详细参数（interval/threshold/port）集中在 `constants.ts` 的 `FEATURE_CONFIGS` 节点
  - **适用**：CDP 在线导入触发、Cookie 自动同步开关、向量库重建触发、批量导出等高风险/高资源消耗功能
  - **不适用**：核心功能（必须默认启用）、性能敏感场景（配置加载延迟不可接受）、简单展示组件
  - **历史教训**：`auto_sync` 默认关闭避免用户不知情下启用自动同步导致浏览器资源被占用；前端触发 CDP 导入的按钮应明确提示"需启动 Edge 调试模式"并默认 disabled，需用户先勾选"我已了解"再启用
- 🆕v4.5【强制】**F-REVIEW-ERROR-SEMANTICS：错误提示语义准确性**
  - 前端错误提示文案必须与后端错误根因语义匹配，**禁止**将特定错误（如 token 过期）显示为不相关的语义（如"登录已过期"）
  - **判断信号**：前端 catch 块中根据 HTTP 状态码或错误消息关键词显示提示文案时，文案语义必须与后端错误根因一致
  - **修复模式**：后端错误码根因分析 → 前端按语义分类显示提示（"稍后重试" vs "重新登录"）→ Alert 类型匹配严重性（warning 而非 error）→ 按钮紧迫性匹配操作出口
  - **通过示例**：
    ```typescript
    // RGV587 = mtop API 临时 token 过期，不是登录态失效
    if (detail.includes('令牌临时过期')) {
      setSessionExpired(true)  // 显示"稍后重试"提示，非"重新登录"
    }
    ```
  - **不通过示例**：
    ```typescript
    // RGV587 被映射为 401，前端显示"登录已过期"
    if (status === 401 || detail.includes('登录已过期')) {
      setSessionExpired(true)  // 误导用户重新登录
    }
    ```
  - **适用**：所有前端错误提示（Alert、message、notification）
  - **不适用**：开发环境调试信息
  - **历史教训**：后端将 RGV587（mtop API 临时 token 过期，TTL 1 小时）映射为 HTTP 401("闲鱼登录已过期")，前端捕获 401 后显示红色 Alert"Cookie 失效或会话过期"。但用户多查几次能成功——说明不是登录态失效。修复后改为橙色 warning"搜索令牌临时过期，请稍后重试"
- 🆕v4.7【强制】**F-REVIEW-DATA-FLOW-TRACE-FRONTEND：字段为空 5 点追踪（前端侧）**
  - 前端"字段为空/显示异常"类问题必须配合后端按 5 点逐层追踪，前端侧负责验证 types 声明 + render 取值两点，**禁止**仅查前端单层就下结论"前端 bug"
  - **判断信号**：用户反馈"字段显示空/'—'/undefined" → 前端 grep 字段名在 `types.ts` 是否声明 → grep 在 `render` 是否正确取值 → 若前端正常则定位为后端问题（配合后端 B-REVIEW-DATA-FLOW-TRACE 追踪 DB/Repo/API 三点）
  - **修复模式**（前端侧 5 点追踪流程）：
    ```typescript
    // 1. types.ts 中字段声明
    interface Order {
      order_id: string          // ✅ 字段已声明
      status: string
      price: number | null      // ✅ 可空字段用 | null
    }
    // 2. render 中取值
    const order = orders.find(o => o.item_id === itemId)
    // ❌ 错误：orders 为空数组时显示 "—"
    // ✅ 正确：先检查 orders 是否加载完成
    {orders.length === 0 ? <Empty /> : <Table data={orders} />}
    // ❌ 错误：order.status 被 Repo 层过滤掉（前端无法发现，需配合后端追踪）
    ```
  - **配置参数**：`trace_nodes_frontend`（前端负责的追踪节点：`frontend_types` + `render`）、`required_fields`（必查字段列表）、`null_value_patterns`（空值渲染模式，如 `field || '—'` / `field ?? '暂无'`）在 `config.yaml` 的 `data_flow_trace_frontend` 节点管理
  - **关键约束**：
    - 前端发现字段为空时，必须先确认前端 types + render 两点正常，再定位为后端问题
    - 可空字段必须用 `| null` 显式声明，禁止用 `any` 或省略类型
    - 渲染时必须区分"数据加载中"、"数据为空"、"字段缺失"三种状态
    - 前端 grep 字段名在 `types.ts` 和 `render` 都正常 → 必须反馈后端排查 DB/Repo/API 三点
  - **适用**：用户反馈"字段为空/显示异常/数据丢失"的所有场景
  - **不适用**：前端布局问题（非数据问题）、样式渲染问题、权限问题（用户看不到数据）
  - **历史教训**：评估明细页订单字段显示 "—"，前端排查 types 声明正常、render 取值正常，最终定位为后端 Repo 层 `list_orders_by_item_ids` 一刀切过滤 `if status == 'failed': continue`。前端侧已正常，根因在后端

- 🆕v4.12【强制】**F-REVIEW-XSS-ESCAPE：用户输入字段 HTML 转义**
  - 后端返回的用户输入字段（如 task.source、item.title、user.nickname）在展示时必须经过 HTML 转义，**禁止**直接渲染到 DOM（即使 JSX 默认转义，仍需双重保护防止 dangerouslySetInnerHTML 误用）
  - **核心机制**（审查时必须理解）：
    - React JSX 默认对 `{value}` 进行 HTML 转义，但以下场景不转义：`dangerouslySetInnerHTML`、`<a href={value}>`（javascript: 协议）、`<iframe src={value}>`、动态属性名
    - 后端字段可能含 `<script>` / `<img onerror=>` / `javascript:` 等 XSS 载荷
    - 双重保护：escapeHtml 函数（转义 < > & " '）+ React JSX 默认转义，确保任意一层失效仍有保护
  - **判断信号**：
    - 后端返回字段直接渲染到 `dangerouslySetInnerHTML` → 视为违规
    - 后端返回字段直接渲染到 `<a href={value}>` 且未校验协议 → 视为违规
    - 后端返回字段含 source/title/nickname/name 等用户可编辑字段 → 必须经过 escapeHtml
    - 代码含 `dangerouslySetInnerHTML={{ __html: backendField }}` → CRITICAL 违规
  - **修复模式**：
    ```typescript
    // ✅ escapeHtml 函数 + SafeSourceTag 组件双重保护
    function escapeHtml(str: string): string {
      return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
    }

    function SafeSourceTag({ source }: { source: string }) {
      // 第一层保护：escapeHtml 转义特殊字符
      const safeSource = escapeHtml(source)
      // 第二层保护：JSX 默认转义（即使 escapeHtml 失效，JSX 仍会转义）
      return <Tag>{safeSource}</Tag>
    }

    // ❌ 错误：后端字段直接渲染到 dangerouslySetInnerHTML
    // <div dangerouslySetInnerHTML={{ __html: task.description }} />

    // ❌ 错误：后端字段直接渲染到 a href 未校验协议
    // <a href={item.url}>链接</a>  // item.url 可能是 javascript:alert(1)

    // ✅ a href 必须校验协议
    function isSafeUrl(url: string): boolean {
      return /^https?:\/\//i.test(url)
    }
    {isSafeUrl(item.url) && <a href={item.url}>链接</a>}
    ```
  - **配置参数**：`xss_escape.required_for_fields`（必须转义的字段名列表，如 `["source", "title", "nickname", "description", "name"]`）、`xss_escape.forbidden_directives`（禁止的指令列表，如 `["dangerouslySetInnerHTML"]`）、`xss_escape.url_protocol_whitelist`（URL 协议白名单，如 `["http:", "https:"]`）、`xss_escape.double_protection`（默认 `true`，必须双重保护）在 `config.yaml` 的 `xss_escape` 节点管理
  - **适用**：所有后端返回字段的渲染；用户可编辑字段（source/title/nickname/description）；URL 字段（href/src）
  - **不适用**：纯前端硬编码字符串（如 'Hello World'）；数字/布尔类型字段（无 XSS 风险）；React 组件内部状态字段
  - **历史教训**：`TaskContentMenu` 直接渲染后端返回的 `task.source` 字段到 `<Tag>{source}</Tag>`，虽然 JSX 默认转义，但若用户切换到 `dangerouslySetInnerHTML` 渲染模式则会被 XSS 攻击。修复后增加 `escapeHtml` 函数 + `SafeSourceTag` 组件双重保护
- 🆕v4.13【强制】**F-REVIEW-ERROR-CONTRACT-TIMEOUT：前后端错误码契约与超时识别**
  - 前端调用后端含重试/异步逻辑的接口时，必须用模块级 `statusMessages: Record<number, string>` 映射表 + 独立 `isAxiosTimeout()` 函数双路识别错误，axios 超时无 `response.status` 必须用 `error.code === 'ECONNABORTED'` 或 `/timeout/i.test(error.message)` 识别，**禁止**所有错误走同一通用文案导致用户无法区分"网络超时"与"商品下架"
  - **核心机制**（审查时必须理解）：
    - axios 超时无 `response.status`（请求未到达后端或后端未响应），必须通过 `error.code` 与 `error.message` 识别
    - 后端按语义区分的状态码（401/403/410/440/441/502/503）必须在前端映射表中有对应文案
    - 超时识别优先于 status 映射（因超时无 status）
  - **判断信号**：
    - 前端 catch 块含 `err.response?.status` 但无超时识别逻辑 → 视为违规
    - 前端 `message.error('xxx 失败，请稍后重试')` 出现在多个 catch 块 → 必须按状态码差异化文案
    - 模块内无独立 `isAxiosTimeout` 函数 → 视为违规
    - 错误消息映射表硬编码在 catch 块内 → 必须提取为模块级常量
  - **修复模式**：
    ```typescript
    // ✅ 模块级常量 + 模块级函数 + 统一错误提示
    const COLLECT_OFFICIAL_ERROR_MESSAGES: Record<number, string> = {
      503: '官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动',
      403: '闲鱼登录已过期，请重新登录闲鱼',
      440: '闲鱼登录已过期，请重新登录闲鱼',
      441: '触发闲鱼反爬限制，请稍后重试或手动完成验证',
      410: '商品详情页加载失败或已下架，请稍后重试',
      502: '浏览器连接异常，请重启服务后重试',
    }
    const COLLECT_OFFICIAL_TIMEOUT_MESSAGE = '官方采集超时（详情页+卖家主页加载缓慢），请稍后重试或检查网络'
    const COLLECT_OFFICIAL_FALLBACK_MESSAGE = '官方采集失败，请稍后重试'

    const isAxiosTimeout = (error: { code?: string; message?: string }): boolean =>
      error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')

    function showStatusError(err: unknown, statusMessages: Record<number, string>,
                             timeoutMessage: string, fallbackMessage: string): void {
      const error = err as { response?: { status?: number; data?: { detail?: string } }; code?: string; message?: string }
      if (isAxiosTimeout(error)) {
        message.error(timeoutMessage)  // 超时优先
      } else if (error?.response?.status != null && statusMessages[error.response.status]) {
        message.error(error?.response?.data?.detail || statusMessages[error.response.status])
      } else {
        message.error(error?.response?.data?.detail || fallbackMessage)
      }
    }

    // ❌ 错误：所有错误走同一通用文案
    // catch (err) { message.error('官方采集失败，请稍后重试') }

    // ❌ 错误：无超时识别（axios 超时无 response.status）
    // catch (err) { if (err.response?.status === 502) message.error('...') }
    ```
  - **配置参数**：`frontend_error_contract.timeout_codes`（默认 `['ECONNABORTED']`，axios 超时 code 列表）、`frontend_error_contract.timeout_patterns`（默认 `['/timeout/i']`，超时 message 正则模式列表）、`frontend_error_contract.status_message_map`（场景到消息映射，按业务接口分组，如 `collect_official: { 410: '...', 441: '...' }`）、`frontend_error_contract.timeout_priority`（默认 `true`，超时识别优先于 status 映射）在 `config.yaml` 的 `frontend_error_contract` 节点管理
  - **适用**：含重试逻辑的 SSE/HTTP 接口、依赖多类 Cookie 的接口、含状态机的业务接口、浏览器自动化接口
  - **不适用**：一次性请求无重试逻辑、纯 token 认证（JWT 无超时概念）、内部 API（无业务文案需求）
  - **历史教训**：用户反馈"官方采集失败，请稍后重试"，理论推断为 axios 30s 超时，实际日志显示采集只花 12s，根因是后端选择器失效返回 502，前端无超时识别导致无法区分"超时"与"502"
- 🆕v4.13【强制】**F-REVIEW-RETRY-BACKOFF：前端可重试错误集与退避策略**
  - 前端调用后端接口必须区分「可重试错误」（410/441/502/timeout）与「需用户介入错误」（403/440/503），可重试错误用指数/固定退避重试 N 次（默认 N=1），重试时不弹消息避免打扰用户，**禁止**对所有错误一刀切重试导致需用户介入的错误被无意义重试
  - **核心机制**（审查时必须理解）：
    - 可重试错误：临时性故障（410 页面未加载/441 反爬触发/502 连接异常/timeout 超时）
    - 需用户介入错误：403 权限不足/440 Cookie 过期/503 服务未启动，重试无意义
    - 重试时不弹消息：避免偶发失败打扰用户，仅在最终失败时展示错误
    - 退避时间按错误类型差异化：441 反爬需 3s 冷却，410/502 快速重试 1s
  - **判断信号**：
    - 前端 catch 块直接 `throw` 或直接 `message.error` → 必须评估错误是否可重试
    - 前端 `retry_count` 或 `MAX_RETRIES` 硬编码数字 → 必须移到配置或模块级常量
    - 前端对所有错误都重试 → 必须区分可重试与不可重试
    - 前端重试时弹消息 → 应改为静默重试（仅在最终失败时展示）
  - **修复模式**：
    ```typescript
    // ✅ 可重试错误集 + 退避时间映射 + 重试不弹消息
    const RETRYABLE_STATUSES = new Set([410, 441, 502])
    const RETRY_DELAYS: Record<string, number> = {
      '410': 1000,   // 页面未加载，快速重试
      '441': 3000,   // 反爬触发，需 3s 冷却
      '502': 1000,   // 连接异常，快速重试
      'timeout': 2000,  // 超时，2s 后重试
    }

    async function collectOfficialWithRetry(itemId: string, taskId?: string): Promise<OfficialCollectResult> {
      const MAX_RETRIES = 1
      let lastErr: unknown
      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
          return await evalApi.collectOfficial(itemId, taskId)
        } catch (err: unknown) {
          lastErr = err
          if (attempt >= MAX_RETRIES) break
          const e = err as { response?: { status?: number }; code?: string; message?: string }
          const status = e?.response?.status
          const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(e?.message || '')
          const retryable = isTimeout || (status !== undefined && RETRYABLE_STATUSES.has(status))
          if (!retryable) break  // 不可重试错误直接抛出
          const delayKey = isTimeout ? 'timeout' : String(status)
          const delay = RETRY_DELAYS[delayKey] ?? 2000
          await new Promise(resolve => setTimeout(resolve, delay))
          // 重试时不弹消息，避免打扰用户（仅在最终失败时展示错误）
        }
      }
      throw lastErr
    }

    // ❌ 错误：对所有错误一刀切重试
    // for (let i = 0; i < 3; i++) { try { return await api() } catch { await sleep(1000) } }

    // ❌ 错误：重试时弹消息打扰用户
    // catch (err) { message.loading('重试中...'); await sleep(1000); retry() }
    ```
  - **配置参数**：`frontend_retry_strategy.retryable_statuses`（默认 `[410, 441, 502]`，可重试状态码列表）、`frontend_retry_strategy.retry_delays_ms`（默认 `{410: 1000, 441: 3000, 502: 1000, timeout: 2000}`，状态码到退避时间映射）、`frontend_retry_strategy.max_retries`（默认 `1`，最大重试次数）、`frontend_retry_strategy.non_retryable_statuses`（默认 `[403, 440, 503]`，需用户介入的错误列表）、`frontend_retry_strategy.silent_on_retry`（默认 `true`，重试时不弹消息）在 `config.yaml` 的 `frontend_retry_strategy` 节点管理
  - **适用**：网络请求（axios/fetch）、临时性错误（410/441/502/timeout）、浏览器自动化接口
  - **不适用**：需用户介入的错误（403 权限不足/440 Cookie 过期/503 服务未启动）、不可重试业务错误（404 资源不存在）、事务性操作（POST/PUT/DELETE 需幂等性保证）
  - **历史教训**：前端对所有错误直接 `message.error`，用户被偶发的 441 反爬或 502 连接异常打扰，需用户手动重试；改为仅对可重试错误自动重试 1 次后，95% 的偶发失败用户无感知
- 🆕v4.14【强制】**F-REVIEW-FILTER-BACKEND-ALIGN：前端过滤与后端分类对齐**
  - 实现前端过滤功能前必须先 grep 后端 `insufficient_count`/`marginals`/`result` 确认分类互斥性，前端过滤条件必须与后端分类逻辑对齐，过滤后各分类数量之和等于总数，**禁止**前端自定义分类逻辑导致与后端统计不一致
  - **维度**：7 API 调用规范
  - **核心机制**（审查时必须理解）：
    - 后端分类是互斥的（每条记录只属于一个分类），前端过滤条件必须与后端分类逻辑 1:1 对齐
    - 过滤后各分类数量之和必须等于总数（互斥性验证），否则说明前端过滤逻辑有误
    - 阈值参数（autoBuyScore/passScore）必须从 config 读取，禁止硬编码
  - **判断信号**：
    - 前端有 filterStatus 状态但未 grep 后端分类逻辑 → 视为违规
    - 前端过滤后各分类数量之和 ≠ 总数 → 视为违规（分类不互斥或过滤逻辑错误）
    - 前端硬编码阈值数字（如 80/60） → 必须移到配置
  - **示例**：评估明细统计卡片过滤，前端 filterStatus 过滤逻辑必须与后端 `api_evaluations.py` 的 `dist.marginals.result` 分类一致（`score==null→insufficient`，`score>=autoBuyScore→auto`，`passScore<=score<autoBuyScore→pass`，`score<passScore→fail`）
  - **适用**：统计卡片过滤、Tab 分类过滤、状态分组过滤
  - **不适用**：纯前端搜索过滤（无后端分类对应）、非互斥分类
  - **配置驱动**：阈值参数从 config 读取，分类映射表在 `config.yaml` 的 `filter_backend_align` 节点管理
  - **历史教训**：评估明细页统计卡片点击过滤后，前端 filterStatus 分类逻辑与后端 `dist.marginals.result` 不一致，导致过滤后数量与统计卡片显示数量不匹配
- 🆕v4.14【强制】**F-REVIEW-FILTER-PAGINATION-ADAPT：前端过滤后分页参数适配**
  - 添加 filterStatus 状态后必须同步调整 pagination 的 total/current/pageSize 三参数，**禁止**过滤后仍用原 total/items 导致分页错乱或数据截断
  - **维度**：10 Hooks 设计模式
  - **核心机制**（审查时必须理解）：
    - `total=filteredItems.length`：分页总数基于过滤后的数据量
    - `current=1`：切换过滤条件时重置到第一页，不触发后端 reload（前端过滤已加载数据）
    - `pageSize=filteredItems.length||1`：全量显示避免截断（过滤后数据量通常较少）
  - **判断信号**：
    - 前端有 filterStatus 但 pagination 仍用原 items.length → 视为违规
    - 切换 filterStatus 后 current 不重置 → 视为违规（可能指向不存在的页）
    - 过滤后 pageSize 仍用原值导致数据截断 → 视为违规
  - **示例**：`filterStatus !== 'all'` 时 `total=filteredItems.length`、`current=1`、`pageSize=filteredItems.length||1`
  - **适用**：前端过滤已加载的分页数据
  - **不适用**：后端分页过滤（filter 参数传给后端）
  - **配置驱动**：分页参数策略在 `config.yaml` 的 `filter_pagination_adapt` 节点管理
  - **历史教训**：评估明细页添加 filterStatus 后未调整 pagination 参数，导致过滤后分页错乱、数据被截断
- 🆕v4.14【强制】**F-REVIEW-FILTER-EMPTY-STATE：过滤空状态区分**
  - 空状态判断必须用 `filteredItems.length` 而非原始 `items.length`，区分「无数据」与「过滤后无匹配」两种文案，**禁止**用同一个空状态文案导致用户无法区分
  - **维度**：3 React 组件规范
  - **核心机制**（审查时必须理解）：
    - `items.length === 0`：数据源为空（后端无数据），应显示「暂无数据」
    - `filteredItems.length === 0` 但 `items.length > 0`：有数据但过滤后无匹配，应显示「当前过滤条件下无匹配记录」
    - 两种空状态文案必须不同，帮助用户判断是数据问题还是过滤问题
  - **判断信号**：
    - 前端用 `items.length === 0` 判断空状态但有 filterStatus → 视为违规
    - 过滤后无匹配数据显示「暂无数据」 → 视为违规（应显示「当前过滤条件下无匹配记录」）
    - 两种空状态用同一文案 → 视为违规
  - **示例**：`filteredItems.length === 0 ? (items.length === 0 ? '暂无数据' : '当前过滤条件下无匹配记录') : <Table>`
  - **适用**：所有带过滤功能的列表页
  - **不适用**：无过滤功能的纯展示列表
  - **配置驱动**：空状态文案在 `config.yaml` 的 `filter_empty_state` 节点管理
  - **历史教训**：评估明细页过滤后无匹配数据时显示「暂无数据」，用户误以为后端无数据，实际是过滤条件不匹配
- 🆕v4.15【强制】**F-REVIEW-DEBUG-CODE-CLEANUP：临时 DEBUG 代码清理**
  - 临时 DEBUG 代码在问题修复后必须移除，**禁止**留在生产代码中。DEBUG 代码包括：临时 import（如 `import * as _fs from 'fs'`）、临时环境变量检查（如 `process.env.DEBUG`）、临时日志文件写入（如 `_fs.writeFileSync('debug.log', ...)`）、临时 console.log（如 `console.log('DEBUG: ...')`）。问题修复后必须 grep 所有 DEBUG 代码并移除，避免污染生产环境
  - **判断信号**：代码含 `import * as _fs` / `process.env.DEBUG` / `writeFileSync('debug.log')` / `console.log('DEBUG')` / 异常密集的 console.log → 必须检查是否为临时 DEBUG 代码；问题修复后 grep 仍有 DEBUG 代码 → 必须移除
  - **修复模式**：
    ```typescript
    // ❌ 错误：问题修复后仍保留 DEBUG 代码
    import * as _fs from 'fs'  // ❌ 临时 import 未移除
    if (process.env.DEBUG) {  // ❌ 临时环境变量检查未移除
      _fs.writeFileSync('debug.log', JSON.stringify(response))  // ❌ 临时日志文件未移除
    }
    console.log('DEBUG: response=', response)  // ❌ 临时打印语句未移除

    // ✅ 正确：问题修复后移除所有 DEBUG 代码
    // grep -rn "DEBUG\|debug\.log\|import \* as _fs\|process\.env\.DEBUG" frontend/src/
    // 确认无残留 DEBUG 代码
    ```
  - **配置参数**：`debug.enabled`（默认 `false`，生产环境禁止 DEBUG 代码）、`debug.cleanup_after_fix`（默认 `true`，问题修复后自动清理 DEBUG 代码）、`debug.whitelist`（长期监控指标白名单，如 `["performance_metrics", "health_check"]`）在 `config.yaml` 的 `debug` 节点管理
  - **适用**：临时调试代码、排查问题后的清理、开发环境调试
  - **不适用**：日志级别动态降级（需保留配置）、长期监控指标收集（需保留）、性能埋点（需保留）
  - **历史教训**：前端问题排查时添加 `import * as _fs` 和 `writeFileSync('debug.log', ...)` 写入调试信息，问题修复后未移除，导致生产环境产生 debug.log 文件污染

- 🆕v4.16【强制】**F-REVIEW-FIELD-CONTRACT-ALIGN：前后端字段契约对齐**
  - **判断信号**：后端有 `_normalize` / `_unify` / `_merge` / `_flatten` 等归一化函数 + 前端 types.ts 声明 damages/inconsistencies 等旧字段名 + 前端通过 `check[signalKey]` 动态 key 取值
  - **强制规则**：后端归一化字段时前端 types.ts 必须注释 `// 后端已归一化，前端消费 X 字段`；保留旧字段名必须标 optional 并注释 `// 仅作兼容保留，后端不返回`；前端禁止通过动态 key 取归一化字段，必须直接用归一化后字段名（如 `check.signals`）
  - **反例**：`const signals = (check[signalKey] as string[] | undefined) ?? []`（后端归一化后 signalKey 永远 undefined）
  - **正例**：`const signals = check.signals ?? []`
  - **配置参数**：`field_contract_align` 节点（enabled / require_doc_comment / detect_dynamic_key_access / fallback_to_legacy_field）
  - **适用场景**：后端有归一化函数 + 前端通过动态 key 取值
  - **不适用场景**：后端直接返回原始响应无转换；前端类型声明与后端 pydantic 模型一一对应

- 🆕v4.16【强制】**F-REVIEW-ERROR-HANDLER-EXTRACT：重复错误处理抽取**
  - **判断信号**：grep `status === 403` / `status === 404` 在同文件内出现 >= 2 处；多个 async 函数调用同一后端端点的错误处理 if-else 完全重复
  - **强制规则**：两处以上相同 if-else 状态码分支必须抽取工具函数 `handleXxxError(err, fallbackMsg, closeModal)`；抽取后原调用处仅保留 `handleXxxError(err, '失败文案', () => setModalOpen(false))` 一行
  - **反例**：onAIEval 和 onDeepAnalyze 各自包含 403/404/422 三段 if-else 完全重复
  - **正例**：抽取 `handleAiError(err, fallbackMsg, closeModal)` 工具函数，两处调用各减少 13 行
  - **配置参数**：`error_handler_extract` 节点（enabled / min_duplicate_count / detect_patterns / unified_signature）
  - **适用场景**：多个 async 函数调用同一后端端点；多个函数处理同一类外部 API 错误
  - **不适用场景**：仅一处调用的错误处理；错误处理逻辑有差异（如不同端点状态码集合不同）

- 🆕v4.21【强制】**F-REVIEW-FIELD-NAME-ALIGN：字段名三层一致性规范**
  - 凭据字段名在四层（前端 `types.ts` / 后端 Pydantic 模型 / keyring KEY 常量 / yaml 字段）必须 1:1 对齐；当第三方库构造函数参数名与本项目字段名不一致时，必须在 API 边界层做字段名映射（`_FIELD_NAME_MAP` 映射表 + `_map_credentials_to_notifier_params()` 转换函数），**禁止** API 端点直接 `**body.credentials` 解包透传
  - **核心机制**（审查时必须理解）：
    - Pydantic v2 + keyring + yaml 三层持久化链路中，字段名不一致会导致同步写错位置或 `model_dump()` 丢弃字段
    - 第三方 Notifier 构造函数参数名（如 `webhook_url`/`send_key`/`token`）通常与项目字段名（如 `dingtalk_webhook`/`serverchan_send_key`/`pushplus_token`）不一致
    - API 端点直接 `**body.credentials` 解包传给 Notifier 构造函数，未识别字段会被 `**kwargs` 吞入，触发 `TypeError`
    - 边界层映射函数必须集中在模块顶部声明，禁止散落在多个函数内
  - **判断信号**：
    - 前端 `types.ts` 凭据字段名 ≠ 后端 Pydantic 字段名 → 视为违规
    - 后端 Pydantic 字段名 ≠ keyring KEY 常量名 → 视为违规
    - keyring KEY 常量名 ≠ yaml 字段名 → 视为违规
    - API 端点直接 `**body.credentials` 解包传给 Notifier 构造函数 → 必查字段名映射
    - Notifier 构造函数参数名与前端字段名不一致（如 `dingtalk_webhook` vs `webhook_url`）→ 必须在边界层做字段名映射
  - **修复模式**：
    ```typescript
    // ✅ 前端 types.ts 字段名与后端 Pydantic 字段名 1:1 对齐
    interface NotifierCredentials {
      serverchan_send_key: string
      pushplus_token: string
      bark_server: string
      bark_key: string
      telegram_bot_token: string
      telegram_chat_id: string
      wecom_webhook: string
      dingtalk_webhook: string
      dingtalk_secret: string
      webhook_url: string
    }
    ```

    ```python
    # ✅ 后端边界层字段名映射（集中在模块顶部声明）
    _FIELD_NAME_MAP: dict[str, str] = {
        "serverchan_send_key": "send_key",
        "pushplus_token": "token",
        "bark_server": "server",
        "bark_key": "key",
        "telegram_bot_token": "bot_token",
        "telegram_chat_id": "chat_id",
        "wecom_webhook": "webhook_url",
        "dingtalk_webhook": "webhook_url",
        "dingtalk_secret": "secret",
    }

    def _map_credentials_to_notifier_params(credentials: dict[str, str]) -> dict[str, str]:
        """将前端字段名转换为 Notifier 构造函数参数名"""
        mapped: dict[str, str] = {}
        for key, value in credentials.items():
            mapped[_FIELD_NAME_MAP.get(key, key)] = value
        return mapped

    # ❌ 错误：直接 **body.credentials 解包
    # notifier = registry.create(channel, **body.credentials)
    # # TypeError: BaseNotifier.__init__() got an unexpected keyword argument 'dingtalk_webhook'
    ```
  - **配置参数**：`field_name_mapping.layers`（必须对齐的层级列表，如 `["frontend_types", "pydantic_model", "keyring_key", "yaml_field"]`）、`field_name_mapping.boundary_map`（边界层字段名映射表，如 `{"serverchan_send_key": "send_key", ...}`）、`field_name_mapping.require_align_check`（默认 `true`，CI 中自动检查字段名对齐）在 `config.yaml` 的 `field_name_mapping` 节点管理
  - **适用场景**：凭据字段（webhook/token/secret 类）；前后端持久化链路字段；多层级字段名一致性要求
  - **不适用场景**：第三方 API 返回字段的归一化（参考 F-REVIEW-FIELD-CONTRACT-ALIGN）；前端内部状态字段（无后端对应）；后端计算字段（无前端写入）
  - **历史教训**：前端字段名 `dingtalk_webhook` 与 Notifier 构造函数参数名 `webhook_url` 不一致，`/api/notifier/test` 直接 `**body.credentials` 解包导致 `TypeError: BaseNotifier.__init__() got an unexpected keyword argument 'dingtalk_webhook'`。修复后添加 `_FIELD_NAME_MAP` 边界层映射

- 🆕v4.21【强制】**F-REVIEW-CONFIG-PERSIST-VERIFY：配置持久化端到端验证规范**
  - 持久化链路必须端到端验证（前端写入 → API 接收 → Pydantic 序列化 → yaml 存储 → keyring 同步（如适用） → GET 回显），每层必须打印中间值确认传递；修复后必须新增端到端测试覆盖该场景（前端写入 → 刷新页面 → 验证回显）；开关状态字段必须默认安全（如 `enabled: bool = False` 默认关闭，避免意外启用）
  - **核心机制**（审查时必须理解）：
    - 持久化链路任一层断裂都会导致"填写后刷新页面变空"问题
    - Pydantic v2 `extra='ignore'` 会丢弃未声明字段（参考 B-REVIEW-PYDANTIC-FIELD-DECLARE）
    - 前端 `types.ts` 字段缺失会导致 API 响应字段无法被前端消费
    - 开关状态默认值若为 `true`，新增功能默认启用可能造成意外影响
  - **判断信号**：
    - 前端表单填写后刷新页面输入框变空 → 必查持久化链路（types.ts → API → Pydantic → yaml → 回显）
    - 前端开关状态切换后刷新页面还原为初始值 → 必查开关字段是否在 Pydantic 模型中声明
    - API 响应缺失前端写入的字段 → 必查 Pydantic `model_dump()` 是否丢弃未声明字段
    - 前端调用 `PUT /api/config` 成功但 `GET /api/config` 返回旧值 → 必查后端是否实际写入 yaml
  - **修复模式**：
    ```typescript
    // ✅ 前端：写入后立即 GET 验证回显
    const onSave = async (credentials: NotifierCredentials) => {
      await fetch('/api/config', {
        method: 'PUT',
        credentials: 'include',
        body: JSON.stringify(credentials),
      })
      // 端到端验证：立即 GET 确认回显
      const resp = await fetch('/api/config', { credentials: 'include' })
      const data = await resp.json()
      if (data.dingtalk_webhook !== credentials.dingtalk_webhook) {
        message.error('配置未持久化，请检查后端')
      }
    }
    ```
  - **配置参数**：`config_persist_verify.layers`（必须验证的层级列表，如 `["frontend_write", "api_receive", "pydantic_serialize", "yaml_store", "get_response"]`）、`config_persist_verify.require_e2e_test`（默认 `true`，必须新增端到端测试）、`config_persist_verify.default_safe_value`（默认 `false`，开关字段默认安全值）在 `config.yaml` 的 `config_persist_verify` 节点管理
  - **适用场景**：所有用户可编辑的配置项（凭据、开关、阈值）；前端表单 → 后端持久化的链路；刷新页面后状态需保持的场景
  - **不适用场景**：纯前端状态（如 UI 折叠状态）；运行时计算字段（无需持久化）；调试用临时字段
  - **历史教训**：通知渠道菜单填写凭据后刷新页面输入框清空。根因：`AppConfig` Pydantic 模型未声明凭据字段，`extra='ignore'` 导致 `model_dump()` 丢弃，`GET /api/config` 不返回凭据。修复后端到端验证每一层传递
- 🆕v4.23【强制】**F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION：模型能力元数据集中展示与降级状态可视化**
  - 前端展示 LLM 模型能力（vision_capable / function_call / json_mode）时必须**集中展示**（从后端 `/api/config` 或 `/api/about` 统一获取，禁止在每个展示页独立 fetch / 内联判断）；用户上传图片 / 启用 tool 时前端必须根据能力位给出**降级状态可视化**（如 `Tag color="warning"` 显示"纯文本模型不支持图片分析，已降级为文字描述"），禁止静默丢弃用户的可选输入
  - **核心机制**（审查时必须理解）：
    - 后端 `api_ai._is_vision_capable()` 共享函数 + `api_ai_deep.py` 调用是后端服务端的"能力-需求"匹配
    - 前端展示层是"用户-能力"对齐：用户能直观看到当前模型支持什么能力 + 不支持时降级行为
    - 后端 LLM 调用前预检 + 前端展示能力位 + 降级状态可视化 = 端到端能力驱动派发
    - 关键字白名单仅在后端 `api_ai._VISION_CAPABLE_KEYWORDS` 一处维护，前端展示用 `settings.openai_vision_model` + 单一 `isVisionCapable()` 共享函数
  - **判断信号**：
    - 前端 `useState` / `useEffect` 内独立 fetch `/api/config` 获取 vision_model + 内联关键字白名单判断（`if (model.includes('vision'))`）→ 视为违规（应统一 fetch + 共享函数）
    - 前端调用图片上传 / function call 时未做能力位预检 + 降级提示 → 视为违规
    - 关键字列表（`['vision', 'gpt-4o', ...]`）出现在前端 `.tsx`/`.ts` 文件中（应仅在后端 `api_ai.py`）→ 视为违规
    - 跨 ≥2 前端组件出现相同的 vision_capable 判断逻辑 → 视为违规（应抽到 `frontend/src/utils/modelCapability.ts` 共享）
  - **修复模式**：
    ```typescript
    // ✅ 共享工具函数 + 集中获取 + 降级可视化
    // frontend/src/utils/modelCapability.ts
    const VISION_KEYWORDS = ['vision', 'gpt-4o', 'gpt-4-vision', 'qvq', 'qwen-vl', 'glm-4v', 'claude-3', 'opus', 'sonnet', 'haiku'] as const;
    export function isVisionCapable(modelName: string | null | undefined): boolean {
      if (!modelName) return false;
      return VISION_KEYWORDS.some(kw => modelName.toLowerCase().includes(kw));
    }
    export function getCapabilityDisplay(modelName: string | null | undefined): { vision: boolean; warning?: string } {
      if (!modelName) return { vision: false, warning: '未配置模型' };
      const vision = isVisionCapable(modelName);
      return { vision, warning: vision ? undefined : '当前模型为纯文本模型，已自动降级为文字描述' };
    }

    // AI 配置页（集中展示）
    import { getCapabilityDisplay } from '@/utils/modelCapability';
    const { vision, warning } = getCapabilityDisplay(settings.openai_vision_model);
    return <div>
      <Tag color={vision ? 'success' : 'warning'}>{vision ? '支持 Vision' : '不支持 Vision'}</Tag>
      {warning && <Alert type="warning" message={warning} />}
    </div>;

    // 图片上传组件（消费端）
    const { vision } = getCapabilityDisplay(settings.openai_vision_model);
    const handleUpload = (file: File) => {
      if (!vision) {
        message.warning('当前模型不支持图片分析，将使用文字描述');
        return uploadAsText(file);
      }
      return uploadAsImage(file);
    };
    ```
    ```typescript
    // ❌ 错误：跨组件内联关键字 + 独立 fetch
    // AIConfigPage.tsx
    const [vision, setVision] = useState(false);
    useEffect(() => {
      fetch('/api/config').then(r => r.json()).then(c => {
        setVision(['vision', 'gpt-4o'].some(kw => c.openai_vision_model.includes(kw)));
      });
    }, []);
    // ImageUploader.tsx（重复）
    const [vision, setVision] = useState(false);
    useEffect(() => {
      fetch('/api/config').then(r => r.json()).then(c => {
        setVision(c.openai_vision_model.includes('vision'));  // 散落修改风险
      });
    }, []);
    ```
  - **配置参数**：`model_capability_centralization.shared_util_path`（默认 `frontend/src/utils/modelCapability.ts`）、`model_capability_centralization.capability_source`（默认 `/api/config` + `/api/about`）、`model_capability_centralization.require_centralized_fetch`（默认 `true`，禁止每页独立 fetch）、`model_capability_centralization.require_downgrade_visualization`（默认 `true`，降级状态必须可视化）、`model_capability_centralization.tag_color_mapping`（默认 `{supported: 'success', unsupported: 'warning'}`）、`model_capability_centralization.alert_message`（默认 `当前模型不支持 {capability}，已自动降级为 {fallback}`）在 `config.yaml` 的 `model_capability_centralization` 节点管理
  - **适用场景**：前端展示 LLM 模型能力（AI 配置页 / 设置页 / 模型选择器）；用户上传图片 / 启用 tool / 选择 json_mode 的交互组件；监控页展示当前模型能力与降级状态；多页面共享同一能力位信息
  - **不适用场景**：纯后端内部能力判断（无前端展示）；单页面单次性能力判断（不必抽取共享函数）；后端 SDK 已封装能力判断（如 langchain `with_structured_output`）
  - **历史教训**：深度分析无脑拼接 `image_url` content block → 后端 400 → WARNING 噪音；前端用户上传图片时未做能力预检，图片被静默丢弃；修复时后端抽 `_is_vision_capable()` 共享函数 + 前端抽 `getCapabilityDisplay()` 共享函数 + 集中展示能力 + 上传时降级提示

### 12. SonarQube 合规 🆕v2.0 / v3.0 增强

- 【强制】**S2004**：函数嵌套层级 ≤ 4，超限提取模块级函数（典型：setState updater）
- 【强制】**S3358**：嵌套三元拆为变量（不超过 2 层）
- 【强制】**S6757**：SFC 内不用 `this`，工厂函数替代 class
- 【强制】**S7784**：使用 `structuredClone` 替代 `JSON.parse(JSON.stringify())`
- 【强制】**S6848**：`clickableProps` 工厂函数配键盘事件
- 【强制】**S1128**：删除未使用 import
- 【强制】**S4325**：移除不必要类型断言
- 【强制】**S3776**：认知复杂度 ≤ 15，拆 case 为模块级 handler
- 🆕【强制】**S7503**：不必要的 `async` 函数（无 await）——同步函数移除 `async` 关键字
- 🆕【强制】**S6767**：未使用的 Props/State/参数 ——立即删除，避免接口膨胀
- 🆕【强制】**S6819**：使用 `<a>` 替代 `<button>`（无 href 时）——改用 `<button type="button">`
- 🆕【强制】**S6844**：使用 `<div role="button">` 替代 `<button>` ——优先原生 `<button>` + 键盘事件
- 🆕【强制】**S7744**：不必要的类型转换（`as` 链路过深）——用类型守卫（`type guard`）收窄类型
- 🆕【强制】**S6582**：可选链冗余调用（`a?.b?.c` 中 a 已非空）——移除冗余 `?.`
- 🆕【强制】**S7735**：useEffect 缺少依赖项 ——补全依赖数组（用 `ref` 持有最新闭包避免循环）
- 🆕【强制】**S6551**：使用 `for...in` 遍历对象 ——改用 `Object.keys/values/entries`
- 🆕【强制】**S1874**：使用 `@deprecated` 标记替代直接删除的 API ——导出前标注 deprecated

**实战案例参考**：
- `SheetTabs.tsx` 拆分 `TabItem` 为 `ThumbnailTab` + `StandardTab` 修复 S3776 + S6767
- `Chatbot/index.tsx` 用 `createSendCompleteHandler` 工厂函数修复 S2004 + S6819
- `ItemList.tsx` `div+onClick` 改 `<button>` 修复 S6844
- `Evaluations/index.tsx` 提取 `resolveActionDisplay` 修复 S3776

### 13. PWA 配置 🆕v2.0

- 【强制】`vite.config.ts` 配置 `base: '/app/'`
- 【强制】构建产物输出到 `../src/xianyu_hunter/web/static/spa`
- 【强制】`VitePWA` `registerType: 'prompt'`
- 【强制】`manifest.theme_color: '#FF6200'`
- 【强制】`workbox.maximumFileSizeToCacheOnBytes: 4MB`
- 【强制】`runtimeCaching` 排除以下路径（不缓存）：
  - `/api/events/stream`
  - `/api/auth/`
  - `/api/export/`
- 【强制】`devOptions.enabled: false`

### 14. 三处映射同步 🆕v2.0

- 【强制】新增页面必须同步维护三处：
  1. `frontend/src/App.tsx`：路由声明
  2. `frontend/src/components/layout/MainLayout.tsx`：`menuItems` 菜单注册
  3. `frontend/src/components/SheetWorkspace/sheetRegistry.tsx`：path → component 映射
- 【强制】菜单三级分组（Command Palette 支持）

### 15. SSE 重连 🆕v2.0

- 【强制】SSE lastEventId 持久化重连（`frontend/src/pages/Dashboard/index.tsx`）
- 【强制】`SSE_LAST_EVENT_ID_KEY = 'xh_sse_last_event_id'` 模块级常量
- 【强制】断线重连从 localStorage 读取 lastEventId 作为 `?last_event_id=` 参数
- 【强制】`handleSseAppEvent` 模块级函数（SonarQube S2004）
- 【强制】**SSE 断线重连三要素**（缺一不可）：
  1. **lastEventId 记录**：`app_event` 回调中 `e.lastEventId`（MessageEvent 属性，非 EventSource）保存到变量
  2. **重连传递 last_event_id**：URL 拼接 `?last_event_id=${lastEventId}`，启用后端回放断线期间事件
  3. **visibilitychange 监听**：页面恢复可见且 SSE 已断开时自动重建连接（解决页面不可见时 selectedTask 变化导致 SSE 永久断开的问题）
- 【强制】SSE error 重连必须有次数上限（`MAX_RECONNECT`，通过配置管理，默认 10），超限后放弃 SSE 退化为轮询
- 【强制】页面恢复可见时重置重连计数（`reconnectAttempts = 0`），给新一轮重连机会
- 【强制】`visibilitychange` 事件监听必须在 useEffect cleanup 中移除（`document.removeEventListener`），避免内存泄漏
- 【常见陷阱】`lastEventId` 是 `MessageEvent` 的属性（`e.lastEventId`），不是 `EventSource` 的属性（`es.lastEventId` 不存在）
- 🆕v4.1【强制】**F-REVIEW-SSE-ERROR-HANDLING：SSE 错误事件状态码分类处理**
  - SSE 流中收到 `stage='error'` 事件时，必须按 `status` 字段分类处理（状态码与文案映射在 `config.yaml` 的 `sse_error_status_mapping` 节点管理）：
    - `503/504`：稍后重试提示（如"网络繁忙，请稍后重试"），不阻塞 UI
    - `401/403`：需用户介入（如"登录已过期，请前往「反爬登录管理」重新登录"）+ 显式"前往登录"跳转按钮（用 `useNavigate` 跳转到 `/login` 或反爬登录页）
    - `502`：需重启服务提示（如"浏览器连接断开，请重启服务"）
  - **禁止**：将 `stage='done'` + 0 条结果与 `stage='error'` 混为一谈（前者是"真的没货"，后者是"业务异常"）
  - **禁止**：吞掉 `stage='error'` 事件只展示通用错误（如只显示"预览失败"而无具体指引）
  - **判断信号**：组件消费 SSE 流（如 `useAutoLiveSearch.ts` 的 `live` 方法回调）→ 必须显式处理 `stage='error'` 分支
  - **通过示例**：
    ```typescript
    if (data.stage === 'error') {
      const status = data.status ?? 500
      if (status === 401 || status === 403) {
        setErrorMsg(data.detail ?? '登录已过期')
        setShowReLoginBtn(true)  // 显示"前往登录"按钮
      } else if (status === 502) {
        setErrorMsg(data.detail ?? '服务异常，请重启')
      } else {
        setErrorMsg(data.detail ?? '网络繁忙，请稍后重试')
      }
      return
    }
    ```
  - **不通过示例**：
    ```typescript
    if (data.stage === 'done') { /* 渲染结果 */ }
    // 未处理 stage='error'，导致 SSE 错误事件被忽略或走默认分支
    ```

### 16. 性能评审

- 【强制】复杂 props（对象、数组、Map）使用 `useMemo` 保证引用稳定
- 【强制】回调函数使用 `useCallback` 避免子组件不必要渲染
- 【强制】`useEffect` 依赖数组完整性（避免遗漏依赖导致 stale closure）
- 【强制】列表渲染使用稳定的 `key`（**禁止**用 index）
- 【强制】大列表虚拟化（`react-window`/`react-virtualized`）
- 【禁止】在 render 内创建新对象/数组
- 【强制】React Flow 数据使用 `useNodes`/`useEdges`（不手动拉取）
- 【强制】echarts 5.5 按需导入
- 【强制】网络重连（SSE/WebSocket/API 重试）必须有最大次数限制，超限后退化为降级方案（如轮询）
- 【强制】无限重连循环（`setTimeout(connect, N)` 无计数器）视为资源浪费风险

### 17. 可访问性评审

- 【强制】交互元素（特别是图标按钮）必须有 `aria-label`
- 【强制】表单控件必须有 `label` 关联
- 【推荐】颜色对比度达标（WCAG AA）
- 【推荐】键盘导航支持（Tab 顺序、Enter/Space 触发）
- 【推荐】屏幕阅读器友好性（语义化标签、`role` 属性）
- 🆕v4.0【强制】**外部链接安全**：`target="_blank"` 必须配 `rel="noopener noreferrer"`（防 `window.opener` 钓鱼 + 不泄露 Referer）

### 18. 闲鱼项目规范 🆕v2.0

- 【强制】UI 组件库：Ant Design 5.21
- 【强制】视觉风格（来自 user_profile.md）：干净明亮的扁平化设计语言，清新治愈的 macaron 配色，浅粉/浅青为主，大圆角，轻透磨砂玻璃质感
- 【强制】API 出口统一：`frontend/src/api/index.ts` 用 `export *` 聚合
- 【强制】测试框架：Vitest 4.1 + @testing-library/react 16.3 + jsdom 29.1
- 【强制】测试文件位置：组件/hook 同级目录 `__tests__/<Component>.test.tsx`
- 【强制】构建命令：`npm run build`（`tsc -b && vite build`）
- 【强制】类型检查：`npx tsc -b`（构建前强制类型检查）
- 【强制】Dev 命令：`npm run dev`（HMR，端口 5173）
- 【强制】测试命令：`npx vitest run`
- 【推荐】抽象模式：纯函数 + 组件 + 常量分层（如 `resolveActionDisplay` + `ActionPlaceholder` + `ACTION_PLACEHOLDER_TEXT`）
- 🆕v4.0【强制】**显式样式优于隐式间距**：图标+文字、按钮+文字等内联元素间距用显式 `style={{ marginRight: N }}` 或 `Space` 组件，**禁止**依赖 JSX 空格渲染间距
- 🆕v4.0【强制】**注释与代码一致性**：注释必须与代码逻辑严格一致，禁止误导性注释；防御性说明需明确标注是"防御性"而非"必需"
- 🆕v4.7【强制】**F-REVIEW-REUSE-PATTERN-FRONTEND：复用既有模式原则（前端侧）**
  - 新增前端功能前必须 grep 项目内相似实现，复用既有 Hook/工具函数/模式，**禁止**重新实现已有功能
  - **判断信号**：新增 Hook/组件/工具函数前 → grep 项目内是否已有相似实现 → 若有则复用或扩展 → 若无则评估是否可抽取为通用工具
  - **修复模式**（复用检查流程）：
    ```typescript
    // 新增"采集评估明细"功能前，先 grep 项目内相似实现
    // grep "message.loading" → 发现多处使用 message.loading + try/catch + message.success/error 模式
    // 复用既有模式：
    const hide = message.loading('正在采集...', 0)  // ✅ 复用 message.loading 模式
    try {
      // ...
    } catch (err) {
      hide()
      message.error(...)  // ✅ 复用 message.error 模式
    }
    // 新增页面路由前，先 grep "lazyRetry" → 复用既有懒加载模式
    const EvalDetail = lazy(() => lazyRetry(() => import('./pages/EvalDetail')))  // ✅ 复用 lazyRetry
    // 新增深拷贝需求前，先 grep "JSON.parse" → 发现应改为 structuredClone（SonarQube S7784）
    const cloned = structuredClone(data)  // ✅ 复用 structuredClone 模式
    ```
  - **配置参数**：`search_keywords`（搜索关键词列表，如 `message.loading` / `lazyRetry` / `structuredClone` / `useDebounce` / `useEventSource`）、`similarity_threshold`（相似度阈值，默认 0.7）、`reuse_priority`（复用优先级：项目内既有 Hook > 工具函数 > 模式 > 标准库 > 第三方库）在 `config.yaml` 的 `reuse_pattern_frontend` 节点管理
  - **关键约束**：
    - 新增 Hook 前必须 grep `use*.ts` 确认无相似实现
    - 新增工具函数前必须 grep `utils/` / `helpers/` 确认无相似实现
    - 强行复用导致耦合 > 重新实现的成本时，允许重新实现但需注释说明
    - 复用 Ant Design 组件时必须确认版本兼容性（项目用 AntD 5.21）
  - **适用**：新增前端功能（Hook/组件/工具函数/模式）前的预检查
  - **不适用**：首次实现的基础设施代码（无既有实现可复用）、业务逻辑差异较大的场景（强行复用会导致耦合）
  - **历史教训**：评估明细采集按钮未复用项目内既有的 `message.loading` + `try/catch` + `message.success/error` 三态反馈模式，导致无用户反馈。修复后复用既有模式实现三态反馈
- 🆕v4.19【强制】**F-REVIEW-SCHEDULER-STATUS-DISPLAY：调度器状态展示规范**
  - 前端"关于"页面必须展示关键调度器启动状态，调用 `/api/about` 端点获取 `schedulers: [{name, enabled, interval_minutes, last_run_at}]` 数组并渲染为状态卡片，未启动的调度器必须显示红色"未启动"标签 + 启动命令提示，启动的调度器显示绿色"运行中"标签 + 间隔 + 最近运行时间，调度器状态变更必须通过 SSE 实时推送或定时轮询刷新
  - **核心机制**（审查时必须理解）：
    - 后端关键调度器（如 `BatchRefreshScheduler`）影响业务正确性，但用户无法从终端日志感知启动状态
    - 前端"关于"页面是用户感知系统运行状态的唯一入口，必须展示调度器状态
    - 未启动调度器必须用红色标签醒目标识 + 显示启动命令（如 `python -m xianyu_hunter web --with-scheduler`）
    - 启动的调度器显示绿色"运行中"标签 + 间隔（如"每 30 分钟"）+ 最近运行时间
    - 调度器状态可能随启动参数/环境变量变化，必须通过 SSE 推送或定时轮询（间隔在 config.yaml 管理）刷新
  - **判断信号**：
    - `grep "schedulers" frontend/src/` 未发现消费 `/api/about` 返回的 `schedulers` 字段 → 视为违规
    - "关于"页面只有版本号/构建时间，无调度器状态展示 → 视为违规
    - 调度器状态用单一布尔值显示（无"未启动"vs"运行中"区分）→ 视为可疑
    - 未启动调度器无启动命令提示 → 视为可疑
    - 调度器状态无定时刷新（仅页面加载时拉一次）→ 视为可疑
  - **修复模式**：
    ```typescript
    // ✅ types.ts 声明调度器状态类型
    interface SchedulerStatus {
      name: string
      enabled: boolean
      interval_minutes: number
      last_run_at: string | null  // ISO 时间字符串，null 表示从未运行
    }

    // ✅ About 页面渲染调度器状态卡片
    function SchedulerStatusCard({ scheduler }: { scheduler: SchedulerStatus }) {
      return (
        <Card size="small" title={scheduler.name}>
          <Space>
            <Tag color={scheduler.enabled ? 'success' : 'error'}>
              {scheduler.enabled ? '运行中' : '未启动'}
            </Tag>
            <Text type="secondary">每 {scheduler.interval_minutes} 分钟</Text>
            {scheduler.last_run_at && (
              <Text type="secondary">
                最近运行：{new Date(scheduler.last_run_at).toLocaleString()}
              </Text>
            )}
          </Space>
          {!scheduler.enabled && (
            <Alert
              type="warning"
              showIcon
              message="该调度器未启动，相关功能将不生效"
              description={
                <Text code>python -m xianyu_hunter web --with-scheduler</Text>
              }
            />
          )}
        </Card>
      )
    }

    // ✅ 定时轮询刷新（间隔从 config 读取）
    const POLL_INTERVAL = 30000  // 30s，应从 config.yaml 读取
    useEffect(() => {
      const timer = setInterval(() => aboutApi.get().then(setAboutInfo), POLL_INTERVAL)
      return () => clearInterval(timer)
    }, [])

    // ❌ 错误：未展示调度器状态，用户无法感知启动情况
    // function AboutPage() {
    //   return <Statistic title="系统版本" value={version} />  // 只有版本号
    // }
    ```
  - **配置参数**：`scheduler_status_display.enabled`（默认 `true`）、`scheduler_status_display.require_about_endpoint_consumption`（默认 `true`，前端必须消费 `/api/about` 的 `schedulers` 字段）、`scheduler_status_display.require_disabled_hint`（默认 `true`，未启动调度器必须显示启动命令提示）、`scheduler_status_display.require_realtime_refresh`（默认 `true`，必须通过 SSE 或定时轮询刷新）、`scheduler_status_display.refresh_interval_ms`（默认 `30000`，轮询间隔毫秒）、`scheduler_status_display.status_color_mapping`（默认 `{enabled: 'success', disabled: 'error'}`）、`scheduler_status_display.startup_command_hint`（默认 `'python -m xianyu_hunter web --with-scheduler'`，未启动时显示的启动命令）在 `config.yaml` 的 `scheduler_status_display` 节点管理
  - **适用**：前端"关于"页面/系统信息页面；展示后端调度器运行状态；用户需要感知后台任务运行情况的场景
  - **不适用**：纯前端调度器（如 `setInterval` 无后端对应）；调试用页面（非用户面向）；无调度器的简单应用
  - **历史教训**：用户启动 web 服务时未加 `--with-scheduler` 参数，`BatchRefreshScheduler` 永远不运行，但前端"关于"页面只显示版本号，用户无法感知调度器未启动。导致商品 1058031608014 实际已售但数据库 `is_sold=0` 长期不刷新，用户看到已售商品仍被推荐。修复后前端"关于"页面展示调度器状态卡片，未启动时显示红色标签 + 启动命令提示

### 19. 跨组件状态同步与死代码检测 🆕v4.3

- 【强制】**F-REVIEW-DEAD-CODE：长期存活对象禁止赋值给局部变量**：`new Proxy()` / `new MutationObserver()` / `new IntersectionObserver()` 等需要长期存活的监听器/观察者，必须赋值给实例属性（`this._observer`）或模块级变量，禁止赋值给局部变量后丢弃
  - **判断信号**：`var xxx = new Proxy(...)` / `const xxx = new MutationObserver(...)` 中 xxx 是局部变量且未被返回/导出
  - **修复模式**：赋值给实例属性或模块级变量，确保引用保留
  - **历史教训**：`awsc_spoof.py` 的 `var baxiaProxy = new Proxy(window.__baxia__, {...})` 赋值给局部变量后从未使用，验证码触发事件永远不会被派发

- 【强制】**F-REVIEW-TRY-FINALLY-INIT：try/finally 变量初始化**：`try/finally` 块中 `finally` 引用的变量必须在 `try` 之前初始化为 `null`/`undefined`，确保 `try` 内赋值前抛异常时 `finally` 不会报 `ReferenceError`
  - **判断信号**：`try { const page = await create() } finally { page.close() }` 中 page 在 try 内声明
  - **修复模式**：`let page = null; try { page = await create() } finally { if (page) await page.close() }`

- 【强制】**F-REVIEW-CROSS-COMPONENT-STATE：跨组件状态同步**：多个组件/模块对同一概念（如"会话有效性"、"登录状态"）做判断时，状态变更必须双向同步——状态变更方通知其他组件、查询方额外检查其他组件的最新状态
  - **判断信号**：两个以上组件各自独立判断"会话有效性"/"登录状态"等同一概念（如健康检查器检查 Cookie 存在性 + worker 检查 API 响应 RGV587_ERROR）
  - **修复模式**：前端 store 状态变更时通过事件/回调通知其他组件；查询方在判断时额外检查其他来源的状态标志
  - **不适用**：单组件内部状态、无跨组件依赖的独立判断

- 【强制】**F-REVIEW-ERROR-HINT-ROUTABLE：错误提示路由可操作性**：面向用户的错误提示中引用的路由路径必须在前端路由表中已注册，引用的 API 端点必须在后端已实现
  - **判断信号**：错误信息中包含 `/api/xxx` 或 `/page-path` 引用
  - **修复模式**：提示中只引用已注册的路由和已实现的端点；提供具体的可操作修复指引（如"请点击「反爬登录管理」重新初始化"而非"请调用 /api/xxx/configure"）

### 20. API 数据源一致性与类型契约对齐 🆕v4.4

- 【强制】**F-REVIEW-API-DATA-SOURCE-CONSISTENCY：API 响应消费一致性**：同一 API 响应被多处组件消费时，必须共用同一 fetch 结果（通过 store/context 缓存），禁止各组件独立调用导致数据不一致；后端返回新增字段时所有消费方必须同步更新
  - 检查清单（参数在 `config.yaml` 的 `api_data_source_consistency` 节点管理）：
    - `enabled`：默认 `true`
    - `shared_fetch_apis`：默认 `["/api/stats", "/api/prices/histogram", "/api/config"]`，需共享 fetch 的端点
    - `require_type_sync`：默认 `true`，后端新增字段时前端 types.ts 必须同步
  - **判断信号**：两个以上组件各自调用同一 `priceApi.histogram()` → 必须改为共享 fetch；后端 summary 新增 `task_price_range` 字段但前端 `HistogramData` 类型未声明 → 类型契约断裂
  - **修复模式**：将 fetch 结果存入 store/context，各组件从 store 读取；后端新增字段后立即在 `api/types.ts` 同步声明并注释字段语义
  - **适用**：仪表盘多卡片消费同一 API、配置页与业务页共用配置数据、后端响应结构变更
  - **不适用**：独立页面的独立 API 调用、明确需要实时刷新的独立请求
  - **历史教训**：后端 `price_histogram.py` summary 新增 `task_price_range` 字段，若前端 `HistogramData` 类型未同步声明，TS 严格模式下访问 `histogram.summary.task_price_range` 会类型报错；`PriceStrategy.tsx` 独立调用 `priceApi.histogram()` 且检查 `data?.counts`（不存在的字段），导致始终走 catch 降级到模拟数据

- 【强制】**F-REVIEW-TYPE-CONTRACT-ALIGN：前后端类型契约对齐**：后端 Pydantic 模型/响应体新增或修改字段时，前端 `api/types.ts` 必须同步更新；可选字段用 `field?: T`，可空字段用 `field: T | null`
  - 检查清单（参数在 `config.yaml` 的 `type_contract_align` 节点管理）：
    - `enabled`：默认 `true`
    - `type_file_path`：默认 `"frontend/src/api/types.ts"`
    - `optional_vs_null`：默认 `"optional"`，优先用 `field?: T` 而非 `field: T | null`
  - **判断信号**：后端响应含 `task_price_range: {min_price: float | null, max_price: float | null}` 但前端类型未声明 → 必须补齐；前端用 `as any` 绕过类型检查 → 必须改为精确类型
  - **修复模式**：后端新增字段后，在 `types.ts` 对应接口同步声明，注释字段语义和可空场景；前端消费新增字段时先做 null 检查
  - **适用**：所有后端响应结构变更、新增 API 端点、字段语义变化
  - **不适用**：内部工具函数返回值、纯前端计算字段

- 【建议】**F-REVIEW-ERROR-CODE-CONSUMPTION：error_code 消费决策**：后端错误响应含 `error_code` 时，前端必须根据 error_code 做重试/降级决策，而非统一展示错误信息
  - 检查清单（参数在 `config.yaml` 的 `error_code_consumption` 节点管理）：
    - `enabled`：默认 `true`
    - `retryable_codes`：默认 `["network_error", "timeout", "rate_limited", "service_unavailable"]`
    - `non_retryable_codes`：默认 `["item_not_found", "invalid_params", "auth_failed", "business_rule"]`
  - **判断信号**：catch 块统一 `message.error(extractApiError(e))` 但未检查 `error_code` → 可重试错误未提供重试入口
  - **修复模式**：解析响应体 `error_code`，可重试错误显示"重试"按钮，不可重试错误显示具体原因
  - **适用**：批量操作错误处理、需用户决策重试的场景
  - **不适用**：简单表单提交错误（用 extractApiError 统一处理即可）

- 🆕v4.25【强制】**F-REVIEW-ERROR-HANDLING-CONSISTENCY：错误处理一致性检查**
  - 维度：20 错误提示语义 + 配置链路
  - 严重等级：error
  - **检查点**：API 调用的 catch 块是否使用 `extractApiError` 提取具体错误信息
  - **判定标准**：**禁止** `message.error('保存失败')` / `message.error('操作失败')` 等无具体信息的错误提示。必须使用 `extractApiError(e)` 提取状态码 + 详情，显示时长不少于 `error_display_duration_sec`（默认 5 秒）
  - **检查范围**：所有含 try/catch 的 API 调用
  - **核心机制**（审查时必须理解）：
    - `extractApiError(e)` 工具函数位于 `frontend/src/utils/apiError.ts`，能从 axios 错误中提取 `error.response.status` + `error.response.data.detail` + `error.response.data.message` 等字段，组合成可读的错误信息
    - 裸 `message.error('保存失败')` 让用户无法判断失败原因（网络错误/参数错误/权限不足/服务异常），无法自助排查
    - 显示时长 < 5 秒会导致用户来不及读完错误信息就被吞掉，特别是包含状态码 + 详情的长文本
    - 错误信息应包含：HTTP 状态码（401/403/404/500/502/503/504）+ 后端返回的具体 detail（如"商品不存在"/"评分必须大于 0"/"权限不足"）
  - **判断信号**（grep 检测）：
    - `grep -nE "message\.error\('保存失败'\)|message\.error\('操作失败'\)|message\.error\('加载失败'\)" frontend/src/pages/**/*.tsx` 命中 → 违规
    - `grep -nE "catch \(.*\) \{ message\.error\('" frontend/src/pages/**/*.tsx` 命中 → 检查是否调用 `extractApiError`
    - `grep -nE "message\.error\(.*\)" frontend/src/pages/**/*.tsx | Select-String -NotMatch "extractApiError"` 命中 → 检查 message.error 是否包含具体信息
    - `grep -nE "message\.error\([^,]+\)$" frontend/src/pages/**/*.tsx` 命中 → 检查是否省略了 duration 参数（应 >= 5 秒）
    - 用户反馈"保存失败但不知道原因" → 必查 catch 块是否用 extractApiError
  - **修复模式**：
    ```typescript
    // ✅ 正确：用 extractApiError 提取具体错误，显示 5 秒
    import { extractApiError } from '@/utils/apiError'

    try {
      await taskApi.update(taskId, payload)
      message.success('保存成功')
    } catch (e) {
      message.error(extractApiError(e), 5)  // 显示 "400: search_config 字段必须是对象"
    }

    // ❌ 错误：无具体信息的错误提示
    try {
      await taskApi.update(taskId, payload)
    } catch {
      message.error('保存失败')  // 用户不知道为什么失败
    }

    // ❌ 错误：显示时长过短
    catch (e) {
      message.error(extractApiError(e))  // 默认 3 秒，长文本来不及读
    }

    // ❌ 错误：直接用 error.message 丢失状态码
    catch (e) {
      message.error(e.message)  // 只有 "Request failed with status code 400"，没有 detail
    }
    ```
  - **配置参数**：`frontend_error_handling` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `error_display_duration_sec`（默认 `5`，错误提示最小显示时长，秒）
    - `required_error_extractor`（默认 `"extractApiError"`，强制使用的错误提取工具函数名）
    - `forbidden_error_patterns`（默认 `["保存失败", "操作失败", "加载失败", "提交失败", "请求失败"]`，禁止使用的笼统错误文案列表）
    - `required_fields_in_message`（默认 `["status_code", "detail"]`，错误信息中必须包含的字段）
    - `extractor_function_path`（默认 `"frontend/src/utils/apiError.ts"`，extractApiError 函数所在路径）
    - `detection_signals`（默认 `["message.error('", "catch (e) { message.error", "message.error(e.message)"]`，触发检查的代码模式）
  - **适用场景**：所有含 try/catch 的 API 调用（保存/更新/删除/查询/批量操作/SSE 错误处理）
  - **不适用场景**：非 API 错误（如本地计算错误、表单验证错误、本地 storage 读写错误）；开发环境调试信息（`console.error`）；用户主动取消操作（`message.info('已取消')`）；表单客户端校验错误（`form.setFields([{ errors: [...] }])`）
  - **历史教训**：任务级配置覆盖功能开发时，保存接口 catch 块用 `message.error('保存失败')`，用户反馈"清除覆盖不生效"但前端只显示"保存失败"，无法定位是 400（参数错误）还是 500（服务异常）还是 401（登录过期）。修复方式：改为 `message.error(extractApiError(e), 5)`，显示具体状态码 + 后端 detail（如"400: search_config 必须显式传 null 才能清除覆盖"），用户能自助排查
  - **对应后端原则**：后端 API 必须返回结构化错误响应（含 `detail` + `error_code` + `status_code`），禁止只返回 `{"detail": "Internal Server Error"}`，详见 `xianyu-backend-code-review` 的 `B-REVIEW-ERROR-RESPONSE-STRUCTURE`（如有）

### 25. 端到端失败原因链前端侧同步原则 🆕v4.27

基于"Failed to collect item detail: page unavailable or login expired"根因复盘（代码被回退 + 服务未重启双重原因导致修复未生效），系统化梳理前端在端到端失败原因链中的同步原则。本维度不直接处理后端失败原因传递/数据完整性预检/合并写入等后端逻辑，但前端作为错误展示方与 API 调用方，必须遵循以下 3 项同步原则，确保前后端错误处理契约一致。

- 🆕v4.27【强制】**F-REVIEW-ERROR-CODE-BRANCH：错误展示按 error_code 字段分支**
  - 维度：25 端到端失败原因链前端侧同步原则
  - 严重等级：error
  - **检查点**：前端 catch 块中处理后端错误响应时，是否按 `error_code` 字段分支决策（重试/降级/提示用户操作）而非按文案子串判断
  - **判定标准**：**禁止** `if (msg.includes('expired'))` / `if (detail.indexOf('unavailable') !== -1)` / `if (err.message === '页面不可用')` 等子串匹配模式。必须改为 `switch (err.error_code) { case 'token_invalid': ...; case 'page_unavailable': ...; case 'rate_limited': ... }`，分支逻辑与后端 `failure_reason_propagation.reason_enum` 一一对应（命名风格以后端为准，统一 lower_snake_case）
  - **检查范围**：所有消费后端错误响应的前端 catch 块（API 调用、SSE 错误事件、批量操作错误处理）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.27.0 起 HTTPException 的 detail 改为结构化 `{'error_code': 'XXX', 'message': '...'}`，禁止用字符串子串做日志降级 marker（后端 B-REVIEW-FAILURE-REASON-PROPAGATION）
    - 前端若按文案子串判断，后端调整文案后前端逻辑会失效（如后端把"login expired"改为"会话已过期"，前端的 `includes('expired')` 不再命中）
    - error_code 是稳定的契约接口，文案是可变的人类可读描述，前端必须依赖前者而非后者
    - 与 F-REVIEW-ERROR-CODE-CONSUMPTION（维度 20）配合：F-REVIEW-ERROR-CODE-CONSUMPTION 关注"是否决策重试/降级"，F-REVIEW-ERROR-CODE-BRANCH 关注"如何识别错误类型（按 error_code 而非文案子串）"
  - **判断信号**（grep 检测）：
    - `grep -nE "if\s*\(\s*\w+\.(message|detail|msg)\.includes\(" frontend/src/**/*.tsx` 命中 → 检查是否在判断后端错误类型
    - `grep -nE "\.(indexOf|search|match)\(['\"](expired|unavailable|rate limited|page unavailable|login expired)" frontend/src/**/*.tsx` 命中 → 违规（按文案子串判断错误类型）
    - `grep -nE "switch\s*\(\s*\w+\.error_code\s*\)" frontend/src/**/*.tsx` 未命中 → 检查是否有按 error_code 分支的实现
    - 用户反馈"后端改了错误文案后前端行为异常" → 必查前端是否按文案子串判断错误类型
  - **修复模式**：
    ```typescript
    // ✅ 正确：按 error_code 字段分支
    import type { ApiErrorResponse } from '@/api/types'

    try {
      await collectionApi.collectItem(itemId)
    } catch (e) {
      const err = e.response?.data as ApiErrorResponse
      switch (err?.error_code) {
        case 'token_invalid':
          message.warning('令牌已失效，请重新获取')
          break
        case 'page_unavailable':
          message.error('页面不可用，可能需要重新登录')
          break
        case 'rate_limited':
          message.warning('操作过于频繁，请稍后重试')
          break
        default:
          message.error(extractApiError(e), 5)
      }
    }

    // ❌ 错误：按文案子串判断（后端改文案后失效）
    catch (e) {
      const msg = e.response?.data?.detail || e.message
      if (msg.includes('expired')) {
        message.warning('登录已过期')
      } else if (msg.indexOf('unavailable') !== -1) {
        message.error('页面不可用')
      } else {
        message.error('操作失败')
      }
    }
    ```
  - **配置参数**：`failure_reason_chain_frontend` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `required_error_code_field`（默认 `"error_code"`，后端错误响应中必须包含的错误码字段名）
    - `forbidden_substring_markers`（默认 `["expired", "unavailable", "rate limited", "page unavailable", "login expired"]`，禁止用于判断错误类型的文案子串列表）
    - `required_branch_pattern`（默认 `"switch.*error_code"`，必须使用的分支模式正则）
    - `backend_reason_enum_source`（默认 `"xianyu-backend-code-review.failure_reason_propagation.reason_enum"`，后端 reason 枚举来源，确保前后端契约对齐）
    - `detection_signals`（默认 `[".includes('expired'", ".indexOf('unavailable'", ".match(/rate limited/i)"]`，触发检查的代码模式）
  - **适用场景**：所有消费后端错误响应的前端 catch 块（API 调用/SSE 错误事件/批量操作错误处理）；后端已实现结构化 error_code 字段的接口；需要按错误类型做不同 UI 反馈的场景（重试/降级/引导用户操作）
  - **不适用场景**：纯前端错误（表单校验错误、本地计算错误、本地 storage 读写错误）；后端未实现 error_code 字段的旧接口（应推动后端补齐）；网络层错误（如 axios 超时无 response.body，应按 F-REVIEW-ERROR-CONTRACT-TIMEOUT 用 `isAxiosTimeout()` 识别）
  - **历史教训**：闲鱼详情采集接口返回 `{"detail": "Failed to collect item detail: page unavailable or login expired"}`，前端按 `detail.includes('expired')` 判断为"登录过期"引导用户重新登录，但实际根因可能是页面不可用（非登录问题）。后端将 detail 改为结构化 `{"error_code": "page_unavailable", "message": "..."}` 后，前端子串判断失效。修复方式：前端改为按 `error_code` 分支，与后端 reason_enum 一一对应
  - **对应后端原则**：后端必须返回结构化错误响应含 `error_code` 字段，禁止用字符串子串做日志降级 marker，详见 `xianyu-backend-code-review` v4.27.0 的 `B-REVIEW-FAILURE-REASON-PROPAGATION` / `B-REVIEW-ERROR-MESSAGE-CONSTANT`

- 🆕v4.27【强制】**F-REVIEW-PRECHECK-API-DELEGATION：数据完整性预检委托后端**
  - 维度：25 端到端失败原因链前端侧同步原则
  - 严重等级：warning
  - **检查点**：前端调用后端 API 前若需预检数据完整性（如 cookie 数量是否足够、关键字段是否非空），是否调用后端预检端点而非前端自行判断
  - **判定标准**：**禁止**前端自行实现数据完整性预检逻辑（如 `if (cookies.length < 10)` / `if (!cookie.token)` / `if (!item.title || !item.price)`）。必须调用后端预检端点（如 `/api/cookies/precheck` / `/api/items/<id>/precheck`）获取预检结果，前端仅根据预检结果的 `passed` 字段决定是否继续调用主接口
  - **检查范围**：所有调用需预检的后端 API 的前端代码路径（采集前预检 cookie、提交前预检表单完整性、批量操作前预检数据状态）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.27.0 起数据完整性预检方法签名统一为 `async def _check_xxx_completeness(self) -> str | None`，返回 None 表示通过、字符串表示错误描述（后端 B-REVIEW-DATA-COMPLETENESS-PRECHECK）
    - 后端预检使用双阈值 AND 判断（总数 + 关键项命中数），前端不具备后端业务规则的完整上下文（如哪些字段是"关键项"、阈值由业务场景决定）
    - 前端自行判断会与后端预检逻辑不一致，导致前端通过预检但后端拒绝（或反之）
    - 前端预检的职责是"调用预检端点 + 展示预检结果 + 引导用户修复"，不是"实现预检逻辑"
  - **判断信号**（grep 检测）：
    - `grep -nE "if\s+\(?\s*\w+\.length\s*<\s*\d+" frontend/src/**/*.tsx` 命中 → 检查是否在判断后端数据完整性
    - `grep -nE "if\s+\(?\s*!\w+\.(token|cookies|title|price)" frontend/src/**/*.tsx` 命中 → 检查是否在前端判断后端字段完整性
    - `grep -nE "/api/\w+/precheck" frontend/src/api/**/*.ts` 未命中 → 检查是否有调用后端预检端点
    - 用户反馈"前端预检通过但后端拒绝" → 必查前端是否自行实现预检逻辑
  - **修复模式**：
    ```typescript
    // ✅ 正确：调用后端预检端点
    try {
      const precheck = await collectionApi.precheckItem(itemId)
      if (!precheck.passed) {
        message.warning(precheck.reason)  // 如 "cookie 数量不足（4/22），请重新登录"
        return
      }
      await collectionApi.collectItem(itemId)  // 预检通过才调用主接口
    } catch (e) {
      message.error(extractApiError(e), 5)
    }

    // ❌ 错误：前端自行判断（与后端预检逻辑可能不一致）
    const cookies = await cookieApi.list()
    if (cookies.length < 10) {  // 阈值硬编码，与后端不一致
      message.warning('cookie 不足，请重新登录')
      return
    }
    await collectionApi.collectItem(itemId)
    ```
  - **配置参数**：`failure_reason_chain_frontend` 节点（在 `config.yaml` 管理，不硬编码）：
    - `precheck_endpoint_pattern`（默认 `"/api/<resource>/precheck"`，后端预检端点的 URL 模式）
    - `precheck_result_field`（默认 `"passed"`，预检结果中是否通过的字段名）
    - `precheck_reason_field`（默认 `"reason"`，预检结果中失败原因的字段名）
    - `forbidden_frontend_precheck_patterns`（默认 `["length < \\d+", "!\\w+\\.token", "!\\w+\\.title"]`，禁止前端自行实现的预检模式）
    - `backend_precheck_method_source`（默认 `"xianyu-backend-code-review.data_completeness_precheck.method_name_pattern"`，后端预检方法来源，确保前后端契约对齐）
  - **适用场景**：调用需预检的后端 API（采集前预检 cookie、提交前预检表单、批量操作前预检数据状态）；后端已提供预检端点的接口；预检逻辑涉及业务规则（如哪些字段是关键项、阈值由业务场景决定）
  - **不适用场景**：纯前端表单校验（必填字段、格式校验、长度限制，用 antd Form rules 即可）；无需预检的简单查询接口（GET /api/items）；前端可独立判断的非业务规则（如"选择的批量操作数量是否超过 100"）
  - **历史教训**：闲鱼详情采集前前端自行判断 cookie 数量（`if (cookies.length < 4)`），但后端预检阈值是 22（关键 cookie 命中数），前端通过预检但后端仍返回 401。修复方式：前端改为调用 `/api/cookies/precheck` 端点，后端返回 `{"passed": false, "reason": "关键 cookie 命中数不足（4/12）"}`，前端展示原因并引导用户重新登录
  - **对应后端原则**：后端必须提供预检端点 + 预检方法签名统一为 `str | None` + 双阈值 AND 判断，详见 `xianyu-backend-code-review` v4.27.0 的 `B-REVIEW-DATA-COMPLETENESS-PRECHECK`

- 🆕v4.27【强制】**F-REVIEW-MOCK-FIELD-SET-SYNC：mock 数据完整字段集同步**
  - 维度：25 端到端失败原因链前端侧同步原则
  - 严重等级：warning
  - **检查点**：前端单元测试/集成测试的 mock 数据是否覆盖后端 Pydantic 模型的完整字段集，新增后端字段后前端 mock 是否同步补齐
  - **判定标准**：**禁止**前端 mock 数据仅包含测试用例当前需要的字段（如 `mockItem = { id: 1, title: 'test' }` 但后端 `Item` 模型有 12 个字段）。必须从后端 Pydantic 模型导出完整字段集作为 mock 基线，测试用例在基线上 override 需要的字段。新增后端字段后必须同步更新 mock 基线，避免"测试通过但生产环境类型不一致"
  - **检查范围**：所有前端单元测试/集成测试中的 mock 数据（API 响应 mock、组件 props mock、Zustand store 初始状态 mock）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.27.0 起测试 mock 必须覆盖完整字段集（后端 B-REVIEW-TEST-MOCK-SYNC），前端同样需要同步
    - 前端 mock 数据不完整会导致：测试通过但生产环境访问未 mock 的字段时类型报错；TS 类型检查可能因 mock 类型断言绕过；新增后端字段后前端未同步 mock 会导致测试用例无法覆盖新字段逻辑
    - 后端 Pydantic 模型是字段集的唯一真实来源（single source of truth），前端 mock 必须与之一致
    - 前端可通过 `api/types.ts` 中声明的接口反推字段集，但 `api/types.ts` 必须与后端 Pydantic 模型同步（F-REVIEW-TYPE-CONTRACT-ALIGN）
  - **判断信号**（grep 检测）：
    - `grep -nE "const\s+mock\w+\s*=\s*\{\s*id:" frontend/src/**/*.test.tsx` 命中 → 检查 mock 是否仅包含部分字段
    - `grep -nE "as\s+(Item|Task|Order|Config)\b" frontend/src/**/*.test.tsx` 命中 → 检查是否用 `as` 类型断言绕过字段完整性检查
    - 后端新增字段后 `git diff frontend/src/api/types.ts` 无变化 → 前端类型未同步，mock 必然也不完整
    - 用户反馈"测试通过但生产环境类型报错" → 必查前端 mock 是否覆盖完整字段集
  - **修复模式**：
    ```typescript
    // ✅ 正确：从完整字段集基线 override
    // frontend/src/test/mocks/itemMocks.ts
    import type { Item } from '@/api/types'

    // 完整字段集基线（与后端 Item Pydantic 模型一一对应）
    export const mockItemBaseline: Item = {
      id: 1,
      title: 'test item',
      price: 100,
      description: '',
      seller_id: 'seller_001',
      status: 'active',
      created_at: '2026-07-05T10:00:00Z',
      updated_at: '2026-07-05T10:00:00Z',
      // ... 所有后端 Item 模型字段
    }

    // 测试用例在基线上 override 需要的字段
    const mockItem: Item = { ...mockItemBaseline, status: 'completed' }

    // ❌ 错误：仅包含测试用例当前需要的字段
    const mockItem = { id: 1, title: 'test' } as Item  // as 绕过类型检查
    ```
  - **配置参数**：`failure_reason_chain_frontend` 节点（在 `config.yaml` 管理，不硬编码）：
    - `mock_field_set_source`（默认 `"backend_pydantic_model"`，mock 字段集的真实来源）
    - `require_baseline_file`（默认 `true`，是否要求集中管理 mock 基线文件）
    - `baseline_file_path`（默认 `"frontend/src/test/mocks/"`，mock 基线文件目录）
    - `forbidden_partial_mock_patterns`（默认 `["as\\s+(Item|Task|Order|Config)\\b", "const\\s+mock\\w+\\s*=\\s*\\{\\s*id:"]`，禁止的部分 mock 模式）
    - `backend_mock_sync_source`（默认 `"xianyu-backend-code-review.test_mock_synchronization.scenario_full_field_sets"`，后端 mock 字段集来源，确保前后端 mock 一致）
    - `detection_signals`（默认 `["as Item", "as Task", "const mock.*=.*{id:"]`，触发检查的代码模式）
  - **适用场景**：前端单元测试/集成测试中的 mock 数据；后端 Pydantic 模型新增字段后前端 mock 同步；TS 严格模式下需要 mock 数据类型完整才能通过编译的场景
  - **不适用场景**：纯前端工具函数测试（无后端模型对应）；只测试组件渲染逻辑的 storybook 故事（可仅传必要 props）；快速原型验证阶段的临时 mock（但需在 PR 前补齐）
  - **历史教训**：闲鱼详情采集接口新增 `failure_reason` 字段后，前端测试 mock 未同步补齐，导致前端 catch 块访问 `err.failure_reason` 时在测试环境为 `undefined`，测试通过但生产环境逻辑分支未覆盖。修复方式：建立 `frontend/src/test/mocks/` 目录集中管理 mock 基线，新增后端字段后同步更新基线文件
  - **对应后端原则**：后端测试 mock 必须覆盖完整字段集 + 集中管理，详见 `xianyu-backend-code-review` v4.27.0 的 `B-REVIEW-TEST-MOCK-SYNC`

### 27. 业务关键字常量集中管理与字段名大小写敏感 🆕v4.31

基于 2026-07-05 解决的 3 类前端反模式复盘（业务文案硬编码 / 事件类型前缀过滤 / 字段名大小写不一致），系统化梳理前端在业务关键字与字段契约层面的同步原则。本维度强调"前端业务关键字常量必须从后端配置拉取 + 事件类型过滤必须 === 精确匹配 + 前后端字段名大小写敏感对齐"，确保前后端业务规则一致性。3 项检查点对应 `xianyu-hunter-dev` 编码规范 step 129/130/131。

- 🆕v4.31【强制】**F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION：业务关键字常量集中管理**
  - 维度：27 业务关键字常量集中管理与字段名大小写敏感
  - 严重等级：error
  - **检查点**：前端使用业务关键字文案（如"卖掉了"/"已售"/"已下架"等业务状态判定文本）时，是否从后端配置端点（如 `/api/config/text_features`）拉取而非前端硬编码
  - **判定标准**：**禁止**前端在 `utils/`、`pages/`、`components/` 中硬编码业务关键字中文字面量（如 `const SOLD_KEYWORDS = ['卖掉了', '已售']`、`if (text.includes('卖掉了'))`）。必须改为从后端配置端点拉取关键字列表，前端通过共享 helper 函数（如 `isItemSoldByText(text)`）调用后端配置
  - **检查范围**：所有前端业务关键字文本判断（商品售出状态、订单状态、用户角色判定等业务规则文本）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.31.0 起业务关键字常量集中到 `collector_utils.py` 的 `SOLD_TEXT_KEYWORDS` + `check_text_sold()` 函数，配置节点为 `config.yaml#external_platform.text_features`
    - 前端硬编码业务关键字会与后端规则不一致（如后端新增"已售出"文案但前端未同步，导致前端展示状态错误）
    - 业务关键字是"业务规则的可配置化入口"，前端不能假设关键字是固定不变的
    - 前端职责是"调用后端配置 + 通过 helper 函数判断"，不是"实现业务规则"
  - **判断信号**（grep 检测）：
    - `grep -nE "const\s+\w*_KEYWORDS?\s*=\s*\[" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否硬编码业务关键字常量
    - `grep -nE "\.includes\(['\"](卖掉了|已售|已下架|已成交)" frontend/src/**/*.{ts,tsx}` 命中 → 违规（硬编码业务关键字判断）
    - `grep -nE "/api/config/text_features" frontend/src/api/**/*.ts` 未命中 → 检查是否有调用后端配置端点
    - 用户反馈"前端判断状态与后端不一致" → 必查前端是否硬编码业务关键字
  - **修复模式**：
    ```typescript
    // ✅ 正确：从后端配置拉取业务关键字
    import { configApi } from '@/api/config'

    let soldKeywords: string[] = ['卖掉了']  // 兜底默认值

    async function loadTextFeatures() {
      const features = await configApi.getTextFeatures()
      soldKeywords = features.sold_keywords ?? soldKeywords
    }

    export function isItemSoldByText(text: string): boolean {
      return soldKeywords.some(kw => text.includes(kw))
    }

    // ❌ 错误：前端硬编码业务关键字
    const SOLD_KEYWORDS = ['卖掉了', '已售']  // 与后端规则可能不一致
    if (text.includes('卖掉了')) {  // 硬编码字面量
      return ItemStatus.Sold
    }
    ```
  - **配置参数**：`business_keyword_centralization` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `config_endpoint_pattern`（默认 `"/api/config/text_features"`，后端业务关键字配置端点 URL）
    - `forbidden_hardcoded_patterns`（默认 `["const \\w*_KEYWORDS?\\s*=\\s*\\[", "\\.includes\\(['\"][^'\"]*(卖掉了|已售|已下架)"]`，禁止前端硬编码业务关键字的代码模式）
    - `required_helper_pattern`（默认 `"is\\w+ByText"`，业务关键字判断必须使用的共享 helper 函数命名模式）
    - `backend_keyword_source`（默认 `"xianyu-backend-code-review.business_keyword_centralization.SOLD_TEXT_KEYWORDS"`，后端业务关键字常量来源，确保前后端契约对齐）
  - **适用场景**：前端业务状态判定（商品售出/订单状态/用户角色）、业务关键字文案判断、需要与后端规则保持一致的业务规则文本
  - **不适用场景**：纯前端 UI 文案（如"保存成功"/"加载中"，不涉及业务规则）；前端组件内部状态文本（如 tab 标签）；固定的 UI 提示文案（不依赖后端规则）
  - **历史教训**：闲鱼"卖掉了"文案判定，后端 `collector_utils.py` 新增"已售出"文案后前端 `utils/soldDetector.ts` 中硬编码的 `['卖掉了', '已售']` 未同步，导致前端展示商品状态错误（显示"在售"实际已售）。修复方式：前端改为从 `/api/config/text_features` 拉取 sold_keywords 列表，与后端 `SOLD_TEXT_KEYWORDS` 一一对应
  - **对应后端原则**：后端业务关键字常量必须集中到 `collector_utils.py` + `check_text_sold()` 统一入口 + 配置节点 `config.yaml#external_platform.text_features`，详见 `xianyu-hunter-dev` step 129

- 🆕v4.31【强制】**F-REVIEW-EVENT-TYPE-EXACT-MATCH：事件类型过滤精确匹配**
  - 维度：27 业务关键字常量集中管理与字段名大小写敏感
  - 严重等级：error
  - **检查点**：前端按事件类型（event_type）过滤时是否使用 `===` 精确匹配，禁止使用 `startsWith()` / `indexOf()` 前缀匹配
  - **判定标准**：**禁止** `if (event.type.startsWith('eval.'))` / `if (event.type.indexOf('task.') === 0)` 等前缀匹配模式（除非该前缀是明确的分组分类场景）。必须改为显式枚举 `if (event.type === 'eval.started' || event.type === 'eval.passed')`，或使用 `Set` 集合判断 `if (EVENT_TYPES_TO_HANDLE.has(event.type))`
  - **检查范围**：所有前端事件类型过滤逻辑（SSE 事件、WebSocket 事件、自定义事件分发、批量事件处理）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.31.0 起事件类型过滤必须 == 精确匹配（step 130），前端 SSE 事件处理同样需要遵循
    - 前缀匹配会误包含子类型事件（如 `startsWith('eval.')` 会误包含 `eval.passed`/`eval.failed`/`eval.error`），导致前端逻辑分支错误
    - 事件类型是"枚举值"而非"前缀分类"，前端必须按枚举值精确匹配
    - 通知事件（如 `notification.created`）与业务事件（如 `task.created`）必须分离处理，禁止用前缀 `startsWith('task.')` 同时匹配业务事件和通知事件
  - **判断信号**（grep 检测）：
    - `grep -nE "\.startsWith\(['\"]\w+\." frontend/src/**/*.{ts,tsx}` 命中 → 检查是否在事件类型前缀匹配
    - `grep -nE "\.indexOf\(['\"]\w+\.\w" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否在事件类型前缀匹配
    - `grep -nE "switch\s*\(\s*\w+\.(type|eventType)" frontend/src/**/*.{ts,tsx}` 未命中 → 检查是否有按事件类型 switch 的实现
    - 用户反馈"前端 SSE 处理了不该处理的事件" → 必查前端是否用前缀匹配事件类型
  - **修复模式**：
    ```typescript
    // ✅ 正确：精确匹配 + 显式枚举
    const EVENT_TYPES_TO_HANDLE = new Set([
      'eval.started',
      'eval.passed',
      'eval.failed',
    ])

    if (EVENT_TYPES_TO_HANDLE.has(event.type)) {
      handleEvent(event)
    }

    // ✅ 正确：switch case 精确匹配
    switch (event.type) {
      case 'eval.started':
        handleEvalStarted(event)
        break
      case 'eval.passed':
        handleEvalPassed(event)
        break
      // ...
    }

    // ❌ 错误：前缀匹配（误包含子类型）
    if (event.type.startsWith('eval.')) {
      // 会误包含 eval.passed / eval.failed / eval.error
      handleEvalEvent(event)
    }
    ```
  - **配置参数**：`event_type_exact_match` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `forbidden_prefix_patterns`（默认 `["startsWith\\(['\"]\\w+\\.", "indexOf\\(['\"]\\w+\\.\\w"]`，禁止用于事件类型过滤的前缀匹配模式）
    - `required_match_pattern`（默认 `["===", "Set\\.has\\(", "switch.*case"]`，必须使用的精确匹配模式）
    - `notification_event_separation_required`（默认 `true`，是否强制通知事件与业务事件分离处理）
    - `allowed_prefix_grouping_scenarios`（默认 `["statistics_aggregation", "log_filtering"]`，允许前缀匹配的统计/日志场景）
  - **适用场景**：前端 SSE 事件处理、WebSocket 消息处理、自定义事件分发、批量事件处理
  - **不适用场景**：纯统计场景（如"统计 eval.* 类型事件总数"，允许前缀匹配）；日志过滤场景（如"过滤 task.* 类型事件"，允许前缀匹配）；路由前缀匹配（如 `/tasks/*` 路由，是路径前缀而非事件类型）
  - **历史教训**：评估明细页前端用 `event.type.startsWith('eval.')` 过滤 SSE 事件，导致 `eval.passed`/`eval.failed`/`eval.error` 等子类型事件全部进入同一处理分支，前端展示 227+ 条空记录（实际只有 `eval.started` 应该进入此分支）。修复方式：前端改为 `Set<string>` 精确匹配 `eval.started`，与后端事件类型枚举一一对应
  - **对应后端原则**：后端事件类型过滤必须 == 精确匹配 + 通知事件与业务事件分离 + 前缀分组仅限统计场景，详见 `xianyu-hunter-dev` step 130

- 🆕v4.31【强制】**F-REVIEW-FIELD-NAME-CASE-SENSITIVE：前后端字段名大小写敏感检查**
  - 维度：27 业务关键字常量集中管理与字段名大小写敏感
  - 严重等级：error
  - **检查点**：前端访问后端 API 响应字段时，字段名大小写是否与后端 Pydantic 模型完全一致
  - **判定标准**：**禁止**前端用 `data.totalForType` 访问后端 `total_for_type` 字段（驼峰/下划线混淆）、用 `repo._Session` 访问后端 `_session` 字段（私有属性大小写不一致）。必须严格对齐后端 Pydantic 模型字段名大小写，前端 `api/types.ts` 中声明的字段名必须与后端模型字段名一一对应；禁止用 `as any` 绕过类型检查
  - **检查范围**：所有前端访问后端 API 响应字段的代码路径（API 响应消费、组件 props 取值、Zustand store 字段读写、测试 mock 数据字段名）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.31.0 起前后端字段名大小写敏感检查规范化（step 131），前端同样需要遵循
    - 后端 Pydantic 模型字段名是契约（如 `total_for_type` snake_case），前端 `api/types.ts` 必须严格对齐
    - 后端私有属性（如 `_session`）大小写敏感，前端通过类型断言访问时必须完全一致
    - 前端用 `as any` 绕过类型检查会掩盖字段名大小写不一致的 bug，必须改为精确类型 + grep 双向匹配验证
  - **判断信号**（grep 检测）：
    - `grep -nE "as\s+any\b" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否用 `as any` 绕过字段名检查
    - `grep -nE "\.\w*[A-Z]\w*\b" frontend/src/api/**/*.ts` 命中 → 检查前端 API 类型定义中是否有驼峰字段名（后端应为 snake_case）
    - 后端字段重命名后 `git diff frontend/src/api/types.ts` 无变化 → 前端类型未同步
    - 用户反馈"前端字段显示 undefined / 0 / 空" → 必查前端字段名大小写是否与后端一致
  - **修复模式**：
    ```typescript
    // ✅ 正确：前端类型与后端 Pydantic 模型一一对应（snake_case）
    interface EvalDetailResponse {
      total: number
      total_for_type: number  // 与后端 Pydantic 模型一致
      items: EvalItem[]
    }

    const data = await api.getEvalDetail()
    console.log(data.total_for_type)  // ✅ 字段名一致

    // ❌ 错误：字段名大小写不一致（前端误用驼峰）
    interface EvalDetailResponse {
      total: number
      totalForType: number  // ❌ 与后端 total_for_type 不一致
    }

    const data = await api.getEvalDetail() as any  // ❌ 用 as any 绕过类型检查
    console.log(data.totalForType)  // ❌ undefined（后端返回 total_for_type）
    ```
  - **配置参数**：`field_name_case_sensitive` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `backend_field_naming_style`（默认 `"snake_case"`，后端字段命名风格）
    - `forbidden_frontend_naming_styles`（默认 `["camelCase", "PascalCase"]`，禁止前端字段命名风格（除非是前端独立字段））
    - `require_type_sync`（默认 `true`，后端字段变更时前端 types.ts 必须同步）
    - `forbidden_bypass_patterns`（默认 `["as\\s+any\\b", "as\\s+unknown\\s+as"]`，禁止用类型断言绕过字段名检查的模式）
    - `detection_signals`（默认 `["\\.\\w*[A-Z]\\w*\\b", "as\\s+any\\b"]`，触发检查的代码模式）
    - `backend_model_source`（默认 `"xianyu-backend-code-review.field_name_contract.models"`，后端 Pydantic 模型字段名来源，确保前后端契约对齐）
  - **适用场景**：前端访问后端 API 响应字段、前端 API 类型定义、前端 Zustand store 字段读写、前端测试 mock 数据字段名
  - **不适用场景**：前端独立字段（如组件内部 state，不涉及后端契约）；前端 UI 文案常量（不涉及字段名）；前端路由参数（前端独立命名）
  - **历史教训**：评估明细页前端展示"0 条"，根因是前端用 `data.totalForType` 访问后端 `total_for_type` 字段（驼峰 vs snake_case 不一致），导致 `data.totalForType` 始终为 `undefined`，前端 `undefined || 0` 显示为 0。同时后端 `ChatbotRepository` 类用 `this._Session` 访问定义的 `this._session` 私有属性（大小写不一致），导致 `AttributeError: 'ChatbotRepository' object has no attribute '_Session'`。修复方式：前端类型定义严格对齐后端 snake_case，私有属性大小写完全一致
  - **对应后端原则**：后端私有属性大小写一致 + API 字段名前后端契约对齐 + grep 双向匹配验证，详见 `xianyu-hunter-dev` step 131

### 28. 多用户认证上下文隔离 🆕v4.32

基于 2026-07-05 完成的 MU2 Sprint（认证中间件改造 + CookieStore 扩展 user_id 维度）复盘（使用 Sequential Thinking 8 步复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景），系统化梳理前端在多用户认证场景下的上下文隔离原则。本维度强调"前端按 user_id 隔离状态 + 认证 token 通过 httpOnly cookie 传递 + 401 降级路径明确分离"，确保多用户场景下不发生跨用户污染、认证失败有可操作的恢复路径。2 项检查点对应 `xianyu-hunter-dev` 编码规范 step 134-137（多用户资源隔离 + 认证中间件多路校验 + 会话 token 安全管理 + 快照与实时数据覆盖决策）。

- 🆕v4.32【强制】**F-REVIEW-MULTI-USER-CONTEXT-ISOLATION：多用户上下文隔离**
  - 维度：28 多用户认证上下文隔离
  - 严重等级：error
  - **检查点**：前端是否存在按 user_id 维度隔离的状态/缓存/请求路径，避免跨用户数据污染
  - **判定标准**：**禁止**前端用全局单例 store/缓存承接多用户会话数据。前端从 `/api/auth/me` 获取当前 `user_id` 后，所有用户特定的 API 请求必须显式携带 `user_id` 上下文（通过请求参数、Header 或后端 session 注入），所有用户特定的 Zustand store 必须按 `user_id` 分桶存储（`Record<UserId, UserState>`），用户切换时必须清空旧用户的全局缓存并触发 `invalidate`
  - **检查范围**：前端所有持有用户特定状态的代码（Zustand store / React Context / localStorage 缓存 / Service Worker 缓存 / SWR/React Query 缓存键）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.32 起 CookieStore 按 `cookies_{uid}.json` 分文件存储 + `_cache: dict[str, tuple[dict, float]]` 分桶缓存（step 134），前端必须同步按 `user_id` 隔离状态
    - 后端中间件三路校验通过后注入 `request.state.user_id`（step 135），前端从 `/api/auth/me` 拿到 `user_id` 后必须传递给所有用户相关 API
    - 多用户切换时未清空缓存会导致跨用户数据泄漏（A 用户的订单列表显示给 B 用户）
    - 前端"全局单例 store 承接多用户数据"是反模式，必须改为 `Record<UserId, UserState>` 分桶或切换时 `store.reset()`
  - **判断信号**（grep 检测）：
    - `grep -nE "user_id" frontend/src/stores/` 未命中 → 检查 Zustand store 是否考虑了 user_id 维度
    - `grep -nE "localStorage\\.(get|set)Item\\(['\"]user_" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否按 user_id 分键存储
    - `grep -nE "useUserStore|useAuthStore" frontend/src/` 命中 → 检查用户切换时是否调用 `reset()` 或 `invalidate`
    - 用户反馈"切换账号后看到上一个账号的数据" → 必查前端是否按 user_id 隔离状态
  - **修复模式**：
    ```typescript
    // ✅ 正确：Zustand store 按 user_id 分桶
    interface UserScopedState {
      [userId: string]: {
        orders: Order[]
        preferences: UserPreferences
      }
    }

    const useUserStore = create<UserScopedState>((set, get) => ({
      // 默认空对象
    }))

    // 切换用户时清空旧用户缓存
    function onUserSwitch(newUserId: string) {
      // 1. 清空全局 SWR/React Query 缓存
      queryClient.clear()
      // 2. 重置非用户特定 store
      useGlobalStore.getState().reset()
      // 3. 加载新用户数据
      loadUserData(newUserId)
    }

    // ❌ 错误：全局单例 store 承接多用户数据
    const useOrderStore = create<{ orders: Order[] }>(() => ({
      orders: []  // 多用户切换时未清空，A 用户的订单残留显示给 B 用户
    }))
    ```
  - **配置参数**：`multi_user_context_isolation` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `require_user_id_in_store`（默认 `true`，用户特定 store 必须按 user_id 分桶）
    - `require_invalidate_on_user_switch`（默认 `true`，用户切换时必须清空旧用户缓存）
    - `forbidden_global_singleton_patterns`（默认 `["create<.*>\\(\\)\\s*=>\\s*\\(\\{\\s*orders:"\\]`，禁止全局单例承接多用户数据的模式）
    - `user_id_source`（默认 `"/api/auth/me"`，前端获取当前 user_id 的端点）
    - `backend_isolation_source`（默认 `"xianyu-hunter-dev.multi_user_resource_isolation"`，后端资源隔离规范来源，确保前后端契约对齐）
  - **适用场景**：多用户系统（用户切换/多账号管理）、多租户 SaaS、需要按用户隔离缓存/状态/请求的场景
  - **不适用场景**：单用户系统（无用户切换需求）、纯内部工具（无登录态）、纯只读公共数据展示（无用户特定数据）
  - **历史教训**：MU2 Sprint 中后端 CookieStore 升级为按 `cookies_{uid}.json` 分文件存储，但前端 Zustand store 仍用全局单例承接订单/偏好数据，导致用户 A 切换到用户 B 时短暂显示 A 的订单列表（缓存未清空）。修复方式：前端引入 `onUserSwitch` 钩子，调用 `queryClient.clear()` + `useGlobalStore.getState().reset()` 后再加载新用户数据
  - **对应后端原则**：后端 CookieStore 按 user_id 分文件 + 分桶缓存 + 白名单校验 + SQLite 兜底隔离，详见 `xianyu-hunter-dev` step 134

- 🆕v4.32【强制】**F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING：认证 token cookie 处理**
  - 维度：28 多用户认证上下文隔离
  - 严重等级：error
  - **检查点**：前端是否正确处理认证 token 的 cookie 传递、`credentials: 'include'` 配置、401 降级路径
  - **判定标准**：**禁止**前端将认证 token 存入 `localStorage`（应通过 httpOnly cookie 由后端写入）；**禁止**fetch/axios 请求遗漏 `credentials: 'include'`（或 axios 的 `withCredentials: true`）；**禁止**所有认证失败一律显示"请重新登录"，必须按后端状态码语义区分：401（未登录，跳登录页）/ 440（Cookie 过期，跳重新登录页）/ 441（Token 过期，调刷新接口）/ 403（权限不足，提示无权限）
  - **检查范围**：前端所有 API 请求代码（fetch/axios/SSE EventSource）、所有 401/403/440/441 错误处理分支、所有 token 存取代码
  - **核心机制**（审查时必须理解）：
    - 后端 v4.32 起中间件三路校验：管理令牌直通（hmac.compare_digest）→ 用户会话查库（verify_session）→ 401（step 135），前端必须配合 cookie 传递 token
    - 后端 `make_auth_response` 在登录成功后通过 `set-cookie` 写入 `xh_token` cookie（httpOnly + samesite=lax + max_age=86400*30），前端无法读取但会自动携带
    - 前端 fetch 必须显式 `credentials: 'include'` 才会携带 cookie；axios 必须设 `withCredentials: true`
    - 后端 SSE 事件需通过 htmx `<meta name="htmx-config">` 配置 `withCredentials` 或 EventSource 显式传 `withCredentials: true`
    - 状态码语义精细化（与 v4.27 F-REVIEW-ERROR-CODE-BRANCH 配合）：前端必须按 `error_code` 字段或 HTTP 状态码区分 401/440/441/403 不同降级路径
  - **判断信号**（grep 检测）：
    - `grep -nE "fetch\\(" frontend/src/api/**/*.ts` 命中后检查是否包含 `credentials: 'include'`
    - `grep -nE "axios\\.create" frontend/src/api/**/*.ts` 命中后检查是否包含 `withCredentials: true`
    - `grep -nE "localStorage\\.(get|set)Item\\(['\"]xh_token" frontend/src/**/*.{ts,tsx}` 命中 → 违规（token 不应存 localStorage）
    - `grep -nE "EventSource\\(" frontend/src/**/*.{ts,tsx}` 命中后检查是否包含 `withCredentials: true`
    - `grep -nE "401.*登录|401.*login" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否区分 401/440/441/403
    - 用户反馈"频繁被踢出登录"或"刷新页面后丢失登录态" → 必查前端是否正确处理 cookie + credentials
  - **修复模式**：
    ```typescript
    // ✅ 正确：fetch 显式 credentials + 状态码分支
    async function fetchOrders() {
      const resp = await fetch('/api/orders', {
        credentials: 'include',  // 必须显式声明，否则不携带 cookie
      })
      if (resp.status === 401) {
        redirectTo('/login')  // 未登录，跳登录页
        return
      }
      if (resp.status === 440) {
        redirectTo('/relogin')  // Cookie 过期，跳重新登录页
        return
      }
      if (resp.status === 441) {
        await refreshToken()  // Token 过期，调刷新接口
        return fetchOrders()  // 重试
      }
      if (resp.status === 403) {
        message.error('权限不足')  // 已登录但无权限
        return
      }
      return resp.json()
    }

    // ✅ 正确：axios 全局配置 withCredentials
    const api = axios.create({
      baseURL: '/api',
      withCredentials: true,  // 全局配置，所有请求携带 cookie
    })

    // ✅ 正确：htmx meta 配置 credentials（初始化时机可靠）
    // <meta name="htmx-config" content='{"withCredentials": true}'>

    // ❌ 错误：token 存 localStorage（XSS 可读取）
    localStorage.setItem('xh_token', token)

    // ❌ 错误：所有认证失败一律跳登录页
    if (resp.status === 401 || resp.status === 440 || resp.status === 441) {
      redirectTo('/login')  // 未区分语义，用户反复被踢
    }
    ```
  - **配置参数**：`auth_token_cookie_handling` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `require_credentials_include`（默认 `true`，fetch 必须显式 `credentials: 'include'`）
    - `require_axios_with_credentials`（默认 `true`，axios 必须设 `withCredentials: true`）
    - `forbidden_token_storage`（默认 `["localStorage", "sessionStorage"]`，禁止存储 token 的位置）
    - `status_code_semantics`（默认 `{"401": "redirect_login", "440": "redirect_relogin", "441": "refresh_token", "403": "show_permission_error"}`，状态码到前端动作的映射）
    - `cookie_name`（默认 `"xh_token"`，后端写入的认证 cookie 名称）
    - `cookie_attributes`（默认 `{"httpOnly": true, "samesite": "lax", "max_age": 2592000}`，后端 cookie 属性契约）
    - `backend_auth_source`（默认 `"xianyu-hunter-dev.auth_multi_path_validation"`，后端认证中间件规范来源，确保前后端契约对齐）
  - **适用场景**：所有涉及认证的 API 请求、登录/会话管理、SSE 事件流认证、多角色权限控制
  - **不适用场景**：纯公共 API（无需认证）、第三方 OAuth 回调（按 OAuth 规范处理）、内部微服务间调用（无 cookie 概念）
  - **历史教训**：MU2 Sprint 中后端中间件实现三路校验（管理令牌 + 用户会话 + 401），但前端仍用旧逻辑：所有 401 一律跳登录页，导致用户会话过期（应跳重新登录页）和 Cookie 过期（应刷新 token）也被误判为"未登录"，用户频繁被踢出。同时部分 fetch 请求遗漏 `credentials: 'include'`，导致 cookie 不传递，后端 401 拒绝。修复方式：前端按 `error_code`/状态码分支处理，全局 axios 实例统一配置 `withCredentials: true`，htmx 通过 `<meta>` 配置 credentials
  - **对应后端原则**：后端中间件三路校验 + `make_auth_response` 写入 httpOnly cookie + 状态码语义精细化，详见 `xianyu-hunter-dev` step 135 + step 71（状态码语义精细化）

- 🆕v4.33【强制】**F-REVIEW-EFFECT-MINIMIZE：useEffect 副作用最小化**
  - 维度：3 React 组件规范
  - 严重等级：HIGH
  - **规范引用**：EFFECT-01 useEffect 副作用最小化原则
  - **检查点**：useEffect 是否用于重置用户交互控制的状态、是否应合并而非替换、是否在依赖数组变化时触发不必要的副作用
  - **判定标准**：**禁止**用 useEffect 联动重置用户交互控制的状态（如 openKeys/expandedKeys/activeKey/open），此类状态应通过 useState 初始化 + 用户交互回调更新；**禁止**用 useEffect 替换本应合并的状态更新；useEffect 仅用于订阅/取消订阅、事件监听挂载/卸载、外部系统同步等真正的副作用场景
  - **检查范围**：所有 useEffect 调用，特别是依赖数组包含路由/location/props 且 setState 用户交互控制状态的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "useEffect\\(\\s*\\(\\s*\\)\\s*=>\\s*\\{[^}]*set(OpenKeys|ExpandedKeys|ActiveKey|Open)" frontend/src/**/*.{ts,tsx}` 命中 → 违规
    - useEffect 依赖数组包含 `location.pathname` / `url` 且 setState 用户控制状态 → 违规
    - 用户反馈"菜单动画闪烁"/"展开状态被重置" → 必查 useEffect 是否联动重置
  - **反模式**：
    ```typescript
    // ❌ 错误：useEffect 联动重置用户控制的 openKeys，触发 SubMenu 动画遮挡
    const [openKeys, setOpenKeys] = useState<string[]>([])
    useEffect(() => {
      setOpenKeys(autoOpenKeys)  // 重置用户控制状态，触发动画
    }, [location.pathname])
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：useState 初始化 + 用户交互控制，移除 useEffect 联动
    const [openKeys, setOpenKeys] = useState<string[]>(() => autoOpenKeys)
    // openKeys 完全由 onOpenChange 用户交互控制，不依赖路由变化
    ```
  - **配置参数**：`coding_standards.effect.disallow_reset_user_controlled_state`（默认 `true`，禁止 useEffect 重置用户控制状态）+ `coding_standards.effect.merge_strategy`（默认 `merge_not_replace`，状态更新应合并而非替换）
  - **适用场景**：所有受控 UI 状态（菜单展开/折叠/选中/Tab 激活）、用户交互后状态需要保留的场景
  - **不适用场景**：订阅外部 store（如 Zustand subscribe）、事件监听挂载/卸载、与外部系统（WebSocket/SSE）同步
  - **历史教训**：MainLayout 中 useEffect 联动重置 openKeys 导致 SubMenu 动画遮挡，用户操作时菜单闪烁。修复方式：完全移除 useEffect，openKeys 由 useState 初始化 + onOpenChange 用户控制
  - **对应后端原则**：无（纯前端 React 组件规范），规范源 xianyu-hunter-dev/references/coding-rules.md EFFECT-01

- 🆕v4.33【强制】**F-REVIEW-STATE-ATOMICITY：状态切换原子性**
  - 维度：3 React 组件规范
  - 严重等级：HIGH
  - **规范引用**：STATE-01 状态切换原子性原则（前端）
  - **检查点**：多字段状态切换是否同步更新，避免部分字段更新导致中间不一致状态
  - **判定标准**：涉及多字段状态切换（如 sheet.active/sheet.minimized/sheet.order 三字段联动）时，**禁止**分散更新单个字段导致中间不一致状态，**必须**封装 transition 方法同步更新所有字段，或使用单一状态枚举（如 sheet.status: 'active' | 'minimized' | 'closed'）替代多字段布尔值
  - **检查范围**：所有涉及多字段状态切换的代码（sheet/workspace/tab/panel 状态管理、对象状态机切换）
  - **判断信号**（grep 检测）：
    - `grep -nE "set\\w+\\(\\s*\\{[^}]*active:\\s*true" frontend/src/**/*.{ts,tsx}` 命中后检查是否同步更新 minimized/order 等关联字段
    - 多字段状态对象的部分更新（`setState({ active: true })` 而非 `setState({ active: true, minimized: false })`）→ 违规
    - 用户反馈"切换 Tab 时短暂出现两个激活状态" → 必查状态切换原子性
  - **反模式**：
    ```typescript
    // ❌ 错误：只更新 active 忘了 minimized，导致 sheet 同时处于 active + minimized
    setSheets(prev => prev.map(s => s.id === id ? { ...s, active: true } : s))
    // 忘了同步 sheet.minimized = false
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：封装 transition 方法，同步更新所有关联字段
    const activateSheet = (id: string) => {
      setSheets(prev => prev.map(s => {
        if (s.id === id) return { ...s, active: true, minimized: false }
        return { ...s, active: false }
      }))
    }
    // 或使用单一状态枚举替代多字段布尔值
    type SheetStatus = 'active' | 'minimized' | 'closed'
    ```
  - **配置参数**：无（纯代码模式检查，配置驱动通过 checklist.react_component 开关）
  - **适用场景**：多字段状态联动切换（sheet/tab/panel/workspace）、状态机转换、需要保持一致性的复合状态
  - **不适用场景**：独立单字段状态、无关联的并行状态更新、性能优化的批量更新（已有 React batching 保证）
  - **历史教训**：SheetWorkspace 中 `sheet.active = true` 时忘记同步 `sheet.minimized = false`，导致 sheet 同时显示为激活和最小化状态。修复方式：封装 `activateSheet` transition 方法同步更新所有关联字段
  - **对应后端原则**：无（纯前端状态管理），规范源 xianyu-hunter-dev/references/coding-rules.md STATE-01

- 🆕v4.33【强制】**F-REVIEW-SSE-CONN-MGMT：SSE 连接管理三要素**
  - 维度：15 SSE 重连
  - 严重等级：CRITICAL
  - **规范引用**：SSE-01 SSE 连接管理三要素
  - **检查点**：SSE 连接是否同时具备三要素——visibilitychange 监听（页面恢复可见时重建连接）、last_event_id 回放（断线重连时传递最后事件 ID）、最大重试限制（超限后降级轮询）
  - **判定标准**：**禁止**SSE 无限重连（必须配置 max_reconnect_attempts，超限后退化为轮询）；**必须**监听 visibilitychange 事件在页面恢复可见时重建连接；**必须**在重连时通过 `?last_event_id=` 参数传递最后事件 ID 启用服务端回放
  - **检查范围**：所有 EventSource / useEventSource 调用，SSE 重连逻辑，visibilitychange 事件监听
  - **判断信号**（grep 检测）：
    - `grep -nE "new EventSource\\(" frontend/src/**/*.{ts,tsx}` 命中后检查是否包含 visibilitychange 监听
    - `grep -nE "addEventListener\\('error'[\\s\\S]*setTimeout\\(connect" frontend/src/**/*.{ts,tsx}` 命中后检查是否有 MAX_RECONNECT 限制
    - `grep -nE "EventSource\\([^)]*\\)" frontend/src/**/*.{ts,tsx}` 命中后检查是否包含 `?last_event_id=` 参数
    - 用户反馈"SSE 频繁重连但不恢复" / "页面切回后事件丢失" → 必查三要素完整性
  - **反模式**：
    ```typescript
    // ❌ 错误：SSE 无限重连，无最大重试限制，无 visibilitychange 监听
    const connect = () => {
      const es = new EventSource('/api/events/stream')
      es.addEventListener('error', () => {
        setTimeout(connect, 3000)  // 无限重连，无降级
      })
    }
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：visibilitychange 监听 + last_event_id 回放 + 最大重试 10 次 + 降级轮询
    const MAX_RECONNECT = 10
    let reconnectCount = 0
    const connect = () => {
      const lastEventId = localStorage.getItem('xh_sse_last_event_id') || ''
      const es = new EventSource(`/api/events/stream?last_event_id=${lastEventId}`)
      es.addEventListener('open', () => { reconnectCount = 0 })
      es.addEventListener('error', () => {
        es.close()
        if (reconnectCount >= MAX_RECONNECT) {
          startPollingFallback()  // 降级轮询
          return
        }
        reconnectCount++
        setTimeout(connect, 3000 * reconnectCount)
      })
    }
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        reconnectCount = 0
        connect()
      }
    })
    ```
  - **配置参数**：`coding_standards.sse.max_reconnect_attempts`（默认 `10`，最大重连次数）+ `coding_standards.sse.polling_fallback_interval`（默认 `30`，降级轮询间隔秒数）+ `coding_standards.sse.visibility_reconnect`（默认 `true`，必须监听 visibilitychange）
  - **适用场景**：所有使用 SSE 的实时数据推送（事件流/通知流/状态变更推送）、长连接场景
  - **不适用场景**：WebSocket（有自己的重连机制）、短连接轮询、一次性事件订阅
  - **历史教训**：SSE 连接在网络抖动时无限重连导致服务器压力，且页面切到后台再切回时事件丢失。修复方式：增加最大重试 10 次限制 + visibilitychange 监听 + last_event_id 回放
  - **对应后端原则**：后端 SSE 端点必须支持 `?last_event_id=` 参数启用事件回放，规范源 xianyu-hunter-dev/references/coding-rules.md SSE-01

- 🆕v4.33【强制】**F-REVIEW-ASYNC-RACE-GUARD：异步竞态防护**
  - 维度：10 Hooks 设计模式
  - 严重等级：HIGH
  - **规范引用**：RACE-01 异步竞态防护
  - **检查点**：异步请求是否用 useRef 维护最新请求 ID，响应回来时对比 ID 决定是否更新状态
  - **判定标准**：**禁止**异步请求完成直接更新状态（无请求 ID 对比），**必须**用 useRef 维护最新请求 ID，响应回来时对比 ID，若不一致则丢弃响应（避免旧响应覆盖新响应）
  - **检查范围**：所有异步请求（fetch/axios）触发的状态更新，特别是搜索/筛选/分页等用户可快速连续触发的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "async\\s+function\\s+\\w+[\\s\\S]{0,500}set\\w+\\(.*\\)" frontend/src/**/*.{ts,tsx}` 命中后检查是否有 requestId 对比
    - `grep -nE "useRef\\(.*requestId" frontend/src/**/*.{ts,tsx}` 未命中 → 检查异步请求是否缺少竞态防护
    - 用户反馈"快速切换筛选条件后显示旧数据" / "搜索结果与关键词不匹配" → 必查异步竞态防护
  - **反模式**：
    ```typescript
    // ❌ 错误：异步请求完成直接更新状态，无请求 ID 对比
    const search = async (keyword: string) => {
      const resp = await fetch(`/api/search?keyword=${keyword}`)
      const data = await resp.json()
      setResults(data)  // 旧响应可能覆盖新响应
    }
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：useRef 维护最新请求 ID，响应回来时对比
    const latestRequestId = useRef(0)
    const search = async (keyword: string) => {
      const requestId = ++latestRequestId.current
      const resp = await fetch(`/api/search?keyword=${keyword}`)
      const data = await resp.json()
      if (requestId !== latestRequestId.current) return  // 丢弃过期响应
      setResults(data)
    }
    ```
  - **配置参数**：`coding_standards.race.check_request_id`（默认 `true`，必须用 useRef 维护请求 ID 对比）
  - **适用场景**：用户可快速连续触发的异步请求（搜索/筛选/分页/排序）、并发请求可能返回顺序不一致的场景
  - **不适用场景**：单次提交（如保存/删除，无连续触发）、请求顺序天然保证的场景（如 await 链式调用）
  - **历史教训**：搜索框快速输入时，前一个请求的响应覆盖后一个请求的响应，导致显示与关键词不匹配的结果。修复方式：引入 useRef 维护最新请求 ID
  - **对应后端原则**：无（纯前端竞态防护），规范源 xianyu-hunter-dev/references/coding-rules.md RACE-01

- 🆕v4.33【强制】**F-REVIEW-THEME-DYNAMIC-ADAPT：主题色动态适配**
  - 维度：5 AntD 5 主题规范
  - 严重等级：HIGH
  - **规范引用**：THEME-01 主题色动态适配
  - **检查点**：是否硬编码颜色值、是否根据 isDark 动态设置主题相关 token
  - **判定标准**：**禁止**硬编码颜色值（特别是主题相关 token 如 rowHoverBg/headerBg/headerColor），**必须**根据 isDark 动态设置；显式指定的主题 token 必须在 ThemedRoot 内按 isDark 覆盖（与 v4.8 F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE 配合）
  - **检查范围**：所有 components.<Component>.<token> 配置、内联样式中的颜色值、CSS 变量定义
  - **判断信号**（grep 检测）：
    - `grep -nE "components\\.[A-Z]\\w+\\.\\w*(?:Color|Bg|Border|Hover|Active|Focus)\\s*:\\s*['\"]#[0-9a-fA-F]+['\"]" frontend/src/**/*.{ts,tsx}` 命中 → 违规（硬编码颜色）
    - `grep -nE "rowHoverBg|headerBg|headerColor" frontend/src/**/*.{ts,tsx}` 命中后检查是否根据 isDark 动态设置
    - 暗色模式下用户反馈"文字看不清"/"背景太亮" → 必查主题色动态适配
  - **反模式**：
    ```typescript
    // ❌ 错误：硬编码 rowHoverBg，暗色模式不可读
    const themeConfig = {
      components: {
        Table: {
          rowHoverBg: '#fff7f0'  // 暗色模式下不可读
        }
      }
    }
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：根据 isDark 动态设置
    const themeConfig = {
      components: {
        Table: {
          rowHoverBg: isDark ? 'rgba(255, 98, 0, 0.08)' : '#fff7f0'
        }
      }
    }
    ```
  - **配置参数**：`coding_standards.theme.disallow_hardcoded_colors`（默认 `true`，禁止硬编码主题色）+ `coding_standards.theme.colors.light`（浅色主题色映射）+ `coding_standards.theme.colors.dark`（暗色主题色映射）
  - **适用场景**：所有支持暗色主题的组件、显式指定的主题 token、内联样式中的颜色值
  - **不适用场景**：纯亮色主题应用（无暗色模式）、第三方组件内部样式（无法控制）、品牌固定色（如 logo 颜色）
  - **历史教训**：Table 组件硬编码 `rowHoverBg: '#fff7f0'`，暗色模式下用户无法看清 hover 行。修复方式：改为 `isDark ? 'rgba(255,98,0,0.08)' : '#fff7f0'`
  - **对应后端原则**：无（纯前端主题规范），规范源 xianyu-hunter-dev/references/coding-rules.md THEME-01

- 🆕v4.33【强制】**F-REVIEW-EMBEDDED-LAYOUT-HEIGHT：嵌入式布局高度**
  - 维度：3 React 组件规范
  - 严重等级：HIGH
  - **规范引用**：LAYOUT-01 嵌入式布局高度
  - **检查点**：嵌入框架页面（如 iframe / Electron / 浏览器扩展弹窗）是否用 `height: 100%` + `flex: 1`，禁止 `minHeight: 100vh`
  - **判定标准**：**禁止**在嵌入式场景使用 `minHeight: '100vh'`（会撑满整个视口而非容器，导致全屏溢出），**必须**使用 `height: '100%'` + `flex: 1` 适配父容器高度
  - **检查范围**：所有页面/布局组件的样式，特别是嵌入 iframe / Electron / 浏览器扩展弹窗的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "minHeight:\\s*['\"]100vh['\"]|minHeight:\\s*['\"]100vh['\"]" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否为嵌入式场景
    - `grep -nE "height:\\s*['\"]100%['\"]" frontend/src/**/*.{ts,tsx}` 未命中 → 检查嵌入式布局是否缺少 height:100%
    - 用户反馈"页面撑满整个浏览器窗口" / "iframe 内出现滚动条" → 必查嵌入式布局高度
  - **反模式**：
    ```typescript
    // ❌ 错误：嵌入 iframe 使用 minHeight: '100vh'，撑满视口导致全屏
    const PageContainer = styled.div`
      minHeight: '100vh';  // 嵌入场景应禁止
    `
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：使用 height: '100%' + flex: 1 适配父容器
    const PageContainer = styled.div`
      height: '100%';
      flex: 1;
      overflow: auto;
    `
    ```
  - **配置参数**：`coding_standards.layout.disallow_minheight_100vh_in_embedded`（默认 `true`，嵌入式场景禁止 minHeight:100vh）
  - **适用场景**：嵌入 iframe / Electron / 浏览器扩展弹窗 / 桌面应用 webview 的页面布局
  - **不适用场景**：独立网页（非嵌入）、需要撑满视口的落地页/营销页、移动端 H5（视口适配）
  - **历史教训**：闲鱼猎人前端嵌入 iframe 时使用 `minHeight: '100vh'`，导致页面撑满整个浏览器窗口而非 iframe 容器，出现全屏溢出。修复方式：改为 `height: '100%'` + `flex: 1`
  - **对应后端原则**：无（纯前端布局规范），规范源 xianyu-hunter-dev/references/coding-rules.md LAYOUT-01

- 🆕v4.33【强制】**F-REVIEW-COMPONENT-REGISTRY：组件注册完整性**
  - 维度：3 React 组件规范
  - 严重等级：HIGH
  - **规范引用**：REGISTRY-01 组件注册完整性
  - **检查点**：ECharts / antd 等需要 register 的组件是否 import + register，避免使用未注册组件导致静默失败
  - **判定标准**：**禁止**使用未注册的组件（如 ECharts 的 FunnelChart / LineChart / BarChart / PieChart 等），**必须**在使用前 `import` + `use()` 注册所有用到的组件；组件注册应集中在入口文件（如 `echarts.setup.ts`）
  - **检查范围**：所有 ECharts 组件使用（`<FunnelChart />` / `<LineChart />` 等）、antd 按需加载配置、其他需要 register 的库
  - **判断信号**（grep 检测）：
    - `grep -nE "<(FunnelChart|LineChart|BarChart|PieChart|MapChart|HeatmapChart)" frontend/src/**/*.{ts,tsx}` 命中后检查对应 import + use 注册
    - `grep -nE "echarts\\.(register|use)\\(" frontend/src/**/*.{ts,tsx}` 命中后核对注册的组件列表是否覆盖所有使用
    - 用户反馈"图表不显示"/"组件渲染空白无报错" → 必查组件注册完整性
  - **反模式**：
    ```typescript
    // ❌ 错误：使用 FunnelChart 但未注册，静默失败（图表不显示无报错）
    import * as echarts from 'echarts/core'
    // 忘了 import { FunnelChart } from 'echarts/charts' + echarts.use([FunnelChart])
    const Chart = () => <EChartReact option={{ series: [{ type: 'funnel' }] }} />
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：import + register 所有用到的组件
    import * as echarts from 'echarts/core'
    import { FunnelChart } from 'echarts/charts'
    import { TooltipComponent, GridComponent } from 'echarts/components'
    import { CanvasRenderer } from 'echarts/renderers'
    
    echarts.use([FunnelChart, TooltipComponent, GridComponent, CanvasRenderer])
    ```
  - **配置参数**：`coding_standards.registry.check_components`（默认 `[FunnelChart, LineChart, BarChart, PieChart]`，需要检查注册的组件列表）
  - **适用场景**：所有使用 ECharts / antd / Mobx 等需要 register 的库的组件
  - **不适用场景**：使用全量引入（`import * as echarts from 'echarts'`，自动注册所有组件）、不涉及 register 的库
  - **历史教训**：使用 FunnelChart 但未注册，导致图表静默失败（无报错但不显示），用户反馈"图表空白"才定位到问题。修复方式：建立 `echarts.setup.ts` 集中注册所有用到的组件
  - **对应后端原则**：无（纯前端组件注册），规范源 xianyu-hunter-dev/references/coding-rules.md REGISTRY-01

- 🆕v4.33【强制】**F-REVIEW-FILTER-TRANSPARENCY：过滤透明化**
  - 维度：7 API 调用规范
  - 严重等级：MEDIUM
  - **规范引用**：FILTER-02 过滤透明化
  - **检查点**：数据被过滤时是否展示过滤原因和条数，避免用户误以为数据丢失
  - **判定标准**：**禁止**仅显示"获取 N 条"而隐藏过滤过程（实际搜到 M 条被过滤为 N 条），**必须**展示过滤原因和条数（如"搜到 59 条，按规则过滤后显示 12 条"），通过 Modal / Tooltip / Alert 展示 `filter_summary`
  - **检查范围**：所有调用后端过滤接口的列表页/搜索页/统计页，特别是显示条数的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "获取\\s*\\d+\\s*条|共\\s*\\d+\\s*条" frontend/src/**/*.{ts,tsx}` 命中后检查是否展示 filter_summary
    - `grep -nE "filter_summary" frontend/src/api/types.ts` 命中后检查前端是否消费该字段
    - 用户反馈"显示获取 0 条但实际有数据" → 必查过滤透明化
  - **反模式**：
    ```typescript
    // ❌ 错误：显示"获取0条"但实际搜到 59 条被过滤，用户误以为数据丢失
    const resp = await fetch('/api/items/search?keyword=xxx')
    const data = await resp.json()
    message.success(`获取 ${data.items.length} 条`)  // 隐藏过滤过程
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：后端返回 filter_summary，前端用 Modal/Tooltip 展示
    const resp = await fetch('/api/items/search?keyword=xxx')
    const data = await resp.json()
    message.success(`显示 ${data.items.length} 条`)
    if (data.filter_summary) {
      Modal.info({
        title: '过滤结果说明',
        content: `搜到 ${data.filter_summary.total_matched} 条，按规则过滤后显示 ${data.items.length} 条。过滤原因：${data.filter_summary.reason}`
      })
    }
    ```
  - **配置参数**：`coding_standards.filter.summary_enabled`（默认 `true`，必须展示过滤摘要）
  - **适用场景**：所有调用后端过滤接口的列表页/搜索页/统计页、用户可能误解数据完整性的场景
  - **不适用场景**：纯前端过滤（无后端 filter_summary）、无需展示过滤过程的内部统计、数据导出场景
  - **历史教训**：搜索接口显示"获取 0 条"但实际后端搜到 59 条被过滤规则过滤，用户误以为数据丢失。修复方式：后端返回 `filter_summary` 字段，前端用 Modal 展示过滤原因和条数
  - **对应后端原则**：后端必须返回 `filter_summary` 字段含 `total_matched` / `total_filtered` / `reason`，规范源 xianyu-hunter-dev/references/coding-rules.md FILTER-02

- 🆕v4.33【强制】**F-REVIEW-DATA-SOURCE-VERIFY：数据源正确性验证**
  - 维度：18 闲鱼项目规范
  - 严重等级：HIGH
  - **规范引用**：SOURCE-01 数据源正确性验证
  - **检查点**：显示数据是否来自正确数据源，避免误用配置备份文件数等错误数据源
  - **判定标准**：**禁止**误用数据源（如版本管理显示配置备份文件数 V10 而非系统版本），**必须**从语义对齐的 API 获取数据（如系统版本从 `/api/about` 获取，而非 `/api/config/version` 返回的 `len(backups)`）
  - **检查范围**：所有显示版本/计数/统计数据的组件，特别是从多个 API 获取类似字段的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "version\\s*[:=]" frontend/src/**/*.{ts,tsx}` 命中后检查数据源是否为 `/api/about`
    - `grep -nE "/api/config/version" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否误用（该接口返回 len(backups)）
    - 用户反馈"版本号显示为 V10 而非实际版本" → 必查数据源正确性
  - **反模式**：
    ```typescript
    // ❌ 错误：版本管理显示 V10（配置备份文件数而非系统版本）
    const resp = await fetch('/api/config/version')
    const data = await resp.json()
    setVersion(`V${data.count}`)  // data.count 是配置备份数，不是系统版本
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：从 /api/about 获取系统版本
    const resp = await fetch('/api/about')
    const data = await resp.json()
    setVersion(data.version)  // 系统版本号
    ```
  - **配置参数**：`coding_standards.source.verify_data_source`（默认 `true`，必须验证数据源语义正确性）
  - **适用场景**：所有显示版本/计数/统计数据的场景、从多个 API 获取类似字段的场景、数据源语义可能混淆的场景
  - **不适用场景**：单一明确数据源、内部计数（无歧义）、测试 mock 数据
  - **历史教训**：版本管理页显示 V10，用户以为是系统版本，实际是配置备份文件数。修复方式：从 `/api/about` 获取系统版本，废弃 `/api/config/version` 误用
  - **对应后端原则**：后端 `/api/about` 必须返回系统版本字段，规范源 xianyu-hunter-dev/references/coding-rules.md SOURCE-01（与 v4.20 F-REVIEW-VERSION-SOURCE-ALIGN 配合）

- 🆕v4.33【强制】**F-REVIEW-STATS-RANGE-CALIBRATE：统计范围校准**
  - 维度：16 性能评审
  - 严重等级：MEDIUM
  - **规范引用**：RANGE-01 统计范围校准（前端）
  - **检查点**：统计图表范围是否与业务范围匹配，避免统计范围过大导致图表不可读或误导
  - **判定标准**：**禁止**统计图表范围过大与业务范围不匹配（如价格直方图统计 0-10000 但任务定价范围仅 0-500），**必须**按业务范围过滤（task_id 过滤）+ 百分位校准（P5/P95）确保图表聚焦业务实际范围
  - **检查范围**：所有统计图表（直方图/折线图/散点图），特别是显示价格/数量/频率等业务指标的图表
  - **判断信号**（grep 检测）：
    - `grep -nE "type:\\s*['\"](histogram|line|scatter)" frontend/src/**/*.{ts,tsx}` 命中后检查统计范围是否与业务范围匹配
    - `grep -nE "min:\\s*\\d+.*max:\\s*\\d+" frontend/src/**/*.{ts,tsx}` 命中后检查 min/max 是否经过业务校准
    - 用户反馈"图表大部分是空白"/"数据集中在角落" → 必查统计范围校准
  - **反模式**：
    ```typescript
    // ❌ 错误：价格直方图统计范围 0-10000，与任务定价范围 0-500 不匹配
    const option = {
      xAxis: { min: 0, max: 10000 },  // 范围过大，数据集中在 0-500
      series: [{ type: 'histogram', data: prices }]
    }
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：task_id 过滤 + P5/P95 百分位校准
    const taskPrices = prices.filter(p => p.task_id === currentTaskId)
    const sorted = [...taskPrices].sort((a, b) => a.price - b.price)
    const p5 = sorted[Math.floor(sorted.length * 0.05)].price
    const p95 = sorted[Math.floor(sorted.length * 0.95)].price
    const option = {
      xAxis: { min: p5, max: p95 },  // 聚焦业务实际范围
      series: [{ type: 'histogram', data: taskPrices }]
    }
    ```
  - **配置参数**：无（纯业务逻辑校准，配置驱动通过 checklist.performance 开关）
  - **适用场景**：所有统计图表（直方图/折线图/散点图）、显示业务指标的图表、数据范围可能过大误导决策的场景
  - **不适用场景**：全量数据展示（无范围限制需求）、固定范围仪表盘、实时监控图表（范围动态）
  - **历史教训**：价格直方图统计范围 0-10000，但任务定价范围仅 0-500，导致图表大部分空白，用户无法看清分布。修复方式：task_id 过滤 + P5/P95 百分位校准聚焦业务范围
  - **对应后端原则**：无（纯前端图表校准），规范源 xianyu-hunter-dev/references/coding-rules.md RANGE-01

- 🆕v4.33【强制】**F-REVIEW-UI-SEMANTICS-SPLIT：按钮与状态语义分离**
  - 维度：3 React 组件规范
  - 严重等级：MEDIUM
  - **规范引用**：UI-SEMANTICS-01 按钮与状态语义分离
  - **检查点**：按钮文案是否表达动作（动词）、状态显示是否表达状态（名词/形容词），避免用户误判
  - **判定标准**：**禁止**按钮文案与状态显示混用（如红色"失效"既是按钮文案又是状态显示，用户无法判断是点击失效还是已失效），**必须**按钮文案表达动作（如"主动失效"/"批量失效"），状态显示表达状态（如"有效"/"已失效"）
  - **检查范围**：所有按钮文案、状态标签/徽章、操作列按钮
  - **判断信号**（grep 检测）：
    - `grep -nE "<Button[^>]*>[^<]*(失效|有效|启用|禁用)" frontend/src/**/*.{ts,tsx}` 命中后检查文案是动作还是状态
    - `grep -nE "<Tag[^>]*>[^<]*(失效|有效|启用|禁用)" frontend/src/**/*.{ts,tsx}` 命中后检查是否与按钮文案混用
    - 用户反馈"误点了失效按钮以为是状态显示" → 必查按钮与状态语义分离
  - **反模式**：
    ```typescript
    // ❌ 错误：红色"失效"是按钮而非状态显示，用户误判
    <Button danger onClick={handleDisable}>失效</Button>
    // 用户以为是状态标签，实际是点击触发失效操作
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：按钮文案表达动作（主动失效），状态显示表达状态（有效/已失效）
    <Space>
      {record.status === 'active' 
        ? <Button danger onClick={handleDisable}>主动失效</Button>
        : <Tag color="default">已失效</Tag>}
    </Space>
    ```
  - **配置参数**：`coding_standards.ui_semantics.button_text_must_be_action`（默认 `true`，按钮文案必须是动作）+ `coding_standards.ui_semantics.status_display_must_be_state`（默认 `true`，状态显示必须是状态）
  - **适用场景**：所有按钮文案、状态标签/徽章、操作列按钮、状态切换控件
  - **不适用场景**：图标按钮（无文案）、纯导航按钮（如"返回"）、确认对话框按钮（如"确定"/"取消"）
  - **历史教训**：列表操作列红色"失效"按钮被用户误以为是状态标签，导致误点击。修复方式：按钮文案改为"主动失效"，状态用 Tag 显示"已失效"
  - **对应后端原则**：无（纯前端 UI 语义），规范源 xianyu-hunter-dev/references/coding-rules.md UI-SEMANTICS-01

- 🆕v4.33【强制】**F-REVIEW-PERSIST-BUSINESS-SWITCH：用户可配置开关持久化**
  - 维度：10 Hooks 设计模式
  - 严重等级：HIGH
  - **规范引用**：PERSIST-01 用户可配置开关持久化
  - **检查点**：业务开关（如自动刷新/批量启用/调试模式）是否用 `usePersistentState` 持久化，避免刷新丢失
  - **判定标准**：**禁止**业务开关用 `useState`（刷新后丢失用户配置），**必须**用 `usePersistentState`（localStorage 持久化）；持久化 key 必须遵循 `xh.<page>.<field>` 命名模式（与 v4.24 F-REVIEW-UI-PREFERENCE-PERSISTENCE 配合）
  - **检查范围**：所有业务开关（自动刷新/批量启用/调试模式/高级筛选/暗色模式等用户可配置的布尔/枚举状态）
  - **判断信号**（grep 检测）：
    - `grep -nE "const\\s+\\[\\s*(autoRefresh|batchEnabled|debugMode|advancedFilter|darkMode)\\s*,\\s*\\w+\\]\\s*=\\s*useState" frontend/src/**/*.{ts,tsx}` 命中 → 违规
    - `grep -nE "usePersistentState\\(\\s*['\"]xh\\." frontend/src/**/*.{ts,tsx}` 未命中 → 检查业务开关是否缺少持久化
    - 用户反馈"刷新后开关重置为默认值" → 必查业务开关持久化
  - **反模式**：
    ```typescript
    // ❌ 错误：业务开关用 useState，刷新丢失
    const [autoRefresh, setAutoRefresh] = useState(false)
    // 刷新页面后 autoRefresh 重置为 false，用户配置丢失
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：业务开关用 usePersistentState（localStorage 持久化）
    const [autoRefresh, setAutoRefresh] = usePersistentState<boolean>(
      'xh.dashboard.autoRefresh',
      false,
      { validator: (v) => typeof v === 'boolean' }
    )
    ```
  - **配置参数**：`coding_standards.persist.business_switch_must_persist`（默认 `true`，业务开关必须持久化）+ `coding_standards.persist.storage_key_prefix`（默认 `xh.`，持久化 key 前缀）
  - **适用场景**：所有业务开关（自动刷新/批量启用/调试模式/高级筛选/暗色模式等用户可配置状态）
  - **不适用场景**：临时状态（如 loading/visible）、会话状态（如 currentStep）、敏感数据（如 token）、后端已持久化的字段（应从后端获取）
  - **历史教训**：批量刷新的自动刷新开关用 useState，用户刷新页面后开关重置为 false，导致用户需要重新开启。修复方式：改用 usePersistentState 持久化到 localStorage
  - **对应后端原则**：无（纯前端持久化），规范源 xianyu-hunter-dev/references/coding-rules.md PERSIST-01

- 🆕v4.33【强制】**F-REVIEW-ERROR-MESSAGE-PASS：错误消息透传**
  - 维度：20 API 数据源一致性与类型契约对齐
  - 严重等级：MEDIUM
  - **规范引用**：ERROR-01 错误消息透传（前端）
  - **检查点**：catch 块是否用 `extractApiError` 提取后端具体错误，避免显示无信息的通用错误
  - **判定标准**：**禁止**catch 块显示无信息的通用错误（如 `message.error('预览失败')`），**必须**用 `extractApiError` 提取后端具体错误（如 `message.error(extractApiError(err, '预览失败'))`），让用户看到后端根因
  - **检查范围**：所有 API 调用的 catch 块，特别是显示错误提示的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "catch\\s*\\([^)]*\\)\\s*\\{[^}]*message\\.error\\(['\"][^'\"]*失败['\"]" frontend/src/**/*.{ts,tsx}` 命中 → 违规（无具体错误）
    - `grep -nE "extractApiError" frontend/src/**/*.{ts,tsx}` 未命中 → 检查 catch 块是否缺少错误透传
    - 用户反馈"只显示保存失败，不知道具体原因" → 必查错误消息透传
  - **反模式**：
    ```typescript
    // ❌ 错误：catch 块显示无具体错误的通用提示
    try {
      await previewFile(id)
    } catch (err) {
      message.error('预览失败')  // 无具体错误，用户不知道根因
    }
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：用 extractApiError 提取后端具体错误
    try {
      await previewFile(id)
    } catch (err) {
      message.error(extractApiError(err, '预览失败'))
      // 显示如"预览失败：文件不存在"或"预览失败：权限不足"
    }
    ```
  - **配置参数**：`coding_standards.error.require_extract_api_error`（默认 `true`，catch 块必须用 extractApiError）
  - **适用场景**：所有 API 调用的 catch 块、显示错误提示的场景、用户需要知道错误根因的操作
  - **不适用场景**：纯前端错误（如表单校验）、网络层错误（无后端响应）、测试 mock
  - **历史教训**：文件预览失败时只显示"预览失败"，用户不知道是文件不存在还是权限不足，无法定位问题。修复方式：用 `extractApiError` 提取后端具体错误透传给用户
  - **对应后端原则**：后端必须返回结构化错误响应含 `error_code` + `message` 字段（与 v4.27 F-REVIEW-ERROR-CODE-BRANCH 配合），规范源 xianyu-hunter-dev/references/coding-rules.md ERROR-01

- 🆕v4.33【强制】**F-REVIEW-API-CONTRACT-CONSISTENCY：API 契约一致性**
  - 维度：11 类型安全评审
  - 严重等级：HIGH
  - **规范引用**：CONTRACT-01 API 契约一致性（前端）
  - **检查点**：TS interface 字段名是否与后端 response_model 一致，避免大小写/命名风格不一致导致数据显示为 0/undefined
  - **判定标准**：**禁止**TS interface 字段名与后端 response_model 不一致（如后端返回 `total`，前端期望 `total_for_type`），**必须**TS interface 字段名与后端 response_model 完全一致（snake_case 对 snake_case）；可选字段用 `field?: T`，可空字段用 `field: T | null`
  - **检查范围**：所有 `frontend/src/api/types.ts` 中的 interface/type 定义，与后端 Pydantic model 的字段名对比
  - **判断信号**（grep 检测）：
    - `grep -nE "interface\\s+\\w+[\\s\\S]{0,500}?\\s+\\w+:\\s" frontend/src/api/types.ts` 命中后与后端 model 对比字段名
    - `grep -nE "as\\s+any\\b|as\\s+unknown\\s+as" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否绕过类型检查掩盖契约不一致
    - 用户反馈"显示 0 条"/"字段显示 undefined" → 必查 API 契约一致性
  - **反模式**：
    ```typescript
    // ❌ 错误：后端返回 total，前端期望 total_for_type，导致显示 0 条
    interface EvaluationResult {
      total_for_type: number  // 后端实际返回 total，前端字段名不一致
    }
    const data: EvaluationResult = await resp.json()
    console.log(data.total_for_type)  // undefined，显示 0 条
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：TS interface 字段名与后端 response_model 完全一致
    interface EvaluationResult {
      total: number  // 与后端 Pydantic model 字段名一致
      total_for_type?: number  // 可选字段用 ?，可空字段用 | null
    }
    ```
  - **配置参数**：`coding_standards.contract.check_ts_interface_match`（默认 `true`，必须检查 TS interface 与后端 model 一致性）
  - **适用场景**：所有 API 响应类型定义、前后端字段契约对齐、类型安全检查
  - **不适用场景**：纯前端内部类型（无后端对应）、第三方 API 类型（按第三方文档）、归一化层类型（前后端字段映射）
  - **历史教训**：评估明细页后端返回 `total`，前端 TS interface 期望 `total_for_type`，导致显示 0 条。修复方式：TS interface 字段名与后端 response_model 完全一致
  - **对应后端原则**：后端 Pydantic model 字段名必须稳定，新增字段需同步前端 types.ts（与 v4.16 F-REVIEW-TYPE-CONTRACT-ALIGN 配合），规范源 xianyu-hunter-dev/references/coding-rules.md CONTRACT-01

---

### 29. 数据契约与时序（meta-rules #25-30 落地）🆕v4.34

> 本维度整合 `xianyu-hunter-dev` v4.30.0 的 meta-rules #25-30 前端侧审查要点，新增 6 项 F-REVIEW 检查点（F-REVIEW-110~115）。所有检查点强调配置驱动（参数在 `config.yaml` 的 `data_contract_temporal` 节点管理，不硬编码）与适用/不适用场景说明。后端对应规范为 `xianyu-backend-code-review` v4.29.0 维度 31 的 B-REVIEW-151~156。

- 🆕v4.34【强制】**F-REVIEW-110: 批量断路器四要素 UI 反馈（batch circuit breaker UI feedback）**
  - 维度：29 数据契约与时序
  - 严重等级：error
  - 规范引用：meta-rule #25 批量处理四要素
  - **检查点**：批量操作 UI 必须区分「用户主动停止」/「熔断可恢复」/「异常失败」三态，**禁止**一律显示"操作已取消"或"操作失败"。熔断可恢复态必须展示 `success_count` / `pending_count` / `failure_reason` / `recover_action`（如"重试剩余 12 个"按钮），与后端 `batch_circuit_breaker` 日志文案（`paused/stopped/failed`）一一对应
  - **判断信号**：
    - `grep "message\\.(warning|error)\\(['\"](?:批次已停止|批次失败).*['\"]\\)" frontend/src/**/*.{ts,tsx}` → 视为**必修 P0 缺陷**（缺少可恢复性提示）
    - `grep "Modal\\.confirm.*停止" frontend/src/**/*.{ts,tsx}` 但 success_count / pending_count 不展示 → 视为缺恢复信息
  - **配置参数**：`data_contract_temporal.batch_circuit_breaker.failure_threshold`（默认 `3`，与后端 B-REVIEW-151 一致）、`required_state_display`（默认 `[running, paused, failed, completed]`）、`required_pause_info`（默认 `[success_count, pending_count, failure_reason, recover_action]`）在 `config.yaml` 管理
  - **适用**：所有用户可中止的批量操作（批量删除/批量导入/批量上报/批量刷新/批量重试）
  - **不适用**：单次 API 调用、≤3 个 item 的小批量操作、定时后台任务（无用户交互入口）
  - **历史教训**：`batch_refresh_scheduler.py` 熔断后剩余项被标记 `skipped` 但前端仅显示"批次已停止"，用户无法判断是否可恢复，也无法看到"重试剩余 N 个"按钮，导致用户以为操作失败后只能重新发起全量

- 🆕v4.34【强制】**F-REVIEW-111: ErrorBoundary 完整 stack 上报（ErrorBoundary full stack report）**
  - 维度：29 数据契约与时序
  - 严重等级：error
  - 规范引用：meta-rule #26 关键路径异常保留完整 traceback
  - **检查点**：React 全局 `ErrorBoundary.componentDidCatch` 必须上报**完整 stack** 到监控服务（如 sentry / 自建 report 端点），**禁止**仅 `console.error` 打印或 `return null` 静默吞异常。后端关键路径（`_on_startup` / `run_migrations`）用 `logger.exception()` 完整堆栈，前端全局错误兜底必须用同等的"全量上报"语义
  - **判断信号**：
    - `grep "componentDidCatch\\(error[\\s\\S]{0,200}(?:console\\.(log|error)|return\\s+null)" frontend/src/**/*.{ts,tsx}` → 视为**必修 P0 缺陷**（吞异常）
    - ErrorBoundary 仅有 `return <h1>出错了</h1>` 无 `Sentry.captureException(error)` → 视为违规
  - **配置参数**：`data_contract_temporal.error_boundary.require_full_stack_report`（默认 `true`）、`forbidden_patterns`（默认 `[console.error_only, return_null]`）、`report_service`（默认 `sentry`，可改为自建 report 端点）在 `config.yaml` 管理
  - **适用**：所有路由层 ErrorBoundary、所有 lazy 加载模块的兜底 ErrorBoundary、所有全局错误拦截
  - **不适用**：业务层 try/catch（业务层应处理具体错误后展示 UI，不应被 ErrorBoundary 兜底）、测试代码中的 mock ErrorBoundary
  - **历史教训**：MainLayout 顶层 ErrorBoundary 仅 `console.error` 打印，生产环境用户报"页面空白"无法定位根因（无 stack、无 userId、无路由信息）。修复：接入 sentry 并补充 `errorInfo.componentStack` 上报

- 🆕v4.34【强制】**F-REVIEW-112: ISO datetime 统一解析与序列化（ISO datetime parse & serialize）**
  - 维度：29 数据契约与时序
  - 严重等级：warning
  - 规范引用：meta-rule #27 datetime 统一时区策略
  - **检查点**：前端展示后端 ISO datetime 必须用 `new Date(isoStr).toLocaleString('zh-CN', { hour12: false })` 解析后转本地时区，**禁止**直接字符串拼接（`iso + ' 创建'`）或字符串方法（`iso.replace('T', ' ').slice(0, 19)`）；前端→后端传递时间必须用 `Date.toISOString()` 保留时区，**禁止** `toString()` / `toLocaleString()` 丢失时区信息
  - **判断信号**：
    - `grep "['\"]\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}['\"]\\s*\\+\\s*['\"]" frontend/src/**/*.{ts,tsx}` → 视为违规（直接拼接）
    - `grep "\\w+_(at|seen|time|active)\\.(replace|slice|substring|substr)\\(" frontend/src/**/*.{ts,tsx}` → 视为违规（字符串方法解析）
    - `grep "(time|date|at)\\s*:\\s*\\w+\\.toString\\(\\)" frontend/src/**/*.{ts,tsx}` → 视为违规（toString 丢时区）
  - **配置参数**：`data_contract_temporal.datetime.parse_iso_method`（默认 `new Date(isoStr)`）、`display_method`（默认 `toLocaleString('zh-CN', { hour12: false })`）、`send_to_backend_method`（默认 `Date.toISOString()`）、`forbidden_parse_methods`（默认 `[replace, slice, substring, substr]`）、`forbidden_send_methods`（默认 `[toString, toLocaleString]`）在 `config.yaml` 管理
  - **适用**：所有展示后端 `created_at` / `updated_at` / `expires_at` / `last_seen_at` 等 ISO 字符串、所有前端→后端的时间字段提交（搜索/筛选/创建）
  - **不适用**：纯展示用 dayjs/day.js 库已封装解析、纯日期不含时间（年月日）、固定文案中的时间字符串
  - **历史教训**：订单列表后端返回 `created_at: "2026-07-05T10:00:00+00:00"`，前端 `isoStr.slice(0, 10)` 取日期直接显示 → 时区错位（UTC 时间当作本地时间，跨时区用户全部晚 8 小时显示）。修复：统一 `new Date(iso).toLocaleString('zh-CN', { timeZone, hour12: false })` 解析

- 🆕v4.34【强制】**F-REVIEW-113: 跨进程状态同步六步法（前端：SSE 推送 + 启动 refetch）**
  - 维度：29 数据契约与时序
  - 严重等级：warning
  - 规范引用：meta-rule #28 跨进程状态同步六步法
  - **检查点**：跨进程状态变更（如 Cookie 多层同步、批量进度、登录态变化）前端必须采用 **SSE 推送 + 启动 refetch** 模式，**禁止**用 `setInterval` 长间隔（≥4s）轮询替代 SSE 推送。SSE 推送失败时退化为短间隔（≤2s）轮询 + 启动时强制 refetch，与后端六步法配对
  - **判断信号**：
    - `grep "setInterval\\([^,]+,\\s*\\d{4,}\\)[\\s\\S]{0,300}//.*\\u4ee3\\u66ff.*SSE|//.*\\u4ee3\\u66ff.*SSE[\\s\\S]{0,300}setInterval" frontend/src/**/*.{ts,tsx}` → 视为违规（setInterval 替代 SSE）
    - SSE 错误处理缺 `visibilitychange` 重建 / 缺 `MAX_RECONNECT` 次数限制 → 与已有 F-REVIEW-SSE-ERROR-HANDLING 重复检查
  - **配置参数**：`data_contract_temporal.state_sync.prefer_sse`（默认 `true`）、`sse_substitute_setinterval`（默认 `forbidden`）、`max_setinterval_for_state_sync`（默认 `0`，表示禁止）、`marker_dir_for_frontend`（默认 `data/markers`）在 `config.yaml` 管理
  - **适用**：Cookie 状态变化推送、批量任务进度推送、登录态变化通知、配置变更广播
  - **不适用**：纯 UI 动画（与后端无关）、表单字段同步（父子组件 props）、单次 API 拉取后的本地轮询（≤1s 防抖）
  - **历史教训**：Cookie 状态变更后端写 marker，但前端用 `setInterval(refetch, 5000)` 轮询 → 5s 延迟 + 高频请求浪费。修复：后端通过 SSE `/api/events/stream` 主动推送 `cookie_status_changed` 事件，前端订阅后立即 refetch

- 🆕v4.34【强制】**F-REVIEW-114: 前端错误按 error_code 分支（error_code switch branch）**
  - 维度：29 数据契约与时序
  - 严重等级：error
  - 规范引用：meta-rule #29 前端错误按 error_code 分支
  - **检查点**：前端错误展示必须用 `switch (err.error_code)` 按后端 `reason_enum` 分支，**禁止**按文案子串判断（`if (err.message.includes('expired'))`）。`reason_enum` 与后端 `error_code_contract.reason_enum` 一一对应（`token_expired/anti_crawler/page_unavailable/rate_limited/login_expired/session_invalid/permission_denied/validation_error/internal_error/service_unavailable`）。前端常量集中在 `frontend/src/constants/errorCode.ts`
  - **判断信号**：
    - `grep "if\\s*\\(\\s*\\w+\\.(message|detail|msg)\\.(includes|indexOf|search|match)\\(['\"](?:expired|unavailable|rate limited|page unavailable|login expired|session invalid)" frontend/src/**/*.{ts,tsx}` → 视为**必修 P0 缺陷**（substring 判断）
    - 前端 import `errorCode` 常量缺失 → 视为违规（应从 `frontend/src/constants/errorCode.ts` 导入）
  - **配置参数**：`data_contract_temporal.error_code_branch.reason_enum_source`（默认 `xianyu-backend-code-review.error_code.reason_enum`，与后端单一可信源）、`recognized_error_codes`（默认 10 个 reason 值）、`forbidden_substring_patterns`（默认 `[expired, unavailable, rate_limited, login_expired, session_invalid]`）、`required_pattern`（默认 `switch\\s*\\(\\s*\\w+\\.error_code\\s*\\)`）、`frontend_constants_file`（默认 `frontend/src/constants/errorCode.ts`）在 `config.yaml` 管理
  - **适用**：所有 API 错误处理分支、所有 toast/notification 文案、所有 4xx/5xx 错误展示
  - **不适用**：本地表单校验（无后端响应）、开发环境 console.error 调试日志、第三方 SDK 错误（按 SDK 文档处理）
  - **历史教训**：前端 8 个组件用 `if (err.message.includes('expired'))` 判断 Cookie 过期 → 后端文案从「登录已过期」改为「会话已失效」后所有页面判断失效，统一显示「未知错误」。修复：建立前后端 `error_code` 契约，前端 `switch (err.error_code)` 分支

- 🆕v4.34【强制】**F-REVIEW-115: 业务关键字常量集中管理（business keyword centralization）**
  - 维度：29 数据契约与时序
  - 严重等级：warning
  - 规范引用：meta-rule #30 业务关键字常量集中管理
  - **检查点**：前端业务关键字（已售/已删除/宝贝不存在/卖掉了/已售罄等需正则匹配/includes 判断的字符串）**禁止**内联到组件（如 `if (text.includes('已售'))`），**必须**从 `frontend/src/constants/businessKeywords.ts` 导入，**必须**与后端 `config.yaml#business_keywords` 等价（通过 `tests/test_keyword_consistency.py` 验证）
  - **判断信号**：
    - `grep "['\"](?:已售|已删除|宝贝不存在|卖掉了|已售罄)['\"]" frontend/src/**/*.{ts,tsx}` → 视为违规（硬编码）
    - 业务代码 `if (text.includes('xxx'))` 但 xxx 不在 `businessKeywords.ts` → 视为违规
  - **配置参数**：`data_contract_temporal.business_keyword.constants_file`（默认 `frontend/src/constants/businessKeywords.ts`）、`backend_source`（默认 `xianyu-backend-code-review.business_keyword`，单一可信源）、`consistency_test`（默认 `tests/test_keyword_consistency.py`）、`categories`（默认 `[sold, deleted, loginExpired, antiCrawler]`）在 `config.yaml` 管理
  - **适用**：商品状态识别（已售/已删/在售）、错误提示文案匹配、风控标签识别、敏感词过滤
  - **不适用**：日志/异常消息中的自由文本、配置文件中的连接信息、测试用例中的 mock 数据
  - **历史教训**：Cookie 自愈系统的 `sold` 关键字集合在 3 处独立维护，新增「宝贝走丢了」时只更新了 2 处，第 3 处漏更新导致「已售商品」被误判为「在售」继续抢单。修复：抽取到 `config.yaml#business_keywords` + `frontend/src/constants/businessKeywords.ts` 集中管理，CI 跑一致性测试

---

### 30. 状态恢复前置校验前端侧 🆕v4.35

> 本维度对应 `xianyu-hunter-dev` v4.31.0 meta-rules #31 与后端 `xianyu-backend-code-review` v4.30.0 的 B-REVIEW-157（状态恢复前置校验）。前端侧新增 1 项 F-REVIEW 检查点（F-REVIEW-116），强调恢复/启动按钮点击时必须先调用后端 precheck 接口校验前置条件。前端无降级链日志场景，不新增 LOG-MERGE 对应检查点（meta-rules #32 仅后端适用）。

- 🆕v4.35【强制】**F-REVIEW-116：RESUME-PRECHECK-FRONTEND 恢复操作前端前置校验**
  - 维度：30 状态恢复前置校验前端侧
  - 严重等级：error（P0）
  - 规范引用：meta-rule #31 状态恢复前置校验（前端侧）+ 后端 B-REVIEW-157
  - **检查点**：前端"恢复/启动/继续"按钮点击时，必须先调用后端 precheck 接口校验前置条件（如 Cookie 层 valid、会话 active、连接可达），校验失败时禁用按钮 + 提示用户先解决根因（如重新登录），禁止绕过前端校验直接调 resume API
  - **检查项**：
    1. resume/启动按钮 `onClick` 必须调用 precheck API（如 `POST /api/<resource>/precheck`），获取 `{resume_blocked, reason_code, user_hint, retry_after}` 结构化响应
    2. precheck 失败时（`resume_blocked: true`）按钮 `disabled` + 提示 `user_hint`（如"请先重新登录闲鱼"），禁止直接调 resume API
    3. 冷却期内（`retry_after > 0`）按钮 `disabled` + 倒计时显示，倒计时结束后允许重新点击 precheck
    4. 禁止绕过前端校验直接调 resume API（如点击按钮立即 `fetch('/api/resume')` 无 precheck 调用）
  - **判断信号**：
    - `grep "onClick.*(resume|start|continue|恢复|启动|继续)" frontend/src/**/*.{ts,tsx}` 缺 precheck 调用 → 视为违规
    - resume/启动按钮无 `disabled` 状态绑定（`disabled={precheckBlocked}`）→ 视为违规
    - 直接调 resume API（`fetch('/api/<resource>/resume')`）无前置 precheck 调用 → 视为违规
    - 冷却期内按钮可点击（无倒计时逻辑）→ 视为违规
  - **配置参数**：`resume_precheck_frontend.precheck_endpoint_pattern`（precheck 端点模式，如 `/api/<resource>/precheck`）、`resume_precheck_frontend.required_response_fields`（响应必须字段，如 `["resume_blocked", "reason_code", "user_hint", "retry_after"]`）、`resume_precheck_frontend.cooldown_countdown_required`（冷却期倒计时是否必须，默认 true）、`resume_precheck_frontend.applicable_buttons`（适用按钮清单，如 `["task_resume", "session_recover", "connection_reconnect"]`）在 `config.yaml` 的 `resume_precheck_frontend` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.31.0 meta-rules #31 + 后端 `xianyu-backend-code-review` v4.30.0 B-REVIEW-157
  - **适用**：任务恢复按钮（如搜索任务暂停后恢复）、登录会话恢复（Cookie 失效后重新登录）、连接重连按钮（连接池断连后重连）
  - **不适用**：无前置依赖的普通启动按钮（如新建任务）、用户主动 pause 后的恢复（非异常触发，无 root_cause）、一次性表单提交按钮
  - **历史教训**：搜索任务 `t68bc149b` 因闲鱼会话失效被自动暂停后，用户在前端连续点击「恢复」按钮 4 次，但前端未调用 precheck 校验 Cookie 层状态，每次恢复后 13~22 秒内再次触发会话失效检测并暂停，形成"恢复→失效→暂停"无效循环。修复：前端「恢复」按钮 onClick 先调 `POST /api/tasks/precheck`，校验 `cookie_rotator` 的 identity/session 层 valid 状态，失效时按钮 disabled + 提示"请先重新登录闲鱼"，冷却期内显示倒计时，彻底消除无效循环

---

### 34. 规范治理（meta-rules #36-37 落地）🆕v4.37

> 本维度对应 `xianyu-hunter-dev` v4.33.0 meta-rules #36（规范沉淀门槛）与 #37（规范退化机制），与后端 `xianyu-backend-code-review` v4.33.0 维度 35 的 B-REVIEW-162/163 联动。前端侧新增 2 项 F-REVIEW 检查点（F-REVIEW-120/121），强调前端编码规范（F-REVIEW）的立项门槛与退化清理，防止过度规范化和规范膨胀。

#### F-REVIEW-120：SEDIMENTATION-THRESHOLD 规范立项前置计数（meta-rule #36 落地）

**规则**：新立前端编码规范（meta-rule / F-REVIEW / step）必须满足 ≥ `meta_rules_governance.sedimentation_threshold`（默认 3）个相似 bug 门槛，单一 bug 立规范需标 `experimental` 标签 + 1 季度观察期。

**关键约束**：
- 单一 bug 立规范（无 experimental 标签）→ 视为违规（规范膨胀风险）
- experimental 标签超 1 季度未升级为正式 → 视为废弃候选
- 例外豁免立规范但未标注豁免原因 → 视为不规范
- 计数阈值硬编码 → 视为违规（必须从 config 读取）

**判断信号**：
- `grep "🆕v4\\." SKILL.md` 新增维度标题但无对应的历史 bug 收集记录 → 视为违规
- `grep "experimental" SKILL.md` 标签超 1 季度未升级 → 废弃候选
- 新增 F-REVIEW 检查点但 `docs/standards/编码规范复盘.md` 无 ≥3 个相似 bug 记录 → 视为违规

**配置参数**：`meta_rules_governance.sedimentation_threshold`（相似 bug 计数门槛，默认 3）、`meta_rules_governance.sedimentation_time_window_months`（计数时间窗口，默认 6 月）、`meta_rules_governance.experimental_observation_quarters`（experimental 观察期，默认 1 季度）、`meta_rules_governance.sedimentation_exemption_categories`（例外豁免类别：security_vulnerability / data_loss / payment_damage）在 `config.yaml` 的 `meta_rules_governance` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.33.0 meta-rules #36 + 后端 `xianyu-backend-code-review` v4.33.0 B-REVIEW-162

**适用**：新增前端编码规范（F-REVIEW 检查点 / 维度 / step）的立项场景
**不适用**：安全漏洞类规范（XSS/CSRF/token 处理，立即立规范）、数据丢失类规范、付费受损类规范（这三类豁免 ≥3 次门槛）

**历史教训**：v4.36.0 新增维度 31-33（F-REVIEW-117/118/119）时，仅基于"通知中心菜单点击无反应"单一 bug 立规范，未满足 ≥3 个相似 bug 门槛，且未标 experimental 标签。虽因属于"注册式资源三件套契约"类问题（影响用户可导航功能入口）可申请豁免，但未在规范中标注豁免原因，导致无法审计。修复：本维度（F-REVIEW-120）作为规范治理元规范，强制要求后续新增规范必须满足门槛或标注豁免原因。

#### F-REVIEW-121：DEGRADATION-CLEANUP 规范退化清理（meta-rule #37 落地）

**规则**：利用率 < `meta_rules_governance.degradation_threshold`（默认 3 次/季度）的 F-REVIEW 检查点必须标记"待合并"或"待废弃"，1 季度观察期后废弃并移入 `version-history.md` Deprecated 章节。

**关键约束**：
- 利用率 < 3 次/季度的 F-REVIEW 未标记待合并/待废弃 → 视为违规
- 标记"待废弃"超 1 季度未处理 → 视为违规（废弃流程卡住）
- 安全类规范被标记退化 → 视为违规（安全类永不退化）
- 退化阈值硬编码 → 视为违规（必须从 config 读取）

**判断信号**：
- `grep "待废弃|deprecated" SKILL.md` 标记超 1 季度未处理 → 废弃流程卡住
- F-REVIEW 检查点在最近 1 季度审查报告中 0 命中且未标记待废弃 → 视为违规
- 安全类 F-REVIEW（如 fetch_credentials_include / no_token_in_localstorage）被标记退化 → 视为违规

**配置参数**：`meta_rules_governance.degradation_threshold`（利用率退化阈值，默认 3 次/季度）、`meta_rules_governance.observation_period_quarters`（待废弃观察期，默认 1 季度）、`meta_rules_governance.degradation_exemption_categories`（永不退化类别：security / config_driven）在 `config.yaml` 的 `meta_rules_governance` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.33.0 meta-rules #37 + 后端 `xianyu-backend-code-review` v4.33.0 B-REVIEW-163

**适用**：每季度末 F-REVIEW 检查点利用率统计与退化清理
**不适用**：安全类规范（XSS/CSRF/token 处理/认证白名单等永不退化）、配置驱动类规范（依赖 config 存在，config 存在则规范存在）

**历史教训**：v4.33.0 一次性新增 14 项 F-REVIEW（F-REVIEW-96~109），其中部分检查点（如 F-REVIEW-EMBEDDED-LAYOUT-HEIGHT）在后续季度审查中 0 命中，但未触发退化清理流程，导致规范堆积。修复：本维度（F-REVIEW-121）作为规范治理元规范，强制要求每季度统计利用率并清理低命中规范。

#### F-REVIEW-122：GLOBAL-AGGREGATE-TASK-FILTER 全局聚合任务级过滤（meta-rule #38 前端侧）🆕v4.38

**维度**：7 API 契约 / 11 数据展示

**规则**：前端聚合统计（如 Dashboard 价格区间分布、市场价比率分布）必须按当前任务的 `price_range`/`market_ratio` 配置过滤，禁止展示越界数据；前端展示聚合数据前必须确认后端已调用 `_filter_by_per_task_range` 过滤。

**关键约束**：
- 前端展示全局聚合数据但未确认后端按任务级配置过滤 → 视为违规（CRITICAL）
- 聚合数据中包含超出任务 `price_range` 的数据点 → 视为违规
- 聚合统计 UI 未标注"已按任务配置过滤" → 视为违规（WARNING）
- 前端自行实现过滤而非依赖后端 → 视为违规（应后端过滤，前端仅展示）

**判断信号**：
- `grep "aggregate\|stats\|distribution" frontend/src/` 后检查是否引用任务级配置过滤
- Dashboard 聚合组件未读取当前任务的 `price_range`/`market_ratio` → 视为违规
- 聚合数据响应中包含超出 `price_range` 的数据点 → 视为违规

**反模式**：
```typescript
// ❌ 前端展示全局聚合数据但未确认后端按任务级配置过滤
useEffect(() => {
  fetch('/api/items/price-distribution').then(res => res.json()).then(setDistribution);
  // 未传递 task_id 或 price_range，后端可能返回全局未过滤数据
}, []);
```

**正确模式**：
```typescript
// ✅ 前端传递 task_id，后端按任务级 price_range/market_ratio 过滤
useEffect(() => {
  fetch(`/api/items/price-distribution?task_id=${taskId}`).then(res => res.json()).then(setDistribution);
  // 后端必须调用 _filter_by_per_task_range 过滤
}, [taskId]);
```

**配置参数**：`meta_rules_38_42_frontend.global_aggregate_filter.enabled`（开关，默认 true）、`severity`（CRITICAL）、`required_filter_function`（后端必须调用的过滤函数名，默认 `_filter_by_per_task_range`）、`task_config_fields`（任务级配置字段列表，默认 `["price_range", "market_ratio"]`）在 `config.yaml` 的 `meta_rules_38_42_frontend.global_aggregate_filter` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #38 + step 184

**适用**：所有全局聚合统计（Dashboard 价格分布、市场价比率分布、评估统计等）
**不适用**：单任务详情页的数据展示（已天然按 task_id 过滤）、用户级全局配置页面

**历史教训**：Dashboard 的"捡漏价格参考"聚合统计未按任务级 `price_range` 过滤，导致展示越界数据（如 price_range 配置为 0-100 元，但聚合分布中包含 200 元的数据点），用户误以为系统配置错误。修复：后端聚合 API 必须调用 `_filter_by_per_task_range` 按任务级配置过滤，前端传递 `task_id` 参数。

#### F-REVIEW-123：LIST-CROSS-DOMAIN-INJECT 列表交叉数据批量注入（meta-rule #39 前端侧）🆕v4.38

**维度**：7 API 契约 / 10 性能

**规则**：列表渲染交叉数据（如商品列表注入最新评估价/订单状态）必须用批量 API 一次性获取，禁止循环中逐项 fetch；前端必须支持批量响应的 `id → value` 映射结构。

**关键约束**：
- 列表中逐项 fetch 交叉数据（如 `items.map(item => fetch(`/api/eval/${item.id}`))`）→ 视为违规（CRITICAL）
- 批量 API 响应未用 `id → value` 映射结构 → 视为违规（WARNING）
- 前端未处理批量响应中缺失的 id → 视为违规（应有 fallback）
- 循环中调用 db query 的模式（`for item in items: db.query(...)`）→ 视为违规

**判断信号**：
- `grep "items.map.*fetch\|for.*of.*fetch" frontend/src/` 命中 → 视为违规
- `grep "\.map\(.*await" frontend/src/` 命中 → 视为违规（循环中 await）
- 列表组件中每个 item 单独发起 API 请求 → 视为违规

**反模式**：
```typescript
// ❌ 列表中逐项 fetch 交叉数据（N+1 查询）
const itemsWithEval = await Promise.all(
  items.map(async (item) => {
    const eval = await fetch(`/api/eval/${item.id}`).then(r => r.json());
    return { ...item, eval };
  })
);
```

**正确模式**：
```typescript
// ✅ 批量 API 一次性获取，id → value 映射
const itemIds = items.map(i => i.id);
const evals = await fetch('/api/eval/batch', {
  method: 'POST',
  body: JSON.stringify({ ids: itemIds }),
}).then(r => r.json());
// evals 是 { id: evalData } 映射结构
const itemsWithEval = items.map(item => ({
  ...item,
  eval: evals[item.id] ?? null, // 缺失时 fallback
}));
```

**配置参数**：`meta_rules_38_42_frontend.cross_domain_inject.enabled`（开关，默认 true）、`severity`（WARNING）、`cache_ttl_seconds`（前端缓存 TTL，默认 300）、`batch_size_limit`（批量请求最大 id 数，默认 500）、`forbidden_loop_patterns`（禁止的循环模式列表）在 `config.yaml` 的 `meta_rules_38_42_frontend.cross_domain_inject` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #39 + step 185

**适用**：列表渲染交叉数据（商品列表注入评估价/订单状态、任务列表注入最新运行状态等）
**不适用**：单条详情页的数据获取、实时 SSE 推送的数据更新

**历史教训**：商品列表页每个商品单独 fetch 评估价，100 个商品触发 100 次 API 请求，页面加载时间从 200ms 膨胀到 5s+。修复：新增批量 API `/api/eval/batch`，前端一次性获取所有评估价并用 `id → value` 映射注入。

#### F-REVIEW-124：MULTI-FIELD-LINKED-SWITCH 多字段联动开关范式（meta-rule #40 前端侧）🆕v4.38

**维度**：3 React 组件 / 6 Zustand 状态管理

**规则**：多字段联动开关（如 mode + bargain_only）必须遵循"主开关决定副开关可见性"范式，副开关值在主开关关闭时必须清零而非保留；前端 UI 必须根据主开关状态动态显示/隐藏副开关。

**关键约束**：
- 副开关在主开关关闭时仍可见 → 视为违规（MAJOR）
- 副开关值在主开关关闭时未清零（保留旧值）→ 视为违规（CRITICAL）
- 主开关切换时未触发副开关 UI 更新 → 视为违规
- 前端 UI 未根据主开关状态动态显示/隐藏副开关 → 视为违规

**判断信号**：
- `grep "mode.*bargain_only\|main_switch.*sub_switch" frontend/src/` 后检查联动逻辑
- 主开关切换时副开关值未清零 → 视为违规
- 副开关组件未根据主开关状态条件渲染 → 视为违规

**反模式**：
```typescript
// ❌ 副开关值在主开关关闭时未清零，且 UI 未联动
const [mode, setMode] = useState('auto');
const [bargainOnly, setBargainOnly] = useState(false);
// mode 切换为 'notify' 时，bargainOnly 仍保留旧值，且 UI 仍显示副开关
useEffect(() => {
  // 缺少 bargainOnly 清零逻辑
}, [mode]);
```

**正确模式**：
```typescript
// ✅ 主开关切换时副开关清零，UI 联动显示/隐藏
const [mode, setMode] = useState('auto');
const [bargainOnly, setBargainOnly] = useState(false);

const handleModeChange = (newMode: string) => {
  setMode(newMode);
  // 主开关关闭时副开关清零
  if (newMode === 'notify') {
    setBargainOnly(false);
  }
};

// 副开关仅在主开关为 auto/semi_auto 时显示
{mode !== 'notify' && (
  <Switch checked={bargainOnly} onChange={setBargainOnly} />
)}
```

**配置参数**：`meta_rules_38_42_frontend.linked_switch_priority.enabled`（开关，默认 true）、`severity`（MAJOR）、`main_switch_field`（主开关字段名，默认 `mode`）、`filter_suffix`（副开关后缀，默认 `_bargain_only`）、`priority_matrix`（主开关值 → 副开关可见性映射）在 `config.yaml` 的 `meta_rules_38_42_frontend.linked_switch_priority` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #40 + step 186

**适用**：所有多字段联动开关场景（mode + bargain_only、auto_buy + notify_only 等）
**不适用**：独立无依赖的开关字段、单向不可逆的开关（如删除确认）

**历史教训**：任务配置中 `mode` 切换为 `notify` 时，`bargain_only` 字段仍保留旧值 `true`，导致后端在 notify 模式下仍尝试 bargain 逻辑引发异常。修复：前端主开关切换时必须清零副开关值，且 UI 根据 `priority_matrix` 动态显示/隐藏副开关。

#### F-REVIEW-125：RESUME-PRECHECK-STRUCTURED 状态恢复前置校验结构化响应（meta-rule #41 前端侧）🆕v4.38

**维度**：7 API 契约 / 11 错误处理

**规则**：前端调用 resume/start 接口必须处理结构化 precheck 响应（`{resume_blocked, reason_code, user_hint, retry_after, task_registered}`），禁止假设接口直接成功；precheck 失败时必须展示 `user_hint` 与 `retry_after` 倒计时。

**关键约束**：
- 前端调用 resume/start 接口未处理 `resume_blocked: true` 情况 → 视为违规（CRITICAL）
- precheck 失败时仅展示通用错误而非 `user_hint` → 视为违规
- 未展示 `retry_after` 倒计时 → 视为违规（WARNING）
- 前端假设 resume 接口直接返回成功 → 视为违规

**判断信号**：
- `grep "resume\|start\|unpause" frontend/src/` 后检查是否处理结构化响应
- resume 接口响应处理中无 `resume_blocked` 字段判断 → 视为违规
- 错误展示中未引用 `user_hint` 或 `retry_after` → 视为违规

**反模式**：
```typescript
// ❌ 假设 resume 接口直接成功，未处理 precheck 结构化响应
const handleResume = async () => {
  await fetch('/api/tasks/resume', { method: 'POST', body: JSON.stringify({ task_id: id }) });
  message.success('任务已恢复');
  // 未处理 resume_blocked: true 的情况
};
```

**正确模式**：
```typescript
// ✅ 处理结构化 precheck 响应，展示 user_hint 与 retry_after 倒计时
const handleResume = async () => {
  const res = await fetch('/api/tasks/resume', {
    method: 'POST',
    body: JSON.stringify({ task_id: id }),
  }).then(r => r.json());

  if (res.resume_blocked) {
    message.warning(res.user_hint);
    // 展示 retry_after 倒计时
    setRetryCountdown(res.retry_after);
    return;
  }

  message.success('任务已恢复');
};
```

**配置参数**：`meta_rules_38_42_frontend.precheck_structured_fields.enabled`（开关，默认 true）、`severity`（CRITICAL）、`required_fields`（结构化响应必须包含的字段列表，默认 `["resume_blocked", "reason_code", "user_hint", "retry_after", "task_registered"]`）、`forbid_raise`（是否禁止后端抛异常，默认 true）、`api_error_status`（precheck 失败时的 HTTP 状态码，默认 400）在 `config.yaml` 的 `meta_rules_38_42_frontend.precheck_structured_fields` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #41 + step 187

**适用**：所有 resume/start/unpause 接口的前端调用
**不适用**：首次创建任务（无 precheck 需求）、纯查询接口（无状态变更）

**历史教训**：前端调用 resume 接口时假设直接成功，但后端 precheck 检测到 cookie 过期返回 `resume_blocked: true`，前端仍展示"任务已恢复"导致用户困惑。修复：前端必须处理结构化 precheck 响应，precheck 失败时展示 `user_hint` 与 `retry_after` 倒计时。

#### F-REVIEW-126：CONFIG-DRIVEN-THRESHOLD-FALLBACK 配置化阈值兜底范式（meta-rule #42 前端侧）🆕v4.38

**维度**：11 配置驱动 / 11 错误处理

**规则**：前端使用的阈值参数（如 p10 百分位、market_ratio_threshold、price_range_tolerance）必须从后端配置 API 获取，禁止前端硬编码；配置 API 失败时必须用兜底默认值并 `console.warn`，禁止抛异常导致页面崩溃。

**关键约束**：
- 前端硬编码阈值参数（如 `const P10 = 0.10`）→ 视为违规（MAJOR）
- 配置 API 失败时抛异常导致页面崩溃 → 视为违规（CRITICAL）
- 配置 API 失败时未用兜底默认值 → 视为违规
- 配置 API 失败时未 `console.warn` 记录 → 视为违规（WARNING）

**判断信号**：
- `grep "const\s+P\d+\s*=\s*0\.\d+\|const\s+THRESHOLD\s*=" frontend/src/` 命中 → 视为违规
- 配置 API 调用无 try/catch 或 .catch() → 视为违规
- 配置 API 失败时无兜底默认值 → 视为违规

**反模式**：
```typescript
// ❌ 前端硬编码阈值，且配置 API 失败时抛异常
const P10_PERCENTILE = 0.10; // 硬编码
const config = await fetch('/api/config').then(r => r.json());
// 配置 API 失败时整个页面崩溃
```

**正确模式**：
```typescript
// ✅ 从后端配置 API 获取，失败时用兜底默认值并 console.warn
const FALLBACK_DEFAULTS = {
  p10_percentile: 0.10,
  market_ratio_threshold: 0.85,
  price_range_tolerance: 0.05,
};

const config = await fetch('/api/config').then(r => r.json()).catch((err) => {
  console.warn('配置 API 失败，使用兜底默认值', err);
  return FALLBACK_DEFAULTS;
});
```

**配置参数**：`meta_rules_38_42_frontend.config_fallback_defaults.enabled`（开关，默认 true）、`severity`（MAJOR）、`fallback_defaults`（兜底默认值映射，默认 `{p10_percentile: 0.10, market_ratio_threshold: 0.85, price_range_tolerance: 0.05}`）、`require_warning_log`（是否强制 console.warn，默认 true）在 `config.yaml` 的 `meta_rules_38_42_frontend.config_fallback_defaults` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #42 + step 188

**适用**：所有阈值参数（p10 百分位、market_ratio_threshold、price_range_tolerance 等）
**不适用**：纯 UI 展示参数（如颜色、字体大小）、无业务语义的常量

**历史教训**：前端硬编码 `P10_PERCENTILE = 0.10`，当后端配置调整为 `0.05` 时前端未同步，导致"捡漏价格参考"展示的"低于 P10"判定标准与后端不一致。修复：前端阈值参数必须从后端配置 API 获取，失败时用兜底默认值并 `console.warn`，禁止硬编码。

### 35. 跨层契约与测试同步（meta-rules #43-47 落地）🆕v4.39

> 本维度对应 `xianyu-hunter-dev` v4.35.0 meta-rules #43-#47（事件多发布点字段对齐 / 路由三重注册同步 / query string 保留 / 测试同步责任 / 外部依赖隔离），与后端 `xianyu-backend-code-review` 的 B-REVIEW-169~173 联动。前端侧新增 5 项 F-REVIEW 检查点（F-REVIEW-131~135），基于 2026-07-07 SEMI_AUTO 模式通知未触发确认类问题复盘（EVAL_PASSED 事件三处发布点 task_mode 字段不对齐 / 前端 sheetRegistry 未注册新路由 + findSheetMeta 未剥离 query string / useSheetSync 丢失 query string），使用 Sequential Thinking 4 维度复盘法提炼，强调跨层契约对齐与测试同步，确保事件多发布点字段集一致 / 路由三处注册同步 / 外部回链 query string 保留 / 接口签名变更同步测试 / 外部依赖显式 mock。所有检查点强调配置驱动（参数在 `config.yaml` 的 `cross_layer_contract_test_sync` 节点管理，不硬编码）与适用 / 不适用场景说明。

#### F-REVIEW-131：EVENT-MULTI-EMIT-ALIGN 事件多发布点字段对齐（meta-rule #43 前端侧）🆕v4.39

**维度**：15 SSE 重连 / 19 跨组件状态同步

**【强制】**前端消费方按事件 payload 字段分支时（如 `payload.task_mode` / `event.task_mode`），必须确认所有事件发布点（成功路径 / 失败路径 / 超时路径 / 降级路径）发布的字段集一致；任一字段缺失必须显式 fallback，禁止默认 `undefined` 进入分支逻辑导致静默无反馈。

**关键约束**：
- 同一事件类型在多个发布点（成功 / 失败 / 超时 / 降级）字段集不一致 → 视为违规（CRITICAL）
- 消费方按某字段分支（如 `task_mode === 'SEMI_AUTO'`）但无 fallback / else 分支 → 视为违规（WARNING）
- 事件字段名在前后端 / 不同发布点拼写不一致（如 `task_mode` vs `taskMode`）→ 视为违规
- 字段添加至某发布点但未同步到其他发布点 → 视为违规

**判断信号**：
- `grep "payload\.\|event\." frontend/src/` 按字段分支但无 fallback / else 分支 → 视为违规
- `grep -r "emit.*task_mode\|emit.*taskMode" backend/` 多个 emit 点字段集不一致 → 视为违规
- 前端 `switch (payload.xxx)` 但 case 列表与后端 emit 字段集不匹配 → 视为违规

**反模式**：
```typescript
// ❌ 按字段分支但无 fallback，且未确认所有发布点字段一致
useEffect(() => {
  const handler = (event: EvalEvent) => {
    if (event.task_mode === 'SEMI_AUTO') {
      showConfirmDialog(event);
    }
    // 缺少 else 分支：当 task_mode 字段未发布时静默无反馈
  };
  eventSource.addEventListener('eval_event', handler);
  return () => eventSource.removeEventListener('eval_event', handler);
}, []);
```

**正确模式**：
```typescript
// ✅ 字段缺失时显式 fallback，并定义事件类型契约
type EvalEvent = { task_mode: 'AUTO' | 'SEMI_AUTO' | 'MANUAL'; status: string };
const handler = (event: EvalEvent) => {
  switch (event.task_mode) {
    case 'SEMI_AUTO':
      showConfirmDialog(event);
      break;
    case 'AUTO':
    case 'MANUAL':
      autoRefresh(event);
      break;
    default:
      // 显式 fallback：字段缺失或未知值走默认分支
      console.warn('未知 task_mode，回退到 AUTO 流程', event);
      autoRefresh(event);
  }
};
```

**配置参数**：`cross_layer_contract_test_sync.event_multi_emit_alignment.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_field_fallback`（是否强制字段缺失 fallback，默认 true）、`event_type_contract_required`（是否强制事件类型契约定义，默认 true）、`emit_point_consistency_check`（是否检查后端多发布点字段一致，默认 true）在 `config.yaml` 的 `cross_layer_contract_test_sync.event_multi_emit_alignment` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #43 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-173

**适用**：消费 SSE / WebSocket / postMessage / 自定义事件的前端组件
**不适用**：纯内部 state 变更（无跨层事件传递）、字段为可选且消费方不依赖分支的场景

**历史教训**：SEMI_AUTO 模式通知未触发确认弹窗。根因：EVAL_PASSED 事件存在三处发布点（成功路径 / 异常路径 / 超时路径），某发布点 `task_mode` 字段拼写不一致或缺失，前端按 `task_mode === 'SEMI_AUTO'` 分支但无 fallback，导致字段缺失时静默跳过确认流程，用户报告"通知未触发"。修复：统一三处发布点字段集，前端增加 default 分支兜底。

#### F-REVIEW-132：ROUTE-TRIPLE-REGISTRATION 前端路由三重注册同步（meta-rule #44 前端侧）🆕v4.39

**维度**：3 路由与懒加载 / 14 三处映射同步

**【强制】**新增 SheetWorkspace 多页签路由必须 L1（路由根组件 `<Route>`）+ L2（路由注册表 sheetRegistry）+ L3（URL 同步 Hook useSheetSync）三处同步注册；任一处缺失视为路由链路断裂，会导致 URL 与页签状态不同步。

**关键约束**：
- 新增 `<Route>` 但路由注册表无对应条目 → 视为违规（CRITICAL）
- 路由注册表注册新路由但 URL 同步 Hook 未处理该 path → 视为违规（URL 不联动）
- URL 同步 Hook 处理某 path 但路由根组件无对应 `<Route>` → 视为违规（404 fallback）
- 路由 path 在三处拼写不一致（如 `/evaluations` vs `/evaluation`）→ 视为违规

**判断信号**：
- `git diff` 新增 `<Route path="...">` 但同 PR 路由注册表无对应条目 → 视为违规
- `grep "sheetRegistry" frontend/src/` 路由表与 `grep "<Route" frontend/src/` 数量不一致 → 视为违规
- `grep "useSheetSync" frontend/src/hooks/` 处理的 path 列表与路由注册表不一致 → 视为违规

**反模式**：
```typescript
// ❌ 路由根组件新增 Route，但路由注册表与 URL 同步 Hook 未同步
// L1: 路由根组件
<Route path="/evaluations/auto" element={<AutoEvalPage />} />
// L2: 路由注册表（未注册 /evaluations/auto）
// L3: URL 同步 Hook（未处理 /evaluations/auto，导致 URL 切换不联动页签）
```

**正确模式**：
```typescript
// ✅ 三处同步注册
// L1: 路由根组件
<Route path="/evaluations/auto" element={<AutoEvalPage />} />

// L2: 路由注册表
export const sheetRegistry = [
  { key: 'evaluations-auto', path: '/evaluations/auto', label: '自动评估' },
  // ...
];

// L3: URL 同步 Hook
const matched = sheetRegistry.find(s => s.path === location.pathname);
// URL 同步 Hook 必须处理 /evaluations/auto 路径，确保 URL 切换联动 sheet
```

**配置参数**：`cross_layer_contract_test_sync.frontend_route_registration.enabled`（开关，默认 true）、`severity`（CRITICAL）、`registration_layers_required`（必须同步的层列表，默认 `["app_route", "sheet_registry", "use_sheet_sync"]`）、`path_consistency_check`（是否检查 path 拼写一致，默认 true）、`auto_validate_on_diff`（是否在 git diff 时自动校验，默认 true）在 `config.yaml` 的 `cross_layer_contract_test_sync.frontend_route_registration` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #44 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-174

**适用**：SheetWorkspace 多页签应用、依赖 URL 同步 sheet 状态的多页签场景
**不适用**：独立路由如 /login / /onboarding（无 sheet 同步需求）、纯内部导航（无 URL 变更）

**历史教训**：新增 SEMI_AUTO 评估路由，仅在路由根组件添加 `<Route>`，但路由注册表未注册对应条目、URL 同步 Hook 未处理该 path，导致用户从外部链接进入该路由时 sheet 页签状态与 URL 不同步。修复：新增路由必须三处同步，CI 自动校验 path 一致性。

#### F-REVIEW-133：QUERY-STRING-RETAIN 外部回链 query string 保留（meta-rule #45 前端侧）🆕v4.39

**维度**：3 路由与懒加载 / 19 跨组件状态同步

**【强制】**URL 同步 Hook 必须以 `location.pathname + location.search` 完整拼接作为路由标识；路由匹配函数（如 findSheetMeta）必须剥离 query string 后再与路由表 path 比对，禁止把含 query 的完整 URL 直接与路由表 path 比较。

**关键约束**：
- URL 同步 Hook 仅用 `location.pathname` 拼接 URL（丢失 query string）→ 视为违规（CRITICAL）
- 路由匹配函数直接用完整 URL（含 query）与路由表 path 比较 → 视为违规（永远匹配失败）
- 外部回链的 query string 在 sheet 切换后丢失 → 视为违规
- 用 `window.location.href` 替代 `location.pathname + location.search` → 视为违规（含 hash / origin 不可控）

**判断信号**：
- `grep "location.pathname" frontend/src/hooks/` 命中但无 `location.search` 配对 → 视为违规
- `grep "findSheetMeta" frontend/src/` 内含 `pathname === path`（未先剥离 query）→ 视为违规
- `grep "window.location.href" frontend/src/hooks/` 命中 → 视为违规（应使用 location 对象拆分字段）

**反模式**：
```typescript
// ❌ URL 同步丢失 query string，路由匹配未剥离 query 直接比对
const useSheetSync = () => {
  const location = useLocation();
  // 仅用 pathname 拼接，外部回链的 ?task_id=xxx 丢失
  const url = location.pathname;
  setSheet(url);
};
const findSheetMeta = (fullPath: string) => {
  // 直接用含 query 的 fullPath 与路由表 path 比较，永远匹配失败
  return sheetRegistry.find(s => s.path === fullPath);
};
```

**正确模式**：
```typescript
// ✅ pathname + search 完整保留，路由匹配前剥离 query
const useSheetSync = () => {
  const location = useLocation();
  // 外部回链的 ?task_id=xxx 必须保留
  const url = location.pathname + location.search;
  setSheet(url);
};
const findSheetMeta = (fullPath: string) => {
  // 先剥离 query string，再与路由表 path 比对
  const pathname = fullPath.split('?')[0];
  return sheetRegistry.find(s => s.path === pathname);
};
```

**配置参数**：`cross_layer_contract_test_sync.external_callback_query_retention.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_search_retention`（是否强制保留 location.search，默认 true）、`require_query_strip_in_match`（是否强制路由匹配前剥离 query，默认 true）、`forbidden_location_apis`（禁止使用的 location API 列表，默认 `["window.location.href"]`）在 `config.yaml` 的 `cross_layer_contract_test_sync.external_callback_query_retention` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #45 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-175

**适用**：从外部通知 / 邮件 / 二维码回链的路由（含 query string 携带业务参数）、SheetWorkspace URL 同步 Hook
**不适用**：纯内部导航（无 query string）、无需保留 query 的简单路由跳转

**历史教训**：用户从通知中心点击回链进入 `/evaluations/auto?task_id=xxx`，但 URL 同步 Hook 仅用 pathname 同步 sheet，query string 丢失；同时路由匹配函数用完整 URL（含 query）与路由表 path 比对，永远匹配失败导致 sheet 显示首页。修复：URL 同步 Hook 必须 `pathname + search` 拼接，路由匹配函数必须先 `split('?')[0]` 剥离 query 再匹配。

#### F-REVIEW-134：TEST-SYNC-RESPONSIBILITY 测试同步责任（meta-rule #46 前端侧）🆕v4.39

**维度**：9 可测试性 / 20 API 数据源一致性与类型契约对齐

**【强制】**前端 API 接口签名变更 / Hook 签名变更 / mock 字段集调整 / 异步同步逻辑重构必须同 PR 同步更新对应 `__tests__/` 测试；测试覆盖率不允许因重构下降。

**关键约束**：
- API 签名变更（参数 / 返回类型 / 字段名）但同 PR `__tests__/` 无修改 → 视为违规（WARNING）
- Hook 签名变更但 Hook 测试未更新 → 视为违规
- mock 字段集调整但测试快照未更新 → 视为违规
- 异步同步逻辑重构（如 useEffect 改用 useSyncExternalStore）但测试用例未调整 → 视为违规

**判断信号**：
- `git diff` 生产代码 API 签名变更但同 PR `__tests__/` 无修改 → 视为违规
- `git diff` Hook 文件签名变更但同 PR Hook 测试文件无修改 → 视为违规
- `grep "vi.mock\|jest.mock" frontend/src/__tests__/` mock 字段集与生产代码字段集不一致 → 视为违规
- 测试覆盖率下降超过 5% → 视为违规

**反模式**：
```typescript
// ❌ API 签名新增字段但测试未更新，mock 仍用旧字段集
// api/evaluations.ts
export const fetchEvaluations = (): Promise<EvalItem[]> => {
  // 新增 task_mode 字段
};
// __tests__/api/evaluations.test.ts（未更新 mock，仍返回旧字段集）
vi.mock('@/api/evaluations', () => ({
  fetchEvaluations: vi.fn(() => Promise.resolve([{ id: '1', status: 'PASSED' }])),
  // 缺少 task_mode 字段，导致测试通过但生产代码按 task_mode 分支失败
}));
```

**正确模式**：
```typescript
// ✅ API 签名变更同步更新测试与 mock 字段集
// api/evaluations.ts
export type EvalItem = { id: string; status: string; task_mode: 'AUTO' | 'SEMI_AUTO' | 'MANUAL' };
export const fetchEvaluations = (): Promise<EvalItem[]> => { /* ... */ };
// __tests__/api/evaluations.test.ts（同步更新 mock 字段集）
vi.mock('@/api/evaluations', () => ({
  fetchEvaluations: vi.fn(() => Promise.resolve([
    { id: '1', status: 'PASSED', task_mode: 'SEMI_AUTO' },
    { id: '2', status: 'PASSED', task_mode: 'AUTO' },
  ])),
}));
// 新增 task_mode 分支测试用例
test('SEMI_AUTO 模式触发确认弹窗', async () => { /* ... */ });
```

**配置参数**：`cross_layer_contract_test_sync.test_synchronization.enabled`（开关，默认 true）、`severity`（WARNING）、`require_test_update_on_signature_change`（是否强制签名变更同步测试，默认 true）、`mock_field_set_sync_required`（是否强制 mock 字段集与生产代码同步，默认 true）、`coverage_drop_threshold_percent`（覆盖率下降阈值，默认 5）、`test_framework`（测试框架，默认 `vitest`）在 `config.yaml` 的 `cross_layer_contract_test_sync.test_synchronization` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #46 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-172

**适用**：前端 API 层重构、Hook 签名变更、异步同步逻辑（useEffect / useSyncExternalStore）重构、mock 字段集调整
**不适用**：纯样式调整（CSS / Tailwind class）、注释 / 文档修改、纯类型导入调整（无运行时影响）

**历史教训**：API 新增 `task_mode` 字段后未同步更新测试 mock，测试用例仍用旧字段集（无 task_mode）通过 CI，但生产环境按 task_mode 分支时字段缺失导致 SEMI_AUTO 确认弹窗未触发。修复：API 签名变更必须同 PR 同步测试与 mock 字段集，CI 校验覆盖率下降不超过阈值。

#### F-REVIEW-135：EXTERNAL-DEP-ISOLATION 外部依赖隔离测试可重复性（meta-rule #47 前端侧）🆕v4.39

**维度**：9 可测试性

**【强制】**前端测试中依赖 `fetch` / `localStorage` / `sessionStorage` / `window` / `import.meta.env` 等外部依赖必须显式 `vi.mock` / `vi.spyOn` / `vi.stubGlobal` / `vi.stubEnv` 隔离，禁止依赖生产 fallback 或运行时真实环境。

**关键约束**：
- 测试中调用 `fetch` 但无 `vi.spyOn(global, 'fetch')` → 视为违规（CRITICAL）
- 测试中读写 `localStorage` 但无 mock → 视为违规（CRITICAL）
- 测试依赖 `import.meta.env.VITE_XXX` 但无 `vi.stubEnv` → 视为违规（WARNING）
- 测试依赖 `window.location` 真实值 → 视为违规

**判断信号**：
- `grep "fetch\|localStorage\|sessionStorage" frontend/src/__tests__/` 命中但同文件无 `vi.mock\|vi.spyOn\|vi.stubGlobal` → 视为违规
- `grep "import.meta.env" frontend/src/__tests__/` 命中但无 `vi.stubEnv` → 视为违规
- `grep "window.location" frontend/src/__tests__/` 命中但无 mock → 视为违规
- 测试在 CI 与本地结果不一致（依赖真实环境）→ 视为违规

**反模式**：
```typescript
// ❌ 测试依赖真实 fetch 与 localStorage，无 mock 导致不可重复
test('fetchEvaluations 返回数据', async () => {
  // 直接调用 fetch，依赖运行时真实网络 / localStorage
  const data = await fetchEvaluations();
  expect(data).toHaveLength(2);
  // 测试在 CI 无网络环境下失败，本地有缓存通过
  localStorage.setItem('last_eval', JSON.stringify(data));
});
```

**正确模式**：
```typescript
// ✅ 显式 mock fetch / localStorage / env，测试可重复
test('fetchEvaluations 返回数据', async () => {
  vi.spyOn(global, 'fetch').mockResolvedValue({
    ok: true,
    json: () => Promise.resolve([{ id: '1', task_mode: 'SEMI_AUTO' }]),
  } as Response);
  vi.stubGlobal('localStorage', {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  });
  vi.stubEnv('VITE_API_BASE', '/api/v1');

  const data = await fetchEvaluations();
  expect(data).toHaveLength(1);
  expect(data[0].task_mode).toBe('SEMI_AUTO');
  vi.restoreAllMocks();
});
```

**配置参数**：`cross_layer_contract_test_sync.external_dependency_isolation.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_mock_for_external_deps`（是否强制外部依赖 mock，默认 true）、`external_deps_to_mock`（需 mock 的依赖列表，默认 `["fetch", "localStorage", "sessionStorage", "window", "import.meta.env"]`）、`forbid_real_env_in_test`（是否禁止测试依赖真实环境，默认 true）、`auto_restore_mocks`（是否自动 restoreAllMocks，默认 true）在 `config.yaml` 的 `cross_layer_contract_test_sync.external_dependency_isolation` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #47 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-177

**适用**：所有前端测试（单元测试 / 集成测试 / Hook 测试 / 组件测试）
**不适用**：纯函数测试（无外部依赖）、TypeScript 类型测试（`tsd`）、常量与枚举测试

**历史教训**：异步同步 Hook 测试依赖真实 `fetch` 与 `localStorage`，本地有缓存与网络通过，CI 无网络环境下失败；同时测试 mock 未设置 `task_mode` 字段，导致 mock 与生产代码字段集不一致。修复：所有外部依赖必须显式 `vi.spyOn` / `vi.stubGlobal` / `vi.stubEnv` mock，确保测试可重复。

---

### 36. 调度器运行时治理前端侧（meta-rules #48-51 落地）🆕v4.40

> 本维度对应 `xianyu-hunter-dev` v4.36.0 meta-rules #48（调度器运行时开关对称性）/ #49（时间参数配置化）/ #50（长生命周期对象状态清理）/ #51（用户输入时间表达式校验，experimental），与后端 `xianyu-backend-code-review` v4.37.0 维度 36 的 B-REVIEW-178/179/180/181 联动。前端侧新增 4 项 F-REVIEW 检查点（F-REVIEW-136~139），聚焦于：调度器开关状态在前端的可见性与同步、前端轮询间隔的配置化、React Hook 的 cleanup 机制、用户输入 cron 表达式的前端校验。

#### F-REVIEW-136：SCHEDULER-STATUS-SYNC 调度器开关状态前端同步（meta-rule #48 前端侧）🆕v4.40

**检查点**：前端必须实时同步后端调度器的开关状态（enabled/disabled），用户切换开关后必须调用后端 API 持久化，前端状态必须以 `GET /api/scheduler/status` 返回值为唯一可信源，禁止前端独立维护 `enabled` 状态。

**检查项**：
1. 调度器开关 UI 组件（Switch/Toggle）的 `checked` 状态必须从后端 `GET /api/scheduler/status` 响应读取，禁止前端独立 `useState` 维护
2. 用户切换开关后必须 `POST/PATCH /api/scheduler/config` 持久化到后端，前端状态更新必须在 API 成功响应后
3. API 失败时前端状态必须回滚到切换前值，并显示错误提示
4. 前端必须有定时轮询（如 `setInterval(fetchSchedulerStatus, 10000)`）同步后端状态，避免多端操作不一致
5. 轮询间隔从 `config.yaml` 读取不硬编码

**判断信号**：
- `grep "schedulerStatus\\|scheduler.*enabled" frontend/src/` 后检查状态来源是否为 API 响应 → 前端独立 `useState` 视为违规
- `grep "Switch.*onChange" frontend/src/` 后检查 onChange 是否调用 API → 缺失 API 调用视为违规
- `grep "setInterval.*scheduler" frontend/src/` 检查是否有定时轮询 → 缺失视为违规

**反模式**：
```typescript
// 前端独立维护 enabled 状态，不调用后端 API
const [enabled, setEnabled] = useState(false);
<Switch checked={enabled} onChange={setEnabled} />  // 缺 API 调用
```

**正确模式**：
```typescript
// 状态从后端 API 读取，切换时调用 API 持久化
const { status, updateConfig } = useSchedulerStatus();
const handleToggle = async (checked: boolean) => {
  const prev = status.enabled;
  // 乐观更新
  updateConfig({ enabled: checked });
  try {
    await api.patch('/api/scheduler/config', { enabled: checked });
  } catch (e) {
    // 失败回滚
    updateConfig({ enabled: prev });
    message.error('切换失败，已回滚');
  }
};
<Switch checked={status.enabled} onChange={handleToggle} />
```

**配置参数**：`scheduler_runtime_governance_frontend.scheduler_status_sync.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_api_source`（是否强制 API 为唯一可信源，默认 true）、`require_polling`（是否强制定时轮询，默认 true）、`polling_interval_ms`（轮询间隔，默认 10000）、`require_rollback_on_failure`（是否强制失败回滚，默认 true）在 `config.yaml` 的 `scheduler_runtime_governance_frontend.scheduler_status_sync` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.36.0 meta-rule #48 + 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-178

**适用**：所有调度器开关 UI（批量采集/Cookie 同步/状态回查）、配置页面中的功能开关组件
**不适用**：纯前端 UI 状态开关（如暗色模式/侧边栏折叠）、无后端持久化需求的临时开关

**历史教训**：前端批量采集开关 `useState(false)` 独立维护，用户切换后未调用后端 API，刷新页面后状态丢失；且多端操作时前端显示与后端实际状态不一致，用户以为已禁用但后端仍持续执行。

---

#### F-REVIEW-137：POLLING-INTERVAL-CONFIG 轮询间隔配置化（meta-rule #49 前端侧）🆕v4.40

**检查点**：前端所有定时轮询（`setInterval`/`setTimeout` 递归调用的轮询）的间隔时间必须从配置读取，禁止硬编码字面量数字；配置来源优先级：后端 API 响应 > 前端 config > 默认值。

**检查项**：
1. `grep "setInterval\\|setTimeout" frontend/src/` 后检查间隔参数来源 → 字面量数字视为违规
2. 轮询间隔必须从配置读取（如 `import { pollingInterval } from '@/config'` 或后端 API 响应）
3. 配置必须提供默认值兜底（如 `pollingInterval ?? 10000`）
4. 页面不可见时（`document.hidden`）必须暂停或降频轮询，使用 `Page Visibility API`
5. 组件卸载时必须 `clearInterval` 清理定时器

**判断信号**：
- `grep "setInterval\\([^,]*,\\s*\\d+\\)" frontend/src/` 匹配到字面量数字 → 视为违规
- `grep "document.hidden\\|visibilitychange" frontend/src/` 检查是否有页面可见性优化 → 缺失视为 WARNING

**反模式**：
```typescript
// 硬编码轮询间隔 10 秒
useEffect(() => {
  const timer = setInterval(fetchData, 10000);  // 字面量 10000
  return () => clearInterval(timer);
}, []);
```

**正确模式**：
```typescript
// 从配置读取轮询间隔，页面不可见时降频
const pollingInterval = config.pollingInterval ?? 10000;
useEffect(() => {
  let timer: number;
  const start = () => {
    timer = setInterval(fetchData, pollingInterval);
  };
  const stop = () => clearInterval(timer);
  // 页面不可见时暂停轮询
  const handleVisibility = () => {
    if (document.hidden) stop();
    else start();
  };
  document.addEventListener('visibilitychange', handleVisibility);
  start();
  return () => {
    stop();
    document.removeEventListener('visibilitychange', handleVisibility);
  };
}, [pollingInterval]);
```

**配置参数**：`scheduler_runtime_governance_frontend.polling_interval_config.enabled`（开关，默认 true）、`severity`（MAJOR）、`forbidden_literals_ms`（禁止的字面量毫秒数，默认 `[5000, 10000, 30000, 60000]`）、`require_default_fallback`（是否强制默认值兜底，默认 true）、`require_visibility_optimization`（是否强制页面可见性优化，默认 true）在 `config.yaml` 的 `scheduler_runtime_governance_frontend.polling_interval_config` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.36.0 meta-rule #49 + 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-179

**适用**：所有前端定时轮询场景（数据刷新/状态同步/心跳检测/SSE 断线重连）
**不适用**：防抖/节流场景（如搜索输入防抖 400ms，属于 UX 参数而非轮询间隔）、动画帧率（`requestAnimationFrame`）、一次性延迟执行（`setTimeout` 非递归）

**历史教训**：前端状态页 `setInterval(fetchStatus, 10000)` 硬编码 10 秒轮询，用户切到后台标签页后仍持续请求，浪费带宽与服务器资源；且间隔无法根据网络环境调整（弱网环境应降频）。

---

#### F-REVIEW-138：HOOK-CLEANUP-COMPLETENESS 长生命周期 Hook cleanup 完整性（meta-rule #50 前端侧）🆕v4.40

**检查点**：React Hook 中创建的所有副作用资源（定时器/事件监听器/WebSocket/SSE/订阅/AbortController）必须在 `useEffect` 的 cleanup 函数中完整清理，禁止遗漏导致内存泄漏或僵尸更新。

**检查项**：
1. `useEffect` 中创建的 `setInterval`/`setTimeout` 必须在 cleanup 中 `clearInterval`/`clearTimeout`
2. `useEffect` 中添加的 `addEventListener` 必须在 cleanup 中 `removeEventListener`
3. `useEffect` 中创建的 `WebSocket`/`EventSource`(SSE) 必须在 cleanup 中 `close()`
4. `useEffect` 中创建的 `AbortController` 必须在 cleanup 中 `abort()`
5. `useEffect` 中创建的 Zustand `subscribe` 必须在 cleanup 中调用返回的 `unsubscribe` 函数
6. 组件卸载后禁止更新 state（`isMounted` ref 或 `AbortController` 防护）

**判断信号**：
- `grep "useEffect" frontend/src/` 后逐个检查是否有 `return () => { ... }` cleanup → 缺失视为违规
- `grep "setInterval\\|addEventListener\\|new WebSocket\\|new EventSource" frontend/src/` 后检查对应 cleanup → 缺失视为违规
- `grep "subscribe(" frontend/src/` 后检查返回值是否在 cleanup 中调用 → 缺失视为违规

**反模式**：
```typescript
// useEffect 创建定时器但无 cleanup
useEffect(() => {
  setInterval(fetchData, 10000);  // 无 cleanup，组件卸载后仍执行
}, []);

// SSE 连接无 cleanup
useEffect(() => {
  const es = new EventSource('/api/events/stream');
  es.onmessage = (e) => setData(JSON.parse(e.data));
  // 缺 es.close() cleanup
}, []);

// Zustand subscribe 无 unsubscribe
useEffect(() => {
  store.subscribe((state) => setLocalState(state.value));
  // 缺 unsubscribe cleanup
}, []);
```

**正确模式**：
```typescript
// 完整 cleanup 模式
useEffect(() => {
  const timer = setInterval(fetchData, 10000);
  const es = new EventSource('/api/events/stream');
  es.onmessage = (e) => setData(JSON.parse(e.data));
  const unsubscribe = store.subscribe((state) => setLocalState(state.value));
  const abortController = new AbortController();

  return () => {
    clearInterval(timer);
    es.close();
    unsubscribe();
    abortController.abort();
  };
}, []);

// 组件卸载后防护 state 更新
useEffect(() => {
  let isMounted = true;
  fetchData().then((data) => {
    if (isMounted) setData(data);  // 卸载后不更新
  });
  return () => { isMounted = false; };
}, []);
```

**配置参数**：`scheduler_runtime_governance_frontend.hook_cleanup_completeness.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_cleanup_for`（必须 cleanup 的副作用类型列表，默认 `["setInterval", "setTimeout", "addEventListener", "WebSocket", "EventSource", "subscribe", "AbortController"]`）、`require_unmount_guard`（是否强制卸载后防护，默认 true）在 `config.yaml` 的 `scheduler_runtime_governance_frontend.hook_cleanup_completeness` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.36.0 meta-rule #50 + 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-180

**适用**：所有 React Hook（`useEffect`/`useLayoutEffect`/自定义 Hook）；创建副作用资源的组件；SSE/WebSocket 实时数据消费组件；Zustand store 订阅组件
**不适用**：纯计算 Hook（无副作用）、只读 Hook（如 `useMemo`/`useCallback`）、SSR 场景（无 DOM 环境）

**历史教训**：SSE 事件流组件 `useEffect` 中创建 `EventSource` 但无 cleanup，用户切换页面后 SSE 连接未关闭，持续接收事件并尝试 `setState`，导致"组件已卸载仍更新 state"的 React 警告与内存泄漏。

---

#### F-REVIEW-139：CRON-EXPR-FRONTEND-VALIDATE cron 表达式前端校验（meta-rule #51 前端侧，experimental）🆕v4.40 experimental

**检查点**：前端接受用户输入 cron 表达式的表单组件必须在提交前进行前端校验，解析失败的 cron 表达式必须显示结构化错误提示，最小间隔阈值从配置读取。

**检查项**：
1. 接受 cron 表达式输入的 `<Input>` / `<Input.TextArea>` 必须有前端校验（`onChange` 或 `onBlur` 触发）
2. 校验函数必须使用 `cron-parser` 或等价库解析表达式，解析失败显示结构化错误
3. 校验通过后必须计算最小执行间隔，低于阈值的显示警告（不阻塞提交但提示用户）
4. 最小间隔阈值从 `config.yaml` 读取（默认 60 秒）
5. 表单提交时必须再次校验，禁止提交无效 cron 表达式

**判断信号**：
- `grep "cron\\|schedule_cron" frontend/src/` 后检查是否有前端校验 → 缺失视为违规
- `grep "cron-parser\\|cronstrue" frontend/src/` 检查是否使用专业库解析 → 内联正则视为 WARNING

**反模式**：
```typescript
// 接受任意输入，无前端校验
<Input
  value={cronExpr}
  onChange={(e) => setCronExpr(e.target.value)}
  placeholder="* * * * *"
/>
// 提交时直接发送到后端，无前端校验
const handleSubmit = () => {
  api.post('/api/tasks', { schedule_cron: cronExpr });  // 无校验
};
```

**正确模式**：
```typescript
import { parseExpression } from 'cron-parser';

const validateCronExpr = (expr: string, minInterval: number = 60): {
  valid: boolean;
  error?: string;
  warning?: string;
} => {
  try {
    const interval = parseExpression(expr);
    const next1 = interval.next().toDate();
    const next2 = interval.next().toDate();
    const actualInterval = (next2.getTime() - next1.getTime()) / 1000;
    if (actualInterval < minInterval) {
      return {
        valid: true,
        warning: `最小执行间隔 ${actualInterval}s 低于建议阈值 ${minInterval}s，可能触发反爬封禁`
      };
    }
    return { valid: true };
  } catch (e) {
    return { valid: false, error: `cron 表达式格式错误: ${(e as Error).message}` };
  }
};

const [validation, setValidation] = useState({ valid: true });
const minInterval = config.cronMinIntervalSeconds ?? 60;

<Input
  value={cronExpr}
  onChange={(e) => {
    setCronExpr(e.target.value);
    setValidation(validateCronExpr(e.target.value, minInterval));
  }}
  status={validation.valid ? (validation.warning ? 'warning' : '') : 'error'}
/>
{validation.error && <Alert type="error" message={validation.error} />}
{validation.warning && <Alert type="warning" message={validation.warning} />}

const handleSubmit = () => {
  const result = validateCronExpr(cronExpr, minInterval);
  if (!result.valid) {
    message.error(result.error!);
    return;
  }
  api.post('/api/tasks', { schedule_cron: cronExpr });
};
```

**配置参数**：`scheduler_runtime_governance_frontend.cron_expr_frontend_validate.enabled`（开关，默认 true）、`severity`（MAJOR）、`min_interval_seconds`（最小间隔阈值，默认 60）、`require_parser_library`（是否强制使用专业库，默认 true）、`require_submit_revalidate`（是否强制提交时再次校验，默认 true）在 `config.yaml` 的 `scheduler_runtime_governance_frontend.cron_expr_frontend_validate` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.36.0 meta-rule #51（experimental）+ 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-181

**适用**：所有接受用户输入 cron 表达式的表单（任务调度配置/定时采集配置/状态回查配置）
**不适用**：系统内部固定 cron 表达式（非用户输入）、interval 触发器配置（已有 interval 参数）、一次性任务（无重复执行）

**历史教训**：任务调度配置页面接受任意 cron 表达式输入，无前端校验，用户输入 `* * * * *`（每分钟执行）直接提交到后端，后端虽有校验但前端无即时反馈，用户体验差且增加无效请求。

---

#### F-REVIEW-144：PARAM-CHAIN-EXEC-FRONTEND 参数链闭环验证（meta-rule #52 前端侧）🆕v4.42

**维度**：7 API 契约
**严重等级**：critical（P0，过滤参数未消费导致数据泄漏）

**检查点**：前端定义的 query 参数必须能在后端找到对应的消费逻辑，前端发送的过滤参数必须被后端实际消费

**检查项**：
1. 前端 API 调用传递的过滤参数（如 market_ratio、price_range）必须对应后端的消费函数
2. 前端 types.ts 中声明的过滤参数字段必须与后端 API 签名一致
3. 前端单元测试应验证"传参 vs 不传参"的请求 URL 差异

**判断信号**：
- `grep "market_ratio\|price_range" frontend/src/api/` 但后端无对应消费逻辑 → 视为违规
- 前端 types.ts 声明过滤参数但后端 API 签名无对应参数 → 契约不一致

**配置参数**：`param_chain_exec_frontend.metadata_whitelist`（默认同后端）在 `config.yaml` 的 `param_chain_exec_frontend` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.37.0 meta-rules #52

**适用**：所有有过滤参数的列表查询 API 前端调用
**不适用**：GET 单个资源详情、DELETE 接口、创建类 POST 接口

**历史教训**：前端传递 `market_ratio=0.85` 参数但后端 `evaluations_list.py` 未调用 `PriceStrategy.check`，导致过滤未生效。修复：前后端同步闭环

---

#### F-REVIEW-145：MODE-VERTICAL-CHAIN-FRONTEND 业务模式纵向链路一致性（meta-rule #53 前端侧）🆕v4.42

**维度**：4 业务逻辑
**严重等级**：critical（P0，模式退化导致业务逻辑失效）

**检查点**：前端必须为每个 mode 枚举值提供对应路由、页面、组件，mode 字段名前后端严格一致

**检查项**：
1. 前端枚举值必须与后端一致（如 AUTO/SEMI_AUTO/MANUAL）
2. 每个 mode 值在前端路由/页面/组件中都有引用
3. SEMI_AUTO 模式必须有确认路由（如 /confirm-buy）
4. mode 字段名严格 snake_case 透传，禁止 camelCase 转换

**判断信号**：
- `grep "SEMI_AUTO\|AUTO\|MANUAL" frontend/src/` 在路由/页面中未命中 → 链路断裂
- 前端 types.ts 用 `taskMode` 而后端用 `task_mode` → 命名漂移

**配置参数**：`mode_vertical_chain_frontend.required_layers`（默认 `["router","page","component","api_wrapper"]`）、`mode_vertical_chain_frontend.mode_field_names`（默认同后端）在 `config.yaml` 的 `mode_vertical_chain_frontend` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.37.0 meta-rules #53

**适用**：任务执行模式、通知模式、采集模式的前端实现
**不适用**：纯展示型 mode 字段、内部状态字段、单一布尔开关

**历史教训**：SEMI_AUTO 模式退化为 CONFIRM/NOTIFY，前端无 /confirm-buy 路由，用户点击通知无反应。修复：新增 ConfirmBuy 页面+路由

---

#### F-REVIEW-146：MOCK-SYNC-BOUNDARY-FRONTEND mock 同步与边界精确性（meta-rule #55 前端侧）🆕v4.42

**维度**：12 可测试性
**严重等级**：critical（P0，mock 错配导致测试假阳性/假阴性）

**检查点**：前端 vitest mock 类型必须与被 mock 对象的同步/异步特性匹配，mock 数据必须覆盖完整字段集

**检查项**：
1. 同步函数用 `vi.fn()`，异步函数用 `vi.fn().mockResolvedValue()` 或 `vi.mock()` 中用 async
2. mock 数据必须覆盖组件访问的所有字段
3. 测试必须断言副作用未发生（如未发起真实 API 请求）

**判断信号**：
- `grep "vi.fn\(\)" frontend/src/__tests__/` 但被 mock 函数是 async → 违规
- mock 数据缺字段导致组件渲染 NPE → 不完整

**配置参数**：`mock_sync_frontend.type_mapping`（默认 `{"sync":"vi.fn()","async":"vi.fn().mockResolvedValue()"}`）、`mock_sync_frontend.required_assertions`（默认 `["no_real_api_request","no_real_router_change"]`）在 `config.yaml` 的 `mock_sync_frontend` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.37.0 meta-rules #55

**适用**：所有 vitest 单元测试、集成测试中的 mock
**不适用**：E2E 测试、快照测试

**历史教训**：后端 AsyncMock 用在同步函数导致测试失败，前端类似问题用 vi.fn() mock 异步函数也会导致 await 失败

---

#### F-REVIEW-147：FILTER-RESULT-TRANSPARENCY-UI 过滤结果透明化 UI（meta-rule #56 前端侧）🆕v4.42

**维度**：7 API 契约
**严重等级**：warning（P1，用户无法理解"为何查不到数据"）

**检查点**：列表查询 UI 同时有 ≥2 个过滤参数时必须透明化展示当前生效的过滤规则组合

**检查项**：
1. 关键过滤参数提供 Tooltip 说明查询规则（用 QuestionCircleOutlined 图标）
2. 空结果时区分"无数据"vs"被过滤排除"vs"全部数据"三态（filter_summary）
3. UI 显式列出当前生效的过滤参数组合
4. 业务参数展示语义化文案（如"低于市场参考价 15%"而非"0.85"）

**判断信号**：
- `grep "filter.*range\|market.*ratio\|min.*max" frontend/src/pages/` 在列表 UI 但无 `Tooltip`/`filter_summary` → 违规
- `grep "empty.*data\|no.*data"` 但无 `filtered_count`/`total_count` 区分 → 违规

**配置参数**：`filter_transparency_ui.min_filter_params`（默认 2）、`filter_transparency_ui.required_elements`（默认 `["tooltip","filter_summary"]`）、`filter_transparency_ui.filter_summary_states`（默认 `["no_data","filtered_empty","all_data"]`）在 `config.yaml` 的 `filter_transparency_ui` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.37.0 meta-rules #56

**适用**：所有多参数列表查询 UI（评估明细/商品列表/订单列表/仪表盘过滤）
**不适用**：单一过滤参数、用户主动输入的查询条件、详情页

**历史教训**：用户调整"低于市场参考价"到 0.85 后，评估明细菜单仍能查出价格上限 800 的商品，且 UI 无任何提示当前生效的过滤规则。修复：在价格范围 label 处添加 QuestionCircleOutlined 图标+Tooltip 说明查询规则

---

#### F-REVIEW-148：ASYNC-AWAIT-SYNC-CHECK-FRONTEND async/await 同步性检查（meta-rule #57 前端侧）🆕v4.43

**维度**：10 Hooks 设计模式
**严重等级**：critical（P0，useEffect 直接传 async 函数导致 React 警告 + 内存泄漏）
**规范引用**：meta-rule #57 async/await 同步性静态检查（前端侧）

**检查点**：React useEffect 内 async 函数必须用 `.then()` 或 IIFE 包裹，禁止 `async () => {}` 直接传给 useEffect

**检查项**：
1. useEffect 回调函数禁止为 async 函数（`useEffect(async () => {...})` 视为违规）
2. useEffect 内的 async 操作必须用 IIFE 包裹或 `.then()` 链式调用
3. 必须用 `cancelled` 标志防止组件卸载后 setState（内存泄漏防护）
4. 事件回调（onClick/onSubmit）中的 async 函数必须处理 rejection

**判断信号**：
- `grep "useEffect(async" frontend/src/` → 视为违规
- `grep "useEffect.*async.*=>" frontend/src/` → 视为违规

**反模式**：
```typescript
// useEffect 直接传 async 函数
useEffect(async () => {
  const data = await fetchData();
  setData(data);
}, []);
// React 警告: "Effect callback cannot be async"
// cleanup 返回 Promise 导致取消逻辑失效
```

**正确模式**：
```typescript
useEffect(() => {
  let cancelled = false;
  (async () => {
    const data = await fetchData();
    if (!cancelled) setData(data);
  })();
  return () => { cancelled = true; };
}, []);
```

**配置参数**：`meta_rules_57_63_frontend.frontend_async_await_check.enabled`（默认 true）、`meta_rules_57_63_frontend.frontend_async_await_check.severity`（默认 CRITICAL）、`meta_rules_57_63_frontend.frontend_async_await_check.forbidden_patterns`（默认 `["useEffect(async", "useEffect.*async.*=>"]`）、`meta_rules_57_63_frontend.frontend_async_await_check.require_cancellation_flag`（默认 true）在 `config.yaml` 的 `meta_rules_57_63_frontend.frontend_async_await_check` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.38.0 meta-rule #57

**适用**：React useEffect 副作用、事件回调（onClick/onSubmit 等）中的 async 函数
**不适用**：top-level await（模块顶层）、`await import()` 动态导入、async generator 函数

**历史教训**：useEffect 直接传 async 函数导致 React 警告 "Effect callback cannot be async"，且 cleanup 返回 Promise 导致取消逻辑失效，组件卸载后异步操作仍 setState 引发内存泄漏

---

#### F-REVIEW-149：HTTP-ERROR-LOCALIZATION HTTP 错误本地化（meta-rule #59 前端侧）🆕v4.43

**维度**：7 API 契约
**严重等级**：warning（P1，优先用后端英文 detail 对中文用户不友好）
**规范引用**：meta-rule #59 HTTP 状态码精细化映射表（前端侧）

**检查点**：已知状态码优先用前端中文 `statusMessages[status]`，后端 detail 仅作 fallback

**检查项**：
1. 已知状态码优先用前端中文消息（`statusMessages[status]`）
2. 多状态码场景必须建立状态码 → 中文消息映射表
3. 未知状态码可回退到后端 detail，但必须标注 fallback 行为
4. 状态码映射表必须在 `api/<域>.ts` 顶层声明，禁止散落在组件内

**判断信号**：
- `grep "detail ||" frontend/src/` → 视为违规（优先用 detail 而非 statusMessages）
- `grep "message.error.*detail" frontend/src/` → 视为违规

**反模式**：
```typescript
catch (err) {
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail;
  message.error(detail || statusMessages[status]);  // 优先用后端英文 detail
}
// 用户看到 "Failed to collect item: detail page unavailable or item removed"
// 中文用户无法理解
```

**正确模式**：
```typescript
const COLLECT_ERROR_MESSAGES: Record<number, string> = {
  503: '官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动',
  403: '闲鱼登录已过期，请重新登录闲鱼',
  440: '闲鱼登录已过期，请重新登录闲鱼',
  441: '触发闲鱼反爬限制，请稍后重试或手动完成验证',
  410: '商品详情页加载失败或已下架，请稍后重试',
  502: '浏览器连接异常，请重启服务后重试',
};
catch (err) {
  const status = err?.response?.status;
  if (status != null && COLLECT_ERROR_MESSAGES[status]) {
    message.error(COLLECT_ERROR_MESSAGES[status]);
  } else {
    message.error(detail || fallbackMessage);
  }
}
```

**配置参数**：`meta_rules_57_63_frontend.frontend_http_error_localization.enabled`（默认 true）、`meta_rules_57_63_frontend.frontend_http_error_localization.severity`（默认 WARNING）、`meta_rules_57_63_frontend.frontend_http_error_localization.prefer_frontend_message`（默认 true）、`meta_rules_57_63_frontend.frontend_http_error_localization.status_messages_required`（默认 true）、`meta_rules_57_63_frontend.frontend_http_error_localization.fallback_to_detail`（默认 true）、`meta_rules_57_63_frontend.frontend_http_error_localization.localized_languages`（默认 `["zh-CN"]`）在 `config.yaml` 的 `meta_rules_57_63_frontend.frontend_http_error_localization` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.38.0 meta-rule #59

**适用**：所有 HTTP 错误响应处理（catch 块中读取 `err.response.status` 与 `err.response.data.detail`）
**不适用**：前端无对应状态码映射的未知错误、调试模式需展示原始 detail、纯技术内部错误不向用户展示

**历史教训**：useEvalCollect.ts 优先用后端 detail 展示 "Failed to collect item 1053036882534: detail page unavailable or item removed"，对中文用户不友好，用户无法理解错误含义。修复：建立 COLLECT_ERROR_MESSAGES 状态码映射表，优先用中文消息

---

#### F-REVIEW-150：ERROR-CHAIN-TRANSPARENT 错误链透明化（meta-rule #61 前端侧）🆕v4.43

**维度**：7 API 契约 / 4 业务逻辑
**严重等级**：warning（P1，仅展示"采集失败"无 reason 用户无法判断）
**规范引用**：meta-rule #61 异常日志语义保留规范（前端侧）

**检查点**：错误链路需透明展示 reason/failure_reason，用户可见错误必须含可操作建议

**检查项**：
1. 错误消息必须含 reason 字段（来自后端 failure_reason）
2. 错误消息必须含可操作建议（如"请重新登录闲鱼"）
3. 错误必须标注 retryable 让用户知道是否可重试
4. 多阶段降级链必须合并展示最终生效路径（如"官方采集失败 → 降级到模拟采集"必须在 UI 体现）

**判断信号**：
- `grep "message.error\|notification.error" frontend/src/` 后检查错误消息是否含 reason 与建议
- `grep "message.error\('采集失败'\)" frontend/src/` → 视为违规（无 reason）

**反模式**：
```typescript
message.error('采集失败');
// 用户无法判断是 cookie 过期还是反爬限制
// 需查看后端日志才能定位
```

**正确模式**：
```typescript
message.error({
  content: `采集失败：${reason}。建议：${actionHint}`,
  duration: 8,
});
// 或结构化展示
const errorDisplay = {
  title: '官方采集失败',
  reason: failure_reason,
  suggestion: getSuggestionByReason(failure_reason),
  retryable: isRetryable(failure_reason),
};
```

**配置参数**：`meta_rules_57_63_frontend.frontend_error_chain_transparent.enabled`（默认 true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.severity`（默认 WARNING）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.require_reason`（默认 true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.require_suggestion`（默认 true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.require_retryable_flag`（默认 true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.multi_stage_merge`（默认 true）在 `config.yaml` 的 `meta_rules_57_63_frontend.frontend_error_chain_transparent` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.38.0 meta-rule #61

**适用**：所有错误展示组件（message.error / notification.error / Modal.error）
**不适用**：纯成功场景、loading 状态、开发调试日志（console.error）

**历史教训**：前端仅展示"采集失败"无 reason，用户无法判断是 cookie 过期还是反爬限制，需查看后端日志才能定位。修复：错误消息含 reason + suggestion + retryable 三字段

---

#### F-REVIEW-151：EXTERNAL-RESOURCE-CLEANUP-FRONTEND 外部资源清理（meta-rule #62 前端侧）🆕v4.43

**维度**：10 Hooks 设计模式 / 6 Zustand 状态管理
**严重等级**：critical（P0，组件卸载后资源未释放导致内存泄漏与重复消息）
**规范引用**：meta-rule #62 外部资源生命周期配对管理（前端侧）

**检查点**：useEffect 内创建的订阅/定时器/AbortController 必须在 cleanup 中释放

**检查项**：
1. useEffect 内创建的 WebSocket 必须在 cleanup 中调用 `ws.close()`
2. useEffect 内创建的 EventSource 必须在 cleanup 中调用 `es.close()`
3. useEffect 内的 `setInterval`/`setTimeout` 必须在 cleanup 中调用 `clearInterval`/`clearTimeout`
4. useEffect 内的 `addEventListener` 必须在 cleanup 中调用 `removeEventListener`
5. useEffect 内的 AbortController 必须在 cleanup 中调用 `controller.abort()`
6. useEffect 必须返回 cleanup 函数（当创建了上述资源时）

**判断信号**：
- `grep "useEffect" frontend/src/` 后检查是否返回 cleanup 函数
- `grep "setInterval\|setTimeout\|addEventListener\|new WebSocket\|new AbortController" frontend/src/` 检查是否在 cleanup 中释放

**反模式**：
```typescript
useEffect(() => {
  const ws = new WebSocket('ws://localhost:8080');
  ws.onmessage = (e) => setMessage(e.data);
  // 缺少 return () => ws.close();
}, []);
// 组件卸载后 WebSocket 仍保持连接
// 导致内存泄漏与重复消息
```

**正确模式**：
```typescript
useEffect(() => {
  const controller = new AbortController();
  const ws = new WebSocket('ws://localhost:8080');
  ws.onmessage = (e) => setMessage(e.data);
  return () => {
    controller.abort();
    ws.close();
  };
}, []);
```

**配置参数**：`meta_rules_57_63_frontend.frontend_external_resource_cleanup.enabled`（默认 true）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.severity`（默认 CRITICAL）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.resource_types`（默认 `["WebSocket", "EventSource", "setInterval", "setTimeout", "addEventListener", "AbortController"]`）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.require_cleanup_return`（默认 true）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.pair_required`（默认 true）在 `config.yaml` 的 `meta_rules_57_63_frontend.frontend_external_resource_cleanup` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.38.0 meta-rule #62

**适用**：所有 useEffect 副作用中创建的外部资源（WebSocket/EventSource/定时器/事件监听器/AbortController）
**不适用**：无副作用的纯渲染组件、React 组件卸载时自动清理的资源（如 useState 管理的状态）

**历史教训**：useEffect 创建 WebSocket 但无 cleanup，组件卸载后 WebSocket 仍保持连接，导致内存泄漏与重复消息（每次组件重新挂载都会新建连接）

---

#### F-REVIEW-152 experimental：URL-STATE-SYNC-FALLBACK URL↔状态同步失败回退（meta-rule #64 前端侧）🆕v4.44 experimental

**维度**：3 React 状态管理 / 19 跨组件状态同步
**严重等级**：critical（P0，URL 与 active sheet 不一致导致 useParams 返回错误值，业务逻辑误判）
**规范引用**：meta-rule #64 URL↔状态同步失败回退（experimental）

**检查点**：SheetWorkspace 多页签应用中，URL 变化触发 openSheet 失败时，必须回退 URL 到当前 active sheet 的 path

**检查项**：
1. useSheetSync Hook 监听 URL 变化时，若 openSheet 返回 false（路径未注册/栈满），必须调用 `navigate(activeSheet.path, { replace: true })` 回退 URL
2. 回退必须在 URL 变化事件处理中同步执行，不能延迟到下一帧（防止 useParams 读取到错误的 URL）
3. 回退动作必须记录日志（`logger.debug('URL sync failed, fallback to active sheet')`）

**判断信号**：
- `grep "openSheet\|findSheetMeta" frontend/src/hooks/useSheetSync.ts` 后检查是否在 openSheet 失败时回退 URL
- `grep "navigate\|location.pathname" frontend/src/hooks/useSheetSync.ts` 检查是否有 fallback 逻辑

**反模式**：
```typescript
useEffect(() => {
  const sheet = findSheetMeta(location.pathname);
  if (sheet) {
    openSheet(sheet.id);
  }
  // 缺少 else { navigate(activeSheet.path, { replace: true }) }
}, [location.pathname]);
// URL 已改变但 activeId 未变 → useParams() 返回错误值 → isEdit 误判为 false
```

**正确模式**：
```typescript
useEffect(() => {
  const sheet = findSheetMeta(location.pathname);
  if (sheet) {
    const success = openSheet(sheet.id);
    if (!success) {
      // 栈满或路径未注册，回退 URL 到当前 active sheet
      navigate(activeSheet.path, { replace: true });
      logger.debug('URL sync failed, fallback to active sheet', { failedPath: location.pathname, fallbackPath: activeSheet.path });
    }
  } else {
    // 路径未注册，回退 URL 到当前 active sheet
    navigate(activeSheet.path, { replace: true });
    logger.debug('Sheet not found, fallback to active sheet', { path: location.pathname });
  }
}, [location.pathname, activeSheet, navigate, openSheet]);
```

**配置参数**：`url_state_sync_fallback` 节点（在 `config.yaml` 管理，不硬编码）：
- `enabled`（默认 `true`，开关本检查）
- `fallback_strategy`（默认 `replace`，回退策略：replace/push）
- `detection_patterns`（默认 `["navigate", "openSheet", "findSheetMeta"]`，需要检测的函数）
- `applicable_routes`（默认 `["/app/tasks", "/app/config/search"]`，适用路由白名单）

**对应编码规范**：详见 `xianyu-hunter-dev` v4.39.0 experimental meta-rule #64

**适用**：SheetWorkspace 多页签应用（useSheetSync Hook）；URL 与 sheet 状态双向同步场景
**不适用**：单页应用（无 SheetWorkspace）；静态路由（无动态 sheet 注册）

**历史教训**：任务修改流程中点击 Step 3「全局搜索配置」按钮，navigate('/app/config/search') 多了 /app 前缀（basename），findSheetMeta 返回 undefined，触发 React Router 重定向到 /。此时 URL 变为 /，但 activeId 仍指向 TaskEditor，useParams().id 返回 undefined，isEdit 误判为 false，提交时创建重复任务。

**experimental 观察期**：案例数<3 次，按 meta-rule #36 门槛规则标 experimental，观察期 2026-07-08 至 2026-10-08（1 季度）。观察期内若再出现 ≥2 个相似 bug 则升级为正式规范，否则废弃。

---

#### F-REVIEW-153 experimental：SW-CACHE-VERSION-SYNC SW 缓存版本同步（meta-rule #65 前端侧）🆕v4.44 experimental

**维度**：13 PWA 配置 / 10 Hooks 设计模式
**严重等级**：warning（P1，缓存旧版本导致功能异常，但用户可手动刷新解决）
**规范引用**：meta-rule #65 Service Worker 缓存版本同步（experimental）

**检查点**：PWA 应用构建时生成的版本哈希必须与前端运行时检测的版本一致，版本不一致时触发 skipWaiting 强制更新

**检查项**：
1. vite-plugin-pwa 配置必须生成版本哈希（`strategies: 'generateSW'`，`manifest: { version: process.env.VITE_BUILD_VERSION }`）
2. 前端必须在 sw.js 注册时监听 `updatefound` 事件，新 SW 进入 waiting 状态时提示用户刷新
3. 用户确认刷新时调用 `registration.waiting.postMessage({ type: 'SKIP_WAITING' })` 触发 skipWaiting
4. 版本检测必须在应用启动时执行（main.tsx 或 App.tsx），不能延迟到用户操作后

**判断信号**：
- `grep "vite-plugin-pwa" frontend/vite.config.ts` 检查是否配置版本生成
- `grep "updatefound\|SKIP_WAITING\|registration.waiting" frontend/src/` 检查是否有版本检测逻辑
- `grep "navigator.serviceWorker.register" frontend/src/` 检查是否有版本同步 Hook

**反模式**：
```typescript
// vite.config.ts 缺少版本配置
VitePWA({
  strategies: 'generateSW',
  // 缺少 manifest.version
});

// main.tsx 注册 SW 但无版本检测
navigator.serviceWorker.register('/sw.js');
// 用户缓存旧版本 → 功能异常（如 PC 端重定向到移动端）
```

**正确模式**：
```typescript
// vite.config.ts
VitePWA({
  strategies: 'generateSW',
  manifest: {
    version: process.env.VITE_BUILD_VERSION || Date.now().toString(),
  },
});

// useSWVersion.ts Hook
export function useSWVersion() {
  const [needsRefresh, setNeedsRefresh] = useState(false);

  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.ready.then((registration) => {
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                setNeedsRefresh(true);
              }
            });
          }
        });
      });
    }
  }, []);

  const skipWaiting = useCallback(() => {
    navigator.serviceWorker.ready.then((registration) => {
      if (registration.waiting) {
        registration.waiting.postMessage({ type: 'SKIP_WAITING' });
      }
    });
  }, []);

  return { needsRefresh, skipWaiting };
}
```

**配置参数**：`sw_cache_version_sync` 节点（在 `config.yaml` 管理，不硬编码）：
- `enabled`（默认 `true`，开关本检查）
- `version_detection`（默认 `updatefound`，版本检测方式：updatefound/manual）
- `skip_waiting_trigger`（默认 `postMessage`，触发方式：postMessage/reload）
- `hard_refresh_prompt`（默认 `true`，是否提示用户硬刷新）

**对应编码规范**：详见 `xianyu-hunter-dev` v4.39.0 experimental meta-rule #65

**适用**：PWA 应用（vite-plugin-pwa）；Service Worker 缓存静态资源场景
**不适用**：非 PWA 应用（无 Service Worker）；纯 SSR 应用（无客户端缓存）

**历史教训**：PC 端首次登录后重定向到 /app/m/（移动端），根因是浏览器缓存了旧版 sw.js，旧版 SPA 中 useMobileDetect.ts 用 pointer:coarse 触屏判断导致 PC 端误判为移动端。

**experimental 观察期**：案例数<3 次，按 meta-rule #36 门槛规则标 experimental，观察期 2026-07-08 至 2026-10-08（1 季度）。观察期内若再出现 ≥2 个相似 bug 则升级为正式规范，否则废弃。

---

## 快速自检

执行 `pwsh .trae/skills/xianyu-frontend-code-review/scripts/auto-scan.ps1` 自动检查以下阻塞项：

1. `fetch` 请求是否包含 `credentials: 'include'`
2. axios 是否设置 `withCredentials: true`
3. token 是否写入 `localStorage`（应优先 httpOnly cookie）
4. 是否使用 `dangerouslySetInnerHTML`
5. 是否使用 `any` 类型
6. 是否存在空 `.catch()` 块
7. 图标按钮是否缺少 `aria-label`
8. `v-for`/`map` 是否使用 index 作为 key
9. 是否使用 `enum`（应用字符串字面量联合）
10. `ConfigProvider` 是否在 `BrowserRouter` 外层
11. 三处映射是否同步（路由、菜单、sheetRegistry）
12. 是否使用 `JSON.parse(JSON.stringify())` 深拷贝（应用 `structuredClone`，S7784）
13. 页面组件是否使用 `minHeight: 100vh`（嵌入场景应用 `height: 100%`）
14. 交互元素文字是否使用 `colorBorder`（应用 `colorPrimary`，确保对比度）
15. 🆕 **S6819/S6844**：是否存在 `<div onClick>` / `<a onClick>` 无 href 的可点击元素（应用 `<button>` + 键盘事件）
16. 🆕 **S7503**：是否存在无 `await` 的 `async` 函数（应改同步函数）
17. 🆕 **S6767**：函数/组件是否存在未使用的 Props、State、参数
18. 🆕 **S7744**：是否存在 `as unknown as T` 多重断言链（应用类型守卫）
19. 🆕 **S7735**：useEffect 依赖数组是否完整（结合 ESLint react-hooks/exhaustive-deps 提示）
20. 🆕 **S6582**：是否存在 `a?.b` 中 a 已确认非空的冗余可选链
21. 🆕 **S1874**：被移除的 API 是否标注 `@deprecated` 而非直接删除
22. 🆕 **S6551**：是否使用 `for...in`（应用 `Object.keys/values/entries`）
23. 🆕 状态管理函数（`activateSheet`、`closeSheet` 等）是否同步更新所有相关字段（`minimized`/`activeId` 等）
24. 🆕 嵌入到 SheetWorkspace/MainLayout 的页面是否用 `height: 100%` 而非 `100vh`
25. 🆕 vitest 测试是否加 `--no-isolate` 参数（Node v24 兼容性）
26. 🆕 antd 组件测试是否 mock `window.matchMedia`（Drawer/Grid/Skeleton）
27. 【强制】EventSource 连接包含 lastEventId 记录（`e.lastEventId`）和重连时 `?last_event_id=` 参数传递
28. 【强制】SSE useEffect 包含 `visibilitychange` 监听器，且在 cleanup 中 `removeEventListener`
29. 【强制】SSE error 重连有 `MAX_RECONNECT` 上限，超限后放弃 SSE 退化为轮询
30. 【强制】全局事件监听（`visibilitychange`/`resize`/`scroll`）在 useEffect cleanup 中移除
31. 🆕v4.0 【强制】Tab/Accordion/Collapse 多视图共享数据是否 state 提升至父组件 + `destroyInactiveTabPane={false}`
32. 🆕v4.0 【强制】JSX 内是否存在 IIFE（`{(() => { ... })()}`），应提取为变量
33. 🆕v4.0 【强制】`target="_blank"` 外部链接是否配 `rel="noopener noreferrer"`
34. 🆕v4.0 【强制】图标+文字间距是否用显式 `marginRight`（非 JSX 空格）
35. 🆕v4.0 【强制】注释是否与代码逻辑一致（无误导性顺序/依赖约束说明）
36. 🆕v4.0 【强制】动态资源映射是否映射表+推断函数分离（非混合），业务参数是否通过配置管理
37. 🆕v4.1 【强制】SSE 流消费回调是否显式处理 `stage='error'` 分支（禁止与 `stage='done'`+0 结果混为一谈）
38. 🆕v4.1 【强制】SSE 错误事件是否按 `status` 分类处理（401/403 显示"前往登录"按钮、503/504 稍后重试、502 重启提示）
39. 🆕v4.2 **F-REVIEW-UI-STATE-INDEPENDENCE**（§3）：受控 UI 状态不应通过 useEffect 联动路由
40. 🆕v4.3 `new Proxy()` / `new MutationObserver()` 是否赋值给局部变量后丢弃（应赋值给实例属性/模块级变量）
41. 🆕v4.3 try/finally 块中 finally 引用的变量是否在 try 之前初始化为 null/undefined
42. 🆕v4.3 多个组件对同一概念（会话有效性/登录状态）做判断时，状态变更是否双向同步
43. 🆕v4.3 错误提示中引用的路由路径/API端点是否实际存在（前端路由已注册/后端已实现）
44. 🆕v4.4 **F-REVIEW-CONFIG-DRIVEN-TOGGLE**（§11）：高风险功能必须配置驱动，默认关闭
45. 🆕v4.5 **F-REVIEW-ERROR-SEMANTICS**（§11）：错误文案必须与后端根因语义匹配
46. 🆕v4.5 **F-REVIEW-CONFIG-LINKAGE**（§7）：配置项从表单到后端消费全链路可追踪
47. 🆕v4.6 **F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND**（§6）：多写入入口统一 updateState
48. 🆕v4.7 **F-REVIEW-FILTER-SCENARIO-FRONTEND**（§7）：按场景显式传递 include_failed 等标志
49. 🆕v4.7 **F-REVIEW-ASYNC-FEEDBACK**（§10）：异步操作 loading → success → error 三态反馈
50. 🆕v4.7 **F-REVIEW-DATA-FLOW-TRACE-FRONTEND**（§11）：字段为空按 5 点逐层追踪
51. 🆕v4.7 **F-REVIEW-REUSE-PATTERN-FRONTEND**（§18）：新增功能前 grep 复用既有模式
52. 🆕v4.8 **F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE**（§5）：暗色主题 token 动态覆盖
53. 🆕v4.9 **F-REVIEW-FREQ-STATS-POLLING**（§10）：累计统计类 API 前端定时刷新
54. 🆕v4.10 **F-REVIEW-FILTER-VISIBILITY**（§7）：filter_summary 三态提示策略
55. 🆕v4.11 **F-REVIEW-STATE-ENUM-ALIGN**（§4）：前后端状态枚举值严格对齐
56. 🆕v4.11 **F-REVIEW-STATE-MACHINE-UI**（§3）：状态机每个状态值有 UI 视觉标识
57. 🆕v4.11 **F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY**（§6）：多链路触发统一 refetch 入口
58. 🆕v4.13 **F-REVIEW-ERROR-CONTRACT-TIMEOUT**（§7）：模块级 statusMessages map + isAxiosTimeout()
59. 🆕v4.13 **F-REVIEW-RETRY-BACKOFF**（§7）：可重试错误按退避序列重试
65. 🆕v4.14 **F-REVIEW-FILTER-BACKEND-ALIGN**（§7）：前端过滤与后端分类逻辑对齐
66. 🆕v4.14 **F-REVIEW-FILTER-PAGINATION-ADAPT**（§10）：filterStatus 后同步调整 pagination 三参数
67. 🆕v4.14 **F-REVIEW-FILTER-EMPTY-STATE**（§3）：空状态判断用 filteredItems.length
68. 🆕v4.15 **F-REVIEW-DEBUG-CODE-CLEANUP**（§11）：临时 DEBUG 代码必须移除
69. 🆕v4.16 **F-REVIEW-STATE-FUNCTIONAL-ALIGN**（§3）：UI 状态与功能可用性一致
74. 🆕v4.20 **F-REVIEW-VERSION-SOURCE-ALIGN**（§7）：版本号源语义对齐 API
75. 🆕v4.21 **F-REVIEW-FIELD-NAME-ALIGN**（§20）：字段名三层一致性
76. 🆕v4.21 **F-REVIEW-CONFIG-PERSIST-VERIFY**（§20）：配置持久化端到端验证
77. 🆕v4.22 **F-REVIEW-PWA-CACHE-VERIFY**（§13）：PWA 三层缓存验证
78. 🆕v4.23 **F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION**（§11）：LLM 模型能力集中展示
79. 🆕v4.24 **F-REVIEW-UI-PREFERENCE-PERSISTENCE**（§10）：用户偏好类 UI 状态用 usePersistentState
80. 🆕v4.25 **F-REVIEW-THREE-STATE-NULL-SEMANTICS**（§7）：PATCH/PUT 清除覆盖显式传 null
81. 🆕v4.25 **F-REVIEW-ERROR-HANDLING-CONSISTENCY**（§20）：catch 块用 extractApiError
82. 🆕v4.25 **F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY**（§4）：默认值统一用 ?? 而非 ||
83. 🆕v4.27 **F-REVIEW-ERROR-CODE-BRANCH**（§25）：按 error_code 字段分支决策
84. 🆕v4.27 **F-REVIEW-PRECHECK-API-DELEGATION**（§25）：数据完整性预检委托后端
85. 🆕v4.27 **F-REVIEW-MOCK-FIELD-SET-SYNC**（§25）：mock 数据覆盖完整字段集
86. 🆕v4.32 **F-REVIEW-MULTI-USER-CONTEXT-ISOLATION**（§28）：多用户上下文按 user_id 隔离 + 切换时清空缓存
87. 🆕v4.32 **F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING**（§28）：token 走 httpOnly cookie + credentials:include + 401/440/441/403 状态码语义分支
88. 🆕v4.33 **F-REVIEW-EFFECT-MINIMIZE**（§3）：useEffect 禁止重置用户交互控制的状态（openKeys/expandedKeys/activeKey），应用 useState 初始化
89. 🆕v4.33 **F-REVIEW-STATE-ATOMICITY**（§3）：多字段状态切换必须同步更新（封装 transition 方法或单一状态枚举）
90. 🆕v4.33 **F-REVIEW-SSE-CONN-MGMT**（§15）：SSE 连接管理三要素（visibilitychange 监听 + last_event_id 回放 + 最大重试 10 次降级轮询）
91. 🆕v4.33 **F-REVIEW-ASYNC-RACE-GUARD**（§10）：异步请求用 useRef 维护最新请求 ID，响应回来时对比丢弃过期响应
92. 🆕v4.33 **F-REVIEW-THEME-DYNAMIC-ADAPT**（§5）：禁止硬编码主题色，必须根据 isDark 动态设置（rowHoverBg/headerBg 等）
93. 🆕v4.33 **F-REVIEW-EMBEDDED-LAYOUT-HEIGHT**（§3）：嵌入式布局用 height:100% + flex:1，禁止 minHeight:100vh
94. 🆕v4.33 **F-REVIEW-COMPONENT-REGISTRY**（§3）：ECharts/antd 组件必须 import + register，避免静默失败
95. 🆕v4.33 **F-REVIEW-FILTER-TRANSPARENCY**（§7）：数据被过滤时展示过滤原因和条数（Modal/Tooltip 展示 filter_summary）
96. 🆕v4.33 **F-REVIEW-DATA-SOURCE-VERIFY**（§18）：显示数据必须来自正确数据源（系统版本从 /api/about 而非 /api/config/version）
97. 🆕v4.33 **F-REVIEW-STATS-RANGE-CALIBRATE**（§16）：统计图表范围与业务范围匹配（task_id 过滤 + P5/P95 百分位校准）
98. 🆕v4.33 **F-REVIEW-UI-SEMANTICS-SPLIT**（§3）：按钮文案表达动作（主动失效），状态显示表达状态（已失效），禁止混用
99. 🆕v4.33 **F-REVIEW-PERSIST-BUSINESS-SWITCH**（§10）：业务开关用 usePersistentState 持久化，禁止 useState 刷新丢失
100. 🆕v4.33 **F-REVIEW-ERROR-MESSAGE-PASS**（§20）：catch 块用 extractApiError 提取后端具体错误，禁止无信息通用错误
101. 🆕v4.33 **F-REVIEW-API-CONTRACT-CONSISTENCY**（§11）：TS interface 字段名与后端 response_model 完全一致（snake_case 对齐）

> **F-REVIEW 检查点详细规则**：以上 50 项 F-REVIEW 检查点的核心机制 / 判断信号 / 修复模式 / 适用场景 / 不适用场景 / 历史教训详见对应维度章节（§+ 维度号）。配置参数在 `config.yaml` 的对应节点管理。

---

## 审查流程（4 阶段流水线）🆕v4.33

> v4.33 将原 5 阶段闭环（Phase 0-4）优化为 4 阶段流水线，新增 `coding_standards` 节点加载与 `coding-rules/` 主题文件加载，强化优先级分类（P0/P1/P2/P3）与结构化报告呈现。

### 阶段 1：上下文加载

1. **加载 config.yaml 配置**（含 `coding_standards` 节点，v4.33 新增）
   - 读取 `scope` / `priority` / `hard_constraints` / `checklist` / `coding_standards` 等节点
   - `coding_standards` 节点提供 14 项 F-REVIEW 检查点的阈值参数（effect/sse/theme/layout/registry/filter/ui_semantics/persist/race/error/contract/source 等）
2. **识别任务类型**（前端/后端/全栈）
   - 前端任务：加载 `frontend/src/` 下的 React/TypeScript/Ant Design 文件
   - 后端任务：转交 `xianyu-backend-code-review` 技能
   - 全栈任务：前后端协同审查，识别跨边界契约问题
3. **加载对应 `coding-rules/` 主题文件**（v4.33 新增规范源联动）
   - 从 `xianyu-hunter-dev/references/coding-rules/` 加载与本次审查相关的主题文件（如 EFFECT-01/SSE-01/THEME-01 等）
   - 每个 F-REVIEW checkpoint 引用对应规范编号，审查时加载规范详情
4. **确定评审范围**：
   - **待提交变更模式**：`git diff HEAD` + `git status` 提取改动的 `.tsx/.ts/.js` 文件
   - **指定文件模式**：用户明确指定的文件列表
   - **片段评审模式**：用户粘贴的代码片段（无文件路径时仅输出建议）
5. **应用 `scope.include_paths` / `scope.exclude_paths` 过滤**，截取 `scope.max_files_per_run` 个文件
6. **对每个待评审文件收集上下文**：
   - 使用 Read 工具读取完整文件内容
   - 使用 Grep 工具查找关键依赖（导入的组件/Hook/工具函数、Ant Design 组件、API 接口）
   - 使用 Grep 查找相关测试文件（`__tests__/*.test.ts(x)`）评估测试覆盖
   - 使用 Grep 查找相关类型定义（`types.ts`）评估类型一致性
   - 记录文件的最近修改历史（`git log --oneline -5 -- <file>`）

**判断逻辑**：范围必须收紧——只评审用户提供的或明确引用的文件，不顺便审查旁边代码。

### 阶段 2：分层扫描

按 `checklist` 配置的 28 大类逐层扫描，每个维度引用对应 F-REVIEW checkpoints，对比反模式示例识别问题。

**优先级排序**：`severity_order` × `category_order`
- 类型安全（CRITICAL）> 业务逻辑（HIGH）> 性能（MEDIUM）> 规范（LOW）
- 硬约束违规优先级最高，无论 severity 如何

**子阶段 2.1：常规规则匹配**

按 `checklist` 配置的 28 大类逐项检查（见上文"审查规则"章节），每个维度引用对应 F-REVIEW checkpoints。

**子阶段 2.2：配置驱动检查** 🆕v4.31

针对配置驱动的 F-REVIEW 检查点，必须在常规规则匹配后追加"配置驱动检查"子阶段，按以下顺序扫描：

1. **业务关键字硬编码扫描**（对应 F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION）
   - 用 Grep 扫描 `frontend/src/**/*.{ts,tsx}` 是否存在 `const \w*_KEYWORDS?\s*=\s*\[` 或 `\.includes\(['"](卖掉了|已售|已下架)` 模式
   - 命中后检查是否调用 `/api/config/text_features` 端点拉取后端配置；未调用 → 标记为"配置节点缺失"分类的 CRITICAL 问题
2. **事件类型前缀匹配扫描**（对应 F-REVIEW-EVENT-TYPE-EXACT-MATCH）
   - 用 Grep 扫描 `frontend/src/**/*.{ts,tsx}` 是否存在 `\.startsWith\(['"]\w+\.` 或 `\.indexOf\(['"]\w+\.\w` 模式
   - 命中后检查是否属于配置节点 `event_type_exact_match.allowed_prefix_grouping_scenarios` 允许的统计/日志场景；不属于 → 标记为 CRITICAL 问题
3. **字段名大小写敏感扫描**（对应 F-REVIEW-FIELD-NAME-CASE-SENSITIVE）
   - 用 Grep 扫描 `frontend/src/api/**/*.ts` 是否存在驼峰字段名（后端应为 snake_case），以及 `frontend/src/**/*.{ts,tsx}` 是否存在 `as any` 类型断言绕过
   - 命中后检查前端 `api/types.ts` 字段名是否与后端 Pydantic 模型一一对应；不一致 → 标记为 CRITICAL 问题
4. 🆕v4.32 **多用户上下文隔离扫描**（对应 F-REVIEW-MULTI-USER-CONTEXT-ISOLATION）
   - 用 Grep 扫描 `frontend/src/stores/` 是否存在未按 `user_id` 分桶的全局单例 store（如 `create<.*>\(\)\s*=>\s*\(\{\s*orders:` 模式）
   - 命中后检查用户切换路径是否调用 `queryClient.clear()` / `useGlobalStore.getState().reset()`；未调用 → 标记为 CRITICAL 问题（跨用户数据泄漏风险）
5. 🆕v4.32 **认证 token cookie 处理扫描**（对应 F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING）
   - 用 Grep 扫描 `frontend/src/api/**/*.ts` 的 `fetch(` 调用是否包含 `credentials: 'include'`，`axios.create` 是否包含 `withCredentials: true`
   - 用 Grep 扫描 `frontend/src/**/*.{ts,tsx}` 是否存在 `localStorage.(get|set)Item(['"]xh_token` 模式（token 不应存 localStorage）
   - 用 Grep 扫描 401 错误处理分支是否区分 401/440/441/403 状态码语义；未区分 → 标记为 CRITICAL 问题（用户频繁被踢出风险）
6. 🆕v4.33 **coding_standards 节点驱动扫描**（对应 F-REVIEW-96~109，14 项新检查点）
   - 按 `coding_standards` 节点配置的阈值参数扫描（effect/sse/theme/layout/registry/filter/ui_semantics/persist/race/error/contract/source）
   - 对比反模式示例识别问题，命中后引用对应规范编号（EFFECT-01/SSE-01/THEME-01 等）

**子阶段 2.3：硬约束合规性检查**

遍历 `hard_constraints.rules`，对每条规则：
1. 使用 Grep 工具扫描代码库（pattern 字段）
2. 匹配到的违规项记录到报告
3. 若 `hard_constraints.block_on_violation=true` 且发现 CRITICAL 违规，在报告中标记"阻止合并"

**判断逻辑**：硬约束违规优先级最高，无论 severity 如何，必须在报告中突出显示。本阶段识别的问题统一归入"配置节点缺失"分类（见 Template A），与常规规则匹配结果合并后进入阶段 3 优先级分类。

### 阶段 3：优先级分类 🆕v4.33

将阶段 2 识别的所有问题按 P0/P1/P2/P3 四级分类，决定修复优先级与是否阻塞合并。

| 优先级 | 含义 | 阻塞合并 | 示例 |
|--------|------|----------|------|
| **P0 阻塞性** | 安全漏洞/数据丢失/崩溃/认证绕过 | ✅ 是 | token 存 localStorage（F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING）、SSE 无限重连（F-REVIEW-SSE-CONN-MGMT） |
| **P1 严重** | 逻辑错误/性能问题/数据不一致 | ❌ 否（强烈建议修复） | useEffect 重置用户状态（F-REVIEW-EFFECT-MINIMIZE）、异步竞态（F-REVIEW-ASYNC-RACE-GUARD）、API 契约不一致（F-REVIEW-API-CONTRACT-CONSISTENCY） |
| **P2 改进** | 代码质量/可维护性/规范偏离 | ❌ 否 | 主题色硬编码（F-REVIEW-THEME-DYNAMIC-ADAPT）、统计范围过大（F-REVIEW-STATS-RANGE-CALIBRATE）、错误消息无透传（F-REVIEW-ERROR-MESSAGE-PASS） |
| **P3 微调** | 风格/注释/命名 | ❌ 否 | 按钮与状态语义混用（F-REVIEW-UI-SEMANTICS-SPLIT）、组件注册集中性（F-REVIEW-COMPONENT-REGISTRY） |

**判断逻辑**：
- P0 问题必须修复后才能合并，报告中标记"阻止合并"
- P1 问题强烈建议在本次迭代修复，报告中突出显示
- P2/P3 问题记录到 backlog，可在后续迭代修复
- 优先级映射到原有 severity：P0=CRITICAL、P1=HIGH、P2=MEDIUM、P3=LOW

### 阶段 4：结果呈现

按 `report.format` 生成结构化报告（Markdown），严格遵循**输出模板**（见 `templates/report-template.md` 与下方"结构化报告模板"）。

**报告结构**：
1. **审查概览**（审查范围/审查维度/问题统计 P0/P1/P2/P3/规范版本）
2. **问题详情**（按 P0→P3 优先级排序，每个问题含编号/维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示例）
3. **与上次审查对比**（🆕新增 / ✅已修复 / ⚠️仍存在）
4. **硬约束合规性检查结果**
5. **好的实践**（正面反馈）
6. **测试运行结果**（若 `verify.run_tests_after_review=true`）
7. **审查结论与修复验证指引**

**结构化报告模板**（v4.33 新增，每个问题按以下格式呈现）：

```markdown
#### [P0] F-REVIEW-96 useEffect 副作用最小化
- **规范引用**: EFFECT-01 useEffect 副作用最小化原则
- **维度**: §3 React 组件规范
- **代码位置**: MainLayout.tsx:358-362
- **问题描述**: useEffect 联动重置 openKeys，触发 SubMenu 动画遮挡
- **修复建议**: 完全移除 useEffect，openKeys 由 useState 初始化 + 用户交互控制
- **配置节点**: coding_standards.effect.disallow_reset_user_controlled_state
- **反模式示例**: useEffect(() => setOpenKeys(autoOpenKeys), [location.pathname])
```

---

## 评审范围判断

- **待提交变更模式**：`git diff HEAD --name-only` + 过滤 `.tsx/.ts/.js` 文件
- **指定文件模式**：用户明确列出文件路径
- **片段模式**：用户粘贴代码但无文件路径（仅输出建议，不输出 File:Line）
- **范围必须收紧**：不顺便审查旁边代码，不主动扩展到未提及的文件

## 误报识别判断

- 路径匹配 `scope.exclude_paths`：跳过
- 测试文件中的规范类问题：降级处理
- 生成代码（含 `// @generated` 注释或 `__generated__` 路径）：跳过
- 第三方库代码（`node_modules`）：跳过
- 类型定义文件（`.d.ts`）中的规范类问题：降级处理

## 修复建议判断

- 必须提供可操作的修复建议（含代码示例）
- 建议必须解释"为什么"而非仅"做什么"
- 优先建议抽取纯函数、共享常量、共享组件
- 若问题需要代码修改，在报告末尾询问用户是否应用修复

## 抽象建议判断（闲鱼项目特色）

- 重复的内联样式（`abstraction_thresholds.inline_style_repeat` 默认 3 处）：建议抽取共享组件或样式常量
- 重复的文案（`abstraction_thresholds.text_literal_repeat` 默认 2 处）：建议抽取共享文案常量
- 复杂的优先级/判定逻辑：建议抽取为纯函数并配套单元测试
- 跨组件共享的状态逻辑：建议抽取为自定义 Hook
- 函数行数超过 `function_max_lines`（默认 50）：建议拆分
- 组件行数超过 `component_max_lines`（默认 300）：建议拆分
- 嵌套深度超过 `max_nesting_depth`（默认 4）：建议重构（SonarQube S2004）

## 失败恢复机制

1. **文件读取失败**：记录跳过原因，继续评审其他文件
2. **Grep 超时**：缩小搜索范围或跳过该检查项
3. **测试运行失败**：输出测试失败信息，不阻止报告生成
4. **配置文件缺失**：使用内置默认配置并提示用户创建 `config.yaml`
5. **TypeScript 编译错误**：记录但继续评审，不阻止报告生成

---

## 审查判断标准

| 🟠阻塞(必须修复) | 🟠严重(强烈建议) | 🟡警告(建议) |
|-----------------|-----------------|-------------|
| `fetch` 请求未包含 `credentials: 'include'` | 未复用组件 | 缩进不规范 |
| axios 未设 `withCredentials: true` | UI 不一致 | 变量命名不规范 |
| token 写入 `localStorage` | 缺注释 | 冗余代码 |
| 使用 `dangerouslySetInnerHTML` | 验证规则不完整 | 注释不清晰 |
| 使用 `any` 类型 | 错误处理不完善 | 缺少类型注解 |
| 空 `.catch()` 块 | 空指针风险（链式调用未判空） | 缺少测试 |
| `v-for`/`map` 使用 index 作为 key | `useEffect` 依赖数组不完整 | 缺少文档字符串 |
| `ConfigProvider` 在 `BrowserRouter` 内层 | `useMemo`/`useCallback` 缺失 | 嵌套层级过深 |
| 三处映射不同步（路由/菜单/sheetRegistry） | `requestId` 竞态保护缺失 | 注释复述代码 |
| `enum` 替代字符串字面量联合 | `mountedRef` 缺失（卸载后 setState） | 魔法数字未提取 |
| `JSON.parse(JSON.stringify())` 深拷贝 | `refreshingRef` 并发保护缺失 | 魔法字符串 |
| 使用 `interface`（应用 `type`） | `lazyRetry` 未包装 | 函数过长 |
| `main.tsx` 入口配置错误 | `SSE_LAST_EVENT_ID_KEY` 缺失 | 缺少 `__all__` |
| 函数嵌套 > 4 层（S2004） | PWA `runtimeCaching` 未排除 `/api/events/stream` | - |
| 认知复杂度 > 15（S3776） | 路由切换未重置滚动位置 | - |
| `vite.config.ts` `base` 错误 | `partialize` 未过滤 ReactNode | - |
| 构建产物未输出到 `web/static/spa` | store 感知路由库（未用 `_navigator` 注入） | - |
| 使用箭头函数定义组件 | `useEffect` 依赖数组缺失导致 stale closure | - |
| 嵌入页面用 `minHeight: 100vh`（应 `height: 100%`） | `activateSheet` 未同步恢复 `minimized` | - |
| 交互元素文字用 `colorBorder`（应 `colorPrimary`） | antd 组件测试未 mock `matchMedia` | - |
| 状态变更操作未同步更新所有相关字段 | vitest 命令缺少 `--no-isolate` | - |
| 🆕 `<div onClick>`/`<a onClick>` 无 href（S6819/S6844） | 🆕 `useEffect` 依赖缺失导致 stale closure（S7735） | - |
| 🆕 无 `await` 的 `async` 函数（S7503） | 🆕 冗余可选链 `a?.b` 中 a 已非空（S6582） | - |
| 🆕 未使用的 Props/State/参数（S6767） | 🆕 重复内联样式 `abstraction_thresholds.inline_style_repeat` 次以上 | - |
| 🆕v4.0 Tab 切换数据丢失（state 未提升） | 🆕v4.0 JSX 内 IIFE 未提取为变量 | - |
| 🆕v4.0 外部链接缺 `rel="noopener noreferrer"` | 🆕v4.0 图标文字间距依赖 JSX 空格 | - |
| 🆕v4.0 注释与代码逻辑不一致（误导性约束说明） | 🆕v4.0 动态资源映射表与推断函数混合 | - |
| 🆕v4.1 SSE 流消费回调未处理 `stage='error'` 分支 | 🆕v4.1 SSE 错误事件未按 `status` 分类（401/403 应显示"前往登录"按钮） | - |
| 🆕v4.1 SSE 错误事件与"真的没货"（`stage='done'`+0 结果）混为一谈 | - | - |
| 🆕v4.2 受控 UI 状态（`openKeys`/`expandedKeys`）通过 `useEffect` 联动路由变化（产生非用户触发的展开/折叠动画） | - | - |
| 🆕v4.3 Proxy/Observer 赋值给局部变量后丢弃（死代码） | 🆕v4.3 跨组件对同一概念判断维度未同步 | - |
| 🆕v4.3 try/finally 变量未初始化为 null/undefined | 🆕v4.3 错误提示引用不存在的路由/端点 | - |
| 🆕v4.4 高风险前端功能默认启用（应默认关闭+配置驱动）（F-REVIEW-CONFIG-DRIVEN-TOGGLE） | 🆕v4.4 功能参数硬编码在组件内（应集中在 `constants.ts` 的 `FEATURE_TOGGLES`/`FEATURE_CONFIGS` 节点管理） | - |
| 🆕v4.5 错误提示文案与后端错误根因语义不匹配（如 token 过期显示"登录已过期"）（F-REVIEW-ERROR-SEMANTICS） | 🆕v4.5 前端配置项未传递给后端 API（配置无效化）（F-REVIEW-CONFIG-LINKAGE） | - |
| 🆕v4.9 累计统计类 API（频率伪装统计 / 健康评分 / 计数器）仅在 useEffect 初始化时拉一次，缺少 setInterval 定时刷新（F-REVIEW-FREQ-STATS-POLLING） | 🆕v4.9 setInterval 间隔数字（10000/30000）硬编码在组件内（应来自 `config.yaml` 的 `freq_stats_polling.interval_ms` 或 `POLL_INTERVALS` 常量） | - |
| 🆕v4.10 后端返回 `filter_summary` 但前端只显示"查询完成"不暴露过滤过程（F-REVIEW-FILTER-VISIBILITY） | 🆕v4.10 API 返回类型用 `as { filter_summary?: ... }` 强制转换绕过 TS 检查（应显式声明 `filter_summary?` 字段） | - |
| 🆕v4.11 前后端状态枚举值不对齐（前端 `types.ts` 联合类型与后端 `Enum` 不一致）（F-REVIEW-STATE-ENUM-ALIGN） | 🆕v4.11 前端硬编码状态字符串（`status === 'running'`）而非引用 `types.ts` 联合类型 | - |
| 🆕v4.11 终态（`completed`/`failed`）仍显示 loading 动画或"进行中"文案（F-REVIEW-STATE-MACHINE-UI） | 🆕v4.11 中间态（`pending`/`running`）缺少 loading 反馈 / 操作按钮与后端状态机白名单不一致 | - |
| 🆕v4.11 多链路触发同一状态变更时各链路独立 `setState` 推断新状态（F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY） | 🆕v4.11 SSE 推送状态变更后只更新当前组件 `setState` 未刷新全局缓存 / `refetch()` 失败清空缓存 | - |
---

## 与现有工具的关系

- **xianyu-hunter-dev**：开发技能，本技能与之配合（开发完成后用本技能审查）
- **frontend-code-review**（全局技能）：本技能参考其检查清单精神，但增加了闲鱼项目专属的硬约束和 19 维度检查清单
- **xianyu-backend-code-review**：前后端协同评审时配合使用
- **xianyu-sonarqube-mcp**：SonarQube 修复后的二次人工评审使用本技能
- **frontend-design**：UI 设计与样式调整使用该技能，不使用本技能
- **systematic-debugging**：纯调试场景使用该技能，不使用本技能
- **skill-creator**：本技能由 skill-creator 创建

---

## 安全注意事项

1. **凭据**：报告中不包含任何 token、密码等敏感信息
2. **XSS 风险**：检查 `dangerouslySetInnerHTML` 的使用
3. **敏感信息存储**：检查 token 是否避免写入 localStorage（优先 httpOnly cookie）
4. **认证一致性**：检查所有 API 请求是否携带 credentials

---

## 示例用法

### 场景1：迭代发布前评审

用户："对这次迭代的前端修改进行代码评审"

技能执行：
1. 读取 `config.yaml`
2. `git diff HEAD --name-only` 提取改动的 `.tsx/.ts/.js` 文件
3. 逐文件读取并按 23 大类检查
4. 硬约束合规性扫描
5. 生成评审报告

### 场景2：指定组件评审

用户："评审 frontend/src/pages/Evaluations/index.tsx"

技能执行：
1. 读取 `config.yaml`
2. 读取指定文件
3. 收集上下文（类型定义、测试文件、API 契约）
4. 按检查清单评审
5. 生成评审报告

### 场景3：仅评审类型安全和业务逻辑

用户修改 `config.yaml`：
```yaml
checklist:
  directory_structure: false
  naming: false
  react_component: false
  typescript_strict: false
  antd_theme: false
  zustand: false
  api_call: false
  routing_lazy: false
  sheet_workspace: false
  hooks_design: false
  type_safety: true
  sonarqube: false
  pwa: false
  three_mappings: false
  sse_reconnect: false
  business_logic: true
  performance: false
  accessibility: false
  testability: true
  auth: false
  project_specific: false
```

技能执行：只检查类型安全、业务逻辑和可测试性。

### 场景4：评审新增的纯函数抽取

用户："评审我新抽取的 `resolveActionDisplay` 函数"

技能执行：
1. 读取函数定义文件（`utils.ts`）
2. 读取对应测试文件（`__tests__/resolveActionDisplay.test.ts`）
3. 重点检查：
   - 类型安全（返回值联合类型、参数类型）
   - 业务逻辑（优先级顺序、边界场景）
   - 可测试性（纯函数、测试覆盖度）
   - 注释质量（是否解释"为什么"）
4. 生成评审报告

---

## 结构化报告模板 🆕v4.33

> v4.33 新增结构化报告模板，强化"审查概览 + 问题详情"两段式呈现，每个问题含编号/维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示例 8 要素。与下方 Template A/B 并存，按 `report.format` 选择。

### 完整报告结构

```markdown
# 代码审查报告

## 审查概览
- **审查范围**: [文件列表，如 MainLayout.tsx / SheetWorkspace.tsx / api/types.ts]
- **审查维度**: [命中的维度列表，如 §3 React 组件规范 / §10 Hooks 设计模式 / §15 SSE 重连]
- **问题统计**: P0=[n] P1=[n] P2=[n] P3=[n]（总计 [n] 项）
- **规范版本**: xianyu-frontend-code-review v4.33.0
- **配置版本**: config.yaml（含 coding_standards 节点）
- **审查日期**: [YYYY-MM-DD]

## 问题详情

### 🔴 P0 阻塞性问题（必须修复后才能合并）

#### [P0] F-REVIEW-SSE-CONN-MGMT SSE 连接管理三要素
- **规范引用**: SSE-01 SSE 连接管理三要素
- **维度**: §15 SSE 重连
- **代码位置**: EventSourceProvider.tsx:45-62
- **问题描述**: SSE 连接无限重连，无最大重试限制，无 visibilitychange 监听，页面切回后事件丢失
- **修复建议**: 增加 MAX_RECONNECT=10 限制 + visibilitychange 监听 + last_event_id 回放 + 降级轮询
- **配置节点**: coding_standards.sse.max_reconnect_attempts / coding_standards.sse.visibility_reconnect
- **反模式示例**:
  ```typescript
  es.addEventListener('error', () => {
    setTimeout(connect, 3000)  // 无限重连，无降级
  })
  ```

#### [P0] F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING 认证 token cookie 处理
- **规范引用**: AUTH-COOKIE-01（与 v4.32 F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING 配合）
- **维度**: §28 多用户认证上下文隔离
- **代码位置**: api/auth.ts:23
- **问题描述**: token 存入 localStorage，XSS 可读取
- **修复建议**: 改为 httpOnly cookie 由后端写入，fetch 显式 credentials: 'include'
- **配置节点**: auth_token_cookie_handling.forbidden_token_storage
- **反模式示例**: `localStorage.setItem('xh_token', token)`

### 🟠 P1 严重问题（强烈建议本次迭代修复）

#### [P1] F-REVIEW-EFFECT-MINIMIZE useEffect 副作用最小化
- **规范引用**: EFFECT-01 useEffect 副作用最小化原则
- **维度**: §3 React 组件规范
- **代码位置**: MainLayout.tsx:358-362
- **问题描述**: useEffect 联动重置 openKeys，触发 SubMenu 动画遮挡
- **修复建议**: 完全移除 useEffect，openKeys 由 useState 初始化 + 用户交互控制
- **配置节点**: coding_standards.effect.disallow_reset_user_controlled_state
- **反模式示例**: `useEffect(() => setOpenKeys(autoOpenKeys), [location.pathname])`

#### [P1] F-REVIEW-API-CONTRACT-CONSISTENCY API 契约一致性
- **规范引用**: CONTRACT-01 API 契约一致性（前端）
- **维度**: §11 类型安全评审
- **代码位置**: api/types.ts:128
- **问题描述**: 后端返回 total，前端 TS interface 期望 total_for_type，导致显示 0 条
- **修复建议**: TS interface 字段名与后端 response_model 完全一致（snake_case 对齐）
- **配置节点**: coding_standards.contract.check_ts_interface_match
- **反模式示例**: `interface EvaluationResult { total_for_type: number }`

### 🟡 P2 改进问题（记录到 backlog，后续迭代修复）

#### [P2] F-REVIEW-THEME-DYNAMIC-ADAPT 主题色动态适配
- **规范引用**: THEME-01 主题色动态适配
- **维度**: §5 AntD 5 主题规范
- **代码位置**: theme.ts:34
- **问题描述**: 硬编码 rowHoverBg: '#fff7f0'，暗色模式不可读
- **修复建议**: 改为 isDark ? 'rgba(255,98,0,0.08)' : '#fff7f0'
- **配置节点**: coding_standards.theme.disallow_hardcoded_colors / coding_standards.theme.colors.light/dark
- **反模式示例**: `rowHoverBg: '#fff7f0'`

### 🟢 P3 微调问题（风格/注释/命名）

#### [P3] F-REVIEW-UI-SEMANTICS-SPLIT 按钮与状态语义分离
- **规范引用**: UI-SEMANTICS-01 按钮与状态语义分离
- **维度**: §3 React 组件规范
- **代码位置**: CookieList.tsx:156
- **问题描述**: 红色"失效"是按钮而非状态显示，用户误判
- **修复建议**: 按钮文案改为"主动失效"，状态用 Tag 显示"已失效"
- **配置节点**: coding_standards.ui_semantics.button_text_must_be_action
- **反模式示例**: `<Button danger>失效</Button>`

## 与上次审查对比
- 🆕 新增: [n] 项
- ✅ 已修复: [n] 项
- ⚠️ 仍存在: [n] 项

## 硬约束合规性检查结果
- 检查规则数: [n]
- 违规数: [n]
- 是否阻止合并: [是/否]

## 好的实践（正面反馈）
1. [正面反馈 1]
2. [正面反馈 2]

## 审查结论与修复验证指引
- **结论**: [通过 / 有条件通过 / 阻止合并]
- **修复优先级**: P0 修复后重新审查，P1 建议本次迭代修复
- **验证方式**: 修复后运行 `npm --prefix frontend test ; npm --prefix frontend run typecheck`
```

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

Found <W> config-node-missing issues (v4.31 新增分类):

## ⚙️ Config Node Missing (v4.31)

> 该分类归集 Phase 2「配置驱动检查」子阶段识别的 3 类问题：业务关键字硬编码（F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION）/ 事件类型前缀匹配（F-REVIEW-EVENT-TYPE-EXACT-MATCH）/ 字段名大小写不一致（F-REVIEW-FIELD-NAME-CASE-SENSITIVE）。问题严重等级默认为 CRITICAL，但可按 `config.yaml` 的对应节点 `enabled` 字段开关。

### 1. <brief description of the config-node-missing issue>

FilePath: <path> line <line>
<relevant code snippet or pointer>

#### Explanation

<detailed explanation: which F-REVIEW rule violated + which config node missing + frontend/backend contract gap>

#### Suggested Fix

1. <brief description of suggested fix: add config node + sync frontend type + grep bidirectional verification>
2. <code example> (optional, omit if not applicable)

---
... (repeat for each config-node-missing issue) ...

## ✅ What's Good

- <Positive feedback on good patterns>
```

- 若某分类无问题，省略该分类的整个 section
- 若问题数超过 10 个，概括为 "Found 10+ critical issues/suggestions/optional nits" 并仅输出前 10 项
- 不要压缩 section 之间的空行，保持可读性
- 「配置节点缺失」分类（v4.31 新增）必须独立呈现，不与 Critical/Suggestions/Nits 混合，便于用户快速定位"配置契约"类问题
- 若有任何问题需要代码修改，在结构化输出后追加简短的后续问题，询问用户是否应用修复。例如："是否需要我使用 Suggested Fix 来修复这些问题？"

### Template B（无问题）

```markdown
## Code Review Summary
✅ No issues found.
```

---

## 重要提醒

1. 【强制】所有 `fetch`/axios 请求必须包含 `credentials: 'include'` / `withCredentials: true`
2. 【强制】`ConfigProvider` 必须在 `BrowserRouter` 外层，响应 `useTheme`
3. 【强制】新增页面必须同步三处映射（路由、菜单、sheetRegistry）
4. 【强制】禁止 `any` 类型、`dangerouslySetInnerHTML`、`enum`、`JSON.parse(JSON.stringify())`
5. 【强制】SSE 请求用 `fetch + ReadableStream`，lastEventId 持久化重连
6. 【强制】提交前执行 `auto-scan.ps1`；完成后调用本技能走查

---

## 快速问题定位

> 现象导向的问题定位对照表（现象 → 原因 → 方案，50+ 项）已外部化至 [references/quick-troubleshooting.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/quick-troubleshooting.md)。当用户报告具体现象时，先查该表快速定位原因，再回到对应维度章节查阅详细规则。

---

## 附录A：硬约束来源

本技能的硬约束规则来源于：
- `c:\Users\hspcadmin\.trae-cn\memory\projects\-d-code-otherProjects-17-xianyu\project_memory.md`
- `.trae/skills/xianyu-hunter-dev/references/project-rules.md`
- `.trae/skills/xianyu-hunter-dev/assets/guides/frontend-guide.md`
- `.trae/skills/xianyu-frontend-code-review/references/encoding-and-io.md` —— 字符编码与 I/O 边界审查要点（FAQ 乱码复盘提炼，ENC-01 ~ ENC-08）
- `.trae/skills/xianyu-frontend-code-review/references/state-and-consistency-checks.md` —— 前端硬编码阈值禁用、状态判断后端一致性、类型对齐、API 字段映射、credentials 传递、错误反馈与重试、事件冒泡控制（代码审查 P1 + 实时搜索复盘提炼，10 项 F-REVIEW 检查点）
- 历史代码评审记录

## 附录B：项目专属规范

以下规范在 `config.yaml` 的 `project_conventions` 节点维护：

| 规范 | 说明 |
|------|------|
| `ui_library` | UI 组件库（Ant Design） |
| `visual_style` | 视觉风格偏好 |
| `auth_requirements` | 认证要求 |
| `test_framework` | 测试框架 |
| `types_location` | 类型定义位置 |
| `abstraction_patterns` | 推荐的抽象模式 |
| `routing` | 路由配置 |
| `pwa` | PWA 配置 |
| `sonarqube_rules` | SonarQube 8 条规则 |

## 附录C：34 维度对照表

| # | 维度 | 核心规则 |
|:--|:---|:---|
| 1 | 目录结构 | `frontend/src/<分类>/` 规范路径 |
| 2 | 命名规范 | PascalCase/camelCase/use<X>/<域>Store |
| 3 | React 组件规范 | function 关键字 + type Props + 双层 ErrorBoundary + 🆕v4.2 F-REVIEW-UI-STATE-INDEPENDENCE（受控 UI 状态不联动路由） |
| 4 | TypeScript 严格规范 | strict:true、type 优先、字符串字面量联合、🆕v4.25 F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY（默认值统一用 ?? 而非 \|\|） |
| 5 | AntD 5 主题 | ConfigProvider 在 BrowserRouter 外层、品牌橙 |
| 6 | Zustand 状态管理 | persist + partialize、store 不感知路由 |
| 7 | API 调用规范 | axios + withCredentials、SSE 用 fetch、🆕v4.25 F-REVIEW-THREE-STATE-NULL-SEMANTICS（PATCH/PUT 清除覆盖必须显式传 null） |
| 8 | 路由与懒加载 | lazyRetry、双层 ErrorBoundary |
| 9 | SheetWorkspace 多页签 | 6 文件组织、四分支决策 |
| 10 | Hooks 设计模式 | 常量模块级、ref 持有最新闭包、requestId 竞态保护、🆕v4.24 F-REVIEW-UI-PREFERENCE-PERSISTENCE（用户偏好类 UI 状态强制复用 usePersistentState） |
| 11 | 类型安全 | 前后端字段对齐、可选链、联合类型、🆕v4.4 配置驱动功能开关（F-REVIEW-CONFIG-DRIVEN-TOGGLE） |
| 12 | SonarQube 合规 | 8 条规则：S2004/S3358/S6757/S7784/S6848/S1128/S4325/S3776 |
| 13 | PWA 配置 | base:'/app/'、runtimeCaching 排除规则 |
| 14 | 三处映射同步 | App.tsx + MainLayout.tsx + sheetRegistry.tsx |
| 15 | SSE 重连 | lastEventId 持久化重连、🆕v4.1 F-REVIEW-SSE-ERROR-HANDLING（stage='error' 按 status 分类处理 + "前往登录"跳转引导） |
| 16 | 性能 | useMemo/useCallback、虚拟化、稳定 key |
| 17 | 可访问性 | aria-label、label 关联、键盘导航 |
| 18 | 闲鱼项目规范 | AntD 5.21、Vitest 4.1、纯函数+组件+常量分层 |
| 19 | 跨组件状态同步与死代码检测 | Proxy/Observer 赋值实例属性、try/finally 变量初始化、跨组件状态双向同步、错误提示路由可操作性 |
| 20 | 错误提示语义 + 配置链路（前端侧） | 🆕v4.5 错误文案与根因匹配、前端配置全链路追踪、🆕v4.25 F-REVIEW-ERROR-HANDLING-CONSISTENCY（catch 块必须用 extractApiError） |
| 21 | 异步反馈 + 数据流转 + 过滤场景 + 复用模式（前端侧） | 🆕v4.7 异步操作三态反馈（loading→success→error）、字段为空 5 点追踪（前端 types+render）、过滤场景标志显式传递（include_failed）、复用既有前端模式（message.loading/lazyRetry/structuredClone） |
| 22 | 累计统计类 API 定时刷新（前端侧） | 🆕v4.9 累计统计类 API（频率伪装统计 / 健康评分 / 计数器）必须在前端 useEffect 中通过 setInterval 定时刷新，禁止只依赖"页面加载时拉一次"；间隔、清理策略、失败兜底均在 `config.yaml` 的 `freq_stats_polling` 节点管理，不硬编码（与后端 v4.8.0 `B-REVIEW-ISLAND-MODULE` 配合） |
| 23 | 前后端错误码契约与超时识别 + 前端可重试错误集与退避策略 | 🆕v4.13 模块级 `statusMessages` map + `isAxiosTimeout()` 函数（axios 超时无 `response.status` 用 `error.code === 'ECONNABORTED'` 或 `/timeout/i.test(error.message)` 识别）；可重试错误集（410/441/502/超时）按 `retry_delays_ms` 退避序列重试，重试过程 `silent_on_retry`；非幂等写入接口禁用自动重试；参数在 `frontend_error_contract` + `frontend_retry_strategy` 节点管理（与后端 v4.12 `B-REVIEW-DOM-FALLBACK-CHAIN` / `B-REVIEW-TIMING-INSTRUMENTATION` / `B-REVIEW-PRECHECK-AND-PARALLEL` 联动） |
| 24 | 模型能力元数据集中展示与降级状态可视化 | 🆕v4.23 前端展示 LLM 模型能力时必须集中展示（从 `/api/config` 或 `/api/about` 统一获取，禁止每页独立 fetch/内联判断），用户上传图片/启用 tool 时前端必须根据能力位给出降级状态可视化（如 `Tag color="warning"` 显示"纯文本模型不支持图片分析，已降级为文字描述"），关键字列表仅在后端 `api_ai._VISION_CAPABLE_KEYWORDS` 一处维护，前端抽 `isVisionCapable()` + `getCapabilityDisplay()` 共享函数到 `frontend/src/utils/modelCapability.ts`；参数在 `model_capability_centralization` 节点管理 |
| 25 | 端到端失败原因链前端侧同步原则 | 🆕v4.27 前端在端到端失败原因链中的 3 项同步原则：F-REVIEW-ERROR-CODE-BRANCH（错误展示按 `error_code` 字段分支，禁止按文案子串判断，与后端 `failure_reason_propagation.reason_enum` 一一对应）、F-REVIEW-PRECHECK-API-DELEGATION（数据完整性预检委托后端，禁止前端自行实现预检业务规则，调用后端预检端点 `/api/<resource>/precheck` 获取 `passed` 字段）、F-REVIEW-MOCK-FIELD-SET-SYNC（前端 mock 数据必须覆盖完整字段集与后端 Pydantic 模型一致，禁止用 `as` 类型断言绕过，集中管理 mock 基线文件 `frontend/src/test/mocks/`）；参数在 `failure_reason_chain_frontend` 节点管理（与后端 v4.27.0 维度 29 的 6 项 B-REVIEW 联动） |
| 26 | 跨边界访问契约前端侧 | 🆕v4.30 后端跨边界契约不明确在前端的对应场景：F-REVIEW-DATETIME-RENDER-CONTRACT（后端 datetime 字段 must use `new Date(isoStr)` 显式解析，naive ISO 字符串追加 `Z` 后缀，禁止字符串方法解析）、F-REVIEW-PRIVATE-HOOK-ENCAPSULATION（跨组件访问私有 hooks/state 必须通过公共 API，禁止 `useXxxStore(s => s._xxx)` 直接访问私有字段，用 `useImperativeHandle` 显式声明可暴露方法）、F-REVIEW-NAMING-CONSISTENCY-FRONTEND（命名一致性验证：变量 camelCase / 组件 PascalCase / 常量 UPPER_SNAKE_CASE / 私有 _ 前缀，跨组件引用必须大小写匹配）；参数在 `cross_boundary_contract_frontend` 节点管理 |
| 27 | 业务关键字常量集中管理与字段名大小写敏感 | 🆕v4.31 前端业务关键字与字段契约层面的 3 项同步原则：F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION（前端业务关键字常量必须从后端配置端点 `/api/config/text_features` 拉取，禁止前端硬编码中文字面量，通过共享 helper `isItemSoldByText()` 调用后端配置）、F-REVIEW-EVENT-TYPE-EXACT-MATCH（前端按事件类型过滤必须 `===` 精确匹配或 `Set.has()`，禁止 `startsWith()`/`indexOf()` 前缀匹配，通知事件与业务事件分离处理）、F-REVIEW-FIELD-NAME-CASE-SENSITIVE（前端访问后端字段时大小写敏感，前端 `api/types.ts` 必须与后端 Pydantic 模型字段名一一对应，禁止用 `as any` 绕过类型检查）；3 项检查点对应 `xianyu-hunter-dev` step 129/130/131；参数在 `business_keyword_centralization` / `event_type_exact_match` / `field_name_case_sensitive` 节点管理（与后端 v4.31.0 维度 30 的 6 项 B-REVIEW 联动） |
| 28 | 多用户认证上下文隔离 | 🆕v4.32 多用户场景前端隔离原则：F-REVIEW-MULTI-USER-CONTEXT-ISOLATION（前端按 `user_id` 隔离 Zustand store / 缓存 / 请求路径，禁止全局单例承接多用户数据；切换用户时必须 `queryClient.clear()` + `useGlobalStore.getState().reset()` 后再加载新用户数据）、F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING（认证 token 通过 httpOnly cookie 传递，fetch 必须 `credentials: 'include'` / axios 必须 `withCredentials: true`，401/440/441/403 状态码语义精细化分支）；参数在 `multi_user_context_isolation` / `auth_token_cookie_handling` 节点管理（与 xianyu-hunter-dev step 134-137 + 后端 v4.32 维度 28 联动） |
| 29 | 数据契约与时序（meta-rules #25-30 落地） | 🆕v4.34 前端在数据契约与时序维度的 6 项落地检查点：F-REVIEW-110（批量断路器 UI 三态反馈，区分用户主动停止/熔断可恢复/异常失败，必须展示 success_count/pending_count/failure_reason/recover_action）、F-REVIEW-111（ErrorBoundary 完整 stack 上报，禁 console.error_only/return_null）、F-REVIEW-112（ISO datetime 统一解析与序列化，解析用 new Date().toLocaleString，发送用 toISOString）、F-REVIEW-113（跨进程状态同步六步法前端侧，禁 setInterval 替代 SSE）、F-REVIEW-114（前端错误按 error_code 分支，禁 substring 判断）、F-REVIEW-115（业务关键字常量集中管理，禁内联字符串，从 @/constants/businessKeywords 导入，与后端一致性测试）；6 项检查点对应 xianyu-hunter-dev v4.30.0 meta-rules #25-30 + 后端 v4.29.0 维度 31 的 B-REVIEW-151~156；参数在 `data_contract_temporal` 节点管理 |
| 30 | 状态恢复前置校验前端侧（meta-rule #31 落地） | 🆕v4.35 前端在状态恢复前置校验维度的 1 项落地检查点：F-REVIEW-116 RESUME-PRECHECK-FRONTEND（恢复/启动/继续按钮 onClick 必须先调用后端 precheck API 校验前置条件，禁前端自行实现预检；校验失败时展示 user_hint + retry_after 倒计时 + 恢复动作按钮；与后端 B-REVIEW-157 配套）；1 项检查点对应 xianyu-hunter-dev v4.31.0 meta-rule #31 + 后端 v4.30.0 B-REVIEW-157；参数在 `resume_policy_precheck` 节点管理 |
| 31 | 注册式资源三件套契约前端侧（meta-rule #33 落地） | 🆕v4.36 前端在注册式资源三件套契约维度的 1 项落地检查点：F-REVIEW-117 REGISTRATION-COMPLETENESS（菜单/路由/页面/API 模块/后端端点 5 层契约，任一层缺失=CRITICAL；自动化校验 `python scripts/check_registration.py` 退出码 0 才算通过）；1 项检查点对应 xianyu-hunter-dev v4.32.0 meta-rule #33 + 后端 B-REVIEW-159；参数在 `frontend_registration_completeness` 节点管理 |
| 32 | 修复前根因扫描协议前端侧（meta-rule #34 落地） | 🆕v4.36 前端在修复前根因扫描协议维度的 1 项落地检查点：F-REVIEW-118 ROOT-CAUSE-MIN-COUNT（修复非平凡 bug 前必须先列 ≥3 个根因覆盖用户层/接口层/数据层/配置层/历史层；PR 描述必含"≥3 根因列表"段；git diff 涉及 ≥3 个无关文件视为违反最小修改原则）；1 项检查点对应 xianyu-hunter-dev v4.32.0 meta-rule #34 + 后端 B-REVIEW-160；参数在 `root_cause_protocol` 节点管理 |
| 33 | 前后端字段契约单一可信源前端侧（meta-rule #35 落地） | 🆕v4.36 前端在前后端字段契约单一可信源维度的 1 项落地检查点：F-REVIEW-119 CONTRACT-SINGLE-SOURCE（后端 Pydantic/DB Row 字段=权威源，前端 types.ts 必须显式标注"派生来源+Pydantic 字段+变更日期+约束"4 段注释；snake_case 严格透传禁止转 camelCase；命名漂移=CRITICAL）；1 项检查点对应 xianyu-hunter-dev v4.32.0 meta-rule #35 + 后端 B-REVIEW-161；参数在 `contract_single_source` 节点管理 |
| 34 | 规范治理（meta-rules #36-37 落地） | 🆕v4.37 前端在规范治理维度的 2 项落地检查点：F-REVIEW-120 SEDIMENTATION-THRESHOLD（新立编码规范必须满足 ≥3 个相似 bug 门槛，单一 bug 立规范需标 experimental 标签 + 1 季度观察期，安全/数据丢失/付费受损豁免）、F-REVIEW-121 DEGRADATION-CLEANUP（利用率 < 3 次/季度的 F-REVIEW 必须标记待合并/待废弃，1 季度观察期后废弃并移入 version-history.md Deprecated 章节，安全类永不退化）；2 项检查点对应 xianyu-hunter-dev v4.33.0 meta-rules #36-37 + 后端 B-REVIEW-162/163；参数在 `meta_rules_governance` 节点管理 |
