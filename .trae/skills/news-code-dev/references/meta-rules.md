# 元规范

本文档定义 MorningBrief 项目开发过程中必须遵守的 22 条元规范。这些规范来源于实际开发中遇到的问题和经验教训。

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

## 规范 8：时区一致性

**项目内所有跨模块时间判定必须使用同一时区源，禁止混用 UTC 与本地时间。**

- 为什么：ai_budget 按日重置 token 用量、workflow_scheduler 按本地日期触发、rewriter 按 crawled_at 本地日期回溯、crawler_dedup 按 TTL 清理。如果 ai_budget 用 UTC 而其他模块用本地时间，会导致本地跨日时额度累加到错误的 UTC 日，触发"今日已用 501,599，上限 500,000"误报
- 判断信号：grep 搜索 `datetime.now(timezone.utc)` 或 `tz=timezone.utc` 在业务模块（非 core/timeutil.py 工具函数）
- 正确做法：
  - 项目选定时区源后，所有业务模块统一使用（本项目使用 `datetime.now()` 本地时间）
  - 时区封装在 `core/timeutil.py` 内部，业务模块不直接调用时区相关函数
  - 跨日额度计算、定时任务、去重表 TTL、素材回溯必须使用同一时区源
- 适用：跨日额度计算、定时任务、去重表 TTL、素材回溯
- 不适用：单次本地时间戳、纯日志时间

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

---

## 规范 31：启动脚本路径含空格安全封装

**为什么**：系统 Python 路径可能包含空格（如 F:\Program Files\Python3.14\python.exe）。PowerShell 的 Start-Process -ArgumentList 会将含空格的字符串重新拆分引号，导致可执行文件路径被截断成 F:\Program。

- 适用：所有 .bat + .ps1 启动/构建脚本
- 不适用：路径不含空格的场景（但应统一防护）
- 判断信号：grep 搜索 Start-Process 后无 /s /c 双层引号封装
- 正确做法：
  1. 构造完整命令字符串 " 2>&1 & pause"
  2. 使用 cmd /d /s /c "" 四层引号封装
  3. -ArgumentList 传数组 @("/d", "/s", "/c", "\"\"")
- 构建脚本同理：uild-exe.ps1 在 PyInstaller COLLECT 阶段需先终止占用旧产物的进程


---

## 规范 32：构建脚本并发保护

**为什么**：多次执行构建脚本可能导致旧 PyInstaller 进程未完全退出，新旧进程同时写入 dist 目录造成 PermissionError / WinError 32。

- 适用：所有 PyInstaller 构建、打包脚本
- 不适用：纯编译型语言构建（C/C++/Rust）
- 判断信号：grep 搜索 Remove-Item 后无进程检查和删除验证
- 正确做法：
  1. 构建前先按可执行路径和命令行查找并终止占用旧产物的进程
  2. 等待进程退出（WaitForExit + 超时）
  3. 删除旧产物时用 	ry/throw 而非 SilentlyContinue，验证删除成功
  4. 删除失败时输出明确提示，而非静默继续让 PyInstaller 数分钟后才报错

---

## 规范 33-43：2026-07-15 工作流执行链路复盘新增规范

> 以下规范来源于工作流 wf-20260714-0001 到 wf-20260715-0004 的执行链路故障复盘，覆盖时区漂移、级联清理、容错分支、动态注入、关联更新、blob 错误解、频道级覆盖、定时触发、类型契约、状态恢复、标题冗余等高频故障场景。

### 规范 33：时区一致性全局统一

**跨模块时间判定（预算限流/调度/回溯/TTL）必须使用同一时区源。**

- 为什么：ai_budget 用 UTC 而其他模块用本地时间，导致本地跨日时额度累加到错误的 UTC 日
- 判断信号：grep `datetime.now(timezone.utc)` 与 `datetime.now()` 在同一项目混用
- 正确做法：所有跨日判定统一使用本地时间 `datetime.now()`，时区封装在 core/timeutil.py
- 适用：跨日额度计算、定时任务、去重表 TTL、素材回溯
- 不适用：单次本地时间戳、纯日志时间

### 规范 34：主从表级联清理完整性

**删除主表记录时必须同步处理所有引用主表 ID 的从表（重置或删除）。**

- 为什么：删除 workflow 后 material 被级联删除但 crawler_dedup 残留，导致爬虫重新爬取时所有 URL 命中 dedup 表，入库 0 条
- 判断信号：grep `delete(Model)` 后无对从表的 update/delete
- 正确做法：删除主表前先 `UPDATE material SET workflow_id=NULL, status='pending'`（保留素材重置状态），并清理 crawler_dedup 中孤儿 URL
- 适用：workflow → material/crawler_dedup/script/review/episode
- 不适用：无外键引用的独立表

### 规范 35：0 结果容错分支

**查询返回 0 条不一定是错误，应先检查是否有可用的历史/回退资源。**

- 为什么：crawler 爬到 0 条新素材时，可能 material 表已有历史 pending 素材可用。直接 `if count == 0: raise` 会导致工作流中断
- 判断信号：grep `if count == 0: raise` 后无 `pending_count` / `fallback` 检查
- 正确做法：0 条新结果时先查询是否有可用历史资源，有则放行并记录日志，无才报错
- 适用：爬虫采集、LLM 改写选题、审核队列
- 不适用：必填字段缺失、鉴权失败

### 规范 36：动态注入而非硬编码条件

**业务参数应通过动态注入 prompt/字段/参数实现，禁止在模板中硬编码后用 has_template 条件跳过。**

- 为什么：思考问题开关用 `if config_flag and not template_text` 跳过，所有频道都有自定义 rewrite_template，`not template_text` 永远为 False，开关被绕过
- 判断信号：grep `if config_flag and not template_text` 之类的多条件跳过
- 正确做法：配置开关直接控制后缀追加（`if enable_flag: prompt += suffix`）
- 适用：LLM prompt 后缀、字段可选序列化、特性开关
- 不适用：安全相关的硬约束

### 规范 37：选题后关联关系更新

**业务流程中选取已有记录后，必须立即 UPDATE 关联字段。**

- 为什么：rewriter 选题改写后未更新 material.workflow_id，工作流详情页按 workflow_id 过滤查不到素材
- 判断信号：grep `select(Material)` 后无 `update(Material).workflow_id=`
- 正确做法：选题后立即 `UPDATE material SET workflow_id=当前工作流, status='selected' WHERE id IN (选中ID)`
- 适用：素材选题、任务分配、角色关联
- 不适用：只读查询

### 规范 38：blob/二进制响应错误解析

**responseType='blob' 的请求在错误分支需读取 blob.text() 解析 JSON 获取真实 message。**

- 为什么：axios 拦截器无法读取 Blob 类型的 .message 字段，前端只能显示 "Network Error"
- 判断信号：前端 grep `responseType: 'blob'` 后无 `parseBlobError`
- 正确做法：catch 中检查 `err.response?.data instanceof Blob`，是则 `await blob.text()` 解析 JSON
- 适用：文件下载、音频流、图片请求
- 不适用：JSON 响应

### 规范 39：频道级配置覆盖全局

**业务参数应支持频道级覆盖，频道未配置时回退全局 settings。**

- 为什么：只做全局配置，所有频道共享同一参数，无法差异化运营
- 判断信号：grep `settings.X` 在业务代码中无 `if ch.x is not None` 频道级检查
- 正确做法：解析配置时先读全局 settings 作为默认值，再查询频道记录，频道字段非 None 则覆盖
- 适用：多频道/多租户场景的所有可配置参数
- 不适用：全局唯一参数（如数据库路径、JWT 密钥）

### 规范 40：定时任务频道级触发

**全局 cron 触发时必须为所有未配置独立定时的活跃频道各触发一次。**

- 为什么：只触发一个无频道的工作流，多频道场景下只有"默认频道"执行定时任务
- 判断信号：grep `_cron_trigger` 中无遍历活跃频道列表
- 正确做法：全局 cron 查询所有 `is_active=1 AND schedule_time IS NULL` 的频道，为每个频道各触发一个工作流
- 适用：多频道调度、多租户定时
- 不适用：单频道项目

### 规范 41：el-switch 类型契约

**当后端返回 int（0/1）时，el-switch 必须显式 :active-value="1" :inactive-value="0"。**

- 为什么：el-switch 默认 active-value=true（bool），JavaScript 严格相等 `1 !== true`，开关死循环无法持久化
- 判断信号：grep `<el-switch` 无 `:active-value` 且后端字段为 int
- 正确做法：el-switch 显式配置 `:active-value="1" :inactive-value="0"` 与后端 int 类型一致
- 适用：所有后端返回 int（0/1）的开关字段
- 不适用：后端已返回 bool

### 规范 42：v-loading 状态恢复

**页面 visibility 切换时必须先重置所有 loading 状态为 false，用 nextTick 延迟加载。**

- 为什么：Element Plus v-loading 在窗口最小化/恢复时 DOM 布局变化导致 mask 元素残留，页面永久遮罩
- 判断信号：grep `handleVisibilityChange` 中直接调用 load 而无 nextTick
- 正确做法：切回时先重置所有 loading 为 false，用 nextTick 延迟到下一帧再执行加载
- 适用：所有带 v-loading + visibility 事件的页面
- 不适用：无 v-loading 的简单页面

### 规范 43：页面标题冗余

**顶部导航已显示页面名时，页面内不再渲染 page-title。**

- 为什么：页面内 page-title 与顶部导航重复，占用屏幕空间，破坏视觉层次
- 判断信号：grep `<span class="page-title">` 且 Layout 侧边栏已有同名菜单
- 正确做法：移除页面内 page-title，CSS `.top-bar` 改为 `justify-content: flex-end`
- 适用：所有带顶部导航的后台页面
- 不适用：无顶部导航的独立页面

## 规范 56-65：2026-07-17 数据库维护模块开发复盘新增规范

### 规范 56：SQLAlchemy Inspector run_sync 陷阱

**run_sync 回调参数是 Session 而非 Connection，使用 Inspector 时必须先 .connection() 转换。**

- 为什么：`AsyncSession.run_sync(callback)` 的 callback 参数是同步 `Session` 对象，但 `sqlalchemy.inspect()` 需要的是 `Connection` 对象。直接将 Session 传给 Inspector 会报错或返回不完整结果。
- 判断信号：grep `run_sync` + `inspect(` 检查回调内是否有 `.connection()` 转换
- 正确做法：
  ```python
  async def get_table_schema(table_name: str):
      async with AsyncSession() as session:
          def _inspect(sync_session):
              # Session → Connection 转换
              conn = sync_session.connection()
              inspector = inspect(conn)
              return inspector.get_columns(table_name)
          return await session.run_sync(_inspect)
  ```
- 错误做法：
  ```python
  # ❌ 直接将 Session 传给 Inspector
  def _inspect(sync_session):
      inspector = inspect(sync_session)  # 报错或返回不完整
  ```
- 适用：动态表结构反射、数据库维护模块、未知表浏览
- 不适用：已知表结构（应直接用 ORM 模型的 `__table__.columns`）

### 规范 57：main.py 导入完整性

**main.py 中使用到的所有中间件、函数、配置必须显式导入，启动前必须预检。**

- 为什么：main.py 作为应用入口，使用了 RequestIdMiddleware、setup_logging、register_exception_handlers、get_settings 等符号。如果使用了但未导入，服务启动时直接 NameError 崩溃，且日志可能为空（因为 logging 未初始化）。
- 判断信号：
  - grep main.py 中使用的符号是否都有对应 `from app.xxx import yyy`
  - 启动前预检：`python -m py_compile main.py` + `python -c "from app.main import app"`
- 正确做法：
  ```python
  from app.config import get_settings
  from app.core.exceptions import register_exception_handlers
  from app.core.logging_setup import setup_logging
  from app.middleware.request_id import RequestIdMiddleware
  from app.paths import resolve_admin_dist
  ```
- 适用：所有应用入口文件（main.py / launcher.py）
- 不适用：模块内部文件（Python 导入链会自然检查）

### 规范 58：CONFIRM_DELETE 令牌双重确认

**危险操作（删表/清空/VACUUM）必须要求输入 CONFIRM_DELETE 令牌，令牌通过配置文件管理。**

- 为什么：危险操作一旦执行不可逆。仅靠按钮点击确认不够安全（误点），必须要求用户输入特定令牌字符串（如 `CONFIRM_DELETE`），形成双重确认。令牌值通过配置文件管理，禁止硬编码。
- 判断信号：grep 危险操作端点（delete/clear/vacuum/truncate）是否检查 `confirm_token` 参数
- 正确做法：
  ```python
  @router.delete("/tables/{table_name}/rows")
  async def delete_rows(table_name: str, confirm_token: str = Body(...)):
      if confirm_token != settings.CONFIRM_DELETE_TOKEN:
          raise BizError("确认令牌不匹配")
      # 执行删除
  ```
- 适用：所有危险操作（删除表、清空数据、VACUUM、DROP、TRUNCATE）
- 不适用：普通增删改查、只读操作

### 规范 59：敏感字段动态脱敏

**表数据导出时必须脱敏敏感字段，采用静态字段名 + 动态字段名匹配双重策略。**

- 为什么：数据库维护模块导出表数据时，password_hash / token / secret 等字段必须脱敏。但仅靠静态字段名列表无法覆盖动态表（如 ai_config 表的 config_value 字段可能含密钥）。必须同时用字段名匹配（含 password/secret/token/key 的字段名）和值匹配。
- 判断信号：grep 导出函数是否有脱敏逻辑，是否仅静态字段名匹配
- 正确做法：
  ```python
  SENSITIVE_FIELD_PATTERNS = ["password", "secret", "token", "api_key", "access_key"]

  def mask_sensitive(row: dict) -> dict:
      for key in row:
          if any(p in key.lower() for p in SENSITIVE_FIELD_PATTERNS):
              row[key] = "****"
      return row
  ```
- 适用：表数据导出、数据库维护、日志记录
- 不适用：内部数据传输（已加密通道）

### 规范 60：应用层级联删除策略

**删除主表记录时必须同步处理从表，级联策略：cascade（删除关联行）+ set_null（置空外键）。**

- 为什么：数据库级 ON DELETE CASCADE 不够灵活（无法区分 cascade 和 set_null 策略），且 SQLite 对外键级联支持有限。应用层级联可以精细控制每张从表的处理方式。
- 判断信号：grep `db.delete(main)` 后是否有对从表的处理逻辑
- 正确做法：
  ```python
  async def delete_workflow(db, workflow_id):
      # cascade: 删除关联行
      await db.execute(delete(Material).where(Material.workflow_id == workflow_id))
      await db.execute(delete(Script).where(Script.workflow_id == workflow_id))
      # set_null: 置空外键
      await db.execute(update(Review).where(Review.workflow_id == workflow_id).values(workflow_id=None))
      # 删除主表
      await db.execute(delete(Workflow).where(Workflow.id == workflow_id))
  ```
- 适用：需要精细控制级联策略的场景、SQLite 数据库
- 不适用：简单外键关系（可用数据库级 ON DELETE CASCADE）

### 规范 61：VACUUM AUTOCOMMIT 模式

**SQLite VACUUM 必须在 AUTOCOMMIT 隔离级别执行，禁止在事务内执行。**

- 为什么：VACUUM 是 SQLite 特殊命令，需要重建整个数据库文件，不能在事务内执行。如果在 `async with session.begin()` 事务块内执行 VACUUM，会报 `OperationalError: cannot VACUUM from within a transaction`。
- 判断信号：grep `VACUUM` 检查是否在 `async with session.begin()` 或 `async with engine.begin()` 事务块内
- 正确做法：
  ```python
  # 方式 1：AUTOCOMMIT 隔离级别
  async with engine.connect() as conn:
      await conn.execution_options(isolation_level="AUTOCOMMIT")
      await conn.execute(text("VACUUM"))

  # 方式 2：VACUUM INTO（不需 AUTOCOMMIT）
  await session.execute(text("VACUUM INTO :path"), {"path": backup_path})
  ```
- 适用：SQLite 数据库压缩、系统清理模块
- 不适用：MySQL（用 OPTIMIZE TABLE）、PostgreSQL（用 VACUUM，可在事务外执行）

### 规范 62：bindparam expanding IN 列表

**IN 查询的参数列表必须用 bindparam(expanding=True)，禁止字符串拼接。**

- 为什么：SQLAlchemy 异步模式下，IN 查询的参数列表如果用字符串拼接（如 `f"IN ({','.join(ids)})"`），会导致 SQL 注入风险和参数绑定失败。必须用 `bindparam(expanding=True)` 让 SQLAlchemy 自动处理变长参数。
- 判断信号：grep `IN (` 后跟字符串拼接而非 `bindparam(expanding=True)`
- 正确做法：
  ```python
  from sqlalchemy import bindparam

  stmt = select(Material).where(
      Material.id.in_(bindparam("ids", expanding=True))
  )
  result = await session.execute(stmt, {"ids": id_list})
  ```
- 适用：所有 IN 查询参数化
- 不适用：固定列表 IN 查询（如 `IN (1, 2, 3)`，但仍建议参数化）

### 规范 63：数据库维护白名单机制

**数据库维护操作必须基于白名单（允许操作的表清单），白名单通过配置文件管理。**

- 为什么：数据库维护模块如果允许操作所有表，可能误操作系统表（sqlite_sequence、sqlite_master）或敏感表。必须维护一个白名单，只允许操作白名单内的表。白名单通过配置文件管理，禁止硬编码。
- 判断信号：grep 表操作是否检查白名单
- 正确做法：
  ```python
  # 配置文件
  DB_ADMIN_ALLOWED_TABLES = ["workflow", "material", "script", "review", ...]

  # 服务层
  def _validate_table(table_name: str):
      if table_name not in settings.DB_ADMIN_ALLOWED_TABLES:
          raise BizError(f"表 {table_name} 不在白名单内")
  ```
- 适用：数据库管理后台、表 CRUD 操作
- 不适用：ORM 模型直接操作（已通过模型定义隔离）

### 规范 64：dry_run 预览模式

**清理/删除类操作必须提供 dry_run 预览模式，预览模式下不执行实际操作。**

- 为什么：清理/删除操作不可逆，用户需要先预览将要清理的内容（哪些记录、多少条、占用多少空间），确认后再执行。dry_run 模式返回预览结果但不执行实际删除。
- 判断信号：grep 清理/删除函数是否支持 `dry_run` 参数
- 正确做法：
  ```python
  async def cleanup_expired_logs(db, days: int, dry_run: bool = False):
      stmt = select(Log).where(Log.created_at < utcnow_naive() - timedelta(days=days))
      logs = (await db.execute(stmt)).scalars().all()
      if dry_run:
          return {"count": len(logs), "preview": [log.id for log in logs[:10]]}
      for log in logs:
          await db.delete(log)
  ```
- 适用：清理/删除类操作（过期记录、日志、缓存）
- 不适用：普通增删改查（不需要预览）

### 规范 65：审计日志完整覆盖

**所有 DML 操作和清理操作必须记录审计日志，包含操作类型/表名/记录 ID/操作人/时间戳。**

- 为什么：数据库维护和系统清理操作需要可追溯。审计日志记录谁在什么时间对哪张表的哪些记录做了什么操作，便于事后审计和问题排查。
- 判断信号：grep `db.delete`/`db.execute(delete(...))` 后是否有 `audit_log` 记录
- 正确做法：
  ```python
  async def _log_audit(db, action: str, table: str, record_id: str, user: str):
      audit = AuditLog(
          action=action,  # create/update/delete/vacuum/cleanup
          table_name=table,
          record_id=str(record_id),
          operator=user,
          created_at=utcnow_naive(),
      )
      db.add(audit)

  async def delete_row(db, table_name, row_id, user):
      await db.execute(delete(...))
      await _log_audit(db, "delete", table_name, row_id, user)
  ```
