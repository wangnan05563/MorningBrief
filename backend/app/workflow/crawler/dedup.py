"""爬虫去重工具。

设计原因：爬虫需要在两个维度去重避免重复入库：
1. URL 精确去重 —— 不同源转发同一新闻时 URL 完全相同
2. 标题近似去重 —— 同一新闻不同源标题略改，URL 不同但内容重复

URL 用 Redis Set O(1) 判重；SimHash 用 SSCAN 遍历已存指纹比较汉明距离。
MVP 规模 50-100 条/天，全量遍历可接受，无需构建 VP-Tree。
"""
import logging

from app.core.simhash import is_similar

logger = logging.getLogger(__name__)

URL_SET_KEY = "crawler:dedup:url"
SIMHASH_SET_KEY = "crawler:dedup:simhash"


async def is_duplicate(url: str, title: str, simhash: str, redis) -> bool:
    """判断素材是否重复。

    URL 命中 → 重复；SimHash 与已存指纹汉明距离 ≤3 → 重复。
    title 参数保留供未来扩展（如基于标题的额外规则），当前仅用 simhash。
    """
    # URL 精确去重：O(1) 查询，优先判断以短路后续 SimHash 遍历
    if await redis.sismember(URL_SET_KEY, url):
        return True

    # SimHash 近似去重：遍历已存指纹，任一相似即判重
    # 规模小（百级），SSCAN 全量遍历可接受
    async for existing in redis.sscan_iter(SIMHASH_SET_KEY):
        if is_similar(simhash, existing, threshold=3):
            logger.debug("SimHash 命中近似重复: %s vs %s", simhash, existing)
            return True

    return False


async def add_to_dedup(url: str, simhash: str, redis, ttl_days: int = 7) -> None:
    """将素材加入去重集合。

    TTL 7 天自动过期，避免 Set 无限增长；
    SADD 是幂等操作，重复添加同值不会报错。
    """
    ttl_seconds = ttl_days * 86400

    await redis.sadd(URL_SET_KEY, url)
    await redis.expire(URL_SET_KEY, ttl_seconds)

    await redis.sadd(SIMHASH_SET_KEY, simhash)
    await redis.expire(SIMHASH_SET_KEY, ttl_seconds)
