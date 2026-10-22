"""T02539（ACC-UX-501 / ACC-UX-005）：指标单位与刻度一致性验收。

PRD M5 验收第 1 条要求「平均收听显示值与 play_log.duration 秒值换算一致（抽查 3 天数据）」。
这里灌入 3 天真实 PlayLog 行，从后端口径钉住这条：

- 概览与趋势返回的都是**原始单位**（秒 / 0~1），不预换算；
- 换算只在 meta 的 factor/precision 里描述一次；
- 按 meta 换算出的展示值必须与 PRD 期望的分钟数逐字一致。

第 2 条「完播率在卡片/趋势/移动端三处一致」的展示端由前端
`tests/stats.spec.js`（卡片 vs 趋势 vs 移动端首页）覆盖，本文件只钉它的输入口径。
"""
from datetime import date, datetime, timedelta

import pytest

from app.models import Channel, Episode, PlayLog
from app.services.stats_service import StatsService

# 三天三种量级：整分钟、带小数、跨小时；补一个小数点后需四舍五入的样本
DAYS = [
    {"offset": 2, "durations": [300, 420], "completed": [1, 0], "minutes": "6.0", "rate": "50.0"},
    {"offset": 1, "durations": [512, 512], "completed": [0, 0], "minutes": "8.5", "rate": "0.0"},
    {"offset": 0, "durations": [600, 900], "completed": [1, 1], "minutes": "12.5", "rate": "100.0"},
]


def _avg(values):
    return sum(values) / len(values)


def _shown(raw, display):
    """与前端 metricNumber 同一契约：raw × factor，按 precision 四舍五入。"""
    return round(raw * display["factor"], display["precision"])


async def _seed_three_days(db):
    ch = Channel(name="验收频道T2539", channel_type="news", selection_strategy="heat")
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    ep = Episode(
        date=date.today(), title="T2539 节目", duration=600,
        audio_url="https://x/t2539.mp3", status="published", channel_id=ch.id,
    )
    db.add(ep)
    await db.commit()
    await db.refresh(ep)

    today = date.today()
    for day in DAYS:
        d = today - timedelta(days=day["offset"])
        for i, (duration, completed) in enumerate(zip(day["durations"], day["completed"])):
            db.add(PlayLog(
                user_id=str(i + 1), episode_id=ep.id, position=10,
                duration=duration, completed=completed,
                played_at=datetime.combine(d, datetime.min.time()) + timedelta(hours=10, minutes=i),
            ))
    await db.commit()
    return today


@pytest.mark.asyncio
async def test_three_days_duration_and_rate_scales(db_session):
    today = await _seed_three_days(db_session)
    svc = StatsService(db_session)

    for day in DAYS:
        d = today - timedelta(days=day["offset"])
        overview = await svc.get_overview(target_date=d)
        avg_seconds = _avg(day["durations"])

        dur_meta = overview["meta"]["avg_listen_duration"]
        assert dur_meta["unit"] == "second", "后端必须给原始秒值"
        assert dur_meta["display"]["factor"] == pytest.approx(1 / 60)
        assert dur_meta["display"]["precision"] == 1

        # 原始值没有被预换算成分钟
        assert overview["avg_listen_duration"] == pytest.approx(avg_seconds)
        shown = _shown(overview["avg_listen_duration"], dur_meta["display"])
        assert f"{shown:.1f}" == day["minutes"], (
            f"{d} 平均收听应显示 {day['minutes']} 分钟，实际 {shown}"
        )

        rate_meta = overview["meta"]["completion_rate"]
        assert rate_meta["unit"] == "ratio"
        assert rate_meta["display"]["unit"] == "%"
        assert rate_meta["display"]["factor"] == pytest.approx(100)
        assert overview["completion_rate"] == pytest.approx(_avg(day["completed"]))
        rate_shown = _shown(overview["completion_rate"], rate_meta["display"])
        assert f"{rate_shown:.1f}" == day["rate"]


@pytest.mark.asyncio
async def test_three_days_trend_shares_the_same_scale(db_session):
    today = await _seed_three_days(db_session)
    svc = StatsService(db_session)

    dur_trend = await svc.get_trend("avg_listen_duration", 3)
    assert dur_trend["dates"] == [(today - timedelta(days=2 - i)).isoformat() for i in range(3)]
    assert dur_trend["values"] == [
        pytest.approx(_avg(day["durations"])) for day in DAYS
    ], "趋势点必须是原始秒值，与卡片同一输入"
    dur_display = dur_trend["meta"]["avg_listen_duration"]["display"]
    assert [f"{_shown(v, dur_display):.1f}" for v in dur_trend["values"]] == [
        day["minutes"] for day in DAYS
    ]

    rate_trend = await svc.get_trend("completion_rate", 3)
    assert rate_trend["values"] == [pytest.approx(_avg(day["completed"])) for day in DAYS]
    rate_display = rate_trend["meta"]["completion_rate"]["display"]
    assert [f"{_shown(v, rate_display):.1f}" for v in rate_trend["values"]] == [
        day["rate"] for day in DAYS
    ]
