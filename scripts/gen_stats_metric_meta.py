"""导出统计指标单位元数据，供前端测试夹具使用（FR-UX-501 / T02506）。

用法：python scripts/gen_stats_metric_meta.py
输出：apps/admin-web/tests/helpers/stats-metric-meta.json

单位字典的唯一真源是 `backend/app/services/stats_metrics.py`；
前端 e2e 夹具需要同一份数据，但不能靠手抄——手抄就是本单要消灭的那类重复。
改完字典重跑本脚本，并由 `backend/tests/test_stats_metric_meta.py` 校验 JSON 与字典一致。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.stats_metrics import METRIC_META  # noqa: E402

OUT = ROOT / "apps" / "admin-web" / "tests" / "helpers" / "stats-metric-meta.json"


def main() -> None:
    OUT.write_text(
        json.dumps(METRIC_META, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({len(METRIC_META)} metrics)")


if __name__ == "__main__":
    main()
