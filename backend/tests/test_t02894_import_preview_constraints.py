"""T02894：导入 dry-run 必须预判 UNIQUE / CHECK / 外键类失败。

T02525 让预览覆盖了「多余列 / 缺 NOT NULL / 只给主键」三类分叉，但这三类只是
「真写之前就能从表结构看出来」的一部分；唯一约束、CHECK、外键仍要等真写才炸。
结果就是预览说「可写 N 行」、导入却报错 N 行——运营照着预览做决定时被误导。

本文件的口径与 INT-UX-02 一致：**预览报的错误行，必须与随后真实导入失败的行对上**。
"""
import pytest
from sqlalchemy import text

from app.models.admin_user import AdminUser
from app.models.ai_config import AIConfig
from app.routers.admin import db_admin as db_router

BASE = "/admin/api/v1/db-admin/tables"


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


@pytest.fixture(autouse=True)
def _server_confirm_token(monkeypatch):
    monkeypatch.setattr(db_router, "CONFIRM_TOKEN", "server-side-only-secret")


async def _preview(client, auth, table, rows, mode="insert"):
    return client.post(
        f"{BASE}/{table}/import/preview", json={"rows": rows, "mode": mode}, headers=auth
    ).json()


async def _apply(client, auth, table, rows, mode="insert"):
    return client.post(
        f"{BASE}/{table}/import",
        json={"rows": rows, "mode": mode, "confirm_text": "IMPORT"},
        headers=auth,
    ).json()


def _u(name: str) -> dict:
    return {"username": name, "password_hash": "x", "role": "operator"}


async def test_preview_counts_batch_duplicate_as_error_and_import_agrees(client, auth):
    """同批载荷内两条相同 username：第一条能进，第二条必炸，预览要报 1 错而不是 2 行可写。"""
    rows = [_u("t02894_dup"), _u("t02894_dup")]

    preview = (await _preview(client, auth, "admin_user", rows))["data"]
    assert preview["error_rows"] == 1, preview
    assert preview["to_insert"] == 1, preview
    assert "唯一约束" in preview["errors"][0]["error"], preview

    applied = (await _apply(client, auth, "admin_user", rows))["data"]
    assert applied["inserted"] == preview["to_insert"], (preview, applied)
    assert len(applied["errors"]) == preview["error_rows"], (preview, applied)


async def test_preview_sees_unique_conflict_with_existing_row(client, auth, db_session):
    db_session.add(AdminUser(username="t02894_taken", password_hash="x", role="operator"))
    await db_session.commit()

    rows = [_u("t02894_taken")]
    preview = (await _preview(client, auth, "admin_user", rows))["data"]
    assert preview["error_rows"] == 1 and preview["to_insert"] == 0, preview

    applied = (await _apply(client, auth, "admin_user", rows))["data"]
    assert applied["inserted"] == 0
    assert len(applied["errors"]) == 1, applied


async def test_preview_reports_check_violation(client, auth):
    """CHECK 是表结构里写死的枚举，预览必须能判，而不是等 INSERT 报约束失败。"""
    rows = [{"username": "t02894_bad_role", "password_hash": "x", "role": "root"}]

    preview = (await _preview(client, auth, "admin_user", rows))["data"]
    assert preview["error_rows"] == 1 and preview["to_insert"] == 0, preview
    assert "CHECK" in preview["errors"][0]["error"], preview

    applied = (await _apply(client, auth, "admin_user", rows))["data"]
    assert applied["inserted"] == 0
    assert len(applied["errors"]) == 1, applied


async def test_preview_reports_replace_update_unique_collision(client, auth, db_session):
    """replace 的 UPDATE 也会撞唯一键；预览不能因为「主键存在」就当成安全更新。"""
    a = AIConfig(config_key="t02894_k1", config_value="a")
    b = AIConfig(config_key="t02894_k2", config_value="b")
    db_session.add_all([a, b])
    await db_session.commit()

    rows = [{"id": a.id, "config_key": "t02894_k2"}]
    preview = (await _preview(client, auth, "ai_config", rows, mode="replace"))["data"]
    assert preview["error_rows"] == 1, preview
    assert preview["to_update"] == 0, preview
    assert "唯一约束" in preview["errors"][0]["error"], preview

    applied = (await _apply(client, auth, "ai_config", rows, mode="replace"))["data"]
    assert applied["updated"] == 0
    assert len(applied["errors"]) == 1, applied


async def test_preview_reports_foreign_key_violation_when_enforced(client, auth, db_session):
    """生产库 PRAGMA foreign_keys=ON（app/database.py）；开着的库上预览必须报外键缺父行。"""
    await db_session.execute(text("PRAGMA foreign_keys=ON"))
    await db_session.commit()

    rows = [{"workflow_id": "t02894_no_such_workflow", "step_name": "crawl"}]
    preview = (await _preview(client, auth, "workflow_step", rows))["data"]
    assert preview["error_rows"] == 1 and preview["to_insert"] == 0, preview
    assert "外键" in preview["errors"][0]["error"], preview

    applied = (await _apply(client, auth, "workflow_step", rows))["data"]
    assert applied["inserted"] == 0
    assert len(applied["errors"]) == 1, applied


async def test_preview_replace_same_unique_value_is_not_conflict(client, auth, db_session):
    """replace 更新未改唯一键时，不能把它判成「与库内重复」——那会逼运营删数据。"""
    row = AIConfig(config_key="t02894_self", config_value="old")
    db_session.add(row)
    await db_session.commit()

    rows = [{"id": row.id, "config_key": "t02894_self", "config_value": "new"}]
    preview = (await _preview(client, auth, "ai_config", rows, mode="replace"))["data"]
    assert preview["error_rows"] == 0 and preview["to_update"] == 1, preview

    applied = (await _apply(client, auth, "ai_config", rows, mode="replace"))["data"]
    assert applied["updated"] == 1 and applied["errors"] == [], applied


async def test_valid_rows_still_counted_as_writable(client, auth):
    """约束检查不能把干净行误判成错误：合法行照常算新增，真实导入也成功。"""
    rows = [_u("t02894_fresh_ok")]
    preview = (await _preview(client, auth, "admin_user", rows))["data"]
    assert preview["error_rows"] == 0 and preview["to_insert"] == 1, preview

    applied = (await _apply(client, auth, "admin_user", rows))["data"]
    assert applied["inserted"] == 1 and applied["errors"] == [], applied
