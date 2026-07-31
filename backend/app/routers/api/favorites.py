"""C 端收藏路由。

设计原因：
- Favorite 模型 user_id 字段为 openid 字符串（与历史 SCF/COS 路径对齐），
  但鉴权依赖返回的是 User.id（int），需在此转换：用 user.openid 作为 favorite.user_id
- 收藏列表仅返回 episode_id 与时间，前端需另调 /episodes/{id} 拼详情，
  避免本接口做 N+1 联表查询
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserPayload, get_current_user, get_optional_user
from app.core.exceptions import BizError, NotFoundError
from app.core.response import success
from app.database import get_db
from app.models import Favorite, Episode, EpisodeStatus
from app.services.user_service import get_user_openid

router = APIRouter(prefix="/api/v1/favorites", tags=["C端-收藏"])


class FavoriteRequest(BaseModel):
    """添加收藏请求体。"""
    episode_id: int


@router.get("")
async def list_favorites(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """收藏列表分页：返回 episode_id 与收藏时间，前端按需拉详情。"""
    openid = await get_user_openid(db, user.user_id)

    count_result = await db.execute(
        select(func.count(Favorite.id)).where(Favorite.user_id == openid)
    )
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    result = await db.execute(
        select(Favorite)
        .where(Favorite.user_id == openid)
        .order_by(Favorite.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    favorites = result.scalars().all()

    episode_ids = [f.episode_id for f in favorites]
    episodes_map = {}
    if episode_ids:
        ep_result = await db.execute(
            select(Episode).where(
                Episode.id.in_(episode_ids),
                Episode.status == EpisodeStatus.published,
            )
        )
        for ep in ep_result.scalars().all():
            episodes_map[ep.id] = ep

    list_data = [
        {
            "episode_id": f.episode_id,
            "favorited_at": f.created_at.isoformat() if f.created_at else None,
            "title": episodes_map[f.episode_id].title if f.episode_id in episodes_map else None,
            "date": episodes_map[f.episode_id].date.isoformat() if f.episode_id in episodes_map else None,
            "duration": episodes_map[f.episode_id].duration if f.episode_id in episodes_map else None,
            "available": f.episode_id in episodes_map,
        }
        for f in favorites
    ]

    return success(data={"total": total, "list": list_data})


@router.post("")
async def add_favorite(
    req: FavoriteRequest,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加收藏：幂等，已收藏则直接返回成功。"""
    openid = await get_user_openid(db, user.user_id)

    ep_result = await db.execute(
        select(Episode).where(
            Episode.id == req.episode_id,
            Episode.status == EpisodeStatus.published,
        )
    )
    if ep_result.scalar_one_or_none() is None:
        raise NotFoundError("节目不存在或未发布")

    existing = await db.execute(
        select(Favorite).where(
            Favorite.user_id == openid,
            Favorite.episode_id == req.episode_id,
        )
    )
    fav = existing.scalar_one_or_none()
    if fav:
        return success(data={"success": True, "favorite_id": fav.id, "already_favorited": True})

    new_fav = Favorite(user_id=openid, episode_id=req.episode_id)
    db.add(new_fav)
    await db.commit()
    await db.refresh(new_fav)
    return success(data={"success": True, "favorite_id": new_fav.id, "already_favorited": False})


@router.delete("/{episode_id}")
async def remove_favorite(
    episode_id: int,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消收藏：幂等，不存在也返回成功。"""
    openid = await get_user_openid(db, user.user_id)

    await db.execute(
        delete(Favorite).where(
            Favorite.user_id == openid,
            Favorite.episode_id == episode_id,
        )
    )
    await db.commit()
    return success(data={"success": True})


@router.get("/check/{episode_id}")
async def check_favorite(
    episode_id: int,
    user: UserPayload | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """查询某节目是否已收藏（详情页按钮态用）。

    无需认证：未登录时始终返回 favorited=false。
    """
    if user is None:
        return success(data={"favorited": False})

    openid = await get_user_openid(db, user.user_id)

    result = await db.execute(
        select(Favorite.id).where(
            Favorite.user_id == openid,
            Favorite.episode_id == episode_id,
        )
    )
    fav_id = result.scalar_one_or_none()
    return success(data={"favorited": fav_id is not None})
