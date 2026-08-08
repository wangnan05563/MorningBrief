"""路径前缀重写中间件。

直接访问后端时（非通过 Tailscale Funnel / Vite proxy），
浏览器按 Vite base='/news/' 请求 /news/admin/api/...，
而后端路由注册为 /admin/api/...（无 /news 前缀）。
此中间件剥离 /news 前缀，使两种访问方式都能命中路由。
"""


class PathPrefixMiddleware:
    """剥离 API 路径 /news 前缀的纯 ASGI 中间件。

    采用纯 ASGI 实现（不继承 BaseHTTPMiddleware），避免对 FileResponse
    等流式响应的缓冲冲突。仅重写 API 路径，静态资源 /news/assets
    已有独立 StaticFiles 挂载，SPA 路由 /news/xxx 由 fallback 处理。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            # 仅剥离 API 路径的 /news 前缀：
            # 静态资源 /news/assets 已有独立挂载，SPA 路由由 fallback 处理
            if path.startswith("/news/admin/api/") or path.startswith("/news/api/") or path.startswith("/news/audio/") or path.startswith("/news/bgm/") or path.startswith("/news/avatars/"):
                scope["path"] = path[5:]
        await self.app(scope, receive, send)

