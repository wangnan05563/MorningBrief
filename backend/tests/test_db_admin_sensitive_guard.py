"""FR-UX-101：敏感列禁止把脱敏哨兵值（***）回写入库（ACC-UX-101 验收 1/2）。"""
import pytest
from sqlalchemy import select

from app.models.admin_user import AdminUser
from app.models.ai_config import AIConfig
from app.services.db_admin_service import BizError, DbAdminService

REAL_HASH = "$2b$12$REALBCRYPTHASHNOTMASKVALUE"


async def _seed(db_session):
    db_session.add(
        AdminUser(username="ux101", password_hash=REAL_HASH, role="admin", nickname="old")
    )
    db_session.add(AIConfig(config_key="openai_api_key", config_value="SK-REAL-VALUE"))
    db_session.add(AIConfig(config_key="default_model", config_value="gpt-4o"))
    await db_session.commit()


async def _admin_user(db_session):
    return (await db_session.execute(select(AdminUser).filter_by(username="ux101"))).scalar_one()


async def _ai_config(db_session, key):
    return (await db_session.execute(select(AIConfig).filter_by(config_key=key))).scalar_one()


@pytest.fixture(autouse=True)
async def seeded(db_session):
    await _seed(db_session)
    yield


async def test_mask_sentinel_on_sensitive_column_is_rejected(db_session):
    """直接回传列表页看到的 *** 应被拒绝，且原凭据保持不变。"""
    user = await _admin_user(db_session)
    svc = DbAdminService(db_session)
    with pytest.raises(BizError) as exc:
        await svc.update_row("admin_user", str(user.id), {"password_hash": "***"})
    assert "敏感字段" in str(exc.value.message)
    await db_session.rollback()
    await db_session.refresh(user)
    assert user.password_hash == REAL_HASH


async def test_only_dirty_field_update_keeps_password_hash(db_session):
    """只改非敏感字段（脏字段提交）时，password_hash 逐字节不变。"""
    user = await _admin_user(db_session)
    svc = DbAdminService(db_session)
    await svc.update_row("admin_user", str(user.id), {"nickname": "new"})
    await db_session.commit()
    await db_session.refresh(user)
    assert user.password_hash == REAL_HASH
    assert user.nickname == "new"


async def test_ai_config_secret_row_mask_rejected(db_session):
    """密钥行（config_key 含 key）的 config_value 传脱敏值应被拒绝。"""
    row = await _ai_config(db_session, "openai_api_key")
    svc = DbAdminService(db_session)
    with pytest.raises(BizError):
        await svc.update_row("ai_config", str(row.id), {"config_value": "***"})
    await db_session.rollback()
    await db_session.refresh(row)
    assert row.config_value == "SK-REAL-VALUE"


async def test_ai_config_non_secret_row_still_writable(db_session):
    """非密钥行的 config_value 不受按列一刀切的封锁。"""
    row = await _ai_config(db_session, "default_model")
    svc = DbAdminService(db_session)
    await svc.update_row("ai_config", str(row.id), {"config_value": "gpt-4o-mini"})
    await db_session.commit()
    await db_session.refresh(row)
    assert row.config_value == "gpt-4o-mini"


async def test_create_row_with_mask_sentinel_rejected(db_session):
    """新增时把脱敏占位值当真实凭据写入同样被拒绝。"""
    svc = DbAdminService(db_session)
    with pytest.raises(BizError):
        await svc.create_row("ai_config", {"config_key": "deepseek_api_key", "config_value": "***"})
