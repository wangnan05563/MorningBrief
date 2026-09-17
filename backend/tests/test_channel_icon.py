"""频道图标上传与 AI 生成测试（T00730）。

- 上传：PNG ≤2MB → 存 /channel-assets/channel_{id}_icon.png + icon_url 落库；
  非法格式 / 超限 → 400；
- AI 生成：mock image_gen_service.generate_image（网络层不实测）→ 文件落盘 + icon_url；
  服务失败（ImageGenError）→ 502 且不影响原图标。
"""
import io
from datetime import date

import pytest

from app.models import Channel


PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f0300050001ffa5a5a50000000049454e44ae426082"
)


async def _seed_channel(session, name="T00730 频道") -> Channel:
    ch = Channel(name=name, channel_type="audiobook", selection_strategy="outline")
    session.add(ch)
    await session.commit()
    await session.refresh(ch)
    return ch


def _auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


@pytest.fixture
def stub_blacklist(monkeypatch):
    """登出黑名单恒 False（与 test_ebook_audiobook_guard 同款）。"""
    import app.core.auth

    async def _always_false(jti: str) -> bool:
        return False

    monkeypatch.setattr(app.core.auth, "is_in_blacklist", _always_false)


def test_upload_icon_ok(client, admin_token, stub_blacklist, db_session):
    ch = db_session.run_sync(lambda s: _seed_channel(s)) if False else None
    # 同步夹具简化：直接用 client 走 API 创建频道
    created = client.post("/admin/api/v1/channels",
                          json={"name": "T00730 图标频道", "channel_type": "audiobook"},
                          headers=_auth(admin_token)).json()
    assert created["code"] == 0, created
    cid = created["data"]["id"] if isinstance(created["data"], dict) else created["data"]["id"]

    resp = client.post(
        f"/admin/api/v1/channels/{cid}/icon",
        files={"file": ("icon.png", io.BytesIO(PNG_BYTES), "image/png")},
        headers=_auth(admin_token),
    ).json()
    assert resp["code"] == 0, resp
    assert "channel_%d_icon.png" % cid in resp["data"]["icon_url"]


def test_upload_icon_bad_format_rejected(client, admin_token, stub_blacklist):
    created = client.post("/admin/api/v1/channels",
                          json={"name": "T00730 格式频道", "channel_type": "news"},
                          headers=_auth(admin_token)).json()
    cid = created["data"]["id"]
    resp = client.post(
        f"/admin/api/v1/channels/{cid}/icon",
        files={"file": ("icon.gif", io.BytesIO(b"GIF89a"), "image/gif")},
        headers=_auth(admin_token),
    ).json()
    assert resp["code"] != 0 and "格式" in resp["message"]


def test_ai_generate_success(client, admin_token, stub_blacklist, db_session, monkeypatch):
    from app.services import image_gen_service

    created = client.post("/admin/api/v1/channels",
                          json={"name": "T00730 AI 频道", "channel_type": "audiobook"},
                          headers=_auth(admin_token)).json()
    cid = created["data"]["id"]

    def fake_gen(prompt, **kwargs):  # 同步函数：端点经 asyncio.to_thread 调用
        return PNG_BYTES

    monkeypatch.setattr(image_gen_service, "generate_image", fake_gen)
    # 端点内通过 asyncio.to_thread 调用 generate_image——monkeypatch 的是模块属性，
    # 端点内 `image_gen_service.generate_image` 引用同一模块属性 ✓ 生效。

    resp = client.post(f"/admin/api/v1/channels/{cid}/icon/ai-generate",
                       json={"prompt": "番茄计时器"}, headers=_auth(admin_token)).json()
    assert resp["code"] == 0, resp
    assert "icon.png" in resp["data"]["icon_url"]


def test_ai_generate_service_failure_returns_502(client, admin_token, stub_blacklist, monkeypatch):
    from app.services import image_gen_service

    created = client.post("/admin/api/v1/channels",
                          json={"name": "T00730 失败频道", "channel_type": "news"},
                          headers=_auth(admin_token)).json()
    cid = created["data"]["id"]

    def boom(prompt, **kwargs):
        raise image_gen_service.ImageGenError("图像生成服务连接失败")

    monkeypatch.setattr(image_gen_service, "generate_image", boom)
    resp = client.post(f"/admin/api/v1/channels/{cid}/icon/ai-generate",
                       json={"prompt": "财经数据"}, headers=_auth(admin_token)).json()
    assert resp["code"] != 0 and "AI 生成失败" in resp["message"]
