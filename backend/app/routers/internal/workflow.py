"""内部工作流接口（同机进程间调用）。

设计说明：这些接口供 APScheduler 或运营后台内部调用，
通过本地回环地址 + 共享密钥签名鉴权（HLD 10.1）。
MVP 阶段简化为仅 localhost 校验。
"""
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.database import get_db
from app.services.content_service import ContentService
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/api/internal/workflow", tags=["内部-工作流"])


async def verify_localhost(request: Request):  # NOSONAR
    """内部接口仅允许 localhost 调用。

    内部接口不经过 JWT 鉴权，必须限制来源 IP 防止外网越权触发工作流。
    """
    client_host = request.client.host if request.client else None
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="仅允许本地调用")


@router.post("/trigger")
async def trigger_workflow(
    episode_date: str = Body(..., embed=True),
    source: str = Body("cron", embed=True),
    _: None = Depends(verify_localhost),
):
    """触发工作流（APScheduler Cron 调用 / 运营后台内部调用）。"""
    from app.services.workflow_scheduler import workflow_scheduler

    target_date = date.fromisoformat(episode_date)
    workflow_id = await workflow_scheduler.trigger_workflow(
        episode_date=target_date,
        source=source,
    )
    return success(data={"workflow_id": workflow_id, "status": "running"})


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """查询工作流状态。"""
    svc = WorkflowService(db)
    data = await svc.get_workflow_detail(workflow_id)
    return success(data=data)


@router.post("/{workflow_id}/publish")
async def publish_workflow(
    workflow_id: str,
    review_id: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_localhost),
):
    """审核通过后发布节目。

    由审核服务在 approve 时内部调用，或由运营后台手动触发。
    """
    svc = ContentService(db)
    episode_id = await svc.publish_episode(workflow_id, review_id)
    return success(data={"episode_id": episode_id, "status": "published"})
