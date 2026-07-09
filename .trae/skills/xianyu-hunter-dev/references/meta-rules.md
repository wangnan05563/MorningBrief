# 元规范（Meta-Rules）

> 本文件抽象 xianyu-hunter-dev skill 128 步编码规范中重复出现的通用要求。
> 各 step 只需写"特有规则"，元规范自动适用，避免重复。
> 主索引见 [SKILL.md](../SKILL.md)。

## 1. 配置驱动原则

所有 step 涉及的参数（阈值/超时/列表/映射表/命名规则）必须在 `config.yaml` 对应节点管理，**禁止**硬编码在代码或技能中。

**适用范围**：
- 数值型配置项（间隔时间/超时/重试次数/并发数/阈值）
- 字符串枚举值（状态码映射/错误文案模板）
- 列表/映射表（关键词白名单/选择器候选/字段对齐表）
- 命名规则（key 前缀/常量后缀/变量前缀）

**配置节点命名规范**：
- 节点名 `snake_case`
- 层级结构清晰，避免扁平化命名冲突
- 每个节点含 `enabled` 开关 + 详细参数字段

**例外**：
- 语言/框架级常量（如 HTTP 200、`path: "/"`）
- 协议固定值（不可配置）
- 安全必需的固定值（如 `hmac.compare_digest`）

## 2. 适用/不适用场景说明

每条编码规范必须明确说明**适用场景**与**不适用场景**，确保通用性，避免审查时误用于不适用场景。

**判断信号**：新增规范时必须自问"这个规范在什么场景下不适用？"，若无法回答则规范过于宽泛需细化。

**典型适用/不适用区分**：
- **适用**：业务模块、跨层调用、外部依赖、有状态生命周期
- **不适用**：纯函数、一次性脚本、内部信任数据、性能敏感 hot path

## 3. 历史教训归档

所有 step 的"历史教训"段落（含用户反馈/根因/修复过程）统一归档到：
- [version-history.md](version-history.md)（按版本组织）
- [cookie-state-recovery-patterns.md](cookie-state-recovery-patterns.md)（Cookie 层专题）
- 各 step 文件内的"历史教训"小节（保留简短引用）

**原则**：教训用于理解"为什么有这条规范"，不重复叙述完整排查过程。

## 4. 修复模式代码归档

完整的修复模式代码示例归档到对应主题文件（`coding-rules/<topic>.md`），step 内只保留：
- 核心规则一句话
- 判断信号（grep 关键词）
- 配置节点名
- 适用/不适用场景

**原则**：代码示例用于理解规范如何落地，不重复贴完整函数。

## 5. 判断信号优先 grep

所有判断信号必须可用 `grep` 验证，禁止用"语义判断"等模糊描述。

**判断信号格式**：
- `grep "<pattern>" <path>` 出现 → 视为违规/可疑
- `grep` 多个调用点 → 触发抽取建议
- 代码含 `<pattern>` → 必须检查

**禁止**：
- "代码风格不好"（无法 grep）
- "逻辑复杂"（无法 grep）
- "可能有问题"（无明确信号）

## 6. 复用优先级

新增功能/工具函数/帮助类时必须按以下优先级复用：

1. **项目内 helper**（如 `_utcnow`/`_escape_like`/`hmac.compare_digest`/`asyncio.wait_for`/`logger.warning`）
2. **标准库**（如 `contextlib.suppress`/`asyncio.gather`/`pathlib.Path`）
3. **第三方库**（如 `loguru`/`pydantic`/`SQLAlchemy`）
4. **新实现**（最后选择）

**判断信号**：新增函数 + `grep` 发现已有相似命名/相似参数/相似功能 → 必须复用而非重复实现。

**禁止**：跨 ≥2 文件出现相同的关键字/正则/常量字面量而未抽取共享（参考 step 113）。

## 7. 状态分类识别

新增任何状态字段前必须识别归属类别，选择对应持久化策略：

| 状态类别 | 持久化策略 | 典型示例 |
|---|---|---|
| 用户偏好类 | `usePersistentState`（localStorage） | 自动刷新/视图模式/列显隐/折叠/展开 |
| 业务数据类 | 后端 API + DB | 任务列表/订单状态/配置项 |
| 会话状态类 | Zustand store | 登录态/当前选中项/跨页共享 |
| 临时状态类 | `useState` | loading/modal open/submitting/表单 dirty |
| 敏感数据类 | secure storage / httpOnly cookie | token/密码/API key |

**判断信号**：新增 React state 时自问"刷新页面后状态应保留还是重置？"——保留则用户偏好类，重置则临时状态类。

## 8. 错误粒度区分

HTTP 状态码必须按语义精细化区分（参考 step 71/123）：

| 状态码 | 语义 | 前端动作 |
|---|---|---|
| 401 | 未登录 | 跳转登录页 |
| 403 | 权限不足 | 显示权限不足提示 |
| 440 | Cookie 过期 | 跳转重新登录 |
| 441 | Token 过期 | 刷新 Token |
| 429 | 反爬触发 | 提示手动验证 |
| 502 | 浏览器异常 | 提示重启服务 |
| 503 | 服务未启动 | 提示启动服务 |
| 504 | 网关超时 | 提示稍后重试 |

**禁止**：所有认证失败都映射为 `401` 导致前端无法区分"未登录"与"登录态过期"。

## 9. 日志级别规范

| 级别 | 适用场景 |
|---|---|
| `logger.error` | 需人工介入的失败（主流程失败/数据丢失/安全事件） |
| `logger.warning` | 可恢复异常/降级/重试（辅助功能失败/配置项缺失/可选资源不可用） |
| `logger.info` | 业务关键路径（触发抢单/采集完成/推送发送/调度器启动） |
| `logger.debug` | 调试信息（默认 INFO 级别不输出，仅开发环境可见） |
| `logger.exception` | 关键路径（启动钩子/迁移/初始化）外层 except 必须用，保留完整 traceback |

**禁止**：
- 辅助功能失败用 `logger.debug`（默认不输出，难以排查）
- 辅助功能失败用 `logger.error`（过度严重，污染告警）
- 关键路径外层 except 用 `logger.warning(f"...{e}")`（丢失堆栈）

## 10. 异步操作规范

所有 `await` 调用外部资源的异步操作必须满足：

1. **整体超时保护**：`asyncio.wait_for(coro, timeout=N)` 包裹，超时返回语义化状态码（504）
2. **超时时间从配置读取**：禁止硬编码，参考 `config.yaml` 的 `async_timeout` 节点
3. **CancelledError 传播**：用 `contextlib.suppress(asyncio.CancelledError)` 包裹并向上传播，禁止 `except: pass`
4. **Task 引用保留**：`self._task = asyncio.create_task(...)` 防止 GC，禁止裸 `asyncio.create_task(...)`
5. **取消+收集模式**：`task.cancel()` + `await asyncio.gather(task, return_exceptions=True)`

## 11. 安全调用检查

所有外部接口调用必须满足：

1. **空值/边界判断**：调用前校验参数非空、范围合法
2. **异常分支处理**：禁止 `except: pass` 静默吞异常
3. **敏感数据脱敏**：`_SENSITIVE_HEADERS` 过滤 authorization/cookie/xh_token/set-cookie
4. **权限校验**：`BearerAuthMiddleware` 白名单检查
5. **SQL 注入防护**：LIKE 用 `_escape_like`，表名/列名用 `_IDENT_RE` 白名单
6. **路径遍历防护**：用户输入用 `_USER_ID_RE` 等正则校验
7. **token 比较**：`hmac.compare_digest` 防时序攻击
8. **外部链接安全**：`target="_blank"` 配 `rel="noopener noreferrer"`

## 12. 状态机设计规范

含「状态」字段且状态会变化的业务对象必须满足：

1. **枚举穷举**：列出所有状态值
2. **转换白名单**：用 `(起始状态 → 目标状态)` 白名单校验，禁止黑名单
3. **终态不可复活**：`failed`/`succeeded`/`cancelled` 禁止再转换，状态变更接口前置校验
4. **中间态超时清理**：独立 APScheduler 定时扫描 + 一次 SQL 批量更新
5. **前后端枚举值统一**：禁止 snake_case ↔ camelCase 映射转换

## 13. 测试隔离规范

1. **生产路径 patch**：fixture 必须用 `tmp_path` 隔离生产路径，禁止直接读写生产文件
2. **测试数据可识别**：带 `test_fixture_` 前缀/`__test__` 后缀
3. **patch 验证**：fixture 加载后 `assert not os.path.exists(production_path)` 验证
4. **遍历 sys.modules**：禁止硬编码模块名列表，必须遍历 `sys.modules` 找所有持目标属性的模块
5. **importlib.import_module**：禁止 `__import__`（返回顶层包而非子模块）
6. **数据污染应急 5 步**：停止服务 → 删除污染文件 → 修复 conftest → 重跑测试 → 通知用户

## 14. Python 现代化规范

Python 3.10+ 项目必须：

1. **asyncio.create_task** 替代 `asyncio.get_event_loop().create_task`
2. **asyncio.get_running_loop** 替代 `asyncio.get_event_loop`（在协程内）
3. **dataclass 字段显式声明**，禁止 `getattr(obj, 'field', default)` 兜底
4. **模块级 import**，禁止函数内重复 import（除非解决循环依赖）
5. **CancelledError 传播**，用 `contextlib.suppress` 包裹
6. **类型注解现代语法**：`X | None` 替代 `Optional[X]`，`list[T]` 替代 `List[T]`

## 15. 前端三态反馈规范

所有用户主动触发的异步操作必须实现 **loading → success → error** 三态：

1. `message.loading` 返回 `hide` 函数，在 `then` 和 `catch` 分支都调用 `hide()`
2. 错误提示从 `err.response.data.detail` 提取后端返回的具体错误
3. loading 文案包含资源标识（如 ID 前 8 位）
4. 操作成功后触发数据刷新（`refresh()` / `refetch()`）
5. 禁止 `.catch(() => {})` 静默吞错误

## 16. 配置全链路生效验证

配置项从定义到消费必须全链路追踪：

1. `config.yaml` 新增字段
2. Config 类有字段
3. TaskConfig 注入
4. Worker/Module/方法参数中读取 `self.config.xxx`
5. 最终消费点（URL 构建/SQL 查询/阈值比较）有读取代码

**验证方法**：`grep` 每个配置项的字段名，确认从定义到最终消费点都有读取代码。

**禁止**：只注入到中间层就认为生效。

## 17. 修改-验证-部署闭环

1. Edit 后立即 `grep` 验证关键标志符存在
2. 修改错误文案后全局 `grep` 旧文案确保唯一来源
3. Python 修改后必须重启服务（禁止认为"修改即生效"）
4. 重启后验证端口监听 + 关键数据状态
5. `git stash` 前先 `git commit -m "WIP"` 保底

## 18. 跨前后端协同修复

跨端数据流问题必须前后端协同修复：

1. 检查前端调用 → 后端端点 → 数据源全链路
2. 禁止只改一边
3. 同步检查相关端点是否也有相同问题
4. 修复时同步清理死代码（只 set 不 read 的 state / 只 import 不调用的函数）

## 19. 死代码检测与清理

每次大版本（v4.x → v4.x+1）时主动检测：

1. `git log -p --all -S "<function_name>"` 查看历史变更
2. `grep -rn "<function_name>" src/ tests/` 确认无调用方
3. 在 PR/Commit 描述中标注"删除死代码 X"

**修复模式**：
- 找到调用方：恢复调用路径
- 改写为入口函数：将死代码改写为"统一同步入口"
- 直接删除：无任何依赖时

## 20. 失败诊断 dump 机制

关键选择器/数据提取失败时：

1. 自动 dump `page.content()` 到 `logs/<场景>_<id>_<timestamp>.html`
2. `logger.warning` 记录 dump 路径
3. dump 用 `try/except` 包裹不阻塞主流程
4. dump 是「事后取证」不是「在线恢复」
5. 禁止依赖 dump 结果做运行时决策
6. 禁止 dump 敏感数据（cookie/auth header）

---

# 工作流元规范（Workflow Meta-Rules，21-24）

> 以下 4 条元规范从「四维度复盘方法论」提炼，定义了 4 类高频工作流的通用判断逻辑。详细配置节点与适用/不适用场景见 [`docs/standards/四维度复盘方法论与历史教训集成.md`](../../../../docs/standards/四维度复盘方法论与历史教训集成.md)。
>
> 命名空间与配置驱动：所有参数（critical_path_patterns / failure_threshold / resource_holder_patterns / single_source_of_truth）均在 `config.yaml` 对应节点管理，禁止硬编码。

## 21. 错误处理决策树（适用于所有 try/except / .catch）

捕获异常后按三问决策：

1. **是否为启动/迁移/关键路径？**（函数名匹配 `config.yaml` 的 `error_handling_decision_tree.critical_path_patterns`）
   - 是 → `logger.exception()` 输出完整 traceback + 阻断启动
   - 否 → 进入问 2
2. **是否需要向用户展示？**
   - 是 → `reason_code`（与后端 `failure_reason_propagation.reason_enum` 对齐）+ `user_message` + 内部 `detail` 三层
   - 否 → `logger.warning` + 计数累计
3. **是否需要重试？**
   - 是 → 指数退避（`retry_strategy: exponential_backoff`）+ 熔断 + 持久化重试状态
   - 否 → 直接记录 + 上报

**关键约束**：
- 关键路径外层 except 禁止 `logger.warning(f"...{e}")`（丢失堆栈）
- 多个独立 try/except 块**禁止**外层统一 try/except 吞异常（强依赖场景允许合并但需注释说明）

**判断信号**：`grep "except" <file>` 关键路径缺 `logger.exception()` 即视为违规。

**适用**：启动钩子、迁移函数、初始化函数、API 路由 try/except、前端 `.catch`。
**不适用**：性能 hot path（用结构化异常）/ 测试代码（`pytest.raises` 期望异常）。

**历史教训**：`run_migrations()` 用外层 `try/except Exception as e: logger.warning(f"迁移失败: {e}")` → 后续迁移块全部跳过 → 启动时缺列触发 `OperationalError`。修复：每个迁移块独立 try/except + 关键路径用 `logger.exception()`。

## 22. 批处理熔断模板（适用于长任务断点续传）

长任务（>30 秒）+ 多步进度 + 需要断点续传的场景必须遵循：

**状态机**：`running → paused（可恢复）→ running（续传）` / `running → stopped（用户主动）/ failed（异常）/ completed（成功）`（后三个为终态）

**强制约束**：
1. **每完成一项就 `save_progress()`**（**关键**：熔断时漏持久化是历史高频 bug）
2. **熔断时**：剩余项标记 `pending`（配置项 `mark_remaining_as`），保存当前 `cursor` / `completed_ids` / `remaining_ids`（`persist_keys`）
3. **续传**：从持久化的 `cursor` 恢复，跳过已完成项
4. **日志区分**：使用 `config.yaml` 的 `log_phrasing.paused` / `stopped` / `failed` 三套文案，避免"暂停"与 `break` 混用导致语义不一致

**关键约束**：
- `failure_threshold`（默认 3）触发熔断后**必须**调用 `save_progress()`，禁止 `break` 后无持久化
- 剩余项处理策略从 `mark_remaining_as` 读取（`pending` / `skipped`），禁止硬编码

**判断信号**：
- `grep "consecutive failure" <file>` 但代码无 `save_progress()` 调用 → 视为违规
- `break` 与 `paused` 混用 → 视为违规
- 日志文案"暂停"但实际 `break` 跳出循环 → 视为违规（语义不一致）

**适用**：批量采集、批量导入、批量上报、长任务、用户主动取消（走 stopped 分支）。
**不适用**：实时单次请求、幂等的小批量（≤3 个）操作、性能 hot path。

**历史教训**：`batch_refresh_scheduler.py` 的 BatchRefresh#95 连续失败 3 次后用 `break` 跳出循环并标记剩余商品为 `skipped`，但**没有调用 `_save_progress()`** 持久化剩余项。导致"断点续传失效 + 剩余项被永久跳过"双重问题。修复后：熔断分支调用 `_save_progress()` + 修正日志措辞为"批次熔断暂停（可恢复）"。

## 23. 资源生命周期管理（适用于浏览器/订阅/连接）

可注册组件（Playwright Page/Browser、EventSource/SSE、WebSocket、Proxy/Observer、asyncio.Task）必须满足：

1. **持有**：实例属性 / ref，命名以 `_` 开头（`self._page`、`this._proxy`、`_task`）
2. **清理**：在 `stop()` / `useEffect cleanup` / `onUnmounted` 中调用 `close()` / `dispose()` / `cancel()`
3. **检测**：硬约束禁止 `const x = new Proxy()` 局部变量（被 GC 回收导致代理失效）
4. **监控**：建立资源使用计数 dashboard（`lifecycle_audit_interval_seconds`）

**关键约束**：
- `asyncio.create_task(coro)` **必须**赋值给实例属性（`self._task = asyncio.create_task(...)`），禁止裸 `create_task`（GC 风险）
- 长连接组件必须有 cleanup hook（`useEffect(() => { ...; return () => es.close() }, [])`）
- `forbid_local_var_creation` 列表中的资源类型禁止局部变量持有

**判断信号**：
- `grep "(const|let)\\s+\\w+\\s*=\\s*new (Proxy|MutationObserver|IntersectionObserver|ResizeObserver)" <file>` → 视为违规
- `asyncio.create_task(coro)` 未赋值给实例属性 → 视为违规
- 长连接组件无 cleanup → 视为违规

**适用**：浏览器自动化（Playwright/Selenium）、SSE/WebSocket 连接、EventSource、Proxy/Observer 订阅、长生命周期 Timer。
**不适用**：短生命周期的局部计算（一次性数组 map）/ 一次性 useEffect（无需 cleanup）/ 测试 mock 资源。

**历史教训**：前端反爬模块 `const observer = new MutationObserver(...)` 后未保存到实例属性，被 GC 回收后 DOM 变化不再触发回调，表面上"代码正常执行"但实际"功能失效"，难以察觉。

## 24. 跨组件/跨源状态同步（适用于多源/多链路场景）

> v4.29 扩展：原 #24 仅覆盖前端跨组件同步，现扩展为「前端跨组件 + 后端跨源」双场景，新增「后端内部双源同步」约束。

复杂前端应用（多组件共享同一份数据）+ 多 Tab / 多路由 + 配置变更实时生效的场景，以及后端内部存在多个数据源（YAML/keyring/EventRow/业务表/缓存）的场景必须满足：

### 24-A 前端跨组件同步

1. **单一可信源**：后端 `GET /api/xxx` 是前端唯一数据源，**禁止**前端 `usePersistentState` 重复持久化
2. **统一入口**：所有写入路径必须通过 `useXxxStore().setXxx(newData)` 集中入口，**禁止**各组件独立 `setState`
3. **统一 refetch**：API 调用后必须 `refetch()` 而非推断新状态（避免乐观更新与后端实际不一致）
4. **跨进程同步**：子进程状态变更必须 SSE 推送，**禁止**前端用 TTL 缓存兜底

### 24-B 后端内部跨源同步 🆕v4.29

后端内部存在多个数据源（YAML/keyring/EventRow/业务表/缓存/浏览器内存）时必须满足：

1. **源识别**：新增状态字段时必须识别归属类别并登记到 `config.yaml#state_sync.backend_internal_sources` 源对清单：
   | 源对 | 典型场景 | 同步方向 |
   |---|---|---|
   | YAML ↔ keyring | 凭据（DingTalk/ServerChan/Bark token） | YAML 启动时同步到 keyring |
   | EventRow ↔ 业务表 | KPI 统计（抢单成功率/推送失败率） | 业务表为可信源，EventRow 仅作聚合 |
   | 健康检查 ↔ Worker 实测 | Cookie 层状态 | Worker 实测优先，健康检查兜底 |
   | Cookie JSON ↔ 浏览器内存 | Cookie 层级管理 | 浏览器内存兜底回填 JSON |
   | 配置缓存 ↔ 原始配置 | AppConfig 单例 | 原始配置变更后必须 invalidate 缓存 |

2. **同步时机**：
   - **启动时同步**：`_on_startup` 中调用 `_sync_xxx()`（如 `_sync_yaml_credentials_to_keyring`）
   - **写入时同步**：业务表写入后同步写 EventRow（如 NotifierHub 推送后写 `type='notify'` 事件）
   - **失效时同步**：Worker 检测到失效（如 RGV587_ERROR）必须调用 `invalidate_layer` 同步到健康检查
   - **读取时兜底**：JSON 缺失时从浏览器内存兜底回填（如 `CookieStore.upsert_cookie_values`）

