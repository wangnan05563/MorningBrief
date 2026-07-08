"""
健康检查接口

Docker 健康检查 + 运维监控用。
检查项：MySQL 连接、Redis 连接。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.database import get_db
from app.redis_client import get_redis

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    健康检查，返回各依赖服务状态。

    设计为轻量检查：MySQL/Redis 各执行一次 ping，不检查外部云服务（LLM/TTS/COS），
    避免健康检查因外部服务波动误报。
    """
    status = {"app": "ok", "mysql": "ok", "redis": "ok"}

    # MySQL 连通性
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        status["mysql"] = "error"

    # Redis 连通性
    try:
        redis = get_redis()
        await redis.ping()
    except Exception:
        status["redis"] = "error"

    # 任一依赖失败则整体状态为 error
    all_ok = all(v == "ok" for v in status.values())
    return success(data={"status": "ok" if all_ok else "error", "services": status})
