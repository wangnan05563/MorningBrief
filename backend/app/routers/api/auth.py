"""C 端认证路由。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError
from app.core.response import success
from app.database import get_db
from app.services.user_service import UserService

router = APIRouter(prefix="/api/v1/auth", tags=["C端-认证"])


class LoginRequest(BaseModel):
    """微信登录请求体。code 来自小程序 wx.login 调用。"""
    code: str


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    # 微信登录涉及外部调用，任何异常统一包装为业务错误码 1001
    try:
        svc = UserService(db)
        data = await svc.login_by_code(req.code)
        return success(data=data)
    except BizError:
        raise
    except Exception as e:
        raise BizError(code=1001, message=f"微信登录失败: {e}")
