"""T03321：审计 reason 字段补齐。

三件事各自有牙齿：
1. `audit_detail` 保证 detail 里永远有 reason 键（空串也要在），
   机器触发走固定来源说明，显式 reason 优先；
2. AST 门禁能对「缺 reason」「死豁免」「action 不可静态解析」三种情况判红，
   而不是只在当前仓库恰好干净时才绿；
3. 真实端点把请求体里的 reason 一路写进 audit_log 的 detail。
"""
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.audit_reason import NO_REASON_REQUIRED, audit_detail
from app.models.audit_log import AuditLog

BACKEND = Path(__file__).resolve().parents[1]
_GATE_PATH = BACKEND / "scripts" / "check_audit_reason.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_audit_reason", _GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


# ---- audit_detail ----


def test_reason_key_always_present_even_when_empty():
    assert json.loads(audit_detail({"a": 1})) == {"a": 1, "reason": ""}


def test_reason_payload_is_not_mutated():
    payload = {"a": 1}
    audit_detail(payload, reason="x")
    assert payload == {"a": 1}


def test_explicit_reason_is_kept_verbatim():
    assert json.loads(audit_detail({}, reason="  重复触发，人工核对  "))["reason"] == "重复触发，人工核对"


def test_machine_provenance_when_no_human_reason():
    detail = json.loads(audit_detail({}, machine="定时任务"))
    assert detail["reason"] == "系统自动触发：定时任务"


def test_explicit_reason_beats_machine():
    assert json.loads(audit_detail({}, reason="运营填的", machine="定时任务"))["reason"] == "运营填的"


def test_chinese_is_not_escaped():
    assert "内容合规" in audit_detail({}, reason="内容合规")


def test_non_serializable_falls_back_to_str():
    detail = json.loads(audit_detail({"at": {1, 2}}, reason="r"))
    assert detail["reason"] == "r"
    assert isinstance(detail["at"], str)


# ---- 门禁 ----


def _sites(source: str, relpath: str = "backend/app/routers/admin/demo.py"):
    return gate.collect_from_source(source, relpath)


def test_gate_flags_missing_reason():
    sites = _sites(
        "from app.models.audit_log import AuditLog\n"
        "AuditLog(category='x', action='delete', detail=json.dumps({'id': 1}))\n"
    )
    assert sites[0]["has_reason"] is False
    assert sites[0]["exempt"] is False


def test_gate_flags_write_point_without_detail():
    """连 detail 都没给的写入点，读口永远看不到原因——必须算缺，不能算「不适用」。

    补这条用例是因为变异探针发现：把 `detail is None → False` 翻成 True，
    原有 20 条用例全都不会红（L5 腿）。分支本身是对的，只是没有牙齿盯着它。
    """
    sites = _sites(
        "from app.models.audit_log import AuditLog\n"
        "AuditLog(category='x', action='delete')\n"
    )
    assert sites[0]["has_reason"] is False
    _, missing, _ = gate.report(sites)
    assert len(missing) == 1


def test_gate_accepts_audit_detail():
    sites = _sites(
        "from app.models.audit_log import AuditLog\n"
        "from app.core.audit_reason import audit_detail\n"
        "AuditLog(category='x', action='delete', detail=audit_detail({'id': 1}, reason=r))\n"
    )
    assert sites[0]["has_reason"] is True


def test_gate_accepts_legacy_json_reason():
    sites = _sites(
        "from app.models.audit_log import AuditLog\n"
        "AuditLog(category='x', action='delete', detail=json.dumps({'reason': r}))\n"
    )
    assert sites[0]["has_reason"] is True


def test_gate_exempts_registered_action():
    file_key, action = next(iter(NO_REASON_REQUIRED))
    sites = _sites(
        "from app.models.audit_log import AuditLog\n"
        f"AuditLog(category='x', action='{action}', detail={{}})\n",
        relpath=f"backend/app/{file_key}",
    )
    assert sites[0]["exempt"] is True


def test_gate_fails_closed_on_unresolvable_action():
    """包装函数把 action 当参数透传时，不能证明豁免，必须按口径内处理。"""
    sites = _sites(
        "from app.models.audit_log import AuditLog\n"
        "def _audit(action, detail):\n"
        "    AuditLog(category='x', action=action, detail=detail)\n"
    )
    assert sites[0]["action"] is None
    assert sites[0]["exempt"] is False
    _, missing, _ = gate.report(sites)
    assert len(missing) == 1


def test_gate_reports_dead_exemption():
    file_key, action = next(iter(NO_REASON_REQUIRED))
    sites = _sites(
        "from app.models.audit_log import AuditLog\n"
        "AuditLog(category='x', action='something_else', detail={})\n",
        relpath=f"backend/app/{file_key}",
    )
    _, missing, unused = gate.report(sites)
    assert (file_key, action) in unused


def test_gate_on_repo_is_clean():
    text, missing, unused = gate.report(gate.scan())
    assert missing == [], text
    assert unused == [], text
    assert "缺 reason: 0" in text


# ---- 端点级：请求体 reason 落进 detail ----


async def test_db_admin_create_row_persists_reason(client, db_session, admin_token):
    resp = client.post(
        "/admin/api/v1/db-admin/tables/admin_user/rows",
        json={
            "values": {"id": 933, "username": "t03321", "password_hash": "HASH", "role": "operator"},
            "reason": "补录历史运营账号",
        },
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    assert resp.status_code == 200, resp.text

    log = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.category == "db_admin", AuditLog.action == "create"
            )
        )
    ).scalar_one()
    detail = json.loads(log.detail)
    assert detail["reason"] == "补录历史运营账号"
    assert detail["id"] == 933


async def test_db_admin_reason_defaults_to_empty(client, db_session, admin_token):
    resp = client.post(
        "/admin/api/v1/db-admin/tables/admin_user/rows",
        json={"values": {"id": 934, "username": "t03321b", "password_hash": "HASH", "role": "operator"}},
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    assert resp.status_code == 200, resp.text

    log = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.category == "db_admin", AuditLog.action == "create"
            )
        )
    ).scalar_one()
    # 既有调用方不传 reason 也不能 422，detail 里补空串而不是缺键
    assert json.loads(log.detail)["reason"] == ""


@pytest.mark.parametrize("model_name", ["RowCreateRequest", "RowUpdateRequest", "BatchDeleteRequest", "ImportRequest"])
def test_request_models_accept_optional_reason(model_name):
    from app.routers.admin import db_admin

    model = getattr(db_admin, model_name)
    assert model.model_fields["reason"].default == ""
    assert not model.model_fields["reason"].is_required()
