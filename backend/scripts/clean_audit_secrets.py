"""一次性清洗历史 audit_log 明文凭据（T02591）。

背景：`write_audit` 自 T02486 起写入前脱敏、`list_audit_logs` 读取后再脱敏，
但**修复前落库**的 `audit_log.detail` 仍是明文（密码哈希 / AI Key / 通知 token）。
审计页看不到，直接查库、导库或从备份文件里仍能看到。

本脚本用与运行时**同一套判定**（`app.services.db_admin_service._mask_audit_detail`）
把命中字段改写为 `***`。默认 dry-run，只报告行数与**字段路径**，绝不打印字段值。

用法（backend 目录下）：
    .venv/Scripts/python scripts/clean_audit_secrets.py                    # 预演 db_admin
    .venv/Scripts/python scripts/clean_audit_secrets.py --category all     # 预演全部类别
    .venv/Scripts/python scripts/clean_audit_secrets.py --apply            # 实际写库（自动留快照）
    .venv/Scripts/python scripts/clean_audit_secrets.py --backup-dir data/backup
    .venv/Scripts/python scripts/clean_audit_secrets.py --apply --include-backups

写库前置：--apply 会先在同目录留一份 `<db>.pre_audit_clean_<时间戳>.bak` 快照；
快照用 sqlite3 backup API 生成，WAL 里的未落盘内容也会包含在内。
清洗只在明确批准后执行；脚本本身可重复运行（已脱敏行不会再次计数）。
"""
import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.paths import resolve_data_dir, resolve_db_path  # noqa: E402
from app.services.db_admin_service import _mask_audit_detail  # noqa: E402

DEFAULT_CATEGORY = "db_admin"
SNAPSHOT_SUFFIX = ".pre_audit_clean"

# 仅用于「报告潜在明文」的取值形状扫描：这些值即使键名不含凭据语义，
# 也不该出现在审计里。只计数、不打印，避免脚本自己成为泄露通道。
_SECRET_VALUE_RE = re.compile(
    r"(AKID[A-Za-z0-9]{10,}|sk-[A-Za-z0-9_-]{16,}|"
    r"access_token=[A-Za-z0-9_-]{8,}|[0-9a-f]{32})"
)


@dataclass
class Change:
    """一条待改写审计行。"""

    id: int
    category: str
    action: str
    target: Optional[str]
    new_detail: str
    fields: list[str] = field(default_factory=list)


@dataclass
class Summary:
    """一次扫描/清洗的结果。"""

    path: Path
    category: Optional[str]
    applied: bool = False
    rows: int = 0
    changed: list[Change] = field(default_factory=list)
    by_category: dict[str, int] = field(default_factory=dict)
    unparsable: int = 0
    raw_secret_rows: int = 0
    snapshot: Optional[Path] = None
    error: Optional[str] = None


def _key_paths_changed(original: Any, masked: Any, prefix: str = "") -> list[str]:
    """返回被脱敏的字段路径；只给路径，不给值。"""
    if isinstance(original, dict) and isinstance(masked, dict):
        paths: list[str] = []
        for key in original:
            if key not in masked:
                continue
            prefix_key = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(original[key], (dict, list)):
                paths.extend(_key_paths_changed(original[key], masked[key], prefix_key))
            elif original[key] != masked[key]:
                paths.append(prefix_key)
        return paths
    if isinstance(original, list) and isinstance(masked, list):
        paths = []
        for index, (before, after) in enumerate(zip(original, masked)):
            paths.extend(_key_paths_changed(before, after, f"{prefix}[{index}]"))
        return paths
    return [prefix or "?"] if original != masked else []


def _connect(path: Path, writable: bool) -> sqlite3.Connection:
    if writable:
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA busy_timeout=5000")
        return conn
    # 只读 URI：dry-run 在数据库层面就无法写，避免「预演顺手改了库」
    uri = "file:" + str(path).replace("\\", "/") + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _iter_rows(conn: sqlite3.Connection, category: Optional[str]):
    sql = "SELECT id, category, action, target, detail FROM audit_log"
    params: tuple = ()
    if category:
        sql += " WHERE category = ?"
        params = (category,)
    sql += " ORDER BY id"
    return conn.execute(sql, params).fetchall()


def _plan_rows(rows: list[tuple], summary: Summary) -> list[Change]:
    changes: list[Change] = []
    for row_id, category, action, target, detail in rows:
        summary.rows += 1
        text = detail or ""
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            summary.unparsable += 1
            if _SECRET_VALUE_RE.search(text):
                summary.raw_secret_rows += 1
            continue
        masked = _mask_audit_detail(parsed, target)
        if masked == parsed:
            # 键名判定没命中、但值形状像凭据：脚本不改它（改了会误伤正常字段），
            # 只把它计成「需人工确认」，让非零退出码把它暴露出来。
            if _SECRET_VALUE_RE.search(text):
                summary.raw_secret_rows += 1
            continue
        fields = _key_paths_changed(parsed, masked)
        changes.append(
            Change(
                id=int(row_id),
                category=str(category),
                action=str(action or ""),
                target=target,
                new_detail=json.dumps(masked, ensure_ascii=False, default=str),
                fields=fields,
            )
        )
        summary.by_category[str(category)] = summary.by_category.get(str(category), 0) + 1
    summary.changed = changes
    return changes


