# 后端代码审查维度详解

> 本文件是 [SKILL.md](../SKILL.md) 的补充参考，包含所有审查维度的完整定义（检查项、判断信号、严重级别）。
> 当 SKILL.md 中的精简表格不足以做出判断时，展开本文件查阅对应维度的详细规则。

## 核心维度（1-15，默认全开）

### 维度 1：分层架构

依赖单向：`routers → services → models → core`，workflow 模块独立可调用 services 与 core。

- 【强制】路由层（`routers/`）仅做 HTTP 请求解析与响应组装，业务逻辑必须放在 `services/` 层
- 【强制】models/ 纯 ORM 定义，禁止含业务逻辑（如发邮件、调外部 API）
- 【强制】core/ 仅放基础设施（认证、配置、安全、异常、响应、时区）
- 【强制】workflow/ 是独立模块，可调用 services/ 和 core/，禁止反向依赖（services 不得 import workflow）
- 【禁止】routers 直接操作数据库 session 业务逻辑（依赖注入 session 后传给 service）
- 【推荐】services 之间通过显式参数传递数据，避免循环依赖

**判断信号**：
- `routers/*.py` 出现 `db.add()` / `db.execute()` 业务查询 → 违规
- `models/*.py` 出现 `httpx` / `requests` / `smtp` 调用 → 违规
- `services/*.py` 出现 `from app.workflow` → 违规

**示例**：
```python
# ❌ 反模式：路由层写业务逻辑
@router.post("/items")
async def create_item(payload: dict, db: AsyncSession = Depends(get_db)):
    item = Item(**payload)
    db.add(item)
    await db.commit()
    return success(data={"id": item.id})

# ✅ 正确：路由层只组装，业务在 service
@router.post("/items")
async def create_item(payload: ItemCreate, db: AsyncSession = Depends(get_db)):
    svc = ItemService(db)
    item_id = await svc.create(payload)
    return success(data={"id": item_id})
```

### 维度 2：命名规范

- 【强制】模块文件名 snake_case（`user_service.py`）
- 【强制】类名 PascalCase（`UserService`、`WorkflowScheduler`）
- 【强制】函数/方法 snake_case（`publish_episode`）
- 【强制】常量 UPPER_SNAKE_CASE（`MAX_RETRY_COUNT`）
- 【强制】Service 类用 `*Service` 后缀（`ContentService`、`ReviewService`）
- 【强制】Router 文件按职责前缀：`api_*.py`（C 端）/ `admin_*.py`（B 端）/ `internal_*.py`（内部）
- 【推荐】私有方法用 `_` 前缀（`_build_query`）

**判断信号**：
- 文件名含大写字母或 `-` → 违规
- Service 类无 `Service` 后缀 → 违规
- Router 文件在 `routers/api/` 下但不含 `api_` 前缀 → 违规

### 维度 3：类型注解

- 【强制】Python 3.11+ 现代语法：`X | None` 而非 `Optional[X]`、`list[X]` 而非 `List[X]`
- 【强制】函数签名标注参数与返回类型（`async def foo(x: int) -> str:`）
- 【强制】Pydantic 模型字段必须标注类型
- 【禁止】滥用 `Any`（除非确实无法确定类型，需注释说明原因）
- 【推荐】复杂类型用 `TypedDict` 或 `Pydantic BaseModel`

**判断信号**：
- 出现 `from typing import Optional, List, Dict` 且用旧式语法 → 违规
- 函数签名缺返回类型 → 违规
- `Any` 出现频率 > 阈值（`coding_standards.type_annotation.max_any_count`）→ 警告

### 维度 4：FastAPI 规范

- 【强制】路由用 `APIRouter`，统一前缀（`prefix="/api/admin/ads"`）
- 【强制】请求体验证用 Pydantic `BaseModel` + `Field` 约束（`Field(..., min_length=1, max_length=100)`）
- 【强制】响应统一用 `success()` / `error()` 包装（`core/response.py`），禁止裸返回 dict
- 【强制】依赖注入用 `Depends()`（`db: AsyncSession = Depends(get_db)`）
- 【强制】内部接口（`routers/internal/`）必须加 `verify_localhost` 依赖
- 【推荐】路径参数用类型注解（`workflow_id: str`），便于自动文档生成

**判断信号**：
- `routers/internal/*.py` 路由缺 `Depends(verify_localhost)` → 阻塞
- 路由函数直接 `return {"code": 0}` 而非 `success()` → 违规
- 路由前缀含 `/api/api/` 重复或缺失 `/api/` → 违规

**示例**：
```python
# ✅ 正确：内部接口加 verify_localhost
@router.post("/trigger")
async def trigger_workflow(
    episode_date: str = Body(..., embed=True),
    _: None = Depends(verify_localhost),  # 必须鉴权
):
    ...
    return success(data={"workflow_id": workflow_id})
```

### 维度 5：SQLAlchemy 2.0 规范

- 【强制】用 `DeclarativeBase` + `Mapped` + `mapped_column`（2.0 风格），禁止旧式 `Column`
- 【强制】异步 session（`AsyncSession`），禁止同步 `Session`
- 【强制】所有时间字段必须使用项目选定的统一时区源（`core/timeutil.py` 的 `utcnow_naive()` 或 `datetime.now()` 本地时间），**禁止同一项目内混用 UTC 与本地时间**（详见维度 38：时区一致性）
- 【强制】Enum 字段取值用 `.value`（`WorkflowStatus.RUNNING.value`），禁止裸枚举对象参与序列化
- 【禁止】裸 SQL（`db.execute(text("SELECT * FROM ..."))`），如必须用则参数化（`text("...WHERE id=:id")`）
- 【推荐】查询用 `select(Model).where(...)` 风格，禁止 legacy `Query` API

**判断信号**：
- 出现 `datetime.utcnow()` → 阻塞（Python 3.12+ 弃用）
- 出现 `datetime.now(timezone.utc)` 与 `datetime.now()` 在同一项目混用 → 阻塞（详见维度 38）
- ORM 模型出现 `Column(Integer)` 而非 `mapped_column(Integer)` → 违规
- Enum 字段直接返回对象（未调 `.value`）→ 违规

**示例**：
```python
# ❌ 反模式
created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)  # 弃用
status: Mapped[str] = mapped_column(default=WorkflowStatus.RUNNING)    # 裸枚举

# ✅ 正确
from app.core.timeutil import utcnow_naive
created_at: Mapped[datetime] = mapped_column(default=utcnow_naive)
status: Mapped[str] = mapped_column(default=WorkflowStatus.RUNNING.value)
```

### 维度 6：异步并发

- 【强制】`async def` 方法体内若不含 `await` 表达式，必须改为同步 `def`
- 【强制】`asyncio.create_task()` 必须保留引用（赋值给 `self._running_tasks` 等实例属性），防止 GC 回收
- 【强制】Redis/缓存操作用 `await`（异步客户端）
- 【强制】httpx 用 `AsyncClient`（`async with httpx.AsyncClient() as client:`）
- 【强制】锁的获取和释放必须配对（用 `lock_acquired` 标志 + try/finally）
- 【禁止】`async def` 中调用同步 IO（`requests.get` / `time.sleep` / 同步文件读写），必须用 `asyncio.to_thread()` 包装
- 【推荐】并发请求用 `asyncio.gather()`，但注意异常传播

**判断信号**：
- `asyncio.create_task(coro)` 未赋值 → 阻塞（GC 风险）
- `async def` 中出现 `requests.` / `time.sleep(` → 阻塞（阻塞事件循环）
- `finally` 块无条件 `release()` 锁（未判断 `lock_acquired`）→ 阻塞（误删他人锁）

**示例**：
```python
# ❌ 反模式：create_task 未保留引用 + finally 误删锁
async def run(self):
    asyncio.create_task(self._worker())  # GC 风险
    lock = await cache.acquire("wf_lock")
    try:
        await self._do_work()
    finally:
        await cache.release("wf_lock")  # 若 acquire 失败也会 release，误删他人锁

# ✅ 正确
async def run(self):
    self._task = asyncio.create_task(self._worker())  # 保留引用
    lock_acquired = False
    try:
        lock_acquired = await cache.acquire("wf_lock")
        if not lock_acquired:
            raise WorkflowConflictError()
        await self._do_work()
    finally:
        if lock_acquired:
            await cache.release("wf_lock")
```

### 维度 7：Redis 缓存规约

> 注：当前项目 V1.2 用 TTLCache 进程内缓存替代 Redis，但本维度规则同样适用；当缓存切回 Redis 时，Lua 脚本原子性检查自动启用。

- 【强制】cache-aside 模式：先查缓存 → 未命中查 DB → 写回缓存
- 【强制】缓存 key 命名规范：`域:操作:参数`（`episode:today:list`、`playlog:user:{user_id}`）
- 【强制】涉及多命令原子操作（如 LRANGE + LTRIM）必须用 Lua 脚本或 pipeline 事务
- 【强制】缓存失效（数据变更）后必须主动删除，禁止依赖 TTL 兜底
- 【推荐】缓存穿透用空值缓存或布隆过滤器

**判断信号**：
- `LRANGE` 后跟 `LTRIM`（无 Lua/pipeline）→ 阻塞（非原子，并发下数据丢失）
- 缓存 key 命名含空格或特殊字符 → 违规
- 写 DB 后未删缓存 → 违规（cache-aside 失效）

**示例**：
```python
# ❌ 反模式：LRANGE + LTRIM 非原子
items = await redis.lrange(key, 0, 99)
await redis.ltrim(key, 100, -1)  # 并发下可能误删其他写入

# ✅ 正确：Lua 脚本保证原子性
LUA_POP_N = """
local items = redis.call('LRANGE', KEYS[1], 0, ARGV[1]-1)
redis.call('LTRIM', KEYS[1], ARGV[1], -1)
return items
"""
items = await redis.eval(LUA_POP_N, 1, key, 100)
```

### 维度 8：安全

- 【强制】JWT token 比较用 `hmac.compare_digest()`，禁止 `==`（防时序攻击）
- 【强制】密码用 bcrypt 哈希（`passlib[bcrypt]`），禁止明文存储
- 【强制】JWT 黑名单机制（登出写黑名单，认证中间件检查）
- 【强制】SQL 注入防护：参数化查询，禁止字符串拼接 SQL
- 【强制】敏感词过滤器必须在应用启动时初始化（调用 `load_words()`），否则后续 `contains()` 全返回 False
- 【强制】内部接口必须 `verify_localhost` 鉴权
- 【推荐】敏感配置（密钥、token）通过环境变量注入，禁止入库

**判断信号**：
- `token == ` / `if token ==` → 阻塞（时序攻击）
- `password` 字段明文存储 → 阻塞
- `sensitive_filter.load_words` 在启动流程中缺失 → 阻塞（过滤器未初始化）
- 登出接口缺失或未写黑名单 → 阻塞（JWT 无法失效）

### 维度 9：错误处理

- 【强制】自定义异常体系继承 `BizError`（`core/exceptions.py`），统一全局处理器转换响应
- 【强制】异常名不得覆盖内置（用 `BizPermissionError` 而非 `PermissionError`）
- 【强制】路由层用 try-except 捕获服务层异常并转换为 HTTP 响应（或依赖全局处理器）
- 【强制】关键路径异常必须用 `logger.exception()` 记录完整 traceback，禁止 `logger.warning(f"...{e}")` 丢堆栈
- 【禁止】裸 `except:` + `pass`（吞异常）
- 【推荐】异常携带上下文（`workflow_id`、`step_name`）

**判断信号**：
- `class PermissionError(Exception)` → 阻塞（覆盖内置）
- `except: pass` → 阻塞
- `except Exception as e: logger.warning(f"...{e}")` 在关键路径 → 阻塞（丢 traceback）

**示例**：
```python
# ❌ 反模式
class PermissionError(Exception):  # 覆盖内置
    pass

except Exception as e:
    logger.warning(f"工作流失败: {e}")  # 丢 traceback

# ✅ 正确
class BizPermissionError(BizError):  # 加 Biz 前缀
    pass

except Exception as e:
    logger.exception("工作流失败")  # 保留 traceback
    raise StepFailedError("workflow", e)
```

### 维度 10：配置驱动

- 【强制】所有外部参数通过 `settings`（`core/config.py`）管理，禁止散落 `os.getenv`
- 【强制】禁止硬编码：URL、密钥、超时时间、TTL、QPS、重试次数等
- 【强制】`.env` 文件管理环境变量，`.env.example` 提供模板（占位符 `<...>`）
- 【强制】`config.yaml` 不得含明文凭据（密钥、token）
- 【推荐】配置项按职责分组（应用、数据库、缓存、JWT、LLM、TTS、COS、SCF、告警、工作流）

**判断信号**：
- 出现 `os.getenv("XXX")` 直接读取 → 违规（应走 settings）
- 代码内出现 `"http://..."` / `"https://..."` 硬编码 URL → 违规
- `timeout=30` 等魔法数字未提取到 settings → 违规
- `config.yaml` 出现 `password: "real_secret"` 明文 → 阻塞

### 维度 11：工作流编排

- 【强制】`WorkflowScheduler` 单实例锁（Redis 分布式锁或 TTLCache 互斥锁），防止并发触发
- 【强制】步骤状态机：`pending → running → success/failed`，每步独立 session 避免长事务
- 【强制】失败重试耗尽后必须告警（企业微信 webhook / 短信），并记录失败原因
- 【强制】`finally` 块仅释放自己获取的锁（`lock_acquired` 标志），禁止无条件 release
- 【推荐】备播机制：检查日 episode 未发布则复用前一日音频

**判断信号**：
- `WorkflowScheduler` 无互斥锁 → 阻塞（并发触发重复执行）
- `finally` 块 `release()` 未判断 `lock_acquired` → 阻塞（误删他人锁）
- 失败重试耗尽无告警 → 违规（运营无感知）
- 跨步骤复用同一 session → 违规（长事务持锁）

### 维度 12：前后端字段契约

- 【强制】后端 ORM 字段名 = API 返回字段名（snake_case），禁止序列化时改名
- 【强制】Enum 字段返回 `.value`（字符串），禁止返回枚举对象
- 【强制】datetime 字段返回 ISO 格式字符串（`dt.isoformat()`）
- 【强制】前后端字段名必须一致（如 `categories` 而非 `category`、`episodes` 而非 `episode_list`）
- 【推荐】响应体用 Pydantic `BaseModel` 定义 schema，自动生成 OpenAPI 文档

**判断信号**：
- ORM 字段 `category` 但 API 返回 `categories`（或反之）→ 阻塞（前后端不一致）
- Enum 字段返回 `<WorkflowStatus.RUNNING: 'running'>` 而非 `'running'` → 阻塞
- datetime 返回 `"2026-07-09 05:00:00"` 而非 ISO `"2026-07-09T05:00:00"` → 违规

### 维度 13：日志规范

- 【强制】用 `logging.getLogger(__name__)`，禁止 `print()`
- 【强制】关键路径异常用 `logger.exception()`（自动带 traceback）
- 【强制】日志含上下文（`workflow_id`、`user_id`、`step_name`、`episode_id`）
- 【禁止】`print(traceback.format_exc())`，应用 `logger.exception()` 或 `logger.error(..., exc_info=True)`
- 【推荐】敏感信息（密码、token）不得记录到日志

**判断信号**：
- 出现 `print(` → 阻塞
- `logger.warning(f"...{e}")` 在 except 块 → 违规（丢 traceback）
- 日志无上下文（`logger.info("done")`）→ 警告

### 维度 14：性能

- 【强制】分页查询必须 `limit` + `offset`，禁止全表返回
- 【强制】N+1 查询检测：列表接口避免循环内查关联，用 `joinedload` 或批量查询
- 【推荐】热点数据用缓存（cache-aside）
- 【推荐】批量操作用 `bulk_insert_mappings` / `bulk_update_mappings`
- 【推荐】SQLite 用 WAL 模式 + `busy_timeout`，MySQL 用连接池

**判断信号**：
- `for item in items: await db.execute(select(...))` → 阻塞（N+1）
- 查询无 `limit` 且表数据增长 → 违规
- `for` 循环内单条 `db.add()` 而非批量 → 警告

### 维度 15：可测试性

- 【强制】服务层方法可独立测试（不依赖 `Request` 对象），通过参数注入 session
- 【推荐】测试用 SQLite 内存（`sqlite:///:memory:`）+ fakeredis（或 TTLCache mock）
- 【推荐】`conftest.py` 提供 `db_session` / `fake_cache` / `mock_llm` / `mock_tts` fixture
- 【推荐】外部服务（LLM / TTS / COS）必须 mock，禁止测试依赖真实 API
- 【推荐】接口签名变更必须同步更新测试调用

**判断信号**：
- Service 方法签名含 `request: Request` → 违规（耦合 HTTP 上下文）
- 测试中 `httpx.AsyncClient` 调真实 LLM API → 违规
- 测试 mock 类型与生产不符（`MagicMock` vs `AsyncMock`）→ 违规


## 补充审查要点（A-I）


> 以下审查要点来源于项目迭代复盘，配置详见 `config.yaml` 对应节点。

### A. PriorityQueue 取消任务审查

**配置节点**：`config.yaml#priority_queue_config`

- 【强制】asyncio.PriorityQueue 的 QueueEntry 必须包含 `cancelled` 标记字段，worker 轮询时跳过已取消条目（规范 36）
- 【强制】禁止尝试从 PriorityQueue 随机删除（底层是堆，不支持随机删除）
- 【强制】维护 `id → entry` 索引用于取消查找
- 判断信号：grep 搜索 `PriorityQueue(` 或 `queue.put(`，检查 QueueEntry 是否有 `cancelled` 字段

### B. Semaphore 管理审查

**配置节点**：`config.yaml#semaphore_management`

- 【强制】Semaphore acquire 后必须用 `try/finally` 保证释放，避免异常时信号量泄漏
- 【强制】配置热生效必须延迟重建（标记 `_config_dirty`），禁止立即重建（规范 33/37）
- 【强制】重建时必须唤醒旧 Semaphore 上的等待者，防止永久阻塞泄漏
- 判断信号：grep 搜索 `Semaphore(` 重新赋值，检查是否有 `_config_dirty` 标记 + `try/finally`

### C. SQLite VACUUM INTO 隔离级别审查

**配置节点**：`config.yaml#sqlite_vacuum`

- 【强制】SQLite VACUUM INTO 必须在 AUTOCOMMIT 隔离级别执行，不能在事务内（规范 38）
- 判断信号：grep 搜索 `VACUUM INTO` 在 `async with session.begin()` 或 `async with engine.begin()` 事务块内
- 正确做法：`await conn.execution_options(isolation_level="AUTOCOMMIT")`

### D. COS 同步幂等性审查

**配置节点**：`config.yaml#cos_sync`

- 【强制】COS 对象同步必须用 `INSERT OR IGNORE` 幂等插入 + 删除源对象双重保障（规范 40）
- 【强制】同步表必须有 `object_key` 唯一约束
- 【强制】同步成功后必须删除源对象（防止下次重复同步）
- 判断信号：grep 搜索 COS 同步逻辑，检查是否有 `INSERT OR IGNORE` + `delete_object`

### E. 文件上传校验审查

**配置节点**：`config.yaml#file_upload`

- 【强制】文件上传必须校验 Content-Type（如 `image/jpeg`、`audio/mpeg`），禁止无类型校验
- 【强制】文件上传必须限制文件大小（从 `settings.MAX_UPLOAD_SIZE_MB` 读取），禁止无大小限制
- 判断信号：grep 搜索 `UploadFile`，检查是否有 `content_type` 校验 + `size` 限制

### F. 强制发布审查

**配置节点**：`config.yaml#force_publish`

- 【强制】强制发布接口必须校验 admin 权限（`require_admin`），禁止 operator 角色强制发布
- 【强制】强制发布必须记录审计日志（操作人、目标 ID、时间戳、原因），便于事后追溯
- 判断信号：grep 搜索 `force_publish`，检查是否有 `require_admin` 依赖 + `audit_log` 写入

### G. V2.0：2026-07-21 综合复盘新增维度

> 以下要点来源于 2026-07-21 综合复盘（图片爬虫、工作流多步骤失败修复、P0/P1 改进实施、监控告警、健康度仪表盘、RSS 巡检、批量回填、PWA manifest），完整规则详见"维度 91-100"章节。所有阈值、cron 表达式、字段清单均通过 `config.yaml` 对应节点管理。

- 【强制】维度 91：图片封面提取必须实现 og:image → article `<img>` → 页面首个非装饰 `<img>` 三级 fallback，且 `og:image` 过滤装饰图、article `<img>` 排除 GIF、Material 新增 `cover_url` 配套回填脚本（联动维度 99）。配置节点：`config.yaml#image_crawl_check`
- 【强制】维度 92：素材回溯天数必须按频道入库天数动态计算（3/7/14 天三档），禁止硬编码 `FALLBACK_DAYS = N`。配置节点：`config.yaml#fallback_days_check`
- 【强制】维度 93：关键词过滤 0 条必须降级 LLM 语义过滤，LLM 失败保留全部条目供 rewriter 二次筛选，禁止直接 `raise`。配置节点：`config.yaml#llm_semantic_fallback_check`
- 【强制】维度 94：LLM 生成后必须统计字数，低于 `target * min_ratio` 重试、超出 `target * max_ratio` 丢弃多余段、低于 `target * append_threshold` 追加段，四档阈值全部配置驱动。配置节点：`config.yaml#llm_word_count_check`
- 【强制】维度 95：BGM 时长不足必须 loop-last 扩展 → silent-pad 静音降级，禁止直接 `raise`。配置节点：`config.yaml#bgm_fallback_check`
- 【强制】维度 96：关键词命中率/LLM 字数达成率/TTS 成功率/工作流成功率四类指标必须采集，低于阈值记录 WARNING，阈值通过配置管理。配置节点：`config.yaml#monitoring_thresholds_check`
- 【强制】维度 97：必须提供 `/channel-health` 端点返回频道素材健康度（healthy/warning/critical 三级），健康度阈值与必填字段通过配置管理。配置节点：`config.yaml#channel_health_dashboard_check`
- 【强制】维度 98：必须提供 `/rss-health` 端点 + APScheduler cron 定时巡检（默认 2 小时），巡检含 HTTP 状态码、响应时间、Content-Type 验证、User-Agent 兼容性。配置节点：`config.yaml#rss_reachability_check`
- 【强制】维度 99：ORM 新增字段必须编写 `backfill_*.py` 脚本，含 `--dry-run`、分批处理、幂等、进度输出。配置节点：`config.yaml#backfill_script_check`
- 【强制】维度 100：`main.py` 必须注册 `.ico` 与 `.webmanifest` MIME 类型，挂载 `public/` 目录，`manifest.json` 含必填字段。配置节点：`config.yaml#pwa_manifest_check`

### H. V2.1：2026-07-22 外部服务降级与异常过滤新增维度

> 以下要点来源于 2026-07-22 音频拼接报错处理（ConnectionResetError + 时长不足）与 TTS COS 降级本地存储修复复盘，对应编码规范 R127-R129。所有阈值、开关、白名单均通过 `config.yaml` 对应节点管理。

- 【强制】维度 113：外部对象存储上传必须实现 `is_xxx_configured()` 单一真相源检测 + 本地降级存储（`data/audio_cache/`）+ 静态目录挂载（`/audio/<key>`，挂在 SPA fallback 之前）。配置节点：`config.yaml#external_storage_fallback_check`
- 【强制】维度 114：Windows 平台必须在事件循环异常处理器中过滤 `ProactorBasePipeTransport` 相关的 `ConnectionResetError [WinError 10054]`，过滤清单配置驱动，仅 DEBUG 日志。配置节点：`config.yaml#asyncio_exception_filter_check`
- 【强制】维度 115：下游 `download_file` 函数必须优先检测本地路径前缀（`/audio/`），命中则用 `shutil.copyfile` 直接拷贝，禁止 `httpx` 自回路请求本机服务。配置节点：`config.yaml#local_path_url_check`

### I. V2.2：2026-07-13 时区一致性 + dedup 残留 + rewrite fallback 新增维度

> 以下要点来源于 2026-07-13 LLM 改写报错 + 前端素材面板空问题修复复盘（SQLite func.now() UTC 时区 bug + crawler_dedup 表残留 347 条 + rewrite 缺少回溯 fallback + PowerShell r-string 被吞 + sqlite3 列名臆测），对应编码规范 R162-R170。所有阈值、开关、白名单均通过 `config.yaml` 对应节点管理。

- 【强制】维度 142：ORM 模型时间字段禁止使用 `func.now()` 作为 default，必须使用项目统一时区源函数（`utcnow_naive()`），禁止同一项目内混用 UTC 与本地时间。配置节点：`config.yaml#timezone_consistency_check`
- 【强制】维度 143：业务表清空时必须联动清理 dedup 表；dedup 表必须有 TTL 自动清理机制；提供 dedup_count vs material_count 比对诊断接口。配置节点：`config.yaml#dedup_table_consistency`
- 【强制】维度 144：当日查询返回 0 条时必须尝试回溯最近 N 天（N 通过配置管理，按频道入库天数动态计算），回溯查询需日志告警，回溯仍 0 条才 raise。配置节点：`config.yaml#date_query_fallback`
- 【强制】维度 145：PowerShell 调用 Python 时禁止使用 r-string（`python -c "...r'...'\"`），必须使用脚本文件方式（`python script.py`）。配置节点：`config.yaml#powershell_python_compat`
- 【强制】维度 146：手动 sqlite3 查询前必须 `PRAGMA table_info(table_name)` 确认列名，禁止臆测列名。配置节点：`config.yaml#sqlite_schema_preflight`
- 【强制】维度 147：SQLite 'database is locked' 必须按 4 步诊断（长事务 → WAL 模式 → busy_timeout → 指数退避重试），禁止直接报错退出。配置节点：`config.yaml#sqlite_lock_diagnosis`
- 【强制】维度 148：stitch 时长不足时禁止直接 raise，必须按优先级尝试兜底（TTS 语速调整 → 静音段补充 → 降级接受 + 日志告警）。配置节点：`config.yaml#stitch_duration_fallback`
- 【强制】维度 149：时间字段（created_at/crawled_at/updated_at）禁止依赖数据库默认值，必须在业务代码中显式赋值（`utcnow_naive()`）。配置节点：`config.yaml#time_field_explicit_assignment`


## 扩展维度（16-149，按需激活）
### 维度 16：外部服务异常分类粒度

第三方服务异常必须按类型分类为可重试或不可重试，不能笼统包装为通用异常。