- 适用：所有 DML 操作和清理操作
- 不适用：查询操作（SELECT 不需要审计）

## 规范 66-75：2026-07-18 SonarQube 迭代闭环复盘新增规范

> 以下规范来源于 2026-07-18 SonarQube MCP 扫描 + 问题修复迭代闭环（23 个 OPEN 问题→0）+ Playwright E2E 12/12 PASS + pytest 单元测试 146/146 PASS 的完整复盘。

### 规范 66：认知复杂度阈值治理

**函数 cognitive_complexity ≤ 15，超阈值必须抽取辅助函数或重构为数据驱动。**

- 为什么：SonarQube 默认 cognitive_complexity 阈值 15。复杂度超阈值函数可读性差、难以测试、易引入缺陷。本次迭代发现 `tunnel_providers.py`、`maintenance_service.py`、`db_admin_service.py` 等函数均因 if/elif 链嵌套过深超标。
- 阈值参数（通过 project-config.json 配置）：
  - `max_function_lines`: 50（函数行数上限）
  - `max_nesting`: 3（嵌套层级上限）
  - `max_cognitive_complexity`: 15（与 SonarQube 一致）
- 判断信号：
  - grep `^    if` 在同一函数内连续出现 4 次以上
  - ruff `C901` 警告
  - SonarQube `cognitive_complexity` issue
- 正确做法：
  ```python
  # 抽取辅助函数
  def _validate_tunnel_config(config: dict) -> list[str]:
      errors = []
      if not config.get('provider'):
          errors.append('provider required')
      if not config.get('token'):
          errors.append('token required')
      return errors

  def create_tunnel(config: dict) -> Tunnel:
      errors = _validate_tunnel_config(config)  # 抽取后复杂度降低
      if errors:
          raise ValidationError(errors)
      # 主逻辑
  ```
- 错误做法：保持长函数 + 嵌套 if/elif
- 适用：业务逻辑复杂的 service/workflow 层
- 不适用：纯数据声明的 models 层、配置常量文件

### 规范 67：async 函数必须含 await

**`async def` 函数体内必须至少有一个 `await` 表达式，否则转为同步函数。**

- 为什么：SonarQube S7503 规则。`async def` 内无 `await` 会误导调用者认为该函数有 IO 操作可并发执行，实际是同步阻塞。本次迭代发现 `secrets.py` 中 `async def mask_secret()` 函数体内无 await，徒增事件循环开销。
- 判断信号：
  - grep `async def` 后 50 行内无 `await` 关键字
  - SonarQube S7503 issue
- 正确做法：
  ```python
  # 方式 1：转同步函数
  def mask_secret(value: str) -> str:
      if not value:
          return ''
      return value[:4] + '*' * (len(value) - 8) + value[-4:]

  # 方式 2：补充 await 调用（如确有异步操作）
  async def fetch_secret(key: str) -> str:
      value = await cache.get(key)  # 必须有 await
      return mask_secret(value)
  ```
- 例外：事件回调、`asyncio.create_task` 包装的 fire-and-forget 任务（需注释说明）
- 适用：所有 async 函数
- 不适用：事件回调函数（如 `async def on_event()` 注册回调）

### 规范 68：正则表达式捕获组优化

**正则表达式中未使用的捕获组必须改为非捕获组 `(?:...)`，仅保留需 `group()` 提取的捕获组。**

- 为什么：SonarQube S6395 规则。捕获组 `(...)` 比 `(?:...)` 慢（需分配内存记录匹配内容），且未使用的捕获组会误导维护者认为该子串会被提取。本次迭代发现 `secrets.py` 中多处 `re.match(r'(prefix)(.*)')` 仅用 `group(0)` 但定义了多个捕获组。
- 判断信号：
  - grep `re.match` / `re.sub` / `re.compile` 中含 `(...)` 但后续无 `group(1)`/`group(2)` 等提取
  - SonarQube S6395 issue
- 正确做法：
  ```python
  # ✅ 使用非捕获组
  match = re.match(r'(?:prefix)(.*)', value)
  if match:
      return match.group(1)  # 仅提取需要的组

  # ❌ 使用捕获组但未提取
  match = re.match(r'(prefix)(.*)', value)  # 浪费内存
  ```
- 适用：所有使用 `re` 模块的代码
- 不适用：需要 `group(N)` 提取子串的场景（必须用捕获组）

### 规范 69：list() 调用必要性检测

**`list(iterable)` 仅在需要索引访问或多次迭代时使用，单一 `for` 循环直接迭代可迭代对象。**

- 为什么：SonarQube S7504 规则。`list(dict.keys())` 在 Python 3 中 dict.keys() 已是可迭代视图，无需转 list 即可迭代。`list()` 转换浪费内存（一次性加载所有元素到列表）。本次迭代发现 `ai_config_service.py` 中 `for key in list(config.keys())` 多余转换。
- 判断信号：
  - grep `for \w+ in list\(` 模式
  - SonarQube S7504 issue
- 正确做法：
  ```python
  # ✅ 直接迭代
  for key in config.keys():  # 或 for key in config:
      process(key)

  # ❌ 多余 list() 转换
  for key in list(config.keys()):
      process(key)
  ```
- 例外：需在迭代中修改 dict（迭代时增删 key 需先转 list 避免运行时错误）
- 适用：所有 `for` 循环代码
- 不适用：需索引访问 `lst[0]`、需多次迭代、迭代中修改集合

### 规范 70：未使用变量与参数检测

**变量、参数、导入声明后必须使用，禁止死代码。**

- 为什么：SonarQube S1481（未使用局部变量）/ S1128（未使用导入）。未使用的代码增加维护负担、误导维护者认为该变量/导入有用途、增加打包体积。本次迭代发现 `workflow_scheduler.py`、`maintenance_service.py` 中多处未使用 import 和局部变量。
- 判断信号：
  - ruff F841（未使用变量）/ F401（未使用导入）
  - pylint W0612 / W0611
  - SonarQube S1481 / S1128 issue
- 正确做法：直接删除未使用声明
  ```python
  # ❌ 未使用
  import os  # 未使用
  from typing import Optional  # 未使用

  def foo():
      unused_var = 42  # 未使用
      return "hello"

  # ✅ 删除后
  def foo():
      return "hello"
  ```
- 例外：协议要求的接口参数（如 `__init__(self, unused_param)` 协议签名）需用 `_unused_param` 前缀
- 适用：所有 Python 代码
- 不适用：协议接口、抽象基类、`__all__` 导出列表

### 规范 71：数据驱动重构模式

**同一函数内 ≥3 个 elif 判断同一变量时，必须重构为 `list[tuple]` + 循环。**

- 为什么：if/elif 链超过 3 个分支时，复杂度线性增长，难以维护和扩展。数据驱动重构将判断条件与处理逻辑解耦，新增分支只需追加 tuple，不需修改主流程。本次迭代发现 `tunnel_providers.py` 中按 provider 类型分发逻辑有 5 个 elif 分支。
- 判断信号：
  - 同一函数内 ≥3 个 `elif` 判断同一变量
  - 函数行数 >50 且含 ≥3 个 elif
- 正确做法：
  ```python
  # ✅ 数据驱动
  PROVIDER_HANDLERS: list[tuple[str, Callable]] = [
      ('ngrok', create_ngrok_tunnel),
      ('cloudflare', create_cloudflare_tunnel),
      ('frp', create_frp_tunnel),
      ('localtunnel', create_localtunnel),
  ]

  def create_tunnel(provider: str, config: dict) -> Tunnel:
      for name, handler in PROVIDER_HANDLERS:
          if provider == name:
              return handler(config)
      raise ValueError(f'Unknown provider: {provider}')

  # ❌ if/elif 链
  def create_tunnel(provider: str, config: dict) -> Tunnel:
      if provider == 'ngrok':
          return create_ngrok_tunnel(config)
      elif provider == 'cloudflare':
          return create_cloudflare_tunnel(config)
      elif provider == 'frp':
          return create_frp_tunnel(config)
      elif provider == 'localtunnel':
          return create_localtunnel(config)
      raise ValueError(f'Unknown provider: {provider}')
  ```
- 适用：分支数 ≥3 且处理逻辑相似的函数
- 不适用：分支逻辑差异大、仅 1-2 个分支、性能敏感场景（每次循环遍历开销）

### 规范 72：import 语句组织规范

**import 语句分三组（标准库→第三方库→项目内），每组内字母序排列。**

- 为什么：SonarQube S3863 规则。统一的 import 组织提升可读性、便于排查依赖来源、降低合并冲突概率。本次迭代发现 `DatabaseAdmin.vue`、`Maintenance.vue`、`Tunnel.vue` 中 import 顺序混乱。
- 判断信号：
  - eslint `import/order` 警告
  - isort `I001` 警告
  - SonarQube S3863 issue
- 正确做法：
  ```python
  # Python
  # 1. 标准库
  import os
  import sys
  from typing import Optional

  # 2. 第三方库
  from fastapi import FastAPI
  from sqlalchemy import select

  # 3. 项目内
  from app.core.config import settings
  from app.models.workflow import Workflow
  ```

  ```vue
  <!-- Vue SFC -->
  <script setup lang="ts">
  // 1. Vue 内置
  import { ref, computed, onMounted } from 'vue'
  import type { PropType } from 'vue'

  // 2. 第三方库
  import { ElMessage, ElMessageBox } from 'element-plus'
  import axios from 'axios'

  // 3. 项目内
  import { getWorkflowList } from '@/api/workflow'
  import type { WorkflowItem } from '@/types/workflow'
  </script>
  ```
- 适用：所有 Python 与前端代码
- 不适用：无（强制规范）

### 规范 73：DOM API 现代化规范

**优先使用现代 DOM API，废弃 API 必须替换。**

- 为什么：SonarQube S7762 规则。现代 DOM API 更简洁、性能更好、跨浏览器兼容性更佳。本次迭代发现前端代码中 `removeChild`、`className` 字符串拼接等废弃写法。
- 判断信号：
  - grep `removeChild(`
  - grep `parentNode.appendChild`
  - grep `className =` 后跟字符串拼接
- 正确做法：
  ```javascript
  // ✅ 现代 API
  element.remove()
  parent.append(child)
  element.classList.add('class1', 'class2')
  element.classList.remove('class1')
  element.dataset.userId = '123'  // 替代 getAttribute('data-user-id')

  // ❌ 废弃 API
  parent.removeChild(element)
  parent.appendChild(child)
  element.className = 'class1 class2'
  element.getAttribute('data-user-id')
  ```
- 适用：所有前端 JavaScript/TypeScript 代码
- 不适用：需兼容 IE11 的项目（本项目仅支持现代浏览器，无此约束）

### 规范 74：空 except 块禁止规范

**except 块禁止为空或仅 `pass`，必须包含日志记录或显式注释说明为何忽略异常。**

- 为什么：SonarQube S2486 规则。空 except 块会吞掉异常，导致问题难以排查。本次迭代发现 `db_admin_service.py`、`ai_config_service.py` 中多处 `except Exception: pass`。
- 判断信号：
  - grep `except[\\s\\w]*:[\\s\\n]{1,3}pass`
  - grep `except[\\s\\w]*:[\\s\\n]{1,3}\\}`
  - SonarQube S2486 issue
- 正确做法：
  ```python
  # ✅ 记录日志
  try:
      risky_operation()
  except Exception as e:
      logger.exception(f'Failed to risky operation: {e}')
      # 或 logger.warning(f'Ignore expected error: {e}')

  # ✅ 显式注释（仅限确知可忽略的异常）
  try:
      cache.clear()
  except Exception:
      pass  # 缓存清理失败不影响主流程，下次启动会自动重建

  # ❌ 空 except 块
  try:
      risky_operation()
  except Exception:
      pass  # 异常被吞，问题无法排查
  ```
- 适用：所有 Python 与前端 try/catch 代码
- 不适用：协议要求的静默失败（需注释说明）

### 规范 75：SonarQube 扫描闭环规范

**发版前必须执行完整 SonarQube 扫描-修复-回归闭环，二次扫描 OPEN=0 且无新增问题方可发版。**

- 为什么：本次迭代通过 SonarQube MCP 扫描发现 23 个 OPEN 问题，单次修复后二次扫描又出现新问题（修复引入新缺陷），证明必须执行回归扫描验证。仅修复首次扫描问题不足以保证质量。
- 闭环流程（7 步）：
  1. 启动扫描：`sonar-scanner` 命令（路径与 token 走环境变量）
  2. 等待分析完成：轮询 `tasks/search` API status=SUCCESS
  3. 拉取问题：`issues/search` API + `componentKeys=` 过滤
  4. 问题分类（按 severity）：
     - BLOCKER/CRITICAL → 必须修复（P0）
     - MAJOR → 应修复（P1）
     - MINOR → 建议修复（P2）
     - INFO → 记录即可（P3）
  5. 按问题类型应用修复模式（参考规范 66-74）
  6. 单元测试验证：`pytest --asyncio-mode=auto`
  7. 二次扫描回归：验证 OPEN=0 且无新增问题
- 配置参数（全部走 project-config.json#sonarqube）：
  - `scanner_path_env_var`: SONAR_SCANNER_HOME
  - `token_env_var`: SONAR_TOKEN
  - `project_key`: 项目标识
  - `sources`: 扫描范围
  - `exclusions`: 排除路径
  - `severity_must_fix`: 必修级别列表
  - `max_regression_retries`: 最大回归重试次数（默认 3）
- 判断逻辑：
  - 二次扫描 OPEN 数量减少 → 继续验证
  - 二次扫描 OPEN 数量持平或增加 → 触发回滚检查（修复方式错误）
  - 二次扫描出现新问题 → 修复引入新缺陷，需重新修复
- 适用：所有发版前完整验证
- 不适用：热修复（hotfix）的快速验证、未集成 SonarQube 的项目

## 规范 76-85：2026-07-20 小程序播放与跨端数据流复盘新增规范

> 以下规范来源于 2026-07-20 微信小程序「今日要闻」迭代修复完整复盘：覆盖播放卡顿、上下首切换标题不刷新、继续播放按钮状态不同步、倍速不生效、tab 切换详情不刷新、文稿图片缺失、背景图缺失、中文 URL 静默失败等 11 类问题。所有阈值通过 `project-config.json#miniprogram_playback`、`project-config.json#cache_versioning`、`project-config.json#url_safety` 配置管理。

### 规范 76：含非 ASCII 字符的 URL 必须 encodeURI

**小程序/浏览器中含中文或特殊字符的资源 URL 必须用 `encodeURI()` 编码后再赋值给 `src`/`href`，禁止直接拼接裸 URL。**

- 为什么：iOS 微信底层 AVPlayer 对含中文（如 `国际视野`）的 URL 不会触发任何回调（onPlay/onCanplay/onError 全部静默），表现为进度条不动、播放按钮不切换、控制台无错误日志，难以排查。Android 端可正常播放造成"假性跨端兼容"错觉。本次迭代 `channel_slug` 含中文时 `audio_url` 在 iOS 上静默失败。
- 阈值参数（通过 `project-config.json#url_safety` 配置）：
  - `require_encode_for_non_ascii`: true（强制编码开关）
  - `allowed_unencoded_patterns`: ["^https?://[a-zA-Z0-9.-]+(?::\\d+)?/[a-zA-Z0-9._/-]*$"]（仅纯 ASCII 路径豁免）
  - `encoding_function`: "encodeURI"（使用 encodeURI 保留 URL 结构语义，禁止 encodeURIComponent 全编码会破坏 / 与 :）
- 判断信号：
  - grep `audioManager\.src\s*=\s*[^e]` 或 `\.src\s*=\s*['"]http[^'"]*[\u4e00-\u9fa5]` 在小程序代码中
  - URL 字符串中含 `[\u4e00-\u9fa5]` 中文字符未编码
- 正确做法：
  ```javascript
  // ✅ 编码后再赋值
  audioManager.src = encodeURI(episode.audio_url);
  // ✅ 或在生成 URL 时就编码（推荐：后端生成时即编码）
  // 后端: audio_url = f"/audio/episodes/{date}/{quote(channel_slug)}.mp3"
  //       → 已编码为 %E5%9B%BD%E9%99%85%E8%A7%86%E9%87%8E
  ```
- 错误做法：
  ```javascript
  // ❌ 直接赋值裸 URL
  audioManager.src = episode.audio_url;  // 含中文时 iOS 静默失败
  ```
- 适用：所有小程序 `audioManager.src`、`<image src>`、`wx.downloadFile`、`<web-view src>` 资源 URL
- 不适用：纯 ASCII 路径（如 `/audio/episodes/20260720/news.mp3`）；后端已编码的 URL

### 规范 77：iOS 倍速切换必须 pause+play+seek 强制重新缓冲

**iOS 微信中播放状态下切换 `audioManager.playbackRate` 不会立即生效，必须 `pause() → 延时 → play() → 延时 → seek(原位置)` 强制底层缓冲重应用新倍速。**

- 为什么：iOS 微信 BackgroundAudioManager 的 `playbackRate` setter 不会主动重新缓冲当前流，倍速仅在下次 play 时生效。直接写入后用户感知"倍速没变"，反复点击触发 UI 抖动。Android 端写入即生效造成跨端表现不一致。
- 阈值参数（通过 `project-config.json#miniprogram_playback.rate_switch` 配置）：
  - `pause_delay_ms`: 100（pause 后等待底层状态切换）
  - `play_delay_ms`: 200（play 后等待缓冲就绪再 seek）
  - `seek_back_guard_ms`: 50（seek 位置回退容差，防止位置漂移）
  - `apply_method`: "pause_play_seek"（强制重新缓冲模式）
- 判断信号：
  - grep `audioManager\.playbackRate\s*=` 后无 `pause()` 调用
  - grep `setPlaybackRate` 函数体内仅一行赋值
- 正确做法：
  ```javascript
  function setPlaybackRate(rate) {
    audioManager.playbackRate = rate;  // 立即写入（Android 即时生效）
    // iOS 需强制重新缓冲
    if (!audioManager.paused && audioManager.currentTime > 0) {
      const pos = audioManager.currentTime;
      audioManager.pause();
      setTimeout(() => {
        audioManager.play();
        setTimeout(() => audioManager.seek(pos), 200);
      }, 100);
    }
  }
  ```
- 错误做法：
  ```javascript
  // ❌ 直接写入，iOS 上不生效
  function setPlaybackRate(rate) {
    audioManager.playbackRate = rate;
  }
  ```
- 适用：iOS 微信小程序音频倍速切换；同样适用 iOS Safari HTMLAudioElement
- 不适用：Android 微信（写入即生效）；非音频播放场景

### 规范 78：onTimeUpdate 必须 setData 节流

**小程序 `audioManager.onTimeUpdate` 回调触发频率可达 4-10 次/秒，必须用时间戳节流（≥`update_interval_ms`）后才能 `setData`，禁止每次回调都 setData。**

- 为什么：onTimeUpdate 每秒触发多次，每次 `setData` 触发渲染层通信，频繁通信导致：
  1. UI 卡顿（进度条抖动、按钮延迟响应）
  2. 通信信道拥堵（其他 setData 排队等待）
  3. 电量消耗加快
  本次迭代未节流时出现进度条卡顿，节流到 800ms 后流畅。
- 阈值参数（通过 `project-config.json#miniprogram_playback.time_update_throttle` 配置）：
  - `update_interval_ms`: 800（节流间隔，默认 800ms）
  - `force_update_on_pause`: true（暂停时强制更新一次，避免最终态偏差）
  - `force_update_on_seek`: true（seek 后强制更新一次）
- 判断信号：
  - grep `onTimeUpdate.*=>\s*{[^}]*setData` 无时间戳判断
  - 同一页面 setData 调用频率 > 2 次/秒
- 正确做法：
  ```javascript
  let lastTimeUpdate = 0;
  audioManager.onTimeUpdate(() => {
    const now = Date.now();
    if (now - lastTimeUpdate < 800) return;  // 节流
    lastTimeUpdate = now;
    this.setData({ currentTime: Math.floor(audioManager.currentTime) });
  });
  ```
