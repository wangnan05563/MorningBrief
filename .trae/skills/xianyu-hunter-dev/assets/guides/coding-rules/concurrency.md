# Concurrency 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「concurrency」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 27：死代码与资源生命周期【强制】🆕v4.3

27. **死代码与资源生命周期【强制】🆕v4.3**
    - 创建的长期存活对象（Proxy/Observer/Listener/Task）必须赋值给有生命周期的变量（实例属性/模块级变量），**禁止**赋值给局部变量后丢弃
    - `try/finally` 块中使用的变量必须在 `try` 之前初始化为 `None`，确保 `finally` 不会因未绑定而抛 `UnboundLocalError`
    - **判断信号**：`new Proxy()` / `new MutationObserver()` / `asyncio.create_task()` 的返回值赋值给局部变量；`try` 块内赋值的变量在 `finally` 中被引用
    - **修复模式**：监听器赋值给实例属性（`self._observer = new MutationObserver(...)`）；资源变量 `page = None` 前置初始化
    - **适用**：所有需要长期存活的监听器/观察者/后台任务；所有 try/finally 资源清理
    - **不适用**：一次性使用的临时对象、`with` 语句（自动管理生命周期）
    - **历史教训**：`awsc_spoof.py` 的 `var baxiaProxy = new Proxy(...)` 赋值给局部变量后从未使用，验证码触发事件永远不会被派发；`api_anticrawl.py` 的 `renew_callback` 中 `page` 变量未初始化，`new_page()` 抛异常时 `finally` 中 `page.close()` 报 `UnboundLocalError`


---

### step 33：独立调度器隔离模式【强制】🆕v4.4

33. **独立调度器隔离模式【强制】🆕v4.4**
    - 生命周期/优先级不同的后台任务必须使用独立 APScheduler `BackgroundScheduler`，避免与项目主调度器耦合
    - **判断信号**：后台任务生命周期与应用主调度器不同 + 共享状态有冲突风险 + 任务优先级不同
    - **修复模式**：创建独立 `BackgroundScheduler()` → 独立 `add_job()` 注册 → 独立 `start()`/`shutdown()` 钩子 → 不共享 jobstore
    - **配置参数**：`scheduler_name`、`max_instances`、`coalesce`、`misfire_grace_time` 在 `config/scheduler.yaml` 管理
    - **适用**：Cookie 同步调度器、健康检查调度器、生命周期不同于主任务调度器的辅助任务
    - **不适用**：紧耦合任务调度、共享状态访问需求、资源限制环境（内存敏感场景应合并调度器）
    - **历史教训**：Cookie 同步任务若复用项目主任务调度器，会与采集任务的优先级产生冲突，且 shutdown 时序复杂；独立调度器后生命周期清晰


---

### step 34：配置驱动功能开关模式【强制】🆕v4.4

34. **配置驱动功能开关模式【强制】🆕v4.4**
    - 高风险/高资源消耗功能默认关闭，需用户显式启用；所有功能参数集中在 `Config` 类（如 `BrowserConfig`），不硬编码
    - **判断信号**：功能需用户主动选择 + 可能耗资源（CPU/内存/网络） + 多环境部署需求
    - **修复模式**：`Config` 类新增 `enable_flag: bool = False` + 详细参数字段 → `config.yaml` 暴露开关 → 文档明确启用条件与资源消耗
    - **配置参数**：`enable_flag` 默认 `false`，详细参数（interval/threshold/port）集中在相应 `Config` 类
    - **适用**：CDP 在线导入、Cookie 自动同步、向量库重建等高风险/高资源消耗功能
    - **不适用**：核心功能（必须默认启用）、性能敏感场景（配置加载延迟不可接受）、简单脚本工具
    - **历史教训**：`auto_sync` 默认 `false`，避免用户不知情下启用自动同步导致浏览器资源被占用；`cdp_port` 通过 `BrowserConfig` 管理而非硬编码


---

### step 35：降级链模式【强制】🆕v4.4