3. **同步方向约束**：
   - 业务表 → EventRow 单向（EventRow 不得反向写业务表）
   - 原始配置 → 配置缓存单向（缓存不得反向写原始配置）
   - 浏览器内存 → JSON 单向回填（JSON 不得反向写浏览器内存）
   - YAML → keyring 启动时单向（keyring 不得反向写 YAML）

4. **禁止**：
   - 多个源独立读写无同步机制（如 YAML 凭据写后 keyring 未同步，导致通知"凭据未找到"被静默跳过）
   - 健康检查与 Worker 实测使用不同判定标准（如健康检查看 cookie 存在，Worker 看 RGV587_ERROR）
   - EventRow 写入 `type='eval.passed'` 但业务表只查 `type='eval.scored'`，导致 KPI 统计 0

**关键约束**：
- 后端 `single_source_of_truth` 列表中的 API 返回值是前端唯一可信源
- `forbid_persistent_state_for` 列表中的字段禁止前端 `usePersistentState` 重复持久化
- 跨进程状态变更（`sse_push_required_for`）必须 SSE 推送，`ttl_grace_seconds: 0` 即禁止 TTL 兜底
- 后端 `backend_internal_sources` 列表中的源对必须有显式同步代码（启动/写入/失效/读取任一时机）

**判断信号**：
- 前端：`grep "usePersistentState" <file>` 但该字段在后端有 `GET /api/xxx` → 视为违规
- 前端：多个组件独立 `useEffect(() => fetch(...), [])` 拉取同一份数据 → 视为违规
- 前端：`setTimeout(refresh, 30000)` 作为跨进程状态同步方案 → 视为违规
- 后端：`grep "keyring" <file>` 与 `grep "yaml" <file>` 同一凭据出现两处但无 `_sync_` 函数 → 视为违规
- 后端：`grep "EventRow" <file>` 写入但业务表查询条件不匹配 → 视为违规
- 后端：健康检查函数与 Worker 函数对同一状态使用不同判定逻辑 → 视为违规
- 后端：`grep "json.load" <file>` 与 `grep "browser.cookies" <file>` 同一 cookie 出现两处但无回填代码 → 视为违规

**适用**：
- 前端：复杂前端应用（多组件共享同一份数据）/ 多 Tab / 多路由场景 / 配置变更实时生效
- 后端：YAML/keyring/EventRow/业务表/缓存/浏览器内存等多源场景

**不适用**：
- 前端：简单组件树（1-2 层 props drilling 即可）/ 服务端渲染场景 / 纯 UI 偏好（主题色、视图模式）→ 纯 UI 偏好应用 `usePersistentState`（参考 meta-rule #7）
- 后端：单一数据源（如纯 DB 查询无缓存）/ 一次性脚本 / 性能 hot path（同步开销不可接受）

**历史教训**：
- 前端：用户反馈"功能正常但状态显示失效"（30 秒才恢复），根因：子进程登录后只更新自己的内存缓存，主进程读时取到 TTL 内的旧"失效"状态，前端 `LayerStatusBadge` 仅依据 `valid: boolean` 显示（无"未检测"区分），三层叠加导致用户体感"明明能跑却一直报错"
- 后端：DingTalk 通知不发送，根因：YAML 中保存了 webhook 凭据但 `secrets.py` 的 KEY 常量名与 YAML 字段名不一致，启动时未调用 `_sync_yaml_credentials_to_keyring()`，keyring 中无凭据导致 DingTalk 渠道被静默跳过
- 后端：抢单成功率/推送失败率恒为 0%，根因：`business_kpi.py` 查询 `EventRow` 用 `type='paid'/'confirmed'`，但 NotifierHub 实际写入 `type='notify'`，且 NotifierHub 未写 EventRow；多源不一致导致 KPI 统计分母为 0
- 后端：健康检查显示 cookie 未过期但 Worker 报 RGV587_ERROR，根因：健康检查看 cookie 存在 + identity 层 validity，Worker 看 API 实际响应 RGV587_ERROR，两套判定标准未同步

---

# 数据契约与时序元规范（25-30）🆕v4.30.0

> 以下 6 条元规范从 2026-06 至 2026-07 期间修复的批量任务断路器/启动钩子/日期时间/多源同步/错误传递/关键字管理 6 类问题中提炼，定义为「数据契约与时序」维度的通用判断逻辑。
>
> 命名空间与配置驱动：所有阈值（`fail_pause_threshold`/`critical_path_patterns`/`timezone_strategy`/`pending_marker_dir`/`error_code_enum`/`business_keyword_set`）均在 `config.yaml` 对应节点管理，禁止硬编码。

## 25. 批量处理四要素（断路器 + 进度持久化 + 续传 + 日志对称）

> 与 #22 批处理熔断模板的区别：本条聚焦**熔断时刻的强约束四要素**，#22 侧重状态机整体；本条是 #22 的「熔断分支」专项检查。

批量处理（>30 秒 / 涉及多个 item / 需断点续传）触发熔断时必须满足四要素：

1. **失败计数**：`failure_threshold`（默认 3，连续失败）+ `failure_window_sec`（默认 3600，滑动窗口）双条件
2. **进度持久化**：熔断分支**必须**调用 `save_progress()`（cursor/completed_ids/remaining_ids 三键齐全），与「用户主动停止」分支对称
3. **续传入口**：从持久化 cursor 恢复，启动时检查 `pending_marker_dir`（默认 `data/markers/`）决定是否触发续传
4. **日志对称**：使用 `config.yaml#batch_circuit_breaker.log_phrasing` 区分 `paused` / `stopped` / `failed` 三套文案，禁止"暂停"与 `break` 混用

**关键约束**：
- 熔断分支未调用 `save_progress()` → 视为**必修 P0 缺陷**（断点续传失效 + 剩余项被永久跳过）
- `log_phrasing` 文案与实际动作必须一致（如"批次熔断暂停（可恢复）"对应 `break + save_progress`，不是 `return`）

**判断信号**：
- `grep "consecutive failure\|consecutive_failures" <file>` 出现但同函数内无 `save_progress()` → 视为违规
- `grep "break" <file>` 后紧跟 `mark.*skipped` 但无 `save_progress` → 视为违规
- `grep "paused" <file>` 但实际 `return`/`break` 跳出循环 → 视为日志语义不一致

**适用**：批量采集（`batch_refresh_scheduler`）、批量导入、批量上报、长任务重试。
**不适用**：单次 API 调用、≤3 个 item 的小批量操作、性能 hot path（持久化开销不可接受）、用户主动停止（走 stopped 分支，无须 save_progress）。

**历史教训**：`batch_refresh_scheduler.py` 的 BatchRefresh#95 连续失败 3 次后 `break` 跳出循环，将剩余商品标记为 `skipped`，但**未调用 `_save_progress()`**。结果：(1) 下次启动无法加载 `remaining_ids` 触发续传；(2) 剩余 10170xxxxx 等 6 个商品被永久跳过且日志无任何持久化记录。两缺陷叠加导致「看似批次结束，实际数据未处理」。

## 26. 关键路径异常保留完整 traceback

> 与 #21 错误处理决策树的关系：#21 给出「是否 critical path → logger.exception」的判断逻辑，本条是 critical path 内的**硬约束细化**。

`config.yaml#error_handling.critical_path_patterns` 列表中的函数（即「关键路径」：`_on_startup` / `run_migrations` / `_init_*` / `_on_close`）外层 except **必须**满足：

1. **使用 `logger.exception()`**：保留完整 traceback（含调用链、异常类型、文件行号）
2. **禁止 `logger.warning(f"...{e}")`**：仅打印异常对象会丢失 Python 堆栈、局部变量、上下文信息
3. **禁止 `logger.error(f"...{e}")`**：同上，error 级别还会触发告警噪音
4. **多个独立 try/except 块**禁止外层统一 try/except 吞掉后续块（强依赖场景如「表重建+数据回填」允许合并但需注释说明合并原因）
5. **降级不静默**：即使 catch 后继续启动，也必须 `logger.exception` 记录，启动后通过 `pending_marker` 提醒用户

**关键约束**：
- `grep "except Exception" <file>` 关键路径缺 `logger.exception()` → 视为违规
- `grep "logger.warning.*f\".*{e}\"\|logger.error.*f\".*{e}\"" <file>` 在关键路径 → 视为违规

**判断信号**：
- 函数名匹配 `critical_path_patterns`（如 `*_on_startup`/`run_migrations`/`_init_*`）→ 强制检查其外层 except
- 关键路径 try 块中含 `await` / `cursor.execute` / `INSERT` 等 IO 操作 → 视为高风险

**适用**：`_on_startup` / `run_migrations` / `_init_db` / `_init_session_manager` / `_on_close` / `_shutdown` / `_register_signal_handlers`。
**不适用**：常规业务函数（用 `logger.error(f"...{e}")` 即可）、测试代码（`pytest.raises` 期望异常）、性能 hot path（结构化异常）。

**历史教训**：`run_migrations()` 用外层 `try/except Exception as e: logger.warning(f"迁移失败: {e}")` → 后续 5 个迁移块 C-01~C-05 全部跳过（异常被吞）→ 启动时表缺列触发 `OperationalError: no such column`。修复：每个迁移块独立 try/except + 关键路径用 `logger.exception()` 输出完整 traceback，问题定位时间从 2 小时缩短到 5 分钟。

## 27. datetime 统一时区策略（naive ↔ aware 混用防护）

> 与 #23 资源生命周期的区别：#23 关注「资源实例」的 GC 与 cleanup，本条关注「时间值」的时区属性对齐。

涉及跨时区/跨进程/跨服务的 `datetime` 算术与序列化必须满足三规则：

1. **存储一律 UTC**：`datetime.now(timezone.utc)` 或 `datetime.utcnow()`，禁止使用本地时区存储
2. **算术前显式 unify tzinfo**：
   - 与 `row.created_at`（DB 读出的 naive）相减 → `_utcnow().replace(tzinfo=None) - row.created_at`
   - 与前端传来的 ISO 字符串 → `datetime.fromisoformat(iso_str).astimezone(timezone.utc)`
3. **序列化时显式标注**：`to_iso_string(aware_dt)` 输出带时区的 ISO 8601；禁止 `aware_dt.isoformat()[:19]` 切片丢失时区
4. **前端渲染契约**（与 F-REVIEW-DATETIME-RENDER-CONTRACT 对应）：前端用 `new Date(isoStr).toLocaleString()` 解析，禁止字符串方法拼接

**关键约束**：
- `grep "\.replace(tzinfo=None)" <file>` 必须配合 `_utcnow()` 或 `datetime.now(timezone.utc)` 出现 → 视为合规
- `grep "datetime.now()" <file>` 无 `tzinfo` 参数 → 视为违规（应用 `datetime.now(timezone.utc)`）
- DB 列定义禁止 `TIMESTAMP WITH TIME ZONE` 与 `TIMESTAMP WITHOUT TIME ZONE` 混用（SQLite 默认无时区，但 ORM 读写约定须统一）

**判断信号**：
- `grep "datetime.now()" <file>` 无 `tzinfo` → 视为违规
- `grep "datetime.utcnow()" <file>` → 视为**反模式**（Python 3.12+ 弃用，应用 `datetime.now(timezone.utc)`）
- `grep "\.isoformat()\[:19\]\|isoformat().*replace.*T.*Z" <file>` → 视为序列化不规范

**适用**：所有 `created_at` / `updated_at` / `expires_at` / `lastCheckedAt` / `lastRunAt` 字段的算术运算、跨服务时间比较、ISO 序列化。
**不适用**：纯展示（前端用 `dayjs` 解析）、同函数内的 local variable 计算、纯日期不含时间（`date.today()`）。

**历史教训**：`repo_chatbot.py:478` 报 `TypeError: can't subtract offset-naive and offset-aware datetimes`：`datetime.utcnow() - row.created_at`，其中 `row.created_at` 是 SQLAlchemy 从 SQLite 读出的 naive datetime。修复：用 `_utcnow().replace(tzinfo=None) - row.created_at` 统一为 naive。同一问题在 `api_orders.py:57` 复现，确认是项目级模式问题。

## 28. 跨进程/跨组件状态同步六步法

> 与 #24 跨组件/跨源状态同步的区别：#24 聚焦「多源读写一致性」（如 YAML ↔ keyring），本条聚焦**写入端 + 同步调度器 + 读取端 + 启动检查**四方的全链路协作。

`config.yaml#state_sync.backend_internal_sources` 或 `frontend_pending_markers` 列表中的状态需要多源写入时（如 Cookie 多层管理、配置变更广播），必须满足六步：

1. **写端**：业务变更后写状态 + 写 `pending_marker`（如 `data/markers/cookie_refresh_<user_id>_<timestamp>.json`）
2. **同步端**：独立调度器（`cookie_sync_scheduler.py`）扫描 `pending_marker_dir` 执行同步
3. **读端**：仅读最新状态，不读 marker（marker 仅作同步信号）
4. **启动时**：`_on_startup` 检查 `pending_marker_dir` 中是否有未处理 marker，有则强制触发全量同步
5. **异常时**：保留 marker 不删除，下次重试（成功后才 `unlink`）
6. **配置**：同步开关、间隔、批次大小均通过 `config.yaml#state_sync` 节点管理

**关键约束**：
- `grep "pending_marker\|write_marker" <file>` 写端与 `grep "scan_marker\|process_marker" <file>` 同步端必须配对存在
- 启动函数匹配 `critical_path_patterns` → 必须含 `process_pending_markers()` 调用
- 失败重试最多 N 次（`max_retry_count`，默认 5）后告警，不无限重试

**判断信号**：
- `grep "write_marker" <file>` 但无 `scan_marker` 同步器 → 视为违规（marker 永远不会被消费）
- 启动函数无 `process_pending_markers` 但有 marker 写入端 → 视为违规（重启时积压 marker 丢失）
- `grep "os.unlink\|os.remove.*marker" <file>` 在 try 块内但无异常分支 → 视为违规（失败时 marker 丢失）

**适用**：Cookie 多层同步（JSON ↔ 浏览器内存 ↔ 业务表）、配置变更广播、跨 Tab 状态共享、用户偏好同步。
**不适用**：单写单读的临时状态、纯 UI 状态、性能 hot path（同步开销不可接受）、无跨进程边界的纯函数计算。

**历史教训**：Cookie 自愈系统（v4.32 优化）涉及 3 个写端（`auth_helper.py` / `browser_login.py` / 外部 API 调用）与 1 个同步器（`cookie_sync_scheduler.py`）。修复前：写端无 marker → 同步器无法被触发；写端有 marker 但启动时不检查 → 重启时积压 marker 永久丢失。修复：补全 6 步后，Cookie 自愈成功率从 65% 提升到 92%。

## 29. 前端错误按 error_code 分支（禁止 substring 判断）

> 与 F-REVIEW-ERROR-CODE-BRANCH（frontend 维度 25）对应，本条是后端 + 前端协同的**契约级**元规范。

所有展示后端错误的 UI 组件 + 后端错误响应必须满足：

1. **后端错误响应统一结构**：`{ "error_code": "<reason>", "user_message": "<人类可读>", "detail": "<技术细节>" }`，其中 `error_code` 来自 `config.yaml#failure_reason_propagation.reason_enum` 枚举
2. **前端 switch 分支**：UI 组件用 `switch (err.error_code) { case 'token_expired': ...; case 'anti_crawler': ...; default: ... }` 匹配枚举
3. **禁止 substring 判断**：`if (msg.includes('expired'))` 类反模式禁止（文案变更即失效）
4. **常量集中管理**：前端在 `frontend/src/constants/errorCode.ts` 定义 `ErrorCode` 联合类型与展示文案映射，与后端 `reason_enum` 一一对应
5. **未知 error_code**：降级为通用错误 + `logger.warn` 记录 + 触发运营补登记

**关键约束**：
- 后端响应缺 `error_code` 字段 → 视为**必修 P0 缺陷**（前端无法分支）
- 前端 `if (err.message.includes(...))` → 视为违规（substring 反模式）
- 前端常量文件缺失 `ErrorCode` 类型与后端 `reason_enum` 对应 → 视为**契约不一致**

**判断信号**：
- 后端 `grep "raise HTTPException" <file>` 无 `error_code` 字段 → 视为违规
- 前端 `grep "if\\s*\\(.*\\.message\\.(includes|indexOf|search|match)" <file>` → 视为违规
- 前端 `grep "constants/errorCode\\|ErrorCode =" <file>` 缺对应枚举值 → 视为契约不一致

**适用**：所有展示后端错误的 UI 组件（错误提示/重试按钮/跳转登录）、所有后端 4xx/5xx 响应（除 401/440/441 走认证拦截器外）。
**不适用**：开发环境 `console.error`、本地输入校验（Zod/yup）、HTTP 5xx 网络层错误（统一 toast"网络异常"）。

**历史教训**：多个前端组件用 `if (err.message.includes('expired'))` 判断 Cookie 过期 → 后端文案从「登录已过期」改为「会话已失效」后，所有页面判断失效，统一显示「未知错误」。修复：建立前后端 `error_code` 契约，前端 `switch` 分支，后端响应携带标准化 `error_code` 字段。

## 30. 业务关键字常量集中管理

> 与 F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION（frontend 维度 27）对应，本条覆盖后端 + 前端 + 配置 + 文档的**全栈关键字管理**。

业务关键字（已售、已删除、宝贝不存在、登录已过期、网络异常等需正则匹配/includes 判断的字符串）必须满足：

1. **集中位置**：
   - 后端：`config.yaml#business_keywords.<category>`（如 `sold` / `deleted` / `error_phrases`）
   - 前端：`frontend/src/constants/businessKeywords.ts`（如 `SOLD_KEYWORDS` / `DELETED_KEYWORDS` / `ERROR_PHRASES`）
2. **禁止散落**：业务代码中禁止硬编码关键字字符串（`if ('已售' in text）` → 应读 `config['business_keywords']['sold']`）
3. **配套版本号**：新增关键字需新增 `keyword_id`（如 `KW-SOLD-001`），用于追踪「哪条规则误判/漏判」
4. **配套测试**：每个关键字集合配单元测试（`test_business_keywords.py`）断言「新增商品文案 → 关键字集合应包含」
5. **同步约束**：前后端关键字集合**必须保持等价**（如后端 `sold` 含「卖掉了」，前端 `SOLD_KEYWORDS` 也必须含「卖掉了」），不一致 → 视为**契约不一致**

**关键约束**：
- `grep "['\"](已售|已删除|宝贝不存在|卖掉了|已售罄)['\"]" src/xianyu_hunter/` → 视为硬编码（应从 config 读）
- 业务代码 `grep "if.*['\"].*['\"].*in.*text\|if.*['\"].*['\"].*in.*msg" <file>` → 视为可能硬编码
- 前后端关键字集合不一致 → CI 校验失败（`tests/test_keyword_consistency.py`）

**判断信号**：
- 后端 `grep "['\"](已售|已删除|宝贝不存在|卖掉了|已售罄|该宝贝不存在|商品不存在)['\"]" <file>` → 视为违规
- 前端 `grep "['\"](已售|已删除|宝贝不存在|卖掉了|已售罄)['\"]" <file>` → 视为违规
- `config.yaml` 与 `frontend/src/constants/businessKeywords.ts` 关键字集合不一致 → 视为契约不一致

**适用**：商品状态识别（已售/已删/在售）、错误提示文案匹配、风控标签识别、敏感词过滤、用户行为分类。
**不适用**：日志/异常消息中的自由文本（仅展示用）、配置文件中的连接信息（用户名/密码）、测试用例中的 mock 数据（应使用 fixture）。

**历史教训**：Cookie 自愈系统的 `sold` 关键字集合在 `auth_helper.py`、`browser_login.py`、`cookie_sync_scheduler.py` 三处独立维护，新增「宝贝走丢了」时只更新了 2 处，第 3 处漏更新导致「已售商品」被误判为「在售」继续抢单。修复：抽取到 `config.yaml#business_keywords.sold` 集中管理，前后端同步，配套一致性测试，问题彻底消除。

## 31. 状态恢复前置校验（pause→resume 根因消除校验）🆕v4.31