- 错误做法：
  ```javascript
  // ❌ 每次回调都 setData
  audioManager.onTimeUpdate(() => {
    this.setData({ currentTime: Math.floor(audioManager.currentTime) });
  });
  ```
- 适用：所有小程序 `onTimeUpdate` 回调；类似高频事件（onScroll、onTouchMove）
- 不适用：低频事件（onPlay、onPause、onEnded）；非 setData 的纯逻辑处理

### 规范 79：异步上报必须有 in-progress 防重叠标志

**异步上报（进度上报、埋点上报）必须用模块级 `progressReporting`/`reporting` 标志位包裹，未完成的上报未返回前禁止发起下一次，防止请求重叠与数据覆盖。**

- 为什么：onTimeUpdate 触发上报时，若网络慢于节流间隔，多次 `fetch` 并发返回顺序不确定，后发起的请求可能覆盖先发起的进度（造成进度回退）。本次迭代进度上报未加标志位时，弱网下出现进度跳变。
- 阈值参数（通过 `project-config.json#miniprogram_playback.progress_report` 配置）：
  - `require_in_progress_flag`: true（强制标志位）
  - `flag_clear_on_failure`: true（失败也清标志，避免死锁）
  - `flag_clear_timeout_ms`: 10000（兜底超时清标志，防止异常未清）
- 判断信号：
  - grep `reportPlayProgress\|fetch.*progress` 无前置 `if (progressReporting) return` 判断
  - 同一上报函数内无 `try/finally` 清标志
- 正确做法：
  ```javascript
  let progressReporting = false;
  async function reportProgress(episodeId, position) {
    if (progressReporting) return;  // 防重叠
    progressReporting = true;
    try {
      await fetch(`${BASE_URL}/playlogs/progress`, { method: 'POST', body: JSON.stringify({ episode_id: episodeId, position }) });
    } catch (e) {
      console.warn('[audio] reportProgress failed:', e);
    } finally {
      progressReporting = false;  // 必须清，失败也清
    }
  }
  ```
- 错误做法：
  ```javascript
  // ❌ 无防重叠，弱网下并发请求覆盖进度
  async function reportProgress(episodeId, position) {
    await fetch(`${BASE_URL}/playlogs/progress`, { method: 'POST', body: JSON.stringify({ episode_id: episodeId, position }) });
  }
  ```
- 适用：所有异步上报（进度/埋点/统计）；写操作幂等性要求高的场景
- 不适用：读操作（无副作用可重复）；同步操作

### 规范 80：seek 必须用 pendingSeek 标志位替代 onCanplay 注册

**小程序 seek 操作必须用 `pendingSeek` 模块级标志位记录目标位置，在 onTimeUpdate 中检测并应用，禁止在 onCanplay 回调中 seek 后再 offCanplay（回调累积+时机不可控）。**

- 为什么：onCanplay 触发时机不稳定（首次播放、seek 后、network 切换都可能触发），在 onCanplay 中 seek 后 offCanplay 会导致：
  1. 监听器累积（每次 playEpisode 注册一次，未及时 off）
  2. 时机不可控（onCanplay 可能在 seek 已应用后才触发，造成二次 seek）
  3. 多页面共享 player 时回调串扰
  本次迭代用 `pendingSeek` 标志位后，seek 行为稳定。
- 阈值参数（通过 `project-config.json#miniprogram_playback.seek` 配置）：
  - `use_pending_flag`: true（强制用标志位）
  - `flag_ttl_ms`: 5000（标志位 TTL，超时自动清，防止异常未清）
  - `apply_on_event`: "onTimeUpdate"（在 onTimeUpdate 中应用，时机稳定）
- 判断信号：
  - grep `onCanplay.*=>.*seek\(` 在 playEpisode 函数内
  - grep `audioManager\.offCanplay` 在 onCanplay 回调内（自清理模式）
- 正确做法：
  ```javascript
  let pendingSeek = null;

  function seekTo(position) {
    pendingSeek = position;  // 仅记录，不立即应用
  }

  audioManager.onTimeUpdate(() => {
    if (pendingSeek !== null && Math.abs(audioManager.currentTime - pendingSeek) > 1) {
      const target = pendingSeek;
      pendingSeek = null;  // 先清再 seek，防止 onTimeUpdate 重复触发
      audioManager.seek(target);
    }
  });
  ```
- 错误做法：
  ```javascript
  // ❌ onCanplay 中 seek 后 offCanplay（回调累积+时机不可控）
  function seekTo(position) {
    const onCanplay = () => {
      audioManager.seek(position);
      audioManager.offCanplay?.(onCanplay);
    };
    audioManager.onCanplay(onCanplay);
  }
  ```
- 适用：所有小程序 audioManager.seek；类似需要在就绪后应用的操作
- 不适用：同步可立即应用的操作（如设置音量）

### 规范 81：倍速/音量等 setter 必须用 lastApplied 缓存避免重复写入

**`playbackRate`/`volume` 等高频 setter 必须用模块级 `lastAppliedRate`/`lastAppliedVolume` 缓存上次应用值，新值与缓存相同时跳过写入，避免重复触发底层状态切换。**

- 为什么：每次 `audioManager.playbackRate = 1.0` 都会触发底层重新评估播放管线，即使值未变。在 onTimeUpdate 等高频回调中反复设置同一倍速会引发：
  1. 底层状态机抖动（可能触发不必要的缓冲）
  2. UI 状态切换闪烁
  3. iOS 上偶尔触发未公开的二次缓冲
  本次迭代未缓存时，倍速按钮点击多次后出现卡顿。
- 阈值参数（通过 `project-config.json#miniprogram_playback.cached_setters` 配置）：
  - `cached_fields`: ["playbackRate", "volume"]（需要缓存的字段列表）
  - `equality_epsilon`: 0.001（浮点数相等的容差）
- 判断信号：
  - grep `audioManager\.playbackRate\s*=\s*` 在 onTimeUpdate 或高频回调内
  - 同一函数内多次赋值同一字段
- 正确做法：
  ```javascript
  let lastAppliedRate = 1.0;
  function setPlaybackRate(rate) {
    if (Math.abs(rate - lastAppliedRate) < 0.001) return;  // 值未变跳过
    lastAppliedRate = rate;
    audioManager.playbackRate = rate;
    // ... iOS pause+play+seek 逻辑（规范 77）
  }
  ```
- 错误做法：
  ```javascript
  // ❌ 每次都写入，即使值未变
  function setPlaybackRate(rate) {
    audioManager.playbackRate = rate;
  }
  ```
- 适用：所有高频 setter（playbackRate/volume/playbackQuality）；其他需幂等的操作
- 不适用：值本身就会变的场景（如 currentTime）

### 规范 82：列表页与详情页布局必须分离

**列表页（首页/历史页）与详情页（播放详情页）必须分页面承载，禁止在列表页内嵌完整播放卡片组件。列表项点击必须 `wx.navigateTo` 跳转到详情页。**

- 为什么：列表页内嵌播放卡片导致：
  1. 单频道模式与列表模式两套布局（不一致，需维护两套样式）
  2. 列表项播放时状态管理复杂（需维护"当前播放项"高亮）
  3. 频道切换时内嵌卡片状态残留（如文稿、评论未清）
  4. 详情页与列表页风格不统一（用户感知割裂）
  本次迭代统一为"列表模式 + navigateTo 跳转详情页"后，布局清晰、状态隔离。
- 阈值参数（通过 `project-config.json#miniprogram_layout` 配置）：
  - `forbid_inline_player_card`: true（禁止内嵌播放卡片）
  - `list_item_action`: "navigateTo"（点击行为）
  - `detail_page_route`: "/pages/detail/detail"（详情页路由模板）
- 判断信号：
  - grep `<block wx:else>` 在列表页内（单频道模式分支）
  - grep `playEpisode` 在列表页 `onTapEpisode` 内（直接播放而非跳转）
- 正确做法：
  ```javascript
  // ✅ 列表页：点击跳转到详情页
  onTapEpisode(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/pages/detail/detail?id=' + id });
  }
  ```
- 错误做法：
  ```javascript
  // ❌ 列表页内嵌播放卡片（单频道模式）
  <block wx:if="{{singleChannelMode}}">
    <player-card episode="{{episode}}" />
  </block>
  <block wx:else>
    <view wx:for="{{todayList}}">...</view>
  </block>
  ```
- 适用：所有列表-详情页场景（节目列表、商品列表、文章列表）
- 不适用：单一详情场景（如设置页只有一个表单）

### 规范 83：频道/筛选切换必须清空关联状态

**频道切换、筛选条件变更时，必须清空与原筛选关联的所有状态（episode、script、segments、comments、bgCoverUrl 等），禁止仅清主数据不清关联数据。**

- 为什么：切换频道时若仅清 `todayList` 不清 `script`/`segments`/`comments`，用户看到新频道列表但点击列表项时详情页仍显示旧频道文稿，造成"数据串台"。本次迭代未清关联状态时出现"切换频道后文稿图片不更新"。
- 阈值参数（通过 `project-config.json#miniprogram_state_clear` 配置）：
  - `clear_fields_on_channel_switch`: ["episode", "script", "segments", "comments", "commentsTotal", "bgCoverUrl", "scriptLoaded", "scriptLoading", "showScript"]
  - `clear_before_fetch`: true（fetch 前先清，避免旧数据闪现）
- 判断信号：
  - grep `currentChannelId\s*=` 后无 `setData.*script.*:.*''` 清理
  - 频道切换函数内 `setData` 仅清列表不清详情字段
- 正确做法：
  ```javascript
  async initData(force) {
    if (force) {
      this.setData({
        showScript: false, scriptLoaded: false,
        scriptLoading: false, script: '', segments: [],  // 清文稿
        episode: null, comments: [], commentsTotal: 0,   // 清详情
        bgCoverUrl: '',  // 清背景图
      });
    }
    // 再 fetch 新数据
  }
  ```
- 错误做法：
  ```javascript
  // ❌ 仅清列表不清详情
  async switchChannel(channelId) {
    this.setData({ todayList: [] });  // 不清 script/segments/comments
    const data = await fetchTodayEpisode(channelId);
    this.setData({ todayList: data });
  }
  ```
- 适用：所有筛选/频道切换场景；分页切换；tab 切换
- 不适用：纯列表刷新（不切换上下文）

### 规范 84：跳转播放详情前必须调用 resumePlay 恢复播放

**从浮动按钮、历史列表、继续播放入口等跳转到播放详情页时，必须先调用 `resumePlay()` 恢复播放状态，再 `wx.navigateTo`，禁止仅 navigateTo 不恢复播放（用户感知"点了但没反应"）。**

- 为什么：若 player 处于暂停状态，仅 navigateTo 后详情页按钮显示"暂停"图标（实际是暂停态），用户需点两次才能播放。本次迭代历史页"正在播放"按钮点击后跳转但不播放，用户反复点击。
- 阈值参数（通过 `project-config.json#miniprogram_navigation` 配置）：
  - `require_resume_before_navigate`: true（强制恢复）
  - `resume_only_if_paused`: true（仅在暂停态才恢复，避免打断正在播放）
  - `resume_method`: "resumePlay"（统一的恢复播放函数名）
- 判断信号：
  - grep `wx\.navigateTo.*detail\?id=` 前无 `resumePlay\(\)` 调用
  - grep `wx\.navigateTo.*detail\?id=` 在 onTapContinue/onTapFloatingPlayer 内
- 正确做法：
  ```javascript
  // ✅ 先恢复播放再跳转
  onTap() {
    resumePlay();  // 恢复播放（仅暂停态才生效）
    wx.navigateTo({ url: '/pages/detail/detail?id=' + ep.id });
  }
  ```
- 错误做法：
  ```javascript
  // ❌ 仅跳转不恢复
  onTap() {
    wx.navigateTo({ url: '/pages/detail/detail?id=' + ep.id });
  }
  ```
- 适用：所有跳转到播放详情页的入口（浮动按钮、历史列表、继续播放）
- 不适用：首次播放（player 尚未初始化）；用户明确选择"仅查看不播放"

### 规范 85：数据结构变更时 cache_key 必须加版本后缀

**当缓存的数据结构发生变更（新增/删除/重命名字段、嵌套结构调整）时，cache_key 必须追加版本后缀（如 `:v2`、`:_v3`），禁止沿用旧 key（旧缓存会被反序列化为新结构导致字段缺失或类型错误）。**

- 为什么：cache-aside 模式下，旧 key 的缓存 TTL 未过期时仍会被命中，但反序列化后字段缺失（如新增 `cover_url` 字段时旧缓存无此字段，前端显示空图）。本次迭代 `segments` 注入 `cover_url` 后未加版本后缀，旧缓存命中导致图片不显示，调试 30 分钟才定位。
- 阈值参数（通过 `project-config.json#cache_versioning` 配置）：
  - `require_version_suffix_on_schema_change`: true（强制）
  - `version_suffix_format`: ":v{n}"（后缀格式，n 从 2 开始）
  - `bump_on_fields`: ["add", "remove", "rename"]（哪些变更触发 bump）
- 判断信号：
  - grep `cache_key\s*=\s*f["'].*:\{` 使用变量插值但无版本字段
  - 数据结构新增字段后 cache_key 未变更
- 正确做法：
  ```python
  # ✅ 数据结构变更时 bump 版本
  # v1: segments = [{"seq": 1, "title": "..."}]
  # v2: segments = [{"seq": 1, "title": "...", "cover_url": "..."}]  → 加 v2
  cache_key = f"script:detail:v2:{episode_id}"  # v2 失效旧缓存
  ```
- 错误做法：
  ```python
  # ❌ 沿用旧 key，旧缓存命中导致 cover_url 缺失
  cache_key = f"script:detail:{episode_id}"  # 旧缓存无 cover_url 字段
  ```
- 适用：所有结构化缓存（dict/list 对象）；前后端字段变更场景
- 不适用：纯标量缓存（如 `count:5`）；TTL 短（< 60s）的临时缓存

## 规范 86-90：2026-07-21 跨项目模块迁移与测试执行复盘新增规范

> 以下规范来源于参考 D:\code\otherProjects\17_xianyu 项目实现"关于"和"帮助文档"模块的完整复盘，覆盖跨项目迁移、嵌套目录路径、图标跨库迁移、缓存测试隔离、多版本 Python 测试执行等高频问题场景。所有阈值通过 `project-config.json#cross_project_migration`、`project-config.json#frontend_nested_paths`、`project-config.json#icon_migration`、`project-config.json#cache_test_isolation`、`project-config.json#python_env_test` 配置管理。

### 规范 86：跨项目模块迁移 7 步法

**参考式跨项目模块迁移必须完整执行 7 个步骤：需求确认 → 架构对齐 → 后端开发 → 前端开发 → 测试编写 → 测试执行 → 构建验证，禁止跳过任一步骤。**

- 为什么：跨项目迁移时，参考项目的架构、技术栈、约定可能与目标项目不一致。直接复制代码会导致路径错误、图标不存在、构建失败等问题。本次迭代从 17_xianyu 迁移"关于/帮助"模块时，因跳过架构对齐导致 SCSS 路径错误、JS import 路径错误、Rocket 图标不存在 3 个问题，全部在 vite build 阶段才暴露。
- 阈值参数（通过 `project-config.json#cross_project_migration` 配置）：
  - `required_steps`: ["requirement_confirm", "architecture_align", "backend_dev", "frontend_dev", "test_write", "test_execute", "build_verify"]
  - `architecture_align_checklist`: ["目录结构对齐", "技术栈对齐", "依赖库对齐", "命名约定对齐", "路径风格对齐"]
  - `build_verify_required`: true（构建验证必须通过才算完成）
  - `test_execute_required`: true（测试执行必须通过才算完成）
- 判断信号：
  - 跨项目迁移任务跳过架构对齐步骤
  - 迁移后未执行 vite build / py_compile 验证
  - 迁移后未执行测试用例验证
- 7 步流程：
  1. **需求确认**：明确迁移目标、范围、验收标准
  2. **架构对齐**：对比参考项目与目标项目的目录结构、技术栈、依赖库、命名约定、路径风格
  3. **后端开发**：按目标项目分层架构（routers → services → models → core）实现
  4. **前端开发**：按目标项目目录结构（views/<module>/<Page>.vue）实现，校验相对路径
  5. **测试编写**：编写单元测试（后端）+ 测试用例（前端）
  6. **测试执行**：运行 pytest + vite build，确保测试通过且构建成功
  7. **构建验证**：实际启动服务/打开页面验证功能可用
- 适用：所有参考式跨项目模块迁移
- 不适用：从零开发（无参考项目）、纯配置迁移（无代码）

### 规范 87：前端嵌套目录相对路径校验

**Vue 项目采用 `views/<module>/<Page>.vue` 嵌套目录结构时，SCSS `@use` 和 JS `import` 的相对路径必须按嵌套层级计算（`../../` 而非 `../`），禁止照搬扁平目录的路径风格。**

- 为什么：17_xianyu 项目采用扁平目录（views/About.vue），SCSS 用 `@use '../styles/variables.scss'`。20_News 项目采用嵌套目录（views/about/About.vue），照搬 17_xianyu 的 `../styles/` 路径会指向 `views/styles/`（不存在），实际应为 `../../styles/`。vite build 阶段才暴露此错误，开发阶段无任何提示。
- 阈值参数（通过 `project-config.json#frontend_nested_paths` 配置）：
  - `nested_dir_pattern`: "views/<module>/<Page>.vue"（嵌套目录结构模式）
  - `parent_level_required`: 2（嵌套层级，扁平为 1，单层嵌套为 2，双层嵌套为 3）
  - `path_types_to_check`: ["scss_use", "js_import", "ts_import", "vue_import"]
  - `build_verify_required`: true（vite build 必须通过）
- 判断信号：
  - grep `@use '\.\./styles/'` 在 `views/<module>/*.vue` 文件中（应为 `../../styles/`）
  - grep `from '\.\./utils/'` 在 `views/<module>/*.vue` 文件中（应为 `../../utils/`）
  - grep `from '\.\./api/'` 在 `views/<module>/*.vue` 文件中（应为 `../../api/`）
- 正确做法：
  ```vue
  <!-- ✅ 正确：嵌套目录 views/about/About.vue 的相对路径 -->
  <style lang="scss">
  @use '../../styles/variables.scss' as *;  // 两级 ../
  </style>
  <script setup>
  import { someUtil } from '../../utils/someUtil'  // 两级 ../
  import { someApi } from '../../api/someApi'      // 两级 ../
  </script>

  <!-- ❌ 错误：照搬扁平目录路径风格 -->
  <style lang="scss">
  @use '../styles/variables.scss' as *;  // 一级 ../，指向 views/styles/（不存在）
  </style>
  <script setup>
  import { someUtil } from '../utils/someUtil'  // 一级 ../，指向 views/utils/（不存在）
  </script>
  ```
- 适用：所有 `views/<module>/<Page>.vue` 嵌套目录结构
- 不适用：扁平目录结构（views/Page.vue）、绝对路径（@/）

### 规范 88：UI 图标跨库迁移存在性验证

**从参考项目迁移 UI 图标到目标项目时，必须验证图标在目标 UI 库中存在，禁止直接照搬参考项目的图标名。**

- 为什么：17_xianyu 项目使用 React 图标库（如 lucide-react），其中含 `Rocket` 图标。20_News 项目使用 @element-plus/icons-vue，该库不含 `Rocket`。照搬 `Rocket` 图标名后 vite build 报错 "Rocket is not exported by @element-plus/icons-vue"。React 图标库与 Vue 图标库的图标命名、覆盖范围差异较大，必须逐个验证。
- 阈值参数（通过 `project-config.json#icon_migration` 配置）：
  - `target_icon_library`: "@element-plus/icons-vue"（目标图标库）
  - `verify_command`: "node -e \"const icons = require('@element-plus/icons-vue'); console.log(Object.keys(icons))\""（验证命令）
  - `fallback_icon`: "MagicStick"（图标不存在时的兜底替换）
  - `verify_before_build`: true（构建前必须验证图标存在性）
