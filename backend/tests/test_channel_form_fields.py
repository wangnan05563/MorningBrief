"""频道表单字段序列化与「启用」开关口径测试（T02518 / FR-UX-704 / C15、C17）。

两条都是「界面说的和后端做的不一致」，只在弹窗里点一遍才会暴露：

- C15：新增模式下「启用」开关完全无效——`ChannelCreateRequest` 没有 `is_active` 字段，
  服务层写死 `is_active=1`。运营把开关关掉再创建，得到的是一个**已启用**频道，
  而提示只说「已创建」，于是新频道当天就被调度抓稿（真实副作用，不只是显示错）。
- C17：`_channel_to_dict` 未序列化 `icon_url`，编辑弹窗回填 `row.icon_url` 恒为空
  → 每次打开都显示「无图标」，运营以为图标丢了，重复上传/重复 AI 生成（每次生成有成本）。

断言口径取自项目约定：参数校验失败是 **HTTP 400 + body.code=400**
（`app/core/exceptions.py` 的 RequestValidationError 处理器），不是 200 信封。
"""
import io

from app.models import Channel

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f0300050001ffa5a5a50000000049454e44ae426082"
)

BASE = "/admin/api/v1/channels"


def _auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def _create(client, admin_token, **extra):
    resp = client.post(BASE, json={"name": extra.pop("name", "T02518 频道"), **extra},
                       headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


# ---------------------------------------------------------------- C15


def test_create_channel_respects_is_active_zero(client, admin_token):
    """关掉「启用」开关创建的频道必须是未启用（此前恒为 1）。"""
    data = _create(client, admin_token, name="T02518 未启用频道", is_active=0)
    assert data["is_active"] == 0, "请求体里的 is_active=0 被忽略 = C15 原缺陷"

    listed = client.get(f"{BASE}?active_only=true", headers=_auth(admin_token)).json()["data"]
    assert data["id"] not in [c["id"] for c in listed], "未启用频道不应出现在启用列表中"


def test_create_channel_defaults_to_active(client, admin_token):
    """不传 is_active 时保持既有行为（默认启用），避免影响所有存量调用方。"""
    assert _create(client, admin_token, name="T02518 默认频道")["is_active"] == 1


def test_create_channel_rejects_illegal_is_active(client, admin_token):
    """is_active 只认 0/1：脏值必须报错，不能被悄悄当成「启用」。"""
    resp = client.post(BASE, json={"name": "T02518 脏值", "is_active": 2},
                       headers=_auth(admin_token))
    assert resp.status_code == 400, resp.text
    assert "is_active" in resp.json()["message"]


def test_inactive_channel_absent_from_active_only_list(client, admin_token):
    """未启用频道不得被 `active_only=true` 取走——调度/小程序按这条路取频道，
    开关失效的后果不只是显示错，而是新建当天就被抓稿。"""
    data = _create(client, admin_token, name="T02518 调度隔离", is_active=0)
    active = client.get(f"{BASE}?active_only=true", headers=_auth(admin_token)).json()["data"]
    all_rows = client.get(BASE, headers=_auth(admin_token)).json()["data"]
    assert data["id"] in [c["id"] for c in all_rows], "未启用频道仍应在全部列表中可见（可再启用）"
    assert data["id"] not in [c["id"] for c in active]


# ---------------------------------------------------------------- C17


def test_channel_serialization_contains_icon_url(client, admin_token):
    """上传图标后，列表与详情都必须带回 icon_url（编辑弹窗据此回填）。"""
    data = _create(client, admin_token, name="T02518 图标频道")
    cid = data["id"]
    assert "icon_url" in data, "_channel_to_dict 缺字段 → 弹窗永远显示「无图标」"
    assert data["icon_url"] is None

    upload = client.post(f"{BASE}/{cid}/icon",
                         files={"file": ("icon.png", io.BytesIO(PNG_BYTES), "image/png")},
                         headers=_auth(admin_token)).json()
    assert upload["code"] == 0, upload
    icon_url = upload["data"]["icon_url"]

    listed = client.get(BASE, headers=_auth(admin_token)).json()["data"]
    row = next(c for c in listed if c["id"] == cid)
    assert row["icon_url"] == icon_url, "列表接口漏 icon_url ⇒ 打开编辑弹窗时图标区显示「无图标」"
    # 该路由没有 GET /{id} 详情端点（弹窗复用列表行），故再验一次 PUT 的返回序列化：
    # 保存后若仍漏字段，前端本地状态会在下一次刷新前把图标当成空
    updated = client.put(f"{BASE}/{cid}", json={"description": "改个描述"},
                         headers=_auth(admin_token)).json()["data"]
    assert updated["icon_url"] == icon_url, "更新响应必须保留 icon_url"


def test_channel_dict_fields_cover_model_column_names(client, admin_token):
    """序列化完整性门禁：模型上可编辑的列，弹窗拿不到就等于「回填丢失」。

    新增列时必须同步 `_channel_to_dict`，否则又是一条 C17。
    """
    editable = {
        "name", "description", "is_active", "schedule_time",
        "intro_prompt", "outro_prompt", "constraint_prompt", "rewrite_template",
        "bgm_path", "bgm_volume", "segment_gap_sec", "bgm_gap_mode",
        "enable_thinking_question", "rss_sources", "book_rss_sources", "keywords",
        "min_duration_sec", "display_order", "material_lookback_days",
        "selection_strategy", "enable_ad", "manual_material_ids",
        "channel_type", "type_label", "cover_url", "disclaimer_level", "icon_url",
    }
    assert editable <= set(Channel.__table__.columns.keys()), "模型列名与用例清单已脱节"
    data = _create(client, admin_token, name="T02518 字段完整性")
    missing = sorted(editable - set(data.keys()))
    assert not missing, f"_channel_to_dict 漏序列化字段: {missing}"
