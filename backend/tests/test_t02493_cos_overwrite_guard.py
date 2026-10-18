"""T02493 / FR-UX-205 上传可回退：同名检测、覆盖前快照、服务端拒绝静默覆盖。

原缺陷（H9）：`upload_file` 直接 put_object，重传同名对象即静默覆盖旧文件，
只有前端确认框拦着 —— 绕过页面（或列表快照过期）就没有任何把关。
现在由服务端把关，且覆盖前把旧对象复制到 .backup/<时间戳>/，让覆盖可回退。

cos_client 单例方法全部替换为 AsyncMock，无真实网络。
"""
from unittest.mock import AsyncMock

import pytest

from app.cos import client as cos_client_mod
from app.core.exceptions import BizError
from app.services import cos_storage_service
from app.services.cos_storage_service import CosStorageService, _human_size


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


def _instance():
    return cos_storage_service.cos_client


def _existing(monkeypatch, meta=None):
    """把「目标对象已存在、快照槽位空闲」装上，返回记录到调用的 dict。"""
    calls = {"put": [], "copy": []}

    async def fake_exists(Key):
        # 快照目录里的 Key 一律视为不存在，否则备份重名探测会一直追加后缀
        return ".backup/" not in Key

    monkeypatch.setattr(_instance(), "object_exists", fake_exists)
    monkeypatch.setattr(
        _instance(), "head_object",
        AsyncMock(return_value=meta or {"size": 2048, "last_modified": "Wed, 15 Oct 2026 08:00:00 GMT",
                                        "content_type": "audio/mpeg", "etag": "abc"}),
    )

    async def fake_put(Key, Body, ContentType=None):
        calls["put"].append(Key)

    async def fake_copy(SourceKey, Key):
        calls["copy"].append((SourceKey, Key))

    monkeypatch.setattr(_instance(), "put_object", fake_put)
    monkeypatch.setattr(_instance(), "copy_object", fake_copy)
    return calls


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


# ---- 服务层 ----

async def test_same_name_without_overwrite_is_rejected(cos_configured, monkeypatch):
    """同名 + 未确认覆盖 → 业务码 409，且不写入任何对象（旧行为是静默覆盖）。"""
    calls = _existing(monkeypatch)
    svc = CosStorageService()
    with pytest.raises(BizError) as exc_info:
        await svc.upload_file("audio/day/a.mp3", b"new", "audio/mpeg")
    assert exc_info.value.code == 409
    assert exc_info.value.http_status == 200  # 走统一信封，前端拦截器能拿到 message
    assert "同名文件已存在" in exc_info.value.message
    assert "audio/day/a.mp3" in exc_info.value.message
    assert "2.0 KB" in exc_info.value.message  # 大小可读，不是裸字节
    assert calls["put"] == [] and calls["copy"] == []


async def test_overwrite_snapshots_before_put(cos_configured, monkeypatch):
    """确认覆盖 → 先复制旧对象到 .backup/<时间戳>/，再写入新对象。"""
    calls = _existing(monkeypatch)
    svc = CosStorageService()
    result = await svc.upload_file("audio/day/a.mp3", b"new", "audio/mpeg", overwrite=True)

    backup_key = result["backup_key"]
    assert backup_key.startswith("audio/day/.backup/")
    assert backup_key.endswith("/a.mp3")
    assert calls["copy"] == [("audio/day/a.mp3", backup_key)]
    assert calls["put"] == ["audio/day/a.mp3"]
    # 备份必须发生在覆盖之前
    assert backup_key != "audio/day/a.mp3"
    assert result["overwritten"] is True
    assert result["previous"]["size"] == 2048


async def test_root_level_key_backup_path(cos_configured, monkeypatch):
    """桶根文件（无目录前缀）的快照落在 .backup/ 下，不能拼出前导 /。"""
    calls = _existing(monkeypatch)
    svc = CosStorageService()
    result = await svc.upload_file("a.mp3", b"new", overwrite=True)
    assert result["backup_key"].startswith(".backup/")
    assert calls["copy"][0][1] == result["backup_key"]


