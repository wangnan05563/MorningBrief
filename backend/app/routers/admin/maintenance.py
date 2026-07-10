"""B 端系统清理路由（对标 17_xianyu api_maintenance）。

仅 admin 角色可访问。
清理操作支持 dry_run 预览模式，非预览模式写入审计日志。
"""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, require_admin
from app.core.response import success
from app.database import get_db
from app.services.maintenance_service import MaintenanceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/v1/maintenance", tags=["B端-系统清理"])


class CleanupRequest(BaseModel):
    """清理请求体。"""
    target: str = "blacklist"       # 清理目标
    days: int = 0                   # 保留天数（0 用配置默认值）
    dry_run: bool = False           # 预览模式


# ---- 存储状态查询 ----

@router.get("/status")
async def get_status(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """查询存储状态：数据库大小 + 日志文件 + 缓存占用。"""
    svc = MaintenanceService(db)
    data = await svc.get_status()
    return success(data=data)


# ---- 数据库清理 ----

@router.post("/database")
async def cleanup_database(
    body: CleanupRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """清理数据库旧数据或 VACUUM 压缩。

    审计日志由服务层 _write_audit 内部写入，路由层无需重复处理。
    """
    svc = MaintenanceService(db)
    result = await svc.cleanup_database(
        target=body.target, days=body.days,
        dry_run=body.dry_run, admin_name=admin.username,
    )
    return success(data=result)


# ---- 日志清理 ----

@router.post("/logs")
async def cleanup_logs(
    body: CleanupRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """清理日志文件（按天数或按大小）。"""
    svc = MaintenanceService(db)
    result = await svc.cleanup_logs(
        target=body.target, days=body.days,
        dry_run=body.dry_run, admin_name=admin.username,
    )
    return success(data=result)


# ---- 缓存清理 ----

@router.post("/cache")
async def cleanup_cache(
    body: CleanupRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """清理缓存（TTLCache / __pycache__ / 临时文件）。"""
    svc = MaintenanceService(db)
    result = await svc.cleanup_cache(
        target=body.target or "pycache",
        dry_run=body.dry_run, admin_name=admin.username,
    )
    return success(data=result)
