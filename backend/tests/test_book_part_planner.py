"""单本讲书分集编排与变量注入测试（T00626 P1）。

覆盖：
- 书名提取（书源前缀、章节分隔符）；
- 分篇阈值（单集 / 上·下 / 上·中·下）与**均衡切分**（边界落在整章、每篇不空）；
- 衔接语与篇尾预告（首篇无衔接 / 中篇回顾 / 末篇回应上一集；末篇提示"明天下一本"）；
- 改写模板注入：`{book_title}` 等新占位符被正确填充，未提供的未知占位符按空串兜底不抛错。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_book_part_planner.py
"""
import pytest

from app.services.book_part_planner import (
    estimate_chapter_words,
    extract_book_title,
    plan_book_parts,
)
from app.workflow.llm.rewriter import _build_prompt


def _chapter(mid: int, title: str, chars: int, source: str = "我只知道人是什么") -> dict:
    return {"id": mid, "title": title, "source": source, "url": f"https://x/{mid}", "content": "字" * chars}


class TestExtractBookTitle:
    @pytest.mark.parametrize(
        "source,title,expected",
        [
            ("我只知道人是什么", None, "我只知道人是什么"),
            ("维基文库-論語", None, "論語"),
            ("Gutendex-唐詩三百首", None, "唐詩三百首"),
            (None, "論語/學而第一", "論語"),
            (None, "唐詩三百首·卷一", "唐詩三百首"),
            (None, None, ""),
        ],
    )
    def test_extract(self, source, title, expected):
        assert extract_book_title(source, title) == expected


class TestEstimate:
    def test_short_chapter_has_floor(self):
        assert estimate_chapter_words("短", 1800) == 600

    def test_long_chapter_capped(self):
        assert estimate_chapter_words("字" * 100000, 1800) == int(1800 * 1.25)

    def test_mid_chapter_scaled(self):
        assert estimate_chapter_words("字" * 2000, 1800) == int(2000 * 0.85)


class TestPlanParts:
    def test_empty_materials(self):
        plan = plan_book_parts([])
        assert plan["parts"] == 0 and plan["assignments"] == {}

    def test_single_part_when_small(self):
        mats = [_chapter(1, "一", 2000), _chapter(2, "二", 2000)]
        plan = plan_book_parts(mats, words_per_segment=1800)
        assert plan["parts"] == 1
        assert {a["part_label"] for a in plan["assignments"].values()} == {"单集"}
        assert plan["assignments"][1]["part_link"] == "", "单集无衔接语"
        assert "明天" in plan["assignments"][2]["next_episode_hint"]

    def test_two_parts_with_balanced_split(self):
        # 6 章 × 3000 字 ≈ 6×2550 = 15300 → 两篇
        mats = [_chapter(i, f"第{i}章", 3000) for i in range(1, 7)]
        plan = plan_book_parts(mats, words_per_segment=1800)
        assert plan["parts"] == 2, plan["total_words_estimate"]
        labels = [plan["assignments"][m["id"]]["part_label"] for m in mats]
        assert labels[:3] == ["上篇"] * 3 and labels[3:] == ["下篇"] * 3, labels

    def test_three_parts_boundaries_on_chapters(self):
        # 单章估算上限 2250 字（words_per_segment×1.25）→ 12 章 = 27000 字 > 24000 才三篇
        mats = [_chapter(i, f"第{i}章", 8000) for i in range(1, 13)]
        plan = plan_book_parts(mats, words_per_segment=1800)
        assert plan["parts"] == 3, plan["total_words_estimate"]
        # 每篇都必须有章节（边界落在整章，不出现空篇）
        assert all(len(part) == 4 for part in plan["part_chapters"]), plan["part_chapters"]
        labels = [plan["assignments"][m["id"]]["part_label"] for m in mats]
        assert labels.count("上篇") + labels.count("中篇") + labels.count("下篇") == 12

    def test_links_and_hints(self):
        mats = [_chapter(i, f"第{i}章", 8000) for i in range(1, 13)]
        plan = plan_book_parts(mats, words_per_segment=1800)
        assert plan["parts"] == 3, plan["total_words_estimate"]
        first = plan["assignments"][mats[0]["id"]]
        middle = plan["assignments"][mats[5]["id"]]   # 中篇首章（第 5-8 章为中篇）
        last = plan["assignments"][mats[-1]["id"]]
        assert first["part_link"] == ""
        assert "回顾上一集" in middle["part_link"]
        assert "接着把它讲完" in last["part_link"]
        assert "下一集" in first["next_episode_hint"]
        assert "明天" in last["next_episode_hint"]

    def test_part_brief_lists_chapters(self):
        mats = [_chapter(1, "學而第一", 3000, source="維基文庫-論語"),
                _chapter(2, "為政第二", 3000, source="維基文庫-論語")]
        plan = plan_book_parts(mats)
        brief = plan["assignments"][1]["part_brief"]
        assert "學而第一" in brief and brief.startswith("本篇覆盖：")

    def test_part_index_within_part(self):
        mats = [_chapter(i, f"第{i}章", 3000) for i in range(1, 7)]
        plan = plan_book_parts(mats, words_per_segment=1800)
        idxs = [plan["assignments"][m["id"]]["part_index"] for m in mats]
        assert idxs == [1, 2, 3, 1, 2, 3], idxs


class TestPromptInjection:
    TEMPLATE = (
        "讲《{book_title}》{part_label}第{part_index}/{part_total}段。\n"
        "{part_brief}\n{part_link}\n{next_episode_hint}\n"
        "章节：{title}\n正文：{content}\n"
        '输出 JSON：{{"title": "x", "content": "y"}}'
    )

    def _material(self):
        return {"id": 7, "title": "學而第一", "content": "子曰", "source": "論語", "url": "https://x/7"}

    def test_placeholders_filled(self):
        ctx = {
            "book_title": "論語", "part_label": "上篇", "part_index": 1, "part_total": 3,
            "part_brief": "本篇覆盖：學而第一。", "part_link": "",
            "next_episode_hint": "下一集我们接着讲《論語》的中篇。",
        }
        prompt = _build_prompt(self._material(), template_text=self.TEMPLATE, book_context=ctx)
        assert "讲《論語》上篇第1/3段" in prompt
        assert "本篇覆盖：學而第一。" in prompt
        assert "下一集我们接着讲" in prompt

    def test_no_book_context_renders_empty(self):
        """非讲书场景（无 book_context）：占位符为空串，模板不报错。"""
        prompt = _build_prompt(self._material(), template_text=self.TEMPLATE)
        assert "讲《》第/段" in prompt

    def test_unknown_placeholder_falls_back_to_empty(self):
        """模板引用未提供占位符时按空值兜底，不中断改写。"""
        template = "书名 {book_title}；未知 {not_provided_field}；正文 {content}"
        prompt = _build_prompt(self._material(), template_text=template)
        assert "未知 ；" in prompt
        assert "子曰" in prompt
