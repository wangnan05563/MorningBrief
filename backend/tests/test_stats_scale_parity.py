"""T02507（FR-UX-502）：完播率「三处同刻度」的数据层前提。

前端把单位换算收敛到 `meta.display.factor` 一个出口（T02506），前提是三处读到的
原始值本来就是同一个数：

- `overview(某日)` 与 `trend(区间)` 对同一天必须给出相同的 ratio；
- 移动端 `m/dashboard-summary` 内嵌的 `today` 必须就是 `overview(today)`。

任一处分叉（趋势改成按节目平均、或后端提前把 ratio 乘成 65），卡片与曲线就会
差 100 倍或直接不等，而 UI 用例只看得见「显示得一致不一致」，看不见「该不该一致」
——所以这条契约钉在数据层。
"""
from datetime import date, datetime, timedelta

import pytest

from app.models import Channel, Episode, PlayLog
from app.services.mobile_service import dashboard_summary
from app.services.stats_metrics import METRIC_META
from app.services.stats_service import StatsService

# 概览与趋势可比的指标（ad_impression 是概览侧的派生估算，趋势没有这个维度）
COMPARABLE = ["dau", "play_count", "completion_rate", "avg_listen_duration"]


async def _episode(db):
    ch = Channel(name="资讯频道T2507", channel_type="news", selection_strategy="heat")
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    ep = Episode(
        date=date.today(), title="T2507 节目", duration=600,
        audio_url="https://x/t2507.mp3", status="published", channel_id=ch.id,
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


async def _seed_three_days(db, ep):
    """三天各不相同的完播构成：1.0 / 0.5 / 0.25，避免「碰巧相等」。"""
    today = datetime.now()
    days = []
    for offset, (users, completed_flags, duration) in {
        0: (["1", "2", "3", "4"], [True, True, True, True], 300),
        1: (["1", "2"], [True, False], 600),
        2: (["1", "2", "3", "4"], [True, False, False, False], 900),
    }.items():
        day = (today - timedelta(days=offset)).replace(hour=10, minute=0, second=0, microsecond=0)
        days.append(day.date())
        for user, flag in zip(users, completed_flags):
            await _log(db, ep, day, user, duration, flag)
    return days


@pytest.mark.asyncio
@pytest.mark.parametrize("metric", COMPARABLE)
async def test_overview_and_trend_report_same_value_for_same_day(db_session, metric):
    ep = await _episode(db_session)
    days = await _seed_three_days(db_session, ep)

    svc = StatsService(db_session)
    trend = await svc.get_trend(metric=metric, range_days=7)
    by_date = dict(zip(trend["dates"], trend["values"]))

    for d in days:
        overview = await svc.get_overview(target_date=d)
        assert overview[metric] == pytest.approx(by_date[d.isoformat()]), (
            f"{metric} 在 {d} 的概览值与趋势值不一致："
            f"overview={overview[metric]} trend={by_date[d.isoformat()]}——"
            "三处（卡片/趋势/移动端）不可能同刻度"
        )


@pytest.mark.asyncio
async def test_trend_completion_rate_stays_raw_ratio(db_session):
    """趋势下发 0~1 原始 ratio，百分化只由 meta 声明、由展示端乘一次。

    后端若提前乘 100（=65），前端按 meta 再乘一次就显示 6500%；
    这条断言把「接口给原始单位」的口径钉住（FR-UX-501 定的契约）。
    """
    ep = await _episode(db_session)
    await _seed_three_days(db_session, ep)

    data = await StatsService(db_session).get_trend(
        metric="completion_rate", range_days=7
    )
    real = [v for v in data["values"] if v is not None]
    assert real
    assert all(0.0 <= v <= 1.0 for v in real), f"完播率应以 ratio 下发：{real}"

    meta = data["meta"]["completion_rate"]
    assert meta["unit"] == "ratio"
    assert meta["display"]["unit"] == "%"
    assert meta["display"]["factor"] == pytest.approx(100)
    # 卡片与趋势共用同一份元数据定义，不存在「趋势另一套换算」
    assert meta == METRIC_META["completion_rate"]


@pytest.mark.asyncio
async def test_mobile_summary_embeds_same_overview(db_session):
    """移动端首页读的是 dashboard_summary.today，必须与 PC 概览逐字段相同。"""
    ep = await _episode(db_session)
    await _seed_three_days(db_session, ep)

    svc = StatsService(db_session)
    overview = await svc.get_overview(target_date=date.today())
    summary = await dashboard_summary(db_session, admin_id=1)

    for metric in COMPARABLE:
        assert summary["today"][metric] == pytest.approx(overview[metric]), metric
    assert summary["today"]["meta"] == overview["meta"]
