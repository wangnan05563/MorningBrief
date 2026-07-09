"""热度计算测试。

覆盖 workflow/llm/heat_score.py：
- heat_score 综合分数在 [0, 1] 范围内
- 源权威度高的分数更高
- 发布时间越近分数越高
- 标题命中热词的分数更高
"""
from datetime import datetime, timedelta

from app.workflow.llm.heat_score import heat_score, _keyword_heat, _recency_score


def test_heat_score_range():
    """综合热度分数应在 [0, 1] 区间内。

    三项加权（authority*0.3 + keyword*0.4 + recency*0.3），
    各项均归一化到 [0,1]，故总和也在 [0,1]。
    """
    # 边界场景：低权威 + 无热词 + 旧新闻
    material = {
        "title": "普通日常新闻",
        "source_authority": 0.0,
        "published_at": datetime.utcnow() - timedelta(days=10),
    }
    score = heat_score(material)
    assert 0.0 <= score <= 1.0

    # 高分场景：高权威 + 热词 + 新发布
    material_hot = {
        "title": "重磅突破发布",
        "source_authority": 1.0,
        "published_at": datetime.utcnow(),
    }
    score_hot = heat_score(material_hot)
    assert 0.0 <= score_hot <= 1.0


def test_higher_authority_higher_score():
    """其他条件相同时，源权威度高的分数更高。"""
    base = {
        "title": "普通标题",
        "published_at": datetime.utcnow(),
    }
    low = heat_score({**base, "source_authority": 0.1})
    high = heat_score({**base, "source_authority": 0.9})
    assert high > low


def test_recency_factor():
    """其他条件相同时，发布时间越近分数越高。"""
    base = {
        "title": "普通标题",
        "source_authority": 0.5,
    }
    fresh = heat_score({**base, "published_at": datetime.utcnow()})
    old = heat_score({
        **base,
        "published_at": datetime.utcnow() - timedelta(days=5),
    })
    assert fresh > old


def test_recency_score_boundaries():
    """_recency_score 各时间区间边界值正确。

    - 无 published_at：0.5
    - 0 小时：1.0
    - 24 小时：0.5
    - 48 小时：0.2
    - 72 小时：0.0
    - >72 小时：0.0
    """
    assert _recency_score(None) == 0.5

    now = datetime.utcnow()
    # 容忍微秒精度误差，用近似断言
    assert abs(_recency_score(now) - 1.0) < 0.01
    assert abs(_recency_score(now - timedelta(hours=24)) - 0.5) < 0.05
    assert abs(_recency_score(now - timedelta(hours=48)) - 0.2) < 0.05
    assert abs(_recency_score(now - timedelta(hours=72)) - 0.0) < 0.05
    assert _recency_score(now - timedelta(days=10)) == 0.0


def test_keyword_heat_with_hot_word():
    """标题命中热词时 _keyword_heat 返回该词的分值。"""
    # "突破" 分值 0.9
    assert _keyword_heat("技术突破引发关注") == 0.9
    # "重磅" 分值 0.95，更高
    assert _keyword_heat("重磅消息发布") == 0.95


def test_keyword_heat_without_hot_word():
    """标题无热词时返回基础分 0.3。"""
    assert _keyword_heat("普通标题无热词") == 0.3


def test_keyword_heat_multiple_returns_max():
    """多个热词命中时取最大分值（不叠加）。"""
    # "突破" 0.9 与 "发布" 0.6 同时命中，取 0.9
    score = _keyword_heat("技术突破正式发布")
    assert score == 0.9


def test_keyword_heat_increases_total_score():
    """包含热词的标题综合分数高于无热词的标题。"""
    base = {
        "source_authority": 0.5,
        "published_at": datetime.utcnow(),
    }
    no_hot = heat_score({**base, "title": "普通日常新闻"})
    with_hot = heat_score({**base, "title": "重磅突破发布"})
    assert with_hot > no_hot


def test_heat_score_default_authority():
    """material 未提供 source_authority 时默认 0.5，不报错。"""
    score = heat_score({"title": "普通标题"})
    assert 0.0 <= score <= 1.0
