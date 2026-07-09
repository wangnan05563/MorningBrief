"""热度计算模块（LLD 7.2）。

综合热度 = 源权威度 × 0.3 + 标题关键词热度 × 0.4 + 发布时间近度 × 0.3

权重设计理由：
- 标题关键词热度权重最高（0.4），标题最能反映新闻重要性；
- 源权威度与时间近度权重相当（0.3），保证权威源 + 时效性的基础分；
- 三项均归一化到 [0, 1]，最终热度也在 [0, 1]。
"""
from datetime import datetime
from typing import Optional

from app.core.timeutil import utcnow_naive

# 热点关键词词表（运营维护，可配置）  # NOSONAR
# 命中后取最大分值，避免多关键词叠加导致偏差
HOT_KEYWORDS = {
    "突破": 0.9,
    "首发": 0.85,
    "独家": 0.8,
    "重磅": 0.95,
    "发布": 0.6,
    "上市": 0.7,
    "收购": 0.75,
    "融资": 0.65,
    "政策": 0.7,
    "改革": 0.65,
    "制裁": 0.85,
    "合作": 0.55,
}


def _keyword_heat(title: str) -> float:
    """标题关键词热度：取标题中命中的最热关键词的分值。

    多个关键词命中取最大值（避免叠加导致偏差）。
    无命中返回 0.3（基础分，避免完全无分导致热度趋零）。
    """
    max_score = 0.0
    for keyword, score in HOT_KEYWORDS.items():
        if keyword in title:
            max_score = max(max_score, score)
    # 无命中给基础分，避免冷门新闻热度归零被选题算法忽略
    return max_score if max_score > 0 else 0.3


def _recency_score(published_at: Optional[datetime]) -> float:
    """发布时间近度：越近分越高。

    24 小时内：1.0 → 0.5 线性衰减
    24-48 小时：0.5 → 0.2 线性衰减
    48-72 小时：0.2 → 0.0 线性衰减
    72 小时以上：0.0

    无发布时间取中值 0.5，避免未知时效的新闻被误判为冷门。
    """
    if not published_at:
        return 0.5
    delta = utcnow_naive() - published_at
    hours = delta.total_seconds() / 3600
    if hours <= 24:
        return 1.0 - (hours / 24) * 0.5
    elif hours <= 48:
        return 0.5 - ((hours - 24) / 24) * 0.3
    elif hours <= 72:
        return 0.2 - ((hours - 48) / 24) * 0.2
    else:
        return 0.0


def heat_score(material: dict) -> float:
    """综合热度计算（LLD 7.2 公式）。

    三项加权：
    - 源权威度 30%：来源在 rss.yaml 配置，权威媒体如新华/人民 0.9，自媒体 0.5
    - 关键词热度 40%：标题命中热点关键词
    - 时间近度 30%：发布越近分越高

    Args:
        material: 素材 dict，需包含 title，可选 source_authority / published_at
                  （schema 未含 source_authority 时默认 0.5，保证可计算）
    """
    authority = material.get("source_authority", 0.5)
    keyword_heat = _keyword_heat(material["title"])
    recency = _recency_score(material.get("published_at"))
    return authority * 0.3 + keyword_heat * 0.4 + recency * 0.3
