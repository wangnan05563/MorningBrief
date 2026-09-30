"""BGM 叠加轨切片对齐回归测试（修复"双人音色切换时短暂 BGM 空白"）。

根因：build_bgm_overlay 原先用 TTS 上报的整数秒 duration 切片，与主音频
实际分段时长每段最多差 1s 且逐段累积，叠加轨相对主音频漂移——段边界
（音色切换点）处 BGM 空白后突然跳回。修复后：
1. concat 用 ffprobe 实测的浮点分段时长切片（此处验证切片命令带浮点 -t）；
2. 每个切片带淡入/淡出，消除段边界硬切断裂感。
"""
import pytest

from app.workflow.stitch import ffmpeg_wrapper


@pytest.fixture
def captured_cmds(monkeypatch, tmp_path):
    """拦截 run_ffmpeg 与 get_audio_duration_f，收集命令便于断言。"""
    cmds: list[list[str]] = []

    async def fake_run_ffmpeg(cmd):
        cmds.append(cmd)

    async def fake_bgm_len(_path):
        return 120.0  # BGM 长 120s，避免触发取模循环分支的边界

    monkeypatch.setattr(ffmpeg_wrapper, "run_ffmpeg", fake_run_ffmpeg)
    monkeypatch.setattr(ffmpeg_wrapper, "get_audio_duration_f", fake_bgm_len)
    return cmds


async def test_overlay_slices_use_float_durations(captured_cmds, tmp_path):
    """切片 -t 必须等于传入的浮点时长，而非取整值。"""
    durations = [12.345, 30.678, 45.0]
    out = str(tmp_path / "overlay.mp3")
    await ffmpeg_wrapper.build_bgm_overlay(
        "bgm.mp3", durations, "gap.mp3", 0.15, out, str(tmp_path),
    )

    slice_cmds = [c for c in captured_cmds if any("bgm_slice_" in a for a in c)]
    assert len(slice_cmds) == 3
    for cmd, dur in zip(slice_cmds, durations):
        t_idx = cmd.index("-t")
        assert float(cmd[t_idx + 1]) == pytest.approx(dur, abs=1e-3)


async def test_overlay_slice_has_fade_in_out(captured_cmds, tmp_path):
    """每个切片必须带 afade 淡入/淡出，避免段边界 BGM 硬切。"""
    await ffmpeg_wrapper.build_bgm_overlay(
        "bgm.mp3", [20.0, 20.0], "gap.mp3", 0.15,
        str(tmp_path / "o.mp3"), str(tmp_path),
    )
    slice_cmds = [c for c in captured_cmds if any("bgm_slice_" in a for a in c)]
    for cmd in slice_cmds:
        af = cmd[cmd.index("-af") + 1]
        assert "afade=t=in" in af, f"缺少淡入: {af}"
        assert "afade=t=out" in af, f"缺少淡出: {af}"


async def test_overlay_fade_clamped_for_short_segments(captured_cmds, tmp_path):
    """超短段（< 淡出时长）淡入/淡出需收缩到 dur/4，st 不为负。"""
    await ffmpeg_wrapper.build_bgm_overlay(
        "bgm.mp3", [0.5], "gap.mp3", 0.15,
        str(tmp_path / "o.mp3"), str(tmp_path),
    )
    slice_cmds = [c for c in captured_cmds if any("bgm_slice_" in a for a in c)]
    assert len(slice_cmds) == 1
    af = slice_cmds[0][slice_cmds[0].index("-af") + 1]
    # 淡入 0.08 → min(0.08, 0.125) = 0.08；淡出 min(0.3, 0.125) = 0.125
    assert "d=0.080" in af
    assert "st=0.375" in af  # 0.5 - 0.125


async def test_overlay_gap_between_slices(captured_cmds, tmp_path):
    """切片之间必须插入 gap（段间静音），最后一段后不插。"""
    await ffmpeg_wrapper.build_bgm_overlay(
        "bgm.mp3", [10.0, 10.0, 10.0], "gap.mp3", 0.15,
        str(tmp_path / "o.mp3"), str(tmp_path),
    )
    concat_cmd = [c for c in captured_cmds if any(".list.txt" in a for a in c)]
    assert len(concat_cmd) == 1
    list_file = next(a for a in concat_cmd[0] if a.endswith(".list.txt"))
    manifest = open(list_file, encoding="utf-8").read()  # NOSONAR
    lines = [ln for ln in manifest.splitlines() if ln.strip()]
    # [slice0, gap, slice1, gap, slice2] = 5 行
    assert len(lines) == 5
    assert lines[1].endswith("gap.mp3'")
    assert lines[3].endswith("gap.mp3'")
    assert "bgm_slice_0" in lines[0]
    assert "bgm_slice_2" in lines[4]


async def test_overlay_slices_read_from_prelooped_source(captured_cmds, tmp_path):
    """切片必须从「预循环实体源」读取，切片命令自身绝不能带 -stream_loop。

    实测两个会让 BGM 消失/错位的 ffmpeg 行为（均为切片命令直接带 -stream_loop 时）：
    - `-ss` 在 `-i` 前：输出侧 `-t` 被忽略，请求 2.5s 产出 4.496s → 叠加轨与主音频错位；
    - `-ss` 在 `-i` 后：seek 偏移超出剩余循环内容时产出整段静音（实测 -91dB）→
      BGM 在某个播报段整段消失。
    因此切片全部改为读取预循环源 + 输入侧 seek。
    """
    await ffmpeg_wrapper.build_bgm_overlay(
        "bgm.mp3", [10.0, 10.0], "gap.mp3", 0.15,
        str(tmp_path / "o.mp3"), str(tmp_path),
    )
    slice_cmds = [c for c in captured_cmds if any("bgm_slice_" in a for a in c)]
    assert len(slice_cmds) == 2
    for cmd in slice_cmds:
        assert "-stream_loop" not in cmd, f"切片命令不应带 -stream_loop: {cmd}"
        # 输入必须是预循环源，且 -ss 在 -i 之前（输入侧 seek，时长精确）
        assert any("bgm_looped_src" in a for a in cmd), cmd
        assert cmd.index("-ss") < cmd.index("-i")

    # 必须恰好有一条命令生成预循环源，且长度为「BGM 长 + 最长分段」留有余量
    loop_cmds = [c for c in captured_cmds if any("bgm_looped_src" in a for a in c)
                 and "-stream_loop" in c]
    assert len(loop_cmds) == 1
    loop_cmd = loop_cmds[0]
    assert loop_cmd[loop_cmd.index("-stream_loop") + 1] == "-1"
    # 夹具把 get_audio_duration_f 固定为 120.0（BGM 长），最长分段 10.0 → 需 ≥ 130
    assert float(loop_cmd[loop_cmd.index("-t") + 1]) >= 130.0
