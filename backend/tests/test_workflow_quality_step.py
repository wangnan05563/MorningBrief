"""质量审核步骤接入工作流的测试（T01712 P1）。

覆盖：
1. _STEP_ORDER 中 quality_check 位于 rewrite 与 tts 之间
2. retry_workflow 断点续跑兼容：从 quality_check 重跑/从 tts 重跑需前置成功
3. _load_completed_step_context 恢复 quality_check 步骤产物

复用 test_workflow_step_retry.py 的 scheduler session patch 模式。
"""
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


async def _add_workflow(db_session, workflow_id="wf-qc"):
    channel = Channel(id=9, name="qc-channel")
    db_session.add(channel)
    await db_session.flush()
    workflow = Workflow(
        id=workflow_id,
        episode_date=date(2026, 10, 10),
        source=WorkflowSource.manual,
        status=WorkflowStatus.failed,
        channel_id=9,
        priority=5,
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


def test_step_order_quality_check_between_rewrite_and_tts():
    """quality_check 必须插在 rewrite 之后、tts 之前（T01712 的核心接线点）。"""
    order = [s.value for s in WorkflowScheduler._STEP_ORDER]
    assert order.index("quality_check") == order.index("rewrite") + 1
    assert order.index("tts") == order.index("quality_check") + 1


def test_workflow_step_name_enum_has_quality_check():
    """枚举值 'quality_check' 与 CHECK 约束/前端映射三处必须一致。"""
    assert WorkflowStepName.quality_check.value == "quality_check"


@pytest.mark.asyncio
async def test_retry_from_quality_check_keeps_prior_steps(db_session, monkeypatch):
    """quality_check 失败后从该步重跑：删 quality_check 及之后，保留 crawl/rewrite。"""
    _patch_scheduler_session(monkeypatch, db_session)
    scheduler = WorkflowScheduler()
    await _add_workflow(db_session)
    await _add_step(
        db_session, "wf-qc", WorkflowStepName.crawl,
        WorkflowStepStatus.success, {"material_count": 6},
    )
    await _add_step(
        db_session, "wf-qc", WorkflowStepName.rewrite,
        WorkflowStepStatus.success, {"script_id": 42},
    )
    await _add_step(
        db_session, "wf-qc", WorkflowStepName.quality_check,
        WorkflowStepStatus.failed,
    )

    class _FakeQueue:
        async def put(self, item):
            pass
    monkeypatch.setattr(scheduler, "_queue", _FakeQueue())
    returned_id = await scheduler.retry_workflow("wf-qc", "quality_check", "admin")

    assert returned_id == "wf-qc"
    wf = await db_session.get(Workflow, "wf-qc")
    assert wf.status == "queued"
    steps = (await db_session.execute(
        select(WorkflowStep).where(WorkflowStep.workflow_id == "wf-qc")
        .order_by(WorkflowStep.id)
    )).scalars().all()
    assert [step.step_name for step in steps] == ["crawl", "rewrite"]


@pytest.mark.asyncio
async def test_retry_from_tts_requires_quality_check_success(db_session, monkeypatch):
    """从 tts 重跑时 quality_check 属于保留步骤，无成功记录则拒绝（防跳审）。"""
    _patch_scheduler_session(monkeypatch, db_session)
    scheduler = WorkflowScheduler()
    await _add_workflow(db_session)
    await _add_step(
        db_session, "wf-qc", WorkflowStepName.crawl,
        WorkflowStepStatus.success, {"material_count": 6},
    )
    await _add_step(
        db_session, "wf-qc", WorkflowStepName.rewrite,
        WorkflowStepStatus.success, {"script_id": 42},
    )
    # quality_check 无成功记录（如历史工作流从未跑过该步骤）

    with pytest.raises(ParamError, match="quality_check"):
        await scheduler.retry_workflow("wf-qc", "tts", "admin")


@pytest.mark.asyncio
async def test_resumed_context_includes_quality_check_result(db_session, monkeypatch):
    """断点续跑时 quality_check 的 result 合并进 context，供后续步骤读取。"""
    _patch_scheduler_session(monkeypatch, db_session)
    scheduler = WorkflowScheduler()
    await _add_workflow(db_session)
    await _add_step(
        db_session, "wf-qc", WorkflowStepName.crawl,
        WorkflowStepStatus.success, {"material_count": 6},
    )
    await _add_step(
        db_session, "wf-qc", WorkflowStepName.rewrite,
        WorkflowStepStatus.success, {"script_id": 42},
    )
    await _add_step(
        db_session, "wf-qc", WorkflowStepName.quality_check,
        WorkflowStepStatus.success,
        {"quality_check": {"passed": False, "issue_count": 2, "alert_count": 1,
                            "skipped": False, "skipped_reason": None}},
    )

    completed, context = await scheduler._load_completed_step_context("wf-qc")

    assert completed == {
        WorkflowStepName.crawl, WorkflowStepName.rewrite, WorkflowStepName.quality_check,
    }
    assert context["script_id"] == 42
    assert context["quality_check"]["issue_count"] == 2
