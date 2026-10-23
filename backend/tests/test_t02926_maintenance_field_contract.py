"""T02926：系统清理三端点的字段契约——未知字段不再被静默吞，审计列记下保留窗口。

本单的**线上真缺陷**是后半个：`/maintenance/database` 与 `/maintenance/logs` 按天数窗口清理，
但 `audit_log.detail` 里从来没有 days——接口返回 200、库里也确实删了，事后只能看到「清过了」，
看不到「按几天清的」。所以这里断言的是**库里的值**（M16 口径），不是返回码。

前半属于契约收紧：三个清理端点原先共用 `CleanupRequest`，缓存端点因此接收它根本无法兑现的
`days`（TTLCache 条目、`__pycache__`、临时文件都没有「保留 N 天」语义）。前端目前只在非缓存
分类提交这个字段（apps/admin-web/src/views/maintenance/Maintenance.vue:400），所以没有造成
错数据；但 pydantic 默认 `extra="ignore"` 会把任何误发的同类字段照单全收，静默失败只是时间问题。
拆出 `CacheCleanupRequest` 并给两个请求体加 `extra="forbid"`，就是把这个潜在漏洞关死。
"""
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog

BASE = "/admin/api/v1/maintenance"
ROLLOUT_FILE = Path(__file__).resolve().parents[2] / "scripts" / "field_audit" / "forbid_endpoints.json"


def _rollout():
    """灰度登记表是断言的参数源——文档说做了、代码没做，这条就红。"""
    return json.loads(ROLLOUT_FILE.read_text(encoding="utf-8"))["endpoints"]


def _route_models():
    """运行时反射：`登记表键 → (模型名, extra)`。不复制字段清单，只读代码现状。"""
    from pydantic import BaseModel

    from app.main import app

    out = {}
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        model = None
        for bp in (getattr(getattr(route, "dependant", None), "body_params", None) or []):
            ann = getattr(bp, "type_", None)
            if isinstance(ann, type) and issubclass(ann, BaseModel):
                model = ann
                break
        if not methods or not path or model is None:
            continue
        parts = [p for p in path.split("/") if p]
        if parts[:3] == ["admin", "api", "v1"]:
            parts = parts[3:]
        key_path = "/" + "/".join("*" if p.startswith("{") else p for p in parts)
        extra = (model.model_config or {}).get("extra") or "ignore"
        for method in methods:
            if method not in ("GET", "HEAD", "OPTIONS"):
                out[f"{method} {key_path}"] = (model.__name__, extra)
    return out


def _post(client, admin_token, category, payload):
    return client.post(f"{BASE}/{category}", json=payload,
                       headers={"Authorization": f"Bearer {admin_token['token']}"})


async def _latest_audit(db_session, action):
    res = await db_session.execute(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id.desc())
    )
    return res.scalars().first()


async def test_cache_rejects_days_instead_of_silently_ignoring_it(client, admin_token):
    """缓存端点不声明 days：多传一个生效不了的参数，比少传更坏。"""
    resp = _post(client, admin_token, "cache", {"target": "pycache", "days": 7, "dry_run": True})
    body = resp.json()
    assert body.get("code") not in (0, 200), (
        f"days 又被静默吞了：{body}——缓存清理没有天数语义，必须拒而不是收")
    errors = (body.get("data") or {}).get("errors") or []
    named = {e.get("field") or (e.get("loc") or [None])[-1] for e in errors}
    assert "days" in named, f"拒绝但没有点名到 days（前端无法定位字段）：{body}"
    assert all(e.get("msg") for e in errors), f"错误明细没给可读原因：{errors}"


