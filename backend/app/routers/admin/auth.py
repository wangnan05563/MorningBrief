"""B 端认证路由。"""
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.audit_reason import audit_detail
from app.core.auth import (
    AdminPayload,
    get_current_admin,
    set_admin_token_cookie,
    clear_admin_token_cookie,
)
from app.core.response import success
from app.core.security import MIN_ADMIN_PASSWORD_LEN
from app.database import get_db
from app.models import AuditLog
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin/api/v1/auth", tags=["B端-认证"])


class LoginRequest(BaseModel):
    """后台登录请求体。"""
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    """改密请求体：长度口径与 MIN_ADMIN_PASSWORD_LEN 同源（设计说明书 minLength 8）。"""
    old_password: str
    new_password: str = Field(min_length=MIN_ADMIN_PASSWORD_LEN)


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


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """自助改密：校验旧口令 → 写新哈希 → 审计 → 吊销当前 token。"""
    svc = AdminService(db)
    await svc.change_password(
        admin.admin_id, req.old_password, req.new_password
    )
    # 审计只记「谁改了谁的口令」，不落新旧口令或其哈希
    db.add(AuditLog(
        category="user",
        action="change_password",
        target=admin.username,
        operator=admin.username,
        detail=audit_detail({"admin_id": admin.admin_id}),
    ))
    await db.commit()
    # 口径：改密即刻吊销当前会话（jti 黑名单），其它会话不受影响；
    # 前端据此清本地态并回登录页，用新口令重新登录。
    await svc.logout(jti=admin.jti, exp=admin.exp, admin_id=admin.admin_id)
    clear_admin_token_cookie(response, request)
    return success(data={"success": True, "relogin_required": True})