35. **降级链模式【强制】🆕v4.4**
    - 多重方案按优先级排序，失败后自动降级，3 次失败加倍间隔，最大间隔 2 小时
    - **判断信号**：多方案优先级明确 + 网络不稳定环境 + 外部依赖不可控
    - **修复模式**：方案 A 失败 → 尝试方案 B → 方案 B 失败 N 次后触发 backoff（`interval *= 2`，上限 `max_interval`）→ 记录降级原因到日志
    - **配置参数**：`max_failures=3`、`backoff_multiplier=2`、`max_interval=7200` 在 `config/fallback.yaml` 管理
    - **适用**：Cookie 同步（offline import → CDP import → backoff）、网络重试、外部 API 调用
    - **不适用**：单一方案场景、降级后体验差于报错（应直接失败）、关键安全场景（必须 fail-fast）
    - **历史教训**：Cookie 同步调度器实现 offline import 优先 → CDP import 次之 → backoff 兜底的降级链，3 次失败后间隔加倍避免无意义重试


---

### step 50：异步操作整体超时保护【强制】🆕v4.7

50. **异步操作整体超时保护【强制】🆕v4.7**
    - 所有 `await` 调用外部资源（浏览器自动化、HTTP 客户端、IO 操作、远程 API）的异步操作，必须在**调用层**用 `asyncio.wait_for(coro, timeout=N)` 包装整体超时，超时后返回语义化状态码（如 504 网关超时），禁止依赖被调用方内部 timeout 参数
    - **判断信号**：代码含 `await container.<module>.<method>(...)` / `await client.<method>(...)` / `await page.<method>(...)` 调用外部资源 → 必须检查是否被 `asyncio.wait_for` 包裹；被调用方内部 `timeout` 参数不视为整体超时保护
    - **修复模式**：
      ```python
      try:
          detail = await asyncio.wait_for(
              container.collector.detail(item_id), timeout=60.0
          )
      except asyncio.TimeoutError:
          logger.warning("[RefreshItem] 采集超时 item=%s（%ss），外部资源可能异常", item_id, timeout)
          raise HTTPException(status_code=504, detail="采集超时：外部资源异常或被反爬拦截，请稍后重试")
      except Exception as e:
          logger.warning("[RefreshItem] 采集失败 item=%s: %s", item_id, e)
          raise HTTPException(status_code=502, detail=f"采集失败：{e}")
      ```
    - **关键约束**：
      - 超时时间必须从配置读取（`config.async_timeout.<operation>_seconds`），**禁止**硬编码
      - 超时后必须返回明确状态码（504=超时、502=失败、503=稍后重试），便于前端按状态码分类处理
      - 超时日志必须记录操作类型 + 资源 ID + 超时秒数，便于排查
      - `asyncio.CancelledError` 不应被 `wait_for` 的 `TimeoutError` 吞掉，应单独传播
    - **配置参数**：`timeout_seconds`（默认 60）、`max_retries`（默认 0=不重试）、`status_code_mapping`（超时→504、失败→502）在 `config.yaml` 的 `async_timeout` 节点管理
    - **适用**：所有 `await` 外部资源的异步操作（浏览器自动化、HTTP 请求、远程 API、IO 操作、子进程调用）
    - **不适用**：有内建 timeout 的 HTTP 客户端（`httpx.Timeout` 已配置）、纯计算函数、`asyncio.CancelledError` 传播路径、有重试机制（如 tenacity）包裹的场景
    - **历史教训**：`refresh_item` 调用 `collector.detail(item_id)` 时，`page.query_selector` 无 `timeout` 参数，闲鱼反爬 RGV587 拦截后浏览器实例异常导致 `query_selector` 无限挂起，前端 90 秒后客户端超时无任何错误提示。修复后 `refresh_item` 加 `asyncio.wait_for(..., timeout=60.0)` + 504 响应，14.4 秒返回明确错误


---

### step 61：资源生命周期规范【强制】🆕v4.10

