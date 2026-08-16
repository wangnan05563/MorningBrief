"""JMeter 性能测试清理脚本。

职责：
1. 删除测试用户（包括关联的 favorite / play_progress / comment 等数据）
2. 删除生成的 token 文件和用户信息文件

执行时机：测试全部完成后运行，避免污染生产数据。
"""
import json
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
DB_PATH = BACKEND_DIR / "data" / "news.db"
USER_INFO = Path(__file__).resolve().parent / "test_user_info.json"
TOKEN_FILE = Path(__file__).resolve().parent / "test_token.txt"

TEST_OPENID_PREFIX = "jmeter_test_"


def cleanup() -> int:
    if not DB_PATH.exists():
        print(f"[ERROR] 数据库不存在: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    try:
        # 查询所有测试用户（前缀匹配，防止遗留）
        cur = conn.execute(
            "SELECT id FROM user WHERE openid LIKE ?", (TEST_OPENID_PREFIX + "%",)
        )
        user_ids = [row[0] for row in cur.fetchall()]

        if not user_ids:
            print("[INFO] 未找到测试用户，无需清理")
            return 0

        placeholders = ",".join("?" * len(user_ids))

        # 删除关联数据（外键约束表）
        # 顺序：先删子表，再删父表，避免外键约束失败
        related_tables = [
            ("favorite", "user_id"),
            ("play_progress", "user_id"),
            ("play_log", "user_id"),
            ("comment", "user_id"),
            ("comment_like", "user_id"),
            ("feedback", "user_id"),
            ("subscription", "user_id"),
            ("channel_subscription", "user_id"),
        ]
        for table, col in related_tables:
            try:
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE {col} IN ({placeholders})",
                    user_ids,
                )
                if cur.rowcount > 0:
                    print(f"[OK] 删除 {table} 表 {cur.rowcount} 条关联记录")
            except sqlite3.OperationalError as e:
                # 表不存在时跳过（如 play_log 表名变化）
                if "no such table" in str(e):
                    continue
                raise

        # 删除测试用户
        cur = conn.execute(
            f"DELETE FROM user WHERE id IN ({placeholders})", user_ids
        )
        conn.commit()
        print(f"[OK] 删除 {cur.rowcount} 个测试用户: {user_ids}")
    finally:
        conn.close()

    # 删除临时文件
    for f in [TOKEN_FILE, USER_INFO]:
        if f.exists():
            f.unlink()
            print(f"[OK] 删除文件: {f.name}")

    return 0


if __name__ == "__main__":
    sys.exit(cleanup())
