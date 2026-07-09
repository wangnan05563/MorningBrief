# 版本演进详细复盘记录（Version Changelog）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)
> **用途**：存放各版本的完整复盘详情（Sequential Thinking 复盘法、根因分析、检查点详情），SKILL.md 顶部仅保留索引表格，需要查阅历史决策与根因时再读取本文件。
> **维护原则**：新增版本复盘时按版本号倒序插入到本文件最上方，SKILL.md 顶部表格仅更新一行索引。

---

## v4.33.0（2026-07-05）全量复盘与审查要点同步

**复盘方法**：Sequential Thinking 18 步四维度复盘法
**复盘范围**：2026-07-03 至 2026-07-05 全量问题（80+ topics）
**问题归纳**：7 大类（A 时区 / B 命名 / C 状态持久化 / D Cookie 认证 / E 前端交互 / F 数据传递 / G 鲁棒性）

**新增审查要点**：14 个 F-REVIEW checkpoints（F-REVIEW-96 ~ F-REVIEW-109，对应任务原编号 F-REVIEW-84~97 因冲突调整为 96~109）

- **React 组件规范维度**：2 条
  - F-REVIEW-EFFECT-MINIMIZE（useEffect 副作用最小化，规范引用 EFFECT-01）
  - F-REVIEW-STATE-ATOMICITY（状态切换原子性，规范引用 STATE-01）
- **性能与竞态维度**：2 条
  - F-REVIEW-SSE-CONN-MGMT（SSE 连接管理三要素，规范引用 SSE-01）
  - F-REVIEW-ASYNC-RACE-GUARD（异步竞态防护，规范引用 RACE-01）
- **AntD 主题维度**：2 条
  - F-REVIEW-THEME-DYNAMIC-ADAPT（主题色动态适配，规范引用 THEME-01）
  - F-REVIEW-EMBEDDED-LAYOUT-HEIGHT（嵌入式布局高度，规范引用 LAYOUT-01）
- **组件注册维度**：1 条
  - F-REVIEW-COMPONENT-REGISTRY（组件注册完整性，规范引用 REGISTRY-01）
- **数据展示维度**：3 条
  - F-REVIEW-FILTER-TRANSPARENCY（过滤透明化，规范引用 FILTER-02）
  - F-REVIEW-DATA-SOURCE-VERIFY（数据源正确性验证，规范引用 SOURCE-01）
  - F-REVIEW-STATS-RANGE-CALIBRATE（统计范围校准，规范引用 RANGE-01）
- **UI 语义维度**：1 条
  - F-REVIEW-UI-SEMANTICS-SPLIT（按钮与状态语义分离，规范引用 UI-SEMANTICS-01）
- **状态持久化维度**：1 条
  - F-REVIEW-PERSIST-BUSINESS-SWITCH（用户可配置开关持久化，规范引用 PERSIST-01）
- **API 契约维度**：2 条
  - F-REVIEW-ERROR-MESSAGE-PASS（错误消息透传，规范引用 ERROR-01）
  - F-REVIEW-API-CONTRACT-CONSISTENCY（API 契约一致性，规范引用 CONTRACT-01）

**审查流程优化**：4 阶段流水线（上下文加载 → 分层扫描 → 优先级分类 → 结果呈现）
- 原 5 阶段闭环（Phase 0-4）重组为 4 阶段流水线
- 阶段 1 新增 `coding_standards` 节点加载 + `coding-rules/` 主题文件加载 + 任务类型识别
- 阶段 2 保留常规规则匹配 + 配置驱动检查 + 硬约束合规性检查三个子阶段
- 阶段 3 新增 P0/P1/P2/P3 四级优先级分类（P0 阻塞合并，P1 强烈建议修复，P2/P3 记录 backlog）
- 阶段 4 强化结构化报告呈现

**结果呈现优化**：结构化报告模板（审查概览 + 问题详情两段式）
- 审查概览：审查范围/审查维度/问题统计 P0/P1/P2/P3/规范版本/配置版本/审查日期
- 问题详情：每个问题含 8 要素（编号/维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示例）
- 与原 Template A/B 并存，按 `report.format` 选择

**配置化**：新增 `coding_standards` 节点，所有 14 项新检查点的参数通过 `config.yaml` 管理
- `coding_standards.effect.disallow_reset_user_controlled_state` / `merge_strategy`
- `coding_standards.sse.max_reconnect_attempts` / `polling_fallback_interval` / `visibility_reconnect`
- `coding_standards.theme.disallow_hardcoded_colors` / `colors.light` / `colors.dark`
- `coding_standards.layout.disallow_minheight_100vh_in_embedded`
- `coding_standards.registry.check_components`
- `coding_standards.filter.summary_enabled`
- `coding_standards.ui_semantics.button_text_must_be_action` / `status_display_must_be_state`
- `coding_standards.persist.business_switch_must_persist` / `storage_key_prefix`
- `coding_standards.race.check_request_id`
- `coding_standards.error.require_extract_api_error`
- `coding_standards.contract.check_ts_interface_match`
- `coding_standards.source.verify_data_source`

**规范源联动**：每个 checkpoint 引用 `xianyu-hunter-dev/references/coding-rules/` 中的规范编号（如 EFFECT-01/SSE-01/THEME-01 等），审查时加载规范详情，实现"检查点 ↔ 规范源"双向追溯。

