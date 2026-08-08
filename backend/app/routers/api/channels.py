"""C 端频道路由。

无需认证：频道列表对所有用户公开，订阅状态在未登录时返回 false。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache
from app.core.response import success
from app.database import get_db
from app.models import Channel

router = APIRouter(prefix="/api/v1/channels", tags=["C端-频道"])

# 频道列表低频变更（运营手动改），60s 缓存可大幅减少 DB 查询
# 压测显示该接口 P95 达 405ms，加缓存后预期 <20ms
_CHANNELS_CACHE_KEY = "api:channels:list_active"
_CHANNELS_CACHE_TTL = 60


@router.get("")
async def list_channels(
    db: AsyncSession = Depends(get_db),
):
    """频道列表：仅返回启用频道，不带订阅状态（未登录场景）。"""
    # 先查缓存：频道低频变更，命中缓存直接返回，避免 DB 全表扫描
    cached = await cache.get(_CHANNELS_CACHE_KEY)
    if cached is not None:
        return success(data=cached)

    result = await db.execute(
        select(Channel)
        .where(Channel.is_active == 1)
        # 展示顺序：display_order 升序（运营在频道管理后台可控），相等时按 id 兜底。
        # 小程序首页/历史页 tab 直接按此返回顺序渲染，无需改小程序即可调整 tab 顺序。
        .order_by(Channel.display_order.asc(), Channel.id.asc())
    )
    channels = result.scalars().all()

    list_data = [
        {
            "id": ch.id,
            "name": ch.name,
            "description": ch.description or "",
            "is_subscribed": False,
            "display_order": ch.display_order,
        }
        for ch in channels
    ]

    payload = {"list": list_data}
    # 写入缓存供后续请求复用
    await cache.set(_CHANNELS_CACHE_KEY, payload, ttl=_CHANNELS_CACHE_TTL)
    return success(data=payload)
