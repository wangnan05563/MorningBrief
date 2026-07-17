---
name: "news-backend-code-review"
description: "对 MorningBrief 项目后端代码（backend/app/ 下 Python/FastAPI/SQLAlchemy 文件）进行全面评审与逻辑审查，覆盖分层架构、异步并发、数据库规约、安全、性能、错误处理、配置驱动、前后端字段契约、工作流编排、缓存一致性等维度。当用户要求'审查/检查/走查/把关/review/评估/看看对不对/规范不规范'后端 Python 代码、'.py 文件修改'、'迭代发布前后端走查'，或提到'后端评审/backend review/Python 代码审查/FastAPI 评审/SQLAlchemy 评审'时调用。仅审查后端 .py 文件；纯前端文件审查请改用 news-frontend-code-review。"
whenToUse: "需要审查 MorningBrief 后端代码（backend/app/ 下 .py 文件）是否符合项目规范"
triggers: "后端代码 走查/审查/审核/把关/review/检查/评估 | .py 文件 修改/变更/迭代 走查 | 迭代发布前 后端 代码 走查 | 这段后端代码 写得对不对/规范不规范 | 路由/服务/模型/工作流 代码 审查"
version: "1.6.0"
updated: "2026-07-17"
config: "config.yaml"
scripts: "scripts/auto-scan.ps1"
template: "templates/report-template.md"
---

# MorningBrief 后端代码审查

## 简介

本技能对 MorningBrief 项目后端代码（`backend/app/**/*.py`）进行系统性评审与逻辑审查，覆盖 **58 个维度**：分层架构、命名规范、类型注解、FastAPI 规范、SQLAlchemy 2.0 规范、异步并发、Redis 缓存规约、安全、错误处理、配置驱动、工作流编排、前后端字段契约、日志规范、性能、可测试性、频道级数据隔离、RSS 源配置管理、第三方服务依赖诊断、PowerShell 工具链兼容性。

适用技术栈：FastAPI + SQLAlchemy 2.0 async + aiomysql（或 aiosqlite）+ Redis（或 TTLCache 进程内缓存）+ APScheduler + httpx + COS + 阿里云 TTS + 通义千问 LLM。

## 核心原则：配置驱动

**所有评审规则、硬约束、阈值、白名单、关键字均通过 `config.yaml` 管理，技能本身不含任何硬编码业务值。**

- 评审范围（scope）→ `config.yaml#scope`
- 优先级排序 → `config.yaml#priority`
- 硬约束规则 → `config.yaml#hard_constraints.rules`
- 维度开关 → `config.yaml#checklist`
- 项目规范（技术栈、ORM 版本、缓存类型）→ `config.yaml#project_conventions`
- 工作流编排配置 → `config.yaml#workflow_orchestration`
- 前后端字段契约 → `config.yaml#field_contract`
- 编码规范阈值 → `config.yaml#coding_standards`

当 `config.yaml` 缺失时，技能会使用 `config.example.yaml` 兜底并提示用户创建 `config.yaml`。修改阈值只需改 config 节点，无需改技能代码。

## 审查模式

| 模式 | 触发方式 | 范围 | 适用场景 |
|------|----------|------|----------|
| 快速自检 | 运行 `scripts/auto-scan.ps1` | 全量 .py | 提交前预检阻塞级问题 |
| 增量审查 | git diff 比对变更文件 | 变更文件 | 日常迭代、PR 走查 |
| 指定文件审查 | 用户给出路径 | 指定文件 | 单文件深度审查 |
| 片段评审 | 用户粘贴代码片段 | 片段 | 即时反馈、Chat 模式 |
| 全量审查 | 扫描 `backend/app/**/*.py` | 全量 | 发版前走查、技术债盘点 |

执行流程：
1. 读取 `config.yaml`，确认 scope 与开启的维度
2. 按模式收集待审查文件
3. 运行 `scripts/auto-scan.ps1` 预检阻塞级问题
4. 按 15 维度 checklist 逐项审查
5. 汇总结果填入 `templates/report-template.md`
6. 输出修复建议 + 四维度复盘

