"""爬虫主入口。

职责：加载配置 → 并发爬取 RSS 源 → 去重 → 提取正文 → 存库。

设计原则：
- 单源失败隔离：每源 try/except，失败记录日志继续，不影响其他源
- 阻塞库隔离：feedparser 用 asyncio.to_thread 包装（HLD 3.1.5）；httpx 原生异步无需包装
- QPS 限制：asyncio.Semaphore(1) 每源串行（简化实现，遵守 robots.txt）
- 去重：URL 精确 + SimHash 近似双维度，避免不同源转发同一新闻重复入库
"""
import asyncio
import json
import logging
import re
from datetime import timedelta
from typing import Optional

from app.config import get_settings
from app.core.simhash import compute
from app.core.timeutil import localnow_naive
from sqlalchemy import func, select, update

from app.database import AsyncSessionLocal
from app.models import Material, Channel
from app.models.material import MaterialSourceType, MaterialStatus
from app.services.rss_source_service import load_rss_sources, load_book_rss_sources, load_book_fulltext_sources
from app.workflow.crawler.fulltext_spider import crawl_fulltext_source
from app.workflow.crawler.article_parser import extract as extract_article
from app.workflow.crawler.dedup import add_to_dedup, is_duplicate
from app.workflow.crawler.rss_spider import RSSSpider

logger = logging.getLogger(__name__)
settings = get_settings()


async def _extract_content(entry: dict) -> dict:
    """事务外提取正文（网络 I/O），避免在持有 SQLite 写锁时等待网络。

    将耗时的 extract_article 网络请求从事务中剥离，使事务仅包含快速 DB 操作
    （去重检查 + INSERT + add_to_dedup），写锁持有时间从"N × 网络耗时"降到毫秒级。
    """
    title = entry["title"]
    url = entry["url"]
    simhash = compute(title)

    # 全文源（T00603）：正文已在爬取时预取（书籍章节全文），直接返回，避免对
    # 维基文库/Gutenberg 页面再跑一次 article_parser（会拿到 HTML 噪声而非纯文本）
    if entry.get("_fulltext"):
        content = entry.get("content") or ""
        return {
            "title": title,
            "url": url,
            "simhash": simhash,
            "content": content,
            "summary": content[:200] if content else None,
            "source": entry.get("source", ""),
            "category_hint": entry.get("category_hint"),
            "published_at": entry.get("published_at"),
            "cover_url": None,
            "images": [],
        }

    article = await extract_article(url)
    content = article.get("content")
    if not content:
        content = entry.get("summary") or ""
    summary = content[:200] if content else None

    return {
        "title": title,
        "url": url,
        "simhash": simhash,
        "content": content,
        "summary": summary,
        "source": entry.get("source", ""),
        "category_hint": entry.get("category_hint"),
        "published_at": entry.get("published_at") or article.get("publish_time"),
        # 封面图由 article_parser 从 og:image 提取，透传到 Material 入库
        # 无封面图时为 None，小程序文稿页降级为纯文本展示
        # T00766：images 为文章全量图片（封面在前），透传入库供详情页轮播
        "cover_url": article.get("cover_url"),
        "images": article.get("images") or [],
    }


