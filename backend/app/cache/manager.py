"""TTLCache 缓存管理器（V1.2 替代 redis_client.py）。

设计要点：
1. 用 cachetools.TTLCache 实现带过期的键值缓存，覆盖原 Redis 大部分场景
2. 原子计数用 asyncio.Lock + int 模拟 Redis INCR（workflow 序号生成）
3. Redis Bitmap/Set/List 等特殊结构改用 SQLite 表实现（见 dedup.py、stats_service.py）

不支持的 Redis 操作（已改造为其他方案）：
- BITCOUNT/SETBIT → SQLite COUNT(DISTINCT user_id) 聚合
- SADD/SISMEMBER/SSCAN → SQLite crawler_dedup 表
- LPUSH/LRANGE/LTRIM → COS 对象 + APScheduler 聚合
- EVAL (Lua 脚本) → 不再需要
- SET NX EX（互斥锁）→ 工作流并发控制改用 WorkflowScheduler._trigger_lock
  （asyncio.Lock 单进程互斥已足够，无需分布式锁语义）

存储格式：所有键值统一存 (value, expire_at) 元组，get 时检查过期。
cachetools.TTLCache 自身有过期机制，元组 expire_at 作为冗余兜底，
确保 set 时传入的自定义 TTL 一定生效（TTLCache 单实例 ttl 全局固定）。
"""
import asyncio
import logging
import time
from typing import Any, Optional

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# 默认缓存参数：最大 10000 条目，默认 TTL 5 分钟
_DEFAULT_MAXSIZE = 10000
_DEFAULT_TTL = 300


class CacheManager:
    """TTLCache 封装，提供与 Redis 类似的异步接口。

    所有方法为 async 以保持与原 redis_client 调用方式一致，
    便于服务层无感切换。
    """

    def __init__(self, maxsize: int = _DEFAULT_MAXSIZE, default_ttl: int = _DEFAULT_TTL):
        # TTLCache 的 ttl 仅作为兜底过期，单 key 自定义 TTL 由元组 expire_at 管理
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=default_ttl)
        self._default_ttl = default_ttl
        # 计数器池：key -> int，模拟 Redis INCR
        self._counters: dict[str, int] = {}
        self._counters_ttl: dict[str, float] = {}
        self._counters_guard = asyncio.Lock()

    # ---- 通用键值操作（替代 Redis GET/SET/DELETE） ----

    async def get(self, key: str) -> Optional[Any]:  # NOSONAR
        """读取缓存值，未命中或已过期返回 None（与 Redis GET 一致）。"""
        raw = self._cache.get(key)
        if raw is None:
            return None
        # 统一存储格式：(value, expire_at)
        try:
            value, expire_at = raw
        except (TypeError, ValueError):
            # 兼容历史格式（直接存值）
            return raw
        # 检查自定义 TTL 是否已过期
        if time.monotonic() >= expire_at:
            self._cache.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:  # NOSONAR
        """写入缓存值，ttl 为 None 时用默认 TTL。

        所有写入统一存 (value, expire_at) 元组，确保 get 时能正确解包。
        """
        actual_ttl = ttl if ttl is not None else self._default_ttl
        expire_at = time.monotonic() + actual_ttl
        self._cache[key] = (value, expire_at)

    async def delete(self, key: str) -> None:  # NOSONAR
        """删除缓存键，不存在不报错（与 Redis DEL 一致）。"""
        self._cache.pop(key, None)

    async def delete_pattern(self, pattern: str) -> None:  # NOSONAR
        """按 glob 模式批量删除（替代 Redis SCAN + DEL）。

        pattern 仅支持末尾 * 通配（覆盖 episodes:history:* 场景）。
        """
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
            for k in keys_to_delete:
                self._cache.pop(k, None)
        else:
            self._cache.pop(pattern, None)

    async def exists(self, key: str) -> bool:
        """检查键是否存在且未过期（与 Redis EXISTS 一致）。"""
        value = await self.get(key)
        return value is not None

    # ---- 原子计数（替代 Redis INCR + EXPIRE） ----

    async def incr(self, key: str) -> int:
        """原子自增并返回新值（与 Redis INCR 一致）。"""
        async with self._counters_guard:
            current = self._counters.get(key, 0) + 1
            self._counters[key] = current
            return current

    async def expire(self, key: str, ttl_sec: int) -> None:
        """为计数器设置过期时间（与 Redis EXPIRE 一致）。

        仅对计数器生效；TTLCache 的键值对过期由 cachetools 自动管理。
        """
        async with self._counters_guard:
            self._counters_ttl[key] = time.monotonic() + ttl_sec
            # 清理已过期的计数器
            now = time.monotonic()
            expired = [k for k, exp in self._counters_ttl.items() if exp < now]
            for k in expired:
                self._counters.pop(k, None)
                self._counters_ttl.pop(k, None)

    async def get_counter(self, key: str) -> int:  # NOSONAR
        """读取计数器当前值（清理过期后返回）。"""
        now = time.monotonic()
        expire_at = self._counters_ttl.get(key)
        if expire_at is not None and now > expire_at:
            self._counters.pop(key, None)
            self._counters_ttl.pop(key, None)
            return 0
        return self._counters.get(key, 0)


# 模块级单例，替代原 redis_client
cache = CacheManager()