def _snapshot(conn: sqlite3.Connection, db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = db_path.with_name(f"{db_path.name}{SNAPSHOT_SUFFIX}_{stamp}.bak")
    dst = sqlite3.connect(str(target))
    try:
        conn.backup(dst)
    finally:
        dst.close()
    return target


def clean_db(
    db_path: Path,
    category: Optional[str] = DEFAULT_CATEGORY,
    apply: bool = False,
) -> Summary:
    """扫描（并在 apply=True 时改写）一个 SQLite 文件里的 audit_log。"""
    summary = Summary(path=db_path, category=category, applied=apply)
    if not db_path.exists():
        summary.error = "数据库不存在"
        return summary
    conn = _connect(db_path, writable=apply)
    try:
        rows = _iter_rows(conn, category)
        changes = _plan_rows(rows, summary)
        if apply and changes:
            summary.snapshot = _snapshot(conn, db_path)
            with conn:
                conn.executemany(
                    "UPDATE audit_log SET detail = ? WHERE id = ?",
                    [(change.new_detail, change.id) for change in changes],
                )
    finally:
        conn.close()
    return summary


def scan_backup_dir(
    backup_dir: Path,
    category: Optional[str] = DEFAULT_CATEGORY,
    apply: bool = False,
) -> list[Summary]:
    """扫描目录下的 *.db 备份；apply=True 时才就地改写。"""
    if not backup_dir.is_dir():
        return []
    results = []
    for path in sorted(backup_dir.glob("*.db")):
        results.append(clean_db(path, category=category, apply=apply))
    return results


def _print_summary(summary: Summary, sample_limit: int = 5) -> None:
    mode = "APPLY（已写库）" if summary.applied else "DRY-RUN（只读预演）"
    print(f"库: {summary.path}")
    print(f"模式: {mode}  类别: {summary.category or '全部'}")
    if summary.error:
        print(f"  [error] {summary.error}")
        return
    print(
        f"  扫描 {summary.rows} 行 · 待改写 {len(summary.changed)} 行"
        f" · 不可解析 {summary.unparsable} 行"
        f" · 含凭据形状值 {summary.raw_secret_rows} 行"
    )
    for category, count in sorted(summary.by_category.items()):
        print(f"    - {category}: {count} 行")
    for change in summary.changed[:sample_limit]:
        fields = ", ".join(change.fields[:8])
        print(f"    id={change.id} [{change.category}/{change.action}] 字段: {fields}")
    if len(summary.changed) > sample_limit:
        print(f"    … 其余 {len(summary.changed) - sample_limit} 行未列出")
    if summary.snapshot:
        print(f"  清洗前快照: {summary.snapshot}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="清洗历史 audit_log 明文凭据（默认 dry-run）")
    parser.add_argument("--db", type=Path, default=None, help="数据库路径（默认 backend/data/news.db）")
    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY,
        help="只处理指定 category；all 表示全部（默认 db_admin）",
    )
    parser.add_argument("--apply", action="store_true", help="实际写库（默认只预演）")
    parser.add_argument("--backup-dir", type=Path, default=None, help="额外扫描的备份目录（*.db）")
    parser.add_argument(
        "--include-backups",
        action="store_true",
        help="配合 --apply 就地清洗备份文件；单独使用时只做预演",
    )
    parser.add_argument("--samples", type=int, default=5, help="每份库列出的样本行数")
    args = parser.parse_args(argv)

    db_path = args.db or resolve_db_path()
    category = None if args.category.lower() == "all" else args.category
    if args.include_backups and not args.apply:
        print("[warn] --include-backups 未配合 --apply，备份文件只做预演")

    print(f"当前时间: {datetime.now().isoformat(timespec='seconds')}")
    main_summary = clean_db(db_path, category=category, apply=args.apply)
    _print_summary(main_summary, args.samples)

    exit_code = 0
    if main_summary.error:
        exit_code = 2
    elif main_summary.raw_secret_rows:
        # 键名无法判定、但值形状像凭据且 detail 不是合法 JSON：脚本不能安全改写，
        # 必须人工处置，所以用非零退出码把它变成可见失败。
        exit_code = 1

    backup_dir = args.backup_dir
    if backup_dir is None and args.include_backups:
        backup_dir = resolve_data_dir() / "backup"
    if backup_dir is not None:
        print("-" * 78)
        backups = scan_backup_dir(
            backup_dir, category=category, apply=args.apply and args.include_backups
        )
        if not backups:
            print(f"备份目录无可扫描的 *.db: {backup_dir}")
        for summary in backups:
            _print_summary(summary, args.samples)
            if summary.error or summary.raw_secret_rows:
                exit_code = max(exit_code, 1)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
