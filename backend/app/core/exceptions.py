"""
自定义异常与全局异常处理

业务异常通过 BizError 抛出，全局处理器统一转换为 { code, message, data } 响应。
避免在业务代码中到处处理错误响应格式。
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.response import error


class BizError(Exception):
    """业务异常基类，携带错误码与消息。"""

    def __init__(self, code: int, message: str, http_status: int = 200):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


# ---- 常见业务异常快捷构造 ----

class AuthError(BizError):
    """未登录或 token 失效。"""
    def __init__(self, message: str = "未登录或登录已过期"):
        super().__init__(code=401, message=message, http_status=401)


class BizPermissionError(BizError):
    """无权限。

    命名加 Biz 前缀避免遮蔽内置 PermissionError，
    便于业务代码在需要时仍可捕获内置异常。
    """
    def __init__(self, message: str = "无权限"):
        super().__init__(code=403, message=message, http_status=403)


class NotFoundError(BizError):
    """资源不存在。"""
    def __init__(self, message: str = "资源不存在"):
        super().__init__(code=404, message=message, http_status=404)


class ParamError(BizError):
    """参数错误。"""
    def __init__(self, message: str = "参数错误"):
        super().__init__(code=400, message=message, http_status=400)


class RateLimitError(BizError):
    """限流。"""
    def __init__(self, message: str = "请求过于频繁，请稍后重试"):
        super().__init__(code=429, message=message, http_status=429)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(BizError)
    async def biz_error_handler(request: Request, exc: BizError):
        return error(code=exc.code, message=exc.message, http_status=exc.http_status)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # 参数校验失败，返回具体错误明细便于前端调试
        return error(code=400, message=f"参数错误: {exc.errors()}", http_status=400)

    @app.exception_handler(SQLAlchemyError)
    async def db_error_handler(request: Request, exc: SQLAlchemyError):
        # 数据库异常不暴露详情，仅记录日志，避免泄露表结构
        return error(code=500, message="数据库错误", http_status=500)

    @app.exception_handler(Exception)
    async def global_error_handler(request: Request, exc: Exception):
        # 兜底：未捕获的异常统一返回 500，堆栈记录到日志
        return error(code=500, message="服务内部错误", http_status=500)
