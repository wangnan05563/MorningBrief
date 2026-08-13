"""回归测试：批量删除工作流时清理 auto_review_stat。

根因：auto_review_stat.review_id 是 RESTRICT 外键指向 review.id，
而批量删除级联先删 Review 却不清理 auto_review_stat，
在 PRAGMA foreign_keys=ON 下触发外键约束冲突 → 500。

本测试构造「工作流 → 稿件 → 审核 → 自动审批统计」链路后批量删除，
断言：① 路由返回 200（不再 500）；② auto_review_stat 行被一并删除。
"""
from datetime import date

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models import (
    AutoReviewStat,
    Comment,
    Episode,
    Favorite,
    PlayLog,
    Review,
    Script,
    Workflow,
)
from app.models.workflow import WorkflowSource, WorkflowStatus


@pytest.fixture
def stub_blacklist(monkeypatch):
    async def _always_false(jti: str) -> bool:
        return False
    monkeypatch.setattr("app.core.auth.is_in_blacklist", _always_false)


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


async def _seed_chain(db, wid):
    """构造 工作流 → 稿件 → 审核 → 自动审批统计 四级链路。"""
    wf = Workflow(
        id=wid, episode_date=date.today(),
        source=WorkflowSource.cron, status=WorkflowStatus.success, started_at=None,
    )
    db.add(wf)
    sc = Script(
        workflow_id=wid, episode_date=date.today(),
        full_text="测试稿件正文", segments=[{"seq": 1, "title": "段1", "content": "内容"}],
    )
    db.add(sc)
    await db.flush()
    rv = Review(
        workflow_id=wid, episode_date=date.today(),
        script_id=sc.id, audio_url="http://example.com/a.mp3", status="pending",
    )
    db.add(rv)
    await db.flush()
    stat = AutoReviewStat(review_id=rv.id, workflow_id=wid, success=True)
    db.add(stat)
    await db.commit()
    return rv.id, stat.id


