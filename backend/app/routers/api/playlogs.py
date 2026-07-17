"""C 端播放进度路由。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserPayload, get_current_user
from app.core.response import success
from app.database import get_db
from app.services.play_service import PlayService
from app.models import PlayLog, Episode, EpisodeStatus

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


@router.get("/recent")
async def get_recent_playlogs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """最近播放记录：按 played_at 倒序，关联 episode 展示标题与进度。

    用于"我的"页面"最近播放"列表，点击可断点续播。
    """
    offset = (page - 1) * size

    # 子查询：每个 episode 取最新一条播放记录（避免同一节目多次播放占满列表）
    subq = (
        select(
            PlayLog.episode_id,
            func.max(PlayLog.played_at).label("latest_played_at"),
        )
        .where(PlayLog.user_id == user.user_id)
        .group_by(PlayLog.episode_id)
        .subquery()
    )

    # 关联 Episode 取标题等信息
    result = await db.execute(
        select(PlayLog, Episode)
        .join(Episode, PlayLog.episode_id == Episode.id)
        .join(
            subq,
            (PlayLog.episode_id == subq.c.episode_id)
            & (PlayLog.played_at == subq.c.latest_played_at),
        )
        .where(PlayLog.user_id == user.user_id)
        .order_by(PlayLog.played_at.desc())
        .offset(offset)
        .limit(size)
    )
    rows = result.all()

    list_data = [
        {
            "episode_id": log.episode_id,
            "title": ep.title,
            "date": ep.date.isoformat() if ep.date else None,
            "duration": ep.duration,
            "position": log.position or 0,
            "completed": bool(log.completed),
            "played_at": log.played_at.isoformat() if log.played_at else None,
        }
        for log, ep in rows
    ]

    # 总数（去重 episode 数）
    count_result = await db.execute(
        select(func.count(func.distinct(PlayLog.episode_id))).where(
            PlayLog.user_id == user.user_id
        )
    )
    total = count_result.scalar() or 0

    return success(data={"total": total, "list": list_data})

