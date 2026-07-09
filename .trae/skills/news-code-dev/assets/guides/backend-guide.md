# 后端开发指南

本文档面向 20_News 项目后端开发，涵盖 FastAPI + SQLAlchemy 2.0 + Redis 的完整开发实践。

## 1. 开发规范概述

后端开发需遵循以下原则：
- 配置驱动：所有参数通过 `settings.py` 管理
- 异步优先：全面使用 async/await，避免阻塞事件循环
- 分层清晰：routers → services → models → core
- 错误分类：区分认证失败、业务失败、系统失败
- 日志完整：错误日志必须包含 traceback

## 2. 工程规约

### 目录结构

```
backend/
├── app/
│   ├── core/          # 基础设施：配置、数据库、Redis、认证
│   ├── models/        # SQLAlchemy ORM 模型
│   ├── schemas/       # Pydantic 请求/响应模型
│   ├── services/      # 业务逻辑层
│   ├── routers/       # HTTP 路由
│   ├── workflows/     # 工作流步骤
│   ├── utils/         # 工具函数
│   └── main.py        # FastAPI 应用入口
├── tests/             # 测试代码
├── migrations/        # Alembic 迁移
├── requirements.txt   # 依赖
└── .env               # 环境变量（不提交）
```

### 命名规范

- 模块名：小写 + 下划线（`news_service.py`）
- 类名：大驼峰（`NewsService`）
- 表名：复数小写 + 下划线（`news_items`）
- 字段名：小写 + 下划线（`created_at`）

## 3. 路由开发

### FastAPI APIRouter

路由文件应使用 `APIRouter` 组织，每个模块一个 router：

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/news", tags=["news"])
```

**为什么使用 prefix**：统一 API 版本管理，后续升级只需修改 prefix。

### 依赖注入

使用 FastAPI 的 `Depends` 实现依赖注入：

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.news_service import NewsService

@router.get("/{news_id}")
async def get_news(
    news_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = NewsService(db)
    news = await service.get_by_id(news_id)
    return {"code": 0, "data": news.to_dict()}
```

**为什么使用 Depends**：
- 数据库会话自动创建和关闭
- 易于测试（可以 mock 依赖）
- 代码复用（多个路由共享相同依赖）

### 响应格式

统一使用 `success()` / `error()` 函数格式化响应：

```python
from app.core.response import success, error

@router.post("/")
async def create_news(data: NewsCreate, db: AsyncSession = Depends(get_db)):
    try:
        news = await NewsService(db).create(data)
        return success(data=news.to_dict())
    except ValidationError as e:
        return error(code=422, message=str(e))
    except Exception as e:
        logger.exception("创建新闻失败")
        return error(code=500, message="服务器内部错误")
```

## 4. 服务层开发

### 业务逻辑封装

服务层是业务逻辑的唯一入口，路由层不应包含业务判断：

```python
class NewsService:
    def __init__(self, db: AsyncSession, redis: Redis | None = None):
        self.db = db
        self.redis = redis
    
    async def get_by_id(self, news_id: int) -> NewsModel | None:
        # 1. 查缓存
        cache_key = f"news:get:{news_id}"
        if self.redis:
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
        
        # 2. 查数据库
        stmt = select(NewsModel).where(NewsModel.id == news_id)
        result = await self.db.execute(stmt)
        news = result.scalar_one_or_none()
        
        # 3. 写缓存
        if news:
            data = news.to_dict()
            if self.redis:
                await self.redis.setex(cache_key, settings.CACHE_TTL_SEC, json.dumps(data))
            return data
        
        return None
```

**为什么缓存使用 setex（带过期）**：防止缓存永不过期导致脏数据。

### 缓存使用

```python
# cache-aside 模式：先查缓存，未命中再查 DB
async def get_with_cache(self, key: str, fetch_func):
    cached = await self.redis.get(key)
    if cached:
        return json.loads(cached)
    
    data = await fetch_func()
    if data:
        await self.redis.setex(key, settings.CACHE_TTL_SEC, json.dumps(data))
    return data

# 写操作后删除缓存（不更新）
async def update(self, news_id: int, data: dict):
    await self.db.execute(update(NewsModel).where(...).values(**data))
    await self.db.commit()
    # 删除缓存，下次读取时重建
    await self.redis.delete(f"news:get:{news_id}")
```

**为什么删除而非更新缓存**：并发写入时，更新缓存可能导致脏数据；删除缓存让下次读取自然重建，保证最终一致性。