> 与 B-REVIEW-157（backend 调度器/任务恢复维度）+ F-REVIEW-116（frontend resume 按钮前置校验）对应。
> 本条覆盖所有具有 pause/resume 语义的组件的**恢复前根因消除校验**。

具有 pause/resume 语义的组件（任务调度器、登录会话、连接池、断路器）在 resume 操作前，必须校验「导致 pause 的根因」是否已消除，未消除时拒绝恢复并返回结构化提示。

1. **pause 时记录根因**：异常 pause 必须将 `root_cause`（含 `reason_code` + 失效层标识 + 时间戳）持久化到任务/会话状态，而非仅记日志
2. **resume 前 precheck**：resume 操作必须调用 precheck 函数校验 `root_cause` 对应的前置条件是否已恢复（如 Cookie 层 valid、连接可达、配额充足）
3. **结构化拒绝响应**：校验失败时返回 `{resume_blocked: true, reason_code, user_hint, retry_after}`，禁止静默失败或无条件放行
4. **冷却期**：异常 pause 后设置冷却期（`config.yaml#resume_policy.cooldown_seconds`），期间拒绝 resume，避免"恢复→失效→暂停"无效循环
5. **配置驱动**：冷却期时长、前置校验开关、`reason_code` → precheck 函数映射表均从 config 读取，禁止硬编码

**关键约束**：
- `resume`/`start`/`unpause` 接口缺 precheck 调用 → 视为**必修 P0 缺陷**（无效循环风险）
- 异常 pause 未记录 `root_cause` 字段 → 视为违规（无法校验根因消除）
- resume 接口无拒绝分支（无条件放行）→ 视为违规
- 冷却期时长硬编码在代码中 → 视为违规（应从 config 读）

**判断信号**：
- `grep "def resume\|def start\|def unpause\|def activate" <file>` 缺 `precheck`/`_check_prerequisite` 调用 → 视为违规
- `grep "pause\|paused\|should_pause"` 无 `root_cause` 字段赋值 → 视为违规
- resume 接口 `grep "return.*True\|return.*ok"` 无 `if not precheck` 拒绝分支 → 视为违规
- `grep "cooldown\|cool_down"` 时长为字面量数字而非 config 引用 → 视为硬编码

**适用**：任务调度器 pause/resume（如搜索任务会话失效暂停）、登录会话失效/恢复（Cookie 层失效后重新登录）、连接池断连/重连、断路器开/闭、限流配额耗尽/恢复。
**不适用**：用户主动 pause（非异常触发，无 root_cause）、一次性任务（无 resume 语义）、纯函数重试（无状态持久化）、开发调试手动 resume。

**历史教训**：搜索任务 `t68bc149b` 因闲鱼会话失效（RGV587_ERROR）被自动暂停后，用户/系统在 30 分钟内连续 4 次恢复任务，但 Cookie 未重新登录刷新，每次恢复后 13~22 秒内再次触发会话失效检测并暂停，形成"恢复→失效→暂停"无效循环，浪费浏览器资源并产生 555 条冗余 WARNING。修复：resume 前校验 `cookie_rotator` 的 identity/session 层 `valid` 状态，失效时拒绝恢复并提示"请先重新登录闲鱼"；异常 pause 后设 5 分钟冷却期（config 可配），彻底消除无效循环。

## 32. 多阶段降级链日志合并 🆕v4.31

> 与 B-REVIEW-158（backend 日志规范维度）对应。前端无降级链日志场景，不新增前端检查点。

同一逻辑链的多个中间阶段（降级、重试、回退、多策略尝试）日志必须合并为 1 条结构化结果日志，禁止每个中间步骤独立输出 WARNING。

1. **中间步骤 DEBUG 化**：降级/重试链的中间步骤（如"尝试刷新 token""尝试 DOM 回退"）使用 `logger.debug()`，最终结果使用 `logger.warning()` 或 `logger.error()`
2. **结果日志结构化**：最终结果日志必须含结构化 `extra` 字段：`{stages: [...], final_reason, keyword/context, attempts}`，其中 `stages` 为各中间步骤的简述数组
3. **合并阈值**：同一逻辑链内 ≥2 个阶段则必须合并（`config.yaml#log_merge.min_stages_to_merge` 可配），单阶段无需合并
4. **配置驱动**：合并阈值、中间步骤 DEBUG 开关、保留的中间步骤白名单均从 config 读取

**关键约束**：
- 同一函数内 ≥3 个 `logger.warning` 且属于同一 try/降级链 → 视为违规（应合并为 1 条）
- 降级链中间步骤用 `logger.warning` 而非 `logger.debug` → 视为违规（噪音日志）
- 结果日志无 `extra` 结构化字段 → 视为不规范（无法聚合分析）
- 合并阈值硬编码 → 视为违规（应从 config 读）

**判断信号**：
- `grep -c "logger.warning" <file>` 同一函数内 ≥3 条且属于同一降级链 → 视为违规
- `grep "logger.warning.*尝试\|logger.warning.*刷新\|logger.warning.*回退\|logger.warning.*重试" <file>` 多条且无结构化合并 → 视为冗余告警
- 降级链结果日志 `grep "logger.warning"` 缺 `extra=` 参数 → 视为不规范

**适用**：降级链（API→DOM→缓存）、重试链（指数退避多轮）、多策略回退（多 selector 候选）、浏览器自动化多策略尝试、批处理多阶段校验。
**不适用**：独立的一次性告警（不同业务流程）、用户操作触发的即时反馈、关键路径异常的 `logger.exception()`（需完整堆栈）、不同函数/模块的告警。

**历史教训**：搜索 API 会话失效时，`_search.py` 在同一次搜索失败中输出 5 条 WARNING（FAIL_SYS_ILLEGAL_ACCESS → 尝试强制刷新 _m_h5_tk → 刷新失败 → 尝试 DOM 回退 → DOM 回退超时），单次搜索失效产生 5 条噪音日志，12 小时内累积 555 条冗余 WARNING（占总 WARNING 88%），淹没真正需要关注的告警。修复：中间步骤降为 DEBUG，最终合并为 1 条结构化 WARNING（含 `stages`/`final_reason`/`keyword`），告警量从 628 降至 ~80，可观测性显著提升。

## 33. 注册式资源三件套契约 🆕v4.32

> 与 B-REVIEW-159（backend 注册完整性）/ F-REVIEW-117（frontend 注册完整性）对应。

任何"用户可点击/可导航"的功能入口必须保证 5 层齐备：菜单注册 → 路由注册 → 页面文件 → API wrapper → 后端 endpoint。任一层缺失视为 CRITICAL 缺陷。

1. **5 层契约模型**：L1 `config/menu_registry.yaml`（path/component/label/i18n_key）+ L2 `frontend/src/App.tsx`（`<Route path>` + lazy import）+ L3 `frontend/src/pages/<域>/index.tsx`（export default 组件）+ L4 `frontend/src/api/<域>.ts`（导出 xxxApi 对象）+ L5 `src/xianyu_hunter/web/routes/api_<域>.py`（APIRouter + include_router）
2. **自动化校验**：`python scripts/check_registration.py` 必须在 CI + pre-commit hook 中执行，退出码非 0 即 CRITICAL
3. **结构化输出**：校验结果同时输出表格（开发者读）+ JSON（CI 解析）
4. **豁免机制**：实验性 feature 用 `exemption_list` 临时豁免，必填 `expires` 过期时间
5. **配置驱动**：5 层路径、校验命令、豁免清单均从 `config.yaml#frontend_registration_completeness` 读取，禁止硬编码

**关键约束**：
- 菜单注册了 path 但 App.tsx 无对应 `<Route>` → 视为 CRITICAL（L1 有 L2 无）
- App.tsx 有 `<Route>` 但 `pages/<域>/index.tsx` 不存在 → 视为 CRITICAL（L2 有 L3 无）
- 页面 import api 模块但 `api/<域>.ts` 不存在 → 视为 CRITICAL（L3 有 L4 无）
- api wrapper 调用 endpoint 但后端无 `@router.<method>` → 视为 CRITICAL（L4 有 L5 无）

**判断信号**：
- `python scripts/check_registration.py` 退出码非 0 → 任意层缺失
- `grep -E "path: ['\"]/(notifications|orders|users)['\"]" config/menu_registry.yaml` 命中但 App.tsx 无对应 Route → L1 有 L2 无
- `Glob "frontend/src/pages/Notifications/index.tsx"` 失败但 App.tsx 有 `path="notifications"` 的 Route 引用 → L3 缺失
- `Glob "frontend/src/api/notifications.ts"` 失败但页面 import 该模块 → L4 缺失
- `grep -E "@router\.(get|post).*['\"\/]notifications" src/xianyu_hunter/web/routes/` 失败 → L5 缺失

**适用**：任何"用户可点击/可导航"的功能入口（菜单/侧边栏/按钮/Tab/Drawer/路由/Breadcrumb/通知订阅）。
**不适用**：纯静态页面、SSR（菜单由后端渲染）、单页 CLI、嵌入式设备、PWA 离线首页（单一 HTML 入口）、草稿/实验性 feature（用 exemption_list 豁免）。

**历史教训**：用户反馈"通知中心菜单点击无反应"。根因：`menu_registry.yaml` 注册了 `path=/notifications`，后端 `api_notifications.py` 完整实现接口，但前端 `App.tsx` 未注册路由、`pages/Notifications/` 不存在、`api/notifications.ts` 缺失。路由 fallback `<Route path="*" element={<Navigate to="/" replace />} />` 静默重定向回首页，用户体感"明明菜单点了几次，URL 都不变"。修复：新建 3 个前端文件 + App.tsx 注册路由。预防：加 #33 元规范 + `check_registration.py` 自动化脚本。

> 📖 详细 5 层契约模型、自动化校验脚本伪代码、配置节点定义见 [registration-completeness.md](registration-completeness.md)。

## 34. 修复前全链路根因扫描协议 🆕v4.32

> 与 B-REVIEW-160（backend 修复链路反查）/ F-REVIEW-118（frontend 根因最小数量）对应。

修复任何非平凡 bug（≥2 个文件参与 / 涉及状态变更 / 跨前后端 / 复盘过 ≥1 次）必须执行 5 步根因扫描协议，禁止"看到什么修什么"的单点修复。

1. **Step 1 列根因（≥3 个）**：必须列出至少 3 个独立根因，覆盖"用户层/接口层/数据层/配置层/历史层"5 维度，按"可能性 × 危害性"排序
2. **Step 2 排根因**：对每个根因用 1-2 个工具命令（Grep/Glob/Read/RunCommand）验证，记录"哪些被排除、哪些被确认"
3. **Step 3 修复**：只修改根因相关行（精确编辑原则），不顺手重构相邻代码，修复后立即 `git diff` 检查改动范围
4. **Step 4 反查**：修复后必须反查"同类 bug 的所有变体（横向同类）+ 用户操作路径其他拦截点（纵向全链）+ 配置/文档/部署中的体现（横向文档）"
5. **Step 5 防回归**：加 unit test + integration test + 更新 B/F-REVIEW 检查点 + 更新 `version-history.md` + 必要时更新 `project_memory.md` 硬约束

**关键约束**：
- PR 描述"修复"段不足 3 句 → 视为根因未充分展开（SUGGESTION）
- 修复后没有"反查同类 bug"段 → 视为 Step 4 缺失（SUGGESTION）
- `git diff` 涉及 ≥3 个无关文件 → 视为违反最小修改原则（WARNING）
- 新增逻辑但没加 unit test → 视为 Step 5 缺失（WARNING）
- 没有更新 `version-history.md` → 视为 Step 5 文档缺失（NIT）

**判断信号**：
- PR 描述 "修复" 段不足 3 句 → 根因未充分展开
- 修复后没有"反查同类 bug" 段 → Step 4 缺失
- `git diff` 涉及 ≥3 个无关文件 → 违反最小修改原则
- 新增逻辑但没加 unit test → Step 5 缺失
- 没有更新 `version-history.md` → Step 5 文档缺失

**适用**：修复任何非平凡 bug（≥2 个文件参与 / 涉及状态变更 / 跨前后端 / 复盘过 ≥1 次）。
**不适用**：纯样式 bug（颜色/间距/字号）、单行 typo（错别字/标点）、纯构建错误（依赖缺失/版本冲突）、安全漏洞补丁（时间敏感，先修后复盘，1 周内补复盘）、实验性 feature 试错。

**历史教训**：用户报告"通知中心菜单点击无反应"。朴素做法：直接去 App.tsx 加一行路由 → 完成。但用户还报告"配置中心"、"操作手册"、"实时日志"等 5 个菜单都"点击无反应"，单点修复只解决了 1/5。根因：6 类失败模式（相似 bug 重复 / 配置一致性盲区 / 跨语言契约模糊 / 熔断重试副作用 / 资源生命周期泄漏 / 空 except 吞异常）都源于"看到什么修什么"的单点修复思维。修复：建立 #34 5 步根因扫描协议，强制列 ≥3 根因 + 反查全链路。

> 📖 详细 5 步协议、6 类失败模式、配置节点定义见 [root-cause-protocol.md](root-cause-protocol.md)。

## 35. 前后端字段契约单一可信源 🆕v4.32

> 与 B-REVIEW-161（backend 字段权威源标记）/ F-REVIEW-119（frontend 字段派生来源标注）对应。

前后端分离架构中，后端 Pydantic 模型 + DB Row 字段定义为权威源，前端 `types.ts` 必须显式标注派生来源，禁止无标注手工复制。

1. **单一可信源原则**：后端 Pydantic + DB Row = 权威源；前端 types.ts 必须显式标注派生来源（后端文件路径 + 行号 + Pydantic 字段 + 变更日期 + 约束）
2. **三种实现路径**：A 后端生成前端 types（datamodel-code-generator）/ B 手工对齐 + 注释标注（本项目当前选 B）/ C 共享 zod schema
3. **5 点追踪清单**：字段变更（新增/重命名/类型调整）必须 5 点全部更新：DB Row 定义 → Pydantic 模型 → 后端返回路径（_row_to_dict 白名单）→ 前端 types.ts → 前端消费点（api 方法 + pages 渲染）
4. **命名约定**：backend snake_case / frontend snake_case 严格透传（禁止转 camelCase）/ url_path kebab-case / class_name PascalCase
5. **配置驱动**：实现路径、注释模板字段、5 点追踪清单、命名约定、类型映射白名单均从 `config.yaml#contract_single_source` 读取

**关键约束**：
- 前端 types.ts 字段 `xxxYyy`（驼峰）但后端 Pydantic 字段 `xxx_yyy`（snake_case）→ 视为 CRITICAL（命名漂移）
- 后端新增字段但前端 types.ts 未同步 → 视为 CRITICAL（字段缺失）
- 前端 types.ts 缺 `派生来源` 注释 → 视为 WARNING（手工对齐但未标注）
- 前端 types.ts 字段标 `?` 但后端 Pydantic 标 `...` → 视为 WARNING（可选性漂移）
- 前端直接访问后端返回的 dict 用 `data['xxxYyy']`（驼峰）→ 视为 CRITICAL（违反 snake_case 透传）

**判断信号**：
- `grep "派生来源" frontend/src/api/types.ts` 缺失 → 手工对齐未标注
- 后端 Pydantic 字段 `xxx_yyy` + 前端 types.ts 字段 `xxxYyy` → 命名漂移
- 后端新增字段，前端 types.ts 未同步 → 字段缺失
- 前端 types.ts 字段标 `?` 但后端 Pydantic 标 `...` → 可选性漂移
- 前端直接访问后端返回的 dict 用 `data['xxxYyy']`（驼峰）→ 违反 snake_case 透传

**适用**：前后端分离架构中，任何跨网络边界传输的数据结构（HTTP body / query / path）。
**不适用**：纯前端单页（无后端）、SSR（后端直接渲染）、monorepo + 共享 types（已 typegen）、第三方 API（不可控，用适配层 + 注释"外部 API 字段名"）、性能 hot path（极致优化，用结构化 schema + 手工断言）。

**历史教训**：前端 `NotificationItem` 接口字段 `read_at` 拼成 `readAt`（驼峰）→ 后端返回 `read_at`（snake_case）→ 前端永远读到 `undefined` → "标记已读"按钮点击无效。根因：前端 types.ts 手工复制 Pydantic 字段时自己转成了驼峰。修复：建立 #35 单一可信源原则 + 5 点追踪清单 + types.ts 注释模板。5 类典型漂移：命名风格漂移 / 大小写漂移 / 类型漂移 / 可选性漂移 / 枚举值漂移。

> 📖 详细单一可信源原则、三种实现路径、5 点追踪清单、配置节点定义、典型反模式见 [contract-single-source.md](contract-single-source.md)。

## 36. 规范沉淀门槛（防过度规范化）🆕v4.33

> 与 B-REVIEW-162（backend 规范立项前置计数）/ F-REVIEW-120（frontend 规范立项前置计数）对应。

新立编码规范（meta-rule / step / B-REVIEW / F-REVIEW）前必须满足"≥3 个相似 bug"门槛，避免单一 bug 立规范导致规范膨胀。安全漏洞/数据丢失/付费受损类 bug 可豁免，立即立规范。

1. **相似 bug 计数门槛**：同一根因（非表象）在不同文件/模块出现 ≥3 次才可立规范，阈值从 `config.yaml#meta_rules_governance.sedimentation_threshold` 读取
2. **计数维度**：根因相同（如"datetime 时区不一致"）而非表象相同（如"TypeError"）；文件/模块不同（非同文件重复）；时间窗口 ≤ 6 个月（避免跨年代久远的 bug 凑数）
3. **例外豁免**：安全漏洞（如 token 泄露）、数据丢失（如 DB 迁移失败）、付费受损（如订单金额错误）可立即立规范，无需 ≥3 次
4. **experimental 标签机制**：未达门槛但希望预沉淀的规范可标 `experimental` 标签，1 季度后未再出现相似 bug 则废弃；达标后升级为正式规范
5. **配置驱动**：相似 bug 计数阈值、时间窗口、例外豁免类别、experimental 观察期均从 config 读取，禁止硬编码

**关键约束**：
- 单一 bug 立规范（无 experimental 标签）→ 视为违规（规范膨胀风险）
- experimental 标签超 1 季度未升级为正式 → 视为废弃候选（应清理）
- 例外豁免立规范但未标注豁免原因 → 视为不规范（无法审计）
- 计数阈值硬编码在代码中 → 视为违规（应从 config 读）

**判断信号**：
- `grep "experimental" meta-rules.md` 标签超 1 季度未升级 → 废弃候选
- 新立 meta-rule 但无"历史教训"段（无相似 bug 支撑）→ 视为可疑
- 新立 B-REVIEW/F-REVIEW 但无对应"历史教训" → 视为可疑
- `grep "豁免原因" meta-rules.md` 例外规范缺豁免说明 → 视为不规范

**适用**：所有新立编码规范（meta-rule / step / B-REVIEW / F-REVIEW）的立项前置检查。
**不适用**：紧急安全修复（先修后立规范，1 周内补立项）、配置项新增（不立规范，只加 config 节点）、文档修正（非规范变更）。

**历史教训**：v4.10 期间某次单一 typo（变量名拼错）触发立规范，新增 1 条 B-REVIEW 检查点，但后续 6 个月未再出现相似 typo。该 B-REVIEW 在审查中 0 命中，占比规范总数 1.5%，拉低审查效率。修复：建立 #36 门槛规则，单一 bug 用 experimental 标签预沉淀，1 季度后未复现则废弃。

## 37. 规范退化机制（防规范膨胀）🆕v4.33

> 与 B-REVIEW-163（backend 规范退化清理）/ F-REVIEW-121（frontend 规范退化清理）对应。

每季度统计各 step / B-REVIEW / F-REVIEW 在审查中的命中次数，利用率 < 3 次/季度则标记为"待合并"或"待废弃"，避免规范垃圾堆积拉低审查信噪比。安全类规范永不退化。

1. **利用率统计**：每季度末统计各 step / B-REVIEW / F-REVIEW 在审查报告中的命中次数，输出利用率排行榜
2. **退化阈值**：利用率 < `config.yaml#meta_rules_governance.degradation_threshold`（默认 3 次/季度）则标记为"待合并"或"待废弃"
3. **合并优先**：相似 step 优先合并（如 3 个 datetime 相关 step 合并为 1 个），废弃是最后手段
4. **废弃流程**：标记"待废弃" → 1 季度观察期（`config.yaml#meta_rules_governance.observation_period_quarters`，默认 1） → 确认无命中 → 废弃并移入 `version-history.md` 的 Deprecated 章节
5. **安全类豁免**：安全类规范（token 比较 / 加密 / 认证白名单等）永不退化，即使 0 命中也保留
6. **配置驱动**：退化阈值、观察期时长、安全类豁免清单均从 config 读取

