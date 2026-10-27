"""T03328：admin 自助改密（路由 + 服务 + 审计 + token 吊销口径）。

三层都测的原因：
- 路由层：FastAPI 依赖、Cookie 清理、审计写入只在 HTTP 链路上发生；
- 服务层：长度校验放在服务方法里，绕过 schema 直接调用的路径也要拦；
- 反例：改密只许改「自己」——schema 全绿但 admin_id 接错对象时，
  受害的是另一个账号，只有「他人哈希不变」这条能抓住。

口径（实现时定的）：改密即吊销**当前** jti，并用同一响应清掉 HttpOnly Cookie；
其它会话不受影响。前端据此回登录页，用新口令重新登录。
"""
import json

import pytest
from sqlalchemy import select

from app.core.exceptions import BizError
from app.core.security import MIN_ADMIN_PASSWORD_LEN, hash_password, verify_password
from app.models import AdminUser, AuditLog
from app.services.admin_service import AdminService

BASE = "/admin/api/v1/auth"
OLD = "Old-Pass-123"
NEW = "New-Pass-456"


def _headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def _add_admin(db, username="admin", password=OLD, admin_id=1):
    row = AdminUser(
        id=admin_id,
        username=username,
        password_hash=hash_password(password),
        role="admin",
    )
    db.add(row)
    return row


@pytest.fixture
def blacklist(monkeypatch):
    """记录被吊销的 jti，鉴权侧按同一集合判定。

    黑名单真实现走 AsyncSessionLocal（生产库）+ COS，测试里换成本地集合，
    才能断言「改密后旧 token 真的被拒」，而不只是「调用了某个函数」。
    """
    revoked: set[str] = set()

    async def _add(jti, token_type, user_id, expires_at, _remaining_ttl):
        revoked.add(jti)

    async def _is_revoked(jti):
        return jti in revoked

    monkeypatch.setattr("app.services.admin_service.add_to_blacklist", _add)
    monkeypatch.setattr("app.core.auth.is_in_blacklist", _is_revoked)
    return revoked


@pytest.mark.asyncio
async def test_change_password_success_rotates_hash_and_revokes_token(
    client, db_session, admin_token, blacklist
):
    """成功后：新口令可登录、旧口令失效、审计只记谁改谁、当前 token 被吊销。"""
    admin = _add_admin(db_session)
    await db_session.commit()

    resp = client.post(
        f"{BASE}/change-password",
        json={"old_password": OLD, "new_password": NEW},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["relogin_required"] is True
    # 响应体不得回显新旧口令
    assert OLD not in resp.text and NEW not in resp.text

    await db_session.refresh(admin)
    assert verify_password(NEW, admin.password_hash)
    assert not verify_password(OLD, admin.password_hash)

    # 立即用新口令登录成功，旧口令登录失败
    login_new = client.post(
        f"{BASE}/login", json={"username": "admin", "password": NEW}
    )
    assert login_new.json()["code"] == 0
    login_old = client.post(
        f"{BASE}/login", json={"username": "admin", "password": OLD}
    )
    assert login_old.json()["code"] == 401

    # 审计只记「谁改了谁的口令」，detail 不落明文/哈希
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert (row.category, row.action) == ("user", "change_password")
    assert row.operator == "admin"
    assert row.target == "admin"
    detail = row.detail or ""
    assert OLD not in detail and NEW not in detail
    assert "reason" in json.loads(detail)

    # 当前 token 进黑名单：同一 token 再访问受保护接口 401
    assert admin_token["jti"] in blacklist
    again = client.post(f"{BASE}/logout", headers=_headers(admin_token))
    assert again.status_code == 401

    # Cookie 被清除（max-age=0）
    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert "admin_token" in set_cookie
    assert "max-age=0" in set_cookie


@pytest.mark.asyncio
async def test_change_password_wrong_old_password(
    client, db_session, admin_token, blacklist
):
    """旧口令错 → 业务码 400，哈希不变，不写审计，不吊销 token。"""
    admin = _add_admin(db_session)
    await db_session.commit()
    before = admin.password_hash

    resp = client.post(
        f"{BASE}/change-password",
        json={"old_password": "Wrong-Pass-1", "new_password": NEW},
        headers=_headers(admin_token),
    )
    # BizError 默认 http_status=200，业务错误靠 code 判定
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 400
    assert body["message"] == "原密码错误"

    await db_session.refresh(admin)
    assert admin.password_hash == before
    assert (await db_session.execute(select(AuditLog))).scalars().all() == []
    assert blacklist == set()


@pytest.mark.asyncio
async def test_change_password_too_short_rejected_by_schema(
    client, db_session, admin_token, blacklist
):
    """新口令短于口径：请求校验直接 400，且不落库。"""
    admin = _add_admin(db_session)
    await db_session.commit()
    before = admin.password_hash
    short = "x" * (MIN_ADMIN_PASSWORD_LEN - 1)

    resp = client.post(
        f"{BASE}/change-password",
        json={"old_password": OLD, "new_password": short},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 400
    assert "new_password" in body["message"]

    await db_session.refresh(admin)
    assert admin.password_hash == before
    assert blacklist == set()


@pytest.mark.asyncio
async def test_change_password_requires_login(client, db_session):
    """未登录 → 401（改密不能是匿名接口）。"""
    _add_admin(db_session)
    await db_session.commit()

    resp = client.post(
        f"{BASE}/change-password",
        json={"old_password": OLD, "new_password": NEW},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_service_rejects_short_password_even_if_schema_bypassed(db_session):
    """服务层自带长度校验：绕过 pydantic 的直接调用方也拦得住。"""
    _add_admin(db_session)
    await db_session.commit()

    with pytest.raises(BizError) as exc:
        await AdminService(db_session).change_password(
            1, OLD, "y" * (MIN_ADMIN_PASSWORD_LEN - 1)
        )
    assert exc.value.code == 400
    assert "至少" in exc.value.message


@pytest.mark.asyncio
async def test_service_unknown_admin_is_404(db_session):
    with pytest.raises(BizError) as exc:
        await AdminService(db_session).change_password(9999, OLD, NEW)
    assert exc.value.code == 404


@pytest.mark.asyncio
async def test_change_password_only_touches_self(db_session):
    """接错对象防护：改 admin 1 的口令，admin 2 的哈希必须原样。"""
    first = _add_admin(db_session, username="admin", admin_id=1)
    second = _add_admin(db_session, username="ops", password="Other-Pass-1", admin_id=2)
    await db_session.commit()
    other_before = second.password_hash

    await AdminService(db_session).change_password(1, OLD, NEW)

    await db_session.refresh(first)
    await db_session.refresh(second)
    assert verify_password(NEW, first.password_hash)
    assert second.password_hash == other_before
