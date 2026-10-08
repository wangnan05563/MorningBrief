"""反向清理 seed_perf_data.py 灌入的基准夹具数据，还原干净 dev 库。

仅删除 seed_perf_data.py 注入的标记行，不动任何原始开发数据：
- user:            openid LIKE 'jmeter_perf_%'
- episode:         audio_url LIKE 'http://127.0.0.1:8000/audio/perf_%' 或 title LIKE '性能测试节目%'
- channel:         name LIKE '性能测试频道%'
- feedback:        id LIKE 'perf%'
- comment/favorite:user_id IN (perf 用户 id 转字符串)  —— seed 把整数 id 当字符串存
- play_log/play_progress/channel_subscription: user_id IN (perf 用户 id 整数)

删除顺序：先子表后父表（comment/favorite/play_log/play_progress/channel_subscription/
feedback -> episode -> channel -> user），并用 PRAGMA foreign_keys=OFF 防止级联意外。

附带：将 logs/ 下超过 100MB 的 MorningBrief 日志截断（轮转），还原干净日志。

用法：
    python cleanup_seed.py
可选先 dry-run 看计数：
    python cleanup_seed.py --dry
"""
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
_REPO = HERE.parent if (HERE.parent / "backend").exists() else HERE.parent.parent
DB = _REPO / "backend" / "data" / "news.db"
BACKUP_DIR = _REPO / "backend" / "data" / "backup"
LOGS_DIR = _REPO / "backend" / "logs"

PERF_USER_Q = "SELECT id FROM user WHERE openid LIKE 'jmeter_perf_%'"
PERF_USER_STR_Q = "SELECT CAST(id AS TEXT) FROM user WHERE openid LIKE 'jmeter_perf_%'"

# 删除顺序：先子表后父表；comment_like 必须在 comment 删除之前
DELETE_SPEC = [
    ("comment_like", f"comment_id IN (SELECT id FROM comment WHERE user_id IN ({PERF_USER_STR_Q}))"),
    ("comment", f"user_id IN ({PERF_USER_STR_Q})"),
    ("favorite", f"user_id IN ({PERF_USER_STR_Q})"),
    ("play_log", f"user_id IN ({PERF_USER_Q})"),
    ("play_progress", f"user_id IN ({PERF_USER_Q})"),
    ("channel_subscription", f"user_id IN ({PERF_USER_Q})"),
    ("feedback", "id LIKE 'perf%'"),
    ("episode", "audio_url LIKE 'http://127.0.0.1:8000/audio/perf_%' OR title LIKE '性能测试节目%'"),
    ("channel", "name LIKE '性能测试频道%'"),
    ("user", "openid LIKE 'jmeter_perf_%'"),
]


TEST_USER_OPENID_Q = r"SELECT id, openid FROM user WHERE openid LIKE 'jmeter\_test\_%' ESCAPE '\'"


def test_user_specs(conn):
    """压测写路径由 API 落库的请求行 —— setup.py 建的合成测试用户（jmeter_test_ 前缀）。

    为什么必须单独清：API 侧 user_id 口径不统一，comment/favorite/feedback 存 openid，
    play_log/play_progress/channel_subscription 存数字 id；而 DELETE_SPEC 只按
    perf 用户的数字串匹配，实测每跑一轮门禁就在开发库上多一层残渣（T01581）。
    这里两种口径一起匹配，并连测试用户本身一并删除，使库回到压测前状态
    （下一轮 setup.py 会幂等重建）。
    """
    rows = conn.execute(TEST_USER_OPENID_Q).fetchall()
    if not rows:
        return []
    ids = [r[0] for r in rows]
    opens = [r[1] for r in rows]
    ids_txt = ",".join(f"'{i}'" for i in ids)                      # 数字 id 的字符串写法
    opens_txt = ",".join("'" + o.replace("'", "''") + "'" for o in opens)
    both = f"user_id IN ({ids_txt},{opens_txt})"
    ints = ",".join(str(i) for i in ids)
    return [
        ("comment_like", f"comment_id IN (SELECT id FROM comment WHERE {both})"),
        ("comment", both),
        ("favorite", both),
        ("play_log", f"user_id IN ({ints})"),
        ("play_progress", f"user_id IN ({ints})"),
        ("channel_subscription", f"user_id IN ({ints})"),
        ("feedback", both),
        ("user", f"openid IN ({opens_txt})"),
    ]


