"""停摆告警护栏测试（T01696）。

覆盖要点（对照历史教训设计）：
- 边界日期语义：cutoff 用时间对象 >= 比较，恰在窗口边界的 success 算"未停摆"
- UTC/本地时区口径：notification_log.created_at 是 SQLite CURRENT_TIMESTAMP（UTC），
  本地 07:30 的告警在库里是前一日 23:30——防抖必须按 UTC 解析转本地再比日期
- 多条 402/401/403 甄别与 24h 窗口
- 当日去重、无渠道降级、失败步骤分布
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.timeutil import localnow_naive
from app.models.notification_log import NotificationLog
from app.models.workflow import Workflow, WorkflowStep
from app.services.stall_alert import (
    ALERT_EVENT_TYPE,
    check_and_alert,
    detect_stall,
)


# ---------- 测试基建 ----------

def _utc_naive_of(local_dt: datetime) -> datetime:
    """把本地 naive 时间换算成对应的 UTC naive 时间（模拟 SQLite CURRENT_TIMESTAMP）。"""
    return (
        local_dt.replace(tzinfo=timezone.utc)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


class FakeHub:
    """记录调用的假 NotifierHub。"""

    def __init__(self, result: dict | None = None):
        self.calls: list = []
        self.result = result or {
            "total": 1, "success": 1, "failed": 0, "suppressed": 0, "results": [],
        }

    async def send(self, event):
        self.calls.append(event)
        return self.result


@pytest.fixture
def fake_hub(monkeypatch):
    hub = FakeHub()
    monkeypatch.setattr(
        "app.services.notifier.hub.get_notifier_hub", lambda: hub
    )
    return hub


def _wf(wid: str, status: str, started_at: datetime) -> Workflow:
    return Workflow(
        id=wid, episode_date=started_at.date(), source="cron",
        status=status, started_at=started_at,
    )


def _step(wid: str, step: str, started_at: datetime, error: str = "") -> WorkflowStep:
    return WorkflowStep(
        workflow_id=wid, step_name=step, status="failed",
        started_at=started_at, error=error,
    )


# ---------- detect_stall ----------

@pytest.mark.asyncio
async def test_empty_db_is_stalled(db_session):
    """空库（从未成功过）→ 停摆，且 last_success_at=None 不炸。"""
    report = await detect_stall(db_session, now=localnow_naive())
    assert report.stalled is True
    assert report.last_success_at is None
    assert "从未有过成功记录" in report.summary()


@pytest.mark.asyncio
async def test_recent_success_not_stalled(db_session):
    now = localnow_naive()
    db_session.add(_wf("wf-ok", "success", now - timedelta(days=1)))
    await db_session.commit()
    report = await detect_stall(db_session, now=now)
    assert report.stalled is False
    assert report.success_in_window == 1


@pytest.mark.asyncio
async def test_stale_success_stalled_with_last_time(db_session):
    """最后一次成功在窗口外 → 停摆，摘要里能看到最后成功时间。"""
    now = localnow_naive()
    db_session.add(_wf("wf-old", "success", now - timedelta(days=3)))
    await db_session.commit()
    report = await detect_stall(db_session, now=now, stall_days=2)
    assert report.stalled is True
    assert report.last_success_at is not None
    assert "最后成功" in report.summary()


@pytest.mark.asyncio
async def test_boundary_success_included(db_session):
    """恰好在 cutoff 时刻的 success 必须算未停摆（>= 语义，含边界）。"""
    now = localnow_naive()
    db_session.add(_wf("wf-edge", "success", now - timedelta(days=2)))
    await db_session.commit()
    report = await detect_stall(db_session, now=now, stall_days=2)
    assert report.stalled is False


@pytest.mark.asyncio
async def test_auth_error_402_and_401_in_24h(db_session):
    """402 与 401 都算余额/鉴权异常，24h 窗口内多条累计。"""
    now = localnow_naive()
    db_session.add(_wf("wf-a", "failed", now - timedelta(hours=2)))
    db_session.add(_step("wf-a", "rewrite", now - timedelta(hours=2),
                         "Error code: 402 - {'code': 30001}"))
    db_session.add(_step("wf-a", "rewrite", now - timedelta(hours=1),
                         "Error code: 401 unauthorized"))
    await db_session.commit()
    report = await detect_stall(db_session, now=now)
    assert report.has_auth_error is True
    assert report.auth_errors_24h == 2


@pytest.mark.asyncio
async def test_auth_error_outside_24h_not_counted(db_session):
    """402 发生在 24h 之外（如 2 天前）→ 不触发鉴权告警（停摆规则另行覆盖）。"""
    now = localnow_naive()
    db_session.add(_wf("wf-b", "failed", now - timedelta(days=2)))
    db_session.add(_step("wf-b", "rewrite", now - timedelta(days=2),
                         "Error code: 402"))
    await db_session.commit()
    report = await detect_stall(db_session, now=now)
    assert report.has_auth_error is False


@pytest.mark.asyncio
async def test_403_not_flagged_as_auth_error(db_session):
    """403/404/500 等其他错误码不误报为余额/鉴权异常。"""
    now = localnow_naive()
    db_session.add(_wf("wf-c", "failed", now - timedelta(hours=1)))
    db_session.add(_step("wf-c", "tts", now - timedelta(hours=1),
                         "HTTP 403 forbidden"))
    await db_session.commit()
    report = await detect_stall(db_session, now=now)
    assert report.has_auth_error is False


@pytest.mark.asyncio
async def test_recent_failure_distribution(db_session):
    """近 3 天失败步骤分布进入报告（供告警正文定位问题）。"""
    now = localnow_naive()
    db_session.add(_wf("wf-d", "failed", now - timedelta(days=1)))
    db_session.add(_step("wf-d", "rewrite", now - timedelta(days=1), "boom"))
    db_session.add(_step("wf-d", "rewrite", now - timedelta(days=1), "boom2"))
    db_session.add(_step("wf-d", "crawl", now - timedelta(days=1), "dead rss"))
    await db_session.commit()
    report = await detect_stall(db_session, now=now)
    assert report.recent_failures == {"rewrite": 2, "crawl": 1}


# ---------- check_and_alert ----------

@pytest.mark.asyncio
async def test_alert_sent_and_logged(db_session, fake_hub):
    """停摆 → 发送 critical 事件 + 落 notification_log(success)。"""
    now = localnow_naive()
    db_session.add(_wf("wf-old", "success", now - timedelta(days=10)))
    await db_session.commit()

    result = await check_and_alert(db_session, now=now)
    assert result["status"] == "success"
    assert len(fake_hub.calls) == 1
    event = fake_hub.calls[0]
    assert event.severity == "critical"
    assert "停摆" in event.title
    log = (await db_session.execute(
        __import__("sqlalchemy").select(NotificationLog)
        .where(NotificationLog.event_type == ALERT_EVENT_TYPE)
        .order_by(NotificationLog.id.desc()).limit(1)
    )).scalar_one_or_none()
    assert log is not None and log.status == "success"


@pytest.mark.asyncio
async def test_all_ok_no_alert(db_session, fake_hub):
    """一切正常（窗口内有一次成功）→ 不发送、不落告警日志。"""
    now = localnow_naive()
    db_session.add(_wf("wf-ok", "success", now - timedelta(hours=3)))
    await db_session.commit()
    result = await check_and_alert(db_session, now=now)
    assert result["status"] == "ok"
    assert fake_hub.calls == []


@pytest.mark.asyncio
async def test_dedup_same_day_local(db_session, fake_hub):
    """当日已成功告警 → skipped。"""
    now = localnow_naive()
    db_session.add(_wf("wf-old", "success", now - timedelta(days=10)))
    db_session.add(NotificationLog(
        event_type=ALERT_EVENT_TYPE, channel="multi", title="t",
        status="success", created_at=_utc_naive_of(now - timedelta(hours=1)),
    ))
    await db_session.commit()
    result = await check_and_alert(db_session, now=now)
    assert result["status"] == "skipped"
    assert fake_hub.calls == []


@pytest.mark.asyncio
async def test_dedup_local_morning_is_utc_previous_day(db_session, fake_hub):
    """关键时区场景：本地 07:30 告警在库里是前一日 UTC 23:30，
    按 UTC 字符串比日期会漏判导致重复告警，必须转本地后判定为当日。"""
    now = datetime(2026, 10, 9, 7, 30, 0)
    db_session.add(_wf("wf-old", "success", now - timedelta(days=10)))
    db_session.add(NotificationLog(
        event_type=ALERT_EVENT_TYPE, channel="multi", title="t",
        status="success",
        created_at=datetime(2026, 10, 8, 23, 30, 0),  # 本地 10-09 07:30 = UTC 10-08 23:30
    ))
    await db_session.commit()
    result = await check_and_alert(db_session, now=now)
    assert result["status"] == "skipped"
    assert fake_hub.calls == []


@pytest.mark.asyncio
async def test_failed_send_logged_but_not_deduped(db_session, monkeypatch):
    """无可用渠道 → 落 failed 日志、不静默吞掉，次日仍会重试（不去重）。"""
    hub = FakeHub(result={"total": 0, "success": 0, "failed": 0,
                          "suppressed": 0, "results": []})
    monkeypatch.setattr(
        "app.services.notifier.hub.get_notifier_hub", lambda: hub
    )

    now = localnow_naive()
    db_session.add(_wf("wf-old", "success", now - timedelta(days=10)))
    await db_session.commit()

    result = await check_and_alert(db_session, now=now)
    assert result["status"] == "failed"
    # failed 不算成功告警 → 再次检查仍会尝试发送（不跳过）
    again = await check_and_alert(db_session, now=now)
    assert again["status"] == "failed"
    assert len(hub.calls) == 2


@pytest.mark.asyncio
async def test_auth_only_alert_title(db_session, fake_hub):
    """仅余额/鉴权异常（未停摆）→ 标题聚焦余额，不停摆措辞。"""
    now = localnow_naive()
    db_session.add(_wf("wf-ok", "success", now - timedelta(hours=1)))
    db_session.add(_wf("wf-e", "failed", now - timedelta(hours=1)))
    db_session.add(_step("wf-e", "rewrite", now - timedelta(hours=1),
                         "Error code: 402 insufficient"))
    await db_session.commit()
    result = await check_and_alert(db_session, now=now)
    assert result["status"] == "success"
    event = fake_hub.calls[0]
    assert "余额" in event.title
    assert "停摆" not in event.title
