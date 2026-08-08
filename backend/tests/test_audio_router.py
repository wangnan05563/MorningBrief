"""audio 路由增量测试。

覆盖本次会话改动的三处关键点：
1. proxy_audio 的 SSRF 防护（放行配置的 COS 域名，拒绝其他主机 / 非 http(s) 协议）；
2. proxy_audio 对配置域名的放行与流式代理（mock COS 客户端，验证无网络依赖）；
3. list_audio 在打包态（本地 audio_cache 为空）回退到 DB 持久化 audio_url，
   且远端成品 path 不为 null（渲染友好文案）。
"""
from datetime import date

import pytest

from app.workflow.tts import uploader as uploader_mod


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


@pytest.fixture
def patch_cos_settings(monkeypatch):
    """将 COS 配置锁定为已知值，便于断言 SSRF 白名单行为。"""
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "COS_BUCKET", "morbucket")
    monkeypatch.setattr(s, "COS_REGION", "ap-beijing")
    monkeypatch.setattr(s, "COS_CDN_DOMAIN", "")
    return s


def test_proxy_audio_rejects_disallowed_host(client, admin_token, patch_cos_settings):
    """SSRF 防护：非配置 COS 域名的地址应被拒绝（包成 BizError，http_status=200）。"""
    resp = client.get(
        "/admin/api/v1/workflows/wf-1/audio/proxy",
        params={"url": "https://evil.example.com/tts/x.mp3"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["code"] != 0


def test_proxy_audio_rejects_non_http_scheme(client, admin_token, patch_cos_settings):
    """SSRF 防护：file:// 等非 http(s) 协议应被拒绝。"""
    resp = client.get(
        "/admin/api/v1/workflows/wf-1/audio/proxy",
        params={"url": "file:///etc/passwd"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["code"] != 0


def test_proxy_audio_allows_configured_bucket(client, admin_token, patch_cos_settings, monkeypatch):
    """配置的 COS 域名放行，且通过代理流式拉取对象（mock 掉真实网络）。"""
    # 占位：定义假流式读取与假响应对象（COS SDK 返回的是 dict，route 用 resp["Body"] 访问）
    class _FakeStream:
        def read(self, _n):
            return b""  # 一次性耗尽，模拟空对象

    class _FakeBody:
        def get_raw_stream(self):
            return _FakeStream()

    fake_client = type("C", (), {
        "get_object": staticmethod(lambda **_k: {"Body": _FakeBody()}),
    })()
    monkeypatch.setattr(uploader_mod, "_get_client", lambda: fake_client)

    url = "https://morbucket.cos.ap-beijing.myqcloud.com/tts/wf-1/1.mp3"
    resp = client.get(
        "/admin/api/v1/workflows/wf-1/audio/proxy",
        params={"url": url},
        headers=_admin_headers(admin_token),
    )
    # 成功路径返回 StreamingResponse：audio/mpeg，且不包 success() 外壳
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "audio/mpeg"


async def test_list_audio_remote_fallback_no_null_path(
    client, db_session, admin_token, patch_cos_settings
):
    """打包态（本地 audio_cache 为空）回退到 DB audio_url，且 path 不为 null。"""
    from app.models import Episode, Script

    db_session.add(Script(
        workflow_id="wf-1",
        episode_date=date(2026, 7, 8),
        full_text="测试稿件",
        segments=[{"seq": 1, "audio_url": "https://morbucket.cos.ap-beijing.myqcloud.com/tts/wf-1/1.mp3"}],
    ))
    db_session.add(Episode(
        date=date(2026, 7, 8),
        title="测试成品",
        duration=60,
        audio_url="https://morbucket.cos.ap-beijing.myqcloud.com/episodes/20260708/tech_wf-1.mp3",
        workflow_id="wf-1",
    ))
    await db_session.commit()

    resp = client.get(
        "/admin/api/v1/workflows/wf-1/audio",
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    # TTS 片段回退自 Script.segments，标记为远端、字节数未知(0)
    assert len(data["tts_dir"]) == 1
    assert data["tts_dir"][0]["remote"] is True
    assert data["tts_dir"][0]["size_bytes"] == 0

    # 成品回退自 Episode.audio_url，path 必须为可读文案而非 null
    assert data["episode_file"] is not None
    assert data["episode_file"]["remote"] is True
    assert data["episode_file"]["path"] == "云端(COS)"
    assert data["episode_file"]["path"] is not None
