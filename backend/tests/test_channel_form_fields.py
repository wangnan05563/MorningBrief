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
import re
from pathlib import Path

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


# ------------------------------------------------- T02820 三层字段矩阵


ROOT = Path(__file__).resolve().parents[2]
CHANNEL_VIEW = ROOT / "apps/admin-web/src/views/channel/ChannelManagement.vue"
CHANNELS_ROUTER = ROOT / "backend/app/routers/admin/channels.py"

# 只活在弹窗里、提交前会转换成别的字段或纯 UI 开关的键。
# 每一项都要写明去向，否则「控件有、请求体没有」会被这张豁免表吞掉。
UI_ONLY = {
    "id": "编辑态主键，走 URL 路径不重复进请求体",
    "lookbackEnabled": "开关，提交时折叠成 material_lookback_days 的 null/值",
    "minDurationEnabled": "开关，提交时折叠成 min_duration_sec 的 null/值",
    "inherit_segment_gap": "开关，提交时把 segment_gap_sec 置空以继承全局",
    "inherit_bgm_gap": "开关，提交时把 bgm_gap_mode 置空以继承全局",
    "manual_material_ids_text": "逗号文本，提交时序列化成 manual_material_ids",
}
# 只在某一个分支提交、另一个分支有意不提交的控件（不登记就等于放走「半边没接线」）
CREATE_SKIP = {
    "intro_prompt", "outro_prompt", "constraint_prompt", "rewrite_template",
}
UPDATE_SKIP = {
    "auto_generate_prompts",
}
# 模型字段与控件名不同名但同源（必须显式登记，避免把改名当成缺口或反过来漏检）
FIELD_ALIASES = {"manual_material_ids": "manual_material_ids_text"}


def _balanced(src: str, open_idx: int) -> str:
    """取 src[open_idx] 的 `{` 起配对的块内容。跳过字符串与 //、/* */ 注释。"""
    assert src[open_idx] == "{", src[open_idx - 20:open_idx + 20]
    depth, i = 0, open_idx
    while i < len(src):
        ch = src[i]
        if ch in "'\"`":
            quote, i = ch, i + 1
            while i < len(src):
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == quote:
                    break
                i += 1
        elif src.startswith("//", i):
            nl = src.find("\n", i)
            if nl == -1:
                break
            i = nl
        elif src.startswith("/*", i):
            i = src.find("*/", i) + 2
            continue
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[open_idx + 1:i]
        i += 1
    raise AssertionError("花括号不配对，源码结构可能已变")


def _object_after(src: str, marker: str) -> tuple[str, set[str]]:
    """marker 之后第一个对象字面量的块文本与顶格键集合（含 ...spread 展开）。"""
    assert src.count(marker) == 1, f"锚点不唯一（{src.count(marker)} 处）：{marker!r}"
    idx = src.index(marker) + len(marker)
    while src[idx] != "{":
        idx += 1
    block = _balanced(src, idx)
    keys, depth, i, prev = set(), 0, 0, ""
    while i < len(block):
        ch = block[i]
        if ch in "'\"`":
            quote, i = ch, i + 1
            while i < len(block):
                if block[i] == "\\":
                    i += 2
                    continue
                if block[i] == quote:
                    break
                i += 1
            prev = quote
        elif block.startswith("//", i):
            nl = block.find("\n", i)
            if nl == -1:
                break
            i = nl
            # 注释不改变 prev：`{ a: 1, // 说明\n b: 2` 里 b 的前一个有效字符仍是逗号
        elif ch in "{[(":
            depth += 1
            prev = ch
        elif ch in "}])":
            depth -= 1
            prev = ch
        elif depth == 0 and (ch.isalpha() or ch in "_$"):
            j = i
            while j < len(block) and (block[j].isalnum() or block[j] in "_$"):
                j += 1
            k = j
            while k < len(block) and block[k] in " \t\n":
                k += 1
            # 属性名前面只能是 `{` 或 `,`：三元 `? null : x` 里的 null 也会长得像 `word:`
            if prev in "{," and k < len(block) and block[k] == ":":
                keys.add(block[i:j])
            prev = block[j - 1]
            i = j
            continue
        elif ch not in " \t\n":
            prev = ch
        i += 1
    return block, keys


