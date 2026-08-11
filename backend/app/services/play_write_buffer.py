"""播放进度写缓冲：进程内聚合 + 定时批量落库（P1 性能优化）。

背景：
- report_progress 是压测中频率最高的写接口（每次播放 tick 一次），原实现每请求
  一次 upsert + commit，全部挤在全局写锁上，虽已消除 database is locked 报错，
  但单写者吞吐受限。
- P1 方案（与架构决策一致）：把同一时间窗内的多笔进度写聚合成一批，用单条
  批量 VALUES + 单 commit 落库，把 N 次请求 → 1 次事务，显著提升写吞吐。

安全网设计：
- COS 主路径仍在 report_progress 内立即写（断点续播位置零丢失），本缓冲只负责 SQLite 侧。
- 缓冲最多延迟 BUFFER_FLUSH_INTERVAL 秒落库；play_count / listen_duration 为非关键统计，
  短暂延迟可接受；崩溃最多丢失未 flush 的缓冲（COS 上的续播位置不丢）。
- 背压：pending 超过 BUFFER_MAX_PENDING 时同步 flush，防止 OOM。
- 关闭阶段 stop() 执行最终 flush，尽量不丢数据。

一致性：
- 与全局写锁共用 _write_lock（via serialized_write），与 comments/favorites 等写互斥，
  保证 batch 内"首次达到阈值才 +1 play_count"的判定在并发下不重复计数。
"""
import asyncio
from collections import OrderedDict, defaultdict

from loguru import logger
from sqlalchemy import or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import get_settings
from app.core.write_gate import serialized_write
from app.models import PlayLog, PlayProgress, User

# 缓冲配置
BUFFER_FLUSH_SIZE = 100          # 累积到该条数立即触发异步 flush
BUFFER_FLUSH_INTERVAL = 1.0      # 定时 flush 间隔（秒）
BUFFER_MAX_PENDING = 5000        # 超过则同步 flush（背压，防 OOM）