检查信号：Grep except Exception 后无按异常类型分类的分支
修复建议：将 NoAudioReceived 等空响应分类为 TTSServiceError（可重试）

### 维度 17：配置键一致性

前端表单字段名、路由模型字段名、数据库配置键、Settings 属性四者必须一致或通过明确映射连接。

检查信号：Grep 前端字段名与后端路由模型字段名不一致
修复建议：统一键名或使用 LEGACY_KEY_MAP 兼容旧键名读取

### 维度 18：批量失败诊断信息

批量操作中每步每段失败原因必须收集并在最终异常中脱敏输出。

检查信号：批量循环失败后无 summarize_segment_failures 类函数
修复建议：添加分段失败摘要函数，脱敏 API Key 和稿件正文

### 维度 19：分步重跑上游产物复用

工作流重跑必须从指定步骤开始，复用上游成功产物，而非从头执行完整流水线。

检查信号：Grep retry 路由后无提取上游产物逻辑
修复建议：实现 extract_step_result 从原工作流提取产物，注入新 context

### 维度 20：路由静态路径优先级

FastAPI 按定义顺序匹配路由，静态路由必须在动态路由之前定义。

检查信号：Grep 静态路由定义在动态路由之后
修复建议：将 batch-delete 等静态路由移至 workflow_id 之前

### 维度 21：批量操作上限约束

接收列表参数的 API 端点必须设置上限，防止单次事务过大。

检查信号：Grep list 字段无 max_length 约束
修复建议：添加 Field max_length=100 约束

### 维度 22：参数规范化写入

前端提交的数值百分比参数在写入数据库前必须规范化，避免传给第三方库的无效值。

检查信号：Grep 第三方库参数传入前无 normalize 处理
修复建议：添加 normalize_edge_adjustment 将 0.0 转为空字符串

### 维度 23：时长/容量约束自动调整

**为什么**：所有有时间、容量、大小等硬性约束的拼接/聚合操作，必须在最终校验前实现自动调整能力（填充/切除），禁止直接报错失败导致工作流中断。

检查信号：Grep duration.*超出.*范围 或 length.*exceed 后直接 raise StitchError / BusinessError
修复建议：在校验前添加自动填充（不足时追加静音/空白）和切除（超出时从末尾裁剪）逻辑，填充/切除后进行二次校验

### 维度 24：确定性失败的重试无效性

**为什么**：工作流步骤的重试只对瞬态失败（网络超时、临时 IO 错误）有意义。对于确定性失败（输入数据导致的结果不变），重试是无效的，应在步骤内部自动调整。

检查信号：Grep 步骤函数内部无外部状态依赖（无网络调用、无文件读写、无 DB 查询），却有重试逻辑
修复建议：识别失败类型——瞬态失败用重试，确定性失败在函数内部自动调整（如音频时长填充）
判断方法：检查步骤函数是否依赖外部可变状态

### 维度 25：临时资源清理保障

**为什么**：使用临时文件/目录的资源（如音频拼接、图片处理）必须在 try/finally 中确保清理，防止磁盘空间泄漏。

检查信号：Grep 	empfile.mkdtemp 或 NamedTemporaryFile 后无 finally/shutil.rmtree 清理
修复建议：使用 try/finally 确保临时资源清理，ignore_errors=True 容忍清理失败

---

### 维度 26：第三方服务模型名称以官方文档为准

**为什么**：第三方 AI 服务商（LLM/TTS）的模型名称是区分大小写的字符串。使用错误的模型名会导致 API 调用失败或路由到错误的模型。预设配置中的模型名称必须以官方文档为事实源。

检查信号：Grep 预设配置中的模型名（如 deepseek-chat），与官网文档逐字核对
修复建议：新接入服务商时先查阅官方文档确认模型名称大小写，修改预设默认模型时同步更新定价表

### 维度 27：模型定价表同步更新

**为什么**：每当修改或新增模型名称时，必须同步检查定价表中是否包含该模型条目。缺失定价条目的模型将使用默认费率（gpt-4o-mini），导致费用统计不准确。

检查信号：Grep 新增模型名是否在 MODEL_PRICING 中存在
修复建议：修改预设模型时，同时检查并更新定价表

### 维度 28：配置键四者一致性

**为什么**：前端表单字段名、路由模型字段名、数据库配置键、Settings 属性四者必须一致或通过明确映射连接。字段不一致会导致前端保存的值在后端被忽略。

检查信号：Grep 前端字段名与后端路由模型字段名不一致
修复建议：统一键名或使用 LEGACY_KEY_MAP 兼容旧键名读取

---

### 维度 29：批量删除事务原子性

**为什么**：批量删除操作涉及多表关联数据，必须在一个事务中按依赖逆序删除，任一校验失败整批回滚，禁止部分删除。

检查信号：Grep 搜索多表 delete 操作无 await db.commit() 包裹、无前置校验
修复建议：实现 batch_delete 方法，按 play_progress → play_log → episode → review → script → material → workflow_step → workflow 顺序删除

### 维度 30：路由静态路径优先级

**为什么**：FastAPI 按定义顺序匹配路由，静态路由必须在动态路由之前定义，否则静态路径会被动态路由捕获。

检查信号：Grep 静态路由（如 /batch-delete）定义在动态路由（如 /{workflow_id}）之后
修复建议：将 batch-delete 等静态路由移至 /:id 之前

### 维度 31：批量操作权限校验

**为什么**：批量删除是高危操作，必须通过 require_admin 装饰器确保仅管理员可执行。

检查信号：Grep POST /batch-delete 路由无 require_admin 装饰器
修复建议：添加 @router.post("/batch-delete") 前装饰 require_admin

### 维度 32：批量操作上限约束


---

### 维度 33：启动脚本路径含空格安全封装

**为什么**：系统 Python 路径可能包含空格（如 F:\Program Files\Python3.14\python.exe）。PowerShell 的 Start-Process -ArgumentList 会将含空格的字符串重新拆分引号，导致可执行文件路径被截断。

检查信号：Grep Start-Process 后无 /s /c 双层引号封装
修复建议：使用 cmd /d /s /c "" 四层引号封装，-ArgumentList 传数组

### 维度 34：构建脚本并发保护

**为什么**：多次执行构建脚本可能导致旧 PyInstaller 进程未完全退出，新旧进程同时写入 dist 目录造成 PermissionError / WinError 32。

检查信号：Grep Remove-Item 后无进程检查和删除验证
修复建议：构建前先终止占用旧产物的进程，删除后用 try/throw 验证成功

---

### 维度 35：日志格式与异常信息透传

**为什么**：Loguru 使用 {} 占位符，旧代码使用 %s 会导致异常对象被当作字符串格式化，真实错误信息被吞掉。

检查信号：Grep logger\.(warning|error|info).*%s
修复建议：统一使用 {} 占位符，异常日志必须包含 exc_info=True

### 维度 36：运行环境与源码一致性

**为什么**：日志格式、异常透传方式与源码版本不一致时，说明运行的是旧构建产物，新修复未生效。

检查信号：运行日志中出现 %s 格式但源码已改为 {}
修复建议：确认运行进程使用的源码版本，必要时重启服务

---

### 维度 37：共享构建依赖包完整提取

**为什么**：FFmpeg 等共享构建的 EXE 文件依赖同目录 DLL。只复制 EXE 而不提取配套 DLL 会导致运行时找不到 vdevice-63.dll 等系统错误。

检查信号：Grep zf.open(ffmpeg_member) 后只提取 exe 文件
修复建议：通过 ffmpeg.exe 定位 zip 内 bin 目录，提取所有普通文件（含 DLL），提取前清除旧文件


**为什么**：批量删除接口应设置单次操作数量上限，防止单次事务过大导致数据库压力。

检查信号：Grep 批量操作接口无 max_length 约束
修复建议：Pydantic model 中设置 Field(max_length=100)

---

> 以下维度来源于 2026-07-15 工作流执行链路复盘，覆盖时区漂移、级联清理、容错分支、动态注入、关联更新、频道级覆盖、定时触发等高频故障场景。配置详见 `config.yaml#hard_constraints.rules` 对应条目。

### 维度 38：时区一致性跨模块对齐

**为什么**：项目内多个模块涉及跨日判定（ai_budget 预算限流按"日"重置、workflow_scheduler 按本地日期触发、rewriter 按 crawled_at 本地日期回溯、crawler_dedup 按 TTL 清理）。如果 ai_budget 用 UTC 而其他模块用本地时间，会导致本地跨日时额度累加错误，触发"今日已用 501,599，上限 500,000"误报。

检查信号：Grep `datetime.now(timezone.utc)` 或 `tz=timezone.utc` 在业务模块（非 core/timeutil.py 工具函数）
修复建议：所有跨日判定统一使用 `datetime.now()` 本地时间或 `utcnow_naive()`，时区封装在 core/timeutil.py 内部
适用场景：跨日额度计算、定时任务、去重表 TTL、素材回溯
不适用场景：单次本地时间戳、纯日志时间

### 维度 39：主从表级联清理完整性

**为什么**：删除主表记录（如 workflow）时，必须同步处理所有引用主表 ID 的从表（material/crawler_dedup/script/review/episode）。否则会产生孤儿记录锁死后续流程——例如删除 workflow 后 material 被级联删除但 crawler_dedup 残留，导致爬虫重新爬取时所有 URL 命中 dedup 表，入库 0 条。

检查信号：Grep `delete(Model)` 或 `db.delete(obj)` 后无对从表的 `update`/`delete`
修复建议：删除主表前先 `UPDATE material SET workflow_id=NULL, status='pending'`（保留素材重置状态），并清理 crawler_dedup 中孤儿 URL 记录
适用场景：workflow → material/crawler_dedup/script/review/episode、channel → workflow/material
不适用场景：无外键引用的独立表

### 维度 40：0 结果容错分支

**为什么**：查询返回 0 条不一定是错误。例如 crawler 爬到 0 条新素材时，可能 material 表已有历史 pending 素材可用（rewriter 通过 FALLBACK_DAYS 回溯选取）。直接 `if count == 0: raise` 会导致工作流中断，但实际有可用资源。

检查信号：Grep `if count == 0` 或 `if material_count == 0` 后直接 `raise RuntimeError` 无 fallback 检查
修复建议：0 条新结果时先查询是否有可用历史/回退资源（如 pending 素材），有则放行并记录日志，无才报错
适用场景：爬虫采集、LLM 改写选题、审核队列
不适用场景：必填字段缺失、鉴权失败、配置加载失败

### 维度 41：动态注入而非硬编码条件分支

**为什么**：业务参数（如"结尾思考问题"开关）应通过动态注入 prompt 后缀实现，而不是在模板中硬编码后用 `if config_flag and not template_text` 条件跳过。后者会导致用户自定义模板时配置开关失效——所有频道都有自定义 rewrite_template，`not template_text` 永远为 False，开关被绕过。

检查信号：Grep `if config_flag and not template_text` 或 `if flag and not has_xxx` 多条件跳过逻辑
修复建议：配置开关直接控制后缀追加（`if enable_flag: prompt += suffix`），不依赖模板存在性判断
适用场景：LLM prompt 后缀、字段可选序列化、特性开关
不适用场景：安全相关的硬约束（如必填校验不应被开关绕过）

### 维度 42：选题后关联关系更新

**为什么**：业务流程中选取已有记录（如 rewriter 从 material 表选题改写）后，必须立即 UPDATE 关联字段（`material.workflow_id = 当前工作流 ID`）。否则工作流详情页按 `WHERE workflow_id = 'wf-xxx'` 过滤素材列表时查不到数据——回溯选取的历史素材 workflow_id 为 NULL。

检查信号：Grep `select(Material)` 后无 `update(Material).values(workflow_id=...)`
修复建议：选题后立即执行 `UPDATE material SET workflow_id=当前工作流, status='selected' WHERE id IN (选中ID)`
适用场景：素材选题、任务分配、角色关联
不适用场景：只读查询、一次性临时查询

### 维度 43：blob/二进制响应错误解析

**为什么**：前端 axios 请求设置 `responseType: 'blob'` 时，错误分支 `error.response.data` 也是 Blob 类型，axios 拦截器无法读取 `.message` 字段，前端只能显示 "Network Error"。后端返回的 `{code, message, data}` 结构在 blob 模式下被包装为 Blob，需要 `blob.text()` 解析。

检查信号：前端 grep `responseType: 'blob'` 后无 `parseBlobError` 或 `blob.text()` 调用
修复建议：blob 请求 catch 中先检查 `err.response?.data instanceof Blob`，是则 `await blob.text()` 解析 JSON 获取真实 message
适用场景：文件下载、音频流、图片请求
不适用场景：JSON 响应（默认 responseType）

### 维度 44：频道级配置覆盖全局

**为什么**：业务参数（BGM 路径/音量、段间静音 SEGMENT_GAP_SEC、思考问题开关）应支持频道级覆盖，频道未配置时回退全局 settings。如果只做全局配置，所有频道共享同一参数，无法差异化运营。

检查信号：Grep `settings.BGM_VOLUME` 或 `settings.SEGMENT_GAP_SEC` 在业务代码中无 `if ch.xxx is not None` 频道级检查
修复建议：解析配置时先读全局 settings 作为默认值，再查询频道记录，频道字段非 None 则覆盖
适用场景：多频道/多租户场景的所有可配置参数
不适用场景：全局唯一参数（如数据库路径、JWT 密钥）

### 维度 45：定时任务频道级触发

**为什么**：全局 cron 触发（如每日 05:00）时，必须为所有未配置独立定时的活跃频道各触发一个带 channel_id 的工作流。如果只触发一个无频道的工作流，多频道场景下只有"默认频道"执行定时任务，其他频道被遗漏。

检查信号：Grep `_cron_trigger` 或全局 cron 入口中无遍历活跃频道列表
修复建议：全局 cron 查询所有 `is_active=1 AND schedule_time IS NULL` 的频道，为每个频道各触发一个工作流
适用场景：多频道调度、多租户定时
不适用场景：单频道项目

### 维度 46：ai_budget 预算限流时区

**为什么**：ai_budget 按"日"重置 token 用量，如果用 UTC 日期而项目其他模块用本地时间，会导致本地跨日时额度累加到错误的 UTC 日。例如本地 7-14 23:30 到 7-15 00:30 的 LLM 调用全部累加到 UTC 7-14，超限后整个本地 7-15 无法调用 LLM。

检查信号：Grep ai_budget 模块中 `datetime.now(timezone.utc)` 或 `tz=timezone.utc`
修复建议：ai_budget 的 `_today_key()` 和 timestamp 解析统一使用本地时间 `datetime.now()`
适用场景：所有按日/按时段重置的预算/限流模块
不适用场景：跨时区服务的全局预算（需明确指定 UTC）

### 维度 47：crawler_dedup 孤儿记录清理

**为什么**：crawler_dedup 表通过 URL 去重防止重复爬取。如果 material 表被非标准方式删除（如直接 SQL 操作），crawler_dedup 残留的 URL 锁会永久阻止爬虫重新入库这些 URL。定时清理任务（每日 03:00）除了清理过期记录，还必须清理孤儿记录（url 不在 material 表中的记录）。

检查信号：Grep `_cleanup_crawler_dedup` 中无 `url NOT IN (SELECT url FROM material)` 孤儿清理
修复建议：定时清理任务额外执行 `DELETE FROM crawler_dedup WHERE url NOT IN (SELECT url FROM material)`
适用场景：所有用 dedup 表做去重的爬虫系统
不适用场景：无 dedup 表的爬虫

### 维度 48：音频时长校验容差动态范围

**为什么**：音频拼接的最终时长校验范围如果固定（如 ±15%），LLM 实际生成字数与 ±10% prompt 约束的偏差叠加 TTS 语速波动，容易超出范围导致工作流失败。应改为基于目标时长的动态范围（如 ±20%），允许更大的容差。

检查信号：Grep `_get_duration_range` 或时长校验中固定 `0.85`/`1.15` 而非动态 `0.80`/`1.20`
修复建议：时长校验范围改为动态计算 `target * 0.80` 到 `target * 1.20`，范围系数通过 config.yaml 可配
适用场景：所有音频/视频拼接的时长校验
不适用场景：精确时长要求的场景（如广告片段）

### 维度 49：频道字段迁移与配置页面同步

**为什么**：后端 Channel 模型新增字段（如 segment_gap_sec、enable_thinking_question）时，必须同步：①main.py 迁移脚本添加新列 ②channel_service.py 的 create/update 方法支持新参数 ③routers/admin/channels.py 的 Request/Response 模型包含新字段 ④前端 ChannelManagement.vue 表单包含新控件。任一环节缺失会导致配置无法持久化或前端看不到配置项。

检查信号：Grep Channel 模型新增字段后，channel_service.py/routers/channels.py/ChannelManagement.vue 是否同步更新
修复建议：新增频道字段时按 4 层同步清单（model → migration → service → router → frontend）逐项检查
适用场景：所有频道/租户配置字段的新增
不适用场景：内部字段（不暴露给前端配置）


---

> 以下维度来源于 2026-07-17 后端 API 复盘，覆盖模型字段名验证、统计口径校验、静态资源 URL 配置化等高频故障场景。配置详见 `config.yaml#hard_constraints.rules` 对应条目。

### 维度 50：模型字段名验证（禁止凭记忆假设）

**为什么**：content_service.py 中曾写 `Workflow.workflow_id == workflow_id`，但 Workflow 模型主键字段名是 `id`（comment="workflow_id"），导致查询永远返回 None。凭记忆假设字段名是高频错误源，ORM 字段名必须以模型定义文件为准。

检查信号：
- 代码中出现 `Model.field_name` 但未先 Read 模型定义文件确认
- 查询条件 `where(Model.xxx == value)` 中 xxx 字段名拼写错误
- 字段名有歧义时（如 id vs workflow_id），以模型定义为准，comment 仅作参考

修复建议：
- 编写涉及模型字段访问的代码前，必须先 Read 模型定义文件
- PR review 时，reviewer 必须对照模型源文件验证字段名
- ORM 模型的 `__table__.columns` 是字段名的唯一可信源
适用场景：所有 ORM（SQLAlchemy/Django ORM/Tortoise）
不适用场景：原生 SQL（字段名在 SQL 中可见）

### 维度 51：统计口径校验（聚合查询前确认字段语义）

**为什么**：用户收听统计曾用 `sum(PlayLog.duration)` 计算累计收听时长，但 PlayLog.duration 是节目总时长（每条日志记录节目时长），不是实际收听时长。结果"9 分钟"实际是"9 个节目总时长之和"，严重偏高。应改用 PlayProgress.position（每用户每节目一条 upsert 记录，position 是最后播放位置）。

检查信号：
- 聚合查询 `sum(field)` / `count(field)` 前未确认 field 的语义
- 统计结果与业务预期不符（如"累计收听 9 分钟"但用户只听了 3 分钟）
- 用日志表（PlayLog）做统计而非状态表（PlayProgress）

修复建议：
- 聚合查询前必须确认字段的业务语义
- 日志表（append-only）用于次数/热度统计，状态表（upsert）用于累计/当前值统计
- 统计结果与业务预期偏差 >20% 时必须复核字段语义

**字段语义对照表**：

| 表 | 字段 | 语义 | 适用统计场景 |
|----|------|------|--------------|
| PlayLog | duration | 节目总时长（每条日志） | 播放次数统计、节目热度 |
| PlayLog | position | 播放位置（每条日志） | 历史播放位置追踪 |
| PlayProgress | position | 最后播放位置（upsert 单条） | 累计收听时长、断点续播 |
| PlayProgress | completed | 是否完播（0/1） | 完播率统计 |

适用场景：所有数据库聚合查询、统计接口、报表
不适用场景：单条记录查询（字段语义直接可见）

### 维度 52：静态资源 URL 配置化

**为什么**：后端 _episode_to_dict 曾硬编码 `http://localhost:8000` + audio_url，导致真机测试时小程序播放器访问不到音频（localhost 在手机上指向手机自己）。所有对外 URL 必须通过 settings 配置项管理，禁止硬编码 host。

检查信号：
- Grep `'http://localhost` 或 `'http://127.0.0.1` 硬编码在业务代码（非配置文件、非 .env）
- Grep `audio_url` / `cover_url` 拼接逻辑中含硬编码 host
- 后端 `app.host` 配置为 `127.0.0.1` 但期望真机访问

修复建议：
```python
# 后端：所有对外 URL 通过 settings 配置项管理
from app.config import get_settings

base = get_settings().AUDIO_BASE_URL or 'http://localhost:8000'
audio_url = base + audio_url  # 从配置读取，未配置时回退 localhost
```

环境地址选择规则：

| 场景 | 后端 APP_HOST | AUDIO_BASE_URL |
|------|---------------|----------------|
| 开发者工具调试 | 127.0.0.1 | 留空（回退 localhost） |
| 真机测试 | 0.0.0.0 | http://<电脑局域网IP>:8000 |
| 生产部署 | 0.0.0.0 | https://<公网域名> |

适用场景：小程序 + 后端服务架构、前后端分离项目
不适用场景：纯前端 SPA（无后端）、单机内部工具

### 维度 53：Favorite.user_id 字段类型一致性

**为什么**：Favorite 模型的 user_id 字段存储的是 openid 字符串（历史对齐 SCF/COS），而 User 模型的主键是 int 类型的 id。统计用户收藏数时需要先查 User.openid 再查 Favorite.user_id，直接用 user_id 关联 User.id 会导致类型不匹配查询为空。

检查信号：
- Grep `Favorite.user_id == User.id` 直接关联（类型不匹配）
- Grep 统计收藏数时未先查 User.openid

修复建议：
```python
# 正确：先查 User.openid，再用 openid 查 Favorite
user_result = await db.execute(select(User.openid).where(User.id == user_id))
openid = user_result.scalar_one_or_none()
if openid:
    fav_count = await db.execute(
        select(func.count(Favorite.id)).where(Favorite.user_id == openid)
    )
```

适用场景：历史遗留的 user_id 类型不一致（openid 字符串 vs int id）
不适用场景：新项目统一用 int user_id

---

> 以下维度来源于 2026-07-17 频道级数据隔离修复与 RSS 源端到端验证复盘，覆盖频道级数据隔离、RSS 源配置管理、第三方服务依赖诊断、PowerShell 工具链兼容性等高频故障场景。配置详见 `config.yaml#hard_constraints.rules` 对应条目。

### 维度 54：频道级数据隔离严格性（禁止 OR NULL 兜底）

**为什么**：多频道场景下，专门频道（channel_id 非空）配置了自己的 rss_sources 和 keywords，期望只抓取和消费本频道素材。如果查询时用 `OR channel_id IS NULL` 兜底，当专门频道的 RSS 源全部失败时，会消费 NULL 历史遗留素材（如 36氪/人民网），导致跨频道内容污染——主机游戏频道出现科技资讯，破坏内容专业性。

**检查信号**：
- Grep `OR.*channel_id IS NULL` 或 `or_(.*channel_id.*is_(None))` 在 services/ 或 workflow/ 目录
- Grep `or_\(.*channel_id` 检查是否有 SQLAlchemy `or_` 兜底逻辑
- Grep `or_` 导入但未使用（修复后未清理 import 残留）

**修复建议**：
```python
# ❌ 反模式：专门频道 OR NULL 兜底，导致跨频道污染
stmt = select(Material).where(
    Material.status == 'pending',
    or_(
        Material.channel_id == channel_id,
        Material.channel_id.is_(None),  # 历史遗留 NULL 素材
    )
)

# ✅ 正确：专门频道严格过滤，NULL 仅全局工作流可用
if channel_id is not None:
    stmt = select(Material).where(
        Material.status == 'pending',
        Material.channel_id == channel_id,  # 严格过滤，无兜底
    )
else:
    stmt = select(Material).where(
        Material.status == 'pending',
        Material.channel_id.is_(None),  # 全局工作流仅查 NULL
    )
```

**crawler 0-count 检查同步**：
```python
# ❌ 反模式：crawler 0 条时 OR NULL 兜底
count = await db.scalar(select(func.count(Material.id)).where(
    Material.channel_id == channel_id
))
if count == 0:
    # 回退查 NULL 素材 → 跨频道污染
    count = await db.scalar(select(func.count(Material.id)).where(
        or_(Material.channel_id == channel_id, Material.channel_id.is_(None))
    ))

# ✅ 正确：专门频道 0 条时显式报错，不兜底
if count == 0 and channel_id is not None:
    raise RuntimeError(f"频道 {channel_id} 无可用素材，请检查 RSS 源配置")
```

适用场景：多频道/多租户数据隔离系统、专门频道（如主机游戏/科技/财经）内容隔离
不适用场景：单频道系统（无 channel_id 字段）、全局工作流（channel_id=None）

### 维度 55：RSS 源配置与频道数据同步

**为什么**：rss.yaml 中的源 name 变更后，数据库 `channel.rss_sources`（JSON 数组）字段仍存储旧 name，导致 crawler 按 name 匹配时找不到源，返回 0 条素材。这是配置文件与数据库不同步的典型问题。同时，rss.yaml 新增源后未更新频道配置，导致新源不被任何频道使用。

**检查信号**：
- Grep rss.yaml 中源 name 变更记录，检查是否有数据库同步脚本调用
- Grep `channel.rss_sources` 读取逻辑，检查是否对 name 做了有效性校验（如 name 在 rss.yaml 中存在）
- Grep 数据库 `channel.rss_sources` JSON 数组中的 name，与 rss.yaml 比对

**修复建议**：
```python
# 配置同步脚本：读取 rss.yaml，更新所有频道的 rss_sources
# python -m app.scripts.sync_rss_sources
import json
from app.workflow.crawler.sources.rss_loader import load_rss_sources

def sync_channel_rss_sources(db_session):
    """同步 rss.yaml 与数据库 channel.rss_sources"""
    yaml_sources = load_rss_sources()
    yaml_names = {s['name'] for s in yaml_sources}

    channels = db_session.execute(select(Channel)).scalars().all()
    for ch in channels:
        if not ch.rss_sources:
            continue
        current_names = set(json.loads(ch.rss_sources))
        # 过滤掉 rss.yaml 中已不存在的 name
        valid_names = current_names & yaml_names
        if valid_names != current_names:
            ch.rss_sources = json.dumps(sorted(valid_names))
            logger.warning(f"频道 {ch.id} rss_sources 已同步：移除 {current_names - valid_names}")
    db_session.commit()
```

