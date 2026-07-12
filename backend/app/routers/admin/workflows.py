"""B 端工作流路由。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.response import success
from app.database import get_db
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/admin/api/v1/workflows", tags=["B端-工作流"])


class RetryRequest(BaseModel):
    """重跑请求体。step 指定从哪一步重跑，Phase 3 生效。"""
    step: str


class BatchDeleteRequest(BaseModel):
    """批量删除请求体。

    约束 1-100 个 ID 是为了：
    - 下限 1：避免 no-op 调用掩盖上游 bug
    - 上限 100：避免单次事务过大导致长事务/锁表
    """
    workflow_ids: list[str] = Field(..., min_length=1, max_length=100, description="待删除工作流 ID 列表")

    @field_validator("workflow_ids")
    @classmethod
    def normalize_ids(cls, v: list[str]) -> list[str]:
        """去空白 + 去重 + 拒绝空串，保证下游 service 拿到规范 ID 列表。"""
        cleaned = [s.strip() for s in v if s and s.strip()]
        if not cleaned:
            raise ValueError("workflow_ids 不能全为空")
        # 去重：同一 ID 重复传入无意义且会放大删除范围断言
        unique = list(dict.fromkeys(cleaned))
        if len(unique) != len(cleaned):
            raise ValueError("workflow_ids 包含重复 ID")
        return unique


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
    channel_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = WorkflowService(db)
    data = await svc.list_workflows(page=page, size=size, channel_id=channel_id)
    return success(data=data)


# 静态路由必须定义在 /{workflow_id} 之前：FastAPI 按定义顺序匹配，
# 否则 "batch-delete" 会被当作 workflow_id 参数捕获
@router.post("/batch-delete")
async def batch_delete_workflows(
    req: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """批量删除工作流（仅管理员）。

    级联删除 workflow 及其全部关联数据（step/script/material/review/episode/play_log/play_progress）。
    running/queued 状态拒绝删除；任一 ID 不存在或状态非法时整批回滚。
    """
    svc = WorkflowService(db)
    data = await svc.batch_delete_workflows(req.workflow_ids)
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
    """重跑失败的工作流（创建新工作流，断点续跑）。

    scheduler.retry_workflow 内部基于原工作流已完成步骤实现断点续跑，
    无需路由层传递 from_step（step 参数保留前端契约，后续扩展时使用）。
    """
    from app.services.workflow_scheduler import workflow_scheduler
    from app.core.exceptions import ParamError
    from app.core.response import error

    try:
        new_wf_id = await workflow_scheduler.retry_workflow(workflow_id)
    except ParamError as e:
        return error(code=400, message=str(e))
    return success(data={
        "original_workflow_id": workflow_id,
        "new_workflow_id": new_wf_id,
        "retry_step": req.step,
        "status": "queued",
    })
