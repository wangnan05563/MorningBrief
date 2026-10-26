"""T02609 快照恢复入口与保留策略。

原缺陷：覆盖前虽然会留 .backup/<时间戳>/ 快照，但回退只能人工下载再重传，
而且快照只增不减；目录里的旧版本与现役文件长得一样，误删即永久丢失。

本单覆盖：
- 快照 Key 的识别与「快照 → 原对象」反推（含同秒 -N 序号后缀的歧义判定）
- 列表标注 is_snapshot / is_snapshot_dir（页面据此加「快照」标签与面包屑提示）
- 恢复预览与恢复执行：目标已存在默认 409、恢复前先备份当前对象（恢复也可回退）
- 保留份数 COS_BACKUP_KEEP_COUNT：覆盖后清理更老的快照；0 = 不备份（点名不可回退）
- 配置热更新与 /status 下发保留份数；审计记录恢复动作（category=cos）

cos_client 单例方法全部替换为内存 FakeBucket，无真实网络。
"""
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.config import Settings, get_settings
from app.core.exceptions import BizError
from app.models.audit_log import AuditLog
from app.models.cos_config import CosConfig
from app.services import cos_storage_service
from app.services.cos_config_service import CosConfigService
from app.services.cos_storage_service import (
    CosStorageService,
    is_snapshot_key,
    snapshot_parts,
)

def OBJ(size=10, modified="2026-01-01"):
    return {"size": size, "last_modified": modified, "content_type": "", "etag": ""}


class FakeBucket:
    """最小 COS 桶：只实现服务用到的 6 个方法，含 delimiter 单层列举语义。"""

    def __init__(self, objects=None):
        self.objects = {k: dict(v) for k, v in (objects or {}).items()}
        self.calls = []

    async def object_exists(self, Key):
        return Key in self.objects

    async def head_object(self, Key):
        if Key not in self.objects:
            raise AssertionError(f"head_object 打到了不存在的 Key: {Key}")
        return dict(self.objects[Key])

    async def copy_object(self, SourceKey, Key):
        self.calls.append(("copy", SourceKey, Key))
        self.objects[Key] = dict(self.objects[SourceKey])

    async def delete_object(self, Key):
        self.calls.append(("delete", Key))
        self.objects.pop(Key, None)

    async def put_object(self, Key, Body, ContentType=None):
        self.calls.append(("put", Key))
        self.objects[Key] = {
            "size": len(Body), "last_modified": "", "content_type": ContentType or "", "etag": "",
        }

    async def delete_objects(self, keys):
        for key in keys:
            await self.delete_object(key)

    async def list_objects_delimited(self, prefix="", delimiter=None, marker="", max_keys=1000):
        contents, prefixes = [], set()
        for key in sorted(self.objects):
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix):]
            if not rest:
                continue
            if delimiter:
                head, sep, _ = rest.partition(delimiter)
                if sep:
                    prefixes.add(prefix + head + delimiter)
                    continue
            contents.append({
                "Key": key,
                "Size": self.objects[key].get("size", 0),
                "LastModified": self.objects[key].get("last_modified", ""),
            })
        return {
            "Contents": contents,
            "CommonPrefixes": [{"Prefix": p} for p in sorted(prefixes)],
            "IsTruncated": False,
        }

    def install(self, monkeypatch):
        for name in (
            "object_exists", "head_object", "copy_object", "delete_object",
            "put_object", "delete_objects", "list_objects_delimited",
        ):
            monkeypatch.setattr(cos_storage_service.cos_client, name, getattr(self, name))
        return self


@pytest.fixture
def cos_configured(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "COS_SECRET_ID", "AKIDx")
    monkeypatch.setattr(s, "COS_SECRET_KEY", "skx")
    monkeypatch.setattr(s, "COS_BUCKET", "bkt")
    monkeypatch.setattr(s, "COS_REGION", "ap-guangzhou")
    monkeypatch.setattr(s, "COS_CDN_DOMAIN", "")
    monkeypatch.setattr(s, "COS_BACKUP_KEEP_COUNT", 5)
    return s


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


# ---- 纯函数：快照 Key 识别与拆分 ----

