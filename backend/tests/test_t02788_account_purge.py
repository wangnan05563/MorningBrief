"""T02788（J98 续）：个人数据自助删除的双键口径与留痕。

红基线（改前）：后端没有任何删除接口，隐私政策第七条只能指人工通道（T02513）。

本单真正的风险不是「接口不存在」，而是「接口存在但删不干净」：用户的身份在库里
是两个键——`favorite`/`comment`/`comment_like`/`subscription` 存 openid，
`play_log`/`play_progress`/`channel_subscription` 存 `User.id`。只按 openid 删，
播放记录、播放进度、频道订阅会整片留下，而接口照样返回成功。

所以下面每条断言看的都是**库里的行数**，不是只看返回码；并且每个用例都同时埋了
「别人的数据」，用来证明删除没有越界（这也是变异探针里「接错对象」腿要抓的东西）。
"""
import hashlib
import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.models import (
    AuditLog,
    ChannelSubscription,
    Comment,
    CommentLike,
    Favorite,
    PlayLog,
    PlayProgress,
    Subscription,
    User,
)

URL = "/api/v1/account/data"


class _FakeSessionCtx:
    """适配 `async with AsyncSessionLocal() as session`（黑名单双写用）。"""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def stub_blacklist(monkeypatch):
    """绕过黑名单的 DB 查询，避免命中生产 SQLite 文件。"""
    import app.core.auth

    async def _never(jti: str) -> bool:
        return False

    monkeypatch.setattr(app.core.auth, "is_in_blacklist", _never)


async def _count(db, model, *conds) -> int:
    return int((await db.execute(select(func.count(model.id)).where(*conds))).scalar_one())


async def _seed_two_users(db) -> None:
    """我（id=1 / openid-me）与别人（id=2 / openid-other）各埋一排数据。

    别人的那排是「不越界」的对照：删除只认 token 里的身份，
    任何按 body 里的 openid 寻址的实现都会把它一起抹掉。
    """
    db.add_all([User(id=1, openid="openid-me"), User(id=2, openid="openid-other")])
    db.add_all(
        [
            # —— 我：openid 键 ——
            Favorite(user_id="openid-me", episode_id=101),
            Comment(id=10, user_id="openid-me", episode_id=101, content="我的评论"),
            CommentLike(user_id="openid-me", comment_id=20),
            # —— 我：User.id 键 ——
            PlayLog(user_id=1, episode_id=101),
            PlayLog(user_id=1, episode_id=102),
            PlayProgress(user_id=1, episode_id=101),
            ChannelSubscription(user_id=1, channel_id=7),
            Subscription(user_id=1, template_id="tpl", openid="openid-me"),
            # —— 别人 ——
            Favorite(user_id="openid-other", episode_id=101),
            Comment(id=20, user_id="openid-other", episode_id=101, content="别人的评论", like_count=1),
            CommentLike(user_id="openid-other", comment_id=10),
            PlayLog(user_id=2, episode_id=101),
            PlayProgress(user_id=2, episode_id=101),
            ChannelSubscription(user_id=2, channel_id=7),
            Subscription(user_id=2, template_id="tpl", openid="openid-other"),
        ]
    )
    await db.commit()


