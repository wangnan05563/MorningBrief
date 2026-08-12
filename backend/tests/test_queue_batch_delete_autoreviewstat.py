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
from app.models import AutoReviewStat, Review, Script, Workflow
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
