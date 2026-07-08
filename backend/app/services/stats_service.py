"""统计服务：概览指标与趋势。"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError
from app.models import PlayLog
from app.redis_client import redis_client


class StatsService:
    def __init__(self, db: AsyncSession, redis=None):
        self.db = db
        self.redis = redis or redis_client

    async def get_overview(self, target_date: date) -> dict:
        """单日概览：DAU、播放数、完播率、平均收听时长、广告曝光。"""
        # DAU 从 Redis Bitmap 读取，与 play_service 写入的 key 约定一致
        yyyymmdd = target_date.strftime("%Y%m%d")
        dau_key = f"stats:daurset:{yyyymmdd}"
        dau = await self.redis.bitcount(dau_key)

        # 当日 [00:00, 次日00:00) 区间聚合，MySQL DateTime 列为 naive
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(
            target_date + timedelta(days=1), datetime.min.time()
        )

        # 播放数独立查询，保证无播放记录时返回 0 而非 None
        count_result = await self.db.execute(
            select(func.count(PlayLog.id)).where(
                PlayLog.played_at >= day_start,
                PlayLog.played_at < day_end,
            )
        )
        play_count = count_result.scalar() or 0

        # 完播率与平均时长同表，合并到一次查询减少往返
        avg_result = await self.db.execute(
            select(func.avg(PlayLog.completed), func.avg(PlayLog.duration)).where(
                PlayLog.played_at >= day_start,
                PlayLog.played_at < day_end,
            )
        )
        avg_completed, avg_duration = avg_result.one()

        completion_rate = float(avg_completed) if avg_completed is not None else 0.0
        avg_listen_duration = (
            float(avg_duration) if avg_duration is not None else 0.0
        )

        # 广告曝光 = 播放数 * 3（每期固定三段广告：头/中/尾）
        return {
            "dau": dau,
            "play_count": play_count,
            "completion_rate": completion_rate,
            "avg_listen_duration": avg_listen_duration,
            "ad_impression": play_count * 3,
        }

    async def get_trend(self, metric: str, range_days: int) -> dict:
        """多日趋势：DAU 取 Redis，其余指标从 MySQL 按日聚合。

        返回 dates 与 values 等长对齐，缺数据的日期补 0。
        """
        # today 用 UTC，与 play_service 写 DAU Bitmap 的时区约定一致
        today = datetime.now(timezone.utc).date()
        dates: list[str] = []
        values: list = []

        if metric == "dau":
            # DAU 按日逐个 BITCOUNT，Bitmap 不支持跨日聚合
            for i in range(range_days - 1, -1, -1):
                d = today - timedelta(days=i)
                dates.append(d.isoformat())
                dau_key = f"stats:daurset:{d.strftime('%Y%m%d')}"
                values.append(await self.redis.bitcount(dau_key))
            return {"dates": dates, "values": values}

        # 其余指标走 MySQL 按日聚合
        if metric == "play_count":
            expr = func.count(PlayLog.id)
        elif metric == "completion_rate":
            expr = func.avg(PlayLog.completed)
        elif metric == "avg_listen_duration":
            expr = func.avg(PlayLog.duration)
        else:
            raise BizError(code=400, message=f"不支持的指标: {metric}")

        start_date = today - timedelta(days=range_days - 1)
        day_start = datetime.combine(start_date, datetime.min.time())
        day_end = datetime.combine(
            today + timedelta(days=1), datetime.min.time()
        )

        result = await self.db.execute(
            select(func.date(PlayLog.played_at), expr)
            .where(PlayLog.played_at >= day_start, PlayLog.played_at < day_end)
            .group_by(func.date(PlayLog.played_at))
        )
        # 按"日期字符串 -> 值"建表，便于按预期日期序列对齐补 0
        db_map: dict[str, float] = {}
        for d, v in result.all():
            db_map[str(d)] = float(v) if v is not None else 0.0

        for i in range(range_days - 1, -1, -1):
            d = today - timedelta(days=i)
            dates.append(d.isoformat())
            values.append(db_map.get(d.isoformat(), 0))

        return {"dates": dates, "values": values}