class PlayWriteBuffer:
    """播放进度写缓冲单例：add() 入队，flush() 批量落库。"""

    def __init__(self):
        self._buf: list[dict] = []
        self._lock = asyncio.Lock()  # 保护 _buf 与 _flushing 标志
        self._flushing = False
        self._task = None
        self._bg_tasks: set = set()  # 保留异步 flush 任务引用，防被 GC 提前回收
        self._stop = False

    async def add(self, event: dict) -> None:
        """入队一笔进度写。非阻塞（仅追加到内存列表）。"""
        async with self._lock:
            self._buf.append(event)
            size = len(self._buf)
        if size >= BUFFER_MAX_PENDING:
            # 背压：pending 过多，同步 flush 防 OOM（会短暂占用调用协程）
            await self.flush()
        elif size >= BUFFER_FLUSH_SIZE:
            # 达到批量阈值，fire-and-forget 异步 flush（不阻塞上报请求）
            # 保留任务引用到 _bg_tasks，避免事件循环回收未完成的 task 导致
            # "Task was destroyed but it is pending" 警告与潜在丢数据（维度 198）
            task = asyncio.create_task(self._safe_flush())
            self._bg_tasks.add(task)
            task.add_done_callback(self._bg_tasks.discard)

    async def start(self) -> None:
        """启动周期 flush 后台任务（在 lifespan 中调用）。"""
        if self._task is not None:
            return
        self._stop = False
        self._task = asyncio.create_task(self._loop())
        logger.info("[startup] PlayWriteBuffer 周期 flush 已启动")

    async def stop(self) -> None:
        """停止周期任务并执行最终 flush（在 lifespan 关闭阶段调用）。"""
        self._stop = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        # 关闭前最终 flush，尽量不丢缓冲中的进度写
        try:
            await self.flush()
        except Exception:
            logger.exception("[shutdown] PlayWriteBuffer 最终 flush 失败")
        logger.info("[shutdown] PlayWriteBuffer 已停止")

    async def _loop(self) -> None:
        while not self._stop:
            await asyncio.sleep(BUFFER_FLUSH_INTERVAL)
            if self._stop:
                break
            try:
                await self.flush()
            except Exception:
                logger.exception("PlayWriteBuffer 周期 flush 失败")

    async def _safe_flush(self) -> None:
        try:
            await self.flush()
        except Exception:
            logger.exception("PlayWriteBuffer 异步 flush 失败")

    async def flush(self, session=None) -> None:
        """把当前缓冲快照批量落库（与全局写锁互斥，保证 play_count 判定一致）。

        :param session: 可选。提供时复用调用方 session 落库（测试可在同一连接内
            立即观察到 PlayLog / play_count 变化）；为 None 时使用全局写锁内的
            独立 ``AsyncSessionLocal()``（生产默认行为）。
        """
        async with self._lock:
            if self._flushing or not self._buf:
                return
            self._flushing = True
            batch = self._buf
            self._buf = []
        should_clear_cache = False
        try:
            should_clear_cache = await serialized_write(
                lambda s: self._persist(s, batch), session=session
            )
        except Exception:
            logger.exception("PlayWriteBuffer 批量持久化失败（本批数据可能丢失）")
            should_clear_cache = False
        finally:
            async with self._lock:
                self._flushing = False

        # 缓存失效必须在落库之后（与 report_progress 原语义一致）
        if should_clear_cache:
            try:
                from app.cache.manager import cache as cache_manager
                await cache_manager.delete("episode:today:all")
                await cache_manager.delete_pattern("episode:today:ch:*")
                await cache_manager.delete_pattern("episode:list:page:*")
            except Exception as e:
                logger.debug("清除节目列表缓存失败（不阻断）: {}", e)

    @staticmethod
    async def _persist(session, batch: list[dict]) -> bool:
        """在独立 session 内批量持久化一批进度写，返回是否触发了 play_count 变化。"""
        threshold = get_settings().PLAY_COUNT_THRESHOLD_SEC
        should_clear_cache = False

        # 1) play_progress 批量 upsert（批量 VALUES + ON CONFLICT DO UPDATE）
        pp_rows = [
            {
                "user_id": ev["user_id"],
                "episode_id": ev["episode_id"],
                "position": ev["position"],
                "duration": ev["duration"],
                "completed": ev["completed"],
                "updated_at": ev["now"],
            }
            for ev in batch
        ]
        if pp_rows:
            stmt = sqlite_insert(PlayProgress).values(pp_rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "episode_id"],
                set_={
                    "position": stmt.excluded.position,
                    "duration": stmt.excluded.duration,
                    "completed": stmt.excluded.completed,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            await session.execute(stmt)

        # 2) 按 (user_id, episode_id) 分组（保留插入顺序，最后一条为最新状态）
        groups: "OrderedDict[tuple, list]" = OrderedDict()
        for ev in batch:
            key = (ev["user_id"], ev["episode_id"])
            groups.setdefault(key, []).append(ev)

        # 3) 查询这些 key 是否已存在 PlayLog（单条 OR 复合条件，一次 IN 查询）
        existing: set = set()
        if groups:
            conds = [
                (PlayLog.user_id == u) & (PlayLog.episode_id == e)
                for (u, e) in groups
            ]
            res = await session.execute(
                select(PlayLog.user_id, PlayLog.episode_id).where(or_(*conds))
            )
            existing = {(r[0], r[1]) for r in res.all()}

        # 4) 加载已存在的 PlayLog 行，用于完播标志更新
        existing_rows: dict = {}
        if existing:
            conds2 = [
                (PlayLog.user_id == u) & (PlayLog.episode_id == e)
                for (u, e) in existing
            ]
            res = await session.execute(select(PlayLog).where(or_(*conds2)))
            for row in res.scalars().all():
                existing_rows[(row.user_id, row.episode_id)] = row

        new_logs = []
        user_count_inc: "defaultdict[int, int]" = defaultdict(int)
        user_dur_inc: "defaultdict[int, int]" = defaultdict(int)

        for (u, e), evs in groups.items():
            last = evs[-1]
            # 累加本批该用户的收听时长增量
            dur_inc = sum(ev["listened_seconds"] for ev in evs)
            user_dur_inc[u] += dur_inc

            if (u, e) in existing:
                # 已有记录：仅在本批出现完播且其记录未标记完播时更新
                row = existing_rows[(u, e)]
                if last["completed"] and not row.completed:
                    row.completed = 1
                    row.position = last["position"]
                    row.duration = last["duration"]
            else:
                # 新用户+节目：本批任一上报达到阈值即插入一条 + play_count +1
                reached = any(ev["position"] >= threshold for ev in evs)
                if reached:
                    new_logs.append(
                        PlayLog(
                            user_id=u,
                            episode_id=e,
                            position=last["position"],
                            duration=last["duration"],
                            completed=last["completed"],
                            played_at=last["now"],
                        )
                    )
                    user_count_inc[u] += 1
                    should_clear_cache = True

        if new_logs:
            session.add_all(new_logs)

        # 5) 用户累计统计：按用户聚合后单条 UPDATE（count + duration 合并为一次）
        for u in set(user_count_inc) | set(user_dur_inc):
            vals = {}
            if user_count_inc.get(u):
                vals["total_listen_count"] = (
                    User.total_listen_count + user_count_inc[u]
                )
            if user_dur_inc.get(u):
                vals["total_listen_duration"] = (
                    User.total_listen_duration + user_dur_inc[u]
                )
            if vals:
                await session.execute(
                    update(User).where(User.id == u).values(**vals)
                )

        return should_clear_cache


# 模块级单例（与 cache 单例同模式）
play_write_buffer = PlayWriteBuffer()
