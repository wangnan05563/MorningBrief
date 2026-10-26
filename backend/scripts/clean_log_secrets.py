"""一次性清洗历史日志里的明文凭据（T02848）。

背景：T02523 已关掉泄露源头（三方日志钳到 WARNING、落盘前脱敏、异常不回显
parameters），但**已经写盘**的旧日志不会被代码修复影响。抽样测得
`backend/logs` 里曾有 2539 行明文腾讯云 COS SecretId（`AKID…`）。

本脚本用与运行时**同一套判定**（`app.core.logging_setup.redact_credentials`）
就地重写旧日志：命中片段换成占位符，行结构、时间戳、其余字节原样保留。
默认 dry-run，只打印文件与行数，绝不打印任何凭据值。

用法（backend 目录下）：
    .venv/Scripts/python scripts/clean_log_secrets.py             # 预演 backend/logs
    .venv/Scripts/python scripts/clean_log_secrets.py --dir logs  # 指定目录
    .venv/Scripts/python scripts/clean_log_secrets.py --apply     # 实际重写

安全边界：
- 只处理目录**直接子级**的 `*.log`，不递归、不跟随符号链接；
- 不以 UTF-8 严格解码的文件**跳过并报错**，不猜编码、不写回；
- 读与写之间文件发生变化（如进程正在追加）则放弃该文件，避免覆盖掉新日志；
- 写回采用「同目录临时文件 + os.replace」，不保留任何明文副本；
- 清洗只在明确批准后执行；脚本可重复运行（已脱敏行不会再次计数）。
"""
import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.logging_setup import redact_credentials  # noqa: E402

DEFAULT_LOG_DIR = BACKEND_DIR / "logs"

# 仅用于报告 SecretId 命中行数（与 T02848 的原始抽样对齐），不参与改写、不打印值。
_AKID_RE = re.compile(r"\bAKID[A-Za-z0-9]{8,}")


@dataclass
class FileReport:
    """单个文件的扫描结果（只含计数，不含值）。"""

    path: Path
    size: int = 0
    lines: int = 0
    secret_lines: int = 0
    akid_lines: int = 0
    would_change: bool = False
    written: bool = False
    skipped_reason: Optional[str] = None


@dataclass
class Summary:
    """一次目录扫描/清洗的结果。"""

    root: Path
    applied: bool = False
    files: list[FileReport] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def changed_files(self) -> list[FileReport]:
        return [item for item in self.files if item.written]

    @property
    def secret_lines(self) -> int:
        return sum(item.secret_lines for item in self.files)

    @property
    def akid_lines(self) -> int:
        return sum(item.akid_lines for item in self.files)

    @property
    def errors(self) -> list[FileReport]:
        return [item for item in self.files if item.skipped_reason]


def _read_stable(path: Path) -> bytes:
    """读取文件；若读取期间大小/mtime 变化则放弃（进程仍在追加）。"""
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("文件在读取期间被修改（可能在追加日志）")
    return data


def _write_atomic(path: Path, data: bytes, expected_size: int, expected_mtime_ns: int) -> None:
    """同目录临时文件 + os.replace 写回，写前再确认文件未被追加。"""
    current = path.stat()
    if (current.st_size, current.st_mtime_ns) != (expected_size, expected_mtime_ns):
        raise RuntimeError("文件在写回前被修改（可能在追加日志）")
    tmp = path.with_name(path.name + ".clean_tmp")
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.stat().st_size != expected_size or path.stat().st_mtime_ns != expected_mtime_ns:
            raise RuntimeError("文件在写回前被修改（可能在追加日志）")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def clean_file(path: Path, apply: bool) -> FileReport:
    """扫描（apply=True 时重写）单个日志文件。"""
    report = FileReport(path=path, size=path.stat().st_size)
    try:
        raw = _read_stable(path)
    except OSError as exc:
        report.skipped_reason = f"读取失败: {type(exc).__name__}"
        return report
    except RuntimeError as exc:
        report.skipped_reason = str(exc)
        return report

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # 不猜编码：按替换字符写回会破坏原始字节，交人工处理
        report.skipped_reason = "非 UTF-8，未改写"
        return report

    report.lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    # 以「脱敏后是否真的变了」计行：像 `ALERT_EMAIL_SMTP_PASSWORD: 空值` 这种
    # 只有键名、值是占位词的行不算命中，否则报告会把 400+ 行噪音说成凭据。
    report.secret_lines = sum(
        1 for line in text.splitlines() if redact_credentials(line) != line
    )
    report.akid_lines = sum(1 for line in text.splitlines() if _AKID_RE.search(line))

    cleaned = redact_credentials(text)
    report.would_change = cleaned != text
    if not report.would_change:
        return report
    if not apply:
        return report

    if cleaned.count("\n") != text.count("\n"):
        report.skipped_reason = "脱敏改动了行结构，未写回"
        return report

    stat = path.stat()
    try:
        _write_atomic(path, cleaned.encode("utf-8"), stat.st_size, stat.st_mtime_ns)
    except (OSError, RuntimeError) as exc:
        report.skipped_reason = f"写回失败: {exc}"
        return report
    report.written = True
    report.size = path.stat().st_size
    return report


def clean_dir(root: Path, apply: bool = False) -> Summary:
    """扫描目录直接子级的 *.log；apply=True 时就地重写。"""
    summary = Summary(root=root, applied=apply)
    if not root.is_dir():
        summary.error = "日志目录不存在"
        return summary
    for path in sorted(root.glob("*.log")):
        if path.is_symlink() or not path.is_file():
            continue
        summary.files.append(clean_file(path, apply=apply))
    return summary


def _print_summary(summary: Summary, verbose: bool = False) -> None:
    mode = "APPLY（已重写）" if summary.applied else "DRY-RUN（只读预演）"
    print(f"目录: {summary.root}")
    print(f"模式: {mode}")
    if summary.error:
        print(f"  [error] {summary.error}")
        return
    changed = summary.changed_files
    actionable = [
        item for item in summary.files if item.would_change and not item.skipped_reason
    ]
    print(
        f"  文件 {len(summary.files)} 个 · 命中凭据行 {summary.secret_lines}"
        f" · 其中 COS SecretId {summary.akid_lines} 行"
        f" · {'已重写' if summary.applied else '待重写'} {len(changed) if summary.applied else len(actionable)} 个"
    )
    for item in summary.files:
        if not item.would_change and not item.skipped_reason and not verbose:
            continue
        if item.written:
            flag = "已重写"
        elif item.skipped_reason:
            flag = "跳过"
        elif item.would_change:
            flag = "待重写"
        else:
            flag = "无改动"
        print(
            f"    {item.path.name}  {item.size / 1024 / 1024:.2f}MB"
            f"  命中 {item.secret_lines} 行 (SecretId {item.akid_lines})  [{flag}]"
        )
        if item.skipped_reason:
            print(f"      原因: {item.skipped_reason}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="清洗历史日志中的明文凭据（默认 dry-run）")
    parser.add_argument("--dir", type=Path, default=DEFAULT_LOG_DIR, help="日志目录（默认 backend/logs）")
    parser.add_argument("--apply", action="store_true", help="实际重写日志（默认只预演）")
    parser.add_argument("--verbose", action="store_true", help="列出所有文件（含 0 命中）")
    args = parser.parse_args(argv)

    print(f"当前时间: {datetime.now().isoformat(timespec='seconds')}")
    summary = clean_dir(args.dir, apply=args.apply)
    _print_summary(summary, verbose=args.verbose)

    if summary.error:
        return 2
    if summary.errors:
        # 跳过/失败的文件必须让人看见，否则「清洗完成」是假象
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
