"""TTS 模型下载路由集成测试（HTTP 层）。

用 TestClient 验证：
- POST /download-tts-models 对非本地引擎（edge）返回 400
- POST 对本地引擎（piper）返回 200 且 started=True，后台任务落状态为 success
- GET /download-tts-models/status 返回状态字典（需 admin 鉴权）
"""
import pytest

from app.routers.admin import ai_config as ai_config_router
from app.services import tts_model_manager as mgr


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


@pytest.fixture(autouse=True)
def _clear_state():
    mgr._DOWNLOAD_STATE.clear()
    yield
    mgr._DOWNLOAD_STATE.clear()


async def _fake_run(provider, **kwargs):
    """替代 run_download：直接把状态置为 success，避免真实联网下载。"""
    mgr._set_state(provider, status="success", message="ok", progress=1.0)
    return {"success": True}


def test_download_rejects_non_local_provider(client, admin_token):
    """非本地引擎（edge）不应触发下载，返回 400。"""
    resp = client.post(
        "/admin/api/v1/ai/download-tts-models",
        json={"provider": "edge"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 400
    assert "无需下载" in resp.json()["message"]


def test_download_piper_starts_and_succeeds(client, admin_token, monkeypatch):
    """piper 触发下载：接口立即返回 started，后台任务执行后状态为 success。"""
    monkeypatch.setattr(ai_config_router, "run_download", _fake_run)

    resp = client.post(
        "/admin/api/v1/ai/download-tts-models",
        json={
            "provider": "piper",
            "piper_voice": "zh_CN-huayan-medium",
            "piper_voice_dir": "./models/piper",
        },
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["started"] is True
    assert body["data"]["provider"] == "piper"

    # TestClient 同步跑完 background tasks，状态应为 success
    st = client.get(
        "/admin/api/v1/ai/download-tts-models/status",
        params={"provider": "piper"},
        headers=_admin_headers(admin_token),
    ).json()
    assert st["code"] == 0
    assert st["data"]["status"] == "success"


def test_status_requires_admin(client):
    """状态接口需 admin 鉴权，未带 token 返回 401/403。"""
    resp = client.get(
        "/admin/api/v1/ai/download-tts-models/status",
        params={"provider": "piper"},
    )
    assert resp.status_code in (401, 403)