async def test_backup_key_never_overwrites_existing_snapshot(cos_configured, monkeypatch):
    """同一秒内连续覆盖：旧快照已被占用时追加 -1，不会覆盖掉上一次的备份。"""
    import datetime as dt_module

    class _FixedClock:
        @staticmethod
        def now():
            return dt_module.datetime(2026, 10, 18, 16, 0, 0)

    monkeypatch.setattr(cos_storage_service, "datetime", _FixedClock)

    head = {"size": 1, "last_modified": "", "content_type": "", "etag": ""}
    occupied = {"d/a.mp3"}
    copies = []

    async def fake_exists(Key):
        return Key in occupied

    async def fake_copy(SourceKey, Key):
        copies.append((SourceKey, Key))
        occupied.add(Key)

    monkeypatch.setattr(_instance(), "object_exists", fake_exists)
    monkeypatch.setattr(_instance(), "head_object", AsyncMock(return_value=head))
    monkeypatch.setattr(_instance(), "copy_object", fake_copy)
    monkeypatch.setattr(_instance(), "put_object", AsyncMock())

    svc = CosStorageService()
    first = await svc.upload_file("d/a.mp3", b"v1", overwrite=True)
    second = await svc.upload_file("d/a.mp3", b"v2", overwrite=True)

    assert first["backup_key"] == "d/.backup/20261018-160000/a.mp3"
    assert second["backup_key"] == "d/.backup/20261018-160000/a.mp3-1"
    assert copies[1] == ("d/a.mp3", second["backup_key"])


async def test_backup_failure_aborts_overwrite(cos_configured, monkeypatch):
    """快照失败必须中止覆盖：宁可上传失败，也不能退化成静默覆盖。"""
    calls = _existing(monkeypatch)
    monkeypatch.setattr(
        _instance(), "copy_object",
        AsyncMock(side_effect=cos_storage_service.CosClientError("网络中断")),
    )
    svc = CosStorageService()
    with pytest.raises(BizError) as exc_info:
        await svc.upload_file("d/a.mp3", b"new", overwrite=True)
    assert "覆盖前快照备份失败" in exc_info.value.message
    assert calls["put"] == []


async def test_new_object_uploads_without_backup(cos_configured, monkeypatch):
    """对象不存在时按原语义直接上传，不查元数据也不做快照。"""
    put = AsyncMock()
    monkeypatch.setattr(_instance(), "object_exists", AsyncMock(return_value=False))
    monkeypatch.setattr(_instance(), "head_object", AsyncMock())
    monkeypatch.setattr(_instance(), "copy_object", AsyncMock())
    monkeypatch.setattr(_instance(), "put_object", put)
    svc = CosStorageService()
    result = await svc.upload_file("d/new.mp3", b"data")
    assert result == {
        "key": "d/new.mp3", "size": 4, "content_type": "",
        "overwritten": False, "previous": None, "backup_key": None,
    }
    assert put.await_count == 1
    _instance().copy_object.assert_not_awaited()
    _instance().head_object.assert_not_awaited()


async def test_object_exists_reports_metadata(cos_configured, monkeypatch):
    """存在性检查回带元数据，供前端在确认框里展示影响对象。"""
    monkeypatch.setattr(_instance(), "object_exists", AsyncMock(return_value=True))
    monkeypatch.setattr(
        _instance(), "head_object",
        AsyncMock(return_value={"size": 10, "last_modified": "x", "content_type": "text/plain", "etag": "e"}),
    )
    data = await CosStorageService().object_exists("d/a.txt")
    assert data == {
        "key": "d/a.txt", "exists": True, "size": 10,
        "last_modified": "x", "content_type": "text/plain",
    }


async def test_object_exists_missing_returns_false(cos_configured, monkeypatch):
    """不存在不是错误：exists=False，且不查 head。"""
    monkeypatch.setattr(_instance(), "object_exists", AsyncMock(return_value=False))
    head = AsyncMock()
    monkeypatch.setattr(_instance(), "head_object", head)
    data = await CosStorageService().object_exists("d/none.txt")
    assert data["exists"] is False and data["size"] == 0
    head.assert_not_awaited()


