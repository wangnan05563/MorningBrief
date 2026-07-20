"""C 端节目路由。

V1.3 扩展：
- /today 与 /history 支持 channel_id 可选参数，按频道过滤
- 新增 /search 关键词搜索（标题模糊匹配）
- /{id}/script 响应追加 sources 字段，展示每段新闻来源 URL（版权溯源合规）
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError, NotFoundError
from app.core.response import success
from app.database import get_db
from app.services.content_service import ContentService
from app.models import Episode, EpisodeStatus, Script, Material

router = APIRouter(prefix="/api/v1/episodes", tags=["C端-节目"])


@router.get("/today")
async def get_today_episode(
    channel_id: int | None = Query(None, description="频道 ID，为空则返回今日最新一期"),
    db: AsyncSession = Depends(get_db),
):
    """今日节目：支持按频道过滤，未指定频道时返回最新一期。"""
    svc = ContentService(db)
    data = await svc.get_today_episode(channel_id=channel_id)
    if data is None:
        raise BizError(code=2001, message="今日节目尚未发布")
    return success(data=data)


@router.get("/history")
async def get_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    channel_id: int | None = Query(None, description="频道 ID，为空则返回全部"),
    sort_order: str | None = Query(
        None,
        regex="^(asc|desc)$",
        description="排序方向：asc=日期正序（最旧在前）/ desc=倒序（最新在前，默认）",
    ),
    db: AsyncSession = Depends(get_db),
):
    """历史列表分页：支持按频道过滤与日期排序（任务7）。"""
    svc = ContentService(db)
    data = await svc.get_history(page, size, channel_id=channel_id, sort_order=sort_order)
    return success(data=data)


@router.get("/search")
async def search_episodes(
    keyword: str = Query(..., min_length=1, max_length=64, description="搜索关键词"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """节目搜索：按标题模糊匹配。

    MVP 使用 SQLite LIKE，远期可接入 FTS5 全文检索提升性能与相关性。
    """
    svc = ContentService(db)
    data = await svc.search_episodes(keyword, page, size)
    return success(data=data)


@router.get("/{episode_id}")
async def get_episode(episode_id: int, db: AsyncSession = Depends(get_db)):
    svc = ContentService(db)
    data = await svc.get_episode_by_id(episode_id)
    if data is None:
        raise NotFoundError("节目不存在")
    return success(data=data)


@router.get("/{episode_id}/script")
async def get_script(episode_id: int, db: AsyncSession = Depends(get_db)):
    """节目稿件：响应追加 sources 字段，展示每段新闻来源 URL。

    sources 来自 Segment.material_ids 关联的 Material 表，按 seq 排序。
    """
    svc = ContentService(db)
    data = await svc.get_script(episode_id)
    if data is None:
        raise NotFoundError("稿件不存在")
    return success(data=data)
