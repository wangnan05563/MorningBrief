# -*- coding: utf-8 -*-
"""T01580 写路径压测：单表写与混合写的吞吐/延迟/锁错误分布。

用法：
    python perf_write_ab.py <输出json> [场景 comments|favorites|mixed] [并发] [时长秒]
token 取 perf_tokens.json（198 个压测用户），episode/channel 取 seed 生成的数据。
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
BASE = os.environ.get("LB_BASE", "http://127.0.0.1:8003")
INFO = json.loads((HERE / "perf_tokens.json").read_text(encoding="utf-8"))
TOKENS, EPS, CHS = INFO["tokens"], INFO["episodes"], INFO["channels"]


def pick(kind, rng):
    tok = rng.choice(TOKENS)
    ep = rng.choice(EPS)
    if kind == "comments":
        return ("POST", "/api/v1/comments",
                {"episode_id": ep, "content": "T01580 写路径评估负载内容 %d" % rng.randrange(10**8)}, tok)
    if kind == "favorites":
        return ("POST", "/api/v1/favorites", {"episode_id": ep}, tok)
    if kind == "feedbacks":
        return ("POST", "/api/v1/feedbacks",
                {"category": "bug", "content": "T01580 反馈写入路径验证内容 %d" % rng.randrange(10**8),
                 "contact": "perf@test.com"}, tok)
    if kind == "subscriptions":
        return ("POST", f"/api/v1/subscriptions/channels/{rng.choice(CHS)}", None, tok)
    raise ValueError(kind)


MIX = [("comments", 40), ("favorites", 20), ("feedbacks", 20), ("subscriptions", 20)]


def pool_for(scenario):
    if scenario in ("comments", "favorites", "feedbacks", "subscriptions"):
        return [(scenario, 1)]
    return MIX


async def worker(s, pool, end, lat, codes, stats):
    rng = random.Random()
    total = len(pool)
    while time.monotonic() < end:
        kind = pool[rng.randrange(total)][0]
        m, path, body, tok = pick(kind, rng)
        headers = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
        t0 = time.monotonic()
        try:
            async with s.request(m, BASE + path, json=body, headers=headers) as r:
                text = await r.text()
                code = r.status
        except Exception:
            code, text = 0, "EXC"
        dt = time.monotonic() - t0
        lat.append(dt)
        codes[code] = codes.get(code, 0) + 1
        if code != 200:
            stats["err"] += 1
            if "locked" in text or "disk I/O" in text:
                stats["locked"] += 1
            stats.setdefault("sample", text[:200])


def pct(v, p):
    if not v:
        return 0.0
    s = sorted(v)
    return s[max(0, min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1)))))] * 1000.0


async def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "w.json"
    scenario = sys.argv[2] if len(sys.argv) > 2 else "comments"
    conc = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    dur = int(sys.argv[4]) if len(sys.argv) > 4 else 45

    pool = pool_for(scenario)
    lat, codes, stats = [], {}, {"err": 0, "locked": 0}
    conn = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=conn, timeout=aiohttp.ClientTimeout(total=120)) as s:
        async with s.get(BASE + "/api/health/live") as r:
            print("health:", r.status)
        end = time.monotonic() + dur
        t0 = time.monotonic()
        await asyncio.gather(*[worker(s, pool, end, lat, codes, stats) for _ in range(conc)])
        elapsed = time.monotonic() - t0
    res = {
        "scenario": scenario, "concurrency": conc, "duration_s": dur,
        "total": len(lat), "tps": round(len(lat) / elapsed, 1),
        "error_rate": round(100.0 * stats["err"] / max(1, len(lat)), 2),
        "lock_errors": stats["locked"],
        "p50_ms": round(pct(lat, 50), 1), "p95_ms": round(pct(lat, 95), 1),
        "p99_ms": round(pct(lat, 99), 1), "max_ms": round(max(lat) * 1000, 1) if lat else 0,
        "codes": codes, "sample": stats.get("sample"),
    }
    print(json.dumps(res, ensure_ascii=False, indent=1))
    (HERE / out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


asyncio.run(main())
