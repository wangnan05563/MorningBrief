"""C 端认证路由。"""
from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserPayload, get_current_user
from app.core.exceptions import BizError
from app.core.response import success
from app.database import get_db
from app.services.user_service import UserService

router = APIRouter(prefix="/api/v1/auth", tags=["C端-认证"])


class LoginRequest(BaseModel):
    """微信登录请求体。code 来自小程序 wx.login 调用。"""
    # 微信 wx.login 返回的 code 长度约 128 字符以内、5 分钟有效
    # 加长度约束避免前端误传超大字符串或空值穿透到微信 API 调用
    code: str = Field(..., min_length=1, max_length=128, description="微信登录 code")


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    # 微信登录涉及外部调用，任何异常统一包装为业务错误码 1001
    try:
        svc = UserService(db)
        data = await svc.login_by_code(req.code)
        return success(data=data)
    except BizError:
        raise
    except Exception:
        # 不把底层异常详情返回给客户端（可能含 URL/SQL/密钥片段），
        # 完整堆栈记录到日志便于排障；客户端只看到通用 message
        logger.exception("微信登录失败 code={}", req.code)
        raise BizError(code=1001, message="微信登录失败，请稍后重试")


@router.post("/logout")
async def logout(
    db: AsyncSession = Depends(get_db),
    user: UserPayload = Depends(get_current_user),
):
    # 登出仅写黑名单，无需事务；jti+exp 已在鉴权时从 JWT 解析
    svc = UserService(db)
    await svc.logout(jti=user.jti, exp=user.exp, user_id=user.user_id)
    return success(data={"success": True})
