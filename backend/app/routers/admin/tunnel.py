"""B 端内网穿透路由。

提供一键开启/关闭远程访问的能力，返回公网 HTTPS 域名。
全部端点需 admin 认证（20_News 是 B 端管理工具，不存在「未登录远程引导」场景）。

端口解析：环境变量 NEWS_WEB_PORT > local_port > settings.APP_PORT。

Cloudflare Named Tunnel 向导端点：
- POST /cloudflare/login        启动 login（非阻塞，返回授权 URL）
- GET  /cloudflare/login/status 轮询 cert.pem 是否生成
- POST /cloudflare/create       创建命名隧道
- POST /cloudflare/route-dns    配置 DNS 路由
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.auth import AdminPayload, get_current_admin
from app.core.response import success
from app.services.tunnel_providers import (
    BinaryDownloadError,
    CloudflareProvider,
    TailscaleFunnelAuthError,
)
from app.services.tunnel_service import get_tunnel_service

router = APIRouter(prefix="/admin/api/v1/tunnel", tags=["B端-内网穿透"])

# 全局 setup provider：login 是两阶段操作（POST start + GET poll），
# 必须在同一个 provider 实例上调用，否则 _login_process / _login_output 状态会丢失
_setup_provider: CloudflareProvider | None = None


class TunnelConfigBody(BaseModel):
    """隧道配置保存请求体。

    cpolar_authtoken 传空串表示「不修改」（保留已有 token），非空才覆盖。
    cert_file 传空串表示「不修改」（保留已有 cert.pem 路径）。
    """
    provider: str = "cloudflare"
    local_port: int = 0
    cpolar_authtoken: str = ""
    binary_path: str = ""
    auto_start: bool = False
    # Cloudflare Named Tunnel 配置（quick 模式下被忽略）
    tunnel_mode: str = "quick"
    tunnel_name: str = ""
    tunnel_id: str = ""
    credentials_file: str = ""
    hostname: str = ""
    cert_file: str = ""


class CloudflareCreateBody(BaseModel):
    """创建命名隧道请求体。"""
    tunnel_name: str
    cert_file: str = ""


class CloudflareRouteDnsBody(BaseModel):
    """配置 DNS 路由请求体。"""
    tunnel_name_or_id: str
    hostname: str
    cert_file: str = ""


def _get_setup_provider() -> CloudflareProvider:
    """获取全局 setup provider 单例。

    login 两阶段流程要求 start_login 和 check_login_status 在同一实例上调用，
    因为 _login_process / _login_output / _login_auth_url 都保存在实例上。
    """
    global _setup_provider
    if _setup_provider is None:
        svc = get_tunnel_service()
        _setup_provider = svc.get_provider_for_setup()
    return _setup_provider


def _reset_setup_provider() -> None:
    """重置 setup provider（login 成功或失败后清理，允许后续重试）。"""
    global _setup_provider
    if _setup_provider is not None:
        _setup_provider._cleanup_login_process()
        _setup_provider = None


# ---------- 状态控制端点 ----------

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

    下载失败时返回 code=5001 + 手动放置指引；
    Tailscale 首次启用需授权时返回 code=5003 + 授权链接；
    前端据此渲染对应的引导 UI。
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
    except TailscaleFunnelAuthError as e:
        # Tailscale 首次启用 Funnel 需用户在浏览器完成授权
        # 返回授权链接，前端渲染可点击的超链接指引用户完成授权
        return JSONResponse(
            status_code=200,
            content={
                "code": 5003,
                "message": str(e),
                "data": {
                    "error_type": "tailscale_funnel_auth",
                    "auth_url": e.auth_url,
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


# ---------- 配置端点 ----------

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
    配置保存后异步 stop 旧 provider，下次 start 按新配置创建。
    """
    svc = get_tunnel_service()
    svc.save_config(body.model_dump())
    return success(data={"ok": True, "message": "配置已保存，下次启动隧道时生效"})


# ---------- Cloudflare Named Tunnel 配置向导端点 ----------

