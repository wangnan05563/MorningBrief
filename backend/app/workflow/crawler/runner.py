"""爬虫主入口。

职责：加载配置 → 并发爬取 RSS 源 → 去重 → 提取正文 → 存库。

设计原则：
- 单源失败隔离：每源 try/except，失败记录日志继续，不影响其他源
- 阻塞库隔离：feedparser 用 asyncio.to_thread 包装（HLD 3.1.5）；httpx 原生异步无需包装
- QPS 限制：asyncio.Semaphore(1) 每源串行（简化实现，遵守 robots.txt）
- 去重：URL 精确 + SimHash 近似双维度，避免不同源转发同一新闻重复入库
"""
import asyncio
import logging
from pathlib import Path

import yaml

from app.core.simhash import compute
from app.database import AsyncSessionLocal
from app.models import Material
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


async def _process_entry(entry: dict, workflow_id: str, session) -> bool:
    """处理单条素材：去重 → 提取正文 → 入库。

    返回 True 表示成功入库（计入计数），False 表示跳过或失败。
    入库成功后才写入去重表，保证 DB 与去重表状态一致。
    """
    title = entry["title"]
    url = entry["url"]

    # 标题 SimHash 指纹，用于近似去重
    simhash = compute(title)

    # 去重判断：URL 精确 + SimHash 近似（V1.2 改为传 session 查 crawler_dedup 表）
    if await is_duplicate(url, title, simhash, session):
        logger.debug("跳过重复素材: %s", url)
        return False

    # 提取正文（httpx + selectolax 异步提取，失败时上层用 RSS summary 兜底）
    article = await extract_article(url)
    content = article.get("content")
    # 正文提取失败则用 RSS summary 兜底，避免空内容入库违反 NOT NULL 约束
    if not content:
        content = entry.get("summary") or ""

    # 摘要取正文前 200 字，与 Material.summary 字段长度对齐
    summary = content[:200] if content else None

    material = Material(
        source=entry["source"],
        source_type=MaterialSourceType.rss,
        title=title,
        content=content,
        summary=summary,
        url=url,
        published_at=entry.get("published_at") or article.get("publish_time"),
        category=entry.get("category_hint"),
        status=MaterialStatus.pending,
        simhash=simhash,
        workflow_id=workflow_id,
    )
    session.add(material)
    # flush 让 DB 层 unique 约束（url）作为最后防线，避免去重表漏判时脏数据入库
    await session.flush()

    # 入库成功后加入去重表，后续相同/近似素材将被跳过
    await add_to_dedup(url, simhash, session)
    return True


async def _crawl_source(source_config: dict) -> list[dict]:
    """爬取单个源的所有条目。

    单源失败由 RSSSpider 内部捕获返回空列表，此处不再额外处理。
    """
    spider = RSSSpider(source_config)
    return await spider.fetch()


async def run(workflow_id: str, date_str: str) -> dict:
    """爬虫主流程：加载配置 → 并发爬取 → 去重 → 存库。

    Args:
        workflow_id: 工作流 ID，用于关联素材与下游筛选环节
        date_str: 日期字符串（如 "2026-07-08"），用于日志追踪

    Returns:
        {"material_count": N, "workflow_id": "wf-xxx"}
    """
    logger.info("爬虫启动 workflow_id=%s date=%s", workflow_id, date_str)

    # 加载 RSS 配置（lists.yaml 预留给未来列表页爬虫扩展，当前仅 RSS）
    rss_config = _load_yaml(SOURCES_DIR / "rss.yaml")
    sources = rss_config.get("sources", [])
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

    logger.info(
        "共抓取 %d 条原始条目，开始去重与正文提取", len(all_entries)
    )

    # 逐条处理：去重 + 提取正文 + 入库
    # 串行处理避免并发写库与去重表的竞态（MVP 规模小，串行可接受）
    material_count = 0
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for entry in all_entries:
                try:
                    if await _process_entry(entry, workflow_id, session):
                        material_count += 1
                except Exception as e:
                    # 单条失败不影响整体，记录后继续处理下一条
                    logger.error(
                        "处理素材失败 url=%s err=%s",
                        entry.get("url"),
                        e,
                    )

    logger.info(
        "爬虫完成 workflow_id=%s 入库 %d 条", workflow_id, material_count
    )
    return {"material_count": material_count, "workflow_id": workflow_id}
