"""TTS 文本清洗的星号/符号变体覆盖测试（T00627）。

背景：用户实测「LLM 改写的文稿有时出现 **，TTS 也会读出来」。排查结论：
- ASCII `**` 早已覆盖，但**全角 ＊ / ﹡ / ∗ / ⁎ 与装饰星 ✱✳✻✽❋、参考标记 ※ 完全未覆盖**；
- 8 月的真实脏数据形态是**残缺标记粘连中文**（如「根据**数据」「、**组织奖」），
  属清洗上线前十历史行（`rewriter.py` 主解析路径此前未调用清洗）。

本测试锁定：
- 真实脏数据形态（含 ASCII 残缺标记与全角变体）→ 彻底清除；
- 零宽字符（ZWSP/ZWNJ/ZWJ/WORD-JOINER/BOM）→ 移除；
- 数学乘号 `1*2*3` / `3 * 4` 仍受保护；
- 幂等（重复清洗无副作用）；
- `_assemble_script` 末道防线：手填开场白/结尾里的标记同样被清洗（落库即干净）。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_text_clean_symbols.py
"""
import pytest

from app.workflow.llm.rewriter import _assemble_script
from app.workflow.text_clean import strip_markdown_residue as clean


class TestAsteriskVariants:
    """星号变体（T00627 新增覆盖）。"""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # 真实脏数据（8 月稿）：ASCII 残缺标记粘连中文
            ("根据**数据，二季度英国劳动力市场整体降温", "根据数据，二季度英国劳动力市场整体降温"),
            ("还设置了文化交流使者奖、**组织奖等多个特别奖项", "还设置了文化交流使者奖、组织奖等多个特别奖项"),
            ("发展奖励，**可达500万元", "发展奖励，可达500万元"),
            # 全角成对与残缺
            ("这是＊＊全角重点＊＊内容。", "这是全角重点内容。"),
            ("根据＊＊数据，二季度", "根据数据，二季度"),
            # 其他变体
            ("这是※参考内容。", "这是参考内容。"),
            ("小号﹡标记﹡测试", "小号标记测试"),
            ("数学符∗号∗测试", "数学符号测试"),
            ("装饰✱星✳号✻测✽试❋", "装饰星号测试"),
            # 行首残缺标记
            ("＊＊第一点：内容", "第一点：内容"),
        ],
    )
    def test_variants_removed(self, raw, expected):
        assert clean(raw) == expected

    def test_math_asterisk_preserved(self):
        """数学乘号不能被误删（回归保护）。"""
        assert clean("1*2*3 的乘积") == "1*2*3 的乘积"
        assert clean("面积是 3 * 4 平方米") == "面积是 3 * 4 平方米"

    def test_emphasis_keeps_inner_text(self):
        assert clean("这是**重点**内容") == "这是重点内容"
        assert clean("这是＊重点＊内容") == "这是重点内容"


class TestZeroWidth:
    def test_zero_width_chars_removed(self):
        raw = "零宽\u200b字符\u200c测试\u200d与\ufeffBOM\u2060连接"
        assert clean(raw) == "零宽字符测试与BOM连接"

    def test_zero_width_between_emphasis_marks(self):
        """零宽字符夹在成对标记中间时，清洗后不应残留任何标记。"""
        raw = "重\u200b点**内容**结束"
        out = clean(raw)
        assert "*" not in out
        assert "重点内容结束" == out


class TestIdempotent:
    @pytest.mark.parametrize(
        "raw",
        ["根据**数据，二季度", "这是＊＊全角＊＊内容", "1*2*3 与 3 * 4", "普通干净文本，无异样。"],
    )
    def test_second_pass_no_change(self, raw):
        once = clean(raw)
        assert clean(once) == once


class TestAssembleScriptDefense:
    """`_assemble_script` 末道防线：手填开场白/结尾的标记也要清洗（落库即干净）。"""

    def test_intro_outro_and_body_cleaned(self):
        segments = [
            {"seq": 2, "title": "正文一", "content": "根据**数据，本季整体降温。", "material_id": 1, "start_sec": 0, "end_sec": 30},
            {"seq": 3, "title": "正文二", "content": "这是＊＊全角重点＊＊。", "material_id": 2, "start_sec": 30, "end_sec": 60},
        ]
        out = _assemble_script(
            segments,
            intro_text="大家好，**欢迎收听**本节目。",
            outro_text="感谢收听，＊＊下期再见＊＊。",
            inject_date=False,
        )
        full = out["full_text"]
        for mark in ("*", "＊", "※"):
            assert mark not in full, f"残留标记 {mark}: {full[:80]}"
        assert "根据数据" in full and "这是全角重点" in full
        assert "欢迎收听" in full and "下期再见" in full
        # 分段内容与 full_text 一致干净（库内与送 TTS 的文本同源）
        assert all("*" not in s["content"] and "＊" not in s["content"] for s in out["segments_json"])
        # 字数为清洗后字数
        assert out["total_words"] == sum(len(s["content"]) for s in out["segments_json"])

    def test_default_intro_outro_unaffected(self):
        """未传频道文案时走默认 INTRO/OUTRO，清洗不应破坏正文。"""
        out = _assemble_script(
            [{"seq": 2, "title": "正文", "content": "正常正文内容。", "material_id": 1, "start_sec": 0, "end_sec": 20}],
            inject_date=False,
        )
        assert "正常正文内容。" in out["full_text"]
        assert out["total_words"] > 0
