"""T02910：读-判-写三条路径的幂等由数据库裁决，不再依赖进程内锁。

锁在跨事件循环/多进程下不成立，因此收藏、点赞、频道订阅的重复提交必须由
UNIQUE 约束 + ON CONFLICT 保证「只落一行、计数只加一次」。
"""
from datetime import date

import pytest
from sqlalchemy import func, select

from app.models import Channel, ChannelSubscription, Comment, CommentLike, Episode, Favorite
from app.routers.api import comments as comments_mod
from app.routers.api import favorites as fav_mod


def _hdr(user_token):
    return {"Authorization": f"Bearer {user_token['token']}"}


async def _mk_episode(db, name):
    ch = (await db.execute(select(Channel).where(Channel.name == "T02910 频道"))).scalar_one_or_none()
    if ch is None:
        ch = Channel(name="T02910 频道", channel_type="news", selection_strategy="heat")
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


async def _count(db, model, **where):
    await db.rollback()
    stmt = select(func.count()).select_from(model)
    for key, value in where.items():
        stmt = stmt.where(getattr(model, key) == value)
    return (await db.execute(stmt)).scalar_one()


@pytest.mark.asyncio
async def test_duplicate_favorite_writes_one_row(db_session, client, user_token, monkeypatch):
    ep = await _mk_episode(db_session, "收藏T02910")
    async def _fake_openid(db, user_id):
        return "openid_t02910_fav"
    monkeypatch.setattr(fav_mod, "get_user_openid", _fake_openid)

    first = client.post("/api/v1/favorites", json={"episode_id": ep.id}, headers=_hdr(user_token)).json()
    second = client.post("/api/v1/favorites", json={"episode_id": ep.id}, headers=_hdr(user_token)).json()

    assert first["code"] == 0 and first["data"]["already_favorited"] is False
    assert second["code"] == 0 and second["data"]["already_favorited"] is True
    assert second["data"]["favorite_id"] == first["data"]["favorite_id"]
    assert await _count(db_session, Favorite, user_id="openid_t02910_fav", episode_id=ep.id) == 1


@pytest.mark.asyncio
async def test_duplicate_like_increments_count_once(db_session, client, user_token, monkeypatch):
    ep = await _mk_episode(db_session, "点赞T02910")
    comment = Comment(user_id="author_t02910", episode_id=ep.id, content="测试", like_count=0)
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    comment_id = comment.id

    async def _fake_openid(db, user_id):
        return "openid_t02910_like"
    monkeypatch.setattr(comments_mod, "get_user_openid", _fake_openid)

    first = client.post(f"/api/v1/comments/{comment_id}/like", headers=_hdr(user_token)).json()
    second = client.post(f"/api/v1/comments/{comment_id}/like", headers=_hdr(user_token)).json()

    assert first["code"] == 0 and first["data"]["like_count"] == 1
    assert second["code"] == 0 and second["data"]["like_count"] == 1
    assert await _count(db_session, CommentLike, user_id="openid_t02910_like", comment_id=comment_id) == 1
    await db_session.rollback()
    stored = (await db_session.execute(select(Comment.like_count).where(Comment.id == comment_id))).scalar_one()
    assert stored == 1


@pytest.mark.asyncio
async def test_duplicate_channel_subscribe_writes_one_row(db_session, client, user_token):
    ch = Channel(name="T02910 订阅频道", channel_type="news", selection_strategy="heat")
    db_session.add(ch)
    await db_session.commit()
    await db_session.refresh(ch)

    first = client.post(f"/api/v1/subscriptions/channels/{ch.id}", headers=_hdr(user_token)).json()
    second = client.post(f"/api/v1/subscriptions/channels/{ch.id}", headers=_hdr(user_token)).json()

    assert first["code"] == 0 and first["data"]["already_subscribed"] is False
    assert second["code"] == 0 and second["data"]["already_subscribed"] is True
    assert await _count(db_session, ChannelSubscription, channel_id=ch.id) == 1
