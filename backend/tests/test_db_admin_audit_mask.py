"""FR-UX-103：审计日志脱敏 + 危险操作确认不再依赖前端内置令牌（ACC-UX-101 验收 4）。"""
import json

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.routers.admin import db_admin as db_router
from app.services.db_admin_service import DbAdminService, _mask_audit_detail

SECRET = "sk-REDACT-ME-1234567890"


def test_mask_audit_detail_covers_column_and_key_semantics():
    detail = {
        "pk": 7,
        "values": {"password_hash": SECRET, "username": "admin", "remark": "ok"},
        "notify": {"access_token": SECRET},
    }
    masked = _mask_audit_detail(detail, "admin_user")
    assert masked["values"]["password_hash"] == "***"
    assert masked["values"]["username"] == "admin"
    assert masked["notify"]["access_token"] == "***"
    assert SECRET not in json.dumps(masked, ensure_ascii=False)


def test_mask_audit_detail_uses_row_level_ai_config_sensitivity():
    secret_row = {"config_key": "openai_api_key", "config_value": SECRET}
    plain_row = {"config_key": "default_model", "config_value": "gpt-4o"}
    assert _mask_audit_detail({"values": secret_row}, "ai_config")["values"]["config_value"] == "***"
    assert _mask_audit_detail({"values": plain_row}, "ai_config")["values"]["config_value"] == "gpt-4o"


async def test_write_audit_persists_masked_values(db_session):
    svc = DbAdminService(db_session)
    await svc.write_audit(
        action="update",
        target="admin_user",
        operator="tester",
        detail={"pk": "1", "values": {"password_hash": SECRET}},
    )
    await db_session.commit()
    log = (
        await db_session.execute(select(AuditLog).filter_by(action="update"))
    ).scalar_one()
    assert SECRET not in (log.detail or "")
    assert json.loads(log.detail)["values"]["password_hash"] == "***"


async def test_update_row_audit_masks_real_secret(db_session, monkeypatch):
    """走完整写入链路：真实密钥保存后，审计里只能看到 ***。"""
    from app.models.admin_user import AdminUser

    db_session.add(AdminUser(id=931, username="ux103", password_hash="INIT", role="admin"))
    await db_session.commit()
    svc = DbAdminService(db_session)
    await svc.update_row("admin_user", "931", {"password_hash": SECRET})
    await svc.write_audit(
        action="update",
        target="admin_user",
        operator="ux103",
        detail={"pk": "931", "values": {"password_hash": SECRET}},
    )
    await db_session.commit()
    logs = (
        await db_session.execute(select(AuditLog).filter_by(target="admin_user"))
    ).scalars().all()
    assert logs
    for log in logs:
        assert SECRET not in (log.detail or "")


def test_mask_audit_detail_ai_config_fail_safe_without_key():
    """只提交 config_value 时拿不到 config_key 语义，按明文密钥处理。"""
    detail = {"pk": "1", "values": {"config_value": SECRET}}
    assert _mask_audit_detail(detail, "ai_config")["values"]["config_value"] == "***"


def test_mask_audit_detail_covers_import_rows():
    detail = {
        "mode": "replace",
        "total": 1,
        "result": {"rows": [{"id": 1, "api_key": SECRET, "name": "ok"}]},
    }
    masked = _mask_audit_detail(detail, "ai_config")
    assert masked["result"]["rows"][0]["api_key"] == "***"
    assert SECRET not in json.dumps(masked, ensure_ascii=False)


async def test_list_audit_logs_masks_legacy_plaintext(db_session):
    """修复前写入的历史明文行，读取时也不能再透出密钥。"""
    from sqlalchemy import text

    legacy = json.dumps({"pk": "1", "values": {"password_hash": SECRET}}, ensure_ascii=False)
    await db_session.execute(
        text(
            "INSERT INTO audit_log (category, action, target, operator, detail, created_at) "
            "VALUES ('db_admin', 'update', 'admin_user', 'legacy', :detail, '2026-01-01 00:00:00')"
        ),
        {"detail": legacy},
    )
    await db_session.commit()
    logs = await DbAdminService(db_session).list_audit_logs(10)
    assert SECRET not in json.dumps(logs, ensure_ascii=False)
    assert logs[0]["detail"]["values"]["password_hash"] == "***"


def test_mask_sensitive_shares_row_level_judgment():
    """重构后读取脱敏与写回守卫、审计脱敏口径一致（列表行仍打码）。"""
    from app.services.db_admin_service import _mask_sensitive

    assert _mask_sensitive("admin_user", {"username": "a", "password_hash": "hash"})["password_hash"] == "***"
    assert _mask_sensitive("ai_config", {"config_key": "api_key", "config_value": SECRET})["config_value"] == "***"
    assert _mask_sensitive("ai_config", {"config_key": "default_model", "config_value": "gpt"})["config_value"] == "gpt"


def test_danger_op_confirms_by_text_not_embedded_token(client, admin_token, monkeypatch):
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    url = "/admin/api/v1/db-admin/tables/admin_user/rows/1"

    monkeypatch.setattr(db_router, "CONFIRM_TOKEN", "")
    forbidden = client.delete(url, params={"confirm_text": "admin_user"}, headers=headers)
    assert "DB_ADMIN_CONFIRM_TOKEN" in forbidden.text

    monkeypatch.setattr(db_router, "CONFIRM_TOKEN", "server-side-only-secret")
    mismatch = client.delete(url, params={"confirm_text": "wrong_table"}, headers=headers)
    assert "确认文本不匹配" in mismatch.text
    assert "server-side-only-secret" not in mismatch.text
