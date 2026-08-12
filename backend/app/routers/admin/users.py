"""B 端终端用户管理路由（SRS M5 FR-M501 检索 / FR-M502 启停）。

仅 admin 角色可访问（require_admin）。终端用户表为 C 端 user，本路由提供运营侧
受控视图：按昵称/openid 检索、按状态筛选、禁用/启用（二次确认 + 审计由前端/路由保证）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, require_admin
from app.core.response import success, error
from app.database import get_db
from app.models import AuditLog
from app.models.user import User

router = APIRouter(prefix="/admin/api/v1/users", tags=["B端-终端用户管理"])


class UserToggleBody(BaseModel):
    """用户启停请求体：disabled=1 禁用，0 启用。"""
    disabled: int

    @field_validator("disabled")
    @classmethod
    def validate_disabled(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("disabled 仅支持 0 / 1")
        return v


@router.get("")
async def list_users(
    keyword: Optional[str] = Query(None, description="昵称/openid 模糊检索"),
    disabled: Optional[int] = Query(None, description="状态筛选：1=已禁用，0=正常"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """分页检索终端用户。

    支持 keyword 模糊匹配 nickname/openid；disabled 精确筛选。
    """
    conditions = []
    if keyword:
        kw = f"%{keyword.strip()}%"
        conditions.append(or_(User.nickname.ilike(kw), User.openid.ilike(kw)))
    if disabled in (0, 1):
        conditions.append(User.disabled == disabled)

    count_stmt = select(func.count()).select_from(User)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one()

    list_stmt = select(User)
    if conditions:
        list_stmt = list_stmt.where(*conditions)
    list_stmt = list_stmt.order_by(User.created_at.desc()).offset(
        (page - 1) * size
    ).limit(size)
    users = (await db.execute(list_stmt)).scalars().all()

    return success(data={
        "total": total,
        "list": [_to_dict(u) for u in users],
        "page": page,
        "size": size,
    })


@router.post("/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: int,
    body: UserToggleBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """禁用 / 启用终端用户（FR-M502，受控 + 审计）。"""
    user = await db.get(User, user_id)
    if user is None:
        return error(code=404, message=f"用户不存在: {user_id}")

    user.disabled = body.disabled
    db.add(AuditLog(
        category="user",
        action="toggle_status",
        target=str(user_id),
        operator=admin.username,
        detail=str({"disabled": body.disabled}),
    ))
    await db.commit()
    await db.refresh(user)
    return success(data=_to_dict(user))


def _to_dict(u: User) -> dict:
    """序列化 User 为运营侧安全视图（不含 openid 之外敏感字段按需脱敏）。"""
    return {
        "id": u.id,
        "nickname": u.nickname,
        "openid": u.openid,
        "disabled": u.disabled,
        "total_listen_duration": u.total_listen_duration or 0,
        "total_listen_count": u.total_listen_count or 0,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }
