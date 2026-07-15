"""B 端审核路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin
from app.core.response import success
from app.database import get_db
from app.services.content_service import ContentService
from app.services.review_service import ReviewService

router = APIRouter(prefix="/admin/api/v1/reviews", tags=["B端-审核"])


class ActionRequest(BaseModel):
    """审核操作请求体。

    action=replace 时必须传 segment_id 与 reason；
    action=reject 时必须传 reason。校验下沉到 service 层。
    """
    action: str
    reason: Optional[str] = None
    segment_id: Optional[int] = None


@router.get("")
async def list_reviews(
    status: str = Query(None),
    workflow_id: str = Query(None, description="按工作流 ID 过滤"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = ReviewService(db)
    data = await svc.list_reviews(
        status=status, page=page, size=size, workflow_id=workflow_id,
    )
    return success(data=data)


@router.get("/{review_id}")
async def get_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = ReviewService(db)
    data = await svc.get_review_detail(review_id)
    return success(data=data)


@router.post("/{review_id}/action")
async def handle_action(
    review_id: int,
    req: ActionRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = ReviewService(db)
    result = await svc.handle_action(
        review_id=review_id,
        action=req.action,
        reviewer_id=admin.admin_id,
        reviewer_name=admin.username,
        reason=req.reason,
        segment_id=req.segment_id,
    )

    episode_id = None
    # approve 通过后触发节目发布；workflow_id 由 handle_action 直接返回，
    # 避免二次查询 get_review_detail（commit 后再查可能引入不一致）
    if result.get("need_publish"):
        content_svc = ContentService(db)
        episode_id = await content_svc.publish_episode(
            workflow_id=result["workflow_id"],
            review_id=review_id,
        )
        # 节目发布成功后触发 published 通知，让运维群感知节目已上线
        # 通知异常不阻塞发布主流程（sender 内部已捕获）
        try:
            from app.services.notification import get_notification_sender
            sender = get_notification_sender()
            await sender.send_workflow_event(
                "workflow.published", result["workflow_id"],
            )
        except Exception:
            # 通知失败不影响发布结果，仅记录日志
            import logging
            logging.getLogger(__name__).exception(
                "发布通知发送失败 workflow_id=%s", result.get("workflow_id"),
            )
    return success(data={"success": True, "episode_id": episode_id})
