"""T02027 取证（只读）：真实库中停摆告警是否存在「同一本地日多条 success」。

口径：notification_log.created_at 由 SQLite CURRENT_TIMESTAMP 写入，是 UTC naive；
按 UTC+8 转本地日期分组统计 success 条数，>1 即说明确实发生了重复告警。
"""
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "backend" / "data" / "news.db"
ET = "system.stall_alert"  # ALERT_EVENT_TYPE（app/services/stall_alert.py:34）

con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
rows = con.execute(
    "SELECT id, created_at, status, title FROM notification_log WHERE event_type = ? "
    "ORDER BY created_at",
    (ET,),
).fetchall()
if not rows:
    rows = con.execute(
        "SELECT DISTINCT event_type FROM notification_log"
    ).fetchall()
    print("no rows for event_type=%s; event_types in db: %s" % (ET, rows))
    raise SystemExit(0)

print(f"event_type={ET} 记录数={len(rows)}")
by_status = Counter(r[2] for r in rows)
print("按 status:", dict(by_status))

local_tz = datetime.now(timezone.utc).astimezone().tzinfo
by_local_day = Counter()
for _id, created, status, title in rows:
    dt = datetime.fromisoformat(str(created))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(local_tz)
    if status == "success":
        by_local_day[local.date().isoformat()] += 1

print("按本地日 success 计数:")
for day, cnt in sorted(by_local_day.items()):
    flag = "  <== 重复告警" if cnt > 1 else ""
    print(f"  {day} {cnt}{flag}")

dups = {d: c for d, c in by_local_day.items() if c > 1}
print(f"\n结论：同一本地日出现多条 success 的天数={len(dups)} {dups if dups else ''}")

print("\n最近 12 条明细（UTC / 本地 / status）:")
for _id, created, status, title in rows[-12:]:
    dt = datetime.fromisoformat(str(created)).replace(tzinfo=timezone.utc)
    print(f"  id={_id} utc={created} local={dt.astimezone(local_tz).isoformat()} "
          f"status={status} offset={dt.astimezone(local_tz).strftime('%z')} title={title[:28]}")
