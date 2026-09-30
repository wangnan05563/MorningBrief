import sys
import types

import pytest

from app.config import get_settings
from app.workflow.tts.base_provider import TTSServiceError, TTSError
from app.workflow.tts.edge_client import EdgeTTSProvider

settings = get_settings()


class NoAudioReceived(Exception):
    pass


class _NoAudioCommunicate:
    def __init__(self, *_args, **_kwargs):
        pass

    async def stream(self):
        raise NoAudioReceived("No audio was received")
        yield  # pragma: no cover


@pytest.mark.asyncio
async def test_empty_edge_response_is_retryable_service_error(monkeypatch):
    fake_edge_tts = types.SimpleNamespace(Communicate=_NoAudioCommunicate)
    monkeypatch.setitem(sys.modules, "edge_tts", fake_edge_tts)
    provider = EdgeTTSProvider(voice="zh-CN-XiaoxiaoNeural")

    with pytest.raises(TTSServiceError, match="未收到音频"):
        await provider.synthesize("诊断文本")


# ==========================================================================
# 语音合成正确性 / 音色(音色) / 语速(rate) 验证
# 全部基于 mock 引擎，确定性、离线、稳定通过（不依赖网络与真实 TTS 服务）。
# ==========================================================================
class _Capture:
    """记录最后一次 Communicate 调用的入参，用于断言音色/语速转发。"""

    last = None


class _FakeAudioCommunicate:
    """模拟正常返回音频分片的 Edge-TTS Communicate。"""

    def __init__(self, text, voice, **kwargs):
        _Capture.last = {"text": text, "voice": voice, "kwargs": kwargs}

    async def stream(self):
        # 故意分两段返回，验证 provider 能正确拼接多分片为连续音频
        yield {"type": "audio", "data": b"AUDIO_PART_1"}
        yield {"type": "audio", "data": b"AUDIO_PART_2"}


def _install_fake_edge_tts(monkeypatch):
    """将 edge_tts 模块替换为可捕获入参、可返回音频分片的假实现。"""
    _Capture.last = None
    fake = types.SimpleNamespace(Communicate=_FakeAudioCommunicate)
    monkeypatch.setitem(sys.modules, "edge_tts", fake)
    return fake


@pytest.mark.asyncio
async def test_synthesize_returns_concatenated_audio_output_correct(monkeypatch):
    """语音合成输出正确：多分片音频被完整拼接为连续字节流。"""
    _install_fake_edge_tts(monkeypatch)
    provider = EdgeTTSProvider(voice="zh-CN-XiaoxiaoNeural")
    audio = await provider.synthesize("这是一段用于验证输出正确性的文本")
    # 两段音频分片被正确拼成完整输出
    assert audio == b"AUDIO_PART_1" + b"AUDIO_PART_2"
    assert len(audio) > 0
    # 入参文本被正确透传（不丢字、不乱码）
    assert _Capture.last["text"] == "这是一段用于验证输出正确性的文本"


@pytest.mark.asyncio
async def test_synthesize_forwards_configured_voice_timbre(monkeypatch):
    """音色符合要求：显式配置的 voice（zh-CN-YunyangNeural）原样转发给 TTS 引擎。"""
    _install_fake_edge_tts(monkeypatch)
    provider = EdgeTTSProvider(voice="zh-CN-YunyangNeural")
    await provider.synthesize("音色验证文本")
    assert _Capture.last["voice"] == "zh-CN-YunyangNeural"


@pytest.mark.asyncio
async def test_synthesize_forwards_default_voice_when_unset(monkeypatch):
    """音色兜底：未显式指定 voice 时，使用全局配置音色（settings.EDGE_TTS_VOICE）。"""
    _install_fake_edge_tts(monkeypatch)
    provider = EdgeTTSProvider()  # 不传 voice，走默认音色
    await provider.synthesize("默认音色文本")
    assert _Capture.last["voice"] == settings.EDGE_TTS_VOICE


@pytest.mark.asyncio
async def test_synthesize_forwards_configured_rate_for_speed(monkeypatch):
    """语速符合要求：显式配置的 rate（+15%）原样转发给 TTS 引擎。"""
    _install_fake_edge_tts(monkeypatch)
    provider = EdgeTTSProvider(voice="zh-CN-XiaoxiaoNeural", rate="+15%")
    await provider.synthesize("语速验证文本")
    assert _Capture.last["kwargs"].get("rate") == "+15%"


@pytest.mark.asyncio
async def test_synthesize_omits_rate_when_unset_default_speed(monkeypatch):
    """未配置语速时不下发 rate，保留引擎默认语速（不污染默认播报速度）。"""
    _install_fake_edge_tts(monkeypatch)
    # rate 传空字符串 == 不调节语速（与 settings.EDGE_TTS_RATE 默认值对齐）
    provider = EdgeTTSProvider(voice="zh-CN-XiaoxiaoNeural", rate="")
    await provider.synthesize("默认语速文本")
    assert "rate" not in _Capture.last["kwargs"]


@pytest.mark.asyncio
async def test_synthesize_empty_text_raises_tts_error(monkeypatch):
    """健壮性：空文本/纯空白文本应抛 TTSError，而非把脏数据喂给引擎。"""
    _install_fake_edge_tts(monkeypatch)
    provider = EdgeTTSProvider(voice="zh-CN-XiaoxiaoNeural")
    with pytest.raises(TTSError):
        await provider.synthesize("   ")
