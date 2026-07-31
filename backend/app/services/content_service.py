"""内容服务：今日节目、节目详情、历史列表、稿件、发布。

V1.2 起缓存层从 Redis 改为进程内 TTLCache：
- TTLCache 直接存 Python dict，无需 json 序列化
- 列表缓存逐页删除改为 delete_pattern 一次性清理
"""
from datetime import date

from loguru import logger
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

    async def get_today_episode(self, channel_id: int | None = None) -> dict | list | None: # NOSONAR
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
        """节目搜索：优先用 FTS5 全文索引，回退到 LIKE 模糊匹配。

        FTS5 性能比 LIKE 高 10-100 倍（走倒排索引而非全表扫描）。
        关键词含双引号或特殊字符时 FTS5 MATCH 可能报错，降级为 LIKE。
        """
        if not keyword or page < 1 or size < 1:
            return {"total": 0, "list": []}

        offset = (page - 1) * size

        # 尝试 FTS5 全文检索（性能最优）
        try:
            from sqlalchemy import text as sql_text

            # FTS5 MATCH 语法：关键词作为整体短语匹配
            # 用参数绑定避免 SQL 注入（FTS5 不支持传统参数化，但 SQLAlchemy text 可安全传递）
            # 双引号包裹让 FTS5 把关键词作为 phrase 查询，避免被分词
            fts_query = f'"{keyword}"'

            # 总数（FTS5 JOIN episode 过滤已发布）
            count_sql = sql_text(
                "SELECT COUNT(*) FROM episode_fts fts "
                "JOIN episode ON episode.id = fts.rowid "
                "WHERE episode_fts MATCH :q "
                "AND episode.status = 'published'"
            )
            count_result = await self.db.execute(count_sql, {"q": fts_query})
            total = count_result.scalar() or 0

            # 分页（按 date 倒序）
            list_sql = sql_text(
                "SELECT episode.id, episode.date, episode.title, "
                "episode.duration, episode.cover_url, episode.categories "
                "FROM episode_fts fts "
                "JOIN episode ON episode.id = fts.rowid "
                "WHERE episode_fts MATCH :q "
                "AND episode.status = 'published' "
                "ORDER BY episode.date DESC, episode.id DESC "
                "LIMIT :limit OFFSET :offset"
            )
            result = await self.db.execute(
                list_sql, {"q": fts_query, "limit": size, "offset": offset}
            )
            rows = result.all()

            list_data = [
                {
                    "id": r[0],
                    "date": r[1].isoformat() if r[1] else None,
                    "title": r[2],
                    "duration": r[3],
                    "cover_url": r[4],
                    "categories": r[5] or [],
                }
                for r in rows
            ]

            return {"total": total, "list": list_data}
        except Exception:
            # FTS5 不可用或 MATCH 语法错误（含特殊字符），降级到 LIKE
            # 为什么不向上抛：搜索是低频但容错性要求高的场景，降级保证可用性
            pass

        # 降级：LIKE 模糊匹配（原 MVP 实现）
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"

        count_result = await self.db.execute(
            select(func.count(Episode.id)).where(
                Episode.status == EpisodeStatus.published,
                Episode.title.like(pattern, escape="\\"),
            )
        )
        total = count_result.scalar() or 0

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

    async def get_script(self, episode_id: int) -> dict | None:  # NOSONAR
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

        # 按 segment 顺序拼装 sources，并把每个 segment 第一个有封面的 material
        # 的 cover_url 注入 segment，供前端"虚化背景"和"分段配图"使用
        # 任务10+任务2：segments 缺少 cover_url 字段，前端无法显示分段图片
        # 任务11：sources 的 seq 必须从 1 重新编号（之前用 segment.seq 会从 2 开始，因为
        #   第 1 段通常是开场白没有 material_ids，sources 直接从第 2 段开始）
        enriched_segments = []
        source_seq = 0  # sources 自己的 1-based 序号
        for seg in segments:
            if not isinstance(seg, dict):
                enriched_segments.append(seg)
                continue
            material_ids = seg.get("material_ids") or []
            seg_cover = None
            for mid in material_ids:
                mat = materials_map.get(mid)
                if mat:
                    source_seq += 1
                    sources.append({
                        "seq": source_seq,
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
            # HLS URL 从 review 拷贝：拼接阶段生成，发布时落入 episode 表
            hls_url=review.hls_url,
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
        # 修复：key 必须与 get_today_episode 中实际写入的 all_key 一致
        # （原代码 delete("episode:today") 是精确匹配，不会命中 "episode:today:all"）
        await self.cache.delete("episode:today:all")
        await self.cache.delete_pattern("episode:today:ch:*")
        await self.cache.delete_pattern("episode:list:page:*")

        return episode.id

    @staticmethod
    def _resolve_audio_base_url() -> str:
        """解析音频/封面静态资源最终生效的对外访问 URL。

        优先级：
        1. tunnel_service.public_url（运行时动态获取的内网穿透地址）
           —— 隧道运行时，外网用户必须通过公网域名访问，否则 audio_url 会指向内网 IP
        2. settings.audio_base_url_resolved（.env 配置或自动检测局域网 IP）
           —— 无隧道时走配置值或局域网 IP

        为什么不直接在 settings.audio_base_url_resolved 里判断：
        get_settings() 用了 @lru_cache，是启动时加载的静态快照；
        而 tunnel 状态是运行时动态变化的（启动/停止），必须在请求时实时查询。
        """
        try:
            from app.services.tunnel_service import get_tunnel_service
            tunnel = get_tunnel_service()
            url = tunnel.public_url
            if url:
                return url.rstrip("/")
        except Exception:
            # tunnel_service 未初始化或导入失败属于降级场景，DEBUG 即可；
            # 必须保留 exc_info=True 便于排障时回溯隧道服务异常根因
            logger.debug("tunnel_service 不可用，回退到静态配置", exc_info=True)
        from app.config import get_settings
        return get_settings().audio_base_url_resolved

    @staticmethod
    def _episode_to_dict(episode: Episode) -> dict:
        """统一 Episode 序列化，避免多处重复。

        音频 URL 转换：相对路径 /audio/... 转换为完整 URL 供小程序播放。
        基础 URL 由 _resolve_audio_base_url 解析：
        - 隧道运行时用公网域名（外网用户可访问）
        - 无隧道时用 .env 配置或自动检测的局域网 IP（局域网真机调试）
        """
        base = ContentService._resolve_audio_base_url()

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

        # HLS m3u8 清单 URL 处理：与 audio_url 同样的相对路径转换 + URL 编码
        # 为什么单独处理：HLS 目录位于 /audio/hls/ 子路径下，m3u8 内部引用的 ts 分片
        # 用相对路径，播放器会基于 m3u8 URL 解析。此处仅转换 m3u8 自身 URL。
        # 为空表示该节目未生成 HLS（HLS_ENABLE=false 或旧节目），客户端回退到 audio_url
        hls_url = episode.hls_url
        if hls_url and hls_url.startswith('/audio/') and not hls_url.startswith('http'):
            hls_url = base + hls_url
        if hls_url and hls_url.startswith('http'):
            from urllib.parse import urlparse, urlunparse, quote
            parsed = urlparse(hls_url)
            encoded_path = quote(parsed.path, safe='/_:')
            hls_url = urlunparse((parsed.scheme, parsed.netloc, encoded_path, parsed.params, parsed.query, parsed.fragment))

        # 任务1：把 channel_id 一起序列化，前端在频道列表加载完前可回退到此字段
        return {
            "id": episode.id,
            "date": episode.date.isoformat() if episode.date else None,
            "title": episode.title,
            "duration": episode.duration,
            "audio_url": audio_url,
            # HLS 清单 URL：为空时小程序回退到 audio_url 播放
            "hls_url": hls_url,
            "cover_url": cover_url,
            "categories": episode.categories or [],
            "status": episode.status if episode.status else None,
            "channel_id": episode.channel_id,
        }
