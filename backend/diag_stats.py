"""统计问题诊断脚本：检查各业务表数据分布 + PlayLog 写入路径。

按 R168 前端列表空数据分层诊断：
1. API total 层（已知：所有指标=0）
2. 后端日志层（聚合 SQL 语法正常）
3. 数据库记录层（已发现 play_log 0 行）

本脚本进一步定位：
- 业务表是否有数据（判断业务是否跑过）
- play_log 写入路径是否会被正确触发
"""
import sqlite3
import sys
from pathlib import Path

DB = Path(r"D:\code\otherProjects\20_News\backend\data\news.db")


def main() -> None:
    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()

    print("=== 1. 各业务表数据分布 ===")
    tables = [
        "user",
        "episode",
        "material",
        "play_log",
        "channel",
        "workflow",
        "admin_user",
        "play_session",
    ]
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"  {t}: {cur.fetchone()[0]} rows")
        except sqlite3.OperationalError as e:
            print(f"  {t}: SKIP ({e})")

    print()
    print("=== 2. episode 表时间分布（最近10天）===")
    try:
        cur.execute("PRAGMA table_info(episode)")
        cols = [r[1] for r in cur.fetchall()]
        print(f"  episode columns: {cols}")
        time_col = None
        for cand in ("created_at", "published_at", "date"):
            if cand in cols:
                time_col = cand
                break
        if time_col:
            cur.execute(f"SELECT MIN({time_col}), MAX({time_col}) FROM episode")
            print(f"  {time_col} range: {cur.fetchone()}")
            cur.execute(
                f"SELECT date({time_col}) as d, COUNT(*) FROM episode "
                f"GROUP BY d ORDER BY d DESC LIMIT 10"
            )
            for r in cur.fetchall():
                print(f"    {r}")
        else:
            print("  no time column found")
    except sqlite3.OperationalError as e:
        print(f"  ERROR: {e}")

    print()
    print("=== 3. episode 状态分布（如果有 status 字段）===")
    try:
        cur.execute("PRAGMA table_info(episode)")
        cols = [r[1] for r in cur.fetchall()]
        if "status" in cols:
            cur.execute("SELECT status, COUNT(*) FROM episode GROUP BY status")
            for r in cur.fetchall():
                print(f"    status={r[0]}: {r[1]} rows")
    except sqlite3.OperationalError as e:
        print(f"  ERROR: {e}")

    print()
    print("=== 4. user 表分布 ===")
    try:
        cur.execute("PRAGMA table_info(user)")
        cols = [r[1] for r in cur.fetchall()]
        print(f"  user columns: {cols}")
        if "total_listen_duration" in cols:
            cur.execute(
                "SELECT COUNT(*), SUM(total_listen_duration), "
                "MAX(total_listen_duration) FROM user"
            )
            print(f"  total_listen_duration stats: {cur.fetchone()}")
    except sqlite3.OperationalError as e:
        print(f"  ERROR: {e}")

    print()
    print("=== 5. play_log 表结构 ===")
    cur.execute("SELECT sql FROM sqlite_master WHERE name='play_log'")
    row = cur.fetchone()
    if row:
        print(row[0])

    print()
    print("=== 6. material 表时间分布（最近10天）===")
    try:
        cur.execute("PRAGMA table_info(material)")
        cols = [r[1] for r in cur.fetchall()]
        print(f"  material columns: {cols}")
        if "crawled_at" in cols:
            cur.execute(
                "SELECT MIN(crawled_at), MAX(crawled_at) FROM material"
            )
            print(f"  crawled_at range: {cur.fetchone()}")
            cur.execute(
                "SELECT date(crawled_at) as d, COUNT(*) FROM material "
                "GROUP BY d ORDER BY d DESC LIMIT 10"
            )
            for r in cur.fetchall():
                print(f"    {r}")
    except sqlite3.OperationalError as e:
        print(f"  ERROR: {e}")

    conn.close()


if __name__ == "__main__":
    sys.exit(main())
