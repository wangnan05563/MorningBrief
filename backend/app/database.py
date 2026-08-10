"""数据库连接管理（V1.2：SQLite + aiosqlite 替代 MySQL + aiomysql）。

SQLAlchemy 异步引擎 + 会话工厂。
会话通过 FastAPI 依赖注入，确保请求结束自动关闭。

SQLite 适配要点：
1. 无连接池（SQLite 为嵌入式数据库，单文件多连接即可）
2. PRAGMA 配置通过 SQLAlchemy 事件监听器在每个连接建立时注入
3. WAL 模式：读不阻塞写、写不阻塞读，仅写-写冲突触发 BUSY
4. busy_timeout=5000：写冲突时自动等待 5 秒（替代 MySQL 死锁重试）
"""
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# SQLite 无需连接池参数（pool_size/pool_recycle 是 MySQL 专用）
# connect_args 仅传 SQLite 支持的参数
engine = create_async_engine(
    settings.sqlite_url,
    echo=settings.APP_DEBUG,
    # SQLite 在 WAL 模式下支持多连接并发读，check_same_thread=False 允许跨线程
    # 注意：SQLite 异步引擎默认 NullPool（每次 checkout 新建连接、checkin 即释放），
    # 不接收 pool_size/max_overflow 等 QueuePool 参数；WAL 下多独立连接可并发读，
    # 写则经全局写锁串行化（单写者上限）。多连接并发是 SQLite 嵌入式设计的预期行为。
    connect_args={"check_same_thread": False},
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


# ---- SQLite PRAGMA 配置 ----
# 通过事件监听器在每个连接建立时执行 PRAGMA，确保所有连接一致
# SQLite 的 PRAGMA 是连接级配置，每个新连接都需重新设置


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    """SQLite 连接级 PRAGMA 配置（V1.2 替代 MySQL my.cnf）。

    - journal_mode=WAL：读不阻塞写，提升并发读性能
    - busy_timeout=5000：写冲突时自动等待 5 秒，替代应用层重试
    - synchronous=NORMAL：WAL 模式下安全，性能优于 FULL
    - foreign_keys=ON：启用外键约束（SQLite 默认关闭）
    """
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute(f"PRAGMA journal_mode={settings.SQLITE_JOURNAL_MODE}")
        cursor.execute(f"PRAGMA busy_timeout={settings.SQLITE_BUSY_TIMEOUT_MS}")
        cursor.execute(f"PRAGMA synchronous={settings.SQLITE_SYNCHRONOUS}")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


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


# ---- SQLite 索引名规范化 ----
# SQLite 索引名在整个数据库内必须唯一（MySQL 仅需表内唯一）。
# 多张表共用同名索引（如 idx_workflow 在 material/script 等表上都有）
# 在 SQLite 下会触发 "index already exists" 错误。
# 此函数给每个索引加上表名前缀，确保跨表不重名；幂等可多次调用。
_metadata_normalized = False


def normalize_metadata_for_sqlite() -> None:
    """规范化 Base.metadata 的索引名以适配 SQLite 全局唯一约束。

    改造规则：
    1. 索引名加表名前缀：idx_workflow → ix_material_idx_workflow
    2. BigInteger 主键改为 Integer，让 SQLite AUTOINCREMENT 生效

    幂等：模块级标志位确保只执行一次。生产启动与测试 fixture 均可安全调用。
    """
    global _metadata_normalized
    if _metadata_normalized:
        return
    from sqlalchemy import Integer
    from sqlalchemy.types import BigInteger

    for table_name, table in Base.metadata.tables.items():
        # 1. 索引名加表名前缀，避免跨表同名冲突
        for idx in table.indexes:
            if idx.name and not idx.name.startswith(f"ix_{table_name}_"):
                idx.name = f"ix_{table_name}_{idx.name}"
        # 2. BigInteger 主键改为 Integer，让 SQLite AUTOINCREMENT
        # SQLite 要求自增列必须是 INTEGER PRIMARY KEY，BigInteger 生成 BIGINT 无法自增
        for col in table.columns:
            if col.primary_key and isinstance(col.type, BigInteger):
                col.type = Integer()
    _metadata_normalized = True
