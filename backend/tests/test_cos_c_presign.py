"""C 端 COS 预签名上传端点集成测试（同步 TestClient）。

依赖 conftest 的 client（get_db 已覆盖为内存库）、user_token fixtures。
COS 客户端方法通过 monkeypatch cos_client 单例替换为 AsyncMock，无真实网络。

覆盖：
- 鉴权（缺 token 401）
- /cos/presign-upload：COS 未配置返回 cos_enabled=false
- /cos/presign-upload：COS 已配置返回 upload_url / object_url / key / content_type
- Key 强制落在 user:{user_id}/ 前缀（防越权）
- 扩展名白名单：拒绝 .exe
- 空文件名拒绝
- CDN 域名已配置时 object_url 走 CDN 直链
- file_size 超过 COS_AVATAR_MAX_SIZE_MB 上限拒绝（400）
- COS_OBJECTS_PUBLIC_READ=False（私有读）时 object_url 回退预签名私有 URL
"""
import pytest
from unittest.mock import AsyncMock

from app.cos import client as cos_client_mod


@pytest.fixture
def cos_configured(monkeypatch):
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "COS_SECRET_ID", "AKIDx")
    monkeypatch.setattr(s, "COS_SECRET_KEY", "skx")
    monkeypatch.setattr(s, "COS_BUCKET", "bkt")
    monkeypatch.setattr(s, "COS_REGION", "ap-guangzhou")
    monkeypatch.setattr(s, "COS_CDN_DOMAIN", "")
    return s


def _user_headers(user_token):
    return {"Authorization": f"Bearer {user_token['token']}"}


def test_presign_requires_auth(client):
    resp = client.post("/api/v1/cos/presign-upload", json={"filename": "a.jpg"})
    assert resp.status_code == 401


def test_presign_unconfigured_returns_disabled(client, user_token, monkeypatch):
    # 显式复位 COS 凭证，确保“未配置”语义（开发环境 .env 可能已预填）
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "COS_SECRET_ID", "")
    monkeypatch.setattr(s, "COS_SECRET_KEY", "")
    monkeypatch.setattr(s, "COS_BUCKET", "")
    resp = client.post(
        "/api/v1/cos/presign-upload",
        json={"filename": "a.jpg"},
        headers=_user_headers(user_token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["cos_enabled"] is False


def test_presign_configured_returns_urls(client, user_token, cos_configured, monkeypatch):
    monkeypatch.setattr(
        cos_client_mod.cos_client,
        "get_presigned_upload_url",
        AsyncMock(return_value="https://presigned.example.com/put?sign=xyz"),
    )
    resp = client.post(
        "/api/v1/cos/presign-upload",
        json={"filename": "avatar.PNG"},
        headers=_user_headers(user_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["cos_enabled"] is True
    assert data["upload_url"].startswith("https://presigned.example.com/put")
    # Key 强制 user:{user_id}/ 前缀；user_token 的 sub 为 "1"
    assert data["key"].startswith("user:1/")
    assert data["key"].endswith(".png")
    # 默认 content_type 为 image/jpeg（客户端 PUT 时自由带）
    assert data["content_type"] == "image/jpeg"
    # 未配置 CDN 时 object_url 走 COS 默认域名
    assert data["object_url"].startswith("https://bkt.cos.ap-guangzhou.myqcloud.com/user:1/")


def test_presign_key_scoped_to_user(client, user_token, cos_configured, monkeypatch):
    monkeypatch.setattr(
        cos_client_mod.cos_client,
        "get_presigned_upload_url",
        AsyncMock(return_value="https://x/put"),
    )
    resp = client.post(
        "/api/v1/cos/presign-upload",
        json={"filename": "a.jpg"},
        headers=_user_headers(user_token),
    )
    key = resp.json()["data"]["key"]
    # 越权兜底：Key 必须以本人前缀开头
    assert key.startswith("user:1/")


def test_presign_rejects_bad_extension(client, user_token, cos_configured, monkeypatch):
    monkeypatch.setattr(
        cos_client_mod.cos_client,
        "get_presigned_upload_url",
        AsyncMock(return_value="https://x/put"),
    )
    resp = client.post(
        "/api/v1/cos/presign-upload",
        json={"filename": "evil.exe"},
        headers=_user_headers(user_token),
    )
    assert resp.status_code == 400


def test_presign_rejects_empty_filename(client, user_token, cos_configured, monkeypatch):
    monkeypatch.setattr(
        cos_client_mod.cos_client,
        "get_presigned_upload_url",
        AsyncMock(return_value="https://x/put"),
    )
    resp = client.post(
        "/api/v1/cos/presign-upload",
        json={"filename": ""},
        headers=_user_headers(user_token),
    )
    assert resp.status_code == 400


def test_presign_cdn_object_url(client, user_token, cos_configured, monkeypatch):
    monkeypatch.setattr(
        cos_client_mod.cos_client,
        "get_presigned_upload_url",
        AsyncMock(return_value="https://x/put"),
    )
    # 配置 CDN 域名（直接改已注入的 settings 对象，避免重复 import）
    monkeypatch.setattr(cos_configured, "COS_CDN_DOMAIN", "https://cdn.example.com")
    resp = client.post(
        "/api/v1/cos/presign-upload",
        json={"filename": "a.jpg"},
        headers=_user_headers(user_token),
    )
    data = resp.json()["data"]
    assert data["object_url"] == f"https://cdn.example.com/{data['key']}"


def test_presign_rejects_oversized_file(client, user_token, cos_configured, monkeypatch):
    # 已配置上限默认 5MB；声明 6MB 应被拒绝（预签名场景服务端读不到 body，
    # 只能依赖客户端声明式 file_size 上限校验）
    monkeypatch.setattr(
        cos_client_mod.cos_client,
        "get_presigned_upload_url",
        AsyncMock(return_value="https://x/put"),
    )
    resp = client.post(
        "/api/v1/cos/presign-upload",
        json={"filename": "a.jpg", "file_size": 6 * 1024 * 1024},
        headers=_user_headers(user_token),
    )
    assert resp.status_code == 400


def test_presign_private_read_falls_back_presigned(
    client, user_token, cos_configured, monkeypatch
):
    # Bucket 私有读：object_url 回退预签名私有 URL（与 get_download_url 口径一致），
    # 避免公开直链 403。验证 HIGH 修复后语义统一。
    monkeypatch.setattr(cos_configured, "COS_OBJECTS_PUBLIC_READ", False)
    monkeypatch.setattr(
        cos_client_mod.cos_client,
        "get_presigned_upload_url",
        AsyncMock(return_value="https://x/put"),
    )
    resp = client.post(
        "/api/v1/cos/presign-upload",
        json={"filename": "a.jpg"},
        headers=_user_headers(user_token),
    )
    data = resp.json()["data"]
    assert data["cos_enabled"] is True
    assert "presigned" in data["object_url"]
