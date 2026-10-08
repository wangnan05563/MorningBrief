"""数据库连接管理（V1.2：SQLite + aiosqlite 替代 MySQL + aiomysql）。

SQLAlchemy 异步引擎 + 会话工厂。
会话通过 FastAPI 依赖注入，确保请求结束自动关闭。

SQLite 适配要点：
1. 连接池（T01662）：默认有界复用池 AsyncAdaptedQueuePool（pool_size/max_overflow 走 settings），
   消除 NullPool 每请求 ≈41ms 的建连+PRAGMA 开销；SQLITE_POOL_ENABLED=False 回退 NullPool
2. PRAGMA 配置通过 SQLAlchemy 事件监听器在每个连接建立时注入（池化后每条连接仅执行一次，正是收益来源）
3. WAL 模式：读不阻塞写、写不阻塞读，仅写-写冲突触发 BUSY
4. busy_timeout：写冲突时自动等待（替代 MySQL 死锁重试）；全局写锁仍串行化应用层提交
"""
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from app.config import get_settings

settings = get_settings()

# 连接池策略（T01662）：
# - 默认 AsyncAdaptedQueuePool（有界复用池）：SQLite 文件库引擎默认 NullPool，每个请求
#   checkout 都要「新建连接 + 4 条 PRAGMA」，checkin 即关闭，实测固定开销 ≈40.84ms/请求
#   （_validate/t01617_conn_cost.py → t01617_conn_cost.json）。池化后连接连同 PRAGMA 初始化
#   在池内复用，该开销降为 ~1-2ms（pre_ping 一次 SELECT 1）。
# - pool_pre_ping=True：checkout 前轻量探活，连接失效即重建，避免「失效连接缺 PRAGMA」的静默降级。
# - reset_on_return 默认 rollback：checkin 时结束事务，WAL 下不会跨请求持有读快照（写后立读无脏读）。
# - 不用 StaticPool：单连接共享会把并发读串行化，抵消 WAL 多连接并发读收益。
# - SQLITE_POOL_ENABLED=False 回退 NullPool（改造前行为），供 A/B 对比与故障回退。
_engine_kwargs: dict = {
    "echo": settings.APP_DEBUG,
    # SQLite 在 WAL 模式下支持多连接并发读，check_same_thread=False 允许跨线程
    # 写经全局写锁串行化（单写者上限），池化不改变该约束。
    "connect_args": {"check_same_thread": False},
}
if settings.SQLITE_POOL_ENABLED:
    _engine_kwargs.update(
        poolclass=AsyncAdaptedQueuePool,
        pool_size=settings.SQLITE_POOL_SIZE,
        max_overflow=settings.SQLITE_MAX_OVERFLOW,
        pool_pre_ping=True,
    )
else:
    _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(settings.sqlite_url, **_engine_kwargs)

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
