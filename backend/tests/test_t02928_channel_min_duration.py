"""频道级最短时长（min_duration_sec）管理端入口（T02928）。

这条业务分支在 `rewriter`（自动扩稿）与 `stitch/concat`（拼接下限）里一直在读，
但管理端没有任何入口：`ChannelUpdateRequest` 不含该字段，路由又是逐个显式 kwarg
透传，所以即使前端补了提交字段也会在 pydantic 与调用点两道被丢。
本文件钉住三件事：

1. 900 秒能从 HTTP 真的写进库（不能只看返回码——C56）；
2. 清除语义：显式 null 清掉覆盖，未传字段保持原值（用 `model_fields_set` 区分）；
3. 接口层区间校验按 INT-UX-01 回传字段级错误，而不是只在输入框上做 `:min/:max`。
"""
import pytest
from sqlalchemy import select

from app.models import Channel
from app.workflow.duration import resolve_channel_min_duration_sec

BASE = "/admin/api/v1/channels"


def _auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def _create(client, admin_token, **extra):
    payload = {"name": extra.pop("name", "T02928 频道"), **extra}
    resp = client.post(BASE, json=payload, headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


async def _db_value(db_session, channel_id):
    row = (
        await db_session.execute(select(Channel).where(Channel.id == channel_id))
    ).scalar_one()
    await db_session.refresh(row)
    return row.min_duration_sec


def _put(client, admin_token, channel_id, payload):
    return client.put(f"{BASE}/{channel_id}", json=payload, headers=_auth(admin_token))


# ---------------------------------------------------------------- 写入与回读


async def test_update_writes_900_to_database(client, admin_token, db_session):
    """编辑填 900 保存 → 库内该列必须等于 900（不断言返回码即算过）。"""
    created = _create(client, admin_token, name="T02928 写入")
    resp = _put(client, admin_token, created["id"], {"min_duration_sec": 900})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["min_duration_sec"] == 900

    assert await _db_value(db_session, created["id"]) == 900, "接口成功但库里没动 = 原缺陷"

    listed = client.get(BASE, headers=_auth(admin_token)).json()["data"]
    row = next(c for c in listed if c["id"] == created["id"])
    assert row["min_duration_sec"] == 900, "列表接口要吐出配置值，编辑弹窗据此回填"


async def test_create_accepts_and_persists_min_duration_sec(client, admin_token, db_session):
    """新增表单同样要能配置（此前创建请求里只能传进 None）。"""
    created = _create(client, admin_token, name="T02928 新增", min_duration_sec=1200)
    assert created["min_duration_sec"] == 1200
    assert await _db_value(db_session, created["id"]) == 1200


# ---------------------------------------------------------------- 清除语义


async def test_explicit_null_clears_override(client, admin_token, db_session):
    """取消勾选「自定义最短时长」= 显式 null = 清除覆盖、回落动态默认。"""
    created = _create(client, admin_token, name="T02928 清除", min_duration_sec=900)
    resp = _put(client, admin_token, created["id"], {"min_duration_sec": None})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["min_duration_sec"] is None
    assert await _db_value(db_session, created["id"]) is None, "清空被静默保留 = 界面提示撒谎"


async def test_omitted_field_preserves_existing_value(client, admin_token, db_session):
    """请求体不带该字段时保持原值——不能把「未提交」当成「清空」。"""
    created = _create(client, admin_token, name="T02928 保留", min_duration_sec=900)
    resp = _put(client, admin_token, created["id"], {"description": "只改描述"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["min_duration_sec"] == 900
    assert await _db_value(db_session, created["id"]) == 900


# ---------------------------------------------------------------- 区间校验


@pytest.mark.parametrize("bad", [179, 1801, 0, -1])
async def test_rejects_out_of_range(client, admin_token, db_session, bad):
    """负数、0、越上界都要在接口层拒绝，并指出是哪个字段。"""
    created = _create(client, admin_token, name=f"T02928 越界{bad}")
    resp = _put(client, admin_token, created["id"], {"min_duration_sec": bad})
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["code"] == 400
    errors = body["data"]["errors"]
    assert errors[0]["loc"] == ["body", "min_duration_sec"], errors
    assert "180-1800" in errors[0]["msg"], errors
    assert await _db_value(db_session, created["id"]) is None, "拒绝的请求不得落库"


@pytest.mark.parametrize("bad", [0, 179])
async def test_create_rejects_out_of_range(client, admin_token, bad):
    resp = client.post(
        BASE,
        json={"name": f"T02928 创建越界{bad}", "min_duration_sec": bad},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["data"]["errors"][0]["loc"] == ["body", "min_duration_sec"]


async def test_accepts_boundaries(client, admin_token):
    low = _create(client, admin_token, name="T02928 下界", min_duration_sec=180)
    high = _create(client, admin_token, name="T02928 上界", min_duration_sec=1800)
    assert (low["min_duration_sec"], high["min_duration_sec"]) == (180, 1800)


# ---------------------------------------------------------------- 业务分支


async def test_configured_value_drives_duration_resolver(client, admin_token):
    """运营态配置的值必须真的进入 `resolve_channel_min_duration_sec`。"""
    created = _create(
        client, admin_token, name="T02928 听书", channel_type="audiobook", min_duration_sec=900
    )
    assert resolve_channel_min_duration_sec(created["channel_type"], created["min_duration_sec"]) == 900
    # 未配置时仍走按类型动态默认，不被本单改写
    assert resolve_channel_min_duration_sec("audiobook", None) == 1800
    assert resolve_channel_min_duration_sec("news", None) is None
