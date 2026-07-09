# 版本历史

> 本文件由 SKILL.md 外外而来，记录 xianyu-hunter-dev skill 各版本复盘与编码规范演进。
> 主索引见 [SKILL.md](../SKILL.md) 的"step 索引表"。

## v4.39.0 experimental 元规范（meta-rules #64-#65 预沉淀）

基于 2026-07-08 解决的「URL↔状态同步失败回退 / Service Worker 缓存版本同步」2 类问题复盘，使用 Sequential Thinking 4 维度复盘法（成功步骤 / 不确定性与失败点 / 可抽象的固定流程与判断逻辑 / 适用场景与不适用场景），新增 2 条 experimental 元规范（meta-rules #64-65）。案例数<3 次，按 meta-rule #36 门槛规则标 experimental 标签预沉淀，观察期 2026-07-08 至 2026-10-08：

**meta-rules.md（2 条 experimental，#64-#65）**：
- **#64 URL↔状态同步失败回退（URL-STATE-SYNC-FALLBACK）experimental**：SheetWorkspace 多页签应用中，URL 变化触发 openSheet 失败时（路径未注册 / 栈满），URL 已改变但 activeId 未变，导致 useParams() 返回错误值，业务逻辑误判。必须在 openSheet 失败时回退 URL 到当前 active sheet 的 path
- **#65 Service Worker 缓存版本同步（SW-CACHE-VERSION-SYNC）experimental**：PWA 应用构建时生成版本哈希，运行时版本检测不一致时触发 skipWaiting 强制更新，避免用户浏览器缓存旧版本导致功能异常

**门槛校验（meta-rule #36）**：
- #64 experimental：仅 2026-07-08 一个案例（useParams 漂移导致 isEdit 误判），未达 ≥3 次门槛，标 experimental 预沉淀
- #65 experimental：仅 2026-07-08 一个案例（PC 端重定向到移动端），未达 ≥3 次门槛，标 experimental 预沉淀
- 观察期：2026-07-08 至 2026-10-08（1 季度），观察期内若再出现 ≥2 个相似 bug 则升级为正式规范，否则废弃

**coding-rules（2 条预沉淀，step 205-206）**：
- **step 205 URL-STATE-SYNC-FALLBACK URL↔状态同步失败回退** → state-management.md（预沉淀）
- **step 206 SW-CACHE-VERSION-SYNC Service Worker 缓存版本同步** → frontend-ui.md（预沉淀）

**审查技能同步落地（预沉淀）**：
- `xianyu-frontend-code-review`：新增 2 项 F-REVIEW（F-REVIEW-152 URL↔状态同步失败回退 / F-REVIEW-153 SW 缓存版本同步）
- `xianyu-backend-code-review`：无新增（纯前端规范）

**配置节点**（全部从 config.yaml 读取，无硬编码）：
- `url_state_sync_fallback`：enabled / fallback_strategy / detection_patterns / applicable_routes
- `sw_cache_version_sync`：enabled / version_detection / skip_waiting_trigger / hard_refresh_prompt

**历史教训来源（2 类问题）**：
1. **URL↔状态同步失败回退**：任务修改流程中点击 Step 3「全局搜索配置」按钮，navigate('/app/config/search') 多了 /app 前缀（basename），findSheetMeta 返回 undefined，触发 React Router * 重定向到 /。此时 URL 变为 /，但 activeId 仍指向 TaskEditor，useParams().id 返回 undefined，isEdit 误判为 false，提交时创建重复任务
2. **Service Worker 缓存版本同步**：PC 端首次登录后重定向到 /app/m/（移动端），根因是浏览器缓存了旧版 sw.js，旧版 SPA 中 useMobileDetect.ts 用 pointer:coarse 触屏判断导致 PC 端误判为移动端

**与 v4.38.0 的关系**：v4.38.0 落地了 #57-#63（异步与资源安全元规范），本批次 #64-#65 为 experimental 预沉淀，聚焦「前端状态同步与缓存版本」维度。#64 与 #44 前端路由三重注册同步互补：#44 管"路由注册同步"，#64 管"同步失败回退"。

---

## v4.38.0 异步与资源安全元规范（meta-rules #57-#63 落地）

基于 2026-07-08 修复的「async/await 误用 / NullPool 性能问题 / HTTP 状态码语义模糊 / CSS 选择器失效 / 异常日志丢失 traceback / 并发安全 page closure / 参数传递缺失 / 日志质量退化链」8 类问题复盘，使用 Sequential Thinking 8 步复盘法（问题识别 → 根因分析 → 修复方案 → 验证 → 影响评估 → 规范候选 → 落地决策 → 内容设计），新增 7 条元规范（meta-rules #57-#63）+ 7 步编码规范（step 198-204），step 总数从 197 → 204，元规范总数从 56 → 63：

**meta-rules.md（7 条，#57-#63）**：
- **#57 async/await 同步性静态检查（ASYNC-AWAIT-SYNC-CHECK）**：async def 方法体内若不含 await 表达式，必须改为同步 def；调用点同步移除 await
- **#58 资源池配置性能基准与决策（RESOURCE-POOL-BENCHMARK）**：数据库/HTTP/浏览器资源池配置必须有性能基准数据支持，docstring 记录选择理由与对比数据
- **#59 HTTP 状态码精细化映射表（HTTP-STATUS-CODE-MAPPING）**：HTTP 状态码必须有统一映射表，状态码语义必须与错误根因匹配，前端按状态码分类处理
- **#60 CSS 选择器多级降级策略（CSS-SELECTOR-FALLBACK）**：CSS 选择器必须按「特定 → 通用 → 最末兜底」三级降级，每级失败进入下一级
- **#61 异常日志语义保留规范（EXCEPTION-LOG-SEMANTIC）**：关键路径必须用 logger.exception() 保留完整堆栈，日志必须含业务上下文
- **#62 外部资源生命周期配对管理（EXTERNAL-RESOURCE-LIFECYCLE）**：register/unregister 必须配对，持有强引用防 GC，使用前检测 is_closed
- **#63 数据库写入函数身份追溯与类型安全（DB-WRITE-IDENTITY-TRACE）**：写入/查询函数必须显式接收 user_id 参数，WHERE 子句过滤，调用点必须传 user_id