async def _route_book_pool_mode(workflow_id: str, channel_id: Optional[int]) -> Optional[dict]:
    """讲书稿模式路由（T00656）。

    - 非讲书稿模式：返回 None，走原采集流程；
    - 讲书稿模式：**完全不采集**书源/资讯源（仅清空频道的 rss_sources 字段并不足够——
      非 audiobook 频道空白名单会回退到全局源），改为按素材池顺序供给"当前应讲的那本书"的
      章节素材，并关联到本次工作流；池空/未到间隔/已到末尾/书未上传书稿等情况抛**明确原因**
      的错误（工作流详情页可见），便于运营直接处置。

    Returns:
        讲书稿模式下的 crawl 结果 dict；非该模式返回 None
    """
    if channel_id is None:
        return None
    from app.models import Channel
    from app.services import book_pool_service as book_pool_svc

    async with AsyncSessionLocal() as session:
        mode = (await session.execute(
            select(Channel.script_mode).where(Channel.id == channel_id)
        )).scalar()
        if (mode or "") != book_pool_svc.MODE_BOOK_POOL:
            return None

        pick = await book_pool_svc.pick_next_book(session, channel_id)
        status = pick.get("status")

        def _raise(reason: str, msg: str, hint: str) -> None:
            err = RuntimeError(msg)
            err.failure_details = {  # type: ignore[attr-defined]
                "reason": reason, "channel_id": channel_id, "hint": hint, "pick": pick,
            }
            raise err

        if status == "empty":
            _raise("book_pool_empty",
                   "讲书稿模式：素材池为空，已跳过当日生成",
                   "请在「频道管理 → 讲书稿素材池」加入书籍（或关闭讲书稿模式改用频道书源）")
        if status == "not_due":
            _raise("book_pool_not_due",
                   f"讲书稿模式：未到取书间隔（上次 {pick.get('last_run_date')}，"
                   f"下次 {pick.get('next_due_date')}），已跳过当日生成",
                   "如需每日生成，请把取书间隔设为 1 天")
        if status == "exhausted":
            _raise("book_pool_exhausted",
                   f"讲书稿模式：素材池已到末尾（进度 {pick.get('cursor')}/{pick.get('total')}），已跳过当日生成",
                   "可在素材池页开启「末尾循环」或重置进度，或向池中追加书籍")
        if status != "ok":
            _raise("book_pool_unknown", f"讲书稿模式：取书失败（{status}）", "请检查频道与素材池配置")

        item = pick.get("item") or {}
        materials = await book_pool_svc.collect_book_materials(session, channel_id, item)
        if not materials:
            _raise("book_not_uploaded",
                   f"讲书稿模式：待讲书籍《{item.get('title')}》尚无待消费的书稿素材",
                   "请在「素材录入」上传该书 EPUB/DOCX 并选择本频道；"
                   "为便于自动聚合全书章节，上传时把「来源」填为书名")

        # 关联到本次工作流（素材本质是频道池，workflow_id 为运行期临时关联）
        ids = [m.id for m in materials]
        await session.execute(
            update(Material).where(Material.id.in_(ids)).values(workflow_id=workflow_id)
        )
        await session.commit()

    logger.info(
        "[讲书稿] workflow_id=%s channel_id=%s 取书《%s》（进度 %s/%s）→ 章节素材 %d 条",
        workflow_id, channel_id, item.get("title"), pick.get("cursor"), pick.get("total"), len(ids),
    )
    return {
        "material_count": len(ids),
        "workflow_id": workflow_id,
        "book_pool": {
            "book_title": item.get("title"),
            "material_id": item.get("material_id"),
            "cursor": pick.get("cursor"),
            "total": pick.get("total"),
            "chapter_count": len(ids),
        },
        "source_details": [],  # 讲书稿模式不采集任何源，前端展示为空属预期
        "total_entries": 0,
        "extracted_entries": 0,
    }


def decide_crawl_outcome(material_count: int, duplicates_skipped: int) -> str:
    """判定 crawl 结果语义（T00649，纯函数便于单测）。

    Returns:
        "ok"    —— 有新增素材（正常成功）
        "reuse" —— 无新增但命中去重：素材已在池中（重跑工作流 / 先经素材录入上传过），
                   视为成功复用，**不得判失败**
        "fail"  —— 无新增且无去重命中：真无可用素材，需阻断（rewrite 会空跑）
    """
    if material_count > 0:
        return "ok"
    if duplicates_skipped > 0:
        return "reuse"
    return "fail"


async def _count_channel_pending_materials(channel_id: Optional[int]) -> int:
    """统计该频道**上传驱动**（selection_strategy=outline/manual）下待消费的素材数（T00649）。

    用途：书稿类内容经「素材录入」入库后，工作流 crawl 若未配置书源（或书源无新增），
    `原始 0 条` 属**预期**而非故障——此时应以素材池为准判断"是否有素材可用"。
    仅对 outline/manual 策略生效：RSS 驱动频道（rss 策略）仍严格按抓取结果判定，
    避免"池里有旧 pending 素材"掩盖抓取失败、导致发布陈旧内容。

    Returns:
        该频道 pending 素材数（非上传驱动策略返回 0）
    """
    if channel_id is None:
        return 0
    async with AsyncSessionLocal() as session:
        strategy = (await session.execute(
            select(Channel.selection_strategy).where(Channel.id == channel_id)
        )).scalar()
        if strategy not in ("outline", "manual"):
            return 0
        cnt = (await session.execute(
            select(func.count(Material.id)).where(
                Material.channel_id == channel_id,
                Material.status == MaterialStatus.pending.value,
            )
        )).scalar()
    return int(cnt or 0)