def test_snapshot_key_detection():
    assert is_snapshot_key(".backup/20260101-120000/a.mp3")
    assert is_snapshot_key("audio/day/.backup/20260101-120000/a.mp3")
    assert not is_snapshot_key("audio/day/a.mp3")
    # 只是名字里带 .backup 不算（必须是一整层目录）
    assert not is_snapshot_key("audio/my.backup/a.mp3")


def test_snapshot_parts_nested_and_root():
    head, stamp, stored = snapshot_parts("audio/day/.backup/20260101-120000/a.mp3")
    assert (head, stamp, stored) == (
        "audio/day/", "audio/day/.backup/20260101-120000/", "a.mp3",
    )
    head, stamp, stored = snapshot_parts(".backup/20260101-120000/a.mp3")
    assert (head, stamp, stored) == ("", ".backup/20260101-120000/", "a.mp3")


def test_snapshot_parts_rejects_non_snapshot_and_broken_structure():
    with pytest.raises(BizError) as not_snapshot:
        snapshot_parts("audio/a.mp3")
    assert not_snapshot.value.code == 400
    with pytest.raises(BizError) as broken:
        snapshot_parts("audio/.backup/20260101-120000/")
    assert "结构不完整" in broken.value.message


# ---- 列表标注 ----

async def test_list_path_marks_snapshot_rows(cos_configured, monkeypatch):
    FakeBucket({
        "audio/a.mp3": OBJ(100),
        "audio/.backup/20260101-120000/a.mp3": OBJ(50, "old"),
    }).install(monkeypatch)

    svc = CosStorageService()
    live = await svc.list_path("audio/")
    assert live["folders"] == [".backup/"]
    assert [f["key"] for f in live["files"]] == ["audio/a.mp3"]
    assert live["files"][0]["is_snapshot"] is False
    assert live["is_snapshot_dir"] is False

    backup_root = await svc.list_path("audio/.backup/")
    assert backup_root["is_snapshot_dir"] is True
    assert backup_root["folders"] == ["20260101-120000/"]

    inside = await svc.list_path("audio/.backup/20260101-120000/")
    assert inside["is_snapshot_dir"] is True
    assert [f["is_snapshot"] for f in inside["files"]] == [True]


# ---- 保留策略 ----

async def test_overwrite_prunes_snapshots_over_keep_count(cos_configured, monkeypatch):
    """覆盖后按 COS_BACKUP_KEEP_COUNT 清理更老的快照，只留最近 N 份。"""
    monkeypatch.setattr(cos_configured, "COS_BACKUP_KEEP_COUNT", 2)
    bucket = FakeBucket({
        "audio/a.mp3": OBJ(100, "live"),
        "audio/.backup/20260101-120000/a.mp3": OBJ(1),
        "audio/.backup/20260102-120000/a.mp3": OBJ(2),
        "audio/.backup/20260103-120000/a.mp3": OBJ(3),
    }).install(monkeypatch)

    result = await CosStorageService().upload_file(
        "audio/a.mp3", b"new", "audio/mpeg", overwrite=True
    )
    assert result["backup_key"] and result["backup_key"].startswith("audio/.backup/")

    snaps = await CosStorageService()._list_snapshots("audio/a.mp3")
    assert len(snaps) == 2
    assert snaps[0]["key"] == result["backup_key"]          # 最新的就是本次覆盖前那份
    assert snaps[1]["key"] == "audio/.backup/20260103-120000/a.mp3"
    deleted = [c[1] for c in bucket.calls if c[0] == "delete"]
    assert sorted(deleted) == [
        "audio/.backup/20260101-120000/a.mp3",
        "audio/.backup/20260102-120000/a.mp3",
    ]


async def test_keep_zero_skips_snapshot_and_reports_none(cos_configured, monkeypatch):
    monkeypatch.setattr(cos_configured, "COS_BACKUP_KEEP_COUNT", 0)
    bucket = FakeBucket({"audio/a.mp3": OBJ(100)}).install(monkeypatch)

    result = await CosStorageService().upload_file(
        "audio/a.mp3", b"new", overwrite=True
    )
    assert result["overwritten"] is True
    assert result["backup_key"] is None
    assert [c for c in bucket.calls if c[0] == "copy"] == []
    assert [c for c in bucket.calls if c[0] == "put"] == [("put", "audio/a.mp3")]
    # 存量快照不因「改为不备份」而被删
    assert bucket.objects["audio/a.mp3"]["size"] == 3


