"""从 results/report_data.json 生成逐接口附件（CSV + Markdown）。

用法：python make_report.py [快照路径]
默认快照为第一轮 soak 的归档数据 results/archive_round1_0929/report_data_snapshot.json。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
SNAP = Path(sys.argv[1]) if len(sys.argv) > 1 else RES / "archive_round1_0929" / "report_data_snapshot.json"


def pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.2%}"


def num(v: float | None, nd: int = 0) -> str:
    return "—" if v is None else f"{v:.{nd}f}"


def main() -> None:
    data = json.loads((RES / "report_data.json").read_text(encoding="utf-8"))
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    base_c = data["runs"]["baseline_c"]["endpoints"]
    base_a = data["runs"]["baseline_admin"]["endpoints"]
    base = {**base_c, **base_a}
    soak_c_lw = snap["soak"]["soak_c"]["label_windows"]
    soak_a_lw = snap["soak"]["soak_admin"]["label_windows"]
    groups = {}
    for item in data["coverage"]["executed"]["endpoints"]:
        groups[item["label"]] = (item["group"], item["coverage"])

    rows = []
    for label, (group, cov) in sorted(groups.items(), key=lambda kv: (kv[1][0], kv[0])):
        b = base.get(label)
        if not b:
            continue
        lw = soak_c_lw.get(label) or soak_a_lw.get(label)
        first = lw[0] if lw else None
        last = lw[-1] if lw else None
        rows.append({
            "接口": label, "分组": group, "场景": cov,
            "基线样本": b["samples"], "基线Avg(ms)": num(b["avg_ms"], 1),
            "基线P90(ms)": num(b["p90_ms"]), "基线P95(ms)": num(b["p95_ms"]),
            "基线P99(ms)": num(b["p99_ms"]), "基线错误率": pct(b["err_rate"]),
            "基线缺陷数": b["defects"],
            "soak首窗P95(ms)": num(first["p95_ms"]) if first else "—",
            "soak末窗P95(ms)": num(last["p95_ms"]) if last else "—",
            "soak末窗RPS": num(last["rps"], 1) if last else "—",
            "soak末窗错误率": pct(last["err_rate"]) if last else "—",
        })

    with (RES / "per_endpoint.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    md = ["# 附件 A：逐接口基线指标（并发 1，循环 3 次）\n",
          "说明：基线错误率按“与期望状态码不符”计；缺陷数为 5xx/连接失败。"
          "soak 列为第一轮 4 小时稳定性测试中该接口的首/末 30 分钟窗口（仅 soak 脚本覆盖的 20 个接口有值）。\n",
          "| 接口 | 场景 | 样本 | Avg | P90 | P95 | P99 | 错误率 | 缺陷 | soak首窗P95 | soak末窗P95 |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        md.append(f"| `{r['接口']}` | {r['场景']} | {r['基线样本']} | {r['基线Avg(ms)']} | {r['基线P90(ms)']} | "
                  f"{r['基线P95(ms)']} | {r['基线P99(ms)']} | {r['基线错误率']} | {r['基线缺陷数']} | "
                  f"{r['soak首窗P95(ms)']} | {r['soak末窗P95(ms)']} |")
    (RES / "appendix_endpoints.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"[ok] {len(rows)} 个接口 → results/per_endpoint.csv, results/appendix_endpoints.md")


if __name__ == "__main__":
    main()