**coding-rules（7 条，step 198-204）**：
- **step 198 ASYNC-AWAIT-SYNC-CHECK async/await 同步性静态检查** → concurrency.md
- **step 199 RESOURCE-POOL-BENCHMARK 资源池配置性能基准与决策** → database.md
- **step 200 HTTP-STATUS-CODE-MAPPING HTTP 状态码精细化映射表** → error-handling.md
- **step 201 CSS-SELECTOR-FALLBACK CSS 选择器多级降级策略** → browser-automation.md
- **step 202 EXCEPTION-LOG-SEMANTIC 异常日志语义保留规范** → error-handling.md
- **step 203 EXTERNAL-RESOURCE-LIFECYCLE 外部资源生命周期配对管理** → concurrency.md
- **step 204 DB-WRITE-IDENTITY-TRACE 数据库写入函数身份追溯与类型安全** → database.md / security.md（双归档：database.md 完整规范 + security.md 安全维度引用）

**编号调整说明**：
- 原计划使用 step 189-195，但发现 step 189-197 已被 v4.37.0 占用（PARAM-CHAIN-EXEC-01 / MODE-VERTICAL-CHAIN-01 / PARSER-FALLBACK-01 / MOCK-SYNC-01 / FILTER-TRANS-01 / SCHEDULER-RUNTIME-TOGGLE-SYMMETRY / CRON-MIN-INTERVAL-CHECK / TIME-PARAM-CONFIG-DRIVEN / LIFECYCLE-RESOURCE-CLEANUP）
- 调整为 step 198-204（紧接 v4.37.0 的 step 197 之后）
- B-REVIEW 编号：186-192（紧接 v4.37.0 的 B-REVIEW-181 之后）
- F-REVIEW 编号：144-147（紧接 v4.37.0 的 F-REVIEW-134 之后）

**门槛校验（meta-rule #36）**：
- #57 正式规范：async def 误用 + Python 3.14 告警 + 调用点 await 不匹配 共 3 个相似 bug，达标
- #58 正式规范：NullPool 性能 + HTTP 连接池 + 浏览器实例池 共 3 个资源池配置场景，达标
- #59 正式规范：RGV587→401 误映射 + 502/504 混用 + 401/403 混用 共 3 个状态码语义问题，达标
- #60 正式规范：tabItem 失效 + data-id 失效 + className 变更 共 3 个选择器失效场景，达标
- #61 正式规范：logger.warning 丢堆栈 + 无业务上下文 + except pass 共 3 个日志退化场景，达标
- #62 正式规范：PageRegistry 无 unregister + page GC 后引用 + 无 is_closed 检测 共 3 个资源生命周期 bug，达标
- #63 正式规范：get_item 缺 user_id + 5 个调用点 TypeError + 跨用户数据泄露风险 共 3 个身份追溯问题，达标

**审查技能同步落地（待落地）**：
- `xianyu-backend-code-review` v4.37.0 → v4.38.0：新增 7 项 B-REVIEW（B-REVIEW-182 async/await 同步性 / B-REVIEW-183 资源池基准 / B-REVIEW-184 HTTP 状态码映射 / B-REVIEW-185 CSS 选择器降级 / B-REVIEW-186 异常日志语义 / B-REVIEW-187 外部资源生命周期 / B-REVIEW-188 数据库写入身份追溯）
- `xianyu-frontend-code-review` v4.40.0 → v4.41.0：新增 4 项 F-REVIEW（F-REVIEW-148 async/await 同步性 / F-REVIEW-149 HTTP 状态码分类处理 / F-REVIEW-150 异常日志语义 / F-REVIEW-151 外部资源生命周期）

**配置节点**（全部从 config.yaml 读取，无硬编码，已添加到 `config/tech-stack.json` 的 `hardConstraints` 节点）：
- `asyncAwaitCheck`：require_true_await / python_min_version / forbidden_patterns / exempt_decorators
- `resourcePoolBenchmark`：require_docstring / require_benchmark_script / slow_query_threshold_ms / monitor_days
- `httpStatusCodeMapping`：mapping_config_path / require_consistency_check / forbidden_mappings
- `cssSelectorFallback`：required_levels / fallback_chain_log_level / selector_repository_required
- `exceptionLogSemantic`：critical_path_use_exception / require_business_context / forbidden_patterns
- `externalResourceLifecycle`：required_pair_methods / strong_reference_required / is_closed_check_before_use
- `dbWriteIdentityTrace`：required_user_id_param / where_filter_required / audit_log_required_for_write

**历史教训来源（8 类问题）**：
1. **async/await 误用**：`async def` 方法体内不含真异步 await，FastAPI 路由并发性能从 1000 QPS 退化为 50 QPS，Python 3.14 升级后 `RuntimeWarning: coroutine never awaited` 告警
2. **NullPool 性能问题**：多用户场景下 NullPool 每次请求创建新连接，P99 延迟从 50ms 涨到 200ms，无基准数据无法定位
3. **HTTP 状态码语义模糊**：RGV587 反爬映射为 401（登录失效），实际是 `_m_h5_tk` 临时 token 过期，前端误导用户重新登录
4. **CSS 选择器失效**：`.tabItem` className 变更为 `_tabItem_1a2b3`，选择器失效导致 `on_sale=0` 和 `sold=0`，用户反馈"商品数据全空"
5. **异常日志丢失 traceback**：`logger.warning(f"失败: {e}")` 只保留一行 message，排查 2 小时才定位 C-01 失败导致 C-04 被跳过
6. **并发安全 page closure**：PageRegistry 只 register 不 unregister，30 分钟累积 50+ 未关闭 page，内存从 200MB 涨到 800MB
7. **参数传递缺失**：`ItemsMixin.get_item()` 缺少 `user_id` 参数，5 个路由调用点传 `user_id` 触发 TypeError，导致 GET /api/items/test-item-001/summary 接口 500 错误
8. **日志质量退化链**：`except: pass` 静默吞异常 + `logger.warning(f"...{e}")` 丢失堆栈 + 无业务上下文，三种退化叠加导致问题排查时间从分钟级延长到小时级

