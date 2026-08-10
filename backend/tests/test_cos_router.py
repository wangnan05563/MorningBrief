"""COS 配置与管理路由集成测试（同步 TestClient）。

依赖 conftest 的 client（get_db 已覆盖为内存库）、admin_token fixtures。
COS 客户端方法通过 monkeypatch cos_client 单例替换为 AsyncMock，无真实网络。

覆盖：
- 鉴权（缺 token 401）
- /cos/status（配置就绪状态）
- /cos/config（获取 / 保存）
- /cos/test-connection（连接测试）
- /cos/objects（列举目录树）
- /cos/folder（新建文件夹）
- /cos/object（删除对象）
- /cos/move（重命名 / 移动）
- /cos/metadata（元数据）
- /cos/download（下载地址，CDN 直链）
- /cos/upload（上传文件 multipart）
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


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def test_status_requires_admin(client):
    resp = client.get("/admin/api/v1/cos/status")
    assert resp.status_code == 401


def test_status_reports_unconfigured(client, admin_token, monkeypatch):
    # 显式复位 COS 凭证（开发环境 .env 可能已预填，需确保“未配置”语义）
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "COS_SECRET_ID", "")
    monkeypatch.setattr(s, "COS_SECRET_KEY", "")
    monkeypatch.setattr(s, "COS_BUCKET", "")
    resp = client.get(
        "/admin/api/v1/cos/status", headers=_admin_headers(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["configured"] is False


def test_status_reports_configured(client, admin_token, cos_configured):
    resp = client.get(
        "/admin/api/v1/cos/status", headers=_admin_headers(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["configured"] is True


def test_config_get_and_put(client, admin_token, cos_configured):
    # 保存配置（secret 末尾 4 位用于脱敏断言）
    resp = client.put(
        "/admin/api/v1/cos/config",
        json={
            "secret_id": "AKID1234",
            "secret_key": "sk5678",
            "region": "ap-shanghai",
            "bucket": "bkt2",
            "cdn_domain": "https://cdn.example.com",
        },
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    # 再次获取：脱敏 + 已保存
    resp2 = client.get(
        "/admin/api/v1/cos/config", headers=_admin_headers(admin_token)
    )
    data = resp2.json()["data"]
    assert data["configured"] is True
    assert data["secret_id"] == "****1234"
    assert data["secret_key"] == "****5678"
    assert data["region"] == "ap-shanghai"
    assert data["bucket"] == "bkt2"
    assert data["cdn_domain"] == "https://cdn.example.com"


def test_config_put_ignores_masked_secret(client, admin_token, cos_configured):
    # 先写入真实值
    client.put(
        "/admin/api/v1/cos/config",
        json={"secret_id": "AKIDreal", "secret_key": "skreal", "bucket": "bkt"},
        headers=_admin_headers(admin_token),
    )
    # 回传脱敏值 + 改 region
    resp = client.put(
        "/admin/api/v1/cos/config",
        json={"secret_id": "****real", "secret_key": "****real", "region": "ap-beijing"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = client.get(
        "/admin/api/v1/cos/config", headers=_admin_headers(admin_token)
    ).json()["data"]
    assert data["secret_id"] == "****real"
    assert data["region"] == "ap-beijing"


def test_test_connection_success(client, admin_token, cos_configured, monkeypatch):
    monkeypatch.setattr(
        cos_client_mod.cos_client,
        "list_objects_delimited",
        AsyncMock(return_value={"Contents": [], "CommonPrefixes": []}),
    )
    resp = client.post(
        "/admin/api/v1/cos/test-connection", headers=_admin_headers(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["success"] is True


def test_objects_list(client, admin_token, cos_configured, monkeypatch):
    monkeypatch.setattr(
        cos_client_mod.cos_client,
        "list_objects_delimited",
        AsyncMock(return_value={
            "Contents": [{"Key": "docs/a.txt", "Size": 10, "ContentType": "text/plain"}],
            "CommonPrefixes": [{"Prefix": "docs/sub/"}],
            "IsTruncated": False,
        }),
    )
    resp = client.get(
        "/admin/api/v1/cos/objects",
        params={"prefix": "docs/"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["folders"] == ["sub/"]
    assert data["files"][0]["name"] == "a.txt"


def test_create_folder(client, admin_token, cos_configured, monkeypatch):
    monkeypatch.setattr(cos_client_mod.cos_client, "put_object", AsyncMock())
    resp = client.post(
        "/admin/api/v1/cos/folder",
        json={"prefix": "photos/"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["key"] == "photos/"


def test_delete_object(client, admin_token, cos_configured, monkeypatch):
    monkeypatch.setattr(cos_client_mod.cos_client, "delete_object", AsyncMock())
    resp = client.delete(
        "/admin/api/v1/cos/object",
        params={"key": "docs/a.txt"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] == "docs/a.txt"


def test_move_object(client, admin_token, cos_configured, monkeypatch):
    monkeypatch.setattr(cos_client_mod.cos_client, "copy_object", AsyncMock())
    monkeypatch.setattr(cos_client_mod.cos_client, "delete_object", AsyncMock())
    resp = client.post(
        "/admin/api/v1/cos/move",
        json={"source_key": "a.txt", "dest_key": "b.txt"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["moved"] == 1


def test_metadata(client, admin_token, cos_configured, monkeypatch):
    monkeypatch.setattr(
        cos_client_mod.cos_client,
        "head_object",
        AsyncMock(return_value={
            "size": 99, "last_modified": "2026", "content_type": "text/plain", "etag": "e1",
        }),
    )
    resp = client.get(
        "/admin/api/v1/cos/metadata",
        params={"key": "a.txt"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["size"] == 99
    assert data["key"] == "a.txt"


def test_download_cdn(client, admin_token, cos_configured, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "COS_CDN_DOMAIN", "https://cdn.example.com")
    resp = client.get(
        "/admin/api/v1/cos/download",
        params={"key": "docs/a.txt"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["url"] == "https://cdn.example.com/docs/a.txt"


def test_upload_file(client, admin_token, cos_configured, monkeypatch):
    monkeypatch.setattr(cos_client_mod.cos_client, "put_object", AsyncMock())
    resp = client.post(
        "/admin/api/v1/cos/upload",
        files={"file": ("a.txt", b"hello world")},
        data={"prefix": "docs/"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["key"] == "docs/a.txt"
