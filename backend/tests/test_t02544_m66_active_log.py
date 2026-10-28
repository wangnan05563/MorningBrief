"""T02544 切片 6 / M66：日志清理必须跳过正在写入的活动分片。

评审口径（T02336 §4.3）：`maintenance_service.py` 的日志清理预览未排除活动日志属实；
但活动文件名是 `MorningBrief_日期.log`、10MB 滚动使活动文件通常 <10MB，所以
「清理必然失败」不成立。真正要守住的是：无论 old_logs / large_logs / all，
活动分片（mtime 最新的 `MorningBrief_*.log`）都不能出现在预览清单里、更不能被删掉——
Windows 上 unlink 直接 PermissionError；POSIX 上句柄继续写但目录里已无该文件，日志静默丢失。
"""
import os
import time

import pytest

from app.services.maintenance_service import (
    LARGE_LOG_THRESHOLD_BYTES,
    MaintenanceService,
)


def _make_log(path, size: int, mtime: float) -> None:
    path.write_bytes(b"")
    with open(path, "r+b") as fh:
        fh.truncate(size)
    os.utime(path, (mtime, mtime))


def _service() -> MaintenanceService:
    # 日志清理不触碰 db 会话；用 __new__ 避开 AsyncSession 构造
    return object.__new__(MaintenanceService)


def test_active_log_skipped_in_preview_and_execute(tmp_path):
    now = time.time()
    old = tmp_path / "MorningBrief_2026-10-01.log"
    older_big = tmp_path / "MorningBrief_2026-09-01.log"
    rotated = tmp_path / "MorningBrief_2026-10-27.2026-10-27_23-59-59.log"
    active = tmp_path / "MorningBrief_2026-10-28.log"
    unrelated = tmp_path / "other.txt"

    _make_log(old, 1024, now - 40 * 86400)
    _make_log(older_big, LARGE_LOG_THRESHOLD_BYTES + 1024, now - 41 * 86400)
    _make_log(rotated, 1024, now - 10 * 86400)
    # 活动分片同时「超龄」且「超过 10MB」，两种模式都想删它——正是被测的组合
    _make_log(active, LARGE_LOG_THRESHOLD_BYTES + 4096, now)
    unrelated.write_text("keep me", encoding="utf-8")

    svc = _service()

    preview = svc._cleanup_log_files(tmp_path, "all", 7, dry_run=True)
    previewed = " ".join(preview["cleaned"])
    assert active.name not in previewed
    for name in (old.name, older_big.name, rotated.name):
        assert name in previewed
    assert active.exists(), "预览不许动文件"
    assert old.exists()

    result = svc._cleanup_log_files(tmp_path, "all", 7, dry_run=False)
    assert active.exists(), "活动分片被删掉了"
    assert active.stat().st_size == LARGE_LOG_THRESHOLD_BYTES + 4096
    for path in (old, older_big, rotated):
        assert not path.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep me"
    assert result["errors"] == []


def test_only_active_log_left_means_nothing_to_clean(tmp_path):
    now = time.time()
    active = tmp_path / "MorningBrief_2026-10-28.log"
    _make_log(active, LARGE_LOG_THRESHOLD_BYTES + 4096, now - 60 * 86400)

    svc = _service()
    for target in ("old_logs", "large_logs", "all"):
        preview = svc._cleanup_log_files(tmp_path, target, 1, dry_run=True)
        assert preview["cleaned"] == [], target
    assert active.exists()


def test_active_log_pick_is_newest_shard(tmp_path):
    now = time.time()
    older = tmp_path / "MorningBrief_2026-10-26.log"
    newest = tmp_path / "MorningBrief_2026-10-28.log"
    _make_log(older, 16, now - 3600)
    _make_log(newest, 16, now)

    svc = _service()
    picked = svc._active_log_file(tmp_path)
    assert picked is not None
    assert picked.name == newest.name

    assert svc._active_log_file(tmp_path / "missing") is None


@pytest.mark.parametrize("target", ["old_logs", "large_logs", "all"])
def test_non_system_logs_still_cleanable(tmp_path, target):
    """跳过规则只保护 MorningBrief_*.log；同目录其他 .log 仍按原规则清理。"""
    now = time.time()
    plain = tmp_path / "app.log"
    _make_log(plain, LARGE_LOG_THRESHOLD_BYTES + 1024, now - 60 * 86400)

    svc = _service()
    result = svc._cleanup_log_files(tmp_path, target, 1, dry_run=False)
    assert not plain.exists()
    assert any(plain.name in item for item in result["cleaned"])