**版本号调整说明**：任务原指定版本号 v4.28.0（基于旧版本认知 v4.27.0），但文件实际已演进至 v4.32.0（v4.28.0/v4.30.0/v4.31.0/v4.32.0 已存在），故调整为 v4.33.0。checkpoint 编号原指定 F-REVIEW-84~97，但 84-87 已被占用（F-REVIEW-PRECHECK-API-DELEGATION/MOCK-FIELD-SET-SYNC/MULTI-USER-CONTEXT-ISOLATION/AUTH-TOKEN-COOKIE-HANDLING），故调整为 F-REVIEW-96~109（与版本表 v4.32.0 的 95 衔接）。

---

## v4.32.0 多用户认证上下文隔离复盘（前端侧同步原则）

基于 2026-07-05 完成的 MU2 Sprint（认证中间件改造 + CookieStore 扩展 user_id 维度）复盘（使用 Sequential Thinking 8 步复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景），新增 2 项 F-REVIEW 检查点（新增维度 28 多用户认证上下文隔离）：

- **F-REVIEW-MULTI-USER-CONTEXT-ISOLATION**（维度 28）：前端按 user_id 维度隔离状态/缓存/请求路径，禁止全局单例 store 承接多用户数据，用户切换时必须调用 `queryClient.clear()` + `useGlobalStore.getState().reset()` + `usePersistentState.invalidate()` 清空旧用户缓存
- **F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING**（维度 28）：认证 token 必须走 httpOnly cookie（禁止 localStorage），fetch 必须显式 `credentials: 'include'`，axios 必须 `withCredentials: true`，htmx 通过 `<meta name="htmx-config">` 配置 credentials；401/440/441/403 必须按状态码语义分支处理（跳登录页/跳重新登录页/刷新 token/提示无权限），禁止所有认证失败一律跳登录页

**4 维度复盘要点**：

1. **成功步骤**：MU2 Sprint 完成后端 CookieStore 按 `cookies_{uid}.json` 分文件存储 + `_cache: dict[str, tuple[dict, float]]` 分桶缓存 + 中间件三路校验（管理令牌 + 用户会话 + 401）+ `make_auth_response` 通过 set-cookie 写入 httpOnly xh_token cookie
2. **不确定性与失败点**：前端 Zustand store 仍用全局单例承接订单/偏好数据，用户切换时未清空缓存导致跨用户数据泄漏；部分 fetch 请求遗漏 `credentials: 'include'` 导致 cookie 不传递；所有 401 一律跳登录页，用户会话过期（应跳重新登录页）和 Cookie 过期（应刷新 token）被误判为"未登录"
3. **可抽象的固定流程**：① 多用户场景下用户特定状态必须按 user_id 分桶（`Record<UserId, UserState>`）或切换时 `store.reset()`；② 认证 token 走 httpOnly cookie + 前端 `credentials: 'include'`；③ 状态码语义精细化分支（401/440/441/403 各自对应不同前端动作）
4. **适用场景**：多用户系统（用户切换/多账号管理）、多租户 SaaS、所有涉及认证的 API 请求、SSE 事件流认证、多角色权限控制。**不适用场景**：单用户系统（无用户切换需求）、纯内部工具（无登录态）、纯公共 API（无需认证）、第三方 OAuth 回调（按 OAuth 规范处理）

自动化扫描从 93 项扩展到 95 项。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `multi_user_context_isolation` + `auth_token_cookie_handling` 节点管理）与适用/不适用场景说明。详细编码规范整合到 `xianyu-hunter-dev` v4.30.0 的 step 134-137（多用户资源隔离 + 认证中间件多路校验 + 会话 token 安全管理 + 快照与实时数据覆盖决策）。后端对应规范为 `xianyu-backend-code-review` v4.28.0 的维度 21（5 项 B-REVIEW：B-REVIEW-MULTI-USER-RESOURCE-ISOLATION / B-REVIEW-AUTH-MULTI-PATH-VALIDATION / B-REVIEW-SESSION-TOKEN-SECURITY / B-REVIEW-SNAPSHOT-REALTIME-OVERWRITE / B-REVIEW-USER-IDENTITY-PRIORITY）。

---

## v4.31.0 业务关键字常量集中管理与字段名大小写敏感复盘

基于 2026-07-05 解决的 3 类前端反模式复盘（业务文案硬编码 / 事件类型前缀过滤 / 字段名大小写不一致；使用 Sequential Thinking 4 维度复盘法），新增 3 项 F-REVIEW 检查点（新增维度 27 业务关键字常量集中管理与字段名大小写敏感）：

- **F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION**（维度 27）：前端使用业务关键字文案（"卖掉了"/"已售"/"已下架"等业务状态判定文本）时必须从后端配置端点（`/api/config/text_features`）拉取而非硬编码，前端通过共享 helper 函数（`isItemSoldByText(text)`）调用后端配置
- **F-REVIEW-EVENT-TYPE-EXACT-MATCH**（维度 27）：前端按事件类型过滤必须用 `===` 精确匹配或 `Set.has()`，禁止 `startsWith()` / `indexOf()` 前缀匹配（除非是配置节点 `event_type_exact_match.allowed_prefix_grouping_scenarios` 允许的统计/日志场景）
- **F-REVIEW-FIELD-NAME-CASE-SENSITIVE**（维度 27）：前端访问后端 API 响应字段时字段名大小写必须与后端 Pydantic 模型完全一致（snake_case），禁止用 `as any` 绕过类型检查

**4 维度复盘要点**：

