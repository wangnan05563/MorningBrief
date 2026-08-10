"""Kokoro TTS provider 单元测试（mock 掉 kokoro 包，无需真实模型）。"""
import sys
import types

import numpy as np
import pytest

from app.workflow.tts.base_provider import TTSError, TTSProviderError
from app.workflow.tts.kokoro_client import KokoroProvider


class _FakeKPipeline:
    """模拟 kokoro.KPipeline：按 (graphemes, phonemes, audio) 生成单段音频。"""

    # 类级调用记录（每个实例 append 到此列表，供测试断言）
    calls: list[tuple] = []

    def __init__(self, lang_code: str = "z"):
        self.lang_code = lang_code

    def __call__(self, text, voice=None, speed: float = 1.0):
        _FakeKPipeline.calls.append((text, voice, speed))
        # 约 10ms @24kHz 的静音缓冲，足以生成合法 WAV
        audio = np.zeros(240, dtype=np.float32)
        yield ("g", "p", audio)


@pytest.fixture
def fake_kokoro(monkeypatch):
    """注入假的 kokoro 模块，使 KokoroProvider 可实例化。"""
    fake = types.SimpleNamespace(KPipeline=_FakeKPipeline)
    monkeypatch.setitem(sys.modules, "kokoro", fake)
    _FakeKPipeline.calls.clear()
    yield _FakeKPipeline


@pytest.mark.asyncio
async def test_kokoro_synthesize_returns_wav(fake_kokoro):
    provider = KokoroProvider(lang="z", voice="zf_xiaoxiao", speed=1.0)
    audio = await provider.synthesize("测试")
    assert audio[:4] == b"RIFF"
    assert len(audio) > 44


@pytest.mark.asyncio
async def test_kokoro_empty_text_raises(fake_kokoro):
    provider = KokoroProvider()
    with pytest.raises(TTSError):
        await provider.synthesize("")


@pytest.mark.asyncio
async def test_kokoro_passes_speed_to_pipeline(fake_kokoro):
    provider = KokoroProvider(lang="z", voice="zf_xiaoxiao", speed=1.5)
    await provider.synthesize("你好")
    # 验证底层 pipeline 收到正确的语速参数
    assert fake_kokoro.calls[-1][2] == 1.5


def test_kokoro_missing_dep_raises():
    """未安装 kokoro 时构造应抛出 TTSProviderError（不可重试）。"""
    saved = sys.modules.pop("kokoro", None)
    try:
        with pytest.raises(TTSProviderError):
            KokoroProvider()
    finally:
        if saved is not None:
            sys.modules["kokoro"] = saved
