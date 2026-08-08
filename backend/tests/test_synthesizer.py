from datetime import date

from sqlalchemy import select

from app.workflow.tts.base_provider import TTSServiceError
from app.workflow.tts import synthesizer
from app.models import Script


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


async def test_persist_segment_audio_urls_writes_back_by_seq(db_session):
    """回写：按 seg_seq 把 COS audio_url 写入 script.segments 对应段。"""
    script = Script(
        workflow_id="wf-1",
        episode_date=date(2026, 7, 8),
        full_text="测试",
        segments=[
            {"seq": 1, "title": "段1", "content": "a"},
            {"seq": 2, "title": "段2", "content": "b"},
        ],
    )
    db_session.add(script)
    await db_session.commit()
    await db_session.refresh(script)

    audio_segments = [
        {"seg_seq": 1, "audio_url": "https://cos/tts/wf-1/1.mp3", "duration": 10},
        {"seg_seq": 2, "audio_url": "https://cos/tts/wf-1/2.mp3", "duration": 20},
    ]
    await synthesizer._persist_segment_audio_urls(
        script.id, audio_segments, "wf-1", session=db_session
    )

    # 重新查询确认已持久化
    reloaded = (await db_session.execute(
        select(Script).where(Script.id == script.id)
    )).scalar_one()
    segs = reloaded.segments
    assert segs[0]["audio_url"] == "https://cos/tts/wf-1/1.mp3"
    assert segs[1]["audio_url"] == "https://cos/tts/wf-1/2.mp3"


async def test_persist_segment_audio_urls_ignores_unmatched_seq(db_session):
    """回写：audio_segments 中 seq 在 segments 不存在时，不报错也不污染。"""
    script = Script(
        workflow_id="wf-2",
        episode_date=date(2026, 7, 8),
        full_text="测试",
        segments=[{"seq": 1, "title": "段1", "content": "a"}],
    )
    db_session.add(script)
    await db_session.commit()
    await db_session.refresh(script)

    # seq=99 不存在，应被忽略；不抛异常
    await synthesizer._persist_segment_audio_urls(
        script.id,
        [{"seg_seq": 99, "audio_url": "https://cos/x.mp3", "duration": 1}],
        "wf-2",
        session=db_session,
    )
    reloaded = (await db_session.execute(
        select(Script).where(Script.id == script.id)
    )).scalar_one()
    assert "audio_url" not in reloaded.segments[0]


async def test_persist_segment_audio_urls_empty_noop(db_session):
    """回写：audio_segments 为空时直接返回，不查询、不报错。"""
    script = Script(
        workflow_id="wf-3",
        episode_date=date(2026, 7, 8),
        full_text="测试",
        segments=[{"seq": 1, "content": "a"}],
    )
    db_session.add(script)
    await db_session.commit()
    await db_session.refresh(script)

    # 不应抛异常
    await synthesizer._persist_segment_audio_urls(
        script.id, [], "wf-3", session=db_session
    )

