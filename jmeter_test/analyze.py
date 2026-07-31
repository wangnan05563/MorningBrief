"""JMeter JTL 结果分析脚本。

读取 CSV 格式的 JTL 文件，计算关键性能指标：
- TPS（每秒事务数）
- 平均/P90/P95/P99 响应时间
- 错误率
- 各接口分项指标
- 本地 vs 生产对比

JTL CSV 字段（与 jmeter.properties 配置一致）：
timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,
success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,
IdleTime,Connect
"""
import csv
import statistics
import sys
from pathlib import Path


def percentile(data: list[float], p: float) -> float:
    """计算百分位数（线性插值法，与 JMeter 一致）。"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def analyze_jtl(jtl_path: Path) -> dict:
    """分析单个 JTL 文件，返回指标字典。"""
    rows = []
    with open(jtl_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        return {"error": "JTL 文件为空"}

    # 解析关键字段
    elapsed_list = [int(r["elapsed"]) for r in rows]
    success_list = [r["success"] == "true" for r in rows]
    labels = sorted(set(r["label"] for r in rows))

    # 时间范围（毫秒）
    timestamps = [int(r["timeStamp"]) for r in rows]
    start_ts = min(timestamps)
    end_ts = max(timestamps)
    duration_sec = (end_ts - start_ts) / 1000.0

    # 全局指标
    total = len(rows)
    success_count = sum(success_list)
    error_count = total - success_count
    tps = total / duration_sec if duration_sec > 0 else 0
    avg = statistics.mean(elapsed_list)
    p50 = percentile(elapsed_list, 50)
    p90 = percentile(elapsed_list, 90)
    p95 = percentile(elapsed_list, 95)
    p99 = percentile(elapsed_list, 99)
    min_v = min(elapsed_list)
    max_v = max(elapsed_list)

    # 分接口指标
    per_label = {}
    for label in labels:
        label_rows = [r for r in rows if r["label"] == label]
        label_elapsed = [int(r["elapsed"]) for r in label_rows]
        label_success = sum(1 for r in label_rows if r["success"] == "true")
        per_label[label] = {
            "count": len(label_rows),
            "avg": round(statistics.mean(label_elapsed), 2),
            "p50": round(percentile(label_elapsed, 50), 2),
            "p90": round(percentile(label_elapsed, 90), 2),
            "p95": round(percentile(label_elapsed, 95), 2),
            "p99": round(percentile(label_elapsed, 99), 2),
            "min": min(label_elapsed),
            "max": max(label_elapsed),
            "error_count": len(label_rows) - label_success,
            "error_rate": round(
                (len(label_rows) - label_success) / len(label_rows) * 100, 2
            ),
        }

    return {
        "total_requests": total,
        "success": success_count,
        "errors": error_count,
        "error_rate": round(error_count / total * 100, 2),
        "duration_sec": round(duration_sec, 2),
        "tps": round(tps, 2),
        "avg_ms": round(avg, 2),
        "p50_ms": round(p50, 2),
        "p90_ms": round(p90, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "min_ms": min_v,
        "max_ms": max_v,
        "per_label": per_label,
        "start_ts": start_ts,
        "end_ts": end_ts,
    }


def rating(value: float, thresholds: list[tuple[float, str]]) -> str:
    """根据阈值评级。"""
    for threshold, label in thresholds:
        if value <= threshold:
            return label
    return thresholds[-1][1]


def rate_response_time(ms: float) -> str:
    """响应时间评级。"""
    return rating(
        ms,
        [(200, "优秀"), (500, "良好"), (1000, "一般"), (2000, "较差")],
    )


def rate_error_rate(pct: float) -> str:
    """错误率评级。"""
    return rating(pct, [(0.1, "优秀"), (1, "良好"), (5, "一般"), (100, "较差")])


def rate_tps(tps: float) -> str:
    """TPS 评级（基准测试受吞吐量限制，主要看响应时间）。"""
    return rating(tps, [(50, "受限"), (200, "正常"), (1000, "良好"), (10000, "优秀")])


def format_report(env_name: str, metrics: dict) -> str:
    """格式化单个环境的报告。"""
    if "error" in metrics:
        return f"## {env_name} 环境\n\n错误: {metrics['error']}\n"

    lines = [f"## {env_name} 环境测试结果\n"]
    lines.append(f"- 测试时长: {metrics['duration_sec']} 秒")
    lines.append(f"- 总请求数: {metrics['total_requests']}")
    lines.append(f"- 成功: {metrics['success']}  失败: {metrics['errors']}")
    lines.append(
        f"- 错误率: {metrics['error_rate']}% ({rate_error_rate(metrics['error_rate'])})"
    )
    lines.append(f"- TPS: {metrics['tps']} ({rate_tps(metrics['tps'])})")
    lines.append("")
    lines.append("### 全局响应时间（毫秒）\n")
    lines.append("| 指标 | 值 | 评级 |")
    lines.append("|------|-----|------|")
    lines.append(
        f"| 平均 | {metrics['avg_ms']} | {rate_response_time(metrics['avg_ms'])} |"
    )
    lines.append(f"| P50 | {metrics['p50_ms']} | {rate_response_time(metrics['p50_ms'])} |")
    lines.append(f"| P90 | {metrics['p90_ms']} | {rate_response_time(metrics['p90_ms'])} |")
    lines.append(f"| P95 | {metrics['p95_ms']} | {rate_response_time(metrics['p95_ms'])} |")
    lines.append(f"| P99 | {metrics['p99_ms']} | {rate_response_time(metrics['p99_ms'])} |")
    lines.append(f"| Min | {metrics['min_ms']} | - |")
    lines.append(f"| Max | {metrics['max_ms']} | - |")
    lines.append("")
    lines.append("### 各接口分项指标\n")
    lines.append(
        "| 接口 | 请求数 | 平均(ms) | P95(ms) | P99(ms) | Max(ms) | 错误率 |"
    )
    lines.append("|------|--------|----------|---------|---------|---------|--------|")
    for label, m in sorted(metrics["per_label"].items()):
        lines.append(
            f"| {label} | {m['count']} | {m['avg']} | {m['p95']} | "
            f"{m['p99']} | {m['max']} | {m['error_rate']}% |"
        )
    return "\n".join(lines)


def format_comparison(local: dict, prod: dict) -> str:
    """格式化本地 vs 生产对比。"""
    lines = ["## 本地 vs 生产 对比\n"]
    lines.append("| 指标 | 本地 | 生产 | 差异 | 倍数 |")
    lines.append("|------|------|------|------|------|")

    pairs = [
        ("总请求数", "total_requests"),
        ("TPS", "tps"),
        ("平均响应时间(ms)", "avg_ms"),
        ("P50(ms)", "p50_ms"),
        ("P90(ms)", "p90_ms"),
        ("P95(ms)", "p95_ms"),
        ("P99(ms)", "p99_ms"),
        ("错误率(%)", "error_rate"),
    ]

    for name, key in pairs:
        lv = local.get(key, 0)
        pv = prod.get(key, 0)
        diff = round(pv - lv, 2) if isinstance(lv, (int, float)) else "N/A"
        ratio = (
            round(pv / lv, 2) if lv and isinstance(lv, (int, float)) else "N/A"
        )
        lines.append(f"| {name} | {lv} | {pv} | {diff} | {ratio}x |")

    # 公网延迟估算（连接时间 + 首字节延迟）
    lines.append("")
    lines.append(
        f"**公网额外延迟** ≈ 生产平均 - 本地平均 = "
        f"{round(prod['avg_ms'] - local['avg_ms'], 2)} ms"
    )
    return "\n".join(lines)


def main() -> int:
    base = Path(__file__).resolve().parent
    local_jtl = base / "results_local" / "result.jtl"
    prod_jtl = base / "results_prod" / "result.jtl"

    if not local_jtl.exists():
        print(f"[ERROR] 本地 JTL 不存在: {local_jtl}", file=sys.stderr)
        return 1
    if not prod_jtl.exists():
        print(f"[ERROR] 生产 JTL 不存在: {prod_jtl}", file=sys.stderr)
        return 1

    local_metrics = analyze_jtl(local_jtl)
    prod_metrics = analyze_jtl(prod_jtl)

    report_lines = []
    report_lines.append(format_report("本地 (http://127.0.0.1:8000)", local_metrics))
    report_lines.append("")
    report_lines.append(format_report("生产 (https://desktop-g10o4nl.tailbca47.ts.net/news)", prod_metrics))
    report_lines.append("")
    report_lines.append(format_comparison(local_metrics, prod_metrics))

    # 输出到 stdout 和文件
    report = "\n".join(report_lines)
    print(report)

    out_file = base / "analysis_report.md"
    out_file.write_text(report, encoding="utf-8")
    print(f"\n[OK] 报告已保存到: {out_file}")

    # 同时保存机器可读的 JSON
    import json
    json_file = base / "analysis_metrics.json"
    json_file.write_text(
        json.dumps(
            {"local": local_metrics, "prod": prod_metrics},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[OK] 指标已保存到: {json_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
