"""C 端播放进度路由。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserPayload, get_current_user
from app.core.exceptions import NotFoundError
from app.core.response import success
from app.database import get_db
from app.services.play_service import PlayService
from app.models import PlayLog, Episode, EpisodeStatus

router = APIRouter(prefix="/api/v1/playlogs", tags=["C端-播放进度"])

# 单条音频最长 24 小时（86400 秒），超过视为异常值
_MAX_AUDIO_SECONDS = 24 * 3600


class ProgressRequest(BaseModel):
    """播放进度上报请求体。

    position/duration 单位为秒；completed 用于触发收听完成统计。
    listened_seconds 为本次上报周期内实际收听时长增量（秒），用于累计用户总收听时长。
    所有数值字段加边界约束：前端 Math.floor 后仍可能传负数或超大值，
    后端必须拦截避免脏数据落库。
    """

    episode_id: int = Field(..., gt=0)
    position: int = Field(..., ge=0, le=_MAX_AUDIO_SECONDS)
    duration: int = Field(..., ge=0, le=_MAX_AUDIO_SECONDS)
    completed: bool = False
    # 本次上报周期内实际收听时长增量（秒）：前端计算 currentTime - lastReportedPosition
    # 后端累加到 User.total_listen_duration，避免 sum(position) 语义错误（upsert 覆盖非累加）
    listened_seconds: int = Field(0, ge=0, le=_MAX_AUDIO_SECONDS)

    @model_validator(mode="after")
    def _clamp_position_to_duration(self) -> "ProgressRequest":
        """position 超出 duration 时截断，而非拒绝上报。

        为什么用截断而非报错：前端 onEnded 回调上报时 audioManager.duration
        可能因流式加载未填准，position 略大于 duration 是常见情况，直接 400
        会导致完播记录丢失。截断后落库的是合理值，不影响统计。
        """
        if self.duration > 0 and self.position > self.duration:
            self.position = self.duration
        return self


async def _get_published_episode(db: AsyncSession, episode_id: int) -> Episode:
    """查询节目是否存在且已发布，否则抛 NotFoundError。

    为什么在路由层校验而非 service 层：
    ① service 层 report_progress/get_progress 主要职责是写读进度，
       不应承担节目状态校验（单一职责）；
    ② 路由层校验后可直接返回 HTTP 404，避免 service 内嵌异常耦合 HTTP 语义。
    """
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    ep = result.scalar_one_or_none()
    if ep is None:
        raise NotFoundError("节目不存在")
    if ep.status != EpisodeStatus.published.value:
        raise NotFoundError("节目不存在或已下线")
    return ep


@router.post("/progress")
async def report_progress(
    req: ProgressRequest,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # 先校验节目存在且已发布，避免脏进度记录入库
    await _get_published_episode(db, req.episode_id)
    svc = PlayService(db)
    await svc.report_progress(
        user_id=user.user_id,
        episode_id=req.episode_id,
        position=req.position,
        duration=req.duration,
        completed=req.completed,
        listened_seconds=req.listened_seconds,
    )
    return success()


@router.get("/progress/{episode_id}")
async def get_progress(
    episode_id: int,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # 校验节目存在且已发布：未发布节目查询进度无业务意义
    await _get_published_episode(db, episode_id)
    svc = PlayService(db)
    # 无进度记录返回 None，前端按未播放处理
    data = await svc.get_progress(user.user_id, episode_id)
    return success(data=data)


@router.get("/recent")
async def get_recent_playlogs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    channel_id: int | None = Query(None, gt=0, description="按频道过滤，不传则返回全部"),
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """最近播放记录：按 played_at 倒序，关联 episode 展示标题与进度。

    用于"我的"页面"最近播放"列表，点击可断点续播。
    channel_id 为可选参数，传入时仅返回该频道的播放记录。
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
    # channel_id 过滤加在外层 JOIN Episode 之后：子查询保持按用户聚合不变，
    # 外层过滤确保结果与 count 口径一致
    base_query = (
        select(PlayLog, Episode)
        .join(Episode, PlayLog.episode_id == Episode.id)
        .join(
            subq,
            (PlayLog.episode_id == subq.c.episode_id)
            & (PlayLog.played_at == subq.c.latest_played_at),
        )
        .where(PlayLog.user_id == user.user_id)
    )
    if channel_id is not None:
        base_query = base_query.where(Episode.channel_id == channel_id)
    base_query = base_query.order_by(PlayLog.played_at.desc()).offset(offset).limit(size)
    result = await db.execute(base_query)
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
    # 与 list 同样 INNER JOIN Episode：episode 被物理删除的播放记录不计入总数，
    # 保证 total 与 list 口径一致，避免前端分页出现空页
    count_query = (
        select(func.count(func.distinct(PlayLog.episode_id)))
        .join(Episode, PlayLog.episode_id == Episode.id)
        .where(PlayLog.user_id == user.user_id)
    )
    if channel_id is not None:
        count_query = count_query.where(Episode.channel_id == channel_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return success(data={"total": total, "list": list_data})

