"""爬虫去重工具。

设计原因：爬虫需要在两个维度去重避免重复入库：
1. URL 精确去重 —— 不同源转发同一新闻时 URL 完全相同
2. 标题近似去重 —— 同一新闻不同源标题略改，URL 不同但内容重复

V1.2 改造：Redis Set → SQLite crawler_dedup 表。
- URL 精确去重：原 Redis SISMEMBER → SELECT url_hash（MD5 索引加速查询）
- SimHash 近似去重：原 Redis SSCAN 遍历 → SELECT simhash 全量遍历比较汉明距离
- TTL 清理：原 Redis EXPIRE 自动过期 → APScheduler 每日 03:00 清理（见 workflow_scheduler）

MVP 规模 50-100 条/天，全量遍历可接受，无需构建 VP-Tree。
"""
import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.simhash import is_similar
from app.models.crawler_dedup import CrawlerDedup

logger = logging.getLogger(__name__)


async def is_duplicate(url: str, title: str, simhash: str, db: AsyncSession) -> bool:
    """判断素材是否重复。

    URL 命中 → 重复；SimHash 与已存指纹汉明距离 ≤3 → 重复。
    title 参数保留供未来扩展（如基于标题的额外规则），当前仅用 simhash。

    Args:
        url: 素材 URL
        title: 素材标题（预留扩展）
        simhash: 标题 SimHash 指纹
        db: 异步会话
    """
    url_hash = hashlib.md5(url.encode()).hexdigest()

    # URL 精确去重：url_hash 有唯一索引，O(log n) 查询，优先判断以短路后续 SimHash 遍历
    url_result = await db.execute(
        select(CrawlerDedup.id).where(CrawlerDedup.url_hash == url_hash)
    )
    if url_result.scalar_one_or_none() is not None:
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
