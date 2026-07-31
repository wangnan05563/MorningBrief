"""诊断脚本2：验证 play_progress 表与 play_log 写入路径。"""
import sqlite3
import sys
from pathlib import Path

DB = Path(r"D:\code\otherProjects\20_News\backend\data\news.db")


def main() -> None:
    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()

    print("=== 1. play_progress 表数据 ===")
    try:
        cur.execute("SELECT COUNT(*) FROM play_progress")
        print(f"play_progress rows: {cur.fetchone()[0]}")
        cur.execute("PRAGMA table_info(play_progress)")
        cols = [r[1] for r in cur.fetchall()]
        print(f"Columns: {cols}")
        cur.execute("SELECT * FROM play_progress LIMIT 5")
        for r in cur.fetchall():
            print(" ", r)
        cur.execute("SELECT MIN(updated_at), MAX(updated_at) FROM play_progress")
        print(f"Time range: {cur.fetchone()}")
        # position 分布：检查是否有 position >= 30
        cur.execute(
            "SELECT COUNT(*) FROM play_progress WHERE position >= 30"
        )
        print(f"position >= 30 (达到播放阈值): {cur.fetchone()[0]}")
        cur.execute(
            "SELECT MIN(position), MAX(position), AVG(position) FROM play_progress"
        )
        print(f"position stats (min/max/avg): {cur.fetchone()}")
    except sqlite3.OperationalError as e:
        print(f"play_progress ERROR: {e}")

    print()
    print("=== 2. user 表详细数据 ===")
    cur.execute(
        "SELECT id, openid, nickname, total_listen_duration, "
        "total_listen_count, created_at FROM user"
    )
    for r in cur.fetchall():
        print(" ", r)

    print()
    print("=== 3. play_log 表索引 ===")
    cur.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' "
        "AND tbl_name='play_log'"
    )
    for r in cur.fetchall():
        print(f"  {r[0]}")
        print(f"    {r[1]}")

    print()
    print("=== 4. play_log 表触发器（看是否有拦截写入）===")
    cur.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='trigger' "
        "AND tbl_name='play_log'"
    )
    triggers = cur.fetchall()
    if not triggers:
        print("  no triggers on play_log")
    for r in triggers:
        print(f"  {r[0]}")
        print(f"    {r[1]}")

    conn.close()


if __name__ == "__main__":
    sys.exit(main())