async def _insert_material(prepared: dict, workflow_id: str, session, channel_id=None, source_type: str = "rss") -> bool:
    """事务内快速入库：去重检查 → INSERT → 加入去重表。

    仅包含 DB 操作，不涉及网络 I/O，写锁持有时间极短。
    入库成功后才写入去重表，保证 DB 与去重表状态一致。

    source_type：素材来源类型。通用 RSS 爬取为 rss；audiobook 频道加载的
    书籍 RSS 预制源为 book_rss；其余渠道（cos/api/qrcode/list）由 material 路由入库。
    """
    url = prepared["url"]
    title = prepared["title"]
    simhash = prepared["simhash"]

    if await is_duplicate(url, title, simhash, session, source_type=source_type):
        logger.debug("跳过重复素材: %s", url)
        return False

    material = Material(
        source=prepared["source"],
        source_type=source_type,
        title=title,
        content=prepared["content"],
        summary=prepared["summary"],
        url=url,
        published_at=prepared["published_at"],
        category=prepared["category_hint"],
        status=MaterialStatus.pending,
        simhash=simhash,
        workflow_id=workflow_id,
        channel_id=channel_id,
        crawled_at=localnow_naive(),
        cover_url=prepared.get("cover_url"),
        # T00766：全量图片 JSON 数组（封面在前）；空列表存 NULL 节省存储
        images_json=(
            json.dumps(prepared.get("images") or [], ensure_ascii=False)
            if prepared.get("images")
            else None
        ),
    )
    session.add(material)
    await session.flush()
    await add_to_dedup(url, simhash, session)
    return True


async def _crawl_source(source_config: dict) -> list[dict]:
    """爬取单个源的所有条目。

    单源失败由 RSSSpider 内部捕获返回空列表，此处不再额外处理。
    """
    spider = RSSSpider(source_config)
    return await spider.fetch()


async def _load_channel_filter(channel_id: Optional[int]) -> tuple[list[str], list[str], str | None, list[str]]:
    """加载频道级数据源白名单和关键词过滤列表。

    返回 (rss_sources, keywords, channel_type, book_rss_sources)：
    - rss_sources 为空列表表示使用所有通用源（兼容旧逻辑/未配置频道的全局模式）
    - keywords 为空列表表示不关键词过滤
    - channel_type 为频道类型（news/course/audiobook），None 表示频道不存在
    - book_rss_sources 为 audiobook 频道专属的书籍 RSS 源白名单（JSON name 数组），
      仅当 channel_type=audiobook 时由 run() 用于加载 book_rss.yaml 预制源
    - channel_id 为 None 或频道不存在时回退到全局模式
    """
    if channel_id is None:
        return [], [], None, []

    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        ch = await session.scalar(select(Channel).where(Channel.id == channel_id))
        if ch is None:
            logger.warning("频道 ID %s 不存在，crawler 回退到全局模式", channel_id)
            # 显式 commit 释放只读事务，避免连接归还连接池时事务残留
            await session.commit()
            return [], [], None, []

        rss_sources: list[str] = []
        if ch.rss_sources:
            try:
                parsed = json.loads(ch.rss_sources)
                if isinstance(parsed, list):
                    rss_sources = [str(s) for s in parsed]
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "频道 %s rss_sources JSON 解析失败，回退到全局源: %s",
                    channel_id, ch.rss_sources,
                )

        book_rss_sources: list[str] = []
        if ch.book_rss_sources:
            try:
                parsed = json.loads(ch.book_rss_sources)
                if isinstance(parsed, list):
                    book_rss_sources = [str(s) for s in parsed]
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "频道 %s book_rss_sources JSON 解析失败，忽略书籍 RSS 源: %s",
                    channel_id, ch.book_rss_sources,
                )

        keywords: list[str] = []
        if ch.keywords:
            keywords = [kw.strip() for kw in ch.keywords.split(",") if kw.strip()]

        logger.info(
            "频道 %s 数据源过滤: channel_type=%s rss_sources=%s book_rss_sources=%s keywords=%s",
            channel_id, ch.channel_type, rss_sources or "(全部)",
            book_rss_sources or "(无)", keywords or "(不过滤)",
        )
        # 显式 commit 释放只读事务，避免连接归还连接池时事务残留导致写锁竞争
        await session.commit()
        return rss_sources, keywords, ch.channel_type, book_rss_sources


async def _load_channel_meta(channel_id: int) -> tuple[str | None, str | None]:
    """查询频道 name + description，供 AI 降级筛选 prompt 使用。

    与 _load_channel_filter 分离：filter 在 crawl 入口时调用（含 rss_sources/keywords），
    meta 仅在关键词 0 命中降级时按需调用（避免无降级场景的多余字段查询）。

    Returns:
        (name, description)，频道不存在时返回 (None, None)
    """
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        ch = await session.scalar(select(Channel).where(Channel.id == channel_id))
        if ch is None:
            await session.commit()
            return None, None
        name = ch.name
        desc = ch.description
        await session.commit()
        return name, desc


def _match_keywords(title: str, keywords: list[str], summary: str = "") -> bool:
    """标题或摘要是否包含任一关键词（大小写不敏感）。

    keywords 为空时返回 True（不过滤），兼容未配置关键词的频道。
    匹配范围扩展到 summary：RSS 标题常为简短短语（如"今日要闻"），
    关键词常出现在摘要正文中。仅匹配 title 会导致大量误过滤
    （如 ch=4 娱乐焦点 10 条原始条目经 13 个关键词 0 命中）。
    """
    if not keywords:
        return True
    # 拼接 title + summary 一次性匹配，避免两次 any() 遍历
    haystack = f"{title} {summary}".lower()
    return any(kw.lower() in haystack for kw in keywords)


