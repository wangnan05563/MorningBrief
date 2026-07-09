"""爬虫去重逻辑测试。

覆盖 workflow/crawler/dedup.py：
- add_to_dedup：URL + SimHash 写入 SQLite crawler_dedup 表
- is_duplicate：URL 命中返回 True
- is_duplicate：SimHash 近似命中返回 True
- 全新素材返回 False

V1.2 改造：Redis Set → SQLite crawler_dedup 表，TTL 由 APScheduler 定时清理。
"""
import pytest
from sqlalchemy import select

from app.core.simhash import compute
from app.models.crawler_dedup import CrawlerDedup
from app.workflow.crawler.dedup import (
    add_to_dedup,
    is_duplicate,
)


@pytest.mark.asyncio
async def test_add_to_dedup_writes_url_and_simhash(db_session):
    """add_to_dedup 后 crawler_dedup 表中应存在该 URL + simhash 记录。"""
    url = "http://example.com/news/1"
    simhash = compute("某条新闻标题")

    await add_to_dedup(url, simhash, db_session)
    await db_session.commit()

    # crawler_dedup 表中应能查到该记录
    result = await db_session.execute(
        select(CrawlerDedup).where(CrawlerDedup.url == url)
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.simhash == simhash


@pytest.mark.asyncio
async def test_is_duplicate_url_hit(db_session):
    """已存在的 URL 再次判断应返回 True（URL 精确去重）。"""
    url = "http://example.com/news/dup"
    simhash = compute("去重测试标题")

    # 首次添加
    await add_to_dedup(url, simhash, db_session)
    await db_session.commit()
    # 同 URL 再次判断应判重
    result = await is_duplicate(url, "其他标题", compute("其他标题"), db_session)
    assert result is True


@pytest.mark.asyncio
async def test_is_duplicate_simhash_similar(db_session):
    """SimHash 相近的标题（汉明距离 ≤3）应判为重复。

    使用完全相同的 simhash 模拟最直接的近似命中场景。
    """
    # 预置一条已存指纹
    title1 = "央行发布最新货币政策"
    simhash1 = compute(title1)
    await add_to_dedup("http://example.com/1", simhash1, db_session)
    await db_session.commit()

    # 新 URL 但 SimHash 完全相同 → 判重
    result = await is_duplicate(
        "http://example.com/2",  # 不同 URL
        title1,
        simhash1,  # 相同 simhash
        db_session,
    )
    assert result is True


@pytest.mark.asyncio
async def test_is_duplicate_new_material_returns_false(db_session):
    """全新 URL + 完全不同的 SimHash 应返回 False。"""
    # 预置一条
    await add_to_dedup(
        "http://example.com/old",
        compute("旧新闻标题一二三"),
        db_session,
    )
    await db_session.commit()

    # 全新素材
    result = await is_duplicate(
        "http://example.com/new",
        "完全不同的新内容标题",
        compute("完全不同的新内容标题"),
        db_session,
    )
    assert result is False


@pytest.mark.asyncio
async def test_is_duplicate_empty_set_returns_false(db_session):
    """空表（未添加任何素材）时任何素材都应返回 False。"""
    result = await is_duplicate(
        "http://example.com/any",
        "任意标题",
        compute("任意标题"),
        db_session,
    )
    assert result is False


@pytest.mark.asyncio
async def test_is_duplicate_url_takes_priority(db_session):
    """URL 命中应优先于 SimHash 判断（短路返回）。

    即使 SimHash 完全不同，URL 命中也应直接判重。
    """
    url = "http://example.com/same-url"
    await add_to_dedup(url, compute("标题 A"), db_session)
    await db_session.commit()

    # 同 URL + 完全不同的 simhash
    result = await is_duplicate(
        url,
        "标题 B",
        compute("标题 B"),  # 与已存的"标题 A" simhash 差异大
        db_session,
    )
    assert result is True
