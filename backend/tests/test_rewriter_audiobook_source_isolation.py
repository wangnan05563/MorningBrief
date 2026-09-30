"""T00914 C10：rewriter 书源隔离纯函数 _filter_audiobook_sources 的单测。

背景：讲书稿模式下频道素材池的 `source` 统一等于书名。历史上一期《每日听书》
(wf-20260922-0001) 的 referenced_materials 混入 culture.people.com.cn 外链
（《大敦煌》《非来不可》等书外内容），导致稿件串味。本函数按 source 锚定
章节数最多的"当前书"，剔除书外素材。
"""
from app.workflow.llm.rewriter import _filter_audiobook_sources


def _m(mid, source, title="章节"):
    return {"id": mid, "source": source, "title": title}


def test_all_same_source_no_change():
    """素材池全部同属一本书（source 一致）时不做变更。"""
    mats = [_m(1, "我只知道人是什么"), _m(2, "我只知道人是什么"), _m(3, "我只知道人是什么")]
    assert _filter_audiobook_sources(mats) == mats


def test_empty_returns_empty():
    assert _filter_audiobook_sources([]) == []


def test_drops_off_book_materials():
    """章节数最多的 source 作为锚，剔除外链/书外素材，保留本书章节。"""
    mats = [
        _m(1, "我只知道人是什么", "序章"),
        _m(2, "我只知道人是什么", "第一章"),
        _m(3, "我只知道人是什么", "第二章"),
        _m(4, "我只知道人是什么", "第三章"),
        # 外链：书评源混入的书外内容（如《大敦煌》纪录片素材）
        _m(5, "culture.people.com.cn", "《大敦煌》：文明交融的智慧"),
        _m(6, "豆瓣读书-最新书评", "《非来不可》书评"),
    ]
    result = _filter_audiobook_sources(mats)
    assert {m["id"] for m in result} == {1, 2, 3, 4}
    assert all(m["source"] == "我只知道人是什么" for m in result)


def test_drops_when_min_segments_satisfied():
    """剔除后仍 ≥ min_segments 才过滤；不足时降级保留（不阻断工作流）。"""
    mats = [_m(1, "本书")] * 4 + [_m(5, "外链新闻")]
    # 默认 min_segments=3，仍剩 4 条 → 过滤
    result = _filter_audiobook_sources(mats, min_segments=3)
    assert all(m["source"] == "本书" for m in result)


def test_unknown_anchor_keeps_all():
    """锚不唯一（两个 source 章节数持平）时不可靠，降级保留全部。"""
    mats = [_m(1, "书甲"), _m(2, "书乙"), _m(3, "外链")]
    assert _filter_audiobook_sources(mats) == mats


def test_insufficient_after_filter_keeps_all():
    """剔除后不足 min_segments 时降级保留原始池，避免空节目。"""
    mats = [
        _m(1, "本书"), _m(2, "本书"),
        _m(3, "外链新闻A"), _m(4, "外链新闻B"),
    ]
    # 锚=本书(2条)，剔除 2 条后仍为 2 条 < min_segments=3 → 保留全部
    result = _filter_audiobook_sources(mats, min_segments=3)
    assert len(result) == 4