适用场景：频道级 RSS 源配置管理、rss.yaml 变更后数据库同步
不适用场景：全局 RSS 源（不按频道隔离）

### 维度 56：第三方转换服务依赖诊断

**为什么**：第三方 RSS 转换服务（rsshub.app、plink.anyfeeder.com）作为中间层，引入额外故障点：(1) DNS 污染（rsshub.app 在大陆被 DNS 污染 + TCP 阻断）；(2) 会话级限流（plink 并发≥5 时部分源返回 0 条目）；(3) 微信公众号封禁（plink 源返回 404）。代码中如果直接依赖第三方服务而不做诊断，故障时难以定位根因。

**检查信号**：
- Grep rss.yaml 中源 URL 含 `rsshub.app`，未标注"第三方转换，有限流风险"
- Grep crawler 抓取逻辑，无第三方服务故障诊断（如 DNS 解析失败、TCP 连接超时、HTTP 404 分类）
- Grep feedparser 解析结果为 0 条目时，未检查响应内容类型（Content-Type）和前 200 字符

**修复建议**：
```python
# RSS 源配置规范：第三方转换服务必须标注
# rss.yaml
- name: 少数派
  url: https://plink.anyfeeder.com/sspai
  category: 科技
  # 第三方转换服务，有限流风险，并发验证时需串行间隔≥3s

# crawler 故障诊断：HTTP 200 但 0 条目需分类
async def fetch_with_diagnosis(url: str) -> list:
    try:
        resp = await client.get(url, timeout=10)
        if resp.status_code == 200:
            content_type = resp.headers.get('content-type', '')
            if 'text/html' in content_type:
                logger.warning(f"{url} 返回 HTML 而非 RSS，站点可能未提供 RSS")
                return []
            # feedparser 解析
            feed = feedparser.parse(resp.text)
            if len(feed.entries) == 0:
                logger.warning(f"{url} HTTP 200 但 0 条目，可能限流或源被封禁")
            return feed.entries
        elif resp.status_code == 404:
            logger.error(f"{url} 404，第三方转换服务源可能被封禁")
            return []
    except httpx.ConnectError as e:
        logger.error(f"{url} 连接失败，可能 DNS 污染或 TCP 阻断: {e}")
        return []
    except httpx.TimeoutException:
        logger.error(f"{url} 超时，可能网络问题或服务不可达")
        return []
```

适用场景：依赖第三方转换服务（rsshub/plink 等）的 RSS 抓取系统、爬虫数据源管理
不适用场景：原生 RSS 源（无第三方依赖）、内部 API（无 DNS/限流问题）

### 维度 57：PowerShell Python 脚本调用兼容性

**为什么**：PowerShell 调用 Python 脚本时，stdout 默认是块缓冲（非行缓冲）。脚本输出在缓冲区满或脚本退出前不可见，导致长时间运行的脚本看起来"卡住"。同时 Python 的 logger.error 写入 stderr，PowerShell 会包装为 RemoteException 警告，但脚本继续执行。开发者可能误判脚本失败而中断。

**检查信号**：
- Grep 项目脚本（.ps1）中 `python script.py`（无 -u 参数）
- Grep 项目脚本中 `python script.py` 后无 `2>&1` 重定向
- Grep 项目脚本中因 RemoteException 警告而 `exit 1` 的逻辑（logger.error 是正常日志，不应中断）

**修复建议**：
```powershell
# ❌ 反模式：stdout 缓冲导致输出不可见
python _verify_rss.py

# ❌ 反模式：stderr 未捕获，logger.error 输出丢失
python -u _verify_rss.py

# ✅ 正确：-u 禁用缓冲 + 2>&1 捕获 stderr
python -u _verify_rss.py 2>&1

# ✅ 正确：区分 logger.error（正常日志）和真实异常
python -u _verify_rss.py 2>&1 | ForEach-Object {
    if ($_ -match '^ERROR') {
        Write-Host $_ -ForegroundColor Yellow  # logger.error 正常输出
    } elseif ($_ -match 'RemoteException') {
        Write-Host $_ -ForegroundColor Yellow  # PowerShell 包装的 stderr
    } else {
        Write-Host $_
    }
}
```

适用场景：Windows + PowerShell + Python 工具链、验证脚本、运维脚本
不适用场景：bash/zsh（默认行缓冲）、IDE 内运行（IDE 处理缓冲）、生产服务（不通过 PowerShell 调用）

### 维度 58：RSS 源可达性验证流程规范

**为什么**：RSS 源可达性验证时，HTTP 200 但 0 条目不一定是 RSS 格式问题。可能原因：(1) 站点返回 HTML 页面（非 RSS）；(2) WAF 拦截；(3) 第三方转换服务限流；(4) 微信公众号被封禁；(5) UA 被拒绝（如 Steam 拒绝 bot UA）。直接判定"RSS 格式错误"会误导修复方向，浪费排查时间。

**检查信号**：
- Grep 验证脚本中 feedparser 返回 0 条目时直接标记"失效"，未检查响应内容类型
- Grep crawler 中 UA 配置，检查是否使用了 bot UA（如 `MorningBriefBot`）访问拒绝 bot 的站点
- Grep 验证脚本中使用 `asyncio.gather` 并发测试第三方转换服务（限流假阳性）

**修复建议**：
```python
# RSS 源可达性诊断流程
async def diagnose_rss_source(url: str, ua: str = None) -> dict:
    """诊断 RSS 源可达性，返回分类结果"""
    headers = {'User-Agent': ua or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    try:
        resp = await client.get(url, headers=headers, timeout=10, follow_redirects=True)
    except httpx.ConnectError:
        return {'status': 'dns_error', 'reason': 'DNS 解析失败或 TCP 阻断'}
    except httpx.TimeoutException:
        return {'status': 'timeout', 'reason': '连接超时'}

    if resp.status_code == 404:
        return {'status': 'not_found', 'reason': '源被封禁或路径错误'}
    if resp.status_code == 403:
        return {'status': 'forbidden', 'reason': 'WAF 拦截或 UA 被拒绝'}

    if resp.status_code == 200:
        content_type = resp.headers.get('content-type', '')
        if 'text/html' in content_type:
            return {'status': 'not_rss', 'reason': '站点返回 HTML 而非 RSS'}

        feed = feedparser.parse(resp.text)
        if len(feed.entries) == 0:
            # HTTP 200 + 0 条目：可能是限流，需串行复测
            return {'status': 'zero_entries', 'reason': '可能限流或源被封禁，需串行复测'}

        return {'status': 'ok', 'reason': f'可达，{len(feed.entries)} 条目'}

    return {'status': 'http_error', 'reason': f'HTTP {resp.status_code}'}

# 验证脚本必须串行执行第三方转换服务（避免限流假阳性）
async def verify_sources_serially(sources: list, interval_sec: float = 3.0):
    """串行验证 RSS 源，间隔≥3s 避免第三方服务限流"""
    results = []
    for src in sources:
        result = await diagnose_rss_source(src['url'])
        results.append({**src, **result})
        await asyncio.sleep(interval_sec)  # 强制间隔
    return results
```

**UA 兼容性检查**：
部分站点（如 Steam）拒绝 bot UA，需用浏览器 UA：
```python
# crawler UA 配置应可切换
CRAWLER_UA = settings.CRAWLER_USER_AGENT or 'Mozilla/5.0 ...'  # 浏览器 UA 作为默认
# Steam 等站点需浏览器 UA，bot UA（如 MorningBriefBot）会被拒绝
```

适用场景：所有 RSS 抓取系统、爬虫数据源验证、第三方转换服务依赖诊断
不适用场景：API 接口验证（JSON 响应）、内部服务（无 DNS/限流问题）

---

> 以下维度来源于 2026-07-17 编码规范 45-48 补充，覆盖模板字符串花括号转义、API Key 脱敏值回传、第三方服务错误码可读化映射、Settings 字段四端同步等高频故障场景。配置详见 `config.yaml#review_dimensions` 对应条目（RD-16 ~ RD-19）。

### 维度 59：模板字符串字面花括号转义（对应编码规范 45，RD-16）

**为什么**：Python `str.format()` 模板中，`{xxx}` 会被当作占位符尝试用 `format()` 参数替换。如果模板内容本身需要输出字面花括号（如 SQL JSON 函数 `JSON_EXTRACT(data, '$.{field}')`、HTTP 响应体示例 `{"code": 0}`），未转义的字面 `{xxx}` 会触发 `KeyError` 或 `IndexError`，导致服务崩溃。字面花括号必须双写转义为 `{{xxx}}`，`format()` 才会输出单层 `{xxx}`。

**判断信号**（grep 模式，见 `config.yaml#review_dimensions[RD-16].rules[0].grep_pattern`）：
- Grep `\.format\(.*\{[a-z_]+\}` 定位 `.format()` 调用附近含 `{xxx}` 字面占位符的字符串
- 误报提示：模板中的 `{name}` `{description}` 若是 format 参数则不算违规（见 `false_positive_hints`）

**违规示例**：
```python
# ❌ 错误：字面 {field} 未转义，format() 尝试替换触发 KeyError
template = "JSON_EXTRACT(data, '$.{field}')".format(field=col)
# ❌ 错误：字面 {code} 未转义
body = '{"code": 0}'.format(code=0)
```

**合规示例**：
```python
# ✅ 正确：字面花括号双写转义 {{field}}，format() 输出单层 {field}
template = "JSON_EXTRACT(data, '$.{{field}}')".format(field=col)
# ✅ 正确：字面花括号双写转义
body = '{{"code": 0}}'.format()
```

**修复建议**：所有走 `str.format()` 的模板字符串中，凡是需要原样输出 `{` `}` 的位置，一律双写为 `{{` `}}`；若模板无需任何参数替换，改用普通字符串而非 `.format()`。

适用场景：所有使用 `str.format()` / `.format_map()` 的 Python 字符串模板
不适用场景：f-string（`f"{var}"` 本身就是占位符）、`string.Template`（用 `$var` 语法）

### 维度 60：API Key 脱敏值回传检测（对应编码规范 46，RD-17）

**为什么**：前端展示已保存的密钥时通常会脱敏为 `****xxxx`（仅保留后 4 位）。用户在未修改密钥的情况下点击"测试连接"时，前端会把脱敏值原样回传后端。如果后端 `test_xxx_connection(api_key=...)` 直接用脱敏值调用第三方 API，必然鉴权失败，用户误以为密钥错误。后端必须判断入参是否为脱敏值，若是则回退到已持久化的真实密钥。

**判断信号**（grep 模式，见 `config.yaml#review_dimensions[RD-17].rules[0].grep_pattern`）：
- Grep `def test_.*_connection.*api_key` 定位测试连接函数
- 检查函数体内是否调用 `_is_masked(api_key)` 或类似脱敏值判断，若否则违规

**违规示例**：
```python
# ❌ 错误：直接用前端回传的脱敏值调用第三方 API，鉴权失败
async def test_tts_connection(api_key: str) -> bool:
    client = TTSClient(api_key=api_key)  # api_key 可能是 ****xxxx
    return await client.ping()
```

**合规示例**：
```python
# ✅ 正确：判断脱敏值，回退到已保存的真实密钥
async def test_tts_connection(api_key: str, config_id: int) -> bool:
    if _is_masked(api_key):
        # 前端回传的是脱敏值，回退到数据库已保存的真实密钥
        api_key = await _load_saved_api_key(config_id)
    client = TTSClient(api_key=api_key)
    return await client.ping()
```

**修复建议**：所有接收前端密钥字段的测试连接 / 保存接口，必须先 `_is_masked()` 判断，脱敏值则从数据库回退到真实值；`_is_masked` 实现须可泛化（匹配 `****` 前缀 + 任意后缀），不绑定具体服务商。

适用场景：所有接收前端回传密钥的后端测试连接 / 校验接口
不适用场景：首次录入密钥（前端必传真实值，无需回退）

### 维度 61：第三方服务错误码可读化映射（对应编码规范 47，RD-18）

**为什么**：第三方服务（阿里云 NLS / OpenAI / DeepSeek 等）返回的错误码是裸字符串或数字（如 `NlsHttp400`、`invalid_api_key`、`40001`），直接抛给前端用户无法理解，运营无法定位问题。后端必须维护 `ERROR_CODE_HINTS` 映射表，将第三方错误码转换为可读中文提示，未命中映射时回退到通用提示并记录原始错误码日志。

**判断信号**（grep 模式，见 `config.yaml#review_dimensions[RD-18].rules[0].grep_pattern`）：
- Grep `error_code.*data\.get\("error_code"\)` 定位直接透传第三方错误码的位置
- 检查同模块是否存在 `ERROR_CODE_HINTS` 映射表，若否则违规

**违规示例**：
```python
# ❌ 错误：直接透传第三方错误码，前端用户无法理解
async def call_tts(payload):
    data = await client.post(...)
    if data.get("error_code"):
        raise BizError(f"TTS 失败：{data.get('error_code')}")  # 裸码 NlsHttp400
```

**合规示例**：
```python
# ✅ 正确：维护 ERROR_CODE_HINTS 映射表，转换为可读中文提示
ERROR_CODE_HINTS = {
    "NlsHttp400": "阿里云 NLS 请求参数错误，请检查 AppKey / Token",
    "NlsAuthFailed": "阿里云 NLS 鉴权失败，请检查 AccessKey",
    "invalid_api_key": "OpenAI API Key 无效，请重新填写",
}

async def call_tts(payload):
    data = await client.post(...)
    code = data.get("error_code")
    if code:
        hint = ERROR_CODE_HINTS.get(code, "第三方服务调用失败")
        logger.warning("第三方服务错误码: %s", code)  # 记录原始码便于排查
        raise BizError(f"{hint}（错误码：{code}）")
```

**修复建议**：每接入一个第三方服务必须同步建立 `ERROR_CODE_HINTS` 字典；映射表须配置驱动（落在 `config.yaml` 或服务模块顶部常量），禁止散落在业务分支；未命中映射时记录原始错误码日志并回退通用提示。

适用场景：所有调用第三方 API（LLM / TTS / COS / 短信 / OCR 等）的后端服务
不适用场景：内部模块错误码（已在业务异常体系中定义）

### 维度 62：Settings 字段四端同步（对应编码规范 48，RD-19）

**为什么**：新增配置项时，`Settings` 类（`core/config.py`）、ORM 模型（`models/`）、前端表单字段、服务层 `CONFIG_KEY_MAP` 必须同步。任一端缺失会导致：①`setattr(settings, xxx, value)` 写入未定义属性 → Pydantic Settings 校验失败或静默丢弃；②`CONFIG_KEY_MAP` 值指向不存在的 Settings 属性 → 配置无法生效；③前端表单字段名与 Settings 属性不一致 → 保存的值被忽略。这与维度 17 / 28（配置键一致性）互补，本维度聚焦"新增配置时四端同步"的增量检查。

**判断信号**（grep 模式，见 `config.yaml#review_dimensions[RD-19].rules`）：
- Grep `setattr\(settings,` 定位动态写入 settings 的位置，检查第二参数是否在 `Settings` 类中定义（规则 R-48-1）
- Grep `CONFIG_KEY_MAP` 定位配置键映射表，检查所有值（Settings 属性名）是否在 `Settings` 类中存在（规则 R-48-2）

**违规示例**：
```python
# ❌ 错误：setattr 写入 Settings 类未定义的属性，Pydantic 静默丢弃
setattr(settings, "tts_volume_new", value)  # Settings 类无 tts_volume_new 字段

# ❌ 错误：CONFIG_KEY_MAP 值指向不存在的 Settings 属性
CONFIG_KEY_MAP = {
    "tts_volume": "tts_vol",  # Settings 类无 tts_vol，应为 tts_volume
}
```

**合规示例**：
```python
# ✅ 正确：Settings 类先定义字段，再被 setattr / CONFIG_KEY_MAP 引用
class Settings(BaseSettings):
    tts_volume: float = 0.8  # 先在 Settings 类定义

# setattr 引用的属性已在 Settings 类定义
setattr(settings, "tts_volume", value)

# CONFIG_KEY_MAP 值与 Settings 属性名一致
CONFIG_KEY_MAP = {
    "tts_volume": "tts_volume",  # 与 Settings.tts_volume 一致
}
```

**修复建议**：新增配置项时按四端同步清单逐项检查：①`Settings` 类定义字段 ②ORM 模型 / 配置表新增列 ③前端表单新增控件且字段名与 Settings 属性一致 ④服务层 `CONFIG_KEY_MAP` 新增映射且值指向已定义的 Settings 属性。PR review 时 reviewer 必须对照 `Settings` 类源文件验证 `setattr` 与 `CONFIG_KEY_MAP` 引用的属性存在。

适用场景：所有动态写入 settings 的配置管理接口、所有维护 CONFIG_KEY_MAP 的服务层
不适用场景：只读配置（不涉及 setattr / CONFIG_KEY_MAP）


---

> 以下维度来源于 2026-07-17 数据库维护 + 系统清理模块开发复盘。配置详见 `config.yaml#hard_constraints.rules`。

### 维度 63：SQLAlchemy Inspector run_sync 陷阱（对应编码规范 56）

**为什么**：`run_sync` 回调参数是 Session 而非 Connection，`inspect()` 需要 Connection。直接传 Session 会报错或返回不完整。

**检查信号**：Grep `run_sync` + `inspect(` 检查回调内是否有 `.connection()` 转换

适用场景：动态表结构反射、数据库维护模块
不适用场景：已知表结构（应直接用 ORM 模型）

### 维度 64：main.py 导入完整性（对应编码规范 57）

**为什么**：main.py 使用了 `RequestIdMiddleware`/`setup_logging` 等符号但未导入，启动时 NameError 崩溃。

**检查信号**：Grep main.py 中使用的符号是否都有对应 import；预检 `python -c "from app.main import app"`

适用场景：所有应用入口文件
不适用场景：模块内部文件

### 维度 65：CONFIRM_DELETE 令牌双重确认（对应编码规范 58）

**为什么**：危险操作不可逆，仅靠按钮确认不够安全，必须输入令牌字符串。令牌通过配置文件管理。

**检查信号**：Grep 危险操作端点是否检查 `confirm_token`；比较应用 `hmac.compare_digest`

适用场景：所有危险操作（删表/清空/VACUUM/DROP）
不适用场景：普通增删改查

### 维度 66：敏感字段动态脱敏（对应编码规范 59）

**为什么**：仅静态字段名匹配无法覆盖动态表（如 `ai_config.config_value`），必须同时用字段名模式匹配。

**检查信号**：Grep 导出函数脱敏逻辑是否仅静态字段名匹配

适用场景：表数据导出、数据库维护
不适用场景：内部数据传输

### 维度 67：应用层级联删除策略（对应编码规范 60）

**为什么**：数据库级 CASCADE 不够灵活，应用层级联可精细控制 cascade + set_null。

**检查信号**：Grep `db.execute(delete(Model))` 后是否有对从表的处理逻辑

适用场景：需要精细控制级联策略、SQLite
不适用场景：简单外键关系（可用数据库级 CASCADE）

### 维度 68：VACUUM AUTOCOMMIT 模式（对应编码规范 61）

**为什么**：VACUUM 不能在事务内执行，会报 `OperationalError: cannot VACUUM from within a transaction`。

**检查信号**：Grep `VACUUM` 是否在事务块内；检查是否设置 AUTOCOMMIT 隔离级别

适用场景：SQLite 压缩、系统清理
不适用场景：MySQL（用 OPTIMIZE TABLE）

### 维度 69：bindparam expanding IN 列表（对应编码规范 62）

**为什么**：IN 查询字符串拼接有 SQL 注入风险，必须用 `bindparam(expanding=True)`。

**检查信号**：Grep `IN (` 后跟字符串拼接；Grep `','.join(ids)` 用于 IN 查询

适用场景：所有 IN 查询参数化
不适用场景：固定列表 IN 查询

### 维度 70：数据库维护白名单机制（对应编码规范 63）

**为什么**：允许操作所有表可能误操作系统表，必须维护白名单，通过配置文件管理。

**检查信号**：Grep 表操作是否检查白名单；白名单是否硬编码

适用场景：数据库管理后台
不适用场景：ORM 模型直接操作

### 维度 71：dry_run 预览模式（对应编码规范 64）

**为什么**：清理/删除操作不可逆，用户需要先预览将要清理的内容。

**检查信号**：Grep 清理函数是否支持 `dry_run` 参数

适用场景：清理/删除类操作
不适用场景：普通增删改查

### 维度 72：审计日志完整覆盖（对应编码规范 65）

**为什么**：数据库维护和清理操作需要可追溯，审计日志记录操作类型/表名/记录ID/操作人/时间。

**检查信号**：Grep `db.delete` 后是否有 `audit_log` 记录

适用场景：所有 DML 操作和清理操作
不适用场景：查询操作（SELECT 不需要审计）
> 以下维度来源于 2026-07-18 SonarQube MCP 扫描 + 问题修复迭代闭环（23 个 OPEN 问题→0）复盘，对应 news-code-dev 编码规范 S51-S60 和元规范 R66-R75。所有阈值通过 config.yaml#sonarqube_checklist 管理。

### 维度 73：认知复杂度治理（对应 news-code-dev S51/R66）

- 【强制】函数 cognitive_complexity ≤ `sonarqube_checklist.complexity.max_cognitive_complexity`（默认 15，与 SonarQube 一致）
- 【强制】函数行数 ≤ `sonarqube_checklist.complexity.max_function_lines`（默认 50）
- 【强制】嵌套层级 ≤ `sonarqube_checklist.complexity.max_nesting`（默认 3）
- 超阈值必须抽取辅助函数（`_validate_xxx` / `_build_xxx`）或重构为数据驱动（见维度 79）

**判断信号**：
- grep `^    if` 在同一函数内连续出现 4 次以上
- ruff `C901` 警告
- SonarQube `cognitive_complexity` issue
- 函数行数 >50 且含 ≥3 层嵌套

**严重级别**：阻塞（critical）

**修复建议**：抽取辅助函数或重构为数据驱动（`list[tuple]` + 循环）

**示例**：
```python
# ❌ 反模式：嵌套 if/elif 链导致复杂度超标
async def create_tunnel(config: dict) -> Tunnel:
    if config.get('provider') == 'ngrok':
        if config.get('token'):
            if config.get('port'):
                # 3 层嵌套...
                pass

# ✅ 正确：抽取辅助函数
def _validate_tunnel_config(config: dict) -> list[str]:
    errors = []
    if not config.get('provider'):
        errors.append('provider required')
    return errors

async def create_tunnel(config: dict) -> Tunnel:
    errors = _validate_tunnel_config(config)
    if errors:
        raise ValidationError(errors)
```

### 维度 74：async/await 语义验证（对应 news-code-dev S52/R67，SonarQube S7503）

- 【强制】`async def` 函数体内必须至少有一个 `await` 表达式
- 无 await 的 async 函数必须转为同步函数（去除 async 关键字）
- 例外：事件回调、`asyncio.create_task` 包装的 fire-and-forget 任务（需注释说明）

**判断信号**：
- grep `async def` 后 50 行内无 `await` 关键字
- SonarQube S7503 issue

**严重级别**：阻塞

**修复建议**：
```python
# ❌ 错误：async 无 await
async def mask_secret(value: str) -> str:
    return value[:4] + '*' * (len(value) - 8) + value[-4:]

# ✅ 正确：转同步函数
def mask_secret(value: str) -> str:
    return value[:4] + '*' * (len(value) - 8) + value[-4:]

# ✅ 或补充 await（如确有异步操作）
async def fetch_secret(key: str) -> str:
    value = await cache.get(key)
    return mask_secret(value)
```

### 维度 75：正则表达式优化（对应 news-code-dev S53/R68，SonarQube S6395）

- 【强制】正则表达式中未使用的捕获组必须改为非捕获组 `(?:...)`
- 仅保留需 `group(N)` 提取的捕获组
- 验证：`re.match`/`re.sub`/`re.compile` 中含 `(...)` 但后续无 `group(N)` 提取 → 违规

**判断信号**：
- grep `re\.(match|sub|compile).*\([^)]*\([^)]*\)` 后无 `group(`
- SonarQube S6395 issue

**严重级别**：警告

**修复建议**：将 `(xxx)` 改为 `(?:xxx)`

### 维度 76：list() 调用必要性检测（对应 news-code-dev S54/R69，SonarQube S7504）

- 【警告】`list(iterable)` 仅在需要索引访问或多次迭代时使用
- 单一 `for` 循环直接迭代可迭代对象，去掉 list() 包装
- 例外：迭代中修改 dict 需先转 list 避免运行时错误

**判断信号**：
- grep `for \w+ in list\(` 模式
- SonarQube S7504 issue

**严重级别**：警告

**修复建议**：去掉多余的 list() 转换

### 维度 77：未使用变量/参数检测（对应 news-code-dev S55/R70，SonarQube S1481）

- 【强制】变量、参数声明后必须使用
- 【强制】协议要求的接口参数需用 `_unused_param` 前缀
- 例外：抽象基类、`__all__` 导出列表

**判断信号**：
- ruff F841（未使用变量）
- pylint W0612（未使用参数）
- SonarQube S1481 issue

**严重级别**：阻塞

**修复建议**：直接删除未使用声明

### 维度 78：未使用导入检测（对应 news-code-dev S55/R70，SonarQube S1128）

- 【强制】import 语句后必须使用
- 【强制】import 语句分三组（标准库→第三方库→项目内），每组字母序（详见维度 72/S3863）

**判断信号**：
- ruff F401（未使用导入）
- pylint W0611
- SonarQube S1128 issue

**严重级别**：警告

**修复建议**：删除未使用 import

### 维度 79：数据驱动重构建议（对应 news-code-dev S56/R71）

- 【建议】同一函数内 ≥ `sonarqube_checklist.data_driven_refactor.min_elif_count`（默认 3）个 elif 判断同一变量时，重构为 `list[tuple]` + 循环
- 修复后复杂度自动下降，且新增分支只需追加 tuple

**判断信号**：
- 同一函数内 ≥3 个 `elif` 判断同一变量
- 函数行数 >50 且含 ≥3 个 elif
- grep `elif \w+ ==` 在同一函数内出现 3 次以上

**严重级别**：建议

**修复建议**：重构为 `RULES: list[tuple[str, Callable]]` + for 循环

