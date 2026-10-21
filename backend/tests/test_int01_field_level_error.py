"""INT-UX-01：敏感列哨兵被拒时，接口要返回「字段级」错误，而不是一段只有人能读的文本。

服务层的拒绝（T02519 / FR-UX-101）已有测试覆盖，但那几条断的是
`"敏感字段" in str(exc.message)`——一段人读文本。运营端拿到它只能弹一句 toast，
仍然不知道该把哪个输入框清空。本文件从 HTTP 边界断言响应体里能定位到具体字段。
"""
import pytest
from sqlalchemy import select

from app.models.admin_user import AdminUser
from app.models.ai_config import AIConfig

REAL_HASH = "$2b$12$REALBCRYPTHASHNOTMASKVALUE"
BASE = "/admin/api/v1/db-admin/tables"


@pytest.fixture(autouse=True)
async def seeded(db_session):
    db_session.add(
        AdminUser(username="int01", password_hash=REAL_HASH, role="admin", nickname="old")
    )
    db_session.add(AIConfig(config_key="openai_api_key", config_value="SK-REAL-VALUE"))
    db_session.add(AIConfig(config_key="default_model", config_value="gpt-4o"))
    await db_session.commit()


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


async def _row_id(db_session, model, **filter_kwargs) -> str:
    row = (await db_session.execute(select(model).filter_by(**filter_kwargs))).scalar_one()
    return str(row.id)


def _field_names(payload) -> list[str]:
    """从响应 data 里取被拒字段名列表（契约：data.errors[].field）。"""
    assert isinstance(payload, dict), f"被拒时 data 应为对象，实际 {payload!r}"
    errors = payload.get("errors")
    assert isinstance(errors, list) and errors, f"data.errors 应是非空列表，实际 {payload!r}"
    return [e["field"] for e in errors]


async def test_patch_sentinel_names_the_offending_field(client, auth, db_session):
    """改密钥行时回传 *** → 响应必须点出 config_value 这个字段。"""
    pk = await _row_id(db_session, AIConfig, config_key="openai_api_key")
    resp = client.patch(f"{BASE}/ai_config/rows/{pk}", json={"values": {"config_value": "***"}}, headers=auth)
    body = resp.json()
    assert body["code"] == 400
    assert _field_names(body["data"]) == ["config_value"]


async def test_patch_error_is_machine_readable_per_field(client, auth, db_session):
    """每个被拒字段自带可展示的说明，前端不必再去切整句中文。"""
    pk = await _row_id(db_session, AIConfig, config_key="openai_api_key")
    resp = client.patch(f"{BASE}/ai_config/rows/{pk}", json={"values": {"config_value": "*** "}}, headers=auth)
    entry = resp.json()["data"]["errors"][0]
    assert entry["field"] == "config_value"
    assert isinstance(entry["message"], str) and "config_value" in entry["message"]
    assert resp.json()["message"]  # 聚合消息仍保留，toast 照旧可用


async def test_mixed_payload_only_lists_sensitive_fields(client, auth, db_session):
    """混合提交时字段列表只能有敏感列：同一次 PUT 里的 config_key 正常字段不该被牵连。

    注：本项目 schema 下没有同时含两个敏感列的表（SENSITIVE_COLUMNS 只有
    password_hash / token / secret，实际模型里只有 admin_user.password_hash
    落地，再加 ai_config.config_value 这一条件敏感列），所以「多个被拒字段全列出」
    这条改由「列表不多报、不少报」的可达路径来断。
    """
    pk = await _row_id(db_session, AIConfig, config_key="openai_api_key")
    resp = client.patch(
        f"{BASE}/ai_config/rows/{pk}",
        json={"values": {"config_key": "openai_api_key_v2", "config_value": "***"}},
        headers=auth,
    )
    assert resp.json()["code"] == 400
    assert _field_names(resp.json()["data"]) == ["config_value"]


async def test_create_sentinel_names_the_offending_field(client, auth):
    """新增行同样走字段级错误（同一契约，别只修 PATCH）。"""
    resp = client.post(
        f"{BASE}/ai_config/rows",
        json={"values": {"config_key": "deepseek_api_key", "config_value": "***"}},
        headers=auth,
    )
    body = resp.json()
    assert body["code"] == 400
    assert _field_names(body["data"]) == ["config_value"]


async def test_non_sensitive_writeback_still_succeeds(client, auth, db_session):
    """加了字段级错误不能顺手把正常提交拦掉。"""
    pk = await _row_id(db_session, AIConfig, config_key="default_model")
    resp = client.patch(
        f"{BASE}/ai_config/rows/{pk}", json={"values": {"config_value": "gpt-4o-mini"}}, headers=auth
    )
    assert resp.json()["code"] == 0
    row = (await db_session.execute(select(AIConfig).filter_by(config_key="default_model"))).scalar_one()
    await db_session.refresh(row)
    assert row.config_value == "gpt-4o-mini"


async def test_rejection_does_not_touch_stored_credential(client, auth, db_session):
    """被拒就是被拒：库里的凭据逐字节不变（字段级错误不该改成「静默部分写入」）。"""
    pk = await _row_id(db_session, AIConfig, config_key="openai_api_key")
    client.patch(f"{BASE}/ai_config/rows/{pk}", json={"values": {"config_value": "***"}}, headers=auth)
    row = (await db_session.execute(select(AIConfig).filter_by(config_key="openai_api_key"))).scalar_one()
    await db_session.refresh(row)
    assert row.config_value == "SK-REAL-VALUE"
    assert "***" not in row.config_value
