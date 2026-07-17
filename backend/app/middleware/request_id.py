"""RequestId 中间件：为每个 HTTP 请求注入全局流水号。

流水号通过 ContextVar 传递，loguru patcher 自动读取并写入每条日志。
同时回写到响应头 X-Request-Id，便于前端/调用方关联排障。

采用纯 ASGI 中间件实现（不继承 BaseHTTPMiddleware），避免对 FileResponse
等流式响应的缓冲冲突——BaseHTTPMiddleware 内部通过 anyio memory stream
消费响应体再转发，大文件传输时可能导致连接重置。
"""
from app.core.request_context import (
    clear_request_id,
    generate_request_id,
    is_valid_request_id,
    set_request_id,
)


class RequestIdMiddleware:
    """为每个请求生成或透传 request_id（纯 ASGI 中间件）。

    支持客户端通过 X-Request-Id 请求头透传（需通过格式校验），
    否则自动生成。请求结束后清除 ContextVar 防止跨请求泄漏。
    直接操作 ASGI scope/receive/send，不消费响应体，对流式响应透明。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 从 ASGI scope 中提取请求头（纯 ASGI 不经过 Starlette Request 封装）
        headers = dict(scope.get("headers", []))
        rid = headers.get(b"x-request-id", b"").decode("utf-8", errors="replace")
        if not is_valid_request_id(rid):
            rid = generate_request_id()

        set_request_id(rid)

        # 包装 send：在 http.response.start 中注入 X-Request-Id 响应头
        # 不消费响应体，仅修改响应头，对 FileResponse 流式传输完全透明
        rid_bytes = rid.encode("utf-8")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # ASGI headers 是 list[tuple[bytes, bytes]]
                # 覆盖而非追加：X-Request-Id 应唯一，避免下游已设置时出现重复头
                raw_headers = [
                    (k, v) for k, v in message.get("headers", [])
                    if k.lower() != b"x-request-id"
                ]
                raw_headers.append((b"x-request-id", rid_bytes))
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            clear_request_id()
