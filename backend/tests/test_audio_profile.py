"""音频档位套餐（T01871：码率 + 采样率成组配置）回归测试。

为什么要成组：MP3 的音质由「码率 × 采样率」共同决定。T01845 实测成品内容上限约
10kHz（TTS 源 24kHz，旧链路把它上采样到 44.1k 再编码），同码率下 64k@32k 的 segSNR
24.77dB 优于 64k@44.1k 的 23.86dB；反过来只抬码率不降采样率，预算全花在空频带上，
PCM 中间态还按 88KB/s 涨。所以两处都不能各写各的，收敛到 app/core/audio_profile.py。

覆盖点：三档解析、非法档位回退、显式覆盖标记、PCM 体积口径、拼接与 TTS 后处理命令
跟随档位（不再出现硬编码 44100 / ALIYUN_TTS_SAMPLE_RATE）、管理端只读档位接口。
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.core.audio_profile import (
    AUDIO_PROFILES,
    DEFAULT_AUDIO_PROFILE,
    normalize_profile,
    resolve_encoding,
)
from app.workflow.stitch import ffmpeg_wrapper as fw
from app.workflow.tts import audio_postprocess as pp


def _settings(profile, bitrate="", sample_rate=0):
    return SimpleNamespace(
        AUDIO_PROFILE=profile, AUDIO_BITRATE=bitrate, AUDIO_SAMPLE_RATE=sample_rate
    )


# ---- 档位解析 ----

@pytest.mark.parametrize(
    "profile,bitrate,sample_rate",
    [("quality", "96k", 44100), ("standard", "64k", 32000), ("lean", "48k", 32000)],
)
def test_profile_bundles_bitrate_with_sample_rate(profile, bitrate, sample_rate):
    enc = resolve_encoding(_settings(profile))
    assert (enc.bitrate, enc.sample_rate) == (bitrate, sample_rate)
    assert enc.overridden is False


@pytest.mark.parametrize("raw", ["", None, "24k", "QUALIY", "opus"])
def test_illegal_profile_falls_back_to_standard(raw):
    """档位名写错不该让整期节目失败，也不该滑到未实测的 24k（MPEG-2 LSF 兼容风险）。"""
    enc = resolve_encoding(_settings(raw))
    assert enc.profile == DEFAULT_AUDIO_PROFILE
    assert normalize_profile(raw) == DEFAULT_AUDIO_PROFILE


def test_explicit_overrides_win_and_are_flagged():
    enc = resolve_encoding(_settings("standard", bitrate="128k", sample_rate=44100))
    assert (enc.bitrate, enc.sample_rate) == ("128k", 44100)
    assert enc.overridden is True, "管理端要能看出实际参数与档位名不一致"


def test_pcm_density_uses_decimal_kb_per_sec():
    """与仓库既有口径一致：44100 单声道 16bit ≈ 88KB/s，standard 档降到 64KB/s。"""
    assert resolve_encoding(_settings("quality")).pcm_kb_per_sec == 88
    assert resolve_encoding(_settings("standard")).pcm_kb_per_sec == 64


def test_profile_table_shape():
    assert list(AUDIO_PROFILES) == ["quality", "standard", "lean"]
    for val in AUDIO_PROFILES.values():
        assert val["sample_rate"] in (32000, 44100), "只取 MPEG-1 Layer III 合法采样率"


# ---- 链路消费侧 ----

def test_settings_defaults_are_standard():
    """仓库默认档 = standard（64k@32k），且两个覆盖项默认留空表示跟随档位。"""
    from app.config import Settings

    defaults = {
        name: field.default
        for name, field in Settings.model_fields.items()
        if name in ("AUDIO_PROFILE", "AUDIO_BITRATE", "AUDIO_SAMPLE_RATE")
    }
    assert defaults == {
        "AUDIO_PROFILE": "standard",
        "AUDIO_BITRATE": "",
        "AUDIO_SAMPLE_RATE": 0,
    }


def _patch_profile(monkeypatch, profile, bitrate=None, sample_rate=None):
    """改 Settings 单例属性而不是 setenv + cache_clear（同 test_app_role_gating 口径）：
    全仓多个模块 import 期就持有同一实例，清缓存会让别的测试读到真实配置。"""
    s = get_settings()
    monkeypatch.setattr(s, "AUDIO_PROFILE", profile, raising=False)
    if bitrate is not None:
        monkeypatch.setattr(s, "AUDIO_BITRATE", bitrate, raising=False)
    if sample_rate is not None:
        monkeypatch.setattr(s, "AUDIO_SAMPLE_RATE", sample_rate, raising=False)


@pytest.mark.parametrize(
    "profile,sample_rate,bitrate",
    [("quality", "44100", "96k"), ("standard", "32000", "64k"), ("lean", "32000", "48k")],
)
def test_stitch_args_follow_profile(monkeypatch, profile, sample_rate, bitrate):
    _patch_profile(monkeypatch, profile, bitrate="", sample_rate=0)
    pcm = fw._pcm_args()
    enc = fw._encode_args()
    assert pcm[pcm.index("-ar") + 1] == sample_rate
    assert enc[enc.index("-ar") + 1] == sample_rate
    assert enc[enc.index("-b:a") + 1] == bitrate


def test_stitch_overrides_beat_profile(monkeypatch):
    _patch_profile(monkeypatch, "standard", bitrate="128k", sample_rate=44100)
    assert fw._audio_bitrate() == "128k"
    assert fw._stitch_sample_rate() == "44100"


def test_hls_cmd_follows_profile(monkeypatch):
    _patch_profile(monkeypatch, "quality", sample_rate=0)
    cmd, _ = fw.build_hls_cmd("timeline.wav", "hls")
    assert cmd[cmd.index("-ar") + 1] == "44100"


@pytest.mark.asyncio
async def test_postprocess_uses_profile_not_provider_sample_rate(monkeypatch):
    """后处理不再跟随 ALIYUN_TTS_SAMPLE_RATE：provider 请求 44.1k 也应降到档位采样率。"""
    cmds = []

    def fake_run_cmd(cmd):
        cmds.append(cmd)
        Path(cmd[-1]).write_bytes(b"x")
        return 0, "", ""

    _patch_profile(monkeypatch, "lean", bitrate="", sample_rate=0)
    monkeypatch.setattr(pp, "_run_cmd", fake_run_cmd)
    monkeypatch.setattr(get_settings(), "ALIYUN_TTS_SAMPLE_RATE", 44100, raising=False)

    await pp.postprocess_segment(b"provider-mp3-bytes")

    cmd = cmds[0]
    assert cmd[cmd.index("-ar") + 1] == "32000"
    assert cmd[cmd.index("-b:a") + 1] == "48k"


# ---- 管理端只读展示 ----

def test_audio_profile_endpoint(client, admin_token):
    resp = client.get(
        "/admin/api/v1/ai/audio-profile",
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["bitrate"] == AUDIO_PROFILES[data["profile"]]["bitrate"] or data["overridden"]
    assert data["sample_rate"] == AUDIO_PROFILES[data["profile"]]["sample_rate"] or data["overridden"]
    assert [p["profile"] for p in data["profiles"]] == list(AUDIO_PROFILES)


def test_audio_profile_endpoint_requires_admin(client):
    assert client.get("/admin/api/v1/ai/audio-profile").status_code in (401, 403)


def test_audio_profile_is_read_only(client):
    """档位没有写接口：改档要走 .env + 真机兼容/人工试听收口（T01871 任务项 3、4）。"""
    from app.main import app

    for route in app.routes:
        if getattr(route, "path", "") == "/admin/api/v1/ai/audio-profile":
            assert set(route.methods) == {"GET"}