1. **成功步骤**：后端 `collector_utils.py` 集中 `SOLD_TEXT_KEYWORDS` + `check_text_sold()` 统一入口 + 配置节点 `config.yaml#external_platform.text_features`，前端通过 `/api/config/text_features` 拉取关键字列表
2. **不确定性与失败点**：前端硬编码业务关键字与后端规则不一致（后端新增"已售出"文案前端未同步）；`event.type.startsWith('eval.')` 误包含 `eval.passed`/`eval.failed`/`eval.error` 子类型；前端用 `data.totalForType` 访问后端 `total_for_type` 字段（驼峰 vs snake_case）导致显示 0 条；后端 `ChatbotRepository` 用 `this._Session` 访问定义的 `this._session` 私有属性（大小写不一致）
3. **可抽象的固定流程**：① 业务关键字从后端配置拉取 + 共享 helper 函数判断；② 事件类型 `===` 精确匹配或 `Set<string>` 集合判断；③ 前端 `api/types.ts` 字段名与后端 Pydantic 模型一一对应 + grep 双向匹配验证
4. **适用场景**：前端业务状态判定（商品售出/订单状态/用户角色）、SSE 事件处理、API 响应消费、Zustand store 字段读写、测试 mock 数据字段名。**不适用场景**：纯前端 UI 文案、组件内部状态文本、路由参数、纯统计/日志场景的事件前缀匹配

自动化扫描从 90 项扩展到 93 项。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `business_keyword_and_field_contract` 节点管理）。详细编码规范整合到 `xianyu-hunter-dev` v4.31.0 的 step 129/130/131。后端对应规范为 `xianyu-backend-code-review` v4.31.0 的维度 30（6 项 B-REVIEW）。

---

## v4.30.0 跨边界访问契约前端侧复盘

基于 2026-07-05 解决的 3 类跨边界访问问题复盘（时区感知 datetime 渲染契约 / 私有 Hook 封装 / 命名一致性；使用 Sequential Thinking 4 维度复盘法），新增 3 项 F-REVIEW 检查点（新增维度 26 跨边界访问契约前端侧）：

- **F-REVIEW-DATETIME-RENDER-CONTRACT**（维度 26）：前后端 datetime 交换必须用 ISO 8601 带时区格式（`2026-07-05T10:30:00+08:00`），前端渲染必须用 `dayjs` 等库解析时区后按用户本地时区显示，禁止直接 `new Date(str)` 解析 naive datetime
- **F-REVIEW-PRIVATE-HOOK-ENCAPSULATION**（维度 26）：自定义 Hook 的内部状态（如 `loadingRef` / `requestIdRef` / `cache`）必须封装在 Hook 闭包内，禁止暴露给消费方，Hook 只返回公共 API（如 `{ data, error, loading, refetch }`）
- **F-REVIEW-NAMING-CONSISTENCY-FRONTEND**（维度 26）：前端命名必须与后端契约保持一致（字段名 snake_case / 函数名 lowerCamelCase / 类型名 PascalCase），禁止前端独立命名导致前后端不一致

**4 维度复盘要点**：

1. **成功步骤**：基于 `repo_chatbot.py` 的 `TypeError: can't subtract offset-naive and offset-aware datetimes` 修复经验，确立 datetime 跨边界传递必须带时区的契约
2. **不确定性与失败点**：后端 `_utcnow().replace(tzinfo=None) - row.created_at` 混用 naive/aware datetime 触发异常；前端自定义 Hook 暴露内部 `loadingRef` 导致消费方误修改；前端用驼峰命名而后端用 snake_case 导致字段对不上
3. **可抽象的固定流程**：① 跨边界 datetime 必须 ISO 8601 + 时区；② Hook 内部状态闭包封装；③ 命名风格前后端一致（snake_case 字段 / lowerCamelCase 函数 / PascalCase 类型）
4. **适用场景**：前后端数据交换、自定义 Hook 设计、跨模块命名约定。**不适用场景**：纯前端内部状态（无后端契约）、第三方库内部实现、CSS 类名（前端独立命名）

自动化扫描从 87 项扩展到 90 项。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `cross_boundary_contract_frontend` 节点管理）。详细编码规范整合到 `xianyu-hunter-dev` v4.30.0 的 step 132/133。后端对应规范为 `xianyu-backend-code-review` v4.30.0 的 B-REVIEW-DATETIME-TIMEZONE-AWARE / B-REVIEW-PRIVATE-ATTR-ENCAPSULATION / B-REVIEW-NAMING-CONSISTENCY。

---

## v4.28.0 工作流元规范硬约束复盘（前端侧同步原则）

基于 xianyu-hunter-dev meta-rules #21-24（错误处理决策树 / 批处理熔断 / 资源生命周期 / 跨组件状态同步）的前端侧同步复盘（使用 Sequential Thinking 4 维度复盘法），新增 4 项 F-REVIEW 检查点（维度 19/6/10/11）：

- **F-REVIEW-WF-ERROR-HANDLING**（维度 19）：前端关键路径（认证/支付/会话初始化）的 `.catch` 禁止空实现或仅 `console.error`，必须分级处理（warning→`message.warning` / error→`message.error`），与 v4.7 异步三态反馈配合
- **F-REVIEW-WF-BATCH-CIRCUIT-BREAKER**（维度 6）：前端调用批量接口时必须展示熔断状态（running/paused/failed/completed），熔断后必须展示"已成功 X 项 + 剩余 Y 项 + 失败原因 Z + 恢复入口"
- **F-REVIEW-WF-RESOURCE-LIFECYCLE**（维度 10）：`new Proxy()` / `new MutationObserver()` / `new IntersectionObserver()` / `new EventSource()` / `new WebSocket()` 等长生命周期资源必须赋值给实例属性或 ref，禁止赋值给局部变量后被 GC 回收；必须在 `useEffect` cleanup 中调用 `close()`
- **F-REVIEW-WF-STATE-SYNC**（维度 11）：跨组件状态同步必须用单一可信源（`useCookieLayersStore` / `useAuthStore` / `useBatchRefreshConfigStore`）+ 统一 refetch 入口 + SSE 推送，禁止前端用 30/60 秒 TTL `setInterval` 同步跨进程状态，禁止 `usePersistentState` 重复持久化后端已有 GET API 的字段