### 事务管理

```python
async def create_with_transaction(self, data: dict):
    try:
        news = NewsModel(**data)
        self.db.add(news)
        await self.db.commit()
        await self.db.refresh(news)
        return news
    except Exception:
        await self.db.rollback()  # 失败时回滚
        raise
```

## 5. 模型开发

### SQLAlchemy 2.0 风格

```python
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class NewsModel(Base):
    __tablename__ = "news_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, index=True)
    content = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
```

**为什么使用 DeclarativeBase**：SQLAlchemy 2.0 推荐的声明式基类，类型推导更好。

### 字段类型选择

| 场景 | 类型 | 说明 |
|------|------|------|
| 主键 | `Integer` / `BigInteger` | 自增 ID |
| 短文本 | `String(255)` | 标题、名称 |
| 长文本 | `Text` | 正文、描述 |
| 状态 | `String(20)` | 使用枚举的 .value |
| 时间 | `DateTime` | 统一 UTC，naive datetime |
| JSON | `JSON` / `Text` | 灵活结构数据 |

### 关系定义

```python
class CommentModel(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True)
    news_id = Column(Integer, ForeignKey("news_items.id"), nullable=False)
    content = Column(Text, nullable=False)
    
    # 反向关系
    news = relationship("NewsModel", back_populates="comments")

class NewsModel(Base):
    # ...
    comments = relationship("CommentModel", back_populates="news")
```

## 6. 工作流开发

### 状态机实现

```python
from enum import Enum

class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class WorkflowStep(Enum):
    FETCH = "fetch"
    REWRITE = "rewrite"
    TTS = "tts"
    MODERATE = "moderate"
    PUBLISH = "publish"
```

**为什么状态继承 str + Enum**：便于序列化为 JSON，数据库存储字符串值。

### 分布式锁

```python
async def acquire_workflow_lock(self, task_id: str) -> bool:
    lock_key = f"workflow:lock:{task_id}"
    acquired = await self.redis.set(
        lock_key, "1", nx=True, ex=settings.WORKFLOW_LOCK_TTL
    )
    return bool(acquired)

async def release_workflow_lock(self, task_id: str):
    lock_key = f"workflow:lock:{task_id}"
    await self.redis.delete(lock_key)
```

### 重试逻辑

```python
async def execute_with_retry(self, func, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                logger.exception(f"Final attempt failed: {e}")
                raise
            delay = 2 ** attempt  # 指数退避
            logger.warning(f"Attempt {attempt + 1} failed, retry in {delay}s")
            await asyncio.sleep(delay)
```

## 7. 异步开发

### asyncio.create_task

```python
# 正确：保留 task 引用
task = asyncio.create_task(send_alert(message))
task.add_done_callback(lambda t: logger.info(f"Alert sent: {t.result()}"))

# 错误：无引用，可能被 GC
asyncio.create_task(send_alert(message))
```

### asyncio.to_thread

```python
# 阻塞操作（如音频处理）放到线程池
async def process_audio(self, file_path: str) -> str:
    loop = asyncio.get_event_loop()
    result = await asyncio.to_thread(self._blocking_audio_process, file_path)
    return result
```

**为什么用 to_thread**：音频处理是 CPU 密集型操作，直接在事件循环中执行会阻塞其他请求。

### httpx 异步客户端

```python
async def fetch_rss(self, url: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text
```

**为什么用 AsyncClient**：同步的 `requests` 会阻塞事件循环。

## 8. 安全开发

### JWT 验证

```python
import hmac

def verify_token(token: str, secret: str) -> bool:
    # 使用 hmac.compare_digest 防时序攻击
    return hmac.compare_digest(token, secret)
```

### SQL 注入防护

```python
# 正确：使用参数化查询
stmt = select(NewsModel).where(NewsModel.title == title)

# 错误：字符串拼接
stmt = f"SELECT * FROM news WHERE title = '{title}'"
```

### 敏感词过滤

```python
# 在应用启动时初始化 AC 自动机
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    sensitive_words = await load_sensitive_words()
    ac_filter = AhoCorasick(sensitive_words)
    app.state.sensitive_filter = ac_filter
    yield
    # 关闭时清理
    ac_filter.clear()
```

## 9. 错误处理

### 自定义异常