**关键约束**：
- 利用率 < 阈值但未标记"待合并/待废弃" → 视为不规范（规范治理缺失）
- 废弃的 step/B-REVIEW 未移入 version-history.md 的 Deprecated 章节 → 视为不规范（历史记录缺失）
- 安全类规范被标记"待废弃" → 视为违规（安全规范永不退化）
- 退化阈值硬编码 → 视为违规（应从 config 读）

**判断信号**：
- `grep "待废弃" meta-rules.md` 标记超 1 季度未处理 → 废弃流程卡住
- `grep "Deprecated" version-history.md` 章节缺失 → 废弃记录不全
- 季度审查报告显示利用率 < 3 的规范未标记 → 退化机制未执行
- 安全类规范出现在"待废弃"列表 → 视为违规

**适用**：所有现有 step / B-REVIEW / F-REVIEW 的季度治理。
**不适用**：安全类规范（永不退化）、配置驱动类规范（依赖 config 存在，config 节点存在则规范保留）、meta-rule #1-35 的元规范（元规范是基础规则，不参与退化）。

**历史教训**：v4.0-v4.10 累积 30+ step，v4.20 季度审查发现其中 8 个 step 在 1 季度内 0 命中，占比 27%。这 8 个 step 拉低审查效率，且部分与后续新增 step 语义重叠。修复：建立 #37 退化机制，8 个 0 命中 step 中 5 个合并到相似 step、3 个移入 Deprecated 章节，规范总数从 30+ 精简到 22，审查信噪比提升 27%。

---

# 列表聚合与状态联动元规范（38-42）🆕v4.34.0

> 以下 5 条元规范从 2026-07 期间修复的「全局聚合列表过滤失效 / 列表交叉数据 N+1 查询 / 多字段联动开关语义模糊 / precheck 异常处理不规范 / 配置化阈值缺失兜底」5 类问题中提炼，定义为「列表聚合与状态联动」维度的通用判断逻辑。
>
> 命名空间与配置驱动：所有阈值（`global_aggregate_filter` / `cross_domain_inject` / `linked_switch_priority` / `precheck_structured_fields` / `config_fallback_defaults`）均在 `config.yaml` 对应节点管理，禁止硬编码。

## 38. 全局聚合任务级过滤（GLOBAL-AGGREGATE-TASK-FILTER）🆕v4.34

> 与 B-REVIEW-164（backend 列表聚合过滤维度）/ F-REVIEW-122（前端列表过滤透传）对应。

多任务共享的列表查询接口（无 `task_id` 参数的全局视图）必须按各任务的个体配置范围进行过滤，禁止只应用全局过滤而忽略任务级范围，导致越界数据被返回。

1. **全局视图与单任务视图区分**：列表查询接口必须区分「单任务视图」（显式 `task_id`）与「全局视图」（无 `task_id`），两者过滤逻辑不同
2. **全局视图任务级过滤**：全局视图必须遍历所有任务，对每条数据按其归属任务的个体配置（如价格范围）过滤，而非用全局默认范围过滤
3. **过滤函数抽取**：任务级过滤逻辑必须抽取为独立函数（如 `_filter_by_per_task_range`），便于复用与单测
4. **空范围处理**：任务无配置时使用全局默认范围兜底，禁止跳过过滤
5. **配置驱动**：过滤策略（per_task / global_only / hybrid）、默认范围兜底开关从 `config.yaml#global_aggregate_filter` 读取

**关键约束**：
- 全局视图缺任务级过滤分支 → 视为**必修 P0 缺陷**（数据越界）
- 任务级过滤逻辑硬编码在主循环（未抽取函数）→ 视为违规
- 任务无配置时跳过过滤（无兜底）→ 视为违规

**判断信号**：
- `grep "task_id.*None\|task_id.*is None" <file>` 但无 `_filter_by_per_task` / `_filter_by_task_range` 调用 → 视为违规
- `grep "def list_.*\(.*task_id.*\)" <file>` 缺全局视图分支 → 视为可疑
- 列表接口返回数据中存在超过任一任务配置上限的值 → 视为 P0

**适用**：多任务共享的列表查询接口（评估列表 / 仪表盘 / 商品列表 / 订单列表）、跨任务聚合视图、全局搜索。
**不适用**：单任务详情视图（task_id 显式传入，应用该任务范围）、统计聚合（无个体过滤需求）、管理后台超管视图（看全部数据）。

**历史教训**：用户反馈「最高价仍显示 ¥2,988.00」。根因：`evaluations_list.py` 在无 `task_id`（默认全局视图）时直接返回 `{min: None, max: None}` 不做任务级过滤，导致 task 价格上限 800 的商品也能查到 ¥2,988 的评估数据。修复：新增 `_filter_by_per_task_range` 函数，全局视图下按各任务个体价格范围过滤；`_load_sold_prices_from_links` 和 `_load_all_prices_from_items` 均调用此函数。

## 39. 列表交叉数据批量注入（LIST-CROSS-DOMAIN-INJECT）🆕v4.34

> 与 B-REVIEW-165（backend 列表 N+1 查询修复维度）/ F-REVIEW-123（前端列表数据合并展示）对应。

列表查询需要交叉注入其他数据源的数据（如评估列表注入捡漏价格、订单列表注入商品详情）时，必须采用批量查询 + TTL 缓存模式，禁止 N+1 单条查询导致接口性能退化。

1. **批量查询强制**：列表接口交叉其他数据源时必须用 `WHERE xxx IN (...)` 批量查询，禁止循环内单条查询
2. **TTL 缓存**：交叉数据查询结果必须按业务键（如 task_id / seller_id）缓存，TTL 从 `config.yaml#cross_domain_inject.cache_ttl_seconds` 读取
3. **单轮缓存**：单次 run_once / 单次请求内缓存，每轮重置（避免缓存陈旧）
4. **缺失降级**：交叉数据查询失败时降级为 `None` / 空对象，禁止阻断主列表返回
5. **配置驱动**：缓存开关、TTL、批量查询分块大小（避免 IN 子句过长）从 config 读取

**关键约束**：
- 循环内单条查询（`for item in items: db.query(filter=item.id)`）→ 视为**必修 P0 缺陷**（N+1 查询）
- 缺失交叉数据时抛异常阻断主列表 → 视为违规（应降级为 None）
- 缓存 key 含时间戳或随机值（无复用性）→ 视为违规

**判断信号**：
- `grep "for.*in.*items:" <file>` 后跟 `db.query\|session.execute` 单条查询 → 视为 N+1 违规
- `grep "def list_.*\(.*\)" <file>` 缺 `IN \(.*\)` 批量查询 → 视为可疑
- 交叉数据查询无 `cache_ttl` / `_cache` / `lru_cache` → 视为不规范

**适用**：列表接口需要交叉其他数据源（评估列表 + 捡漏价格、订单列表 + 商品详情、商品列表 + 卖家信息、任务列表 + 最后执行状态）。
**不适用**：单条详情查询（无 N+1 风险）、TTL 不可接受的热路径（需实时数据）、列表数据量固定 ≤3 条（无性能问题）。

**历史教训**：评估列表显示「预估盈利」时，`_compute_sold_range` 在循环内对每个 task 单独查询已售价格，10 个任务触发 10 次 DB 查询，接口耗时从 200ms 升到 1.8s。修复：改为批量查询所有 task 的已售价格 + 5 分钟 TTL 缓存，接口耗时降到 250ms。

## 40. 多字段联动开关范式（MULTI-FIELD-LINKED-SWITCH）🆕v4.34

> 与 B-REVIEW-166（backend 联动开关优先级矩阵）/ F-REVIEW-124（前端联动开关 UI 状态）对应。

多个业务字段叠加生效（如 `mode` 主开关 + `notify_bargain_only` / `auto_buy_bargain_only` 子过滤器）时，必须明确「主开关 → 过滤器」优先级矩阵，主开关失效时子过滤器自动禁用，禁止语义冲突的组合。

1. **优先级矩阵显式声明**：联动字段必须在文档/注释中显式声明「主开关 → 过滤器」优先级矩阵，列出所有合法组合
2. **主开关失效时子过滤器禁用**：主开关为 `notify`（仅通知）时 `auto_buy_*` 过滤器必须自动禁用 + UI 标识不可用
3. **PATCH 三态语义**：PATCH 接口必须用 `exclude_unset=True` 区分「未传 / 传 null / 传值」三态，禁止 0/false 被误判为未传
4. **bool→int 存储**：DB 存储 BOOLEAN 字段时统一用 INTEGER(0/1)，与同类开关字段（如 `use_cron`）保持一致
5. **配置驱动**：优先级矩阵、禁用规则、字段映射从 `config.yaml#linked_switch_priority` 读取

**关键约束**：
- 联动字段无优先级矩阵文档 → 视为 WARNING（语义模糊）
- 主开关 notify 模式但 `auto_buy_*` 未禁用 → 视为 P1（语义冲突）
- PATCH 接口未用 `exclude_unset=True` → 视为违规（三态丢失）
- bool 字段存储为 STRING('true'/'false') → 视为违规（应 INTEGER 0/1）

**判断信号**：
- `grep "mode.*notify\|mode.*auto_buy" <file>` 但无优先级矩阵注释 → 视为可疑
- `grep "exclude_unset.*True\|exclude_unset=True" <file>` PATCH 接口缺此参数 → 视为违规
- `grep "notify_bargain_only\|auto_buy_bargain_only" <file>` 缺 `disabled={.*mode.*===.*notify}` → 视为前端 UI 不规范
- `grep "BOOLEAN\|String.*true.*false" <file>` DB schema 中 bool 字段非 INTEGER → 视为违规

**适用**：多字段叠加生效的业务开关（mode + 子过滤器、enabled + 子配置、auto_* + 限制条件）。
**不适用**：独立开关（无联动）、纯前端 UI 开关（无后端逻辑）、单一布尔开关（无组合语义）。

**历史教训**：任务配置含 `mode` + `notify_bargain_only` + `auto_buy_bargain_only` 三个字段，无优先级矩阵。用户反馈「mode=notify 但 auto_buy_bargain_only=true 是否会触发自动下单」语义模糊。修复：明确优先级矩阵（mode 是主开关，*_bargain_only 是过滤器；mode=notify 时 auto_buy_bargain_only 自动禁用 + UI Tag 标识），PATCH 接口用 `exclude_unset=True` 三态语义，bool→int 存储与 `use_cron` 一致。

## 41. 状态恢复前置校验结构化响应（RESUME-PRECHECK-STRUCTURED）🆕v4.34

> 与 B-REVIEW-167（backend precheck 结构化响应）/ F-REVIEW-125（前端 precheck 失败 UI 反馈）对应。
> 与 #31 状态恢复前置校验的关系：#31 给出「resume 前 precheck 校验根因」的整体框架，本条是 precheck 函数自身的**结构化响应契约**。

precheck 函数必须返回结构化 dict，不抛异常，包含 5 个标准字段，便于 API 层统一转换为 HTTP 响应与前端统一渲染。

1. **5 字段结构化响应**：precheck 必须返回 dict，含 5 字段：
   - `resume_blocked: bool` — 是否阻断恢复
   - `reason_code: str` — 来自 `config.yaml#error_code.reason_enum` 枚举（ok / cooldown / cookie_invalid / not_registered 等）
   - `user_hint: str` — 人类可读提示（含恢复动作建议）
   - `retry_after: int | None` — 冷却期剩余秒数（null 表示无冷却期）
   - `task_registered: bool` — 任务是否注册到调度器（区分纯 web 模式）
2. **不抛异常原则**：precheck 内部异常必须 catch 并转换为结构化响应，禁止向上抛异常（API 层无法统一处理）
3. **API 层转换**：API 层（`api_tasks.py` 等）调用 precheck 后直接返回 dict，禁止再做异常转换
4. **前端 4 字段消费**：前端必须消费 4 字段（`resume_blocked` / `reason_code` / `user_hint` / `retry_after`），按 `reason_code` switch 分支
5. **配置驱动**：5 字段名、reason_code 枚举、纯 web 模式响应模板从 `config.yaml#precheck_structured_fields` 读取

**关键约束**：
- precheck 函数 `raise` 异常 → 视为**必修 P0 缺陷**（API 层无法处理）
- precheck 返回 dict 缺任一标准字段 → 视为违规
- API 层用 `try/except` 包 precheck → 视为违规（应在 precheck 内部 catch）
- 前端不消费 `reason_code` 而用 `user_hint.includes(...)` 判断 → 视为违规（违反 #29）

**判断信号**：
- `grep "def precheck_\|def _precheck" <file>` 函数体内含 `raise` → 视为违规
- `grep "def precheck_\|def _precheck" <file>` 返回值缺 `resume_blocked\|reason_code\|user_hint\|retry_after\|task_registered` 任一 → 视为违规
- `grep "precheck.*\(.*\).*:" <file>` API 路由内含 `try.*precheck.*except` → 视为违规
- `grep "result\.user_hint\.includes\|result\.user_hint\.indexOf" frontend/` → 视为违规

**适用**：任何 precheck/resume 类接口（任务恢复 / 会话恢复 / 调度器恢复 / 连接池重连 / 断路器闭合 / 限流配额恢复）。
**不适用**：单纯校验函数（无结构化响应需求，直接返回 bool）、同步阻塞式校验（无恢复语义）、纯前端校验（无后端 precheck）。

**历史教训**：`scheduler.precheck_resume` 最初设计为抛 `ResumeBlockedError` 异常，`api_tasks.py` 用 `try/except` 捕获后转换为 400 响应。问题：(1) 多种阻断原因（冷却期 / Cookie 失效 / 未注册）需多个异常类，类爆炸；(2) 前端无法用 `reason_code` 分支只能 substring 判断 `user_hint`；(3) 纯 web 模式（无 collector）需特殊处理。修复：改为结构化 dict 返回 5 字段，API 层直接透传，前端按 `reason_code` switch 分支（cooldown 显示倒计时、cookie_invalid 跳登录、not_registered 提示重启服务）。

## 42. 配置化阈值兜底范式（CONFIG-DRIVEN-THRESHOLD-FALLBACK）🆕v4.34

> 与 B-REVIEW-168（backend 配置兜底范式）/ F-REVIEW-126（前端配置缺失降级）对应。

从 `config.yaml` 读取的阈值/分位数/百分位必须有 `try/except` 兜底默认值，保证配置缺失、配置加载失败、配置类型错误时系统仍可运行，禁止"配置缺失即崩溃"。

1. **try/except 兜底强制**：所有从 config 读取的阈值必须用 `try/except` 包裹，失败时回退到代码内默认值
2. **默认值合理性**：默认值必须与配置模板（`config.example.yaml`）保持一致，禁止默认值与示例配置冲突
3. **失败降级日志**：兜底时必须 `logger.warning` 记录（不用 `logger.error`，避免污染告警），含字段名与回退值
4. **配置全链路验证**：新增配置项必须同步更新 `config.example.yaml` + Config 类字段 + 消费点 try/except
5. **配置驱动**：兜底开关、默认值表、降级日志级别从 `config.yaml#config_fallback_defaults` 读取

**关键约束**：
- 配置读取无 `try/except` 兜底 → 视为 P1（配置缺失即崩溃）
- 默认值与 `config.example.yaml` 不一致 → 视为违规
- 兜底时用 `logger.error` 触发告警 → 视为不规范（应 `logger.warning`）
- 新增配置项未更新 `config.example.yaml` → 视为违规（参考 meta-rule #16 全链路验证）

**判断信号**：
- `grep "get_config\(\)\.\w+\.\w+" <file>` 但无 `try.*except.*default` 包裹 → 视为可疑
- `grep "from.*yaml_config import get_config" <file>` 但同文件 `get_config()` 调用无 try/except → 视为违规
- `grep "logger\.error.*配置.*默认\|logger\.error.*fallback" <file>` → 视为不规范（应 warning）
- `config.example.yaml` 与 Config 类默认值 grep 不一致 → 视为违规

**适用**：从 config 读取的阈值/分位数/百分位/重试次数/超时秒数/批次大小等可调参数。
**不适用**：强制必需配置（如数据库路径、认证密钥，缺失即不可启动，应在启动校验时 `raise` 而非兜底）、安全相关配置（如 token 比较方式，不可兜底）、协议固定值（不可配置）。

**历史教训**：`_compute_sold_range` 中 P10 分位数从配置读取 `bargain_percentile = get_config().bargain_price.percentile`，但用户 `config.yaml` 是旧版本无此字段，启动时未报错但调用时 `AttributeError: 'BargainPriceConfig' object has no attribute 'percentile'`，整个价格策略接口崩溃。修复：改为 `try: bargain_percentile = get_config().bargain_price.percentile; except Exception: bargain_percentile = 0.10` 兜底默认值，并 `logger.warning` 记录。后续推广为 #42 范式，所有配置读取必须有兜底。

> 📖 详细配置兜底范式、默认值表、降级日志模板见 [config-driven.md](../assets/guides/coding-rules/config-driven.md) step 188。

---

# 跨层契约与测试同步元规范（43-47）🆕v4.35.0

> 以下 5 条元规范从 2026-07-07 解决的「SEMI_AUTO 模式通知未触发确认 / EVAL_PASSED 事件三处发布点 task_mode 字段不对齐 / 前端 sheetRegistry 未注册新路由 + findSheetMeta 未剥离 query string / useSheetSync 丢失 query string / 历史测试 mock 类型不匹配 + keyring fallback + 接口签名变更未同步测试」5 类问题中提炼，定义为「跨层契约对齐与测试同步」维度的通用判断逻辑。
>
> 命名空间与配置驱动：所有参数（`event_multi_emit_alignment` / `frontend_route_registration` / `external_callback_query_retention` / `test_synchronization` / `external_dependency_isolation`）均在 `config.yaml` 对应节点管理，禁止硬编码。所有路径/模块名/字段名通过角色抽象描述（如「事件发布点」「路由注册表」「query string 字段名」），不硬编码具体文件名。

## 43. 事件多发布点字段对齐（EVENT-MULTI-EMIT-ALIGN）🆕v4.35

> 与 B-REVIEW-173（backend 事件多发布点字段对齐审查，v4.35 待落地）/ F-REVIEW-131（前端消费方分支对齐审查，v4.39 待落地）对应。

业务事件在多个层（worker / 服务 / 路由 / 通知模板）有发布点时，每处发布点必须保持事件 payload 字段集与字段语义一致，禁止某处补齐某字段而其他发布点遗漏，导致下游消费方按字段分支失败。

1. **多发布点识别**：grep 事件类型字符串（如 `EVAL_PASSED` / `task.started`），识别所有发布点（worker / service / route / template / SSE 推送器）
2. **字段对齐**：每处发布点的 payload 必须包含配置中声明的「必传字段集」（如 `task_mode` / `user_id` / `trace_id`），缺一视为违规
3. **重构同步**：当某处发布点新增字段时，必须 grep 所有发布点逐一同步
4. **下游消费对齐**：消费方按字段分支（如 `if payload.task_mode == SEMI_AUTO`）时，必须存在 fallback 分支（`else` / `default`），避免字段缺失时静默走默认路径
5. **配置驱动**：发布点清单、必传字段集、字段语义说明从 `config.yaml#event_multi_emit_alignment` 读取

**关键约束**：
- 业务事件有 ≥2 处发布点但 payload 字段集不一致 → 视为 **必修 P0 缺陷**（下游分支失效）
- 新增字段但未 grep 同步所有发布点 → 视为违规
- 消费方按字段分支但无 fallback → 视为违规（字段缺失时静默默认）
- 发布点清单硬编码在代码中（如 `["worker.py", "collection_service.py"]`）→ 视为违规（应从 config 读）

**判断信号**：
- `grep "<event_type>" src/` 命中 ≥2 处，每处上下文 `grep "<required_field>"` 不全命中 → 字段未对齐
- `grep "<event_type>.*emit\|publish.*<event_type>"` 多处但 `payload = {` 后字段数不同 → 字段集不一致
- 消费方 `if payload.<field> == X` 但无 `else` → fallback 缺失
- 新增字段后 git diff 显示发布点未同步更新 → 同步缺失

