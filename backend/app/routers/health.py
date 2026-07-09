"""
健康检查接口

V1.2 起单机 exe 部署，无外部中间件依赖：
检查项：SQLite 连接（应用唯一外部状态存储）+ 进程内缓存可用性。
不检查 LLM/TTS/COS 等外部云服务，避免健康检查因外部波动误报。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache
from app.core.response import success
from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    健康检查，返回各依赖服务状态。

    设计为轻量检查：SQLite 执行一次 SELECT 1，cache 做一次读写探测，
    不检查外部云服务（LLM/TTS/COS），避免健康检查因外部服务波动误报。
    """
    status = {"app": "ok", "sqlite": "ok", "cache": "ok"}

    # SQLite 连通性
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        status["sqlite"] = "error"

    # 进程内缓存可用性：写入探测键再读回，校验 TTLCache 正常工作
    try:
        await cache.set("__health_probe__", "1", ttl=60)
        probe = await cache.get("__health_probe__")
        if probe != "1":
            status["cache"] = "error"
        await cache.delete("__health_probe__")
    except Exception:
        status["cache"] = "error"

    # 任一依赖失败则整体状态为 error
    all_ok = all(v == "ok" for v in status.values())
    return success(data={"status": "ok" if all_ok else "error", "services": status})
