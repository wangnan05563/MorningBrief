"""Piper TTS provider 单元测试（mock 掉 piper-tts 包，无需真实模型）。"""
import sys
import types
import wave

import pytest

from app.workflow.tts.base_provider import TTSError, TTSProviderError
from app.workflow.tts.piper_client import PiperProvider


class _FakeVoice:
    """模拟已加载的 PiperVoice：向 wave 文件写入一段合法 WAV。"""

    def synthesize(self, text, wav_file, length_scale=1.0, volume=0.5, noise_scale=0.667):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00" * 100)


class _FakePiperVoice:
    @classmethod
    def load(cls, model_path, config_path=None, use_cuda=False):
        return _FakeVoice()


@pytest.fixture
def fake_piper(monkeypatch):
    fake = types.SimpleNamespace(PiperVoice=_FakePiperVoice)
    monkeypatch.setitem(sys.modules, "piper", fake)
    yield


@pytest.mark.asyncio
async def test_piper_synthesize_returns_wav(fake_piper, tmp_path):
    (tmp_path / "zh_CN-huayan-medium.onnx").write_bytes(b"dummy")
    provider = PiperProvider(voice="zh_CN-huayan-medium", voice_dir=str(tmp_path))
    audio = await provider.synthesize("测试")
    assert audio[:4] == b"RIFF"
    assert len(audio) > 44


@pytest.mark.asyncio
async def test_piper_empty_text_raises(fake_piper, tmp_path):
    (tmp_path / "m.onnx").write_bytes(b"x")
    provider = PiperProvider(voice="m", voice_dir=str(tmp_path))
    with pytest.raises(TTSError):
        await provider.synthesize("")


@pytest.mark.asyncio
async def test_piper_missing_model_file_raises(fake_piper, tmp_path):
    """模型文件不存在时应抛出 TTSProviderError（不可重试）。"""
    provider = PiperProvider(voice="nope", voice_dir=str(tmp_path))
    with pytest.raises(TTSProviderError):
        await provider.synthesize("测试")


def test_piper_missing_dep_raises():
    saved = sys.modules.pop("piper", None)
    try:
        with pytest.raises(TTSProviderError):
            PiperProvider()
    finally:
        if saved is not None:
            sys.modules["piper"] = saved
