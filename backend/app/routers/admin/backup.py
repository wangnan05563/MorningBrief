"""B 端数据库备份管理路由。

仅 admin 角色可访问。
恢复操作须传 confirm_token 校验，防止误操作覆盖最新数据。
"""
import hmac
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import AdminPayload, require_admin
from app.core.exceptions import ParamError
from app.core.response import success
from app.database import get_db
from app.models.audit_log import AuditLog
from app.services.backup_service import BackupService

logger = logging.getLogger(__name__)
settings = get_settings()

# 恢复操作确认令牌（与 db_admin 复用同一令牌，保持危险操作校验统一）
CONFIRM_TOKEN = settings.DB_ADMIN_CONFIRM_TOKEN

router = APIRouter(prefix="/admin/api/v1/backups", tags=["B端-数据库备份"])


class RestoreRequest(BaseModel):
    """恢复请求体。"""
    backup_path: str           # 备份文件路径（从 list_backups 返回的 path）
    confirm_token: str         # 危险操作确认令牌


def _validate_confirm_token(token: str) -> None:
    """校验危险操作确认令牌。

    空值拒绝执行：DB_ADMIN_CONFIRM_TOKEN 未配置时禁止危险操作。
    使用 hmac.compare_digest 常量时间比较，防御时序攻击。
    """
    if not CONFIRM_TOKEN:
        raise ParamError("服务器未配置 DB_ADMIN_CONFIRM_TOKEN，危险操作被禁止")
    if not hmac.compare_digest(token, CONFIRM_TOKEN):
        raise ParamError("confirm_token 校验失败")


# ---- 备份列表 ----

@router.get("")
async def list_backups(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """列出所有可用备份。

    返回按时间降序排列的备份列表，包含文件名、路径、大小、创建时间。
    """
    backups = await BackupService.list_backups()
    return success(data={"backups": backups, "total": len(backups)})


# ---- 手动触发备份 ----

@router.post("")
async def create_backup(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """手动触发一次数据库备份。

    场景：定时备份失败后运维手动补备，或重大变更前临时备份。
    """
    try:
        backup_path = await BackupService.backup_database()
    except Exception as e:
        logger.exception("手动备份失败 operator=%s", admin.username)
        raise ParamError(f"备份失败: {e}")

    # 写审计日志：备份是只读快照，但记录操作人便于追溯
    db.add(AuditLog(
        category="backup",
        action="create",
        target="database",
        operator=admin.username,
        detail=f'{{"path": "{backup_path}"}}',
    ))
    await db.commit()

    return success(data={"backup_path": backup_path}, message="备份成功")


# ---- 从备份恢复 ----

@router.post("/restore")
async def restore_backup(
    body: RestoreRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """从指定备份恢复数据库。

    警告：恢复会覆盖当前数据库，丢失自备份以来所有数据。
    需传 confirm_token 校验，防止误操作。
    恢复后应用需重启以重建 engine 连接池。
    """
    _validate_confirm_token(body.confirm_token)

    try:
        await BackupService.restore_backup(body.backup_path)
    except FileNotFoundError as e:
        raise ParamError(str(e))
    except ValueError as e:
        raise ParamError(str(e))
    except Exception as e:
        logger.exception("恢复数据库失败 operator=%s path=%s", admin.username, body.backup_path)
        raise ParamError(f"恢复失败: {e}")

    # 写审计日志：恢复是危险操作，必须记录
    db.add(AuditLog(
        category="backup",
        action="restore",
        target="database",
        operator=admin.username,
        detail=f'{{"source": "{body.backup_path}"}}',
    ))
    await db.commit()

    logger.warning(
        "数据库已从备份恢复 operator=%s source=%s（需重启应用重建连接池）",
        admin.username, body.backup_path,
    )
    return success(
        data={"restored_from": body.backup_path},
        message="恢复成功，请重启应用以重建数据库连接",
    )


# ---- 清理过期备份 ----

@router.post("/cleanup")
async def cleanup_backups(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """手动清理过期备份（保留最近 7 天）。

    定时任务每日 04:00 已自动清理，此接口供运维主动清理场景使用。
    """
    deleted = await BackupService.cleanup_old_backups()

    db.add(AuditLog(
        category="backup",
        action="cleanup",
        target="backup_files",
        operator=admin.username,
        detail=f'{{"deleted": {deleted}}}',
    ))
    await db.commit()

    return success(data={"deleted": deleted}, message=f"已清理 {deleted} 个过期备份")
