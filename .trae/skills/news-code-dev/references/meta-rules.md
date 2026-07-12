# 元规范

本文档定义 20_News 项目开发过程中必须遵守的 22 条元规范。这些规范来源于实际开发中遇到的问题和经验教训。

## 规范 1：配置驱动

**所有业务参数必须通过配置管理，禁止硬编码。**

- 适用：后端所有服务、工作流参数
- 不适用：代码逻辑常量（如 HTTP 状态码）
- 判断信号：grep 搜索 `3600`、`http://`、`api_key` 等具体值
- 正确做法：通过 `settings.py` 的 `BaseSettings` 统一管理，从 `.env` 加载

## 规范 2：复用优先

**优先复用已有模块，避免重复实现。**

- 适用：新增 API、工作流步骤、工具函数
- 判断信号：发现相似的业务逻辑（如两个 service 都有相同的缓存逻辑）
- 正确做法：提取公共基类或工具函数到 `core/` 目录
- 例外：复用导致代码复杂度显著增加时，允许适度重复

## 规范 3：错误分类

**区分三类错误，使用不同的 HTTP 状态码和错误码。**

- `AuthError`（401）：认证失败，token 无效/过期
- `BusinessError`（400/422）：业务规则失败，参数错误
- `SystemError`（500）：系统内部错误，服务不可用
- 判断信号：except 块中统一返回 500
- 正确做法：根据错误原因分类抛出自定义异常

## 规范 4：资源生命周期

**明确每个资源的创建者和销毁者。**

| 资源 | 创建者 | 销毁者 | 超时处理 |
|------|--------|--------|----------|
| asyncio.Task | create_task | GC（完成时） | 保留引用 + add_done_callback |
| Redis 锁 | set(nx=True) | 主动 delete / TTL 过期 | ex 参数设置超时 |
| 数据库连接 | 连接池 | 连接池回收 / 事务结束 | pool_timeout 配置 |
| httpx.Client | AsyncClient() | await client.aclose() | timeout 配置 |
| 文件句柄 | open() | with 语句 / close() | with 语句自动管理 |

## 规范 5：异步安全

**create_task 必须保留引用，阻塞 IO 必须用 to_thread 包装。**

- 判断信号：grep 搜索 `asyncio.create_task(` 后面没有赋值
- 判断信号：grep 搜索 `requests.get`、`time.sleep`、`os.system`
- 正确做法：
  ```python
  task = asyncio.create_task(worker())  # 保留引用
  result = await asyncio.to_thread(blocking_call)  # 阻塞操作
  ```

## 规范 6：数据库迁移幂等

**迁移脚本必须支持重复执行，不因重复执行而报错。**

- 判断信号：迁移脚本中没有 `IF NOT EXISTS` 或存在性检查
- 正确做法：在迁移脚本开头检查对象是否存在
- Alembic 迁移中：使用 `op.execute("SELECT ...")` 检查后决定是否执行 DDL

## 规范 7：JWT 安全

**Token 比较必须使用 hmac.compare_digest，禁止使用 ==。**

- 为什么：`==` 比较存在时序攻击风险，黑客可通过响应时间推断 token
- 判断信号：grep 搜索 `token ==` 或 `jwt_token ==`
- 正确做法：`hmac.compare_digest(provided_token, expected_token)`

## 规范 8：时间字段统一 UTC

**所有时间字段存储和传输使用 UTC，展示时转换为本地时区。**

- 判断信号：grep 搜索 `datetime.now()`、`datetime.utcnow()`
- 正确做法：
  - 存储：使用 `utcnow_naive()` 获取 naive datetime（不带时区信息）
  - 传输：ISO8601 格式，末尾带 Z（如 `2026-07-10T12:00:00Z`）
  - 展示：前端根据用户时区转换

## 规范 9：枚举字段 .value 取值

**数据库存储枚举的 .value，不存储枚举名。**

- 为什么：枚举名是 Python 内部概念，序列化到前端时会丢失
- 判断信号：grep 搜索 `str(MyEnum.VALUE)` 或 `MyEnum.VALUE.name`
- 正确做法：
  ```python
  # 存储
  obj.status = NewsStatus.PENDING.value  # "pending"
  
  # 查询
  status = NewsStatus(data["status"])  # 从字符串恢复枚举
  ```