## 审查规则

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

## 补充审查要点

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

## 四维度复盘

> 基于本次 MorningBrief 后端代码审查完整过程的复盘，沉淀可复用的工作流模板与判断逻辑。

### 维度 1：成功执行任务的完整步骤

本次审查在 15 维度下识别问题并闭环，关键成功路径（按时间顺序）：

1. **Grep 搜索反模式**：按维度 1-15 的判断信号，用 Grep 工具扫描 `backend/app/**/*.py`，定位疑似违规位置
2. **分类问题**：按 severity（CRITICAL / HIGH / MEDIUM / LOW）与 category（15 维度）归类
3. **子智能体并行修复**：对独立问题派发并行子智能体，每个子智能体负责一类修复（如「敏感词初始化」「JWT 黑名单」「Enum .value」「finally 锁保护」）
4. **py_compile 验证**：修复后运行 `python -m py_compile <file>` 确保语法正确
5. **pytest 测试**：运行 `pytest backend/tests/ -x` 确保未破坏现有测试

复用方法/工具：Grep（反模式扫描）、Edit（精确修复）、RunCommand（py_compile + pytest 验证）。

### 维度 2：任务执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 敏感词过滤器未初始化 | `sensitive_filter.load_words()` 从未被调用 | LLM 改写结果命中敏感词不拦截，内容合规风险 | 启动流程遗漏初始化调用 | 在 `main.py` lifespan 或 `WorkflowScheduler.__init__` 调用 `load_words()` |
| 登出接口缺失 | 无 `/logout` 路由 | JWT token 无法主动失效，被盗用风险持续到过期 | 黑名单机制未闭环 | 新增登出接口，写黑名单（COS 或 SQLite） |
| workflow source 字段返回 Enum 对象 | `WorkflowSource.CRON` 直接序列化 | API 返回 `<WorkflowSource.CRON: 'cron'>`，前端解析失败 | Enum 未调 `.value` | 序列化时用 `source.value` |
| finally 误删其他工作流的锁 | `finally: await cache.release("wf_lock")` 无条件执行 | 并发工作流互相误删锁，重复触发 | `lock_acquired` 标志缺失 | 加 `lock_acquired` 标志，仅在自己获取时 release |
| approve 跨事务 | 审核批准与发布在同一事务 | 发布失败回滚审核状态，运营误判 | 事务边界设计错误 | 拆分为两步：先 commit 审核，再独立事务发布 |
| PermissionError 覆盖内置异常 | `class PermissionError(Exception)` | 业务代码无法捕获内置 `PermissionError` | 命名未加 Biz 前缀 | 改名 `BizPermissionError` |
| datetime.utcnow() 弃用 | Python 3.12+ 警告，3.14 移除 | 升级 Python 后报错 | 沿用旧 API | 改用 `utcnow_naive()`（core/timeutil.py） |
| play_log LRANGE+LTRIM 非原子 | 消费日志时两条命令间并发写入 | 日志丢失或重复消费 | 未用 Lua 脚本 | 用 Lua 脚本封装 LRANGE+LTRIM |
| asyncio.create_task 未保留引用 | 裸 `asyncio.create_task(coro)` | 协程被 GC 回收，任务静默取消 | 局部变量无生命周期 | 赋值给 `self._running_tasks` |
| 异步函数中同步 IO 阻塞事件循环 | `async def` 内 `time.sleep` / `requests.get` | 整个事件循环阻塞，所有请求超时 | 误用同步库 | 用 `asyncio.to_thread()` 或异步库 |

### 维度 3：可抽象的固定流程与判断逻辑

