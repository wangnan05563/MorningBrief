"""T00726 验证失败修复：二层内容按频道类型（channel_type）分开查询。

覆盖：
- GET /playlogs/recent 的 channel_type 过滤（join 频道类型）；
- GET /favorites 的 channel_type 过滤；
- 两类混合数据时过滤结果互不串台。
"""
from datetime import date, timedelta

import pytest

from app.models import Channel, Episode, Favorite, PlayLog


async def _mk(db, name, ch_type):
    ch = Channel(name=name, channel_type=ch_type, selection_strategy="heat")
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
    return ch, ep


def _auth(user_token):
    return {"Authorization": f"Bearer {user_token['token']}"}


@pytest.mark.asyncio
async def test_recent_playlogs_filter_by_channel_type(db_session, client, admin_token, user_token):
    ch_news, ep_news = await _mk(db_session, "资讯频道T726", "news")
    ch_audiobook, ep_book = await _mk(db_session, "听书频道T726", "audiobook")

    now = __import__("datetime").datetime.now()
    for ep in (ep_news, ep_book):
        db_session.add(PlayLog(
            user_id="1", episode_id=ep.id, position=10, duration=600,
            completed=False, played_at=now,
        ))
    await db_session.commit()

    hdrs = _auth(user_token)
    all_res = client.get("/api/v1/playlogs/recent", params={"size": 20}, headers=hdrs).json()
    assert all_res["code"] == 0, all_res
    ids_all = {i["episode_id"] for i in all_res["data"]["list"]}
    assert {ep_news.id, ep_book.id} <= ids_all

    news_res = client.get(
        "/api/v1/playlogs/recent", params={"size": 20, "channel_type": "news"}, headers=hdrs
    ).json()
    news_ids = {i["episode_id"] for i in news_res["data"]["list"]}
    assert ep_news.id in news_ids and ep_book.id not in news_ids
    assert all(i.get("channel_type") == "news" for i in news_res["data"]["list"])

    book_res = client.get(
        "/api/v1/playlogs/recent", params={"size": 20, "channel_type": "audiobook"}, headers=hdrs
    ).json()
    book_ids = {i["episode_id"] for i in book_res["data"]["list"]}
    assert ep_book.id in book_ids and ep_news.id not in book_ids


@pytest.mark.asyncio
async def test_favorites_filter_by_channel_type(db_session, client, admin_token, user_token, monkeypatch):
    # 收藏按 openid 归属：mock openid 解析，避免依赖真实用户表
    import app.routers.api.favorites as fav_mod

    async def _fake_openid(db, user_id):
        return "openid_1"

    monkeypatch.setattr(fav_mod, "get_user_openid", _fake_openid)
    _, ep_news = await _mk(db_session, "收藏资讯T726", "news")
    _, ep_course = await _mk(db_session, "收藏课程T726", "course")

    db_session.add(Favorite(user_id="openid_1", episode_id=ep_news.id))
    db_session.add(Favorite(user_id="openid_1", episode_id=ep_course.id))
    await db_session.commit()

    hdrs = _auth(user_token)
    all_res = client.get("/api/v1/favorites", headers=hdrs).json()
    assert all_res["code"] == 0, all_res
    items = all_res["data"]["list"] if isinstance(all_res["data"], dict) else all_res["data"]
    assert {i["episode_id"] for i in items} >= {ep_news.id, ep_course.id}

    course_res = client.get(
        "/api/v1/favorites", params={"channel_type": "course"}, headers=hdrs
    ).json()
    c_items = course_res["data"]["list"] if isinstance(course_res["data"], dict) else course_res["data"]
    c_ids = {i["episode_id"] for i in c_items}
    assert ep_course.id in c_ids and ep_news.id not in c_ids