**与 v4.37.0 的关系**：v4.37.0 落地了 #52-#56（参数链闭环 / 业务模式纵向链路 / 外部页面解析容错 / mock 同步 / 过滤结果透明化 UI），本批次 #57-#63 聚焦「异步与资源安全」维度，与 v4.37.0 的「工程闭环」维度互补。#60 CSS-SELECTOR-FALLBACK 与 v4.37.0 #54 PARSER-FALLBACK-CHAIN 互补：#54 管"解析器三级 fallback"，#60 管"CSS 选择器多级降级"。

**SKILL.md 速查表补全**：本次更新同时补全了 v4.37.0 遗留债务——SKILL.md 速查表此前只到 #51，本次更新补全了 #52-#56（v4.37）和 #57-#63（v4.38）共 12 行。

---

## v4.37.0 工程闭环元规范（meta-rules #52-#56 落地）

基于 2026-07-07 修复的「价格过滤失效 / SEMI_AUTO 模式退化 / 外部 DOM 解析失败 / 测试 mock 错配 / 多参数 UI 不透明」5 类问题复盘，使用 Sequential Thinking 4 维度复盘法（成功步骤 / 不确定性与失败点 / 可抽象的固定流程与判断逻辑 / 适用场景与不适用场景），新增 5 条元规范（meta-rules #52-#56）+ 5 步编码规范（step 189-193），step 总数从 188 → 193，元规范总数从 47 → 52（注：#48-#51 为 v4.36.0 规划但未落地，保留为未来工作）：

**meta-rules.md（5 条，#52-#56）**：
- **#52 参数链闭环验证（PARAM-CHAIN-EXEC）**：过滤类参数必须存在消费点，禁止"参数已接收但未被消费"
- **#53 业务模式纵向链路一致性（MODE-VERTICAL-CHAIN）**：业务模式枚举必须在决策/事件/通知/路由/接口/状态机 6 层纵向一致传递
- **#54 外部页面解析容错（PARSER-FALLBACK-CHAIN）**：解析第三方 DOM 必须三级 fallback selector 策略
- **#55 mock 同步与边界精确性（MOCK-SYNC-BOUNDARY）**：mock 类型与边界必须与被 mock 对象同步（与 #47 EXTERNAL-DEP-ISOLATION 互补：#47 管"是否 patch"，#55 管"如何 patch"）
- **#56 过滤结果透明化 UI（FILTER-RESULT-TRANSPARENCY-UI）**：≥2 个过滤参数的列表 UI 必须透明化展示

**coding-rules（5 条，step 189-193）**：
- **step 189 PARAM-CHAIN-EXEC-01 参数链闭环验证规范** → config-driven.md
- **step 190 MODE-VERTICAL-CHAIN-01 业务模式纵向链路一致性规范** → state-management.md
- **step 191 PARSER-FALLBACK-01 外部页面解析容错规范** → browser-automation.md
- **step 192 MOCK-SYNC-01 mock 同步与边界精确性规范** → testing.md
- **step 193 FILTER-TRANS-01 过滤结果透明化 UI 规范** → frontend-ui.md

**与 v4.36.0 的关系**：v4.36.0 已规划 #48-#51（调度器运行时开关对称性 / 时间参数配置化 / 长生命周期对象状态清理 / cron 最小间隔校验），但未在 meta-rules.md 落地。本批次 #52-#56 不重复定义调度器开关规范，与 v4.36.0 #48 视角互补。

代码修复点：`evaluations_list.py`（_resolve_market_ratio / _compute_eval_market_median / _filter_market_ratio）/ `worker.py`（EVAL_PASSED 事件 payload 含 task_mode）/ `templates.py`（SEMI_AUTO 通知含确认链接）/ `App.tsx`（新增 /confirm-buy 路由）/ `ConfirmBuy/index.tsx`（新页面）/ `_detail.py`（三级 fallback selector）/ `test_notifier_new_channels.py` / `test_manual_takeover_lock.py` / `test_dingtalk_notify_integration.py`（mock 类型对齐）/ `Evaluations/index.tsx`（价格范围 Tooltip）

审查技能同步落地：`xianyu-backend-code-review` v4.33.0 → v4.37.0 新增 4 项 B-REVIEW（B-REVIEW-177~180，过滤透明化 UI 仅前端不适用）；`xianyu-frontend-code-review` v4.38.0 → v4.42.0 新增 4 项 F-REVIEW（F-REVIEW-144~147，PARSER-FALLBACK 前端不适用）。

历史教训来源：
1. **价格过滤逻辑 Bug**：调整"低于市场参考价"到 0.85 仍能查出价格上限 800 商品，根因是 list_evaluations API 未调用 PriceStrategy.check
2. **SEMI_AUTO 模式退化**：通知中心点击无反应，根因是 5 层链路断裂（决策/事件/通知/路由/接口）
3. **DOM 解析失败**：闲鱼页面 tabItem class 名变更导致 on_sale=0 和 sold=0
4. **测试 mock 错配**：AsyncMock 用在同步函数 / patch 边界错误 / mock 数据不完整
5. **多参数 UI 不透明**：评估明细菜单无 tooltip 说明查询规则

---

## v4.36.0 调度器运行时治理元规范（meta-rules #48-51 落地）

基于 2026-07-07 解决的「任务管理自动执行逻辑审查」5 类问题（BatchRefreshScheduler 运行时禁用无效 / CookieSyncScheduler 无法运行时禁用 / scheduler 异常重试等待硬编码 300s / _resume_cooldown 字典内存泄漏 / Cron 模式无最小间隔校验），使用 Sequential Thinking 4 维度复盘法（成功步骤 / 不确定性与失败点 / 可抽象的固定流程与判断逻辑 / 适用场景与不适用场景），新增 4 条元规范（meta-rules #48-51），元规范总数从 47 → 51：

