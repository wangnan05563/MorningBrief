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
from app.core.write_gate import write_lock
from app.models import PlayLog, PlayProgress, User
from app.services.play_write_buffer import play_write_buffer

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

        P0-1 优化：SQLite 写（步骤 2-4）统一纳入全局写锁串行化，任意时刻仅一个写事务
        提交，从机制上消除压测实测的 database is locked（67,186 次 / 写错误率 59%）。
        COS 主路径在锁外，网络 IO 不串行化。
        """
        # 项目约定：所有时间字段存为本地 naive datetime（香港 UTC+8，无夏令时）
        now = localnow_naive()
        now_str = now.isoformat()
        completed_flag = 1 if completed else 0
        payload = {
            "user_id": user_id,
            "episode_id": episode_id,
            "position": position,
            "duration": duration,
            "completed": completed_flag,
            "updated_at": now_str,
        }

        # 1. 写 COS 对象（C 端主路径，云函数直读断点续播）— 在写锁之外，网络 IO 不串行化
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

        # 2. SQLite 写改为缓冲聚合（P1 优化）：COS 续播位置已立即落盘（步骤1），
        #    此处仅把 SQLite 侧的进度/play_count/收听时长入队，由 PlayWriteBuffer
        #    定时批量落库。把 N 次上报 → 1 次批量事务，显著降低全局写锁竞争与提交频率。
        #    语义变化：play_count 与收听时长变为秒级最终一致（≤BUFFER_FLUSH_INTERVAL）；
        #    续播位置因 COS 实时写入不受影响。缓存失效也在批量落库后统一处理。
        await play_write_buffer.add({
            "user_id": user_id,
            "episode_id": episode_id,
            "position": position,
            "duration": duration,
            "completed": completed_flag,
            "listened_seconds": listened_seconds,
            "now": now,
        })

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
            # 与全局写锁互斥，避免后台批量落库与请求路径/缓冲落库并发写竞争
            async with write_lock():
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