61. **资源生命周期规范【强制】🆕v4.10**
    - 所有可注册的组件（Worker/Adapter/Plugin/Handler）必须实现 `cleanup()` 钩子，由调度器/容器在 `unregister` 时统一调用，确保资源释放
    - **关键约束**：
      1. **cleanup 钩子约定**：即使当前实现为空，也必须保留 `async def cleanup(self) -> None: return None` 方法（为未来扩展预留接入点，参考 `TaskWorker.cleanup`）
      2. **asyncio.Task 引用保留**：后台任务必须 `self._task = asyncio.create_task(...)` 保留引用防 GC，**禁止**裸 `asyncio.create_task(...)` 不持有引用
      3. **取消+收集模式**：取消后台任务必须 `task.cancel()` + `await asyncio.gather(task, return_exceptions=True)`，确保资源清理完成
      4. **try/finally 初始化**：`try/finally` 块中 `finally` 引用的变量必须在 `try` 之前初始化为 `None`（`page = None; try: page = await ...; finally: if page: await page.close()`）
      5. **锁内原子检查**：共享状态（计数器/冷却时间）的「检查+更新」必须在同一锁内完成，避免竞态
    - **判断信号**：组件有「注册/注销」生命周期 + 持有后台任务/连接/锁/文件句柄 → 必须按此流程设计
    - **修复模式**：
      ```python
      # ✅ cleanup 钩子 + Task 引用保留 + cancel+gather
      class TaskWorker:
          def __init__(self):
              self._task: asyncio.Task | None = None

          async def cleanup(self) -> None:
              """Worker 资源清理钩子，供 scheduler.unregister 调用"""
              if self._task is not None and not self._task.done():
                  self._task.cancel()
                  await asyncio.gather(self._task, return_exceptions=True)
                  self._task = None
      ```
    - **配置参数**：`lifecycle.cleanup_method_name`（默认 `cleanup`）、`lifecycle.task_cancel_timeout`（默认 5s）、`lifecycle.required_cleanup_components`（必须实现 cleanup 的组件类型列表）在 `config.yaml` 的 `resource_lifecycle` 节点管理
    - **适用**：可注册组件（Worker/Adapter/Plugin/Handler）、持有后台任务的组件、持有连接/锁/文件句柄的组件
    - **不适用**：纯函数（无状态无副作用）；一次性脚本（进程结束即释放）；纯数据对象（无生命周期）
    - **历史教训**：`TaskWorker` 缺少 `cleanup()` 方法，`TaskScheduler.unregister` 时无法释放 worker 持有的资源；`_WorkerHandle` 缺少 `loop_task` 字段声明导致 `getattr` 兜底反模式。修复后 `TaskWorker` 实现 cleanup 钩子，`_WorkerHandle` 显式声明所有字段


---

### step 63：并发安全规范【强制】🆕v4.10

63. **并发安全规范【强制】🆕v4.10**
    - 多线程/协程访问同一共享状态（计数器/冷却时间/最后执行时间）时，「检查+更新」必须在同一锁内完成，避免竞态
    - **关键约束**：
      1. **锁内原子检查**：共享状态的「检查+更新」必须在同一锁内（`with self._lock: if can_proceed(): self._last_run = now()`）
      2. **锁粒度最小化**：锁仅保护临界区（检查+更新），**禁止**用锁保护 IO（如 `await` 网络请求），避免阻塞其他协程
      3. **锁内禁止 await**：`asyncio.Lock` 内禁止 `await` 长时间操作（会导致锁持有过久），必要时先释放锁再做 IO
      4. **Dataclass 字段显式声明**：dataclass 字段必须显式声明默认值（`consecutive_errors: int = 0`），**禁止**用 `getattr(h, 'consecutive_errors', 0)` 兜底（反模式，掩盖字段未初始化的 bug）
      5. **锁类型选择**：跨线程用 `threading.RLock`（可重入），跨协程用 `asyncio.Lock`，**禁止**混用
    - **判断信号**：多线程/协程访问同一字段 + 字段有「检查-更新」模式（如 `if self._last_run + interval < now: self._last_run = now()`）→ 必须加锁
    - **修复模式**：
      ```python
      # ✅ 锁内原子检查 + Dataclass 字段显式声明
      @dataclass
      class _WorkerHandle:
          consecutive_errors: int = 0  # ✅ 显式声明，禁止 getattr 兜底

      class Scheduler:
          def __init__(self):
              self._lock = threading.RLock()
              self._handles: dict[str, _WorkerHandle] = {}

          def _check_and_update(self, task_id: str) -> bool:
              with self._lock:  # 锁内原子检查+更新
                  h = self._handles[task_id]
                  if h.consecutive_errors >= threshold:
                      return False
                  h.consecutive_errors += 1
                  return True
      ```
    - **配置参数**：`concurrency.lock_type`（默认 `RLock`）、`concurrency.critical_section_max_await`（默认 `0`，禁止 await）、`concurrency.required_lock_fields`（必须加锁保护的字段名列表）在 `config.yaml` 的 `concurrency_safety` 节点管理
    - **适用**：多线程/协程访问同一共享状态；定时任务与 API 请求并发修改同一数据
    - **不适用**：单线程顺序执行；thread-local 数据；不可变对象
    - **历史教训**：`_WorkerHandle` 缺少 `consecutive_errors` 字段声明，代码用 `getattr(h, 'consecutive_errors', 0) + 1` 兜底，掩盖了字段未初始化的 bug；并发场景下「检查+更新」未在锁内可能导致竞态。修复后显式声明字段 + 锁内原子检查