@router.post("/cloudflare/login")
async def cloudflare_login(
    admin: AdminPayload = Depends(get_current_admin),
):
    """启动 cloudflared tunnel login（非阻塞）。

    login 是交互式命令：cloudflared 会打开浏览器让用户授权。
    此端点用 Popen 启动子进程后立即返回授权 URL，不等待用户完成浏览器操作。
    前端通过 GET /cloudflare/login/status 轮询 cert.pem 是否生成。
    """
    provider = _get_setup_provider()
    try:
        result = provider.start_login()
    except Exception as e:
        _reset_setup_provider()
        return JSONResponse(
            status_code=200,
            content={"code": 5004, "message": f"login 启动失败: {e}", "data": None},
        )
    # failed 时清理 provider 允许重试；waiting 时保留 provider 供 status 轮询
    if result.get("status") == "failed":
        _reset_setup_provider()
    return success(data=result)


@router.get("/cloudflare/login/status")
async def cloudflare_login_status(
    admin: AdminPayload = Depends(get_current_admin),
):
    """轮询 cloudflared login 状态。

    前端每 2-3 秒调用一次，直到 status 变为 success 或 failed。
    - success: cert.pem 已生成，自动持久化 cert_file 路径并清理 provider
    - failed:  清理 provider 允许重试
    - waiting: 继续轮询
    - idle:    login 未启动（provider 被重置或从未调用 POST /login）
    """
    provider = _get_setup_provider()
    result = provider.check_login_status()

    if result["status"] == "success":
        # 持久化 cert_file，后续 create/route-dns 自动读取
        svc = get_tunnel_service()
        svc.save_field("cert_file", result["cert_file"])
        _reset_setup_provider()
    elif result["status"] == "failed":
        _reset_setup_provider()

    return success(data=result)


@router.post("/cloudflare/create")
async def cloudflare_create(
    body: CloudflareCreateBody,
    admin: AdminPayload = Depends(get_current_admin),
):
    """执行 cloudflared tunnel create <name>（创建命名隧道）。

    需要 cert.pem（login 步骤生成）。成功后自动将 tunnel_id 和 credentials_file 持久化。
    """
    svc = get_tunnel_service()
    cfg = svc.get_config()
    # 请求体 cert_file 优先于配置中的 cert_file
    cert_file = body.cert_file or cfg.get("cert_file", "")
    if not cert_file:
        return JSONResponse(
            status_code=200,
            content={
                "code": 5005,
                "message": "请先执行 login 步骤获取 cert.pem，或手动指定 cert_file 路径",
                "data": None,
            },
        )

    provider = svc.get_provider_for_setup()
    try:
        result = provider.setup_create(body.tunnel_name, cert_file=cert_file)
    except Exception as e:
        return JSONResponse(
            status_code=200,
            content={"code": 5006, "message": f"创建隧道失败: {e}", "data": None},
        )

    # 持久化 tunnel_id、credentials_file、tunnel_name
    svc.save_field("tunnel_id", result["tunnel_id"])
    svc.save_field("credentials_file", result["credentials_file"])
    svc.save_field("tunnel_name", result["tunnel_name"])
    return success(data={
        "ok": True,
        "tunnel_id": result["tunnel_id"],
        "credentials_file": result["credentials_file"],
        "tunnel_name": result["tunnel_name"],
        "message": "隧道创建成功，可以继续配置 DNS 路由",
    })


@router.post("/cloudflare/route-dns")
async def cloudflare_route_dns(
    body: CloudflareRouteDnsBody,
    admin: AdminPayload = Depends(get_current_admin),
):
    """执行 cloudflared tunnel route dns <name> <hostname>（创建 CNAME 记录）。

    成功后自动将 hostname 持久化，并切换 tunnel_mode 为 named。
    """
    svc = get_tunnel_service()
    cfg = svc.get_config()
    cert_file = body.cert_file or cfg.get("cert_file", "")
    if not cert_file:
        return JSONResponse(
            status_code=200,
            content={
                "code": 5005,
                "message": "请先执行 login 步骤获取 cert.pem，或手动指定 cert_file 路径",
                "data": None,
            },
        )

    provider = svc.get_provider_for_setup()
    try:
        url = provider.setup_route_dns(body.tunnel_name_or_id, body.hostname, cert_file=cert_file)
    except Exception as e:
        return JSONResponse(
            status_code=200,
            content={"code": 5007, "message": f"DNS 路由配置失败: {e}", "data": None},
        )

    # 持久化 hostname，并自动切换到 named 模式
    svc.save_field("hostname", body.hostname)
    svc.save_field("tunnel_mode", "named")
    return success(data={
        "ok": True,
        "public_url": url,
        "message": "DNS 路由配置成功，已自动切换到固定域名模式",
    })