**适用**：业务事件在多层有发布点的场景（worker → service → route → 通知模板）；事件 payload 含分支决策字段（如 `task_mode` / `severity` / `source`）；事件需多消费方订阅（SSE 推送 + 通知中心 + Dashboard 刷新）。
**不适用**：单一发布点的内部事件（一处发布无需对齐）；纯调试日志事件（不产生下游副作用）；一次性脚本事件（无长期维护成本）。

**历史教训**：SEMI_AUTO 模式任务通过评估后，`worker.py` 的 `EVAL_PASSED` 发布点 payload 含 `task_mode` 字段，但 `collection_service.py` 与 `evaluations_common.py` 两处发布点未携带 `task_mode`，导致通知模板层无法按 `task_mode` 渲染"确认抢单"链接，SEMI_AUTO 退化为 NOTIFY_ONLY，从未触发确认动作。修复：grep 所有 EVAL_PASSED 发布点逐一补齐 `task_mode`，并建立 #43 强制对齐规则。

## 44. 前端路由三重注册同步（ROUTE-TRIPLE-REGISTRATION）🆕v4.35

> 与 B-REVIEW-174（backend 路由清单与前端注册对齐，v4.35 待落地）/ F-REVIEW-132（前端路由三重注册审查，v4.39 待落地）对应。

新增前端路由（含 SheetWorkspace 多页签应用）必须在「路由声明层 / 多页签注册层 / URL 同步 Hook 层」三处同步注册，禁止只注册一层导致「URL 变了内容不变」或「内容变了 URL 不变」的 UI 错乱。

1. **三重注册清单**：新增路由必须同步注册：
   - L1 路由声明层（如 `App.tsx` 的 `<Route>`）
   - L2 多页签注册层（如 `SheetWorkspace/sheetRegistry.tsx` 的 path → component 映射）
   - L3 URL 同步 Hook 层（如 `useSheetSync.ts` 的 location → sheet 同步逻辑）
2. **query string 保留**：路由携带 query string（如 `?task_id=xxx`）时，L3 Hook 必须 `location.pathname + location.search` 拼接，禁止只取 pathname 丢 query string
3. **路径匹配剥离**：L2 注册层的 `findSheetMeta` 函数必须先剥离 query string 与 hash 再匹配，避免 `?xxx` 干扰精确匹配
4. **配置驱动**：三重注册清单、query string 保留路由列表、路径匹配剥离规则从 `config.yaml#frontend_route_registration` 读取

**关键约束**：
- 新增路由只注册 L1（App.tsx）但未注册 L2（sheetRegistry）→ SheetWorkspace 显示"未打开任何页面"
- L3 Hook 只取 `location.pathname` 不取 `location.search` → query string 丢失，下游组件读不到参数
- L2 `findSheetMeta` 直接用原始 path 匹配（含 query string）→ 精确匹配失败
- 注册清单硬编码在代码中（如 `["/confirm-buy", "/tasks"]`）→ 视为违规（应从 config 读）

**判断信号**：
- `git diff` 显示新增 `<Route path="/<route_name>"` 但同 PR 内 `sheetRegistry` 无对应条目 → L2 同步缺失
- `grep "location.pathname" frontend/src/hooks/useSheetSync.ts` 但无 `location.search` → query string 丢失
- `grep "findSheetMeta" frontend/src/components/SheetWorkspace/` 函数体内无 `split('?')[0]` → 剥离缺失
- 新增路由后用户反馈"URL 变了内容不变"或"内容变了 URL 不变" → 三重同步失败

**适用**：SheetWorkspace 多页签应用中的新增路由；从外部链接（通知 / 邮件 / 二维码）回链进入应用的路由（依赖 query string 传参）；任何 path → component → URL 三层联动的路由系统。
**不适用**：独立路由（如 `/login` 不进入 SheetWorkspace）；纯 Hash 路由（query string 不在 pathname 中）；纯服务端渲染（无前端路由层）。

**历史教训**：新增 `/confirm-buy` 路由（SEMI_AUTO 通知回链）只在 `App.tsx` 注册，未同步到 `sheetRegistry`，导致用户点击通知后 URL 变为 `/confirm-buy` 但页面显示"未打开任何页面，请从左侧菜单选择"。修复：在 sheetRegistry 新增条目 + 修改 `findSheetMeta` 剥离 query string + 修改 `useSheetSync` 保留 query string，三重同步后页面正常渲染。

## 45. 外部回链 query string 保留（QUERY-STRING-RETAIN）🆕v4.35

> 与 B-REVIEW-175（backend 回链 URL 构造审查，v4.35 待落地）/ F-REVIEW-133（前端 query string 保留审查，v4.39 待落地）对应。

从外部链接（通知 / 邮件 / 二维码 / 公网 URL）回链进入应用的路由，必须完整保留 URL 中的 query string（如 `?task_id=xxx&item_id=yyy&error_code=zzz`），禁止 URL 同步 Hook 只取 pathname 丢失 query string，导致下游组件读不到业务参数。

1. **回链路由识别**：从 `config.yaml#external_callback_query_retention.callback_routes` 读取需要保留 query string 的路由列表
2. **URL 拼接规则**：URL 同步 Hook 在计算「当前路径」时必须 `location.pathname + location.search`，依赖数组必须包含 `location.search`
3. **路径匹配剥离**：路径查找函数（如 `findSheetMeta`）必须先 `path.split('?')[0].split('#')[0]` 剥离 query string 与 hash 再匹配
4. **下游消费契约**：回链页面组件必须能从 `useSearchParams` / `useLocation().search` 读取 query string 参数
5. **配置驱动**：回链路由列表、query string 字段名清单、剥离规则从 config 读取

**关键约束**：
- URL 同步 Hook 依赖数组缺 `location.search` → 视为违规（query string 变化不触发同步）
- 路径查找函数未剥离 query string 直接匹配 → 视为违规（带 `?xxx` 的 path 无法精确匹配）
- 回链路由列表硬编码在 Hook 中 → 视为违规（应从 config 读）
- 回链页面组件无法从 `useSearchParams` 读到 query string → 配置契约破裂

**判断信号**：
- `grep "location.pathname" frontend/src/hooks/` 但同函数无 `location.search` → query string 丢失
- `grep "findSheetMeta\|findRouteMeta" frontend/src/` 函数体内无 `split('?')` → 剥离缺失
- `grep "useEffect.*location.pathname" frontend/src/hooks/useSheetSync.ts` 依赖数组无 `location.search` → 依赖不全
- 用户反馈"从通知点击进入页面后参数丢失" → query string 未保留

**适用**：从外部通知 / 邮件 / 二维码 / 公网 URL 回链进入应用的路由（依赖 query string 传 task_id / item_id / error_code / token）；任何 URL 同步 Hook 处理带参数路由的场景。
**不适用**：纯内部导航（用户点击菜单，无 query string）；纯 `:param` 路径参数路由（参数在 pathname 中）；纯 Hash 路由（query string 不在 pathname 中）；纯服务端路由（无前端 Hook 层）。

**历史教训**：`/confirm-buy?task_id=xxx&item_id=yyy` 回链路由，`useSheetSync` 计算路径时只用 `location.pathname`，丢失 `?task_id=xxx`，导致 `ConfirmBuy` 组件读 `useSearchParams` 时 task_id 为 null，无法加载确认抢单数据。修复：path 改为 `location.pathname + location.search`，依赖数组加入 `location.search`，并建立 #45 强制保留规则。

## 46. 测试同步责任原则（TEST-SYNC-RESPONSIBILITY）🆕v4.35

> 与 B-REVIEW-176（backend 接口签名变更同步审查，v4.35 待落地）/ F-REVIEW-134（前端异步函数调用签名匹配审查，v4.39 待落地）对应。

后端接口签名变更（新增 / 删除 / 重命名参数）、异步同步重构（async → sync 或反之）、mock 字段集与生产 Pydantic 模型同步时，必须同步更新所有调用方测试，禁止「改了生产代码忘了改测试」导致测试失败或假阳性。

1. **签名变更同步**：方法签名新增参数后必须 grep 所有调用点（包括测试中的 mock 调用）确认传递新参数
2. **异步同步重构同步**：`async def` → `def` 或反之时，测试中的 `AsyncMock` ↔ `MagicMock` 必须同步切换
3. **mock 字段集同步**：测试 mock 数据必须与生产 Pydantic 模型字段集 1:1 对齐，禁止用 `as ModelType` 类型断言绕过完整性检查
4. **外部依赖隔离同步**：测试中依赖外部资源（keyring / env / 文件系统 / 网络）时必须 patch 为 None 或 mock，禁止依赖生产 fallback 导致测试不可重复
5. **配置驱动**：签名变更检查点、mock 类型映射表、外部依赖类型清单从 `config.yaml#test_synchronization` 读取

**关键约束**：
- 方法签名新增参数但测试调用未传新参数 → 视为违规（`TypeError: missing required positional argument`）
- 生产代码 `async def` 但测试用 `MagicMock`（或反之）→ 视为违规（mock 类型不匹配）
- mock 数据用 `as Item` / `as Task` 绕过字段检查 → 视为违规（与 B-REVIEW-TEST-MOCK-SYNC 一致）
- 测试依赖 keyring fallback → 视为违规（测试环境不可重复）
- 检查点清单硬编码在代码中 → 视为违规（应从 config 读）

**判断信号**：
- `git diff` 显示生产代码方法签名变更但同 PR 内 `tests/` 无对应修改 → 同步缺失
- `grep "AsyncMock" tests/` 但生产代码对应方法已改为 `def` → mock 类型不匹配
- `grep "as Item\b\|as Task\b\|as Order\b" tests/` → 类型断言绕过字段检查
- `grep "get_secret\|os.environ\.\[" tests/` 但无 `patch(..., return_value=None)` → 外部依赖未隔离
- 测试在 CI 通过但本地失败（或反之）→ 环境依赖问题

**适用**：后端接口签名重构（新增 / 删除 / 重命名参数）；async / await 重构（同步异步切换）；测试 mock 数据与生产 Pydantic 模型对齐；外部依赖（keyring / env / 文件系统 / 网络）测试隔离。
**不适用**：纯内部实现重构（不改变接口签名）；新增功能（不破坏现有测试）；一次性验证脚本（无长期维护成本）。

**历史教训**：`manual_takeover` 接口签名加了 `request` 参数（用于多用户隔离读取 `request.state.user_id`），但 `test_manual_takeover_lock.py` 未传 `request`，触发 `TypeError: missing 1 required positional argument: 'request'`。修复：创建 `mock_request = MagicMock()` 并设置 `mock_request.state.user_id = "default"` 后传入。同期 `worker.py` 重构为同步代码后 `test_dingtalk_notify_integration.py` 仍用 `AsyncMock` 导致断言失败，改为 `MagicMock` 后通过。建立 #46 强制同步规则。

## 47. 外部依赖隔离测试可重复性（EXTERNAL-DEP-ISOLATION）🆕v4.35

> 与 B-REVIEW-177（backend 外部依赖隔离审查，v4.35 待落地）/ F-REVIEW-135（前端 mock 类型与生产同步审查，v4.39 待落地）对应。

测试中依赖外部资源（keyring / 环境变量 / 文件系统 / 网络 / 系统 API）时必须显式 patch 为 None 或 mock，禁止依赖生产代码的 fallback 机制（如 keyring 不可用时回退到 env / yaml），避免测试环境与生产环境配置不一致导致测试不可重复（CI 通过本地失败或反之）。

1. **外部依赖清单识别**：从 `config.yaml#external_dependency_isolation.dependency_types` 读取外部依赖类型清单（keyring / env / file / network / system_api）
2. **patch 强制**：测试中调用任何外部依赖函数（如 `get_secret` / `os.environ[...]` / `Path(...).read_text()` / `httpx.get`）必须 `with patch(..., return_value=None)` 或 `MagicMock()` 显式隔离
3. **fallback 禁用**：禁止依赖生产代码的 fallback（如 `secret = get_secret(name) or os.environ.get(name) or read_from_yaml(name)`），测试中必须 patch 全部 3 层 fallback
4. **可重复性验证**：测试在「无外部依赖」环境下（如 Docker 容器无 keyring / 无 env / 无网络）必须仍能通过
5. **配置驱动**：依赖类型清单、隔离策略映射表、fallback 层数从 config 读取

**关键约束**：
- 测试中调用 `get_secret` 但无 `patch("...get_secret", return_value=None)` → 视为违规
- 测试中 `os.environ["XXX"]` 但无 `monkeypatch.setenv` 或 `patch.dict(os.environ, ...)` → 视为违规
- 测试在 CI 通过但本地失败（或反之）→ 视为环境依赖问题
- 依赖类型清单硬编码在测试中 → 视为违规（应从 config 读）

**判断信号**：
- `grep "get_secret\|keyring\.get_password" tests/` 但同测试无 `patch` → keyring fallback 未隔离
- `grep "os\.environ\[" tests/` 但同测试无 `monkeypatch\.setenv\|patch\.dict` → env 依赖未隔离
- `grep "Path\([^)]*\)\.read_text\(\)\|open\([^)]*\)\.read\(\)" tests/` 但无 `tmp_path` fixture → 文件系统依赖未隔离
- `grep "httpx\.get\|requests\.get\|aiohttp\.ClientSession" tests/` 但无 `respx` / `responses` / `MagicMock` → 网络依赖未隔离
- 测试结果随环境变化（CI vs 本地 / Windows vs Linux）→ 环境依赖问题

**适用**：依赖 keyring / 环境变量 / 文件系统 / 网络 / 系统 API 的测试；CI/CD 需可重复的场景；跨平台测试（Windows / Linux / macOS）。
**不适用**：纯函数测试（无外部依赖）；使用 pytest fixture 已隔离的测试（fixture 内部已 patch）；一次性验证脚本（无长期维护成本）；集成测试（故意依赖真实外部资源）。

**历史教训**：`test_notifier_new_channels.py` 中 `DingTalkNotifier(webhook_url="...", secret="")` 测试期望 `secret=""` 时不发送请求，但生产代码 `get_secret` 在 keyring 不可用时 fallback 到 keyring 真实值（测试机已配置 dingtalk secret），导致 `secret=""` 但实际读到 keyring 中的 secret，触发真实钉钉请求，断言失败。修复：在两个测试函数中都加 `with patch("...dingtalk.get_secret", return_value=None):` 显式隔离。建立 #47 强制隔离规则。

> 📖 详细测试同步责任原则、签名变更检查点、mock 类型映射表、外部依赖隔离策略、配置节点定义见 [test-synchronization-and-isolation.md](test-synchronization-and-isolation.md)。

---

# 调度器运行时治理元规范（48-51）🆕v4.36.0

> 基于 2026-07-07 "任务管理自动执行逻辑审查"修复的 5 个问题（BatchRefreshScheduler 运行时禁用无效 / CookieSyncScheduler 无法运行时禁用 / scheduler.py 异常重试等待硬编码 300s / `_resume_cooldown` 字典内存泄漏 / Cron 模式无最小间隔校验），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，提炼 4 条新元规范。门槛校验：#48/#49/#50 各有 ≥3 个相似 bug 达标立正式规范，#51 仅 1 个相似 bug 按门槛规则 #36 标 experimental 标签预沉淀。

## 48. 调度器运行时开关对称性（SCHEDULER-RUNTIME-TOGGLE-SYMMETRY）🆕v4.36

> 与 B-REVIEW-178（backend 调度器开关对称性审查）/ F-REVIEW-136（前端调度器状态同步审查）对应。

调度器（APScheduler BackgroundScheduler/AsyncIOScheduler）的 `update_config(enabled=False)` 必须立即生效——调用 `remove_job(job_id)` 移除已注册 job + job 函数入口 `if not self._enabled: return` 双重检查；`update_config(enabled=True)` 必须恢复 job（`add_job(...)` 或 `resume_job(...)`）。开关操作必须对称：禁用即移除、启用即恢复，禁止"禁用只设标志位不移除 job"或"启用只设标志位不恢复 job"的不对称实现。

1. **禁用立即生效**：`update_config(enabled=False)` 必须在同一个方法内完成"设标志位 + remove_job"两步操作，禁止只设标志位依赖 job 函数入口检查兜底（job 函数入口检查是第二道防线，不是第一道）
2. **入口 double-check**：job 函数入口必须 `if not self._enabled: logger.warning("调度器已禁用但 job 仍触发，检查 update_config 实现"); return`，作为 remove_job 失败/时序竞态的兜底
3. **启用恢复 job**：`update_config(enabled=True)` 必须调用 `add_job(...)` 或 `resume_job(job_id)` 重新注册/恢复 job，禁止只设标志位期望"下次 job 触发时自动恢复"
4. **开关状态可查询**：调度器必须提供 `is_enabled() -> bool` 方法供 API 层查询当前状态，禁止 API 层直接访问 `_enabled` 私有字段
5. **配置驱动**：`enabled` 字段必须从 `config.yaml` 的对应节点读取（如 `batch_refresh.enabled` / `cookie_sync.enabled`），运行时 `update_config` 修改后必须同步写回 config 持久化（参考 B-REVIEW-CONFIG-DRIVEN-TOGGLE）

**关键约束**：
- `update_config(enabled=False)` 后 `scheduler.get_job(job_id)` 仍返回非 None → 视为 CRITICAL（禁用未生效）
- `update_config(enabled=True)` 后 `scheduler.get_job(job_id)` 返回 None 且无 `add_job` 调用 → 视为 CRITICAL（启用未恢复）
- job 函数入口无 `if not self._enabled: return` → 视为 WARNING（缺第二道防线）
- API 层直接访问 `scheduler._enabled` → 视为 WARNING（应通过 `is_enabled()` 方法）

**判断信号**：
- `grep "def update_config" <scheduler_file>` 缺 `remove_job` 或缺 `add_job`/`resume_job` → 开关不对称
- `grep "def _run_.*_job" <scheduler_file>` 缺 `if not self._enabled` → 缺入口 double-check
- `grep "scheduler\._enabled\|scheduler\.enabled" routes/` → API 层直接访问私有字段

**适用**：所有 APScheduler 调度器（BackgroundScheduler/AsyncIOScheduler）；具有 `enabled` 配置开关的后台任务；运行时可动态启停的调度器（如批量采集/Cookie 同步/状态回查）。
**不适用**：一次性任务（无 `enabled` 字段）；启动时确定整个生命周期不启停的调度器（如系统监控）；外部托管调度器（如 celery beat，由外部进程管理）。

**历史教训**：`BatchRefreshScheduler.update_config(enabled=False)` 只设 `self._enabled = False` 标志位，未调用 `scheduler.remove_job()`，APScheduler 已注册的 job 仍按 trigger 触发，触发后 job 函数入口也无 double-check，导致禁用后仍持续执行批量采集。同期 `CookieSyncScheduler` 完全没有 `_enabled` 字段和 `update_config` 方法，配置开关形同虚设。修复：两个调度器都加 `_enabled` 字段 + `update_config` 方法（禁用即 remove_job、启用即 add_job）+ job 函数入口 double-check。建立 #48 强制对称规则。

## 49. 时间参数配置化（TIME-PARAM-CONFIG-DRIVEN）🆕v4.36

> 与 B-REVIEW-179（backend 时间参数配置化审查）/ F-REVIEW-137（前端轮询间隔配置化审查）对应。

异常重试等待秒数、轮询间隔、超时秒数、冷却期等时间参数必须从 `config.yaml` 读取，禁止在代码中硬编码字面量数字（如 `time.sleep(300)` / `await asyncio.sleep(60)` / `timeout=30`）。配置类（Pydantic BaseModel）必须设 `ge`/`le` 边界值校验，读取时按 #42 配置化阈值兜底范式用 `try/except` 包裹提供默认值。

1. **时间参数清单识别**：从 `config.yaml#time_param_config_driven.param_types` 读取需配置化的时间参数类型清单（retry_wait / poll_interval / timeout / cooldown / backoff_base / max_backoff）
2. **配置读取强制**：所有 `time.sleep()` / `asyncio.sleep()` / `timeout=` / `wait_for(timeout=)` 的时间参数必须从 `get_config()` 读取，禁止字面量数字
3. **边界值校验**：Pydantic 配置类必须用 `Field(300, ge=10, le=3600)` 标注边界值，超出范围触发 ValidationError
4. **默认值兜底**：配置读取失败（如配置文件缺失/字段未定义）必须 `try/except` 兜底默认值（参考 #42 配置化阈值兜底范式），禁止配置缺失即崩溃
5. **配置驱动**：参数类型清单、边界值、默认值从 `config.yaml#time_param_config_driven` 节点管理

