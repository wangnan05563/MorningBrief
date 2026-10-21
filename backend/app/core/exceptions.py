"""
自定义异常与全局异常处理

业务异常通过 BizError 抛出，全局处理器统一转换为 { code, message, data } 响应。
避免在业务代码中到处处理错误响应格式。
"""
from loguru import logger

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging_setup import unwrap_echo_exception
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
        # 数据库异常不暴露详情给前端，但完整堆栈记录到日志便于排障。
        # 消息里只写异常类型，不写 str(exc)：SQLAlchemyError 的字符串自带
        # `[SQL: ...] [parameters: ...]`，等于把本次写入的绑定参数（含凭据列的明文值）
        # 贴进日志文件；NFR-UX-05 的日志抽样在真实日志里查到 18 行这种回显。
        # 堆栈本身带完整的异常链与原因（opt(exception=...) 会渲染 __cause__），
        # 排障信息不减。
        # unwrap_echo_exception：loguru 渲染堆栈取的是异常对象自身的字符串，
        # 消息层的脱敏管不到它，所以这里先把 SQLAlchemy 的「带 SQL + 绑定参数」包装
        # 换成底层 DBAPI 异常。
        logger.opt(exception=unwrap_echo_exception(exc)).error(
            "数据库异常 type={}", type(exc).__name__
        )
        return error(code=500, message="数据库错误", http_status=500)

    @app.exception_handler(Exception)
    async def global_error_handler(request: Request, exc: Exception):
        # 兜底：未捕获的异常统一返回 500，完整堆栈记录到日志。
        # 同样只记类型不记 str(exc) —— 第三方库的异常文本常把请求参数回显出来。
        logger.opt(exception=unwrap_echo_exception(exc)).error(
            "未捕获异常 type={}", type(exc).__name__
        )
        return error(code=500, message="服务内部错误", http_status=500)
