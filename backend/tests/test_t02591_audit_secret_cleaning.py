"""T02591：历史 audit_log 明文一次性清洗脚本的判定与安全边界。

脚本本身是破坏性工具，所以用例的目标不是「能跑」，而是钉住四条不许退化的性质：
1. dry-run 绝不写库；
2. 只改命中字段，其余字段与行数原样；
3. 重复执行不再计数（幂等）；
4. 不可解析的行宁可报失败也不猜着改。
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

import clean_audit_secrets as cleaner  # noqa: E402

SECRET = "sk-REDACT-ME-1234567890"
AKID = "AKIDabcdefghij1234567890"


def _make_db(path: Path, rows: list[dict]) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE audit_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, action TEXT, "
            "target TEXT, operator TEXT, detail TEXT, created_at TEXT)"
        )
        for row in rows:
            conn.execute(
                "INSERT INTO audit_log (category, action, target, operator, detail, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row.get("category", "db_admin"),
                    row.get("action", "update"),
                    row.get("target", "admin_user"),
                    row.get("operator", "legacy"),
                    row.get("detail"),
                    row.get("created_at", "2026-01-01 00:00:00"),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _details(path: Path) -> dict[int, str]:
    conn = sqlite3.connect(str(path))
    try:
        return {row[0]: row[1] for row in conn.execute("SELECT id, detail FROM audit_log")}
    finally:
        conn.close()


def _legacy_secret_row() -> dict:
    return {
        "detail": json.dumps(
            {
                "pk": "7",
                "values": {"password_hash": SECRET, "username": "admin", "remark": "ok"},
                "notify": {"access_token": SECRET},
            },
            ensure_ascii=False,
        )
    }


def test_dry_run_reports_fields_without_writing(tmp_path):
    db = tmp_path / "news.db"
    _make_db(db, [_legacy_secret_row(), {"detail": '{"pk": "1", "values": {"username": "a"}}'}])
    before = _details(db)

    summary = cleaner.clean_db(db, apply=False)

    assert summary.rows == 2
    assert len(summary.changed) == 1
    assert summary.changed[0].fields == [
        "values.password_hash",
        "notify.access_token",
    ]
    assert summary.by_category == {"db_admin": 1}
    assert _details(db) == before, "dry-run 改动了库"


def test_apply_masks_only_hit_fields_and_keeps_row_shape(tmp_path):
    db = tmp_path / "news.db"
    _make_db(db, [dict(_legacy_secret_row(), **{"created_at": "2025-06-01 00:00:00"})])

    summary = cleaner.clean_db(db, apply=True)

    assert len(summary.changed) == 1
    assert summary.snapshot is not None and summary.snapshot.exists()
    assert cleaner.SNAPSHOT_SUFFIX in summary.snapshot.name
    # 快照必须是清洗前的忠实副本，才能当回滚材料
    assert SECRET in next(iter(_details(summary.snapshot).values()))

    detail = json.loads(next(iter(_details(db).values())))
    assert detail["pk"] == "7"
    assert detail["values"]["username"] == "admin"
    assert detail["values"]["remark"] == "ok"
    assert detail["values"]["password_hash"] == "***"
    assert detail["notify"]["access_token"] == "***"
    assert SECRET not in json.dumps(detail, ensure_ascii=False)

    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT category, action, target, operator, created_at FROM audit_log"
        ).fetchone()
        count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    finally:
        conn.close()
    assert count == 1
    assert row == ("db_admin", "update", "admin_user", "legacy", "2025-06-01 00:00:00")


def test_apply_is_idempotent(tmp_path):
    db = tmp_path / "news.db"
    _make_db(db, [_legacy_secret_row()])

    assert len(cleaner.clean_db(db, apply=True).changed) == 1
    second = cleaner.clean_db(db, apply=True)
    assert second.changed == []
    assert second.snapshot is None, "没有改动时不该再产快照"


def test_category_filter_limits_scope(tmp_path):
    db = tmp_path / "news.db"
    _make_db(
        db,
        [
            _legacy_secret_row(),
            {
                "category": "review",
                "action": "force_pass",
                "target": "review",
                "detail": json.dumps({"values": {"password": SECRET}}),
            },
        ],
    )

    only_db_admin = cleaner.clean_db(db, category="db_admin", apply=True)
    # 先钉住越权红线（另一 category 的行必须原样），再核对计数：
    # 反过来的话「过滤失效」只会表现为 assert 2 == 1，看不出是越权。
    details = _details(db)
    review_detail = json.loads(details[2])
    assert review_detail["values"]["password"] == SECRET, "越过了 category 过滤"
    assert len(only_db_admin.changed) == 1

    everything = cleaner.clean_db(db, category=None, apply=True)
    assert len(everything.changed) == 1
    assert json.loads(_details(db)[2])["values"]["password"] == "***"


def test_ai_config_fail_safe_masks_bare_config_value(tmp_path):
    """与写入口径一致：只带 config_value、拿不到 config_key 时按明文处理。"""
    db = tmp_path / "news.db"
    _make_db(
        db,
        [
            {
                "target": "ai_config",
                "detail": json.dumps({"values": {"config_value": SECRET}}),
            }
        ],
    )

    cleaner.clean_db(db, apply=True)
    masked = json.loads(next(iter(_details(db).values())))
    assert masked["values"]["config_value"] == "***"


def test_unparsable_secret_like_row_is_reported_not_rewritten(tmp_path, capsys):
    db = tmp_path / "news.db"
    broken = f'{{"path": "C:\\data\\{AKID}.db"}}'  # 反斜杠未转义：历史 f-string 落库形态
    _make_db(db, [{"detail": broken}])

    summary = cleaner.clean_db(db, apply=False)
    assert summary.unparsable == 1
    assert summary.raw_secret_rows == 1
    assert summary.changed == []
    assert _details(db)[1] == broken

    code = cleaner.main(["--db", str(db)])
    assert code == 1, "含凭据形状但不可解析的行必须让脚本以非零码可见失败"
    out = capsys.readouterr().out
    assert AKID not in out, "脚本不能把凭据值打到控制台"


def test_cli_dry_run_prints_counts_but_never_values(tmp_path, capsys):
    db = tmp_path / "news.db"
    _make_db(db, [_legacy_secret_row()])

    assert cleaner.main(["--db", str(db)]) == 0

    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "待改写 1 行" in out
    assert "values.password_hash" in out
    assert SECRET not in out
    assert _details(db)  # 仍然原样


def test_backup_dir_is_previewed_then_cleaned_only_with_include_backups(tmp_path):
    live = tmp_path / "news.db"
    _make_db(live, [{"detail": '{"pk": "1"}'}])
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    backup = backup_dir / "news_backup_20260101_000000.db"
    _make_db(backup, [_legacy_secret_row()])

    # 只给 --backup-dir：预演，不动备份文件
    assert cleaner.main(["--db", str(live), "--backup-dir", str(backup_dir)]) == 0
    assert SECRET in next(iter(_details(backup).values()))

    # --include-backups 不配 --apply 仍是预演
    assert cleaner.main(["--db", str(live), "--backup-dir", str(backup_dir), "--include-backups"]) == 0
    assert SECRET in next(iter(_details(backup).values()))

    # 真正写库时才清洗备份，并在备份目录留快照（.bak 不会被下一轮 *.db 扫描到）
    assert cleaner.main(
        ["--db", str(live), "--backup-dir", str(backup_dir), "--apply", "--include-backups"]
    ) == 0
    masked = json.loads(next(iter(_details(backup).values())))
    assert masked["values"]["password_hash"] == "***"
    assert SECRET not in json.dumps(masked, ensure_ascii=False)
    assert list(backup_dir.glob(f"*.db{cleaner.SNAPSHOT_SUFFIX}_*.bak"))


def test_missing_database_exits_nonzero(tmp_path):
    assert cleaner.main(["--db", str(tmp_path / "nope.db")]) == 2


@pytest.mark.parametrize("shape", ["AKID", "sk", "token", "hex32"])
def test_secret_value_shape_detector(shape):
    samples = {
        "AKID": AKID,
        "sk": SECRET,
        "token": "access_token=abcdefghijklmnop",
        "hex32": "0123456789abcdef0123456789abcdef",
    }
    assert cleaner._SECRET_VALUE_RE.search(samples[shape])


# ---- 写入侧：备份模块的审计 detail 必须是合法 JSON ----
# 历史 3 行「不可解析」就是这里用 f-string 拼 Windows 路径造成的：
# `{"path": "D:\data\..."}` 里的 \d 是非法转义。清洗脚本遇到这种行只能报失败，
# 所以要同时在源头堵住，否则脚本永远追不上新产生的脏行。

WINDOWS_PATH = r"D:\data\backup\news_backup_20260101_000000.db"


async def test_backup_audit_details_parse_as_json(client, admin_token, db_session, monkeypatch):
    from sqlalchemy import select

    from app.models.audit_log import AuditLog
    from app.routers.admin import backup as backup_router
    from app.services.backup_service import BackupService

    async def fake_backup() -> str:
        return WINDOWS_PATH

    async def fake_cleanup(keep_days: int = 7, max_files: int = 7) -> int:
        return 2

    async def fake_restore(path: str) -> bool:
        return True

    monkeypatch.setattr(BackupService, "backup_database", staticmethod(fake_backup))
    monkeypatch.setattr(BackupService, "cleanup_old_backups", staticmethod(fake_cleanup))
    monkeypatch.setattr(BackupService, "restore_backup", staticmethod(fake_restore))
    monkeypatch.setattr(backup_router, "CONFIRM_TOKEN", "server-side-only-secret")

    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    assert client.post("/admin/api/v1/backups", headers=headers).status_code == 200
    assert client.post("/admin/api/v1/backups/cleanup", headers=headers).status_code == 200
    assert client.post(
        "/admin/api/v1/backups/restore",
        json={
            "backup_path": WINDOWS_PATH,
            "confirm_text": "news_backup_20260101_000000.db",
        },
        headers=headers,
    ).status_code == 200

    logs = (await db_session.execute(select(AuditLog).where(AuditLog.category == "backup"))).scalars().all()
    assert len(logs) == 3
    details = {}
    for log in logs:
        parsed = json.loads(log.detail)  # 历史 f-string 写法在这里会抛 JSONDecodeError
        details[log.action] = parsed
    assert details["create"] == {"path": WINDOWS_PATH}
    assert details["restore"] == {"source": WINDOWS_PATH}
    assert details["cleanup"] == {"deleted": 2, "keep_days": 7, "max_files": 7}
