"""诊断 3 条豆瓣电影评论被去重的原因。
URL 精确去重 vs SimHash 近似去重。
"""
import hashlib
import sqlite3

DB = r"d:\code\otherProjects\20_News\backend\data\news.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 从日志得知 3 条豆瓣电影评论 URL
douban_urls = [
    "https://movie.douban.com/review/17727639/",
    "https://movie.douban.com/review/17726565/",
    "https://movie.douban.com/review/17728057/",
]

print("=" * 70)
print("1. 检查 crawler_dedup 中 douban.com URL 精确去重")
print("=" * 70)
for url in douban_urls:
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cur.execute("SELECT id, url, simhash, created_at FROM crawler_dedup WHERE url_hash = ?", (url_hash,))
    row = cur.fetchone()
    if row:
        print(f"  URL 命中: {url}")
        print(f"    dedup id={row['id']} created={row['created_at']} sim={row['simhash']}")
    else:
        print(f"  URL 未命中: {url}")

# 也检查 douban.com 在 dedup 表中的总量
print("\n2. crawler_dedup 中 douban.com 记录数:")
cur.execute("SELECT COUNT(*) AS c FROM crawler_dedup WHERE url LIKE '%douban.com%'")
print(f"  {cur.fetchone()['c']} 条")

print("\n3. material 表中 douban.com 记录数:")
cur.execute("SELECT COUNT(*) AS c FROM material WHERE url LIKE '%douban.com%'")
print(f"  {cur.fetchone()['c']} 条")

# SimHash 近似去重检查：计算 3 条评论标题的 simhash，与 dedup 表全量比较
print("\n" + "=" * 70)
print("4. SimHash 近似去重检查")
print("=" * 70)

# 需要知道 3 条评论的标题。从 RSS feed 获取或从日志推断
# 日志中没有标题，但可以从 DB 查（如果有历史入库）
cur.execute("""
    SELECT title, url, simhash FROM material
    WHERE url LIKE '%movie.douban.com/review%'
    ORDER BY crawled_at DESC LIMIT 10
""")
rows = cur.fetchall()
print(f"material 表中豆瓣电影评论历史记录: {len(rows)} 条")
for r in rows:
    print(f"  sim={r['simhash']} | {r['title'][:40]}")
    print(f"    {r['url']}")

# 如果有历史记录，检查其 simhash 是否在 dedup 表中
if rows:
    from app.core.simhash import hamming_distance
    # 取 dedup 表全量 simhash
    cur.execute("SELECT id, url, simhash FROM crawler_dedup WHERE simhash IS NOT NULL")
    dedup_hashes = cur.fetchall()
    print(f"\ndedup 表 simhash 总量: {len(dedup_hashes)}")

    for r in rows[:3]:
        print(f"\n  检查标题: {r['title'][:40]}")
        print(f"  simhash: {r['simhash']}")
        matches = []
        for d in dedup_hashes:
            try:
                dist = hamming_distance(r["simhash"], d["simhash"])
                if dist <= 3:
                    matches.append((d["id"], d["url"], dist, d["simhash"]))
            except Exception:
                continue
        if matches:
            print(f"  ⚠ SimHash 命中 {len(matches)} 条:")
            for m in matches[:5]:
                print(f"    dedup id={m[0]} dist={m[2]} sim={m[3]}")
                print(f"      url={m[1]}")
        else:
            print(f"  ✓ SimHash 未命中")

conn.close()