**4 维度复盘要点**：

1. **成功步骤**：抽取 xianyu-hunter-dev meta-rules #21-24 对应的前端检查点，确保前后端工作流元规范一致
2. **不确定性与失败点**：meta-rule 在前端场景的适用边界（如批处理熔断前端如何展示、资源生命周期前端 GC 风险、跨组件状态同步前端 TTL 兜底禁止）
3. **可抽象的固定流程**：4 项 meta-rule 在前端的检查模式（决策树/状态展示/资源持有/单一可信源），所有规则配置驱动
4. **适用场景**：所有 useEffect / fetch / axios / EventSource 代码路径、批量操作 UI、跨组件状态同步。**不适用场景**：测试 mock / 一次性脚本 / 短生命周期对象

自动化扫描从 83 项扩展到 87 项。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `workflow_meta_rules_frontend` 节点管理）。详细编码规范整合到 `xianyu-hunter-dev` v4.28.0 的 meta-rules #21-24。后端对应规范为 `xianyu-backend-code-review` v4.28.0 的工作流元规范检查点。

---

## v4.27.0 端到端失败原因链与数据完整性闭环复盘（前端侧同步原则）

基于本轮对话解决的 `Failed to collect item detail: page unavailable or login expired` 问题复盘（根因：代码被回退 + 服务未重启双重原因导致修复未生效；使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景），新增 3 项 F-REVIEW 检查点（维度 25 端到端失败原因链前端侧同步原则）：

- **F-REVIEW-ERROR-CODE-BRANCH**：前端错误展示必须按后端返回的 `error_code` 字段分支而非按文案子串判断，禁止 `if (msg.includes('expired'))` 等子串匹配模式，应改为 `switch (err.error_code) { case 'token_invalid': ... }`，与后端 `failure_reason_propagation.reason_enum` 一一对应（命名风格以后端为准，统一 lower_snake_case）
- **F-REVIEW-PRECHECK-API-DELEGATION**：前端调用后端 API 前若需预检数据完整性，必须调用后端预检端点（如 `/api/cookies/precheck`）而非前端自行判断 cookie 数量/字段完整性，前端不具备后端业务规则的完整上下文
- **F-REVIEW-MOCK-FIELD-SET-SYNC**：前端 mock 数据必须覆盖完整字段集与后端 Pydantic 模型保持一致，新增后端字段后前端 mock 必须同步补齐，避免测试通过但生产环境类型不一致

自动化扫描从 80 项扩展到 83 项；所有新检查点强调配置驱动（参数在 `config.yaml` 的 `failure_reason_chain_frontend` 节点管理）与适用/不适用场景说明。详细编码规范整合到 `xianyu-hunter-dev` v4.27.0 的 step 123-128。后端对应规范为 `xianyu-backend-code-review` v4.27.0 的维度 29（6 项 B-REVIEW）。

---

## v4.26.0 API三态语义/错误处理/默认值操作符复盘（前端侧）

基于本轮对话解决的「任务级配置覆盖功能开发 + 代码审查」复盘（使用 Sequential Thinking 8 步复盘法），新增 3 项 F-REVIEW 检查点：

- **F-REVIEW-THREE-STATE-NULL-SEMANTICS**（维度 7）：PATCH/PUT 请求清除覆盖字段必须显式传 null，禁止用省略字段代替传 null
- **F-REVIEW-ERROR-HANDLING-CONSISTENCY**（维度 20）：API 调用的 catch 块必须用 extractApiError 提取具体错误信息，禁止 `message.error('保存失败')` 等无信息提示
- **F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY**（维度 4）：默认值场景统一用 `??` 而非 `||`，只有需要同时过滤 0/''/false 时才用 `||`

自动化扫描从 77 项扩展到 80 项。详细编码规范整合到 xianyu-hunter-dev v4.26.0 的 step 117/121/122。后端对应规范为 xianyu-backend-code-review v4.26.0 的 B-REVIEW-EXCLUDE-UNSET-CHECK / B-REVIEW-NOT-NULL-NONE-DEFENSE。

---

## v4.25.0 数据库迁移块独立容错与关键路径异常可见性复盘（前端侧同步原则）

基于本轮对话解决的 `sqlite3.OperationalError: no such column: notifications.read_at` 问题复盘（使用 Sequential Thinking 6 步复盘法），**不新增 F-REVIEW 检查点**（自动化扫描项保持 77 项不变）。原因：本次问题为纯后端数据库迁移问题，前端不直接处理数据库迁移，业务场景过于狭窄。

仅在前端层面同步以下原则：

1. 前端若涉及"启动时初始化"逻辑（如 `useEffect` 中的初始化请求、Zustand store 的 `hydrate` 操作），错误处理必须用 `console.error` 输出完整错误对象而非 `console.warn(String(e))` 丢失堆栈
2. 前端初始化逻辑中有多个独立初始化步骤时（如并行 fetch 多个 API），每个步骤应独立 catch 而非统一 try/catch 吞掉异常导致后续步骤跳过
3. 前端若展示后端迁移状态或数据库 schema 信息（如"关于"页面展示数据库版本），应从后端 `/api/about` 等端点获取而非前端硬编码