**meta-rules.md（4 条，#48-#51）**：
- **#48 调度器运行时开关对称性（SCHEDULER-RUNTIME-TOGGLE-SYMMETRY）**：update_config(enabled=False) 必立即 remove_job + 入口 double-check；enabled=True 必恢复 job，开关操作必须对称，配置参数在 `scheduler_runtime_toggle` 节点管理
- **#49 时间参数配置化（TIME-PARAM-CONFIG-DRIVEN）**：异常重试等待/轮询间隔/超时秒数必须从 config 读取，禁止硬编码字面量数字，配置类必须设 ge/le 边界值校验，按 #42 兜底范式 try/except 包裹，配置参数在 `time_param_config_driven` 节点管理
- **#50 长生命周期对象状态清理（LIFECYCLE-RESOURCE-CLEANUP）**：长生命周期对象持 task 级状态字典必须提供 drop_task_state(task_id) 方法，DELETE API 删除 task 时调用，try/except 容错不阻断主流程，配置参数在 `lifecycle_resource_cleanup` 节点管理
- **#51 用户输入时间表达式校验（CRON-MIN-INTERVAL-CHECK）experimental**：cron 表达式必须校验最小间隔 ≥ 反爬最小延迟（antidetect.min_delay_ms / 1000），配置读取失败回退 10 秒默认值，配置参数在 `cron_min_interval_check` 节点管理。仅 1 个相似 bug，按 #36 门槛规则标 experimental 标签预沉淀，1 季度观察期

**门槛校验（meta-rule #36）**：
- #48 正式规范：BatchRefreshScheduler + CookieSyncScheduler + scheduler._stop_flag 共 3 个相似 bug，达标
- #49 正式规范：error_retry_wait_seconds + interval_minutes + cookie_sync_interval 共 3 个硬编码时间参数，达标
- #50 正式规范：_resume_cooldown + _last_failure_reason + _task_status_cache 共 3 个状态字典泄漏，达标
- #51 experimental：仅 Cron 模式无最小间隔校验 1 个相似 bug，未达标，标 experimental 标签

**代码修复点**：
- `batch_refresh_scheduler.py`：update_config(enabled=False) 立即 remove_job + _run_batch_job 入口 double-check
- `cookie_sync_scheduler.py`：新增 _enabled 字段 + update_config 方法 + _run_sync_job 入口 double-check
- `scheduler.py`：异常重试等待从 config 读取 + 新增 drop_task_state 方法 + _get_min_cron_interval_seconds 静态方法 + _compute_next_wait_seconds cron 间隔校验
- `yaml_config.py`：新增 TaskSchedulerConfig.error_retry_wait_seconds: int = Field(300, ge=10, le=3600)
- `api_tasks.py`：delete_task 与 batch_delete_tasks 调用 container.scheduler.drop_task_state(task_id)，try/except 容错
- `config.example.yaml`：新增 task_scheduler.error_retry_wait_seconds 配置项

**审查技能同步落地**：
- `xianyu-backend-code-review` v4.33.0 → v4.34.0：新增 4 项 B-REVIEW（B-REVIEW-173 调度器开关对称性 / B-REVIEW-174 时间参数配置化 / B-REVIEW-175 长生命周期对象状态清理 / B-REVIEW-176 cron 最小间隔校验），自动化扫描从 163 项扩展到 167 项
- `xianyu-frontend-code-review` v4.37.0 → v4.38.0：新增 4 项 F-REVIEW（F-REVIEW-127 调度器开关 UI 同步 / F-REVIEW-128 时间参数配置化 / F-REVIEW-129 长生命周期对象状态清理 / F-REVIEW-130 cron 表达式输入提示），自动化扫描从 121 项扩展到 125 项

**配置节点**（全部从 config.yaml 读取，无硬编码）：
- `scheduler_runtime_toggle`：开关方法名、入口函数名、double-check 模式
- `time_param_config_driven`：时间参数模式清单、边界值范围、兜底默认值表
- `lifecycle_resource_cleanup`：状态字典清单、清理方法名、异常日志级别
- `cron_min_interval_check`：最小间隔阈值、校验错误消息模板、豁免场景清单

**历史教训来源**：
1. **BatchRefreshScheduler 运行时禁用无效**：用户禁用批量采集后仍持续执行，根因是 update_config(enabled=False) 只设 _enabled 标志未 remove_job，APScheduler job 仍按 trigger 触发
2. **CookieSyncScheduler 无法运行时禁用**：CookieSyncScheduler 无 _enabled 字段，根本无法运行时禁用
3. **scheduler 异常重试等待硬编码 300s**：asyncio.sleep(300) 硬编码，开发环境想缩短需改代码重新部署
4. **_resume_cooldown 字典内存泄漏**：task 删除后 _resume_cooldown 条目残留，30 天累积 5000+ 条目，内存从 1MB 增到 50MB
5. **Cron 模式无最小间隔校验**：用户配置 */1 * * * * 每分钟一次，过于频繁导致 IP 被风控

**已知债务**：v4.32.0 ~ v4.35.0 的 version-history 条目待补（meta-rules #33-#47 已在 SKILL.md 速查表与 meta-rules.md 中落地，但 version-history.md 缺失对应版本条目），需后续补全。

## v4.31.0 状态恢复前置校验 + 多阶段降级链日志合并（meta-rules #31/#32 落地）

基于 2026-07-02 日志排查报告发现的两类高频问题，使用 Sequential Thinking 5 步复盘法（问题识别 → 规范候选 → 落地决策 → 内容设计 → 执行规划），新增 2 条元规范（meta-rules #31/#32）+ 2 步编码规范（step 179-180），step 总数从 178 → 180，元规范总数从 30 → 32：

**meta-rules.md（2 条，#31-#32）**：
- **#31 状态恢复前置校验（pause→resume 根因消除校验）**：具有 pause/resume 语义的组件（任务调度器、登录会话、连接池、断路器）在 resume 前必须校验"导致 pause 的根因"是否消除，未消除时返回结构化拒绝响应并设冷却期，禁止无条件放行
- **#32 多阶段降级链日志合并**：同一逻辑链的多个中间阶段（降级、重试、回退、多策略尝试）日志必须合并为 1 条结构化结果日志，中间步骤 DEBUG 化，最终结果用 WARNING + extra 字段（stages/final_reason/attempts）

