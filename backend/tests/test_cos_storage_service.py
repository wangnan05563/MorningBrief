"""COS 存储管理服务单元测试。

通过 monkeypatch 把模块级 cos_client 单例的异步方法替换为 AsyncMock，
避免任何真实网络 / COS SDK 调用。is_cos_configured 通过 patch_cos_settings
自然返回 True（设置 Settings 单例的 COS_* 字段）。

覆盖：
- 列举（目录树解析、未配置守卫）
- 上传（路径穿越拒绝、正常）
- 下载 URL（CDN 直链优先 / 预签名回退）
- 删除（单文件 / 文件夹递归）
- 文件夹（新建占位对象）
- 重命名 / 移动（单文件 / 文件夹递归）
- 元数据
"""
import pytest
from unittest.mock import AsyncMock

from app.core.exceptions import BizError
from app.services import cos_storage_service


@pytest.fixture
def cos_configured(monkeypatch):
    """锁定 COS 配置为已知值，使 is_cos_configured 自然返回 True。"""
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "COS_SECRET_ID", "AKIDx")
    monkeypatch.setattr(s, "COS_SECRET_KEY", "skx")
    monkeypatch.setattr(s, "COS_BUCKET", "bkt")
    monkeypatch.setattr(s, "COS_REGION", "ap-guangzhou")
    monkeypatch.setattr(s, "COS_CDN_DOMAIN", "")
    return s


def _instance():
    """返回被各模块共享的 cos_client 单例（同一对象，直接 patch 其方法即可）。"""
    return cos_storage_service.cos_client


async def test_list_path_not_configured(monkeypatch):
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "COS_SECRET_ID", "")
    monkeypatch.setattr(s, "COS_SECRET_KEY", "")
    monkeypatch.setattr(s, "COS_BUCKET", "")
    svc = cos_storage_service.CosStorageService()
    with pytest.raises(BizError):
        await svc.list_path("")


async def test_list_path_parses_folders_and_files(cos_configured, monkeypatch):
    svc = cos_storage_service.CosStorageService()
    fake_resp = {
        "Contents": [
            {
                "Key": "folder/a.txt",
                "Size": 123,
                "LastModified": "2026-01-01T00:00:00",
                "ContentType": "text/plain",
            },
        ],
        "CommonPrefixes": [{"Prefix": "folder/sub/"}],
        "IsTruncated": False,
    }
    monkeypatch.setattr(
        _instance(), "list_objects_delimited", AsyncMock(return_value=fake_resp)
    )
    result = await svc.list_path("folder/")
    assert result["prefix"] == "folder/"
    assert result["folders"] == ["sub/"]
    assert len(result["files"]) == 1
    assert result["files"][0]["name"] == "a.txt"
    assert result["files"][0]["size"] == 123


async def test_upload_rejects_path_traversal(cos_configured):
    svc = cos_storage_service.CosStorageService()
    with pytest.raises(BizError):
        await svc.upload_file("../evil.txt", b"data")


async def test_upload_success(cos_configured, monkeypatch):
    captured = {}

    async def fake_put(Key, Body, ContentType=None):
        captured["key"] = Key
        captured["size"] = len(Body)

    monkeypatch.setattr(_instance(), "put_object", fake_put)
    svc = cos_storage_service.CosStorageService()
    result = await svc.upload_file("docs/a.txt", b"hello", "text/plain")
    assert result["key"] == "docs/a.txt"
    assert result["size"] == 5
    assert captured["key"] == "docs/a.txt"


async def test_get_download_url_cdn(cos_configured, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "COS_CDN_DOMAIN", "https://cdn.example.com")
    svc = cos_storage_service.CosStorageService()
    url = await svc.get_download_url("folder/a.txt")
    assert url == "https://cdn.example.com/folder/a.txt"


async def test_get_download_url_presigned(cos_configured, monkeypatch):
    monkeypatch.setattr(
        _instance(),
        "get_presigned_download_url",
        AsyncMock(return_value="https://presigned.example.com/x"),
    )
    svc = cos_storage_service.CosStorageService()
    url = await svc.get_download_url("a.txt")
    assert url == "https://presigned.example.com/x"


async def test_delete_file(cos_configured, monkeypatch):
    deleted = {}
    monkeypatch.setattr(
        _instance(), "delete_object", AsyncMock(side_effect=lambda **k: deleted.update(k))
    )
    svc = cos_storage_service.CosStorageService()
    await svc.delete_file("docs/a.txt")
    assert deleted["Key"] == "docs/a.txt"


async def test_create_folder(cos_configured, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        _instance(), "put_object", AsyncMock(side_effect=lambda **k: captured.update(k))
    )
    svc = cos_storage_service.CosStorageService()
    result = await svc.create_folder("photos/")
    assert result["key"] == "photos/"
    assert captured["Key"] == "photos/"


async def test_delete_folder_recursive(cos_configured, monkeypatch):
    monkeypatch.setattr(
        _instance(),
        "list_objects_delimited",
        AsyncMock(return_value={"Contents": [{"Key": "d/x.txt"}, {"Key": "d/y.txt"}], "IsTruncated": False}),
    )
    batches = []
    monkeypatch.setattr(
        _instance(),
        "delete_objects",
        AsyncMock(side_effect=lambda keys: batches.append(keys)),
    )
    svc = cos_storage_service.CosStorageService()
    count = await svc.delete_folder("d/")
    assert count == 2
    assert batches and len(batches[0]) == 2


async def test_move_file(cos_configured, monkeypatch):
    monkeypatch.setattr(_instance(), "copy_object", AsyncMock())
    monkeypatch.setattr(_instance(), "delete_object", AsyncMock())
    svc = cos_storage_service.CosStorageService()
    result = await svc.move_object("a.txt", "b.txt")
    assert result["moved"] == 1


async def test_move_folder_recursive(cos_configured, monkeypatch):
    monkeypatch.setattr(
        _instance(),
        "list_objects_delimited",
        AsyncMock(return_value={
            "Contents": [{"Key": "old/a.txt"}, {"Key": "old/b.txt"}],
            "IsTruncated": False,
        }),
    )
    copied = []
    monkeypatch.setattr(
        _instance(), "copy_object", AsyncMock(side_effect=lambda **k: copied.append(k))
    )
    monkeypatch.setattr(_instance(), "delete_objects", AsyncMock())
    svc = cos_storage_service.CosStorageService()
    result = await svc.move_object("old/", "new/")
    assert result["moved"] == 2
    # 目标 key 前缀已替换为 new/
    assert copied[0]["Key"].startswith("new/")


async def test_get_metadata(cos_configured, monkeypatch):
    monkeypatch.setattr(
        _instance(),
        "head_object",
        AsyncMock(return_value={
            "size": 100, "last_modified": "2026", "content_type": "text/plain", "etag": "abc",
        }),
    )
    svc = cos_storage_service.CosStorageService()
    meta = await svc.get_metadata("a.txt")
    assert meta["size"] == 100
    assert meta["key"] == "a.txt"
    assert meta["etag"] == "abc"