@pytest.mark.asyncio
async def test_purge_clears_both_identity_keys(db_session, client, user_token, stub_blacklist):
    """双键都归零；同一条用例里别人的数据必须原样还在。"""
    await _seed_two_users(db_session)

    resp = client.request(
        "DELETE", URL, json={"confirm": True}, headers={"Authorization": f"Bearer {user_token['token']}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0, body

    # openid 键
    assert await _count(db_session, Favorite, Favorite.user_id == "openid-me") == 0
    assert await _count(db_session, Comment, Comment.user_id == "openid-me") == 0
    assert await _count(db_session, CommentLike, CommentLike.user_id == "openid-me") == 0
    # User.id 键：只按 openid 删的实现会在这里留下 2 / 1 / 1 行
    assert await _count(db_session, PlayLog, PlayLog.user_id == 1) == 0
    assert await _count(db_session, PlayProgress, PlayProgress.user_id == 1) == 0
    assert await _count(db_session, ChannelSubscription, ChannelSubscription.user_id == 1) == 0
    # 订阅消息授权：两种键都可能有，按 user_id 或 openid 任一命中即删
    assert await _count(db_session, Subscription, Subscription.user_id == 1) == 0
    # 用户行本身
    assert (
        await db_session.execute(select(User.id).where(User.id == 1))
    ).scalar_one_or_none() is None

    # 别人的数据一个都不能少
    assert await _count(db_session, Favorite, Favorite.user_id == "openid-other") == 1
    assert await _count(db_session, Comment, Comment.user_id == "openid-other") == 1
    assert await _count(db_session, PlayLog, PlayLog.user_id == 2) == 1
    assert await _count(db_session, PlayProgress, PlayProgress.user_id == 2) == 1
    assert await _count(db_session, ChannelSubscription, ChannelSubscription.user_id == 2) == 1
    assert (
        await db_session.execute(select(User.id).where(User.id == 2))
    ).scalar_one_or_none() == 2

    # 响应里的计数与库里一致（前端确认框显示的就是这份）
    deleted = body["data"]["deleted"]
    assert deleted["play_log"] == 2
    assert deleted["favorite"] == 1
    assert deleted["user"] == 1


@pytest.mark.asyncio
async def test_purge_without_confirm_deletes_nothing(db_session, client, user_token, stub_blacklist):
    """没有二次确认必须一行都不删——否则误触一次就不可逆。"""
    await _seed_two_users(db_session)

    resp = client.request(
        "DELETE", URL, json={}, headers={"Authorization": f"Bearer {user_token['token']}"}
    )
    assert resp.json()["code"] == 400
    assert await _count(db_session, Favorite, Favorite.user_id == "openid-me") == 1
    assert await _count(db_session, PlayLog, PlayLog.user_id == 1) == 2
    assert (
        await db_session.execute(select(User.id).where(User.id == 1))
    ).scalar_one_or_none() == 1


@pytest.mark.asyncio
async def test_body_identity_is_ignored(db_session, client, user_token, stub_blacklist):
    """请求体里塞 openid/user_id 不得改变删除对象：身份只认 token。"""
    await _seed_two_users(db_session)

    resp = client.request(
        "DELETE",
        URL,
        json={"confirm": True, "openid": "openid-other", "user_id": 2},
        headers={"Authorization": f"Bearer {user_token['token']}"},
    )
    assert resp.json()["code"] == 0

    # 被点名的「别人」毫发无损
    assert await _count(db_session, Favorite, Favorite.user_id == "openid-other") == 1
    assert await _count(db_session, PlayLog, PlayLog.user_id == 2) == 1
    assert (
        await db_session.execute(select(User.id).where(User.id == 2))
    ).scalar_one_or_none() == 2
    # 真正被删的仍是 token 对应的我自己
    assert await _count(db_session, Favorite, Favorite.user_id == "openid-me") == 0
    assert await _count(db_session, PlayLog, PlayLog.user_id == 1) == 0


@pytest.mark.asyncio
async def test_comment_like_count_recomputed(db_session, client, user_token, stub_blacklist):
    """我点过的赞删掉后，被赞评论的冗余列 like_count 必须跟着归零。"""
    await _seed_two_users(db_session)

    resp = client.request(
        "DELETE", URL, json={"confirm": True}, headers={"Authorization": f"Bearer {user_token['token']}"}
    )
    assert resp.json()["code"] == 0

    like_count = (
        await db_session.execute(select(Comment.like_count).where(Comment.id == 20))
    ).scalar_one()
    assert like_count == 0
    # 我的评论连同它收到的赞一起消失（不留悬空引用）
    assert (
        await db_session.execute(select(Comment.id).where(Comment.id == 10))
    ).scalar_one_or_none() is None
    assert await _count(db_session, CommentLike, CommentLike.comment_id == 10) == 0


@pytest.mark.asyncio
async def test_audit_keeps_counts_and_digest_only(db_session, client, user_token, stub_blacklist):
    """审计只留各表删除行数与 openid 不可逆摘要，不留明文。"""
    await _seed_two_users(db_session)

    resp = client.request(
        "DELETE", URL, json={"confirm": True}, headers={"Authorization": f"Bearer {user_token['token']}"}
    )
    assert resp.json()["code"] == 0

    row = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "user_data_purge")
        )
    ).scalar_one()
    assert row.category == "user"
    digest = hashlib.sha256(b"openid-me").hexdigest()[:12]
    assert row.target == digest
    assert "openid-me" not in (row.detail or "")
    detail = json.loads(row.detail)
    assert detail["play_log"] == 2
    assert detail["play_progress"] == 1
    assert detail["channel_subscription"] == 1


