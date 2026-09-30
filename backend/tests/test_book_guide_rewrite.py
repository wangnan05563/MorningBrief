"""T00584 —— 得到式听书改造（一本书一条完整音频）单元测试。

覆盖三件事：
1. `LLM_MAX_SCRIPT_SEGMENTS` 可运行时配置（默认 10；调到 20 后 30 分钟节目可产 20 段）；
2. 得到式书籍导读模板 `prompts/rewrite_book_guide.txt` 存在、可被 `_resolve_rewrite_template`
   的 `file:` 前缀与文件名两种方式解析，且占位符与 `_build_prompt` 的 format 参数严格兼容；
3. 模板内容确为「讲书人」风格（而非新闻改写），且自带 JSON 输出格式声明
   （`_build_prompt` 据此判断不再追加 JSON 后缀）。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_book_guide_rewrite.py
"""
import pytest

from app.workflow.llm import rewriter
from app.workflow.llm.rewriter import (
    MAX_SCRIPT_SEGMENTS,
    _calc_segment_words,
    _resolve_rewrite_template,
)

TEMPLATE_NAME = "rewrite_book_guide.txt"


# ---------- 1. 段数上限可配置 ----------

def test_default_segment_cap_is_10():
    """默认行为不变：30 分钟目标在旧上限下仍只产 10 段。"""
    seg_count, words = _calc_segment_words(1800, 1.0)
    assert seg_count == MAX_SCRIPT_SEGMENTS == 10
    assert words >= 200


def test_segment_cap_configurable_to_20(monkeypatch):
    """LLM_MAX_SCRIPT_SEGMENTS=20 时，30 分钟目标可产 20 段（得到式 20-30 分钟）。"""
    monkeypatch.setattr(rewriter.settings, "LLM_MAX_SCRIPT_SEGMENTS", 20, raising=False)
    seg_count, words = _calc_segment_words(1800, 1.0)
    assert seg_count == 20
    assert words >= 200


def test_segment_cap_clamped_to_sane_range(monkeypatch):
    """误配防呆：上限被钳制在 [10, 40]，且非法值回退默认。"""
    monkeypatch.setattr(rewriter.settings, "LLM_MAX_SCRIPT_SEGMENTS", 3, raising=False)
    assert _calc_segment_words(1800, 1.0)[0] == 10  # 低于 10 的配置抬回 10
    monkeypatch.setattr(rewriter.settings, "LLM_MAX_SCRIPT_SEGMENTS", 999, raising=False)
    # 3600s（1 小时）自然段数 ≈56，超配 999 被钳到 40
    assert _calc_segment_words(3600, 1.0)[0] == 40
    monkeypatch.setattr(rewriter.settings, "LLM_MAX_SCRIPT_SEGMENTS", "abc", raising=False)
    assert _calc_segment_words(1800, 1.0)[0] == MAX_SCRIPT_SEGMENTS  # 非法回退默认


# ---------- 2. 得到式模板存在且可解析 ----------

def test_book_guide_template_file_exists():
    t = _resolve_rewrite_template(f"file:{TEMPLATE_NAME}", "audiobook")
    assert t and "讲书" in t


def test_book_guide_template_resolvable_by_filename():
    """频道列直接存文件名的旧用法同样可解析。"""
    t = _resolve_rewrite_template(TEMPLATE_NAME, "audiobook")
    assert t and "讲书" in t


def test_book_guide_template_placeholders_compatible():
    """模板占位符必须与 _build_prompt 的 format 参数严格兼容（多余占位符会 KeyError）。"""
    t = _resolve_rewrite_template(f"file:{TEMPLATE_NAME}", "audiobook")
    kwargs = dict(
        title="书名", content="正文", source="来源", category="有声书", source_url="https://x",
        words_per_segment=500, words_min=450, words_max=550, segment_duration=90,
    )
    formatted = t.format(**kwargs)  # 不应抛 KeyError
    assert "书名" in formatted
    # JSON 输出格式声明由模板自带（_build_prompt 据此判断不再追加后缀）
    assert '"title"' in t


def test_book_guide_template_is_speaker_style_not_news():
    t = _resolve_rewrite_template(f"file:{TEMPLATE_NAME}", "audiobook")
    # 讲书人风格标记
    for marker in ("讲书人", "这本书"):
        assert marker in t
    # 不应残留新闻播报式定位（如"为您播报今日新闻"）
    assert "播报今日" not in t
