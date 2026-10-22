"""M16：清空文本字段后保存，库里必须真的被清空（FR-UX-101 脏字段提交的另一半）。

原实现 `update_row` 把「值等于空串」和「值等于 None」一起丢进丢弃分支，注释却写着
「显式 None 表示置空」——契约与实现矛盾。前端 `clearable` 输入框清空后交上来的就是
空串，于是这条 UPDATE 少了一个 SET 项，`affected` 照样返回 1，界面弹「更新成功」，
数据库还是旧值：置空在 UI 上永远做不到。

判据不能只看接口返回码——它一直是 0。全部断言落在库内实际值上。
"""
import pytest
from sqlalchemy import select

from app.models.admin_user import AdminUser
from app.models.ai_config import AIConfig
from app.services.db_admin_service import BizError, DbAdminService


async def _user(db_session):
    return (
        await db_session.execute(select(AdminUser).filter_by(username="m16"))
    ).scalar_one()


async def _config(db_session, key):
    return (
        await db_session.execute(select(AIConfig).filter_by(config_key=key))
    ).scalar_one()


@pytest.fixture(autouse=True)
async def seeded(db_session):
    db_session.add(
        AdminUser(username="m16", password_hash="$2b$12$REALHASHNOTEMPTYNOTMASK", nickname="旧昵称")
    )
    db_session.add(AIConfig(config_key="llm_timeout_sec", config_value="30"))
    await db_session.commit()


async def test_empty_string_clears_nullable_text_column(db_session):
    """把昵称清成空串：这是用户真实动作，必须落库，不能被当成「没填」。"""
    user = await _user(db_session)
    svc = DbAdminService(db_session)
    await svc.update_row("admin_user", str(user.id), {"nickname": ""})
    await db_session.commit()
    await db_session.refresh(user)
    assert user.nickname == "", f"清空被静默丢弃，库里仍是 {user.nickname!r}"


async def test_explicit_none_clears_column(db_session):
    """注释承诺的「显式 None 表示置空」现在也得兑现。"""
    user = await _user(db_session)
    svc = DbAdminService(db_session)
    await svc.update_row("admin_user", str(user.id), {"nickname": None})
    await db_session.commit()
    await db_session.refresh(user)
    assert user.nickname is None


async def test_non_secret_config_can_be_cleared(db_session):
    """非密钥配置项清空是常规运维动作（把超时改回默认即清空该覆盖项）。"""
    row = await _config(db_session, "llm_timeout_sec")
    svc = DbAdminService(db_session)
    await svc.update_row("ai_config", str(row.id), {"config_value": ""})
    await db_session.commit()
    await db_session.refresh(row)
    assert row.config_value == ""


async def test_changed_and_unchanged_fields_both_survive(db_session):
    """脏字段提交下，同一批里既要有被清空的列，也要有被改成新值的列。"""
    user = await _user(db_session)
    svc = DbAdminService(db_session)
    await svc.update_row("admin_user", str(user.id), {"nickname": "", "role": "operator"})
    await db_session.commit()
    await db_session.refresh(user)
    assert user.nickname == ""
    assert user.role == "operator"


async def test_no_valid_column_still_raises(db_session):
    """放开空串后不能把「全是无效列」的请求也放成成功：否则改不到还弹成功的老毛病换个形态回来。"""
    user = await _user(db_session)
    svc = DbAdminService(db_session)
    with pytest.raises(BizError) as exc:
        await svc.update_row("admin_user", str(user.id), {"not_a_column": "", "id": "9"})
    assert "无有效更新字段" in str(exc.value.message)


async def test_mask_sentinel_on_sensitive_column_is_still_rejected(db_session):
    """M14 的哨兵封锁不许因为这次放开空串而松动。"""
    user = await _user(db_session)
    svc = DbAdminService(db_session)
    with pytest.raises(BizError):
        await svc.update_row("admin_user", str(user.id), {"password_hash": "***"})
    await db_session.rollback()
    await db_session.refresh(user)
    assert user.password_hash == "$2b$12$REALHASHNOTEMPTYNOTMASK"


async def test_sending_no_value_for_sensitive_column_leaves_it_untouched(db_session):
    """清空别的列时，凭据列不在 payload 里就不该进 SET 子句。"""
    user = await _user(db_session)
    svc = DbAdminService(db_session)
    await svc.update_row("admin_user", str(user.id), {"nickname": ""})
    await db_session.commit()
    await db_session.refresh(user)
    assert user.password_hash == "$2b$12$REALHASHNOTEMPTYNOTMASK"
