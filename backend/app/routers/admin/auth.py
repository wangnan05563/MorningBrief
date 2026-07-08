"""B 端认证路由。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.database import get_db
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin/api/v1/auth", tags=["B端-认证"])


class LoginRequest(BaseModel):
    """后台登录请求体。"""
    username: str
    password: str


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    svc = AdminService(db)
    data = await svc.login(req.username, req.password)
    return success(data=data)
