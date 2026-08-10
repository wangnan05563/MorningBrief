"""SQLite 单写者串行化闸门（P0-1 性能优化，进程内、不引入 MySQL/Redis）。

问题根因
--------
压测实测 ``sqlite3.OperationalError: database is locked`` 累计 **67,186 次**，
写接口错误率高达 59%。根因是 SQLite 为*单写者*数据库：每个写接口在请求路径内
各自开启独立写事务并 ``commit``，高并发下多个连接同时抢写锁，超过
``busy_timeout``(默认 5s) 即抛锁错误 → 全局异常处理器转 HTTP 500。

方案
----
用进程内全局 ``asyncio.Lock`` 串行化所有“写事务的提交阶段”，任意时刻仅一个写
事务在进行，从机制上消除并发写锁竞争：

- 仅串行化“写”，读请求不受影响（WAL 模式下读不阻塞写、写不阻塞读）。
- 请求仍等待写完成再返回（语义不变：C 端进度/评论/收藏都需要即时结果）。
- 与 config.SQLITE_BUSY_TIMEOUT_MS 上调形成双重兜底。

用法
----
1. 写逻辑可用独立 session 跑时，用 ``serialized_write(fn)``（推荐，解耦请求 session）：
       should_clear = await serialized_write(lambda s: _do_write(s, **kw))
2. 写逻辑必须复用请求 session（如路由内直接 ``db.add/commit``）时，用全局锁：
       from app.core.write_gate import write_lock
       async with write_lock:
           db.add(obj); await db.commit()
"""
import asyncio
from typing import Awaitable, Callable, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal

T = TypeVar("T")

# 全局写锁：保证同一时刻只有一个写事务在提交。
_write_lock = asyncio.Lock()


async def serialized_write(
    fn: Callable[[AsyncSession], Awaitable[T]],
    session: AsyncSession | None = None,
) -> T:
    """串行执行写逻辑：用独立 session 跑 fn 后提交，避免并发写锁竞争。

    fn 接收独立 ``AsyncSession``，返回结果透传给调用方（如是否需要清缓存的标记）。
    异常时自动 rollback，不吞异常。

    :param session: 可选。提供时复用调用方 session 跑 fn（用于测试等需在同一
        连接/事务内观察落库结果的场景）；为 None 时使用全局 ``AsyncSessionLocal()``
        （生产默认行为，连接独立文件库）。
    """
    async with _write_lock:
        own_session = session is None
        s = session if session is not None else AsyncSessionLocal()
        try:
            result = await fn(s)
            await s.commit()
            return result
        except Exception:
            await s.rollback()
            raise
        finally:
            if own_session:
                await s.close()


def write_lock() -> asyncio.Lock:
    """返回全局写锁，供需要在现有请求 session 上串行化提交的场景使用。

    与 ``serialized_write`` 共用同一把锁，确保全应用写事务统一串行。
    """
    return _write_lock
