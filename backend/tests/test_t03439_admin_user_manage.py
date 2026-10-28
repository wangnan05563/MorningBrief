"""T03439：后台账号管理（B 端用户管理菜单）。

覆盖三层：
- 路由：仅 admin 可用，响应不含 password_hash，写审计；
- 服务：绕过 HTTP 直接调用也拦得住用户名/口令长度/角色；
- 反例：不许把自己降级/禁用/删掉，也不许把最后一个启用管理员弄没。
"""
import json

import pytest
from sqlalchemy import select

from app.core.exceptions import BizError
from app.core.security import (
    MIN_ADMIN_PASSWORD_LEN,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models import AdminUser, AuditLog
from app.services.admin_service import MAX_ADMIN_PASSWORD_LEN, AdminService

BASE = "/admin/api/v1/auth"
PWD = "Init-Pass-123"
NEW_PWD = "Reset-Pass-456"


def _token(role="admin", username="admin", admin_id=1):
    token, jti, _ = create_access_token(
        str(admin_id),
        token_type="admin",
        extra_claims={"username": username, "role": role},
    )
    return {"token": token, "jti": jti}


def _headers(token):
    return {"Authorization": f"Bearer {token['token']}"}


def _add_admin(db, username="admin", password=PWD, admin_id=1, role="admin", status=1):
    row = AdminUser(
        id=admin_id,
        username=username,
        password_hash=hash_password(password),
        role=role,
        status=status,
    )
    db.add(row)
    return row


@pytest.fixture(autouse=True)
def _no_blacklist(monkeypatch):
    async def _never(jti):
        return False

    monkeypatch.setattr("app.core.auth.is_in_blacklist", _never)


@pytest.mark.asyncio
async def test_list_returns_sanitized_accounts(client, db_session, admin_token):
    _add_admin(db_session, username="admin", admin_id=1)
    _add_admin(db_session, username="ops", password="Other-Pass-1", admin_id=2, role="operator")
    await db_session.commit()

    resp = client.get(f"{BASE}/users", headers=_headers(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["total"] == 2
    assert [row["username"] for row in data["list"]] == ["admin", "ops"]
    assert set(data["list"][0]) == {
        "id", "username", "nickname", "role", "status",
        "last_login_at", "created_at", "updated_at",
    }
    assert "password_hash" not in resp.text and PWD not in resp.text

    # 关键词同时命中用户名与昵称
    hit = client.get(f"{BASE}/users?keyword=op", headers=_headers(admin_token))
    assert [row["username"] for row in hit.json()["data"]["list"]] == ["ops"]


@pytest.mark.asyncio
async def test_operator_cannot_manage_accounts(client, db_session):
    _add_admin(db_session, username="admin", admin_id=1)
    await db_session.commit()
    op = _token(role="operator", username="ops", admin_id=2)

    for method, path, payload in [
        ("get", f"{BASE}/users", None),
        ("post", f"{BASE}/users", {"username": "newbie", "password": PWD}),
        ("put", f"{BASE}/users/1", {"nickname": "x"}),
        ("delete", f"{BASE}/users/1", None),
    ]:
        kwargs = {"headers": _headers(op)}
        if payload is not None:
            kwargs["json"] = payload
        resp = getattr(client, method)(path, **kwargs)
        assert resp.status_code == 403, f"{method} {path} 应拒绝 operator，实际 {resp.status_code}"


@pytest.mark.asyncio
async def test_create_hashes_password_and_audits(client, db_session, admin_token):
    _add_admin(db_session, username="admin", admin_id=1)
    await db_session.commit()

    resp = client.post(
        f"{BASE}/users",
        json={
            "username": "reviewer_1",
            "password": PWD,
            "role": "operator",
            "nickname": "审核一号",
            "reason": "新增夜班审核",
        },
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    created = body["data"]
    assert created["username"] == "reviewer_1"
    assert created["role"] == "operator"
    assert created["status"] == 1
    assert PWD not in resp.text

    row = (
        await db_session.execute(
            select(AdminUser).where(AdminUser.username == "reviewer_1")
        )
    ).scalar_one()
    assert verify_password(PWD, row.password_hash)
    assert PWD not in row.password_hash

    # 新账号可直接登录（哈希与登录链路同源）
    login = client.post(f"{BASE}/login", json={"username": "reviewer_1", "password": PWD})
    assert login.json()["code"] == 0

    audit = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(audit) == 1
    log = audit[0]
    assert (log.category, log.action) == ("admin_user", "create")
    assert log.target == "reviewer_1"
    assert log.operator == "admin"
    detail = json.loads(log.detail)
    assert detail["reason"] == "新增夜班审核"
    assert PWD not in log.detail


@pytest.mark.asyncio
async def test_create_rejects_duplicate_and_bad_input(client, db_session, admin_token):
    _add_admin(db_session, username="admin", admin_id=1)
    await db_session.commit()
    h = _headers(admin_token)

    dup = client.post(
        f"{BASE}/users", json={"username": "admin", "password": PWD}, headers=h
    )
    assert dup.status_code == 200
    assert dup.json()["code"] == 400
    assert dup.json()["message"] == "用户名已存在"

    bad_name = client.post(
        f"{BASE}/users", json={"username": "a!", "password": PWD}, headers=h
    )
    assert bad_name.json()["code"] == 400
    assert "用户名" in bad_name.json()["message"]

    short = client.post(
        f"{BASE}/users",
        json={"username": "shorty", "password": "x" * (MIN_ADMIN_PASSWORD_LEN - 1)},
        headers=h,
    )
    assert short.status_code == 400
    assert "password" in short.json()["message"]

    bad_role = client.post(
        f"{BASE}/users",
        json={"username": "rooty", "password": PWD, "role": "root"},
        headers=h,
    )
    assert bad_role.json()["code"] == 400
    assert "角色" in bad_role.json()["message"]

    # 失败路径不落账号、不写审计
    assert (await db_session.execute(select(AdminUser))).scalars().all()[0].username == "admin"
    assert (await db_session.execute(select(AuditLog))).scalars().all() == []


@pytest.mark.asyncio
async def test_update_role_status_and_reset_password(client, db_session, admin_token):
    _add_admin(db_session, username="admin", admin_id=1)
    target = _add_admin(
        db_session, username="ops", password="Other-Pass-1", admin_id=2, role="operator"
    )
    await db_session.commit()
    h = _headers(admin_token)

    promoted = client.put(
        f"{BASE}/users/2",
        json={"role": "admin", "nickname": "夜班", "reason": "接管审核"},
        headers=h,
    )
    assert promoted.json()["code"] == 0
    await db_session.refresh(target)
    assert target.role == "admin"
    assert target.nickname == "夜班"

    disabled = client.put(f"{BASE}/users/2", json={"status": 0}, headers=h)
    assert disabled.json()["code"] == 0
    await db_session.refresh(target)
    assert target.status == 0
    # 禁用后不能登录
    assert client.post(
        f"{BASE}/login", json={"username": "ops", "password": "Other-Pass-1"}
    ).json()["code"] == 403

    old_hash = target.password_hash
    reset = client.put(f"{BASE}/users/2", json={"password": NEW_PWD}, headers=h)
    assert reset.json()["code"] == 0
    assert NEW_PWD not in reset.text
    await db_session.refresh(target)
    assert target.password_hash != old_hash
    assert verify_password(NEW_PWD, target.password_hash)

    logs = (await db_session.execute(
        select(AuditLog).where(AuditLog.category == "admin_user")
    )).scalars().all()
    assert [log.action for log in logs] == ["update", "update", "update"]
    details = [json.loads(log.detail) for log in logs]
    assert details[0]["changes"] == {"role": "admin", "nickname": "夜班"}
    assert details[1]["changes"] == {"status": 0}
    assert details[2]["changes"] == {"password_reset": True}
    assert all(log.operator == "admin" for log in logs)
    assert NEW_PWD not in json.dumps(details, ensure_ascii=False)

    empty = client.put(f"{BASE}/users/2", json={}, headers=h)
    assert empty.json()["code"] == 400


@pytest.mark.asyncio
async def test_self_guards_block_lockout(client, db_session):
    me = _add_admin(db_session, username="admin", admin_id=1)
    await db_session.commit()
    h = _headers(_token(admin_id=1, username="admin"))

    cases = [
        ({"role": "operator"}, "不能修改自己的角色"),
        ({"status": 0}, "不能禁用当前登录的账号"),
        ({"password": NEW_PWD}, "修改密码"),
    ]
    for payload, expected in cases:
        resp = client.put(f"{BASE}/users/1", json=payload, headers=h)
        assert resp.json()["code"] == 400, (payload, resp.text)
        assert expected in resp.json()["message"]

    deleted = client.delete(f"{BASE}/users/1", headers=h)
    assert deleted.json()["code"] == 400
    assert "不能删除当前登录的账号" == deleted.json()["message"]

    # 改昵称仍允许
    renamed = client.put(f"{BASE}/users/1", json={"nickname": "管理员"}, headers=h)
    assert renamed.json()["code"] == 0
    await db_session.refresh(me)
    assert me.nickname == "管理员"


@pytest.mark.asyncio
async def test_keeps_last_active_admin(client, db_session):
    # actor(id=1) 不在库里；库里只有一个管理员 id=2
    only = _add_admin(db_session, username="solo", admin_id=2)
    await db_session.commit()
    h = _headers(_token(admin_id=1, username="admin"))

    for payload in ({"role": "operator"}, {"status": 0}):
        resp = client.put(f"{BASE}/users/2", json=payload, headers=h)
        assert resp.json()["code"] == 400, resp.text
        assert resp.json()["message"] == "至少保留一个启用状态的管理员"

    resp = client.delete(f"{BASE}/users/2", headers=h)
    assert resp.json()["code"] == 400
    assert resp.json()["message"] == "至少保留一个启用状态的管理员"

    # 有第二个启用管理员后放行
    _add_admin(db_session, username="backup", password="Backup-Pass-1", admin_id=3)
    await db_session.commit()
    ok = client.delete(f"{BASE}/users/2", headers=h)
    assert ok.json()["code"] == 0
    assert (await db_session.execute(
        select(AdminUser).where(AdminUser.id == only.id)
    )).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_operator_writes_audit(client, db_session):
    _add_admin(db_session, username="admin", admin_id=1)
    op = _add_admin(
        db_session, username="ops", password="Other-Pass-1", admin_id=2, role="operator"
    )
    await db_session.commit()

    resp = client.delete(
        f"{BASE}/users/{op.id}?reason=离岗",
        headers=_headers(_token(admin_id=1, username="admin")),
    )
    assert resp.json()["code"] == 0
    assert (await db_session.execute(
        select(AdminUser).where(AdminUser.id == op.id)
    )).scalar_one_or_none() is None

    log = (await db_session.execute(select(AuditLog))).scalar_one()
    assert (log.category, log.action, log.target) == ("admin_user", "delete", "ops")
    assert json.loads(log.detail)["reason"] == "离岗"


@pytest.mark.asyncio
async def test_only_touches_target_account(client, db_session, admin_token):
    first = _add_admin(db_session, username="admin", admin_id=1)
    second = _add_admin(
        db_session, username="ops", password="Other-Pass-1", admin_id=2, role="operator"
    )
    await db_session.commit()
    second_before = second.password_hash

    resp = client.put(
        f"{BASE}/users/1",
        json={"nickname": "运维"},
        headers=_headers(admin_token),
    )
    assert resp.json()["code"] == 0
    await db_session.refresh(first)
    await db_session.refresh(second)
    assert first.nickname == "运维"
    assert second.password_hash == second_before and second.nickname is None


@pytest.mark.asyncio
async def test_service_validation_and_unknown_account(db_session):
    _add_admin(db_session, username="admin", admin_id=1)
    await db_session.commit()
    svc = AdminService(db_session)

    with pytest.raises(BizError) as exc:
        await svc.create_admin(username="okname", password="z" * (MAX_ADMIN_PASSWORD_LEN + 1))
    assert exc.value.code == 400
    with pytest.raises(BizError) as exc:
        await svc.create_admin(username="okname", password=PWD, role="root")
    assert exc.value.code == 400

    with pytest.raises(BizError) as exc:
        await svc.update_admin(actor_id=1, admin_id=9999, nickname="x")
    assert exc.value.code == 404
    with pytest.raises(BizError) as exc:
        await svc.delete_admin(actor_id=1, admin_id=9999)
    assert exc.value.code == 404
