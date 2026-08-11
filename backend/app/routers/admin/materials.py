"""B 端爬虫素材管理路由。

供运营后台工作流产物查看与维护使用：
- 列表查询：按 workflow_id 分页查询，不返回 content 全文
- 详情查询：返回单条素材全文
- 新增/编辑/删除：手动维护素材，需 admin 权限
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.exceptions import NotFoundError, BizError
from app.core.response import success
from app.database import get_db
from app.models import AuditLog, Material, MaterialSourceType
from app.services.document_ingest import parse_document, compute_content_hash, UnsupportedFormatError

router = APIRouter(prefix="/admin/api/v1/materials", tags=["B端-素材管理"])

# 素材不存在错误消息常量（统一字面量，避免 S1192 字符串重复告警）
_MATERIAL_NOT_FOUND_MSG = "素材不存在"


class MaterialCreateRequest(BaseModel):
    """手动新增素材请求体。

    source_type 默认 list：手动添加的素材与 rss 爬取的素材区分开，
    便于后续按来源类型筛选与统计。
    """
    workflow_id: str
    channel_id: Optional[int] = None
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
        "channel_id": m.channel_id,
        "workflow_id": m.workflow_id,
    }


async def _persist_material(
    db: AsyncSession,
    *,
    channel_id: int | None,
    source: str,
    title: str,
    content: str,
    category: str | None = None,
    source_type: str = MaterialSourceType.list.value,
    url: str | None = None,
    dedup_key: str | None = None,
) -> Material:
    """入库单条素材，按 source_type 选择去重策略（list 用 dedup_key，rss 用 url）。

    list 类型无真实 URL，url 用合成值 list://{channel_id}/{dedup_key[:16]} 满足
    NOT NULL + 唯一约束；去重判定走 (source_type, dedup_key)，与 rss 的 url 唯一键解耦。
    """
    if source_type == MaterialSourceType.list.value:
        key = dedup_key or compute_content_hash(content)
        dup = await db.execute(
            select(Material.id).where(
                Material.source_type == MaterialSourceType.list.value,
                Material.dedup_key == key,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise BizError(code=409, message="素材内容已存在（重复上传）")
        synthetic_url = f"list://{channel_id or 0}/{key[:16]}"
        m = Material(
            channel_id=channel_id,
            source=source,
            source_type=source_type,
            title=title,
            content=content,
            url=synthetic_url,
            dedup_key=key,
            category=category,
        )
    else:
        if not url:
            raise BizError(code=400, message="rss 类型素材必须提供 url")
        dup = await db.execute(select(Material.id).where(Material.url == url))
        if dup.scalar_one_or_none() is not None:
            raise BizError(code=409, message="URL 已存在")
        m = Material(
            channel_id=channel_id,
            source=source,
            source_type=source_type,
            title=title,
            content=content,
            url=url,
            category=category,
        )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@router.get("")
async def list_materials(
    workflow_id: str = Query(None, description="按工作流 ID 过滤（运行期临时关联，终态后释放，详情页改用 channel_id）"),
    channel_id: int = Query(None, description="按频道 ID 过滤（素材本质是频道级素材池，详情页用此查询）"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """素材分页列表。

    列表仅返回摘要字段，content 全文走详情接口获取，避免单次响应过大。

    过滤策略：素材属于「频道级素材池」（channel_id 始终有值，workflow_id 仅为
    运行期临时关联，工作流终态后由调度器重置为 NULL）。详情页展示某工作流的
    爬虫素材时，应传 channel_id 查询该频道素材池，而非 workflow_id——否则已完成
    工作流的素材因 workflow_id 被释放而全部落空，导致面板空白。
    """
    # 基础查询条件：workflow_id / channel_id 可选过滤（AND）
    base_query = select(Material)
    count_query = select(func.count(Material.id))
    if workflow_id:
        base_query = base_query.where(Material.workflow_id == workflow_id)
        count_query = count_query.where(Material.workflow_id == workflow_id)
    if channel_id is not None:
        base_query = base_query.where(Material.channel_id == channel_id)
        count_query = count_query.where(Material.channel_id == channel_id)

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
        raise NotFoundError(_MATERIAL_NOT_FOUND_MSG)
    return success(data=_material_to_dict(m))


@router.post("")
async def create_material(
    req: MaterialCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """手动新增素材。

    去重按 source_type 分流：rss 走 url 唯一约束，list 走 dedup_key。
    workflow_id 为运行期临时关联，可空。
    """
    m = await _persist_material(
        db,
        channel_id=req.channel_id,
        source=req.source,
        title=req.title,
        content=req.content,
        category=req.category,
        source_type=req.source_type,
        url=req.url if req.source_type == MaterialSourceType.rss.value else None,
        dedup_key=compute_content_hash(req.content) if req.source_type == MaterialSourceType.list.value else None,
    )
    # 回填运行期关联（文档上传场景无 workflow，留空）
    if req.workflow_id:
        m.workflow_id = req.workflow_id
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
        raise NotFoundError(_MATERIAL_NOT_FOUND_MSG)

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
        raise NotFoundError(_MATERIAL_NOT_FOUND_MSG)

    await db.delete(m)
    # 审计日志：硬删除不可恢复，记录操作人与素材标题便于事后追溯
    db.add(AuditLog(
        category="material",
        action="delete",
        target=str(material_id),
        operator=admin.username,
        detail=json.dumps({"material_id": material_id, "title": m.title}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"deleted": material_id})


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    channel_id: int = Form(..., description="目标课程/资料频道 ID"),
    source: str = Form("文档上传", description="素材来源名称"),
    category: Optional[str] = Form(None, description="可选分类"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """上传专业资料文档，解析为章节素材批量入库（MVP 输入适配器）。

    支持 .txt / .md；.pdf / .docx / .html 需安装对应解析库（见 UnsupportedFormatError 提示）。
    每个章节作为一条 source_type=list 素材入库，按 content_hash 去重，避免重复上传。
    """
    raw = await file.read()
    try:
        chapters = parse_document(file.filename or "document.txt", raw)
    except UnsupportedFormatError as e:
        raise BizError(code=400, message=str(e))

    created = []
    for ch in chapters:
        m = await _persist_material(
            db,
            channel_id=channel_id,
            source=source,
            title=ch.title,
            content=ch.content,
            category=category,
            source_type=MaterialSourceType.list.value,
            dedup_key=compute_content_hash(ch.content),
        )
        created.append(_material_to_dict(m))
    return success(data={"count": len(created), "list": created})
