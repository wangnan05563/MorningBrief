"""数据库备份服务清理逻辑测试。

覆盖 cleanup_old_backups 的三层判定：
1. 天数窗口：常规备份超期删除 / 预备份快照用更短窗口
2. 份数上限：窗口内备份超过 max_files 时删最旧的
3. 不误删：未匹配命名模式的人工文件保持原样
"""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.services import backup_service
from app.services.backup_service import BackupService


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    """把备份目录重定向到 tmp_path，保证用例隔离。"""
    d = tmp_path / "backup"
    d.mkdir()
    monkeypatch.setattr(backup_service, "_resolve_backup_dir", lambda: d)
    return d


def _touch(directory: Path, name: str) -> Path:
    p = directory / name
    p.write_bytes(b"x" * 16)
    return p


def _regular(days_ago: int, hh: str = "030000") -> str:
    """生成常规备份文件名（本地时间）。

    hh 为 HHMMSS 形式的数字串：Windows 文件名不允许 ':'，不能插分隔符。
    """
    ts = (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")
    return f"news_backup_{ts}_{hh}.db"


def _pre(days_ago: int, scene: str = "restore") -> str:
    d = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    return f"news_pre_{scene}_{d}.db"


# ---- 天数窗口 ----

def test_removes_expired_regular_backups(backup_dir):
    """超过保留窗口的常规备份应被删除。"""
    _touch(backup_dir, _regular(days_ago=30))
    _touch(backup_dir, _regular(days_ago=1))

    deleted = _run(BackupService.cleanup_old_backups(keep_days=7, max_files=100))

    assert deleted == 1
    assert not (backup_dir / _regular(days_ago=30)).exists()
    assert (backup_dir / _regular(days_ago=1)).exists()


def test_pre_backup_uses_shorter_window(backup_dir):
    """预备份快照 5 天即应删除（常规备份的 7 天窗口对它太长）。"""
    _touch(backup_dir, _pre(days_ago=5))

    deleted = _run(BackupService.cleanup_old_backups(keep_days=7, max_files=100))

    assert deleted == 1
    assert not (backup_dir / _pre(days_ago=5)).exists()


def test_pre_backup_within_short_window_kept(backup_dir):
    """预备份快照在 3 天窗口内应保留。"""
    name = _pre(days_ago=1)
    _touch(backup_dir, name)

    deleted = _run(BackupService.cleanup_old_backups(keep_days=7, max_files=100))

    assert deleted == 0
    assert (backup_dir / name).exists()


def test_pre_backup_scenes_all_matched(backup_dir):
    """restore / seedpurge 等不同场景前缀都应纳入清理。"""
    for scene in ("restore", "seedpurge", "upgrade_v1_2"):
        _touch(backup_dir, _pre(days_ago=10, scene=scene))

    deleted = _run(BackupService.cleanup_old_backups(keep_days=7, max_files=100))

    assert deleted == 3


# ---- 份数上限 ----

def test_enforces_max_files_cap(backup_dir):
    """窗口内的常规备份超过上限时，删掉最旧的几份。"""
    for i in range(10):
        _touch(backup_dir, _regular(days_ago=i, hh=f"0{i}0000"))

    deleted = _run(BackupService.cleanup_old_backups(keep_days=7, max_files=3))

    assert deleted == 7
    remaining = sorted(p.name for p in backup_dir.iterdir())
    assert len(remaining) == 3
    # 保留的应是最新 3 份
    assert _regular(days_ago=0, hh="000000") in remaining
    assert _regular(days_ago=9, hh="090000") not in remaining


def test_max_files_cap_does_not_touch_pre_backups(backup_dir):
    """份数上限只作用于常规备份，不牵连预备份快照。"""
    for i in range(6):
        _touch(backup_dir, _regular(days_ago=i, hh=f"0{i}0000"))
    keep = _pre(days_ago=1)
    _touch(backup_dir, keep)

    _run(BackupService.cleanup_old_backups(keep_days=7, max_files=2))

    assert (backup_dir / keep).exists()


# ---- 不误删 ----

def test_ignores_unmatched_manual_files(backup_dir):
    """未匹配任何命名模式的人工文件不自动删（哪怕超出天数窗口）。"""
    other = _touch(backup_dir, "manual_snapshot.db")
    readme = _touch(backup_dir, "README.txt")
    # 名字长得像但格式不对（日期部分不是 YYYY-MM-DD）
    lookalike = _touch(backup_dir, "news_pre_restore_20261003.db")

    deleted = _run(BackupService.cleanup_old_backups(keep_days=0, max_files=1))

    assert deleted == 0
    for p in (other, readme, lookalike):
        assert p.exists()


def test_pre_backup_in_window_survives_max_files_pressure(backup_dir):
    """份数上限不得把仍在短窗口内的预备份一起清掉。"""
    keep = _pre(days_ago=1, scene="seedpurge")
    _touch(backup_dir, keep)
    for i in range(4):
        _touch(backup_dir, _regular(days_ago=i, hh=f"0{i}0000"))

    _run(BackupService.cleanup_old_backups(keep_days=7, max_files=1))

    assert (backup_dir / keep).exists()


def test_invalid_date_in_pre_name_not_deleted(backup_dir):
    """预备份文件名日期非法时保持原样，交人工判断。"""
    name = "news_pre_restore_2026-13-45.db"
    p = _touch(backup_dir, name)

    deleted = _run(BackupService.cleanup_old_backups(keep_days=7, max_files=100))

    assert deleted == 0
    assert p.exists()


def test_empty_dir_returns_zero(backup_dir):
    """空目录返回 0，不报错。"""
    assert _run(BackupService.cleanup_old_backups()) == 0


def test_missing_dir_returns_zero(tmp_path, monkeypatch):
    """备份目录不存在时返回 0。"""
    monkeypatch.setattr(backup_service, "_resolve_backup_dir", lambda: tmp_path / "nope")
    assert _run(BackupService.cleanup_old_backups()) == 0


# ---- 回归：list_backups 曾因 entry.path 报 AttributeError（接口必 500） ----

def test_list_backups_returns_entries(backup_dir):
    """列备份不应因 Path/DirEntry 混用而抛异常，且按文件名降序。"""
    _touch(backup_dir, _regular(days_ago=2, hh="010000"))
    _touch(backup_dir, _regular(days_ago=0, hh="020000"))
    _touch(backup_dir, "manual.db")  # 未匹配模式，不应出现在结果里

    result = _run(BackupService.list_backups())

    assert [b["filename"] for b in result] == [
        _regular(days_ago=0, hh="020000"),
        _regular(days_ago=2, hh="010000"),
    ]
    assert all(b["path"] for b in result)
    assert all(b["size_mb"] >= 0 for b in result)


def test_list_backups_empty(backup_dir):
    """空目录返回空列表。"""
    assert _run(BackupService.list_backups()) == []


# ---- 兼容：原有调用签名仍可用 ----

def test_default_signature_still_works(backup_dir):
    """定时任务/router 用的无参调用应保持可用。"""
    _touch(backup_dir, _regular(days_ago=30))
    assert _run(BackupService.cleanup_old_backups()) == 1


def _run(coro):
    """在事件循环中执行协程（服务方法均为 async）。"""
    import asyncio
    return asyncio.run(coro)
