"""
数据库连接管理

SQLAlchemy 异步引擎 + 会话工厂。
会话通过 FastAPI 依赖注入，确保请求结束自动关闭。
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# pool_recycle 避免 MySQL 默认 8 小时空闲断连
# pool_pre_ping 在取连接前做一次轻量 ping，避免使用已断开的连接
engine = create_async_engine(
    settings.mysql_dsn,
    pool_size=settings.MYSQL_POOL_SIZE,
    pool_recycle=settings.MYSQL_POOL_RECYCLE,
    pool_pre_ping=True,
    echo=settings.APP_DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：注入数据库会话，请求结束自动关闭。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