**关键约束**：
- `grep "time\.sleep\([0-9]" <file>` 命中 → 视为 CRITICAL（硬编码 sleep）
- `grep "asyncio\.sleep\([0-9]" <file>` 命中 → 视为 CRITICAL（硬编码 await sleep）
- `grep "timeout=[0-9]" <file>` 命中 → 视为 CRITICAL（硬编码 timeout）
- Pydantic 配置类时间字段无 `ge`/`le` → 视为 WARNING（缺边界校验）

**判断信号**：
- `grep "time\.sleep\|asyncio\.sleep" <file>` 参数为字面量数字 → 硬编码
- `grep "Field\(.*ge=.*le=" <config_file>` 缺时间字段 → 边界校验缺失
- `grep "get_config\(\)\.\w+\.\w+_seconds" <file>` 但无 `try.*except` 包裹 → 缺兜底

**适用**：所有 `time.sleep` / `asyncio.sleep` / `timeout` / `wait_for(timeout=)` 调用；异常重试/退避策略；轮询/心跳间隔；超时控制；冷却期/防抖期。
**不适用**：单元测试中的 `time.sleep(0.1)`（测试固定延迟）；性能基准测试中的精确计时；日志刷新间隔（<100ms 无业务影响）；UI 动画时长（前端 CSS transition）。

**历史教训**：`scheduler.py` 的 `_compute_next_wait_seconds` 异常重试等待硬编码 `return 300`，导致所有任务异常后必须等 5 分钟才能重试，无法根据业务场景调整。同期 `cookie_sync_scheduler.py` 的同步间隔硬编码在代码中，`batch_refresh_scheduler.py` 的失败重试等待也是字面量数字。修复：在 `TaskSchedulerConfig` 加 `error_retry_wait_seconds: int = Field(300, ge=10, le=3600)` 字段，所有硬编码改为 `get_config().task_scheduler.error_retry_wait_seconds`。建立 #49 强制配置化规则。

## 50. 长生命周期对象状态清理（LIFECYCLE-RESOURCE-CLEANUP）🆕v4.36

> 与 B-REVIEW-180（backend 长生命周期对象状态清理审查）/ F-REVIEW-138（前端长生命周期 Hook cleanup 审查）对应。

长生命周期对象（scheduler / container / registry / manager）持有 task 级或 session 级状态字典（如 `_resume_cooldown: dict[str, float]` / `_last_failure_reason: dict[str, str]` / `_task_status_cache: dict[str, dict]`）时，必须提供 `drop_task_state(task_id: str) -> None` 方法，DELETE API 删除 task 时调用该方法清理对应状态，避免字典无限增长导致内存泄漏。

1. **状态字典识别**：长生命周期对象的 `__init__` 中所有 `dict[str, ...]` 类型字段视为状态字典，必须支持按 task_id 清理
2. **drop_task_state 方法签名**：`def drop_task_state(self, task_id: str) -> None: ...`，内部遍历所有状态字典 `self._resume_cooldown.pop(task_id, None)` / `self._last_failure_reason.pop(task_id, None)` 等
3. **DELETE API 调用**：`DELETE /api/tasks/{task_id}` 和 `DELETE /api/tasks/batch` 路由必须调用 `container.scheduler.drop_task_state(task_id)`，与 DB 删除操作配对执行
4. **异常容错**：`drop_task_state` 内部 `pop` 操作必须 `try/except Exception: logger.debug(...)` 容错，不阻断主流程（DB 删除已成功，状态清理失败仅记日志）
5. **配置驱动**：状态字典清单、清理策略（lazy/active）、清理触发点（DELETE API/scheduler shutdown/定期扫描）从 `config.yaml#lifecycle_resource_cleanup` 节点管理

**关键约束**：
- 长生命周期对象 `__init__` 有 `self._xxx: dict[str, ...]` 但无 `drop_task_state` 方法 → 视为 CRITICAL（状态字典无清理入口）
- `grep "def delete_task\|def unregister" <route_file>` 无 `drop_task_state` 调用 → 视为 CRITICAL（DELETE 未清理状态）
- `drop_task_state` 内 `pop` 操作无 `try/except` → 视为 WARNING（清理失败可能阻断主流程）

**判断信号**：
- `grep "self\._\w*: dict\[str," <scheduler_file>` 命中 → 状态字典识别
- `grep "def drop_task_state" <scheduler_file>` 无匹配 → 缺清理方法
- `grep "def delete_task" <route_file>` 但无 `drop_task_state` → DELETE 未清理

**适用**：长生命周期对象（scheduler / container / registry / manager / singleton service）；持有 `dict[str, ...]` 状态字段的组件；task 级或 session 级状态缓存；DELETE API 删除资源的场景。
**不适用**：短生命周期对象（请求级 / 函数级局部变量）；无状态服务（stateless）；只读缓存（never expire，如配置缓存）；测试 fixture（测试结束自动清理）。

**历史教训**：`scheduler.py` 的 `_resume_cooldown: dict[str, float]` 在 task 异常 pause 后写入冷却时间戳，但 DELETE API 删除 task 时未清理该字段，长期运行后字典无限增长（每个已删除 task 留一条记录）。同期 `_last_failure_reason: dict[str, str]` 和 `_task_status_cache: dict[str, dict]` 也有同样问题。修复：在 `scheduler.py` 加 `drop_task_state(task_id)` 方法遍历清理所有状态字典，`api_tasks.py` 的 `delete_task` 和 `batch_delete_tasks` 路由调用该方法。建立 #50 强制清理规则。

## 51. 用户输入时间表达式校验（CRON-MIN-INTERVAL-CHECK）🆕v4.36 experimental

> 与 B-REVIEW-181（backend cron 表达式最小间隔审查）/ F-REVIEW-139（前端 cron 表达式校验审查）对应。
> experimental 标签：仅 1 个相似 bug（Cron 模式无最小间隔校验），按 #36 门槛规则未达标（≥3 个相似 bug 才立正式规范），标 experimental 标签预沉淀，1 季度观察期内若再出现 ≥2 个相似 bug 则升级为正式规范。

用户输入的 cron 表达式（如 task 的 `schedule_cron` 字段）必须校验最小间隔 ≥ 反爬最小延迟（`antidetect.min_delay_ms / 1000` 秒），禁止 `* * * * *`（每秒执行）等滥用表达式导致触发反爬封禁。校验在 `add_job` 前执行，校验失败返回结构化错误不抛异常。

1. **cron 表达式解析**：使用 `apscheduler.triggers.cron.CronTrigger.from_crontab(cron_expr)` 解析表达式，解析失败返回 `{"valid": False, "reason": "cron 表达式语法错误"}`
2. **最小间隔计算**：解析后计算连续两次触发的时间差最小值（`_get_min_cron_interval_seconds(cron_expr) -> float`），通过枚举 24 小时内所有触发点取最小差值
3. **阈值校验**：最小间隔 < `get_config().antidetect.min_delay_ms / 1000` 视为滥用，返回 `{"valid": False, "reason": "cron 最小间隔 X 秒 < 反爬最小延迟 Y 秒"}`；阈值配置读取失败回退 10 秒默认值
4. **配置读取容错**：`_get_min_cron_interval_seconds` 内 `try/except` 包裹 `get_config()` 调用，配置缺失时回退 `return 10.0`（参考 #42 配置化阈值兜底范式）
5. **配置驱动**：最小间隔阈值、回退默认值、校验开关从 `config.yaml#cron_min_interval_check` 节点管理

**关键约束**：
- `grep "CronTrigger\.from_crontab" <file>` 但无 `_get_min_cron_interval_seconds` 调用 → 视为 WARNING（缺最小间隔校验）
- `add_job` 前无 cron 表达式校验 → 视为 WARNING
- 校验函数内 `raise ValueError` → 视为 WARNING（应返回结构化 dict 不抛异常，参考 #41）

**判断信号**：
- `grep "CronTrigger" <file>` 无 `min_interval` 校验 → 缺最小间隔校验
- `grep "schedule_cron" <file>` 但无 `validate_cron` 调用 → 用户输入未校验
- `grep "def _get_min_cron_interval_seconds" <file>` 无 `try.*except` → 配置读取无容错

**适用**：用户输入的 cron 表达式（task 的 `schedule_cron` 字段）；APScheduler CronTrigger 调度器；可能触发反爬的定时任务（采集/同步/轮询）。
**不适用**：interval 触发器（已通过 `seconds=` 参数控制间隔）；date 触发器（一次性执行无间隔概念）；内部系统调度（非用户输入，已通过 code review 保证合理）；测试用 cron 表达式（测试环境无反爬风险）。

**历史教训**：task 的 `schedule_cron` 字段接受任意 cron 表达式，用户配置 `* * * * *`（每分钟执行）导致批量采集每分钟触发一次，远低于反爬最小延迟（10 秒），触发闲鱼反爬封禁。修复：在 `scheduler.py` 加 `_compute_next_wait_seconds` 调用 `_get_min_cron_interval_seconds` 校验最小间隔，小于阈值时返回结构化错误不创建 job。建立 #51 强制校验规则（experimental，待 1 季度观察期升级）。

---

# 工程闭环元规范（52-56）🆕v4.37

> 以下 5 条元规范从 2026-07-07 修复的「价格过滤失效 / SEMI_AUTO 模式退化 / 外部 DOM 解析失败 / 测试 mock 错配 / 多参数 UI 不透明」5 类问题中提炼，使用 Sequential Thinking 4 维度复盘法（成功步骤 / 不确定性与失败点 / 可抽象的固定流程与判断逻辑 / 适用场景与不适用场景）抽象而成。
>
> 与 v4.36.0 的 #48 调度器运行时开关对称性（SCHEDULER-RUNTIME-TOGGLE-SYMMETRY）视角互补：v4.36.0 #48 关注"update_config + double-check"对称性，本批次不重复定义调度器开关规范。
>
> 命名空间与配置驱动：所有阈值（参数名白名单 / mock 类型映射表 / fallback 层级数）均在 `config.yaml` 对应节点管理，禁止硬编码。

## 52. 参数链闭环验证（PARAM-CHAIN-EXEC）🆕v4.37

> 与维度 19 API 设计（B-REVIEW-177）/ 维度 7 API 契约（F-REVIEW-144）对应。

过滤类参数（filter / constraint 语义）从 API 接收后必须存在对应的消费点（函数调用 / SQL WHERE / 条件分支），禁止"参数已接收但未被消费"。

1. **接收点验证**：API endpoint 函数签名声明参数后，函数体内必须存在该参数的消费逻辑
2. **消费点验证**：参数必须实际参与过滤条件构建（WHERE 子句 / 条件分支 / 函数调用参数）
3. **结果集验证**：必须存在单元测试验证"传参 vs 不传参"结果集差异，否则视为过滤未生效
4. **元数据参数豁免**：分页参数（page / page_size / limit / offset）与排序参数（sort / order）属于标识/定位类参数，不在本规范范围

**关键约束**：
- 参数出现在函数签名 + return dict 中但未出现在过滤逻辑 → 视为"参数悬挂"违规
- 参数命名暗示过滤语义（含 `filter_` / `range_` / `min_` / `max_` / `ratio_` 前缀）必须闭环
- 元数据参数白名单在 `config.yaml` 管理，禁止硬编码

**判断信号**：
- `grep "<param_name>" <file>` 仅命中函数签名和 return 语句但未命中函数调用 → 视为可疑
- API 接收 `market_ratio` 参数但未调用 `PriceStrategy.check(market_ratio=...)` → 违规
- 单元测试无 `with_param` / `without_param` 对比用例 → 视为闭环验证缺失

**适用**：所有有过滤参数的列表查询 API（list_evaluations / list_items / search_* / list_orders）、PATCH/PUT 接口的可空字段
**不适用**：GET 单个资源详情（无过滤）、DELETE 接口（参数仅定位资源）、仅作元数据返回的字段（total_count）、创建类 POST 接口

**历史教训**：`evaluations_list.py` 接收 `market_ratio=0.85` 参数但未调用 `PriceStrategy.check`，导致调整到 0.85 后仍能查出价格上限 800 的商品。修复：新增 `_resolve_market_ratio` / `_compute_eval_market_median` / `_filter_market_ratio` 三个辅助函数形成闭环。

> 📖 详见 [config-driven.md](../assets/guides/coding-rules/config-driven.md) step 189。

## 53. 业务模式纵向链路一致性（MODE-VERTICAL-CHAIN）🆕v4.37

> 与维度 19 状态管理（B-REVIEW-183，待落地）/ 维度 4 业务逻辑（F-REVIEW-141，待落地）对应。

业务模式枚举（如 AUTO / SEMI_AUTO / MANUAL）必须在 6 个层纵向一致传递：决策层 → 事件层 → 通知层 → 路由层 → 接口层 → 状态机层。任一层缺失即模式退化。

**与 #40 MULTI-FIELD-LINKED-SWITCH 的边界**：
- #40 关注"字段间横向联动"（主开关 + 子过滤器的优先级矩阵）
- 本规范关注"模式枚举纵向链路"（同一 mode 值在 6 层是否都引用）

1. **决策层**：`_should_buy()` 等决策函数必须根据 mode 返回不同决策
2. **事件层**：业务事件 payload 必含 mode 字段（如 `EVAL_PASSED` 事件含 `task_mode`）
3. **通知层**：不同 mode 渲染不同模板（SEMI_AUTO 必含确认链接）
4. **路由层**：前端为每个 mode 的后续动作提供对应路由（如 `/confirm-buy`）
5. **接口层**：后端为每个 mode 的后续动作提供 endpoint
6. **状态机层**：必要时引入中间状态（如 `pending_confirm`）防越权

**关键约束**：
- grep mode 枚举值，每个值必须在 6 个层都至少出现 1 次
- 中间状态必须显式声明，禁止用临时变量隐式表达
- mode 字段名在 6 层必须严格一致（snake_case 透传，禁止 camelCase 转换）

**判断信号**：
- `grep "task_mode\|mode.*AUTO\|mode.*MANUAL"` 在事件 payload / 通知模板 / 路由 / endpoint 中未命中 → 链路断裂
- 决策函数返回值与 mode 无关 → 决策层未实现
- 通知模板对所有 mode 渲染相同内容 → 通知层未实现

**适用**：所有引入 mode 枚举且影响后续行为的业务（任务执行模式、采集模式、通知模式、订单确认模式）
**不适用**：纯展示型 mode 字段（仅日志记录不影响流转）、内部状态字段（不跨层传递）、单一布尔开关（无枚举语义，归 #40）

**历史教训**：SEMI_AUTO 模式退化为 CONFIRM/NOTIFY，因为：`_should_buy()` 返回 False / 通知模板缺确认链接 / 事件 payload 缺 `task_mode` / 缺 `pending_confirm` 中间状态 / 缺确认接口。修复：5 层全补齐（决策/事件/通知/路由/接口）+ 引入 `pending_confirm` 状态。

> 📖 详见 [state-management.md](../assets/guides/coding-rules/state-management.md) step 190。

## 54. 外部页面解析容错（PARSER-FALLBACK-CHAIN）🆕v4.37

> 与维度 13 浏览器自动化（B-REVIEW-179）对应。

解析不受控的第三方页面 DOM 必须采用多级 fallback selector 策略，任一 selector 命中即返回，全部失败才触发 debug dump。

1. **三级 fallback**：按"结构化 selector → 属性 selector → 文本扫描"顺序尝试
2. **debug dump 触发条件**：基于业务语义（如 `on_sale == 0`）而非实现细节（如 `sold == 0`）
3. **selector 列表配置化**：所有 selector 字符串在 `config.yaml` 管理，禁止硬编码
4. **降级链日志合并**：与 #32 一致，多 selector 尝试的中间步骤 DEBUG 化，最终失败 WARNING

**关键约束**：
- 单一 selector 无 try/except fallback → 视为风险
- selector 硬编码在代码中 → 违规（必须配置化）
- debug dump 触发条件耦合实现细节 → 违规

**判断信号**：
- `grep "querySelector\|querySelectorAll\|select\|css"` 在外部页面解析上下文，无 `try/except` 或 `or []` fallback → 违规
- `grep "tabItem\|tab.*role.*tab\|tab.*class"` selector 字符串硬编码 → 违规
- debug dump 条件含 `sold == 0`（实现细节）而非 `on_sale == 0`（业务语义）→ 违规

**适用**：所有解析闲鱼/淘宝/天猫/京东等第三方页面的代码（`_detail.py` / `_parse_*` 函数 / Playwright page.evaluate 返回值解析）
**不适用**：解析自己生成的内容（本地 HTML 模板）、解析 API 返回的 JSON（结构稳定）、解析固定 schema 的 XML/YAML

**历史教训**：`_parse_sale_counts_from_tabs` 仅依赖 `tabItem` class 名，闲鱼页面 DOM 结构变化导致 `on_sale=0` 和 `sold=0`。修复：实现三级 fallback（`[class*='tabItem']` → `[class*='tab'][role='tab']` → 文本前缀扫描 div/span/a），收紧 debug dump 触发条件从 `on_sale==0 or sold==0` 改为 `on_sale==0`（因为 `sold==0` 是新 UI 的预期行为）。

> 📖 详见 [browser-automation.md](../assets/guides/coding-rules/browser-automation.md) step 191。

## 55. mock 同步与边界精确性（MOCK-SYNC-BOUNDARY）🆕v4.37

> 与维度 20 测试建议（B-REVIEW-180）/ 维度 12 可测试性（F-REVIEW-146）对应。

**与 #47 EXTERNAL-DEP-ISOLATION 的边界**：
- #47 关注"是否要 patch"（强制 patch 外部依赖）
- 本规范关注"如何 patch"（patch 的类型/边界/字段/副作用）

修改被测代码后必须同步 mock：mock 类型与被 mock 对象的同步/异步特性必须一致，patch 必须 patch 实际调用点而非定义点，mock 数据必须覆盖完整字段集。

1. **类型匹配**：同步函数用 `MagicMock`，异步函数用 `AsyncMock`，禁止混用
2. **patch 边界**：patch 必须 patch 实际调用点（如 `worker.get_secret`）而非定义点（如 `secrets.get_secret`）
3. **字段完整性**：mock 数据必须覆盖被测代码访问的所有字段，禁止部分 mock
4. **副作用验证**：测试必须断言"副作用未发生"（如未发起真实网络请求 / 未写文件 / 未发邮件）

**关键约束**：
- 同步函数用 `AsyncMock` → CRITICAL（mock 类型错配）
- 异步函数用 `MagicMock` → CRITICAL
- patch 路径与实际调用路径不一致 → WARNING
- mock 数据缺字段 → 测试可能 NPE，视为不完整

**判断信号**：
- `grep "AsyncMock" <test_file>` 但被 mock 函数是同步函数（无 `async def`）→ 违规
- `grep "MagicMock" <test_file>` 但被 mock 函数是 `async def` → 违规
- `patch("module.function")` 但实际调用是 `from module import function; function()` → patch 边界错误

**适用**：所有 unit test / 集成测试中的 mock 替身
**不适用**：E2E 测试（应使用真实环境）、快照测试（snapshot test）

**历史教训**：`test_dingtalk_notify_integration.py` 用 `AsyncMock` 但 `worker.py` 的 `filter_new` 已改为同步实现，导致 `await` 在同步对象上失败。`test_notifier_new_channels.py` patch `get_secret` 位置错误导致 webhook_url/secret 实际不为空，测试发起真实钉钉请求。修复：AsyncMock 改 MagicMock 对齐同步实现 / patch get_secret 返回 None 确保真正为空 / test_manual_takeover_lock 构造 mock request 含 user_id。

> 📖 详见 [testing.md](../assets/guides/coding-rules/testing.md) step 192。

## 56. 过滤结果透明化 UI（FILTER-RESULT-TRANSPARENCY-UI）🆕v4.37

> 与维度 7 API 契约（F-REVIEW-147）对应。

列表查询 UI 同时有 ≥2 个过滤参数（价格区间 + 市场比例 + 任务范围）时，必须透明化展示当前生效的过滤规则组合，否则用户无法理解"为何查不到数据"。

