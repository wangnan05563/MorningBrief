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

    async def get_today_episode(self, channel_id: int | None = None) -> dict | list:
        """今日节目，cache-aside：先查缓存，未命中查 DB 后回写。

        channel_id 指定时按频道过滤，返回该频道今日最新一期；
        未指定时返回今日所有已发布节目列表（多频道场景，每个频道保留最新一期）。
        """
        all_key = "episode:today:all"
        if channel_id is not None:
            cache_key = f"episode:today:ch:{channel_id}"
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
        else:
            cached = await self.cache.get(all_key)
            if cached:
                return cached

        today = date.today()
        stmt = select(Episode).where(
            Episode.date == today,
            Episode.status == EpisodeStatus.published,
        )
        if channel_id is not None:
            stmt = stmt.where(Episode.channel_id == channel_id)

        # 全部模式下：每个频道只保留今日最新一期（避免同一频道多次运行累积的多期）
        # 排序：按 channel_id 升序保证输出顺序稳定，前端无需二次排序
        stmt = stmt.order_by(Episode.channel_id.asc(), Episode.id.desc())

        result = await self.db.execute(stmt)
        episodes = result.scalars().all()

        if channel_id is not None:
            # 单频道：取最新一期；空则返回 None（不写缓存，便于下次穿透重查）
            if not episodes:
                return None
            data = self._episode_to_dict(episodes[0])
            await self.cache.set(cache_key, data, ttl=TTL_TODAY)
            return data

        # 全部：每个频道取最新一期（episodes 已按 channel_id asc, id desc 排好）
        seen_channels = set()
        unique = []
        for ep in episodes:
            if ep.channel_id in seen_channels:
                continue
            seen_channels.add(ep.channel_id)
            unique.append(self._episode_to_dict(ep))

        # 任务3：批量统计各 episode 的播放次数（一次 IN 查询避免 N+1）
        if unique:
            from app.models import PlayLog
            ep_ids = [e["id"] for e in unique]
            count_result = await self.db.execute(
                select(PlayLog.episode_id, func.count(PlayLog.id))
                .where(PlayLog.episode_id.in_(ep_ids))
                .group_by(PlayLog.episode_id)
            )
            count_map = {row[0]: row[1] for row in count_result.all()}
            for e in unique:
                e["play_count"] = count_map.get(e["id"], 0)

        await self.cache.set(all_key, unique, ttl=TTL_TODAY)
        return unique

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

    async def get_history(
        self,
        page: int,
        size: int,
        channel_id: int | None = None,
        sort_order: str | None = None,
    ) -> dict:
        """历史列表分页，cache-aside。支持按频道过滤与日期正/倒序。

        任务7：sort_order='desc'（默认，最新在前）/ 'asc'（最旧在前）
        """
        if page < 1 or size < 1:
            return {"total": 0, "list": []}

        # cache_key 包含 sort_order，避免不同排序命中同一缓存
        sort_key = sort_order if sort_order in ("asc", "desc") else "desc"
        cache_key = f"episode:list:page:{page}:ch:{channel_id}:sort:{sort_key}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # 总数独立查询，避免扫描全部数据
        count_stmt = select(func.count(Episode.id)).where(
            Episode.status == EpisodeStatus.published
        )
        if channel_id is not None:
            count_stmt = count_stmt.where(Episode.channel_id == channel_id)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 任务7：按 sort_order 选择排序方向
        date_order = Episode.date.asc() if sort_key == "asc" else Episode.date.desc()
        id_order = Episode.id.asc() if sort_key == "asc" else Episode.id.desc()
        offset = (page - 1) * size
        list_stmt = (
            select(Episode)
            .where(Episode.status == EpisodeStatus.published)
            .order_by(date_order, id_order)
            .offset(offset)
            .limit(size)
        )
        if channel_id is not None:
            list_stmt = list_stmt.where(Episode.channel_id == channel_id)
        result = await self.db.execute(list_stmt)
        episodes = result.scalars().all()

        list_data = [
            {
                "id": ep.id,
                "date": ep.date.isoformat() if ep.date else None,
                "title": ep.title,
                "duration": ep.duration,
                "cover_url": ep.cover_url,
                "categories": ep.categories or [],
                "channel_id": ep.channel_id,
            }
            for ep in episodes
        ]

        # 任务3：批量统计各 episode 的播放次数（一次 IN 查询避免 N+1）
        if list_data:
            from app.models import PlayLog
            ep_ids = [e["id"] for e in list_data]
            count_result = await self.db.execute(
                select(PlayLog.episode_id, func.count(PlayLog.id))
                .where(PlayLog.episode_id.in_(ep_ids))
                .group_by(PlayLog.episode_id)
            )
            count_map = {row[0]: row[1] for row in count_result.all()}
            for e in list_data:
                e["play_count"] = count_map.get(e["id"], 0)

        data = {"total": total, "list": list_data}
        await self.cache.set(cache_key, data, ttl=TTL_LIST)
        return data

    async def search_episodes(self, keyword: str, page: int, size: int) -> dict:
        """节目搜索：按标题模糊匹配。

        MVP 使用 SQLite LIKE，远期可接入 FTS5 全文检索。
        """
        if not keyword or page < 1 or size < 1:
            return {"total": 0, "list": []}

        # 转义 LIKE 特殊字符，避免用户输入 % _ 影响匹配
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"

        # 总数
        count_result = await self.db.execute(
            select(func.count(Episode.id)).where(
                Episode.status == EpisodeStatus.published,
                Episode.title.like(pattern, escape="\\"),
            )
        )
        total = count_result.scalar() or 0

        # 分页
        offset = (page - 1) * size
        result = await self.db.execute(
            select(Episode)
            .where(
                Episode.status == EpisodeStatus.published,
                Episode.title.like(pattern, escape="\\"),
            )
            .order_by(Episode.date.desc(), Episode.id.desc())
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

        return {"total": total, "list": list_data}

    async def get_script(self, episode_id: int) -> dict | None:
        """稿件全文，懒加载：先查 episode 拿 script_id，再查 script 表。

        V1.3：响应追加 sources 字段，展示每段新闻来源 URL（版权溯源合规）。
        sources 来自 Segment.material_ids 关联的 Material 表，按 seq 排序。
        """
        # cache_key 加 v2 后缀：本次新增 segments.cover_url 字段，旧缓存无此字段需失效
        cache_key = f"script:detail:v2:{episode_id}"
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

        # 拼装 sources：遍历 segments 的 material_ids，联表查询 Material
        from app.models import Material
        sources = []
        segments = script.segments or []
        # 收集所有 material_ids（去重）
        all_material_ids = set()
        for seg in segments:
            material_ids = seg.get("material_ids") if isinstance(seg, dict) else None
            if material_ids:
                all_material_ids.update(material_ids)

        materials_map = {}
        if all_material_ids:
            mat_result = await self.db.execute(
                select(Material).where(Material.id.in_(list(all_material_ids)))
            )
            for mat in mat_result.scalars().all():
                materials_map[mat.id] = mat

        # 按 segment seq 顺序拼装 sources，并把每个 segment 第一个有封面的 material
        # 的 cover_url 注入 segment，供前端"虚化背景"和"分段配图"使用
        # 任务10+任务2：segments 缺少 cover_url 字段，前端无法显示分段图片
        enriched_segments = []
        for seg in segments:
            if not isinstance(seg, dict):
                enriched_segments.append(seg)
                continue
            seq = seg.get("seq")
            material_ids = seg.get("material_ids") or []
            seg_cover = None
            for mid in material_ids:
                mat = materials_map.get(mid)
                if mat:
                    sources.append({
                        "seq": seq,
                        "title": mat.title,
                        "url": mat.url,
                        "category": mat.category,
                        "source": mat.source,
                        "cover_url": mat.cover_url,
                    })
                    # 取该 segment 第一个有封面的 material 作为分段封面
                    if not seg_cover and mat.cover_url:
                        seg_cover = mat.cover_url
            enriched_seg = dict(seg)
            if seg_cover:
                enriched_seg["cover_url"] = seg_cover
            enriched_segments.append(enriched_seg)

        data = {
            "episode_id": episode_id,
            "script": script.full_text,
            "segments": enriched_segments,
            "sources": sources,
        }
        await self.cache.set(cache_key, data, ttl=TTL_SCRIPT)
        return data

    async def publish_episode(self, workflow_id: str, review_id: int) -> int:
        """审核通过后创建 episode 并发布。

        流程：
        1. 从 review 表读取 script_id + audio_url + episode_date
        2. 从 script 表读取 categories + estimated_duration
        3. 从 workflow 表读取 channel_id（多频道架构下节目归属频道）
        4. 创建 episode 记录（status=published）
        5. 主动失效缓存：DEL episode:today + episode:list:page:* + episode:detail:{id}
        6. 返回 episode_id
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

        # 3. 读 workflow 获取 channel_id（多频道架构）
        # Workflow 主键字段名为 id（comment=workflow_id），不是 workflow_id
        from app.models import Workflow, Channel
        channel_id = None
        channel_name = None
        if workflow_id:
            wf_result = await self.db.execute(
                select(Workflow.channel_id).where(Workflow.id == workflow_id)
            )
            channel_id = wf_result.scalar_one_or_none()
            if channel_id:
                ch_result = await self.db.execute(
                    select(Channel.name).where(Channel.id == channel_id)
                )
                channel_name = ch_result.scalar_one_or_none()
        # 任务1：标题必须含频道名（无 channel_name 时降级为原模板，避免破坏既有数据）
        date_part = f"{review.episode_date.month}月{review.episode_date.day}日"
        if channel_name:
            title = f"{date_part} · {channel_name}"
        else:
            title = f"{date_part} · 今日要闻"

        # 4. 创建 episode
        episode = Episode(
            date=review.episode_date,
            title=title,
            duration=script.estimated_duration if script else 600,
            audio_url=review.audio_url,
            script_id=review.script_id,
            review_id=review.id,
            categories=script.categories if script else None,
            status=EpisodeStatus.published,
            workflow_id=workflow_id,
            channel_id=channel_id,
            published_at=utcnow_naive(),
        )
        self.db.add(episode)
        await self.db.commit()
        await self.db.refresh(episode)

        # 5. 缓存失效（发布后旧缓存必须清除，否则小程序看到旧节目）
        # TTLCache 不支持 SCAN，用 delete_pattern 一次性清理列表前缀
        await self.cache.delete("episode:today")
        await self.cache.delete_pattern("episode:today:ch:*")
        await self.cache.delete_pattern("episode:list:page:*")

        return episode.id

    @staticmethod
    def _episode_to_dict(episode: Episode) -> dict:
        """统一 Episode 序列化，避免多处重复。

        音频 URL 转换：相对路径 /audio/... 转换为完整 URL 供小程序播放。
        基础 URL 由 AUDIO_BASE_URL 配置决定（真机测试需设为局域网 IP），
        未配置时回退到 localhost（仅开发者工具可用）。
        """
        from app.config import get_settings
        from urllib.parse import quote
        base = get_settings().AUDIO_BASE_URL or 'http://localhost:8000'

        audio_url = episode.audio_url
        if audio_url and audio_url.startswith('/audio/') and not audio_url.startswith('http'):
            audio_url = base + audio_url
        # Percent-encode Chinese/special chars in URL path for BackgroundAudioManager compatibility
        if audio_url and audio_url.startswith('http'):
            from urllib.parse import urlparse, urlunparse, quote
            parsed = urlparse(audio_url)
            encoded_path = quote(parsed.path, safe='/_:')
            audio_url = urlunparse((parsed.scheme, parsed.netloc, encoded_path, parsed.params, parsed.query, parsed.fragment))

        cover_url = episode.cover_url
        if cover_url and cover_url.startswith('/') and not cover_url.startswith('http'):
            cover_url = base + cover_url

        # Same URL encoding for cover images
        if cover_url and cover_url.startswith('http'):
            from urllib.parse import urlparse, urlunparse, quote
            parsed = urlparse(cover_url)
            encoded_path = quote(parsed.path, safe='/_:')
            cover_url = urlunparse((parsed.scheme, parsed.netloc, encoded_path, parsed.params, parsed.query, parsed.fragment))

        # 任务1：把 channel_id 一起序列化，前端在频道列表加载完前可回退到此字段
        return {
            "id": episode.id,
            "date": episode.date.isoformat() if episode.date else None,
            "title": episode.title,
            "duration": episode.duration,
            "audio_url": audio_url,
            "cover_url": cover_url,
            "categories": episode.categories or [],
            "status": episode.status if episode.status else None,
            "channel_id": episode.channel_id,
        }