@pytest.mark.asyncio
async def test_batch_delete_cleans_auto_review_stat(client, db_session, admin_token, stub_blacklist):
    """批量删除含 auto_review_stat 的工作流：返回 200 且统计行被级联删除。"""
    wid = "ars-wf-1"
    review_id, stat_id = await _seed_chain(db_session, wid)

    # 删除前应存在 auto_review_stat 行
    before = (await db_session.execute(
        select(AutoReviewStat).where(AutoReviewStat.id == stat_id)
    )).scalar_one_or_none()
    assert before is not None

    resp = client.post(
        "/admin/api/v1/queue/tasks/batch-delete",
        json={"workflow_ids": [wid]},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["deleted"] == [wid]

    # 关键断言：auto_review_stat 随 Review 一并被清理，否则旧逻辑会因 FK 冲突 500
    after = (await db_session.execute(
        select(AutoReviewStat).where(AutoReviewStat.id == stat_id)
    )).scalars().all()
    assert after == []

    # 关联 Review 也应被删除
    review_left = (await db_session.execute(
        select(Review).where(Review.id == review_id)
    )).scalars().all()
    assert review_left == []


@pytest.mark.asyncio
async def test_batch_delete_cleans_orphan_null_workflow_episode(client, db_session, admin_token, stub_blacklist):
    """回归：Script 被 workflow_id=NULL 的孤儿 Episode 引用时批量删除不应报 FK 错误。

    根因：部分历史 Episode.workflow_id 为 NULL，仅按 workflow_id 删 Episode 会漏掉，
    删 Script 时触发 FOREIGN KEY constraint failed → 前端"数据库错误"。
    修复后 Episode/Review 同时按 script_id 命中，可覆盖孤儿子表。
    """
    wid = "orphan-wf-1"
    wf = Workflow(
        id=wid, episode_date=date.today(),
        source=WorkflowSource.cron, status=WorkflowStatus.success, started_at=None,
    )
    db_session.add(wf)
    sc = Script(
        workflow_id=wid, episode_date=date.today(),
        full_text="x", segments=[{"seq": 1, "title": "t", "content": "c"}],
    )
    db_session.add(sc)
    await db_session.flush()
    # 孤儿 Episode：workflow_id=None 但 script_id 指向本批 Script（复现历史脏数据）
    ep = Episode(
        workflow_id=None, script_id=sc.id, date=date.today(),
        title="孤儿节目", duration=60, audio_url="http://example.com/a.mp3",
    )
    db_session.add(ep)
    await db_session.commit()

    resp = client.post(
        "/admin/api/v1/queue/tasks/batch-delete",
        json={"workflow_ids": [wid]},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    # 孤儿 Episode 应被级联删除（按 script_id 命中），否则旧逻辑会因 FK 冲突 500
    ep_left = (await db_session.execute(
        select(Episode).where(Episode.id == ep.id)
    )).scalars().all()
    assert ep_left == []
    # Script 本身也应被删除
    sc_left = (await db_session.execute(
        select(Script).where(Script.id == sc.id)
    )).scalars().all()
    assert sc_left == []


def test_batch_delete_auto_review_stat_rejects_non_admin(client, admin_token, stub_blacklist):
    """operator 角色调用应返回 403（确保鉴权不被改动影响）。"""
    token, _, _ = create_access_token(
        "2", token_type="admin", extra_claims={"username": "op01", "role": "operator"}
    )
    resp = client.post(
        "/admin/api/v1/queue/tasks/batch-delete",
        json={"workflow_ids": ["ars-wf-x"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_batch_delete_cleans_orphan_episode_with_playlog(client, db_session, admin_token, stub_blacklist):
    """回归 #1：Script 被 workflow_id=NULL 孤儿 Episode 引用且 Ep 带 PlayLog 时，
    批量删除不应 FK 失败，且孤儿 Episode 与其 PlayLog 一并被清理。

    旧逻辑 episode_ids 仅按 workflow_id 收集，Orphan Episode 的 PlayLog 不被清理 →
    删 Episode 时 FOREIGN KEY constraint failed（前端"数据库错误"）。
    修复后 episode_ids 采用与 Episode 删除相同的双条件，PlayLog 清理覆盖全部被删 Episode。
    """
    wid = "orphan-pl-wf-1"
    wf = Workflow(
        id=wid, episode_date=date.today(),
        source=WorkflowSource.cron, status=WorkflowStatus.success, started_at=None,
    )
    db_session.add(wf)
    sc = Script(
        workflow_id=wid, episode_date=date.today(),
        full_text="x", segments=[{"seq": 1, "title": "t", "content": "c"}],
    )
    db_session.add(sc)
    await db_session.flush()
    ep = Episode(
        workflow_id=None, script_id=sc.id, date=date.today(),
        title="孤儿节目", duration=60, audio_url="http://example.com/a.mp3",
    )
    db_session.add(ep)
    await db_session.flush()
    pl = PlayLog(episode_id=ep.id)
    db_session.add(pl)
    await db_session.commit()

    resp = client.post(
        "/admin/api/v1/queue/tasks/batch-delete",
        json={"workflow_ids": [wid]},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    ep_left = (await db_session.execute(
        select(Episode).where(Episode.id == ep.id)
    )).scalars().all()
    assert ep_left == []
    pl_left = (await db_session.execute(
        select(PlayLog).where(PlayLog.id == pl.id)
    )).scalars().all()
    assert pl_left == []


@pytest.mark.asyncio
async def test_batch_delete_cleans_comment_favorite(client, db_session, admin_token, stub_blacklist):
    """回归 #6：批量删除应一并清理被删 Episode 的 Comment/Favorite（普通列孤儿数据）。

    Comment/Favorite 的 episode_id 是普通列（非外键），删 Episode 不报 FK，
    但会指向已删 Episode 成为孤儿数据累积；与 maintenance_service 清理口径对齐。
    """
    wid = "cf-wf-1"
    wf = Workflow(
        id=wid, episode_date=date.today(),
        source=WorkflowSource.cron, status=WorkflowStatus.success, started_at=None,
    )
    db_session.add(wf)
    sc = Script(
        workflow_id=wid, episode_date=date.today(),
        full_text="x", segments=[{"seq": 1, "title": "t", "content": "c"}],
    )
    db_session.add(sc)
    await db_session.flush()
    ep = Episode(
        workflow_id=wid, script_id=sc.id, date=date.today(),
        title="节目", duration=60, audio_url="http://example.com/a.mp3",
    )
    db_session.add(ep)
    await db_session.flush()
    cm = Comment(user_id="u1", episode_id=ep.id, content="评论")
    db_session.add(cm)
    fv = Favorite(user_id="u1", episode_id=ep.id)
    db_session.add(fv)
    await db_session.commit()

    resp = client.post(
        "/admin/api/v1/queue/tasks/batch-delete",
        json={"workflow_ids": [wid]},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    cm_left = (await db_session.execute(
        select(Comment).where(Comment.id == cm.id)
    )).scalars().all()
    assert cm_left == []
    fv_left = (await db_session.execute(
        select(Favorite).where(Favorite.id == fv.id)
    )).scalars().all()
    assert fv_left == []
