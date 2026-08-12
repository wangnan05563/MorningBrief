"""B 端认证路由。"""
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import (
    AdminPayload,
    get_current_admin,
    set_admin_token_cookie,
    clear_admin_token_cookie,
)
from app.core.response import success
from app.database import get_db
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin/api/v1/auth", tags=["B端-认证"])


class LoginRequest(BaseModel):
    """后台登录请求体。"""
    username: str
    password: str


@router.post("/login")
async def login(
    req: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    svc = AdminService(db)
    data = await svc.login(req.username, req.password)
    # NFR-M103：写入 HttpOnly admin_token Cookie（JS 不可读，避免 XSS 窃取持久 token）
    max_age = int(get_settings().JWT_ADMIN_EXPIRE_HOURS * 3600)
    set_admin_token_cookie(response, request, data["token"], max_age)
    # 仍返回 token 供非浏览器 API 客户端按 Authorization 头调用（双通道兼容）
    return success(data=data)


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    # 登出仅写黑名单，无需事务；jti+exp+admin_id 已在鉴权时从 JWT 解析
    svc = AdminService(db)
    await svc.logout(jti=admin.jti, exp=admin.exp, admin_id=admin.admin_id)
    # NFR-M103：清除 HttpOnly admin_token Cookie
    clear_admin_token_cookie(response, request)
    return success(data={"success": True})