```python
class NewsAPIError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

class AuthenticationError(NewsAPIError):
    def __init__(self, message: str = "认证失败"):
        super().__init__(code=2000, message=message)

class ValidationError(NewsAPIError):
    def __init__(self, message: str = "参数校验失败"):
        super().__init__(code=1000, message=message)
```

### 全局异常处理器

```python
@app.exception_handler(NewsAPIError)
async def handle_api_error(request: Request, exc: NewsAPIError):
    return JSONResponse(
        status_code=exc.code,
        content={"code": exc.code, "message": exc.message}
    )

@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("未预期的错误")
    return JSONResponse(
        status_code=500,
        content={"code": 5000, "message": "服务器内部错误"}
    )
```

## 10. 最佳实践

### 完整的 Service 示例

```python
"""新闻服务层 - 处理新闻的 CRUD 和缓存逻辑。"""
import json
import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.news import NewsModel
from app.schemas.news import NewsCreate, NewsUpdate

logger = logging.getLogger(__name__)


class NewsService:
    """新闻业务逻辑服务。"""

    def __init__(self, db: AsyncSession, redis_client=None):
        self.db = db
        self.redis = redis_client

    async def get_by_id(self, news_id: int) -> dict[str, Any] | None:
        """获取单条新闻，使用 cache-aside 模式。"""
        cache_key = f"news:get:{news_id}"
        
        # 先查缓存
        if self.redis:
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

        # 缓存未命中，查数据库
        stmt = select(NewsModel).where(NewsModel.id == news_id)
        result = await self.db.execute(stmt)
        news = result.scalar_one_or_none()

        if not news:
            return None

        data = news.to_dict()

        # 写入缓存
        if self.redis:
            await self.redis.setex(cache_key, settings.CACHE_TTL_SEC, json.dumps(data))

        return data

    async def create(self, data: NewsCreate) -> NewsModel:
        """创建新闻，同时清除相关缓存。"""
        news = NewsModel(
            title=data.title,
            content=data.content,
            status="pending",
            created_at=utcnow_naive(),
            updated_at=utcnow_naive(),
        )
        self.db.add(news)
        await self.db.commit()
        await self.db.refresh(news)

        # 清除列表缓存
        if self.redis:
            await self.redis.delete("news:list:*")

        return news

    async def update(self, news_id: int, data: NewsUpdate) -> NewsModel | None:
        """更新新闻，使用乐观锁防止并发覆盖。"""
        stmt = (
            update(NewsModel)
            .where(NewsModel.id == news_id, NewsModel.updated_at == data.last_updated_at)
            .values(**data.model_dump(exclude={"last_updated_at"}), updated_at=utcnow_naive())
        )
        result = await self.db.execute(stmt)
        await self.db.commit()

        if result.rowcount == 0:
            return None

        return await self.get_by_id(news_id)
```

### 完整的路由示例

```python
"""新闻路由 - 处理新闻相关的 HTTP 请求。"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import success, error
from app.schemas.news import NewsCreate, NewsUpdate
from app.services.news_service import NewsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/news", tags=["news"])


async def get_news_service(
    db: AsyncSession = Depends(get_db),
) -> NewsService:
    """获取新闻服务实例。"""
    return NewsService(db)


@router.get("/{news_id}")
async def get_news(
    news_id: int,
    service: Annotated[NewsService, Depends(get_news_service)],
):
    """获取单条新闻详情。"""
    news = await service.get_by_id(news_id)
    if not news:
        return error(code=404, message="新闻不存在")
    return success(data=news)


@router.post("/")
async def create_news(
    data: NewsCreate,
    service: Annotated[NewsService, Depends(get_news_service)],
):
    """创建新闻。"""
    try:
        news = await service.create(data)
        return success(data=news.to_dict(), message="创建成功")
    except Exception as e:
        logger.exception(f"创建新闻失败: title={data.title}")
        return error(code=500, message="服务器内部错误")


@router.put("/{news_id}")
async def update_news(
    news_id: int,
    data: NewsUpdate,
    service: Annotated[NewsService, Depends(get_news_service)],
):
    """更新新闻。"""
    news = await service.update(news_id, data)
    if not news:
        return error(code=404, message="新闻不存在或版本冲突")
    return success(data=news)


@router.get("/")
async def list_news(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    service: Annotated[NewsService, Depends(get_news_service)],
):
    """分页获取新闻列表。"""
    news_list, total = await service.list(page, page_size, category)
    return success(data={
        "items": news_list,
        "total": total,
        "page": page,
        "page_size": page_size,
    })
```
