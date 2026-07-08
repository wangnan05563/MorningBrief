"""
统一响应格式

所有 API 响应统一包装为 { code, message, data } 格式：
- 成功：code=0, message="success", data=实际数据
- 失败：code=非零错误码, message=错误描述, data=null

设计原因：前端只需判断 code 是否为 0，无需关注 HTTP 状态码与业务码的映射关系。
"""
from typing import Any, Optional

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一响应体模型。"""
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


def success(data: Any = None, message: str = "success") -> dict:
    """成功响应。"""
    return {"code": 0, "message": message, "data": data}


def error(code: int, message: str, data: Any = None, http_status: int = 200) -> JSONResponse:
    """
    错误响应。

    默认 http_status=200，让前端通过 code 字段判断业务错误，
    避免 HTTP 状态码与业务错误码的映射混乱。
    仅在认证、权限等场景使用对应 HTTP 状态码（401/403/404）。
    """
    return JSONResponse(
        status_code=http_status,
        content={"code": code, "message": message, "data": data},
    )
