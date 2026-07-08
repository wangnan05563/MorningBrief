"""C 端播放进度路由。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserPayload, get_current_user
from app.core.response import success
from app.database import get_db
from app.services.play_service import PlayService

router = APIRouter(prefix="/api/v1/playlogs", tags=["C端-播放进度"])


class ProgressRequest(BaseModel):
    """播放进度上报请求体。

    position/duration 单位为秒；completed 用于触发收听完成统计。
    """
    episode_id: int
    position: int
    duration: int
    completed: bool = False


@router.post("/progress")
async def report_progress(
    req: ProgressRequest,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = PlayService(db)
    await svc.report_progress(
        user_id=user.user_id,
        episode_id=req.episode_id,
        position=req.position,
        duration=req.duration,
        completed=req.completed,
    )
    return success(data={"success": True})


@router.get("/progress/{episode_id}")
async def get_progress(
    episode_id: int,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = PlayService(db)
    # 无进度记录返回 None，前端按未播放处理
    data = await svc.get_progress(user.user_id, episode_id)
    return success(data=data)
