"""轻量级异步压测复测脚本（无需 Java/JMeter）。

用 aiohttp 在本地后端重放写/读混合负载，验证 P0-1/P0-2/P1 进程内优化效果。

场景对齐原 JMeter 计划：
- 写场景：7 个写接口按权重随机重放（原 S2_write 全量写错误率曾达 27-73%）
- 读场景：today/history/search/recent/favorites/script

用法：
    # 默认打 127.0.0.1:8000，需要先有 test_token.txt（setup.py 生成）
    python loadtest_async.py
    # 打别的地址
    LB_BASE=http://127.0.0.1:9000 python loadtest_async.py

输出：总量、错误率（按状态码）、延迟分位、吞吐、非 200 状态码样本。
注意：需先解除限流（RATE_LIMIT_PER_MINUTE 调大）否则单源会被 429。
"""
import asyncio
import json
import os
import random
import time
from pathlib import Path

import aiohttp

BASE = os.environ.get("LB_BASE", "http://127.0.0.1:8000")
TOKEN = Path(__file__).resolve().parent / "test_token.txt"
HDR = {"Authorization": f"Bearer {TOKEN.read_text(encoding='utf-8').strip()}",
       "Content-Type": "application/json"}

EP = 57          # 已发布节目
CH = 5           # 活跃频道（1-30）

WRITE_TASKS = [
    # (weight, method, path, json-body-factory)
    (40, "POST", f"/api/v1/playlogs/progress",
     lambda: {"episode_id": EP, "position": random.randint(0, 600),
              "duration": 600, "completed": random.random() < 0.1,
              "listened_seconds": random.randint(1, 30)}),
    (15, "POST", "/api/v1/comments",
     lambda: {"episode_id": EP, "content": "loadtest comment %d" % random.randint(0, 999999)}),
    (10, "POST", "/api/v1/favorites",
     lambda: {"episode_id": EP}),
    (10, "POST", "/api/v1/feedbacks",
     lambda: {"category": "建议", "content": "loadtest feedback %d" % random.randint(0, 999999)}),
    (10, "POST", f"/api/v1/subscriptions/channels/{CH}",
     lambda: None),
    (10, "DELETE", f"/api/v1/subscriptions/channels/{CH}",
     lambda: None),
    (5, "POST", "/api/v1/subscriptions/message",
     lambda: {"template_id": "loadtest_template_id_%d" % random.randint(0, 99999)}),
]
_WRITE_POOL = []
for w, m, p, f in WRITE_TASKS:
    _WRITE_POOL += [(m, p, f)] * w

READ_TASKS = [
    ("GET", "/api/v1/episodes/today", None),
    ("GET", "/api/v1/episodes/history?page=1&size=20&channel_id=1", None),
    ("GET", "/api/v1/episodes/search?keyword=%E7%A7%91%E6%8A%80&page=1&size=10", None),
    ("GET", "/api/v1/playlogs/recent", None),
    ("GET", "/api/v1/favorites?page=1&size=20", None),
    ("GET", f"/api/v1/episodes/{EP}/script", None),
]


def pct(latencies, p):
    if not latencies:
        return 0.0
    s = sorted(latencies)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k] * 1000.0  # ms


async def worker(session, tasks, is_write, duration, stats):
    end = time.monotonic() + duration
    while time.monotonic() < end:
        if is_write:
            m, p, f = random.choice(_WRITE_POOL)
            body = f() if f else None
            req = session.request(m, BASE + p, json=body, headers=HDR)
        else:
            m, p, b = random.choice(READ_TASKS)
            req = session.request(m, BASE + p, headers=HDR)
        t0 = time.monotonic()
        try:
            async with req as resp:
                code = resp.status
                text = await resp.text()
        except Exception as e:
            code = 0  # 连接/超时异常
            text = f"EXC {type(e).__name__}: {e}"
        dt = time.monotonic() - t0
        stats["codes"][code] = stats["codes"].get(code, 0) + 1
        stats["lat"].append(dt)
        if code >= 400 or code == 0:
            stats["err"] += 1
            # 记录每种非 200 的一个样本
            if code not in stats["samples"]:
                stats["samples"][code] = (m, p, text[:300])
        stats["total"] += 1


async def run_scenario(name, tasks, is_write, concurrency, duration):
    stats = {"total": 0, "err": 0, "codes": {}, "lat": [], "samples": {}}
    conn = aiohttp.TCPConnector(limit=0, ssl=False)
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        t0 = time.monotonic()
        await asyncio.gather(*[
            worker(session, tasks, is_write, duration, stats)
            for _ in range(concurrency)
        ])
        elapsed = time.monotonic() - t0
    lat = stats["lat"]
    print(f"\n=== {name} (concurrency={concurrency}, duration={duration}s) ===")
    print(f"  total={stats['total']}  errors={stats['err']}  "
          f"error_rate={100.0*stats['err']/max(1,stats['total']):.2f}%")
    print(f"  throughput={stats['total']/elapsed:.1f} req/s  elapsed={elapsed:.1f}s")
    print(f"  latency ms  avg={1000.0*sum(lat)/max(1,len(lat)):.1f}  "
          f"p50={pct(lat,50):.1f}  p95={pct(lat,95):.1f}  p99={pct(lat,99):.1f}  max={1000.0*max(lat):.1f}")
    non200 = {c: n for c, n in stats["codes"].items() if c != 200}
    print(f"  non-200 codes: {dict(sorted(non200.items()))}")
    for c, (m, p, t) in sorted(stats.get("samples", {}).items()):
        print(f"  sample[{c}] {m} {p}: {t}")
    return stats


async def main():
    print("warmup health...")
    async with aiohttp.ClientSession() as s:
        async with s.get(BASE + "/api/health") as r:
            print("  health:", r.status)
    await run_scenario("WRITE_S2_200", WRITE_TASKS, True, 200, 30)
    await run_scenario("READ_S1_200", READ_TASKS, False, 200, 30)
    await run_scenario("WRITE_mod_50", WRITE_TASKS, True, 50, 20)
    await run_scenario("READ_mod_50", READ_TASKS, False, 50, 20)


if __name__ == "__main__":
    asyncio.run(main())
