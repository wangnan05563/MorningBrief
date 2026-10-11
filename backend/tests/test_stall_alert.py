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
from sqlalchemy import select

from app.core.timeutil import localnow_naive
from app.models.notification_log import NotificationLog
from app.models.workflow import Workflow, WorkflowStep
from app.services.notification.log_service import LogService
from app.services.notifier.base import NotifyResult
from app.services.stall_alert import (
    ALERT_EVENT_TYPE,
    check_and_alert,
    detect_stall,
)


# ---------- 测试基建 ----------

def _utc_naive_of(local_dt: datetime) -> datetime:
    """把本地 naive 时间换算成对应的 UTC naive 时间（模拟 SQLite CURRENT_TIMESTAMP）。

    必须真正做时区换算：SQLite 的 CURRENT_TIMESTAMP 是 UTC，本地 18:00 落库是 10:00。
    历史缺陷（T02027）：此处曾用 `replace(tzinfo=utc).astimezone(utc)`，是恒等变换——
    把本地钟点当成 UTC 存进库，造出生产写不出来的记录；`_already_alerted_today`
    按 UTC 解回本地后会整体偏移一个时区差，本地钟点 ≥17:00 时跨到次日，
    防抖判 False 从而重复发送，用例只在白天通过（时间依赖性假失败）。
    """
    local_tz = datetime.now().astimezone().tzinfo
    return (
        local_dt.replace(tzinfo=local_tz)
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
    """当日已成功告警 → skipped（用例内钉住正午本地钟点，不依赖跑测试的时机）。"""
    now = datetime(2026, 10, 11, 12, 0, 0)
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
async def test_dedup_against_real_write_path(db_session, fake_hub):
    """防抖口径必须与真实写入口径一致：日志由 LogService 落库（created_at 走
    server_default=func.now()，SQLite 为 UTC naive），不手造时间戳。

    这是 T02027 的回归锚点：上一版用例自己造了一个生产写不出来的 created_at，
    既掩盖了口径、又让结果随本地钟点漂移。真实写入 + 当前本地时刻必然同日。
    """
    now = localnow_naive()
    db_session.add(_wf("wf-old", "success", now - timedelta(days=10)))
    await db_session.commit()
    await LogService(db_session).create_log(
        event_type=ALERT_EVENT_TYPE, channel="multi", title="t", status="success",
    )
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


# ---------- T02030：per-channel 真因落库 + 同日失败上限 ----------

async def _logs(db_session, status: str | None = None) -> list[NotificationLog]:
    stmt = select(NotificationLog).where(NotificationLog.event_type == ALERT_EVENT_TYPE)
    if status:
        stmt = stmt.where(NotificationLog.status == status)
    rows = (await db_session.execute(stmt.order_by(NotificationLog.id))).scalars().all()
    return list(rows)


@pytest.mark.asyncio
async def test_per_channel_errors_land_in_payload(db_session, monkeypatch):
    """渠道全部失败时，hub 的逐渠道 error 必须写进 payload（管理端看详情即知真因）。"""
    hub = FakeHub(result={
        "total": 1, "success": 0, "failed": 1, "suppressed": 0,
        "results": [NotifyResult(
            channel="wecom", success=False,
            error="网络错误: Request URL is missing an 'http://' or 'https://' protocol.",
        )],
    })
    monkeypatch.setattr("app.services.notifier.hub.get_notifier_hub", lambda: hub)

    now = localnow_naive()
    db_session.add(_wf("wf-old", "success", now - timedelta(days=10)))
    await db_session.commit()

    assert (await check_and_alert(db_session, now=now))["status"] == "failed"
    import json
    log = (await _logs(db_session))[-1]
    payload = json.loads(log.payload)
    assert payload["channels"] == [{
        "channel": "wecom", "success": False,
        "error": "网络错误: Request URL is missing an 'http://' or 'https://' protocol.",
    }]
    assert payload["hub"] == {"total": 1, "success": 0, "failed": 1, "suppressed": 0}
    # 聚合 error 仍是旧口径（不破坏既有前端展示），真因在 channels 里
    assert log.error == "所有渠道发送失败"


@pytest.mark.asyncio
async def test_no_channel_failure_is_recorded_explicitly(db_session, monkeypatch):
    """一个渠道都没加载（total==0）→ 记录里显式写「未配置任何通知渠道」而不是网络错误。"""
    hub = FakeHub(result={"total": 0, "success": 0, "failed": 0,
                          "suppressed": 0, "results": []})
    monkeypatch.setattr("app.services.notifier.hub.get_notifier_hub", lambda: hub)

    now = localnow_naive()
    db_session.add(_wf("wf-old", "success", now - timedelta(days=10)))
    await db_session.commit()

    await check_and_alert(db_session, now=now)
    import json
    log = (await _logs(db_session))[-1]
    assert log.status == "failed"
    assert "未配置任何通知渠道" in log.error
    assert json.loads(log.payload)["channels"][0]["channel"] == "-"


@pytest.mark.asyncio
async def test_same_day_failure_cap_stops_retrying(db_session, monkeypatch):
    """同日连续失败达上限（默认 3）→ 落一条 failed_capped 并停止重试；再次检查不再刷记录。

    与 test_failed_send_logged_but_not_deduped 的既有语义相容：failed 不参与成功防抖，
    上限之内（<3 次）仍会重试，超过上限才收敛——不是把失败当成功吞掉。
    """
    hub = FakeHub(result={
        "total": 1, "success": 0, "failed": 1, "suppressed": 0,
        "results": [NotifyResult(channel="wecom", success=False, error="网络错误: boom")],
    })
    monkeypatch.setattr("app.services.notifier.hub.get_notifier_hub", lambda: hub)

    now = localnow_naive()
    db_session.add(_wf("wf-old", "success", now - timedelta(days=10)))
    await db_session.commit()

    for _ in range(3):
        assert (await check_and_alert(db_session, now=now))["status"] == "failed"
    assert len(hub.calls) == 3

    capped = await check_and_alert(db_session, now=now)
    assert capped["status"] == "failed_capped"
    assert capped["failed_today"] == 3
    assert len(hub.calls) == 3  # 达上限后不再调用渠道

    assert len(await _logs(db_session, "failed")) == 3
    capped_logs = await _logs(db_session, "failed_capped")
    assert len(capped_logs) == 1
    assert "上限" in capped_logs[0].error

    # 同日再检查：已有 failed_capped → 直接跳过，不再刷库
    again = await check_and_alert(db_session, now=now)
    assert again["status"] == "skipped"
    assert again["reason"] == "今日发送失败已达上限"
    assert len(hub.calls) == 3
    assert len(await _logs(db_session)) == 4


@pytest.mark.asyncio
async def test_failure_cap_is_per_local_day(db_session, monkeypatch):
    """失败计数按本地日归零：前一日的 failed 不吃掉今天的重试额度。"""
    hub = FakeHub(result={
        "total": 1, "success": 0, "failed": 1, "suppressed": 0,
        "results": [NotifyResult(channel="wecom", success=False, error="网络错误: boom")],
    })
    monkeypatch.setattr("app.services.notifier.hub.get_notifier_hub", lambda: hub)

    now = localnow_naive()
    db_session.add(_wf("wf-old", "success", now - timedelta(days=10)))
    for _ in range(5):
        db_session.add(NotificationLog(
            event_type=ALERT_EVENT_TYPE, channel="multi", title="t", status="failed",
            created_at=_utc_naive_of(now - timedelta(days=1)),
        ))
    await db_session.commit()

    assert (await check_and_alert(db_session, now=now))["status"] == "failed"
    assert len(hub.calls) == 1
