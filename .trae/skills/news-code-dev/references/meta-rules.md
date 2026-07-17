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