## 规范 10：Redis Lua 原子性

**涉及多个 Redis 操作的逻辑，使用 Lua 脚本保证原子性。**

- 适用：计数器 + 过期、检查 + 更新、队列 pop + 处理
- 判断信号：连续两次 Redis 操作之间有业务逻辑间隙
- 正确做法：
  ```lua
  local key = KEYS[1]
  local value = redis.call('get', key)
  if value then
      redis.call('del', key)
      return tonumber(value) + 1
  end
  return 0
  ```

## 规范 11：内部接口鉴权

** localhost 内部接口必须有 IP 校验，不能仅依赖路由可见性。**

- 适用：工作流触发接口、健康检查增强接口
- 判断信号：路由定义中有 `internal` 标签但没有 IP 校验
- 正确做法：
  ```python
  async def verify_internal_ip(request: Request):
      client_host = request.client.host
      if client_host not in ("127.0.0.1", "::1", "localhost"):
          raise HTTPException(status_code=403, detail="Internal access only")
  ```

## 规范 12：敏感词过滤器初始化

**敏感词过滤器（AC 自动机）必须在应用启动时初始化，不能在请求时延迟加载。**

- 为什么：AC 自动机构建是 CPU 密集型操作，延迟加载会导致首次请求超时
- 判断信号：grep 搜索 `AhoCorasick(` 在请求处理函数内
- 正确做法：在 `main.py` 的 `lifespan` 事件中初始化

## 规范 13：自定义异常不覆盖内置

**自定义异常类名不能与 Python 内置异常同名。**

- 判断信号：grep 搜索 `class Error(Exception)` 或 `class Warning(Exception)`
- 正确做法：使用业务前缀，如 `NewsAPIError`、`WorkflowError`

## 规范 14：日志保留 traceback

**错误日志必须包含完整 traceback，便于问题排查。**

- 判断信号：grep 搜索 `logger.error(e)` 没有 `exc_info=True`
- 正确做法：
  ```python
  logger.exception("处理新闻失败")  # 自动包含 exc_info=True
  # 或
  logger.error("处理新闻失败", exc_info=True)
  ```

## 规范 15：分页查询必须 limit

**所有数据库查询必须有限制，禁止返回全表数据。**

- 判断信号：grep 搜索 `.all()` 没有 `.limit()`
- 正确做法：
  ```python
  stmt = select(Model).where(Model.status == status).limit(1000)
  result = await session.execute(stmt)
  ```

## 规范 16：前后端字段契约

**前后端字段命名必须遵循约定，转换在序列化层完成。**

- 后端输出：snake_case（与数据库一致）
- 前端接收：camelCase（与 JavaScript 习惯一致）
- 转换位置：Pydantic model 的 `alias` 或手动序列化函数
- 判断信号：前端代码中出现 `snake_case` 字段名

## 规范 17：缓存主动失效

**写操作后删除缓存，不更新缓存。**

- 为什么：更新缓存可能导致并发脏数据，删除缓存让下次读取自然重建
- 判断信号：grep 搜索 `redis.setex` 紧跟在 `db.update` 之后
- 正确做法：
  ```python
  await db.update(record)
  await redis.delete(cache_key)  # 删除而非更新
  ```

## 规范 18：工作流重试上限

**每个工作流步骤必须有最大重试次数，防止无限重试。**

- 适用：LLM 改写、TTS 合成、COS 上传
- 判断信号：grep 搜索 `while True` 或递归调用没有 base case
- 正确做法：通过配置驱动最大重试次数，超过后标记失败并告警

## 规范 19：敏感信息不落地

**密码、API Key、Token 等敏感信息禁止写入日志、数据库或文件。**

- 判断信号：grep 搜索 `logger.info.*password`、`logger.debug.*token`
- 正确做法：使用环境变量或密钥管理服务（如 AWS Secrets Manager）

## 规范 20：测试隔离

**每个测试用例必须独立，不依赖其他测试的执行顺序。**

- 适用：单元测试、集成测试
- 判断信号：测试之间共享全局状态（如同一个数据库记录）
- 正确做法：
  - 使用 fixture 创建独立的测试数据
  - 测试完成后清理数据（rollback 或删除）
  - 使用内存数据库（SQLite in-memory）避免数据污染