**state-management.md（1 条，step 179）**：
- **step 179 RESUME-01 状态恢复前置校验原则**：异常 pause 必须持久化 root_cause（reason_code + 失效层 + 时间戳），resume 前 precheck 校验根因消除，失败时返回 `{resume_blocked, reason_code, user_hint, retry_after}` 结构化响应，冷却期与 precheck 映射表从 `config.yaml#resume_policy` 读取

**error-handling.md（1 条，step 180）**：
- **step 180 LOGMERGE-01 降级链日志合并原则**：降级/重试链中间步骤用 `logger.debug()`，最终结果合并为 1 条结构化 WARNING（含 `extra={stages, final_reason, keyword, attempts}`），合并阈值与 DEBUG 开关从 `config.yaml#log_merge` 读取

代码修复点：`scheduler.py` resume 前校验 `cookie_rotator` 的 identity/session 层 valid 状态，失效时拒绝恢复并提示"请先重新登录闲鱼"；`_search.py` 降级链中间步骤（API 失败 → 刷新 _m_h5_tk → 刷新失败 → DOM 回退 → DOM 超时）从 5 条 WARNING 降为 DEBUG，最终合并为 1 条结构化 WARNING，告警量从 628 降至 ~80。

审查技能同步落地：`xianyu-backend-code-review` v4.29 → v4.30 新增 2 项 B-REVIEW（B-REVIEW-157 调度器/任务恢复前置校验 / B-REVIEW-158 降级链日志合并）；`xianyu-frontend-code-review` v4.34 → v4.35 新增 1 项 F-REVIEW（F-REVIEW-116 resume 按钮前置校验，前端仅校验 UI 层 root_cause 提示，不涉及降级链日志）。

历史教训来源：
1. **任务 `t68bc149b` 会话失效无效循环**：搜索任务因 RGV587_ERROR 被自动暂停后，用户/系统在 30 分钟内连续 4 次恢复，但 Cookie 未重新登录刷新，每次恢复后 13~22 秒内再次触发会话失效检测并暂停，形成"恢复→失效→暂停"无效循环，浪费浏览器资源并产生 555 条冗余 WARNING
2. **搜索 API 5 阶段 555 条冗余 WARNING**：`_search.py` 在同一次搜索失败中输出 5 条 WARNING（FAIL_SYS_ILLEGAL_ACCESS → 尝试强制刷新 _m_h5_tk → 刷新失败 → 尝试 DOM 回退 → DOM 回退超时），12 小时累积 555 条冗余 WARNING（占总 WARNING 88%），淹没真正需要关注的告警

## v4.29.0 编码规范批量沉淀（时区一致性 / 熔断器持久化 / 异步竞态 / 多源状态同步 / Cookie 完整保留 / 关键词集中管理 / 前后端契约对齐）

基于近期多个问题复盘（使用 Sequential Thinking 复盘法），新增 35 条编码规范（step 138-178）到 8 个主题文件，step 总数从 137 → 178：

**database.md（6 条，step 138-143）**：
- **step 138 DATETIME-TZ-01 时区一致性三步检查法**：datetime 混用 naive/aware 导致 TypeError，必须来源识别 + 对齐策略 + 能力检测
- **step 139 DATETIME-TZ-02 原生 SQL 返回值防御**：SQLAlchemy text() 返回 DateTime 列可能为字符串，必须封装 `_coerce_datetime()` 转换
- **step 140 MIGRATE-01 迁移步骤独立性原则**：独立迁移步骤必须各自 try/except，禁止外层统一捕获吞掉异常
- **step 141 NULL-01 NOT NULL 字段防御原则**：DB NOT NULL 字段在 API 层必须做 null 防御，禁止直接写入触发 IntegrityError
- **step 142 QUERY-01 数据查询条件精确性原则**：匹配单个值用 `==` 精确匹配，禁止 startswith/endswith 做前缀过滤
- **step 143 ENUM-01 状态值枚举一致性原则**：业务逻辑状态值必须与 DB 枚举完全一致，禁止用同义词

**error-handling.md（5 条，step 144-148）**：
- **step 144 ATTRIB-01 错误归因精细化原则**：错误归因必须定位到具体模块/函数/行号，禁止笼统归因
- **step 145 EXCEPT-01 异常传播原则**：底层异常必须传播到能处理的层级，禁止静默吞掉
- **step 146 ERROR-01 错误消息透传原则**：错误消息必须透传根因信息，禁止丢失上下文
- **step 147 RETRY-01 重试策略配置化原则**：重试次数/间隔/退避策略必须配置化，禁止硬编码
- **step 148 LOG-NOISE-01 已知场景日志降噪原则**：已知场景（如健康检查）必须降噪，禁止 INFO 级日志刷屏

**state-management.md（6 条，step 149-154）**：
- **step 149 CIRCUIT-01 熔断器持久化对称性原则**：熔断器触发时必须调用 `_save_progress()`，与用户停止分支保持对称
- **step 150 STATE-01 状态切换原子性原则**：状态切换必须同步更新所有相关字段（如 activateSheet 必须设 minimized:false）
- **step 151 CONSISTENCY-01 多源失效判定一致性原则**：多源（健康检查器/worker）失效判定标准必须一致
- **step 152 FALLBACK-01 缺失数据回退策略**：主数据源缺失时必须降级到备用数据源（如浏览器内存）
- **step 153 SYNC-01 多源状态同步标记机制**：多源写入必须用 pending marker 标记，消费方必须检测并消费标记
- **step 154 RACE-01 异步竞态防护原则**：长耗时异步请求必须用 useRef + 请求 ID 校验防护 race condition

**config-driven.md（4 条，step 155-158）**：
- **step 155 PARAM-CHAIN-01 参数传递链完整性原则**：参数传递链路（config → API → service → builder）必须完整，禁止漏传
- **step 156 KEYWORD-01 业务关键词集中管理原则**：业务关键词必须集中为模块级常量，多处消费点 import 复用
- **step 157 PERSIST-01 用户可配置开关持久化原则**：用户偏好类开关必须用 `usePersistentState`，禁止裸 `useState`
- **step 158 CREDENTIAL-01 凭证多存储同步原则**：凭证在 yaml/keyring/.env 多源存储时必须显式同步，读取失败必须降级

