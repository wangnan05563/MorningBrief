"""统计服务：概览指标与趋势。

V1.2 改造：Redis Bitmap DAU → SQLite COUNT(DISTINCT user_id) 聚合。
- get_overview: DAU 与 play_count 等合并为一次查询
- get_trend: DAU 趋势改为 SQLite GROUP BY func.date 一次聚合
"""
import json
from datetime import date, datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError
from app.models import PlayLog, Material, Channel
from app.models.material import MaterialStatus


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
        # 项目约定：所有时间字段存为本地 naive datetime（香港 UTC+8，无夏令时）
        # 与 get_overview 的 day_start/day_end 切分逻辑保持一致，避免 UTC vs 本地偏差
        today = date.today()
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

    async def get_channel_health(self, range_days: int = 7) -> dict:  # NOSONAR S3776: 健康度仪表盘聚合多维度数据，职责单一
        """频道素材健康度仪表盘：按频道聚合近 N 天入库趋势与当日待改写量。

        用于运维发现"某频道长期无新素材"或"RSS 源衰退"等问题：
        - 近 7 天每日入库数趋势：连续 0 入库说明 RSS 源失效
        - 当日 pending 数：<3 时 rewriter 可能无素材可用，触发降级回溯
        - 健康状态：healthy / warning / critical，按入库连续性与 pending 数综合判定

        Args:
            range_days: 趋势回溯天数，默认 7（与 rewriter FALLBACK_DAYS 对齐）

        Returns:
            {
                "channels": [
                    {
                        "channel_id": 1, "name": "科技前沿",
                        "rss_source_count": 5, "keyword_count": 12,
                        "today_pending": 8,
                        "range_total": 35,
                        "daily_trend": [{"date": "2026-07-15", "count": 5}, ...],
                        "health_status": "healthy"
                    }, ...
                ],
                "summary": {"healthy": 6, "warning": 2, "critical": 1, "total": 9}
            }
        """
        # 项目约定：所有时间字段存为本地 naive datetime（香港 UTC+8，无夏令时）
        # 与 crawled_at 存储方式一致，避免 UTC vs 本地 8 小时偏差导致凌晨数据漏统计
        today = date.today()
        day_start = datetime.combine(today - timedelta(days=range_days - 1), datetime.min.time())
        day_end = datetime.combine(today + timedelta(days=1), datetime.min.time())

        # 1. 查询所有频道（含未激活，便于全局观察）
        ch_result = await self.db.execute(
            select(Channel).order_by(Channel.id)
        )
        channels = ch_result.scalars().all()

        # 2. 近 N 天每日入库数（按 channel_id + date 聚合，一次查询）
        # func.date(crawled_at) 在 SQLite 返回字符串 YYYY-MM-DD
        trend_result = await self.db.execute(
            select(
                Material.channel_id,
                func.date(Material.crawled_at),
                func.count(Material.id),
            ).where(
                Material.crawled_at >= day_start,
                Material.crawled_at < day_end,
            ).group_by(Material.channel_id, func.date(Material.crawled_at))
        )
        # 建表 {(channel_id, date_str): count}，供后续填充每日序列
        trend_map: dict[tuple[int | None, str], int] = {}
        for cid, d, cnt in trend_result.all():
            trend_map[(cid, str(d))] = int(cnt or 0)

        # 3. 当日 pending 素材数（按 channel_id 聚合）
        # pending 数是 rewriter 是否可用的直接指标，selected/skipped 已被处理过
        today_start = datetime.combine(today, datetime.min.time())
        pending_result = await self.db.execute(
            select(
                Material.channel_id,
                func.count(Material.id),
            ).where(
                Material.crawled_at >= today_start,
                Material.crawled_at < day_end,
                Material.status == MaterialStatus.pending.value,
            ).group_by(Material.channel_id)
        )
        pending_map: dict[int | None, int] = {}
        for cid, cnt in pending_result.all():
            pending_map[cid] = int(cnt or 0)

        # 4. 组装每个频道的健康数据
        channel_list = []
        summary = {"healthy": 0, "warning": 0, "critical": 0, "total": 0}

        for ch in channels:
            # 每日入库趋势序列：补 0 对齐日期，便于前端折线图渲染
            daily_trend = []
            range_total = 0
            zero_days = 0
            for i in range(range_days - 1, -1, -1):
                d = (today - timedelta(days=i)).isoformat()
                cnt = trend_map.get((ch.id, d), 0)
                daily_trend.append({"date": d, "count": cnt})
                range_total += cnt
                if cnt == 0:
                    zero_days += 1

            today_pending = pending_map.get(ch.id, 0)

            # RSS 源数量与关键词数量：从配置 JSON / 逗号字符串解析
            rss_source_count = 0
            if ch.rss_sources:
                try:
                    parsed = json.loads(ch.rss_sources)
                    if isinstance(parsed, list):
                        rss_source_count = len(parsed)
                except (json.JSONDecodeError, TypeError):
                    pass
            keyword_count = 0
            if ch.keywords:
                keyword_count = len([k for k in ch.keywords.split(",") if k.strip()])

            # 健康状态判定：
            # - critical: 近 N 天 0 入库（RSS 源全部失效 / 配置错误）
            # - warning: 近 N 天有入库但当日 pending < 3（rewriter 可用素材不足）
            #            或 zero_days >= N-1（仅 1 天有素材，源不稳定）
            # - healthy: 近 N 天有 ≥2 天入库且当日 pending ≥ 3
            if range_total == 0:
                status = "critical"
            elif today_pending < 3 or zero_days >= range_days - 1:
                status = "warning"
            else:
                status = "healthy"

            summary[status] += 1
            summary["total"] += 1

            channel_list.append({
                "channel_id": ch.id,
                "name": ch.name,
                "description": ch.description,
                "is_active": bool(ch.is_active),
                "rss_source_count": rss_source_count,
                "keyword_count": keyword_count,
                "today_pending": today_pending,
                "range_total": range_total,
                "daily_trend": daily_trend,
                "health_status": status,
            })

        return {"channels": channel_list, "summary": summary}
