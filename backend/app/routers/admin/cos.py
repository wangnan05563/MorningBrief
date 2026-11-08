"""B 端云端 COS 配置与管理路由（V1.5 新增）。

端点：
- GET  /admin/api/v1/cos/config          获取 COS 配置（SecretId/SecretKey 脱敏）
- PUT  /admin/api/v1/cos/config          保存 COS 配置（热更新 Settings + 重置客户端缓存）
- POST /admin/api/v1/cos/reset-config    清除已存凭证（SecretId/SecretKey，保留地域/桶）
- POST /admin/api/v1/cos/test-connection 测试 COS 连接（列举桶验证凭证）
- GET  /admin/api/v1/cos/status          配置就绪状态（前端管理页快速判断）
- GET  /admin/api/v1/cos/objects         列举某前缀下的目录与文件
- POST /admin/api/v1/cos/upload          上传文件（multipart，含 prefix / overwrite）
- GET  /admin/api/v1/cos/exists          对象存在性检查（同名检测）
- GET  /admin/api/v1/cos/download        获取对象下载地址（CDN 直链或预签名）
- DELETE /admin/api/v1/cos/object        删除单个对象
- POST /admin/api/v1/cos/folder          新建文件夹
- DELETE /admin/api/v1/cos/folder        删除文件夹（递归）
- POST /admin/api/v1/cos/move            重命名 / 移动（文件或文件夹，目标同名默认拒绝）
- GET  /admin/api/v1/cos/move-preview    移动前的目标同名冲突预览（覆盖条数）
- GET  /admin/api/v1/cos/restore-preview 快照恢复前的预览（原对象 Key、目标当前状态）
- POST /admin/api/v1/cos/restore         从 .backup 快照恢复对象（恢复前先备份当前对象）
- GET  /admin/api/v1/cos/metadata        获取对象元数据

所有端点需要管理员权限。未配置 COS 时管理类接口返回可读的业务错误提示。
覆盖上传、覆盖移动与快照恢复都会写审计日志（category=cos，含管理员名）。
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_reason import audit_detail
from app.core.auth import AdminPayload, require_admin
from app.core.response import success
from app.database import get_db
from app.models.audit_log import AuditLog
from app.services.cos_config_service import CREDENTIAL_KEYS, CosConfigService
from app.services.cos_storage_service import CosStorageService, backup_keep_count



_DESC_OBJECT_KEY = "对象 Key"
router = APIRouter(prefix="/admin/api/v1/cos", tags=["B端-云端存储"])
logger = logging.getLogger(__name__)


class CosConfigBody(BaseModel):
    """COS 配置保存体。"""
    secret_id: str = ""
    secret_key: str = ""
    region: str = "ap-guangzhou"
    bucket: str = ""
    cdn_domain: str = ""
    # 传 None 表示不修改（老前端不带该字段时不能把保留份数静默清零，T02609）
    backup_keep_count: Optional[int] = None


class CosFolderBody(BaseModel):
    """新建文件夹请求体。"""
    prefix: str


class CosMoveBody(BaseModel):
    """重命名 / 移动请求体。

    overwrite 默认 False：目标已有同名对象时服务端拒绝（业务码 409），
    必须由调用方确认后显式带 True 才会覆盖（T02608 / H19）。
    多传字段一律 422 而不是静默丢弃——「参数被吞」和「没生效」在界面上看起来一样。
    """
    model_config = ConfigDict(extra="forbid")

    source_key: str
    dest_key: str
    overwrite: bool = False
    reason: str = ""


class CosRestoreBody(BaseModel):
    """快照恢复请求体（T02609）。

    backup_key 指向 .backup/<时间戳>/ 下的快照对象；target_key 留空时由服务端
    从快照 Key 推出原对象位置，显式传入则必须与推出值一致。
    extra=forbid：覆盖开关拼错（如 overwrit）会被拒，而不是静默当作「不覆盖」。
    """
    model_config = ConfigDict(extra="forbid")

    backup_key: str
    target_key: str = ""
    overwrite: bool = False
    reason: str = ""


async def _audit(
    db: AsyncSession,
    admin: AdminPayload,
    action: str,
    target: str,
    detail: dict,
    reason: str = "",
) -> None:
    """写 COS 审计日志（category=cos）。

    审计失败只记日志不抛：存储操作此时已经成功，因为审计写不进去就让接口报错，
    会让调用方以为上传/恢复失败并重做一次。
    """
    try:
        db.add(AuditLog(
            category="cos",
            action=action,
            target=target,
            operator=admin.username,
            detail=audit_detail(detail, reason=reason),
        ))
        await db.commit()
    except Exception:  # NOSONAR 审计是旁路，不能反噬主流程
        logger.exception("COS 审计写入失败 action=%s target=%s", action, target)
        await db.rollback()


@router.get("/config")
async def get_config(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """获取 COS 配置（SecretId/SecretKey 脱敏）。"""
    svc = CosConfigService(db)
    data = await svc.get_config_for_frontend()
    return success(data=data)


@router.put("/config")
async def save_config(
    body: CosConfigBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """保存 COS 配置（热更新 Settings 单例 + 重置客户端缓存）。"""
    svc = CosConfigService(db)
    await svc.update_config(
        secret_id=body.secret_id,
        secret_key=body.secret_key,
        region=body.region,
        bucket=body.bucket,
        cdn_domain=body.cdn_domain,
        backup_keep_count=body.backup_keep_count,
    )
    return success(message="COS 配置已保存并热更新")


@router.post("/reset-config")
async def reset_config(
    reason: str = Query("", max_length=200, description="清除原因（可选，写入审计）"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """清除已保存的 COS 凭证（T02919）。

    只清 SecretId / SecretKey：地域、桶、CDN 域名保留。这是 COS 侧唯一的
    清除通道——保存接口的「留空」表示不修改。审计只记被清的 key 名，不含明文。
    """
    svc = CosConfigService(db)
    config = await svc.reset_credentials()
    db.add(AuditLog(
        category="cos",
        action="reset_config",
        target="credentials",
        operator=admin.username,
        detail=audit_detail({"cleared_keys": CREDENTIAL_KEYS}, reason=reason),
    ))
    await db.commit()
    return success(data=config, message="COS 凭证已清除，回退到 .env 默认值")


@router.post("/test-connection")
async def test_connection(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """测试 COS 连接（列举桶根验证凭证与 Bucket 可达性）。"""
    svc = CosConfigService(db)
    result = await svc.test_connection()
    return success(data=result)


@router.get("/status")
async def get_status(
    admin: AdminPayload = Depends(require_admin),
):
    """COS 配置就绪状态（前端管理页快速判断，无需 DB）。"""
    from app.cos.client import is_cos_configured
    from app.config import get_settings

    settings = get_settings()
    return success(data={
        "configured": is_cos_configured(),
        "bucket": settings.COS_BUCKET,
        "region": settings.COS_REGION,
        "cdn_domain": settings.COS_CDN_DOMAIN,
        "backup_keep_count": backup_keep_count(),
    })


@router.get("/objects")
async def list_objects(
    prefix: str = Query("", description="列举前缀，目录以 / 结尾，根目录为空"),
    admin: AdminPayload = Depends(require_admin),
):
    """列举某前缀下的目录与文件（模拟目录树）。"""
    svc = CosStorageService()
    data = await svc.list_path(prefix=prefix)
    return success(data=data)


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    prefix: str = Form("", description="上传目标前缀（目录），以 / 结尾"),
    overwrite: bool = Form(False, description="同名对象已存在时是否覆盖（覆盖前自动留快照）"),
    reason: str = Form("", description="覆盖原因（可选，写入审计）"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """上传文件到 COS。

    key = prefix + 原始文件名。文件名已做安全校验（拒绝路径穿越）。
    同名对象默认拒绝覆盖（业务码 409），确认后带 overwrite=true 重传，
    覆盖前旧对象会复制到同目录 .backup/<时间戳>/ 下（FR-UX-205 可回退）。
    """
    import os

    filename = os.path.basename(file.filename or "")
    if not filename:
        from app.core.exceptions import ParamError
        raise ParamError("文件名不能为空")

    # 规范化前缀并拼接 key
    prefix = (prefix or "").strip()
    if prefix and not prefix.endswith("/"):
        prefix = prefix + "/"
    key = prefix + filename

    data = await file.read()
    svc = CosStorageService()
    result = await svc.upload_file(
        key=key, data=data, content_type=file.content_type, overwrite=overwrite
    )
    backup_key = result.get("backup_key")
    message = "上传成功"
    if result.get("overwritten"):
        if backup_key:
            message = f"已覆盖上传，旧文件已备份至 {backup_key}"
        elif backup_keep_count() == 0:
            message = "已覆盖上传（当前设置不保留快照，旧文件不可找回）"
        else:
            message = "已覆盖上传"
        await _audit(db, admin, "overwrite_upload", key, {
            "backup_key": backup_key,
            "previous_size": (result.get("previous") or {}).get("size"),
        }, reason=reason)
    return success(data=result, message=message)


@router.get("/exists")
async def check_exists(
    key: str = Query(..., description=_DESC_OBJECT_KEY),
    admin: AdminPayload = Depends(require_admin),
):
    """对象存在性检查（上传/移动前的同名检测，FR-UX-205）。"""
    svc = CosStorageService()
    data = await svc.object_exists(key=key)
    return success(data=data)


@router.get("/download")
async def get_download(
    key: str = Query(..., description=_DESC_OBJECT_KEY),
    expired: int = Query(300, description="预签名有效期（秒），CDN 模式忽略"),
    admin: AdminPayload = Depends(require_admin),
):
    """获取对象下载地址（CDN 直链优先，否则预签名）。"""
    svc = CosStorageService()
    url = await svc.get_download_url(key=key, expired=expired)
    return success(data={"key": key, "url": url})


@router.delete("/object")
async def delete_object(
    key: str = Query(..., description=_DESC_OBJECT_KEY),
    admin: AdminPayload = Depends(require_admin),
):
    """删除单个对象。"""
    svc = CosStorageService()
    await svc.delete_file(key=key)
    return success(data={"deleted": key})


@router.post("/folder")
async def create_folder(
    body: CosFolderBody,
    admin: AdminPayload = Depends(require_admin),
):
    """新建文件夹（上传占位对象）。"""
    svc = CosStorageService()
    result = await svc.create_folder(prefix=body.prefix)
    return success(data=result, message="文件夹已创建")


@router.delete("/folder")
async def delete_folder(
    prefix: str = Query(..., description="要删除的目录前缀（以 / 结尾）"),
    admin: AdminPayload = Depends(require_admin),
):
    """删除文件夹（递归删除前缀下所有对象）。"""
    svc = CosStorageService()
    count = await svc.delete_folder(prefix=prefix)
    return success(data={"deleted": count}, message=f"已删除 {count} 个对象")


@router.get("/move-preview")
async def move_preview(
    source_key: str = Query(..., description="源对象 Key 或源前缀（以 / 结尾表示文件夹）"),
    dest_key: str = Query(..., description=_DESC_OBJECT_KEY),
    admin: AdminPayload = Depends(require_admin),
):
    """移动/重命名前的同名冲突预览：目标侧将被覆盖的对象条数与样例。

    条数只由服务端实测给出（T02608 第 5 点）：文件夹移动是批量覆盖，
    前端按当前页列表估算会漏掉分页外与子层级里的同名对象。
    """
    svc = CosStorageService()
    data = await svc.move_preview(source_key=source_key, dest_key=dest_key)
    return success(data=data)


@router.post("/move")
async def move_object(
    body: CosMoveBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """重命名 / 移动对象或文件夹。

    source_key 以 '/' 结尾视为文件夹，递归移动。
    目标位置已有同名对象时默认拒绝（业务码 409），需带 overwrite=true 重做，
    且覆盖前会把旧对象复制到 .backup/<时间戳>/（T02608 / H19）。
    """
    svc = CosStorageService()
    result = await svc.move_object(
        source_key=body.source_key, dest_key=body.dest_key, overwrite=body.overwrite
    )
    overwritten = result.get("overwritten") or 0
    if overwritten:
        backup_keys = result.get("backup_keys") or []
        if backup_keys:
            message = f"移动成功，已覆盖 {overwritten} 个同名对象，旧对象已备份到 .backup/ 目录"
        elif backup_keep_count() == 0:
            message = f"移动成功，已覆盖 {overwritten} 个同名对象（当前设置不保留快照，旧对象不可找回）"
        else:
            message = f"移动成功，已覆盖 {overwritten} 个同名对象"
        await _audit(db, admin, "overwrite_move", body.dest_key, {
            "source_key": body.source_key,
            "overwritten": overwritten,
            "backup_keys": backup_keys,
        }, reason=body.reason)
    else:
        message = "移动成功"
    return success(data=result, message=message)


@router.get("/restore-preview")
async def restore_preview(
    backup_key: str = Query(..., description="快照对象 Key（.backup/<时间戳>/ 下）"),
    admin: AdminPayload = Depends(require_admin),
):
    """快照恢复前的预览（T02609）。

    原对象 Key 由服务端从快照 Key 推出并回给前端：确认框必须点名「从哪恢复到哪」，
    而不是让用户在一个可能拼错的目标 Key 上确认。
    """
    svc = CosStorageService()
    data = await svc.restore_preview(backup_key=backup_key)
    return success(data=data)


@router.post("/restore")
async def restore_snapshot(
    body: CosRestoreBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """从 .backup 快照恢复对象。

    恢复前会先给当前对象留一份快照（恢复也可回退）；backup_keep_count=0 时不备份，
    响应里 backup_key 为 null，界面据此在确认框点名「不可找回」。
    """
    svc = CosStorageService()
    result = await svc.restore_snapshot(
        backup_key=body.backup_key,
        target_key=body.target_key,
        overwrite=body.overwrite,
    )
    await _audit(db, admin, "restore_snapshot", result["target_key"], {
        "restored_from": result["restored_from"],
        "backup_key": result.get("backup_key"),
    }, reason=body.reason)
    if result.get("backup_key"):
        message = f"已从快照恢复 {result['target_key']}，恢复前的对象已备份至 {result['backup_key']}"
    elif result.get("overwritten"):
        message = f"已从快照恢复 {result['target_key']}（当前设置不保留快照，恢复前的对象不可找回）"
    else:
        message = f"已从快照恢复 {result['target_key']}"
    return success(data=result, message=message)


@router.get("/metadata")
async def get_metadata(
    key: str = Query(..., description=_DESC_OBJECT_KEY),
    admin: AdminPayload = Depends(require_admin),
):
    """获取对象元数据（大小 / 最后修改 / 类型 / ETag）。"""
    svc = CosStorageService()
    data = await svc.get_metadata(key=key)
    return success(data=data)