---

### step 74：后台任务健康监控【强制】🆕v4.12

74. **后台任务健康监控【强制】🆕v4.12**
    - 后台任务（EventBus 消费者 / 调度器循环 / 健康检查器）必须用轮询监控（`while not stop_event.is_set(): if task.done(): break; await asyncio.wait_for(stop_event.wait(), timeout=N)`），**禁止** `await asyncio.Event().wait()` 静默等待导致任务异常退出时主循环无感知
    - **判断信号**：代码含 `bus_task = asyncio.create_task(...)` 后 `await stop_event.wait()` → 必须改为轮询检查 `bus_task.done()`
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
    - **配置参数**：`background_task_monitor.poll_interval_seconds`（默认 `10`，轮询间隔）、`background_task_monitor.monitored_tasks`（必须监控的后台任务名列表，如 `["event_bus", "scheduler_loop", "health_check"]`）、`background_task_monitor.on_task_exit`（默认 `log_and_break`，可选 `restart`）在 `config.yaml` 的 `background_task_monitor` 节点管理
    - **适用**：所有后台 asyncio.Task（EventBus / Scheduler / Health Checker / Cookie Sync / KB Refresh）；需要在主循环中感知子任务退出的场景
    - **不适用**：fire-and-forget 任务（不需感知退出）；一次性任务（如启动初始化）；有 done_callback 处理的任务
    - **历史教训**：`startup._scheduler_loop` 用 `await stop_event.wait()` 等待关闭信号，EventBus 任务异常退出时主循环无感知，事件推送静默失效 30 分钟才被用户发现


---

### step 95：长耗时异步请求 race condition 防护规范【强制】🆕v4.17

**背景**：Vision 推理 90s 期间用户切换商品，旧请求的 result/error/loading 污染新商品 UI 状态；原 onAIEval（60s）也存在同源问题。

**规范**：
1. 任何 > 3s 的异步请求（LLM Vision/批量采集/重型 DB 查询）必须用 `useRef` 跟踪最新请求 ID
2. 旧请求的 result/error/loading 三态在 setState 前必须校验 `ref.current === itemId`，不匹配则丢弃
3. finally 块同样校验，避免提前关闭新请求的 loading

**判断逻辑**：
- grep 前端 `client.post` / `client.get` 调用看是否有 `timeout` 参数 >= 3000
- 或调用方为 LLM/批量类（`aiApi.deepAnalyze` / `aiApi.evaluateCondition` / `evalApi.batchEvaluate`）
- 有则强制加 `useRef` 防护

**代码模板**：
```typescript
const itemIdRef = useRef('')
const onXxx = async (itemId: string) => {
  itemIdRef.current = itemId
  setLoading(true)
  setResult(null)
  try {
    const result = await api.fetch(itemId)
    if (itemIdRef.current !== itemId) return  // 丢弃过期结果
    setResult(result)
  } catch (err) {
    if (itemIdRef.current !== itemId) return  // 丢弃过期错误
    handleError(err)
  } finally {
    if (itemIdRef.current === itemId) {  // 仅最新请求结束 loading
      setLoading(false)
    }
  }
}
```

**配置参数**：`async_race_condition` 节点（enabled / threshold_ms / detect_patterns / abort_controller_preferred）

