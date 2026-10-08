"""T01579 收藏/最近播放列表缓存正确性：写后必须失效，不得读到陈旧列表。

覆盖：
- POST /favorites 后列表立即含新条目；
- DELETE /favorites 后列表立即不含该条目；
- PlayWriteBuffer 批量落库后 /playlogs/recent 立即含新节目。
"""
from datetime import date, datetime

import pytest

from app.models import Channel, Episode, Favorite, PlayLog
from app.routers.api import favorites as fav_mod
from app.services.play_write_buffer import play_write_buffer


def _hdr(user_token):
    return {"Authorization": f"Bearer {user_token['token']}"}


async def _mk_episode(db, name, ch_name="缓存验证频道"):
    ch = (await db.execute(__import__("sqlalchemy").select(Channel).where(Channel.name == ch_name))).scalar_one_or_none()
    if ch is None:
        ch = Channel(name=ch_name, channel_type="news", selection_strategy="heat")
        db.add(ch)
        await db.commit()
        await db.refresh(ch)
    ep = Episode(
        date=date.today(), title=f"{name} 节目", duration=600,
        audio_url=f"https://x/{name}.mp3", status="published", channel_id=ch.id,
    )
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    return ep


@pytest.mark.asyncio
async def test_favorites_list_cache_invalidated_on_add_and_remove(db_session, client, admin_token, user_token, monkeypatch):
    ep = await _mk_episode(db_session, "收藏T01579")
    hdrs = _hdr(user_token)

    # 收藏按 openid 归属：与既有用例一致 mock openid，不依赖真实用户表
    async def _fake_openid(db, user_id):
        return "openid_t01579"
    monkeypatch.setattr(fav_mod, "get_user_openid", _fake_openid)

    # 先建立缓存
    first = client.get("/api/v1/favorites", params={"page": 1, "size": 20}, headers=hdrs).json()
    assert first["code"] == 0
    assert ep.id not in {i["episode_id"] for i in first["data"]["list"]}

    added = client.post("/api/v1/favorites", json={"episode_id": ep.id}, headers=hdrs).json()
    assert added["code"] == 0 and added["data"]["success"]

    after_add = client.get("/api/v1/favorites", params={"page": 1, "size": 20}, headers=hdrs).json()
    assert ep.id in {i["episode_id"] for i in after_add["data"]["list"]}, "写后仍读到陈旧缓存"

    client.delete(f"/api/v1/favorites/{ep.id}", headers=hdrs)
    after_del = client.get("/api/v1/favorites", params={"page": 1, "size": 20}, headers=hdrs).json()
    assert ep.id not in {i["episode_id"] for i in after_del["data"]["list"]}, "删后仍读到陈旧缓存"


@pytest.mark.asyncio
async def test_recent_playlogs_cache_invalidated_after_buffer_flush(db_session, client, admin_token, user_token):
    ep = await _mk_episode(db_session, "最近播放T01579")
    hdrs = _hdr(user_token)
    uid = 1  # conftest user_token 的 sub="1"

    first = client.get("/api/v1/playlogs/recent", params={"page": 1, "size": 20}, headers=hdrs).json()
    assert first["code"] == 0
    assert ep.id not in {i["episode_id"] for i in first["data"]["list"]}

    await play_write_buffer.add({
        "user_id": uid, "episode_id": ep.id, "position": 120,
        "duration": 600, "completed": 0, "listened_seconds": 30, "now": datetime.now(),
    })
    await play_write_buffer.flush(session=db_session)

    after = client.get("/api/v1/playlogs/recent", params={"page": 1, "size": 20}, headers=hdrs).json()
    assert ep.id in {i["episode_id"] for i in after["data"]["list"]}, "批量落库后仍读到陈旧缓存"
