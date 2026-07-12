"""B 端频道管理路由。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache as cache_manager
from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.response import success
from app.database import get_db
from app.services.channel_service import ChannelService, _TTL_CHANNELS

router = APIRouter(prefix="/admin/api/v1/channels", tags=["B端-频道管理"])


class ChannelCreateRequest(BaseModel):
    """新增频道请求体。"""
    name: str
    description: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("频道名称不能为空")
        if len(v) > 64:
            raise ValueError("频道名称不能超过 64 字符")
        return v


class ChannelUpdateRequest(BaseModel):
    """修改频道请求体。"""
    name: str | None = None
    description: str | None = None
    is_active: int | None = None


@router.get("")
async def list_channels(
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """查询频道列表。admin + operator 均可查看。

    cache-aside：频道数据变更频率极低，缓存 5 分钟减少 DB 查询。
    """
    cache_key = f"channels:list:{'active' if active_only else 'all'}"
    cached = await cache_manager.get(cache_key)
    if cached:
        return success(data=cached)

    svc = ChannelService(db)
    channels = await svc.list_channels(active_only=active_only)
    data = [
        {
            "id": ch.id,
            "name": ch.name,
            "description": ch.description,
            "is_active": ch.is_active,
            "created_at": ch.created_at.isoformat() if ch.created_at else None,
            "updated_at": ch.updated_at.isoformat() if ch.updated_at else None,
        }
        for ch in channels
    ]
    await cache_manager.set(cache_key, data, ttl=_TTL_CHANNELS)
    return success(data=data)


@router.post("")
async def create_channel(
    req: ChannelCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """新增频道。仅 admin。"""
    svc = ChannelService(db)
    try:
        channel = await svc.create_channel(name=req.name, description=req.description)
    except ValueError as e:
        from app.core.response import error
        return error(code=400, message=str(e))
    return success(data={
        "id": channel.id,
        "name": channel.name,
        "description": channel.description,
        "is_active": channel.is_active,
    })


@router.put("/{channel_id}")
async def update_channel(
    channel_id: int,
    req: ChannelUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """修改频道。仅 admin。"""
    svc = ChannelService(db)
    try:
        channel = await svc.update_channel(
            channel_id=channel_id,
            name=req.name,
            description=req.description,
            is_active=req.is_active,
        )
    except ValueError as e:
        from app.core.response import error
        return error(code=400, message=str(e))
    return success(data={
        "id": channel.id,
        "name": channel.name,
        "description": channel.description,
        "is_active": channel.is_active,
    })


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """删除频道。仅 admin。关联工作流的 channel_id 自动置 NULL。"""
    svc = ChannelService(db)
    try:
        await svc.delete_channel(channel_id=channel_id)
    except ValueError as e:
        from app.core.response import error
        return error(code=404, message=str(e))
    return success(data={"deleted": True})