def _model_fields(cls_name: str) -> set[str]:
    src = CHANNELS_ROUTER.read_text(encoding="utf-8")
    # 类体到下一个顶格行结束：不能跨进模块级函数，否则函数体里的 try:/with: 会被当成字段
    body = re.search(rf"class {cls_name}\(BaseModel\):(.*?)(?=\nclass |\n\S|\Z)", src, re.S)
    assert body, f"未找到 {cls_name}"
    return set(re.findall(r"^ {4}(\w+)\s*:", body.group(1), re.M))


def test_channel_form_request_model_matrix_has_no_gap():
    """控件 / 请求体 / 后端模型 三层字段矩阵（T02820 附加检查项）。

    C15 的形态是「弹窗有控件、请求体没有该字段」——后端只能按默认值落库，
    运营看到保存成功，实际配置没生效。序列化侧（模型→响应）已有
    `test_channel_dict_fields_cover_model_column_names` 兜住，本用例兜的是
    请求体侧：新增/编辑两个 payload 的每个键都必须被对应模型接收，
    每个表单控件都必须有去处（进请求体，或在 UI_ONLY 里写明转换去向）。
    """
    src = CHANNEL_VIEW.read_text(encoding="utf-8")

    _, form = _object_after(src, "const form = reactive(")
    _, ext = _object_after(src, "const extPayload = ")
    create_block, create = _object_after(src, "await createChannel(")
    update_block, update = _object_after(
        src, "// 编辑：提交所有字段（空字符串表示清空，后端会判断）\n      await updateChannel(form.id, "
    )
    # spread 展开的键也要算作「提交了」，否则扩展字段会被误判成未接线
    if "...extPayload" in create_block:
        create |= ext
    if "...extPayload" in update_block:
        update |= ext

    create_model = _model_fields("ChannelCreateRequest")
    update_model = _model_fields("ChannelUpdateRequest")

    # 解析本身要成立：表单控件有几十个，解析成个位数说明锚点或扫描器坏了
    assert len(form) >= 30, f"form 只解析出 {len(form)} 个键，扫描器可能失效：{sorted(form)}"

    # 1) 请求体 → 后端模型：多提交一个模型不认识的键，FastAPI 会静默丢弃
    assert create <= create_model, f"新增请求体有模型不接收的字段: {sorted(create - create_model)}"
    assert update <= update_model, f"编辑请求体有模型不接收的字段: {sorted(update - update_model)}"

    # 2) 控件 → 请求体：分分支检查，只接一半（C15 就是新增分支漏了）同样算缺口
    missing_create = form - set(UI_ONLY) - CREATE_SKIP - create
    assert not missing_create, f"新增请求体漏提交这些控件: {sorted(missing_create)}"
    missing_update = form - set(UI_ONLY) - UPDATE_SKIP - update
    assert not missing_update, f"编辑请求体漏提交这些控件: {sorted(missing_update)}"

    # 3) 后端模型 → 控件：模型能存的字段，弹窗得能填（否则只能靠 API 改库）
    aliased = set(FIELD_ALIASES)
    no_control = create_model - form - aliased
    assert not no_control, f"后端可写但弹窗无控件: {sorted(no_control)}"
    no_control = update_model - form - aliased
    assert not no_control, f"后端可编辑但弹窗无控件: {sorted(no_control)}"

    # 4) C15 定点回归：新增分支必须显式提交 is_active，否则开关又是摆设
    assert "is_active" in create and "is_active" in create_model
    assert "is_active" in update and "is_active" in update_model

    # 5) 别名表不能空转：它指向的控件与模型字段都要真实存在
    for model_key, form_key in FIELD_ALIASES.items():
        assert model_key in create_model | update_model, f"别名表里的 {model_key} 已不在模型上"
        assert form_key in form, f"别名表里的控件 {form_key} 已不存在"


def test_channel_matrix_ignores_spread_by_expanding_ext_payload():
    """extPayload 的键必须真的被两个分支展开（否则扩展字段只在编辑态生效）。"""
    src = CHANNEL_VIEW.read_text(encoding="utf-8")
    _, ext = _object_after(src, "const extPayload = ")
    create_block, _ = _object_after(src, "await createChannel(")
    update_block, _ = _object_after(
        src, "// 编辑：提交所有字段（空字符串表示清空，后端会判断）\n      await updateChannel(form.id, "
    )
    assert ext, "extPayload 未解析出任何键"
    assert "...extPayload" in create_block, "新增分支未展开 extPayload ⇒ 扩展字段创建时丢失"
    assert "...extPayload" in update_block, "编辑分支未展开 extPayload ⇒ 扩展字段无法修改"
