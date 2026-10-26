"""T02608 / H19：COS 重命名·移动的目标同名把关（409 + 覆盖前快照 + 服务端冲突条数）。

原缺陷：`move_object` 直接 `copy_object`——COS 复制即覆盖，目标已存在时那个被换掉的对象
连一条提示都没有。上传路径在 T02493 已经改成「服务端检测 + 确认后先备份」，
移动是同族漏网：H19 与 H9 是同一件事，只是入口不同。

cos_client 单例方法全部替换成内存假桶（_bucket），无真实网络。
"""
import pytest

from app.core.exceptions import BizError
from app.services.cos_storage_service import CosStorageService


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
    from app.services import cos_storage_service

    return cos_storage_service.cos_client


def _bucket(monkeypatch, objects: dict[str, int]):
    """装一个内存桶：exists/head/list/copy/delete 全部同步它，返回可断言的 state。"""
    state = {"objects": dict(objects), "copied": [], "deleted": [], "fail_backup": False}

    async def fake_exists(Key):
        # 快照槽位一律视为空闲，否则同一秒连续覆盖会无限追加后缀
        if ".backup/" in Key:
            return False
        return Key in state["objects"]

    async def fake_head(Key):
        if ".backup/" in Key:
            return {"size": 0, "last_modified": "", "content_type": "", "etag": ""}
        return {
            "size": state["objects"].get(Key, 0),
            "last_modified": "Wed, 15 Oct 2026 08:00:00 GMT",
            "content_type": "audio/mpeg",
            "etag": "e",
        }

    async def fake_list(prefix="", delimiter="/", marker="", max_keys=1000):
        keys = sorted(
            k for k in state["objects"] if k.startswith(prefix) and ".backup/" not in k
        )
        return {
            "Contents": [{"Key": k, "Size": state["objects"][k]} for k in keys],
            "IsTruncated": False,
        }

    async def fake_copy(SourceKey, Key):
        if state["fail_backup"] and ".backup/" in Key:
            # 用 BizError 模拟 SDK 失败经 _cos_call 转换后的形态：快照失败必须中止覆盖
            raise BizError(code=502, message="COS 服务调用失败")
        state["copied"].append((SourceKey, Key))
        state["objects"][Key] = state["objects"].get(SourceKey, 0)

    async def fake_delete(Key):
        state["deleted"].append(Key)
        state["objects"].pop(Key, None)

    async def fake_delete_objects(keys):
        state["deleted"].extend(keys)
        for k in keys:
            state["objects"].pop(k, None)

    monkeypatch.setattr(_instance(), "object_exists", fake_exists)
    monkeypatch.setattr(_instance(), "head_object", fake_head)
    monkeypatch.setattr(_instance(), "list_objects_delimited", fake_list)
    monkeypatch.setattr(_instance(), "copy_object", fake_copy)
    monkeypatch.setattr(_instance(), "delete_object", fake_delete)
    monkeypatch.setattr(_instance(), "delete_objects", fake_delete_objects)
    return state


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


# ---- 单文件 ----

async def test_move_to_free_key_does_not_snapshot(cos_configured, monkeypatch):
    """目标不存在时行为不变：一次复制 + 一次删除，不多做快照，也不报覆盖。"""
    state = _bucket(monkeypatch, {"a.txt": 10})
    result = await CosStorageService().move_object("a.txt", "b.txt")

    assert result == {"moved": 1, "overwritten": 0, "backup_keys": []}
    assert state["copied"] == [("a.txt", "b.txt")]
    assert state["deleted"] == ["a.txt"]


async def test_move_same_name_without_overwrite_is_rejected(cos_configured, monkeypatch):
    """同名且未确认覆盖 → 业务码 409，且一个字节都不动（旧行为是静默换掉）。"""
    state = _bucket(monkeypatch, {"a.txt": 10, "b.txt": 99})
    with pytest.raises(BizError) as exc_info:
        await CosStorageService().move_object("a.txt", "b.txt")

    assert exc_info.value.code == 409
    assert exc_info.value.http_status == 200  # 统一信封，前端拦截器拿得到 message
    assert "b.txt" in exc_info.value.message
    assert "99 B" in exc_info.value.message  # 点名目标与当前大小，不是「操作失败」
    assert exc_info.value.data["conflict_count"] == 1
    assert state["copied"] == [] and state["deleted"] == []
    assert "b.txt" in state["objects"] and "a.txt" in state["objects"]


async def test_move_overwrite_snapshots_target_before_copy(cos_configured, monkeypatch):
    """确认覆盖 → 先把目标旧对象复制进 .backup/，再复制源，最后删源。"""
    state = _bucket(monkeypatch, {"a.txt": 10, "b.txt": 99})
    result = await CosStorageService().move_object("a.txt", "b.txt", overwrite=True)

    backup = result["backup_keys"][0]
    assert backup.startswith(".backup/") and backup.endswith("/b.txt")
    # 顺序即正确性：备份必须排在覆盖之前
    assert state["copied"] == [("b.txt", backup), ("a.txt", "b.txt")]
    assert state["deleted"] == ["a.txt"]
    assert result["overwritten"] == 1