**示例**：
```python
# ❌ 反模式：5 个 elif 判断 provider
def create_tunnel(provider: str, config: dict) -> Tunnel:
    if provider == 'ngrok':
        return create_ngrok_tunnel(config)
    elif provider == 'cloudflare':
        return create_cloudflare_tunnel(config)
    # ... 3 more elif

# ✅ 正确：数据驱动重构
PROVIDER_HANDLERS: list[tuple[str, Callable]] = [
    ('ngrok', create_ngrok_tunnel),
    ('cloudflare', create_cloudflare_tunnel),
]
def create_tunnel(provider: str, config: dict) -> Tunnel:
    for name, handler in PROVIDER_HANDLERS:
        if provider == name:
            return handler(config)
    raise ValueError(f'Unknown provider: {provider}')
```

### 维度 80：空 except 块检测（对应 news-code-dev S59/R74，SonarQube S2486）

- 【强制】except 块禁止为空或仅 `pass`
- 必须包含 logger.exception/warning 或显式注释说明为何忽略异常
- 例外：协议要求的静默失败需注释说明（如 `# noqa: intended-empty`）

**判断信号**：
- grep `except[\s\w]*:[\s\n]{1,3}pass`
- grep `except[\s\w]*:[\s\n]{1,3}\}`
- SonarQube S2486 issue

**严重级别**：警告

**修复建议**：添加 logger.exception 或显式注释

**示例**：
```python
# ❌ 反模式：空 except 块
try:
    risky_operation()
except Exception:
    pass  # 异常被吞，问题无法排查

# ✅ 正确：记录日志
try:
    risky_operation()
except Exception as e:
    logger.exception(f'Failed to risky operation: {e}')

# ✅ 正确：显式注释（仅限确知可忽略）
try:
    cache.clear()
except Exception:
    pass  # 缓存清理失败不影响主流程，下次启动会自动重建
```

## SonarQube 规则号交叉引用表

| SonarQube 规则 | 审查维度 | news-code-dev 规范 | news-code-dev 元规范 | 严重级别 | 修复建议 |
|---------------|---------|-------------------|---------------------|---------|----------|
| S7503 | 维度 74 | S52 | R67 | 阻塞 | 转同步函数或补充 await |
| S6395 | 维度 75 | S53 | R68 | 警告 | 改用非捕获组 `(?:...)` |
| S7504 | 维度 76 | S54 | R69 | 警告 | 去掉多余 list() 转换 |
| S1481 | 维度 77 | S55 | R70 | 阻塞 | 删除未使用变量/参数 |
| S1128 | 维度 78 | S55 | R70 | 警告 | 删除未使用导入 |
| S2486 | 维度 80 | S59 | R74 | 警告 | 添加日志或注释 |
| cognitive_complexity | 维度 73 | S51 | R66 | 阻塞 | 抽取辅助函数或数据驱动重构 |
| - | 维度 79 | S56 | R71 | 建议 | 重构为 list[tuple] + 循环 |
> 以下维度来源于 2026-07-20 微信小程序「今日要闻」迭代修复完整复盘，对应 news-code-dev 编码规范 S70 和元规范 R85。所有阈值通过 `config.yaml#cache_versioning`、`config.yaml#segments_data_completeness`、`config.yaml#response_field_priority` 配置管理。

### 维度 81：数据结构变更时 cache_key 版本后缀（对应 news-code-dev S70/R85）

- 【强制】当缓存的数据结构发生变更（新增/删除/重命名字段、嵌套结构调整）时，cache_key 必须追加版本后缀（如 `:v2`、`:_v3`），禁止沿用旧 key
- 【强制】版本号从 2 开始（v1 隐含为初版），每次结构变更必须 bump 一次版本
- 【强制】版本号变更后必须在代码注释中说明本次变更的字段（如 `# v2: 新增 cover_url 字段`）
- 【推荐】版本后缀格式通过 `config.yaml#cache_versioning.version_suffix_format` 配置（默认 `:v{n}`）
- 配置节点：`config.yaml#cache_versioning`

**判断信号**：
- grep `cache_key\s*=\s*f["'].*:\{` 使用变量插值但无版本字段
- grep `cache_key\s*=\s*f["']script:detail:` 无 `:v\d+` 后缀
- 数据结构新增字段（如 segments 新增 `cover_url`）后 cache_key 未变更
- 字段重命名（如 `category` → `categories`）后 cache_key 未变更

**严重级别**：HIGH（旧缓存命中导致字段缺失或类型错误，前端显示空白）

**修复建议**：
```python
# ✅ 正确：数据结构变更时 bump 版本
# v1: segments = [{"seq": 1, "title": "..."}]
# v2: segments = [{"seq": 1, "title": "...", "cover_url": "..."}]  → 加 v2
cache_key = f"script:detail:v2:{episode_id}"  # v2 失效旧缓存
# 注释说明：v2 新增 cover_url 字段

# ❌ 错误：沿用旧 key，旧缓存命中导致 cover_url 缺失
cache_key = f"script:detail:{episode_id}"  # 旧缓存无 cover_url 字段
```

**示例（content_service.py）**：
```python
# 维度 81 检测点：cache_key 必须含版本号
cache_key = f"script:detail:v2:{episode_id}"  # ✅
# cache_key = f"script:detail:{episode_id}"  # ❌ 无版本号

# 版本变更说明（推荐）：
# v1: 初版 segments 结构
# v2: 2026-07-20 新增 cover_url 字段（material.cover_url 注入）
# v3: 待定（下次结构变更时 bump）
```

### 维度 82：segments 数据完整性注入（对应 news-code-dev S70/R85 关联）

- 【强制】后端返回 segments 时必须注入关联资源字段（如 `cover_url`、`source`、`category`），不能仅返回 segment 自身字段
- 【强制】segment 的 `cover_url` 必须从关联的 `material_ids` 中取第一个有 `cover_url` 的 material 注入
- 【强制】material_ids 为空或所有 material 都无 cover_url 时，segment 不强加 `cover_url` 字段（前端按 undefined 处理）
- 【推荐】注入字段列表通过 `config.yaml#segments_data_completeness.inject_fields` 配置
- 配置节点：`config.yaml#segments_data_completeness`

**判断信号**：
- grep `segments\.append\(` 在 content_service.py 中无 `cover_url` 注入
- grep `enriched_seg\s*=\s*dict\(seg\)` 后无 `if seg_cover:` 注入逻辑
- API 返回的 segments 字段缺失前端期望的 `cover_url`/`source`/`category`

**严重级别**：HIGH（前端文稿图片不显示）

**修复建议**：
```python
# ✅ 正确：遍历 segments 注入关联资源字段
enriched_segments = []
for seg in segments:
    if not isinstance(seg, dict):
        enriched_segments.append(seg)
        continue
    seq = seg.get("seq")
    material_ids = seg.get("material_ids") or []
    seg_cover = None
    for mid in material_ids:
        mat = materials_map.get(mid)
        if mat:
            sources.append({
                "seq": seq, "title": mat.title, "url": mat.url,
                "category": mat.category, "source": mat.source,
                "cover_url": mat.cover_url,
            })
            if not seg_cover and mat.cover_url:
                seg_cover = mat.cover_url  # 取第一个有 cover_url 的 material
    enriched_seg = dict(seg)
    if seg_cover:
        enriched_seg["cover_url"] = seg_cover  # 注入到 segment
    enriched_segments.append(enriched_seg)

# ❌ 错误：仅返回 segment 自身字段
enriched_segments = list(segments)  # 无 cover_url 注入
```

### 维度 83：响应字段优先级与背景图设置（对应 news-code-dev S68/R83 关联）

- 【强制】API 响应中应包含可用的背景图字段（如 `cover_url`），供前端在列表/详情页通用展示
- 【强制】`episode` 对象的 `cover_url` 字段必须从 `cover_url`（节目级）→ `channel.cover_url`（频道级）→ 默认值 优先级取值
- 【强制】禁止仅在加载详情时设置 `cover_url`（如 `onLoadScript`），应在 `loadDetail` 中即设置
- 【推荐】优先级链通过 `config.yaml#response_field_priority.cover_url_chain` 配置
- 配置节点：`config.yaml#response_field_priority`

**判断信号**：
- grep `cover_url\s*=\s*None` 在 episode 序列化时未取频道级 cover_url 兜底
- API 返回的 episode 对象无 `cover_url` 字段或值为 None 但 channel 有 cover_url

**严重级别**：MEDIUM（背景图不显示，用户体验差）

**修复建议**：
```python
# ✅ 正确：多级 fallback
def _resolve_episode_cover(episode: Episode, channel: Channel | None) -> str | None:
    """按优先级解析 episode 背景图"""
    if episode.cover_url:
        return episode.cover_url
    if channel and channel.cover_url:
        return channel.cover_url
    return None  # 前端按 undefined 处理，显示默认背景

# ❌ 错误：仅返回 episode.cover_url，无 fallback
return {"cover_url": episode.cover_url}  # None 时前端无背景图
```


---
> 以下维度来源于 2026-07-20 SonarQube 全项目质量扫描复盘，覆盖 NOSONAR 注释位置、扫描环境兼容性、并行子代理核查、git stash 测试验证、NOSONAR vs 修复决策共 5 个维度。对应 news-code-dev 编码规范 61-65 / 元规范速查 86-90。

### 维度 84：NOSONAR 注释位置正确性（对应 news-code-dev S61/R86）

- 【强制】Python 多行函数定义加 NOSONAR 时，必须加在首行 `def func_name(` 行尾，禁止加在末行 `) -> ReturnType:`
- 【强制】NOSONAR 必须大写，前置一个空格（` # NOSONAR`），小写或紧贴代码不生效
- 【推荐】单行函数定义直接在行尾加 NOSONAR
- 配置节点：`config.yaml#nosonar_positioning`

**为什么**：SonarQube Python 解析器把 cognitive complexity（S3776）、async-without-await（S7503）等 issue 报告在函数定义首行 `def func_name(`，NOSONAR 只识别 issue 行的注释。加在末行会导致重新扫描后 issue 仍为 OPEN，浪费扫描时间。本次扫描中 18 个 issues 因位置错误未生效。

**判断信号**：
- grep `\) -> .*:  # NOSONAR` 在多行函数定义末行 → 违规
- grep `# nosonar` / `# Nosonar`（小写或混合大小写）→ 违规
- SonarQube 重新扫描后已加 NOSONAR 的 issue 仍 OPEN → 位置错误
- grep `def \w+\(.*# NOSONAR` 在多行函数首行 → 正确

**严重级别**：CRITICAL（导致扫描闭环失败，issue 无法关闭）

**修复建议**：
```python
# ✅ 正确：NOSONAR 加在多行函数定义首行 def 行
async def list_workflows(  # NOSONAR
    self,
    page: int,
    size: int,
) -> dict:
    ...

# ❌ 错误：NOSONAR 加在末行返回类型注解行
async def list_workflows(
    self,
    page: int,
    size: int,
) -> dict:  # NOSONAR  ← 不生效，issue 仍报 OPEN
    ...

# ❌ 错误：小写或紧贴代码
async def list_workflows(self):  # nosonar  ← 小写不生效
async def list_workflows(self):# NOSONAR  ← 无空格不生效
```

适用场景：所有 Python 多行函数定义（参数跨行、返回类型注解跨行）
不适用场景：单行函数定义（直接加在行尾即可）

---

### 维度 85：SonarQube 扫描环境兼容性（对应 news-code-dev S62/R87）

- 【强制】SonarQube 扫描前必须预检 Node.js 版本（≥ v24 不兼容 SonarJS bridge）
- 【强制】Windows + PowerShell 5 环境下，sonar-scanner CLI 必须用 .bat 文件封装，禁止直接传 `-D` 参数
- 【强制】禁止使用 `cmd /c` 启动 sonar-scanner（被沙盒安全策略阻止）
- 【推荐】Node.js v24 不兼容时，临时修改 `sonar-project.properties` 的 `sonar.sources` 排除 JS/TS，扫描完成后恢复原配置
- 配置节点：`config.yaml#sonarqube_environment`

**为什么**：环境兼容性问题与代码无关，重试无效。本次扫描遇到三类环境问题：(1) Node v24 报 `Cannot find module './globals-IVYI6PB4.json'`；(2) PS5 对 `-Dsonar.host.url=...` 参数中的 `:` 解析异常报 `Unrecognized option`；(3) `cmd /c` 被沙盒阻止。

**判断信号**：
- `node --version` 输出 ≥ v24 → SonarJS bridge 启动失败
- PowerShell 5 直接执行 `sonar-scanner -D...` → 报 `Unrecognized option: .host.url=...`
- 日志含 `cmd /c is blocked on Windows for safety` → 沙盒阻止
- 日志含 `Cannot find module './globals-IVYI6PB4.json'` → Node v24 不兼容

**严重级别**：HIGH（阻塞扫描流程）

**修复建议**：
```powershell
# ✅ 正确：用 .bat 文件封装 sonar-scanner 调用
# sonar-scanner.bat 内容：
# @echo off
# chcp 65001 > nul
# set "SONAR_TOKEN=xxx"
# "D:\path\sonar-scanner.bat" -Dsonar.host.url=http://127.0.0.1:9000
Start-Process -FilePath ".tmp_run_scanner.bat" -NoNewWindow -Wait

# ✅ 降级策略：Node v24 不兼容时，临时仅扫描 Python
# sonar-project.properties
# sonar.sources=backend/app  # 临时排除 admin-web/src, miniprogram, scf

# ❌ 错误：直接在 PS5 中传 -D 参数
& sonar-scanner.bat -Dsonar.host.url=http://127.0.0.1:9000  # 报 Unrecognized option

# ❌ 错误：用 cmd /c 启动
cmd /c "sonar-scanner.bat -D..."  # 被沙盒阻止
```

适用场景：Windows + PowerShell 5 + SonarQube 扫描
不适用场景：Linux/Mac + bash + Node v20 LTS

---

### 维度 86：并行子代理修复结果核查（对应 news-code-dev S63/R88）

- 【强制】多个并行子代理修复 SonarQube issues 后，主代理必须用 grep 二次核查 NOSONAR 是否实际写入
- 【强制】核查内容包括：(1) NOSONAR 是否在文件中实际存在；(2) NOSONAR 行号是否与 SonarQube 报告的 issue 行号一致；(3) 多行函数定义的 NOSONAR 是否在首行
- 【推荐】子代理任务分发的文件组必须互斥（同一文件不能被多个子代理修改），避免合并冲突
- 配置节点：`config.yaml#parallel_subagent_verification`

**为什么**：子代理在长任务中可能因 token 压缩丢失上下文，或对"加在某行"的理解与主代理不一致。本次扫描中 5 个子代理修复 54 个 issues，重新扫描后 18 个仍 OPEN，核查发现：(1) 1 个子代理报告加 NOSONAR 但实际未加；(2) 4 个子代理把 NOSONAR 加到多行函数末行而非首行。

**判断信号**：
- 子代理报告"已加 NOSONAR 到 L504"但 grep `NOSONAR` 该文件未找到 → 遗漏
- grep 找到 NOSONAR 但行号与 SonarQube 报告的 issue 行号不符 → 位置错误
- 重新扫描后该 issue 仍 OPEN → 必然存在位置或遗漏问题

**严重级别**：HIGH（导致扫描闭环失败，需多次迭代）

**修复建议**：
```powershell
# ✅ 正确：子代理修复后，主代理用 grep 核查所有 NOSONAR 位置
Select-String -Path "backend/app/services/*.py" -Pattern "NOSONAR" |
  ForEach-Object { "$($_.Filename):$($_.LineNumber): $($_.Line)" }
# 对照 SonarQube 报告的 issue 行号，逐一核对

# ✅ 正确：子代理任务分发文件组互斥
# 子代理 1: models/ + routers/admin/
# 子代理 2: services/
# 子代理 3: workflow/
# 子代理 4: main/auth/tunnel/notification
# 子代理 5: workflow_scheduler.py（单文件多 issue）
```

适用场景：所有并行子代理修复任务（SonarQube issues、批量重构、多文件改动）
不适用场景：单代理串行修改（主代理可直接观察每次 Edit 结果）

---

### 维度 87：测试失败 git stash 验证（对应 news-code-dev S64/R89）

- 【强制】代码修改后测试失败时，必须用 git stash 验证失败是否为预先存在问题
- 【强制】git stash 流程：`git stash push -m 'verify-baseline' -- <修改的文件>` → 运行测试 → `git stash pop` 恢复
- 【推荐】失败的测试与本次修改的文件无直接关联时，优先怀疑预先存在问题
- 配置节点：`config.yaml#test_failure_diagnosis`

**为什么**：项目可能存在长期失败的测试（如测试与实现不同步）。如果直接修复会浪费时间为"回归"找原因，实际是预先存在问题。本次扫描修改 content_service.py L29 类型注解后，4 个 test_content_service.py 测试失败，git stash 后测试仍失败，证明是预先存在的"测试与多频道实现不同步"问题。

**判断信号**：
- 修改后 N 个测试失败，但失败的测试与修改文件无直接关联 → 可能预先存在
- 失败信息提示类型不匹配（如 `assert [] is None`）→ 测试与实现契约不同步
- 失败信息提示 `TypeError: list indices must be integers`（访问 `result["key"]` 但 result 是 list）→ 多频道架构演进未同步测试

**严重级别**：HIGH（误判为回归会浪费排查时间）

**修复建议**：
```bash
# ✅ 正确：git stash 后运行测试，对比失败是否预先存在
git stash push -m 'verify-baseline' -- backend/app/services/content_service.py
python -m pytest tests/test_content_service.py -v
# 若仍失败 → 预先存在问题，git stash pop 恢复后修复测试
# 若通过 → 本次修改引入回归，git stash pop 后修复代码
git stash pop

# ❌ 错误：直接断定为回归，回退代码修改
# 这会让真正的代码改进（如类型注解完善）被回退
```

适用场景：任何代码修改后的测试验证
不适用场景：全新项目无 git 历史

---

### 维度 88：NOSONAR 抑制 vs 代码修复决策（对应 news-code-dev S65/R90）

- 【强制】真缺陷必须修复代码，禁止用 NOSONAR 抑制
- 【强制】误报或重构成本高时可用 NOSONAR 抑制，但必须在注释中说明抑制原因
- 【强制】NOSONAR 抑制需在代码审查时单独标注，便于后续重构
- 配置节点：`config.yaml#nosonar_decision_matrix`

**为什么**：滥用 NOSONAR 会让真实缺陷被掩盖，降低代码质量。反之，对认知复杂度超阈值但职责单一的函数强行重构会引入风险。需要明确判断标准。本次扫描中 backup_service.py L92 裸 `except:` 必须修复（真缺陷），main.py L98 `_seed_default_admin` async 但内部 sqlite3 同步操作可用 NOSONAR 抑制（契约约束）。

**判断信号**：

| 规则 | 类型 | 处理方式 |
|------|------|----------|
| S5446 裸 except | 真缺陷 | 修复为 `except Exception:` |
| S930 参数不匹配 | 真缺陷 | 修复参数名 |
| S2817 硬编码 SQL | 真缺陷 | 提取常量 |
| S5886 Optional 缺失 | 真缺陷 | 补充类型注解 |
| S3776 认知复杂度 | 重构成本高 | NOSONAR 抑制（若职责单一） |
| S7503 async 无 await | 误报/契约约束 | NOSONAR 抑制（如 lifespan 钩子） |
| S125 注释代码误报 | 误报 | NOSONAR 抑制 |

**严重级别**：CRITICAL（错误决策会导致真缺陷被掩盖或可读性下降）

**修复建议**：
```python
# ✅ 真缺陷：必须修复代码
# 修复前：except:  # 裸 except（S5446）
# 修复后：
except Exception as e:
    logger.exception("操作失败: %s", e)

# ✅ 契约约束：NOSONAR 抑制 + 注释说明
# lifespan 调用方用 await 调用，改 async 会破坏调用契约
async def _seed_default_admin() -> None:  # NOSONAR  # S7503: lifespan 钩子契约约束
    # 内部用 sqlite3 同步操作（启动时一次性 seed，无需并发）
    ...

# ❌ 错误：真缺陷用 NOSONAR 抑制
except:  # NOSONAR  # 掩盖了所有异常包括 KeyboardInterrupt
    pass
```

适用场景：所有 SonarQube issue 修复决策
不适用场景：无 SonarQube 的项目（用 IDE linter 规则替代）

---


---
> 以下维度来源于跨项目模块迁移与测试执行复盘，覆盖后端侧的模块级单例缓存测试隔离、多版本 Python 环境下的测试执行。前端侧的对应维度（75-77）见 `news-frontend-code-review/SKILL.md`。

### 维度 89：模块级单例缓存的测试隔离（对应 news-code-dev S64/R89）

- 【强制】模块级单例缓存（TTLCache / dict / lru_cache / functools.cache）的模块必须提供 `_reset_cache_for_test()` 函数
- 【强制】测试 fixture 的 `setUp` / `autouse=True` 钩子必须调用 `_reset_cache_for_test()`，禁止依赖测试用例间的"自然失效"
- 【强制】`_reset_cache_for_test()` 必须清空所有模块级缓存容器，包括嵌套的 dict 和 TTLCache 实例
- 配置节点：`config.yaml#cache_test_isolation_backend`

**为什么**：后端项目中 ai_budget、workflow_id 计数器、crawler_dedup TTL 表、stats 缓存均使用模块级 TTLCache 或 dict 单例。进程内 pytest 共享同一个解释器，测试用例 A 写入的缓存若不在 fixture 中清理，会用例 B 读取到 A 的脏数据，导致断言失败但代码正确，或断言通过但隐藏真实缺陷。本次测试中 ai_budget 模块的 `_budget_cache` 未在 fixture 中重置，导致跨日额度重置测试用例间相互污染。

**判断信号**：

```bash
# 信号 1：模块级缓存容器无对应的 _reset_cache_for_test 函数
grep -rn "^_[a-z_]*_cache\s*[:=]\|^_[a-z_]*_dict\s*[:=]" backend/app/

# 信号 2：测试文件无 _reset_cache_for_test 调用
grep -rn "_reset_cache_for_test" backend/tests/ | wc -l

# 信号 3：使用 module-level dict 作为计数器但无重置入口
grep -rn "^_[a-z_]*_counter\s*[:=]\s*\(0\|{}\)" backend/app/
```

**严重级别**：HIGH（隐藏真实缺陷，导致测试通过但生产环境出错）

**正确做法**：

```python
# ✅ app/services/ai_budget_service.py
from cachetools import TTLCache

# 模块级单例缓存
_budget_cache: TTLCache[str, int] = TTLCache(maxsize=1024, ttl=3600)
_daily_counter: dict[str, int] = {}

def _reset_cache_for_test() -> None:
    """重置模块级缓存，仅供测试 fixture 调用。

    为什么要单独提供：TTLCache 和 dict 的 clear() 不能清空已绑定的引用，
    必须通过赋值新实例或显式 clear() 两种方式之一，统一入口避免遗漏。
    """
    _budget_cache.clear()
    _daily_counter.clear()


# ✅ tests/test_ai_budget.py
import pytest
from app.services.ai_budget_service import _reset_cache_for_test

@pytest.fixture(autouse=True)
def reset_caches():
    """每个测试用例前重置模块级缓存，保证隔离。"""
    _reset_cache_for_test()
    yield
    _reset_cache_for_test()  # 测试后也清理，防止下一个用例受影响


# ❌ 错误：依赖 TTL 自然失效
@pytest.fixture
def setup_data():
    # 不调用 _reset_cache_for_test，TTL=3600s，测试用例间共享脏数据
    await create_budget_record(date="2026-07-21", tokens=50000)
```

适用场景：所有使用模块级 TTLCache / dict / lru_cache / functools.cache 的后端模块的单元测试
不适用场景：纯函数模块（无模块级状态）、集成测试（每个测试用独立数据库实例）

---

### 维度 90：多版本 Python 环境下的测试执行（对应 news-code-dev S65/R90）

- 【强制】Windows + Trae 内置 Python + 系统 Python 多版本共存时，测试执行必须使用显式 Python 路径，禁止依赖 PATH 解析
- 【强制】CI/CD 和本地测试脚本必须先验证 `python -c "import pytest"` 成功后再执行 `python -m pytest`
- 【强制】测试依赖（pytest、pytest-asyncio、aiosqlite 等）必须在 `requirements-dev.txt` 中显式声明，且与生产 `requirements.txt` 分离
- 配置节点：`config.yaml#python_env_test_backend`

**为什么**：Windows 系统中 Trae IDE 内置的 Python 解释器优先级高于系统 Python，但内置解释器不安装 pytest 等测试依赖。直接运行 `python -m pytest` 会触发 `No module named pytest` 错误，且错误信息不指明实际使用的 Python 路径，导致排查耗时。本次测试中 `& "F:\Program Files\Python3.14\python.exe" -m pytest` 显式路径才解决问题。

**判断信号**：

```bash
# 信号 1：测试脚本使用 python 而非显式路径
grep -rn "^python -m pytest\|^python\s" scripts/run_tests.* backend/tests/conftest.py

# 信号 2：requirements-dev.txt 缺失或未包含 pytest
ls backend/requirements-dev.txt 2>/dev/null
grep -E "^pytest(-asyncio)?$" backend/requirements-dev.txt

# 信号 3：CI 配置使用 PATH 中的 python
grep -rn "python -m pytest" .github/workflows/ .gitlab-ci.yml
```

**严重级别**：HIGH（测试环境不可用，阻塞迭代发布）

**正确做法**：

```powershell
# ✅ scripts/run_tests.ps1 - 显式 Python 路径 + 依赖验证
param(
    [string]$PythonPath = "F:\Program Files\Python3.14\python.exe"
)

# 步骤 1：验证 Python 路径存在
if (-not (Test-Path $PythonPath)) {
    Write-Error "Python not found at: $PythonPath"
    exit 1
}

# 步骤 2：验证 pytest 已安装
& $PythonPath -c "import pytest; print('pytest', pytest.__version__)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "pytest not installed in $PythonPath, run: & '$PythonPath' -m pip install -r requirements-dev.txt"
    exit 1
}

# 步骤 3：执行测试
& $PythonPath -m pytest backend/tests/ -v --tb=short


# ❌ 错误：依赖 PATH 解析
python -m pytest backend/tests/  # 可能调用 Trae 内置 Python，无 pytest


# ✅ backend/requirements-dev.txt（与生产依赖分离）
pytest==8.4.0
pytest-asyncio==0.24.0
pytest-cov==5.0.0
aiosqlite==0.20.0
httpx==0.27.0  # 用于测试 FastAPI TestClient
```

适用场景：Windows 多 Python 版本共存、Trae/VSCode 内置 Python 干扰 PATH、CI/CD 矩阵测试
不适用场景：单一 Python 环境的 Docker 容器、Linux 系统的 pyenv global 锁定版本