async def test_prune_failure_does_not_fail_the_overwrite(cos_configured, monkeypatch):
    """清理旧快照失败只记日志：新文件已经写进去了，接口不能因此报错。"""
    monkeypatch.setattr(cos_configured, "COS_BACKUP_KEEP_COUNT", 1)
    bucket = FakeBucket({
        "audio/a.mp3": OBJ(100),
        "audio/.backup/20260101-120000/a.mp3": OBJ(1),
    }).install(monkeypatch)
    monkeypatch.setattr(
        bucket, "list_objects_delimited",
        AsyncMock(side_effect=cos_storage_service.CosClientError("网络中断")),
    )
    monkeypatch.setattr(cos_storage_service.cos_client, "list_objects_delimited",
                        bucket.list_objects_delimited)

    result = await CosStorageService().upload_file("audio/a.mp3", b"new", overwrite=True)
    assert result["backup_key"] is not None
    assert bucket.objects["audio/a.mp3"]["size"] == 3


# ---- 恢复预览 ----

async def test_restore_preview_resolves_target_and_current_state(cos_configured, monkeypatch):
    FakeBucket({
        "audio/a.mp3": OBJ(100, "live"),
        "audio/.backup/20260101-120000/a.mp3": OBJ(50, "old"),
    }).install(monkeypatch)

    data = await CosStorageService().restore_preview(
        "audio/.backup/20260101-120000/a.mp3"
    )
    assert data["backup_key"] == "audio/.backup/20260101-120000/a.mp3"
    assert data["target_key"] == "audio/a.mp3"
    assert data["snapshot"] == {"size": 50, "last_modified": "old"}
    assert data["target_exists"] is True
    assert data["target"]["size"] == 100
    assert data["backup_keep_count"] == 5


async def test_restore_preview_missing_snapshot_is_404(cos_configured, monkeypatch):
    FakeBucket({}).install(monkeypatch)
    with pytest.raises(BizError) as exc:
        await CosStorageService().restore_preview(
            "audio/.backup/20260101-120000/a.mp3"
        )
    assert exc.value.code == 404
    assert "快照对象不存在" in exc.value.message


async def test_restore_preview_rejects_regular_object(cos_configured, monkeypatch):
    FakeBucket({"audio/a.mp3": OBJ()}).install(monkeypatch)
    with pytest.raises(BizError) as exc:
        await CosStorageService().restore_preview("audio/a.mp3")
    assert exc.value.code == 400
    assert "不是 .backup 快照对象" in exc.value.message


async def test_snapshot_sequence_suffix_maps_back_to_base_name(cos_configured, monkeypatch):
    """同秒 -1 后缀要还原成原 Key；原文件名本身以 -1 结尾时不能误剥。"""
    FakeBucket({
        "audio/.backup/20260101-120000/a.mp3": OBJ(1),
        "audio/.backup/20260101-120000/a.mp3-1": OBJ(2),
        "audio/.backup/20260101-120000/b-1": OBJ(3),
    }).install(monkeypatch)
    svc = CosStorageService()
    seq = (await svc.restore_preview("audio/.backup/20260101-120000/a.mp3-1"))["target_key"]
    assert seq == "audio/a.mp3"
    own_suffix = (await svc.restore_preview("audio/.backup/20260101-120000/b-1"))["target_key"]
    assert own_suffix == "audio/b-1"


# ---- 恢复执行 ----

async def test_restore_rejects_existing_target_without_overwrite(cos_configured, monkeypatch):
    bucket = FakeBucket({
        "audio/a.mp3": OBJ(100, "live"),
        "audio/.backup/20260101-120000/a.mp3": OBJ(50, "old"),
    }).install(monkeypatch)
    with pytest.raises(BizError) as exc:
        await CosStorageService().restore_snapshot(
            "audio/.backup/20260101-120000/a.mp3"
        )
    assert exc.value.code == 409
    assert "audio/a.mp3" in exc.value.message and "100 B" in exc.value.message
    assert [c for c in bucket.calls if c[0] == "copy"] == []


