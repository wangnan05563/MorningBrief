"""B 端云端 COS 配置与管理路由（V1.5 新增）。

端点：
- GET  /admin/api/v1/cos/config          获取 COS 配置（SecretId/SecretKey 脱敏）
- PUT  /admin/api/v1/cos/config          保存 COS 配置（热更新 Settings + 重置客户端缓存）
- POST /admin/api/v1/cos/test-connection 测试 COS 连接（列举桶验证凭证）
- GET  /admin/api/v1/cos/status          配置就绪状态（前端管理页快速判断）
- GET  /admin/api/v1/cos/objects         列举某前缀下的目录与文件
- POST /admin/api/v1/cos/upload          上传文件（multipart，含 prefix）
- GET  /admin/api/v1/cos/download        获取对象下载地址（CDN 直链或预签名）
- DELETE /admin/api/v1/cos/object        删除单个对象
- POST /admin/api/v1/cos/folder          新建文件夹
- DELETE /admin/api/v1/cos/folder        删除文件夹（递归）
- POST /admin/api/v1/cos/move            重命名 / 移动（文件或文件夹）
- GET  /admin/api/v1/cos/metadata        获取对象元数据

所有端点需要管理员权限。未配置 COS 时管理类接口返回可读的业务错误提示。
"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, require_admin
from app.core.response import success
from app.database import get_db
from app.services.cos_config_service import CosConfigService
from app.services.cos_storage_service import CosStorageService

router = APIRouter(prefix="/admin/api/v1/cos", tags=["B端-云端存储"])


class CosConfigBody(BaseModel):
    """COS 配置保存体。"""
    secret_id: str = ""
    secret_key: str = ""
    region: str = "ap-guangzhou"
    bucket: str = ""
    cdn_domain: str = ""


class CosFolderBody(BaseModel):
    """新建文件夹请求体。"""
    prefix: str


class CosMoveBody(BaseModel):
    """重命名 / 移动请求体。"""
    source_key: str
    dest_key: str


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
    )
    return success(message="COS 配置已保存并热更新")


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
    admin: AdminPayload = Depends(require_admin),
):
    """上传文件到 COS。

    key = prefix + 原始文件名。文件名已做安全校验（拒绝路径穿越）。
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
        key=key, data=data, content_type=file.content_type
    )
    return success(data=result, message="上传成功")


@router.get("/download")
async def get_download(
    key: str = Query(..., description="对象 Key"),
    expired: int = Query(300, description="预签名有效期（秒），CDN 模式忽略"),
    admin: AdminPayload = Depends(require_admin),
):
    """获取对象下载地址（CDN 直链优先，否则预签名）。"""
    svc = CosStorageService()
    url = await svc.get_download_url(key=key, expired=expired)
    return success(data={"key": key, "url": url})


@router.delete("/object")
async def delete_object(
    key: str = Query(..., description="对象 Key"),
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


@router.post("/move")
async def move_object(
    body: CosMoveBody,
    admin: AdminPayload = Depends(require_admin),
):
    """重命名 / 移动对象或文件夹。

    source_key 以 '/' 结尾视为文件夹，递归移动。
    """
    svc = CosStorageService()
    result = await svc.move_object(source_key=body.source_key, dest_key=body.dest_key)
    return success(data=result, message="移动成功")


@router.get("/metadata")
async def get_metadata(
    key: str = Query(..., description="对象 Key"),
    admin: AdminPayload = Depends(require_admin),
):
    """获取对象元数据（大小 / 最后修改 / 类型 / ETag）。"""
    svc = CosStorageService()
    data = await svc.get_metadata(key=key)
    return success(data=data)