- 判断信号：
  - grep `from '@element-plus/icons-vue'` 后跟参考项目特有图标名（如 Rocket, Heart, Star 等）
  - 迁移任务未执行图标存在性验证
- 正确做法：
  ```javascript
  // ✅ 正确：迁移前验证图标存在性
  // 1. 列出目标库所有图标
  // node -e "const icons = require('@element-plus/icons-vue'); console.log(Object.keys(icons))"
  // 2. 对照参考项目使用的图标，替换不存在的
  import { MagicStick } from '@element-plus/icons-vue'  // Rocket 不存在，替换为 MagicStick

  // ❌ 错误：照搬参考项目图标名
  import { Rocket } from '@element-plus/icons-vue'  // vite build 报错
  ```
- 适用：所有跨 UI 库图标迁移（React → Vue、Ant Design → Element Plus 等）
- 不适用：同 UI 库内的图标调整、自定义 SVG 图标

### 规范 89：模块级单例缓存的测试隔离

**进程内模块级单例缓存（TTLCache / dict / lru_cache）的单元测试，必须在测试用例间通过 `_reset_cache_for_test()` 等显式清理函数重置缓存，禁止依赖测试执行顺序或 GC 自动清理。**

- 为什么：模块级单例（如 `settings = get_settings()`、`_cache = TTLCache(...)`）在进程生命周期内只初始化一次。pytest 多个测试用例共享同一进程，前一个用例修改的缓存状态会影响后一个用例。本次迭代测试 settings 单例时，未重置缓存导致后续用例读取到前一个用例修改的值，测试结果与执行顺序相关，违反测试隔离原则。
- 阈值参数（通过 `project-config.json#cache_test_isolation` 配置）：
  - `require_reset_function`: true（必须有显式重置函数）
  - `reset_function_naming`: "_reset_cache_for_test"（重置函数命名约定）
  - `reset_in_fixture`: true（推荐在 pytest fixture 中调用重置）
  - `cache_types_to_reset`: ["TTLCache", "dict_module_level", "lru_cache", "functools.cache"]
- 判断信号：
  - 测试用例依赖执行顺序（颠倒顺序后失败）
  - 测试模块级单例的代码无 `_reset_cache_for_test()` 调用
  - 使用 `pytest-randomly` 随机顺序执行时出现间歇性失败
- 正确做法：
  ```python
  # app/core/cache.py
  from cachetools import TTLCache
  _cache: TTLCache = TTLCache(maxsize=100, ttl=300)

  def _reset_cache_for_test() -> None:
      """测试专用：重置模块级缓存，确保用例间隔离。"""
      _cache.clear()

  # tests/test_cache.py
  import pytest
  from app.core.cache import _cache, _reset_cache_for_test

  @pytest.fixture(autouse=True)
  def reset_cache():
      """每个测试用例前自动重置缓存。"""
      _reset_cache_for_test()
      yield

  def test_cache_set():
      _cache["key1"] = "value1"
      assert _cache["key1"] == "value1"

  def test_cache_empty():  # 不受 test_cache_set 影响
      assert "key1" not in _cache  # 通过，因为 fixture 已重置
  ```
- 错误做法：
  ```python
  # ❌ 无重置函数，依赖 GC 或测试顺序
  def test_cache_set():
      _cache["key1"] = "value1"
      assert _cache["key1"] == "value1"

  def test_cache_empty():  # 如果在 test_cache_set 后执行，会失败
      assert "key1" not in _cache  # 失败，_cache["key1"] 仍存在
  ```
- 适用：所有进程内缓存模块（TTLCache / dict 模块级单例 / lru_cache / functools.cache / 单例模式的类属性）
- 不适用：函数局部变量（每次调用自然隔离）、数据库状态（用事务回滚隔离）

### 规范 90：多版本 Python 环境下的测试执行

**Windows 环境下 Trae 内置 Python 与系统 Python 多版本共存时，执行 pytest 必须显式指定 Python 解释器完整路径，禁止依赖 PATH 解析（PATH 中 Trae 内置 Python 可能优先，但其不含 pytest 等开发依赖）。**

- 为什么：Windows 安装 Trae 后，PATH 中 Trae 内置 Python 可能优先于系统 Python。Trae 内置 Python 是精简版，不含 pytest / pytest-asyncio 等开发依赖。直接 `python -m pytest` 会报 `No module named pytest`，但 `python --version` 显示正常版本号，误导开发者以为是其他问题。
- 阈值参数（通过 `project-config.json#python_env_test` 配置）：
  - `require_explicit_python_path`: true（强制显式指定 Python 路径）
  - `system_python_path`: "F:\\Program Files\\Python3.14\\python.exe"（系统 Python 完整路径，从配置读取）
  - `required_test_deps`: ["pytest", "pytest-asyncio", "aiosqlite"]（必需测试依赖列表）
  - `verify_command`: "python -c \"import pytest; print(pytest.__version__)\""（验证命令）
- 判断信号：
  - `python -m pytest` 报 `No module named pytest` 但 `python --version` 正常
  - PATH 中 Trae 内置 Python 优先于系统 Python
  - 多个 Python 版本共存（如 Python 3.12 / 3.14 / Trae 内置）
- 正确做法：
  ```powershell
  # ✅ 正确：显式指定系统 Python 完整路径
  & "F:\Program Files\Python3.14\python.exe" -m pytest tests/ -v
  & "F:\Program Files\Python3.14\python.exe" -m pytest --asyncio-mode=auto

  # ✅ 正确：先验证 pytest 已安装
  & "F:\Program Files\Python3.14\python.exe" -c "import pytest; print(pytest.__version__)"

  # ❌ 错误：依赖 PATH 解析
  python -m pytest tests/ -v  # 可能使用 Trae 内置 Python，无 pytest
  ```
- 适用：Windows + 多 Python 版本共存环境（Trae 内置 Python + 系统 Python）
- 不适用：Linux/Mac 单版本 Python 环境、虚拟环境（venv 已激活）

## 规范 91-100：2026-07-21 综合复盘新增规范

> 以下规范来源于 2026-07-21 图片爬虫功能开发、工作流多步骤失败修复、P0/P1 改进实施、菜单分组功能开发、图标设计任务等综合复盘，覆盖封面图提取、装饰图过滤、动态回溯天数、LLM 语义降级、LLM 字数约束、BGM 兜底、菜单分组、PWA 图标、监控告警、批量回填脚本等高频场景。所有阈值通过 `project-config.json#image_crawl`、`project-config.json#workflow_orchestration`、`project-config.json#frontend_menu_grouping`、`project-config.json#pwa_icon_generation`、`project-config.json#monitoring_thresholds`、`project-config.json#backfill_script` 配置管理。

### 规范 91：图片封面三级 fallback 提取

**文章封面图提取必须实现 og:image → article <img> → 页面首个非装饰 <img> 三级 fallback，禁止仅依赖单一来源。**

- **为什么**：文章封面图来源多样且不稳定。og:image 缺失（部分站点不设置 meta 标签）、article <img> 为空（部分文章纯图文混排无主图）、页面 <img> 含装饰图（logo/icon 等）。仅依赖单一来源会导致 30%+ 文章无封面，影响小程序展示效果。
- **阈值参数**（通过 `project-config.json#image_crawl` 配置）：
  - `fallback_chain`: ["og_image", "article_img", "page_first_img"]（fallback 顺序）
  - `timeout_per_source_sec`: 5（单源超时）
  - `min_image_size_bytes`: 1024（小于此大小的图视为无效）
- **判断信号**：grep `og:image` 后无 `elif`/`try/except` fallback 逻辑
- **正确做法**：
  ```python
  async def extract_cover_image(html: str, url: str) -> str | None:
      sources = settings.image_crawl.fallback_chain  # 从配置读取
      for source in sources:
          try:
              img_url = await _extract_from_source(source, html, url)
              if img_url and await _validate_image_size(img_url):
                  return img_url
          except Exception as e:
              logger.warning(f"Cover extraction via {source} failed: {e}")
              continue
      return None  # 全部失败返回 None，由上层降级处理
  ```
- **错误做法**：
  ```python
  # ❌ 仅依赖 og:image，无 fallback
  def extract_cover_image(html: str) -> str | None:
      match = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
      return match.group(1) if match else None
  ```
- **适用场景**：所有需要封面图的文章/新闻类业务
- **不适用场景**：无图片需求的纯文本内容；用户主动上传封面的场景

### 规范 92：装饰图过滤规则

**封面图提取必须过滤装饰图（logo/icon/arrow 等 URL 关键词、特定站点模板路径、GIF 扩展名），禁止将装饰图作为封面。**

- **为什么**：页面首个 <img> 常常是站点 logo、导航 icon、箭头装饰等，这些图作为封面会严重影响阅读体验。GIF 动图作为封面在 iOS 上不显示动效且体积过大。本次迭代未过滤时，小程序封面图 40% 是站点 logo。
- **阈值参数**（通过 `project-config.json#image_crawl.decorative_filter` 配置）：
  - `url_keyword_blacklist`: ["logo", "icon", "arrow", "btn", "button", "sprite", "placeholder"]
  - `template_path_blacklist`: ["/static/", "/assets/img/", "/images/common/"]
  - `extension_blacklist`: [".gif", ".svg"]
  - `min_aspect_ratio`: 0.3（宽高比下限，过滤细长装饰条）
- **判断信号**：grep `cover_url` 提取逻辑无装饰图过滤（无 keyword_blacklist 检查）
- **正确做法**：
  ```python
  def is_decorative_image(img_url: str) -> bool:
      cfg = settings.image_crawl.decorative_filter
      url_lower = img_url.lower()
      # URL 关键词过滤
      if any(kw in url_lower for kw in cfg.url_keyword_blacklist):
          return True
      # 模板路径过滤
      if any(path in url_lower for path in cfg.template_path_blacklist):
          return True
      # 扩展名过滤
      if any(url_lower.endswith(ext) for ext in cfg.extension_blacklist):
          return True
      return False
  ```
- **错误做法**：
  ```python
  # ❌ 直接取首个 <img> 不做过滤
  def extract_first_img(html: str) -> str | None:
      match = re.search(r'<img[^>]+src="([^"]+)"', html)
      return match.group(1) if match else None  # 可能是 logo/icon
  ```
- **适用场景**：所有图片提取场景（封面图、列表缩略图、OG 图）
- **不适用场景**：用户主动上传的图片（无需过滤）；图标库素材站（图标本就是有效内容）

### 规范 93：FALLBACK_DAYS 动态计算

**素材回溯天数应根据频道入库天数动态计算（3/7/14 天三档），而非固定值。**

- **为什么**：新频道入库天数 <3 天时，固定 7 天回溯会查到 0 条素材导致工作流失败；老频道入库天数 >30 天时，3 天回溯过短，无法覆盖节假日内容空窗。本次迭代固定 FALLBACK_DAYS=3 导致新频道首日 0 素材失败。
- **阈值参数**（通过 `project-config.json#workflow_orchestration.fallback_days_tiers` 配置）：
  - `tiers`: [{"max_channel_age_days": 3, "fallback_days": 1}, {"max_channel_age_days": 14, "fallback_days": 3}, {"max_channel_age_days": 9999, "fallback_days": 7}]
  - `default_tier_index`: 1（默认档位）
- **判断信号**：grep `FALLBACK_DAYS` 为硬编码数字（如 `FALLBACK_DAYS = 3`）
- **正确做法**：
  ```python
  def calculate_fallback_days(channel_created_at: datetime) -> int:
      channel_age_days = (datetime.now() - channel_created_at).days
      tiers = settings.workflow_orchestration.fallback_days_tiers.tiers
      for tier in tiers:
          if channel_age_days <= tier["max_channel_age_days"]:
              return tier["fallback_days"]
      return tiers[settings.workflow_orchestration.fallback_days_tiers.default_tier_index]["fallback_days"]
  ```
- **错误做法**：
  ```python
  # ❌ 硬编码固定值
  FALLBACK_DAYS = 3  # 新频道首日不够 3 天，查不到素材

  async def get_recent_materials(channel_id: int):
      since = datetime.now() - timedelta(days=FALLBACK_DAYS)
      return await db.execute(select(Material).where(Material.created_at >= since))
  ```
- **适用场景**：多频道/多租户的素材回溯场景；新频道冷启动场景
- **不适用场景**：单频道项目（无频道差异化需求）；无历史数据的全新项目（首次入库无回溯必要）

### 规范 94：LLM 语义过滤 fallback

**关键词过滤结果为 0 时必须降级到 LLM 语义过滤，LLM 失败时保留全部条目供 rewriter 二次筛选。**

- **为什么**：关键词过滤依赖词表覆盖度，新话题/同义词/隐喻表达会全部漏掉。若过滤后 0 条直接报错，工作流中断。LLM 语义过滤能理解语义相似性，但仍可能失败（API 超时/限流）。最坏情况下保留全部条目让 rewriter 自行筛选，保证工作流不中断。本次迭代关键词过滤 0 条导致工作流失败 30 分钟。
- **阈值参数**（通过 `project-config.json#workflow_orchestration.llm_semantic_fallback` 配置）：
  - `trigger_when_keyword_result_zero`: true（关键词过滤 0 条时触发）
  - `llm_filter_batch_size`: 10（LLM 批量过滤批次大小）
  - `fallback_strategy_on_llm_failure`: "keep_all"（LLM 失败时保留全部）
  - `llm_filter_timeout_sec`: 30（LLM 过滤超时）
- **判断信号**：grep 关键词过滤后无 LLM fallback 分支（`if not filtered: raise` 无降级）
- **正确做法**：
  ```python
  async def filter_materials(materials: list, keywords: list[str]) -> list:
      # 第一级：关键词过滤
      filtered = [m for m in materials if any(kw in m.title for kw in keywords)]
      if filtered:
          return filtered
      # 第二级：LLM 语义过滤
      cfg = settings.workflow_orchestration.llm_semantic_fallback
      try:
          return await asyncio.wait_for(
              _llm_semantic_filter(materials, keywords),
              timeout=cfg.llm_filter_timeout_sec,
          )
      except Exception as e:
          logger.warning(f"LLM semantic filter failed, keep all materials: {e}")
          # 第三级：保留全部条目
          return materials
  ```
- **错误做法**：
  ```python
  # ❌ 关键词过滤 0 条直接报错
  async def filter_materials(materials: list, keywords: list[str]) -> list:
      filtered = [m for m in materials if any(kw in m.title for kw in keywords)]
      if not filtered:
          raise BusinessError("无匹配素材")  # 工作流中断
      return filtered
  ```
- **适用场景**：所有基于关键词的内容过滤场景（素材筛选/文章分类/评论审核）
- **不适用场景**：纯精确匹配场景（如 ID 过滤、SKU 过滤）；安全敏感场景（不能保留全部，必须严格过滤）

### 规范 95：LLM 字数达标约束

**LLM 生成内容必须达到目标字数的 70%，低于阈值触发硬约束重试；超过目标×1.20 时丢弃多余段（保留至少 3 主段+intro+outro）；低于目标×0.80 时追加最多 2 段。**

- **为什么**：LLM 生成稿件字数偏差过大会导致音频时长异常（TTS 时长与字数正相关）。字数不足音频过短（小程序显示节目时长 <5 分钟用户体验差），字数超长音频过长（超出 10:30 上限触发切除丢内容）。本次迭代未约束时稿件字数从 800-3500 字波动，音频时长 4-15 分钟。
- **阈值参数**（通过 `project-config.json#workflow_orchestration.llm_word_count` 配置）：
  - `target_word_count`: 1500（目标字数）
  - `min_achievement_ratio`: 0.70（硬约束下限，低于触发重试）
  - `trim_threshold_ratio`: 1.20（超此比例丢弃多余段）
  - `append_threshold_ratio`: 0.80（低于此比例追加段）
  - `max_append_segments`: 2（最多追加段数）
  - `min_main_segments`: 3（修剪后最少保留主段数）
- **判断信号**：grep LLM 调用后无字数验证逻辑（无 `len(content)` / `word_count` 检查）
- **正确做法**：
  ```python
  async def generate_script_with_constraint(topic: str) -> str:
      cfg = settings.workflow_orchestration.llm_word_count
      target = cfg.target_word_count
      for attempt in range(3):  # 硬约束重试
          content = await llm.generate(topic, target_words=target)
          actual = len(content)
          if actual >= target * cfg.min_achievement_ratio:
              break
          logger.warning(f"Word count {actual} < {target * cfg.min_achievement_ratio}, retry {attempt+1}")
      # 超长修剪
      if actual > target * cfg.trim_threshold_ratio:
          content = _trim_to_target(content, target, cfg.min_main_segments)
      # 过短追加
      elif actual < target * cfg.append_threshold_ratio:
          content = await _append_segments(content, topic, cfg.max_append_segments)
      return content
  ```
- **错误做法**：
  ```python
  # ❌ 无字数约束，LLM 生成什么用什么
  async def generate_script(topic: str) -> str:
      return await llm.generate(topic)  # 字数可能 200 也可能 5000
  ```
- **适用场景**：所有 LLM 生成内容场景（稿件/标题/摘要/口播文案）
- **不适用场景**：自由创作场景（无字数要求）；结构化输出（如 JSON 数据）

### 规范 96：BGM 时长不足兜底

**视频拼接时 BGM 时长不足必须用 BGM 尾段扩展或静音降级，禁止直接报错。**

- **为什么**：BGM 库素材时长固定（通常 3-5 分钟），但视频时长可能 6-10 分钟。BGM 短于视频时直接报错会导致整个工作流失败，用户体验断裂。本次迭代 BGM 4:30 视频 6:00 时报错失败。
- **阈值参数**（通过 `project-config.json#workflow_orchestration.bgm_fallback` 配置）：
  - `extension_strategy`: "tail_loop"（尾段扩展策略，可选 "tail_loop"/"silence"/"crossfade"）
  - `tail_loop_max_count`: 2（尾段扩展最大次数，超过则降级静音）
  - `silence_fadeout_sec`: 2（静音降级时的淡出秒数）
- **判断信号**：grep BGM 拼接逻辑无时长不足处理（`if bgm_duration < video_duration: raise`）
- **正确做法**：
  ```python
  async def merge_bgm_with_video(bgm_path: str, video_path: str) -> str:
      bgm_duration = await get_audio_duration(bgm_path)
      video_duration = await get_video_duration(video_path)
      cfg = settings.workflow_orchestration.bgm_fallback

      if bgm_duration >= video_duration:
          # 正常裁剪
          return await _trim_bgm(bgm_path, video_duration)
      # 时长不足：尾段扩展
      extended_bgm = await _extend_bgm_tail_loop(bgm_path, video_duration, cfg.tail_loop_max_count)
      if extended_bgm:
          return extended_bgm
      # 兜底：静音降级
      logger.warning(f"BGM extend failed, fallback to silence for {video_duration - bgm_duration}s")
      return await _pad_with_silence(bgm_path, video_duration, cfg.silence_fadeout_sec)
  ```
- **错误做法**：
  ```python
  # ❌ BGM 时长不足直接报错
  async def merge_bgm(bgm_path: str, video_path: str) -> str:
      bgm_duration = await get_audio_duration(bgm_path)
      video_duration = await get_video_duration(video_path)
      if bgm_duration < video_duration:
          raise WorkflowError(f"BGM {bgm_duration}s < video {video_duration}s")  # 工作流中断
      return await _merge(bgm_path, video_path)
  ```
- **适用场景**：所有音频/视频拼接场景（BGM 配音/背景音乐/片头片尾）
- **不适用场景**：无 BGM 的纯人声拼接；BGM 必须完整播放的场景（如音乐 MV）