---


---
> 以下维度来源于 2026-07-21 图片爬虫、工作流多步骤失败修复、P0/P1 改进实施、监控告警、健康度仪表盘、RSS 巡检、批量回填、PWA manifest 等综合复盘。所有阈值、白名单、cron 表达式、字段清单均通过 `config.yaml` 对应节点管理，禁止硬编码业务值。

### 维度 91：图片封面三级 fallback 提取审查

**配置节点**：`config.yaml#image_crawl_check`

来源：2026-07-21 图片爬虫功能开发。

- 【强制】文章封面图提取必须实现 `og:image → article <img> → 页面首个非装饰 <img>` 三级 fallback
- 【强制】`og:image` 必须过滤装饰图（URL 含 `logo/icon/arrow` 等关键词时跳过）
- 【强制】`article <img>` 必须排除 GIF 扩展名（动画图不适合封面）
- 【强制】特定站点模板路径必须排除（通过配置白名单管理）
- 【强制】Material 模型新增 `cover_url` 字段时必须配套迁移脚本 + 批量回填脚本（联动维度 99）

**判断信号**：
- Grep `og:image` 后无 fallback 到 `<img>` 逻辑
- Grep `cover_url` 提取无装饰图 URL 关键词过滤
- Grep Material 模型有 `cover_url` 字段但无 `backfill_cover_url.py` 脚本
- Grep `re\.search\(["']\.(gif|GIF)["']` 在 article `<img>` 分支缺失

**严重级别**：HIGH（封面图缺失或为装饰图导致前端展示异常）

**正确做法**：
```python
# ✅ 正确：三级 fallback + 装饰图过滤 + GIF 排除
from app.config import get_settings

_DECORATIVE_KEYWORDS = tuple(get_settings().IMAGE_DECORATIVE_KEYWORDS)  # 配置驱动
_EXCLUDE_PATH_PATTERNS = tuple(get_settings().IMAGE_EXCLUDE_PATH_PATTERNS)

def _is_decorative(url: str) -> bool:
    url_lower = url.lower()
    return any(kw in url_lower for kw in _DECORATIVE_KEYWORDS)

def _is_gif(url: str) -> bool:
    return url.lower().endswith('.gif')

def extract_cover(html: str, article_html: str | None = None) -> str | None:
    # 第一级：og:image（过滤装饰图 + 排除模板路径）
    og = _parse_og_image(html)
    if og and not _is_decorative(og) and not _is_path_excluded(og, _EXCLUDE_PATH_PATTERNS):
        return og
    # 第二级：article <img>（排除 GIF + 装饰图）
    if article_html:
        for src in _parse_article_imgs(article_html):
            if not _is_gif(src) and not _is_decorative(src):
                return src
    # 第三级：页面首个非装饰 <img>
    for src in _parse_all_imgs(html):
        if not _is_decorative(src):
            return src
    return None
```

**错误做法**：
```python
# ❌ 错误：仅 og:image，无 fallback、无装饰图过滤
def extract_cover(html: str) -> str | None:
    return _parse_og_image(html)  # og:image 缺失时返回 None，且 logo 等装饰图被当封面

# ❌ 错误：article <img> 未排除 GIF（动画图被当封面，前端列表页跳动）
for src in _parse_article_imgs(article_html):
    return src  # 第一个可能是 .gif
```

适用场景：所有从外部 HTML 提取封面图的爬虫/采集模块
不适用场景：上游已提供 cover_url 字段（如 RSS enclosure）、纯文本源

---

### 维度 92：FALLBACK_DAYS 动态计算审查

**配置节点**：`config.yaml#fallback_days_check`

来源：2026-07-21 工作流多步骤失败修复。

- 【强制】素材回溯天数必须根据频道入库天数动态计算（默认 3/7/14 天三档），禁止硬编码固定值
- 【强制】频道入库天数 <3 天时使用 3 天 fallback；3-7 天用 7 天；>7 天用 14 天（具体阈值通过 `fallback_days_check.tiers` 配置）
- 【强制】阈值通过 `config.yaml#fallback_days_check.tiers` 配置管理
- 【推荐】日志中记录实际使用的 `fallback_days` 值和对应频道 ID，便于排查素材不足问题

**判断信号**：
- Grep `FALLBACK_DAYS\s*=\s*\d+` 硬编码数字
- Grep `fallback_days\s*=\s*\d+` 直接赋值常量
- Grep 素材回溯逻辑无频道入库天数判断
- Grep `select\(Material\).*created_at\s*>=` 无 `timedelta\(days=fallback_days\)` 动态计算

**严重级别**：HIGH（新频道素材不足直接报错，工作流中断）

**正确做法**：
```python
# ✅ 正确：根据频道入库天数动态选择 fallback_days（配置驱动）
from app.config import get_settings

def compute_fallback_days(channel_created_at: datetime | None) -> int:
    tiers = get_settings().FALLBACK_DAYS_TIERS  # [{"max_age_days": 3, "fallback_days": 3}, ...]
    if channel_created_at is None:
        return tiers[0]["fallback_days"]  # 默认最小档
    age_days = (datetime.now() - channel_created_at).days
    for tier in tiers:  # 按阈值升序
        if age_days < tier["max_age_days"]:
            return tier["fallback_days"]
    return tiers[-1]["fallback_days"]  # 最大档

async def fetch_materials(channel_id: int, channel_created_at: datetime | None):
    fallback_days = compute_fallback_days(channel_created_at)
    logger.info("channel_id=%s fallback_days=%s", channel_id, fallback_days)
    cutoff = datetime.now() - timedelta(days=fallback_days)
    return await db.execute(select(Material).where(
        Material.channel_id == channel_id,
        Material.created_at >= cutoff,
    ))
```

**错误做法**：
```python
# ❌ 错误：硬编码固定 7 天
FALLBACK_DAYS = 7
cutoff = datetime.now() - timedelta(days=FALLBACK_DAYS)  # 新频道入库 1 天，回溯 7 天无数据

# ❌ 错误：日志无 fallback_days 上下文
logger.info("开始回溯素材")
```

适用场景：所有按时间窗口回溯素材/数据的工作流（爬虫回溯、审核队列、缓存预热）
不适用场景：固定时间窗口业务（如"昨日数据日报"）

---

### 维度 93：LLM 语义过滤 fallback 审查

**配置节点**：`config.yaml#llm_semantic_fallback_check`

来源：2026-07-21 工作流多步骤失败修复。

- 【强制】关键词过滤结果为 0 条时必须降级到 LLM 语义过滤
- 【强制】LLM 语义过滤失败时保留全部条目供 rewriter 二次筛选，禁止直接报错
- 【强制】LLM 语义过滤必须记录 fallback 触发原因到日志（关键词命中 0 条、超时、解析失败等）
- 【推荐】LLM 语义过滤结果与关键词过滤结果差异较大时记录 WARNING（差异率阈值通过配置管理）

**判断信号**：
- Grep 关键词过滤后 `if not results:` 直接 `raise` 而无 LLM fallback
- Grep LLM 语义过滤无 `try/except` 兜底
- Grep `llm_semantic_filter` 调用无 `logger` 记录 fallback 原因
- Grep LLM 过滤结果与关键词过滤结果无差异率比较

**严重级别**：HIGH（关键词全失效时工作流直接中断）

**正确做法**：
```python
# ✅ 正确：关键词 0 条降级 LLM，LLM 失败保留全部
from app.config import get_settings

async def filter_materials(materials: list[Material]) -> list[Material]:
    # 第一级：关键词过滤
    keyword_filtered = _keyword_filter(materials)
    if keyword_filtered:
        return keyword_filtered

    # 第二级：LLM 语义过滤（关键词 0 条触发）
    logger.warning("keyword_filter 返回 0 条，降级到 LLM 语义过滤，material_count=%d", len(materials))
    try:
        llm_filtered = await _llm_semantic_filter(materials)
        _log_diff_rate(keyword_filtered, llm_filtered)  # 差异率超阈值记录 WARNING
        return llm_filtered or materials  # LLM 返回空也保留全部
    except Exception as e:
        # 第三级：LLM 失败保留全部，供 rewriter 二次筛选
        logger.exception("LLM 语义过滤失败，保留全部 %d 条供 rewriter 筛选", len(materials))
        return materials
```

**错误做法**：
```python
# ❌ 错误：关键词 0 条直接 raise，工作流中断
async def filter_materials(materials):
    filtered = _keyword_filter(materials)
    if not filtered:
        raise RuntimeError("关键词过滤无结果")  # 工作流直接挂
    return filtered

# ❌ 错误：LLM 失败未兜底
async def filter_materials(materials):
    return await _llm_semantic_filter(materials)  # 抛异常无人接
```

适用场景：所有"关键词过滤 → LLM 语义过滤"多级筛选链路
不适用场景：纯关键词过滤（无 LLM 依赖）、强一致要求的过滤（如合规审核）

---

### 维度 94：LLM 字数达标约束审查

**配置节点**：`config.yaml#llm_word_count_check`

来源：2026-07-21 P0 改进实施。

- 【强制】LLM 生成内容后必须统计字数，低于 `target * min_ratio`（默认 0.70）时触发硬约束重试
- 【强制】重试次数上限通过 `llm_word_count_check.max_retry` 配置（默认 3 次），超限后标记失败
- 【强制】字数超过 `target * max_ratio`（默认 1.20）时必须丢弃多余段（保留至少 3 主段 + intro + outro）
- 【强制】字数低于 `target * append_threshold`（默认 0.80）时必须追加最多 2 段（从未使用的选中素材中选取）
- 【强制】所有阈值通过 `config.yaml#llm_word_count_check` 配置，禁止硬编码

**判断信号**：
- Grep LLM 调用后无 `_count_content_words` 字数统计
- Grep 字数校验逻辑无 `target * 0.70` 或 `target * min_ratio` 阈值判断
- Grep 字数超出无 `_discard_excess_segments` 逻辑
- Grep 字数不足无 `_append_segments_from_unused` 逻辑

**严重级别**：CRITICAL（字数不达标导致 TTS 时长不足，最终音频与目标时长严重偏离）

**正确做法**：
```python
# ✅ 正确：四档字数约束（重试/丢弃/追加/失败）全部配置驱动
from app.config import get_settings

async def generate_with_word_constraint(prompt: str, target: int, materials: list) -> str:
    cfg = get_settings().LLM_WORD_COUNT_CHECK
    for attempt in range(cfg["max_retry"]):
        content = await _llm_generate(prompt)
        word_count = _count_content_words(content)
        if word_count >= target * cfg["min_ratio"]:  # 达标
            break
        logger.warning("LLM 字数不足 attempt=%d count=%d target=%d", attempt, word_count, target)
    else:
        raise BizError(f"LLM 字数 {word_count} < {target * cfg['min_ratio']}，重试 {cfg['max_retry']} 次仍不达标")

    # 超出阈值：丢弃多余段
    if word_count > target * cfg["max_ratio"]:
        content = _discard_excess_segments(content, keep_main=3, keep_intro=True, keep_outro=True)
        logger.info("字数超出丢弃多余段，原 %d 现 %d", word_count, _count_content_words(content))

    # 不足阈值：追加段（最多 2 段，从未使用素材选取）
    if _count_content_words(content) < target * cfg["append_threshold"]:
        content = _append_segments_from_unused(content, materials, max_append=2)
        logger.info("字数不足追加段，现 %d", _count_content_words(content))
    return content
```

**错误做法**：
```python
# ❌ 错误：LLM 生成后直接返回，无字数校验
async def generate(prompt: str) -> str:
    return await _llm_generate(prompt)  # 字数严重不足时直接送 TTS

# ❌ 错误：硬编码阈值
if word_count < target * 0.70:  # 0.70 应在 config.yaml
    ...
```

适用场景：所有 LLM 生成 + 字数/长度约束的工作流（稿件改写、内容生成、摘要生成）
不适用场景：纯翻译（字数与原文对齐）、纯结构化输出（JSON/列表）

---

### 维度 95：BGM 时长不足兜底审查

**配置节点**：`config.yaml#bgm_fallback_check`

来源：2026-07-21 P1 改进实施。

- 【强制】视频拼接时 BGM 时长 < 视频时长必须用 BGM 尾段扩展（loop-last 模式）
- 【强制】BGM 尾段扩展仍不足时必须静音降级（静音填充剩余部分），禁止直接报错失败
- 【强制】禁止 BGM 时长不足时直接 `raise` 导致工作流中断
- 【推荐】日志记录 BGM fallback 触发原因和实际处理方式（loop-last / silent-pad）

**判断信号**：
- Grep BGM 拼接逻辑无时长不足判断
- Grep `bgm_duration < video_duration` 后直接 `raise`
- Grep `ffmpeg.*BGM` 命令构造无 `-stream_loop` 或 `apad` 兜底参数
- Grep 无 `silent_pad` 或 `anullsrc` 静音降级逻辑

**严重级别**：CRITICAL（BGM 时长不足直接报错会导致整个工作流失败，已生成的 TTS 音频浪费）

**正确做法**：
```python
# ✅ 正确：BGM 时长不足时三级兜底（loop-last → silent-pad → raise 仅在所有兜底失败时）
import subprocess
from app.config import get_settings

def stitch_bgm(video_path: str, bgm_path: str, video_duration: float) -> str:
    cfg = get_settings().BGM_FALLBACK_CHECK
    bgm_duration = _probe_duration(bgm_path)

    if bgm_duration >= video_duration:
        # 正常拼接
        return _ffmpeg_stitch(video_path, bgm_path, end_at=video_duration)

    # 一级兜底：loop-last（BGM 尾段扩展到视频时长）
    if bgm_duration >= video_duration * cfg["loop_last_min_ratio"]:  # 默认 0.5
        logger.info("BGM 不足 loop-last 扩展 bgm=%.1f video=%.1f", bgm_duration, video_duration)
        return _ffmpeg_stitch_loop_last(video_path, bgm_path, video_duration)

    # 二级兜底：BGM 用到结尾 + 静音填充剩余
    logger.warning("BGM 不足静音降级 bgm=%.1f video=%.1f", bgm_duration, video_duration)
    return _ffmpeg_stitch_with_silent_pad(video_path, bgm_path, bgm_duration, video_duration)
```

**错误做法**：
```python
# ❌ 错误：BGM 时长不足直接 raise
def stitch_bgm(video_path, bgm_path, video_duration):
    bgm_duration = _probe_duration(bgm_path)
    if bgm_duration < video_duration:
        raise BizError(f"BGM 时长 {bgm_duration} 不足 {video_duration}")  # 工作流直接挂
    ...

# ❌ 错误：无静音降级，仅靠 loop-last（BGM 极短时 loop-last 也不够）
```

适用场景：所有视频/音频拼接 + BGM 背景音的工作流
不适用场景：纯人声朗读（无 BGM）、BGM 与视频等长（如循环 BGM 资源）

---

### 维度 96：关键指标监控告警审查

**配置节点**：`config.yaml#monitoring_thresholds_check`

来源：2026-07-21 P0 改进实施。

- 【强制】关键词命中率 < `monitoring_thresholds.keyword_hit_rate_min`（默认 0.10）时记录 WARNING
- 【强制】LLM 字数达成率 < `monitoring_thresholds.llm_word_count_rate_min`（默认 0.80）时记录 WARNING
- 【强制】TTS 成功率 < `monitoring_thresholds.tts_success_rate_min`（默认 0.90）时记录 WARNING
- 【强制】工作流成功率 < `monitoring_thresholds.workflow_success_rate_min`（默认 0.95）时记录 WARNING
- 【强制】所有阈值通过 `config.yaml#monitoring_thresholds_check` 配置管理

**判断信号**：
- Grep 关键词过滤流程无命中率计算和 WARNING 判断
- Grep LLM 调用流程无字数达成率计算和 WARNING 判断
- Grep TTS 调用流程无成功率统计和 WARNING 判断
- Grep 工作流执行流程无成功率统计和 WARNING 判断
- Grep 阈值数字（如 `0.10`、`0.80`、`0.90`、`0.95`）硬编码而非从 settings 读取

**严重级别**：HIGH（指标异常未告警，运营无感知，问题累积到 P0 才发现）

**正确做法**：
```python
# ✅ 正确：四类指标全部从配置读阈值 + 低于阈值记录 WARNING
from app.config import get_settings

async def report_keyword_hit_rate(filtered: list, total: list):
    rate = len(filtered) / max(len(total), 1)
    threshold = get_settings().MONITORING_THRESHOLDS["keyword_hit_rate_min"]
    if rate < threshold:
        logger.warning("关键词命中率 %.2f < 阈值 %.2f filtered=%d total=%d",
                       rate, threshold, len(filtered), len(total))

async def report_llm_word_rate(content: str, target: int):
    rate = _count_content_words(content) / max(target, 1)
    threshold = get_settings().MONITORING_THRESHOLDS["llm_word_count_rate_min"]
    if rate < threshold:
        logger.warning("LLM 字数达成率 %.2f < 阈值 %.2f", rate, threshold)

async def report_tts_success_rate(success: int, total: int):
    rate = success / max(total, 1)
    threshold = get_settings().MONITORING_THRESHOLDS["tts_success_rate_min"]
    if rate < threshold:
        logger.warning("TTS 成功率 %.2f < 阈值 %.2f success=%d total=%d", rate, threshold, success, total)
```

**错误做法**：
```python
# ❌ 错误：阈值硬编码
if rate < 0.10:
    logger.warning("关键词命中率低")

# ❌ 错误：无指标采集（运营靠用户投诉发现问题）
async def filter_materials(materials):
    return _keyword_filter(materials)  # 不记录命中率
```

适用场景：所有工作流关键节点（爬虫、改写、TTS、拼接、发布）
不适用场景：实验性脚本、一次性数据迁移

---

### 维度 97：频道素材健康度仪表盘审查

**配置节点**：`config.yaml#channel_health_dashboard_check`

来源：2026-07-21 P1 改进实施。

- 【强制】必须提供 `/channel-health` 端点返回频道素材健康度（三级健康判定：healthy / warning / critical）
- 【强制】健康度判定标准通过配置管理：素材数 ≥ N 为 healthy，≥ M 为 warning，< M 为 critical
- 【强制】健康度数据必须包含：频道 ID、频道名、素材总数、近 7 天素材数、健康等级
- 【推荐】健康度仪表盘支持时间范围筛选（`?days=7` 参数）

**判断信号**：
- Grep 路由文件无 `/channel-health` 端点
- Grep 健康度判定逻辑无阈值配置读取（硬编码 N/M）
- Grep 健康度响应无 `channel_id` / `channel_name` / `total_count` / `recent_count` / `health_level` 字段
- Grep `health_level` 取值非 `healthy|warning|critical` 三档之一

**严重级别**：MEDIUM（无健康度可视化，运营无法主动发现素材不足频道）

**正确做法**：
```python
# ✅ 正确：端点 + 配置驱动阈值 + 完整字段 + 时间范围筛选
from app.config import get_settings

@router.get("/channel-health")
async def channel_health(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    cfg = get_settings().CHANNEL_HEALTH_DASHBOARD_CHECK
    cutoff = datetime.now() - timedelta(days=days)
    channels = await db.execute(select(Channel).where(Channel.is_active == 1))
    result = []
    for ch in channels.scalars():
        total = await _count_materials(db, ch.id)
        recent = await _count_materials(db, ch.id, since=cutoff)
        level = _classify_health(total, cfg["healthy_min"], cfg["warning_min"])
        result.append({
            "channel_id": ch.id,
            "channel_name": ch.name,
            "total_count": total,
            "recent_count": recent,
            "health_level": level,  # healthy | warning | critical
        })
    return success(data={"channels": result, "days": days})

def _classify_health(total: int, healthy_min: int, warning_min: int) -> str:
    if total >= healthy_min:
        return "healthy"
    if total >= warning_min:
        return "warning"
    return "critical"
```

**错误做法**：
```python
# ❌ 错误：无 /channel-health 端点（运营只能 SQL 查询）
# ❌ 错误：阈值硬编码
if total >= 100:  # 100 应在 config.yaml
    return "healthy"

# ❌ 错误：响应缺字段（仅有 channel_id，无 health_level）
return {"channels": [{"channel_id": ch.id} for ch in channels]}
```

适用场景：多频道内容生产系统、需要运营主动监控素材储备的场景
不适用场景：单频道项目、无运营介入的自动化系统

---

### 维度 98：RSS 源可达性巡检审查

**配置节点**：`config.yaml#rss_reachability_check`

来源：2026-07-21 P1 改进实施。

- 【强制】必须提供 `/rss-health` 端点返回 RSS 源可达性状态
- 【强制】RSS 源巡检必须包括：HTTP 状态码、响应时间、内容类型验证（Content-Type 含 `application/rss+xml` 或 `text/xml`）
- 【强制】巡检必须定时执行（通过 APScheduler cron），频率通过 `rss_reachability_check.cron_expression` 配置（默认 2 小时一次）
- 【强制】不可达的 RSS 源必须标记为 `unavailable` 并记录原因（DNS 失败 / 超时 / 404 / 非 RSS 内容等）
- 【强制】巡检必须支持 User-Agent 兼容性（部分 RSS 源拒绝默认 UA），UA 列表通过配置管理

**判断信号**：
- Grep 路由文件无 `/rss-health` 端点
- Grep RSS 源巡检无 `APScheduler` 或 `cron` 定时任务配置
- Grep RSS 巡检无 `User-Agent` 设置
- Grep RSS 巡检无 `Content-Type` 验证（HTTP 200 但返回 HTML 也判定为可达）
- Grep 不可达源无 `unavailable` 状态标记

**严重级别**：HIGH（源失效长期未发现，素材持续 0 入库）

**正确做法**：
```python
# ✅ 正确：端点 + cron 巡检 + UA 兼容 + Content-Type 验证 + 状态标记
from app.config import get_settings

@router.get("/rss-health")
async def rss_health(_: None = Depends(require_admin)):
    sources = await _load_rss_sources_with_status()
    return success(data={"sources": sources})

async def inspect_rss_source(url: str) -> dict:
    cfg = get_settings().RSS_REACHABILITY_CHECK
    headers = {"User-Agent": cfg["user_agents"][0]}  # 配置驱动 UA 列表
    start = time.monotonic()
    try:
        resp = await client.get(url, headers=headers, timeout=cfg["timeout_sec"])
        elapsed = time.monotonic() - start
        content_type = resp.headers.get("content-type", "")
        if resp.status_code != 200:
            return {"url": url, "status": "unavailable", "reason": f"HTTP {resp.status_code}", "elapsed_sec": elapsed}
        if not _is_rss_content_type(content_type):
            return {"url": url, "status": "unavailable", "reason": f"非 RSS 内容类型: {content_type}", "elapsed_sec": elapsed}
        return {"url": url, "status": "available", "reason": "ok", "elapsed_sec": elapsed}
    except httpx.ConnectError:
        return {"url": url, "status": "unavailable", "reason": "DNS/TCP 失败", "elapsed_sec": time.monotonic() - start}
    except httpx.TimeoutException:
        return {"url": url, "status": "unavailable", "reason": "超时", "elapsed_sec": time.monotonic() - start}

# APScheduler cron 定时巡检（cron 表达式配置驱动）
scheduler.add_job(inspect_all_rss_sources, "cron", **_parse_cron(cfg["cron_expression"]))
```

**错误做法**：
```python
# ❌ 错误：无 /rss-health 端点
# ❌ 错误：无 cron 定时巡检（仅在用户手动触发时检查）
# ❌ 错误：无 User-Agent 设置（部分源拒绝默认 UA，巡检全部误判为不可达）
resp = await client.get(url)  # 无 headers
# ❌ 错误：HTTP 200 即判定可达（不验证 Content-Type，HTML 页面误判为 RSS 可达）
if resp.status_code == 200:
    return {"status": "available"}
```

适用场景：依赖外部 RSS 源的内容采集系统
不适用场景：内部 API 数据源（无 DNS/限流问题）、一次性导入

---

### 维度 99：批量数据回填脚本审查

**配置节点**：`config.yaml#backfill_script_check`

来源：2026-07-21 图片爬虫功能开发。

- 【强制】ORM 模型新增字段后必须编写 `backfill_*.py` 批量回填脚本
- 【强制】回填脚本必须支持 `--dry-run` 预览模式（只输出不执行）
- 【强制】回填脚本必须分批处理（默认 100 条/批），避免内存溢出
- 【强制】回填脚本必须幂等（重复执行不报错，已回填的记录跳过）
- 【强制】回填脚本必须输出进度（已处理/总数/百分比）
- 【推荐】回填脚本支持 `--batch-size` 参数自定义批量大小

**判断信号**：
- Grep ORM 模型新增字段（如 `cover_url: Mapped[...]`）但无对应 `backfill_*.py` 脚本
- Grep `backfill` 脚本无 `--dry-run` 参数
- Grep `backfill` 脚本无分批处理逻辑（`limit/offset` 或 `slice`）
- Grep `backfill` 脚本无幂等检查（已回填记录未跳过）
- Grep `backfill` 脚本无进度输出

**严重级别**：HIGH（字段新增后存量数据缺失，前端展示空白）

**正确做法**：
```python
# ✅ 正确：backfill_cover_url.py 完整实现
# python -m app.scripts.backfill_cover_url --dry-run --batch-size 100
import argparse
from app.config import get_settings

async def main(dry_run: bool, batch_size: int):
    cfg = get_settings().BACKFILL_SCRIPT_CHECK
    batch_size = batch_size or cfg["default_batch_size"]
    total = await db.scalar(select(func.count(Material.id)).where(Material.cover_url.is_(None)))
    processed = 0
    while True:
        # 分批查询未回填记录（幂等：仅查 cover_url IS NULL）
        batch = await db.execute(
            select(Material).where(Material.cover_url.is_(None))
            .limit(batch_size).offset(processed)
        )
        materials = batch.scalars().all()
        if not materials:
            break
        for mat in materials:
            cover = await extract_cover(mat.source_url)
            if cover and not dry_run:
                mat.cover_url = cover
        if not dry_run:
            await db.commit()
        processed += len(materials)
        pct = processed / total * 100
        logger.info("backfill progress %d/%d (%.1f%%) dry_run=%s", processed, total, pct, dry_run)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.batch_size))
```

