"""B 端审计日志统一读口（T02909，派生自 T02529 / INT-UX-06）。

权限裁决：**全量管理员可读**。这里用 `get_current_admin` 而不是 `require_admin`，
与裁决一致——所有已登录管理员都能读全部 category；不按模块切分。
匿名/过期 token 由依赖直接 401。
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin
from app.core.exceptions import ParamError
from app.core.response import success
from app.database import get_db
from app.services import audit_service

router = APIRouter(prefix="/admin/api/v1/audit-logs", tags=["B端-审计日志"])


@router.get("")
async def list_audit_logs(
    category: Optional[str] = Query(None, description="审计类别，须在登记表中"),
    action: Optional[str] = Query(None, description="动作，如 restore / cleanup / toggle_status"),
    start: Optional[datetime] = Query(None, description="起始时间（含）"),
    end: Optional[datetime] = Query(None, description="结束时间（含）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """按类别 / 动作 / 时间范围分页查询审计，倒序。"""
    if category and category not in audit_service.AUDIT_CATEGORIES:
        raise ParamError(f"未知审计类别: {category}")
    data = await audit_service.list_logs(
        db,
        category=category,
        action=action,
        start=start,
        end=end,
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.get("/categories")
async def audit_categories(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """登记类别及各自条数/最近时间：一次调用可复核所有写入类别都有读口。"""
    return success(data=await audit_service.category_summary(db))