### 规范 97：菜单分组与角色可见性

**管理后台菜单数量 ≥10 时必须按功能分组（el-sub-menu），通过 meta.group 字段配置分组，groupConfig 数组定义分组渲染，支持角色可见性控制（RBAC），启用 unique-opened 手风琴效果，路由变化时自动展开当前分组。**

- **为什么**：菜单 ≥10 项时扁平列表视觉拥挤，用户查找困难。功能分组让相关菜单聚合（如"内容管理"含文章/评论/标签）。RBAC 让 operator 看不到"系统设置"等敏感菜单。unique-opened 避免多个分组同时展开挤占屏幕。本次迭代菜单从 8 项增加到 14 项后，扁平列表查找成本激增。
- **阈值参数**（通过 `project-config.json#frontend_menu_grouping` 配置）：
  - `group_threshold`: 10（触发分组的最小菜单数）
  - `unique_opened`: true（手风琴效果）
  - `auto_expand_on_route_change`: true（路由变化自动展开）
  - `group_field`: "meta.group"（路由 meta 中的分组字段名）
  - `default_visible_roles`: ["admin"]（默认仅 admin 可见敏感分组）
- **判断信号**：grep 菜单数量 ≥10 但无 `meta.group` 字段；grep `<el-sub-menu` 无 `unique-opened` 属性
- **正确做法**：
  ```javascript
  // router/routes.js
  const routes = [
    {
      path: '/content',
      meta: { group: 'content', roles: ['admin', 'operator'] },
      component: ArticleList,
    },
    {
      path: '/system',
      meta: { group: 'system', roles: ['admin'] },  // 仅 admin 可见
      component: SystemConfig,
    },
  ]

  // Layout.vue
  <el-menu :unique-opened="groupConfig.unique_opened" @select="handleSelect">
    <el-sub-menu v-for="group in visibleGroups" :key="group.id" :index="group.id">
      <template #title>{{ group.title }}</template>
      <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
        {{ item.title }}
      </el-menu-item>
    </el-sub-menu>
  </el-menu>

  // 路由变化时自动展开当前分组
  watch(() => route.path, (newPath) => {
    const group = findGroupByPath(newPath)
    if (group) activeGroup.value = group.id
  })
  ```
- **错误做法**：
  ```javascript
  // ❌ 14 项菜单扁平渲染，无分组
  <el-menu>
    <el-menu-item v-for="item in allMenus" :key="item.path" :index="item.path">
      {{ item.title }}
    </el-menu-item>
  </el-menu>
  ```
- **适用场景**：所有管理后台菜单（≥10 项）；多角色权限系统
- **不适用场景**：菜单数量 <10 的简单后台；无角色区分的内部工具

### 规范 98：PWA 图标生成与 MIME 注册

**PWA 应用图标必须同时生成 PNG（192/512）和 ICO（多尺寸 16/32/48），main.py 必须注册 `.ico` 的 MIME 类型（image/x-icon），manifest.json 必须声明 icons 数组含 maskable purpose。**

- **为什么**：不同平台对图标格式要求不同——iOS Safari 仅识别 PNG 且需 apple-touch-icon；Windows 桌面 PWA 仅识别 ICO；Android Chrome 要求 maskable purpose 图标（自适应裁剪）。若 main.py 未注册 .ico MIME 类型，浏览器默认按 text/plain 解析导致图标 404/损坏。本次迭代 PWA 安装到 Windows 桌面后图标显示为白板。
- **阈值参数**（通过 `project-config.json#pwa_icon_generation` 配置）：
  - `png_sizes`: [192, 512]（PNG 尺寸列表）
  - `ico_sizes`: [16, 32, 48]（ICO 多尺寸）
  - `ico_mime_type`: "image/x-icon"（.ico MIME 类型）
  - `manifest_purposes`: ["any", "maskable"]（manifest purpose 列表）
  - `source_icon_path`: "assets/source-icon.png"（源图标路径）
- **判断信号**：grep `manifest.json` 无 `maskable` purpose；grep `main.py` 无 `mimetypes.add_type` for `.ico`
- **正确做法**：
  ```python
  # main.py - 注册 .ico MIME 类型
  import mimetypes
  mimetypes.add_type(settings.pwa_icon_generation.ico_mime_type, ".ico")

  app.mount("/icons", StaticFiles(directory="admin-web/dist/icons"), name="icons")
  ```

  ```json
  // manifest.json - 声明含 maskable purpose 的 icons 数组
  {
    "icons": [
      {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
      {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
      {"src": "/icons/icon-192-maskable.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
      {"src": "/icons/icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
      {"src": "/favicon.ico", "sizes": "16x16 32x32 48x48", "type": "image/x-icon"}
    ]
  }
  ```
- **错误做法**：
  ```python
  # ❌ 未注册 .ico MIME 类型
  # main.py
  app.mount("/icons", StaticFiles(directory="dist/icons"))  # .ico 按 text/plain 返回

  # ❌ manifest.json 无 maskable purpose
  {
    "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"}]
  }
  ```
- **适用场景**：所有 PWA 应用（含 manifest.json 的 Web 应用）
- **不适用场景**：非 PWA 的纯 SPA 应用（无离线能力要求）；原生应用（使用原生图标资源）

### 规范 99：关键指标监控告警

**关键业务指标（关键词命中率、LLM 字数达成率、TTS 成功率、工作流成功率）低于阈值时必须记录 WARNING 级别日志，阈值通过配置管理。**

- **为什么**：关键指标下滑是系统健康度的领先指标。关键词命中率从 80% 降到 30% 意味着关键词表过期或 RSS 源失效；LLM 字数达成率低意味着 LLM 服务降级；TTS 成功率低意味着 TTS 服务故障或配额耗尽。仅记录 INFO 级别日志会被埋没，必须 WARNING 级别触发运维关注。本次迭代 TTS 成功率 50% 持续 2 小时未被发现。
- **阈值参数**（通过 `project-config.json#monitoring_thresholds` 配置）：
  - `keyword_hit_rate_min`: 0.30（关键词命中率下限）
  - `llm_word_count_achievement_min`: 0.70（LLM 字数达成率下限）
  - `tts_success_rate_min`: 0.80（TTS 成功率下限）
  - `workflow_success_rate_min`: 0.90（工作流成功率下限）
  - `alert_log_level`: "WARNING"（告警日志级别）
- **判断信号**：grep 关键业务流程无 WARNING 阈值判断（无 `if rate < threshold: logger.warning`）
- **正确做法**：
  ```python
  async def report_workflow_metrics(metrics: dict) -> None:
      cfg = settings.monitoring_thresholds
      if metrics["keyword_hit_rate"] < cfg.keyword_hit_rate_min:
          logger.warning(
              f"Keyword hit rate {metrics['keyword_hit_rate']:.2%} below threshold {cfg.keyword_hit_rate_min:.2%}"
          )
      if metrics["llm_word_count_achievement"] < cfg.llm_word_count_achievement_min:
          logger.warning(
              f"LLM word count achievement {metrics['llm_word_count_achievement']:.2%} below threshold"
          )
      if metrics["tts_success_rate"] < cfg.tts_success_rate_min:
          logger.warning(
              f"TTS success rate {metrics['tts_success_rate']:.2%} below threshold"
          )
      if metrics["workflow_success_rate"] < cfg.workflow_success_rate_min:
          logger.warning(
              f"Workflow success rate {metrics['workflow_success_rate']:.2%} below threshold"
          )
  ```
- **错误做法**：
  ```python
  # ❌ 关键指标仅记录 INFO，无 WARNING 阈值
  async def report_metrics(metrics: dict):
      logger.info(f"keyword_hit_rate={metrics['keyword_hit_rate']}")  # 阈值下滑被埋没
  ```
- **适用场景**：所有关键业务流程（工作流/LLM/TTS/爬虫/审核）
- **不适用场景**：调试日志（DEBUG 级别）；非关键路径（如 UI 点击统计）；已对接 APM 系统（由 APM 告警）

### 规范 100：批量数据回填脚本规范

**新增 ORM 字段后必须编写批量回填脚本（backfill_*.py），脚本必须支持 dry_run 预览模式、分批处理（默认 100 条/批）、幂等执行（重复运行不报错）、进度输出。**

- **为什么**：ORM 新增字段后，存量数据该字段为 NULL，业务代码读取 NULL 会报错或降级。回填脚本必须 dry_run 让运维预览影响范围；分批处理避免单次事务过大锁表；幂等执行保证重试安全（部分失败后重跑不报错）；进度输出便于长时间任务监控。本次迭代新增 `cover_url` 字段后无回填脚本，导致小程序 80% 文章无封面。
- **阈值参数**（通过 `project-config.json#backfill_script` 配置）：
  - `batch_size`: 100（每批处理条数）
  - `dry_run_default`: true（默认 dry_run 模式，需显式 --execute 才真实执行）
  - `progress_log_interval`: 10（每 N 批输出一次进度）
  - `idempotent_check_field`: "updated_at"（幂等检查字段，已回填的跳过）
  - `script_naming_pattern`: "backfill_{model}_{field}.py"（脚本命名约定）
- **判断信号**：grep ORM 模型新增字段但无对应 `backfill_*.py` 脚本
- **正确做法**：
  ```python
  # backfill_material_cover_url.py
  import argparse
  from app.core.config import settings
  from app.models.material import Material

  async def backfill(dry_run: bool = None, batch_size: int = None):
      cfg = settings.backfill_script
      dry_run = cfg.dry_run_default if dry_run is None else dry_run
      batch_size = batch_size or cfg.batch_size

      total = await db.scalar(select(func.count(Material.id)).where(Material.cover_url.is_(None)))
      logger.info(f"Backfill {total} materials, dry_run={dry_run}, batch_size={batch_size}")

      offset = 0
      processed = 0
      while offset < total:
          batch = await db.execute(
              select(Material).where(Material.cover_url.is_(None))
              .limit(batch_size).offset(offset)
          )
          materials = batch.scalars().all()
          if dry_run:
              logger.info(f"[DRY-RUN] Would update {len(materials)} materials (offset={offset})")
          else:
              for m in materials:
                  m.cover_url = await extract_cover_image(m.content, m.source_url)
              await db.commit()
          processed += len(materials)
          offset += batch_size
          if offset % (batch_size * cfg.progress_log_interval) == 0:
              logger.info(f"Progress: {processed}/{total} ({processed/total:.1%})")

  if __name__ == "__main__":
      parser = argparse.ArgumentParser()
      parser.add_argument("--execute", action="store_true", help="Real execute (default dry_run)")
      parser.add_argument("--batch-size", type=int, default=None)
      args = parser.parse_args()
      asyncio.run(backfill(dry_run=not args.execute, batch_size=args.batch_size))
  ```
- **错误做法**：
  ```python
  # ❌ 一次性 UPDATE 全表，无 dry_run 无分批
  async def backfill_cover_url():
      await db.execute(update(Material).values(cover_url=None))  # 锁表风险
      # 实际上没调用 extract_cover_image，字段仍为 NULL
  ```
- **适用场景**：所有 ORM 模型字段新增场景；数据迁移场景（字段类型变更/数据格式转换）
- **不适用场景**：纯查询字段（computed property）；临时字段（一次性使用后删除）；少量数据（<100 条可直接事务处理）

## 规范 118-126：2026-07-22 前端交互稳定性与编辑完整性复盘新增规范

### 规范 118：浏览器窗口最小化防护

**SPA 后台管理系统中，401 跳转必须用 router.push（非 location.href），错误提示前必须检查 !document.hidden，后台轮询请求必须加 silent: true。**

- 为什么：浏览器最小化时，任何 ElMessage.error / location.href 全量刷新都会触发 DOM 插入或页面重载，导致最小化的窗口被重新激活弹出。本次浏览器最小化自动弹出问题经历三轮修复才彻底解决，根因是 Edit 工具损坏文件未及时发现，且未验证构建产物。
- 阈值参数（通过 `project-config.json#frontend_minimize_guard` 配置）：
  - `forbid_location_href`: true（禁止 location.href 全量刷新）
  - `require_hidden_check`: true（错误提示前必须检查 document.hidden）
  - `silent_param`: "silent"（静默请求参数名）
  - `strict_path_match`: true（路径判断用 === 严格相等，禁止 includes）
  - `login_path`: "/login"（登录页路径，可配置）
- 判断信号：
  - grep `location\.href\s*=` 在 api/index.js 或 router 守卫
  - grep `ElMessage\.(error|warning|success)\(` 后无 `!document.hidden` 检查
  - grep `pathname\.includes\(['"]\/login['"]\)` 应改为 `===`
- 正确做法：
  ```javascript
  if (error.response?.status === 401) {
    localStorage.removeItem('admin_token')
    if (globalThis.location.pathname !== '/login') {
      router.push('/login')
    }
  } else if (!error.config?.silent && !document.hidden) {
    ElMessage.error(error.response?.data?.message || '请求失败')
  }
  ```
- 错误做法：
  ```javascript
  if (status === 401) { location.href = '/login' }
  ElMessage.error(message)
  ```
- 适用：SPA 后台管理系统、需要轮询的页面、ElMessage 全局拦截器
- 不适用：SSR 应用、移动端 App、无登录态系统

### 规范 119：异步路由参数时序处理

**router.replace/router.push 是异步操作，回调内禁止依赖 route.params 即时更新，必须用显式传参模式或 detail.value 取最新值。**

- 为什么：router.replace 是异步操作，调用后 route.params.id 尚未更新，立即执行 loadDetail() 会请求旧 ID。本次工作流重跑后 loadDetail 请求的是旧工作流 ID。
- 阈值参数（通过 `project-config.json#route_param_timing` 配置）：
  - `explicit_param_mode`: true（loadDetail 接受可选 workflowId 参数）
  - `use_detail_value`: true（轮询函数用 detail.value.xxx 而非 route.params）
  - `await_after_replace`: true（router.replace 后必须 await loadDetail(new_id)）
- 判断信号：
  - grep `router\.(replace|push)\(` 后立即调用依赖 route.params 的函数
  - grep `setInterval.*route\.params` 在轮询回调中读 route.params
- 正确做法：
  ```javascript
  async function loadDetail(workflowId) {
    const wid = workflowId || route.params.id
    detail.value = await api.get(`/workflows/${wid}`)
    startPolling()
  }
  async function handleRetry() {
    const data = await api.post(`/workflows/${route.params.id}/retry`, {...})
    router.replace(`/workflows/${data.new_workflow_id}`)
    await loadDetail(data.new_workflow_id)
  }
  ```
- 错误做法：
  ```javascript
  router.replace(`/workflows/${data.new_workflow_id}`)
  await loadDetail()  // route.params.id 还是旧值
  ```
- 适用：任何 SPA 路由跳转后需立即加载新数据的场景
- 不适用：同步路由；URL 直接访问

### 规范 120：列表数据动态轮询状态同步

**轮询必须满足：终态停止、运行态轮询、不可见暂停、silent 请求、重跑重置。**

- 为什么：重跑后状态不更新导致用户无法感知执行状态；轮询触发的 ElMessage 同样会激活最小化窗口；页面不可见时继续轮询浪费资源。
- 阈值参数（通过 `project-config.json#polling_state_sync` 配置）：
  - `interval_ms`: 3000（轮询间隔，默认 3 秒）
  - `terminal_states`: ["success", "failed"]（终态列表）
  - `running_state`: "running"（运行态，触发轮询）
  - `silent_param`: "silent"（静默请求参数名）
  - `pause_on_hidden`: true（页面不可见时暂停轮询）
  - `stop_before_restart`: true（重跑/重置前必须 stopPolling）
- 判断信号：
  - grep `setInterval` 无 `clearInterval` 配对
  - grep `setInterval` 无 `document.hidden` 检查
  - grep 轮询回调内调用 `ElMessage` 无 `silent: true`
- 正确做法：
  ```javascript
  function startPolling() {
    stopPolling()
    if (detail.value.status === 'running' && !document.hidden) {
      const wid = detail.value.workflow_id
      pollTimer = setInterval(async () => {
        if (document.hidden) return
        try {
          detail.value = await api.get(`/workflows/${wid}`, { silent: true })
          if (detail.value.status !== 'running') stopPolling()
        } catch { }
      }, POLL_INTERVAL)
    }
  }
  onMounted(() => {
    loadDetail()
    document.addEventListener('visibilitychange', handleVisibilityChange)
  })
  onUnmounted(() => {
    stopPolling()
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  })
  ```
- 错误做法：
  ```javascript
  pollTimer = setInterval(async () => {
    const data = await api.get(`/workflows/${id}`)
    if (data.status === 'success') ElMessage.success('完成')
  }, 3000)
  ```
- 适用：工作流/任务监控、长耗时操作状态跟踪、批处理进度
- 不适用：WebSocket/SSE 实时推送；一次性查询；高频数据

### 规范 121：第三方服务模型名称核对

**模型名称以官方文档为准，大小写敏感；LLM_PRESETS 中 model 字段必须与 API 实际接受的值一致。**

- 为什么：本次 Agnes AI 模型名 "Agnes-2.0-Flash"（大写）被 API 拒绝，改为 "agnes-2.0-flash"（小写）才通过。
- 阈值参数（通过 `project-config.json#model_name_verification` 配置）：
  - `case_sensitive`: true（模型名大小写敏感）
  - `official_source_required`: true（必须以官方文档为准）
  - `sync_pricing_table`: true（新增模型必须同步定价表）
  - `sync_frontend_presets`: true（新增模型必须同步前端预设列表）
- 判断信号：
  - grep `LLM_PRESETS` 中 model 字段含大写字母
  - 新增 Provider 时未查询官方文档
- 正确做法：
  ```python
  LLM_PRESETS = [
      {"key": "agnes", "label": "Agnes AI",
       "base_url": "https://api.agnes-ai.com/v1",
       "model": "agnes-2.0-flash"},
  ]
  ```
- 错误做法：
  ```python
  "model": "Agnes-2.0-Flash"  # 大写，API 拒绝
  ```
- 适用：接入任何第三方 LLM/TTS/Image API；新增 Provider 预设
- 不适用：内部自研 API；模型名固定不变

### 规范 122：API Key 脱敏回退链路

**返回前端前必须用 is_masked 检查并脱敏；前端提交时若 is_masked=true，后端必须回退到数据库真实密钥；preset_configs 旧数据必须兼容填充。**

- 为什么：本次切换回 DeepSeek 时 API Key 为空，根因是首次使用 preset_configs 机制时数据库无存储值。脱敏回退需要前后端协同，三层缺一不可。
- 阈值参数（通过 `project-config.json#masked_key_fallback` 配置）：
  - `is_masked_check`: true（返回前端前必须 is_masked 检查）
  - `fallback_to_db`: true（前端提交 is_masked=true 时后端回退数据库值）
  - `preset_configs_storage`: true（每个预设独立存储 api_key + model）
  - `legacy_data_compat`: true（旧数据用数据库全局值填充）
  - `masked_prefix`: "sk-****"（脱敏前缀，可配置）
- 判断信号：
  - grep `api_key` 返回前端前无 `is_masked` 检查
  - grep `preset_configs` 无旧数据兼容填充逻辑
- 正确做法：
  ```python
  def get_config():
      config = read_from_db()
      if config.get("api_key"):
          config["api_key_masked"] = _mask_api_key(config["api_key"])
          config["is_masked"] = True
      presets = config.get("preset_configs", {})
      selected = config.get("llm_preset")
      if selected and selected not in presets:
          presets[selected] = {"api_key": config.get("api_key", ""),
                               "model": config.get("llm_model", "")}
      return config

  def update_config(payload):
      if payload.get("is_masked"):
          payload["api_key"] = read_from_db().get("api_key", "")
  ```
- 错误做法：
  ```python
  def get_config():
      return read_from_db()  # api_key 明文返回
  ```
