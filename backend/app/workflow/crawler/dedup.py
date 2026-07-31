"""爬虫去重工具。

设计原因：爬虫需要在两个维度去重避免重复入库：
1. URL 精确去重 —— 不同源转发同一新闻时 URL 完全相同
2. 标题近似去重 —— 同一新闻不同源标题略改，URL 不同但内容重复

V1.2 改造：Redis Set → SQLite crawler_dedup 表。
- URL 精确去重：原 Redis SISMEMBER → SELECT url_hash（MD5 索引加速查询）
- SimHash 近似去重：原 Redis SSCAN 遍历 → SELECT simhash 全量遍历比较汉明距离
- TTL 清理：原 Redis EXPIRE 自动过期 → APScheduler 每日 03:00 清理（见 workflow_scheduler）

V2 改造（2026-07-30）：双源去重（dedup + material.url）。
- 背景：凌晨 03:00 _cleanup_crawler_dedup 清理 TTL 过期 dedup 记录，
  但 material 表中 url 仍保留（UNIQUE 约束）。05:00 cron crawl 时 dedup 未命中，
  INSERT material 触发 UNIQUE constraint failed，导致整批 insert_failures
  （wf-20260730-0005/0006/0008 故障根因）。
- 解法：is_duplicate 同时检查 material.url，任一命中即判重。
- 兼容性：dedup 表仍保留作为 SimHash 近似去重的索引源，material.url
  作为 URL 精确去重的兜底真相源，避免 dedup 清理后 INSERT 冲突。

MVP 规模 50-100 条/天，全量遍历可接受，无需构建 VP-Tree。
"""
import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.simhash import is_similar
from app.models.crawler_dedup import CrawlerDedup
from app.models.material import Material

logger = logging.getLogger(__name__)


async def is_duplicate(url: str, title: str, simhash: str, db: AsyncSession) -> bool:
    """判断素材是否重复。

    URL 命中 → 重复；SimHash 与已存指纹汉明距离 ≤3 → 重复。
    title 参数保留供未来扩展（如基于标题的额外规则），当前仅用 simhash。

    双源 URL 去重（R163 反向场景）：
    1. crawler_dedup.url_hash 命中 → 重复（dedup 表内命中）
    2. material.url 命中 → 重复（dedup 被清理但 material 仍存在）
    任一命中即跳过 INSERT，避免 UNIQUE constraint failed。

    Args:
        url: 素材 URL
        title: 素材标题（预留扩展）
        simhash: 标题 SimHash 指纹
        db: 异步会话
    """
    url_hash = hashlib.md5(url.encode()).hexdigest()

    # URL 精确去重源 1：crawler_dedup.url_hash（有唯一索引，O(log n) 查询）
    url_result = await db.execute(
        select(CrawlerDedup.id).where(CrawlerDedup.url_hash == url_hash)
    )
    if url_result.scalar_one_or_none() is not None:
        return True

    # URL 精确去重源 2：material.url（兜底真相源，dedup 被清理后仍能命中）
    # 背景：凌晨 03:00 _cleanup_crawler_dedup 清理 TTL 过期 dedup，
    # 但 material 表 url 仍保留（UNIQUE 约束）。若不检查 material.url，
    # 05:00 cron crawl 会触发 UNIQUE constraint failed（wf-20260730-0005/0006/0008）
    material_result = await db.execute(
        select(Material.id).where(Material.url == url)
    )
    if material_result.scalar_one_or_none() is not None:
        logger.debug("material.url 命中（dedup 已被 TTL 清理）: %s", url)
        return True

    # SimHash 近似去重：遍历已存指纹，任一相似即判重
    # 规模小（百级），全表遍历可接受
    simhash_result = await db.execute(
        select(CrawlerDedup.simhash).where(CrawlerDedup.simhash.isnot(None))
    )
    for (existing,) in simhash_result.all():
        if is_similar(simhash, existing, threshold=3):
            logger.debug("SimHash 命中近似重复: %s vs %s", simhash, existing)
            return True

    return False


async def add_to_dedup(url: str, simhash: str, db: AsyncSession) -> None:
    """将素材加入去重表。

    Args:
        url: 素材 URL
        simhash: 标题 SimHash 指纹
        db: 异步会话（由调用方控制 commit 事务边界）
    """
    url_hash = hashlib.md5(url.encode()).hexdigest()
    entry = CrawlerDedup(url=url, url_hash=url_hash, simhash=simhash)
    db.add(entry)
    # flush 让记录立即可见但不提交，事务边界交由调用方控制
    # （爬虫流程内通常一个 source 处理完后统一 commit）
    await db.flush()
