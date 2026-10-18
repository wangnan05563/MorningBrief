"""T02496（FR-UX-302）：趋势接口必须区分「没有数据」与「数据为 0」。

旧实现在缺数据的日期补 0，前端 hasTrend 只看 dates 长度，于是空档期被画成
一条贴着 0 的折线——看起来像「这两天用户播放量归零」，实际是根本没记录。
改造后：dates 仍与区间等长（用于对齐坐标轴），values 在缺数据日期给 null，
前端据此判空并显示「暂无趋势数据」而不是 0 折线。
"""
from datetime import date, datetime, timedelta

import pytest

from app.models import Channel, Episode, PlayLog
from app.services.stats_service import StatsService


async def _episode(db):
    ch = Channel(name="资讯频道T2496", channel_type="news", selection_strategy="heat")
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    ep = Episode(
        date=date.today(), title="T2496 节目", duration=600,
        audio_url="https://x/t2496.mp3", status="published", channel_id=ch.id,
    )
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    return ep


async def _log(db, ep, played_at, user_id, duration, completed):
    db.add(PlayLog(
        user_id=user_id, episode_id=ep.id, position=10, duration=duration,
        completed=completed, played_at=played_at,
    ))
    await db.commit()


@pytest.mark.asyncio
async def test_trend_gap_days_are_null_not_zero(db_session):
    ep = await _episode(db_session)
    today = datetime.now()
    two_days_ago = today - timedelta(days=2)
    # 今日 2 个不同用户，前日 1 个用户；其余 5 天完全无记录
    await _log(db_session, ep, today, "1", 300, True)
    await _log(db_session, ep, today, "2", 500, False)
    await _log(db_session, ep, two_days_ago, "1", 200, True)

    data = await StatsService(db_session).get_trend(metric="play_count", range_days=7)

    assert len(data["dates"]) == 7
    assert len(data["values"]) == 7
    by_date = dict(zip(data["dates"], data["values"]))
    assert by_date[today.date().isoformat()] == 2
    assert by_date[two_days_ago.date().isoformat()] == 1
    # 空档日必须是 null：0 会被前端当成真实的零播放
    gap_days = [d for d in data["dates"] if d not in (today.date().isoformat(), two_days_ago.date().isoformat())]
    assert len(gap_days) == 5
    assert all(by_date[d] is None for d in gap_days)


@pytest.mark.asyncio
async def test_trend_all_null_when_no_records(db_session):
    """整段区间无记录：values 全为 null，前端 hasTrend 必须判为假。"""
    data = await StatsService(db_session).get_trend(metric="dau", range_days=7)
    assert len(data["dates"]) == 7
    assert data["values"] == [None] * 7


@pytest.mark.asyncio
async def test_trend_null_aggregate_is_not_reported_as_zero(db_session):
    """当天有记录但指标列全为 NULL（avg 返回 NULL）：该日同样是 null 而非 0。"""
    ep = await _episode(db_session)
    played_at = datetime.now()
    db_session.add(PlayLog(
        user_id="1", episode_id=ep.id, position=0, duration=None,
        completed=None, played_at=played_at,
    ))
    await db_session.commit()

    data = await StatsService(db_session).get_trend(metric="avg_listen_duration", range_days=7)
    assert data["values"][-1] is None