| 模板 | 核心判断信号 | 落地配置节点 |
|------|--------------|--------------|
| 敏感词初始化检查 | Grep `load_words` 在 startup 路径缺失 | `hard_constraints.rules.sensitive_filter_not_initialized` |
| JWT 黑名单闭环检查 | Grep `/logout` 路由缺失或未写黑名单 | `hard_constraints.rules.logout_missing` |
| Enum 字段序列化检查 | Grep `WorkflowStatus\.\w+` 后无 `.value` 在序列化路径 | `hard_constraints.rules.enum_field_without_value` |
| finally 锁保护检查 | Grep `finally` 块内 `release` 无 `lock_acquired` 判断 | `hard_constraints.rules.finally_unconditional_release` |
| 内置异常覆盖检查 | Grep `class PermissionError` / `class KeyError` 等 | `hard_constraints.rules.builtin_exception_shadowing` |
| datetime 弃用检查 | Grep `datetime\.utcnow\(\)` / `datetime\.now\(\)` | `hard_constraints.rules.deprecated_utcnow` |
| Redis 非原子操作检查 | Grep `LRANGE` 后跟 `LTRIM` 无 `eval` / `pipeline` | `hard_constraints.rules.redis_non_atomic_lrange_ltrim` |
| create_task 引用检查 | Grep `asyncio\.create_task` 未赋值实例属性 | `hard_constraints.rules.create_task_no_reference` |
| 同步 IO 阻塞检查 | Grep `async def` 内 `time\.sleep` / `requests\.` | `hard_constraints.rules.sync_io_in_async` |
| 内部接口鉴权检查 | Grep `routers/internal` 路由无 `verify_localhost` | `hard_constraints.rules.internal_route_no_auth` |
| 裸 SQL 注入检查 | Grep `text\(["'].*\+` 或 `f"SELECT` 字符串拼接 | `hard_constraints.rules.bare_sql_injection` |
| print 语句检查 | Grep `print\(` 在 .py 文件 | `hard_constraints.rules.print_statement` |

### 维度 4：适用场景与不适用场景

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 敏感词初始化检查 | 含 LLM 改写/内容审核的 workflow 项目 | 无敏感词过滤的项目 |
| JWT 黑名单闭环检查 | 需要主动登出/封禁 token 的认证系统 | 无状态 JWT（接受 token 不可主动失效） |
| Enum .value 检查 | 用 Python Enum 定义状态字段的 ORM | 用字符串常量而非 Enum 的项目 |
| finally 锁保护检查 | 用 Redis/TTLCache 分布式锁的并发场景 | 单进程无锁场景、`with lock:` 上下文管理器 |
| 内置异常覆盖检查 | 所有 Python 项目 | 无 |
| datetime 弃用检查 | Python 3.12+ 项目 | Python 3.8-3.11 兼容场景（仅警告） |
| Redis 非原子检查 | 用 Redis 多命令原子操作场景 | 单命令操作、Lua 脚本已封装 |
| create_task 引用检查 | `asyncio.create_task` 长生命周期协程 | `asyncio.gather` 短期并发（自动等待） |
| 同步 IO 阻塞检查 | FastAPI / asyncio 异步项目 | 同步框架（Flask 默认）、CLI 脚本 |
| 内部接口鉴权检查 | 暴露内部 API 的项目（`routers/internal/`） | 无内部接口的项目 |
| 裸 SQL 注入检查 | 用 SQLAlchemy `text()` 的项目 | 纯 ORM 查询、纯参数化查询 |
| print 语句检查 | 所有生产项目 | 一次性脚本、debug 临时调试 |

### 维度 5（补充）：频道级数据隔离与 RSS 源管理复盘（2026-07-17）

**成功执行任务的完整步骤**：

1. **问题定位**：用户报告主机游戏频道（channel_id=9）工作流产出 36氪/人民网内容
2. **根因分析**：Grep 搜索 `OR channel_id IS NULL` 定位到 `rewriter._fetch_materials` 和 `crawler` 的 0-count 检查
3. **代码修复**：移除 `or_(Material.channel_id == channel_id, Material.channel_id.is_(None))` 兜底，专门频道严格按 channel_id 过滤
4. **RSS 源替换**：识别 rsshub.app 在大陆被 DNS 污染，4 个游戏源全部失效，替换为原生 RSS（机核/触乐/17173）
5. **端到端验证**：编写验证脚本，串行执行（3s 间隔）避免 plink 限流，5 轮探测扩展到 62 源
6. **配置同步**：rss.yaml name 变更后同步数据库 `channel.rss_sources` JSON 数组