@pytest.mark.asyncio
async def test_cos_failure_does_not_undo_db_delete(
    db_session, client, user_token, stub_blacklist, monkeypatch
):
    """COS 抖动只告警：库已删就不回滚，避免「删了却报错」的二义状态。"""
    import app.services.account_service as acc

    monkeypatch.setattr(acc, "is_cos_configured", lambda: True)
    monkeypatch.setattr(
        acc.CosStorageService,
        "delete_folder",
        AsyncMock(side_effect=RuntimeError("cos down")),
    )
    await _seed_two_users(db_session)

    resp = client.request(
        "DELETE", URL, json={"confirm": True}, headers={"Authorization": f"Bearer {user_token['token']}"}
    )
    body = resp.json()
    assert body["code"] == 0, body
    assert await _count(db_session, Favorite, Favorite.user_id == "openid-me") == 0
    assert await _count(db_session, PlayLog, PlayLog.user_id == 1) == 0
    # 响应如实说明云端没删成，而不是假装成功
    assert str(body["data"]["cos"]["favorites"]).startswith("failed:")


@pytest.mark.asyncio
async def test_preview_reports_counts_without_side_effects(
    db_session, client, user_token, stub_blacklist
):
    """预览接口给出确认框需要的条数与备份保留口径，且不改任何数据。"""
    await _seed_two_users(db_session)

    resp = client.get(URL, headers={"Authorization": f"Bearer {user_token['token']}"})
    body = resp.json()
    assert body["code"] == 0, body

    counts = body["data"]["counts"]
    assert counts["favorite"] == 1
    assert counts["comment"] == 1
    # 我点出去的 1 条 + 我的评论收到的 1 条：后者随评论一起消失，确认框必须算进去
    assert counts["comment_like"] == 2
    assert counts["play_log"] == 2
    assert counts["play_progress"] == 1
    assert counts["channel_subscription"] == 1
    assert counts["subscription"] == 1
    # 账号行本身也算一条：确认框里的总数必须与 purge 实际删除口径一致
    assert counts["user"] == 1
    assert counts["total"] == sum(
        v for k, v in counts.items() if k != "total"
    )

    retention = body["data"]["retention"]
    assert retention["db_backup_keep_days"] >= 1
    assert retention["cos_backup_keep_count"] >= 1

    # 预览不能顺手删：看一眼就把数据删了是最糟的失败模式
    assert await _count(db_session, Favorite, Favorite.user_id == "openid-me") == 1
    assert await _count(db_session, PlayLog, PlayLog.user_id == 1) == 2


@pytest.mark.asyncio
async def test_token_revoked_after_purge(db_session, client, user_token, monkeypatch):
    """删号后同一张 token 立刻失效：不靠 user 行缺失撞 404，而是 401。"""
    import app.services.blacklist_service as bl

    monkeypatch.setattr(bl, "AsyncSessionLocal", lambda: _FakeSessionCtx(db_session))
    monkeypatch.setattr(bl.cos_client, "put_object", AsyncMock(return_value=None))
    # 强制下次查询回源到测试库，避免命中别的用例留下的内存缓存
    monkeypatch.setattr(bl, "_blacklist_cache_expires_at", 0)
    monkeypatch.setattr(bl, "_blacklist_cache", set())

    await _seed_two_users(db_session)
    headers = {"Authorization": f"Bearer {user_token['token']}"}

    assert client.request("DELETE", URL, json={"confirm": True}, headers=headers).json()["code"] == 0
    assert client.get("/api/v1/users/stats", headers=headers).status_code == 401