**与 #40 MULTI-FIELD-LINKED-SWITCH 的边界**：
- #40 关注"字段间联动 UI 禁用标识"（开关 disabled 状态）
- 本规范关注"过滤结果透明化展示"（数据被过滤的可见性）

1. **Tooltip 说明**：关键过滤参数提供 Tooltip 说明查询规则（如"价格区间 + 低于市场参考价参数取值"）
2. **filter_summary 三态**：空结果时区分"无数据"vs"被过滤排除"vs"全部数据"三种状态
3. **当前过滤组合展示**：UI 显式列出当前生效的过滤参数组合（如"当前过滤：价格 600-800 + 市场比例 ≤0.85"）
4. **参数语义化**：业务参数（如 `market_ratio` 0.85）应展示语义化文案（如"低于市场参考价 15%"）

**关键约束**：
- UI 同时有 ≥2 个过滤参数但无 tooltip / filter_summary → 透明化不足
- 空结果统一显示"暂无数据"不区分原因 → 违规
- 过滤参数展示仅显示数值不显示语义 → 不友好

**判断信号**：
- `grep "filter.*range\|market.*ratio\|min.*max"` 在列表 UI 但无 `Tooltip` / `filter_summary` → 违规
- `grep "empty.*data\|no.*data"` 但无 `filtered_count` / `total_count` 区分 → 违规
- 参数展示仅 `value` 无 `label` / `description` → 不友好

**适用**：所有多参数列表查询 UI（评估明细 / 商品列表 / 订单列表 / 仪表盘过滤）
**不适用**：单一过滤参数（如仅搜索关键字）、用户主动输入的查询条件（用户已知）、详情页（无过滤）

**历史教训**：用户调整"低于市场参考价"到 0.85 后，评估明细菜单仍能查出价格上限 800 的商品，且 UI 无任何提示当前生效的过滤规则。用户误以为是价格范围 600-800 的问题，实际是 market_ratio 过滤未生效。修复：在价格范围 label 处添加 `QuestionCircleOutlined` 图标 + Tooltip 说明查询规则（价格区间 + 低于市场参考价参数取值）。

> 📖 详见 [frontend-ui.md](../assets/guides/coding-rules/frontend-ui.md) step 193。

---

# 异步与资源安全元规范（57-63）🆕v4.38.0

> 基于 2026-07-08 解决的「async/await 误用、NullPool 性能问题、HTTP 状态码语义模糊、CSS 选择器失效、异常日志丢失 traceback、并发安全 page closure、参数传递缺失、日志质量退化链」8 类问题，使用 Sequential Thinking 8 步复盘法（问题识别 → 根因分析 → 修复方案 → 验证 → 影响评估 → 规范候选 → 落地决策 → 内容设计），新增 7 条元规范（meta-rules #57-63），元规范总数从 56 → 63。
>
> 命名空间与配置驱动：所有阈值（`async_await_check` / `resource_pool_benchmark` / `http_status_code_mapping` / `css_selector_fallback` / `exception_log_semantic` / `external_resource_lifecycle` / `db_write_identity_trace`）均在 `config.yaml` 对应节点管理，禁止硬编码。
>
> 编号说明：step 198-204 / B-REVIEW-182-188 / F-REVIEW-148-151。

## 57. async/await 同步性静态检查（ASYNC-AWAIT-SYNC-CHECK）🆕v4.38

> 与 B-REVIEW-182（backend async/await 同步性审查）/ F-REVIEW-148（前端 async/await 同步性审查）对应。

`async def` 方法体内若不含 `await` 表达式，必须改为同步 `def`；调用点同步移除 `await`。Python 3.14 可能优化无 await 的 async 函数返回 None，导致 `await None` 触发 `TypeError: 'NoneType' object can't be awaited`。

1. **静态检查强制**：所有 `async def` 方法必须检查方法体内是否含 `await` 表达式，无 `await` 则改为 `def`
2. **调用点同步**：方法从 `async def` 改为 `def` 后，所有调用点必须同步移除 `await`
3. **白名单豁免**：`@abstractmethod` 纯接口定义、`__aenter__`/`__aexit__` 上下文管理器、async generator（含 `yield`）可保留 `async def` 无 `await`
4. **AST 分析**：推荐用 AST 分析而非正则，准确识别方法体内是否含 `await` 节点
5. **配置驱动**：白名单装饰器清单、检查开关、严重级别从 `config.yaml#async_await_check` 读取

**关键约束**：
- `async def` 方法体内无 `await` 且不在白名单 → 视为 CRITICAL（Python 3.14 兼容性风险）
- 方法改为 `def` 后调用点仍用 `await` → 视为 CRITICAL（`TypeError: object NoneType can't be awaited`）
- 白名单装饰器硬编码 → 视为违规（应从 config 读）

**判断信号**：
- `grep "async def" <file>` 后检查方法体内是否含 `await`；或用 AST 分析
- `grep "await self._finalize_run\|await self._simple_method" <file>` 但方法体全同步 → 违规
- 方法从 async 改为 sync 但 `grep "await <method_name>"` 仍有命中 → 调用点未同步

**适用**：Python 3.11+ 异步代码，尤其是被 `await` 调用的方法；使用 asyncio 的 FastAPI/uvicorn 项目；含 `async def` 的 worker/scheduler/service 层。
**不适用**：纯接口定义（`@abstractmethod`）、上下文管理器（`__aenter__`/`__aexit__`）、async generator（含 `yield`）、测试代码中的 `async def test_*`（pytest-asyncio 自动处理）。

**反模式**：
```python
# ❌ async def 但方法体全同步，Python 3.14 优化后 await None 触发 TypeError
async def _finalize_run(self, stats: dict) -> None:
    self._stats = stats
    self._persist_to_db(stats)
    logger.info("完成统计")

# 调用点
await self._finalize_run(stats)  # Python 3.14: TypeError: 'NoneType' object can't be awaited
```

**正确模式**：
```python
# ✅ 改为同步 def，调用点移除 await
def _finalize_run(self, stats: dict) -> None:
    self._stats = stats
    self._persist_to_db(stats)
    logger.info("完成统计")

# 调用点
self._finalize_run(stats)
```

**历史教训**：`worker.py` 的 `_finalize_run` 标记为 `async def` 但方法体全同步（仅赋值 + DB 写入 + 日志），Python 3.14 优化后返回 None，`await None` 触发 TypeError 导致调度器崩溃。修复：改为 `def _finalize_run` + 所有调用点移除 `await`。同期发现 3 处类似问题（`_save_progress` / `_update_status` / `_notify_done`），均改为同步。

> 📖 详见 [concurrency.md](../assets/guides/coding-rules/concurrency.md) step 198。

## 58. 资源池配置性能基准与决策（RESOURCE-POOL-BENCHMARK）🆕v4.38

> 与 B-REVIEW-183（backend 资源池配置性能审查）对应。

数据库/HTTP/浏览器资源池配置（如 `poolclass=NullPool` / `QueuePool` / `StaticPool`）必须有性能基准数据支持，docstring 记录选择理由与对比数据。禁止"无说明选 NullPool"导致每次连接都执行初始化开销（如 PRAGMA）。

1. **性能基准强制**：资源池选择必须有性能基准数据支持，记录"NullPool vs QueuePool"的连接建立/复用/销毁开销对比
2. **docstring 记录**：资源池配置代码必须有 docstring 说明选择理由、对比数据、适用场景
3. **开销阈值**：系统层开销（连接建立 + PRAGMA + init SQL）> `config.yaml#resource_pool_benchmark.overhead_threshold_ms`（默认 50ms）时禁止用 NullPool
4. **测试环境豁免**：测试环境可用 StaticPool 保证隔离，但需 docstring 标注"仅测试用"
5. **配置驱动**：开销阈值、池类型清单、基准数据模板从 `config.yaml#resource_pool_benchmark` 读取

**关键约束**：
- `grep "poolclass=" <file>` 无 docstring 说明 → 视为 WARNING（选择理由缺失）
- 慢查询日志中系统层开销 > 50ms 且使用 NullPool → 视为 CRITICAL（性能退化）
- 生产环境用 StaticPool → 视为 CRITICAL（无连接复用）

**判断信号**：
- `grep "poolclass=" <file>` 后检查是否有 docstring 说明；或慢查询日志中系统层开销>50ms
- `grep "poolclass=NullPool" <file>` 但无性能基准 docstring → 违规
- `grep "PRAGMA\|initialization SQL" <file>` 与 `grep "NullPool" <file>` 同时出现 → 性能风险

**适用**：所有资源池选择（NullPool/QueuePool/StaticPool）；含 PRAGMA/init/重试开销的资源初始化；数据库连接池、HTTP 连接池、浏览器实例池。
**不适用**：测试环境（用 StaticPool 保证隔离）、单次请求资源（无复用价值）、内存数据结构（无连接开销）、CLI 一次性脚本（无长期运行需求）。

**反模式**：
```python
# ❌ NullPool 无 docstring 说明，每次连接都执行 5 条 PRAGMA（~100ms 开销）
engine = create_engine(
    "sqlite:///data/xianyu.db",
    poolclass=NullPool,  # 无任何说明
)
```

**正确模式**：
```python
# ✅ QueuePool + docstring 记录选择理由与对比数据
engine = create_engine(
    "sqlite:///data/xianyu.db",
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    # docstring: NullPool 每次新建连接执行 PRAGMA 开销 ~100ms（5 条 PRAGMA），
    # QueuePool 复用连接，性能提升 10-50x。list_and_count_task_links 从 231ms 降至 11.9ms。
)
```

**历史教训**：`db_models.py` 使用 `NullPool` 导致 `list_and_count_task_links` 慢查询 231ms（其中 ~100ms 是 PRAGMA 开销：`PRAGMA journal_mode=WAL` / `PRAGMA foreign_keys=ON` / `PRAGMA synchronous=NORMAL` / `PRAGMA busy_timeout=10000` / `PRAGMA cache_size=-20000`）。改为 `QueuePool(pool_size=5, max_overflow=5, pool_pre_ping=True)` 后降至 11.9ms（19x 提升）。根因：NullPool 每次操作都新建连接并执行 5 条 PRAGMA，QueuePool 复用连接跳过 PRAGMA。

> 📖 详见 [database.md](../assets/guides/coding-rules/database.md) step 199。

## 59. HTTP 状态码精细化映射表（HTTP-STATUS-CODE-MAPPING）🆕v4.38

> 与 B-REVIEW-184（backend HTTP 状态码精细化审查）/ F-REVIEW-149（前端状态码本地化消息审查）对应。
> 与 #8 错误粒度区分的关系：#8 给出"状态码→语义"的通用映射表，本条是**多原因 None 返回值的精细化映射**专项规范。

底层模块返回多原因的 None/错误时，必须建立 `reason_code → status_code` 映射表；底层设置 `last_*_failure_reason`；上游按映射查找状态码；前端按状态码提供本地化消息。禁止"所有 None 一律映射为 410 Gone"导致用户无法区分"商品下架"与"Cookie 过期"。

1. **reason_code 持久化**：底层模块返回 None 时必须设置 `self.last_*_failure_reason`（如 `last_detail_failure_reason`），记录具体原因
2. **映射表强制**：上游必须建立 `_FAILURE_STATUS_MAP = {reason_code: status_code}` 映射表，按 reason 查找状态码
3. **默认状态码兜底**：未知 reason 用默认状态码（如 410），但必须 `logger.warning` 记录未知 reason
4. **前端本地化**：前端按状态码提供本地化消息，禁止用 `detail.includes(...)` substring 判断
5. **配置驱动**：映射表、默认状态码、reason 枚举从 `config.yaml#http_status_code_mapping` 读取

**关键约束**：
- `grep "raise HTTPException(410\|raise HTTPException(502" <file>` 多原因汇聚同一码 → 视为 WARNING（语义模糊）
- 底层返回 None 但无 `last_*_failure_reason` 设置 → 视为 WARNING（原因丢失）
- 前端用 `detail.includes("下架")` 判断 → 视为 CRITICAL（违反 #29 error_code 分支）

**判断信号**：
- `grep "raise HTTPException(410\|raise HTTPException(502" <file>` 后检查是否多原因汇聚同一码
- `grep "last_.*_failure_reason" <file>` 与 `grep "is None" <file>` 配对检查
- `grep "_FAILURE_STATUS_MAP\|_STATUS_MAP" <file>` 无映射表 → 违规

**适用**：所有 HTTP 错误响应；多原因返回 None/错误的底层模块（如 detail() 返回 None 有 10+ 原因：商品下架/Cookie 过期/登录重定向/验证码拦截/页面不存在/网络超时等）。
**不适用**：唯一原因的错误码（如 404 仅表示资源不存在）、内部异常不向用户暴露、纯日志级别错误、健康检查端点（固定 200/503）。

**反模式**：
```python
# ❌ detail() is None 一律映射为 410 Gone，但 detail() 返回 None 有 10+ 原因
detail = await self.container.collector.detail(item_id)
if detail is None:
    raise HTTPException(status_code=410, detail="商品详情页加载失败或已下架")
    # 实际原因可能是 cookie 过期需重新登录，但用户看到"已下架"
```

**正确模式**：
```python
# ✅ reason_code → status_code 映射表 + 底层设置 last_detail_failure_reason
_DETAIL_FAILURE_STATUS_MAP = {
    "home_title_redirect": 403,      # 首页重定向，权限不足
    "login_redirect": 403,           # 登录重定向，权限不足
    "verify_redirect": 441,          # 验证重定向，需刷新 Token
    "item_not_found": 410,           # 商品不存在
    "item_removed": 410,             # 商品已下架
    "anti_crawler": 429,             # 反爬触发
    "network_timeout": 504,          # 网络超时
}

detail = await self.container.collector.detail(item_id)
if detail is None:
    reason = getattr(self.container.collector, "last_detail_failure_reason", "unknown")
    status_code = self._DETAIL_FAILURE_STATUS_MAP.get(reason, 410)
    if reason == "unknown":
        logger.warning(f"detail() 返回 None 但未设置 failure_reason, item_id={item_id}")
    raise HTTPException(status_code=status_code, detail=f"商品详情获取失败: {reason}")
```

**历史教训**：`collection_service.py` 将所有 `detail() is None` 映射为 410 Gone，前端展示"商品详情页加载失败或已下架"。但实际原因可能是 Cookie 过期（需重新登录）、登录重定向（需刷新 Token）、反爬触发（需手动验证）。用户看到"已下架"后误以为商品真的下架，实际重新登录后商品仍在。修复：建立 `_DETAIL_FAILURE_STATUS_MAP` + 底层设置 `last_detail_failure_reason` + 前端按状态码提供本地化消息（410→"商品已下架"、403→"权限不足请重新登录"、441→"Token 过期请刷新"、429→"触发反爬请验证"）。

> 📖 详见 [error-handling.md](../assets/guides/coding-rules/error-handling.md) step 200。

## 60. CSS 选择器多级降级策略（CSS-SELECTOR-FALLBACK）🆕v4.38

> 与 B-REVIEW-185（backend CSS 选择器降级审查）对应。
> 与 #54 外部页面解析容错的关系：#54 给出"三级 fallback selector"的整体框架，本条是**降级策略与 dump 触发条件的细化**。

依赖第三方网站 DOM 的选择器必须有 ≥3 级降级（业务语义 className → HTML role 属性 → 文本内容前缀扫描）；每级失败自动降级；调试 dump 触发条件收窄到核心字段失败，禁止"任一字段失败就 dump"导致 dump 文件泛滥。

1. **三级降级强制**：选择器必须按"业务语义 className → HTML role 属性 → 文本内容前缀扫描"顺序尝试，每级失败自动降级
2. **dump 触发条件收窄**：调试 dump 仅在核心字段（如 `on_sale`）失败时触发，非核心字段（如 `sold`）失败不 dump
3. **选择器配置化**：所有 selector 字符串在 `config.yaml` 管理，禁止硬编码
4. **降级链日志合并**：与 #32 一致，多 selector 尝试的中间步骤 DEBUG 化，最终失败 WARNING
5. **配置驱动**：降级级数、dump 触发条件、选择器清单从 `config.yaml#css_selector_fallback` 读取

**关键约束**：
- `grep "querySelectorAll\|querySelector" <file>` 选择器单一无 fallback → 视为 CRITICAL（改版即失效）
- `grep "tabItem\|tab.*role.*tab\|tab.*class"` selector 字符串硬编码 → 视为违规
- dump 触发条件含 `sold == 0`（非核心字段）→ 视为 WARNING（dump 泛滥）
- dump 文件频繁生成（> `config.yaml#css_selector_fallback.dump_max_per_hour`）→ 视为 WARNING

**判断信号**：
- `grep "querySelectorAll\|querySelector" <file>` 后检查选择器是否单一；或 dump 文件频繁生成
- `grep "tabItem\|tab.*class.*tab" <file>` 无 `try/except` 或 `or []` fallback → 违规
- `grep "dump.*html\|page.content" <file>` 触发条件含非核心字段 → dump 泛滥

**适用**：第三方网站 DOM 解析（闲鱼/淘宝/天猫/京东/第三方 API 返回 HTML）；依赖 className 的选择器；Playwright `page.querySelectorAll` / `page.evaluate` 返回值解析。
**不适用**：自有代码 DOM（可控制稳定性）、ID 选择器（业务语义稳定）、`data-*` 属性选择器（开发者主动标记）、后端 API JSON 解析（结构稳定）、SSR 页面（结构固定）。

**反模式**：
```python
# ❌ 单一选择器，闲鱼改版 className 后失效
tabs = page.querySelectorAll('[class*="tabItem"]')
# 无 fallback，改版后 on_sale=0 sold=0 误报
if not tabs:
    page.content()  # dump 触发条件过宽
```

**正确模式**：
```python
# ✅ 三级降级 + dump 触发条件收窄
# Level 1: 业务语义 className
tabs = page.querySelectorAll('[class*="tabItem"]')
# Level 2: HTML role 属性
if not tabs:
    tabs = page.querySelectorAll('[class*="tab"][role="tab"]')
# Level 3: 文本内容前缀扫描
if not tabs:
    tabs = page.querySelectorAll('div, span, a').filter(el =>
        el.text_content().startswith(("在售", "已售", "想要")))
# dump 仅在核心字段 on_sale 失败时触发（非 sold）
if on_sale == 0:
    logger.warning("on_sale 解析失败，dump 页面")
    dump_page(page, "sale_counts")
```

**历史教训**：`_detail.py` 的 `_parse_sale_counts_from_tabs` 仅依赖 `tabItem` class 名，闲鱼页面 DOM 结构变化后 `on_sale=0` 和 `sold=0`。dump 触发条件设为 `on_sale==0 or sold==0`，但 `sold==0` 是新 UI 的预期行为（新 UI 不显示已售数），导致每次采集都生成 dump 文件，12 小时内累积 500+ dump 文件。修复：实现三级 fallback（`[class*='tabItem']` → `[class*='tab'][role='tab']` → 文本前缀扫描 div/span/a），收紧 dump 触发条件从 `on_sale==0 or sold==0` 改为 `on_sale==0`。

> 📖 详见 [browser-automation.md](../assets/guides/coding-rules/browser-automation.md) step 201。

## 61. 异常日志语义保留规范（EXCEPTION-LOG-SEMANTIC）🆕v4.38

> 与 B-REVIEW-186（backend 异常日志语义审查）/ F-REVIEW-150（前端异常日志语义审查）对应。
> 与 #26 关键路径异常保留 traceback 的关系：#26 聚焦"关键路径"的 `logger.exception()`，本条覆盖**所有 except 块**的日志语义保留。

`except` 块内必须用 `logger.exception('描述')` 保留完整 traceback，禁用 `logger.warning(f'...{e}')` 丢失堆栈；非 `except` 块用 `warning + exc_info=True`；多阶段降级链合并为单条结构化 WARNING。

1. **except 块强制 exception()**：`except` 块内必须用 `logger.exception("描述")` 自动保留完整 traceback（含调用链、异常类型、文件行号）
2. **禁止 warning 丢堆栈**：`except` 块内禁止 `logger.warning(f"操作失败: {e}")`（仅打印异常对象，丢失堆栈）
3. **非 except 块用 exc_info**：非 except 块需记录异常信息时用 `logger.warning("描述", exc_info=True)`
4. **多阶段降级链合并**：同一逻辑链多个 except 的中间步骤 DEBUG 化，最终合并为单条结构化 WARNING（参考 #32）
5. **配置驱动**：禁止模式、必需模式、关键路径函数清单从 `config.yaml#exception_log_semantic` 读取

