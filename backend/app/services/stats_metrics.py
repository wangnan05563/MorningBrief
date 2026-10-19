"""统计指标单位元数据（FR-UX-501 / T02506）。

口径：接口一律按「原始单位」返回数值，换算与单位文案由本表随数据一起下发，
展示端按 meta 格式化——同一指标在 PC 卡片、移动端首页、小程序只乘换算一次。
新增统计指标时在这里登记，不要在页面里另写一份「(分钟)」「(%)」。
"""

# unit = 原始值单位（count 次/人、second 秒、ratio 0~1 小数、percent 0~100）
# display = 展示换算：factor 乘数、precision 小数位、unit 展示单位
METRIC_META: dict[str, dict] = {
    "dau": {
        "label": "DAU",
        "unit": "count",
        "display": {"unit": "人", "factor": 1, "precision": 0},
    },
    "play_count": {
        "label": "播放量",
        "unit": "count",
        "display": {"unit": "次", "factor": 1, "precision": 0},
    },
    "completion_rate": {
        "label": "完播率",
        "unit": "ratio",
        "display": {"unit": "%", "factor": 100, "precision": 1},
    },
    # 原始值是 func.avg(PlayLog.duration)，PlayLog.duration 存秒（models/play_log.py:32）
    "avg_listen_duration": {
        "label": "平均收听",
        "unit": "second",
        "display": {"unit": "分钟", "factor": 1 / 60, "precision": 1},
    },
    "ad_impression": {
        "label": "广告曝光",
        "unit": "count",
        "display": {"unit": "次", "factor": 1, "precision": 0},
    },
}

# 概览卡片的固定顺序（展示端按此顺序渲染，避免各页面各自排一遍）
OVERVIEW_METRICS = [
    "dau",
    "play_count",
    "completion_rate",
    "avg_listen_duration",
    "ad_impression",
]


def meta_for(*fields: str) -> dict[str, dict]:
    """取若干指标的单位元数据；未登记的指标不返回（页面会显示 '-' 而不是猜单位）。"""
    return {f: METRIC_META[f] for f in fields if f in METRIC_META}
