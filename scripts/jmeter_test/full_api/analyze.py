"""JTL/监控数据分析：逐端点延迟、TPS、错误分类、拐点、4 小时退化趋势。

输出 results/report_data.json 与 results/tables.md，供最终报告引用。
错误率一律从 responseCode 重算，不信任 success 字段。
"""
from __future__ import annotations

import csv
import json
import math
from array import array
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
CASES = json.loads((HERE / "runtime" / "cases.json").read_text(encoding="utf-8"))
EXPECTED = {c["label"]: set(c["expected"]) for c in CASES}
COVERAGE = {c["label"]: c["coverage"] for c in CASES}
CONFIG = json.loads((HERE / "perf_config.json").read_text(encoding="utf-8"))

SOAK_RUNS = ("soak_c", "soak_admin")


def code_class(code: str) -> str:
    if not code or not code.isdigit():
        return "000"
    n = int(code)
    if 200 <= n < 300:
        return "2xx"
    if 300 <= n < 400:
        return "3xx"
    if 400 <= n < 500:
        return "4xx"
    if 500 <= n < 600:
        return "5xx"
    return "000"


def pctl(sorted_vals, p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = max(0, min(len(sorted_vals) - 1, math.ceil(p / 100 * len(sorted_vals)) - 1))
    return float(sorted_vals[idx])


class Lane:
    __slots__ = ("elapsed", "codes", "bytes", "sent", "ts_min", "ts_max", "mismatch")

    def __init__(self) -> None:
        self.elapsed = array("i")
        self.codes: Counter[str] = Counter()
        self.bytes = 0
        self.sent = 0
        self.ts_min = None
        self.ts_max = None
        self.mismatch = 0

    def add(self, ts: int, elapsed: int, code: str, nbytes: int, sent: int, label: str) -> None:
        self.elapsed.append(elapsed)
        self.codes[code] += 1
        self.bytes += nbytes
        self.sent += sent
        self.ts_min = ts if self.ts_min is None else min(self.ts_min, ts)
        self.ts_max = ts if self.ts_max is None else max(self.ts_max, ts)
        exp = EXPECTED.get(label)
        if exp and code.isdigit() and int(code) not in exp:
            self.mismatch += 1

    def summary(self) -> dict:
        n = len(self.elapsed)
        vals = sorted(self.elapsed)
        span = ((self.ts_max - self.ts_min) / 1000) if self.ts_min is not None else 0
        span = max(span, 0.001)
        cls = Counter({k: sum(v for c, v in self.codes.items() if code_class(c) == k)
                       for k in ("2xx", "3xx", "4xx", "5xx", "000")})
        defect = cls["5xx"] + cls["000"]
        return {
            "samples": n,
            "rps": round(n / span, 1),
            "span_sec": round(span, 1),
            "avg_ms": round(sum(vals) / n, 1) if n else 0,
            "p50_ms": pctl(vals, 50),
            "p90_ms": pctl(vals, 90),
            "p95_ms": pctl(vals, 95),
            "p99_ms": pctl(vals, 99),
            "max_ms": vals[-1] if vals else 0,
            "err_rate": round(self.mismatch / n, 4) if n else 0,
            "assert_errors": self.mismatch,
            "defect_rate": round(defect / n, 4) if n else 0,
            "defects": defect,
            "codes": dict(sorted(self.codes.items())),
            "code_classes": dict(cls),
            "rx_mbps": round(self.bytes * 8 / span / 1e6, 3),
            "tx_mbps": round(self.sent * 8 / span / 1e6, 3),
        }


def load(path: Path, windows: int = 0) -> tuple[dict, dict]:
    """返回 (per-label Lane, 按时间窗聚合的 Lane)。windows=0 时第二项为空。"""
    lanes: dict[str, Lane] = defaultdict(Lane)
    overall = Lane()
    t0 = None
    win: dict[tuple[int, str], Lane] = defaultdict(Lane)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            try:
                ts = int(row["timeStamp"])
                elapsed = int(row["elapsed"] or 0)
            except (KeyError, ValueError):
                continue
            label = (row.get("label") or "").strip()
            if not label:
                continue
            code = (row.get("responseCode") or "").strip()
            nbytes = int(row.get("bytes") or 0)
            sent = int(row.get("sentBytes") or 0)
            lanes[label].add(ts, elapsed, code, nbytes, sent, label)
            overall.add(ts, elapsed, code, nbytes, sent, label)
            if windows:
                if t0 is None:
                    t0 = ts
                w = int((ts - t0) / 1000 // windows)
                win[(w, label)].add(ts, elapsed, code, nbytes, sent, label)
    if not windows:
        return dict(lanes), {}
    # 每窗整体：合并该窗所有端点
    per_window: dict[int, Lane] = defaultdict(Lane)
    for (w, _label), lane in win.items():
        dst = per_window[w]
        dst.elapsed.extend(lane.elapsed)
        dst.codes.update(lane.codes)
        dst.bytes += lane.bytes
        dst.sent += lane.sent
        dst.ts_min = lane.ts_min if dst.ts_min is None else min(dst.ts_min, lane.ts_min)
        dst.ts_max = lane.ts_max if dst.ts_max is None else max(dst.ts_max, lane.ts_max)
        dst.mismatch += lane.mismatch
    per_label_window: dict[int, dict[str, Lane]] = defaultdict(dict)
    for (w, label), lane in win.items():
        per_label_window[w][label] = lane
    return {"overall": per_window, "by_label": per_label_window}, {}


def completed(name: str) -> bool:
    log = RES / f"{name}.log"
    return log.exists() and "end of run" in log.read_text(encoding="utf-8", errors="replace")


def load_run(name: str) -> dict | None:
    path = RES / f"{name}.jtl"
    if not path.exists():
        return None
    lanes, _ = load(path)
    overall = Lane()
    for lane in lanes.values():
        overall.elapsed.extend(lane.elapsed)
        overall.codes.update(lane.codes)
        overall.bytes += lane.bytes
        overall.sent += lane.sent
        overall.ts_min = lane.ts_min if overall.ts_min is None else min(overall.ts_min, lane.ts_min)
        overall.ts_max = lane.ts_max if overall.ts_max is None else max(overall.ts_max, lane.ts_max)
        overall.mismatch += lane.mismatch
    return {
        "overall": overall.summary(),
        "endpoints": {k: v.summary() for k, v in sorted(lanes.items())},
    }


def tier_of(name: str) -> int | None:
    tail = name.rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else None


def knee(series: list[dict]) -> dict:
    base_p95 = series[0]["p95_ms"] or 1
    prev_rps = 0.0
    for i, s in enumerate(series):
        if s["defect_rate"] > 0:
            return {"tier": s["tier"], "reason": "出现 5xx/连接失败", "metric": s["defects"]}
        if s["err_rate"] > 0.05:
            return {"tier": s["tier"], "reason": "断言错误率 > 5%", "metric": s["err_rate"]}
        if i > 0:
            growth = (s["rps"] - prev_rps) / prev_rps if prev_rps else 1
            p95_ratio = s["p95_ms"] / series[i - 1]["p95_ms"] if series[i - 1]["p95_ms"] else 1
            if growth < 0.15 and p95_ratio > 1.5:
                return {"tier": s["tier"], "reason": "吞吐饱和（增幅 <15% 且 P95 上升 >50%）",
                        "metric": {"rps_growth": round(growth, 3), "p95_ratio": round(p95_ratio, 2)}}
            if s["p95_ms"] > base_p95 * 4:
                return {"tier": s["tier"], "reason": "P95 超过基线 4 倍",
                        "metric": round(s["p95_ms"] / base_p95, 2)}
        prev_rps = s["rps"]
    return {"tier": None, "reason": "未在测试档位内出现拐点", "metric": None}


def analyze_stress(runs: dict) -> dict:
    families = {
        "C 端读": "stress_c_read",
        "C 端写": "stress_c_write",
        "管理端读": "stress_admin_read",
    }
    out = {}
    for family, prefix in families.items():
        series = []
        for name, data in runs.items():
            if name.startswith(prefix + "_") and tier_of(name):
                row = {"tier": tier_of(name), **data["overall"]}
                series.append(row)
        series.sort(key=lambda x: x["tier"])
        if not series:
            continue
        out[family] = {
            "series": series,
            "knee": knee(series),
            "max_rps": max(series, key=lambda x: x["rps"])["rps"],
            "max_rps_tier": max(series, key=lambda x: x["rps"])["tier"],
        }
    return out


def analyze_soak(name: str) -> dict | None:
    path = RES / f"{name}.jtl"
    if not path.exists():
        return None
    data, _ = load(path, windows=1800)
    per_window, per_label_window = data["overall"], data["by_label"]
    windows = []
    for w in sorted(per_window):
        s = per_window[w].summary()
        windows.append({"window": w, "start_min": w * 30, **s})
    trend = {}
    if len(windows) >= 2:
        def slope(key: str) -> float:
            ys = [x[key] for x in windows]
            xs = list(range(len(ys)))
            mx = sum(xs) / len(xs)
            my = sum(ys) / len(ys)
            den = sum((x - mx) ** 2 for x in xs) or 1
            return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den, 4)
        trend = {
            "p95_ms_per_window": slope("p95_ms"),
            "rps_per_window": slope("rps"),
            "err_rate_per_window": slope("err_rate"),
            "first_p95": windows[0]["p95_ms"],
            "last_p95": windows[-1]["p95_ms"],
            "first_rps": windows[0]["rps"],
            "last_rps": windows[-1]["rps"],
            "first_err": windows[0]["err_rate"],
            "last_err": windows[-1]["err_rate"],
        }
    label_trend = {}
    for w in sorted(per_label_window):
        for label, lane in per_label_window[w].items():
            s = lane.summary()
            label_trend.setdefault(label, []).append(
                {"window": w, "p95_ms": s["p95_ms"], "avg_ms": s["avg_ms"], "rps": s["rps"],
                 "err_rate": s["err_rate"], "defects": s["defects"]}
            )
    degraded = []
    for label, rows in label_trend.items():
        if len(rows) < 2:
            continue
        first, last = rows[0], rows[-1]
        if first["p95_ms"] and last["p95_ms"] > first["p95_ms"] * 1.5:
            degraded.append({"label": label, "first_p95": first["p95_ms"],
                             "last_p95": last["p95_ms"]})
    return {"windows": windows, "trend": trend, "label_windows": label_trend,
            "degraded_endpoints": degraded}


def analyze_monitor(path: Path) -> dict | None:
    if not path.exists():
        return None
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)

    def fnum(key: str) -> list[float]:
        out = []
        for r in rows:
            try:
                out.append(float(r.get(key) or 0))
            except ValueError:
                pass
        return out

    rss = fnum("rss_mb")
    cpu = [x for x in fnum("cpu_pct") if x >= 0]
    handles = fnum("handles")
    db = fnum("db_mb")
    wal = fnum("wal_mb")
    free = fnum("disk_free_gb")
    io_w = [x for x in fnum("io_write_kbps") if x > 0]
    io_r = [x for x in fnum("io_read_kbps") if x > 0]

    def slope(vals: list[float]) -> float:
        if len(vals) < 2:
            return 0.0
        xs = list(range(len(vals)))
        mx, my = sum(xs) / len(xs), sum(vals) / len(vals)
        den = sum((x - mx) ** 2 for x in xs) or 1
        return round(sum((x - mx) * (y - my) for x, y in zip(xs, vals)) / den, 4)

    pids = sorted({r.get("pid", "") for r in rows})
    return {
        "samples": len(rows), "pids": pids,
        "rss_first_mb": rss[0] if rss else 0, "rss_last_mb": rss[-1] if rss else 0,
        "rss_max_mb": max(rss) if rss else 0,
        "rss_slope_mb_per_sample": slope(rss),
        "peak_ws_mb": max(fnum("peak_ws_mb")) if rows else 0,
        "cpu_avg_pct": round(sum(cpu) / len(cpu), 1) if cpu else 0,
        "cpu_max_pct": max(cpu) if cpu else 0,
        "handles_max": int(max(handles)) if handles else 0,
        "handles_slope_per_sample": slope(handles),
        "db_first_mb": db[0] if db else 0, "db_last_mb": db[-1] if db else 0,
        "db_growth_mb": round((db[-1] - db[0]), 1) if len(db) > 1 else 0,
        "wal_max_mb": max(wal) if wal else 0,
        "wal_last_mb": wal[-1] if wal else 0,
        "disk_free_min_gb": min(free) if free else 0,
        "io_write_avg_kbps": round(sum(io_w) / len(io_w), 1) if io_w else 0,
        "io_write_max_kbps": max(io_w) if io_w else 0,
        "io_read_avg_kbps": round(sum(io_r) / len(io_r), 1) if io_r else 0,
    }


