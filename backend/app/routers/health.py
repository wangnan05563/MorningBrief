"""
健康检查接口（对标 17_xianyu /healthz 多项依赖探测）。

V1.2 起单机 exe 部署，无外部中间件依赖：
检查项：SQLite 连接（应用唯一外部状态存储）+ 进程内缓存可用性。
不检查 LLM/TTS/COS 等外部云服务，避免健康检查因外部波动误报。

提供三个端点：
- GET /api/health         综合健康检查（兼容旧接口，返回依赖状态）
- GET /api/health/live    存活探针（进程存活即返回 200，不查依赖）
- GET /api/health/ready    就绪探针（依赖全部就绪才返回 200，用于启动后流量接入）

开发模式额外返回 lan_ips：后端所有局域网 IPv4 地址，供小程序真机调试自动发现。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache
from app.config import get_all_lan_ips, get_settings
from app.core.response import success
from app.database import get_db

# 模块级单例：get_settings 用 lru_cache 缓存，与 user_service 等模块一致
settings = get_settings()

router = APIRouter(tags=["health"])


async def _check_sqlite(db: AsyncSession) -> str:
    """SQLite 连通性检查：执行 SELECT 1，失败返回 error。"""
    try:
        await db.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


async def _check_cache() -> str:
    """进程内缓存可用性：写入探测键再读回，校验 TTLCache 正常工作。"""
    try:
        await cache.set("__health_probe__", "1", ttl=60)
        probe = await cache.get("__health_probe__")
        if probe != "1":
            return "error"
        await cache.delete("__health_probe__")
        return "ok"
    except Exception:
        return "error"


@router.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    综合健康检查，返回各依赖服务状态。

    设计为轻量检查：SQLite 执行一次 SELECT 1，cache 做一次读写探测，
    不检查外部云服务（LLM/TTS/COS），避免健康检查因外部服务波动误报。

    开发模式额外返回 lan_ips：后端所有局域网 IPv4 地址（排除 Tailscale/回环）。
    小程序真机调试时从 Tailscale 引导地址拉取本接口，获取 lan_ips 后加入候选，
    实现自动发现，避免弹窗引导用户手动输入 IP。
    生产模式不返回 lan_ips，避免泄露内网拓扑。
    """
    sqlite_status = await _check_sqlite(db)
    cache_status = await _check_cache()

    status = {"app": "ok", "sqlite": sqlite_status, "cache": cache_status}

    # 任一依赖失败则整体状态为 error
    all_ok = all(v == "ok" for v in status.values())
    data = {"status": "ok" if all_ok else "error", "services": status}

    # 开发模式返回局域网 IP 列表，供小程序真机调试自动发现
    if settings.is_dev:
        data["lan_ips"] = get_all_lan_ips()

    return success(data=data)


@router.get("/api/health/live")
async def liveness():
    """存活探针（Kubernetes liveness probe 语义）。

    进程能响应即认为存活，不检查任何依赖。
    用于判断是否需要重启容器/进程。
    """
    return success(data={"status": "alive"})


@router.get("/api/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """就绪探针（Kubernetes readiness probe 语义）。

    依赖全部就绪才返回 200，用于判断是否可以接入流量。
    SQLite 失败返回 503（核心依赖不可用），cache 失败仅降级不阻断。
    """
    sqlite_status = await _check_sqlite(db)
    cache_status = await _check_cache()

    services = {"sqlite": sqlite_status, "cache": cache_status}

    # SQLite 是核心依赖，失败时返回 503 让启动脚本/负载均衡器暂不接入流量
    if sqlite_status == "error":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail={"status": "not ready", "services": services},
        )

    return success(data={"status": "ready", "services": services})