**任务执行中的不确定性与失败点（补充）**：

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 频道级 OR NULL 兜底 | `rewriter._fetch_materials` 用 `or_(channel_id == x, channel_id IS NULL)` | 专门频道消费 NULL 历史素材，跨频道污染 | 历史兜底逻辑未考虑专门频道场景 | 移除 OR NULL，专门频道严格过滤 |
| rsshub.app 全站失效 | 所有 rsshub.app 源返回 ConnectError | 4 个游戏源全部不可达 | rsshub.app 公共实例在大陆被 DNS 污染 + TCP 阻断 | 替换为原生 RSS（机核/触乐/17173） |
| plink 并发限流假阳性 | 验证脚本并发≥5 测试 plink 源 | 12 个 plink 源返回 0 条目（假阳性） | plink.anyfeeder.com 会话级限流 | 改用串行模式，3s 间隔全部恢复 |
| PowerShell stdout 缓冲 | `python script.py` 在 PowerShell 中输出不可见 | 验证脚本"卡住"误判 | stdout 块缓冲未刷新 | `python -u script.py 2>&1` |
| feedparser HTTP 200+0 条目 | 站点返回 HTML 而非 RSS | 误判为 RSS 格式错误 | 站点未提供 RSS，返回网页 | 检查 Content-Type 和前 200 字符 |
| rss.yaml name 变更未同步数据库 | channel.rss_sources JSON 数组存储旧 name | crawler 按 name 匹配找不到源 | 配置文件与数据库不同步 | 同步脚本 `python -m app.scripts.sync_rss_sources` |
| 4 个 plink 源持续失效 | 联合早报-国际/财新网/新智元/果壳网多次测试 0 条目 | 4 源无法使用 | 微信公众号被封禁，plink 无法获取 | 从 rss.yaml 移除，替换为联合早报-中港台 |
| Edit 工具字符串匹配失败 | 文件内容与预期不符 | Edit 失败需重试 | 文件内容已被修改但缓存未更新 | 改用 Write 完整重写文件 |
| 中国国家地理误删 | 移除果壳网时误删 | 可达源丢失 | Edit 操作误伤相邻条目 | 立即恢复该条目 |

**可抽象的固定流程与判断逻辑（补充）**：

| 模板 | 核心判断信号 | 落地配置节点 |
|------|--------------|--------------|
| 频道级数据隔离检查 | Grep `OR.*channel_id IS NULL` 或 `or_\(.*channel_id` | `hard_constraints.rules.channel_isolation_no_null_fallback` |
| RSS 源配置同步检查 | Grep rss.yaml name 变更后无 `sync_rss_sources` 调用 | `hard_constraints.rules.rss_source_db_sync` |
| 第三方转换服务标注检查 | Grep rss.yaml 含 `rsshub.app\|plink.anyfeeder` 无风险标注 | `hard_constraints.rules.third_party_rss_annotation` |
| PowerShell Python 调用检查 | Grep `.ps1` 中 `python script.py` 无 `-u` 或 `2>&1` | `hard_constraints.rules.powershell_python_unbuffered` |
| RSS 源可达性诊断检查 | Grep 验证脚本中 0 条目直接标记失效无 Content-Type 检查 | `hard_constraints.rules.rss_reachability_diagnosis` |
| 并发验证限流检查 | Grep 验证脚本中 `asyncio.gather` 测试第三方转换服务 | `hard_constraints.rules.no_concurrent_third_party_verify` |

**适用场景与不适用场景（补充）**：

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 频道级数据隔离检查 | 多频道/多租户系统 | 单频道系统、全局工作流 |
| RSS 源配置同步检查 | 频道级 RSS 配置管理 | 全局 RSS（不按频道隔离） |
| 第三方转换服务标注检查 | 依赖 rsshub/plink 的项目 | 全部使用原生 RSS 的项目 |
| PowerShell Python 调用检查 | Windows + PowerShell 工具链 | bash/zsh、IDE、生产服务 |
| RSS 源可达性诊断检查 | 所有 RSS 抓取系统 | API 接口验证（JSON 响应） |
| 并发验证限流检查 | 第三方转换服务验证 | 原生 RSS 验证、生产 crawler |

