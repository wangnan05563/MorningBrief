"""临时排查脚本：检查 ai_config 表中的通知配置。"""
import sqlite3

conn = sqlite3.connect('data/news.db')
cur = conn.cursor()
cur.execute("SELECT config_key, config_value FROM ai_config WHERE config_key LIKE 'notify_%'")
rows = cur.fetchall()
print("==== ai_config notify_* ====")
for r in rows:
    # 脱敏显示 secret
    k, v = r
    if 'secret' in k and v:
        v = f"****{v[-4:]}" if len(v) > 4 else "****"
    print(f"  {k} = {v!r}")

print("\n==== notification_template ====")
cur.execute("SELECT id, event_type, name, enabled FROM notification_template")
for r in cur.fetchall():
    print(f"  {r}")

print("\n==== notification_log recent 10 ====")
cur.execute("SELECT id, event_type, status, error, workflow_id, created_at FROM notification_log ORDER BY id DESC LIMIT 10")
for r in cur.fetchall():
    err = r[3][:80] if r[3] else ""
    print(f"  id={r[0]} event={r[1]} status={r[2]} wf={r[4]} time={r[5]}")
    if err:
        print(f"    err: {err}")

conn.close()