def coverage_matrix(probes: dict) -> dict:
    buckets = defaultdict(list)
    for c in CASES:
        label = c["label"]
        if label in probes:
            status = probes[label].get("status", "probed")
            evidence = probes[label].get("code", "")
        elif c["coverage"] == "destructive":
            status, evidence = "excluded-by-design", "污染夹具，单独 404/校验探针"
        elif c["external"]:
            status, evidence = "external-skipped", "出站付费/第三方，避免真实调用"
        elif c["sse"]:
            status, evidence = "sse-probe", "长连接单次连接后断开"
        elif c["execute_baseline"]:
            status, evidence = "executed", "baseline"
        else:
            status, evidence = "not-run", ""
        buckets[status].append({"label": label, "group": c["group"], "coverage": c["coverage"],
                                "evidence": evidence})
    return {k: {"count": len(v), "endpoints": v} for k, v in buckets.items()}


def table_runs(runs: dict) -> str:
    lines = ["| 运行 | 样本 | RPS | Avg | P90 | P95 | P99 | Max | 错误率 | 真实缺陷 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, data in runs.items():
        o = data["overall"]
        lines.append(f"| {name} | {o['samples']} | {o['rps']} | {o['avg_ms']} | {o['p90_ms']} | "
                     f"{o['p95_ms']} | {o['p99_ms']} | {o['max_ms']} | {o['err_rate']:.2%} | {o['defects']} |")
    return "\n".join(lines)


def table_endpoints(runs: dict, names: list[str]) -> str:
    outp = []
    for name in names:
        data = runs.get(name)
        if not data:
            continue
        outp.append(f"\n### {name}\n")
        outp.append("| 端点 | 样本 | RPS | Avg | P90 | P95 | P99 | 错误率 | 5xx/000 |")
        outp.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for label, e in data["endpoints"].items():
            outp.append(f"| {label} | {e['samples']} | {e['rps']} | {e['avg_ms']} | {e['p90_ms']} | "
                        f"{e['p95_ms']} | {e['p99_ms']} | {e['err_rate']:.1%} | {e['defects']} |")
    return "\n".join(outp)


def main() -> None:
    runs = {}
    for p in sorted(RES.glob("*.jtl")):
        name = p.stem
        if name.startswith("base_") or not completed(name):
            continue
        data = load_run(name)
        if data:
            runs[name] = data
    stress = analyze_stress(runs)
    soak = {name: analyze_soak(name) for name in SOAK_RUNS if name in runs}
    resources = {}
    for tag in ("baseline", "stress", "soak"):
        r = analyze_monitor(RES / f"monitor_{tag}.csv")
        if r:
            resources[tag] = r
    probes = {}
    if (RES / "probes.json").exists():
        probes = json.loads((RES / "probes.json").read_text(encoding="utf-8"))

    out = {
        "generated_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "runs": runs,
        "stress": stress,
        "soak": soak,
        "resources": resources,
        "coverage": coverage_matrix(probes),
        "probes": probes,
    }
    (RES / "report_data.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# 性能数据表（自动生成）\n", "## 各轮次总览\n", table_runs(runs)]
    if stress:
        md.append("\n## 阶梯压测与拐点\n")
        for family, s in stress.items():
            md.append(f"\n### {family}（拐点：{s['knee']['reason']} @ {s['knee']['tier']} 线程；"
                      f"峰值 {s['max_rps']} RPS @ {s['max_rps_tier']} 线程）\n")
            md.append("| 线程 | RPS | Avg | P95 | P99 | 错误率 | 缺陷 |")
            md.append("|---:|---:|---:|---:|---:|---:|---:|")
            for row in s["series"]:
                md.append(f"| {row['tier']} | {row['rps']} | {row['avg_ms']} | {row['p95_ms']} | "
                          f"{row['p99_ms']} | {row['err_rate']:.2%} | {row['defects']} |")
    if soak:
        for soak_name, soak_data in soak.items():
            md.append(f"\n## 稳定性 {soak_name}（30 分钟窗口）\n")
            md.append("| 窗口 | 起始分钟 | 样本 | RPS | Avg | P95 | P99 | 错误率 | 缺陷 |")
            md.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
            for w in soak_data["windows"]:
                md.append(f"| {w['window']} | {w['start_min']} | {w['samples']} | {w['rps']} | {w['avg_ms']} | "
                          f"{w['p95_ms']} | {w['p99_ms']} | {w['err_rate']:.2%} | {w['defects']} |")
            t = soak_data["trend"]
            if t:
                md.append(f"\n趋势：P95 {t['first_p95']}→{t['last_p95']} ms，RPS {t['first_rps']}→{t['last_rps']}，"
                          f"错误率 {t['first_err']:.2%}→{t['last_err']:.2%}；P95 斜率 {t['p95_ms_per_window']}/窗口。")
            if soak_data["degraded_endpoints"]:
                md.append("\n端点级退化（末窗 P95 > 首窗 1.5 倍）：")
                for d in soak_data["degraded_endpoints"]:
                    md.append(f"- {d['label']}: {d['first_p95']} → {d['last_p95']} ms")
            else:
                md.append("\n端点级退化：无（所有端点末窗 P95 未超首窗 1.5 倍）。")
    if resources:
        md.append("\n## 资源水位\n")
        md.append("| 场景 | 采样 | PID | RSS 首/末/峰 (MB) | CPU 均/峰 | 句柄峰 | DB 增长 (MB) | WAL 峰 | 写 IO 均 (KB/s) | 磁盘余量 (GB) |")
        md.append("|---|---:|---|---|---:|---:|---:|---:|---:|---:|")
        for tag, r in resources.items():
            md.append(f"| {tag} | {r['samples']} | {','.join(r['pids'])} | {r['rss_first_mb']}/{r['rss_last_mb']}/{r['rss_max_mb']} | "
                      f"{r['cpu_avg_pct']}%/{r['cpu_max_pct']}% | {r['handles_max']} | {r['db_growth_mb']} | "
                      f"{r['wal_max_mb']} | {r['io_write_avg_kbps']} | {r['disk_free_min_gb']} |")
    md.append("\n## 端点明细（基线 / 阶梯）\n")
    md.append(table_endpoints(runs, ["baseline_c", "baseline_admin", "stress_c_read_200",
                                     "stress_c_write_50", "stress_admin_read_50"]))
    md.append("\n## 覆盖统计\n")
    for k, v in out["coverage"].items():
        md.append(f"- {k}: {v['count']}")
    (RES / "tables.md").write_text("\n".join(md), encoding="utf-8")
    print(f"[ok] report_data.json + tables.md；运行 {len(runs)} 轮，覆盖桶 {len(out['coverage'])} 类")


if __name__ == "__main__":
    main()