## 附录：配置节点速查

| 配置节点 | 用途 | 对应维度 |
|----------|------|----------|
| `scope` | 评审范围（glob） | 全部 |
| `priority.severity_order` | severity 排序 | 全部 |
| `hard_constraints.rules` | 硬约束规则列表（含 pattern/message/severity） | 全部 |
| `checklist` | 15 维度开关 | 1-15 |
| `project_conventions` | 技术栈、ORM 版本、缓存类型 | 5, 7 |
| `workflow_orchestration` | 工作流编排配置 | 11 |
| `field_contract` | 前后端字段契约 | 12 |
| `coding_standards` | 编码规范阈值 | 3, 5, 14 |
| `verify` | 验证配置（py_compile / pytest） | 全部 |
| `report` | 报告生成配置 | 全部 |
| `channel_isolation` | 频道级数据隔离配置（channel_id 严格过滤、NULL 兜底禁用） | 54 |
| `rss_source_management` | RSS 源配置管理（rss.yaml 同步、第三方服务标注、可达性诊断） | 55, 56, 58 |
| `powershell_compat` | PowerShell 工具链兼容性（Python 调用规范、stderr 捕获） | 57 |


---

## 新增审查维度：外部服务与配置一致性

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

## 新增审查维度：第三方服务模型名称与定价表一致性

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

## 新增审查维度：批量删除与事务规范

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

## 新增审查维度：启动脚本路径与并发安全

### 维度 33：启动脚本路径含空格安全封装

**为什么**：系统 Python 路径可能包含空格（如 F:\Program Files\Python3.14\python.exe）。PowerShell 的 Start-Process -ArgumentList 会将含空格的字符串重新拆分引号，导致可执行文件路径被截断。

检查信号：Grep Start-Process 后无 /s /c 双层引号封装
修复建议：使用 cmd /d /s /c "" 四层引号封装，-ArgumentList 传数组

### 维度 34：构建脚本并发保护

**为什么**：多次执行构建脚本可能导致旧 PyInstaller 进程未完全退出，新旧进程同时写入 dist 目录造成 PermissionError / WinError 32。

检查信号：Grep Remove-Item 后无进程检查和删除验证
修复建议：构建前先终止占用旧产物的进程，删除后用 try/throw 验证成功

---

## 新增审查维度：日志格式与异常透传

### 维度 35：日志格式与异常信息透传

**为什么**：Loguru 使用 {} 占位符，旧代码使用 %s 会导致异常对象被当作字符串格式化，真实错误信息被吞掉。

检查信号：Grep logger\.(warning|error|info).*%s
修复建议：统一使用 {} 占位符，异常日志必须包含 exc_info=True

### 维度 36：运行环境与源码一致性

**为什么**：日志格式、异常透传方式与源码版本不一致时，说明运行的是旧构建产物，新修复未生效。

检查信号：运行日志中出现 %s 格式但源码已改为 {}
修复建议：确认运行进程使用的源码版本，必要时重启服务

---

## 新增审查维度：共享构建依赖包完整提取

### 维度 37：共享构建依赖包完整提取

**为什么**：FFmpeg 等共享构建的 EXE 文件依赖同目录 DLL。只复制 EXE 而不提取配套 DLL 会导致运行时找不到 vdevice-63.dll 等系统错误。

检查信号：Grep zf.open(ffmpeg_member) 后只提取 exe 文件
修复建议：通过 ffmpeg.exe 定位 zip 内 bin 目录，提取所有普通文件（含 DLL），提取前清除旧文件


**为什么**：批量删除接口应设置单次操作数量上限，防止单次事务过大导致数据库压力。

检查信号：Grep 批量操作接口无 max_length 约束
修复建议：Pydantic model 中设置 Field(max_length=100)

---

## 新增审查维度：时区一致性与跨模块状态对齐

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

## 新增审查维度：模型字段验证与统计口径

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

## 新增审查维度：频道级数据隔离与 RSS 源管理

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