**适用场景**：timeout >= 3s 的异步请求 + 用户可触发多次切换商品/任务/对象的场景（Modal 内异步、列表行按钮异步）
**不适用场景**：同步请求（< 1s）；一次性请求（页面加载）；用户无法重复触发（如表单提交后禁用按钮）；请求顺序由用户显式控制（如分页加载）

注：`AbortController` 是更优解但需后端支持取消；`useRef` 方案是通用轻量解，无需后端配合。


---

### step 198：ASYNC-AWAIT-SYNC-CHECK async/await 同步性静态检查【强制】🆕v4.38

**背景**：本轮对话修复的 8 类问题之一——`async def` 方法体内不含 `await` 表达式（或仅 await 同步函数），导致 asyncio 事件循环被阻塞、并发性能退化为串行，且 Python 3.14 已对此类反模式强化告警。

**问题**：开发者将同步函数标记为 `async def` 但未在内部真正 await 异步操作，造成两种危害：① 调用点被迫 `await` 一个本质同步的操作，徒增事件循环负担；② Python 3.14+ 对此反模式有运行时告警，但项目未在静态检查阶段拦截。

**规范**：

1. **async def 方法体内必须含至少一个真异步 await【强制】**：`async def` 声明的方法体内若不含 `await <coroutine>` 表达式（或仅 `await` 同步函数返回值），必须改为同步 `def`，调用点同步移除 `await`。
   ```python
   # ❌ 错误：async def 内部无真异步 await，徒增事件循环负担
   async def get_user_name(user_id: str) -> str:
       row = db.query(User).filter_by(id=user_id).first()  # 同步 DB 调用
       return row.name if row else ""

   # ✅ 正确：同步函数，调用点不 await
   def get_user_name(user_id: str) -> str:
       row = db.query(User).filter_by(id=user_id).first()
       return row.name if row else ""
   ```

2. **调用点 await 与函数声明必须同步【强制】**：当 `async def` 改为 `def` 时，所有调用点的 `await xxx()` 必须同步移除 `await`；反向调整时亦然。修改必须覆盖全量调用点，禁止遗漏导致 `TypeError: object str can't be used in 'await' expression`。

3. **静态检查触发条件【强制】**：Code review 时必须用 `grep "async def" <file>` 列出所有异步声明，逐个检查方法体内是否含真异步 `await`；Python 3.14+ 的 `RuntimeWarning: coroutine never awaited` 也是触发信号。

4. **真异步判定【强制】**：`await` 的对象必须是 `coroutine` / `Task` / `Future`，`await` 同步函数返回值（如 `await db.query(...).first()`）不算真异步，应改为同步 `def`。

**配置驱动**：`async_await_check` 节点管理检测规则，包含 `require_true_await`（默认 `true`）、`python_min_version_for_runtime_warning`（默认 `"3.14"`）、`forbidden_patterns`（`async def` 内无 await 的代码模式清单）、`exempt_decorators`（豁免的装饰器列表，如 `@asynccontextmanager`）在 `config.yaml` 管理，不硬编码。

**适用场景**：
- 所有 `async def` 声明的函数（后端 FastAPI 路由、Service、Repository、调度器方法）
- Python 3.10+ 项目（Python 3.14+ 强化告警）
- async/await 与同步 DB 调用混用的代码库

**不适用场景**：
- `@asynccontextmanager` 装饰的异步上下文管理器（即使内部无 await，也保留 async 声明）
- `async def __aenter__` / `async def __aexit__` 协议方法（语义要求 async）
- 测试代码中的 `async def test_xxx()`（pytest-asyncio 框架要求）

**历史教训**：项目早期将多个本质同步的 DB 查询函数标记为 `async def` 但内部用同步 SQLAlchemy 调用，调用点被迫 `await`，FastAPI 路由的并发性能从理论 1000 QPS 退化为串行 50 QPS。Python 3.14 升级后出现 `RuntimeWarning: coroutine never awaited` 告警才被发现。修复后所有无真异步 await 的 `async def` 改为同步 `def`，调用点同步移除 `await`。

**判断信号（review 触发条件）**：
- `grep "async def" <file>` 命中后检查方法体内是否含 `await <coroutine>`
- `RuntimeWarning: coroutine never awaited` 运行时告警
- `TypeError: object str can't be used in 'await' expression` 运行时错误
- `async def` 方法体内仅 `return <value>` 或 `return <sync_call>()`


