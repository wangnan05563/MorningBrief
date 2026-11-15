"""T05753 课程生成链路与素材相关性回归测试。

覆盖三类零 LLM 成本的核心逻辑：
1. 课程素材源守卫（纯 RSS 新闻快速失败 / 混入文档时只保留文档）；
2. 单文档隔离、heat 段序与课程位置约束（纯函数）；
3. 课程稿确定性审计与课程版相关性 prompt。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.workflow.llm import rewriter


def _m(mid: int, title: str, source: str, source_type: str = "list", content: str = ""):
    return {
        "id": mid,
        "title": title,
        "source": source,
        "source_type": source_type,
        "content": content or f"{title} 正文内容",
        "url": f"https://doc.test/{mid}",
        "category": "课程",
    }


# ==========================================================================
# 1. 素材源守卫
# ==========================================================================
def test_material_public_dict_exposes_source_type():
    """_fetch_materials 返回的 dict 必须带 source_type，课程守卫才有判据。"""
    row = SimpleNamespace(
        id=1, source="doc-upload", source_type="list", title="第一章",
        content="正文", url="https://doc.test/1", published_at=None,
        category="课程", workflow_id=None, cover_url=None,
    )
    assert rewriter._material_to_public_dict(row)["source_type"] == "list"


def test_course_guard_rejects_rss_only_material_pool():
    """实测根因：course 频道 180 条素材全是 rss 新闻，必须快速失败而非拼课。"""
    materials = [
        _m(1, "竹节虫无性繁殖", "IT之家", "rss"),
        _m(2, "北汽第 4000 万辆交付", "IT之家", "rss"),
    ]
    with pytest.raises(rewriter.LLMError) as exc:
        rewriter._filter_course_materials_by_source_type(materials)
    message = str(exc.value)
    assert "课程频道素材源不匹配" in message
    assert "上传课程文档" in message


def test_course_guard_keeps_documents_and_drops_rss():
    """课程池里混入资讯时只保留文档类素材，不让新闻串进讲义。"""
    materials = [
        _m(1, "第一章 机器学习概述", "AI 通识讲义", "list"),
        _m(2, "第二章 监督学习", "AI 通识讲义", "cos"),
        _m(3, "V2EX 求推荐 VPS", "V2EX", "rss"),
        _m(4, "手机新品曝光", "IT之家", "rss"),
    ]
    kept = rewriter._filter_course_materials_by_source_type(materials)
    assert [m["id"] for m in kept] == [1, 2]


# ==========================================================================
# 2. 单文档隔离与段序
# ==========================================================================
def test_course_document_isolation_picks_largest_source():
    """同一期只讲章节数最多的那份讲义，避免两门课混讲。"""
    materials = [
        _m(1, "讲义A 第一章", "讲义A"),
        _m(2, "讲义A 第二章", "讲义A"),
        _m(3, "讲义A 第三章", "讲义A"),
        _m(4, "讲义B 第一章", "讲义B"),
    ]
    kept = rewriter._filter_course_document_sources(materials, min_segments=3)
    assert [m["id"] for m in kept] == [1, 2, 3]


def test_course_document_isolation_keeps_all_on_tie():
    """两份讲义章节数相同无法判定锚时降级保留，不误删素材。"""
    materials = [
        _m(1, "讲义A 第一章", "讲义A"),
        _m(2, "讲义A 第二章", "讲义A"),
        _m(3, "讲义B 第一章", "讲义B"),
        _m(4, "讲义B 第二章", "讲义B"),
    ]
    kept = rewriter._filter_course_document_sources(materials, min_segments=3)
    assert len(kept) == 4


def test_order_course_materials_heat_groups_by_source_then_id():
    """heat 不能让章节乱序：同源讲义先聚合，再按 id（章节）升序。"""
    materials = [
        _m(3, "讲义B 第一章", "讲义B"),
        _m(2, "讲义A 第二章", "讲义A"),
        _m(4, "讲义B 第二章", "讲义B"),
        _m(1, "讲义A 第一章", "讲义A"),
    ]
    ordered = rewriter._order_course_materials(materials, "heat")
    sources = [m["source"] for m in ordered]
    assert sources in (["讲义B", "讲义B", "讲义A", "讲义A"],
                       ["讲义A", "讲义A", "讲义B", "讲义B"])


def test_order_course_materials_outline_is_untouched():
    """outline 已按章节 id 选题，不能再排序打乱运营指定顺序。"""
    materials = [_m(3, "第三章", "讲义A"), _m(1, "第一章", "讲义A")]
    assert rewriter._order_course_materials(materials, "outline") == materials


# ==========================================================================
# 3. 课程位置约束与审计
# ==========================================================================
def test_course_quality_rule_contains_position_outline_and_bans():
    selected = [
        _m(1, "什么是人工智能", "AI 通识讲义"),
        _m(2, "机器学习入门", "AI 通识讲义"),
        _m(3, "神经网络基础", "AI 通识讲义"),
    ]
    ctx_map = rewriter._build_course_context_map(selected, "AI 通识课堂")
    rule = rewriter._build_course_quality_rule(ctx_map[2])
    assert rule
    assert "第 2/3 讲" in rule
    assert "上一讲是《什么是人工智能》" in rule
    assert "下一讲是《神经网络基础》" in rule
    assert "不得提前展开" in rule
    assert "据悉" in rule
    assert "上节讲过" in rule


def test_course_quality_rule_first_and_last_position():
    selected = [_m(1, "第一讲", "讲义A"), _m(2, "第二讲", "讲义A")]
    ctx_map = rewriter._build_course_context_map(selected, "课程")
    first = rewriter._build_course_quality_rule(ctx_map[1])
    last = rewriter._build_course_quality_rule(ctx_map[2])
    assert "课程开篇" in first
    assert "课程收尾" in last


def test_build_prompt_puts_course_rule_at_the_end():
    """课程专项约束必须追加在 prompt 最末，优先于素材内容指令生效。"""
    selected = [_m(1, "什么是人工智能", "AI 通识讲义")]
    ctx_map = rewriter._build_course_context_map(selected, "AI 通识课堂")
    rule = rewriter._build_course_quality_rule(ctx_map[1])
    template = '{{"title": "{title}", "content": "{content}", "source": "{source}"}}'
    prompt = rewriter._build_prompt(
        selected[0], template_text=template, quality_rule=rule,
    )
    assert "第 1/1 讲" in prompt
    assert prompt.rstrip().endswith(rule.strip())


def test_audit_course_script_flags_news_tone_and_dangling():
    segments = [
        {"seq": 2, "title": "机器学习", "content": "据悉，记者了解到该技术很热。"},
        {"seq": 3, "title": "神经网络", "content": "上节我们讲过感知机，这里不再展开。"},
        {"seq": 4, "title": "神经网络", "content": "神经网络由多层感知机组成。"},
    ]
    issues = rewriter._audit_course_script(segments)
    types = {issue["issue_type"] for issue in issues}
    assert "news_tone" in types
    assert "dangling_reference" in types
    assert "duplicate_topic" in types


def test_audit_course_script_clean_script_has_no_issue():
    segments = [
        {"seq": 2, "title": "什么是机器学习", "content": "机器学习是让程序从数据中总结规律的方法。"},
        {"seq": 3, "title": "监督学习", "content": "监督学习依靠带标签的数据来训练模型。"},
        {"seq": 4, "title": "本节复习", "content": "上一节是《什么是机器学习》，我们已了解了基本定义。"},
    ]
    assert rewriter._audit_course_script(segments) == []


def test_audit_summary_counts_by_type():
    issues = [
        {"issue_type": "news_tone"},
        {"issue_type": "news_tone"},
        {"issue_type": "hook_repeat"},
    ]
    summary = rewriter._summarize_course_audit(issues)
    assert summary["issue_count"] == 3
    assert summary["by_type"] == {"news_tone": 2, "hook_repeat": 1}


# ==========================================================================
# 4. 课程版相关性 prompt
# ==========================================================================
@pytest.mark.asyncio
async def test_course_relevance_prompt_uses_course_editor(monkeypatch):
    captured = {}

    async def fake_call_llm(prompt: str) -> str:
        captured["prompt"] = prompt
        return "[0, 1, 2, 3, 4]"

    monkeypatch.setattr(rewriter, "_call_llm", fake_call_llm)
    materials = [
        _m(1, "第一章 机器学习概述", "AI 通识讲义", "list"),
        _m(2, "第二章 监督学习", "AI 通识讲义", "list"),
        _m(3, "第三章 无监督学习", "AI 通识讲义", "list"),
        _m(4, "第四章 神经网络", "AI 通识讲义", "list"),
        _m(5, "第五章 模型评估", "AI 通识讲义", "list"),
        _m(6, "V2EX 求推荐新加坡 VPS", "V2EX", "rss"),
        _m(7, "手机新品曝光", "IT之家", "rss"),
    ]
    kept = await rewriter._filter_materials_by_relevance(
        materials, "AI 通识课堂", "面向大众的 AI 通识课程", channel_type="course",
    )
    assert [m["id"] for m in kept] == [1, 2, 3, 4, 5]
    assert "课程编辑" in captured["prompt"]
    assert "同一门课程" in captured["prompt"]
    assert "新闻频道内容审核员" not in captured["prompt"]


@pytest.mark.asyncio
async def test_news_relevance_prompt_keeps_original_role(monkeypatch):
    captured = {}

    async def fake_call_llm(prompt: str) -> str:
        captured["prompt"] = prompt
        return "[0, 1]"

    monkeypatch.setattr(rewriter, "_call_llm", fake_call_llm)
    materials = [
        _m(1, "影视动态", "某站", "rss"),
        _m(2, "音乐资讯", "某站", "rss"),
    ]
    kept = await rewriter._filter_materials_by_relevance(
        materials, "娱乐焦点", "影视音乐资讯",
    )
    assert len(kept) == 2
    assert "新闻频道内容审核员" in captured["prompt"]
    assert "课程编辑" not in captured["prompt"]
