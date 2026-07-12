"""B 端用户反馈管理路由。

接口：
- GET /admin/api/v1/feedbacks：分页查询反馈列表（支持按 status 筛选）
- PUT /admin/api/v1/feedbacks/{id}/status：更新反馈状态

权限：仅 admin 角色可访问（require_admin）。
反馈数据由 FeedbackSyncService 每小时从 COS 同步到 SQLite feedback 表。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, require_admin
from app.core.response import error, success
from app.database import get_db
from app.models.feedback import Feedback

router = APIRouter(prefix="/admin/api/v1/feedbacks", tags=["B端-用户反馈"])

# 允许的状态值白名单：防止前端传入非法状态污染数据
_ALLOWED_STATUS = {"pending", "processed", "resolved"}


class FeedbackStatusUpdateRequest(BaseModel):
    """更新反馈状态请求体。"""
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in _ALLOWED_STATUS:
            raise ValueError(f"状态值非法，允许值: {sorted(_ALLOWED_STATUS)}")
        return v


@router.get("")
async def list_feedbacks(
    status: Optional[str] = Query(None, description="按状态筛选：pending/processed/resolved"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """分页查询反馈列表。

    支持按 status 筛选；按 created_at 倒序排列（最新反馈优先）。
    """
    # 基础查询条件
    conditions = []
    if status:
        if status not in _ALLOWED_STATUS:
            return error(code=400, message=f"状态值非法，允许值: {sorted(_ALLOWED_STATUS)}")
        conditions.append(Feedback.status == status)

    # 总数统计（分页元数据）
    count_stmt = select(func.count()).select_from(Feedback)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one()

    # 分页列表查询：created_at 倒序，NULL 值排最后（旧数据兼容）
    list_stmt = select(Feedback)
    if conditions:
        list_stmt = list_stmt.where(*conditions)
    list_stmt = list_stmt.order_by(
        Feedback.created_at.desc().nullslast()
    ).offset((page - 1) * size).limit(size)
    result = await db.execute(list_stmt)
    feedbacks = result.scalars().all()

    return success(data={
        "total": total,
        "list": [_to_dict(fb) for fb in feedbacks],
    })


@router.put("/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: str,
    req: FeedbackStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """更新反馈状态。

    状态流转：pending → processed → resolved（非强制顺序，允许跳转）。
    """
    fb = await db.get(Feedback, feedback_id)
    if fb is None:
        return error(code=404, message=f"反馈不存在: {feedback_id}")

    fb.status = req.status
    await db.commit()
    await db.refresh(fb)

    return success(data=_to_dict(fb))


def _to_dict(fb: Feedback) -> dict:
    """序列化 Feedback ORM 对象为响应字典。"""
    return {
        "id": fb.id,
        "user_id": fb.user_id,
        "category": fb.category,
        "content": fb.content,
        "contact": fb.contact,
        "status": fb.status,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
        "synced_at": fb.synced_at.isoformat() if fb.synced_at else None,
    }
