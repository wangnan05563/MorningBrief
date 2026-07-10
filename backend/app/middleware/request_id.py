"""RequestId 中间件：为每个 HTTP 请求注入全局流水号。

流水号通过 ContextVar 传递，loguru patcher 自动读取并写入每条日志。
同时回写到响应头 X-Request-Id，便于前端/调用方关联排障。
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_context import (
    clear_request_id,
    generate_request_id,
    is_valid_request_id,
    set_request_id,
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个请求生成或透传 request_id。

    支持客户端通过 X-Request-Id 请求头透传（需通过格式校验），
    否则自动生成。请求结束后清除 ContextVar 防止跨请求泄漏。
    """

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-Id", "")
        if not is_valid_request_id(rid):
            rid = generate_request_id()

        set_request_id(rid)
        try:
            response: Response = await call_next(request)
        finally:
            clear_request_id()

        response.headers["X-Request-Id"] = rid
        return response
