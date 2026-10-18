"""T02489 / FR-UX-201 应急停服幂等（后端侧）。

覆盖 PRD 中「停服动作幂等（已停服时不再重复写审计）」这一条：
- 首次停服 → 写标志 + 1 条审计
- 已停服时重复调用 → 不新增审计、不覆盖首次停服时间与原因，返回 already=True
- 恢复后再次停服 → 是新一轮停服，正常追加审计
- 路由层：强制原因、重复停服的信封、维护态查询结构
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.services import mobile_service


ADMIN = SimpleNamespace(username="admin")


@pytest.fixture(autouse=True)
def _reset_maint_cache():
    """模块级缓存跨测试会残留（TTL 5s），每条用例前后清零保证隔离。"""
    mobile_service._maint_cache["value"] = None
    mobile_service._maint_cache["ts"] = 0.0
    yield
    mobile_service._maint_cache["value"] = None
    mobile_service._maint_cache["ts"] = 0.0


async def _stop_rows(db):
    return (
        (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.category == "mobile", AuditLog.action == "emergency_stop"
                )
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_first_stop_writes_flag_and_one_audit(db_session):
    result = await mobile_service.emergency_stop(db_session, ADMIN, "上游 TTS 全部超时")
    await db_session.commit()

    assert result["enabled"] is True
    assert result["already"] is False
    assert result["reason"] == "上游 TTS 全部超时"
    assert result["at"]
    assert len(await _stop_rows(db_session)) == 1


@pytest.mark.asyncio
async def test_repeat_stop_is_idempotent(db_session):
    first = await mobile_service.emergency_stop(db_session, ADMIN, "第一次原因")
    await db_session.commit()

    second = await mobile_service.emergency_stop(db_session, ADMIN, "第二次原因（重复点击）")
    await db_session.commit()

    rows = await _stop_rows(db_session)
    assert len(rows) == 1, "已停服时重复停服不得再写审计"
    # 首次停服时间与原因不能被第二次调用覆盖（否则倒计时/追责起点会漂）
    assert second["already"] is True
    assert second["at"] == first["at"]
    assert second["reason"] == "第一次原因"


@pytest.mark.asyncio
async def test_repeat_stop_keeps_guard_active(db_session):
    await mobile_service.emergency_stop(db_session, ADMIN, "首次")
    await mobile_service.emergency_stop(db_session, ADMIN, "重复")

    assert await mobile_service.is_maintenance_enabled(db_session) is True


@pytest.mark.asyncio
async def test_stop_after_resume_is_a_new_stop(db_session):
    await mobile_service.emergency_stop(db_session, ADMIN, "第一轮")
    await mobile_service.resume_maintenance(db_session, ADMIN)
    await db_session.commit()

    result = await mobile_service.emergency_stop(db_session, ADMIN, "第二轮")
    await db_session.commit()

    assert result["already"] is False
    assert result["reason"] == "第二轮"
    assert len(await _stop_rows(db_session)) == 2


# ---- 路由层 ----

BASE = "/admin/api/v1/m"


def _headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def test_router_stop_requires_reason(client, admin_token):
    resp = client.post(f"{BASE}/emergency/stop", json={"reason": "   "}, headers=_headers(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] != 0
    assert "原因" in body["message"]


def test_router_second_stop_reports_already(client, admin_token):
    first = client.post(f"{BASE}/emergency/stop", json={"reason": "故障"}, headers=_headers(admin_token))
    assert first.json()["data"]["already"] is False

    second = client.post(f"{BASE}/emergency/stop", json={"reason": "故障"}, headers=_headers(admin_token))
    assert second.json()["data"]["already"] is True


def test_router_maintenance_status_shape(client, admin_token):
    empty = client.get(f"{BASE}/maintenance-status", headers=_headers(admin_token)).json()["data"]
    assert empty == {"enabled": False, "reason": None, "by": None, "at": None}

    client.post(f"{BASE}/emergency/stop", json={"reason": "磁盘写满"}, headers=_headers(admin_token))
    data = client.get(f"{BASE}/maintenance-status", headers=_headers(admin_token)).json()["data"]
    assert data["enabled"] is True
    assert data["reason"] == "磁盘写满"
    assert data["by"] == "admin"
    assert data["at"], "前端倒计时依赖 at，缺失则无法计时"


def test_router_requires_auth(client):
    assert client.get(f"{BASE}/maintenance-status").status_code in (401, 403)
