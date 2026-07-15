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
from pathlib import Path
from typing import Optional

import yaml

from app.core.simhash import compute
from app.core.timeutil import utcnow_naive
from app.database import AsyncSessionLocal
from app.models import Material, Channel
from app.models.material import MaterialSourceType, MaterialStatus
from app.workflow.crawler.article_parser import extract as extract_article
from app.workflow.crawler.dedup import add_to_dedup, is_duplicate
from app.workflow.crawler.rss_spider import RSSSpider

logger = logging.getLogger(__name__)

SOURCES_DIR = Path(__file__).parent / "sources"


def _load_yaml(path: Path) -> dict:
    """加载 YAML 配置（同步文件读取，调用频率低无需异步化）。"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def _extract_content(entry: dict) -> dict:
    """事务外提取正文（网络 I/O），避免在持有 SQLite 写锁时等待网络。

    将耗时的 extract_article 网络请求从事务中剥离，使事务仅包含快速 DB 操作
    （去重检查 + INSERT + add_to_dedup），写锁持有时间从"N × 网络耗时"降到毫秒级。
    """
    title = entry["title"]
    url = entry["url"]
    simhash = compute(title)

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
    }


async def _insert_material(prepared: dict, workflow_id: str, session, channel_id=None) -> bool:
    """事务内快速入库：去重检查 → INSERT → 加入去重表。

    仅包含 DB 操作，不涉及网络 I/O，写锁持有时间极短。
    入库成功后才写入去重表，保证 DB 与去重表状态一致。
    """
    url = prepared["url"]
    title = prepared["title"]
    simhash = prepared["simhash"]

    if await is_duplicate(url, title, simhash, session):
        logger.debug("跳过重复素材: %s", url)
        return False

    material = Material(
        source=prepared["source"],
        source_type=MaterialSourceType.rss,
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
        crawled_at=utcnow_naive(),
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


async def _load_channel_filter(channel_id: Optional[int]) -> tuple[list[str], list[str]]:
    """加载频道级数据源白名单和关键词过滤列表。

    返回 (rss_sources, keywords)：
    - rss_sources 为空列表表示使用所有源（兼容旧逻辑/未配置频道的全局模式）
    - keywords 为空列表表示不关键词过滤
    - channel_id 为 None 或频道不存在时回退到全局模式
    """
    if channel_id is None:
        return [], []

    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        ch = await session.scalar(select(Channel).where(Channel.id == channel_id))
        if ch is None:
            logger.warning("频道 ID %s 不存在，crawler 回退到全局模式", channel_id)
            # 显式 commit 释放只读事务，避免连接归还连接池时事务残留
            await session.commit()
            return [], []

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

        keywords: list[str] = []
        if ch.keywords:
            keywords = [kw.strip() for kw in ch.keywords.split(",") if kw.strip()]

        logger.info(
            "频道 %s 数据源过滤: rss_sources=%s keywords=%s",
            channel_id, rss_sources or "(全部)", keywords or "(不过滤)",
        )
        # 显式 commit 释放只读事务，避免连接归还连接池时事务残留导致写锁竞争
        await session.commit()
        return rss_sources, keywords


def _match_keywords(title: str, keywords: list[str]) -> bool:
    """标题是否包含任一关键词（大小写不敏感）。

    keywords 为空时返回 True（不过滤），兼容未配置关键词的频道。
    """
    if not keywords:
        return True
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in keywords)


async def run(workflow_id: str, date_str: str, channel_id: Optional[int] = None) -> dict:
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

    # 加载频道级数据源白名单和关键词过滤配置
    # channel_id 为 None 或频道未配置时返回空列表，回退到全局模式
    rss_sources_filter, keywords_filter = await _load_channel_filter(channel_id)

    # 加载 RSS 配置（lists.yaml 预留给未来列表页爬虫扩展，当前仅 RSS）
    rss_config = _load_yaml(SOURCES_DIR / "rss.yaml")
    all_sources = rss_config.get("sources", [])

    # 频道级数据源白名单过滤：rss_sources_filter 非空时仅保留白名单中的源
    # 为空时使用全部源（兼容未配置 rss_sources 的频道/全局模式）
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
    else:
        sources = all_sources
    logger.info("加载 RSS 源 %d 个", len(sources))

    # 并发爬取所有源：gather + return_exceptions 确保单源异常不影响其他
    tasks = [_crawl_source(src) for src in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 合并所有条目，异常的源跳过
    all_entries = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                "源 %s 爬取异常: %s", sources[i].get("name"), result
            )
            continue
        all_entries.extend(result)

    # 频道级关键词过滤：keywords_filter 非空时，标题必须包含至少一个关键词
    # 在 extract_article 之前过滤，避免对不相关素材做网络请求
    # 为空时不过滤（兼容未配置 keywords 的频道/全局模式）
    if keywords_filter:
        before_count = len(all_entries)
        all_entries = [
            entry for entry in all_entries
            if _match_keywords(entry.get("title", ""), keywords_filter)
        ]
        logger.info(
            "频道 %s 关键词过滤: %d → %d 条（过滤 %d 条不相关）",
            channel_id, before_count, len(all_entries),
            before_count - len(all_entries),
        )

    logger.info(
        "共抓取 %d 条原始条目，开始去重与正文提取", len(all_entries)
    )

    # 两阶段处理：避免 SQLite 长事务持锁导致 database is locked
    # 阶段1（事务外）：逐条提取正文（网络 I/O），不持有任何 DB 写锁
    # 阶段2（短事务）：批量入库（去重检查 + INSERT + add_to_dedup），写锁仅持毫秒级
    prepared_list = []
    for entry in all_entries:
        try:
            prepared = await _extract_content(entry)
            prepared_list.append(prepared)
        except Exception as e:
            logger.error(
                "提取正文失败 url=%s err=%s",
                entry.get("url"),
                e,
            )

    # 阶段2：短事务批量入库，写锁持有时间极短
    material_count = 0
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for prepared in prepared_list:
                try:
                    if await _insert_material(prepared, workflow_id, session, channel_id):
                        material_count += 1
                except Exception as e:
                    logger.error(
                        "入库素材失败 url=%s err=%s",
                        prepared.get("url"),
                        e,
                    )

    logger.info(
        "爬虫完成 workflow_id=%s channel_id=%s 入库 %d 条",
        workflow_id, channel_id, material_count,
    )

    # 0 条新素材时检查是否已有 pending 素材可用
    # 场景：RSS 源未更新/dedup 表锁死重复 URL，但 material 表已有历史 pending 素材
    # rewriter 通过 FALLBACK_DAYS 回溯可选取这些素材，crawl 步骤不应中断工作流
    # 仅当 material 表完全无 pending 素材时才报错（首次运行/数据库重置/RSS 全不可达）
    # 频道模式下按 channel_id 过滤 pending 素材，确保回溯选取的也是本频道素材
    if material_count == 0:
        from sqlalchemy import select, func
        async with AsyncSessionLocal() as check_session:
            pending_stmt = select(func.count(Material.id)).where(
                Material.status == MaterialStatus.pending
            )
            # 频道模式下只统计本频道的 pending 素材
            # 避免其他频道素材被本频道 rewriter 误选（频道级隔离）
            if channel_id is not None:
                pending_stmt = pending_stmt.where(Material.channel_id == channel_id)
            pending_count = await check_session.scalar(pending_stmt)
        if pending_count == 0:
            raise RuntimeError(
                f"爬虫未爬取到任何素材（{len(sources)} 个源，"
                f"{len(all_entries)} 条原始条目），且无历史 pending 素材可用，"
                f"请检查 RSS 源配置与网络连通性"
            )
        logger.info(
            "爬虫入库 0 条新素材，但 material 表已有 %d 条 pending，"
            "rewriter 将通过回溯机制选取",
            pending_count,
        )

    return {"material_count": material_count, "workflow_id": workflow_id}