async def test_restore_snapshots_current_object_then_copies(cos_configured, monkeypatch):
    """恢复也可回退：先把当前对象备份一份，再把快照复制回原 Key。"""
    bucket = FakeBucket({
        "audio/a.mp3": OBJ(100, "live"),
        "audio/.backup/20260101-120000/a.mp3": OBJ(50, "old"),
    }).install(monkeypatch)

    result = await CosStorageService().restore_snapshot(
        "audio/.backup/20260101-120000/a.mp3", overwrite=True
    )
    assert result["target_key"] == "audio/a.mp3"
    assert result["overwritten"] is True
    assert result["size"] == 50
    assert result["backup_key"].startswith("audio/.backup/")
    copies = [c for c in bucket.calls if c[0] == "copy"]
    assert copies == [
        ("copy", "audio/a.mp3", result["backup_key"]),
        ("copy", "audio/.backup/20260101-120000/a.mp3", "audio/a.mp3"),
    ]
    assert bucket.objects["audio/a.mp3"]["size"] == 50
    assert bucket.objects[result["backup_key"]]["size"] == 100


async def test_restore_into_missing_target_needs_no_backup(cos_configured, monkeypatch):
    bucket = FakeBucket({
        "audio/.backup/20260101-120000/a.mp3": OBJ(50, "old"),
    }).install(monkeypatch)

    result = await CosStorageService().restore_snapshot(
        "audio/.backup/20260101-120000/a.mp3"
    )
    assert result["overwritten"] is False
    assert result["backup_key"] is None
    assert [c for c in bucket.calls if c[0] == "copy"] == [
        ("copy", "audio/.backup/20260101-120000/a.mp3", "audio/a.mp3"),
    ]
    assert bucket.objects["audio/a.mp3"]["size"] == 50


async def test_restore_rejects_target_that_does_not_match_snapshot(cos_configured, monkeypatch):
    """显式 target_key 与快照推出值不一致时拒绝：不做「把 A 的内容写到 B」这种事。"""
    bucket = FakeBucket({
        "audio/.backup/20260101-120000/a.mp3": OBJ(50),
    }).install(monkeypatch)
    with pytest.raises(BizError) as exc:
        await CosStorageService().restore_snapshot(
            "audio/.backup/20260101-120000/a.mp3", target_key="other/b.mp3"
        )
    assert exc.value.code == 400
    assert "不能恢复到 other/b.mp3" in exc.value.message
    assert [c for c in bucket.calls if c[0] == "copy"] == []


async def test_restore_keep_zero_has_no_revert_backup(cos_configured, monkeypatch):
    monkeypatch.setattr(cos_configured, "COS_BACKUP_KEEP_COUNT", 0)
    bucket = FakeBucket({
        "audio/a.mp3": OBJ(100),
        "audio/.backup/20260101-120000/a.mp3": OBJ(50),
    }).install(monkeypatch)

    result = await CosStorageService().restore_snapshot(
        "audio/.backup/20260101-120000/a.mp3", overwrite=True
    )
    assert result["backup_key"] is None
    assert result["backup_keep_count"] == 0
    assert [c for c in bucket.calls if c[0] == "copy"] == [
        ("copy", "audio/.backup/20260101-120000/a.mp3", "audio/a.mp3"),
    ]


# ---- 配置热更新 ----

async def test_update_config_persists_and_hot_reloads_keep_count(
    db_session, cos_configured, monkeypatch
):
    monkeypatch.setattr(cos_configured, "COS_BACKUP_KEEP_COUNT", 5)
    svc = CosConfigService(db_session)
    await svc.update_config(bucket="bkt", backup_keep_count=3)

    assert get_settings().COS_BACKUP_KEEP_COUNT == 3
    value = (
        await db_session.execute(
            select(CosConfig.config_value).where(
                CosConfig.config_key == "cos_backup_keep_count"
            )
        )
    ).scalar_one()
    assert value == "3"
    assert (await svc.get_config_for_frontend())["backup_keep_count"] == 3


async def test_update_config_keep_count_none_means_unchanged(db_session, cos_configured):
    db_session.add(CosConfig(config_key="cos_backup_keep_count", config_value="7"))
    await db_session.commit()

    await CosConfigService(db_session).update_config(bucket="bkt")
    value = (
        await db_session.execute(
            select(CosConfig.config_value).where(
                CosConfig.config_key == "cos_backup_keep_count"
            )
        )
    ).scalar_one()
    assert value == "7"


