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
# v2：本次 cover_url/icon_url 改为绝对 URL（小程序 <image> 需完整地址）+ 新增 icon_url 下发，
# 旧缓存存的是相对路径需失效
_CHANNELS_CACHE_KEY = "api:channels:list_active:v2"
_CHANNELS_CACHE_TTL = 60


def _abs_asset_url(path: str | None) -> str | None:
    """频道静态资源（封面/图标）相对路径 → 绝对 URL。

    小程序 <image> 不解析相对路径（会当包内路径加载失败），必须拼完整域名；
    复用 ContentService 的音频同源 base（隧道 public_url 带 /news 前缀，Funnel 剥离后命中静态挂载）。
    """
    if not path:
        return None
    if path.startswith("http"):
        return path
    from app.services.content_service import ContentService
    return ContentService._resolve_audio_base_url() + path


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
            # 多频道适配 M2 数据契约（SRS §6.1）：类型/标签/封面/风险提示等级
            # 用 getattr 兜底，避免存量库尚未迁移列时整条接口报错
            # T00730：icon_url 随列表下发（小程序频道卡展示）；封面/图标统一绝对 URL
            "channel_type": getattr(ch, "channel_type", "news") or "news",
            "type_label": getattr(ch, "type_label", None),
            "cover_url": _abs_asset_url(getattr(ch, "cover_url", None)),
            "icon_url": _abs_asset_url(getattr(ch, "icon_url", None)),
            "disclaimer_level": getattr(ch, "disclaimer_level", "none") or "none",
            "selection_strategy": getattr(ch, "selection_strategy", None),
        }
        for ch in channels
    ]

    payload = {"list": list_data}
    # 写入缓存供后续请求复用
    await cache.set(_CHANNELS_CACHE_KEY, payload, ttl=_CHANNELS_CACHE_TTL)
    return success(data=payload)