**关键约束**：
- `except` 块内 `logger.warning(f"...{e}")` → 视为 CRITICAL（丢失 traceback）
- `except` 块内 `logger.error(f"...{e}")` → 视为 CRITICAL（丢失 traceback）
- `except` 块内 `logger.exception(f"...{e}")` → 视为 WARNING（exception 已保留堆栈，但 f-string 冗余）
- 关键路径函数（`critical_path_functions`）的 `except` 块无 `logger.exception` → 视为 CRITICAL

**判断信号**：
- `grep "logger.warning.*f\".*{e}\"" <file>` 或 `grep "logger.exception.*f\"" <file>` 在 except 块内
- `grep "except.*as e:" <file>` 后跟 `logger.warning\|logger.error` 但无 `logger.exception` → 违规
- `grep "logger.error.*f\".*{e}\"" <file>` 在 except 块内 → 违规

**适用**：所有异常处理代码，尤其是关键路径（启动/迁移/初始化）；多阶段降级链路（API→DOM→缓存）；后台任务异常处理；API 路由异常处理。
**不适用**：纯性能日志（无异常场景）、DEBUG 级别日志（仅诊断用）、非 except 块的 warning（用 exc_info=True）、测试代码（`pytest.raises` 期望异常）。

**反模式**：
```python
# ❌ except 块内用 warning(f"...{e}") 丢失 traceback
try:
    result = await self.collector.detail(item_id)
except Exception as e:
    logger.warning(f"获取详情失败: {e}")  # 丢失 traceback，定位问题耗时 30+ 分钟
    return None
```

**正确模式**：
```python
# ✅ except 块内用 exception() 保留完整 traceback
try:
    result = await self.collector.detail(item_id)
except Exception:
    logger.exception(f"获取详情失败, item_id={item_id}")  # 自动保留 traceback
    return None

# ✅ 非 except 块用 warning + exc_info=True
try:
    result = risky_operation()
except Exception as e:
    logger.warning(f"操作失败: {e}", exc_info=True)
    return None
```

**历史教训**：关键路径（`_on_startup` / `run_migrations` / `_init_db`）用 `logger.warning(f"操作失败: {e}")` 丢失 traceback，排查问题时只能看到异常消息但无法定位具体行号和调用链，定位耗时 30+ 分钟。修复：所有 `except` 块改用 `logger.exception("描述")` 自动保留 traceback，问题定位时间从 30+ 分钟缩短到 5 分钟。同期发现 15+ 处类似问题，全部修复。

> 📖 详见 [error-handling.md](../assets/guides/coding-rules/error-handling.md) step 202。

## 62. 外部资源生命周期配对管理（EXTERNAL-RESOURCE-LIFECYCLE）🆕v4.38

> 与 B-REVIEW-187（backend 外部资源生命周期审查）/ F-REVIEW-151（前端外部资源生命周期审查）对应。
> 与 #23 资源生命周期管理的关系：#23 关注"资源实例的 GC 与 cleanup"，本条关注"外部传入资源的配对 register/unregister"。

外部传入的资源（Page/Connection/Lock）必须配对调用 `register`/`unregister`，且在 `finally` 块 `unregister` 避免泄漏；并发场景下资源不被误关。

1. **register/unregister 配对**：外部传入的资源必须调用 `register_external_page(page)` 注册，使用完毕在 `finally` 块调用 `unregister_external_page(page)` 注销
2. **finally 块强制**：`unregister` 必须在 `finally` 块中调用，确保异常时也能注销
3. **并发安全**：并发采集时，资源不被主流程误关（通过 register 标记"资源正在使用"）
4. **引用计数**：`register` 时引用计数 +1，`unregister` 时 -1，计数为 0 时才允许关闭资源
5. **配置驱动**：资源类型清单、配对函数名、引用计数策略从 `config.yaml#external_resource_lifecycle` 读取

**关键约束**：
- 外部传入 page 未调用 `register_external_page` → 视为 CRITICAL（并发采集时 page 被误关）
- `register` 后无 `finally: unregister` → 视为 CRITICAL（资源泄漏）
- `unregister` 不在 `finally` 块 → 视为 WARNING（异常时无法注销）
- 引用计数为 0 但未关闭资源 → 视为 WARNING（资源泄漏）

**判断信号**：
- `grep "reuse_page\|external_page\|register_external" <file>` 后检查是否配对 register/unregister
- `grep "def.*page.*Page" <file>` 参数含 Page 但无 `register_external_page` → 违规
- `grep "register_external_page" <file>` 但无 `finally.*unregister` → 配对缺失

**适用**：外部资源传入（Page/Connection/Lock/SSE 连接）；并发采集场景（多 worker 共享 Page）；Playwright Page 共享（主流程创建 Page 传给采集器）；跨函数/跨模块资源传递。
**不适用**：内部创建的资源（自己管理生命周期）、单线程使用（无并发风险）、一次性资源（用完即关）、`with` 语句管理的资源（自动生命周期）。

**反模式**：
```python
# ❌ 外部传入 page 未注册，并发采集时 page 被主流程关闭
async def collect_items(self, page: Page, item_ids: list[str]):
    # 未调用 register_external_page，主流程可能在此期间关闭 page
    for item_id in item_ids:
        await self._collect_one(page, item_id)
    # 主流程关闭 page 后，后续操作报 TargetClosedError
```

**正确模式**：
```python
# ✅ register + finally unregister 配对
async def collect_items(self, page: Page, item_ids: list[str]):
    self._register_external_page(page)  # 引用计数 +1，标记"正在使用"
    try:
        for item_id in item_ids:
            await self._collect_one(page, item_id)
    finally:
        self._unregister_external_page(page)  # 引用计数 -1，计数为 0 时才允许关闭
```

**历史教训**：`collection_service.py` 接收外部传入的 `page` 但未调用 `register_external_page`，并发采集时主流程（`_cleanup_idle_pages`）检测到 page 空闲后关闭，导致采集器后续操作报 `playwright._impl._errors.TargetClosedError`。修复：在 `collection_service.py` 入口调用 `self._register_external_page(page)` + `finally: self._unregister_external_page(page)`，主流程通过引用计数判断 page 是否正在使用，使用中不关闭。

> 📖 详见 [concurrency.md](../assets/guides/coding-rules/concurrency.md) step 203。

## 63. 数据库写入函数身份追溯与类型安全（DB-WRITE-IDENTITY-TRACE）🆕v4.38

> 与 B-REVIEW-188（backend 数据库写入身份追溯审查）对应。

数据库写入函数必须含 `user_id` 参数用于跨用户隔离；converter 函数处理 `re.Match` 对象必须显式调用 `m.group(1)` 再转型，禁用 `int(m)`。

1. **user_id 参数强制**：所有数据库写入函数（`upsert_*` / `insert_*` / `update_*` / `create_*`）必须含 `user_id: str` 参数，用于跨用户数据隔离
2. **WHERE 子句强制**：写入 SQL 的 WHERE 子句必须含 `user_id` 条件，禁止跨用户写入
3. **converter 类型安全**：正则 converter 函数处理 `re.Match` 对象必须显式调用 `m.group(1)` 获取字符串再转型（`int(m.group(1))`），禁用 `int(m)`（报 `int() argument must be a string, not 're.Match'`）
4. **Pydantic 入口校验豁免**：Pydantic 模型入口已校验的函数可豁免 user_id（但需注释标注"入口已校验"）
5. **配置驱动**：必需 user_id 函数名清单、converter 检查规则从 `config.yaml#db_write_identity_trace` 读取

**关键约束**：
- `grep "def upsert_\|def insert_\|def update_\|def create_" <file>` 无 `user_id` 参数 → 视为 WARNING（跨用户风险）
- `grep "lambda m: int"` 无 `group(1)` → 视为 CRITICAL（`int() argument must be a string, not 're.Match'`）
- `grep "WHERE.*task_id" <file>` 但无 `AND user_id` → 视为 WARNING（跨用户写入风险）

**判断信号**：
- `grep "def upsert_\|def insert_\|def update_\|def create_" <file>` 后检查参数是否含 `user_id`
- `grep "lambda m: int" <file>` 检查是否显式 `group(1)`
- `grep "WHERE.*task_id.*$" <file>` 但无 `user_id` 条件 → 跨用户风险

**适用**：所有数据库写入函数（upsert/insert/update/create）；正则 converter 函数；跨用户系统（多用户共享数据库）；含 `re.findall` + converter 的解析逻辑。
**不适用**：系统级写入（如日志表、统计表、全局配置表，无 user_id 概念）、单一调用点的函数（无复用需求）、Pydantic 入口校验后的函数（已校验 user_id）、纯查询函数（SELECT 无写入风险）。

**反模式 1**：
```python
# ❌ 缺 user_id 参数，跨用户写入风险
def upsert_eval_event(event: EventRow):
    session.execute(
        text("INSERT INTO evaluations (task_id, score) VALUES (:task_id, :score)"),
        {"task_id": event.task_id, "score": event.score}
    )
    # 无 user_id，可能写入其他用户的数据
```

**反模式 2**：
```python
# ❌ lambda m: int(m) 报 "int() argument must be a string, not 're.Match'"
_SELLER_LABEL_PATTERNS = {
    "follower_count": (re.compile(r"关注(\d+)"), lambda m: int(m)),  # TypeError
}
```

**正确模式 1**：
```python
# ✅ 含 user_id 参数 + WHERE 子句含 user_id
def upsert_eval_event(event: EventRow, user_id: str):
    session.execute(
        text("INSERT INTO evaluations (task_id, user_id, score) VALUES (:task_id, :user_id, :score)"),
        {"task_id": event.task_id, "user_id": user_id, "score": event.score}
    )
```

**正确模式 2**：
```python
# ✅ 显式调用 m.group(1) 再转型
_SELLER_LABEL_PATTERNS = {
    "follower_count": (re.compile(r"关注(\d+)"), lambda m: int(m.group(1))),
}
```

**历史教训**：`_SELLER_LABEL_PATTERNS` 用 `int` 作为 converter，`re.findall` 返回 `Match` 对象，`int(m)` 报 `TypeError: int() argument must be a string, not a 're.Match'`，导致卖家关注数解析失败。修复：改为 `lambda m: int(m.group(1))`。同期发现 `upsert_eval_event` 缺 `user_id` 参数，多用户场景下可能写入其他用户的评估数据。修复：新增 `user_id: str` 参数 + WHERE 子句含 `user_id` 条件。

> 📖 详见 [database.md](../assets/guides/coding-rules/database.md) step 204。

---

# experimental 元规范（64-65）🆕v4.39.0

> 以下 2 条元规范从 2026-07-08 解决的「SheetWorkspace URL↔状态同步失败回退」「Service Worker 缓存版本同步」2 类问题中提炼，使用 Sequential Thinking 4 维度复盘法（成功步骤 / 不确定性与失败点 / 可抽象的固定流程与判断逻辑 / 适用场景与不适用场景）抽象而成。
>
> **experimental 标签说明**（参考 #36 规范沉淀门槛）：以下规范案例数 <3 次（仅 2026-07-08 一个案例），未达正式规范门槛（≥3 个相似 bug），标 experimental 标签预沉淀，1 季度观察期（2026-07-08 至 2026-10-08）。观察期内若再出现 ≥2 个相似 bug 则升级为正式规范，否则废弃。
>
> 命名空间与配置驱动：所有参数（`url_state_sync_fallback` / `sw_cache_version_sync`）均在 `config.yaml` 对应节点管理，禁止硬编码。

## 64. URL↔状态同步失败回退（URL-STATE-SYNC-FALLBACK）🆕v4.39 experimental

> 与 F-REVIEW-152（前端 URL↔状态同步失败回退审查）对应。后端无此场景，不新增 B-REVIEW。

SheetWorkspace 多页签应用中，URL 变化触发 `openSheet` 失败时（路径未注册 / 栈满），URL 已改变但 activeId 未变，导致 `useParams()` 返回错误值，业务逻辑误判。必须在 `openSheet` 失败时回退 URL 到当前 active sheet 的 path，保持 URL 与 active sheet 一致。

1. **失败时 URL 回退强制**：`useSheetSync` Hook 在 `openSheet` 失败时（`!result.ok`）必须调用 `navigate(activeSheet.path, { replace: true })` 回退 URL
2. **activeSheet 存在性检查**：回退前必须检查 `activeSheet` 是否存在（可能首次加载无 activeId），不存在则跳过回退
3. **replace 参数强制**：回退必须用 `{ replace: true }` 避免污染浏览器历史记录
4. **防循环检查保留**：回退后 `activeSheet.path === URL`，防循环检查（第 40 行）会跳过，不会死循环
5. **配置驱动**：回退开关、回退策略（replace / push）、允许回退的 reason 清单从 `config.yaml#url_state_sync_fallback` 读取

**关键约束**：
- `useSheetSync` Hook 缺 `navigate` 引入 → 视为 WARNING（无法回退）
- `openSheet` 失败时无 URL 回退逻辑 → 视为 CRITICAL（URL 漂移导致业务误判）
- 回退未用 `{ replace: true }` → 视为 WARNING（污染历史记录）
- 回退前未检查 `activeSheet` 存在性 → 视为 WARNING（空指针风险）

**判断信号**：
- `grep "useSheetSync" frontend/src/hooks/` 但无 `useNavigate` 引入 → 缺 navigate
- `grep "!result.ok" frontend/src/hooks/useSheetSync.ts` 但无 `navigate(activeSheet.path)` → 缺回退逻辑
- `grep "navigate\(.*\)" frontend/src/hooks/useSheetSync.ts` 但无 `replace: true` → 缺 replace 参数

**适用**：SheetWorkspace 多页签应用（URL ↔ sheet 栈双向同步）、URL 参数驱动的页面状态（如 `useParams().id` 判断编辑/新增模式）、外部链接回链场景（通知点击、邮件链接、二维码）。
**不适用**：纯静态路由（无状态同步）、无 URL 参数的页面（无 useParams 依赖）、独立路由（如 `/login` 不进入 SheetWorkspace）、传统 MPA（后端渲染无前端状态）。

**反模式**：
```typescript
// ❌ openSheet 失败时 URL 已改变但 activeId 不变，useParams 漂移
useEffect(() => {
  const path = location.pathname + location.search
  const activeSheet = sheets.find((s) => s.id === activeId)
  if (activeSheet?.path === path) return
  const result = openSheetWithNotification(path)
  // 缺失败时 URL 回退，导致 isEdit 误判
}, [location.pathname, location.search, sheets, activeId])
```

**正确模式**：
```typescript
// ✅ openSheet 失败时回退 URL 到 active sheet 的 path
import { useNavigate } from 'react-router-dom'

export function useSheetSync(): void {
  const location = useLocation()
  const navigate = useNavigate()
  const sheets = useSheetStore((s) => s.sheets)
  const activeId = useSheetStore((s) => s.activeId)

  useEffect(() => {
    const path = location.pathname + location.search
    const activeSheet = sheets.find((s) => s.id === activeId)
    if (activeSheet?.path === path) return
    const result = openSheetWithNotification(path)
    // openSheet 失败时回退 URL 到当前 active sheet 的 path
    if (!result.ok && activeSheet) {
      navigate(activeSheet.path, { replace: true })
    }
  }, [location.pathname, location.search, sheets, activeId, navigate])
}
```

**历史教训**：任务修改流程中点击 Step 3「全局搜索配置」按钮，`navigate('/app/config/search')` 多了 `/app` 前缀（basename），`findSheetMeta('/app/config/search')` 返回 undefined，触发 React Router `*` 重定向到 `/`。此时 URL 变为 `/`，但 activeId 仍指向 TaskEditor，`useParams().id` 返回 undefined，`isEdit` 误判为 false，提交时创建重复任务。修复：(1) Step 3 改为打开 Modal（避免 navigate）；(2) `useSheetSync` 在 `openSheet` 失败时回退 URL。

> 📖 详见 [state-management.md](../assets/guides/coding-rules/state-management.md) step 205（预沉淀）。

## 65. Service Worker 缓存版本同步（SW-CACHE-VERSION-SYNC）🆕v4.39 experimental

> 与 F-REVIEW-153（前端 SW 缓存版本同步审查）对应。后端无此场景，不新增 B-REVIEW。

PWA 应用使用 Service Worker 缓存静态资源，构建时生成的版本哈希（如 `sw.js` 中的 `precaching-manifest`）必须与前端运行时检测的版本一致。版本不一致时（如用户浏览器缓存旧 `sw.js`），必须触发 `skipWaiting()` 强制更新，避免旧版本页面功能异常。

1. **构建时版本哈希**：`vite-plugin-pwa` 构建时在 `sw.js` 中生成版本哈希（`self.__WB_MANIFEST` 中的文件哈希）
2. **运行时版本检测**：前端启动时（`main.tsx` 或 `App.tsx`）读取 `navigator.serviceWorker.controller` 的版本，与当前构建版本对比
3. **skipWaiting 强制更新**：版本不一致时调用 `registration.waiting?.postMessage({ type: 'SKIP_WAITING' })` 触发 `skipWaiting()`
4. **硬刷新提示**：`skipWaiting` 后显示「新版本已就绪，点击刷新加载」提示，用户确认后 `window.location.reload()`
5. **配置驱动**：版本检测开关、硬刷新提示文案、skipWaiting 触发策略从 `config.yaml#sw_cache_version_sync` 读取

**关键约束**：
- `sw.js` 缺版本哈希 → 视为 WARNING（无法检测版本差异）
- 前端启动时无版本检测逻辑 → 视为 WARNING（无法触发强制更新）
- 版本不一致时无 `skipWaiting` 触发 → 视为 CRITICAL（用户功能异常）
- 缺硬刷新提示直接 `reload()` → 视为 WARNING（用户体验突兀）

**判断信号**：
- `grep "self.__WB_MANIFEST\|precaching-manifest" frontend/dist/sw.js` 缺失 → 缺版本哈希
- `grep "navigator.serviceWorker.getRegistration" frontend/src/` 缺失 → 缺版本检测
- `grep "SKIP_WAITING\|skipWaiting" frontend/src/` 缺失 → 缺强制更新逻辑
- `grep "新版本.*刷新\|版本已更新" frontend/src/` 缺失 → 缺硬刷新提示

**适用**：PWA 应用（使用 Service Worker 缓存）、SPA 应用（单页应用前端构建）、依赖 Service Worker 缓存的离线应用、频繁迭代的前端项目（版本更新快）。
**不适用**：传统 MPA 应用（每次加载最新 HTML）、无 Service Worker 的应用、纯静态站点（无动态内容）、测试环境（版本检测关闭）。

**反模式**：
```typescript
// ❌ 无版本检测逻辑，用户浏览器缓存旧 sw.js 导致功能异常
// main.tsx 直接注册 SW，不检测版本
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js')
}
```

**正确模式**：
```typescript
// ✅ 构建时生成版本哈希 + 运行时版本检测 + skipWaiting 强制更新
// vite.config.ts
VitePWA({
  strategies: 'generateSW',
  manifest: { /* ... */ },
  workbox: {
    skipWaiting: true,
    clientsClaim: true,
  },
})

// main.tsx
async function checkSWUpdate() {
  if (!('serviceWorker' in navigator)) return
  const registration = await navigator.serviceWorker.getRegistration()
  if (registration?.waiting) {
    // 版本不一致，显示硬刷新提示
    const userConfirmed = confirm('新版本已就绪，点击刷新加载')
    if (userConfirmed) {
      registration.waiting.postMessage({ type: 'SKIP_WAITING' })
      window.location.reload()
    }
  }
}
checkSWUpdate()
```

**历史教训**：PC 端首次登录后重定向到 `/app/m/`（移动端），根因是浏览器缓存了旧版 `sw.js`，旧版 SPA 中 `useMobileDetect.ts` 用 `pointer:coarse` 触屏判断导致 PC 端误判为移动端。修复：(1) 修复 `useMobileDetect.ts` 移除 `pointer:coarse` 判断；(2) 构建新 SPA 生成新 `sw.js` 哈希；(3) 用户需硬刷新（Ctrl+Shift+R）清除 Service Worker 缓存。预防：添加版本检测 + `skipWaiting` 强制更新逻辑。

> 📖 详见 [frontend-ui.md](../assets/guides/coding-rules/frontend-ui.md) step 206（预沉淀）。
