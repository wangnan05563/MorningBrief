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


class TriggerRequest(BaseModel):
    """手动触发请求体。channel_id 可选，携带时使用频道级提示词。"""
    channel_id: int | None = None


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
    req: TriggerRequest,
    admin: AdminPayload = Depends(require_admin),
):
    """手动触发工作流（运营后台调用）。

    支持携带 channel_id，rewrite 步骤据此读取频道级提示词。
    """
    from datetime import date
    from app.services.workflow_scheduler import workflow_scheduler

    workflow_id = await workflow_scheduler.trigger_workflow(
        episode_date=date.today(),
        source="manual",
        channel_id=req.channel_id,
        triggered_by=admin.username,
    )
    return success(data={"workflow_id": workflow_id, "status": "running"})


@router.post("/{workflow_id}/retry")
async def retry_workflow(
    workflow_id: str,
    req: RetryRequest,
    admin: AdminPayload = Depends(require_admin),
):
    """在原工作流上从指定步骤重跑（断点续跑）。

    删除 from_step 及其之后的步骤记录，保留之前的成功步骤，
    重置状态为 queued 后重新入队，_run_workflow 跳过已成功步骤。
    """
    from app.services.workflow_scheduler import workflow_scheduler
    from app.core.exceptions import ParamError
    from app.core.response import error

    try:
        wf_id = await workflow_scheduler.retry_workflow(
            workflow_id, from_step=req.step, triggered_by=admin.username,
        )
    except ParamError as e:
        return error(code=400, message=str(e))
    return success(data={
        "workflow_id": wf_id,
        "retry_step": req.step,
        "status": "queued",
    })
