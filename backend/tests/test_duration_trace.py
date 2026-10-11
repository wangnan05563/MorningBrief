"""时长改造留痕链路测试（T02028）。

背景（T01925）：拼接阶段实测的成品时长随 context 返回，但 `_create_review` 只透传 URL，
实测值被丢弃，发布只能落稿件字数估算值（`estimated_duration`）。T01925 用「发布时探测外链」
绕过，本单把实测值在链路里正规落地，并要求拼接阶段的「凑了多少秒/压缩前多少秒」可见。

覆盖点：
- `_create_review` 把 context 的 duration / original_duration / supplement_sec 落 review 行
- 老 context（无这些键）时列为 NULL，不抛错
- 发布优先取 review 实测值，**不再发起网络探测**；老 review 才回退探测
- episode 快照 supplement_sec / original_duration_sec（管理端据此标记「凑时」）
- 加列迁移幂等且在存量数据上安全
"""
from datetime import date

import pytest
from sqlalchemy import select

from app.models import Episode, Review, Script
from app.services.content_service import ContentService


class _SessionCtx:
    """把测试用的 db_session 包成 `async with AsyncSessionLocal()` 的形状。"""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


async def _seed_script(db) -> Script:
    script = Script(
        workflow_id="wf-trace", episode_date=date.today(), full_text="稿件全文",
        segments=[{"seq": 1, "content": "段"}], estimated_duration=86,
        categories=None, status="approved",
    )
    db.add(script)
    await db.commit()
    await db.refresh(script)
    return script


# ---------- _create_review：实测时长不再被丢弃 ----------

@pytest.mark.asyncio
async def test_create_review_persists_duration_trace(db_session, monkeypatch):
    """拼接实测时长与改造前后差值随 review 落库（T01925 断点就在这一步）。"""
    from app.services import workflow_scheduler as sched_mod

    script = await _seed_script(db_session)
    monkeypatch.setattr(
        sched_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))

    scheduler = sched_mod.WorkflowScheduler()
    context = {
        "workflow_id": "wf-trace",
        "episode_date": date.today(),
        "script_id": script.id,
        "final_audio_url": "https://cos.example/ep.mp3",
        "hls_url": "https://cos.example/ep.m3u8",
        # concat() 返回的三个时长口径：成品实测 / 改造前实测 / 补入秒数
        "duration": 482,
        "original_duration": 282,
        "supplement_sec": 200,
    }
    result = await scheduler._create_review(context)

    review = (await db_session.execute(
        select(Review).where(Review.id == result["review_id"])
    )).scalar_one()
    assert review.measured_duration_sec == 482
    assert review.original_duration_sec == 282
    assert review.supplement_sec == 200


@pytest.mark.asyncio
async def test_create_review_without_duration_keys_is_null(db_session, monkeypatch):
    """老 context 不带时长键时列为 NULL（历史行为，发布仍需回退探测）。"""
    from app.services import workflow_scheduler as sched_mod

    script = await _seed_script(db_session)
    monkeypatch.setattr(
        sched_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))

    scheduler = sched_mod.WorkflowScheduler()
    result = await scheduler._create_review({
        "workflow_id": "wf-trace",
        "episode_date": date.today(),
        "script_id": script.id,
        "final_audio_url": "https://cos.example/old.mp3",
    })

    review = (await db_session.execute(
        select(Review).where(Review.id == result["review_id"])
    )).scalar_one()
    assert review.measured_duration_sec is None
    assert review.supplement_sec is None


# ---------- publish：实测值优先，且不再探测 ----------

@pytest.mark.asyncio
async def test_publish_prefers_review_duration_without_probe(
    db_session, monkeypatch
):
    """review 有实测时长时，发布不得发起网络探测，且 episode 快照改造留痕。"""
    import app.workflow.stitch.ffmpeg_wrapper as fw

    script = await _seed_script(db_session)
    review = Review(
        workflow_id="wf-trace", episode_date=date.today(), script_id=script.id,
        audio_url="https://cos.example/ep.mp3",
        measured_duration_sec=482, original_duration_sec=282, supplement_sec=200,
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)

    probe_calls = []

    async def _no_probe(path: str) -> float:
        probe_calls.append(path)
        return 999.0

    monkeypatch.setattr(fw, "get_audio_duration_f", _no_probe)

    svc = ContentService(db_session)
    episode_id = await svc.publish_episode("wf-trace", review.id)
    episode = (await db_session.execute(
        select(Episode).where(Episode.id == episode_id)
    )).scalar_one()

    assert probe_calls == [], "review 已有实测时长，不该再探测外链"
    assert episode.duration == 482  # 既不是估算值 86，也不是探测值 999
    assert episode.supplement_sec == 200
    assert episode.original_duration_sec == 282


@pytest.mark.asyncio
async def test_publish_falls_back_to_probe_for_legacy_review(
    db_session, monkeypatch
):
    """老 review（实测列为 NULL）仍走 T01925 的探测兜底，行为不回退。"""
    import app.workflow.stitch.ffmpeg_wrapper as fw

    script = await _seed_script(db_session)
    review = Review(
        workflow_id="wf-trace", episode_date=date.today(), script_id=script.id,
        audio_url="https://cos.example/legacy.mp3",
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)

    async def _fake_probe(path: str) -> float:
        assert path == review.audio_url
        return 597.055

    monkeypatch.setattr(fw, "get_audio_duration_f", _fake_probe)

    svc = ContentService(db_session)
    episode_id = await svc.publish_episode("wf-trace", review.id)
    episode = (await db_session.execute(
        select(Episode).where(Episode.id == episode_id)
    )).scalar_one()

    assert episode.duration == 597
    assert episode.supplement_sec is None


# ---------- 迁移：幂等 + 存量数据安全 ----------

def test_duration_trace_migration_is_idempotent(tmp_path, monkeypatch):
    """缺列时补列、重复执行不报错，且不改动存量行（列可空、默认 NULL）。"""
    import sqlite3

    from app import paths

    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE review (id INTEGER PRIMARY KEY, audio_url TEXT)")
    conn.execute("CREATE TABLE episode (id INTEGER PRIMARY KEY, duration INTEGER)")
    conn.execute("INSERT INTO review (id, audio_url) VALUES (1, 'https://cos/a.mp3')")
    conn.execute("INSERT INTO episode (id, duration) VALUES (1, 482)")
    conn.commit()
    conn.close()

    monkeypatch.setattr(paths, "resolve_db_path", lambda: db_file)

    from app.main import _migrate_duration_trace_columns

    for _ in range(2):  # 跑两次验证幂等
        import asyncio
        asyncio.run(_migrate_duration_trace_columns())

    conn = sqlite3.connect(db_file)
    review_cols = {r[1] for r in conn.execute("PRAGMA table_info(review)")}
    episode_cols = {r[1] for r in conn.execute("PRAGMA table_info(episode)")}
    rows = conn.execute("SELECT id, audio_url, measured_duration_sec FROM review").fetchall()
    legacy = conn.execute("SELECT id, duration, supplement_sec FROM episode").fetchall()
    conn.close()

    assert {
        "measured_duration_sec", "original_duration_sec", "supplement_sec",
    } <= review_cols
    assert {"supplement_sec", "original_duration_sec"} <= episode_cols
    # 存量行保留，新列为 NULL（不回填历史数据）
    assert rows == [(1, "https://cos/a.mp3", None)]
    assert legacy == [(1, 482, None)]