本次复盘的详细编码规范整合到 `xianyu-hunter-dev` v4.25.0 的 step 116（仅后端规范），后端审查规则落地到 `xianyu-backend-code-review` v4.25.0 的 B-REVIEW-MIGRATION-BLOCK-ISOLATION（第 110 项）/ B-REVIEW-CRITICAL-PATH-NO-SWALLOW（第 111 项）。

---

## v4.24.0 用户偏好类 UI 状态持久化复盘（前端侧）

基于本轮对话解决的「批量采集菜单相关参数开关应支持持久化」需求复盘（使用 Sequential Thinking 7 步复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-UI-PREFERENCE-PERSISTENCE**（维度 10）：用户偏好类 UI 状态（自动刷新/视图模式/列显隐/折叠/展开/主题偏好/最近使用列表/记住上次选中项）必须使用项目既有 `frontend/src/hooks/usePersistentState.ts` 持久化，禁止裸 useState、禁止自行实现 localStorage 读写、禁止引入第三方持久化库

自动化扫描从 76 项扩展到 77 项。核心机制：项目已有统一封装的 usePersistentState hook（含防抖写入、数据验证、localStorage 不可用回退到内存 Map）。详细编码规范整合到 `xianyu-hunter-dev` v4.24.0 的 step 115。后端对应规范为 `xianyu-backend-code-review` v4.24.0 的复盘记录同步原则（不新增 B-REVIEW 检查点，纯前端问题）。

---

## v4.23.0 模型能力元数据集中展示与降级状态可视化复盘（前端侧）

基于本轮对话解决的"LLM 深度分析因 vision 模型不支持 image_url 触发 400"问题复盘（使用 Sequential Thinking 4 维度复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION**（维度 11）：前端展示 LLM 模型能力时必须集中展示（从 `/api/config` 或 `/api/about` 统一获取，禁止每页独立 fetch/内联判断），用户上传图片/启用 tool 时前端必须根据能力位给出降级状态可视化，关键字列表仅在后端 `api_ai._VISION_CAPABLE_KEYWORDS` 一处维护，前端抽 `isVisionCapable()` + `getCapabilityDisplay()` 共享函数到 `frontend/src/utils/modelCapability.ts`

自动化扫描从 75 项扩展到 76 项。详细编码规范整合到 `xianyu-hunter-dev` v4.21.0 的 step 112-114。后端对应规范为 `xianyu-backend-code-review` v4.23.0 的 B-REVIEW-LLM-CAPABILITY-DISPATCH / B-REVIEW-SHARED-UTIL-CENTRALIZATION / B-REVIEW-SILENT-DOWNGRADE-PRECHECK。

---

## v4.22.0 PWA 缓存验证复盘（前端侧）

基于本轮对话解决的「批量采集执行历史 Tab2 前端不可见」问题复盘（使用 Sequential Thinking 6 步复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-PWA-CACHE-VERIFY**（维度 13）：前端功能不可见时必须从源码→构建产物→sw.js 预缓存清单三层验证，vite-plugin-pwa 的 registerType: 'prompt' 模式检测到新版本仅弹通知不自动刷新，必须实现 ReloadPrompt 组件提示用户刷新，或改用 registerType: 'autoUpdate' 自动激活新版本

自动化扫描从 74 项扩展到 75 项。详细编码规范整合到 xianyu-hunter-dev v4.20.0 的 step 107-111。后端对应规范为 xianyu-backend-code-review v4.22.0 的 B-REVIEW-STARTUP-HOOK-COMPLETENESS / B-REVIEW-TASK-HISTORY-THREE-LAYER-PROTECTION / B-REVIEW-COUNTER-DB-MAX-INIT / B-REVIEW-APSCHEDULER-INTERVAL-FIRST-RUN。

---

## v4.20.0 版本号源管理复盘（前端侧）

基于本轮解决的"版本管理菜单持续显示 V10"问题复盘（使用 Sequential Thinking 6 步复盘法），落地 v4.19.0 遗留待办，新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-VERSION-SOURCE-ALIGN**（维度 7）：前端显示元数据必须调用语义对齐的 API 端点，禁止将返回 `len(backups)` / `count` / `size` / `length` 的端点当作版本号使用；新增 aboutApi 调用必须通过 `Promise.all` 与既有 configApi 并行化避免瀑布请求；修复时同步清理只 set 不 read 的死代码 state

自动化扫描从 73 项扩展到 74 项。详细编码规范整合到 `xianyu-hunter-dev` v4.18.0 的 step 98。后端对应规范为 `xianyu-backend-code-review` v4.20.0 的 B-REVIEW-VERSION-SOURCE-SINGLE。

---

## v4.19.0 调度器状态展示复盘（前端侧）

基于本次对话解决的 3 个后端问题中"关键调度器启动状态可见性"对应的前端需求复盘（使用 Sequential Thinking 12 步复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-SCHEDULER-STATUS-DISPLAY**（维度 18）：前端"关于"页面必须展示关键调度器启动状态，调用 `/api/about` 端点获取 `schedulers` 数组并渲染为状态卡片，未启动的调度器必须显示红色"未启动"标签 + 启动命令提示

自动化扫描从 72 项扩展到 73 项。详细编码规范整合到 `xianyu-hunter-dev` v4.19.0 的 step 101。后端对应规范为 `xianyu-backend-code-review` v4.19.0 的 B-REVIEW-SCHEDULER-STARTUP-VISIBILITY。遗留待办：v4.17.0/v4.18.0 的 VERSION-SOURCE 规范尚未在本 skill 落地，需后续补充。

---

## v4.16.0 Cookie 层状态管理复盘（前端侧）

