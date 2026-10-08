"""T01659 第三优先级：访问日志落盘成本实测。

复刻 app/core/logging_setup.py 的 sink 配置（同样的 format / filter / rotation），
只变一个变量，测「一条典型 access 日志」的每记录开销：
  A 现状：stderr(log_level) + 文件(level=DEBUG)
  B 文件 sink 降到 INFO
  C 文件 sink 加 enqueue=True（写盘移出调用线程）
  D 只有 stderr sink（量化文件 sink 的边际成本）
  E 无任何 sink（loguru 地板）
"""
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

from loguru import logger

from app.core.logging_setup import _admin_log_filter, _patcher

CONSOLE_FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>[req={extra[request_id]}]</cyan> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)
FILE_FMT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "[req={extra[request_id]}] | "
    "{name}:{function}:{line} - {message}"
)

ACCESS = '127.0.0.1:50642 - "GET /api/v1/favorites HTTP/1.1" 200'
DEBUG_CHATTER = "operation functools.partial(<built-in method commit of sqlite3.Connection>) completed"
N = 300


def bench(name: str, build) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="t01659_log_"))
    logger.remove()
    logger.configure(patcher=_patcher)  # 与 setup_logging 一致：注入 extra[request_id]
    build(tmp)
    # 预热：首次写会创建文件/handler
    logger.info(ACCESS)
    per_call = []
    for _ in range(6):
        t0 = time.perf_counter()
        for _ in range(N):
            logger.info(ACCESS)
            logger.debug(DEBUG_CHATTER)
        per_call.append((time.perf_counter() - t0) / (2 * N) * 1000)
    size = sum(p.stat().st_size for p in tmp.glob("*.log")) if any(tmp.glob("*.log")) else 0
    logger.remove()
    shutil.rmtree(tmp, ignore_errors=True)
    return {
        "case": name,
        "ms_per_record_min": round(min(per_call), 4),
        "ms_per_record_median": round(statistics.median(per_call), 4),
        "records": 2 * N * 6,
        "bytes_written": size,
    }


def a(tmp):
    logger.add(sys.stderr, level="DEBUG", format=CONSOLE_FMT)
    logger.add(tmp / "l.log", filter=_admin_log_filter, level="DEBUG", format=FILE_FMT)


def b(tmp):
    logger.add(sys.stderr, level="DEBUG", format=CONSOLE_FMT)
    logger.add(tmp / "l.log", filter=_admin_log_filter, level="INFO", format=FILE_FMT)


def c(tmp):
    logger.add(sys.stderr, level="DEBUG", format=CONSOLE_FMT)
    logger.add(tmp / "l.log", filter=_admin_log_filter, level="DEBUG", format=FILE_FMT, enqueue=True)


def d(tmp):
    logger.add(sys.stderr, level="DEBUG", format=CONSOLE_FMT)


def e(tmp):
    pass


def f(tmp):
    # 只有文件 sink：量化 stderr 的边际成本
    logger.add(tmp / "l.log", filter=_admin_log_filter, level="DEBUG", format=FILE_FMT)


results = []
for _ in range(2):
    for name, fn in [("A_current_stderr+fileDEBUG", a), ("B_fileINFO", b), ("C_fileEnqueue", c),
                     ("D_stderrOnly", d), ("E_noSink", e), ("F_fileOnly", f)]:
        results.append(bench(name, fn))

import json

print(json.dumps(results, ensure_ascii=False, indent=1))
out = Path(__file__).with_name("t01659_log_sink_cost.json")
out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
