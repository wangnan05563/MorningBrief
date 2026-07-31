"""触发频道 4 工作流并轮询 crawl 步骤结果，验证修复效果。

直接调用 workflow_scheduler.trigger_workflow 绕过 admin 认证，
触发后轮询 workflow_step 表直到 crawl 步骤完成（success/failed）。
"""
import asyncio
import sqlite3
from datetime import date

# 必须先初始化 logging，避免 asyncio 内部日志丢失
from app.core.logging_setup import setup_logging
setup_logging(log_level="INFO", log_dir="./logs")

from app.services.workflow_scheduler import workflow_scheduler

DB = r"d:\code\otherProjects\20_News\backend\data\news.db"


async def main():
    # 启动调度器（trigger_workflow 依赖调度器内部状态）
    await workflow_scheduler.start()
    print("=" * 70)
    print("触发频道 4（娱乐焦点）工作流")
    print("=" * 70)

    wf_id = await workflow_scheduler.trigger_workflow(
        episode_date=date.today(),
        source="manual",
        channel_id=4,
        triggered_by="diag_verify",
    )
    print(f"工作流已触发: {wf_id}")

    # 轮询 crawl 步骤状态（最多等 180 秒）
    print("\n轮询 crawl 步骤状态...")
    import time
    deadline = time.time() + 180
    last_status = None
    while time.time() < deadline:
        await asyncio.sleep(3)
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT step_name, status, error, result
            FROM workflow_step
            WHERE workflow_id = ? AND step_name = 'crawl'
        """, (wf_id,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            print(f"  [{time.strftime('%H:%M:%S')}] crawl 步骤尚未创建...")
            continue
        status = row["status"]
        if status != last_status:
            print(f"  [{time.strftime('%H:%M:%S')}] crawl status = {status}")
            last_status = status
        if status in ("success", "failed"):
            print(f"\ncrawl 步骤完成: {status}")
            if row["error"]:
                print(f"  error: {row['error']}")
            if row["result"]:
                import json
                try:
                    result = json.loads(row["result"])
                    print(f"  result: {json.dumps(result, ensure_ascii=False, indent=2)[:1500]}")
                except Exception:
                    print(f"  result(raw): {row['result'][:500]}")
            break
    else:
        print("\n⚠ 超时 180 秒，crawl 步骤未完成")

    # 查 material 表新增情况
    print("\n" + "=" * 70)
    print(f"工作流 {wf_id} 的 material 入库情况")
    print("=" * 70)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM material WHERE workflow_id = ?", (wf_id,))
    count = cur.fetchone()["c"]
    print(f"material 入库数: {count}")
    if count > 0:
        cur.execute("""
            SELECT title, url, published_at, source
            FROM material WHERE workflow_id = ?
            ORDER BY crawled_at DESC LIMIT 10
        """, (wf_id,))
        print(f"前 10 条:")
        for r in cur.fetchall():
            print(f"  [{r['source']}] {r['published_at']} | {r['title'][:40]}")
    conn.close()

    # 停止调度器
    await workflow_scheduler.stop()
    print("\n验证完成。")


asyncio.run(main())