基于本轮解决的"功能正常但状态显示失效"问题（用户反馈：实时查询、官方采集等功能均能正常运行，但 identity、session、tracking 状态持续显示失效）复盘（使用 Sequential Thinking 4 维度复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-STATE-FUNCTIONAL-ALIGN**（维度 3）：前端 UI 显示的"功能/会话/服务状态"必须与"功能实际可用性"保持一致；禁止仅依据后端返回的"初始值"或"短期缓存"判定 UI 状态显示为"失效/异常"，必须配合"已发生过真实调用"标记（首次成功时间戳、计数器、最近一次成功时间）才更新 UI 状态为"有效/正常"

自动化扫描从 68 项扩展到 69 项。详细编码规范整合到 `xianyu-hunter-dev` v4.16.0 的 step 91-93。后端对应规范为 `xianyu-backend-code-review` v4.15.0 的 B-REVIEW-CACHE-INVALIDATION / B-REVIEW-STATE-DETECTION-BOOTSTRAP / B-REVIEW-MIGRATION-TRANSACTION。

### v4.16.0 同时补充 3 项 F-REVIEW 检查点

基于「前端接入 api_ai_deep 端点」代码审查复盘（使用 Sequential Thinking 4 维度复盘法）：

- **F-REVIEW-FIELD-CONTRACT-ALIGN**（维度 11）：后端归一化字段时前端 types.ts 必须注释「后端已归一化，前端消费 X 字段」，禁止通过动态 key 取归一化字段
- **F-REVIEW-ASYNC-RACE-CONDITION**（维度 10）：timeout >= 3s 的异步请求必须用 useRef 跟踪最新请求 ID，旧请求的 result/error/loading 三态在 setState 前校验 `ref.current === itemId` 不匹配则丢弃
- **F-REVIEW-ERROR-HANDLER-EXTRACT**（维度 11）：两处以上相同 if-else 状态码分支必须抽取工具函数 `handleXxxError(err, fallbackMsg, closeModal)`

自动化扫描从 69 项扩展到 72 项。后端对应规范为 `xianyu-backend-code-review` v4.16.0 的 B-REVIEW-FIELD-NORMALIZE-DOC / B-REVIEW-DIVZERO-FALLBACK，详细编码规范整合到 `xianyu-hunter-dev` v4.17.0 的 step 94-97。

---

## v4.15.0 登录流程性能优化/Cookie层同步测试修复/代码变更逻辑审查复盘（前端侧）

基于本次会话解决的 4 个问题复盘（使用 Sequential Thinking 4 维度复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-DEBUG-CODE-CLEANUP**（维度 11）：临时 DEBUG 代码在问题修复后必须移除，禁止留在生产代码中，包括临时 import/临时环境变量检查/临时日志文件写入/临时打印语句

自动化扫描从 67 项扩展到 68 项。详细编码规范整合到 `xianyu-hunter-dev` v4.15.0 的 step 88。后端对应规范为 `xianyu-backend-code-review` v4.14.0 的 B-REVIEW-DEBUG-CODE-CLEANUP。

---

## v4.14.0 评估明细过滤/分页/空状态复盘（前端侧）

基于本轮对话解决的「评估明细页面优化」工作复盘（使用 Sequential Thinking 5 步系统分析），新增 3 项 F-REVIEW 检查点：

- **F-REVIEW-FILTER-BACKEND-ALIGN**（维度 7）：实现前端过滤功能前必须先 grep 后端 insufficient_count/marginals/result 确认分类互斥性，前端过滤条件必须与后端分类逻辑对齐
- **F-REVIEW-FILTER-PAGINATION-ADAPT**（维度 10）：添加 filterStatus 状态后必须同步调整 pagination 三参数：total=filteredItems.length、current=1、pageSize=filteredItems.length||1
- **F-REVIEW-FILTER-EMPTY-STATE**（维度 3）：空状态判断必须用 filteredItems.length 而非原始 items.length，区分两种文案

自动化扫描从 64 项扩展到 67 项。后端对应规范为 xianyu-backend-code-review v4.13.0 的 B-REVIEW-STATS-EXCLUSIVE，详细编码规范整合到 xianyu-hunter-dev v4.14.0 的 step 82-85。

---

## v4.13.0 官方采集失败复盘（前端侧）

基于本轮对话解决的「官方采集失败」P0-P3 优化工作复盘（使用 Sequential Thinking 4 维度复盘法），新增 2 项 F-REVIEW 检查点：

- **F-REVIEW-ERROR-CONTRACT-TIMEOUT**（维度 7）：前端 API 模块必须声明模块级 `statusMessages: Record<number, string>` 映射表，axios 错误处理必须提供独立 `isAxiosTimeout(error)` 工具函数双路识别 `error.code === 'ECONNABORTED'` 或 `/timeout/i.test(error.message)`
- **F-REVIEW-RETRY-BACKOFF**（维度 7）：前端 API 重试逻辑必须区分可重试错误集（410/441/502/超时）与需用户介入错误集（401/403/440/503），可重试错误按 `retry_delays_ms` 退避序列重试默认 [500,1500,3000]ms，重试过程 `silent_on_retry=true` 不弹 message

自动化扫描从 62 项扩展到 64 项。后端对应规范为 `xianyu-backend-code-review` v4.12.0 的 B-REVIEW-DOM-FALLBACK-CHAIN / B-REVIEW-FAILURE-DUMP / B-REVIEW-TIMING-INSTRUMENTATION / B-REVIEW-PRECHECK-AND-PARALLEL，详细编码规范整合到 `xianyu-hunter-dev` v4.13.0 的 step 76-81。