**错误做法**：
```python
# ❌ 错误：ORM 新增 cover_url 字段后无回填脚本（存量数据 cover_url 全为 NULL）
# ❌ 错误：无 --dry-run（直接执行无法预览影响范围）
# ❌ 错误：一次性查全部（百万级表 OOM）
materials = await db.execute(select(Material).where(Material.cover_url.is_(None)))
for mat in materials.scalars():  # 全量加载到内存
    ...
# ❌ 错误：非幂等（重复执行覆盖已回填的 cover_url）
```

适用场景：所有 ORM 模型新增字段后的存量数据迁移
不适用场景：新表首次初始化（无存量数据）、字段重命名（用 ALTER TABLE）

---

### 维度 100：PWA manifest 与 MIME 注册审查

**配置节点**：`config.yaml#pwa_manifest_check`

来源：2026-07-21 图标设计任务。

- 【强制】`main.py` 必须注册 `.ico` 的 MIME 类型（`mimetypes.add_type("image/x-icon", ".ico")`）
- 【强制】`main.py` 必须注册 `.webmanifest` 的 MIME 类型（`application/manifest+json`）
- 【强制】静态文件挂载必须包含 `public/` 目录（manifest.json 和图标文件所在）
- 【强制】`manifest.json` 必须含 `icons` 数组、`name`、`short_name`、`theme_color`、`background_color`
- 【推荐】PWA 应用注册 Service Worker 支持离线访问

**判断信号**：
- Grep `main.py` 无 `mimetypes.add_type.*ico`
- Grep `main.py` 无 `mimetypes.add_type.*webmanifest`
- Grep `StaticFiles` 挂载无 `public` 目录
- Grep `manifest.json` 缺少 `icons` / `name` / `short_name` / `theme_color` / `background_color` 字段

**严重级别**：MEDIUM（PWA 安装失败、favicon 404、manifest 加载失败）

**正确做法**：
```python
# ✅ 正确：main.py 注册 MIME + 挂载 public 目录
import mimetypes
from fastapi.staticfiles import StaticFiles

mimetypes.add_type("image/x-icon", ".ico")
mimetypes.add_type("application/manifest+json", ".webmanifest")

app.mount("/static", StaticFiles(directory="backend/static"), name="static")
app.mount("/public", StaticFiles(directory="backend/public"), name="public")  # manifest.json + icons/

# ✅ 正确：manifest.json 含必填字段
{
    "name": "MorningBrief",
    "short_name": "MB",
    "theme_color": "#1976d2",
    "background_color": "#ffffff",
    "display": "standalone",
    "icons": [
        {"src": "/public/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/public/icon-512.png", "sizes": "512x512", "type": "image/png"}
    ]
}
```

**错误做法**：
```python
# ❌ 错误：未注册 .ico MIME（浏览器请求 favicon.ico 返回 text/plain，部分浏览器拒绝渲染）
# ❌ 错误：未注册 .webmanifest（浏览器请求 manifest.webmanifest 返回 application/octet-stream，PWA 安装失败）
# ❌ 错误：未挂载 public 目录（manifest.json 和图标 404）
app.mount("/static", StaticFiles(directory="backend/static"))  # 无 public 挂载

# ❌ 错误：manifest.json 缺字段（缺 theme_color，PWA 安装后状态栏颜色异常）
{"name": "MB", "icons": [...]}  # 缺 short_name / theme_color / background_color
```

适用场景：所有提供 PWA 安装、favicon 加载、manifest 引用的后端服务
不适用场景：纯 API 服务（无静态资源）、纯 SPA（前端服务器直接服务静态资源）

---
来源：2026-07-21 小程序真机调试复盘。后端侧涉及 5 个新维度，对应 news-code-dev 元规范 R101-R108 中的后端部分（R102/R106 + list 接口批量关联、聚合序号独立计数、CommentRequest 字段扩展、cache_key 版本后缀）。

### 维度 101：list 接口批量关联覆盖审查（对应 R102）

**配置节点**：`config.yaml#list_batch_relation_check`

**为什么**：`list_*` API 返回列表时，若逐条查询关联表（如 User、Channel、Material）会造成 N+1 查询；若不覆盖关联字段则前端拿不到 user_name/channel_name 等展示字段，导致前端显示"匿名观众""未知频道"。

**判断信号**：
- Grep `list_comments` / `list_episodes` / `list_reviews` 返回 `c.user_name` 但未批量查 User 表覆盖
- Grep `for .* in .*:` 循环内出现 `await self.db.execute(select(User).where(...))`（N+1 查询）
- Grep 返回字段含 `user_name` / `channel_name` 但代码中无 `IN (` 批量查询

**严重级别**：HIGH（前端显示数据缺失；性能 N+1 查询）

**正确做法**：
```python
# ✅ 正确：批量 IN 查询覆盖关联字段
async def list_comments(self, episode_id: int) -> list[dict]:
    result = await self.db.execute(
        select(Comment).where(Comment.episode_id == episode_id)
    )
    comments = result.scalars().all()
    if not comments:
        return []

    # 批量查 User：一次 IN 查询覆盖所有 user_id
    user_ids = {c.user_id for c in comments if c.user_id}
    user_map = {}
    if user_ids:
        user_result = await self.db.execute(
            select(User).where(User.id.in_(list(user_ids)))
        )
        user_map = {u.id: u for u in user_result.scalars().all()}

    # 拼装时从 map 取关联字段，避免循环内查询
    return [
        {
            "id": c.id,
            "content": c.content,
            "user_name": user_map.get(c.user_id).name if user_map.get(c.user_id) else "匿名听众",
            "user_avatar": user_map.get(c.user_id).avatar if user_map.get(c.user_id) else "",
        }
        for c in comments
    ]
```

**错误做法**：
```python
# ❌ 错误：循环内查询造成 N+1
for c in comments:
    user = await self.db.execute(select(User).where(User.id == c.user_id))
    # ...

# ❌ 错误：返回字段含 user_name 但未覆盖（前端拿到 null）
return [{"id": c.id, "content": c.content, "user_name": None} for c in comments]
```

**适用场景**：所有返回列表的 API（list_comments / list_episodes / list_reviews / list_workflows）
**不适用场景**：单条详情查询（get_by_id）；纯 count 查询

---

### 维度 102：聚合列表序号独立计数审查（对应 R106）

**配置节点**：`config.yaml#aggregated_seq_independence_check`

**为什么**：拼装列表数据时（如 sources 来自多个 segment 的 material_ids），若复用外部 segment.seq 作为聚合序号，第 1 段通常是开场白/结尾无 material，导致 sources 从 seq=2 开始，前端显示序号错乱。

**判断信号**：
- Grep `sources.append.*seq.*seg.get` 复用外部 seq 作为聚合序号
- Grep `seq.*\+.*1` 但 `seq` 来自外部循环变量
- Grep 聚合列表字段含 `seq` 但代码中无独立计数器（如 `source_seq = 0`）

**严重级别**：HIGH（前端序号错乱，用户体验差）

**正确做法**：
```python
# ✅ 正确：独立计数器，从 1 重新编号
sources = []
source_seq = 0  # sources 自己的 1-based 序号
for seg in segments:
    material_ids = seg.get("material_ids") or []
    for mid in material_ids:
        mat = materials_map.get(mid)
        if mat:
            source_seq += 1  # 独立递增，不复用 seg.seq
            sources.append({
                "seq": source_seq,
                "title": mat.title,
                "url": mat.url,
            })
```

**错误做法**：
```python
# ❌ 错误：复用 seg.seq，第 1 段开场白无 material 导致从 2 开始
for seg in segments:
    for mid in seg.get("material_ids") or []:
        sources.append({
            "seq": seg.get("seq"),  # 复用外部 seq
            "title": materials_map[mid].title,
        })
```

**适用场景**：所有拼装列表数据（sources / chapters / timestamps / related_items）
**不适用场景**：直接返回 ORM 模型列表（序号由前端生成）

---

### 维度 103：CommentRequest 可选字段扩展审查（对应前端 R103 适配）

**配置节点**：`config.yaml#comment_request_optional_fields_check`

**为什么**：微信基础库 2.27+ 后 `wx.getUserProfile` 废弃，前端无法在评论提交时自动获取用户昵称/头像，必须由用户手动填写。后端 CommentRequest 必须将 user_name/user_avatar 设为可选字段，否则前端无法提交评论（pydantic 校验失败）。

**判断信号**：
- Grep `class CommentRequest` 字段 `user_name: str`（非 Optional，强制必填）
- Grep `CommentRequest` 无 `user_name: str | None = None` 可选声明
- Grep 评论创建逻辑 `Comment(user_name=req.user_name)` 无 `or "匿名听众"` 兜底

**严重级别**：HIGH（前端无法提交评论，核心功能阻塞）

**正确做法**：
```python
# ✅ 正确：可选字段 + 兜底默认值
class CommentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
    parent_id: int | None = None
    user_name: str | None = None  # 可选（微信 2.27+ 用户手动填写）
    user_avatar: str | None = None  # 可选

# 创建时兜底
comment = Comment(
    content=req.content,
    user_name=req.user_name or "匿名听众",
    user_avatar=req.user_avatar or "",
)
```

**错误做法**：
```python
# ❌ 错误：强制必填，前端无法提交
class CommentRequest(BaseModel):
    content: str
    user_name: str  # 必填 → 前端 wx.getUserProfile 失败时无法提交
    user_avatar: str  # 必填
```

**适用场景**：所有用户提交内容的 API（评论/反馈/举报）
**不适用场景**：管理后台 API（admin 已登录，字段必填）

---

### 维度 104：get_history play_count 批量统计审查

**配置节点**：`config.yaml#history_play_count_batch_check`

**为什么**：历史列表需要展示播放次数，若逐条查询 PlayLog 会造成 N+1；若不返回 play_count 则前端列表缺失关键信息。必须使用一次 IN 查询批量统计。

**判断信号**：
- Grep `get_history` 返回字段含 `play_count` 但无 `IN (` 批量查询
- Grep `get_history` 循环内 `await self.db.execute(select(func.count(PlayLog.id)).where(...))`（N+1）
- Grep `get_history` 返回字段无 `play_count`（前端无法展示播放次数）

**严重级别**：MEDIUM（性能 N+1；前端数据缺失）

**正确做法**：
```python
# ✅ 正确：一次 IN 查询批量统计
if list_data:
    ep_ids = [e["id"] for e in list_data]
    count_result = await self.db.execute(
        select(PlayLog.episode_id, func.count(PlayLog.id))
        .where(PlayLog.episode_id.in_(ep_ids))
        .group_by(PlayLog.episode_id)
    )
    count_map = {row[0]: row[1] for row in count_result.all()}
    for e in list_data:
        e["play_count"] = count_map.get(e["id"], 0)
```

**错误做法**：
```python
# ❌ 错误：N+1 查询
for e in list_data:
    result = await self.db.execute(
        select(func.count(PlayLog.id)).where(PlayLog.episode_id == e["id"])
    )
    e["play_count"] = result.scalar() or 0

# ❌ 错误：未返回 play_count 字段
return {"total": total, "list": list_data}  # list_data 无 play_count
```

**适用场景**：所有分页列表 API 需要展示聚合统计字段（play_count / comment_count / like_count）
**不适用场景**：纯列表无聚合需求；总数已通过 COUNT 查询返回

---

### 维度 105：cache_key 版本后缀审查（对应 R85）

**配置节点**：`config.yaml#cache_key_version_suffix_check`

**为什么**：当响应数据结构变更（如新增 cover_url / segments / sources 字段）时，旧缓存仍按旧结构返回，前端拿到缺失字段的响应。cache_key 必须加版本后缀（如 `:v2`），结构变更时递增版本号使旧缓存自然失效。

**判断信号**：
- Grep `cache_key = f"...:{episode_id}"` 无 `:v{n}` 后缀
- Grep 响应新增字段后 cache_key 未变更版本号
- Grep `await self.cache.set(cache_key, data, ttl=...)` 但 cache_key 无版本后缀

**严重级别**：HIGH（前端拿到旧缓存缺字段，功能异常）

**正确做法**：
```python
# ✅ 正确：cache_key 含版本后缀，结构变更时递增
cache_key = f"script:detail:v2:{episode_id}"  # v2：新增 segments.cover_url 字段
# 结构再次变更时改为 v3
```

**错误做法**：
```python
# ❌ 错误：无版本后缀，结构变更后旧缓存仍返回
cache_key = f"script:detail:{episode_id}"
```

**适用场景**：所有结构化缓存（dict/list 响应，字段可能变更）
**不适用场景**：纯标量缓存（如 `config:value:{key}`）；TTL 很短（<60s）的缓存

---


---
> 基于 2026-07-22 TTS 多 Provider 架构开发经验（阿里云/Edge-TTS/腾讯云三 Provider + 自动降级链路 + edge-tts 版本修复 + 凭证 fallback + TC3-HMAC-SHA256 签名 + Pydantic 类型转换 + tenacity/Semaphore/check_budget 三层防护），按 Sequential Thinking 4 维度框架沉淀可复用的后端审查模板。对应 news-code-dev 元规范 R109-R117。

### 维度 106：多 Provider 抽象基类 + 工厂注册表审查（对应 R109）

**为什么**：同一业务能力有多个外部服务商时，若用 if/elif 分支调用不同服务商，新增 Provider 需改调用方代码，违反开闭原则。抽象基类 + 工厂注册表模式使新增 Provider 仅需实现基类 + 注册工厂。

**配置节点**：`config.yaml#tts_multi_provider_check`

- 【强制】定义抽象基类（如 TTSProvider）含统一接口（synthesize/test_connection），所有 Provider 必须继承
- 【强制】定义统一异常层级（TTSError → TTSProviderError/TTSRateLimitError/TTSTimeoutError/TTSServiceError），按可重试性分类
- 【强制】使用 _PROVIDER_REGISTRY 字典注册 Provider 工厂函数，禁止 if/elif 分支选择 Provider
- 【强制】get_provider() 按 settings 动态返回实例，调用方不感知具体厂商
- 【强制】新增 Provider 仅需实现基类 + 注册工厂，不改调用方代码

**判断信号**：
- `grep 'if provider == ' backend/app/` 多分支调用不同服务商 → 违规
- `grep 'class.*Provider' backend/app/` 无抽象基类（无 ABCMeta/abstractmethod） → 违规
- `grep '_PROVIDER_REGISTRY' backend/app/` 无注册表字典 → 违规

**示例**：
```python
# ❌ 反模式：if/elif 分支选择 Provider
async def synthesize(text, provider):
    if provider == 'aliyun':
        return await aliyun_synthesize(text)
    elif provider == 'edge':
        return await edge_synthesize(text)
    # 新增 Provider 需改此处

# ✅ 正确：抽象基类 + 工厂注册表
class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: str = None) -> bytes: ...

_PROVIDER_REGISTRY: dict[str, Callable[[], TTSProvider]] = {
    'aliyun': _create_aliyun,
    'edge': _create_edge,
    'tencent': _create_tencent,
}
# 新增 Provider 仅需注册工厂，不改调用方
```

### 维度 107：自动降级链路审查（对应 R110）

**为什么**：主 Provider 不可用时需自动切换备选 Provider，否则单点故障导致整个 TTS 环节失败。降级链路按配置顺序逐个尝试，所有 Provider 失败才抛终极异常。

**配置节点**：`config.yaml#tts_fallback_chain_check`

- 【强制】主 Provider + _parse_fallback_chain() 解析配置为有序列表
- 【强制】for 循环逐个尝试，每个 Provider 失败后 continue（不中断）
- 【强制】仅在所有 Provider 均失败时 raise 终极异常（含尝试顺序信息）
- 【强制】降级成功时 logger.warning 记录（不静默，便于监控）
- 【强制】配置驱动：TTS_FALLBACK_PROVIDERS 逗号分隔，禁止硬编码降级顺序
- 【推荐】降级循环内不重复 check_budget（预算检查在循环外）

**判断信号**：
- `grep 'try.*except.*raise' backend/app/workflow/tts/` 外部服务调用无 fallback 分支 → 违规
- `grep 'TTS_FALLBACK_PROVIDERS' backend/app/` 无 _parse_fallback_chain 解析 → 违规
- `grep 'logger.warning.*降级成功' backend/app/` 无降级成功日志 → 违规

**示例**：
```python
# ✅ 正确：降级链路逐个尝试
async def synthesize_segment(text: str, voice: str = None) -> bytes:
    allowed, reason = check_budget(service_type="tts")
    if not allowed:
        raise TTSRateLimitError(f"AI 预算超限: {reason}")

    main_provider = settings.TTS_PROVIDER
    fallback_chain = _parse_fallback_chain()
    providers_to_try = [main_provider] + fallback_chain

    last_error = None
    for provider_name in providers_to_try:
        try:
            audio = await _synthesize_with_retry(provider_name, text, voice)
            if provider_name != main_provider:
                logger.warning("TTS 降级成功: 主 %s 失败，已降级到 %s", main_provider, provider_name)
            return audio
        except (TTSProviderError, TTSRateLimitError, TTSTimeoutError, TTSServiceError) as e:
            logger.warning("TTS provider %s 不可用，跳过: %s", provider_name, e)
            last_error = e
            continue

    raise TTSError(f"所有 TTS provider 均失败（尝试顺序: {providers_to_try}）: {last_error}")
```

### 维度 108：凭证 fallback 链审查（对应 R111）

**为什么**：同一云厂商多产品（腾讯云 COS/TTS/短信）可复用凭证，避免用户重复配置。凭证 fallback 链按"显式参数 → 专用配置 → 通用配置"三级优先级。

**配置节点**：`config.yaml#credentials_fallback_chain_check`

- 【强制】凭证读取按三级 fallback：显式参数 → 专用配置 → 通用配置（如 COS_SECRET_ID）
- 【强制】fallback 逻辑用 `or` 链式表达：`self._secret_id = secret_id or settings.TENCENT_TTS_SECRET_ID or settings.COS_SECRET_ID`
- 【强制】所有凭证均空时报明确错误（不能默认空字符串静默通过）
- 【推荐】配置文档明确说明 fallback 优先级

**判断信号**：
- `grep 'SECRET_ID.*=' backend/app/` 独立配置项无 fallback → 违规
- `grep 'or settings.COS_SECRET_ID' backend/app/` 缺失通用配置 fallback → 违规
- `grep 'TENCENT_TTS_SECRET_ID' backend/app/` 无 fallback 链 → 违规

### 维度 109：第三方库版本兼容性预检审查（对应 R112）

**为什么**：依赖外部服务的第三方库（如 edge-tts 依赖微软 Azure）版本过旧可能导致认证失败（如 TrustedClientToken 被封禁返回 403）。外部服务认证失败时优先怀疑库版本。

**配置节点**：`config.yaml#third_party_lib_version_check`

- 【强制】外部服务认证失败（403/401）时优先检查第三方库版本
- 【强制】requirements.txt 锁定经验证兼容的版本号
- 【强制】Windows 环境升级库时注意 cacert.pem 文件锁问题（使用 --no-deps）
- 【推荐】定期检查 PyPI 最新版本与 requirements.txt 差异

**判断信号**：
- `grep 'edge-tts\|edge_tts' backend/requirements.txt` 版本号过旧（< 7.2.8） → 违规
- `grep '403.*Forbidden\|WSServerHandshakeError' backend/` 未检查库版本 → 违规

### 维度 110：TC3-HMAC-SHA256 签名实现审查（对应 R116）

**为什么**：接入腾讯云 API 且不引入腾讯云 SDK 时，需按官方文档完整实现 TC3-HMAC-SHA256 签名算法。签名实现不完整会导致鉴权失败。

**配置节点**：`config.yaml#tencent_tc3_signature_check`

- 【强制】按官方文档逐层实现：canonical_request → string_to_sign → signature
- 【强制】使用 hmac + hashlib 标准库，禁止手写拼接遗漏步骤
- 【强制】签名算法包含：请求方法、URI、查询串、头部、payload 哈希
- 【强制】Date 头使用 UTC 时间戳（格式 YYYY-MM-DD）
- 【强制】Content-Type 为 application/json; charset=utf-8
- 【推荐】签名实现单元测试覆盖（与官方示例对比）

**判断信号**：
- `grep 'tencentcloudapi.com' backend/app/` 无 tencentcloud SDK 依赖（需手写签名） → 触发审查
- `grep 'TC3-HMAC-SHA256' backend/app/` 实现不完整（缺 canonical_request 或 string_to_sign） → 违规
- `grep 'hmac.new\|hashlib.sha256' backend/app/workflow/tts/tencent_client.py` 缺失 → 违规

### 维度 111：Pydantic Settings 类型转换注册审查（对应 R114）

**为什么**：动态配置项含 int/float 类型（如音量/语速/采样率），前端表单提交字符串需转为正确类型。未在 INT_KEYS/FLOAT_KEYS 注册会导致配置值类型错误。

**配置节点**：`config.yaml#pydantic_settings_type_check`

- 【强制】INT_KEYS/FLOAT_KEYS/SENSITIVE_KEYS 集合注册所有对应类型配置键名
- 【强制】配置写入时按集合自动转换类型（int(key_value) / float(key_value)）
- 【强制】新增配置项必须同步注册到对应集合
- 【推荐】类型转换失败时报明确错误（含字段名和期望类型）

**判断信号**：
- `grep 'float(' backend/app/services/ai_config_service.py` 配置读取处手动转换 → 违规（应通过 FLOAT_KEYS 自动转换）
- `grep 'INT_KEYS\|FLOAT_KEYS' backend/app/services/ai_config_service.py` 新增配置项未注册 → 违规
- `grep 'tencent_tts_speed\|tencent_tts_volume' backend/app/` 未在 FLOAT_KEYS 注册 → 违规

### 维度 112：tenacity + Semaphore + check_budget 三层防护审查（对应 R117）

**为什么**：外部 API 调用需要三层防护：tenacity 重试（应对瞬态失败）、Semaphore 并发控制（避免打爆 API 频率限制）、check_budget 预算检查（避免无效请求计费）。三层缺一不可。

**配置节点**：`config.yaml#external_api_three_layer_protection_check`

- 【强制】tenacity 装饰器重试可重试异常（TTSRateLimitError/TTSTimeoutError/TTSServiceError），不重试确定性失败
- 【强制】Semaphore 限制并发数（如 3），避免瞬间打爆 API 频率限制
- 【强制】check_budget 预算检查在调用前（避免无效请求打到外部 API 计费）
- 【强制】调用成功后 record_call 记录用量更新预算计数
- 【推荐】频率超限时主动等待 60s 滑动窗口滑过（而非立即抛错）

**判断信号**：
- `grep 'retry(' backend/app/workflow/tts/synthesizer.py` 无 Semaphore 或 check_budget → 违规
- `grep 'asyncio.Semaphore' backend/app/workflow/tts/` 无 check_budget → 违规
- `grep 'check_budget' backend/app/workflow/tts/` 无 record_call → 违规
- `grep 'stop_after_attempt' backend/app/` 重试不可重试异常（如 TTSProviderError） → 违规

**示例**：
```python
# ✅ 正确：三层防护完整
tts_retry = retry(
    stop=stop_after_attempt(settings.TTS_RETRY_ATTEMPTS),
    wait=wait_exponential(min=1, max=10, multiplier=1),
    retry=retry_if_exception_type((TTSRateLimitError, TTSTimeoutError, TTSServiceError)),
    before_sleep=_log_tts_retry,
    reraise=True,
)

@tts_retry
async def synthesize_segment(text: str, voice: str = None) -> bytes:
    # 第一层：预算检查
    allowed, reason = check_budget(service_type="tts")
    if not allowed:
        raise TTSRateLimitError(f"AI 预算超限: {reason}")

    # 第二层：并发控制
    sem = _get_tts_semaphore()
    async with sem:
        # 第三层：tenacity 重试（装饰器层）
        provider = get_tts_provider()
        audio = await provider.synthesize(text, voice=voice)
        record_call(service_type="tts", model=settings.ALIYUN_TTS_VOICE, char_count=len(text))
        return audio
```
> 基于 2026-07-22 AI 重新生成报错 timeout（频道提示词生成 4 段长文本超过 15s 默认超时）与频道级配置/定时任务事件驱动修复过程，按 Sequential Thinking 4 维度框架沉淀可复用的后端审查模板。新增维度 133-135（原误编为 113-115，与 V2.1 摘要列表冲突，2026-07-22 修正），对应 `channel_prompt_service.py` LLM 超时公式化、`channel_service.py` 频道级配置覆盖、`workflow_scheduler.py` 事件驱动 cron 管理。

### 维度 133：LLM 调用超时配置驱动

**审查范围**：所有调用 LLM 的 service/workflow 文件（channel_prompt_service.py、rewriter.py、translator.py 等）。

- 【强制】LLM 调用 timeout 必须从 settings 读取（`settings.LLM_TIMEOUT_SEC`），禁止硬编码
- 【强制】长耗时 LLM 调用（如生成多段文本）必须使用 `max(settings.LLM_TIMEOUT_SEC * N, MIN_SEC)` 公式，N 为预估耗时倍数
- 【强制】LLM_TIMEOUT_SEC 必须在 AI 配置服务中可配置（ai_config_service.py CONFIG_KEY_MAP 含 llm_timeout_sec）
- 【强制】用户在 AI 配置页调整 llm_timeout_sec 后，LLM 调用超时必须自动联动（无需重启）
- 【推荐】单条改写 N=1，多段生成（如频道提示词 4 段）N=2，MIN_SEC=60
- 【推荐】LLM 调用失败时必须记录 input_tokens/output_tokens 到预算系统（ai_budget.record_call）

**判断信号**：
- `grep -rn "timeout=" backend/app/services/ backend/app/workflow/ | grep -v "settings\."` → 硬编码 timeout
- `grep -rn "chat.completions.create" backend/app/ | grep -v "settings.LLM_TIMEOUT"` → 未从 settings 读取超时
- `grep -rn "llm_timeout_sec" backend/app/services/ai_config_service.py` → 确认 CONFIG_KEY_MAP 含此键

**示例**：
```python
# ❌ 反模式：硬编码 timeout，用户无法调整
resp = await client.chat.completions.create(
    model=settings.LLM_MODEL,
    messages=[...],
    timeout=30,  # 硬编码
)

# ✅ 正确：从 settings 读取，支持公式计算，用户可配置
# 频道提示词生成需产出 4 段长文本，比单条改写更耗时
# 取 LLM_TIMEOUT_SEC × 2 作为超时，避免长响应被截断
# 用户可在 AI 配置页调整 llm_timeout_sec，此处自动联动
prompt_timeout = max(settings.LLM_TIMEOUT_SEC * 2, 60)
resp = await client.chat.completions.create(
    model=settings.LLM_MODEL,
    messages=[...],
    timeout=prompt_timeout,
)
```

