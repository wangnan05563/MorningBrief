"""C 端频道路由。

无需认证：频道列表对所有用户公开，订阅状态在未登录时返回 false。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.database import get_db
from app.models import Channel

router = APIRouter(prefix="/api/v1/channels", tags=["C端-频道"])


@router.get("")
async def list_channels(
    db: AsyncSession = Depends(get_db),
):
    """频道列表：仅返回启用频道，不带订阅状态（未登录场景）。"""
    result = await db.execute(
        select(Channel)
        .where(Channel.is_active == 1)
        .order_by(Channel.id.asc())
    )
    channels = result.scalars().all()

    list_data = [
        {
            "id": ch.id,
            "name": ch.name,
            "description": ch.description or "",
            "is_subscribed": False,
        }
        for ch in channels
    ]

    return success(data={"list": list_data})
