"""C 端用户路由：收听统计 + 头像昵称编辑。

设计原因：
- 收听统计基于 play_progress 表聚合查询（每用户每节目一条 upsert 记录），
  不用 play_log 表是因为 play_log 是落库批写的历史日志，position/duration 语义
  为节目总时长而非实际收听时长，sum(duration) 会严重偏高
- 头像昵称编辑使用微信新版 chooseAvatar + nickname 能力，旧版 getUserProfile 已废弃
- 头像上传由前端调用 wx.uploadFile 上传到后端，后端转存或直接存 URL
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserPayload, get_current_user
from app.core.exceptions import BizError
from app.core.response import success
from app.database import get_db
from app.models import User, PlayProgress, Favorite

router = APIRouter(prefix="/api/v1/users", tags=["C端-用户"])


@router.get("/stats")
async def get_user_stats(
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户收听统计：累计收听时长、累计收听期数、完播期数、收藏数。

    基于 play_progress 表聚合：每用户每节目仅一条记录（upsert），
    position 为最后播放位置，sum(position) 近似实际收听时长。
    """
    # 累计收听时长（秒）= sum(position)；累计收听期数 = count(episode_id)
    play_result = await db.execute(
        select(
            func.coalesce(func.sum(PlayProgress.position), 0),
            func.count(PlayProgress.episode_id),
        ).where(PlayProgress.user_id == user.user_id)
    )
    total_listen_seconds, total_listen_episodes = play_result.one()

    # 完播期数：completed=1 的记录数（每节目仅一条，无需 distinct）
    completed_result = await db.execute(
        select(func.count(PlayProgress.id)).where(
            PlayProgress.user_id == user.user_id,
            PlayProgress.completed == 1,
        )
    )
    completed_episodes = completed_result.scalar() or 0

    # 收藏数：Favorite.user_id 存的是 openid 字符串，需先查用户 openid
    user_result = await db.execute(select(User.openid).where(User.id == user.user_id))
    openid = user_result.scalar_one_or_none()
    favorite_count = 0
    if openid is not None:
        fav_result = await db.execute(
            select(func.count(Favorite.id)).where(Favorite.user_id == openid)
        )
        favorite_count = fav_result.scalar() or 0

    return success(data={
        "total_listen_seconds": int(total_listen_seconds or 0),
        "total_listen_episodes": int(total_listen_episodes or 0),
        "completed_episodes": int(completed_episodes),
        "favorite_count": int(favorite_count),
    })


class UpdateProfileRequest(BaseModel):
    """更新用户资料请求体。"""
    nickname: str | None = Field(None, max_length=64)
    avatar: str | None = Field(None, max_length=512)


@router.put("/profile")
async def update_profile(
    req: UpdateProfileRequest,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新用户头像与昵称。

    头像由前端 wx.uploadFile 上传到后端 /upload 接口后返回 URL，
    或直接存微信临时链接（短期有效，建议转存 COS）。
    """
    result = await db.execute(select(User).where(User.id == user.user_id))
    user_obj = result.scalar_one_or_none()
    if user_obj is None:
        raise BizError(code=1002, message="用户不存在")

    if req.nickname is not None:
        user_obj.nickname = req.nickname.strip() or user_obj.nickname
    if req.avatar is not None:
        user_obj.avatar = req.avatar.strip()

    await db.commit()

    return success(data={
        "success": True,
        "user": {
            "nickname": user_obj.nickname,
            "avatar": user_obj.avatar,
        },
    })
