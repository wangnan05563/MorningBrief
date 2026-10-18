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
    monkeypatch.setattr(_instance(), "object_exists", AsyncMock(return_value=False))
    svc = cos_storage_service.CosStorageService()
    result = await svc.upload_file("docs/a.txt", b"hello", "text/plain")
    assert result["key"] == "docs/a.txt"
    assert result["size"] == 5
    assert captured["key"] == "docs/a.txt"
    assert result["overwritten"] is False and result["backup_key"] is None


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


# ---- T00921：COS SDK 异常应转成语义化 BizError，而非冒泡成 500「服务内部错误」 ----

# qcloud_cos 真实异常类：CosServiceError(exec 双参不适用，业务层透传时保留原信息)
from qcloud_cos import CosClientError, CosServiceError  # noqa: E402


def _svc_error(message: str) -> CosServiceError:
    """构造携带可读原因 msg 的 COS 服务错误。

    真实 qcloud_cos 的 get_error_code() 用 digest_xml 解析响应 body，
    需要同时含 Code/Message/Resource/RequestId 四个节点；缺任一都会让
    get_error_code() 退化为 "Unknown"、str() 变成固定兜底串，导致关键词
    分类失效。这里按 COS 真实 XML 错误响应格式构造。
    """
    body = (
        "<Error>"
        f"<Code>{message}</Code>"
        f"<Message>{message}</Message>"
        "<Resource>test-bucket</Resource>"
        "<RequestId>test-request</RequestId>"
        "</Error>"
    )
    return CosServiceError("GET /", body, 403)


async def test_list_path_cos_service_error_translated(cos_configured, monkeypatch):
    """列表接口遇到 COS 服务异常时应抛 BizError 而非让异常冒泡为 500。"""
    monkeypatch.setattr(
        _instance(), "list_objects_delimited",
        AsyncMock(side_effect=_svc_error("AccessDenied: no permission")),
    )
    svc = cos_storage_service.CosStorageService()
    with pytest.raises(BizError) as exc_info:
        await svc.list_path("")
    # 转成业务异常（code=502），避免前端看到笼统的「服务内部错误」
    assert exc_info.value.code == 502


async def test_list_path_cos_client_error_translated(cos_configured, monkeypatch):
    """网络/连接类异常（CosClientError）同样转成 BizError，不冒泡为 500。"""
    monkeypatch.setattr(
        _instance(), "list_objects_delimited",
        AsyncMock(side_effect=CosClientError("connection reset")),
    )
    svc = cos_storage_service.CosStorageService()
    with pytest.raises(BizError) as exc_info:
        await svc.list_path("")
    assert exc_info.value.code == 502


async def test_upload_service_error_translated(cos_configured, monkeypatch):
    """上传接口同样受保护：SDK 异常不冒泡成 500。"""
    monkeypatch.setattr(_instance(), "object_exists", AsyncMock(return_value=False))
    monkeypatch.setattr(
        _instance(), "put_object",
        AsyncMock(side_effect=_svc_error("NoSuchBucket")),
    )
    svc = cos_storage_service.CosStorageService()
    with pytest.raises(BizError) as exc_info:
        await svc.upload_file("a.txt", b"data")
    assert exc_info.value.code == 502


def test_cos_sdk_message_classify():
    """语义化函数应把常见 COS 错误码映射为可读中文提示（对齐 test_connection 口径）。"""
    msg = cos_storage_service._cos_sdk_message(_svc_error("AccessDenied"))
    assert "凭证无效" in msg
    msg2 = cos_storage_service._cos_sdk_message(RuntimeError("NoSuchBucket"))
    assert "存储桶" in msg2
