import sqlite3

conn = sqlite3.connect('data/news.db')
cur = conn.cursor()

# 1. material 表状态
print("=== material 表状态 ===")
cur.execute("SELECT COUNT(*) FROM material")
print(f"material 总数: {cur.fetchone()[0]}")
cur.execute("SELECT status, COUNT(*) FROM material GROUP BY status")
for r in cur.fetchall():
    print(f"  status={r[0]} count={r[1]}")

# 2. crawler_dedup 表状态
print("\n=== crawler_dedup 表状态 ===")
cur.execute("SELECT COUNT(*) FROM crawler_dedup")
print(f"crawler_dedup 总数: {cur.fetchone()[0]}")

# 3. workflow 表状态
print("\n=== workflow 表状态 ===")
cur.execute("SELECT COUNT(*) FROM workflow")
print(f"workflow 总数: {cur.fetchone()[0]}")

# 4. channel 表 - 查看哪些频道配置了 rss_sources
print("\n=== channel 表 ===")
cur.execute("PRAGMA table_info(channel)")
cols = [r[1] for r in cur.fetchall()]
print(f"channel 字段: {cols}")
if 'rss_sources' in cols:
    cur.execute("SELECT id, name, rss_sources, keywords FROM channel ORDER BY id")
    for r in cur.fetchall():
        print(f"  id={r[0]} name={r[1]} rss_sources={r[2]} keywords={r[3]}")
else:
    print("  rss_sources 字段不存在（迁移未执行）")
    cur.execute("SELECT id, name FROM channel ORDER BY id")
    for r in cur.fetchall():
        print(f"  id={r[0]} name={r[1]}")

# 5. material 表字段
print("\n=== material 表字段 ===")
cur.execute("PRAGMA table_info(material)")
cols_m = [r[1] for r in cur.fetchall()]
print(f"material 字段: {cols_m}")

# 6. 检查 crawler_dedup 表结构
print("\n=== crawler_dedup 表结构 ===")
cur.execute("PRAGMA table_info(crawler_dedup)")
for r in cur.fetchall():
    print(f"  {r[1]} {r[2]}")

# 7. 如果有 crawler_dedup 数据，看几条
cur.execute("SELECT * FROM crawler_dedup LIMIT 5")
rows = cur.fetchall()
if rows:
    print(f"\n=== crawler_dedup 样本 {len(rows)} 条 ===")
    for r in rows:
        print(f"  {r}")
else:
    print("\ncrawler_dedup 表为空")

conn.close()