COUNT_SPEC = [
    ("user(jmeter_perf_)", "user", "openid LIKE 'jmeter_perf_%'"),
    ("episode(audio_url perf)", "episode", "audio_url LIKE 'http://127.0.0.1:8000/audio/perf_%'"),
    ("episode(title 性能测试节目)", "episode", "title LIKE '性能测试节目%'"),
    ("channel(性能测试频道)", "channel", "name LIKE '性能测试频道%'"),
    ("comment(by perf str)", "comment", f"user_id IN ({PERF_USER_STR_Q})"),
    ("favorite(by perf str)", "favorite", f"user_id IN ({PERF_USER_STR_Q})"),
    ("play_log(by perf int)", "play_log", f"user_id IN ({PERF_USER_Q})"),
    ("play_progress(by perf int)", "play_progress", f"user_id IN ({PERF_USER_Q})"),
    ("channel_subscription(by perf int)", "channel_subscription", f"user_id IN ({PERF_USER_Q})"),
    ("feedback(id perf%)", "feedback", "id LIKE 'perf%'"),
]


def main():
    dry = "--dry" in sys.argv
    if not DB.exists():
        print(f"[ERROR] DB not found: {DB}")
        return 1

    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA foreign_keys=OFF")
    cur = conn.cursor()

    # 压测写路径由 API 落库的行按测试用户（jmeter_test_ 前缀）一并还原，与 seed 夹具同批清理
    specs = DELETE_SPEC + test_user_specs(cur)

    print("=== 删除前计数 ===")
    before = {}
    for label, table, where in COUNT_SPEC:
        n = cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
        before[label] = n
        print(f"  {label:34s} -> {n}")
    perf_tables = {(t, w) for t, w in DELETE_SPEC}
    for table, where in specs:
        if (table, where) in perf_tables:
            continue
        n = cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
        label = f"{table}(by test user)"
        before[label] = n
        print(f"  {label:34s} -> {n}")

    if dry:
        print("\n[DRY-RUN] 未做任何修改。")
        conn.close()
        return 0

    # 备份（仅当确有种子数据要删）
    if sum(before.values()) > 0:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        bak = BACKUP_DIR / f"news_pre_seedpurge_{date.today().isoformat()}.db"
        shutil.copy2(str(DB), str(bak))
        print(f"\n[BACKUP] -> {bak} ({bak.stat().st_size/1024/1024:.2f} MB)")

    print("\n=== 删除 ===")
    for table, where in specs:
        cur.execute(f"DELETE FROM {table} WHERE {where}")
        print(f"  DELETE {table:22s}: {cur.rowcount} 行")
    conn.commit()

    print("\n=== 删除后计数 ===")
    for label, table, where in COUNT_SPEC:
        n = cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
        print(f"  {label:34s} -> {n}")

    print("\n[INTEGRITY]", conn.execute("PRAGMA integrity_check").fetchone()[0])
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("VACUUM")
    conn.close()
    print(f"[DB] size={DB.stat().st_size/1024/1024:.2f} MB")

    # 轮转超大日志（>100MB 的 MorningBrief 日志）
    print("\n=== 日志轮转 ===")
    truncated = False
    for log in sorted(LOGS_DIR.glob("MorningBrief_*.log")):
        sz = log.stat().st_size
        if sz > 100 * 1024 * 1024:
            log.write_text("")  # 截断为 0 字节
            print(f"  TRUNCATE {log.name} ({sz/1024/1024:.1f} MB -> 0)")
            truncated = True
    if not truncated:
        print("  (无 >100MB 日志，跳过)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
