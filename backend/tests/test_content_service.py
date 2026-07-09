"""内容服务测试。

覆盖 services/content_service.py：
- get_today_episode：无发布节目返回 None；有发布节目返回数据
- get_history：分页正确
- publish_episode：发布后创建 episode + 失效缓存
- cache-aside 模式：miss 时查 DB 回写，hit 时直接返回缓存
"""
from datetime import date, datetime, timedelta

import pytest

from app.cache.manager import cache as cache_manager
from app.models import Episode, Script, Review, EpisodeStatus, ReviewStatus
from app.services.content_service import ContentService


async def _create_episode(
    db, target_date: date, status=EpisodeStatus.published, title=None, episode_id=None
):
    """辅助：插入一条 episode 记录。"""
    ep = Episode(
        id=episode_id,
        date=target_date,
        title=title or f"{target_date.isoformat()} 节目",
        duration=600,
        audio_url=f"http://cdn/{target_date.isoformat()}.mp3",
        cover_url="http://cdn/cover.png",
        categories=["科技", "财经"],
        status=status,
        published_at=datetime.utcnow() if status == EpisodeStatus.published else None,
    )
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    return ep


@pytest.mark.asyncio
async def test_get_today_episode_none(db_session):
    """今日无已发布节目时返回 None。"""
    svc = ContentService(db_session)
    result = await svc.get_today_episode()
    assert result is None


@pytest.mark.asyncio
async def test_get_today_episode_published(db_session):
    """今日有 published 节目时返回节目数据。"""
    today = date.today()
    await _create_episode(db_session, today, status=EpisodeStatus.published)

    svc = ContentService(db_session)
    result = await svc.get_today_episode()
    assert result is not None
    assert result["date"] == today.isoformat()
    assert result["status"] == "published"
    assert "audio_url" in result


@pytest.mark.asyncio
async def test_get_today_episode_draft_not_returned(db_session):
    """draft 状态的节目不应被 get_today_episode 返回。"""
    today = date.today()
    await _create_episode(db_session, today, status=EpisodeStatus.draft)

    svc = ContentService(db_session)
    result = await svc.get_today_episode()
    assert result is None


@pytest.mark.asyncio
async def test_get_history_pagination(db_session):
    """分页查询：total 正确，list 按日期倒序返回对应页。"""
    # 插入 5 期已发布节目
    base = date.today()
    for i in range(5):
        await _create_episode(
            db_session, base - timedelta(days=i),
            title=f"第{i}期",
        )

    svc = ContentService(db_session)

    # 第一页 2 条
    page1 = await svc.get_history(page=1, size=2)
    assert page1["total"] == 5
    assert len(page1["list"]) == 2
    # 倒序：最新（base）应在第一条
    assert page1["list"][0]["date"] == base.isoformat()

    # 第二页 2 条
    page2 = await svc.get_history(page=2, size=2)
    assert page2["total"] == 5
    assert len(page2["list"]) == 2

    # 第三页 1 条
    page3 = await svc.get_history(page=3, size=2)
    assert len(page3["list"]) == 1


@pytest.mark.asyncio
async def test_get_history_invalid_page_returns_empty(db_session):
    """page < 1 或 size < 1 返回空列表。"""
    svc = ContentService(db_session)
    result = await svc.get_history(page=0, size=10)
    assert result == {"total": 0, "list": []}
    result = await svc.get_history(page=1, size=0)
    assert result == {"total": 0, "list": []}


@pytest.mark.asyncio
async def test_publish_episode_creates_episode_and_invalidates_cache(db_session):
    """publish_episode：创建 episode 记录 + 失效 episode:today 缓存。"""
    # 预置 script + review
    script = Script(
        workflow_id="wf-test-001",
        episode_date=date.today(),
        full_text="稿件全文",
        segments=[{"seq": 1, "title": "段1", "content": "内容"}],
        estimated_duration=600,
        categories=["科技"],
        status="approved",
    )
    db_session.add(script)
    await db_session.flush()

    review = Review(
        workflow_id="wf-test-001",
        episode_date=date.today(),
        script_id=script.id,
        audio_url="http://cdn/today.mp3",
        status=ReviewStatus.pending,
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)

    # 预先写一个 episode:today 缓存，验证发布后被删除
    # cache_manager.set 直接接收 Python 对象，无需 json.dumps
    await cache_manager.set("episode:today", {"old": True}, ttl=3600)
    # 预写列表缓存
    await cache_manager.set("episode:list:page:1", {"old": True}, ttl=3600)

    svc = ContentService(db_session)
    episode_id = await svc.publish_episode("wf-test-001", review.id)

    # episode 已创建
    assert episode_id > 0
    from sqlalchemy import select
    res = await db_session.execute(select(Episode).where(Episode.id == episode_id))
    ep = res.scalar_one()
    assert ep.status == EpisodeStatus.published
    assert ep.review_id == review.id
    assert ep.workflow_id == "wf-test-001"

    # 缓存应被失效：get 返回 None 即表示已删除
    assert await cache_manager.get("episode:today") is None
    assert await cache_manager.get("episode:list:page:1") is None


@pytest.mark.asyncio
async def test_publish_episode_review_not_found_raises(db_session):
    """review 不存在时 publish_episode 抛 NotFoundError。"""
    from app.core.exceptions import NotFoundError
    svc = ContentService(db_session)
    with pytest.raises(NotFoundError):
        await svc.publish_episode("wf-x", 99999)


@pytest.mark.asyncio
async def test_cache_miss_and_hit(db_session):
    """cache-aside 模式：首次 miss 查 DB 回写，二次 hit 直接返回缓存。

    通过修改 DB 数据验证第二次返回的是缓存（旧数据）而非新数据。
    """
    today = date.today()
    ep = await _create_episode(db_session, today, title="原始标题")

    svc = ContentService(db_session)

    # 第一次：cache miss，查 DB 并回写缓存
    result1 = await svc.get_today_episode()
    assert result1["title"] == "原始标题"

    # 篡改 DB 数据（不通过缓存）
    ep.title = "新标题"
    await db_session.commit()

    # 第二次：cache hit，应返回缓存的旧标题
    result2 = await svc.get_today_episode()
    assert result2["title"] == "原始标题"

    # 验证缓存 key 存在：get 返回非 None 即表示命中
    assert await cache_manager.get("episode:today") is not None
