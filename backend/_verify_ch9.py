"""临时脚本：触发 channel_id=9 工作流并等待完成，验证新 prompt 效果。"""
import httpx
import sqlite3
import time
import asyncio
import json

BASE = "http://127.0.0.1:8000"

# 从 .env 读取默认管理员
import os
from pathlib import Path
env_path = Path("data") / ".env"
admin_user = "admin"
admin_pwd = "admin123"  # 默认密码，由 lifespan 自动 seed

# 若 .env 中有自定义配置则覆盖
env_full = Path(".env")
if env_full.exists():
    for line in env_full.read_text(encoding="utf-8").splitlines():
        if line.startswith("ADMIN_USERNAME="):
            admin_user = line.split("=", 1)[1].strip() or "admin"
        if line.startswith("ADMIN_PASSWORD="):
            admin_pwd = line.split("=", 1)[1].strip() or "admin123"

print(f"使用管理员账号: {admin_user}")

# 1. 登录获取 token
async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        r = await client.post("/admin/api/v1/auth/login", json={"username": admin_user, "password": admin_pwd})
        if r.status_code != 200:
            print(f"登录失败: {r.status_code} {r.text}")
            return
        token = r.json().get("data", {}).get("token")
        if not token:
            print(f"未获取 token: {r.text}")
            return
        print(f"登录成功 token={token[:30]}...")

        # 2. 触发 channel_id=9 工作流
        r = await client.post(
            "/admin/api/v1/workflows/trigger",
            json={"channel_id": 9},
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code != 200:
            print(f"触发失败: {r.status_code} {r.text}")
            return
        wf_id = r.json().get("data", {}).get("workflow_id")
        print(f"触发成功 workflow_id={wf_id}")

        # 3. 轮询工作流状态
        for i in range(60):  # 最多等 10 分钟
            await asyncio.sleep(10)
            r = await client.get(
                f"/admin/api/v1/workflows/{wf_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code != 200:
                continue
            data = r.json().get("data", {})
            status = data.get("status")
            print(f"  [{i*10}s] workflow status={status}")
            if status in ("success", "failed", "cancelled"):
                # 工作流成功时 error 为 None，需兜底为空串避免 NoneType[:200] 抛 TypeError
                error = data.get("error", "") or ""
                print(f"工作流终态={status} error={error[:200]}")
                break

        # 4. 查询 script 表中的最新稿件
        conn = sqlite3.connect("data/news.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT id, workflow_id, substr(full_text, 1, 500) as preview, full_text "
            "FROM script WHERE workflow_id=? ORDER BY id DESC LIMIT 1",
            (wf_id,),
        ).fetchall()
        if not rows:
            print(f"未找到 workflow_id={wf_id} 的 script 记录")
            # 看是否在更早的 workflow
            rows = cur.execute(
                "SELECT id, workflow_id, substr(full_text, 1, 500) as preview, full_text "
                "FROM script WHERE workflow_id LIKE 'wf-2026072%' ORDER BY id DESC LIMIT 3"
            ).fetchall()

        for r in rows:
            print(f"\n=== script_id={r['id']} wf={r['workflow_id']} ===")
            print(f"前 500 字: {r['preview']}")
            # 检查重复度指标
            full = r["full_text"] or ""
            checks = ["老铁", "大佬", "神作", "真香", "接下来", "下面这条", "下面为您"]
            for kw in checks:
                cnt = full.count(kw)
                if cnt > 0:
                    print(f"  '{kw}' 出现 {cnt} 次")
        conn.close()

asyncio.run(main())
