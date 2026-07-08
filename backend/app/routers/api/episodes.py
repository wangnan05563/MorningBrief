"""C 端节目路由。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError, NotFoundError
from app.core.response import success
from app.database import get_db
from app.services.content_service import ContentService

router = APIRouter(prefix="/api/v1/episodes", tags=["C端-节目"])


@router.get("/today")
async def get_today_episode(db: AsyncSession = Depends(get_db)):
    svc = ContentService(db)
    data = await svc.get_today_episode()
    # 今日节目未发布属于业务态而非 404，前端按 2001 引导占位
    if data is None:
        raise BizError(code=2001, message="今日节目尚未发布")
    return success(data=data)


@router.get("/history")
async def get_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = ContentService(db)
    data = await svc.get_history(page, size)
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
    svc = ContentService(db)
    data = await svc.get_script(episode_id)
    if data is None:
        raise NotFoundError("稿件不存在")
    return success(data=data)
