"""拼接链路「中间态无损」回归测试（T01870，消除代际损失）。

根因（T01845 实测）：旧实现里 loudnorm→silenceremove→段间拼接→BGM 混音→
广告插入→最终 concat 每一步都用 libmp3lame 重编一次，同一段语音最多被有损编码
4~5 代；同码率下 1 代→4 代 segSNR 掉 4.6dB（9-12kHz 频带丢 2.23dB），
而体积一个字节没省——纯亏。

修复口径：
- 素材入口统一解码为 16bit PCM（`to_pcm`），中间态全部 PCM（`_pcm_args`）；
- 有损编码只在最终交付物发生一次（`_encode_args`），HLS 从 PCM 编 AAC；
- TTS 后处理 loudnorm + silenceremove 合并为单次编码（`postprocess_segment`）。

覆盖点：中间命令构造器只出 PCM、不含 libmp3lame；成品编码参数单点定义；
后处理单次调用且滤镜顺序不变；素材入口解码后清理原始有损文件。
"""
from pathlib import Path

import pytest

from app.workflow.stitch import concat as concat_mod
from app.workflow.stitch import ffmpeg_wrapper as fw
from app.workflow.tts import audio_postprocess as pp

PCM_BUILDERS = [
    ("build_concat_cmd", lambda: fw.build_concat_cmd(["a.wav", "b.wav"], "main.wav")),
    ("build_crossfade_cmd",
     lambda: fw.build_crossfade_cmd(["a.wav", "b.wav"], 0.12, "main.wav")),
    ("build_crossfade_cmd_single",
     lambda: fw.build_crossfade_cmd(["a.wav"], 0.12, "main.wav")),
    ("build_mid_ad_cmd", lambda: fw.build_mid_ad_cmd("main.wav", "ad.wav", "out.wav")),
    ("build_full_concat_cmd",
     lambda: fw.build_full_concat_cmd(["a.wav", "b.wav"], "timeline.wav")),
    ("build_amix_cmd", lambda: fw.build_amix_cmd("main.wav", "overlay.wav", "out.wav")),
]


@pytest.mark.parametrize("name,builder", PCM_BUILDERS, ids=[c[0] for c in PCM_BUILDERS])
def test_intermediate_builders_emit_pcm_only(name, builder):
    cmd = builder()
    assert "pcm_s16le" in cmd, f"{name} 中间态应为无损 PCM"
    assert "libmp3lame" not in cmd, f"{name} 中间态不应再做有损编码"
    assert cmd[cmd.index("-ar") + 1] == "44100"
    assert cmd[cmd.index("-ac") + 1] == "1"


def test_encode_args_is_the_single_lossy_definition():
    args = fw._encode_args()
    assert args[:2] == ["-c:a", "libmp3lame"]
    assert fw._audio_bitrate() in args


def test_hls_encodes_aac_from_pcm_timeline():
    cmd, playlist = fw.build_hls_cmd("timeline.wav", "hls")
    assert "aac" in cmd
    assert "libmp3lame" not in cmd
    assert cmd[cmd.index("-i") + 1] == "timeline.wav"
    assert playlist.endswith("playlist.m3u8")


@pytest.mark.asyncio
async def test_to_pcm_outputs_pcm(monkeypatch):
    captured = []

    async def fake_run(cmd):
        captured.append(cmd)

    monkeypatch.setattr(fw, "run_ffmpeg", fake_run)
    await fw.to_pcm("a.mp3", "a.wav")
    assert captured[0][-1] == "a.wav"
    assert "pcm_s16le" in captured[0]


@pytest.mark.asyncio
async def test_postprocess_segment_runs_encoder_once(monkeypatch):
    """loudnorm 与 silenceremove 串在同一条 -af 链上，整段只编一次。"""
    cmds = []

    def fake_run_cmd(cmd):
        Path(cmd[-1]).write_bytes(b"fake-audio")
        cmds.append(cmd)
        return 0, "", ""

    monkeypatch.setattr(pp, "_run_cmd", fake_run_cmd)
    result = await pp.postprocess_segment(b"provider-mp3-bytes")

    assert len(cmds) == 1, "后处理应只有一次编码调用（旧实现是两次）"
    af = cmds[0][cmds[0].index("-af") + 1]
    assert af.index("loudnorm") < af.index("silenceremove"), \
        "先去静音会让 loudnorm 漏统计被切掉的段落，整体音量偏高"
    assert result == b"fake-audio"


def test_two_step_postprocess_helpers_removed():
    """拆分实现已删除，避免再被串成两代编码。"""
    assert not hasattr(pp, "normalize_loudness")
    assert not hasattr(pp, "trim_silence")


@pytest.mark.asyncio
async def test_to_pcm_asset_decodes_and_removes_source(tmp_path, monkeypatch):
    async def fake_download(url, dest):
        Path(dest).write_bytes(b"lossy-source")

    async def fake_to_pcm(input_path, output_path):
        Path(output_path).write_bytes(b"pcm")

    monkeypatch.setattr(concat_mod, "download_file", fake_download)
    monkeypatch.setattr(concat_mod, "to_pcm", fake_to_pcm)

    out = await concat_mod._to_pcm_asset("/audio/x.mp3", tmp_path, "head_ad")

    assert out == str(tmp_path / "head_ad.wav")
    assert Path(out).read_bytes() == b"pcm"
    assert not (tmp_path / "head_ad.src.mp3").exists(), "原始有损文件应尽早回收"


@pytest.mark.asyncio
async def test_encode_timeline_uses_encode_args(monkeypatch):
    captured = []

    async def fake_run(cmd):
        captured.append(cmd)

    monkeypatch.setattr(concat_mod, "run_ffmpeg", fake_run)
    await concat_mod._encode_timeline("timeline.wav", "final.mp3")

    cmd = captured[0]
    assert cmd[-1] == "final.mp3"
    assert "libmp3lame" in cmd and "pcm_s16le" not in cmd