---

## v4.12.0 配置加载/输入边界/null 语义/XSS 转义/批量操作复盘（前端侧）

基于本轮对话解决的 5 类前端问题复盘（使用 Sequential Thinking 4 维度复盘法），新增 5 项 F-REVIEW 检查点：

- **F-REVIEW-ASYNC-CONFIG-LOAD**（维度 10）：异步加载配置后设置 usePersistentState 必须双重检查 localStorage 防止竞态，cancelled 标志防止组件卸载后 setState
- **F-REVIEW-INPUT-NUMBER-BOUNDS**（维度 4）：InputNumber 必须设置 min/max 边界，禁止无边界输入导致 0/负数触发后端 ZeroDivisionError
- **F-REVIEW-NULL-SEMANTICS**（维度 4）：类型必须明确区分 null/undefined/空字符串三种语义
- **F-REVIEW-XSS-ESCAPE**（维度 11）：用户输入字段必须 HTML 转义+JSX 双重保护
- **F-REVIEW-BATCH-OPERATION**（维度 7）：批量操作必须实现 Modal.confirm + loading + success/error message + 异常处理 + 状态刷新完整流程

自动化扫描从 57 项扩展到 62 项。后端对应规范为 `xianyu-backend-code-review` v4.11.0 的 B-REVIEW-CONFIG-VALIDATION / B-REVIEW-STATUS-CODE-SEMANTICS，详细编码规范整合到 `xianyu-hunter-dev` v4.12.0 的 step 69-75。

---

## v4.11.0 状态机/双链路/缓存一致性复盘（前端侧）

基于后端 v4.9.0 的 5 类问题复盘（使用 Sequential Thinking 4 维度复盘法），新增 3 项 F-REVIEW 检查点：

- **F-REVIEW-STATE-ENUM-ALIGN**（维度 4）：前后端状态枚举值必须严格对齐，禁止前端硬编码状态字符串而应从 `types.ts` 导出常量联合类型
- **F-REVIEW-STATE-MACHINE-UI**（维度 3）：状态机每个状态值必须有对应的 UI 视觉标识，终态禁止显示"进行中"类动画，中间态必须有 loading 反馈
- **F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY**（维度 6）：多链路触发同一状态变更时必须通过统一 refetch 入口刷新缓存，禁止各链路独立 setState

自动化扫描从 54 项扩展到 57 项。后端对应规范为 `xianyu-backend-code-review` v4.9.0 的 B-REVIEW-STATE-MACHINE-WHITELIST / B-REVIEW-DUAL-LINK-CONSISTENCY，详细编码规范整合到 `xianyu-hunter-dev` v4.10.0 的 step 60-64。

---

## v4.10.0 过滤结果可见性复盘（前端侧）

基于"实时搜索过滤结果全部被筛掉但前端只显示'查询完成'导致用户不知原因"问题复盘（使用 Sequential Thinking 8 步系统分析），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-FILTER-VISIBILITY**（维度 7）：后端返回 `filter_summary` 时前端必须实现三态提示策略 success/warning/info；`filtered_out` 非空时必须提供"查看被过滤结果"按钮+Modal；API 返回类型必须显式声明 `filter_summary?` 字段，禁止 `as` 强制类型转换绕过 TS 检查

自动化扫描从 53 项扩展到 54 项。后端对应规范为 `xianyu-backend-code-review` v4.10.0 的 B-REVIEW-FILTER-VISIBILITY，详细编码规范整合到 `xianyu-hunter-dev` v4.11.0 的 step 65。

---

## v4.9.0 频率伪装统计孤岛复盘（前端定时刷新）

基于"反爬登录管理菜单的频率伪装统计持续为 0 且无变化"问题复盘（与后端 v4.8.0 配合，使用 Sequential Thinking 4 维度复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-FREQ-STATS-POLLING**（维度 10）：累计统计类 API（频率伪装统计 / 采样器 / 计数器 / 令牌桶 / 健康评分）必须在前端通过 `setInterval` 定时刷新，不能只依赖"页面加载时拉一次"

自动化扫描从 52 项扩展到 53 项。核心机制：业务模块持续调用后端核心模块累加统计，前端若不轮询，UI 会永远停留在某个时刻的快照。后端对应规范为 `xianyu-backend-code-review` v4.8.0 的 B-REVIEW-ISLAND-MODULE，详细编码规范整合到 `xianyu-hunter-dev` v4.9.0 的 step 56-59。

---

## v4.8.0 AntD 主题 token 动态覆盖复盘

基于"暗色主题下 Table hover 高亮色与文字色一致导致不可见"问题复盘（使用 Sequential Thinking 5 步系统分析），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE**（维度 5）：项目支持暗色主题时，`baseTheme.components.<Component>.<token>` 中显式指定的主题相关 token（含 `Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus` 后缀）必须根据 `isDark` 状态在 `ThemedRoot` 内动态覆盖，禁止依赖 `darkAlgorithm` 自动重算或 `index.css` 的 `--ant-*` CSS 变量

自动化扫描从 51 项扩展到 52 项。核心机制：antd v5 `darkAlgorithm` 仅重算未指定 token + `cssVar` 模式默认未启用。

---

## v4.7.0 异步反馈 + 数据流转 + 过滤场景 + 复用模式复盘

基于"评估明细标题采集超时 + 订单字段为空根因定位 + 一刀切过滤导致展示缺失"三个问题复盘（使用 Sequential Thinking 5 步系统分析），新增 4 项 F-REVIEW 检查点：