## 规范 21：配置热生效延迟重建

**运行时配置变更导致资源（Semaphore / 连接池 / 线程池）需要重建时，必须标记 dirty 延迟重建，禁止立即重建。**

- 为什么：立即重建会导致当前运行任务的 `finally release()` 操作新资源引起计数错乱，且旧资源上等待的任务会永久阻塞泄漏
- 适用：Semaphore 重建、连接池重建、线程池重建等有状态资源的配置热生效
- 不适用：只读配置（立即生效无副作用）、无等待者的无状态资源
- 判断信号：grep 搜索配置更新后立即 `new Semaphore()` / `new ConnectionPool()` 重建资源
- 正确做法：
  ```python
  # 标记 dirty，延迟到安全时机（无活跃持有时）重建
  def update_config(self, new_max: int):
      self._max_concurrent = new_max
      self._config_dirty = True  # 标记，不立即重建

  async def acquire(self):
      if self._config_dirty and self._active_count == 0:
          self._rebuild()  # 安全时机重建
          self._config_dirty = False
      return await self._semaphore.acquire()
  ```

## 规范 22：队列状态 DB 权威源

**需要重启恢复的状态（ID 生成器、计数器、队列任务）必须以 DB 为权威源，内存缓存仅作加速层。**

- 为什么：纯内存缓存（TTLCache / dict）重启后丢失，导致 ID 重复、任务重复执行
- 适用：workflow_id 生成、序号计数器、分布式 ID、队列任务持久化
- 不适用：纯缓存数据（丢失可接受）、临时计算结果
- 判断信号：grep 搜索内存计数器（`TTLCache` / `self._counter`）无 DB 校验
- 正确做法：
  ```python
  # DB 当日最大序号校验补充内存缓存
  def _get_next_seq(self, date_str: str) -> int:
      cache_seq = self._cache.get(f"seq:{date_str}", 0)
      db_max_seq = self._get_db_max_seq(date_str)  # DB 权威源
      seq = max(cache_seq, db_max_seq + 1)
      self._cache.set(f"seq:{date_str}", seq)
      return seq
  ```

## 规范 23：时长/容量约束的自动调整

**所有有时间、容量、大小等硬性约束的拼接/聚合操作，必须在最终校验前实现自动调整能力，禁止直接报错失败。**

- 适用：音频拼接、文档生成、报表输出、批量数据处理
- 不适用：实时流处理（不能追加/切除）、精确时长要求（如音乐视频同步）
- 判断信号：grep 搜索 duration.*超出.*范围、length.*exceed、size.*limit 后直接 raise
- 正确做法：
  1. 计算最终结果的实际值
  2. 不足时追加填充物（静音、空白页、默认内容等）
  3. 超出时从末尾切除多余部分
  4. 调整后必须二次校验作为兜底

## 规范 24：确定性失败的重试无效性

**工作流步骤的重试只对瞬态失败（网络超时、临时 IO 错误）有意义。对于确定性失败（输入数据导致的结果不变），应在步骤内部自动调整，而非依赖重试。**

- 适用：工作流编排、ETL 流水线、批处理任务
- 不适用：纯计算步骤（重试本身无意义，应直接失败）
- 判断信号：grep 搜索步骤函数内部无外部状态依赖（无网络调用、无文件读写、无 DB 查询）
- 正确做法：
  1. 识别步骤函数的输入是否可变
  2. 输入不变时，在函数内部实现自动调整（如音频时长填充）
  3. 输入可变时，保留重试机制（如网络请求）
  4. 在日志中标注重试原因类型（transient vs deterministic）


## 规范 25：第三方服务模型名称以官方文档为准

**所有第三方 AI 服务商的模型名称必须以官方文档为事实源，禁止自行编造或猜测大小写。**

- 适用：LLM/TTS/存储等第三方服务接入
- 不适用：内部自研服务
- 判断信号：grep 搜索预设配置中的模型名，与官网文档逐字核对
- 正确做法：新接入服务商时先查阅官方文档确认模型名称大小写，修改预设默认模型时同步更新定价表
- 注意：模型名称是区分大小写的字符串，deepseek-v4-flash 与 DeepSeek-V4-Flash 是不同的标识符

## 规范 26：配置持久化与返显完整性

