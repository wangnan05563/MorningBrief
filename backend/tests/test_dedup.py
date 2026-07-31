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


@pytest.mark.asyncio
async def test_is_duplicate_material_url_hit_when_dedup_empty(db_session):
    """dedup 表无记录但 material 表有同 URL 时应判重（双源去重兜底）。

    复盘 wf-20260730-0005/0006/0008 故障：凌晨 03:00 _cleanup_crawler_dedup
    清理 TTL 过期 dedup 记录，但 material.url 仍保留 UNIQUE 约束。
    05:00 cron crawl 时 dedup 未命中但 INSERT material 触发 UNIQUE 冲突。
    修复：is_duplicate 同时检查 material.url，避免 INSERT 冲突。
    """
    from app.models.material import Material, MaterialSourceType, MaterialStatus

    url = "http://example.com/legacy-article"
    # 直接向 material 表插入一条记录（不通过 dedup，模拟 dedup 被 TTL 清理后的状态）
    material = Material(
        source="测试源",
        source_type=MaterialSourceType.rss,
        title="测试标题",
        content="测试内容",
        url=url,
        status=MaterialStatus.pending.value,
        simhash=compute("测试标题"),
    )
    db_session.add(material)
    await db_session.commit()

    # dedup 表为空，但 material 表有该 URL → 应判重
    result = await is_duplicate(url, "其他标题", compute("其他标题"), db_session)
    assert result is True


@pytest.mark.asyncio
async def test_is_duplicate_dedup_hit_short_circuits_material_check(db_session):
    """dedup 命中时应短路返回，不再查询 material 表（性能优化）。

    验证 dedup 检查优先于 material.url 检查。
    """
    url = "http://example.com/dedup-first"
    await add_to_dedup(url, compute("dedup 测试"), db_session)
    await db_session.commit()

    # material 表中无此 URL，但 dedup 表命中 → 应判重（短路）
    result = await is_duplicate(url, "其他标题", compute("其他标题"), db_session)
    assert result is True
