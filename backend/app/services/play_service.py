"""播放服务：进度上报、查询、批量落库。

V1.2 改造：Redis Hash/List/Bitmap → COS 对象 + SQLite play_progress 表。
- 进度上报：写 COS play_progress/{user_id}/{episode_id}.json + upsert SQLite play_progress
- 进度查询：读 COS 对象，回退查 SQLite play_progress 表
- 日志落库：从 COS 拉取 playlogs/ 前缀对象，批量写入 play_log 表后删除
- DAU 统计：原 Redis Bitmap 改为 SQLite COUNT(DISTINCT user_id) 聚合（见 stats_service）
"""
import json
from datetime import datetime, timezone
from loguru import logger

from sqlalchemy import insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cos.client import cos_client
from app.models import PlayLog, PlayProgress

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
    ) -> None:
        """上报播放进度：写 COS 对象 + upsert SQLite play_progress 表。

        COS 写入失败时降级为仅写 SQLite（COS 未配置时不阻断）。
        """
        now_str = datetime.now(timezone.utc).isoformat()
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
            logger.debug("COS put_object 失败（可能未配置），降级为仅写 SQLite: %s", e)

        # 2. upsert SQLite play_progress 表（B 端备用，每用户每节目仅一条记录）
        stmt = sqlite_insert(PlayProgress).values(
            user_id=user_id,
            episode_id=episode_id,
            position=position,
            duration=duration,
            completed=completed_flag,
            updated_at=datetime.now(timezone.utc),
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
        await self.db.commit()

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
        except Exception:
            pass

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
            keys_to_delete.append(key)
            body = await cos_client.get_object_bytes(key)
            if body is None:
                continue
            try:
                item = json.loads(body)
            except json.JSONDecodeError:
                continue
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

        if rows:
            await self.db.execute(insert(PlayLog), rows)
            await self.db.commit()

        for key in keys_to_delete:
            try:
                await cos_client.delete_object(key)
            except Exception:
                pass

        return len(rows)
