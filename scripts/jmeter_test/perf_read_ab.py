# -*- coding: utf-8 -*-
"""T01579 读路径对照压测：仅打收藏/最近播放/历史三条接口，200 并发。

用法：
    python perf_read_ab.py <输出json名> [并发] [时长秒]
token 取 scripts/jmeter_test/test_token.txt（setup.py 生成）。
"""
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

import aiohttp

HERE = Path(__file__).resolve().parent
BASE = os.environ.get("LB_BASE", "http://127.0.0.1:8002")
TOKEN = (HERE / "test_token.txt").read_text(encoding="utf-8").strip()
HDR = {"Authorization": f"Bearer {TOKEN}"}
# 与 morningbrief_perf_plan.jmx 读场景同款随机参数（保证缓存不会 100% 命中）
PATHS = [
    "/api/v1/favorites?page={p}&size=20",
    "/api/v1/favorites?page=1&size=20&channel_type=news",
    "/api/v1/playlogs/recent",
    "/api/v1/playlogs/recent?page={p}&size=20&channel_type=news",
    "/api/v1/episodes/history?page={p}&size=20&channel_id={c}",
    "/api/v1/episodes/history?page=1&size=20",
]
EP_MAX = int(os.environ.get("PERF_EP_MAX", "1000"))
CH_MAX = int(os.environ.get("PERF_CH_MAX", "30"))


def pct(v, p):
    if not v:
        return 0.0
    s = sorted(v)
    return s[max(0, min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1)))))] * 1000.0


async def worker(session, lat, codes, end):
    while time.monotonic() < end:
        path = random.choice(PATHS).format(p=random.randint(1, 50), c=random.randint(1, CH_MAX))
        t0 = time.monotonic()
        try:
            async with session.get(BASE + path, headers=HDR) as resp:
                await resp.read()
                code = resp.status
        except Exception:
            code = 0
        lat.append(time.monotonic() - t0)
        codes[code] = codes.get(code, 0) + 1


async def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "ab_result.json"
    conc = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    dur = int(sys.argv[3]) if len(sys.argv) > 3 else 60

    conn = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=conn, timeout=aiohttp.ClientTimeout(total=60)) as s:
        async with s.get(BASE + "/api/health/live") as r:
            print("health:", r.status)
        lat, codes = [], {}
        end = time.monotonic() + dur
        t0 = time.monotonic()
        await asyncio.gather(*[worker(s, lat, codes, end) for _ in range(conc)])
        elapsed = time.monotonic() - t0
    res = {
        "concurrency": conc, "duration_s": dur, "total": len(lat),
        "tps": round(len(lat) / elapsed, 1),
        "error_rate": round(100.0 * sum(n for c, n in codes.items() if c != 200) / max(1, len(lat)), 2),
        "p50_ms": round(pct(lat, 50), 1), "p90_ms": round(pct(lat, 90), 1),
        "p95_ms": round(pct(lat, 95), 1), "p99_ms": round(pct(lat, 99), 1),
        "codes": codes,
    }
    print(json.dumps(res, ensure_ascii=False, indent=1))
    (HERE / out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


asyncio.run(main())
