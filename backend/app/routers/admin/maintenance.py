"""B 端系统清理路由（对标 17_xianyu api_maintenance）。

仅 admin 角色可访问。
清理操作支持 dry_run 预览模式，非预览模式写入审计日志。

T02799（FR-UX-702）：非预览的清理改为后台任务——POST 立即返回 `task_id`，
前端轮询 `GET /maintenance/tasks/{task_id}` 看状态，不再挂一条 300s 的 HTTP 请求。
dry_run 仍是同步返回（只统计不执行，秒级），预览结果要能直接拿来确认影响范围。
"""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, require_admin
from app.core.exceptions import NotFoundError
from app.core.response import success
from app.database import get_db
from app.services import maintenance_task_service as task_service
from app.services.maintenance_service import MaintenanceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/v1/maintenance", tags=["B端-系统清理"])


class CleanupRequest(BaseModel):
    """数据库/日志清理请求体：都按天数窗口执行，所以 days 是本端点的契约字段。

    T02926 起 `extra="forbid"`：曾经这里和缓存清理共用一个模型，`days` 对缓存端点
    毫无意义却被照单全收（返回成功、按天数保留却没发生）。未知字段一律拒，不再静默吞。
    """
    model_config = ConfigDict(extra="forbid")

    target: str = "blacklist"       # 清理目标
    days: int = Field(0, ge=0, le=3650)  # 保留天数（0 用配置默认值）
    dry_run: bool = False           # 预览模式


class CacheCleanupRequest(BaseModel):
    """缓存清理请求体。

    TTLCache 条目、`__pycache__` 与临时文件都没有「保留 N 天」语义，因此本端点
    **不声明 days**——多传一个生效不了的参数，比少一个参数更坏（T02926 灰度第一批）。
    """
    model_config = ConfigDict(extra="forbid")

    target: str = "pycache"         # ttlcache | pycache | temp | all
    dry_run: bool = False


class WorkflowChainCleanupRequest(BaseModel):
    """指定工作流全链清理请求体。

    按 ID 清理没有「保留 N 天」语义，因此不声明 days；target 也不适用，
    路径本身已表明清理范围（T02926 同口径：不声明用不上的字段）。
    """
    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(min_length=1, max_length=64)
    dry_run: bool = False



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
    dry_run 同步返回预览；真实执行转为后台任务（T02799）。
    """
    if body.dry_run:
        svc = MaintenanceService(db)
        result = await svc.cleanup_database(
            target=body.target, days=body.days,
            dry_run=True, admin_name=admin.username,
        )
        return success(data=result)
    data = await task_service.submit(
        db,
        category="database",
        target=body.target,
        params={"days": body.days},
        admin_name=admin.username,
    )
    return success(data=data)


# ---- 指定工作流全链清理 ----

@router.post("/workflow-chain")
async def cleanup_workflow_chain(
    body: WorkflowChainCleanupRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """按工作流 ID 清理其全部子表（与按天清理共用同一套级联口径）。"""
    if body.dry_run:
        svc = MaintenanceService(db)
        result = await svc.cleanup_workflow_chain(
            workflow_id=body.workflow_id,
            dry_run=True,
            admin_name=admin.username,
        )
        return success(data=result)
    data = await task_service.submit(
        db,
        category="workflow_chain",
        target=body.workflow_id,
        params={},
        admin_name=admin.username,
    )
    return success(data=data)


# ---- 日志清理 ----

@router.post("/logs")
async def cleanup_logs(
    body: CleanupRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """清理日志文件（按天数或按大小）。dry_run 同步预览，真实执行走后台任务。"""
    if body.dry_run:
        svc = MaintenanceService(db)
        result = await svc.cleanup_logs(
            target=body.target, days=body.days,
            dry_run=True, admin_name=admin.username,
        )
        return success(data=result)
    data = await task_service.submit(
        db,
        category="logs",
        target=body.target,
        params={"days": body.days},
        admin_name=admin.username,
    )
    return success(data=data)


# ---- 缓存清理 ----

@router.post("/cache")
async def cleanup_cache(
    body: CacheCleanupRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """清理缓存（TTLCache / __pycache__ / 临时文件）。

    dry_run 同步返回预览；真实执行转为后台任务（T02799）。
    """
    target = body.target or "pycache"
    if body.dry_run:
        svc = MaintenanceService(db)
        result = await svc.cleanup_cache(
            target=target, dry_run=True, admin_name=admin.username,
        )
        return success(data=result)
    data = await task_service.submit(
        db,
        category="cache",
        target=target,
        params={},
        admin_name=admin.username,
    )
    return success(data=data)


# ---- 后台任务状态 ----

@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """查询清理任务状态（T02799）。

    state: queued | running | succeeded | failed；执行中 elapsed_ms 按当前时间实时算，
    结束后返回结果（result.total_deleted / cleaned / errors）或错误原因。
    """
    row = await task_service.get_task(db, task_id)
    if row is None:
        raise NotFoundError("清理任务不存在")
    return success(data=task_service.serialize(row))
