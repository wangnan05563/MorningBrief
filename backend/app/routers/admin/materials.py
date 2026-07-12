"""B 端爬虫素材查询路由。

供运营后台工作流产物查看使用：按 workflow_id 分页查询素材列表，或查单条详情。
列表接口不返回 content 全文（可能很长），详情接口返回全文。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin
from app.core.exceptions import NotFoundError
from app.core.response import success
from app.database import get_db
from app.models import Material

router = APIRouter(prefix="/admin/api/v1/materials", tags=["B端-素材管理"])


@router.get("")
async def list_materials(
    workflow_id: str = Query(None, description="按工作流 ID 过滤"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """素材分页列表。

    列表仅返回摘要字段，content 全文走详情接口获取，避免单次响应过大。
    """
    # 基础查询条件：workflow_id 可选过滤
    base_query = select(Material)
    count_query = select(func.count(Material.id))
    if workflow_id:
        base_query = base_query.where(Material.workflow_id == workflow_id)
        count_query = count_query.where(Material.workflow_id == workflow_id)

    total = (await db.execute(count_query)).scalar() or 0

    # 分页必须 LIMIT，防止全表扫描
    offset = (page - 1) * size
    result = await db.execute(
        base_query.order_by(Material.crawled_at.desc()).offset(offset).limit(size)
    )
    items = result.scalars().all()

    return success(data={
        "total": total,
        "list": [
            {
                "id": m.id,
                "source": m.source,
                "title": m.title,
                "summary": m.summary,
                "category": m.category,
                "status": m.status,
                "crawled_at": m.crawled_at.isoformat() if m.crawled_at else None,
                "url": m.url,
            }
            for m in items
        ],
    })


@router.get("/{material_id}")
async def get_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """查询单条素材详情（含 content 全文）。"""
    result = await db.execute(select(Material).where(Material.id == material_id))
    m = result.scalar_one_or_none()
    if m is None:
        raise NotFoundError("素材不存在")
    return success(data={
        "id": m.id,
        "source": m.source,
        "source_type": m.source_type,
        "title": m.title,
        "content": m.content,
        "summary": m.summary,
        "url": m.url,
        "published_at": m.published_at.isoformat() if m.published_at else None,
        "crawled_at": m.crawled_at.isoformat() if m.crawled_at else None,
        "category": m.category,
        "status": m.status,
        "workflow_id": m.workflow_id,
    })
