"""频道级「素材周期回溯天数」(material_lookback_days) 透传与校验测试。

覆盖三个层面：
1. 请求体校验（ChannelCreateRequest / ChannelUpdateRequest）：合法值接受、非法值拒绝。
2. ChannelService 透传：create/update 写入并回读；update 传 None 可清空。
3. 管理端 API 端到端：POST/PUT 回显该字段，_channel_to_dict 序列化一致。

纯单元 + 内存 DB，无外部依赖。
"""
import pytest

from app.routers.admin.channels import ChannelCreateRequest, ChannelUpdateRequest
from app.services.channel_service import ChannelService

# 合法值：None（继承动态）/ 1 / 30 / 90（上限边界）
_VALID = [None, 1, 30, 90]
# 非法值：0 / 负数 / 超过 90 上限，均应在校验阶段被 ValueError 拒绝
_INVALID = [0, -1, -5, 91, 100]


@pytest.mark.parametrize("days", _VALID)
def test_create_request_accepts_valid_days(days):
    req = ChannelCreateRequest(name="测试频道", material_lookback_days=days)
    assert req.material_lookback_days == days


@pytest.mark.parametrize("days", _VALID)
def test_update_request_accepts_valid_days(days):
    req = ChannelUpdateRequest(material_lookback_days=days)
    assert req.material_lookback_days == days


@pytest.mark.parametrize("bad", _INVALID)
def test_create_request_rejects_invalid_days(bad):
    with pytest.raises(ValueError):
        ChannelCreateRequest(name="测试频道", material_lookback_days=bad)


@pytest.mark.parametrize("bad", _INVALID)
def test_update_request_rejects_invalid_days(bad):
    with pytest.raises(ValueError):
        ChannelUpdateRequest(material_lookback_days=bad)


async def test_service_create_persists_lookback_days(db_session):
    """create_channel 写入 material_lookback_days 并可在回读对象中取到。"""
    svc = ChannelService(db_session)
    ch = await svc.create_channel(
        name="素材稀疏频道", material_lookback_days=30,
    )
    # 回读对象字段已写入
    assert ch.material_lookback_days == 30
    # 重新从 DB 取，确认已落库（非仅内存）
    reread = await svc.get_channel(ch.id)
    assert reread.material_lookback_days == 30


async def test_service_create_default_is_none(db_session):
    """未传该字段时默认 None（继承系统动态回溯）。"""
    svc = ChannelService(db_session)
    ch = await svc.create_channel(name="默认回溯频道")
    assert ch.material_lookback_days is None


async def test_service_update_sets_and_clears_lookback_days(db_session):
    """update_channel 可设置该字段；传 None 可清空（运营取消自定义回溯）。"""
    svc = ChannelService(db_session)
    ch = await svc.create_channel(name="可改回溯频道")

    # 先设为 14 天
    updated = await svc.update_channel(channel_id=ch.id, material_lookback_days=14)
    assert updated.material_lookback_days == 14

    # 再传 None 清空（回退继承动态）
    cleared = await svc.update_channel(channel_id=ch.id, material_lookback_days=None)
    assert cleared.material_lookback_days is None


async def test_api_create_echoes_lookback_days(client, admin_token, db_session):
    """POST /admin/api/v1/channels 回显 material_lookback_days，_channel_to_dict 含该字段。"""
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    resp = client.post(
        "/admin/api/v1/channels",
        json={"name": "API回溯频道", "material_lookback_days": 25},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["material_lookback_days"] == 25
    assert "material_lookback_days" in body["data"]


async def test_api_update_echoes_and_clears_lookback_days(client, admin_token, db_session):
    """PUT 更新该字段；传 null 清空。"""
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    created = client.post(
        "/admin/api/v1/channels",
        json={"name": "API改回溯频道", "material_lookback_days": 25},
        headers=headers,
    ).json()["data"]
    cid = created["id"]

    # 改为 40 天
    resp = client.put(
        f"/admin/api/v1/channels/{cid}",
        json={"material_lookback_days": 40},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["material_lookback_days"] == 40

    # 传 null 清空
    resp = client.put(
        f"/admin/api/v1/channels/{cid}",
        json={"material_lookback_days": None},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["material_lookback_days"] is None
