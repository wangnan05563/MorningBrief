"""T00914 二轮：听书频道 30 分钟保底的时长口径贯通性测试。

覆盖三处必须一致的口径：
1. 频道级/类型级保底的解析（rewriter 与 stitch 共用同一函数）；
2. 拼接阶段的允许时长区间不得与保底值倒挂（历史缺陷：配 1800s 得 [1800, 720]）；
3. 保底驱动的目标字数反算（1800s → 与 600s 不同的字数预算）。
"""
from app.workflow.duration import (
    AUDIOBOOK_DEFAULT_MIN_SEC,
    duration_range_sec,
    resolve_channel_min_duration_sec,
)
from app.workflow.llm import rewriter
from app.workflow.stitch import concat


class TestResolveChannelMinDuration:
    def test_audiobook_defaults_to_30_min(self):
        assert resolve_channel_min_duration_sec("audiobook", None) == AUDIOBOOK_DEFAULT_MIN_SEC == 1800

    def test_news_channel_keeps_global(self):
        assert resolve_channel_min_duration_sec("news", None) is None
        assert resolve_channel_min_duration_sec(None, None) is None

    def test_explicit_config_wins_over_default(self):
        assert resolve_channel_min_duration_sec("audiobook", 900) == 900
        assert resolve_channel_min_duration_sec("news", 300) == 300

    def test_explicit_config_clamped(self):
        assert resolve_channel_min_duration_sec("audiobook", 10) == 180
        assert resolve_channel_min_duration_sec("audiobook", 99999) == 1800


class TestDurationRange:
    def test_no_channel_floor_keeps_legacy_target_band(self):
        assert duration_range_sec(600) == (480, 720)
        assert duration_range_sec(900) == (720, 1080)

    def test_channel_floor_raises_upper_bound_too(self):
        # 历史缺陷：上限固定取 target×1.2，配 1800s 保底会得到区间倒挂
        low, high = duration_range_sec(600, AUDIOBOOK_DEFAULT_MIN_SEC)
        assert (low, high) == (1800, 2160)
        assert high > low

    def test_small_channel_floor_keeps_target_upper(self):
        assert duration_range_sec(600, 300) == (300, 720)

    def test_invalid_target_falls_back(self):
        assert duration_range_sec("abc", None) == (480, 720)

    def test_stitch_wrapper_matches_module(self, monkeypatch):
        monkeypatch.setattr(concat.settings, "TARGET_DURATION_SEC", 600, raising=False)
        assert concat._get_duration_range(AUDIOBOOK_DEFAULT_MIN_SEC) == (1800, 2160)
        assert concat._get_duration_range(None) == (480, 720)


class TestRewriterWordBudget:
    def test_audiobook_target_sec_uses_default_floor(self):
        # 保底 1800s 与全局 600s 必须反算出不同的字数预算，否则扩稿不生效
        seg10, words10 = rewriter._calc_segment_words(600, 1.0)
        seg30, words30 = rewriter._calc_segment_words(AUDIOBOOK_DEFAULT_MIN_SEC, 1.0)
        assert words30 > words10
        assert seg30 >= seg10

    def test_top_n_follows_target_segments(self, monkeypatch):
        """选题数随目标段数放大（30 分钟 + llm_max_script_segments=20 时取 20 条素材）。"""
        monkeypatch.setattr(rewriter.settings, "LLM_MAX_SCRIPT_SEGMENTS", 20, raising=False)
        target_segments, _ = rewriter._calc_segment_words(AUDIOBOOK_DEFAULT_MIN_SEC, 1.0)
        assert target_segments == 20
        assert max(rewriter.SELECT_TOP_N, target_segments) == 20

    def test_more_segments_keep_chapter_reading_order(self):
        """放大选题数用于按章节顺序取材的听书稿，不得打乱阅读顺序。"""
        materials = [{"id": i, "title": f"第{i}章", "content": "x" * 50} for i in range(1, 26)]
        picked = rewriter._select_top_materials(materials, top_n=20, strategy="outline")
        assert len(picked) == 20
        assert [m["id"] for m in picked] == list(range(1, 21))
