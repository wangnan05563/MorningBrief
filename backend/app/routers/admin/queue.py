"""B 端队列管理路由。"""
import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.response import success, error
from app.database import get_db
from app.models import AuditLog
from app.services.queue_service import QueueService

router = APIRouter(prefix="/admin/api/v1/queue", tags=["B端-队列管理"])


class PriorityUpdateRequest(BaseModel):
    """修改优先级请求体。"""
    priority: int = Field(ge=0, le=10)


class ConfigUpdateRequest(BaseModel):
    """更新队列配置请求体。"""
    execution_mode: str = Field(pattern="^(serial|parallel)$")
    max_concurrent: int = Field(ge=1, le=5)


class BatchDeleteTasksRequest(BaseModel):
    """批量删除队列任务请求体。复用 workflows 批量删除的 ID 约束语义。"""
    workflow_ids: list[str] = Field(
        ..., min_length=1, max_length=100, description="待删除任务(workflow) ID 列表"
    )

    @field_validator("workflow_ids")
    @classmethod
    def normalize_ids(cls, v: list[str]) -> list[str]:
        """去空白 + 去重 + 拒绝空串，保证下游 service 拿到规范 ID 列表。"""
        cleaned = [s.strip() for s in v if s and s.strip()]
        if not cleaned:
            raise ValueError("workflow_ids 不能全为空")
        # 去重：同一 ID 重复传入无意义且会放大删除范围
        unique = list(dict.fromkeys(cleaned))
        if len(unique) != len(cleaned):
            raise ValueError("workflow_ids 包含重复 ID")
        return unique


@router.get("/stats")
async def get_queue_stats(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """队列统计。admin + operator 均可查看。"""
    svc = QueueService(db)
    data = await svc.get_queue_stats()
    return success(data=data)


@router.get("/tasks")
async def list_queue_tasks(
    status: str | None = Query(None),
    channel_id: int | None = Query(None),
    priority: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort_by: str | None = Query(
        None,
        description="排序字段：channel_name/priority/status/started_at。留空走默认排序",
    ),
    sort_order: str | None = Query(
        None,
        pattern="^(asc|desc)$",
        description="排序方向：asc/desc。留空走默认排序",
    ),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """队列任务列表。admin + operator 均可查看。

    默认排序：failed 状态最新优先 + started_at 倒序。
    指定 sort_by/sort_order 后按单一字段排序，方向由 sort_order 决定。
    """
    svc = QueueService(db)
    items, total = await svc.list_queue_tasks(
        status=status, channel_id=channel_id, priority=priority,
        page=page, size=size,
        sort_by=sort_by, sort_order=sort_order,
    )
    return success(data={"items": items, "total": total, "page": page, "size": size})


@router.post("/tasks/batch-delete")
async def batch_delete_tasks(
    req: BatchDeleteTasksRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """批量删除队列任务（仅管理员）。

    委托 WorkflowService 执行事务级联删除：running/queued 状态拒绝删除，
    其余状态级联清理 play_log/play_progress → episode → review → script
    → workflow_step → workflow，素材重置为 pending 保留。
    任一 ID 不存在或含运行中/排队中则整批回滚。
    """
    svc = QueueService(db)
    data = await svc.batch_delete_tasks(req.workflow_ids)
    # 审计日志：批量删除为不可恢复的级联删除，记录操作人与目标 ID 便于追溯
    db.add(AuditLog(
        category="queue",
        action="batch_delete",
        target="tasks",
        operator=admin.username,
        detail=json.dumps(
            {"workflow_ids": req.workflow_ids, "result": data}, ensure_ascii=False
        ),
    ))
    await db.commit()
    return success(data=data)


@router.post("/tasks/{workflow_id}/cancel")
async def cancel_task(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """取消排队中任务。仅 admin。"""
    svc = QueueService(db)
    try:
        await svc.cancel_task(workflow_id=workflow_id)
    except ValueError as e:
        return error(code=400, message=str(e))
    # 审计日志：取消任务影响工作流执行顺序，记录操作人便于追溯异常取消
    db.add(AuditLog(
        category="queue",
        action="cancel",
        target=workflow_id,
        operator=admin.username,
        detail=json.dumps({"workflow_id": workflow_id}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"cancelled": True})


@router.put("/tasks/{workflow_id}/priority")
async def update_priority(
    workflow_id: str,
    req: PriorityUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """修改优先级。仅 admin。"""
    svc = QueueService(db)
    try:
        await svc.update_priority(workflow_id=workflow_id, priority=req.priority)
    except ValueError as e:
        return error(code=400, message=str(e))
    # 审计日志：优先级调整影响任务执行顺序，记录新优先级便于追溯排队异常
    db.add(AuditLog(
        category="queue",
        action="update_priority",
        target=workflow_id,
        operator=admin.username,
        detail=json.dumps({"workflow_id": workflow_id, "priority": req.priority}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"updated": True})


@router.post("/tasks/{workflow_id}/retry")
async def retry_task(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """重试失败任务：在原工作流上从最早失败步骤断点续跑。仅 admin。

    保留已成功步骤的产出（爬虫素材/LLM 稿件等），仅重跑失败步骤及其后续步骤。
    不创建新工作流，原工作流 ID 不变。
    """
    from app.core.exceptions import ParamError

    svc = QueueService(db)
    try:
        wf_id = await svc.retry_task(workflow_id=workflow_id)
    except (ValueError, ParamError) as e:
        return error(code=400, message=str(e))
    # 审计日志：重试任务会重新消耗 AI 预算，记录操作人便于事后用量核对
    db.add(AuditLog(
        category="queue",
        action="retry",
        target=wf_id,
        operator=admin.username,
        detail=json.dumps({"workflow_id": wf_id}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"workflow_id": wf_id, "status": "queued"})


@router.get("/config")
async def get_queue_config(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """获取队列配置。admin + operator 均可查看。"""
    svc = QueueService(db)
    data = await svc.get_queue_config()
    return success(data=data)


@router.put("/config")
async def update_queue_config(
    req: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """更新队列配置。仅 admin。配置延迟生效（当前任务完成后重建 Semaphore）。"""
    svc = QueueService(db)
    try:
        await svc.update_queue_config(mode=req.execution_mode, max_concurrent=req.max_concurrent)
    except ValueError as e:
        return error(code=400, message=str(e))
    return success(data={"updated": True})
