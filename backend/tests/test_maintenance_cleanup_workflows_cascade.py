"""回归测试：maintenance_service._cleanup_workflows 级联清理子表。

根因：_cleanup_workflows 删 Workflow 时只靠 ORM cascade 清 workflow_step，
但 Script/Review/Episode/AutoReviewStat/NotificationLog 的 workflow_id 是普通
字符串列（非外键），删 Workflow 不会自动清理 → 悬空数据随定时清理累积。
此外历史 Episode.workflow_id 为 NULL（孤儿），仅按 workflow_id 删 Episode 会
漏掉，删 Script 时触发 FOREIGN KEY constraint failed。

本测试构造「旧工作流(超 cutoff) + 完整子表链 + NULL-workflow 孤儿 Episode」与
一个「近工作流(未超 cutoff)」负对照，断言：
- 旧工作流及其 Script/Episode(含孤儿)/Review/AutoReviewStat/PlayLog/PlayProgress/
  Comment/Favorite/NotificationLog/WorkflowStep 全部被级联删除；
- 近工作流及其子表保留；
- dry_run 仅统计、不删除。
"""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import (
    AutoReviewStat,
    Comment,
    Episode,
    Favorite,
    NotificationLog,
    PlayLog,
    PlayProgress,
    Review,
    Script,
    Workflow,
    WorkflowStep,
)
from app.models.workflow import WorkflowSource, WorkflowStatus
from app.services.maintenance_service import MaintenanceService


async def _seed_workflow(db, wid, finished_at, *, old=True):
    """构造一条工作流及其完整子表链；old=True 时额外加一条 NULL-workflow 孤儿 Episode。"""
    wf = Workflow(
        id=wid,
        episode_date=date.today(),
        source=WorkflowSource.cron,
        status=WorkflowStatus.success,
        started_at=None,
        finished_at=finished_at,
    )
    db.add(wf)
    db.add(WorkflowStep(workflow_id=wid, step_name="crawl"))
    sc = Script(
        workflow_id=wid,
        episode_date=date.today(),
        full_text="测试稿件正文",
        segments=[{"seq": 1, "title": "段1", "content": "内容"}],
    )
    db.add(sc)
    await db.flush()

    ep = Episode(
        workflow_id=wid,
        script_id=sc.id,
        date=date.today(),
        title="节目",
        duration=60,
        audio_url="http://example.com/a.mp3",
    )
    db.add(ep)
    await db.flush()

    rv = Review(
        workflow_id=wid,
        episode_date=date.today(),
        script_id=sc.id,
        audio_url="http://example.com/a.mp3",
        status="pending",
    )
    db.add(rv)
    await db.flush()

    db.add(AutoReviewStat(review_id=rv.id, workflow_id=wid, success=True))
    db.add(PlayLog(episode_id=ep.id))
    db.add(PlayProgress(user_id=1, episode_id=ep.id))
    db.add(Comment(user_id="u1", episode_id=ep.id, content="评论"))
    db.add(Favorite(user_id="u1", episode_id=ep.id))
    db.add(
        NotificationLog(
            event_type="publish",
            channel="wechat",
            title="已发布",
            status="sent",
            workflow_id=wid,
            created_at=datetime.now(),
        )
    )
    # 历史脏数据：workflow_id=None 但 script_id 指向本批 Script
    if old:
        db.add(
            Episode(
                workflow_id=None,
                script_id=sc.id,
                date=date.today(),
                title="孤儿节目",
                duration=30,
                audio_url="http://example.com/orphan.mp3",
            )
        )
    await db.commit()


@pytest.mark.asyncio
async def test_cleanup_workflows_cascades_children(db_session):
    now = datetime.now()
    cutoff = now - timedelta(days=10)
    old_finished = now - timedelta(days=30)
    recent_finished = now - timedelta(days=1)

    await _seed_workflow(db_session, "old-wf", old_finished, old=True)
    # 负对照：未完成清理窗口，应保留
    await _seed_workflow(db_session, "recent-wf", recent_finished, old=False)

    # 清理前计数基线
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "old-wf"))).scalar_one_or_none() is not None

    deleted = await MaintenanceService(db_session)._cleanup_workflows(cutoff, dry_run=False)
    assert deleted == 1

    # 旧工作流及全部子表被级联删除
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "old-wf"))).scalar_one_or_none() is None
    assert (await db_session.execute(select(Script).where(Script.workflow_id == "old-wf"))).scalars().all() == []
    assert (await db_session.execute(select(Episode).where(Episode.workflow_id == "old-wf"))).scalars().all() == []
    # 孤儿 Episode（workflow_id=None）按 script_id 命中，应被删
    assert (await db_session.execute(select(Review).where(Review.workflow_id == "old-wf"))).scalars().all() == []
    assert (await db_session.execute(select(AutoReviewStat).where(AutoReviewStat.workflow_id == "old-wf"))).scalars().all() == []
    assert (await db_session.execute(select(NotificationLog).where(NotificationLog.workflow_id == "old-wf"))).scalars().all() == []
    assert (await db_session.execute(select(WorkflowStep).where(WorkflowStep.workflow_id == "old-wf"))).scalars().all() == []

    # 负对照：近工作流保留
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "recent-wf"))).scalar_one_or_none() is not None
    assert (await db_session.execute(select(Script).where(Script.workflow_id == "recent-wf"))).scalars().all() != []


@pytest.mark.asyncio
async def test_cleanup_workflows_dry_run_only_counts(db_session):
    now = datetime.now()
    cutoff = now - timedelta(days=10)
    old_finished = now - timedelta(days=30)

    await _seed_workflow(db_session, "dry-wf", old_finished, old=True)

    deleted = await MaintenanceService(db_session)._cleanup_workflows(cutoff, dry_run=True)
    assert deleted == 1

    # dry_run 不删除任何行
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "dry-wf"))).scalar_one_or_none() is not None
    assert (await db_session.execute(select(Script).where(Script.workflow_id == "dry-wf"))).scalars().all() != []