async def _ai_fallback_filter(
    entries: list[dict], channel_name: str, channel_description: str
) -> list[dict]:
    """关键词 0 命中时的 AI 相关性降级筛选。

    场景：频道关键词为硬编码子串匹配，RSS 标题措辞多样时容易全军覆没
    （如 ch=4 娱乐焦点 10 条原始条目经 13 个关键词 0 命中）。
    此时改用 LLM 判断语义相关性，作为关键词过滤的兜底补充。

    策略：一次 LLM 调用判断所有 entries，返回相关序号 JSON 数组。
    失败时降级为全部保留（不阻断 crawl），仅记录 warning。

    Args:
        entries: RSS 原始条目列表，含 title/summary 字段
        channel_name: 频道名称（如"娱乐焦点"）
        channel_description: 频道描述

    Returns:
        相关条目子集；失败时返回原 entries（降级保留全部）
    """
    if not entries or not channel_name:
        return entries

    # 构造批量筛选 prompt：用 title + summary 前 100 字作为判断依据
    # summary 缺失时仅用 title，避免空字符串干扰 LLM 判断
    items_text = "\n".join(
        f"[{i}] 标题：{e.get('title', '')}\n    摘要：{(e.get('summary') or '')[:100]}"
        for i, e in enumerate(entries)
    )

    prompt = f"""你是新闻频道内容审核员。请判断以下 RSS 条目是否与频道主题相关。

频道名称：{channel_name}
频道描述：{channel_description or ''}

待审核条目：
{items_text}

请仅返回相关条目的序号（方括号中的数字），以 JSON 数组格式输出。
判断标准：条目核心内容应与频道主题直接相关，边缘关联也算（避免漏过相关内容）。
仅输出 JSON 数组本身，不要任何解释。

示例输出：[0, 2, 5]"""

    try:
        # 延迟导入避免循环依赖：rewriter 模块较重（含 tenacity/sensitive_filter 初始化）
        from app.workflow.llm.rewriter import _call_llm
        resp = await _call_llm(prompt)

        # 提取 JSON 数组（LLM 可能包裹在 markdown 代码块中）
        match = re.search(r'\[[\d\s,]*\]', resp or "")
        if not match:
            logger.warning(
                "AI 降级筛选返回格式异常，保留全部条目 channel=%s resp=%s",
                channel_name, (resp or "")[:200],
            )
            return entries

        raw_indices = json.loads(match.group())
        # 保序去重 + 越界过滤：LLM 可能返回重复序号或非整数值
        seen = set()
        relevant = []
        for i in raw_indices:
            if isinstance(i, int) and 0 <= i < len(entries) and i not in seen:
                seen.add(i)
                relevant.append(entries[i])

        logger.info(
            "AI 降级筛选 channel=%s: %d → %d 条（关键词 0 命中后兜底）",
            channel_name, len(entries), len(relevant),
        )

        # AI 筛选后仍为 0 条时，降级保留全部（不阻断 crawl，由 rewriter 二次筛选）
        if not relevant:
            logger.warning(
                "AI 降级筛选后仍 0 条，保留全部 %d 条 entries channel=%s",
                len(entries), channel_name,
            )
            return entries

        return relevant
    except Exception as e:
        # AI 筛选失败时降级为全部保留，不阻断 crawl 流程
        logger.warning(
            "AI 降级筛选异常，保留全部 %d 条 entries channel=%s: %s",
            len(entries), channel_name, e,
        )
        return entries