**frontend-ui.md（8 条，step 159-166）**：
- **step 159 EFFECT-01 useEffect 副作用清理与依赖完整性规范**：useEffect 副作用必须在 cleanup 中取消，依赖数组必须完整
- **step 160 SSE-01 SSE 事件流生命周期管理规范**：EventSource 必须在 cleanup 中关闭，重连前必须关闭旧连接
- **step 161 THEME-01 AntD 主题 token 单一数据源规范**：主题 token 必须集中到单一配置文件，禁止嵌套 ConfigProvider 覆盖
- **step 162 LAYOUT-01 布局响应式与最小宽度规范**：布局宽度必须用响应式单位，禁止固定像素宽度
- **step 163 REGISTRY-01 注册表单一数据源规范**：页面注册信息必须集中到单一注册表，路由表与菜单项从注册表派生
- **step 164 FILTER-02 过滤条件与分页状态同步规范**：过滤变更必须重置页码，pagination.total 必须用过滤后长度
- **step 165 UI-SEMANTICS-01 UI 语义与行为一致性规范**：按钮文案必须与实际行为语义一致，禁止「立即」对应「排队」
- **step 166 SOURCE-01 前端数据源单一可信源规范**：同一数据必须只有一个可信源（store 或本地 state），禁止多处分别获取

**testing.md（1 条，step 167）**：
- **step 167 MOCK-01 测试 Mock 数据集中管理与字段完整性规范**：mock 数据必须集中为模块级常量，字段必须覆盖完整字段集

**browser-automation.md（3 条，step 168-170）**：
- **step 168 COOKIE-01 Cookie 完整保留与导入规范**：cookie 导入必须用 `import_full=true` 保留完整字段，维护 75+ cookie 目标
- **step 169 PARSER-01 解析器多层兜底规范**：DOM 解析器必须维护多选择器仓库（≥3 种），ID 提取必须有 3 层兜底
- **step 170 KEYWORD-01 爬虫关键词集中管理规范**：爬虫关键词必须集中到 `collector_utils.py`，多消费点 import 复用

**general-engineering.md（8 条，step 171-178）**：
- **step 171 NAMING-01 命名一致性与歧义消除规范**：命名必须大小写一致、语义明确，同一概念统一命名
- **step 172 CONTRACT-01 前后端契约对齐规范**：后端响应字段名必须与前端 types.ts 严格一致，变更时双向 grep
- **step 173 SEMANTICS-01 语义一致性规范**：状态值/事件类型语义必须与 DB 存储一致，禁止模糊匹配
- **step 174 FILTER-01 过滤逻辑精确匹配规范**：过滤单个值用 `==` 精确匹配，禁止 startswith/endswith 做前缀过滤
- **step 175 DRY-01 重复代码抽取规范**：跨 ≥2 模块复用的逻辑必须抽取到被依赖方模块顶层
- **step 176 ENCODING-01 编码一致性规范**：脚本启动必须设置 UTF-8 编码，API 调用必须显式设置 charset
- **step 177 DATACLASS-01 数据类使用规范**：领域模型用 `@dataclass(frozen=True)`，API 边界用 Pydantic model
- **step 178 STARTUP-01 启动钩子完整性规范**：关键路径外层必须用 `logger.exception()`，禁止 warning 吞掉堆栈

代码修复点：`repo_chatbot.py` 时区对齐；`api_chatbot_config.py` 私有属性大小写修正；`batch_refresh_scheduler.py` 熔断器持久化对称性；`browser_import.py` import_full=true 保留完整 cookie；`collector_utils.py` 提取 SOLD_TEXT_KEYWORDS 常量 + check_text_sold() 函数；`cookie_sync_scheduler.py` DRY 重构减少 37 行重复代码；`startup.py` 关键路径 logger.exception() + 迁移块独立 try/except。

## v4.27.0 失败原因传递链 / 数据完整性预检 / 合并写入决策 / 文案常量集中 / 修改验证闭环 / 测试 Mock 同步

基于「商品列表点击标题触发官方采集报错 502 含糊错误」问题复盘（使用 Sequential Thinking 8 步复盘法），新增 6 步编码规范（step 123-128）：

- **step 123 失败原因传递链规范**：底层操作返回 None/空时必须设置 `last_<operation>_failure_reason` 属性，中层按 reason 映射 401/429/502/503 状态码，文案与根因语义匹配，reason 值集中为模块级常量
- **step 124 数据完整性预检规范**：依赖外部状态的接口必须提供 `_check_<state>_completeness()` 方法，双阈值 AND 判断（总数 + 关键项命中），调用前预检 + 调用后二次检查，错误信息含具体缺失清单
- **step 125 合并写入 vs 覆盖写入决策规范**：用户手动注入数据用合并写（merge），系统登录成功用覆盖写（overwrite，需先验证完整），系统刷新 token 用合并写；合并写按字段名为 key 合并，相同 name 新值覆盖旧值
- **step 126 文案常量集中管理规范**：错误文案集中为模块级常量，跨模块引用必须 import 常量而非硬编码字符串，禁止用字符串子串做日志降级 marker，复杂错误响应增加 `error_code` 字段
- **step 127 修改-验证-部署闭环规范**：Edit 后立即 grep 验证关键标志符，修改错误文案后全局 grep 旧文案确保唯一来源，Python 修改后必须重启服务，git stash 前先 commit 保底
- **step 128 测试 Mock 同步规范**：修改前置条件时同步更新测试 mock，mock 数据必须覆盖完整字段集，测试失败时优先检查前置条件变更，mock 数据集中为测试模块级常量

代码修复点：`_detail.py` 7 个失败分支设置 `last_detail_failure_reason`；`collection_service.py` 按 reason 映射状态码；`cookie_store.py` 新增 `merge_cookies` 方法；`exception_handler.py` import 文案常量；测试 mock 添加 12 个 cookie 完整集。

## v4.26.0 API 三态语义 / 死字段 / 共享单例 / 类型对齐 / 错误处理 / 默认值操作符

基于「任务级配置覆盖功能开发 + 代码审查」复盘（使用 Sequential Thinking 8 步复盘法），新增 6 步编码规范（step 117-122）：

