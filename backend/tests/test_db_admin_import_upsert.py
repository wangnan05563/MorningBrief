"""FR-UX-102：导入 replace 不再整行删插 + 标准 CSV 解析 + dry-run 预览（ACC-UX-101 验收 3）。"""
import pytest
from sqlalchemy import select

from app.models.admin_user import AdminUser
from app.services.db_admin_service import DbAdminService

REAL_HASH = "$2b$12$REALBCRYPTHASHNOTMASKVALUE"


@pytest.fixture(autouse=True)
async def seeded(db_session):
    db_session.add(
        AdminUser(id=901, username="ux102", password_hash=REAL_HASH, role="admin", nickname="old")
    )
    await db_session.commit()
    yield


async def _user(db_session, uid=901):
    return (await db_session.execute(select(AdminUser).filter_by(id=uid))).scalar_one()


async def test_replace_import_keeps_unsubmitted_columns(db_session):
    """只带 id + nickname 的 replace 导入，不能把未提交的 password_hash 置空。"""
    svc = DbAdminService(db_session)
    result = await svc.import_rows("admin_user", [{"id": 901, "nickname": "new"}], "replace")
    await db_session.commit()
    assert not result["errors"], result["errors"]
    assert result["updated"] == 1
    assert result["inserted"] == 0
    user = await _user(db_session)
    await db_session.refresh(user)
    assert user.password_hash == REAL_HASH
    assert user.nickname == "new"
    assert user.username == "ux102"


async def test_replace_import_rejects_mask_sentinel(db_session):
    """导入内容里的脱敏占位值同样被拒绝，不会覆盖真实凭据。"""
    svc = DbAdminService(db_session)
    result = await svc.import_rows(
        "admin_user", [{"id": 901, "password_hash": "***"}], "replace"
    )
    await db_session.commit()
    assert result["skipped"] == 1
    assert "敏感字段" in result["errors"][0]["error"]
    user = await _user(db_session)
    assert user.password_hash == REAL_HASH


async def test_replace_import_requires_primary_key(db_session):
    svc = DbAdminService(db_session)
    result = await svc.import_rows("admin_user", [{"nickname": "no-pk"}], "replace")
    assert result["skipped"] == 1
    assert "主键列" in result["errors"][0]["error"]


async def test_preview_counts_without_writing(db_session):
    svc = DbAdminService(db_session)
    preview = await svc.preview_import(
        "admin_user",
        [{"id": 901, "nickname": "a"}, {"id": 902, "nickname": "b"}],
        "replace",
    )
    assert preview["to_update"] == 1
    assert preview["to_insert"] == 1
    assert preview["conflicts"] == 1
    await db_session.commit()
    others = (await db_session.execute(select(AdminUser).filter_by(id=902))).scalar()
    assert others is None


async def test_parse_csv_handles_quotes_crlf_bom():
    raw = "\ufeffid,nickname,remark\n901,\"张,三\",\"line1\r\nline2\"\n"
    rows = DbAdminService.parse_import_payload(raw, "csv")
    assert rows == [{"id": "901", "nickname": "张,三", "remark": "line1\r\nline2"}]


async def test_parse_csv_skips_blank_lines():
    rows = DbAdminService.parse_import_payload("id,nickname\n901,a\n\n", "csv")
    assert len(rows) == 1


async def test_parse_json_requires_array():
    with pytest.raises(Exception):
        DbAdminService.parse_import_payload('{"id": 1}', "json")


def test_import_preview_endpoint(client, admin_token):
    """INT-UX-02：dry-run 预览接口只读，返回预计新增/更新行数。"""
    resp = client.post(
        "/admin/api/v1/db-admin/tables/admin_user/import/preview",
        headers={"Authorization": f"Bearer {admin_token['token']}"},
        json={"content": "id,nickname\n901,a\n902,b\n", "format": "csv", "mode": "replace"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["to_update"] == 1
    assert data["to_insert"] == 1
    assert data["conflicts"] == 1
