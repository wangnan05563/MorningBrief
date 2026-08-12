"""B 端移动端适配路由（SRS INT-M101~M105）。

前缀 /admin/api/v1/m，复用现有鉴权（get_current_admin / require_admin）、API 约定（success 解包）。
与 PC 端路由隔离，不影响既有 /admin/api/v1/* 接口。
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.exceptions import BizError
from app.core.response import success
from app.database import get_db
from app.services import mobile_service

router = APIRouter(prefix="/admin/api/v1/m", tags=["B端-移动端"])

_ALLOWED_PLATFORMS = {"ios", "android", "wecom", "dingtalk"}


# ---- 请求体 ----
class MarkReadBody(BaseModel):
    message_ids: Optional[List[int]] = None
    mark_all: bool = False


class DeviceRegisterBody(BaseModel):
    platform: str
    device_fingerprint: Optional[str] = None
    push_token: Optional[str] = None


class PushRegisterBody(BaseModel):
    platform: str
    push_token: str
    device_fingerprint: Optional[str] = None


class EmergencyStopBody(BaseModel):
    reason: str


def _validate_platform(platform: str) -> None:
    if platform not in _ALLOWED_PLATFORMS:
        raise BizError(code=400, message=f"不支持的 platform: {platform}")


# ---- INT-M101：运营消息收件箱 ----
@router.get("/inbox")
async def get_inbox(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    data = await mobile_service.get_inbox(
        db, admin.admin_id, page=page, page_size=page_size, unread_only=unread_only
    )
    return success(data=data)


@router.post("/inbox/mark-read")
async def mark_read(
    body: MarkReadBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    if not body.mark_all and not body.message_ids:
        raise BizError(code=400, message="mark_all 与 message_ids 至少提供一个")
    affected = await mobile_service.mark_read(
        db, admin.admin_id, message_ids=body.message_ids, mark_all=body.mark_all
    )
    await db.commit()
    return success(data={"affected": affected})


# ---- INT-M103：设备登记（登录风控 / 绑定） ----
@router.post("/device/register")
async def device_register(
    body: DeviceRegisterBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    _validate_platform(body.platform)
    device = await mobile_service.register_device(
        db,
        admin.admin_id,
        platform=body.platform,
        push_token=body.push_token,
        device_fingerprint=body.device_fingerprint,
    )
    await db.commit()
    return success(data={"device_id": device.id, "platform": device.platform})


# ---- INT-M102：推送 token 注册 ----
@router.post("/push/register")
async def push_register(
    body: PushRegisterBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    _validate_platform(body.platform)
    device = await mobile_service.register_device(
        db,
        admin.admin_id,
        platform=body.platform,
        push_token=body.push_token,
        device_fingerprint=body.device_fingerprint,
    )
    await db.commit()
    return success(data={"device_id": device.id})


# ---- INT-M104：移动首页聚合 ----
@router.get("/dashboard-summary")
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    data = await mobile_service.dashboard_summary(db, admin.admin_id)
    return success(data=data)


# ---- INT-M105：应急停服（仅超级管理员） ----
@router.post("/emergency/stop")
async def emergency_stop(
    body: EmergencyStopBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    reason = (body.reason or "").strip()
    if not reason:
        raise BizError(code=400, message="应急停服必须填写原因")
    result = await mobile_service.emergency_stop(db, admin, reason)
    await db.commit()
    return success(data=result)


# ---- 维护态查询（移动端展示停服横幅） ----
@router.get("/maintenance-status")
async def maintenance_status(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    data = await mobile_service.get_maintenance(db)
    return success(data=data)


# ---- 解除应急停服（仅超级管理员） ----
@router.post("/emergency/resume")
async def emergency_resume(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    result = await mobile_service.resume_maintenance(db, admin)
    await db.commit()
    return success(data=result)
