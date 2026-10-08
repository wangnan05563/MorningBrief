# -*- coding: utf-8 -*-
"""T01579 端点级延迟探针：串行测量三条读路径的单请求耗时（排除并发排队噪声）。

对每个端点用递增的大 page 参数保证每次都未命中缓存（冷查），
测的是「索引/查询本身」的成本；另各测一次热点参数（page=1）看缓存命中效果。

用法：python probe_read_endpoints.py <输出json> [每端点次数]
"""
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8003"
TOKEN = (HERE / "test_token.txt").read_text(encoding="utf-8").strip()
HDR = {"Authorization": f"Bearer {TOKEN}"}

# (名称, 路径模板, 缓存命中的热点路径)
ENDPOINTS = {
    "favorites": ("/api/v1/favorites?page={i}&size=20", "/api/v1/favorites?page=1&size=20"),
    "favorites_type_news": (
        "/api/v1/favorites?page={i}&size=20&channel_type=news",
        "/api/v1/favorites?page=1&size=20&channel_type=news",
    ),
    "playlogs_recent": ("/api/v1/playlogs/recent?page={i}&size=20", "/api/v1/playlogs/recent?page=1&size=20"),
    "history_ch": ("/api/v1/episodes/history?page={i}&size=20&channel_id=5", None),
}


def measure(c, url):
    t0 = time.perf_counter()
    r = c.get(url, headers=HDR)
    dt = (time.perf_counter() - t0) * 1000
    return (dt if r.status_code == 200 else None), r.status_code


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "probe.json"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    results = {}
    with httpx.Client(timeout=120) as c:
        for name, (cold_tpl, hot) in ENDPOINTS.items():
            times = []
            for i in range(n):
                dt, code = measure(c, BASE + cold_tpl.format(i=1000 + i))
                if dt is None:
                    print(f"  [WARN] {name} 非200: {code}")
                    continue
                times.append(dt)
            entry = None
            if times:
                entry = {
                    "cold_n": len(times),
                    "cold_avg_ms": round(statistics.mean(times), 1),
                    "cold_p95_ms": round(sorted(times)[max(0, int(0.95 * len(times)) - 1)], 1),
                    "cold_max_ms": round(max(times), 1),
                }
            if hot:
                measure(c, BASE + hot)          # 填充缓存
                dt, _ = measure(c, BASE + hot)  # 命中
                entry = entry or {}
                entry["hot_cached_ms"] = round(dt, 1) if dt is not None else None
            results[name] = entry
            print(f"{name:22s} {json.dumps(entry, ensure_ascii=False)}")
    Path(out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


main()
