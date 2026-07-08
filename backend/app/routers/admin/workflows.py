"""B 端工作流路由。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.response import success
from app.database import get_db
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/admin/api/v1/workflows", tags=["B端-工作流"])


class RetryRequest(BaseModel):
    """重跑请求体。step 指定从哪一步重跑，Phase 3 生效。"""
    step: str


@router.get("/today")
async def get_today_workflow(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = WorkflowService(db)
    data = await svc.get_today_workflow()
    return success(data=data)


@router.get("")
async def list_workflows(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = WorkflowService(db)
    data = await svc.list_workflows(page=page, size=size)
    return success(data=data)


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = WorkflowService(db)
    data = await svc.get_workflow_detail(workflow_id=workflow_id)
    return success(data=data)


@router.post("/trigger")
async def trigger_workflow(
    admin: AdminPayload = Depends(require_admin),
):
    """手动触发工作流（运营后台调用）。"""
    from datetime import date
    from app.services.workflow_scheduler import workflow_scheduler

    workflow_id = await workflow_scheduler.trigger_workflow(
        episode_date=date.today(),
        source="manual",
        triggered_by=admin.username,
    )
    return success(data={"workflow_id": workflow_id, "status": "running"})


@router.post("/{workflow_id}/retry")
async def retry_workflow(
    workflow_id: str,
    req: RetryRequest,
    admin: AdminPayload = Depends(require_admin),
):
    """从指定步骤重跑工作流。

    MVP 阶段简化为重新触发完整工作流（保留原 workflow_id 的失败记录供回溯）。
    """
    from datetime import date
    from app.services.workflow_scheduler import workflow_scheduler

    new_wf_id = await workflow_scheduler.trigger_workflow(
        episode_date=date.today(),
        source="manual",
        triggered_by=admin.username,
    )
    return success(data={
        "original_workflow_id": workflow_id,
        "new_workflow_id": new_wf_id,
        "retry_step": req.step,
        "status": "running",
    })