- **step 117 API 更新接口三态语义规范**：PATCH/PUT 接口必须用 `model_dump(exclude_unset=True)` 区分未传/传 null/传值三态，NOT NULL 字段传 null 时防御性 pop，配置参数在 `api_update_semantics` 节点
- **step 118 字段全链路消费规范**：新增任务级配置字段必须同时实现 DB存储→startup 读取→worker 消费 完整链路，死字段必须移除 UI 入口或添加注释
- **step 119 共享单例局部变量规范**：循环中创建任务级覆盖对象必须用局部变量 `worker_xxx`，禁止直接修改 container 单例
- **step 120 跨前后端类型对齐规范**：前端 TypeScript interface 必须与后端运行时模型字段严格对齐，部分实现时必须注释说明
- **step 121 前端错误处理规范**：API 调用的 catch 块必须用 `extractApiError` 显示具体错误信息，禁止 `message.error('保存失败')` 等无信息提示
- **step 122 默认值操作符规范**：默认值场景统一用 `??` 而非 `||`，只有需要同时过滤 0/''/false 时才用 `||`

审查技能同步落地：`xianyu-frontend-code-review` v4.25.0 → v4.26.0 新增 3 项 F-REVIEW（THREE-STATE-NULL-SEMANTICS / ERROR-HANDLING-CONSISTENCY / DEFAULT-OPERATOR-CONSISTENCY），扫描从 77→80 项；`xianyu-backend-code-review` v4.25.0 → v4.26.0 新增 3 项 B-REVIEW（EXCLUDE-UNSET-CHECK / NOT-NULL-NONE-DEFENSE / SHARED-SINGLETON-POLLUTION），扫描从 111→114 项。

代码修复点：`api_tasks.py` 改用 `exclude_unset=True` + None 防御；`startup.py` 引入 `worker_price_strategy` 局部变量 + `antidetect_config` 死字段注释；`worker.py` 激活 `eval_threshold` 任务级优先消费；`TaskEditor.tsx` 新增 `GlobalAntidetectConfigModal` + `extractApiError` + `??` 统一。

## v4.25.0 数据库迁移块独立容错与关键路径异常可见性

基于 `sqlite3.OperationalError: no such column: notifications.read_at` 问题复盘（使用 Sequential Thinking 6 步复盘法），新增 1 步编码规范（step 116）：

- **step 116 数据库迁移块独立容错与关键路径异常可见性规范**：(1) 迁移块独立容错——同一迁移函数内多个独立迁移块（C-01~C-05）必须各自独立 try/except；(2) 强依赖时允许合并；(3) 外层禁止吞掉关键路径异常——启动钩子/迁移/初始化等关键路径的外层 except 必须用 `logger.exception()` 输出完整 traceback；(4) 数据库 schema 三方对比诊断法——ORM 模型声明/迁移逻辑/实际数据库 schema（`PRAGMA table_info`）三方对比

代码修复点：`startup.py` 的 `run_migrations()` 将 C-01~C-05 改为各自独立 try/except；外层 `_on_startup` 的 except 从 `logger.warning(f"...{e}")` 升级为 `logger.exception()`。

## v4.24.0 用户偏好类 UI 状态持久化

基于「批量采集菜单相关参数开关应支持持久化」需求复盘（使用 Sequential Thinking 7 步复盘法），新增 1 步编码规范（step 115）：

- **step 115 用户偏好类 UI 状态持久化强制复用 usePersistentState 规范**：用户偏好类 UI 状态（自动刷新/视图模式/列显隐/折叠/展开/主题偏好/最近使用列表/记住上次选中项）必须使用项目既有 `frontend/src/hooks/usePersistentState.ts`，禁止裸 `useState`、禁止各组件自行实现 localStorage 读写、禁止引入第三方持久化库。规范要点：(1) 状态分类识别（用户偏好类/业务数据类/会话状态类/临时状态类/敏感数据类）；(2) 强制复用既有 hook；(3) key 命名规范 `xh.<page>.<field>`；(4) validator 必填防脏数据；(5) localStorage 不可用自动内存回退；(6) 不重复持久化后端已持久化字段

代码修复点：`Maintenance/BatchRefresh.tsx` 引入 `usePersistentState` hook，将 `useState(false)` 替换为 `usePersistentState<boolean>('xh.batchRefresh.autoRefresh', false, { validator: ... })`。

## v4.21.0 能力驱动派发 / 共享工具函数 / 静默降级预检

基于「LLM 深度分析因 vision 模型不支持 image_url 触发 400」问题复盘（使用 Sequential Thinking 4 维度复盘法），新增 3 步编码规范（step 112-114）：

- **step 112 能力驱动派发规范**（capability-driven dispatch）：任何 LLM/多模态/function_call 调用必须在构造 payload 前预检目标模型能力，校验函数必须共享（`api_ai._is_vision_capable`），关键字白名单配置化（`llm_capability_keywords` 节点）
- **step 113 共享工具函数规范**（避免散落内联判断）：跨 ≥2 模块复用的判断逻辑/常量必须抽取为"被依赖方"模块顶层的纯函数或模块级常量，导入方只能 `from <source> import <shared>`
- **step 114 静默降级预检规范**（不支持能力 → 友好降级）：可选增强能力（vision/function_call/json_mode）调用前必须预检，失败时降级为等价文本表达而非抛错，预检失败日志级别 `logger.warning`

代码修复点：`api_ai.py` 顶层新增 `_VISION_CAPABLE_KEYWORDS` 元组 + `_is_vision_capable()` 工具函数；`api_ai_deep.py` 删除内联关键字白名单，改为 `from xianyu_hunter.web.routes.api_ai import _is_vision_capable` 复用。

## v4.19.0 DOM 选择器同步 / 外部文案集中管理 / 调度器启动可见性

基于 3 个核心问题复盘（使用 Sequential Thinking 12 步复盘法），新增 3 步编码规范（step 99-101）：

