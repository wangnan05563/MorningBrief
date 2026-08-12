"""C 端课程进度聚合路由（FR-MC-04 / FR-MC-05 P1）。

GET /api/v1/courses/{channel_id}/progress
返回 { total, learned, percent, last_chapter_id, last_position }。
基于该频道已发布章节（episode）总数 × 用户 PlayProgress 完成标记聚合。

设计要点（R2 修正）：
- 仅接受课程类频道（channel_type ∈ {course, audiobook}）；传入其他类型（如 news）
  或不存在的频道一律 404，避免被误用为「通用进度接口」而与命名/语义偏离。
- total = 频道下 status=published 的 episode 数（即课程章节总数）
- learned = 用户对该频道章节中「已学完」的数量；判定与前端 COURSE_COMPLETE_RATIO=0.95
  保持一致：PlayProgress.completed==1 或 position/duration ≥ 0.95
- 无章节 / 无进度时安全返回全 0，不报错
- 仅聚合本人进度（PlayProgress.user_id），与播放内核 PlayProgress 表同源
- last_chapter_id / last_position 取用户最近一次有进度的章节（updated_at 倒序），
  供前端「继续学习」直接定位；无进度时为 null / 0
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserPayload, get_current_user
from app.core.exceptions import NotFoundError
from app.core.response import success
from app.database import get_db
from app.models import Channel, Episode, PlayProgress
from app.models.episode import EpisodeStatus

router = APIRouter(prefix="/api/v1/courses", tags=["C端-课程"])

# 章节「已学完」判定阈值：与前端 miniprogram COURSE_COMPLETE_RATIO 保持一致
_COMPLETE_RATIO = 0.95


@router.get("/{channel_id}/progress")
async def get_course_progress(
    channel_id: int,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """课程学习进度聚合（FR-MC-04 / FR-MC-05 P1）。

    返回该课程频道的学习完成度。前端课程主页 / 学习中心首屏读此接口获取精确进度，
    播放结束后再拉一次刷新；无后端聚合时前端回退纯本地聚合（MVP 可接受）。

    R2 修正：仅服务课程类频道（course/audiobook）。传 news 等其它类型或不存在频道，
    一律作为 NotFoundError（HTTP 404）返回，明确接口语义边界。
    """
    # 频道存在性 + 类型校验（R2 修正：拒绝非课程类频道）
    ch = (
        await db.execute(select(Channel).where(Channel.id == channel_id))
    ).scalar_one_or_none()
    if ch is None:
        raise NotFoundError("频道不存在")
    if ch.channel_type not in ("course", "audiobook"):
        raise NotFoundError("该频道不是课程类频道，无法获取课程进度")

    # 该频道已发布章节总数
    total = (
        await db.execute(
            select(func.count(Episode.id)).where(
                Episode.channel_id == channel_id,
                Episode.status == EpisodeStatus.published,
            )
        )
    ).scalar() or 0

    if total == 0:
        return success(data={
            "total": 0,
            "learned": 0,
            "percent": 0,
            "last_chapter_id": None,
            "last_position": 0,
        })

    # 用户在该频道各章节的进度（按最近更新倒序，便于取 last + 判定完成态）
    rows = (
        await db.execute(
            select(
                Episode.id,
                PlayProgress.completed,
                PlayProgress.position,
                PlayProgress.duration,
                PlayProgress.updated_at,
            )
            .join(PlayProgress, PlayProgress.episode_id == Episode.id)
            .where(
                Episode.channel_id == channel_id,
                Episode.status == EpisodeStatus.published,
                PlayProgress.user_id == user.user_id,
            )
            .order_by(PlayProgress.updated_at.desc())
        )
    ).all()

    learned = 0
    last_chapter_id = None
    last_position = 0
    for ep_id, completed, position, duration, _updated_at in rows:
        ratio = (position / duration) if duration else 0.0
        if completed == 1 or ratio >= _COMPLETE_RATIO:
            learned += 1
        if last_chapter_id is None:
            last_chapter_id = ep_id
            last_position = position or 0

    percent = round(learned / total * 100) if total else 0
    return success(data={
        "total": total,
        "learned": learned,
        "percent": percent,
        "last_chapter_id": last_chapter_id,
        "last_position": last_position,
    })
