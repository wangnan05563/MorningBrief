"""JWT 黑名单服务（V1.2 替代 redis_client.py 的黑名单功能）。

双写策略：
1. 登出时同时写 SQLite jwt_blacklist 表（B 端本地查询）+ COS 对象（C 端 SCF 共享）
2. B 端验签查 SQLite（本地快速查询）
3. C 端 SCF 验签查 COS（内存缓存 TTL 5 分钟）

与原 Redis 黑名单的差异：
- Redis 用 SET + TTL 自动过期 → SQLite 需定时清理 + COS 对象需定时删除
- 查询频率极低（仅登出时写入，验签时 jti 命中才拒绝）
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache
from app.config import get_settings
from app.cos.client import cos_client
from app.database import AsyncSessionLocal
from app.models.jwt_blacklist import JwtBlacklist

logger = logging.getLogger(__name__)
settings = get_settings()

# B 端黑名单内存缓存（TTL 5 分钟，避免高频验签打库）
_BLACKLIST_CACHE_TTL = settings.JWT_BLACKLIST_CACHE_TTL_SEC
_blacklist_cache: set[str] = set()
_blacklist_cache_expires_at: float = 0


async def add_to_blacklist(
    jti: str,
    token_type: str,
    user_id: Optional[int],
    expires_at: datetime,
    _remaining_ttl: int,
) -> None:
    """写入黑名单（SQLite + COS 双写）。

    Args:
        jti: JWT 唯一标识
        token_type: user | admin
        user_id: 关联用户 ID（admin 为 None）
        expires_at: JWT 原始过期时间
        remaining_ttl: JWT 剩余有效期秒数（COS 对象 TTL 用）
    """
    # 1. 写 SQLite（B 端本地查询用）
    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(JwtBlacklist).where(JwtBlacklist.jti == jti)
        )
        if existing.scalar_one_or_none() is None:
            entry = JwtBlacklist(
                jti=jti,
                token_type=token_type,
                user_id=user_id,
                expires_at=expires_at,
            )
            session.add(entry)
            await session.commit()

    # 2. 写 COS 对象（C 端 SCF 共享读取）
    # COS 路径：jwt_blacklist/{jti}.json，TTL = JWT 剩余有效期
    try:
        cos_key = f"{settings.JWT_BLACKLIST_COS_PREFIX}{jti}.json"
        payload = {
            "jti": jti,
            "token_type": token_type,
            "user_id": user_id,
            "expires_at": expires_at.isoformat(),
        }
        await cos_client.put_object(
            Key=cos_key,
            Body=json.dumps(payload).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
    except Exception as e:
        # COS 写入失败不阻断登出（SQLite 已写入，B 端仍可识别）
        logger.warning(f"[blacklist] COS 写入失败（不阻断）: {e}")

    # 3. 更新内存缓存
    _blacklist_cache.add(jti)

    logger.info(f"[blacklist] 黑名单已写入 jti={jti} type={token_type}")


async def is_in_blacklist(jti: str) -> bool:
    """检查 jti 是否在黑名单中（B 端查 SQLite，带内存缓存）。

    C 端 SCF 的黑名单查询不调用此方法（SCF 直接查 COS）。
    """
    import time
    global _blacklist_cache, _blacklist_cache_expires_at

    # 内存缓存未过期时直接查
    now = time.monotonic()
    if now > _blacklist_cache_expires_at:
        # 缓存过期，重新从 SQLite 加载未过期的 jti 集合
        await _refresh_blacklist_cache()

    return jti in _blacklist_cache


async def _refresh_blacklist_cache() -> None:
    """从 SQLite 加载未过期的黑名单 jti 到内存缓存。"""
    import time
    global _blacklist_cache, _blacklist_cache_expires_at

    now_naive = datetime.now()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(JwtBlacklist.jti).where(JwtBlacklist.expires_at > now_naive)
        )
        _blacklist_cache = {row[0] for row in result.all()}

    _blacklist_cache_expires_at = time.monotonic() + _BLACKLIST_CACHE_TTL


async def cleanup_expired_blacklist() -> int:
    """清理已过期的黑名单记录（APScheduler 定时调用）。

    Returns:
        清理的记录数
    """
    now_naive = datetime.now()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(JwtBlacklist).where(JwtBlacklist.expires_at < now_naive)
        )
        await session.commit()
        deleted = result.rowcount

    if deleted > 0:
        logger.info(f"[blacklist] 清理过期黑名单 {deleted} 条")

    # 同步清理 COS 上已过期的黑名单对象（可选，COS 生命周期规则也可处理）
    # MVP 阶段由 COS 生命周期规则自动删除，此处不主动清理

    return deleted


# ---- 兼容性工具函数（保持与原 redis_client.py 调用方式一致） ----

def user_blacklist_key(jti: str) -> str:
    """C 端 JWT 黑名单 Key（兼容原 redis_client 接口）。"""
    return f"user:session:bl:{jti}"


def admin_blacklist_key(jti: str) -> str:
    """B 端 JWT 黑名单 Key（兼容原 redis_client 接口）。"""
    return f"admin:session:bl:{jti}"