- **step 99 选择器仓库同步与单一数据源规范**：同一 DOM 数据源的所有解析路径（主解析 `_find_cards` / 批量解析 `_BATCH_PARSE_SCRIPT` / 降级解析）必须引用同一选择器仓库，JS 脚本必须动态拼接选择器字符串，ID 提取必须有 3 层兜底（data-* → a[href] → /item/数字 路径）
- **step 100 外部系统文本特征集中管理规范**：外部系统（闲鱼/淘宝/第三方 API）的文本特征（已售关键词/错误码/状态文案）必须提取为模块级常量（`tuple[str, ...]`），多处消费点必须复用同一纯函数（`check_xxx(text) -> bool`）
- **step 101 关键调度器启动状态可见性规范**：关键后台调度器启动时输出 INFO + 间隔，未启动时输出 WARNING + 醒目提示 + 启动命令 + 影响范围，`/api/about` 端点必须返回调度器状态

代码修复点：`_BATCH_PARSE_SCRIPT` 选择器从 2 种扩展到 6 种 + 3 层 ID 提取兜底；新增 `SOLD_TEXT_KEYWORDS` 常量 + `check_text_sold()` 函数到 `collector_utils.py`（3 处复用）；调度器未启动时输出 WARNING 提示。

## v4.18.0 元数据单源管理与跨端显示对齐

基于「版本管理菜单持续显示 V10」问题复盘（使用 Sequential Thinking 6 步复盘法），新增 1 步编码规范（step 98）：

- **step 98 元数据单源管理与跨端显示对齐规范**：构建期元数据（版本号/构建时间/git_sha）必须指定唯一源头（`__init__.py` 的 `__version__`），多端点读取同一元数据必须封装 `_safe_xxx()` 辅助函数（三层 try/except 回退到 `'unknown'`），生产代码禁止占位符字面量，前端显示元数据必须调用语义对齐的 API（`/api/about` 而非 `/api/config/version`），跨端数据流问题必须前后端协同修复，修复时同步清理死代码

代码修复点：前端 `VersionManager.tsx` 改用 `aboutApi.get()` + `Promise.all` 并行化；后端 `api_config.py` 新增 `_safe_app_version()` 辅助函数替换 `"version": "1.0"` 占位符；清理 `Dashboard/index.tsx` 中只 set 不 read 的 `configVersion` 死代码。

## v4.16.0 Cookie 层状态管理 + 代码变更逻辑审查

基于「功能正常但状态显示失效」问题（用户反馈：实时查询、官方采集等功能均能正常运行，但 identity、session、tracking 状态持续显示失效）+ 代码变更逻辑审查（发现 2 个 Critical / 3 个 Suggestion / 2 个 Nit）复盘（使用 Sequential Thinking 4 维度复盘法），新增 3 步编码规范（step 91-93）：

- **step 91 缓存失效传播规范**：任何持久化层变更后必须显式调用 `invalidate_cache()`，TTL 兜底不替代主动失效，跨进程变更必须主动通知主进程
- **step 92 状态判定需区分"未检测"与"已检测未失效"规范**：任何"功能信号"字段不能仅用布尔初始值代表"未检测"，必须配合"已发生过检测"标记（时间戳/计数器/标志位），强制恢复需白名单
- **step 93 SQLite DDL 修改列约束必须用表重建 + 事务安全规范**：SQLite 不支持 ALTER COLUMN，必须用 `engine.begin()` 单事务 + 残留清理 + 数据复制 + 异常恢复模式

代码修复点：`_migrate_make_column_nullable` 事务原子性（Critical #1）、collector 误判前置条件（Critical #2）、`sync_state_from_cookies` 死代码 + 顺序依赖（Suggestion #1）、`force_restore_layers` 时间戳（Suggestion #2）、else 死代码 + list 转 set（Nits）。详细复盘文档参见 [cookie-state-recovery-patterns.md](cookie-state-recovery-patterns.md)。

## v4.15.0 登录流程性能优化 / Cookie 层同步测试修复 / 代码变更逻辑审查

基于 4 个问题复盘（使用 Sequential Thinking 4 维度复盘法），新增 5 步编码规范（step 86-90）：

- **step 86 浏览器自动化资源拦截粒度规范**：拦截前必须检查页面是否依赖图片渲染关键内容（二维码图片），禁止盲目拦截 image/font/media
- **step 87 Cookie 层依赖关系信号匹配规范**：层恢复信号必须与层范围匹配（SESSION 层信号不能恢复 IDENTITY 层），信号只能恢复其所属层及以下层
- **step 88 DEBUG 代码清理规范**：临时 DEBUG 代码在问题修复后必须移除，禁止留在生产代码中
- **step 89 子进程创建标志规范**：WebView2/Playwright GUI 子进程必须用 CREATE_NEW_CONSOLE
- **step 90 配置驱动原则强化**：所有新增规范必须配置驱动，新增检查点必须包含适用/不适用场景说明

## v4.14.0 评估明细过滤 / 分页 / 空状态 / 派生正交

基于「评估明细页面优化」工作复盘（使用 Sequential Thinking 5 步系统分析），新增 4 步编码规范（step 82-85）：

- **step 82 前端过滤与后端分类一致性验证**：实现前端过滤前必须先 grep 后端 `insufficient_count`/`marginals`/`result` 确认分类互斥性，前端过滤条件必须与后端对齐
- **step 83 过滤+分页适配流程**：添加 filterStatus 状态后必须同步调整 pagination 的 total/current/pageSize 三参数
- **step 84 空状态边界条件处理规范**：空状态判断必须用 `filteredItems.length` 而非原始 `items.length`，区分「无数据」与「过滤后无匹配」两种文案
- **step 85 系统行为派生与用户配置正交原则**：系统行为（如折叠态列宽自适应）通过 `useMemo` 派生，不修改通用 hook 的用户配置

所有新规范强调配置驱动（参数在 `config.yaml` 的 `filter_backend_align` / `filter_pagination_adapt` / `filter_empty_state` / `derive_orthogonal` 节点管理）与适用/不适用场景说明。前端对应审查规范为 `xianyu-frontend-code-review` v4.14.0 的 F-REVIEW-FILTER-BACKEND-ALIGN / F-REVIEW-FILTER-PAGINATION-ADAPT / F-REVIEW-FILTER-EMPTY-STATE，后端对应规范为 `xianyu-backend-code-review` v4.13.0 的 B-REVIEW-STATS-EXCLUSIVE。
