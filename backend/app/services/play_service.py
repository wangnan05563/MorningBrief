"""播放服务：进度上报、查询、批量落库。"""
import json
from datetime import datetime, timezone

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlayLog
from app.redis_client import redis_client

# 落库队列单批上限：与 APScheduler 每 1 分钟调度周期配合，避免单次事务过大
FLUSH_BATCH = 500
# DAU 位图保留 90 天，覆盖月度活跃度统计周期
DAU_BITMAP_TTL = 90 * 24 * 3600


class PlayService:
    def __init__(self, db: AsyncSession, redis=None):
        self.db = db
        self.redis = redis or redis_client

    async def report_progress(
        self,
        user_id: int,
        episode_id: int,
        position: int,
        duration: int,
        completed: bool,
    ) -> None:
        """上报播放进度：写 Redis Hash + 落库队列 + DAU 位图。"""
        now_str = datetime.now(timezone.utc).isoformat()

        # Hash 存最新进度，读多写多场景下避免每次落库
        progress_key = f"playlog:progress:{user_id}:{episode_id}"
        await self.redis.hset(
            progress_key,
            mapping={
                "position": position,
                "duration": duration,
                "completed": 1 if completed else 0,
                "updated_at": now_str,
            },
        )

        # 队列条目用于异步落库，保留全字段便于批量 INSERT
        queue_entry = json.dumps(
            {
                "user_id": user_id,
                "episode_id": episode_id,
                "position": position,
                "duration": duration,
                "completed": 1 if completed else 0,
                "played_at": now_str,
            }
        )
        await self.redis.lpush("playlog:flush:queue", queue_entry)

        # DAU 位图：Bitmap 比 Set 更省内存，user_id 作为位偏移
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        dau_key = f"stats:daurset:{today}"
        await self.redis.setbit(dau_key, user_id, 1)
        await self.redis.expire(dau_key, DAU_BITMAP_TTL)

    async def get_progress(self, user_id: int, episode_id: int) -> dict | None:
        """查询播放进度。"""
        progress_key = f"playlog:progress:{user_id}:{episode_id}"
        data = await self.redis.hgetall(progress_key)
        if not data:
            return None

        return {
            "episode_id": episode_id,
            "position": int(data.get("position", 0)),
            "completed": data.get("completed") == "1",
            "updated_at": data.get("updated_at"),
        }

    async def flush_playlog_queue(self) -> int:
        """批量落库：APScheduler 每 1 分钟调用一次。"""
        # 取前 FLUSH_BATCH 条，剩余下次处理，控制单次事务规模
        entries = await self.redis.lrange("playlog:flush:queue", 0, FLUSH_BATCH - 1)
        if not entries:
            return 0

        rows = []
        for raw in entries:
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                # 损坏数据跳过，不阻断批量处理
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

        # 删除已处理条目，避免重复落库
        await self.redis.ltrim("playlog:flush:queue", FLUSH_BATCH, -1)
        return len(rows)
