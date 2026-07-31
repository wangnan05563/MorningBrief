"""B 端审核路由。"""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin
from app.core.response import success
from app.database import get_db
from app.models import AuditLog
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


class BatchActionRequest(BaseModel):
    """批量审核操作请求体。

    review_ids 上限由 service 层 BATCH_MAX_SIZE 控制；
    action=reject 时必须传 reason。
    """
    review_ids: List[int]
    action: str
    reason: Optional[str] = None


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


@router.post("/batch-action")
async def batch_handle_action(
    req: BatchActionRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """批量审核操作。

    路径 /batch-action 必须在 /{review_id}/action 之前声明，
    否则 FastAPI 会把 batch-action 当成 review_id 解析。
    """
    svc = ReviewService(db)
    batch_result = await svc.batch_handle_action(
        review_ids=req.review_ids,
        action=req.action,
        reviewer_id=admin.admin_id,
        reviewer_name=admin.username,
        reason=req.reason,
    )

    # 仅 approve 触发节目发布；逐条发布，失败不阻塞其他条目
    published: list[dict] = []
    publish_failed: list[dict] = []
    if req.action == "approve":
        content_svc = ContentService(db)
        for item in batch_result["succeeded"]:
            if not item.get("need_publish"):
                continue
            try:
                episode_id = await content_svc.publish_episode(
                    workflow_id=item["workflow_id"],
                    review_id=item["id"],
                )
                published.append({"id": item["id"], "episode_id": episode_id})
            except Exception as exc:
                # 发布失败记录原因，不影响已通过的审核状态
                publish_failed.append({"id": item["id"], "reason": str(exc)})

    batch_result["published"] = published
    batch_result["publish_failed"] = publish_failed
    # 审计日志：批量审核影响多个节目上线，记录批量 ID 与每条结果便于追溯
    db.add(AuditLog(
        category="review",
        action=f"batch_{req.action}",
        target="reviews",
        operator=admin.username,
        detail=json.dumps({
            "review_ids": req.review_ids,
            "reason": req.reason,
            "succeeded": batch_result.get("succeeded", []),
            "failed": batch_result.get("failed", []),
            "published": published,
            "publish_failed": publish_failed,
        }, ensure_ascii=False),
    ))
    await db.commit()
    return success(data=batch_result)


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
    # 审计日志：审核操作直接决定节目是否上线，记录审核人/动作/原因便于事后追溯
    db.add(AuditLog(
        category="review",
        action=req.action,
        target=str(review_id),
        operator=admin.username,
        detail=json.dumps({
            "review_id": review_id,
            "action": req.action,
            "reason": req.reason,
            "segment_id": req.segment_id,
            "episode_id": episode_id,
            "workflow_id": result.get("workflow_id"),
        }, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"success": True, "episode_id": episode_id})
