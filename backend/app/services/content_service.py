"""内容服务：今日节目、节目详情、历史列表、稿件、发布。

V1.2 起缓存层从 Redis 改为进程内 TTLCache：
- TTLCache 直接存 Python dict，无需 json 序列化
- 列表缓存逐页删除改为 delete_pattern 一次性清理
"""
from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache as cache_manager
from app.core.timeutil import utcnow_naive
from app.models import Episode, Script, Review, EpisodeStatus

# 缓存 TTL（秒）：与数据变更频率匹配
TTL_TODAY = 3600   # 今日节目 1 小时
TTL_DETAIL = 1800  # 节目详情 30 分钟
TTL_LIST = 600     # 列表 10 分钟
TTL_SCRIPT = 1800  # 稿件 30 分钟


class ContentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # 进程内缓存：替代原 Redis cache-aside，避免热点查询打 DB
        self.cache = cache_manager

    async def get_today_episode(self) -> dict | None:
        """今日节目，cache-aside：先查缓存，未命中查 DB 后回写。"""
        cache_key = "episode:today"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        today = date.today()
        result = await self.db.execute(
            select(Episode).where(
                Episode.date == today,
                Episode.status == EpisodeStatus.published,
            )
        )
        episode = result.scalar_one_or_none()
        if episode is None:
            return None

        data = self._episode_to_dict(episode)
        await self.cache.set(cache_key, data, ttl=TTL_TODAY)
        return data

    async def get_episode_by_id(self, episode_id: int) -> dict | None:
        """节目详情，cache-aside。"""
        cache_key = f"episode:detail:{episode_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        result = await self.db.execute(
            select(Episode).where(Episode.id == episode_id)
        )
        episode = result.scalar_one_or_none()
        if episode is None:
            return None

        data = self._episode_to_dict(episode)
        await self.cache.set(cache_key, data, ttl=TTL_DETAIL)
        return data

    async def get_history(self, page: int, size: int) -> dict:
        """历史列表分页，cache-aside。"""
        if page < 1 or size < 1:
            return {"total": 0, "list": []}

        cache_key = f"episode:list:page:{page}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # 总数独立查询，避免扫描全部数据
        count_result = await self.db.execute(
            select(func.count(Episode.id)).where(
                Episode.status == EpisodeStatus.published
            )
        )
        total = count_result.scalar() or 0

        # 按日期倒序，最新一期在最前
        offset = (page - 1) * size
        result = await self.db.execute(
            select(Episode)
            .where(Episode.status == EpisodeStatus.published)
            .order_by(Episode.date.desc())
            .offset(offset)
            .limit(size)
        )
        episodes = result.scalars().all()

        list_data = [
            {
                "id": ep.id,
                "date": ep.date.isoformat() if ep.date else None,
                "title": ep.title,
                "duration": ep.duration,
                "cover_url": ep.cover_url,
                "categories": ep.categories or [],
            }
            for ep in episodes
        ]

        data = {"total": total, "list": list_data}
        await self.cache.set(cache_key, data, ttl=TTL_LIST)
        return data

    async def get_script(self, episode_id: int) -> dict | None:
        """稿件全文，懒加载：先查 episode 拿 script_id，再查 script 表。"""
        cache_key = f"script:detail:{episode_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # 先取 script_id，避免无条件扫 script 表
        result = await self.db.execute(
            select(Episode.script_id).where(Episode.id == episode_id)
        )
        script_id = result.scalar_one_or_none()
        if script_id is None:
            return None

        result = await self.db.execute(
            select(Script).where(Script.id == script_id)
        )
        script = result.scalar_one_or_none()
        if script is None:
            return None

        data = {
            "episode_id": episode_id,
            "script": script.full_text,
            "segments": script.segments or [],
        }
        await self.cache.set(cache_key, data, ttl=TTL_SCRIPT)
        return data

    async def publish_episode(self, workflow_id: str, review_id: int) -> int:
        """审核通过后创建 episode 并发布。

        流程：
        1. 从 review 表读取 script_id + audio_url + episode_date
        2. 从 script 表读取 categories + estimated_duration
        3. 创建 episode 记录（status=published）
        4. 主动失效缓存：DEL episode:today + episode:list:page:* + episode:detail:{id}
        5. 返回 episode_id
        """
        # 1. 读 review
        result = await self.db.execute(
            select(Review).where(Review.id == review_id)
        )
        review = result.scalar_one_or_none()
        if review is None:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("审核记录不存在")

        # 2. 读 script 获取分类与时长
        result = await self.db.execute(
            select(Script).where(Script.id == review.script_id)
        )
        script = result.scalar_one_or_none()

        # 3. 创建 episode
        episode = Episode(
            date=review.episode_date,
            title=f"{review.episode_date.month}月{review.episode_date.day}日 · 今日要闻",
            duration=script.estimated_duration if script else 600,
            audio_url=review.audio_url,
            script_id=review.script_id,
            review_id=review.id,
            categories=script.categories if script else None,
            status=EpisodeStatus.published,
            workflow_id=workflow_id,
            published_at=utcnow_naive(),
        )
        self.db.add(episode)
        await self.db.commit()
        await self.db.refresh(episode)

        # 4. 缓存失效（发布后旧缓存必须清除，否则小程序看到旧节目）
        # TTLCache 不支持 SCAN，用 delete_pattern 一次性清理列表前缀
        await self.cache.delete("episode:today")
        await self.cache.delete_pattern("episode:list:page:*")

        return episode.id

    def _episode_to_dict(self, episode: Episode) -> dict:
        """统一 Episode 序列化，避免多处重复。"""
        return {
            "id": episode.id,
            "date": episode.date.isoformat() if episode.date else None,
            "title": episode.title,
            "duration": episode.duration,
            "audio_url": episode.audio_url,
            "cover_url": episode.cover_url,
            "categories": episode.categories or [],
            "status": episode.status if episode.status else None,
        }
