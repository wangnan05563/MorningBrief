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
    # D39：值是播放数 × 3 的推算（每期固定三段广告），不是曝光埋点。
    # label 直接写「推算」，note 随 meta 下发到卡片脚注——只在文档或 tooltip 里
    # 说明，截图传播时仍会被读成真实曝光。
    "ad_impression": {
        "label": "推算广告曝光",
        "unit": "count",
        "display": {"unit": "次", "factor": 1, "precision": 0},
        "note": "按每期 3 段推算（播放数 × 3），不是真实曝光埋点，不能用来算点击率/完播率",
    },
    # ---- INT-UX-03 / T02526：llm-metrics 与 rss-health ----
    # 这四个计数与三条率同源于 rewriter._WORD_COUNT_RETRY_STATS（进程内累计，重启清零）。
    "trigger_rate": {
        "label": "触发率",
        # 后端已经 ×100（rewriter.get_word_count_retry_stats），所以换算是 1 而不是 100。
        # 与 completion_rate（unit=ratio、factor=100）刻意相反：两个都叫 rate，量级却不同，
        # 只有 unit 能区分——页面自己写死 "%" 时看不出风险，接到共用格式化器上就会乘两次。
        "unit": "percent",
        "display": {"unit": "%", "factor": 1, "precision": 2},
    },
    "improve_rate": {
        "label": "改善率",
        "unit": "percent",
        "display": {"unit": "%", "factor": 1, "precision": 2},
    },
    "not_improve_rate": {
        "label": "未改善率",
        "unit": "percent",
        "display": {"unit": "%", "factor": 1, "precision": 2},
    },
    "total_calls": {
        "label": "改写调用总数",
        "unit": "count",
        "display": {"unit": "次", "factor": 1, "precision": 0},
    },
    "triggered": {
        "label": "触发重试",
        "unit": "count",
        "display": {"unit": "次", "factor": 1, "precision": 0},
    },
    "improved": {
        "label": "重试有改善",
        "unit": "count",
        "display": {"unit": "次", "factor": 1, "precision": 0},
    },
    "not_improved": {
        "label": "重试未改善",
        "unit": "count",
        "display": {"unit": "次", "factor": 1, "precision": 0},
    },
    # 表头原先写死「 ms」，属 PRD 点名要消掉的「页面自己标单位」
    "latency_ms": {
        "label": "响应延迟",
        "unit": "millisecond",
        "display": {"unit": "ms", "factor": 1, "precision": 0},
    },
    "consecutive_failures": {
        "label": "连续失败",
        "unit": "count",
        "display": {"unit": "次", "factor": 1, "precision": 0},
    },
    # channel-health 的 daily_trend[].count：卡片折线不画坐标轴，单位只能靠文案，
    # 页面原先自己写死「条」——写「次」还是「条」没人会发现不一致
    "count": {
        "label": "每日入库",
        "unit": "count",
        "display": {"unit": "条", "factor": 1, "precision": 0},
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

# LLM 指标页：三条率 + 四个计数（累计起点由 started_at/pid 另行说明，FR-UX-503）
LLM_METRICS = [
    "total_calls",
    "triggered",
    "improved",
    "not_improved",
    "trigger_rate",
    "improve_rate",
    "not_improve_rate",
]

# RSS 健康度表格里带单位的列
RSS_HEALTH_METRICS = [
    "latency_ms",
    "consecutive_failures",
]

# 频道健康度折线（daily_trend[].count）的计数单位
CHANNEL_HEALTH_METRICS = [
    "count",
]


def meta_for(*fields: str) -> dict[str, dict]:
    """取若干指标的单位元数据；未登记的指标不返回（页面会显示 '-' 而不是猜单位）。"""
    return {f: METRIC_META[f] for f in fields if f in METRIC_META}