### 维度 134：频道级配置覆盖全局

**审查范围**：所有涉及频道级配置的 service 文件（channel_service.py、rewriter.py、crawler runner 等）。

- 【强制】service 层查询频道字段后必须优先使用频道级配置（`if ch.intro_prompt: use ch.intro_prompt else use settings default`）
- 【强制】频道字段为空时必须 fallback 到 settings 全局配置或默认值
- 【强制】频道字段变更必须通过 EventBus 发布事件（channel.active_changed/channel.schedule_changed）
- 【强制】频道级配置字段必须通过 ORM 模型定义（Channel 模型含 schedule_time/intro_prompt 等字段）
- 【强制】数据库迁移必须幂等（PRAGMA table_info 检测列存在后 ALTER TABLE）
- 【推荐】频道级配置字段变更时记录审计日志

**判断信号**：
- `grep -rn "settings\.LLM_" backend/app/workflow/llm/ | grep -v "channel"` → 未检查频道级配置
- `grep -rn "Channel\." backend/app/services/ | grep -v "schedule_time\|is_active\|intro_prompt"` → 未使用频道级字段
- `grep -rn "ALTER TABLE" backend/app/main.py | grep -v "PRAGMA"` → 迁移未做幂等检测

**示例**：
```python
# ❌ 反模式：直接使用 settings 全局配置，忽略频道级配置
async def rewrite(workflow_id, date_str, channel_id=None):
    prompt = settings.LLM_REWRITE_TEMPLATE  # 忽略频道级 template

# ✅ 正确：查询频道级配置，优先使用，为空时 fallback 到全局
async def _fetch_channel_prompts(channel_id: int | None) -> dict:
    if channel_id is None:
        return {}  # 全局工作流用默认配置
    async with AsyncSessionLocal() as session:
        ch = await session.get(Channel, channel_id)
        return {
            "intro_text": ch.intro_prompt or "",  # 频道级优先
            "outro_text": ch.outro_prompt or "",
            "constraint_text": ch.constraint_prompt or "",
            "template_text": ch.rewrite_template or "",  # 为空时 fallback 到默认
        }
```

### 维度 135：频道级定时任务事件驱动

**审查范围**：workflow_scheduler.py 及所有涉及定时任务的文件。

- 【强制】频道 schedule_time 变更必须通过 EventBus 发布 channel.schedule_changed 事件
- 【强制】频道 is_active 变更必须通过 EventBus 发布 channel.active_changed 事件
- 【强制】事件发布必须用 publish_nowait（避免阻塞主流程）
- 【强制】订阅者处理必须幂等（重复事件不产生副作用）
- 【强制】频道禁用时必须取消该频道所有 queued 工作流（is_active=0 事件处理）
- 【强制】schedule_time 清空时必须移除对应 cron 任务
- 【强制】schedule_time 非空且频道活跃时必须注册/更新 cron 任务
- 【推荐】cron 任务配置 misfire_grace_time/coalesce/max_instances=1/replace_existing=True

**判断信号**：
- `grep -rn "schedule_time" backend/app/services/channel_service.py | grep -v "publish"` → 变更未发布事件
- `grep -rn "is_active" backend/app/services/channel_service.py | grep -v "publish"` → 变更未发布事件
- `grep -rn "bus.publish_nowait\|bus.publish" backend/app/services/ | grep -v "channel"` → 未发布频道事件
- `grep -rn "subscribe.*channel" backend/app/services/workflow_scheduler.py` → 确认订阅频道事件

**示例**：
```python
# ❌ 反模式：频道字段变更未发布事件，定时任务不更新
async def update_channel(self, channel_id: int, data: dict):
    ch = await self.db.get(Channel, channel_id)
    if "schedule_time" in data:
        ch.schedule_time = data["schedule_time"]  # 无事件发布
    await self.db.commit()

# ✅ 正确：频道字段变更发布事件，订阅者重注册 cron
async def update_channel(self, channel_id: int, data: dict):
    ch = await self.db.get(Channel, channel_id)
    schedule_changed = "schedule_time" in data and data["schedule_time"] != ch.schedule_time
    active_changed = "is_active" in data and data["is_active"] != ch.is_active
    # ... 更新字段
    await self.db.commit()
    if schedule_changed:
        self._publish_schedule_changed(channel_id, data["schedule_time"], ch.is_active)
    if active_changed:
        self._publish_active_changed(channel_id, ch.is_active)
```


---


### 维度 119：Pydantic Body 字段声明完整性（对应 R144 后端侧）

**审查范围**：所有 FastAPI 路由中接收 Body 参数的 Pydantic 模型（`*Body`/`*Request`/`*Create`/`*Update` 等）。

- 【强制】Pydantic Body 模型必须声明前端已提交的所有字段，不得依赖 `extra='ignore'` 默认行为静默丢弃
- 【强制】新增前端表单字段时，必须同步在对应 Body 模型中声明字段名和类型
- 【强制】Body 模型字段必须有合理的默认值和校验约束（`Field(default, ge=, le=)`）
- 【强制】配置类 Body 模型（如 LLMConfigBody）字段集必须与 CONFIG_KEY_MAP 中的键完全对齐
- 【推荐】Body 模型应使用 `model_config = ConfigDict(extra='forbid')` 替代默认的 `extra='ignore'`，在开发阶段尽早发现未声明字段
- 【推荐】Body 模型字段变更时必须同步更新 API 文档（Swagger 自动生成但需验证）

**判断信号**：
- `grep -rn "class.*Body.*BaseModel\|class.*Request.*BaseModel" backend/app/routers/` → 提取所有 Body 模型
- `grep -rn "extra.*=.*ignore\|extra.*=.*forbid" backend/app/` → 检查 extra 策略
- 对比前端 form 字段集与后端 Body 模型字段集差异

**示例**：
```python
# ❌ 反模式：Body 模型缺少 target_duration_sec 字段声明，前端提交后被静默丢弃
class LLMConfigBody(BaseModel):
    model: str = "qwen-turbo"
    # 缺少 target_duration_sec → Pydantic extra='ignore' 静默丢弃
    temperature: float = 0.7

# ✅ 正确：声明所有前端提交的字段，含校验约束
class LLMConfigBody(BaseModel):
    model: str = "qwen-turbo"
    target_duration_sec: int = Field(600, ge=60, le=1800)  # 必须声明
    temperature: float = Field(0.7, ge=0.0, le=2.0)

# ✅ 推荐：开发阶段使用 extra='forbid' 尽早发现未声明字段
class LLMConfigBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model: str = "qwen-turbo"
    target_duration_sec: int = Field(600, ge=60, le=1800)
```

### 维度 120：配置键四端一致性（对应 R147 后端侧）

**审查范围**：config.py 中 CONFIG_KEY_MAP/LEGACY_KEY_MAP、Pydantic Body 模型字段名、数据库 settings 表键名、前端 form 字段名。

- 【强制】配置键命名必须四端一致：前端 form 字段名 ↔ 后端 Body 模型字段名 ↔ CONFIG_KEY_MAP 键名 ↔ 数据库 settings 表 key 字段
- 【强制】配置键命名不得混用前缀风格（如 `edge_tts_voice` 与 `edge_voice` 不得混用，必须统一为一种前缀）
- 【强制】新增配置项时必须同时更新四端：前端 form + 后端 Body + CONFIG_KEY_MAP + 数据库
- 【强制】配置键变更时必须添加 LEGACY_KEY_MAP 兼容映射，确保旧配置平滑迁移
- 【推荐】配置键命名应使用 `provider_feature_field` 格式（如 `edge_tts_voice`、`aliyun_tts_voice`）

**判断信号**：
- `grep -rn "CONFIG_KEY_MAP\|LEGACY_KEY_MAP" backend/app/config.py` → 提取配置键映射
- `grep -rn "edge_tts_\|edge_" backend/app/config.py | grep -v "#"` → 检查前缀风格混用
- 对比 CONFIG_KEY_MAP 键名与 Body 模型字段名是否完全一致

**示例**：
```python
# ❌ 反模式：配置键前缀混用，edge_tts_* 与 edge_* 混合存在
CONFIG_KEY_MAP = {
    "edge_tts_voice": "edge_voice",      # 前缀不一致
    "edge_tts_rate": "edge_rate",        # 前缀不一致
    "aliyun_tts_voice": "aliyun_voice",  # 统一前缀
}

# ✅ 正确：统一前缀风格，四端一致
CONFIG_KEY_MAP = {
    "edge_tts_voice": "edge_tts_voice",   # 统一 edge_tts_ 前缀
    "edge_tts_rate": "edge_tts_rate",     # 统一 edge_tts_ 前缀
    "aliyun_tts_voice": "aliyun_tts_voice",
}

# ✅ 正确：配置键变更时添加 LEGACY_KEY_MAP 兼容
LEGACY_KEY_MAP = {
    "edge_voice": "edge_tts_voice",  # 旧键 → 新键
    "edge_rate": "edge_tts_rate",
}
```

### 维度 121：工作流时间本地化后端存储（对应 R148 后端侧）

**审查范围**：所有 ORM 模型中的时间字段（created_at/updated_at/started_at/finished_at）、COS 写入时间戳、SQLite upsert 时间字段。

- 【强制】后端时间存储必须使用 `utcnow_naive()`（本地 naive datetime），不得混用 `datetime.now(timezone.utc)` 和 `datetime.now()`
- 【强制】ORM 模型 `server_default=func.now()` 必须配合应用层本地化写入，不得依赖数据库默认值
- 【强制】COS 写入的时间戳必须与 SQLite upsert 的时间戳来源一致（同一 `utcnow_naive()` 调用）
- 【强制】API 返回的时间字段必须标注时区或使用 ISO 8601 格式（含时区偏移）
- 【推荐】时间字段查询时应统一使用 naive datetime 比较，避免 timezone-aware 与 naive 混用报错

**判断信号**：
- `grep -rn "datetime.now(timezone.utc)\|datetime.utcnow()" backend/app/` → 使用了 UTC 时间（应改用 utcnow_naive）
- `grep -rn "datetime.now()" backend/app/ | grep -v "utcnow_naive"` → 使用了本地时间但未通过统一函数
- `grep -rn "server_default=func.now()" backend/app/models/ | grep -v "utcnow_naive"` → 依赖数据库默认值未配合应用层

**示例**：
```python
# ❌ 反模式：混用 UTC 和本地时间，导致时间比较和显示不一致
from datetime import datetime, timezone

async def create_workflow():
    wf = Workflow(
        created_at=datetime.now(timezone.utc),  # UTC aware
        updated_at=datetime.now(),               # 本地 naive → 混用报错
    )

# ✅ 正确：统一使用 utcnow_naive()
from app.utils.time_utils import utcnow_naive

async def create_workflow():
    now = utcnow_naive()  # 统一时间来源
    wf = Workflow(
        created_at=now,
        updated_at=now,
    )
    # COS 写入使用同一时间戳
    await cos_client.put_object(
        key=f"episodes/{now.strftime('%Y%m%d')}/...",
        timestamp=now.isoformat(),
    )
```

### 维度 122：预设配置 JSON 存储与恢复

**审查范围**：AI 配置预设（presets）、通知配置预设等 JSON 格式存储的配置集合。

- 【强制】预设配置必须以 JSON 格式存储在数据库或配置文件中，不得硬编码在源码中
- 【强制】预设配置 JSON 必须包含完整的配置键值对，不得部分省略
- 【强制】预设切换时必须完整覆盖目标配置，不得遗漏字段（特别是 API Key 等敏感字段）
- 【强制】预设配置 JSON schema 必须与 Body 模型字段集对齐
- 【推荐】预设配置应支持版本号，便于升级时迁移
- 【推荐】预设配置应支持导入/导出功能

**判断信号**：
- `grep -rn "preset.*=.*{" backend/app/ | grep -v "json\|JSON\|config"` → 预设硬编码在源码中
- `grep -rn "PRESETS\|presets" backend/app/ | grep -v "\.json\|database\|db"` → 预设未存储在数据库/JSON 文件中
- 对比预设 JSON 字段集与 Body 模型字段集差异

### 维度 123：恢复初始配置端点完整性

**审查范围**：所有提供"恢复默认"/"重置配置"功能的 API 端点。

- 【强制】恢复初始配置端点必须重置所有配置字段为默认值，不得遗漏新增字段
- 【强制】恢复初始配置后必须返回完整的配置对象（含所有字段），前端据此刷新表单
- 【强制】恢复初始配置端点必须有操作日志记录（谁、何时、重置了什么配置）
- 【强制】恢复初始配置不得删除 API Key 等敏感凭证（应保留或单独确认）
- 【推荐】恢复初始配置应支持选择性重置（如仅重置 LLM 配置、仅重置 TTS 配置）

**判断信号**：
- `grep -rn "reset.*config\|restore.*default\|init.*config" backend/app/routers/` → 提取恢复配置端点
- `grep -rn "DEFAULT_CONFIG\|default_config" backend/app/ | grep -v "test"` → 检查默认配置定义完整性
- 对比恢复端点返回的字段集与 Body 模型字段集差异


---


> 基于近期后端代码迭代中暴露的 6 类高频故障复盘（FileResponse 拦截器误处理、工作流重跑语义混淆、CONFIG_KEY_MAP 内部映射不一致、测试时间基线漂移、SQLite 外键 PRAGMA 依赖、凭证脱敏正则丢失 key 名），按「检查项 + 判断标准 + 修复建议」三元组结构沉淀可复用的后端审查模板。新增维度 124-129，所有阈值、关键词清单、扫描目录均通过 `config.yaml` 对应节点管理，禁止硬编码业务值。

### 维度 124：响应拦截器特殊响应类型处理（FileResponse 场景）

**审查范围**：所有返回二进制数据（文件流/音频流/视频流/图片流）的 API 端点。

**检查项**：后端使用 `FileResponse` / `StreamingResponse` 返回二进制数据时，前端是否能正确处理；错误路径（如文件不存在）是否返回正确的 HTTP 状态码。

**判断标准**：

- 【强制】`FileResponse` / `StreamingResponse` 必须显式设置 `media_type`（如 `audio/mpeg` / `application/octet-stream`），禁止依赖自动推断
- 【强制】二进制响应必须直接返回文件流，禁止包装在 `{code, message, data}` 格式中（前端拦截器对二进制响应无法解析 JSON 包装层）
- 【强制】文件不存在的错误必须返回 HTTP 404（通过 `raise HTTPException(status_code=404)` 或自定义异常映射到 404），禁止返回 HTTP 200 + `{code: error, message: "..."}` 格式
- 【强制】文件接口的 `NotFoundError` 异常必须映射到 HTTP 404 而非 200，前端通过 `error.response.status === 404` 区分处理路径
- 【推荐】下载接口应通过 `Content-Disposition: attachment; filename="xxx"` 提示浏览器下载行为

**判断信号**：

- `grep -rn "FileResponse\|StreamingResponse" backend/app/routers/` → 提取所有二进制响应端点
- `grep -rn "FileResponse.*media_type=None\|StreamingResponse.*media_type=None" backend/app/` → 未设置 media_type
- `grep -rn "success.*FileResponse\|return.*success.*data.*file" backend/app/` → 二进制响应被包装在 success() 中（违规）
- `grep -rn "NotFoundError.*raise\|raise.*NotFoundError" backend/app/` → 检查 NotFoundError 异常映射
- `grep -rn "status_code=200.*not_found\|return.*error.*not_found" backend/app/` → NotFound 错误返回 200（违规）

**修复建议**：

```python
# ❌ 反模式：FileResponse 包装在 success() 中，前端拦截器无法解析
@router.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    audio_path = await _get_audio_path(audio_id)
    if not audio_path:
        return error(message="音频不存在")  # 返回 200 + {code: error}，前端误判为成功
    return success(data=FileResponse(audio_path))  # 二进制被 JSON 包装，前端无法播放

# ✅ 正确：FileResponse 直接返回，错误用 HTTP 404
@router.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    audio_path = await _get_audio_path(audio_id)
    if not audio_path:
        raise HTTPException(status_code=404, detail="音频不存在")  # 前端通过 status code 判断
    return FileResponse(audio_path, media_type="audio/mpeg")  # 直接返回文件流
```

适用场景：所有返回二进制数据（文件下载、音频流、视频流、图片流）的 API 端点
不适用场景：JSON 响应（默认走 success() 包装）；纯文本响应

---

### 维度 125：工作流重跑/重试语义验证（断点续跑模式）

**审查范围**：`workflow_scheduler.py` 中 `retry_workflow` / `rerun_workflow` / `resume_workflow` 等方法。

**检查项**：`retry_workflow` 方法是否在原工作流上执行（断点续跑模式）而非创建新工作流（从头执行模式）。

**判断标准**：

- 【强制】`retry_workflow` 必须接受 `from_step` 参数（指定从哪个步骤开始重跑）
- 【强制】必须删除 `from_step` 及其之后的所有步骤记录（含 `failed` 状态记录），避免重复执行
- 【强制】必须保留 `from_step` 之前的所有 `success` 状态步骤记录及其产物（如 LLM 改写结果、TTS 音频路径）
- 【强制】必须校验前驱步骤（`from_step` 的前一步）状态为 `success` 且有 `result` 字段，否则拒绝重跑并提示
- 【强制】必须重置工作流状态为 `queued`，清空 `error` 和 `finished_at` 字段
- 【强制】入队时使用当前 `workflow_id`（不创建新工作流），禁止调用 `trigger_workflow` 创建新工作流
- 【推荐】日志中记录 `workflow_id` / `from_step` / 保留的步骤清单，便于审计

**判断信号**：

- `grep -rn "def retry_workflow\|def rerun_workflow\|def resume_workflow" backend/app/services/workflow_scheduler.py` → 提取重跑方法
- `grep -rn "retry_workflow.*trigger_workflow\|retry.*create.*workflow" backend/app/` → 重跑创建新工作流（违规）
- `grep -rn "from_step" backend/app/services/workflow_scheduler.py` → 检查 from_step 参数是否存在
- `grep -rn "delete.*workflow_step.*from_step\|delete.*WorkflowStep.*seq.*>=" backend/app/` → 检查是否删除 from_step 及之后记录
- `grep -rn "update.*workflow.*status.*queued\|update.*workflow.*error.*None" backend/app/` → 检查状态重置

**修复建议**：

```python
# ❌ 反模式：retry_workflow 创建新工作流，浪费已成功的 LLM/TTS 配额
async def retry_workflow(self, workflow_id: str):
    old_wf = await self._get_workflow(workflow_id)
    new_wf = await self.trigger_workflow(  # 创建新工作流，从头执行
        episode_date=old_wf.episode_date,
        channel_id=old_wf.channel_id,
    )
    return new_wf.id

# ✅ 正确：断点续跑模式——删除失败步骤 + 重置状态 + 入队当前 workflow_id
async def retry_workflow(self, workflow_id: str, from_step: str) -> str:
    # 1. 校验前驱步骤
    predecessor = await self._get_predecessor_step(workflow_id, from_step)
    if not predecessor or predecessor.status != "success" or not predecessor.result:
        raise BizError(f"前驱步骤 {predecessor.step_name} 未成功或无产物，无法从 {from_step} 续跑")

    # 2. 删除 from_step 及其之后的步骤记录（含 failed 记录）
    await self.db.execute(
        delete(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .where(WorkflowStep.seq >= from_step_seq)
    )

    # 3. 重置工作流状态
    await self.db.execute(
        update(Workflow)
        .where(Workflow.id == workflow_id)
        .values(status="queued", error=None, finished_at=None)
    )
    await self.db.commit()

    # 4. 入队当前 workflow_id（不创建新工作流）
    await self.queue.put(workflow_id)
    logger.info("workflow_id=%s retry from_step=%s preserved_steps=%s",
                workflow_id, from_step, preserved_step_names)
    return workflow_id
```

适用场景：所有支持断点续跑的工作流（LLM 改写、TTS 合成、视频拼接等多步骤工作流）
不适用场景：无状态的请求重试（如 HTTP 调用重试）；需要从头执行的场景（应使用 `trigger_workflow` 而非 `retry_workflow`）

---

### 维度 126：config_key 与 Settings 属性名映射一致性

**审查范围**：服务层 `CONFIG_KEY_MAP` 字典、`_normalize_xxx` 函数、`get_config_for_frontend` 函数、`SENSITIVE_KEYS` / `INT_KEYS` / `FLOAT_KEYS` 集合。

**检查项**：`CONFIG_KEY_MAP` 的 key 是否与路由层 BaseModel 字段名、前端字段名一致；value 是否与 Settings 属性名一致；`_normalize_xxx` 与 `get_config_for_frontend` 返回的 key 是否与 `CONFIG_KEY_MAP` 的 key 对齐。

**判断标准**：

- 【强制】`CONFIG_KEY_MAP` 的 key（对外暴露的配置名）= 路由层 BaseModel 字段名 = 前端表单字段名
- 【强制】`CONFIG_KEY_MAP` 的 value 必须是 `Settings` 类中已定义的属性名（`getattr(settings, value)` 必须成功）
- 【强制】`_normalize_xxx` 函数返回的 `result` 字典的 key 必须与 `CONFIG_KEY_MAP` 的 key 完全一致
- 【强制】`get_config_for_frontend` 函数返回的字段名必须与 `CONFIG_KEY_MAP` 的 key 完全一致
- 【强制】`SENSITIVE_KEYS` / `INT_KEYS` / `FLOAT_KEYS` 集合中的元素必须使用与 `CONFIG_KEY_MAP` 的 key 相同的命名（不得混用前缀风格）
- 【强制】配置键命名不得混用前缀风格（如 `provider_feature_field` 与 `feature_field` 不得混用，必须统一为一种前缀风格）
- 【推荐】`CONFIG_KEY_MAP` 作为"单一真相源"，新增配置项时必须同步更新 `SENSITIVE_KEYS` / `INT_KEYS` / `FLOAT_KEYS`（如适用）

**判断信号**：

- `grep -rn "CONFIG_KEY_MAP\s*=" backend/app/services/` → 提取 CONFIG_KEY_MAP 定义
- `grep -rn "def _normalize_\|def get_config_for_frontend" backend/app/services/` → 提取归一化与前端读取函数
- `grep -rn "SENSITIVE_KEYS\s*=\|INT_KEYS\s*=\|FLOAT_KEYS\s*=" backend/app/services/` → 提取类型/敏感键集合
- 对比 `CONFIG_KEY_MAP` 的 key 与 Settings 类的属性名（grep `class Settings` 后逐一比对）
- 对比 `_normalize_xxx` 返回的 key 与 `CONFIG_KEY_MAP` 的 key 是否完全一致
- `grep -rn "edge_tts_\|edge_" backend/app/services/ai_config_service.py | grep -v "#"` → 检查前缀风格混用

**修复建议**：

```python
# ❌ 反模式：CONFIG_KEY_MAP key 与 _normalize_xxx 返回的 key 不一致
CONFIG_KEY_MAP = {
    "tts_voice": "TTS_VOICE",  # 对外名为 tts_voice
}

def _normalize_tts(config: dict) -> dict:
    return {
        "voice": config.get("tts_voice"),  # 返回 key 为 voice，与 CONFIG_KEY_MAP 不一致
    }

def get_config_for_frontend() -> dict:
    return {
        "tts_voice_value": settings.TTS_VOICE,  # 返回 key 为 tts_voice_value，与 CONFIG_KEY_MAP 不一致
    }

# ✅ 正确：CONFIG_KEY_MAP 作为单一真相源，所有函数返回的 key 与其完全一致
CONFIG_KEY_MAP = {
    "tts_voice": "tts_voice",  # 对外名 = Settings 属性名（统一命名）
}

def _normalize_tts(config: dict) -> dict:
    return {
        "tts_voice": config.get("tts_voice"),  # 与 CONFIG_KEY_MAP key 一致
    }

def get_config_for_frontend() -> dict:
    return {
        "tts_voice": getattr(settings, "tts_voice", None),  # 与 CONFIG_KEY_MAP key 一致
    }

# ✅ 正确：SENSITIVE_KEYS / INT_KEYS / FLOAT_KEYS 使用与 CONFIG_KEY_MAP 相同的命名
SENSITIVE_KEYS = {"tts_api_key", "llm_api_key"}  # 与 CONFIG_KEY_MAP key 命名一致
INT_KEYS = {"tts_timeout_sec", "llm_max_tokens"}
FLOAT_KEYS = {"tts_speed", "tts_volume"}
```

适用场景：所有使用 `CONFIG_KEY_MAP` 集中管理配置键的服务层（AI 配置、TTS 配置、通知配置等）
不适用场景：无 CONFIG_KEY_MAP 的简单配置读取（直接通过 settings 属性访问）；前端表单字段（前端字段名应与 CONFIG_KEY_MAP key 对齐，但本维度聚焦后端内部一致性）

注：本维度与维度 120（配置键四端一致性）互补——维度 120 强调"四端字段名对齐（前端/后端 Body/CONFIG_KEY_MAP/数据库）"，本维度强调"CONFIG_KEY_MAP 内部映射逻辑一致性（key ↔ value ↔ normalize_xxx ↔ get_config_for_frontend ↔ 类型集合）"。

---

### 维度 127：测试时间基线与生产代码对齐

**审查范围**：所有测试文件（`backend/tests/**/*.py`）中涉及时间获取与时间断言的代码。

**检查项**：测试代码的时间获取方式是否与生产代码一致；时间断言是否使用近似比较而非精确等于。

**判断标准**：

- 【强制】生产代码使用 `utcnow_naive()`（返回本地 naive datetime）时，测试代码必须使用 `datetime.now()`（本地时间），禁止使用 `datetime.utcnow()` 或 `datetime.now(timezone.utc)` 与本地时间混用
- 【强制】禁止测试代码中使用 `datetime.utcnow()` 全文搜索匹配后替换为 `datetime.now()`
- 【强制】时间比较必须使用近似断言（`abs(actual - expected) < timedelta(seconds=epsilon)`），禁止使用精确等于（`==`）
- 【强制】时间字段断言必须考虑数据库存储精度（SQLite 默认秒级精度，MySQL 默认微秒级精度），跨数据库测试需用更大的 epsilon
- 【推荐】测试 fixture 提供 `frozen_time` / `time_machine` 等时间冻结工具，避免测试用例间时间漂移
- 【推荐】时间断言 epsilon 通过 `config.yaml#test_time_baseline_alignment_check.time_epsilon_sec` 配置

**判断信号**：

