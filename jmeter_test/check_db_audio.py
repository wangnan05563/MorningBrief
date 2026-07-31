"""检查数据库中所有 episode 的 audio_url 字段。"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(r"d:\code\otherProjects\20_News\backend\data\news.db")
if not DB_PATH.exists():
    print(f"[ERROR] DB not found: {DB_PATH}")
    sys.exit(1)

conn = sqlite3.connect(str(DB_PATH))
try:
    cur = conn.execute(
        "SELECT id, channel_id, title, audio_url, status, date FROM episode ORDER BY id DESC LIMIT 20"
    )
    rows = cur.fetchall()
    print(f"总记录数（最近 20 条）: {len(rows)}\n")
    print(f"{'ID':<5} {'CH':<4} {'Status':<10} {'Date':<12} {'Audio URL':<60} Title")
    print("-" * 150)
    for r in rows:
        eid, ch, title, url, status, date = r
        title_short = (title or "")[:40]
        url_short = (url or "")[:80]
        print(f"{eid:<5} {ch:<4} {status:<10} {str(date):<12} {url_short:<60} {title_short}")

    # 统计 URL 类型
    print("\n=== URL 来源统计 ===")
    cur = conn.execute("SELECT COUNT(*) FROM episode WHERE audio_url LIKE '%myqcloud.com%'")
    cos_count = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM episode WHERE audio_url LIKE '%ts.net%'")
    ts_count = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM episode WHERE audio_url LIKE '/audio/%'")
    local_count = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM episode WHERE audio_url IS NULL OR audio_url = ''")
    null_count = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM episode")
    total = cur.fetchone()[0]
    print(f"  总数: {total}")
    print(f"  COS (myqcloud.com): {cos_count}")
    print(f"  Tailscale (ts.net): {ts_count}")
    print(f"  本地 (/audio/): {local_count}")
    print(f"  空: {null_count}")
finally:
    conn.close()
