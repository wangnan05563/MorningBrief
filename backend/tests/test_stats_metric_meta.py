"""T02506（FR-UX-501）：统计指标必须随数据下发单位元数据，且换算只在一处做。

背景：`avg_listen_duration` 后端返回的是秒（`func.avg(PlayLog.duration)`），
PC 卡片却标「(分钟)」且不换算、移动端标「(分)」同样不换算，`completion_rate`
一处乘 100 一处不乘——同一个指标在不同界面差 60 倍 / 100 倍。
本单把单位与换算登记在后端唯一真源里随接口下发，展示端按 meta 格式化。
"""
import json
from datetime import date, datetime
from pathlib import Path

import pytest

from app.models import Channel, Episode, PlayLog
from app.services.stats_metrics import METRIC_META, OVERVIEW_METRICS
from app.services.stats_service import StatsService

# 前端 e2e 夹具（由 scripts/gen_stats_metric_meta.py 从本表生成）
FRONTEND_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "apps" / "admin-web" / "tests" / "helpers" / "stats-metric-meta.json"
)


async def _episode(db):
    ch = Channel(name="资讯频道T2506", channel_type="news", selection_strategy="heat")
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    ep = Episode(
        date=date.today(), title="T2506 节目", duration=600,
        audio_url="https://x/t2506.mp3", status="published", channel_id=ch.id,
    )
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    return ep


@pytest.mark.asyncio
async def test_overview_raw_values_stay_in_source_unit(db_session):
    """接口给原始单位（秒 / 0~1 小数），换算交给 meta——预换算会变成第二份口径。"""
    ep = await _episode(db_session)
    now = datetime.now()
    db_session.add(PlayLog(user_id="1", episode_id=ep.id, position=10,
                           duration=512, completed=1, played_at=now))
    db_session.add(PlayLog(user_id="2", episode_id=ep.id, position=10,
                           duration=512, completed=0, played_at=now))
    await db_session.commit()

    data = await StatsService(db_session).get_overview(target_date=date.today())

    assert data["avg_listen_duration"] == pytest.approx(512.0)
    assert data["completion_rate"] == pytest.approx(0.5)
    # ACC-UX-501：显示值 = play_log.duration 秒值 ÷ 60，由 meta 描述而非页面硬编码
    assert data["meta"]["avg_listen_duration"]["display"] == {
        "unit": "分钟", "factor": pytest.approx(1 / 60), "precision": 1,
    }


@pytest.mark.asyncio
async def test_overview_meta_covers_all_returned_metrics(db_session):
    """概览返回几个指标就必须给几份单位，漏一个前端只会显示 '-'，不会猜单位。"""
    ep = await _episode(db_session)
    db_session.add(PlayLog(user_id="1", episode_id=ep.id, position=10,
                           duration=300, completed=1, played_at=datetime.now()))
    await db_session.commit()

    data = await StatsService(db_session).get_overview(target_date=date.today())

    assert list(data["meta"]) == OVERVIEW_METRICS
    for key in OVERVIEW_METRICS:
        assert key in data, f"{key} 在单位表里登记了却没出现在概览返回中"
        meta = data["meta"][key]
        assert meta["unit"] in {"count", "second", "ratio", "percent"}
        assert set(meta["display"]) == {"unit", "factor", "precision"}


@pytest.mark.asyncio
async def test_trend_returns_meta_for_requested_metric(db_session):
    ep = await _episode(db_session)
    db_session.add(PlayLog(user_id="1", episode_id=ep.id, position=10,
                           duration=300, completed=1, played_at=datetime.now()))
    await db_session.commit()

    data = await StatsService(db_session).get_trend(metric="dau", range_days=7)

    assert data["metric"] == "dau"
    assert data["meta"] == {"dau": METRIC_META["dau"]}


def test_frontend_e2e_fixture_matches_backend_table():
    """前端测试夹具必须与本表逐字一致（防止「夹具抄错、CI 照样绿」复发）。"""
    fixture = json.loads(FRONTEND_FIXTURE.read_text(encoding="utf-8"))
    assert fixture == METRIC_META, (
        "apps/admin-web/tests/helpers/stats-metric-meta.json 已过期，"
        "请重跑 python scripts/gen_stats_metric_meta.py"
    )


def _headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def test_overview_endpoint_returns_meta_in_envelope(client, admin_token):
    """接口冒烟：单位元数据要真的出现在 HTTP 响应里，而不只在 service 返回值里。"""
    resp = client.get(
        "/admin/api/v1/stats/overview",
        params={"date": date.today().isoformat()},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert list(data["meta"]) == OVERVIEW_METRICS
    assert data["meta"]["avg_listen_duration"]["unit"] == "second"


def test_dashboard_summary_endpoint_shares_the_same_meta(client, admin_token):
    """移动首页内嵌同一份 overview + meta：两端不可能各说一种单位。"""
    resp = client.get("/admin/api/v1/m/dashboard-summary", headers=_headers(admin_token))
    assert resp.status_code == 200
    today = resp.json()["data"]["today"]
    assert list(today["meta"]) == OVERVIEW_METRICS
