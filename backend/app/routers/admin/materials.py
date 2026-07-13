"""B 端爬虫素材管理路由。

供运营后台工作流产物查看与维护使用：
- 列表查询：按 workflow_id 分页查询，不返回 content 全文
- 详情查询：返回单条素材全文
- 新增/编辑/删除：手动维护素材，需 admin 权限
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.exceptions import NotFoundError, BizError
from app.core.response import success
from app.database import get_db
from app.models import Material

router = APIRouter(prefix="/admin/api/v1/materials", tags=["B端-素材管理"])


class MaterialCreateRequest(BaseModel):
    """手动新增素材请求体。

    source_type 默认 list：手动添加的素材与 rss 爬取的素材区分开，
    便于后续按来源类型筛选与统计。
    """
    workflow_id: str
    source: str
    title: str
    content: str
    url: str
    category: Optional[str] = None
    source_type: str = "list"


class MaterialUpdateRequest(BaseModel):
    """编辑素材请求体，所有字段可选。

    仅更新请求中显式提供的字段，避免误清空未传字段。
    """
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None


def _material_to_dict(m: Material) -> dict:
    """素材序列化（含 content 全文），供详情/新增/编辑响应复用。"""
    return {
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
    }


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
    return success(data=_material_to_dict(m))


@router.post("")
async def create_material(
    req: MaterialCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """手动新增素材。

    url 唯一性先查重再插入，避免依赖数据库 IntegrityError 兜底，
    返回更友好的业务错误码。
    """
    # 查重放在事务前，命中则直接拒绝，省一次写操作
    dup = await db.execute(select(Material.id).where(Material.url == req.url))
    if dup.scalar_one_or_none() is not None:
        raise BizError(code=409, message="URL 已存在")

    m = Material(
        workflow_id=req.workflow_id,
        source=req.source,
        source_type=req.source_type,
        title=req.title,
        content=req.content,
        url=req.url,
        category=req.category,
        # status 走模型默认值 pending，无需显式传
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return success(data=_material_to_dict(m))


@router.put("/{material_id}")
async def update_material(
    material_id: int,
    req: MaterialUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """编辑素材。

    status 仅允许 pending/selected/skipped（与模型 CheckConstraint 对齐），
    违反返回 BizError 而非等到数据库报错。
    """
    result = await db.execute(select(Material).where(Material.id == material_id))
    m = result.scalar_one_or_none()
    if m is None:
        raise NotFoundError("素材不存在")

    if req.status is not None and req.status not in ("pending", "selected", "skipped"):
        raise BizError(code=400, message="status 仅允许 pending/selected/skipped")

    # exclude_unset 确保 PATCH 语义：仅更新请求中显式提供的字段
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(m, field, value)

    await db.commit()
    await db.refresh(m)
    return success(data=_material_to_dict(m))


@router.delete("/{material_id}")
async def delete_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """删除素材（硬删除）。

    Material 表无外键被其他表引用，可直接物理删除；
    若后续有外键依赖需改为软删除或级联检查。
    """
    result = await db.execute(select(Material).where(Material.id == material_id))
    m = result.scalar_one_or_none()
    if m is None:
        raise NotFoundError("素材不存在")

    await db.delete(m)
    await db.commit()
    return success(data={"deleted": material_id})
