from app.workflow.tts.base_provider import TTSServiceError
from app.workflow.tts import synthesizer


def test_segment_failure_summary_is_bounded_and_redacts_credentials():
    summary = synthesizer._summarize_segment_failures(
        [
            (1, "合成", TTSServiceError("Edge-TTS 未收到音频数据")),
            (2, "后处理", RuntimeError("token=secret-value")),
        ]
    )

    assert "1（合成）: TTSServiceError: Edge-TTS 未收到音频数据" in summary
    assert "2（后处理）: RuntimeError: token=***" in summary
    assert "secret-value" not in summary
