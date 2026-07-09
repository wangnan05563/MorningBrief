"""统计服务：概览指标与趋势。

V1.2 改造：Redis Bitmap DAU → SQLite COUNT(DISTINCT user_id) 聚合。
- get_overview: DAU 与 play_count 等合并为一次查询
- get_trend: DAU 趋势改为 SQLite GROUP BY func.date 一次聚合
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError
from app.models import PlayLog


class StatsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # V1.2 起 Redis 移除，DAU 改为 SQLite COUNT(DISTINCT user_id) 聚合

    async def get_overview(self, target_date: date) -> dict:
        """单日概览：DAU、播放数、完播率、平均收听时长、广告曝光。

        V1.2 改造：DAU 改为 SQLite COUNT(DISTINCT user_id)，与 play_count 等指标
        合并为一次查询，减少数据库往返。
        """
        # 当日 [00:00, 次日00:00) 区间聚合，DateTime 列为 naive
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(
            target_date + timedelta(days=1), datetime.min.time()
        )

        # DAU、播放数、完播率、平均时长合并为一次查询
        # DAU = COUNT(DISTINCT user_id)，替代原 Redis Bitmap BITCOUNT
        result = await self.db.execute(
            select(
                func.count(func.distinct(PlayLog.user_id)),
                func.count(PlayLog.id),
                func.avg(PlayLog.completed),
                func.avg(PlayLog.duration),
            ).where(
                PlayLog.played_at >= day_start,
                PlayLog.played_at < day_end,
            )
        )
        dau, play_count, avg_completed, avg_duration = result.one()

        dau = dau or 0
        play_count = play_count or 0
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
        """多日趋势：所有指标均从 SQLite 按日聚合。

        V1.2 改造：DAU 趋势从原逐日 Redis BITCOUNT 改为 SQLite
        GROUP BY func.date(played_at) 一次聚合，与其他指标统一。
        返回 dates 与 values 等长对齐，缺数据的日期补 0。
        """
        today = datetime.now(timezone.utc).date()
        dates: list[str] = []
        values: list = []

        # DAU 改为 COUNT(DISTINCT user_id) 按日聚合，与其他指标统一走 SQLite
        if metric == "dau":
            expr = func.count(func.distinct(PlayLog.user_id))
        elif metric == "play_count":
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
