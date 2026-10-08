"""C 端收藏路由。

设计原因：
- Favorite 模型 user_id 字段为 openid 字符串（与历史 SCF/COS 路径对齐），
  但鉴权依赖返回的是 User.id（int），需在此转换：用 user.openid 作为 favorite.user_id
- 收藏列表仅返回 episode_id 与时间，前端需另调 /episodes/{id} 拼详情，
  避免本接口做 N+1 联表查询
"""
import os

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache as cache_manager
from app.core.auth import UserPayload, get_current_user, get_optional_user
from app.core.exceptions import BizError, NotFoundError
from app.core.response import success
from app.core.write_gate import write_lock
from app.database import get_db
from app.models import Favorite, Episode, EpisodeStatus, Channel
from app.services.user_service import get_user_openid

router = APIRouter(prefix="/api/v1/favorites", tags=["C端-收藏"])

# T01579：收藏列表缓存 TTL（秒）。收藏变更频率低、列表读放大明显（count+分页+详情补拉
# 三段查询），压测 200 并发下 P95 达 10s；短 TTL + 写路径主动失效即可吸收热点读。
# 置 0 关闭缓存（回归对照/排障用）。
TTL_FAV_LIST = int(os.getenv("FAVORITES_CACHE_TTL_SEC", "60"))


def _fav_list_key(openid: str, page: int, size: int, channel_type: str | None) -> str:
    return f"fav:list:{openid}:{page}:{size}:{channel_type or 'all'}"


class FavoriteRequest(BaseModel):
    """添加收藏请求体。"""
    episode_id: int


@router.get("")
async def list_favorites(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    channel_type: str | None = Query(
        None, description="按频道类型过滤（news/audiobook/course），T00726 二层内容按类型查询"
    ),
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """收藏列表分页：返回 episode_id 与收藏时间，前端按需拉详情。"""
    openid = await get_user_openid(db, user.user_id)

    # T01579：cache-aside（纯 dict 载荷可安全跨请求缓存）
    cache_key = _fav_list_key(openid, page, size, channel_type)
    cached = await cache_manager.get(cache_key) if TTL_FAV_LIST > 0 else None
    if cached is not None:
        return success(data=cached)

    offset = (page - 1) * size
    # T00726：按频道类型过滤——先取该类型的频道 id，再限制收藏的 episode 归属
    fav_query = select(Favorite).where(Favorite.user_id == openid)
    count_stmt = select(func.count(Favorite.id)).where(Favorite.user_id == openid)
    if channel_type:
        type_ids = (
            await db.execute(select(Channel.id).where(Channel.channel_type == channel_type))
        ).scalars().all()
        fav_query = fav_query.join(Episode, Favorite.episode_id == Episode.id).where(
            Episode.channel_id.in_(type_ids)
        )
        count_stmt = count_stmt.join(Episode, Favorite.episode_id == Episode.id).where(
            Episode.channel_id.in_(type_ids)
        )

    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    result = await db.execute(
        fav_query
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

    data = {"total": total, "list": list_data}
    if TTL_FAV_LIST > 0:
        await cache_manager.set(cache_key, data, ttl=TTL_FAV_LIST)
    return success(data=data)


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
        # 兜底失效：缓存 TTL 窗口内的数据变更（如另一设备取消后重新收藏）保持一致
        await cache_manager.delete_pattern(f"fav:list:{openid}:*")
        return success(data={"success": True, "favorite_id": fav.id, "already_favorited": True})

    new_fav = Favorite(user_id=openid, episode_id=req.episode_id)
    async with write_lock():
        db.add(new_fav)
        await db.commit()
        await db.refresh(new_fav)
    # T01579：写后失效该用户全部列表页缓存
    await cache_manager.delete_pattern(f"fav:list:{openid}:*")
    return success(data={"success": True, "favorite_id": new_fav.id, "already_favorited": False})


@router.delete("/{episode_id}")
async def remove_favorite(
    episode_id: int,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消收藏：幂等，不存在也返回成功。"""
    openid = await get_user_openid(db, user.user_id)

    async with write_lock():
        await db.execute(
            delete(Favorite).where(
                Favorite.user_id == openid,
                Favorite.episode_id == episode_id,
            )
        )
        await db.commit()
    # T01579：写后失效该用户全部列表页缓存
    await cache_manager.delete_pattern(f"fav:list:{openid}:*")
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
