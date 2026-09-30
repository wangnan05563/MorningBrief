"""T00914 B6/C8：rewriter 书籍质量兜底（动态规则 + 书外套话清洗）单测。

覆盖三个纯函数/低依赖函数：
1. _clean_audiobook_bridge_phrases：程序化清洗残留新闻播报式书外套话衔接短语
2. _clean_audiobook_segment_content：按频道类型决定是否清洗（仅 audiobook）
3. _build_audiobook_quality_rule：动态注入唯一书名/作者约束（channel_id=None 不触 DB）
"""
import pytest

from app.workflow.llm.rewriter import (
    _AUDIOBOOK_BRIDGE_CLEANUP,
    _AUDIOBOOK_QUALITY_RULE,
    _clean_audiobook_bridge_phrases,
    _clean_audiobook_segment_content,
    _build_audiobook_quality_rule,
)


# ---------- 书外套话清洗 ----------

def test_clean_swaps_bridge_phrase_to_neutral():
    """“从开发商动态来看”应被换成中性的“回到书中，”。"""
    text = "从开发商动态来看，本书主题直指人心。"
    cleaned, hits = _clean_audiobook_bridge_phrases(text)
    assert "从开发商动态来看" not in cleaned
    assert "回到书中，" in cleaned
    assert hits >= 1


def test_clean_removes_standalone_news_phrase():
    """“硬件之外，软件也有看点。”这类纯新闻套话应整体删除，不留空句。"""
    text = "文学中的克制与洞察。硬件之外，软件也有看点。"
    cleaned, _ = _clean_audiobook_bridge_phrases(text)
    assert "硬件之外" not in cleaned
    assert cleaned.strip()


def test_clean_noop_on_clean_text():
    """无套话的正常书籍解读文本不应被改动。"""
    text = "余华在序章中写道，人是什么这个问题贯穿了他的写作。"
    cleaned, hits = _clean_audiobook_bridge_phrases(text)
    assert cleaned == text
    assert hits == 0


def test_clean_empty_text():
    assert _clean_audiobook_bridge_phrases("") == ("", 0)


def test_clean_regularizes_dup_punctuation():
    """替换后可能残留的连续标点应被规整（中文逗号/句号去重）。"""
    cleaned, _ = _clean_audiobook_bridge_phrases("换个赛道，，然后。。")
    assert "，，" not in cleaned
    assert "。。" not in cleaned


def test_cleanup_table_has_no_opaque_repl():
    """禁语表应无“假值”占位替换（值为空串=删除，非空=换为承接语），防死代码。"""
    for phrase, repl in _AUDIOBOOK_BRIDGE_CLEANUP.items():
        # 替换值必须为非空承接语，或显式空串表示删除；不允许 Any/占位假值
        assert (
            repl == "" or repl == "回到书中，"
        ), f"非法替换值: {phrase!r} -> {repl!r}"


# ---------- 频道级清洗 ----------

def test_segment_clean_applies_on_audiobook():
    seg = {"material_id": 1, "content": "从开发商动态来看，我们回到书中。"}
    out = _clean_audiobook_segment_content(seg, "audiobook")
    assert "从开发商动态来看" not in out["content"]


def test_segment_clean_skips_non_audiobook():
    """news 频道的正常新闻衔接不得被清洗误伤。"""
    seg = {"material_id": 2, "content": "换个赛道来看，行业迎来新变化。"}
    out = _clean_audiobook_segment_content(seg, "news")
    assert out is seg  # 非 audiobook 必须原样返回（同一对象）
    assert "换个赛道来看" in seg["content"]


def test_segment_clean_keeps_identity_when_no_hit():
    seg = {"material_id": 3, "content": "纯粹书籍解读，无需清洗。"}
    out = _clean_audiobook_segment_content(seg, "audiobook")
    assert out is seg


# ---------- 动态质量规则 ----------

def test_rule_no_book_title_returns_base():
    """无书名时返回基础规则（构建是 async，需 await 校验）。"""
    import asyncio
    rule = asyncio.run(_build_audiobook_quality_rule(9, ""))
    assert rule == _AUDIOBOOK_QUALITY_RULE


@pytest.mark.asyncio
async def test_rule_book_title_injects_unique_name():
    rule = await _build_audiobook_quality_rule(None, "我只知道人是什么")
    assert "《我只知道人是什么》" in rule
    assert "正文统一以“我只知道人是什么”指代本书" in rule
    # 无 author（channel_id=None）时要求不编造作者
    assert "不要擅自编造作者姓名" in rule


@pytest.mark.asyncio
async def test_rule_without_author_forbids_fabrication():
    """未提供作者信息时，明确要求全文不得臆造作者，杜绝“昆德拉/余华”混记复现。"""
    rule = await _build_audiobook_quality_rule(None, "某书")
    assert "不得擅自编造作者姓名" in rule or "不要擅自编造作者姓名" in rule