async def test_move_snapshot_failure_aborts_overwrite(cos_configured, monkeypatch):
    """快照失败必须中止：宁可移动失败，也不能退化成静默覆盖。"""
    state = _bucket(monkeypatch, {"a.txt": 10, "b.txt": 99})
    state["fail_backup"] = True
    with pytest.raises(BizError) as exc_info:
        await CosStorageService().move_object("a.txt", "b.txt", overwrite=True)

    assert "覆盖前快照备份失败，已中止覆盖" in exc_info.value.message
    assert state["copied"] == [] and state["deleted"] == []
    # 源与目标都还在——中止不能只做到一半
    assert "a.txt" in state["objects"] and "b.txt" in state["objects"]


# ---- 文件夹（批量覆盖） ----

async def test_folder_preview_counts_conflicts_from_server(cos_configured, monkeypatch):
    """冲突条数由服务端实测：old/ 三个对象里有两个在 new/ 已存在。"""
    _bucket(monkeypatch, {"old/a.txt": 5, "old/b.txt": 7, "old/c.txt": 9, "new/a.txt": 111,
                          "new/c.txt": 222, "new/z.txt": 1})
    data = await CosStorageService().move_preview("old/", "new/")

    assert data["is_prefix"] is True
    assert data["moved"] == 3
    assert data["conflict_count"] == 2
    assert [c["dest_key"] for c in data["conflicts"]] == ["new/a.txt", "new/c.txt"]
    assert data["conflicts"][0]["size"] == 111
    assert data["conflicts_truncated"] is False


async def test_folder_move_without_overwrite_rejects_whole_batch(cos_configured, monkeypatch):
    """批量覆盖风险：未确认时整个文件夹都不动，而不是「能移的移了」。"""
    state = _bucket(monkeypatch, {"old/a.txt": 5, "old/b.txt": 7, "old/c.txt": 9,
                                  "new/a.txt": 111, "new/c.txt": 222})
    with pytest.raises(BizError) as exc_info:
        await CosStorageService().move_object("old/", "new/")

    assert exc_info.value.code == 409
    assert "2 个同名对象" in exc_info.value.message
    assert exc_info.value.data["conflict_count"] == 2
    assert state["copied"] == [] and state["deleted"] == []
    assert "old/a.txt" in state["objects"]


async def test_folder_move_overwritten_equals_preview_count(cos_configured, monkeypatch):
    """预览说几条，实际就覆盖几条——两处共用同一份列举与映射，这是确认框诚实的前提。"""
    state = _bucket(monkeypatch, {"old/a.txt": 5, "old/b.txt": 7, "old/c.txt": 9,
                                  "new/a.txt": 111, "new/c.txt": 222})
    svc = CosStorageService()
    preview = await svc.move_preview("old/", "new/")
    result = await svc.move_object("old/", "new/", overwrite=True)

    assert result["overwritten"] == preview["conflict_count"]
    assert result["moved"] == preview["moved"] == 3
    backups = result["backup_keys"]
    assert len(backups) == 2 and all(k.startswith("new/.backup/") for k in backups)
    # 两份快照排在任何覆盖复制之前——先备份后动手，顺序错了就等于没备份
    assert state["copied"][:2] == [("new/a.txt", backups[0]), ("new/c.txt", backups[1])]
    assert ("old/a.txt", "new/a.txt") in state["copied"]
    assert ("old/c.txt", "new/c.txt") in state["copied"]
    assert state["deleted"] == ["old/a.txt", "old/b.txt", "old/c.txt"]


# ---- 路由层 ----

def test_move_route_rejects_same_name(client, admin_token, cos_configured, monkeypatch):
    _bucket(monkeypatch, {"a.txt": 10, "b.txt": 99})
    resp = client.post(
        "/admin/api/v1/cos/move",
        json={"source_key": "a.txt", "dest_key": "b.txt"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 409
    assert "请确认后再以覆盖方式重做" in body["message"]


def test_move_route_overwrite_reports_backup(client, admin_token, cos_configured, monkeypatch):
    _bucket(monkeypatch, {"a.txt": 10, "b.txt": 99})
    resp = client.post(
        "/admin/api/v1/cos/move",
        json={"source_key": "a.txt", "dest_key": "b.txt", "overwrite": True},
        headers=_admin_headers(admin_token),
    )
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["overwritten"] == 1
    assert "已覆盖 1 个同名对象" in body["message"]
    assert body["data"]["backup_keys"][0].startswith(".backup/")


def test_move_route_rejects_unknown_field(client, admin_token, cos_configured, monkeypatch):
    """多传的字段必须被拒（信封 code 400）：静默吞掉和一个「没生效」的移动在界面上看起来一样。"""
    _bucket(monkeypatch, {"a.txt": 10})
    resp = client.post(
        "/admin/api/v1/cos/move",
        json={"source_key": "a.txt", "dest_key": "b.txt", "overwrote": True},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 400
    assert "overwrote" in body["message"]


def test_move_preview_route_envelope(client, admin_token, cos_configured, monkeypatch):
    _bucket(monkeypatch, {"old/a.txt": 5, "new/a.txt": 111})
    resp = client.get(
        "/admin/api/v1/cos/move-preview",
        params={"source_key": "old/", "dest_key": "new/"},
        headers=_admin_headers(admin_token),
    )
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["conflict_count"] == 1
    assert body["data"]["conflicts"][0]["dest_key"] == "new/a.txt"


def test_move_preview_route_requires_admin(client):
    resp = client.get(
        "/admin/api/v1/cos/move-preview", params={"source_key": "a/", "dest_key": "b/"}
    )
    assert resp.status_code == 401
