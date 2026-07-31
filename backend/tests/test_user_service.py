"""用户服务测试。

覆盖 services/user_service.py：
- login_by_code：新用户登录创建记录；老用户登录更新信息
- logout：登出后 jti 写入 SQLite jwt_blacklist 表
- get_user_info：查询用户信息返回正确数据

微信 API 调用通过 mock httpx.AsyncClient.get 模拟，避免真实外部依赖。
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.exceptions import AuthError, BizError
from app.models import User
from app.models.jwt_blacklist import JwtBlacklist
from app.services.user_service import UserService


def _mock_wx_response(openid: str = "wx-openid-001", unionid: str = None):
    """构造 mock httpx.Response 对象。

    用 MagicMock 而非 AsyncMock：httpx.Response.json() 是同步方法，
    用 AsyncMock 会让 json() 返回协程，导致后续 data.get() 失败。
    """
    resp = MagicMock()
    resp.json.return_value = {
        "errcode": 0,
        "openid": openid,
        "unionid": unionid,
    }
    return resp


class _FakeSessionCtx:
    """适配 `async with AsyncSessionLocal() as session` 调用模式。

    blacklist_service.add_to_blacklist 内部用全局 AsyncSessionLocal 创建独立
    session 写 SQLite，而测试用的是内存 engine 的 db_session。要让 logout 测试
    能用 db_session 查到黑名单记录，必须把 AsyncSessionLocal 替换为返回 db_session
    的上下文管理器，让 add_to_blacklist 写到测试 engine 中。
    """

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_login_by_code_new_user(db_session):
    """新用户首次登录：自动创建 User 记录，返回 token 与用户信息。"""
    svc = UserService(db_session)

    # 用 MagicMock 而非 AsyncMock 作为 client：AsyncMock 会让所有属性变异步，
    # 导致 resp.json() 返回协程而非 dict。MagicMock 的 json() 保持同步。
    # 仅 __aenter__/__aexit__/get 需要 AsyncMock（异步方法）
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=_mock_wx_response())
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await svc.login_by_code("valid-code")

    # 返回结构完整
    assert "token" in result
    assert "expires_in" in result
    assert result["expires_in"] > 0
    assert result["user"]["openid"] == "wx-openid-001"

    # DB 中应有一条用户记录
    res = await db_session.execute(select(User).where(User.openid == "wx-openid-001"))
    user = res.scalar_one_or_none()
    assert user is not None
    assert user.id is not None


@pytest.mark.asyncio
async def test_login_by_code_existing_user(db_session):
    """老用户再次登录：复用已有记录，不新建。"""
    # 预置一个老用户
    existing = User(openid="wx-old-001", nickname="old-name")
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)
    old_id = existing.id

    svc = UserService(db_session)
    # 同 test_login_by_code_new_user：MagicMock client + AsyncMock get/__aenter__
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=_mock_wx_response(openid="wx-old-001"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await svc.login_by_code("any-code")

    # 复用同一用户，未新建
    res = await db_session.execute(select(User).where(User.openid == "wx-old-001"))
    user = res.scalar_one_or_none()
    assert user.id == old_id

    # 全表只有 1 条记录
    res_all = await db_session.execute(select(User))
    assert len(res_all.scalars().all()) == 1


@pytest.mark.asyncio
async def test_login_by_code_empty_code_raises(db_session):
    """空 code 应抛 BizError，不调用微信 API。"""
    svc = UserService(db_session)
    with pytest.raises(BizError) as exc_info:
        await svc.login_by_code("")
    assert exc_info.value.code == 400


@pytest.mark.asyncio
async def test_login_by_code_wx_error_raises(db_session):
    """微信返回 errcode != 0 时抛 BizError。"""
    resp = MagicMock()
    resp.json.return_value = {"errcode": 40029, "errmsg": "invalid code"}

    svc = UserService(db_session)
    # 同 test_login_by_code_new_user：MagicMock client + AsyncMock get/__aenter__
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(BizError) as exc_info:
            await svc.login_by_code("bad-code")
    assert "微信登录失败" in exc_info.value.message


@pytest.mark.asyncio
async def test_logout_adds_to_blacklist(db_session, monkeypatch):
    """登出后 jti 应写入 SQLite jwt_blacklist 表。

    logout 内部调用 blacklist_service.add_to_blacklist，该函数：
    1. 用全局 AsyncSessionLocal() 创建独立 session 写 SQLite —— 必须替换为
       返回 db_session 的 ctx，让记录写到测试 engine 中
    2. 调用 cos_client.put_object 写 COS —— 替换为 no-op，避免真实 COS 调用
    """
    import app.services.blacklist_service as bl_module

    # 让 add_to_blacklist 内的 `async with AsyncSessionLocal() as session` 拿到测试 session
    monkeypatch.setattr(
        bl_module, "AsyncSessionLocal", lambda: _FakeSessionCtx(db_session)
    )
    # COS 写入在 add_to_blacklist 内被 try/except 兜住，但显式 mock 更稳妥
    monkeypatch.setattr(bl_module.cos_client, "put_object", AsyncMock(return_value=None))

    svc = UserService(db_session)
    # exp 设为 1 小时后，确保 remaining_ttl > 0
    future_exp = int((datetime.now(timezone.utc)).timestamp()) + 3600
    await svc.logout(jti="test-jti-001", exp=future_exp, user_id=1)

    # jwt_blacklist 表中应能查到该 jti
    result = await db_session.execute(
        select(JwtBlacklist).where(JwtBlacklist.jti == "test-jti-001")
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.token_type == "user"
    assert entry.user_id == 1


@pytest.mark.asyncio
async def test_logout_expired_token_noop(db_session):
    """已过期的 token 登出不应写黑名单（避免 SQLite/COS 残留无意义记录）。"""
    svc = UserService(db_session)
    # exp 设为过去时间，logout 内部 remaining_ttl <= 0 时直接 return
    past_exp = int((datetime.now(timezone.utc)).timestamp()) - 100
    await svc.logout(jti="expired-jti", exp=past_exp, user_id=1)

    # jwt_blacklist 表中不应有该 jti
    result = await db_session.execute(
        select(JwtBlacklist).where(JwtBlacklist.jti == "expired-jti")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_get_user_info_returns_data(db_session):
    """get_user_info 返回用户完整信息。"""
    user = User(
        openid="wx-info-001",
        nickname="info-user",
        avatar="http://example.com/a.png",
        total_listen_duration=120,
        total_listen_count=3,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    svc = UserService(db_session)
    info = await svc.get_user_info(user.id)
    assert info["user_id"] == user.id
    assert info["openid"] == "wx-info-001"
    assert info["nickname"] == "info-user"
    assert info["avatar"] == "http://example.com/a.png"
    assert info["total_listen_duration"] == 120
    assert info["total_listen_count"] == 3


@pytest.mark.asyncio
async def test_get_user_info_not_found_raises(db_session):
    """查询不存在的用户抛 AuthError。"""
    svc = UserService(db_session)
    with pytest.raises(AuthError):
        await svc.get_user_info(99999)
