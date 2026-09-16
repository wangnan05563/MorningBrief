"""播放量端到端可见性测试（T00637）。

背景：用户报「音频播放量每次重新进入应用，播放量都会变成 0」。
排查发现实例库中 `play_progress` 有 14 条（含 position=593/647 的完成播放），
而 `play_log` 仅 2 条 —— 远超阈值（30s）的播放却没有计数记录。

本测试锁定**用户可见契约**：
1. 上报进度（position ≥ 阈值）→ 列表接口 play_count 应可见 +1；
2. 该值必须**持久化**：清空列表缓存（模拟重新进入应用）后再次查询，值不变（不得归零）；
3. 同一用户重复播放同一节目不重复计数（每用户每节目一条）。
"""
from datetime import date

import pytest
from sqlalchemy import select

from app.models import Episode, EpisodeStatus, PlayLog, User
from app.services.play_write_buffer import play_write_buffer


async def _seed(db_session):
    """构造 C 端用户（id=1，与 user_token 对应）+ 已发布节目。"""
    existing = (await db_session.execute(select(User).where(User.id == 1))).scalar_one_or_none()
    if not existing:
        db_session.add(User(id=1, openid="wx-t00637-user", nickname="播放量测试"))
        await db_session.commit()
    episode = Episode(
        title="T00637 播放量测试节目",
        date=date.today(),
        duration=600,
        audio_url="http://example.com/t00637.mp3",
        status=EpisodeStatus.published.value,
    )
    db_session.add(episode)
    await db_session.commit()
    await db_session.refresh(episode)
    return episode


def _auth(user_token):
    return {"Authorization": f"Bearer {user_token['token']}"}


@pytest.mark.asyncio
async def test_play_count_visible_and_persistent(db_session, client, user_token):
    from app.cache.manager import cache as cache_manager

    episode = await _seed(db_session)

    # 1) 上报播放进度（position 60s ≥ 阈值 30s）
    resp = client.post(
        "/api/v1/playlogs/progress",
        json={"episode_id": episode.id, "position": 60, "duration": 600,
              "completed": False, "listened_seconds": 60},
        headers=_auth(user_token),
    )
    assert resp.json()["code"] == 0, resp.text

    # 缓冲落库（生产由 1s 周期任务 flush；测试显式触发）
    await play_write_buffer.flush(session=db_session)

    logs = (await db_session.execute(
        select(PlayLog).where(PlayLog.episode_id == episode.id)
    )).scalars().all()
    assert len(logs) == 1, f"阈值以上播放应生成 1 条 play_log，实际 {len(logs)}"

    # 2) 列表接口应可见 play_count=1
    today = client.get("/api/v1/episodes/today", headers=_auth(user_token)).json()
    items = today["data"] if isinstance(today.get("data"), list) else (today.get("data") or {}).get("items") or []
    target = next((e for e in items if e.get("id") == episode.id), None)
    assert target is not None, f"今日节目接口未返回该节目：{[e.get('id') for e in items]}"
    assert target.get("play_count") == 1, f"列表 play_count 应为 1，实际 {target.get('play_count')}"

    # 3) 模拟「重新进入应用」：清空列表缓存后再查，播放量不得归零
    await cache_manager.delete("episode:today:all")
    await cache_manager.delete_pattern("episode:today:ch:*")
    again = client.get("/api/v1/episodes/today", headers=_auth(user_token)).json()
    items2 = again["data"] if isinstance(again.get("data"), list) else (again.get("data") or {}).get("items") or []
    target2 = next((e for e in items2 if e.get("id") == episode.id), None)
    assert target2 is not None
    assert target2.get("play_count") == 1, f"清缓存后 play_count 应仍为 1，实际 {target2.get('play_count')}"

    # 4) 重复播放不重复计数（每用户每节目一条）
    client.post(
        "/api/v1/playlogs/progress",
        json={"episode_id": episode.id, "position": 120, "duration": 600,
              "completed": False, "listened_seconds": 60},
        headers=_auth(user_token),
    )
    await play_write_buffer.flush(session=db_session)
    logs2 = (await db_session.execute(
        select(PlayLog).where(PlayLog.episode_id == episode.id)
    )).scalars().all()
    assert len(logs2) == 1, "同一用户重复播放不应新增 play_log"