- 适用：任何配置页面有 API Key 脱敏显示的场景；多预设独立配置
- 不适用：无 API Key 的系统；单租户无脱敏需求；前端只读不提交

### 规范 123：文件编辑完整性验证

**Edit 工具修改后必须 Read 验证文件完整性；大范围重写优先用 Write 工具；修复后必须 Grep 构建产物验证修复代码已编译。**

- 为什么：本次 api/index.js 被 Edit 工具严重损坏（变量名错误、语法截断、函数名损坏），导致第一轮修复未生效。损坏信号检测 + 构建产物验证是双重保险。
- 阈值参数（通过 `project-config.json#edit_integrity_verify` 配置）：
  - `verify_after_edit`: true（Edit 后必须 Read 验证）
  - `corruption_signals`: ["reesponse", "ne  }", "Mesror", "El.respon", "globalThis.location.href"]
  - `use_write_for_large_rewrite`: true（大范围重写优先 Write）
  - `build_grep_check`: true（修复后 Grep 构建产物验证）
  - `build_artifact_path`: "admin-web/dist/assets"
- 判断信号：
  - Edit 后 Read 文件发现变量名错误（如 `(reesponse.data`）
  - Edit 后 Read 文件发现语法截断（如 `return Promise.reject(ne  }`）
  - Edit 后 Read 文件发现函数名损坏（如 `Mesror('无权限...')`）
- 正确做法：
  ```text
  步骤 1: Edit 修改后 Read 验证完整性
  步骤 2: 检测损坏信号（变量名错误、语法截断、函数名损坏）
  步骤 3: 若损坏，改用 Write 工具完整重写
  步骤 4: 构建后 Grep 构建产物验证修复代码已编译
    grep "document.hidden" admin-web/dist/assets/*.js
    grep "$t.push(\"/login\")" admin-web/dist/assets/*.js
  ```
- 错误做法：
  ```text
  Edit 后不验证，直接构建
  结果：文件损坏，构建产物不包含修复代码，用户反馈"还是存在"
  ```
- 适用：所有使用 Edit 工具修改文件的场景；大范围重写
- 不适用：全新文件创建（用 Write）；小范围单行修改且 old_string 唯一

### 规范 124：步骤进度可视化

**进度条状态映射：pending=0%、running/retrying=50%、success/failed=100%；success 用 status='success'，failed 用 status='exception'；running/retrying 启用条纹动画。**

- 为什么：本次工作流详情页步骤缺少进度条，用户无法直观感知执行进度。el-progress 的状态映射 + 条纹动画提供清晰的视觉反馈。
- 阈值参数（通过 `project-config.json#step_progress_visualize` 配置）：
  - `state_mapping`: {"pending": 0, "running": 50, "retrying": 50, "success": 100, "failed": 100}
  - `success_status`: "success"（绿色）
  - `failed_status`: "exception"（红色）
  - `stripe_anim_states`: ["running", "retrying"]
  - `max_percentage`: 100
- 判断信号：
  - grep 工作流步骤表格无 `el-progress` 组件
  - grep `el-progress` 的 `percentage` 无状态映射函数
- 正确做法：
  ```vue
  <el-table-column label="进度" width="200">
    <template #default="{ row }">
      <el-progress
        :percentage="stepProgress(row)"
        :status="stepProgressStatus(row.status)"
        :striped="row.status === 'running' || row.status === 'retrying'"
        :striped-flow="row.status === 'running' || row.status === 'retrying'"
      />
    </template>
  </el-table-column>
  ```
- 错误做法：
  ```vue
  <el-table-column label="状态">
    <template #default="{ row }">{{ row.status }}</template>
  </el-table-column>
  ```
- 适用：工作流步骤、任务流水线、批处理进度、长耗时操作
- 不适用：实时数据流；瞬时操作（<1秒）；纯文本终端

### 规范 125：跨流程组合应用场景

**多个流程模板可组合应用：详情页优化 = R118+R119+R120+R124；配置页优化 = R121+R122+R123；测试连接 = R121+R122。**

- 为什么：本次工作流详情页优化同时涉及 4 个流程模板，AI 配置页优化涉及 3 个流程模板。
- 阈值参数（通过 `project-config.json#cross_flow_combination` 配置）：
  - `detail_page_combo`: ["R118", "R119", "R120", "R124"]
  - `config_page_combo`: ["R121", "R122", "R123"]
  - `test_connection_combo`: ["R121", "R122"]
- 判断信号：
  - 详情页优化需求（重跑状态 + 进度条 + 路由跳转）→ 应用 detail_page_combo
  - 配置页优化需求（模型名 + API Key + 编辑修复）→ 应用 config_page_combo
  - 测试连接失败 → 应用 test_connection_combo
- 正确做法：识别场景 → 应用对应组合 → 按组合中每个流程模板执行
- 错误做法：只应用单一流程模板，忽略其他相关流程
- 适用：详情页优化、配置页优化、测试连接
- 不适用：单一问题场景；互斥流程

### 规范 126：配置驱动与通用性约束

**所有技能参数必须通过 config.yaml / project-config.json 管理；禁止在审查规则或测试用例中硬编码 URL、账号、阈值；新增业务场景只需修改配置文件。**

- 为什么：本次优化四个技能要求无硬编码、参数化、通用性。流程模板本身固定，参数化的是模板内的具体数值。
- 阈值参数（通过 `project-config.json#config_driven_universal` 配置）：
  - `config_files`: ["project-config.json", "config.yaml"]
  - `forbid_hardcoded`: ["url", "account", "threshold", "interval"]
  - `template_fixed`: true（流程模板固定，参数化的是模板内的具体数值）
  - `new_scenario_config_only`: true（新增场景只需修改配置文件）
- 判断信号：
  - grep 技能代码含硬编码 URL（http://localhost、127.0.0.1）
  - grep 技能代码含硬编码账号（admin/admin123）
  - grep 技能代码含硬编码阈值（3000ms、50%、0.001）
- 正确做法：
  ```yaml
  polling_state_sync:
    interval_ms: 3000
    terminal_states: ["success", "failed"]
  ```
- 错误做法：
  ```javascript
  const POLL_INTERVAL = 3000  // 硬编码
  ```
- 适用：所有技能（code-dev/review/testing）；多项目复用；参数频繁调整
- 不适用：一次性脚本；原型验证；纯文档技能

## 规范 127-129：2026-07-22 外部服务降级与异常过滤复盘新增规范

### 规范 127：外部服务降级本地存储模式

**COS/OSS/S3 等外部对象存储未配置或不可达时，必须降级到本地文件系统保证业务连续性；单一真相源 `is_xxx_configured()` 全项目复用；静态目录挂载顺序在 SPA fallback 之前。**

- **为什么**：生产环境 COS 可能因配置缺失、凭证失效、网络不可达等原因不可用。若代码直接 raise 会导致整个工作流失败，已生成的 TTS 音频浪费。本次 TTS COS 上传失败后，实施本地降级存储（`data/audio_cache/` + `/audio/<key>` 静态目录）保证业务连续性。
- **阈值参数**（通过 `project-config.json#external_storage_fallback` 配置）：
  - `enabled`: true（是否启用降级模式）
  - `severity`: "CRITICAL"（违规严重级别）
  - `single_truth_source_fn`: "is_cos_configured"（单一真相源函数名，全项目复用）
  - `local_dir`: "data/audio_cache"（本地降级目录）
  - `static_mount_point`: "/audio"（静态目录挂载点）
  - `url_generator_modes`: ["cos", "local"]（URL 生成函数必须感知的模式）
  - `downstream_prefixes`: ["/audio/"]（下游消费者支持的前缀列表）
  - `fallback_log_level`: "INFO"（降级模式日志级别）
- **判断信号**：
  - grep `cos_client.put_object` 后无 try/except 或无 fallback 分支
  - grep `if is_cos_configured():` 后无 else 分支
  - grep 多处 `if settings.COS_SECRET_ID:` 重复判断（应复用 `is_cos_configured()`）
  - grep 外部存储上传失败直接 raise 而非降级
- **正确做法**：
  ```python
  from app.core.config import is_cos_configured

  async def upload_audio(content: bytes, key: str) -> str:
      if is_cos_configured():
          try:
              cos_client.put_object(Bucket=settings.COS_BUCKET, Key=key, Body=content)
              return f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
          except Exception as e:
              logger.warning(f"COS upload failed, fallback to local: {e}")
      # 降级到本地存储
      local_dir = Path(settings.LOCAL_AUDIO_CACHE_DIR)
      local_dir.mkdir(parents=True, exist_ok=True)
      (local_dir / key).write_bytes(content)
      logger.info("External COS not configured, fallback to local storage")
      return f"/audio/{key}"
  ```
- **错误做法**：
  ```python
  # 多处重复判断 + 无降级
  if settings.COS_SECRET_ID and settings.COS_SECRET_KEY:
      cos_client.put_object(...)
      return url
  raise RuntimeError("COS not configured")  # 业务中断
  ```
- **适用场景**：生产环境 COS 降级、开发环境无 COS、COS 配置缺失容错
- **不适用场景**：纯本地开发环境（无需 COS 配置检测）；已配置 COS 的稳定生产环境

### 规范 128：Windows asyncio ConnectionResetError 异常过滤

**Windows 平台 FastAPI/uvicorn 服务，浏览器 audio 标签提前关闭连接时，ProactorBasePipeTransport 抛出 ConnectionResetError [WinError 10054]，属平台已知行为非业务 bug，必须通过配置驱动的事件循环异常处理器过滤，避免日志污染。**

- **为什么**：Windows asyncio ProactorBasePipeTransport 在客户端提前关闭连接时，服务端 `socket.shutdown` 抛出 `ConnectionResetError`。这是 Python + Windows 的已知行为，非业务 bug。但默认异常处理器会打印完整 traceback 到 stderr，污染日志，干扰真实问题定位。
- **阈值参数**（通过 `project-config.json#asyncio_exception_filter` 配置）：
  - `enabled`: true（是否启用异常过滤）
  - `severity`: "MEDIUM"（违规严重级别，非业务 bug 但需减少日志污染）
  - `enabled_platforms`: ["win32"]（启用平台，仅 Windows）
  - `ignored_exceptions`:
    - `exception_type`: "ConnectionResetError"（异常类型）
    - `transport_class`: "ProactorBasePipeTransport"（传输类名）
    - `winerror`: 10054（Windows 错误码）
    - `log_level`: "DEBUG"（过滤后日志级别）
  - `handler_priority`: 100（处理器优先级）
- **判断信号**：
  - 日志中重复出现 `Exception in callback _ProactorBasePipeTransport._call_connection_lost`
  - `ConnectionResetError: [WinError 10054]` 频繁出现
  - 无自定义异常处理器过滤此类已知行为
- **正确做法**：
  ```python
  import sys
  from app.core.config import settings

  def _on_loop_exception(loop, context):
      exc = context.get('exception')
      handle = context.get('handle', '')
      for rule in settings.ASYNCIO_IGNORED_EXCEPTIONS:
          if (isinstance(exc, getattr(__builtins__, rule['exception_type'], object))
                  and rule['transport_class'] in str(handle)):
              logger.debug(f"Ignored platform exception: {rule['exception_type']}")
              return
      loop.default_exception_handler(context)

  if sys.platform == 'win32' and settings.ASYNCIO_SUPPRESS_CONNECTION_RESET:
      loop.set_exception_handler(_on_loop_exception)
  ```
- **错误做法**：
  ```python
  # 无异常过滤，日志被污染
  loop = asyncio.get_event_loop()
  # 默认异常处理器会打印完整 traceback 到 stderr
  ```
- **适用场景**：Windows 平台部署、客户端连接频繁断开（如浏览器 audio 标签）
- **不适用场景**：Linux/macOS（select/epoll 无此问题）；服务端长连接

### 规范 129：本地路径 URL 约定

**外部存储降级模式下，URL 必须使用 `/audio/<key>` 相对路径约定，映射到 `data/audio_cache/<key>` 物理路径；下游 download_file 函数必须优先检测本地前缀，命中则用 shutil.copyfile 直接拷贝，禁止 httpx 自回路请求本机服务。**

- **为什么**：外部存储降级模式下，下游服务（如 ffmpeg、TTS 拼接器）需要通过 URL 访问本地文件。若用 httpx 自回路请求本机服务（`http://localhost:8000/audio/...`）会造成性能损耗和死锁风险（事件循环等待自己处理请求）。
- **阈值参数**（通过 `project-config.json#local_path_url` 配置）：
  - `enabled`: true（是否启用本地路径约定）
  - `severity`: "HIGH"（违规严重级别）
  - `url_prefixes`:
    - `prefix`: "/audio/"（URL 前缀）
    - `physical_dir`: "data/audio_cache"（物理目录）
    - `copy_strategy`: "shutil.copyfile"（拷贝策略）
  - `forbidden_patterns`:
    - "http://localhost:*/audio/"（禁止自回路请求）
    - "http://127.0.0.1:*/audio/"（禁止自回路请求）
  - `required_prefix_detection`: true（download_file 必须支持前缀检测）
- **判断信号**：
  - grep `download_file(url)` 函数无 `url.startswith('/audio/')` 分支
  - grep `httpx.get('http://localhost:*/audio/')` 自回路请求
  - grep 文件路径硬编码绝对路径
- **正确做法**：
  ```python
  import shutil
  from pathlib import Path

  async def download_file(url: str, dest: str) -> None:
      for prefix_config in settings.LOCAL_PATH_PREFIXES:
          prefix = prefix_config['prefix']
          physical_dir = Path(prefix_config['physical_dir'])
          if url.startswith(prefix):
              key = url[len(prefix):]
              src = physical_dir / key
              shutil.copyfile(str(src), dest)
              return
      async with httpx.AsyncClient() as client:
          resp = await client.get(url)
          resp.raise_for_status()
          with open(dest, 'wb') as f:
              f.write(resp.content)
  ```
- **错误做法**：
  ```python
  # 自回路请求本机服务下载本地文件
  async with httpx.AsyncClient() as client:
      resp = await client.get(url)  # url 是 http://localhost:8000/audio/xxx
  ```
- **适用场景**：外部存储降级模式、本地开发联调、CI 测试环境
- **不适用场景**：已配置 COS 的生产环境；跨主机访问场景

## 规范 140-143：2026-07-13 前端组件类型契约与配置覆盖复盘新增规范

> 以下规范来源于 2026-07-13 频道管理 3 类问题修复复盘：el-switch 状态不持久化（JS `===` 严格比较陷阱）、AI 生成超时（前后端超时不协同）、频道级配置覆盖全局（service 层未实现优先级链路）。所有阈值通过 `project-config.json#frontend_switch_type_contract`、`project-config.json#api_timeout_override`、`project-config.json#channel_level_config_override`、`project-config.json#event_bus_config_driven` 配置管理。

### 规范 140：el-switch 双向绑定值类型契约

**当后端返回 int（0/1）时，el-switch 必须显式 `:active-value="1" :inactive-value="0"`；form 初始值与 @change 回调参数类型必须与 active-value 一致，禁止依赖 JS 隐式类型转换。**

- **为什么**：el-switch 默认 `active-value=true`（bool）、`inactive-value=false`（bool），但后端 `is_active` 字段是 int 0/1。JavaScript 严格相等 `1 === true` 为 false，导致开关始终显示关闭。更隐蔽的是，el-switch 在列表渲染初始化时，值从 int 1 变为默认 false 时会触发 `@change` 事件，将 `row.is_active` 改写为 false，提交给后端时数据丢失；同时初始化阶段触发的 ElMessage 会误导用户"已禁用"。
- **阈值参数**（通过 `project-config.json#frontend_switch_type_contract` 配置）：
  - `enabled`: true（启用强制类型契约）
  - `require_explicit_values`: true（强制显式声明 active-value/inactive-value）
  - `active_value_type`: "int"（active-value 类型，与后端字段类型一致）
  - `inactive_value_type`: "int"（inactive-value 类型）
  - `active_value`: 1（active-value 字面值）
  - `inactive_value`: 0（inactive-value 字面值）
  - `applicable_components`: ["el-switch", "el-radio", "el-checkbox"]（适用组件列表）
  - `backend_field_types`: {"is_active": "int", "status": "int", "enabled": "int"}（后端字段类型映射）
  - `change_callback_param_must_match`: true（@change 回调参数类型必须与 active-value 一致）
  - `form_init_must_match_active_value`: true（form 初始值必须与 active-value 类型一致）
- **判断信号**：
  - grep `<el-switch` 无 `:active-value` 属性且后端对应字段为 int 类型
  - grep `:active-value="true"` 或 `:active-value="'1'"`（类型与后端不一致：bool/str vs int）
  - grep `form\.is_active\s*=\s*true` 或 `form\.is_active\s*=\s*'1'`（form 初始值类型与 active-value 不一致）
- **正确做法**：
  ```vue
  <!-- ✅ 显式声明 int 类型 active-value/inactive-value -->
  <el-switch
    v-model="row.is_active"
    :active-value="1"
    :inactive-value="0"
    @change="handleActiveChange(row)"
  />

  <script setup>
  // form 初始值类型与 active-value 一致（int 1，非 bool true / str '1'）
  const form = ref({
    is_active: 1,
    name: '',
  })

  // @change 回调参数类型与 active-value 一致（int 0 或 1）
  function handleActiveChange(row) {
    // row.is_active 此时为 int 1 或 0，可直接提交后端
    api.post('/channels/update', { id: row.id, is_active: row.is_active })
  }
  </script>
  ```
- **错误做法**：
  ```vue
  <!-- ❌ 未显式声明 active-value，依赖默认 true/false -->
  <el-switch v-model="row.is_active" @change="handleActiveChange(row)" />
  <!-- row.is_active 是 int 1，但 el-switch 默认 active-value=true -->
  <!-- 1 === true 为 false，开关始终显示关闭 -->
  <!-- 初始化时 el-switch 把 row.is_active 从 1 改为 false，触发 @change -->

  <script setup>
  // ❌ form 初始值类型为 bool，与后端 int 不一致
  const form = ref({ is_active: true })
  </script>
  ```
- **适用场景**：所有 el-switch/el-radio/el-checkbox 双向绑定后端 int 0/1 字段；管理后台开关状态字段；任何后端返回 int 但前端默认 bool 的场景
- **不适用场景**：后端已返回 bool 的字段；纯展示组件（无 v-model 双向绑定）；无状态组件

### 规范 141：请求级超时覆盖全局

**长耗时接口（AI 生成/大文件上传/批量处理）必须请求级 timeout 覆盖 axios 全局默认值；后端 LLM 调用 timeout 必须从 settings 读取，且支持 `max(LLM_TIMEOUT_SEC*N, MIN)` 公式动态计算。**

- **为什么**：axios 默认 `timeout=15000ms`（15 秒），但 AI 生成 4 段提示词需 30-60 秒。前端 15 秒超时先于后端 30 秒触发，导致接口报错 `timeout of 15000ms exceeded`，但后端实际仍在正常执行，造成资源浪费和用户感知失败。前后端超时必须协同：前端 timeout ≥ 后端实际耗时上限，后端 timeout 从 settings 读取可配置，避免硬编码。
- **阈值参数**（通过 `project-config.json#api_timeout_override` 配置）：
  - `enabled`: true（启用长耗时接口超时覆盖）
  - `default_timeout_ms`: 15000（axios 全局默认超时）
  - `long_running_endpoints`: ["/channels/{id}/generate-prompts", "/workflows/trigger", "/workflows/batch-delete", "/admin/.*upload", "/admin/.*import"]（长耗时接口正则列表）
  - `override_timeout_ms`: 120000（长耗时接口请求级超时，默认 120 秒）
  - `llm_timeout_multiplier`: 2（LLM 超时倍数，长文本生成 N=2）
  - `min_llm_timeout_sec`: 60（LLM 最小超时秒数）
  - `backend_setting_key`: "LLM_TIMEOUT_SEC"（后端 settings 中的超时配置键名）
  - `frontend_timeout_must_ge_backend`: true（前端 timeout 必须 ≥ 后端 timeout）
