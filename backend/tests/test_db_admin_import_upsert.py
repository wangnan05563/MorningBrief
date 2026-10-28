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
    """INT-UX-02：预览按「这行真能写进去吗」计数。

    原先这里断言 `{"id": 902, "nickname": "b"}` 算一次新增，而实测同一条载荷
    走真实导入是 `inserted=0, skipped=1, NOT NULL constraint failed: admin_user.username`
    ——预览报的行数比实际多，正是 dry-run 最该避免的误导。
    """
    svc = DbAdminService(db_session)
    preview = await svc.preview_import(
        "admin_user",
        [
            {"id": 901, "nickname": "a"},  # 命中已有主键 → 走 UPDATE，缺必填列不影响
            {"id": 902, "nickname": "b"},  # 新行缺 username/password_hash/role → 拦下
        ],
        "replace",
    )
    assert preview["to_update"] == 1
    assert preview["to_insert"] == 0
    assert preview["conflicts"] == 1
    assert preview["error_rows"] == 1
    assert "username" in preview["errors"][0]["error"]
    await db_session.commit()
    others = (await db_session.execute(select(AdminUser).filter_by(id=902))).scalar()
    assert others is None


async def test_preview_counts_complete_new_row_as_insert(db_session):
    """把必填列带齐，同一行就恢复成一次新增——拦截是按缺失判定的，不是一刀切。"""
    svc = DbAdminService(db_session)
    preview = await svc.preview_import(
        "admin_user",
        [{"id": 902, "username": "u902", "password_hash": REAL_HASH, "role": "operator"}],
        "replace",
    )
    assert (preview["to_insert"], preview["error_rows"]) == (1, 0)
    result = await svc.import_rows(
        "admin_user",
        [{"id": 902, "username": "u902", "password_hash": REAL_HASH, "role": "operator"}],
        "replace",
    )
    assert result["inserted"] == preview["to_insert"]


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
    """INT-UX-02：dry-run 预览接口只读，返回预计新增/更新行数。

    载荷把必填列带齐（原先只带 id+nickname 的新行其实写不进去，
    预览却按新增计数——见 test_preview_counts_without_writing）。
    """
    resp = client.post(
        "/admin/api/v1/db-admin/tables/admin_user/import/preview",
        headers={"Authorization": f"Bearer {admin_token['token']}"},
        json={
            "content": (
                "id,username,password_hash,role,nickname\n"
                f"901,ux102,{REAL_HASH},admin,a\n"
                f"902,u902,{REAL_HASH},operator,b\n"
            ),
            "format": "csv",
            "mode": "replace",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["to_update"] == 1
    assert data["to_insert"] == 1
    assert data["conflicts"] == 1
    assert data["error_rows"] == 0


# ---------------------------------------------------------------- T03603 计数口径


async def test_import_counts_each_failed_row_once(db_session):
    """T03603：真实导入里 skipped 已包含错误行，前端不得再叠加 errors.length。

    原先 1 行哨兵被拒时 skipped=1 且 errors 长度 1，前端 ``skipped + errors.length``
    算成「未写入 2 行」，与概览面板的「未写入 1 行」同屏矛盾。
    """
    svc = DbAdminService(db_session)
    result = await svc.import_rows("admin_user", [{"id": 901, "password_hash": "***"}], "replace")
    assert (result["inserted"], result["updated"]) == (0, 0)
    assert result["skipped"] == 1
    assert len(result["errors"]) == 1
    assert result["skipped"] == len(result["errors"]), "skipped 与逐行原因必须一一对应"


async def test_import_unknown_only_row_keeps_a_reason(db_session):
    """整行都没有可识别列时，不能只是 skipped+1 而查不到原因。"""
    svc = DbAdminService(db_session)
    result = await svc.import_rows("admin_user", [{"nope": "x"}], "insert")
    assert result["skipped"] == 1
    assert len(result["errors"]) == 1
    assert "没有匹配当前表的列" in result["errors"][0]["error"]


async def test_preview_buckets_sum_to_total(db_session):
    """T03603：新增+更新+错误 == 总数；「冲突」是子集，不参与相加。

    replace 下命中已有主键的行既算 to_update 又曾算 conflicts，四个数字相加 2 > 总行数 1。
    """
    svc = DbAdminService(db_session)
    replace_preview = await svc.preview_import(
        "admin_user",
        [
            {"id": 901, "nickname": "a"},
            {"id": 902, "username": "u902", "password_hash": REAL_HASH, "role": "operator"},
        ],
        "replace",
    )
    assert replace_preview["total"] == 2
    assert (
        replace_preview["to_insert"] + replace_preview["to_update"] + replace_preview["error_rows"]
        == replace_preview["total"]
    )
    assert replace_preview["conflicts"] == 1, "冲突只标记「主键已存在」，不是独立分桶"

    insert_preview = await svc.preview_import(
        "admin_user",
        [
            {"id": 901, "username": "x", "password_hash": REAL_HASH, "role": "admin"},
            {"nope": "x"},
        ],
        "insert",
    )
    assert insert_preview["total"] == 2
    assert (
        insert_preview["to_insert"] + insert_preview["to_update"] + insert_preview["error_rows"]
        == insert_preview["total"]
    )
    assert insert_preview["conflicts"] == 1
