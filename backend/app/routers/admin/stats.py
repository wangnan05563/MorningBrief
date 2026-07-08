"""B 端统计路由。"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin
from app.core.exceptions import BizError
from app.core.response import success
from app.database import get_db
from app.services.stats_service import StatsService

router = APIRouter(prefix="/admin/api/v1/stats", tags=["B端-统计"])

# range 字符串到天数的映射，前端只允许这三个枚举值
RANGE_MAP = {"7d": 7, "30d": 30, "90d": 90}


@router.get("/overview")
async def get_overview(
    target_date: date = Query(..., description="日期，格式 YYYY-MM-DD", alias="date"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = StatsService(db)
    data = await svc.get_overview(target_date=target_date)
    return success(data=data)


@router.get("/trend")
async def get_trend(
    metric: str = Query(..., description="指标：dau/play_count/completion_rate/avg_listen_duration"),
    range_str: str = Query("7d", alias="range", description="区间：7d/30d/90d"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    # range 在路由层解析为天数，service 只接收 int
    range_days = RANGE_MAP.get(range_str)
    if range_days is None:
        raise BizError(code=400, message=f"不支持的 range: {range_str}")
    svc = StatsService(db)
    data = await svc.get_trend(metric=metric, range_days=range_days)
    return success(data=data)