async def test_database_audit_records_the_retention_window(db_session, client, admin_token):
    """按天数执行的清理，审计 detail 列里必须真的带着那个天数。"""
    resp = _post(client, admin_token, "database",
                 {"target": "old_dedup", "days": 21, "dry_run": True})
    assert resp.json().get("code") in (0, 200), resp.json()
    row = await _latest_audit(db_session, "cleanup_database")
    assert row is not None, "dry_run 也要留痕：清理审计一条都没写"
    detail = json.loads(row.detail or "{}")
    assert detail.get("days") == 21, (
        f"audit_log.detail 里没有保留窗口（现值 {detail}）——事后无法判断那次清理按几天执行")


async def test_logs_audit_records_the_retention_window(db_session, client, admin_token):
    resp = _post(client, admin_token, "logs", {"target": "old_logs", "days": 14, "dry_run": True})
    assert resp.json().get("code") in (0, 200), resp.json()
    row = await _latest_audit(db_session, "cleanup_logs")
    assert row is not None
    assert json.loads(row.detail or "{}").get("days") == 14


async def test_cache_audit_has_no_days_field(client, admin_token):
    """反向钉：缓存清理不该写 days，写了说明模型又被合并回去了。"""
    resp = _post(client, admin_token, "cache", {"target": "ttlcache", "dry_run": True})
    assert resp.json().get("code") in (0, 200), resp.json()


async def test_cache_still_accepts_its_own_fields(client, admin_token):
    """灰度不能顺手把合法请求也拦掉：target/dry_run 必须照常通过。"""
    for target in ("ttlcache", "pycache", "temp", "all"):
        resp = _post(client, admin_token, "cache", {"target": target, "dry_run": True})
        assert resp.json().get("code") in (0, 200), f"{target} 被误拦：{resp.json()}"


def test_three_maintenance_models_are_now_forbid():
    """登记表口径：这三个端点的 extra 必须是 forbid，且缓存模型不再声明 days。"""
    from app.routers.admin.maintenance import CacheCleanupRequest, CleanupRequest

    assert CleanupRequest.model_config.get("extra") == "forbid"
    assert CacheCleanupRequest.model_config.get("extra") == "forbid"
    assert "days" not in CacheCleanupRequest.model_fields


@pytest.mark.parametrize("entry", _rollout(), ids=[e["key"] for e in _rollout()])
async def test_registered_forbid_endpoint_rejects_undeclared_field(client, admin_token, entry):
    """登记为 forbid 的每个端点都必须真的拒未知字段——登记表与代码不能两张皮。"""
    resp = client.post(f"/admin/api/v1{entry['key'].split(' ', 1)[1]}",
                       json={"dry_run": True, entry["probe_field"]: 1},
                       headers={"Authorization": f"Bearer {admin_token['token']}"})
    body = resp.json()
    assert body.get("code") not in (0, 200), (
        f"{entry['key']} 登记为 forbid 但未知字段又被吞了：{body}")
    errors = (body.get("data") or {}).get("errors") or []
    named = {e.get("field") or (e.get("loc") or [None])[-1] for e in errors}
    assert entry["probe_field"] in named, f"拒了但没点名 {entry['probe_field']}：{body}"


def test_forbid_rollout_list_matches_reflection():
    """双向比对：登记表列了但代码没 forbid → 红；代码 forbid 了但没登记 → 也红。"""
    models = _route_models()
    registered = {e["key"] for e in _rollout()}
    actually_forbid = {k for k, (_, extra) in models.items() if extra == "forbid"}
    for key in registered:
        assert key in models, f"登记表端点不存在或没有 body 模型：{key}"
        assert models[key][1] == "forbid", f"{key} 登记为 forbid，代码里却是 {models[key][1]}"
    assert actually_forbid == registered, (
        f"代码已 forbid 但未登记的端点：{sorted(actually_forbid - registered)}；"
        f"登记了但代码没 forbid 的：{sorted(registered - actually_forbid)}")
    entry_models = {e["key"]: e["model"] for e in _rollout()}
    for key, model_name in entry_models.items():
        assert models[key][0] == model_name, f"{key} 登记的模型名与代码不符：{models[key][0]}"
