"""频道类型枚举化（T02704 / FR-UX-405 收尾）。

`channel_type` 的取值此前只写在列注释和两处 pydantic 校验的元组里，
前端 `CHANNEL_TYPE` 字典只能手抄，门禁无法对账（`BACKEND_ENUM_OF` 只能置 null）。
本单把它提升为 `ChannelType(str, Enum)`：

- 值字符串保持不变，存量数据无需迁移；
- 模型默认值、新库 CHECK 约束、接口白名单都从枚举派生，新增类型只改一处；
- 前端字典改为与 `ChannelType` 对账（`npm run validate:nav`）。

`type_label` 仍是人工覆盖名：留空时后端如实回传 null，由展示层回落枚举标签，
不在后端编造一份中文（否则两处各写一半，改文案会漂移）。
"""
from app.models import Channel, ChannelType

BASE = "/admin/api/v1/channels"


def _auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def _create(client, admin_token, name, **extra):
    resp = client.post(BASE, json={"name": name, **extra}, headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


def test_channel_type_enum_values_are_stable():
    """枚举值就是前后端与存量数据的契约，顺序也影响报错文案与前端下拉顺序。"""
    assert [t.value for t in ChannelType] == ["news", "course", "audiobook"]


def test_channel_model_defaults_to_news_and_declares_check():
    col = Channel.__table__.c.channel_type
    assert col.default.arg == ChannelType.news.value, "默认值必须回到枚举，不能另写一份字面量"
    checks = {c.name: str(c.sqltext) for c in Channel.__table__.constraints if c.name}
    assert "ck_channel_type" in checks, "新库应由 create_all 建出 channel_type CHECK"
    for value in (t.value for t in ChannelType):
        assert f"'{value}'" in checks["ck_channel_type"]


def test_create_channel_type_defaults_to_enum_news(client, admin_token):
    data = _create(client, admin_token, "T02704 默认类型")
    assert data["channel_type"] == ChannelType.news.value


def test_all_enum_values_are_accepted_and_type_label_left_empty(client, admin_token):
    """三个枚举值端到端可写；type_label 留空时不得被后端编造成中文。"""
    for t in ChannelType:
        data = _create(client, admin_token, f"T02704 类型-{t.value}", channel_type=t.value)
        assert data["channel_type"] == t.value
        assert data["type_label"] is None, "留空即算人工未覆盖，回落标签是展示层的事"


def test_update_channel_type_to_another_enum_value(client, admin_token):
    data = _create(client, admin_token, "T02704 改名", channel_type=ChannelType.news.value)
    resp = client.put(f"{BASE}/{data['id']}", json={"channel_type": ChannelType.audiobook.value},
                      headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["channel_type"] == ChannelType.audiobook.value


def test_create_rejects_unregistered_channel_type(client, admin_token):
    resp = client.post(BASE, json={"name": "T02704 非法类型", "channel_type": "feature"},
                       headers=_auth(admin_token))
    assert resp.status_code == 400, resp.text
    assert "channel_type" in resp.json()["message"]


def test_update_rejects_unregistered_channel_type(client, admin_token):
    data = _create(client, admin_token, "T02704 更新非法", channel_type=ChannelType.news.value)
    resp = client.put(f"{BASE}/{data['id']}", json={"channel_type": "feature"},
                      headers=_auth(admin_token))
    assert resp.status_code == 400, resp.text
    assert "channel_type" in resp.json()["message"]
    # 拒绝后原值不得被写坏
    listed = client.get(BASE, headers=_auth(admin_token)).json()["data"]
    row = next(c for c in listed if c["id"] == data["id"])
    assert row["channel_type"] == ChannelType.news.value
