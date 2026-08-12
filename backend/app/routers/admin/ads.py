"""B 端广告路由。"""
import json
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin
from app.core.response import success
from app.database import get_db
from app.models import AuditLog
from app.services.ad_service import AdService

router = APIRouter(prefix="/admin/api/v1/ads", tags=["B端-广告"])


class MaterialCreateRequest(BaseModel):
    """素材创建请求体。简化版：直接传 file_url 与 duration，跳过上传流程。"""
    name: str
    description: str
    file_url: str
    duration: int


class PlacementCreateRequest(BaseModel):
    """投放创建请求体。start/end_date 由 Pydantic 自动解析 ISO 日期字符串。"""
    material_id: int
    position: str
    start_date: date
    end_date: date


@router.get("/materials")
async def list_materials(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = AdService(db)
    data = await svc.list_materials(page=page, size=size)
    return success(data=data)


@router.post("/materials")
async def create_material(
    req: MaterialCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = AdService(db)
    material_id = await svc.create_material(
        name=req.name,
        description=req.description,
        file_url=req.file_url,
        duration=req.duration,
    )
    return success(data={"id": material_id})


@router.delete("/materials/{material_id}")
async def delete_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = AdService(db)
    await svc.delete_material(material_id)
    # 审计日志：广告素材删除影响关联投放，记录操作人便于追溯
    db.add(AuditLog(
        category="ad",
        action="delete_material",
        target=str(material_id),
        operator=admin.username,
        detail=json.dumps({"material_id": material_id}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"success": True})


@router.get("/placements")
async def list_placements(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = AdService(db)
    data = await svc.list_placements(page=page, size=size)
    return success(data=data)


class PlacementUpdateRequest(BaseModel):
    """投放更新请求体（M7 FR-M702 移动端启停，当前仅暴露 enabled 安全开关）。"""
    enabled: int

    @field_validator("enabled")
    @classmethod
    def validate_enabled(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("enabled 仅支持 0 / 1")
        return v


@router.put("/placements/{placement_id}")
async def update_placement(
    placement_id: int,
    req: PlacementUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """投放启用/停用（仅启停开关，复杂编辑走 PC）。"""
    svc = AdService(db)
    try:
        data = await svc.set_placement_enabled(placement_id, req.enabled)
    except ValueError as e:
        return error(code=404, message=str(e))
    db.add(AuditLog(
        category="ad",
        action="update_placement_enabled",
        target=str(placement_id),
        operator=admin.username,
        detail=json.dumps({"enabled": req.enabled}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data=data)


@router.post("/placements")
async def create_placement(
    req: PlacementCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = AdService(db)
    placement_id = await svc.create_placement(
        material_id=req.material_id,
        position=req.position,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    return success(data={"id": placement_id})


@router.delete("/placements/{placement_id}")
async def delete_placement(
    placement_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = AdService(db)
    await svc.delete_placement(placement_id)
    # 审计日志：投放删除影响广告排期，记录操作人便于追溯
    db.add(AuditLog(
        category="ad",
        action="delete_placement",
        target=str(placement_id),
        operator=admin.username,
        detail=json.dumps({"placement_id": placement_id}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"success": True})


@router.get("/schedule")
async def get_schedule(
    month: str = Query(..., description="月份，格式 YYYY-MM"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = AdService(db)
    data = await svc.get_schedule(month=month)
    return success(data=data)
