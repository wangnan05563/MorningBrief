"""C 端反馈路由。

设计原因：
- Feedback 模型 id 字段为 uuid4 hex 字符串（与历史 SCF/COS 路径对齐），
  C 端写入时也生成 uuid4 hex 作为主键
- user_id 用 openid 字符串存储，与 favorites.py 一致
- 管理端已有 /admin/api/v1/feedbacks 查看接口，此处仅负责 C 端写入
"""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserPayload, get_current_user
from app.core.exceptions import BizError
from app.core.response import success
from app.core.timeutil import utcnow_naive
from app.database import get_db
from app.models import Feedback

router = APIRouter(prefix="/api/v1/feedbacks", tags=["C端-反馈"])

# 反馈内容长度约束：与小程序 config.js 对齐，防止前端绕过校验
MIN_CONTENT_LENGTH = 10
MAX_CONTENT_LENGTH = 500
MAX_CONTACT_LENGTH = 50


class FeedbackRequest(BaseModel):
    """用户反馈请求体。"""
    category: str = Field(..., min_length=1, max_length=32)
    content: str = Field(..., min_length=MIN_CONTENT_LENGTH, max_length=MAX_CONTENT_LENGTH)
    contact: str | None = Field(None, max_length=MAX_CONTACT_LENGTH)


async def _get_user_openid(db: AsyncSession, user_id: int) -> str:
    """根据 User.id 查询 openid，作为 feedback.user_id 存储。"""
    from app.models import User
    result = await db.execute(select(User.openid).where(User.id == user_id))
    openid = result.scalar_one_or_none()
    if openid is None:
        raise BizError(code=1002, message="用户不存在")
    return openid


@router.post("")
async def submit_feedback(
    req: FeedbackRequest,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交用户反馈，写入 feedback 表。

    id 用 uuid4 hex，与历史 SCF 端生成的 feedback_id 格式一致，便于管理端统一查看。
    """
    openid = await _get_user_openid(db, user.user_id)

    feedback = Feedback(
        id=uuid.uuid4().hex,
        user_id=openid,
        category=req.category,
        content=req.content.strip(),
        contact=req.contact.strip() if req.contact else None,
        status="pending",
        created_at=utcnow_naive(),
        synced_at=utcnow_naive(),
    )
    db.add(feedback)
    await db.commit()

    return success(data={"success": True, "feedback_id": feedback.id})
