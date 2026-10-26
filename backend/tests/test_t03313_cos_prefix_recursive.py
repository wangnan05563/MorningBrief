"""T03313：COS 前缀列举必须递归，删除/移动的文件夹分支才名副其实。

原缺陷：`_list_prefix_objects` 调用 `list_objects_delimited` 时没传 delimiter，
拿到默认 "/"——按目录分组后 Contents 只剩当前层直接文件，子目录里的对象全被
丢进 CommonPrefixes。于是 `delete_folder("a/")` 只删 `a/x.txt`，`a/b/c.txt`
原地留下却仍回「已删 N 个」；`move_object("old/","new/")` 同样只搬顶层，
子目录成为无主对象。本文件用一个**遵守 Delimiter 语义**的内存桶把这条钉住。

cos_client 单例方法全部替换成内存假桶，无真实网络。
"""
import pytest

from app.services import cos_storage_service
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


class FakeBucket:
    """遵守 COS Delimiter 语义的内存桶：delimiter 为空才是递归列举。

    真实 COS 在 delimiter="/" 时把 `prefix + 第一段 + "/"` 收进 CommonPrefixes，
    Contents 只剩当前层文件（Key 恰等于 prefix 的占位对象也算当前层）。
    """

    def __init__(self, objects: dict[str, int]):
        self.objects = dict(objects)
        self.copied: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.delimiters: list[str] = []

    async def object_exists(self, Key):
        if ".backup/" in Key:
            return False
        return Key in self.objects

    async def head_object(self, Key):
        if ".backup/" in Key:
            return {"size": 0, "last_modified": "", "content_type": "", "etag": ""}
        return {
            "size": self.objects.get(Key, 0),
            "last_modified": "Wed, 15 Oct 2026 08:00:00 GMT",
            "content_type": "",
            "etag": "e",
        }

    async def list_objects_delimited(self, prefix="", delimiter="/", marker="", max_keys=1000):
        self.delimiters.append(delimiter)
        contents: list[dict] = []
        prefixes: set[str] = set()
        for key in sorted(self.objects):
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix):]
            if delimiter and rest:
                head, sep, _ = rest.partition(delimiter)
                if sep:
                    prefixes.add(prefix + head + delimiter)
                    continue
            contents.append({"Key": key, "Size": self.objects[key]})
        return {
            "Contents": contents,
            "CommonPrefixes": [{"Prefix": p} for p in sorted(prefixes)],
            "IsTruncated": False,
        }

    async def copy_object(self, SourceKey, Key):
        self.copied.append((SourceKey, Key))
        self.objects[Key] = self.objects.get(SourceKey, 0)

    async def delete_object(self, Key):
        self.deleted.append(Key)
        self.objects.pop(Key, None)

    async def delete_objects(self, keys):
        for key in keys:
            await self.delete_object(key)

    def install(self, monkeypatch):
        for name in (
            "object_exists", "head_object", "copy_object", "delete_object",
            "delete_objects", "list_objects_delimited",
        ):
            monkeypatch.setattr(cos_storage_service.cos_client, name, getattr(self, name))
        return self


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


# ---- 列举口径 ----

async def test_list_all_keys_is_recursive(cos_configured, monkeypatch):
    """a/b/c.txt、a/b/d/e.txt 都在 a/ 下——只拿顶层就是漏。"""
    bucket = FakeBucket({
        "a/x.txt": 1,
        "a/b/c.txt": 2,
        "a/b/d/e.txt": 3,
        "other/z.txt": 4,
    }).install(monkeypatch)

    keys = await CosStorageService()._list_all_keys("a/")

    assert sorted(keys) == ["a/b/c.txt", "a/b/d/e.txt", "a/x.txt"]
    # 递归必须显式传 delimiter=""（默认值 "/" 是这次缺陷的根因）
    assert bucket.delimiters == [""]


# ---- 删除 ----

async def test_delete_folder_removes_every_level(cos_configured, monkeypatch):
    """删 a/ 要把 a/b/c.txt 一并删掉，返回的条数就是实际删除条数。

    快照目录也在这个前缀下面，递归删除会连它一起清掉——否则重建同名目录时
    会看到上一个同名对象的旧快照，且没有任何界面能解释它们从哪来。
    """
    bucket = FakeBucket({
        "a/": 0,                                    # 目录占位对象本身也要删
        "a/x.txt": 1,
        "a/b/c.txt": 2,
        "a/.backup/20260101-120000/x.txt": 5,       # 其下的快照一并清掉
        "b/keep.txt": 3,                            # 前缀外的对象不能被波及
    }).install(monkeypatch)

    count = await CosStorageService().delete_folder("a")

    assert count == 4
    assert sorted(bucket.deleted) == [
        "a/", "a/.backup/20260101-120000/x.txt", "a/b/c.txt", "a/x.txt",
    ]
    assert sorted(bucket.objects) == ["b/keep.txt"]


async def test_delete_folder_route_reports_nested_count(client, admin_token, cos_configured, monkeypatch):
    """接口回传的 deleted 必须是含子目录条数的实测值，不是「顶层几个」。"""
    FakeBucket({"docs/a.txt": 1, "docs/sub/b.txt": 2}).install(monkeypatch)

    resp = client.delete(
        "/admin/api/v1/cos/folder",
        params={"prefix": "docs/"},
        headers=_admin_headers(admin_token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["deleted"] == 2
    assert "已删除 2 个对象" in body["message"]


# ---- 移动 ----

async def test_move_preview_counts_nested_conflicts(cos_configured, monkeypatch):
    """子目录里的同名对象同样会被换掉，确认框的条数必须把它们算进来。"""
    FakeBucket({
        "old/a.txt": 1,
        "old/b/c.txt": 2,
        "new/a.txt": 90,
        "new/b/c.txt": 80,
        "new/z.txt": 70,
    }).install(monkeypatch)

    data = await CosStorageService().move_preview("old/", "new/")

    assert data["moved"] == 2
    assert data["conflict_count"] == 2
    assert {c["dest_key"]: c["size"] for c in data["conflicts"]} == {
        "new/a.txt": 90,
        "new/b/c.txt": 80,
    }


async def test_move_folder_moves_nested_objects(cos_configured, monkeypatch):
    """移动文件夹后源前缀下不能残留任何一层对象。"""
    bucket = FakeBucket({"old/a.txt": 1, "old/b/c.txt": 2}).install(monkeypatch)

    result = await CosStorageService().move_object("old/", "new/")

    assert result["moved"] == 2
    assert bucket.copied == [("old/a.txt", "new/a.txt"), ("old/b/c.txt", "new/b/c.txt")]
    assert sorted(bucket.objects) == ["new/a.txt", "new/b/c.txt"]


# ---- 回归控制：单层视图不得被递归口径带跑 ----

async def test_list_path_stays_single_level(cos_configured, monkeypatch):
    """列表页仍按层展示：a/b/ 是子目录条目，c.txt 不应直接出现在 a/ 这一层。"""
    bucket = FakeBucket({"a/x.txt": 1, "a/b/c.txt": 2}).install(monkeypatch)

    data = await CosStorageService().list_path("a/")

    assert data["folders"] == ["b/"]
    assert [f["key"] for f in data["files"]] == ["a/x.txt"]
    # 单层列举仍显式带 delimiter="/"——与递归列举是两套口径
    assert bucket.delimiters == ["/"]