async def run(workflow_id: str, date_str: str, channel_id: Optional[int] = None) -> dict:  # NOSONAR
    """爬虫主流程：加载配置 → 频道级过滤 → 并发爬取 → 去重 → 存库。

    Args:
        workflow_id: 工作流 ID，用于关联素材与下游筛选环节
        date_str: 日期字符串（如 "2026-07-08"），用于日志追踪
        channel_id: 频道 ID，用于频道级数据源隔离。为 None 时使用全局所有源
            （兼容旧逻辑）；非 None 时按频道 rss_sources 白名单过滤源、
            按 keywords 过滤标题，入库时写入 channel_id 供 rewriter 按频道选题

    Returns:
        {"material_count": N, "workflow_id": "wf-xxx"}
    """
    logger.info(
        "爬虫启动 workflow_id=%s date=%s channel_id=%s",
        workflow_id, date_str, channel_id,
    )

    # T00656：讲书稿模式——完全不采集书源，按素材池顺序供给"当前应讲的那本书"的章节素材。
    # 置于最前：既省去无谓抓取，也让"忽略频道书源"在**行为**上真正成立
    # （仅把频道 rss_sources 清空并不足够：非 audiobook 频道空白名单会回退到全局源）。
    book_pool_outcome = await _route_book_pool_mode(workflow_id, channel_id)
    if book_pool_outcome is not None:
        return book_pool_outcome

    # 加载频道级数据源白名单和关键词过滤配置
    # channel_id 为 None 或频道未配置时返回空列表，回退到全局模式
    rss_sources_filter, keywords_filter, channel_type, book_rss_sources_filter = await _load_channel_filter(channel_id)

    # 加载 RSS 配置：复用 rss_source_service 统一加载逻辑
    # load_rss_sources 返回完整源配置（含 url/authority/qps），
    # RSSSpider 实际只使用 url 字段，qps 为预留配置当前未实现限速
    all_sources = load_rss_sources()

    # 频道级数据源白名单过滤：rss_sources_filter 非空时仅保留白名单中的源
    # audiobook 频道：空白名单 = 不爬通用资讯 RSS（避免混入新闻源），仅用书籍 RSS 预制源
    # 其余类型：空白名单 = 使用全部通用源（兼容未配置 rss_sources 的频道/全局模式）
    if rss_sources_filter:
        sources = [
            src for src in all_sources
            if src.get("name") in rss_sources_filter
        ]
        # 白名单中的源名称在 rss.yaml 不存在时记录警告，便于配置纠错
        matched_names = {src.get("name") for src in sources}
        missing = set(rss_sources_filter) - matched_names
        if missing:
            logger.warning(
                "频道 %s 配置的 RSS 源在 rss.yaml 中不存在: %s",
                channel_id, missing,
            )
        logger.info(
            "频道 %s 数据源白名单过滤: %d/%d 个源命中",
            channel_id, len(sources), len(all_sources),
        )
    elif channel_type == "audiobook":
        sources = []
    else:
        sources = all_sources

    # 书籍 RSS 预制源：仅 audiobook 频道加载（book_rss.yaml）
    # book_rss_sources_filter 非空时仅保留白名单中的书籍源；为空时加载全部书籍源
    # book_source_names 用于后续入库时把书籍源条目标记为 source_type=book_rss
    book_source_names: set[str] = set()
    if channel_type == "audiobook":
        all_book = load_book_rss_sources()
        if book_rss_sources_filter:
            book_sources = [s for s in all_book if s.get("name") in book_rss_sources_filter]
            matched_book = {s.get("name") for s in book_sources}
            missing_book = set(book_rss_sources_filter) - matched_book
            if missing_book:
                logger.warning(
                    "频道 %s 配置的书籍 RSS 源在 book_rss.yaml 中不存在: %s",
                    channel_id, missing_book,
                )
        else:
            book_sources = all_book
        if book_sources:
            book_source_names = {s.get("name") for s in book_sources}
            sources.extend(book_sources)
            logger.info(
                "频道 %s 合并书籍 RSS 源 %d 个（book_rss.yaml）",
                channel_id, len(book_sources),
            )
    # 书籍「全文」预制源：仅 audiobook 频道加载（book_fulltext.yaml，T00603）
    # 条目为整本书章节全文（wikisource/gutendex，带 provider 字段），由 fulltext_spider 抓取，
    # 配合 outline 选题策略实现「一本书一条音频」的得到式形态。
    # 白名单与 book_rss_sources 共用一套 name（channel.book_rss_sources），无 DB 变更。
    fulltext_source_names: set[str] = set()
    if channel_type == "audiobook":
        all_fulltext = load_book_fulltext_sources()
        if book_rss_sources_filter:
            fulltext_sources = [s for s in all_fulltext if s.get("name") in book_rss_sources_filter]
        else:
            fulltext_sources = all_fulltext
        if fulltext_sources:
            fulltext_source_names = {s.get("name") for s in fulltext_sources}
            sources.extend(fulltext_sources)
            logger.info(
                "频道 %s 合并书籍全文源 %d 个（book_fulltext.yaml）",
                channel_id, len(fulltext_sources),
            )
    logger.info("加载数据源 %d 个（含书籍 RSS %d 个）", len(sources), len(book_source_names))

    # 并发爬取所有源：gather + return_exceptions 确保单源异常不影响其他
    # 同时收集每个源的爬取细节，供管理员定位"爬不到信息"问题
    # 分派：带 provider 的为全文源（fulltext_spider），其余为 feedparser RSS 源
    tasks = [crawl_fulltext_source(src) if src.get("provider") else _crawl_source(src) for src in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 合并所有条目，异常的源跳过，但记录失败细节供 result 字段展示
    all_entries = []
    source_details = []  # 每个源的爬取细节：name/url/status/entry_count/error
    for i, result in enumerate(results):
        src_name = sources[i].get("name", "unknown")
        src_url = sources[i].get("url", "")
        if isinstance(result, Exception):
            logger.error(
                "源 %s 爬取异常: %s", src_name, result
            )
            source_details.append({
                "name": src_name, "url": src_url,
                "status": "fail", "entry_count": 0,
                "error": str(result)[:200],
            })
            continue
        all_entries.extend(result)
        source_details.append({
            "name": src_name, "url": src_url,
            "status": "ok", "entry_count": len(result), "error": None,
        })

    # 频道级关键词过滤：keywords_filter 非空时，标题必须包含至少一个关键词
    # 在 extract_article 之前过滤，避免对不相关素材做网络请求
    # 为空时不过滤（兼容未配置 keywords 的频道/全局模式）
    if keywords_filter:
        before_count = len(all_entries)
        # 保留原始备份：关键词 0 命中时降级 AI 筛选用，避免重新爬取
        raw_entries_backup = list(all_entries)
        all_entries = [
            entry for entry in all_entries
            if _match_keywords(
                entry.get("title", ""),
                keywords_filter,
                entry.get("summary", ""),
            )
        ]
        hit_count = len(all_entries)
        logger.info(
            "频道 %s 关键词过滤: %d → %d 条（过滤 %d 条不相关）",
            channel_id, before_count, hit_count,
            before_count - hit_count,
        )

        # 命中率监控：低于 10% 时 WARNING，便于运维发现关键词过严或 RSS 标题措辞漂移
        # 0 命中场景由下方 AI 降级兜底，但仍需告警提示关键词配置可能需要调整
        # 阈值取 10%：健康的关键词命中率通常在 30-70%，低于 10% 多为配置问题
        if before_count > 0:
            hit_rate = hit_count / before_count
            if hit_rate < 0.10:
                logger.warning(
                    "频道 %s 关键词命中率 %.0f%% 低于 10%% 阈值"
                    "（%d/%d，关键词=%s），建议检查关键词配置或 RSS 标题措辞",
                    channel_id, hit_rate * 100, hit_count, before_count,
                    keywords_filter,
                )

        # 关键词 0 命中降级：RSS 标题措辞多样时硬编码关键词容易全军覆没
        # 改用 AI 语义判断兜底，避免 crawl 直接失败导致整期节目无法生成
        # 仅在有原始条目但关键词 0 命中时触发，避免无意义的 LLM 调用
        if not all_entries and before_count > 0 and channel_id is not None:
            logger.warning(
                "频道 %s 关键词过滤后 0 命中（原始 %d 条），降级 AI 相关性筛选",
                channel_id, before_count,
            )
            # 查频道 name + description 供 AI 筛选 prompt 使用
            ch_name, ch_desc = await _load_channel_meta(channel_id)
            if ch_name:
                all_entries = await _ai_fallback_filter(
                    raw_entries_backup, ch_name, ch_desc or "",
                )
            else:
                # 频道查询失败时保留全部原始条目，由 rewriter 二次筛选
                logger.warning(
                    "频道 %s 元数据查询失败，保留全部 %d 条原始条目",
                    channel_id, before_count,
                )
                all_entries = raw_entries_backup

    logger.info(
        "共抓取 %d 条原始条目，开始去重与正文提取", len(all_entries)
    )

    # 新鲜度过滤：剔除 published_at 超过 MAX_ARTICLE_AGE_DAYS 的历史存量
    # 背景：部分 RSS 源（如人民网 ent/culture）更新缓慢，长期返回 1-3 年前的历史文章，
    # 首次入库后 dedup 锁住 URL，导致后续爬取 0 入库（wf-20260728-0011 故障根因）。
    # 过滤后若 0 条则降级保留全部（避免阻断），并 WARNING 告警提示源质量问题。
    # published_at 为 None 的条目保留（无法判断年龄，可能只是源未提供发布时间）。
    max_age_days = settings.CRAWLER_MAX_ARTICLE_AGE_DAYS
    if max_age_days > 0 and all_entries:
        age_cutoff = localnow_naive() - timedelta(days=max_age_days)

        # 统计每个源的最新发布时间，更新 source_details 供前端展示源新鲜度
        source_newest: dict[str, object] = {}
        for e in all_entries:
            src = e.get("source", "unknown")
            pub = e.get("published_at")
            if pub is not None and (src not in source_newest or pub > source_newest[src]):
                source_newest[src] = pub
        for sd in source_details:
            newest = source_newest.get(sd["name"])
            sd["newest_published_at"] = newest.isoformat() if newest else None
            # 仅对有 published_at 的源判断 stale，避免误报无发布时间的源
            sd["stale"] = newest is not None and newest < age_cutoff

        fresh_entries = [
            e for e in all_entries
            if e.get("published_at") is None or e["published_at"] >= age_cutoff
        ]
        stale_count = len(all_entries) - len(fresh_entries)
        if stale_count > 0:
            stale_by_source: dict[str, int] = {}
            for e in all_entries:
                pub = e.get("published_at")
                if pub is not None and pub < age_cutoff:
                    src = e.get("source", "unknown")
                    stale_by_source[src] = stale_by_source.get(src, 0) + 1
            logger.warning(
                "新鲜度过滤: 剔除 %d 条历史存量（超过 %d 天），涉及源: %s",
                stale_count, max_age_days, stale_by_source,
            )

        if fresh_entries:
            all_entries = fresh_entries
        else:
            # 全部超龄时降级保留全部，避免 0 素材阻断（由 rewriter 二次筛选）
            logger.warning(
                "全部 %d 条 entries 超过 %d 天年龄阈值，降级保留全部（源可能已停更）",
                len(all_entries), max_age_days,
            )

    # 单次抓取条目上限：避免 RSS 源爆发式更新导致正文提取耗时失控
    # 超出限制时按 published_at 倒序保留最新条目，旧条目下轮再抓
    _MAX_ENTRIES = 200
    if len(all_entries) > _MAX_ENTRIES:
        logger.warning(
            "原始条目 %d 超过上限 %d，仅保留最新 %d 条（旧条目下轮再抓）",
            len(all_entries), _MAX_ENTRIES, _MAX_ENTRIES,
        )
        # 按 published_at 降序排序，无 published_at 视为最旧
        # 用 datetime.min 替代空字符串兜底：避免 str 与 datetime 混合 sort 时
        # 抛 "'<' not supported between instances of 'str' and 'datetime.datetime'"
        # （wf-20260727-0010 复现：部分 RSS 源 published_parsed 缺失返回空字符串）
        from datetime import datetime as _dt
        all_entries.sort(
            key=lambda e: e.get("published_at") or _dt.min,
            reverse=True,
        )
        all_entries = all_entries[:_MAX_ENTRIES]

    # 两阶段处理：避免 SQLite 长事务持锁导致 database is locked
    # 阶段1（事务外）：并发提取正文（网络 I/O），不持有任何 DB 写锁
    # 阶段2（短事务）：批量入库（去重检查 + INSERT + add_to_dedup），写锁仅持毫秒级
    # 并发上限 8：避免瞬间打爆源站 WAF，又比串行快约 8 倍
    # 修复 wf-20260722-0011 卡死：原串行 await 单条 30s 超时 × 200 条 = 100 分钟
    _EXTRACT_CONCURRENCY = 8
    extract_sem = asyncio.Semaphore(_EXTRACT_CONCURRENCY)

    async def _extract_with_sem(entry: dict) -> Optional[dict]:
        async with extract_sem:
            return await _extract_content(entry)

    tasks = [_extract_with_sem(entry) for entry in all_entries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    prepared_list = []
    for entry, result in zip(all_entries, results):
        if isinstance(result, Exception):
            logger.error(
                "提取正文失败 url=%s err=%s",
                entry.get("url"), result,
            )
            continue
        if result is not None:
            prepared_list.append(result)

    # 阶段2：逐条短事务入库，避免单条失败导致整批回滚
    material_count = 0
    insert_failures = 0
    # T00649：因"已在素材池/去重命中"而跳过的新增数——**不等于失败**
    # （用户重跑工作流、或先经「素材录入」上传过同一内容时，全部条目都会落这里）
    duplicates_skipped = 0
    # IntegrityError 视为已入库跳过（防御性兜底）：
    # is_duplicate 已检查 dedup + material.url 双源，正常路径不应再触发 UNIQUE 冲突。
    # 但并发场景（同时两个 crawl 任务竞争同一 URL）或 dedup/material 一致性窗口外的
    # 极端情况下仍可能触发，此时视为已入库跳过，不污染 insert_failures 统计。
    from sqlalchemy.exc import IntegrityError
    for prepared in prepared_list:
        # 书籍 RSS 预制源（仅 audiobook 频道）入库标记为 book_rss，通用 RSS 仍为 rss
        if prepared.get("source") in book_source_names:
            src_type = "book_rss"
        elif prepared.get("source") in fulltext_source_names:
            src_type = "book_fulltext"
        else:
            src_type = "rss"
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    if await _insert_material(prepared, workflow_id, session, channel_id, source_type=src_type):
                        material_count += 1
                    else:
                        # _insert_material 返回 False = 去重命中（URL/dedup_key 已在池中）
                        duplicates_skipped += 1
        except IntegrityError as e:
            # UNIQUE 冲突 = 该 URL 已入库，视为成功跳过（不计入 insert_failures）
            logger.debug(
                "URL 已入库（UNIQUE 冲突跳过）url=%s err=%s",
                prepared.get("url"), e,
            )
        except Exception as e:
            insert_failures += 1
            logger.error(
                "入库素材失败 url=%s err=%s", prepared.get("url"), e,
            )

    # 爬取总结：原始/提取/入库三个维度的数量便于日志快速定位
    # source_details 已包含每个源的 name/url/status/entry_count/error
    logger.info(
        "爬虫完成 workflow_id=%s channel_id=%s: 原始 %d 条 → 提取 %d 条 → 新增 %d 条"
        "（去重跳过 %d 条，提取失败 %d 条，入库失败 %d 条）",
        workflow_id, channel_id, len(all_entries), len(prepared_list),
        material_count, duplicates_skipped,
        len(all_entries) - len(prepared_list), insert_failures,
    )

    # T00649：**去重命中不算失败**——素材已存在于池中（重跑工作流 / 先经「素材录入」上传过
    # 同一内容）时，本条 crawl 的实际语义是"素材可复用"，下游 rewrite 会按
    # channel_id + status=pending 正常取到；旧实现把这种情况与"真无素材"一并判失败，
    # 用户重跑时必然报「入库 0 条」，与预期（复用已上传的书）相悖。
    if decide_crawl_outcome(material_count, duplicates_skipped) == "reuse":
        logger.info(
            "本次未新增素材，但 %d 条已在素材池中被去重跳过，视为成功复用"
            "（workflow_id=%s channel_id=%s）",
            duplicates_skipped, workflow_id, channel_id,
        )
        return {
            "material_count": 0,
            "reused_materials": duplicates_skipped,
            "workflow_id": workflow_id,
            "source_details": source_details,
            "total_entries": len(all_entries),
            "extracted_entries": len(prepared_list),
        }

    # T00649：上传驱动频道（outline/manual）的素材池兜底——书稿经「素材录入」入库、
    # crawl 无书源或书源无新增时，池中 pending 素材即"可用素材"，不应阻断工作流。
    if decide_crawl_outcome(material_count, duplicates_skipped) == "fail":
        pool_pending = await _count_channel_pending_materials(channel_id)
        if pool_pending > 0:
            logger.info(
                "crawl 未采集到新素材，但频道 %s 素材池已有 %d 条 pending 素材（上传驱动），"
                "视为可用（workflow_id=%s）",
                channel_id, pool_pending, workflow_id,
            )
            return {
                "material_count": 0,
                "pool_materials": pool_pending,
                "workflow_id": workflow_id,
                "source_details": source_details,
                "total_entries": len(all_entries),
                "extracted_entries": len(prepared_list),
            }

    # 0 素材阻断：rewrite 步骤对空 pending 也会失败并浪费 LLM 调用
    # 此处主动抛异常让 crawl 步骤 failed，避免后续无效执行
    # 通过 failure_details 携带 source_details，被 _run_step 写入 workflow_step.result
    # 前端工作流详情页可直接展示每个源的爬取状态，便于运维定位
    if material_count == 0:
        # 统计 stale 源数量，为 hint 提供针对性提示
        stale_sources = [
            sd.get("name") for sd in source_details
            if sd.get("stale") is True
        ]
        stale_hint = ""
        if stale_sources:
            stale_hint = (
                f" 5) 源停更嫌疑: {stale_sources[:3]} 等的最新发布时间超过"
                f" {settings.CRAWLER_MAX_ARTICLE_AGE_DAYS} 天，建议在 rss.yaml 替换失效源；"
            )
        failure_details = {
            "reason": "zero_material",
            "total_entries": len(all_entries),
            "extracted_entries": len(prepared_list),
            "insert_failures": insert_failures,
            "source_details": source_details,
            "hint": (
                "请检查：1) RSS 源是否可达（status=fail 的源）；"
                "2) 关键词配置是否过严导致 0 命中；"
                "3) 源今日是否无新内容；4) 正文提取是否全部失败；"
                + stale_hint
                + " 注：已入库 URL 会被去重跳过（dedup + material.url 双源检查）。"
            ),
        }
        err = RuntimeError(
            f"爬虫未获取到有效素材（原始 {len(all_entries)} 条，"
            f"提取 {len(prepared_list)} 条，入库 0 条）"
        )
        err.failure_details = failure_details  # type: ignore[attr-defined]
        raise err

    # 成功路径：返回 material_count 供下游使用，source_details 供前端展示
    return {
        "material_count": material_count,
        "reused_materials": duplicates_skipped,
        "workflow_id": workflow_id,
        "source_details": source_details,
        "total_entries": len(all_entries),
        "extracted_entries": len(prepared_list),
    }