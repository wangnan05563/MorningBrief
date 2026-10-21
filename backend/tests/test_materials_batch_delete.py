"""素材库批量删除接口测试（T02517 / FR-UX-703 / C52）。

背景：素材库两张表此前没有勾选列，清理一本误入库的书要逐行点删除几十次。
新增 `POST /admin/api/v1/materials/batch-delete` 在**一条事务 + 一条审计日志**里
按素材 ID / 书名批删。本文件锁住四条口径：
1) ids 与 sources 是「或」的关系，命中集合去重后一次删除；
2) sources 那一路必须带 channel_id 才收窄（否则同名书会波及其他频道，与
   `delete_materials_by_source` 同口径）；
3) 空请求与超上限都是 400，不静默接受；
4) 破坏性操作写审计日志（NFR-UX-05），且只允许 admin。
"""
import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models import AuditLog, Material
from app.models.material import MaterialSourceType, MaterialStatus

BATCH_URL = "/admin/api/v1/materials/batch-delete"


def _make_material(channel_id, source, title, url):
    return Material(
        source=source,
        source_type=MaterialSourceType.list.value,
        title=title,
        content="正文",
        url=url,
        category="tech",
        status=MaterialStatus.pending.value,
        channel_id=channel_id,
    )


def _headers(token):
    return {"Authorization": f"Bearer {token['token']}"}


@pytest.fixture
def operator_token():
    """非 admin 的运营 token：用于断言批删只放给 admin。"""
    token, _jti, _expires_in = create_access_token(
        "2", token_type="admin", extra_claims={"username": "op", "role": "operator"},
    )
    return {"token": token, "jti": _jti}


async def _seed(client, db_session, admin_token):
    """种 4 条素材：频道 1 的两章《A 书》 + 一章《B 书》，频道 2 的一章同名《A 书》。"""
    rows = [
        _make_material(1, "A书", "A-1", "https://a.com/a1"),
        _make_material(1, "A书", "A-2", "https://a.com/a2"),
        _make_material(1, "B书", "B-1", "https://a.com/b1"),
        _make_material(2, "A书", "A-其他频道", "https://a.com/other-a"),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    return rows


async def test_batch_delete_by_ids_removes_only_selected(client, db_session, admin_token):
    rows = await _seed(client, db_session, admin_token)
    resp = client.post(
        BATCH_URL,
        json={"ids": [rows[0].id, rows[2].id]},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == {"deleted": 2, "requested": 2}

    left = client.get(
        "/admin/api/v1/materials", headers=_headers(admin_token)
    ).json()["data"]["list"]
    assert {m["title"] for m in left} == {"A-2", "A-其他频道"}


async def test_batch_delete_by_source_scoped_by_channel(client, db_session, admin_token):
    """带 channel_id 时只删该频道下的同名书；不带时跨频道一起删（与单本删除同口径）。"""
    await _seed(client, db_session, admin_token)
    resp = client.post(
        BATCH_URL,
        json={"sources": ["A书"], "channel_id": 1},
        headers=_headers(admin_token),
    )
    assert resp.json()["data"]["deleted"] == 2

    left = client.get("/admin/api/v1/materials", headers=_headers(admin_token)).json()["data"]["list"]
    assert {m["title"] for m in left} == {"B-1", "A-其他频道"}, "其他频道的同名书必须保留"


async def test_batch_delete_by_source_without_channel_hits_all_channels(client, db_session, admin_token):
    await _seed(client, db_session, admin_token)
    resp = client.post(BATCH_URL, json={"sources": ["A书"]}, headers=_headers(admin_token))
    assert resp.json()["data"]["deleted"] == 3


async def test_batch_delete_ids_and_sources_are_unioned_without_duplicates(client, db_session, admin_token):
    """同一本书里被点到的某章既在 ids 又在 sources：只删一次，不重复计数。"""
    rows = await _seed(client, db_session, admin_token)
    resp = client.post(
        BATCH_URL,
        json={"ids": [rows[0].id], "sources": ["A书"], "channel_id": 1},
        headers=_headers(admin_token),
    )
    # A书/频道1 = 2 条（含 rows[0]），并上 B? 不含 → 恰好 2
    assert resp.json()["data"]["deleted"] == 2


async def test_batch_delete_empty_request_is_rejected(client, db_session, admin_token):
    await _seed(client, db_session, admin_token)
    resp = client.post(BATCH_URL, json={}, headers=_headers(admin_token))
    # 项目口径：业务校验失败走信封 code=400（HTTP 200），前端拦截器按 code!==0 提示
    assert resp.json()["code"] == 400, resp.text
    assert "至少提供一个" in resp.json()["message"]


async def test_batch_delete_over_limit_deletes_nothing(client, db_session, admin_token):
    rows = await _seed(client, db_session, admin_token)
    # 真实 ids + 大量不存在的 id 一起超上限：必须先拒绝，不能让部分删除先落库
    ids = [r.id for r in rows] + [90000 + i for i in range(200)]
    resp = client.post(BATCH_URL, json={"ids": ids}, headers=_headers(admin_token))
    assert resp.json()["code"] == 400, resp.text
    assert "单次最多删除" in resp.json()["message"]
    total = client.get("/admin/api/v1/materials", headers=_headers(admin_token)).json()["data"]["total"]
    assert total == 4, "超限请求必须一条都不删"


async def test_batch_delete_writes_one_audit_log(client, db_session, admin_token):
    rows = await _seed(client, db_session, admin_token)
    client.post(BATCH_URL, json={"ids": [r.id for r in rows[:2]]}, headers=_headers(admin_token))
    logs = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.category == "material", AuditLog.action == "batch_delete")
            )
        )
        .scalars()
        .all()
    )
    assert len(logs) == 1, "一次批删只留一条审计（记范围，不逐行刷屏）"
    detail = logs[-1].detail or ""
    assert "deleted_count" in detail and "正文" not in detail, "审计明细记范围，不带素材正文"


async def test_batch_delete_requires_admin_role(client, db_session, admin_token, operator_token):
    rows = await _seed(client, db_session, admin_token)
    resp = client.post(BATCH_URL, json={"ids": [rows[0].id]}, headers=_headers(operator_token))
    assert resp.status_code in (401, 403), f"operator 不应能批删，实际 {resp.status_code}"
    total = client.get("/admin/api/v1/materials", headers=_headers(admin_token)).json()["data"]["total"]
    assert total == 4


async def test_batch_delete_missing_ids_returns_zero_not_error(client, db_session, admin_token):
    """勾选后数据已被他人删除：返回 deleted=0，前端提示「已无匹配素材」，不能报 500。"""
    await _seed(client, db_session, admin_token)
    resp = client.post(BATCH_URL, json={"ids": [999999]}, headers=_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] == 0