---

### step 203：EXTERNAL-RESOURCE-LIFECYCLE 外部资源生命周期配对管理【强制】🆕v4.38

**背景**：本轮对话修复的 8 类问题之一——并发场景下 Playwright `Page` 对象在外部资源注册/注销时未配对管理，导致 page 被 GC 后仍被引用、或注册后未清理残留引用，触发 `TargetClosedError` 与内存泄漏。

**问题**：外部资源（Playwright Page/BrowserContext、HTTP 连接池、文件句柄）在多协程环境下注册到容器后，若注销时未配对清理，会出现两类 bug：① 注销时 page 未关闭，残留引用占用内存；② 注册的 page 在使用中被 GC 回收，调用方拿到已关闭的 page 触发 `TargetClosedError`。

**规范**：

1. **register/unregister 必须配对【强制】**：外部资源（Page/BrowserContext/Connection）注册到容器时，必须同时实现 `unregister` 方法清理引用，禁止只 register 不 unregister：
   ```python
   # ✅ 正确：register/unregister 配对
   class PageRegistry:
       def __init__(self):
           self._pages: dict[str, Page] = {}

       async def register(self, key: str, page: Page) -> None:
           self._pages[key] = page

       async def unregister(self, key: str) -> None:
           page = self._pages.pop(key, None)
           if page and not page.is_closed():
               await page.close()  # 配对关闭
   ```

2. **持有强引用防 GC【强制】**：注册到容器的资源必须由容器持有强引用（`self._pages[key] = page`），禁止只传弱引用导致使用中被 GC 回收。与 step 27「死代码与资源生命周期」互补：step 27 管"赋值给有生命周期的变量"，本规范管"register/unregister 配对"。

3. **使用前检测 is_closed【强制】**：从注册表取出 Page/BrowserContext 后必须检测 `is_closed()`，已关闭则重新创建或抛出明确异常：
   ```python
   page = self._pages.get(key)
   if page is None or page.is_closed():
       page = await self._create_new_page()
       self._pages[key] = page
   ```

4. **异常路径必须清理【强制】**：使用外部资源的代码必须用 `try/finally` 包裹，`finally` 块调用 `unregister` 清理，禁止异常路径残留引用。与 step 27「try/finally 块变量前置初始化」配合使用。

5. **并发注销加锁【强制】**：register/unregister 必须在 `asyncio.Lock` 内完成，避免并发注销时同一资源被关闭两次触发 `RuntimeError`。

**配置驱动**：`external_resource_lifecycle` 节点管理配对规则，包含 `required_pair_methods`（必须配对的方法名对，如 `[("register", "unregister"), ("acquire", "release")]`）、`strong_reference_required`（默认 `true`）、`is_closed_check_before_use`（默认 `true`）、`cleanup_in_finally`（默认 `true`）、`lock_required_for_unregister`（默认 `true`）在 `config.yaml` 管理，不硬编码。

**适用场景**：
- Playwright Page/BrowserContext 的注册表管理
- HTTP 连接池（httpx.AsyncClient / aiohttp.ClientSession）的获取与释放
- 文件句柄、socket、subprocess 的注册与清理
- 多协程共享的外部资源池

**不适用场景**：
- `with` 语句管理的同步资源（Python 上下文管理器自动配对）
- `async with` 管理的异步资源（异步上下文管理器自动配对）
- 单次使用即释放的资源（无注册需求）

**历史教训**：项目的 `PageRegistry` 只实现了 `register` 未实现 `unregister`，批量采集任务结束后 page 残留在 `_pages` 字典中，30 分钟累积 50+ 个未关闭的 page，内存从 200MB 涨到 800MB；同时另一处代码取出 page 后未检测 `is_closed()`，page 被 GC 回收后调用方触发 `TargetClosedError`。修复后实现配对的 register/unregister + 使用前 is_closed 检测 + finally 块清理。

**判断信号（review 触发条件）**：
- `grep "def register" <file>` 命中但无对应 `def unregister`
- `grep "page.query_selector" <file>` 前未检测 `page.is_closed()`
- `asyncio.create_task` 创建的任务未持有强引用
- `try/finally` 块中 `finally` 未调用 unregister


---

