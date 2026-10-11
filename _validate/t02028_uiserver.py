"""T02028 UI 实测用后端：把库路径指向 news.db 的副本后启动 uvicorn。

为什么用副本：审核列表要看到 T02028 新链路写出的真实行（measured/original/supplement），
而生产库的历史行按设计不回填（全是 NULL），列渲染与「凑时」标记都无法在真实库上验证。
只读验证，不写生产库。端口按 vite/后端惯例用 8000。
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

DB_COPY = Path(__file__).with_name("t02028_smoke") / "news.db"
assert DB_COPY.exists(), f"副本库不存在：{DB_COPY}"

from app import paths  # noqa: E402

paths.resolve_db_path = lambda *a, **k: DB_COPY

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")
