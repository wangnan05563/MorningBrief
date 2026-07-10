"""B 端内网穿透路由。

提供一键开启/关闭远程访问的能力，返回公网 HTTPS 域名。
全部端点需 admin 认证（20_News 是 B 端管理工具，不存在「未登录远程引导」场景）。

端口解析：local_port > 0 用 local_port，否则回退到 settings.APP_PORT。
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.auth import AdminPayload, get_current_admin
from app.core.response import success
from app.services.tunnel_providers import BinaryDownloadError
from app.services.tunnel_service import get_tunnel_service

router = APIRouter(prefix="/admin/api/v1/tunnel", tags=["B端-内网穿透"])


class TunnelConfigBody(BaseModel):
    """隧道配置保存请求体。

    cpolar_authtoken 传空串表示「不修改」（保留已有 token），非空才覆盖。
    """
    provider: str = "cloudflare"
    local_port: int = 0
    cpolar_authtoken: str = ""
    binary_path: str = ""
    auto_start: bool = False


@router.get("/status")
async def tunnel_status(
    admin: AdminPayload = Depends(get_current_admin),
):
    """查询隧道状态。"""
    svc = get_tunnel_service()
    return success(data={
        "status": svc.status,
        "public_url": svc.public_url,
        "provider": svc.provider_name,
    })


@router.post("/start")
async def tunnel_start(
    admin: AdminPayload = Depends(get_current_admin),
):
    """启动隧道，返回公网 URL。

    下载失败时返回 error_type=binary_download_failed + 手动放置指引，
    前端据此渲染下载链接和路径。
    """
    svc = get_tunnel_service()
    try:
        url = svc.start()
        return success(data={
            "status": svc.status,
            "public_url": url,
            "provider": svc.provider_name,
        })
    except BinaryDownloadError as e:
        # 下载失败：返回手动放置指引，前端渲染下载链接和路径
        return JSONResponse(
            status_code=200,
            content={
                "code": 5001,
                "message": str(e),
                "data": {
                    "error_type": "binary_download_failed",
                    "manual_path": e.manual_path,
                    "download_urls": e.download_urls,
                },
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=200,
            content={"code": 5002, "message": f"隧道启动失败: {e}", "data": None},
        )


@router.post("/stop")
async def tunnel_stop(
    admin: AdminPayload = Depends(get_current_admin),
):
    """停止隧道。"""
    svc = get_tunnel_service()
    svc.stop()
    return success(data={
        "status": svc.status,
        "public_url": svc.public_url,
        "provider": svc.provider_name,
    })


@router.get("/config")
async def tunnel_config_get(
    admin: AdminPayload = Depends(get_current_admin),
):
    """获取当前隧道配置（authtoken 脱敏：仅保留末4位）。"""
    svc = get_tunnel_service()
    return success(data=svc.get_config())


@router.post("/config")
async def tunnel_config_save(
    body: TunnelConfigBody,
    admin: AdminPayload = Depends(get_current_admin),
):
    """保存隧道配置到 JSON 文件并热重载。

    前端传 cpolar_authtoken 空串表示「不修改」，非空才覆盖。
    配置保存后重置 provider 单例，下次 start 按新配置创建。
    """
    svc = get_tunnel_service()
    svc.save_config(body.model_dump())
    return success(data={"ok": True, "message": "配置已保存，下次启动隧道时生效"})
