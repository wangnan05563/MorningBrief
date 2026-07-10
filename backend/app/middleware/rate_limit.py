"""API 限流中间件（对标 17_xianyu anti_detect 滑动窗口）。

按客户端 IP 限流，每分钟请求数上限由 Settings.RATE_LIMIT_PER_MINUTE 控制。
采用滑动窗口算法：维护每个 IP 最近 1 分钟的时间戳列表，超限返回 429。

设计取舍：
- 不用 Redis 计数器（V1.2 无 Redis），用进程内 dict + threading.Lock
- 不用令牌桶/漏桶：滑动窗口实现简单且精度足够（秒级即可，无需毫秒）
- 多实例部署时此限流失效（每实例独立计数），但 V1.2 为单机架构可接受

健康检查与内部工作流路由豁免限流，避免运维探针误触发 429。
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings

# 豁免限流的路径前缀：健康检查、内部工作流回调、docs 静态资源
_EXEMPT_PREFIXES = (
    "/api/health",
    "/api/internal/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/assets/",
)

# 滑动窗口清理周期：每 60 秒清理一次过期 IP 记录，避免 dict 无限增长
_CLEANUP_INTERVAL_SEC = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按客户端 IP 限流的滑动窗口中间件。

    维护 {ip: [timestamp, ...]} 字典，每次请求清理超过 1 分钟的时间戳，
    剩余数量即为最近 1 分钟的请求计数。
    """

    def __init__(self, app):
        super().__init__(app)
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    async def dispatch(self, request: Request, call_next):
        # 豁免路径直通（健康检查、内部回调等）
        path = request.url.path
        if path.startswith(_EXEMPT_PREFIXES):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        settings = get_settings()
        limit = settings.RATE_LIMIT_PER_MINUTE

        now = time.monotonic()
        cutoff = now - 60

        with self._lock:
            # 定期清理过期 IP 桶，防止字典无限增长（攻击者切换 IP）
            if now - self._last_cleanup > _CLEANUP_INTERVAL_SEC:
                stale = [
                    ip for ip, ts in self._requests.items()
                    if not ts or ts[-1] < cutoff
                ]
                for ip in stale:
                    self._requests.pop(ip, None)
                self._last_cleanup = now

            # 滑动窗口：保留最近 1 分钟的时间戳
            bucket = self._requests[client_ip]
            bucket[:] = [t for t in bucket if t > cutoff]

            if len(bucket) >= limit:
                # 超限：返回 429 + Retry-After 头
                retry_after = 60
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": 429,
                        "message": "请求过于频繁，请稍后再试",
                        "data": {
                            "retry_after": retry_after,
                            "limit_per_minute": limit,
                        },
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            bucket.append(now)

        return await call_next(request)
