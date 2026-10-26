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
    _AUDIOBOOK_SPLIT_MIN_CHARS,
    _append_audiobook_position_rule,
    _clean_audiobook_bridge_phrases,
    _clean_audiobook_segment_content,
    _build_audiobook_quality_rule,
    _detect_repeated_audiobook_hooks,
    _split_overlong_audiobook_segments,
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
    """禁语表替换值必须透明：空串=删除、“回到书中，”=承接语，或显式登记的
    中性化语义替换（T01009：游戏受众称呼/喻体换词而非删除，删除会破句残留逗号）。"""
    allowed_semantic_repl = {"各位听众", "经典之作"}
    for phrase, repl in _AUDIOBOOK_BRIDGE_CLEANUP.items():
        # 替换值必须为非空承接语、显式空串（删除）或已登记的语义替换；不允许 Any/占位假值
        assert (
            repl == "" or repl == "回到书中，" or repl in allowed_semantic_repl
        ), f"非法替换值: {phrase!r} -> {repl!r}"


# ---------- 频道级清洗 ----------

def test_clean_removes_game_channel_intro_t01009():
    """T01009：style_hint 曾误注入游戏词库，稿件残留游戏播报开场与受众称呼，
    兜底清洗应删除开场套话并把称呼中性化。"""
    text = (
        "来看今天游戏圈的一条重磅消息，这听起来似乎与文学阅读相去甚远。"
        "余华写道……各位游戏爱好者，是否也停下来问过自己？"
    )
    cleaned, hits = _clean_audiobook_bridge_phrases(text)
    assert "来看今天游戏圈的一条重磅消息" not in cleaned
    assert "各位游戏爱好者" not in cleaned
    assert "各位听众" in cleaned
    assert hits >= 2
    # 开场删除后不应残留段首/句首孤立标点
    assert not cleaned.startswith(("，", "。"))


def test_clean_strips_leading_punctuation_t01009():
    """T01009：LLM 残留的段首孤立句号（含 \\n\\n 后行首形态）应被剥离。"""
    cleaned, _ = _clean_audiobook_bridge_phrases("。在《我只知道人是什么》中，一个细节……")
    assert cleaned.startswith("在《我只知道人是什么》中")

    cleaned2, _ = _clean_audiobook_bridge_phrases(
        "会碰撞出怎样的火花？\n\n。二〇一四年十一月，我去意大利维罗纳地区。"
    )
    assert "？\n\n。" not in cleaned2
    assert "？\n\n二〇一四年十一月" in cleaned2


def test_clean_merges_material_line_breaks_t01009():
    """T01009：素材复制的单换行断行应合并，\\n\\n 自然段分隔保留；\\r\\n 先归一。"""
    cleaned, _ = _clean_audiobook_bridge_phrases("被视为英雄\r\n被请到耶路撒冷。")
    assert cleaned == "被视为英雄被请到耶路撒冷。"

    cleaned2, _ = _clean_audiobook_bridge_phrases("上段结束。\n\n下段开始。")
    assert cleaned2 == "上段结束。\n\n下段开始。"

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


# ---------- 未兑现预告句清洗（T01010 对标得到听书稿） ----------

def test_clean_removes_unfulfilled_promise_t01010():
    """T01010：选材截断导致的“待会再说”预告句应整句删除（seg10 真实案例句式），
    同句内的拼接过渡分句一并去除，其余正文不受影响。"""
    text = (
        "纳博科夫在此前的叙述里做了不少铺垫，让车祸之死变得与众不同了。"
        "还有一个记忆误差的例子我待会再说，我现在继续说说自己的“文革”往事。"
        "在那个压抑的年代里，他目睹了很多不幸。"
    )
    cleaned, hits = _clean_audiobook_bridge_phrases(text)
    assert "待会再说" not in cleaned
    assert "继续说说" not in cleaned
    assert "目睹了很多不幸" in cleaned
    assert hits >= 1
    # 整句删除后不应残留连续标点或孤立标点
    assert "。。" not in cleaned and "，。" not in cleaned


def test_clean_keeps_text_without_promise_t01010():
    """无预告短语的正常转述文本不得被切句逻辑误伤（含引号/书名号的复杂句）。"""
    text = "作者回忆道，一九九四年他借来了《爸爸出差时》，没有字幕却看懂了。后面的事，多年后仍历历在目。"
    cleaned, hits = _clean_audiobook_bridge_phrases(text)
    assert cleaned == text
    assert hits == 0


def test_position_rule_intro_and_outro_t01010():
    """T01010：首段注入作者导论条款、末段注入收尾总结条款、中间段不追加。"""
    rule = "【书籍解读专项要求】基础规则。"
    assert "正文开篇段" in _append_audiobook_position_rule(rule, 1, 11)
    assert "正文收尾段" in _append_audiobook_position_rule(rule, 11, 11)
    assert _append_audiobook_position_rule(rule, 5, 11) == rule
    # quality_rule 为 None（非 audiobook）时原样返回，不抛错
    assert _append_audiobook_position_rule(None, 1, 11) is None


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


