"""T02138 UI 实测用隔离后端：库指向 news.db 副本（含注入的逐渠道明细行）后起 uvicorn。

两点与 T02028 脚本的差异：
- 端口用 8010，避免撞上用户本机正在运行的桌面实例（8000）；
- APP_ROLE=api：跳过一次性职责（模板 seed / APScheduler / 启动补跑清理），
  第二个实例不会拉起工作流调度器去跑停摆告警等定时任务。
只读验证前端渲染，不写生产库、不发真实通知。
"""
import os
import sys
from pathlib import Path

os.environ["APP_ROLE"] = "api"

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

DB_COPY = Path(__file__).with_name("t02138_smoke") / "news.db"
assert DB_COPY.exists(), f"副本库不存在：{DB_COPY}（先跑 t02138_uisetup.py）"

from app import paths  # noqa: E402

paths.resolve_db_path = lambda *a, **k: DB_COPY

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8010, log_level="warning")
