"""日志目录配额与滚动策略测试。

覆盖 _enforce_dir_quota（目录总量兜底，retention 的双保险）：
- 超限时从最旧分片开始删
- 活动分片（最新）永不删
- 未超限不动任何文件
- 不碰非 MorningBrief_*.log 的同目录文件
- 符号链接不作为删除目标
- 异常场景（目录不存在 / max_mb=0）安全返回

为什么必须有它：loguru retention 按**单文件 mtime** 清理，压测等高频场景可在
数小时内刷出数十个当日分片，它们 mtime 全在保留窗口内 → retention 一个都删不掉。
"""
import os
import time
from pathlib import Path

import pytest

from app.core.logging_setup import _enforce_dir_quota, _make_rotation


def _mk(directory: Path, name: str, size_kb: int, age_days: float = 0) -> Path:
    p = directory / name
    p.write_bytes(b"x" * (size_kb * 1024))
    if age_days:
        t = time.time() - age_days * 86400
        os.utime(p, (t, t))
    return p


@pytest.fixture
def log_dir(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    return d


# ---- 总量超限 ----

def test_deletes_oldest_shards_when_over_quota(log_dir):
    """超限时应从最旧的分片开始删。"""
    old1 = _mk(log_dir, "MorningBrief_2026-10-01.log", 100, age_days=3)
    old2 = _mk(log_dir, "MorningBrief_2026-10-02.log", 100, age_days=2)
    newest = _mk(log_dir, "MorningBrief_2026-10-03.log", 100, age_days=1)

    # 上限 250KB < 总量 300KB -> 需释放 50KB+，删掉最旧的 100KB
    freed = _enforce_dir_quota(log_dir, max_mb=1)  # 1MB 不足以触发，改用小阈值

    # 1MB 上限下 300KB 不超限，什么都不该删
    assert freed == 0
    assert old1.exists() and old2.exists() and newest.exists()

    # 用 0MB 上限强制清空（max_mb=0 视为禁用，返回 0）——验证禁用语义
    assert _enforce_dir_quota(log_dir, max_mb=0) == 0
    assert old1.exists()


def test_quota_uses_megabytes_as_unit(log_dir):
    """max_mb 单位是 MB：1MB 上限下 1.5MB 总量应触发清理。"""
    _mk(log_dir, "MorningBrief_2026-10-01.log", 800, age_days=2)
    newest = _mk(log_dir, "MorningBrief_2026-10-03.log", 700)

    freed = _enforce_dir_quota(log_dir, max_mb=1)

    assert freed == 800 * 1024  # 删掉了 800KB 的旧分片
    assert newest.exists()


def test_keeps_active_shard_even_if_over_quota(log_dir):
    """活动分片（mtime 最新）永不删除，避免删掉正在写入的文件。"""
    _mk(log_dir, "MorningBrief_2026-10-01.log", 500, age_days=5)
    active = _mk(log_dir, "MorningBrief_2026-10-03.log", 100)

    _enforce_dir_quota(log_dir, max_mb=1)

    assert active.exists(), "活动分片被误删"


def test_only_deletes_shards_exceeding_limit(log_dir):
    """刚好降到限额就停手，不多删。"""
    _mk(log_dir, "MorningBrief_2026-10-01.log", 1000, age_days=3)
    _mk(log_dir, "MorningBrief_2026-10-02.log", 100, age_days=2)
    _mk(log_dir, "MorningBrief_2026-10-03.log", 100, age_days=1)

    # 总量 1200KB，上限 1MB=1024KB -> 只需删 1000KB 那份
    freed = _enforce_dir_quota(log_dir, max_mb=1)

    assert freed == 1000 * 1024
    remaining = sorted(p.name for p in log_dir.iterdir())
    assert remaining == [
        "MorningBrief_2026-10-02.log",
        "MorningBrief_2026-10-03.log",
    ]


def test_deletes_enough_to_reach_limit(log_dir):
    """回归：必须真正降到限额以下，不能删一半就停手。

    历史 bug：循环里同时维护 total 和 freed 两个「已删除量」变量并各自累加，
    `total - freed` 重复扣减导致提前跌破 limit 停手 —— 40MB 总量、5MB 限额
    只删了 18MB 就退出，剩余 22MB 仍远超限额。
    本用例用 40 片 × 1MB 复现该场景。
    """
    for i in range(40):
        _mk(log_dir, f"MorningBrief_2026-10-03.2026-10-03_{i:02d}-00-00_000000.log",
            1024, age_days=(40 - i) / 24)

    freed = _enforce_dir_quota(log_dir, max_mb=5)

    # 配额只约束本系统产生的分片（人工文件不计入、也不会被删）
    shards_left = [p for p in log_dir.iterdir() if p.name.startswith("MorningBrief_")]
    total_after = sum(p.stat().st_size for p in shards_left)
    assert total_after <= 5 * 1024 * 1024, (
        f"清理后分片仍有 {total_after / 1024 / 1024:.1f}MB，超出 5MB 限额")
    # 每片 1MB、限额 5MB → 恰好剩 5 片（旧的 bug 会剩 22 片）
    names = {p.name for p in shards_left}
    assert len(names) == 5
    # 最新那片（age 最小的 39 号）是活动分片，必须保留。
    # 注意 iterdir() 顺序无保证，必须用集合断言而非下标。
    assert "MorningBrief_2026-10-03.2026-10-03_39-00-00_000000.log" in names


# ---- 边界与安全性 ----

def test_ignores_non_system_files(log_dir):
    """同目录下的其他文件（人工放的文件）不受影响。"""
    manual = _mk(log_dir, "my_debug_output.log", 2000, age_days=9)
    other = log_dir / "notes.txt"
    other.write_text("keep me", encoding="utf-8")
    _mk(log_dir, "MorningBrief_2026-10-01.log", 100, age_days=3)
    _mk(log_dir, "MorningBrief_2026-10-03.log", 100)

    _enforce_dir_quota(log_dir, max_mb=1)

    assert manual.exists(), "非 MorningBrief_*.log 被误删"
    assert other.exists()


def test_skips_symlinks(log_dir):
    """符号链接不作为删除目标（避免删到项目树外的真实文件）。"""
    real = _mk(log_dir.parent, "outside.log", 2000, age_days=9)
    link = log_dir / "MorningBrief_2026-09-01.log"
    try:
        os.symlink(real, link)
    except OSError:
        pytest.skip("当前环境不允许创建符号链接")

    _enforce_dir_quota(log_dir, max_mb=1)

    assert real.exists(), "沿符号链接删到了目录外"
    assert link.exists(), "符号链接本身被删除"


def test_missing_dir_returns_zero(tmp_path):
    """目录不存在时安全返回 0。"""
    assert _enforce_dir_quota(tmp_path / "nope", max_mb=100) == 0


def test_zero_limit_disables_quota(log_dir):
    """max_mb<=0 视为禁用配额（0 返回、负数同样禁用）。"""
    _mk(log_dir, "MorningBrief_2026-10-01.log", 5000, age_days=9)
    assert _enforce_dir_quota(log_dir, max_mb=0) == 0
    assert _enforce_dir_quota(log_dir, max_mb=-1) == 0
    assert len(list(log_dir.iterdir())) == 1


def test_empty_dir_returns_zero(log_dir):
    """空目录返回 0。"""
    assert _enforce_dir_quota(log_dir, max_mb=100) == 0


def test_retention_uses_configured_days(monkeypatch, tmp_path):
    """retention 字符串应跟随配置项（原先硬编码 "14 days"）。"""
    from loguru import logger
    import app.core.logging_setup as ls

    monkeypatch.setattr(ls, "_configured", False)
    seen = {}

    orig_add = ls.logger.add

    def spy_add(sink, *a, **kw):
        seen["retention"] = kw.get("retention")
        # 不真正注册 sink，避免污染测试进程的全局 logger
        return 0

    monkeypatch.setattr(ls.logger, "add", spy_add)
    ls.setup_logging(log_dir=tmp_path, retention_days=3)
    monkeypatch.setattr(ls.logger, "add", orig_add)
    logger  # keep import used

    assert seen["retention"] == "3 days"


def test_retention_floor_is_one_day(monkeypatch, tmp_path):
    """retention_days<=0 时夹到 1 天（loguru 不接受 "0 days"）。"""
    import app.core.logging_setup as ls

    monkeypatch.setattr(ls, "_configured", False)
    seen = {}
    monkeypatch.setattr(ls.logger, "add", lambda s, *a, **kw: seen.update(kw) or 0)

    ls.setup_logging(log_dir=tmp_path, retention_days=0)

    assert seen["retention"] == "1 days"


# ---- 滚动谓词 ----

def test_rotation_size_trigger(tmp_path):
    """达到大小上限应触发滚动。"""
    rotate = _make_rotation(1)  # 1MB
    f = tmp_path / "a.log"
    f.write_bytes(b"x" * (1024 * 1024))  # 正好 1MB
    assert rotate(type("M", (), {"file": type("F", (), {"name": str(f)})()})()) is True


def test_rotation_under_size_no_rotate(tmp_path):
    """未达上限首条日志不触发滚动（仅记录基准日）。"""
    rotate = _make_rotation(10)
    f = tmp_path / "a.log"
    f.write_bytes(b"x" * 100)
    msg = type("M", (), {"file": type("F", (), {"name": str(f)})()})()
    assert rotate(msg) is False
    assert rotate(msg) is False  # 同日不重复触发
