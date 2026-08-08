"""播放服务：进度上报、查询、批量落库。

V1.2 改造：Redis Hash/List/Bitmap → COS 对象 + SQLite play_progress 表。
- 进度上报：写 COS play_progress/{user_id}/{episode_id}.json + upsert SQLite play_progress
- 进度查询：读 COS 对象，回退查 SQLite play_progress 表
- 日志落库：从 COS 拉取 playlogs/ 前缀对象，批量写入 play_log 表后删除
- DAU 统计：原 Redis Bitmap 改为 SQLite COUNT(DISTINCT user_id) 聚合（见 stats_service）
"""
import asyncio
import json
from datetime import datetime
from loguru import logger

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.timeutil import localnow_naive
from app.cos.client import cos_client, is_cos_configured
from app.models import PlayLog, PlayProgress, User

# 落库单批上限：与 APScheduler 每 1 分钟调度周期配合，避免单次事务过大
FLUSH_BATCH = 500


class PlayService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # V1.2 起 Redis Hash/List/Bitmap 全部移除，改用 COS 对象 + SQLite play_progress 表

    async def report_progress(
        self,
        user_id: int,
        episode_id: int,
        position: int,
        duration: int,
        completed: bool,
        listened_seconds: int = 0,
    ) -> None:
        """上报播放进度：写 COS 对象 + upsert SQLite play_progress 表 + upsert PlayLog。

        COS 写入失败时降级为仅写 SQLite（COS 未配置时不阻断）。

        PlayLog 记录策略（V1.4 调整）：
        - position >= PLAY_COUNT_THRESHOLD_SEC 时 upsert PlayLog（每用户每节目去重一条）
        - 首次达到阈值：插入 PlayLog，play_count +1
        - 后续上报：仅更新 completed 标志（完播时），不重复计数
        - listened_seconds 增量累加到 User.total_listen_duration，避免 sum(position) 语义错误
        """
        # 项目约定：所有时间字段存为本地 naive datetime（香港 UTC+8，无夏令时）
        # 与 PlayProgress 其他表、StatsService 趋势切分逻辑一致，避免 UTC vs 本地 8 小时偏差
        # C 端读 COS 对象的 updated_at 直接展示，本地时间无需前端再转时区
        now_str = localnow_naive().isoformat()
        completed_flag = 1 if completed else 0
        payload = {
            "user_id": user_id,
            "episode_id": episode_id,
            "position": position,
            "duration": duration,
            "completed": completed_flag,
            "updated_at": now_str,
        }

        # 1. 写 COS 对象（C 端主路径，云函数直读断点续播）
        # COS 未配置时静默降级，不阻断播放进度记录
        try:
            cos_key = f"play_progress/{user_id}/{episode_id}.json"
            await cos_client.put_object(
                Key=cos_key,
                Body=json.dumps(payload).encode("utf-8"),
                ContentType="application/json; charset=utf-8",
            )
        except Exception as e:
            # 区分日志级别：未配置→DEBUG（运维已知，避免噪声）；
            # 已配置但失败→WARNING（真实异常需排障，否则进度只存 SQLite 影响云函数断点续播）
            if is_cos_configured():
                logger.warning("COS put_object 失败（已配置但写入异常），降级为仅写 SQLite: {}", e)
            else:
                logger.debug("COS put_object 跳过（未配置），仅写 SQLite: {}", e)

        # 2. upsert SQLite play_progress 表（B 端备用，每用户每节目仅一条记录）
        stmt = sqlite_insert(PlayProgress).values(
            user_id=user_id,
            episode_id=episode_id,
            position=position,
            duration=duration,
            completed=completed_flag,
            updated_at=localnow_naive(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "episode_id"],
            set_={
                "position": stmt.excluded.position,
                "duration": stmt.excluded.duration,
                "completed": stmt.excluded.completed,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)

        # 3. PlayLog upsert：position 达到阈值时记录/更新（每用户每节目去重一条）
        # 为什么改 upsert：旧逻辑仅 completed=True 时 insert，未完播不计 play_count，
        # 用户听了几秒退出 play_count 永远为 0。改为 position >= 阈值即记录，
        # 完播时仅更新 completed 标志，避免重复计数。
        # 阈值通过 Settings.PLAY_COUNT_THRESHOLD_SEC 配置（默认 30 秒），避免硬编码
        threshold = get_settings().PLAY_COUNT_THRESHOLD_SEC
        should_clear_cache = False
        if position >= threshold:
            existing = await self.db.execute(
                select(PlayLog).where(
                    PlayLog.user_id == user_id,
                    PlayLog.episode_id == episode_id,
                )
            )
            log_row = existing.scalar_one_or_none()
            if log_row is None:
                # 首次达到阈值：插入一条 PlayLog，play_count +1
                # played_at 记录首次达到阈值的时间，用于"最近播放"排序
                self.db.add(
                    PlayLog(
                        user_id=user_id,
                        episode_id=episode_id,
                        position=position,
                        duration=duration,
                        completed=completed_flag,
                        played_at=localnow_naive(),
                    )
                )
                # 同步累加用户累计收听期数（与 play_count 口径一致）
                await self.db.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(total_listen_count=User.total_listen_count + 1)
                )
                # 首次记录触发缓存清除：play_count 实际变化，需让列表刷新
                should_clear_cache = True
            elif completed and not log_row.completed:
                # 已有记录且本次完播：仅更新 completed 标志，不重复计数
                # position/duration 同步更新为完播时的最终值
                log_row.completed = 1
                log_row.position = position
                log_row.duration = duration
            # 其他情况（已有记录且未完播）：不重复 insert，避免灌入大量未完播记录

        # 4. 累加用户累计收听时长（任务7）
        # 为什么用增量累加而非 sum(position)：PlayProgress.position 是最后位置（upsert 覆盖），
        # 重新听同一段只会覆盖不会累加，sum 会严重低估实际收听时长。
        # 前端计算本次上报周期内的增量 listened_seconds 透传，后端直接累加到 User 字段。
        if listened_seconds > 0:
            await self.db.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    total_listen_duration=User.total_listen_duration + listened_seconds
                )
            )

        await self.db.commit()

        # 5. 首次达到阈值时清除节目列表缓存，让下次请求拿到最新 play_count
        # 为什么放 commit 后：缓存失效必须在数据落库之后，避免并发请求读到旧值再回填缓存
        # 为什么只在首次记录时清除：后续上报不改变 play_count，无需频繁清缓存
        if should_clear_cache:
            try:
                from app.cache.manager import cache as cache_manager
                await cache_manager.delete("episode:today:all")
                await cache_manager.delete_pattern("episode:today:ch:*")
                await cache_manager.delete_pattern("episode:list:page:*")
            except Exception as e:
                # 缓存失效失败不阻断主流程：下次缓存 TTL 过期后自然刷新
                logger.debug("清除节目列表缓存失败（不阻断）: {}", e)

    async def get_progress(self, user_id: int, episode_id: int) -> dict | None:
        """查询播放进度：优先读 COS 对象，回退查 SQLite play_progress 表。"""
        # 1. 读 COS 对象（主路径）
        try:
            cos_key = f"play_progress/{user_id}/{episode_id}.json"
            body = await cos_client.get_object_bytes(cos_key)
            if body is not None:
                try:
                    data = json.loads(body)
                    return {
                        "episode_id": episode_id,
                        "position": int(data.get("position", 0)),
                        "completed": data.get("completed") == 1,
                        "updated_at": data.get("updated_at"),
                    }
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            # 区分日志级别：未配置→DEBUG（与 report_progress 一致）；
            # 已配置但失败→WARNING（COS 是主路径，读取异常会导致回退查 SQLite，影响响应延迟）
            if is_cos_configured():
                logger.warning("COS get_object_bytes 失败（已配置但读取异常）key={}: {}", cos_key, e)
            else:
                logger.debug("COS get_object_bytes 跳过（未配置）key={}: {}", cos_key, e)

        # 2. 回退查 SQLite play_progress 表
        result = await self.db.execute(
            select(PlayProgress).where(
                PlayProgress.user_id == user_id,
                PlayProgress.episode_id == episode_id,
            )
        )
        progress = result.scalar_one_or_none()
        if progress is None:
            return None
        return {
            "episode_id": episode_id,
            "position": progress.position,
            "completed": bool(progress.completed),
            "updated_at": progress.updated_at.isoformat() if progress.updated_at else None,
        }

    async def flush_playlog_queue(self) -> int:
        """批量落库：从 COS 拉取 playlogs/ 前缀对象，写入 play_log 表后删除。"""
        objects = await cos_client.list_objects(Prefix="playlogs/")
        if not objects:
            return 0

        objects = objects[:FLUSH_BATCH]

        rows = []
        keys_to_delete = []
        for obj in objects:
            key = obj.get("Key")
            if not key:
                continue
            body = await cos_client.get_object_bytes(key)
            if body is None:
                # body 为空的对象也需删除，避免下次重复拉取占用配额
                keys_to_delete.append(key)
                continue
            try:
                item = json.loads(body)
                # 单条坏数据（缺字段/时间格式错）只跳过该条，不影响整批入库
                rows.append(
                    {
                        "user_id": item.get("user_id"),
                        "episode_id": item["episode_id"],
                        "position": item.get("position", 0),
                        "duration": item.get("duration"),
                        "completed": item.get("completed", 0),
                        "played_at": datetime.fromisoformat(item["played_at"]),
                    }
                )
                keys_to_delete.append(key)
            except (KeyError, ValueError, TypeError) as e:
                # 坏数据不加入 keys_to_delete，保留在 COS 中供排查；
                # 若直接删除会永久丢失，且下次 flush 不会重试
                logger.warning("playlog 坏数据跳过 key={} err={}", key, e)
                continue

        if rows:
            await self.db.execute(insert(PlayLog), rows)
            await self.db.commit()

        # 并发删除已入库的 COS 对象：gather + return_exceptions 确保单条失败不阻断其他删除
        # COS 默认 QPS 100，FLUSH_BATCH 上限 500 不会触发限流；
        # 后台 APScheduler 任务不在请求路径，但并发可显著缩短批量删除耗时
        if keys_to_delete:
            results = await asyncio.gather(
                *[cos_client.delete_object(key) for key in keys_to_delete],
                return_exceptions=True,
            )
            for key, result in zip(keys_to_delete, results):
                if isinstance(result, Exception):
                    # 删除失败不阻断：下次 flush 会重复入库，记录 WARNING 便于排查
                    logger.warning("COS delete_object 失败 key={}: {}", key, result)

        return len(rows)
