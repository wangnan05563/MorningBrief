"""工作流查询服务测试。

覆盖 services/workflow_service.py：
- get_today_workflow：查询今日工作流
- list_workflows：分页
- get_workflow_detail：详情含步骤
"""
from datetime import date, datetime

import pytest

from app.core.exceptions import NotFoundError
from app.models import Workflow, WorkflowStep
from app.models.workflow import (
    WorkflowSource,
    WorkflowStatus,
    WorkflowStepName,
    WorkflowStepStatus,
)
from app.services.workflow_service import WorkflowService


async def _create_workflow(
    db,
    wid="wf-20260708-0001",
    episode_date=None,
    status=WorkflowStatus.running,
    source=WorkflowSource.cron,
):
    """辅助：创建一条 workflow 记录。"""
    wf = Workflow(
        id=wid,
        episode_date=episode_date or date.today(),
        source=source,
        status=status,
        started_at=datetime.utcnow(),
    )
    db.add(wf)
    await db.commit()
    return wf


async def _add_step(db, workflow_id, step_name=WorkflowStepName.crawl, status=WorkflowStepStatus.success):
    """辅助：为 workflow 添加一条 step。"""
    step = WorkflowStep(
        workflow_id=workflow_id,
        step_name=step_name,
        status=status,
        started_at=datetime.utcnow(),
    )
    db.add(step)
    await db.commit()
    return step


@pytest.mark.asyncio
async def test_get_today_workflow_returns_none(db_session):
    """今日无工作流时返回 None。"""
    svc = WorkflowService(db_session)
    result = await svc.get_today_workflow()
    assert result is None


@pytest.mark.asyncio
async def test_get_today_workflow_returns_data(db_session):
    """今日有工作流时返回详情。"""
    await _create_workflow(db_session)

    svc = WorkflowService(db_session)
    result = await svc.get_today_workflow()
    assert result is not None
    assert result["workflow_id"] == "wf-20260708-0001"
    assert result["status"] == "running"
    assert "steps" in result


@pytest.mark.asyncio
async def test_get_today_workflow_returns_latest(db_session):
    """今日多条工作流时返回最新一条（按 started_at 倒序）。"""
    # 同一日期创建两条
    wf1 = Workflow(
        id="wf-a",
        episode_date=date.today(),
        source=WorkflowSource.cron,
        status=WorkflowStatus.success,
        started_at=datetime(2026, 7, 8, 5, 0, 0),
    )
    wf2 = Workflow(
        id="wf-b",
        episode_date=date.today(),
        source=WorkflowSource.manual,
        status=WorkflowStatus.running,
        started_at=datetime(2026, 7, 8, 6, 0, 0),  # 更晚
    )
    db_session.add_all([wf1, wf2])
    await db_session.commit()

    svc = WorkflowService(db_session)
    result = await svc.get_today_workflow()
    # 返回 started_at 更晚的 wf-b
    assert result["workflow_id"] == "wf-b"


@pytest.mark.asyncio
async def test_list_workflows_pagination(db_session):
    """list_workflows 分页：total 与每页条数正确。"""
    for i in range(5):
        await _create_workflow(
            db_session, wid=f"wf-{i}", episode_date=date(2026, 7, i + 1)
        )

    svc = WorkflowService(db_session)
    page1 = await svc.list_workflows(page=1, size=2)
    assert page1["total"] == 5
    assert len(page1["list"]) == 2

    page3 = await svc.list_workflows(page=3, size=2)
    assert len(page3["list"]) == 1


@pytest.mark.asyncio
async def test_get_workflow_detail_with_steps(db_session):
    """get_workflow_detail 返回详情含步骤列表。"""
    await _create_workflow(db_session, wid="wf-detail")
    await _add_step(db_session, "wf-detail", WorkflowStepName.crawl, WorkflowStepStatus.success)
    await _add_step(db_session, "wf-detail", WorkflowStepName.rewrite, WorkflowStepStatus.running)

    svc = WorkflowService(db_session)
    detail = await svc.get_workflow_detail("wf-detail")
    assert detail["workflow_id"] == "wf-detail"
    assert len(detail["steps"]) == 2
    # 步骤按 id 排序
    assert detail["steps"][0]["name"] == "crawl"
    assert detail["steps"][0]["status"] == "success"
    assert detail["steps"][1]["name"] == "rewrite"
    assert detail["steps"][1]["status"] == "running"


@pytest.mark.asyncio
async def test_get_workflow_detail_not_found_raises(db_session):
    """workflow_id 不存在时抛 NotFoundError。"""
    svc = WorkflowService(db_session)
    with pytest.raises(NotFoundError):
        await svc.get_workflow_detail("not-exist")


@pytest.mark.asyncio
async def test_list_workflows_empty(db_session):
    """无工作流时返回空列表。"""
    svc = WorkflowService(db_session)
    result = await svc.list_workflows(page=1, size=10)
    assert result == {"total": 0, "list": []}
