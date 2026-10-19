"""T02508 真机联测：把 backend 的数据根切到副本目录后起真实 uvicorn（一次性脚本）。

只作为 `_live_probe2.py` 的子进程入口使用，跑完即删。
"""
import pathlib
import sys

BACKEND_ROOT = pathlib.Path(r"D:\code\otherProjects\20_News\backend")
LIVE_ROOT = BACKEND_ROOT / ".tmp" / "t02508-live"
sys.path.insert(0, str(BACKEND_ROOT))

from app import paths  # noqa: E402

# 关键：所有可写数据路径（data/、logs/）都经由 get_app_root() 解析，
# 替换它即可让整个进程读写副本目录，绝不触碰生产 data/news.db
paths.get_app_root = lambda: LIVE_ROOT  # type: ignore[method-assign]

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
