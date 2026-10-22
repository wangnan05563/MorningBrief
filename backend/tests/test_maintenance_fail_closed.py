"""T02612：维护态读取失败不再 fail-open（停服指令不得被静默绕过）。

口径：
1. 读库异常且从未成功读到过 → 按维护态处理（fail-closed），拒绝新任务；
2. 读库异常但已有最后已知值（哪怕缓存已过期）→ 沿用它；
3. 首次降级发一次 critical 告警，恢复后重置；
4. 调度器连 session 都建不起来时同样按停服处理。
"""
import time
from datetime import date

import pytest

from app.services import mobile_service


@pytest.fixture(autouse=True)
def _reset_maint_state(monkeypatch):
    """清模块级缓存与降级标志，并拦下真实通知（守护线程）以便断言。"""
    mobile_service._maint_cache["value"] = None
    mobile_service._maint_cache["ts"] = 0.0
    mobile_service._maint_degraded = False
    notices: list[str] = []
    monkeypatch.setattr(
        mobile_service, "_notify_maintenance_check_failed", notices.append
    )
    yield notices
    mobile_service._maint_cache["value"] = None
    mobile_service._maint_cache["ts"] = 0.0
    mobile_service._maint_degraded = False


def _expire_cache(seconds: float = 60) -> None:
    mobile_service._maint_cache["ts"] = time.time() - seconds


@pytest.mark.asyncio
async def test_read_failure_without_known_value_fails_closed(db_session, monkeypatch, _reset_maint_state):
    async def boom(_db):
        raise RuntimeError("db down")

    monkeypatch.setattr(mobile_service, "get_maintenance", boom)

    assert await mobile_service.is_maintenance_enabled(db_session) is True
    assert _reset_maint_state == ["RuntimeError"]

    # 同一轮故障持续期间（缓存过期后再读失败）沿用上次结果，不重复告警
    _expire_cache()
    assert await mobile_service.is_maintenance_enabled(db_session) is True
    assert _reset_maint_state == ["RuntimeError"]


@pytest.mark.asyncio
@pytest.mark.parametrize("last_known", [True, False])
async def test_read_failure_reuses_last_known_value(db_session, monkeypatch, _reset_maint_state, last_known):
    mobile_service._maint_cache["value"] = last_known
    _expire_cache()

    async def boom(_db):
        raise TimeoutError("db timeout")

    monkeypatch.setattr(mobile_service, "get_maintenance", boom)

    assert await mobile_service.is_maintenance_enabled(db_session) is last_known
    assert _reset_maint_state == ["TimeoutError"]


@pytest.mark.asyncio
async def test_recovery_resets_degraded_alert(db_session, monkeypatch, _reset_maint_state):
    async def boom(_db):
        raise RuntimeError("db down")

    monkeypatch.setattr(mobile_service, "get_maintenance", boom)
    await mobile_service.is_maintenance_enabled(db_session)
    assert _reset_maint_state == ["RuntimeError"]

    async def recovered(_db):
        return {"enabled": False, "reason": None, "by": None, "at": None}

    monkeypatch.setattr(mobile_service, "get_maintenance", recovered)
    _expire_cache()
    assert await mobile_service.is_maintenance_enabled(db_session) is False
    assert _reset_maint_state == ["RuntimeError"]

    # 新一轮故障：沿用恢复后读到的 False，且重新告警一次
    monkeypatch.setattr(mobile_service, "get_maintenance", boom)
    _expire_cache()
    assert await mobile_service.is_maintenance_enabled(db_session) is False
    assert _reset_maint_state == ["RuntimeError", "RuntimeError"]


@pytest.mark.asyncio
async def test_scheduler_rejects_when_session_creation_fails(monkeypatch):
    from app.services import workflow_scheduler as ws

    class _BoomSession:
        async def __aenter__(self):
            raise RuntimeError("no db session")

        async def __aexit__(self, *exc_info):
            return False

    monkeypatch.setattr(ws, "AsyncSessionLocal", lambda: _BoomSession())

    with pytest.raises(ws.BizError) as exc_info:
        await ws.workflow_scheduler.trigger_workflow(date.today(), source="cron")

    assert exc_info.value.code == 409
    assert "维护" in exc_info.value.message
