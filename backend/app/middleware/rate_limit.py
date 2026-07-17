"""API 限流中间件（滑动窗口算法）。

按客户端 IP 限流，每分钟请求数上限由 Settings.RATE_LIMIT_PER_MINUTE 控制。
维护每个 IP 最近 1 分钟的时间戳列表，超限返回 429。

设计取舍：
- 不用 Redis 计数器（V1.2 无 Redis），用进程内 dict + threading.Lock
- 不用令牌桶/漏桶：滑动窗口实现简单且精度足够（秒级即可，无需毫秒）
- 多实例部署时此限流失效（每实例独立计数），但 V1.2 为单机架构可接受

采用纯 ASGI 中间件实现（不继承 BaseHTTPMiddleware），避免对 FileResponse
等流式响应的缓冲冲突。健康检查与内部工作流路由豁免限流。

健康检查与内部工作流路由豁免限流，避免运维探针误触发 429。
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict

from app.config import get_settings
from app.core.logging_setup import get_logger

logger = get_logger()

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


class RateLimitMiddleware:
    """按客户端 IP 限流的滑动窗口中间件（纯 ASGI 中间件）。

    维护 {ip: [timestamp, ...]} 字典，每次请求清理超过 1 分钟的时间戳，
    剩余数量即为最近 1 分钟的请求计数。
    直接操作 ASGI scope/receive/send，不消费响应体，对流式响应透明。
    """

    def __init__(self, app):
        self.app = app
        self._requests: dict[str, list[float]] = defaultdict(list)
        # asyncio.Lock 不阻塞事件循环（threading.Lock 会阻塞整个循环）
        self._lock = asyncio.Lock()
        self._last_cleanup = time.monotonic()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        # 豁免路径直通（健康检查、内部回调等）
        if path.startswith(_EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return

        # 从 ASGI scope 提取客户端 IP
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        settings = get_settings()
        limit = settings.RATE_LIMIT_PER_MINUTE

        now = time.monotonic()
        cutoff = now - 60

        async with self._lock:
            # 定期清理过期 IP 桶，防止字典无限增长
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
                # 超限：直接通过 ASGI send 返回 429 响应
                # 不经过 Starlette JSONResponse，避免 BaseHTTPMiddleware 封装
                logger.warning("限流触发 ip=%s path=%s limit=%d", client_ip, path, limit)
                body = json.dumps({
                    "code": 429,
                    "message": "请求过于频繁，请稍后再试",
                    "data": {
                        "retry_after": 60,
                        "limit_per_minute": limit,
                    },
                }).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json; charset=utf-8"),
                        (b"retry-after", b"60"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": body,
                })
                return

            bucket.append(now)

        await self.app(scope, receive, send)
