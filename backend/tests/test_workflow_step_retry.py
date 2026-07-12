from contextlib import asynccontextmanager
from datetime import date
import pytest
from sqlalchemy import select

from app.core.exceptions import ParamError
from app.models import Workflow, WorkflowStep
from app.models.channel import Channel
from app.models.workflow import (
    WorkflowSource,
    WorkflowStatus,
    WorkflowStepName,
    WorkflowStepStatus,
)
from app.services.workflow_scheduler import WorkflowScheduler


def _patch_scheduler_session(monkeypatch, db_session):
    from app.services import workflow_scheduler as scheduler_module

    @asynccontextmanager
    async def session_factory():
        yield db_session

    monkeypatch.setattr(scheduler_module, "AsyncSessionLocal", session_factory)


async def _add_workflow(db_session, workflow_id="wf-original"):
    # conftest 启用了 PRAGMA foreign_keys=ON，需先插入 channel 记录满足外键约束
    channel = Channel(id=7, name="test-channel")
    db_session.add(channel)
    await db_session.flush()
    workflow = Workflow(
        id=workflow_id,
        episode_date=date(2026, 7, 12),
        source=WorkflowSource.manual,
        status=WorkflowStatus.failed,
        channel_id=7,
        priority=8,
    )
    db_session.add(workflow)
    await db_session.commit()
    return workflow


async def _add_step(db_session, workflow_id, name, status, result=None):
    step = WorkflowStep(
        workflow_id=workflow_id,
        step_name=name,
        status=status,
        result=result,
    )
    db_session.add(step)
    await db_session.commit()
    return step


@pytest.mark.asyncio
async def test_retry_tts_copies_rewrite_result_and_preserves_metadata(
    db_session, monkeypatch,
):
    _patch_scheduler_session(monkeypatch, db_session)
    scheduler = WorkflowScheduler()
    await _add_workflow(db_session)
    await _add_step(
        db_session, "wf-original", WorkflowStepName.crawl,
        WorkflowStepStatus.success, {"material_count": 6},
    )
    await _add_step(
        db_session, "wf-original", WorkflowStepName.rewrite,
        WorkflowStepStatus.success, {"script_id": 42},
    )
    await _add_step(
        db_session, "wf-original", WorkflowStepName.tts,
        WorkflowStepStatus.failed,
    )

    new_workflow_id = await scheduler.retry_workflow(
        "wf-original", "tts", "admin",
    )

    new_workflow = await db_session.get(Workflow, new_workflow_id)
    assert new_workflow.episode_date == date(2026, 7, 12)
    assert new_workflow.channel_id == 7
    assert new_workflow.priority == 8
    steps = (await db_session.execute(
        select(WorkflowStep).where(WorkflowStep.workflow_id == new_workflow_id)
        .order_by(WorkflowStep.id)
    )).scalars().all()
    assert [step.step_name for step in steps] == ["crawl", "rewrite"]
    assert [step.status for step in steps] == ["success", "success"]
    assert steps[1].result == {"script_id": 42}


@pytest.mark.asyncio
async def test_retry_tts_rejects_missing_rewrite_output(db_session, monkeypatch):
    _patch_scheduler_session(monkeypatch, db_session)
    scheduler = WorkflowScheduler()
    await _add_workflow(db_session)
    await _add_step(
        db_session, "wf-original", WorkflowStepName.crawl,
        WorkflowStepStatus.success, {"material_count": 6},
    )
    await _add_step(
        db_session, "wf-original", WorkflowStepName.rewrite,
        WorkflowStepStatus.success,
    )

    with pytest.raises(ParamError, match="rewrite"):
        await scheduler.retry_workflow("wf-original", "tts", "admin")


@pytest.mark.asyncio
async def test_resumed_tts_workflow_restores_rewrite_context(db_session, monkeypatch):
    _patch_scheduler_session(monkeypatch, db_session)
    scheduler = WorkflowScheduler()
    await _add_workflow(db_session, workflow_id="wf-retry")
    await _add_step(
        db_session, "wf-retry", WorkflowStepName.crawl,
        WorkflowStepStatus.success, {"material_count": 6},
    )
    await _add_step(
        db_session, "wf-retry", WorkflowStepName.rewrite,
        WorkflowStepStatus.success, {"script_id": 42},
    )

    completed, context = await scheduler._load_completed_step_context("wf-retry")

    assert completed == {WorkflowStepName.crawl, WorkflowStepName.rewrite}
    assert context["script_id"] == 42