# ---------- 超长段程序化拆分（T01010 对标得到听书稿·工程层兜底） ----------

def _para(text: str, n: int) -> str:
    """构造 n 字自然段（含句读，模拟真实讲书段落）。"""
    unit = "余华回忆道，那年冬天他借来了《爸爸出差时》，没有字幕却看懂了。"
    return (text + unit * 300)[:n]


def test_split_overlong_by_paragraph_boundaries():
    """1300 字含 3 自然段（各约 430 字）应拆为 2 段，且拆分无损（拼接还原全文）。"""
    p1, p2, p3 = _para("一", 430), _para("二", 430), _para("三", 440)
    seg = {"seq": 6, "material_id": 66, "title": "第六章", "content": f"{p1}\n\n{p2}\n\n{p3}"}
    out = _split_overlong_audiobook_segments([seg], words_per_segment=730)
    assert len(out) == 2
    # 无损：拆分段落去除分隔符后拼接应与原文一致
    assert (out[0]["content"] + out[1]["content"]).replace("\n\n", "") == p1 + p2 + p3
    # 阈值内：每段不超 max(730*1.5, 800)=1095
    threshold = max(int(730 * 1.5), _AUDIOBOOK_SPLIT_MIN_CHARS)
    assert all(len(s["content"]) <= threshold for s in out)
    # title/material_id 原样继承（素材溯源与文稿页封面一致）
    assert all(s["material_id"] == 66 and s["title"] == "第六章" for s in out)


def test_split_renumbers_seq_continuous():
    """拆分导致段数变化后 seq 必须重排为连续 1..N，否则前端文稿页错乱。"""
    p1, p2, p3 = _para("一", 430), _para("二", 430), _para("三", 440)
    segs = [
        {"seq": 1, "material_id": 1, "title": "a", "content": "正常短段落。"},
        {"seq": 2, "material_id": 2, "title": "b", "content": f"{p1}\n\n{p2}\n\n{p3}"},
    ]
    out = _split_overlong_audiobook_segments(segs, words_per_segment=730)
    assert [s["seq"] for s in out] == [1, 2, 3]


def test_split_noop_under_threshold():
    """未超阈值（words_per_segment×1.5）的正常段不拆，原对象原样保留。"""
    seg = {"seq": 1, "material_id": 1, "title": "a", "content": _para("一", 1000)}
    out = _split_overlong_audiobook_segments([seg], words_per_segment=730)
    assert out == [seg]


def test_split_single_para_over_threshold_kept_intact():
    """无自然段边界的超长段无法无损拆分，必须保留原段（禁止句中硬切）。"""
    body = _para("一", 1300)
    seg = {"seq": 1, "material_id": 1, "title": "a", "content": body}
    out = _split_overlong_audiobook_segments([seg], words_per_segment=730)
    assert len(out) == 1 and out[0]["content"] == body


def test_split_threshold_floor_800():
    """短节目档 words_per_segment=400 时阈值为绝对下限 800 而非 600，防过度拆碎。"""
    p1, p2 = _para("一", 500), _para("二", 500)
    seg = {"seq": 1, "material_id": 1, "title": "a", "content": f"{p1}\n\n{p2}"}
    out = _split_overlong_audiobook_segments([seg], words_per_segment=400)
    assert len(out) == 2
    assert all(len(s["content"]) <= _AUDIOBOOK_SPLIT_MIN_CHARS for s in out)


# ---------- 段首钩子同型重复检测（T01010·只告警不改稿） ----------

def test_hook_detect_reports_repeated_opener():
    """同型钩子（如“你有没有想过”）出现 >2 次应被报告，附出现次数。"""
    segs = [
        {"content": f"你有没有想过，第{i}段讲一个不同的故事。"}
        for i in range(3)
    ]
    repeats = _detect_repeated_audiobook_hooks(segs)
    assert ("你有没有想过" in repeats[0][0]) or any("你有没有想过" in c for c, _ in repeats)
    assert all(n >= 3 for _, n in repeats)


def test_hook_detect_ignores_variant_and_short_openers():
    """变体钩子（同型不同词）不误报；<4 字的连接词分句不作指纹。"""
    segs = [
        {"content": "你有没有想过，甲问题值得琢磨。"},
        {"content": "你是否想过，乙问题同样值得琢磨。"},  # 变体：不与前者同指纹
        {"content": "所以，这件事才显得反常。"},  # <4 字指纹：剔除
        {"content": "作者回忆道，一九九四年的冬天格外冷。"},
    ]
    assert _detect_repeated_audiobook_hooks(segs) == []


def test_hook_detect_noop_on_distinct_openers():
    """各段钩子各不相同时返回空列表。"""
    segs = [
        {"content": "作者在序章里讲了一个故事。"},
        {"content": "书中最反常识的细节出现了。"},
        {"content": "一九九四年冬天，作者借书未还。"},
    ]
    assert _detect_repeated_audiobook_hooks(segs) == []