- **判断信号**：
  - grep `api\.(post|put|get)\(` 调用长耗时接口（含 AI/upload/batch/import）但无 `{ timeout: }` 请求级配置
  - grep 后端 LLM 调用代码硬编码 `timeout=30` 而非从 `settings.LLM_TIMEOUT_SEC` 读取
  - 接口报错 `timeout of 15000ms exceeded` 但后端日志显示仍在执行
- **正确做法**：
  ```javascript
  // ✅ 前端：长耗时接口请求级 timeout 覆盖全局
  export function generateChannelPrompts(channelId) {
    return api.post(
      `/channels/${channelId}/generate-prompts`,
      {},
      { timeout: 120000 } // 请求级 timeout 覆盖 axios 默认 15s
    )
  }
  ```
  ```python
  # ✅ 后端：LLM timeout 从 settings 读取，支持 max(N*multiplier, MIN) 公式
  from app.core.config import settings

  async def generate_prompts(channel_id: int):
      cfg = settings.api_timeout_override
      prompt_timeout = max(
          settings.LLM_TIMEOUT_SEC * cfg.llm_timeout_multiplier,
          cfg.min_llm_timeout_sec,
      )
      result = await asyncio.wait_for(
          _call_llm_generate(prompts),
          timeout=prompt_timeout,
      )
  ```
- **错误做法**：
  ```javascript
  // ❌ 长耗时接口无请求级 timeout，使用 axios 默认 15s
  export function generateChannelPrompts(channelId) {
    return api.post(`/channels/${channelId}/generate-prompts`, {})
    // 15s 后报 timeout of 15000ms exceeded
  }
  ```
  ```python
  # ❌ 后端 LLM timeout 硬编码
  async def generate_prompts(channel_id: int):
      result = await asyncio.wait_for(_call_llm_generate(prompts), timeout=30)
      # 30s 硬编码，不可配置；前端 15s 先超时
  ```
- **适用场景**：AI 生成接口（提示词/稿件/摘要）、大文件上传、批量处理、导入导出等长耗时 API；任何实际耗时可能超过 axios 默认 15s 的接口
- **不适用场景**：短查询接口（<3s）；本地操作（无网络 IO）；WebSocket 长连接（用心跳机制而非 timeout）

### 规范 142：频道级配置覆盖全局

**多频道/多租户场景下，频道级配置字段（schedule_time/is_active/intro_prompt/outro_prompt/constraint_prompt/rewrite_template/rss_sources/keywords）必须优先于 settings 全局配置；频道字段为空时 fallback 到全局 settings；service 层必须实现优先级链路。**

- **为什么**：只做全局配置时所有频道共享同一参数，无法差异化运营。本次修复前，channel_prompt_service.py 直接读 `settings.LLM_INTRO_PROMPT`，未查询频道字段 `channel.intro_prompt`，导致频道自定义提示词不生效，工作流使用全局默认提示词。频道级配置与全局配置的优先级关系是 SaaS 多租户的通用模式，service 层必须实现"频道字段非空优先，为空 fallback"的链路。
- **阈值参数**（通过 `project-config.json#channel_level_config_override` 配置）：
  - `enabled`: true（启用频道级配置覆盖）
  - `channel_fields`: ["schedule_time", "is_active", "intro_prompt", "outro_prompt", "constraint_prompt", "rewrite_template", "rss_sources", "keywords"]（支持频道级覆盖的字段列表）
  - `fallback_to_global`: true（频道字段为空时 fallback 到全局 settings）
  - `priority_order`: ["channel_field", "settings_global", "default_value"]（优先级顺序）
  - `global_settings_prefix`: "LLM_"（全局 settings 中对应的配置项前缀）
  - `require_event_publish_on_change`: true（频道字段变更必须发布事件，见 R143）
- **判断信号**：
  - grep `settings\.(LLM_|X)` 在 service 层中无 `if channel.x is not None` 频道级检查
  - grep service 函数参数中无 `channel` 对象但使用全局 settings 配置提示词
  - 频道配置了自定义提示词但工作流实际使用全局默认值
- **正确做法**：
  ```python
  from app.core.config import settings

  async def build_prompts(channel: Channel) -> dict:
      """构建提示词，频道级字段优先于 settings 全局。"""
      # 优先级：channel.xxx → settings.LLM_XXX → 默认值
      intro = channel.intro_prompt or settings.LLM_INTRO_PROMPT or ""
      outro = channel.outro_prompt or settings.LLM_OUTRO_PROMPT or ""
      constraint = channel.constraint_prompt or settings.LLM_CONSTRAINT_PROMPT or ""
      rewrite_tpl = channel.rewrite_template or settings.LLM_REWRITE_TEMPLATE or ""
      return {
          "intro": intro,
          "outro": outro,
          "constraint": constraint,
          "rewrite_template": rewrite_tpl,
      }

  async def get_schedule_time(channel: Channel) -> str:
      """频道级 schedule_time 优先于全局。"""
      return channel.schedule_time or settings.DEFAULT_SCHEDULE_TIME
  ```
- **错误做法**：
  ```python
  # ❌ service 层直接读全局 settings，未查询频道字段
  async def build_prompts(channel_id: int) -> dict:
      # 频道自定义提示词不生效
      return {
          "intro": settings.LLM_INTRO_PROMPT,
          "outro": settings.LLM_OUTRO_PROMPT,
      }
  ```
- **适用场景**：多频道/多租户/多环境差异化配置场景；频道级配置字段（提示词/模板/调度时间/状态）；SaaS 产品的租户级配置覆盖
- **不适用场景**：单频道项目（无频道概念）；全局唯一配置（如数据库路径、JWT 密钥）；无频道字段的配置项

### 规范 143：配置驱动事件总线

**频道字段变更必须通过 EventBus 发布事件（channel.active_changed/channel.schedule_changed），订阅者重注册 cron 任务或取消 queued 工作流；事件发布用 `publish_nowait` 避免阻塞主流程；订阅者必须幂等。**

- **为什么**：频道 `schedule_time` 变更后，原 cron 任务不更新，仍按旧时间触发；频道 `is_active` 变更为 0 后，已入队的工作流仍会执行。缺少事件总线导致配置变更无法联动调度系统。事件发布必须用 `publish_nowait`（非阻塞），否则配置变更接口会因订阅者执行慢而超时；订阅者必须幂等，避免重复注册 cron 或重复取消工作流。
- **阈值参数**（通过 `project-config.json#event_bus_config_driven` 配置）：
  - `enabled`: true（启用事件总线）
  - `event_types`: ["channel.active_changed", "channel.schedule_changed"]（事件类型列表）
  - `publish_method`: "publish_nowait"（事件发布方法，非阻塞）
  - `subscriber_idempotent`: true（订阅者必须幂等）
  - `subscribers`: {"channel.active_changed": ["_on_channel_active_changed"], "channel.schedule_changed": ["_on_channel_schedule_changed"]}（事件订阅者映射）
  - `event_data_fields`: ["channel_id", "is_active", "schedule_time"]（事件数据字段列表）
- **判断信号**：
  - grep `update.*channel` 后无 `bus\.publish_nowait` 事件发布
  - grep `schedule_time` 变更后无 `channel.schedule_changed` 事件
  - grep `is_active` 变更后无 `channel.active_changed` 事件
  - 频道配置变更后 cron 任务未更新（仍按旧时间触发）
- **正确做法**：
  ```python
  from app.core.event_bus import bus

  async def update_channel(channel_id: int, payload: dict):
      """更新频道，发布配置变更事件。"""
      old = await get_channel(channel_id)
      await db.execute(update(Channel).where(Channel.id == channel_id).values(**payload))
      await db.commit()

      # 配置变更发布事件（非阻塞）
      if "is_active" in payload and payload["is_active"] != old.is_active:
          bus.publish_nowait(
              "channel.active_changed",
              {"channel_id": channel_id, "is_active": payload["is_active"]},
          )
      if "schedule_time" in payload and payload["schedule_time"] != old.schedule_time:
          bus.publish_nowait(
              "channel.schedule_changed",
              {"channel_id": channel_id, "schedule_time": payload["schedule_time"]},
          )

  # 订阅者：幂等重注册 cron / 取消 queued 工作流
  @bus.subscribe("channel.schedule_changed")
  async def _on_channel_schedule_changed(event: dict):
      """幂等：先移除旧 cron，再注册新 cron。"""
      channel_id = event["channel_id"]
      schedule_time = event["schedule_time"]
      await scheduler.remove_job(f"channel_cron_{channel_id}")  # 幂等：不存在不报错
      if schedule_time:
          await scheduler.add_job(
              trigger_workflow, "cron", hour=schedule_time.hour, minute=schedule_time.minute,
              id=f"channel_cron_{channel_id}", args=[channel_id],
          )

  @bus.subscribe("channel.active_changed")
  async def _on_channel_active_changed(event: dict):
      """幂等：频道禁用时取消 queued 工作流。"""
      if not event["is_active"]:
          await cancel_queued_workflows(event["channel_id"])  # 幂等：无 queued 不报错
  ```
- **错误做法**：
  ```python
  # ❌ 频道字段变更无事件发布
  async def update_channel(channel_id: int, payload: dict):
      await db.execute(update(Channel).where(Channel.id == channel_id).values(**payload))
      await db.commit()
      # 未发布 channel.active_changed / channel.schedule_changed 事件
      # cron 任务不更新，queued 工作流不取消

  # ❌ 事件发布用阻塞方法
  await bus.publish("channel.schedule_changed", data)  # 阻塞主流程
  ```
- **适用场景**：频道/租户配置变更需联动调度系统的场景；cron 任务重注册；queued 工作流取消；任何配置变更需通知订阅者的场景
- **不适用场景**：单频道项目（无配置变更）；无调度系统的项目；同步场景（可直接调用，无需事件总线）

## 规范 156-161：2026-07-22 三参数联动与编码规范系统提炼复盘新增规范

> 以下规范来源于 2026-07-22 音频拼接时长越界（276s 超出 [300, 630]）问题修复复盘：TTS 语速 1.5 倍导致实际时长缩短、目标时长参数缺失、字数与语速未联动、校验范围硬编码、错误诊断信息不完整、前端 computed 命名冲突。所有阈值通过 `project-config.json#config_full_chain_registration`、`project-config.json#estimation_actual_param_linkage`、`project-config.json#dynamic_range_calculation`、`project-config.json#error_diagnostic_completeness`、`project-config.json#frontend_computed_naming_safety`、`project-config.json#dual_verification_workflow` 配置管理。

### 规范 156：配置项全链路注册

**新增配置项必须贯穿 config.py → ai_config_service（CONFIG_KEY_MAP + INT_KEYS + _normalize + get_config_for_frontend）→ 前端序列化五端，缺任一端则配置无法持久化或前端不可见。**

- **为什么**：TARGET_DURATION_SEC 配置项最初只在 config.py 定义，未在 ai_config_service 的 CONFIG_KEY_MAP 注册，导致前端保存后无法回传后端；未加入 INT_KEYS 导致类型不归一化；未在 _normalize 中处理导致写入时被丢弃；未在 get_config_for_frontend 中序列化导致前端读取不到。配置项的"五端注册"是配置全链路管理的最小完整集合，缺少任何一端都会导致配置"断链"。
- **阈值参数**（通过 `project-config.json#config_full_chain_registration` 配置）：
  - `enabled`: true（启用全链路注册校验）
  - `required_anchors`: ["config_py_field", "config_key_map", "int_keys_or_float_keys", "normalize_handler", "frontend_serialize"]（必须注册的五端）
  - `config_key_map_location`: "ai_config_service.py CONFIG_KEY_MAP dict"（CONFIG_KEY_MAP 定义位置）
  - `int_keys_location`: "ai_config_service.py INT_KEYS list"（INT_KEYS 定义位置）
  - `normalize_location`: "ai_config_service.py _normalize_llm function"（_normalize 定义位置）
  - `frontend_serialize_location`: "ai_config_service.py get_config_for_frontend function"（前端序列化位置）
  - `type_keys_map`: {"int": "INT_KEYS", "float": "FLOAT_KEYS", "str": "STR_KEYS"}（类型与 keys 列表映射）
- **判断信号**：
  - grep `config.py` 新增 `X_FIELD: int = 600` 但 `ai_config_service.py` 的 `CONFIG_KEY_MAP` 无 `"x_field": "X_FIELD"` 映射
  - grep `CONFIG_KEY_MAP` 含 `"x_field"` 但 `INT_KEYS`/`FLOAT_KEYS` 无 `"x_field"`（类型未注册）
  - grep `_normalize_llm` 中无 `"x_field"` 分支（写入时被丢弃）
  - grep `get_config_for_frontend` 的 `llm_config` 中无 `"x_field"` 字段（前端读取不到）
- **正确做法**：
  ```python
  # 1. config.py：定义字段
  class Settings(BaseSettings):
      X_FIELD: int = 600

  # 2. ai_config_service.py：五端注册
  CONFIG_KEY_MAP = {
      ...
      "x_field": "X_FIELD",  # ② CONFIG_KEY_MAP 注册
  }
  INT_KEYS = [..., "x_field"]  # ③ INT_KEYS 注册（int 类型）

  def _normalize_llm(config: dict) -> dict:
      result = {}
      ...
      if "x_field" in config:  # ④ _normalize 处理
          result["x_field"] = str(config["x_field"])
      return result

  def get_config_for_frontend(...):
      ...
      llm_config = {
          ...
          "x_field": _get_int("x_field", "X_FIELD", 600),  # ⑤ 前端序列化
      }
  ```
- **错误做法**：
  ```python
  # ❌ 只在 config.py 定义，未注册到 ai_config_service
  # 前端保存配置 → 后端 _normalize 不识别 → 写入时被丢弃 → 读取时回退默认值
  class Settings(BaseSettings):
      X_FIELD: int = 600
  # ai_config_service.py 中无任何引用 → 配置"断链"
  ```
- **适用场景**：所有需要前端可配置的后端 settings 字段；AI 配置项（LLM/TTS 参数）；任何通过 admin-web 持久化到 SQLite 的配置项
- **不适用场景**：仅后端内部使用的配置（如 SQLITE_DB_PATH）；环境变量直接读取的配置（不经 ai_config_service）；一次性脚本配置

### 规范 157：估算参数与实际产出联动

**当系统存在"估算值"与"实际产出值"两个相关参数时，估算公式必须包含实际产出参数作为变量；调整实际产出参数时，估算值必须自动重新计算。**

- **为什么**：TTS 语速设为 1.5 倍后，实际音频时长 = 字数 / (基础语速 × 1.5) × 60，但 rewriter 仍按基础语速估算字数，导致生成 1450 字 → 实际 1450/(210×1.5)×60 = 276s，远低于目标 600s。估算与实际产出脱钩是参数联动失效的根因。三参数数学模型：`时长(秒) = 总字数 / (基础语速 × 语速倍率) × 60`，反算 `总字数 = 时长 × 基础语速 × 倍率 / 60`，调整任一参数时必须按公式反算其他参数。
- **阈值参数**（通过 `project-config.json#estimation_actual_param_linkage` 配置）：
  - `enabled`: true（启用估算与实际产出联动）
  - `linkage_formula`: "duration = words / (base_rate * multiplier) * 60"（联动公式）
  - `reverse_formula`: "words = duration * base_rate * multiplier / 60"（反算公式）
  - `params`: ["duration_sec", "total_words", "base_rate", "rate_multiplier"]（联动参数列表）
  - `adjustable_params`: ["duration_sec", "rate_multiplier"]（用户可调参数）
  - `derived_params`: ["total_words", "segment_count", "words_per_segment"]（自动反算参数）
  - `provider_rate_mapping`: {"edge": "parse_edge_rate", "tencent": "1.0 + speed * 0.1", "aliyun": "1.0"}（Provider 语速解析映射）
  - `clamp_range`: {"rate_multiplier": [0.5, 2.5], "duration_sec": [180, 1800]}（参数安全范围）
- **判断信号**：
  - grep 估算公式中不含实际产出参数（如 `words = duration * 330 / 60` 无 `rate_multiplier` 变量）
  - grep 调整语速配置后估算字数未重新计算（无 `_get_rate_multiplier()` 调用）
  - grep 实际产出（TTS 时长）与估算值（字数推算时长）偏差 > 15%
- **正确做法**：
  ```python
  # ✅ 估算公式包含实际产出参数（rate_multiplier）
  def _calc_target_words(target_sec: int, rate_multiplier: float) -> int:
      """按目标时长 + 实际语速反算所需总字数。"""
      return int(target_sec * WORDS_PER_MINUTE * rate_multiplier / 60)

  def _assemble_script(segments, rate_multiplier: float = 1.0):
      """组装时用实际语速估算时长，而非基础语速。"""
      actual_words_per_min = WORDS_PER_MINUTE * rate_multiplier
      estimated_duration = total_words / actual_words_per_min * 60
  ```
- **错误做法**：
  ```python
  # ❌ 估算公式不含语速倍率，按基础语速估算
  def _calc_target_words(target_sec: int) -> int:
      return int(target_sec * WORDS_PER_MINUTE / 60)  # 缺少 rate_multiplier
  # 语速 1.5 倍时：估算 2100 字 → 实际 2100/(210×1.5)×60 = 400s（目标 600s，偏差 33%）
  ```
- **适用场景**：TTS 语速/时长/字数三参数联动；任何"估算→实际产出"场景（如视频时长估算、文件大小估算）；用户可调参数影响产出的场景
- **不适用场景**：固定参数场景（无用户可调变量）；纯展示场景（估算值不用于控制逻辑）；一次性计算（无联动需求）

### 规范 158：校验范围动态计算

**时长/容量/大小等校验范围必须基于目标值动态计算，禁止硬编码固定范围；动态范围公式：[max(下限, target×0.85), target×1.15]。**

- **为什么**：stitch 原硬编码 `MIN_DURATION_SEC=200, MAX_DURATION_SEC=630`，当目标时长从 600s 改为 300s 时，最大值 630s 仍不变，导致 300s 目标下允许 630s 的音频通过校验（超出目标 110%）。动态范围基于目标值计算，目标变化时范围自动跟随，确保校验始终与目标对齐。
- **阈值参数**（通过 `project-config.json#dynamic_range_calculation` 配置）：
  - `enabled`: true（启用动态范围计算）
  - `lower_bound_ratio`: 0.85（下限比例，target × 0.85）
  - `upper_bound_ratio`: 1.15（上限比例，target × 1.15）
  - `absolute_min`: 180（绝对下限，max(absolute_min, target×ratio)）
  - `absolute_max`: null（绝对上限，null 表示无上限，否则 target×ratio 和 absolute_max 取小）
  - `target_field`: "TARGET_DURATION_SEC"（目标值字段名）
  - `applicable_metrics`: ["duration_sec", "file_size_mb", "word_count"]（适用度量指标）
- **判断信号**：
  - grep `MIN_DURATION_SEC = 200` 或 `MAX_DURATION_SEC = 630` 等硬编码范围常量
  - grep 校验逻辑 `if duration < MIN or duration > MAX` 中 MIN/MAX 为字面值而非动态计算
  - grep `target_duration` 配置项变更后校验范围未跟随变化
- **正确做法**：
  ```python
  ABSOLUTE_MIN_DURATION_SEC = 180

  def _get_duration_range() -> tuple[int, int]:
      """按目标时长动态计算允许的时长范围。"""
      target = getattr(settings, "TARGET_DURATION_SEC", 600) or 600
      try:
          target = int(target)
      except (ValueError, TypeError):
          target = 600
      low = max(ABSOLUTE_MIN_DURATION_SEC, int(target * 0.85))
      high = int(target * 1.15)
      return low, high
  ```