**所有配置输入框的值必须完整持久化到数据库，并在页面加载时正确返显。预设切换时不应覆盖已保存的 API Key。**

- 适用：所有配置管理场景（LLM/TTS/通知/存储）
- 不适用：一次性表单（无需持久化）
- 判断信号：grep 搜索预设切换函数，确认是否保留 api_key
- 正确做法：预设切换只更新 base_url 和 model，保留 api_key；页面加载后自动匹配预设（基于 base_url）；前端 selectedPreset 状态与下拉框实际选中值同步

## 规范 27：模型定价表同步更新

**每当修改或新增模型名称时，必须同步检查定价表中是否包含该模型条目。**

- 适用：LLM 服务商模型配置变更
- 不适用：无费用计费的内部服务
- 判断信号：grep 搜索新增模型名是否在 MODEL_PRICING 中存在
- 正确做法：修改预设模型时，同时检查并更新定价表，缺失定价条目的模型将使用默认费率，导致费用统计不准确

## 规范 28：批量删除的事务原子性与级联规范

**所有批量删除操作必须在一个数据库事务中完成，按依赖逆序删除，任一校验失败整批回滚，禁止部分删除。**

- 适用：任何涉及多表关联数据的删除操作
- 不适用：单表简单删除、软删除场景、需要保留审计追溯的场景
- 判断信号：grep 搜索 delete( 后无 commit() 包裹、多表删除无事务上下文
- 正确做法：
  1. 前置校验：检查所有 ID 存在性、运行状态、权限
  2. 依赖逆序删除：从叶子表到根表（play_progress → play_log → episode → review → script → material → workflow_step → workflow）
  3. 单事务提交：wait db.commit() 包裹全部删除操作
  4. 返回统计：删除接口返回各类数据的删除数量
  5. 前端确认后执行：批量删除前必须二次确认，明确提示不可恢复

**级联删除依赖顺序表**：

| 顺序 | 表名 | 依赖关系 | 说明 |
|------|------|---------|------|
| 1 | play_progress | episode_id FK | 播放进度依赖节目 |
| 2 | play_log | episode_id FK | 播放日志依赖节目 |
| 3 | episode | script_id/review_id/workflow_id FK | 节目依赖审核和稿件 |
| 4 | review | script_id FK | 审核依赖稿件 |
| 5 | script | workflow_id FK | 稿件依赖工作流 |
| 6 | material | workflow_id FK | 素材依赖工作流 |
| 7 | workflow_step | workflow_id FK (cascade delete-orphan) | 步骤依赖工作流 |
| 8 | workflow | 根表 | 工作流本身 |

**注意事项**：
- COS 对象（音频文件、临时文件）不在数据库事务范围内，需单独处理或由运维清理
- 正在运行的工作流禁止删除，避免后台任务继续写入残留数据
- 批量删除接口应设置 max_length 上限（建议 100），防止单次事务过大

---

## 规范 29：前端多选交互规范

**涉及批量操作的前端表格必须实现选择列、选中计数、二次确认和删除后分页修正。**

- 适用：所有需要批量操作的数据表格
- 判断信号：grep 搜索 el-table 无 	ype="selection"、批量操作无确认框
- 正确做法：
  1. 表格添加 	ype="selection" 列，仅管理员可见
  2. 使用 @selection-change 跟踪选中状态
  3. 批量操作按钮显示选中数量，数量为 0 时禁用
  4. 操作前 ElMessageBox.confirm 二次确认，提示不可恢复
  5. 删除后清空选择、修正分页（若当前页无数据则回退一页）

---

## 规范 30：路由静态路径优先级（强化版）

**静态路由必须在动态路由之前定义，这是 FastAPI 和 Vue Router 的共同规则。**

- 适用：所有路由定义（后端 FastAPI / 前端 Vue Router）
- 判断信号：grep 搜索静态路由（如 /batch-delete）定义在动态路由（如 /{id}）之后
- 正确做法：
  1. FastAPI：@router.post("/batch-delete") 必须在 @router.get("/{workflow_id}") 之前
  2. Vue Router：静态路径（如 workflows）必须在动态路径（如 workflows/:id）之前
  3. 新增批量操作接口时，必须检查同级路由表中是否有动态路径在其后

---
