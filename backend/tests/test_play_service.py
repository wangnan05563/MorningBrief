"""PlayService.report_progress 单元测试。

覆盖本次迭代两项修复的核心逻辑：
- 任务5：播放计数器（position >= PLAY_COUNT_THRESHOLD_SEC 时 upsert PlayLog，每用户每节目去重一条）
- 任务7：累计收听时长（listened_seconds 增量累加到 User.total_listen_duration）

COS 写入在测试环境（未配置）会静默降级，report_progress 内 try/except 兜底，
不阻断 SQLite 主路径，故无需 mock cos_client。
"""
from datetime import date

import pytest
from sqlalchemy import select

from app.models import Episode, EpisodeStatus, PlayLog, User
from app.services.play_service import PlayService
from app.services.play_write_buffer import play_write_buffer


async def _seed_user_episode(db_session, user_openid="wx-play-001", ep_title="测试节目"):
    """构造一对 User + 已发布 Episode，返回 (user, episode)。"""
    user = User(openid=user_openid, nickname="play-tester")
    db_session.add(user)
    episode = Episode(
        title=ep_title,
        date=date.today(),
        duration=600,
        audio_url="http://example.com/test.mp3",
        status=EpisodeStatus.published.value,
    )
    db_session.add(episode)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(episode)
    return user, episode


@pytest.mark.asyncio
async def test_report_progress_below_threshold_no_playlog(db_session):
    """任务5：position 未达阈值（<30s）时不插入 PlayLog，play_count 不 +1。"""
    user, episode = await _seed_user_episode(db_session)
    svc = PlayService(db_session)
    # position=10s 未达 30s 阈值
    await svc.report_progress(
        user_id=user.id,
        episode_id=episode.id,
        position=10,
        duration=600,
        completed=False,
        listened_seconds=10,
    )

    # PlayLog 不应有记录
    await play_write_buffer.flush(session=db_session)
    logs = (await db_session.execute(
        select(PlayLog).where(PlayLog.user_id == user.id)
    )).scalars().all()
    assert len(logs) == 0
    # total_listen_count 也不应增加
    await db_session.refresh(user)
    assert (user.total_listen_count or 0) == 0


@pytest.mark.asyncio
async def test_report_progress_above_threshold_inserts_playlog(db_session):
    """任务5：position 首次 >=30s 时插入 PlayLog，total_listen_count +1。"""
    user, episode = await _seed_user_episode(db_session)
    svc = PlayService(db_session)
    await svc.report_progress(
        user_id=user.id,
        episode_id=episode.id,
        position=35,
        duration=600,
        completed=False,
        listened_seconds=0,
    )

    await play_write_buffer.flush(session=db_session)
    logs = (await db_session.execute(
        select(PlayLog).where(PlayLog.user_id == user.id, PlayLog.episode_id == episode.id)
    )).scalars().all()
    assert len(logs) == 1
    assert logs[0].position == 35
    await db_session.refresh(user)
    assert user.total_listen_count == 1


@pytest.mark.asyncio
async def test_report_progress_dedup_no_double_count(db_session):
    """任务5：同一用户同一节目重复上报 position>=30 不重复计数。"""
    user, episode = await _seed_user_episode(db_session)
    svc = PlayService(db_session)
    # 第一次：35s，插入 PlayLog
    await svc.report_progress(user.id, episode.id, 35, 600, False, 0)
    # 第二次：60s，已存在记录，不应再插入也不应再 +1
    await svc.report_progress(user.id, episode.id, 60, 600, False, 0)
    await play_write_buffer.flush(session=db_session)

    logs = (await db_session.execute(
        select(PlayLog).where(PlayLog.user_id == user.id, PlayLog.episode_id == episode.id)
    )).scalars().all()
    assert len(logs) == 1
    await db_session.refresh(user)
    assert user.total_listen_count == 1


@pytest.mark.asyncio
async def test_report_progress_completed_updates_flag_no_recount(db_session):
    """任务5：已记录后再完播，仅更新 completed 标志，不重复计数。"""
    user, episode = await _seed_user_episode(db_session)
    svc = PlayService(db_session)
    # 先听到 35s（未完播）
    await svc.report_progress(user.id, episode.id, 35, 600, False, 0)
    # 再完播
    await svc.report_progress(user.id, episode.id, 600, 600, True, 0)
    await play_write_buffer.flush(session=db_session)

    logs = (await db_session.execute(
        select(PlayLog).where(PlayLog.user_id == user.id, PlayLog.episode_id == episode.id)
    )).scalars().all()
    assert len(logs) == 1
    assert logs[0].completed == 1
    assert logs[0].position == 600
    await db_session.refresh(user)
    # 完播不重复计数
    assert user.total_listen_count == 1


@pytest.mark.asyncio
async def test_report_progress_listened_seconds_accumulates(db_session):
    """任务7：listened_seconds 增量累加到 User.total_listen_duration。"""
    user, episode = await _seed_user_episode(db_session)
    svc = PlayService(db_session)
    # 第一次上报增量 25s
    await svc.report_progress(user.id, episode.id, 25, 600, False, listened_seconds=25)
    # 第二次上报增量 40s
    await svc.report_progress(user.id, episode.id, 65, 600, False, listened_seconds=40)
    await play_write_buffer.flush(session=db_session)

    await db_session.refresh(user)
    assert user.total_listen_duration == 65


@pytest.mark.asyncio
async def test_report_progress_zero_listened_seconds_no_accumulate(db_session):
    """任务7：listened_seconds=0 时不累加（用户 seek 后退或未前进场景）。"""
    user, episode = await _seed_user_episode(db_session)
    svc = PlayService(db_session)
    await svc.report_progress(user.id, episode.id, 35, 600, False, listened_seconds=0)
    await play_write_buffer.flush(session=db_session)

    await db_session.refresh(user)
    assert (user.total_listen_duration or 0) == 0


@pytest.mark.asyncio
async def test_report_progress_different_episodes_count_separately(db_session):
    """任务5：同一用户对不同节目分别达阈值，total_listen_count 各 +1 累加。"""
    user, ep1 = await _seed_user_episode(db_session, ep_title="测试节目A")
    # 第二个节目复用同一 user
    ep2 = Episode(
        title="测试节目B",
        date=date.today(),
        duration=600,
        audio_url="http://example.com/test2.mp3",
        status=EpisodeStatus.published.value,
    )
    db_session.add(ep2)
    await db_session.commit()
    await db_session.refresh(ep2)

    svc = PlayService(db_session)
    await svc.report_progress(user.id, ep1.id, 40, 600, False, 0)
    await svc.report_progress(user.id, ep2.id, 50, 600, False, 0)
    await play_write_buffer.flush(session=db_session)

    await db_session.refresh(user)
    # 两个节目各计一次
    assert user.total_listen_count == 2
    logs = (await db_session.execute(
        select(PlayLog).where(PlayLog.user_id == user.id)
    )).scalars().all()
    assert len(logs) == 2