async def test_update_config_keep_count_is_clamped(db_session, cos_configured):
    svc = CosConfigService(db_session)
    await svc.update_config(bucket="bkt", backup_keep_count=9999)
    assert get_settings().COS_BACKUP_KEEP_COUNT == 50
    await svc.update_config(bucket="bkt", backup_keep_count=-3)
    assert get_settings().COS_BACKUP_KEEP_COUNT == 0


def test_settings_declares_keep_count_default():
    """Settings 默认值即契约：缺 .env / 缺配置行时按 5 份保留。"""
    assert Settings.model_fields["COS_BACKUP_KEEP_COUNT"].default == 5


# ---- 路由层 ----

async def test_restore_route_returns_envelope_and_audit(
    client, admin_token, db_session, cos_configured, monkeypatch
):
    FakeBucket({
        "audio/a.mp3": OBJ(100, "live"),
        "audio/.backup/20260101-120000/a.mp3": OBJ(50, "old"),
    }).install(monkeypatch)

    resp = client.post(
        "/admin/api/v1/cos/restore",
        json={
            "backup_key": "audio/.backup/20260101-120000/a.mp3",
            "overwrite": True,
        },
        headers=_admin_headers(admin_token),
    )
    body = resp.json()
    assert body["code"] == 0, body
    assert body["data"]["target_key"] == "audio/a.mp3"
    assert "已从快照恢复 audio/a.mp3" in body["message"]

    audit = (await db_session.execute(
        select(AuditLog).where(
            AuditLog.category == "cos", AuditLog.action == "restore_snapshot"
        )
    )).scalars().all()
    assert [a.target for a in audit] == ["audio/a.mp3"]
    assert audit[0].operator == "admin"
    assert "audio/.backup/20260101-120000/a.mp3" in audit[0].detail


async def test_restore_route_rejects_unknown_field(
    client, admin_token, cos_configured, monkeypatch
):
    """覆盖开关拼错必须被拒：静默当作「不覆盖」会让用户以为恢复成功。"""
    FakeBucket({}).install(monkeypatch)
    resp = client.post(
        "/admin/api/v1/cos/restore",
        json={
            "backup_key": "audio/.backup/20260101-120000/a.mp3",
            "overwrit": True,
        },
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 400
    assert "overwrit" in body["message"]


async def test_restore_preview_route(client, admin_token, cos_configured, monkeypatch):
    FakeBucket({
        "audio/.backup/20260101-120000/a.mp3": OBJ(50, "old"),
    }).install(monkeypatch)
    resp = client.get(
        "/admin/api/v1/cos/restore-preview",
        params={"backup_key": "audio/.backup/20260101-120000/a.mp3"},
        headers=_admin_headers(admin_token),
    )
    data = resp.json()["data"]
    assert data["target_key"] == "audio/a.mp3"
    assert data["target_exists"] is False


async def test_status_route_reports_backup_keep_count(
    client, admin_token, cos_configured, monkeypatch
):
    monkeypatch.setattr(cos_configured, "COS_BACKUP_KEEP_COUNT", 2)
    resp = client.get("/admin/api/v1/cos/status", headers=_admin_headers(admin_token))
    assert resp.json()["data"]["backup_keep_count"] == 2


async def test_upload_route_keep_zero_names_the_risk(
    client, admin_token, cos_configured, monkeypatch
):
    monkeypatch.setattr(cos_configured, "COS_BACKUP_KEEP_COUNT", 0)
    FakeBucket({"docs/a.txt": OBJ(5)}).install(monkeypatch)
    resp = client.post(
        "/admin/api/v1/cos/upload",
        files={"file": ("a.txt", b"hello world")},
        data={"prefix": "docs/", "overwrite": "true"},
        headers=_admin_headers(admin_token),
    )
    body = resp.json()
    assert body["code"] == 0, body
    assert "不保留快照" in body["message"]
    assert body["data"]["backup_key"] is None


async def test_restore_route_requires_admin(client):
    resp = client.post(
        "/admin/api/v1/cos/restore",
        json={"backup_key": "audio/.backup/20260101-120000/a.mp3"},
    )
    assert resp.status_code == 401
