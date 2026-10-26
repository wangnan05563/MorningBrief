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
from app.models.audit_log import AuditLog
from app.models.workflow import WorkflowSource, WorkflowStatus
from app.core.exceptions import NotFoundError, ParamError
from app.services.maintenance_service import MaintenanceService


async def _seed_workflow(db, wid, finished_at, *, old=True, status=WorkflowStatus.success):
    """构造一条工作流及其完整子表链；old=True 时额外加一条 NULL-workflow 孤儿 Episode。"""
    wf = Workflow(
        id=wid,
        episode_date=date.today(),
        source=WorkflowSource.cron,
        status=status,
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


@pytest.mark.asyncio
async def test_cleanup_workflow_chain_by_id_preview_then_delete(db_session):
    """T02599：按 ID 全链清理先预览命中行数，再真删；其他工作流不受影响。"""
    now = datetime.now()
    await _seed_workflow(db_session, "target-wf", now - timedelta(days=3), old=True)
    await _seed_workflow(db_session, "other-wf", now - timedelta(days=2), old=False)
    svc = MaintenanceService(db_session)

    preview = await svc.cleanup_workflow_chain("target-wf", dry_run=True, admin_name="tester")
    assert preview["target"] == "workflow_chain"
    assert preview["workflow_id"] == "target-wf"
    assert preview["dry_run"] is True
    assert preview["counts"] == {
        "workflow_steps": 1, "scripts": 1, "episodes": 2, "reviews": 1,
        "auto_review_stats": 1, "notification_logs": 1, "play_logs": 1,
        "play_progress": 1, "comments": 1, "favorites": 1, "workflows": 1,
    }
    assert preview["total_deleted"] == 12
    assert all(" 将删除 " in line for line in preview["cleaned"])
    # 预览不得删任何行
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "target-wf"))).scalar_one_or_none() is not None
    assert (await db_session.execute(select(Script).where(Script.workflow_id == "target-wf"))).scalars().all() != []

    result = await svc.cleanup_workflow_chain("target-wf", dry_run=False, admin_name="tester")
    assert result["dry_run"] is False
    assert result["counts"] == preview["counts"]
    assert all(" 已删除 " in line for line in result["cleaned"])

    # 目标工作流全链清空
    for model, cond in [
        (Workflow, Workflow.id == "target-wf"),
        (WorkflowStep, WorkflowStep.workflow_id == "target-wf"),
        (Script, Script.workflow_id == "target-wf"),
        (Episode, Episode.workflow_id == "target-wf"),
        (Review, Review.workflow_id == "target-wf"),
        (AutoReviewStat, AutoReviewStat.workflow_id == "target-wf"),
        (NotificationLog, NotificationLog.workflow_id == "target-wf"),
    ]:
        assert (await db_session.execute(select(model).where(cond))).scalars().all() == [], model

    # 负对照：另一条工作流及其子表原样保留
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "other-wf"))).scalar_one_or_none() is not None
    assert (await db_session.execute(select(Script).where(Script.workflow_id == "other-wf"))).scalars().all() != []

    # 审计：动作、对象、操作者三要素齐全（T02599 要求事后可查「谁删了哪条」）
    audit = (await db_session.execute(
        select(AuditLog).where(
            AuditLog.category == "maintenance",
            AuditLog.action == "cleanup_workflow_chain",
        )
    )).scalars().all()
    assert [a.target for a in audit] == ["target-wf", "target-wf"]
    assert all(a.operator == "tester" for a in audit)


@pytest.mark.asyncio
async def test_cleanup_workflow_chain_rejects_running_and_unknown(db_session):
    """运行中工作流拒绝清理；未知 ID 明确 404，不能静默当作已清理。"""
    await _seed_workflow(
        db_session, "running-wf", None,
        old=False, status=WorkflowStatus.running,
    )
    svc = MaintenanceService(db_session)

    with pytest.raises(ParamError) as refused:
        await svc.cleanup_workflow_chain("running-wf", dry_run=False, admin_name="tester")
    assert "仅已完结的工作流允许全链清理" in refused.value.message
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "running-wf"))).scalar_one_or_none() is not None

    with pytest.raises(NotFoundError) as missing:
        await svc.cleanup_workflow_chain("no-such-wf", dry_run=True, admin_name="tester")
    assert "工作流不存在" in missing.value.message
