"""
Redis 异步客户端

提供全局 Redis 连接，用于：
- 播放进度实时缓存
- JWT 登出黑名单
- 爬虫去重（URL Set + SimHash Set）
- 接口限流计数
"""
from typing import Optional

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()

# decode_responses=True 让返回值直接是 str，避免业务层到处 decode
redis_client: redis.Redis = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    max_connections=50,
)


async def get_redis() -> redis.Redis:
    """FastAPI 依赖：注入 Redis 客户端。"""
    return redis_client


# ---- 黑名单 Key 工具函数 ----
# 设计原因：JWT 无状态本地验签，仅登出/强制下线时写 Redis 黑名单。
# 校验流程：本地验签 → 查黑名单（仅 jti 命中才拒绝，QPS 极低）。

def user_blacklist_key(jti: str) -> str:
    """C 端 JWT 登出黑名单 Key。"""
    return f"user:session:bl:{jti}"


def admin_blacklist_key(jti: str) -> str:
    """B 端 JWT 登出黑名单 Key。"""
    return f"admin:session:bl:{jti}"


async def add_to_blacklist(key: str, ttl_seconds: int) -> None:
    """写入黑名单，TTL 与 JWT 剩余有效期一致，过期自动清理。"""
    await redis_client.set(key, "1", ex=ttl_seconds)


async def is_in_blacklist(key: str) -> bool:
    """检查 jti 是否在黑名单中。"""
    return await redis_client.exists(key) > 0