- **错误做法**：
  ```python
  # ❌ 硬编码固定范围
  MIN_DURATION_SEC = 200
  MAX_DURATION_SEC = 630
  if not (MIN_DURATION_SEC <= duration <= MAX_DURATION_SEC):
      raise StitchError(f"时长 {duration}s 超出 [{MIN}, {MAX}]")
  # 目标改为 300s 时，MAX=630 仍允许 630s 通过（超出目标 110%）
  ```
- **适用场景**：音频/视频时长校验；文件大小校验；字数/段数校验；任何基于目标值的容差范围校验
- **不适用场景**：物理硬限制（如 HTTP 状态码 200-299）；协议固定值（如 TCP 端口 0-65535）；无目标值的绝对限制

### 规范 159：错误诊断信息完整性

**校验类异常信息必须包含：目标值、实际值、允许范围、配置来源，四要素缺一则运维无法定位根因。**

- **为什么**：原错误 `最终音频时长 276s 超出允许范围 [300, 630]` 缺少目标值（600s）和配置来源（TARGET_DURATION_SEC），运维无法判断是目标配置错误还是 TTS 语速问题。完整诊断信息应让运维一眼看出：目标是什么、实际是多少、允许范围、范围如何计算。
- **阈值参数**（通过 `project-config.json#error_diagnostic_completeness` 配置）：
  - `enabled`: true（启用错误诊断完整性校验）
  - `required_fields`: ["target_value", "actual_value", "allowed_range", "config_source"]（必须包含的四要素）
  - `config_source_format`: "settings.{FIELD_NAME} (default={DEFAULT})"（配置来源格式）
  - `range_explanation_format`: "目标 {target}s ±{ratio}%"（范围解释格式）
  - `applicable_exception_types`: ["StitchError", "ValueError", "RuntimeError"]（适用异常类型）
- **判断信号**：
  - grep `raise.*Error.*超出.*范围` 但错误信息中无目标值（`target`）
  - grep `raise.*Error.*时长` 但错误信息中无配置来源（`TARGET_DURATION_SEC`）
  - grep 校验异常信息仅含实际值和范围，缺少目标值和范围计算依据
- **正确做法**：
  ```python
  min_allowed, max_allowed = _get_duration_range()
  if not (min_allowed <= duration <= max_allowed):
      raise StitchError(
          f"最终音频时长 {duration}s 超出允许范围 "
          f"[{min_allowed}, {max_allowed}]"
          f"（目标时长 {getattr(settings, 'TARGET_DURATION_SEC', 600)}s ±15%）"
      )
  # 输出：最终音频时长 276s 超出允许范围 [510, 690]（目标时长 600s ±15%）
  # 运维可立即判断：目标 600s，实际 276s，范围 [510, 690]，目标配置正确 → 排查字数/语速
  ```
- **错误做法**：
  ```python
  # ❌ 错误信息缺少目标值和配置来源
  raise StitchError(f"最终音频时长 {duration}s 超出允许范围 [{min}, {max}]")
  # 运维不知道目标是什么，范围如何计算，无法定位根因
  ```
- **适用场景**：所有校验类异常（时长/大小/数量/范围）；配置驱动的校验逻辑；运维需要快速定位的校验失败
- **不适用场景**：用户输入校验（前端表单验证）；协议级错误（HTTP 400/404）；业务逻辑错误（如"库存不足"）

### 规范 160：前端 computed 命名避让内置属性

**Vue 3 computed 名称不得与 Element Plus 组件内置 prop/属性名冲突，否则 computed 返回值会覆盖组件内置行为导致不可预期的 UI 异常。**

- **为什么**：AIConfig.vue 中 computed 命名为 `duration`（计算目标时长），与 el-slider 的内置 prop `duration`（动画时长）冲突，导致 el-slider 滑动时 computed 返回值覆盖了组件内置动画时长，出现滑动卡顿。Element Plus 组件内置 prop 名是保留字，computed 命名必须避让。
- **阈值参数**（通过 `project-config.json#frontend_computed_naming_safety` 配置）：
  - `enabled`: true（启用 computed 命名安全检查）
  - `reserved_prefixes`: ["el-", "El"]（Element Plus 组件前缀）
  - `conflict_detection`: true（启用冲突检测）
  - `known_conflicting_props`: ["duration", "size", "type", "placeholder", "name", "value", "label", "disabled", "readonly", "loading"]（已知与 Element Plus 组件 prop 冲突的常见名称）
  - `naming_pattern`: "calculatedXxx / expectedXxx / xxxValue"（推荐命名模式，加前缀避免冲突）
  - `check_scope`: "computed + ref + reactive 字段名"（检查范围）
- **判断信号**：
  - grep `const duration = computed(` 但模板中使用 `<el-slider v-model="duration">`（冲突）
  - grep computed 名称出现在 `known_conflicting_props` 列表中
  - grep computed 名称与同文件中 el-* 组件的 prop 名相同
- **正确做法**：
  ```vue
  <!-- ✅ computed 加前缀避免冲突 -->
  <script setup>
  const calculatedDuration = computed(() => form.target_duration_sec)
  const expectedWords = computed(() => calcWords(calculatedDuration.value, edgeRatePercent.value))
  </script>
  <template>
    <el-slider v-model="form.target_duration_sec" />
    <el-tag>预期字数：{{ expectedWords }}</el-tag>
  </template>
  ```
- **错误做法**：
  ```vue
  <!-- ❌ computed 命名 duration 与 el-slider 内置 prop duration 冲突 -->
  <script setup>
  const duration = computed(() => form.target_duration_sec)
  </script>
  <template>
    <el-slider v-model="duration" />  <!-- duration 覆盖 el-slider 动画时长 -->
  </template>
  ```
- **适用场景**：Vue 3 + Element Plus 项目的 computed/ref/reactive 命名；任何 UI 框架的组件 prop 保留字避让
- **不适用场景**：非 UI 框架项目；纯逻辑模块（无 UI 组件）；局部变量（非响应式）

### 规范 161：修改后双重验证流程

**代码修改后必须执行双重验证：后端 py_compile 全部修改文件 + 前端 vite build 全量构建，两者均通过方可认定修改完成。**

- **为什么**：rewriter.py 修改后未执行 py_compile，导致 WORDS_PER_MINUTE 常量重复定义（Edit 工具残留旧代码）未被发现，运行时后者覆盖前者。前端 AIConfig.vue 修改后未执行 vite build，computed 命名冲突等语法错误未被发现。双重验证是修改完成的必要条件，编译/构建能发现语法错误、重复定义、导入缺失等问题。
- **阈值参数**（通过 `project-config.json#dual_verification_workflow` 配置）：
  - `enabled`: true（启用双重验证）
  - `backend_verify_command`: "python -m py_compile {files}"（后端验证命令模板）
  - `frontend_verify_command`: "npm run build"（前端验证命令）
  - `verify_all_modified_files`: true（验证所有修改文件，非仅入口文件）
  - `fail_fast`: true（任一文件验证失败立即停止）
  - `cleanup_check`: true（验证后检查常量重复定义、残留旧代码）
  - `grep_after_edit`: true（Edit 工具修改常量后必须 grep 全局去重）
- **判断信号**：
  - 修改 .py 文件后未执行 `python -m py_compile` 验证
  - 修改 .vue/.js 文件后未执行 `npm run build` 验证
  - Edit 工具修改常量后未 grep 全局检查重复定义
  - 声称"修改完成"但未提供编译/构建通过的证明
- **正确做法**：
  ```powershell
  # 后端修改后：逐文件 py_compile 验证
  python -m py_compile backend/app/config.py
  python -m py_compile backend/app/services/ai_config_service.py
  python -m py_compile backend/app/workflow/llm/rewriter.py
  python -m py_compile backend/app/workflow/stitch/concat.py

  # 修改常量后：grep 全局去重
  # Grep WORDS_PER_MINUTE 确认无重复定义

  # 前端修改后：vite build 全量构建
  cd admin-web; npm run build
  # build exit 0 方可认定完成
  ```
- **错误做法**：
  ```python
  # ❌ 修改后未验证，残留重复定义
  WORDS_PER_MINUTE = 470  # 旧代码残留
  WORDS_PER_MINUTE = 210  # 新代码，运行时后者覆盖前者
  ```
- **适用场景**：所有代码修改后的验证；Edit 工具修改常量后的去重检查；发版前的编译/构建验证
- **不适用场景**：文档修改（无编译需求）；配置文件修改（无语法检查）；注释修改（不影响运行）

## 规范 171-185：2026-07-31 微信登录修复+历史对话复盘新增规范

以下 15 条规范来源于 2026-07-27 至 2026-07-31 的多个历史对话复盘，使用 Sequential Thinking 从四个维度（成功步骤 / 失败点 / 可抽象流程 / 适用场景）系统提炼。

### 规范 171：小程序用户态数据双层同步

**小程序中写入 globalData 的用户态数据必须同步写入 localStorage，确保跨会话持久化。**

- 适用：小程序所有用户态数据（userInfo / token / 偏好设置）
- 不适用：纯 UI 状态（弹窗开关）、会话内临时数据（临时文件路径）
- 判断信号：grep 搜索 `app.globalData.userInfo =` 后无 `setToken` 或 `wx.setStorageSync` 调用
- 正确做法：每次写入 globalData 后，紧接 `const tk = getToken(); if (tk) setToken(tk, enriched);` 同步 localStorage
- 为什么：globalData 是小程序进程内内存，重启即丢；若不同步 localStorage，重启后若 login() 失败（网络/invalid code）会回退读 getUser() 拿到旧空缓存，导致"保存了头像昵称但下次进来又没了"

### 规范 172：Pydantic Settings 单例导入模式

**后端模块导入配置必须使用 get_settings() 工厂函数，禁止直接导入 settings 实例。**

- 适用：backend/app/ 下所有模块导入配置
- 不适用：测试代码（用 fixture 注入）、scripts/ 下独立脚本
- 判断信号：grep 搜索 `from app.config import settings`（直接导入实例）
- 正确做法：`from app.config import get_settings` + 模块级 `settings = get_settings()`
- 为什么：直接导入 settings 实例可能在配置未加载时就触发实例化，导致 ImportError 或配置缺失；get_settings 用 lru_cache 延迟加载，与 user_service 等模块一致

### 规范 173：统一响应模式测试断言对齐

**测试断言必须对齐项目统一响应模式：BizError 返回 HTTP 200 + JSON body {code: 非0}，而非标准 RESTful 的 HTTP 4xx。**

- 适用：所有调用返回统一响应格式 API 的测试
- 不适用：HTTP 异常端点（如 /health/ready 返回 503）、文件上传 multipart 响应
- 判断信号：grep 搜索测试代码中 `assert resp.status_code == 400` 或 `== 422`
- 正确做法：`assert resp.status_code == 200` + `assert resp.json()["code"] == 期望错误码`
- 为什么：项目统一响应模式中 BizError 返回 HTTP 200 + JSON body {code: 非0, message: ...}，与标准 RESTful 语义不同。按标准 RESTful 习惯断言 HTTP 400 会导致假失败

### 规范 174：小程序原生代码 4 维静态验证

**小程序原生代码修改后必须通过 4 维静态验证：语法 + 接口 + 契约 + 渲染。**

- 适用：微信小程序原生代码修改后、无法用 Playwright 直接测试的场景
- 不适用：Web 应用（应直接用 Playwright 动态测试）、后端 Python 代码（应用 pytest）
- 判断信号：修改了 miniprogram/ 下的 .js 文件但未做 4 维验证
- 正确做法：
  - 语法维：`node --check` 检查所有修改的 .js 文件
  - 接口维：读取依赖模块，验证调用签名一致性
  - 契约维：读取后端路由，验证请求/响应字段对齐
  - 渲染维：读取 .wxml，验证数据绑定字段名与 setData 一致
- 为什么：小程序的 Page/wx/getApp 等全局对象在 Node.js 中不存在，无法直接执行；4 维静态验证是不启动小程序的情况下最全面的验证方式

### 规范 175：前后端字段契约验证清单

**前后端交互的 API 开发后必须按验证清单核对字段：请求字段对齐 + 响应字段对齐 + 兜底链数据源验证。**

- 适用：任何涉及前后端交互的 API 开发
- 不适用：纯前端 UI 逻辑（动画/布局）、纯后端内部逻辑（工作流编排）
- 判断信号：前端使用 snake_case 而后端返回 camelCase，或前端用了后端不返回的字段名
- 正确做法：
  - 请求字段：前端发送的字段名 vs 后端 Pydantic Model 定义的字段名
  - 响应字段：后端返回的字段名 vs 前端使用的字段名
  - 兜底链：前端多名字兜底（如 `avatar_url || avatar || avatarUrl`）是否有对应的数据源
- 为什么：规范 16 已定义"前后端字段契约"原则，但缺少具体的验证清单流程。本规范补充可操作的验证步骤

### 规范 176：文件上传安全双重校验

**文件上传接口必须实施扩展名白名单 + content_type 双重校验 + 大小上限 + 流式写入。**

- 适用：所有文件上传接口（头像/封面/BGM/附件）
- 不适用：纯文本/JSON 接口
- 判断信号：grep 搜索 `UploadFile` 无扩展名白名单检查，或无 content_type 校验
- 正确做法：
  - 扩展名白名单：`_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}`
  - content_type 双重校验：扩展名与 content_type 必须匹配
  - 大小上限：流式写入时累计字节超过上限则拒绝
  - 文件名：用 user_id + timestamp 命名，避免路径穿越
- 为什么：仅校验扩展名可被伪造（改后缀绕过），content_type 双重校验防止上传可执行文件

### 规范 177：小程序进度上报条件容错

**小程序进度上报不得因单一字段异常（如 duration<=0）而整体跳过，必须容错处理。**

- 适用：小程序所有进度/状态上报逻辑
- 不适用：无上报需求的纯展示页面
- 判断信号：grep 搜索 `if (duration > 0)` 或 `if (duration <= 0) return` 在进度上报函数中
- 正确做法：将 listened_seconds 作为独立累计字段，duration<=0 时仍上报 listened_seconds，不跳过整个上报
- 为什么：HLS 流式播放下 duration 初始为 0，若以此跳过上报会导致 listened_seconds 永远为 0，用户收听时长统计失真

### 规范 178：UNIQUE 约束冲突 IntegrityError 兜底

**数据库写入操作必须捕获 IntegrityError 并做兜底处理，不因 UNIQUE 约束冲突导致整个流程失败。**

- 适用：所有涉及 UNIQUE 约束的数据库写入（material.url / user.openid 等）
- 不适用：无 UNIQUE 约束的表、允许重复的日志表
- 判断信号：grep 搜索 `db.add()` 或 `db.flush()` 后无 `except IntegrityError`
- 正确做法：
  ```python
  try:
      db.add(obj)
      await db.flush()
  except IntegrityError:
      await db.rollback()
      # 兜底：查询已有记录并复用，或跳过
  ```
- 为什么：dedup TTL 清理后仍可能存在残留记录，并发写入时 UNIQUE 约束冲突是预期场景而非错误

### 规范 179：状态属性与标志位一致性

**对象的状态属性（property）必须先检查标志位，不能直接重新查询覆盖已设置的标志位。**

- 适用：所有有 stop()/start() 方法的状态对象（TailscaleProvider / 播放器 / 连接池）
- 不适用：无状态服务、一次性操作
- 判断信号：grep 搜索 `def status` 属性中直接查询外部状态而无标志位检查
- 正确做法：stop() 中设置 `self._stopped = True`，status 属性开头检查 `if self._stopped: return "stopped"`
- 为什么：stop() 后若 status 属性重新查询外部状态（如 `tailscale funnel status`），会覆盖 _stopped 标志位，返回 "running"，导致 UI 显示与实际不符

### 规范 180：音频队列自动播放

**小程序音频播放器 onEnded 必须触发 playNext 自动播放下一首，队列空时 _autoFillQueue 预填。**

- 适用：小程序音频播放器
- 不适用：单曲循环模式、用户主动暂停
- 判断信号：grep 搜索 `onEnded` 无 `playNext` 调用
- 正确做法：
  ```javascript
  audioManager.onEnded(() => {
      this.playNext();  // 自动播放下一首
  });
  // playNext 中队列空时调 _autoFillQueue 预填
  ```
- 为什么：用户听节目时不会手动点下一首，onEnded 不自动播放会导致播放中断，用户体验差

### 规范 181：工作流 0 结果阻断+失败详情可见

**工作流步骤返回 0 结果时必须标记失败并阻断后续步骤，result 中包含失败详情供前端展示。**

- 适用：所有工作流步骤（crawl / rewrite / tts 等）
- 不适用：允许 0 结果的查询步骤（如搜索）
- 判断信号：grep 搜索 `material_count == 0` 或 `len(results) == 0` 后无 `raise RuntimeError`
- 正确做法：
  ```python
  if material_count == 0:
      raise RuntimeError({
          "failure_details": {
              "source_details": [...],
              "troubleshooting_hints": [...]
          }
      })
  ```
- 为什么：0 结果仍标记 success 会导致后续步骤（rewrite/tts）因无输入而报错，且前端无法显示失败原因。在 crawl 步骤阻断可避免不必要的 LLM 调用

### 规范 182：小程序分包配置校验

**小程序 app.json 中主包页面路径不能在分包 root 目录下，提交前必须校验。**

- 适用：小程序 app.json 配置变更
- 不适用：无分包的小程序
- 判断信号：app.json 中 pages 数组的页面路径以 subPackages[].root 为前缀
- 正确做法：预检脚本遍历 pages 数组，检查每个页面路径是否在任一分包 root 下，有冲突则报错
- 为什么：主包页面在分包 root 下会触发编译错误，且报错信息不直观，容易浪费排查时间

### 规范 183：HTTP 编码探测 fallback

**HTTP 抓取时 header 无 charset 必须用 charset_normalizer 探测编码，不依赖默认 UTF-8。**

- 适用：所有 HTTP 抓取场景（RSS / 网页解析 / API 调用）
- 不适用：已知编码的 API 响应（如 JSON 默认 UTF-8）
- 判断信号：grep 搜索 `resp.text` 或 `resp.encoding` 无 charset_normalizer fallback
- 正确做法：
  ```python
  if not resp.encoding or resp.encoding == 'ISO-8859-1':
      detected = charset_normalizer.detect(resp.content)
      resp.encoding = detected['encoding']
  ```
- 为什么：部分中文网站（如人民网）HTTP header 不声明 charset，默认按 ISO-8859-1 解码会导致中文乱码

### 规范 184：启停脚本 PID 文件三级兜底

**启停脚本必须实现三级进程查找兜底：PID 文件 → 进程名 → 端口监听者。**

- 适用：所有服务的启停脚本（start.ps1 / stop.ps1）
- 不适用：Docker 容器环境（用 docker stop）
- 判断信号：grep 搜索 stop 脚本中仅用 PID 文件查找进程，无进程名/端口兜底
- 正确做法：
  1. 优先读 PID 文件
  2. PID 文件不存在时，按进程名（如 `python.*launcher.py`）查找
  3. 进程名找不到时，按端口监听者（如 `netstat -ano | findstr :8000`）查找
- 为什么：健康检查超时时 start.ps1 可能未写入 PID 文件，stop.ps1 仅依赖 PID 文件会导致旧进程残留、端口占用

### 规范 185：风格库顺序轮换去重

**LLM 生成内容使用风格库时必须用 seq % len(candidates) 顺序轮换，避免高频词重复。**

- 适用：LLM 改写/生成中的风格库（开场白/过渡词/结尾词）
- 不适用：固定模板（如新闻标题格式）、随机选择场景
- 判断信号：grep 搜索 `random.choice` 或 `candidates[0]` 在风格库选择中
- 正确做法：
  ```python
  intro = style_library['intro'][seq % len(style_library['intro'])]
  ```
- 为什么：random.choice 可能连续选中同一项，candidates[0] 永远用第一个；顺序轮换确保每个候选词均匀使用，高频词重复率降低 40%+


