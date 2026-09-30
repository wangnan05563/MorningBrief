"""段间「连续衔接」模式回归测试（修复双人播报切换空档 + BGM 中断）。

根因（T00382）：
1. 段间空档——主音频用 concat demuxer 首尾硬接，段间必须插 SEGMENT_GAP_SEC 静音，
   双人（交叉音色）播报时每个切换点都有可感知停顿；
2. BGM 中断——BGM 叠加轨按段切片，每段切片各自编码并加淡入淡出，
   段边界处 BGM 断一下再回来。

修复后 continuous 模式（默认）：
- 主音频用 acrossfade 交叉淡化直连（build_crossfade_cmd）→ 无静音空档；
- BGM 用单条连续流铺满整期（build_bgm_continuous）→ 全程不断。

覆盖点：
- build_crossfade_cmd 的链式 filter 构造 / 单段退让 / 空输入报错；
- _resolve_crossfade_sec 对超短段的收敛（d 必须小于最短段时长，否则 ffmpeg 失败）；
- build_bgm_continuous 的循环铺满参数；
- normalize_gap_mode 的取值归一化（含新增 continuous 与非法值回退）。
"""
import pytest

from app.core.audio_modes import (
    DEFAULT_GAP_MODE,
    VALID_GAP_MODES,
    normalize_gap_mode,
)
from app.workflow.stitch import ffmpeg_wrapper
from app.workflow.stitch.concat import _resolve_crossfade_sec
from app.workflow.stitch.ffmpeg_wrapper import StitchError


# ---------- build_crossfade_cmd ----------

def test_crossfade_chain_built_for_three_segments():
    """3 段 → 链式 2 次 acrossfade，首次用 [0:a][1:a]，末次输出 [out]。"""
    cmd = ffmpeg_wrapper.build_crossfade_cmd(
        ["a.mp3", "b.mp3", "c.mp3"], 0.12, "out.mp3"
    )
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert fc.count("acrossfade") == 2
    assert fc.startswith("[0:a][1:a]acrossfade=")
    # 第二次的输入必须是第一次的输出标签
    assert "[a1][2:a]acrossfade=" in fc
    assert fc.endswith("[out]")
    # 三个输入都要以 -i 传入
    assert cmd.count("-i") == 3
    # 只重编码一次，输出参数统一
    assert cmd[cmd.index("-map") + 1] == "[out]"
    assert cmd[-1] == "out.mp3"


def test_crossfade_duration_in_filter_is_float_formatted():
    """交叉淡化时长必须按 3 位小数写入 filter，避免浮点串进 ffmpeg。"""
    cmd = ffmpeg_wrapper.build_crossfade_cmd(["a.mp3", "b.mp3"], 0.123456, "o.mp3")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "d=0.123" in fc
    assert "c1=tri" in fc and "c2=tri" in fc


def test_crossfade_single_segment_has_no_filter():
    """单段无需交叉淡化，直接重编码统一参数（不应出现 filter_complex）。"""
    cmd = ffmpeg_wrapper.build_crossfade_cmd(["a.mp3"], 0.12, "o.mp3")
    assert "-filter_complex" not in cmd
    assert cmd[-1] == "o.mp3"
    assert "-i" in cmd


def test_crossfade_empty_input_raises():
    """空输入必须显式报错，而不是产出静默的空音频。"""
    with pytest.raises(StitchError):
        ffmpeg_wrapper.build_crossfade_cmd([], 0.12, "o.mp3")


def test_crossfade_zero_duration_clamped():
    """d=0 会让 acrossfade 报错，必须收敛到正数下界。"""
    cmd = ffmpeg_wrapper.build_crossfade_cmd(["a.mp3", "b.mp3"], 0.0, "o.mp3")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "d=0.010" in fc


# ---------- _resolve_crossfade_sec ----------

def test_resolve_crossfade_uses_config_when_segments_long():
    """常规段长下直接用配置值（默认 0.12s）。"""
    assert _resolve_crossfade_sec([30.0, 40.0, 25.0]) == pytest.approx(0.12)


def test_resolve_crossfade_clamped_by_shortest_segment():
    """超短段（LLM 单句分段）时 d 必须收敛到 最短段/3，否则 ffmpeg 直接失败。"""
    # 最短 0.3s → 上限 0.1s
    assert _resolve_crossfade_sec([0.3, 30.0]) == pytest.approx(0.1)


def test_resolve_crossfade_empty_segments_returns_config():
    """无分段时回退配置值，不应抛 ZeroDivisionError。"""
    assert _resolve_crossfade_sec([]) == pytest.approx(0.12)


# ---------- build_bgm_continuous ----------

async def test_bgm_continuous_loops_single_stream(monkeypatch):
    """连续 BGM 必须只用一条 -stream_loop -1 流铺满总时长（不是按段多条切片）。"""
    cmds: list[list[str]] = []

    async def fake_run_ffmpeg(cmd):
        cmds.append(cmd)

    monkeypatch.setattr(ffmpeg_wrapper, "run_ffmpeg", fake_run_ffmpeg)
    await ffmpeg_wrapper.build_bgm_continuous("bgm.mp3", 123.456, 0.15, "o.mp3")

    # 只编码一次 BGM，且没有任何切片文件
    assert len(cmds) == 1
    cmd = cmds[0]
    assert "-stream_loop" in cmd and cmd[cmd.index("-stream_loop") + 1] == "-1"
    assert cmd[cmd.index("-t") + 1] == "123.456"
    assert cmd[cmd.index("-af") + 1] == "volume=0.15"
    assert not any("bgm_slice_" in a for a in cmd)
    assert cmd[-1] == "o.mp3"


def test_amix_cmd_uses_first_duration():
    """amix 必须以主音频长度为准（duration=first），否则叠加轨会拖长节目。"""
    cmd = ffmpeg_wrapper.build_amix_cmd("main.mp3", "ov.mp3", "o.mp3")
    assert "amix=inputs=2:duration=first" in cmd
    assert cmd[-1] == "o.mp3"


# ---------- normalize_gap_mode ----------

def test_gap_mode_accepts_continuous_and_legacy():
    for mode in ("continuous", "silence", "bridge"):
        assert normalize_gap_mode(mode) == mode


def test_gap_mode_is_case_and_space_insensitive():
    """前端手工输入 / DB 手改值可能是 Continuous，需容错归一化。"""
    assert normalize_gap_mode(" Continuous ") == "continuous"
    assert normalize_gap_mode("SILENCE") == "silence"


def test_gap_mode_falls_back_on_invalid_or_none():
    """非法值与 None 必须回退默认，绝不能因展示层脏值把整期拼接做失败。"""
    assert normalize_gap_mode(None) == DEFAULT_GAP_MODE
    assert normalize_gap_mode("") == DEFAULT_GAP_MODE
    assert normalize_gap_mode("nonsense") == DEFAULT_GAP_MODE


def test_default_gap_mode_is_continuous():
    """默认必须是连续衔接（T00382 的核心诉求：BGM 连续 + 切换丝滑）。"""
    assert DEFAULT_GAP_MODE == "continuous"
    assert VALID_GAP_MODES[0] == "continuous"
