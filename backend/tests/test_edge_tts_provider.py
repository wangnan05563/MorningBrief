import sys
import types

import pytest

from app.workflow.tts.base_provider import TTSServiceError
from app.workflow.tts.edge_client import EdgeTTSProvider


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