- `grep -rn "datetime\.utcnow\(\)" backend/tests/` → 测试代码使用 UTC 时间（违规）
- `grep -rn "datetime\.now(timezone\.utc)" backend/tests/` → 测试代码使用 UTC aware 时间（违规）
- `grep -rn "assert.*==.*datetime\|assert.*datetime.*==" backend/tests/` → 时间精确等于断言（违规）
- `grep -rn "assert.*abs(.*-.*)\s*<\s*timedelta" backend/tests/` → 近似断言（正确）
- 对比生产代码时间获取方式与测试代码时间获取方式是否一致

**修复建议**：

```python
# ❌ 反模式：测试用 datetime.utcnow()，与生产代码 utcnow_naive() 产生 8 小时偏差
from datetime import datetime, timezone

async def test_workflow_created_at():
    wf = await create_workflow()
    assert wf.created_at == datetime.utcnow()  # 与生产代码 utcnow_naive() 偏差 8 小时

# ❌ 反模式：时间精确等于断言，datetime.now() 调用间隔导致微小偏差
async def test_workflow_created_at():
    before = datetime.now()
    wf = await create_workflow()
    after = datetime.now()
    assert wf.created_at == before  # create_workflow 内部调用 datetime.now() 与 before 不在同一瞬间

# ✅ 正确：测试用 datetime.now()（与生产代码 utcnow_naive() 时区一致）+ 近似断言
from datetime import datetime, timedelta

async def test_workflow_created_at():
    before = datetime.now()
    wf = await create_workflow()
    after = datetime.now()
    # epsilon 容忍数据库存储精度与 datetime.now() 调用间隔
    epsilon = timedelta(seconds=2)
    assert before - epsilon <= wf.created_at <= after + epsilon

# ✅ 推荐：使用时间冻结 fixture 避免时间漂移
@pytest.fixture
def frozen_time():
    """冻结时间，测试用例内 datetime.now() 返回固定值"""
    fixed_time = datetime(2026, 7, 22, 12, 0, 0)
    with freeze_time(fixed_time):
        yield fixed_time

async def test_workflow_created_at(frozen_time):
    wf = await create_workflow()
    assert wf.created_at == frozen_time  # 时间冻结后可精确等于
```

适用场景：所有涉及时间字段的单元测试、集成测试、回归测试
不适用场景：纯计算字段测试（无时间）；mock 时间返回固定值的测试（已通过 mock 控制时间）

注：本维度与维度 38（时区一致性跨模块对齐）、维度 121（工作流时间本地化后端存储）互补——维度 38/121 强调"生产代码时区一致"，本维度强调"测试代码与生产代码时区基线对齐"。

---

### 维度 128：外键操作防御性处理

**审查范围**：所有 ORM 删除操作（`db.delete(obj)` / `db.execute(delete(Model))`）。

**检查项**：删除父记录时是否手动处理子表外键（UPDATE 为 NULL 或显式级联删除），是否依赖 SQLite `PRAGMA foreign_keys` 开关。

**判断标准**：

- 【强制】删除父记录前必须先 `UPDATE` 子表外键为 `NULL`（或显式 `DELETE` 子表记录），不得依赖数据库自动级联
- 【强制】禁止依赖 `PRAGMA foreign_keys = ON` 开关（SQLite 默认关闭，MySQL 默认开启，环境不一致会导致行为漂移）
- 【强制】测试环境与生产环境的删除行为必须一致（不依赖 PRAGMA 开关切换）
- 【强制】删除父记录的事务必须包含子表外键处理（同一事务内完成 UPDATE + DELETE，避免事务中途失败产生孤儿记录）
- 【推荐】删除父记录前先查询子表引用计数，引用计数 > 0 时提示用户或阻止删除（避免误删）
- 【推荐】子表外键列应使用 `ondelete="SET NULL"` 或 `ondelete="CASCADE"` 作为兜底，但不得作为唯一保障

**判断信号**：

- `grep -rn "db\.delete\(\|db\.execute(delete(" backend/app/services/ | grep -v "update\|UPDATE" ` → 删除操作无前置 UPDATE
- `grep -rn "PRAGMA foreign_keys\|foreign_keys\s*=\s*ON" backend/app/` → 依赖 PRAGMA 开关（违规）
- `grep -rn "ondelete=\"SET NULL\"\|ondelete=\"CASCADE\"" backend/app/models/` → 检查外键 ondelete 配置
- `grep -rn "delete(Model).*\n.*delete(ChildModel)" backend/app/services/` → 检查是否在同一事务内处理子表

**修复建议**：

```python
# ❌ 反模式：删除父记录时不处理子表外键，依赖 PRAGMA foreign_keys 自动级联
async def delete_workflow(workflow_id: str):
    wf = await db.get(Workflow, workflow_id)
    await db.delete(wf)  # 子表 material.workflow_id 残留为孤儿记录
    await db.commit()
    # SQLite 默认 PRAGMA foreign_keys=OFF，子表不级联，产生孤儿记录锁死后续流程

# ❌ 反模式：依赖 PRAGMA foreign_keys = ON 开关
async def init_db():
    await db.execute(text("PRAGMA foreign_keys = ON"))  # 依赖开关，环境切换会失效
    # ...

# ✅ 正确：删除父记录前先 UPDATE 子表外键为 NULL（或显式 DELETE 子表）
async def delete_workflow(workflow_id: str):
    # 1. 先 UPDATE 子表外键为 NULL（保留子表记录，重置关联）
    await db.execute(
        update(Material)
        .where(Material.workflow_id == workflow_id)
        .values(workflow_id=None, status="pending")
    )
    # 2. 显式 DELETE 子表记录（如 WorkflowStep）
    await db.execute(
        delete(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
    )
    # 3. 最后 DELETE 父记录
    wf = await db.get(Workflow, workflow_id)
    await db.delete(wf)
    await db.commit()  # 同一事务内完成 UPDATE + DELETE
```

适用场景：所有 ORM 删除操作（特别是 SQLite 环境、跨数据库环境、子表存在外键引用的场景）
不适用场景：无外键引用的独立表；数据库强一致约束的环境（如 PostgreSQL + ON DELETE CASCADE 强制开启）

注：本维度与维度 39（主从表级联清理完整性）、维度 67（应用层级联删除策略）互补——维度 39 强调"删除主表时同步处理从表避免孤儿记录"，维度 67 强调"应用层级联可精细控制 cascade + set_null"，本维度强调"不依赖 PRAGMA foreign_keys 开关，必须应用层主动处理"。

---

### 维度 129：凭证脱敏正则验证

**审查范围**：所有日志输出、错误信息、响应体中涉及凭证（token / secret / key / password / appkey 等）的脱敏处理。

**检查项**：脱敏正则是否使用捕获组保留 key 名；脱敏后的文本是否仍可辨识是哪个字段。

**判断标准**：

- 【强制】脱敏正则必须使用捕获组保留 key 名，禁止整体替换为 `***`
- 【强制】脱敏正则模式：`(?i)((?:关键词清单)\s*[:=]\s*)\S+`，其中关键词清单通过 `config.yaml#credential_masking_regex_check.sensitive_keywords` 配置
- 【强制】替换字符串必须为 `m.group(1) + "***"` 或 `r"\1***"`，保留 key 名便于诊断
- 【强制】脱敏后的文本必须仍可辨识字段名（如 `token=***` / `api_key: ***`），禁止替换为裸 `***`
- 【强制】脱敏正则必须大小写不敏感（`(?i)` 前缀），覆盖 `Token` / `TOKEN` / `token` 等变体
- 【推荐】脱敏函数应提供 `mask_sensitive(text: str) -> str` 统一入口，禁止散落在多处
- 【推荐】关键词清单通过 `config.yaml` 管理，禁止硬编码在业务代码中

**判断信号**：

- `grep -rn "re\.sub\(.*token\|re\.sub\(.*secret\|re\.sub\(.*password" backend/app/` → 提取脱敏正则
- `grep -rn "re\.sub\(.*['\"]\\*\\*\\*['\"]" backend/app/` → 整体替换为 `***`（违规）
- `grep -rn "re\.sub\(.*group\(1\)\|re\.sub\(.*\\\\1" backend/app/` → 使用捕获组保留 key 名（正确）
- `grep -rn "mask_sensitive\|_mask_credential\|sanitize" backend/app/` → 提取脱敏函数入口
- `grep -rn "(?:token\|secret\|key\|password\|appkey)" backend/app/` → 检查关键词清单是否硬编码

**修复建议**：

```python
# ❌ 反模式：整体替换为 ***，丢失 key 名，无法辨识是哪个字段
import re

def mask_sensitive(text: str) -> str:
    # 整体替换为 ***，日志中只剩 ***，无法区分是 token 还是 password
    return re.sub(r'token=\S+|password=\S+', '***', text)
    # 输出：***（无法辨识字段名）

# ❌ 反模式：硬编码关键词清单，未通过 config 管理
def mask_sensitive(text: str) -> str:
    pattern = r'(?i)(token|secret|key|password|appkey)\s*[:=]\s*\S+'
    return re.sub(pattern, r'\1=***', text)
    # 关键词清单硬编码，新增关键词需改代码

# ✅ 正确：捕获组保留 key 名 + 关键词清单通过 config 管理
import re
from app.config import get_settings

def mask_sensitive(text: str) -> str:
    """脱敏敏感信息，保留 key 名便于诊断。

    为什么要保留 key 名：日志中需要辨识是哪个字段被脱敏（如 token=*** vs password=***），
    便于排查问题时定位是哪个凭证失效。整体替换为 *** 会让日志变成 *** *** ***，无法区分。
    """
    cfg = get_settings().CREDENTIAL_MASKING_REGEX_CHECK
    keywords = "|".join(cfg["sensitive_keywords"])  # 配置驱动关键词清单
    pattern = rf'(?i)((?:{keywords})\s*[:=]\s*)\S+'
    return re.sub(pattern, r'\1***', text)
    # 输出：token=*** / api_key=*** / password=***（保留 key 名）

# ✅ 正确：脱敏后的日志可辨识字段名
logger.info("请求参数: %s", mask_sensitive(f"token={api_key}&user={user}"))
# 输出：请求参数: token=***&user=admin
```

适用场景：所有日志输出、错误信息、响应体中涉及凭证（token / secret / key / password / appkey 等）的脱敏处理
不适用场景：非凭证字段的日志（如 user_id / episode_id 等业务字段无需脱敏）；测试 mock 数据（无需脱敏）

注：本维度与维度 8（安全）、维度 60（API Key 脱敏值回传检测）互补——维度 8 强调"敏感信息不得记录到日志"（原则层），维度 60 强调"返回前端前必须脱敏"（接口层），本维度强调"脱敏正则的实现质量"（实现层）。

---


> 来源：2026-07-27 至 2026-07-31 多个历史对话复盘，对应 news-code-dev 元规范 R172/R173/R176/R178/R181/R183/R185。本次新增 7 个后端审查维度 J-P，覆盖配置导入、统一响应测试断言、文件上传安全、UNIQUE 约束兜底、工作流 0 结果阻断、HTTP 编码探测、风格库轮换。

### J. V2.9：2026-07-31 Pydantic Settings 单例导入审查

> 来源：2026-07-31 微信登录修复复盘（规范 R172）。直接导入 settings 实例可能导致配置未加载时就触发实例化。

**配置节点**：`config.yaml#review_dimensions` → `pydantic_settings_singleton_import`

- 【强制】backend/app/ 下所有模块导入配置必须使用 `get_settings()` 工厂函数，禁止直接 `from app.config import settings`
- 【强制】模块级使用配置时必须 `from app.config import get_settings` + `settings = get_settings()`
- 不适用：测试代码（用 fixture 注入）、scripts/ 下独立脚本
- 判断信号：
  - grep `from app.config import settings`（直接导入实例）→ 违规
  - grep `from app.config import get_settings` 后无 `settings = get_settings()` → 违规
- 严重级别：HIGH（直接导入可能在配置未加载时触发实例化，导致 ImportError 或配置缺失）

### K. V2.9：2026-07-31 统一响应模式测试断言对齐审查

> 来源：2026-07-31 历史对话复盘（规范 R173）。项目统一响应模式中 BizError 返回 HTTP 200 + JSON body {code: 非0}，按标准 RESTful 断言 HTTP 4xx 会导致假失败。

**配置节点**：`config.yaml#review_dimensions` → `unified_response_test_assertion`

- 【强制】调用返回统一响应格式 API 的测试，必须断言 `resp.status_code == 200` + `resp.json()["code"] == 期望错误码`，禁止断言 `== 400` 或 `== 422`
- 不适用：HTTP 异常端点（如 `/health/ready` 返回 503）、文件上传 multipart 响应
- 判断信号：
  - grep 测试代码中 `assert resp.status_code == 400` 或 `== 422` → 违规
  - grep 测试代码中断言 HTTP 4xx 但未检查 `resp.json()["code"]` → 违规
- 严重级别：HIGH（断言模式不对齐会导致假失败，掩盖真实问题）

### L. V2.9：2026-07-31 文件上传安全双重校验审查

> 来源：2026-07-31 历史对话复盘（规范 R176）。仅校验扩展名可被伪造（改后缀绕过），需扩展名 + content_type 双重校验。

**配置节点**：`config.yaml#review_dimensions` → `file_upload_security`

- 【强制】所有文件上传接口（头像/封面/BGM/附件）必须实施扩展名白名单 + content_type 双重校验 + 大小上限 + 流式写入
- 【强制】扩展名与 content_type 必须匹配（如 `.jpg` ↔ `image/jpeg`）
- 【强制】文件名用 `user_id + timestamp` 命名，避免路径穿越
- 不适用：纯文本/JSON 接口
- 判断信号：
  - grep `UploadFile` 无扩展名白名单检查（`_ALLOWED_EXTS` 或 `allowed_extensions`）→ 违规
  - grep `UploadFile` 无 `content_type` 校验 → 违规
  - grep `await file.read()` 一次性读取（非流式）且无大小累计 → 违规
- 严重级别：CRITICAL（安全漏洞，可上传可执行文件）

### M. V2.9：2026-07-31 UNIQUE 约束冲突 IntegrityError 兜底审查

> 来源：2026-07-31 历史对话复盘（规范 R178）。dedup TTL 清理后仍可能残留记录，并发写入时 UNIQUE 约束冲突是预期场景而非错误。

**配置节点**：`config.yaml#review_dimensions` → `unique_integrity_error_fallback`

- 【强制】所有涉及 UNIQUE 约束的数据库写入（material.url / user.openid 等）必须捕获 `IntegrityError` 并做兜底处理
- 【强制】兜底处理必须 `await db.rollback()` 后查询已有记录并复用，或跳过
- 不适用：无 UNIQUE 约束的表、允许重复的日志表
- 判断信号：
  - grep `db.add()` 或 `db.flush()` 后无 `except IntegrityError` → 违规
  - grep `except IntegrityError` 后无 `await db.rollback()` → 违规
  - grep `except IntegrityError` 中直接 `raise` 而无兜底（查询复用/跳过）→ 违规
- 严重级别：HIGH（不兜底会导致整个流程因预期冲突失败）

### N. V2.9：2026-07-31 工作流 0 结果阻断+失败详情可见审查

> 来源：2026-07-31 历史对话复盘（规范 R181）。0 结果仍标记 success 会导致后续步骤因无输入而报错，且前端无法显示失败原因。

**配置节点**：`config.yaml#review_dimensions` → `workflow_zero_result_block`

- 【强制】工作流步骤（crawl / rewrite / tts 等）返回 0 结果时必须 `raise RuntimeError` 标记失败并阻断后续步骤
- 【强制】result 中必须包含 `failure_details` 字段（`source_details` / `troubleshooting_hints`）供前端展示
- 不适用：允许 0 结果的查询步骤（如搜索）
- 判断信号：
  - grep `material_count == 0` 或 `len(results) == 0` 后无 `raise RuntimeError` → 违规
  - grep `raise RuntimeError` 在 0 结果分支中但无 `failure_details` 字段 → 违规
  - grep 0 结果分支直接 `return {"status": "success"}` → 违规
- 严重级别：CRITICAL（0 结果不阻断会浪费 LLM 调用，且前端无法展示失败原因）

### O. V2.9：2026-07-31 HTTP 编码探测 fallback 审查

> 来源：2026-07-31 历史对话复盘（规范 R183）。部分中文网站 HTTP header 不声明 charset，默认按 ISO-8859-1 解码会导致中文乱码。

**配置节点**：`config.yaml#review_dimensions` → `http_encoding_detection_fallback`

- 【强制】HTTP 抓取时若 header 无 charset 或 `resp.encoding == 'ISO-8859-1'`，必须用 `charset_normalizer.detect` 探测编码
- 【强制】探测后必须赋值 `resp.encoding = detected['encoding']` 再读 `resp.text`
- 不适用：已知编码的 API 响应（如 JSON 默认 UTF-8）
- 判断信号：
  - grep `resp.text` 或 `resp.encoding` 无 `charset_normalizer` fallback → 违规
  - grep `resp.encoding` 直接判断但无 `charset_normalizer.detect` 调用 → 违规
  - grep `charset_normalizer` import 但未在 `resp.encoding == 'ISO-8859-1'` 分支调用 → 违规
- 严重级别：HIGH（中文乱码导致后续解析失败）

### P. V2.9：2026-07-31 风格库顺序轮换去重审查

> 来源：2026-07-31 历史对话复盘（规范 R185）。random.choice 可能连续选中同一项，candidates[0] 永远用第一个；顺序轮换确保每个候选词均匀使用。

**配置节点**：`config.yaml#review_dimensions` → `style_library_sequential_rotation`

- 【强制】LLM 改写/生成中使用风格库（开场白/过渡词/结尾词）必须用 `seq % len(candidates)` 顺序轮换
- 【强制】`seq` 必须是单调递增的计数器（如素材序号/日期序号），不能用 random
- 不适用：固定模板（如新闻标题格式）、用户主动选择风格的场景
- 判断信号：
  - grep `random.choice` 在风格库选择中 → 违规
  - grep `candidates[0]` 或 `style_library['intro'][0]` 永远取第一项 → 违规
  - grep `% len(` 在风格库选择中 → 合规
- 严重级别：MEDIUM（高频词重复率影响内容质量，非功能性问题）

### 维度 136：打包模式外部存储回退与路径解析

> 来源：2026-08-05 复盘（规范 R186/R187/R191）。exe 模式 COS 已配置时只上传云端无本地副本，列表接口只查本地缓存会导致三面板全空。

**配置节点**：`config.yaml#review_dimensions` → `RD-BE-27`

- 【强制】列表接口（素材/TTS/成品）本地缓存为空时须回退 DB 持久化远程 URL（Script.segments.audio_url / Episode.audio_url / Review.audio_url），禁止 return []
- 【强制】远程项 path 须返回语义值（如 `云端(COS)`），size_bytes 远程时为 0 且前端须正确展示
- 不适用：纯本地文件服务、无云端双写
- 判断信号：
  - grep `list_audio` 本地空后直接 `return []` 无 `audio_url` 回退 → 违规
  - grep `is_cos_configured()` 已配置但列表接口无本地缺失分支 → 违规
  - grep 远程项 `path` 为 None/空或 `size_bytes` 为 None → 违规
- 严重级别：CRITICAL（exe 模式三面板全空，且 dev 正常易漏测）

### 维度 137：异步路由同步 SDK 调用

> 来源：2026-08-05 复盘（规范 R188）。同步第三方 SDK（腾讯云 COS qcloud_cos）在 FastAPI async 路由直接调用会阻塞事件循环。

**配置节点**：`config.yaml#review_dimensions` → `RD-BE-28`

- 【强制】async 函数内同步 SDK 调用（cos_client.get_object / uploader.put_object 等）必须用 `await asyncio.to_thread(...)` 包裹
- 不适用：Flask 等同步框架、SDK 本身提供 async 接口
- 判断信号：
  - grep `cos_client.` / `uploader.*get_object` 出现在 `async def` 且非 `asyncio.to_thread` → 违规
  - grep `await asyncio.to_thread` 包裹同步 SDK → 合规
- 严重级别：CRITICAL（阻塞事件循环导致并发请求串行化/超时）

### 维度 138：二进制流式响应契约

> 来源：2026-08-05 复盘（规范 R189）。二进制音频/文件响应被 success() 信封包裹会导致前端 blob 解析失败。

**配置节点**：`config.yaml#review_dimensions` → `RD-BE-29`

- 【强制】音频/图片/文件下载端点返回原始 `StreamingResponse` / `FileResponse`，禁止 `success({data: bytes})` 信封
- 【强制】大文件用 `StreamingResponse` 分块（如 1MB）返回，禁止一次性读全量字节
- 不适用：JSON API、分页列表
- 判断信号：
  - grep `return success(` 包裹 `.mp3`/`.wav`/音频响应体 → 违规
  - grep `StreamingResponse|FileResponse` 用于二进制下载 → 合规
- 严重级别：HIGH（blob 解析失败 / 大文件内存峰值）

### 维度 139：音频代理 SSRF 防护

> 来源：2026-08-05 复盘（规范 R190）。代理外部音频 URL 的端点若透传任意 host 构成 SSRF（内网探测）。

**配置节点**：`config.yaml#review_dimensions` → `RD-BE-30`

- 【强制】代理外部 URL 的端点须校验域名白名单（仅允许存储服务域名），禁止透传任意 host
- 【强制】复用已初始化的 client 单例（如 uploader._get_client），禁止每次新建
- 判断信号：
  - grep 代理端点对传入 URL 无域名白名单校验 → 违规
  - grep 复用 `_get_client` 单例 → 合规
- 严重级别：CRITICAL（SSRF 可探测内网元数据）

---

## V3.0 会话复盘新增维度（196–204）

> 来源：2026-08-05 会话（两轮）解决的真实问题。完整规则、判断信号与代码示例见 news-code-dev `references/diagnostic-standards.md` 的 DS-1~DS-14；评审要点概览见本技能 `SKILL.md` 的 V3.0 维度表；参数全部由 `config.yaml` 对应节点管理（无硬编码）。

### 维度 196：异常吞没 / traceback 保留（DS-1）
**配置节点**：`config.yaml#exception_swallow_check`
- 【强制】`except` 块不得仅记录 `str(e)` 而无 `exc_info`；子进程/SDK 启动异常须转专用异常（带异常类型 + cmd）
- 判断信号：grep `except Exception` 后仅 `logger.warning(f"...{e}")`/`str(e)` 且无 `exc_info`；`create_subprocess_exec` 外层无 try/except
- 严重级别：HIGH

### 维度 197：CancelledError 逃逸防护（DS-2）
**配置节点**：`config.yaml#cancelled_error_guard_check`
- 【强制】`asyncio.wait_for`/`create_task` 包裹函数中，`except Exception` 之前必须补 `except asyncio.CancelledError`（Python 3.12+ 中为 BaseException 子类）
- 判断信号：grep `wait_for`/`create_task` 包裹函数，`except` 顺序为 `Exception` 在前且无 `CancelledError` 分支
- 严重级别：CRITICAL

### 维度 198：fire-and-forget 保活与守卫（DS-3）
**配置节点**：`config.yaml#fire_and_forget_keepalive_check`
- 【强制】同步签名函数内派发后台协程须模块级集合保活 + `get_running_loop()` 守卫 + 测试环境禁用
- 判断信号：grep 同步函数内 `create_task` 无 `_tasks.add(...)` / 无 `get_running_loop()` 守卫
- 严重级别：HIGH

### 维度 199：构建/发布元数据单一真相源（DS-6）
**配置节点**：`config.yaml#build_metadata_single_source_check`
- 【强制】`_build_info.py` 禁止硬编码 `git_sha="unknown"`/`build_date`；生成器须被构建/发布脚本调用
- 判断信号：grep `git_sha="unknown"` / 硬编码 `build_date=` / `_build_info.py` 未被生成器覆盖
- 严重级别：HIGH

### 维度 200：全量重命名/别名移除完整性（DS-8）
**配置节点**：`config.yaml#alias_rename_completeness_check`
- 【强制】删除/重命名公共 API 后 grep 全仓库旧名须 0 匹配；矛盾注释须清理
- 判断信号：grep 旧名非零匹配（API import + `default=` + `()` 调用 + 注释）
- 严重级别：CRITICAL

### 维度 201：测试隔离与状态防泄漏（DS-9）
**配置节点**：`config.yaml#test_isolation_safe_delete_check`
- 【强制】依赖模块级文件路径/单例的测试须 `tmp_path` + `monkeypatch` 重定向，不得依赖 `unlink()` 成功
- 判断信号：测试用 `unlink()`/`os.remove()` 且依赖其成功；模块级路径未重定向 `tmp_path`
- 严重级别：HIGH（safe-delete 拦截属环境制品，报告单独归类）

### 维度 202：安装包/构建配置完整性（DS-10）
**配置节点**：`config.yaml#packaging_config_completeness_check`
- 【强制】Inno Setup 必须 `SetupIconFile` 复用产品图标；spec 与 iss 模板须一致
- 判断信号：grep `installer.iss` 无 `SetupIconFile`；`MorningBrief.ico` 有效多尺寸 ICO
- 严重级别：MEDIUM

### 维度 203：frozen 模式配置加载路径解析（DS-11）
**配置节点**：`config.yaml#frozen_config_load_check`
- 【强制】PyInstaller 冻结 exe 的配置加载须按 `sys.frozen` 回退到 `sys.executable` 同级解析 `.env`；禁止依赖 cwd 的相对 `env_file`
- 判断信号：grep `config.py` 的 `env_file` 为相对/固定路径且无 `getattr(sys, "frozen")` 分支
- 严重级别：CRITICAL（exe 模式读不到 `WX_APPID` 等表现 appid missing）
- 适用/不适用：适用 PyInstaller/Nuitka 冻结 exe；不适用纯源码运行

### 维度 204：安装包配置完整性（DS-12）
**配置节点**：`config.yaml#installer_secret_completeness_check`
- 【强制】`installer.iss` 不得 `Excludes` 静默丢弃 `.env`/密钥；须显式 `Source:` 包含 `.env`；构建脚本拷贝后须 `attrib -H` 去隐藏属性
- 判断信号：grep `Excludes:.*\.env`；或 `Source:` 列表无 `.env`；构建脚本拷贝 `.env` 后无 `attrib -H`
- 严重级别：CRITICAL（代码已修仍 appid missing 的常见部署层根因）
- 适用/不适用：适用含 `.env`/密钥的安装包；不适用配置全环境变量注入