async def test_object_exists_not_configured(monkeypatch):
    from app.config import get_settings

    s = get_settings()
    for field in ("COS_SECRET_ID", "COS_SECRET_KEY", "COS_BUCKET"):
        monkeypatch.setattr(s, field, "")
    with pytest.raises(BizError) as exc_info:
        await CosStorageService().object_exists("d/a.txt")
    assert "COS 未配置" in exc_info.value.message


async def test_object_exists_rejects_traversal(cos_configured):
    with pytest.raises(BizError):
        await CosStorageService().object_exists("../secret")


def test_human_size_readable():
    assert _human_size(0) == "0 B"
    assert _human_size(1536) == "1.5 KB"
    assert _human_size(5 * 1024 * 1024) == "5.0 MB"
    assert _human_size(None) == "大小未知"


async def test_backup_probe_gives_up_after_cap(cos_configured, monkeypatch):
    """快照槽位探测有上限：任何情况下都不能无限循环（回归防护）。"""
    monkeypatch.setattr(_instance(), "object_exists", AsyncMock(return_value=True))
    monkeypatch.setattr(
        _instance(), "head_object",
        AsyncMock(return_value={"size": 1, "last_modified": "", "content_type": "", "etag": ""}),
    )
    put = AsyncMock()
    monkeypatch.setattr(_instance(), "put_object", put)
    monkeypatch.setattr(_instance(), "copy_object", AsyncMock())
    svc = CosStorageService()
    with pytest.raises(BizError) as exc_info:
        await svc.upload_file("d/a.mp3", b"v", overwrite=True)
    assert "同一秒内已有" in exc_info.value.message
    put.assert_not_awaited()


# ---- 路由层（信封与参数贯通） ----

def _route_existing(cos_configured, monkeypatch):
    """目标对象存在、快照槽位空闲（与真实桶语义一致，避免探测死循环）。"""
    async def fake_exists(Key):
        return ".backup/" not in Key

    monkeypatch.setattr(cos_client_mod.cos_client, "object_exists", fake_exists)
    monkeypatch.setattr(
        cos_client_mod.cos_client, "head_object",
        AsyncMock(return_value={"size": 33, "last_modified": "", "content_type": "", "etag": ""}),
    )


def test_upload_route_rejects_same_name(client, admin_token, cos_configured, monkeypatch):
    _route_existing(cos_configured, monkeypatch)
    put = AsyncMock()
    monkeypatch.setattr(cos_client_mod.cos_client, "put_object", put)
    resp = client.post(
        "/admin/api/v1/cos/upload",
        files={"file": ("a.txt", b"hello world")},
        data={"prefix": "docs/"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 409
    assert "已拒绝覆盖上传" in body["message"]
    put.assert_not_awaited()


def test_upload_route_overwrite_returns_backup_key(
    client, admin_token, cos_configured, monkeypatch
):
    _route_existing(cos_configured, monkeypatch)
    monkeypatch.setattr(cos_client_mod.cos_client, "put_object", AsyncMock())
    monkeypatch.setattr(cos_client_mod.cos_client, "copy_object", AsyncMock())
    resp = client.post(
        "/admin/api/v1/cos/upload",
        files={"file": ("a.txt", b"hello world")},
        data={"prefix": "docs/", "overwrite": "true"},
        headers=_admin_headers(admin_token),
    )
    body = resp.json()
    assert body["code"] == 0
    backup_key = body["data"]["backup_key"]
    assert backup_key.startswith("docs/.backup/")
    assert "旧文件已备份至" in body["message"]


def test_exists_route_reports_envelope(client, admin_token, cos_configured, monkeypatch):
    monkeypatch.setattr(cos_client_mod.cos_client, "object_exists", AsyncMock(return_value=True))
    monkeypatch.setattr(
        cos_client_mod.cos_client, "head_object",
        AsyncMock(return_value={"size": 7, "last_modified": "x", "content_type": "audio/mpeg", "etag": "e"}),
    )
    resp = client.get(
        "/admin/api/v1/cos/exists", params={"key": "audio/a.mp3"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == {
        "key": "audio/a.mp3", "exists": True, "size": 7,
        "last_modified": "x", "content_type": "audio/mpeg",
    }


def test_exists_route_requires_admin(client):
    resp = client.get("/admin/api/v1/cos/exists", params={"key": "a"})
    assert resp.status_code == 401
