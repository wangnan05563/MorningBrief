"""有声读物 book_rss 去重豁免回归测试。

背景：全局 SimHash 近似去重会把书籍评论（尤其豆瓣书评）误判为与已存
新闻/影评近似重复，导致有声读物频道抓取 0 素材、工作流失败。
修复：book_rss 来源仅走 URL 精确去重，豁免 SimHash 近似去重。
"""
import hashlib

import pytest

from app.models.crawler_dedup import CrawlerDedup
from app.workflow.crawler.dedup import is_duplicate

# 64-bit hex 形式的 simhash 占位（与 is_similar 阈值逻辑无关，仅用于命中判定）
SIM = "0123456789abcdef0123456789abcdef"
OTHER_SIM = "ffffffffffffffffffffffffffffffff"


async def _seed_dedup(session, url: str, simhash: str) -> None:
    uh = hashlib.md5(url.encode()).hexdigest()
    session.add(CrawlerDedup(url=url, url_hash=uh, simhash=simhash))
    await session.commit()


async def test_book_rss_exempt_from_simhash_dedup(db_session):
    """book_rss 素材即使 simhash 与已存内容碰撞，也不应被判重（仅 URL 去重）。"""
    await _seed_dedup(db_session, "https://news.example.com/old", SIM)

    # 通用 rss：simhash 命中 -> 判重
    assert await is_duplicate(
        "https://book.example.com/new-1", "书评标题", SIM, db_session, source_type="rss"
    ) is True

    # book_rss：豁免 SimHash -> 不判重（URL 不在库）
    assert await is_duplicate(
        "https://book.example.com/new-1", "书评标题", SIM, db_session, source_type="book_rss"
    ) is False


async def test_book_rss_still_url_deduped(db_session):
    """book_rss 仍须遵守 URL 精确去重（material.url UNIQUE 兜底）。"""
    dup_url = "https://book.example.com/dup-review"
    await _seed_dedup(db_session, dup_url, OTHER_SIM)

    # 即使 simhash 完全不同，URL 命中即判重
    assert await is_duplicate(
        dup_url, "另一书评", OTHER_SIM, db_session, source_type="book_rss"
    ) is True


async def test_book_rss_url_hash_dedup(db_session):
    """book_rss 素材若 URL 已在 crawler_dedup 中，仍判重。"""
    url = "https://book.example.com/in-dedup"
    await _seed_dedup(db_session, url, OTHER_SIM)

    assert await is_duplicate(
        url, "标题", SIM, db_session, source_type="book_rss"
    ) is True
