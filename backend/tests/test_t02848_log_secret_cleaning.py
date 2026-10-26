"""T02848：历史日志明文凭据一次性清洗脚本的安全边界。

脚本是破坏性工具（就地重写日志），用例钉住：
1. dry-run 绝不写文件；
2. 只遮凭据片段，行结构与其余字节原样；
3. 重复执行不再计数；
4. 不可解码/正在追加的文件不猜改，并让失败可见；
5. 写回后目录里不残留任何明文副本。
"""
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

import clean_log_secrets as cleaner  # noqa: E402

AKID = "AKIDEXAMPLE1234567890"
SECRET_KEY = "abcdefghijklmnop1234567890"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sample_log() -> str:
    return (
        "2026-10-21 10:00:00 | INFO | cos sign url q-ak=" + AKID + "&q-sign-time=1\n"
        "2026-10-21 10:00:01 | ERROR | [parameters: ('" + AKID + "',)]\n"
        "2026-10-21 10:00:02 | WARN | secret_key=" + SECRET_KEY + "\n"
        "2026-10-21 10:00:03 | INFO | 正常中文行，不含凭据\n"
    )


def test_dry_run_reports_without_touching_files(tmp_path):
    log = tmp_path / "MorningBrief_2026-10-21.log"
    _write(log, _sample_log())
    before = log.read_bytes()

    summary = cleaner.clean_dir(tmp_path, apply=False)

    assert log.read_bytes() == before, "dry-run 改动了日志"
    assert summary.files[0].secret_lines == 3
    assert summary.files[0].akid_lines == 2
    assert summary.changed_files == []
    assert log.read_bytes() == before, "dry-run 改动了日志"


def test_apply_masks_only_secret_fragments(tmp_path):
    log = tmp_path / "MorningBrief_2026-10-21.log"
    _write(log, _sample_log())
    before_lines = _sample_log().splitlines()

    summary = cleaner.clean_dir(tmp_path, apply=True)

    after = log.read_text(encoding="utf-8")
    assert AKID not in after, "AKID 未脱敏"
    assert SECRET_KEY not in after, "SecretKey 未脱敏"
    assert summary.changed_files and summary.changed_files[0].path == log
    after_lines = after.splitlines()
    assert len(after_lines) == len(before_lines)
    # 行前缀、级别、时间戳与正常行都不许被动
    assert after_lines[0].startswith("2026-10-21 10:00:00 | INFO | cos sign url q-ak=")
    assert after_lines[2].startswith("2026-10-21 10:00:02 | WARN | secret_key=")
    assert after_lines[3] == before_lines[3]


def test_apply_is_idempotent_and_leaves_no_plaintext_copy(tmp_path):
    log = tmp_path / "MorningBrief_2026-10-21.log"
    _write(log, _sample_log())
    names_before = sorted(p.name for p in tmp_path.iterdir())

    assert cleaner.clean_dir(tmp_path, apply=True).changed_files
    second = cleaner.clean_dir(tmp_path, apply=True)

    assert second.changed_files == []
    assert sorted(p.name for p in tmp_path.iterdir()) == names_before, "残留了明文备份或临时文件"
    assert AKID not in log.read_text(encoding="utf-8")


def test_files_without_hits_are_not_rewritten(tmp_path):
    clean = tmp_path / "MorningBrief_2026-10-26.log"
    _write(clean, "2026-10-26 00:00:00 | INFO | 正常行\n")
    st = clean.stat()

    summary = cleaner.clean_dir(tmp_path, apply=True)

    assert summary.changed_files == []
    assert clean.stat().st_mtime_ns == st.st_mtime_ns


def test_binary_or_non_utf8_file_is_skipped_not_guessed(tmp_path):
    bad = tmp_path / "MorningBrief_2026-10-20.log"
    raw = b"\x80\x81 " + AKID.encode() + b"\n"
    bad.write_bytes(raw)

    summary = cleaner.clean_dir(tmp_path, apply=True)

    assert bad.read_bytes() == raw, "非 UTF-8 文件被改写"
    assert summary.files[0].skipped_reason == "非 UTF-8，未改写", "应跳过非 UTF-8"
    assert cleaner.main(["--dir", str(tmp_path), "--apply"]) == 1


def test_crlf_and_trailing_bytes_are_preserved(tmp_path):
    log = tmp_path / "MorningBrief_2026-10-19.log"
    log.write_bytes(("q-ak=" + AKID + "\r\n正常\r\n").encode("utf-8"))

    cleaner.clean_dir(tmp_path, apply=True)

    data = log.read_bytes()
    assert AKID.encode() not in data
    assert data.endswith(b"\r\n")
    assert data == b"q-ak=<" + "已脱敏".encode("utf-8") + b">\r\n" + "正常\r\n".encode("utf-8")


def test_symlinked_log_is_not_followed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.log"
    _write(target, "q-ak=" + AKID + "\n")
    logdir = tmp_path / "logs"
    logdir.mkdir()
    link = logdir / "link.log"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不允许创建符号链接")

    summary = cleaner.clean_dir(logdir, apply=True)

    assert summary.files == []
    assert AKID in target.read_text(encoding="utf-8"), "跟随链接改写了目录外的文件"


def test_only_log_suffix_is_scanned(tmp_path):
    other = tmp_path / "app.txt"
    _write(other, "q-ak=" + AKID + "\n")

    summary = cleaner.clean_dir(tmp_path, apply=True)

    assert summary.files == [], "扫描了非 .log 文件"
    assert AKID in other.read_text(encoding="utf-8"), "非 .log 文件被改写"


def test_cli_prints_counts_but_never_values(tmp_path, capsys):
    log = tmp_path / "MorningBrief_2026-10-21.log"
    _write(log, _sample_log())

    assert cleaner.main(["--dir", str(tmp_path)]) == 0

    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "命中凭据行 3" in out
    assert "COS SecretId 2 行" in out
    assert AKID not in out
    assert SECRET_KEY not in out


def test_missing_directory_exits_nonzero(tmp_path):
    assert cleaner.main(["--dir", str(tmp_path / "nope")]) == 2
