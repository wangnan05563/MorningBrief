"""T02030 副本库实跑：真实 .env 配置 + 新代码，验证 Hub 不加载占位符渠道后的落库形态。

安全边界：
- 只把真实库**复制**到 _validate/t02030_copydb/news.db，app 指向副本，绝不写 backend/data/news.db
- 全程不发送真实通知：占位符被拦在 is_configured 之前 → hub 加载 0 个渠道 → total==0 短路
"""
import json

import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent / "backend"
COPY_DIR = HERE / "t02030_copydb"
COPY_DB = COPY_DIR / "news.db"

sys.path.insert(0, str(BACKEND))

COPY_DIR.mkdir(exist_ok=True)
if COPY_DB.exists():
    COPY_DB.unlink()
# 用 SQLite backup API 而不是文件拷贝：真实库正被桌面端打开，直接 copy 可能读到半写状态
_src = sqlite3.connect(f"file:{(BACKEND / 'data' / 'news.db').as_posix()}?mode=ro", uri=True)
_dst = sqlite3.connect(COPY_DB)
with _src, _dst:
    _src.backup(_dst)
_src.close()
_dst.close()

import app.paths as paths  # noqa: E402

paths.resolve_data_dir = lambda: COPY_DIR  # sqlite_url 运行时走这里

from app.database import AsyncSessionLocal  # noqa: E402
from app.services.stall_alert import ALERT_EVENT_TYPE, check_and_alert  # noqa: E402

OUT = HERE / "t02030_copydb_run.txt"
lines = [f"副本库: {COPY_DB}"]


def dump() -> None:
    conn = sqlite3.connect(f"file:{COPY_DB.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT id, status, error, payload FROM notification_log "
            "WHERE event_type=? ORDER BY id DESC LIMIT 6",
            (ALERT_EVENT_TYPE,),
        ).fetchall()
    finally:
        conn.close()
    lines.append(f"-- 副本库最新 6 条 system.stall_alert（新→旧）--")
    for rid, status, error, payload in rows:
        pl = json.loads(payload or "{}")
        lines.append(
            f"id={rid} status={status}\n  error={error}\n"
            f"  payload.channels={pl.get('channels')}\n"
            f"  payload.hub={pl.get('hub')}"
        )


import asyncio  # noqa: E402


async def run_checks() -> None:
    lines.append("-- 连续 4 次 check_and_alert（真实配置，副本库）--")
    for i in range(4):
        async with AsyncSessionLocal() as s:
            r = await check_and_alert(s)
        lines.append(
            f"  第{i + 1}次: status={r['status']} reason={r.get('reason', '')} "
            f"failed_today={r.get('failed_today', '')}"
        )


asyncio.run(run_checks())
dump()
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