- **F-REVIEW-ASYNC-FEEDBACK**（维度 10）：前端异步操作必须实现 loading → success → error 三态反馈，禁止 `.catch(() => {})` 静默吞错误
- **F-REVIEW-DATA-FLOW-TRACE-FRONTEND**（维度 11）：前端"字段为空"类问题必须配合后端按 5 点逐层追踪，前端侧验证 types 声明 + render 取值
- **F-REVIEW-FILTER-SCENARIO-FRONTEND**（维度 7）：前端调用后端查询接口时必须按场景传 `include_failed` 等场景标志，展示历史场景传 True
- **F-REVIEW-REUSE-PATTERN-FRONTEND**（维度 18）：新增前端功能前必须 grep 项目内相似实现，复用既有 Hook/工具函数/模式

自动化扫描从 47 项扩展到 51 项。

---

## v4.6.0 Cookie 分层管理架构前端同步复盘

基于后端 5 个登录路径不更新 CookieRotator 层状态 + cookie_checker 覆盖手动失效问题复盘，新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND**（维度 6）：前端调用同一后端写入接口的不同代码路径时，状态更新必须统一通过单一 `updateState` 函数而非各路径独立更新

自动化扫描从 46 项扩展到 47 项。

---

## v4.5.0 搜索参数链路 + 错误语义复盘

基于"实时搜索错误提示语义偏差 + 搜索参数配置不生效"两个问题复盘（使用 Sequential Thinking 4 维度分析），新增 2 项 F-REVIEW 检查点：

- **F-REVIEW-ERROR-SEMANTICS**（维度 11）：前端错误提示文案必须与后端错误根因语义匹配（如 RGV587=token 过期不应显示"登录已过期"）
- **F-REVIEW-CONFIG-LINKAGE**（维度 7）：前端配置项从定义到消费必须全链路追踪，配置注入≠配置生效

自动化扫描从 44 项扩展到 46 项。

---

## v4.4.0 浏览器 Cookie 导入增强复盘

基于"浏览器 Cookie 导入增强（v20 加密 + 多 Profile + 自动同步）"复盘（使用 Sequential Thinking 4 维度分析），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-CONFIG-DRIVEN-TOGGLE**（维度 11）：前端高风险功能（如自动同步开关、CDP 调试触发按钮）必须配置驱动，参数集中在 `constants.ts` 或 config 文件管理（不硬编码），默认关闭需用户显式启用

自动化扫描从 43 项扩展到 44 项。

---

## v4.3.0 反爬模块代码审查复盘

基于反爬模块全面评估复盘，新增维度 19（跨组件状态同步与死代码检测），补充检查项：Proxy/Observer 赋值给局部变量（死代码）、try/finally 变量未初始化为 None、跨组件对同一概念判断维度差异、错误提示引用不存在的端点/路由，自动化扫描从 39 项扩展到 43 项。

---

## v4.2.0 UI 状态独立性复盘

基于"菜单树动画遮挡"问题复盘，新增 F-REVIEW-UI-STATE-INDEPENDENCE 检查项到维度 3（React 组件规范），要求受控 UI 状态（`openKeys`/`expandedKeys`/`activeKey`）不应通过 `useEffect` 联动路由变化，仅在用户主动操作时变化；路由变化只应更新派生状态（`selectedKeys`/breadcrumb）。自动化扫描从 38 项扩展到 39 项。

---

## v4.1.0 SSE 错误处理复盘

基于"实时搜索会话失效未推送明确错误提示"问题复盘，新增维度 15（F-REVIEW-SSE-ERROR-HANDLING：SSE 错误事件状态码分类处理 + "前往登录"跳转引导）补充检查项，对应后端 v4.1.0 的错误粒度三类区分（503/504 稍后重试、401/403 需用户介入、502 需重启服务），自动化扫描从 36 项扩展到 38 项。

---

## v4.0.0 布局重构/搜索标准化/代码质量复盘

基于 AI 服务页面 Tab 布局重构 + 实时搜索标准化 + 代码评审通用规范复盘，新增维度 3（多视图 state 提升）、维度 10（requestId 竞态保护 + 统一防抖）、维度 11（IIFE 反模式禁止 + 动态资源映射分离）、维度 17（外部链接 rel 安全）、维度 18（显式样式 + 注释一致性）补充检查项，自动化扫描从 26 项扩展到 36 项。

---

## v3.0.0 SonarQube 规则增强

基于 SonarQube 修复实战复盘，扩展维度 12（SonarQube 合规）从 8 条规则到 16 条，新增 S7503（不必要 async）、S6767（未使用 Props/State）、S6819/S6844（div/anchor 替代 button）、S7744（不必要类型转换）、S6582（冗余可选链）、S7735（useEffect 依赖缺失）、S6551（for...in）、S1874（@deprecated 缺失），自动化扫描从 14 项扩展到 26 项；抽象建议新增"纯函数+组件+常量分层"模式（如 `resolveActionDisplay` + `ActionPlaceholder` + `ACTION_PLACEHOLDER_TEXT`）。

---

## v2.0.0 知识点整合

整合 `xianyu-hunter-dev` 技能的 `frontend-guide.md` 与 `project-rules.md` 硬约束，新增维度 1（目录结构）、3（React 组件规范）、4（TypeScript 严格规范）、5（AntD 5 主题）、6（Zustand 状态管理）、7（API 调用规范）、8（路由与懒加载）、9（SheetWorkspace 多页签）、10（Hooks 设计模式）、12（SonarQube 合规）、13（PWA 配置）、14（三处映射同步）、15（SSE 重连）、17（移动端适配）、18（闲鱼项目规范），扩展抽象建议与硬约束规则，自动化扫描 12 项。
