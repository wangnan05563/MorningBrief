"""缓存层（V1.2 新增）。

V1.2 用 TTLCache（cachetools）替代 Redis，提供进程内缓存。
面向接口编程，保留未来回退到 Redis 的扩展点。
"""
from app.cache.manager import cache, CacheManager

__all__ = ["cache", "CacheManager"]
