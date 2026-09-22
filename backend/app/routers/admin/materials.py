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
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.exceptions import NotFoundError, BizError
from pathlib import Path

from app.core.response import success
from app.database import get_db
from app.models import AuditLog, Material, MaterialSourceType, MaterialStatus
from app.services.document_ingest import parse_document, compute_content_hash, UnsupportedFormatError

router = APIRouter(prefix="/admin/api/v1/materials", tags=["B端-素材管理"])

# 素材不存在错误消息常量（统一字面量，避免 S1192 字符串重复告警）
_MATERIAL_NOT_FOUND_MSG = "素材不存在"


class MaterialCreateRequest(BaseModel):
    """手动新增素材请求体。

    source_type 取值（应用层校验，DB 层无 CHECK 约束）：
    - list：手动录入 / 文档上传（无真实 URL，用 content_hash 去重）
    - rss：通用资讯 RSS 爬取
    - book_rss：书籍 RSS 预制源（仅 audiobook 频道）
    - cos：云端对象存储导入
    - api：API / 网页 URL 拉取
    - qrcode：二维码 / 链接分享进入的手动录入门户
    """
    workflow_id: str
    channel_id: Optional[int] = None
    source: str
    title: str
    content: str
    # url 对 list 类型无需提供（路由内部按 content_hash 合成）；
    # 非 list 类型（rss/book_rss/api/qrcode）缺失时由 _persist_material 返回 400
    url: Optional[str] = None
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
    """入库单条素材，按 source_type 选择去重策略（list/cos 用 dedup_key，其余用 url）。

    list / cos 无真实 Web URL（cos 为对象存储 key，非可访问 URL），url 用合成值
    {source_type}://{channel_id}/{dedup_key[:16]} 满足 NOT NULL + 唯一约束；
    去重判定走 (source_type, dedup_key)。rss/book_rss/api/qrcode 有真实 URL，走 url 唯一键。
    """
    if source_type in (MaterialSourceType.list.value, MaterialSourceType.cos.value):
        key = dedup_key or compute_content_hash(content)
        dup = await db.execute(
            select(Material.id).where(
                Material.source_type == source_type,
                Material.dedup_key == key,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise BizError(code=409, message="素材内容已存在（重复上传）")
        synthetic_url = f"{source_type}://{channel_id or 0}/{key[:16]}"
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
            raise BizError(code=400, message="非 list 类型素材（rss/book_rss/cos/api/qrcode）必须提供 url")
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
    keyword: str = Query(None, description="按标题/来源模糊搜索（素材库管理页用）"),
    status: str = Query(None, description="按状态过滤（pending/selected/skipped）"),
    # T00775：精确过滤（绕开 keyword 的 LIKE 语义，避免标题含 % / _ 时被当作通配符）
    material_id: int = Query(None, description="按素材 ID 精确过滤（讲书稿书单「素材 ID」深链定位用）"),
    source: str = Query(None, description="按来源（书名）精确过滤（按书聚合视图点书名进明细用）"),
    source_type: str = Query(None, description="按录入渠道过滤（list/cos=书稿文档，rss/book_rss=资讯与书评源，api/qrcode=外部拉取）"),
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
    # T00716：素材库管理页的查询能力（标题/来源模糊 + 状态过滤）
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        base_query = base_query.where(Material.title.like(like) | Material.source.like(like))
        count_query = count_query.where(Material.title.like(like) | Material.source.like(like))
    if status:
        base_query = base_query.where(Material.status == status)
        count_query = count_query.where(Material.status == status)
    # T00775：精确过滤优先于模糊 keyword（两者同时传时取交集）
    if material_id is not None:
        base_query = base_query.where(Material.id == material_id)
        count_query = count_query.where(Material.id == material_id)
    if source and source.strip():
        base_query = base_query.where(Material.source == source.strip())
        count_query = count_query.where(Material.source == source.strip())
    # T00775：按录入渠道过滤——「书稿素材」（list/cos）常被海量 RSS 资讯挤出前几页，
    # 素材库管理页据此提供「只看书稿」筛选，避免"翻不到素材"。非法值显式报 400，
    # 不做静默忽略（否则前端以为筛选生效但结果未过滤）。
    if source_type:
        allowed_types = {t.value for t in MaterialSourceType}
        if source_type not in allowed_types:
            raise BizError(
                code=400,
                message=f"不支持的 source_type: {source_type}（允许：{', '.join(sorted(allowed_types))}）",
            )
        base_query = base_query.where(Material.source_type == source_type)
        count_query = count_query.where(Material.source_type == source_type)

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


@router.get("/aggregate")
async def aggregate_materials(
    channel_id: int = Query(None, description="按频道 ID 过滤（素材是频道级素材池，聚合视图须先选频道）"),
    keyword: str = Query(None, description="按书名（来源）模糊搜索"),
    status: str = Query(None, description="按状态过滤（pending/selected/skipped），仅统计命中该状态的章节"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """按书聚合浏览素材（T00775 遗留建议）：一行一本书，解决「章节零散找不到整本书」。

    聚合键 = `Material.source`（文档上传时后端已自动写为书名，与讲书稿 book_key 同源）。
    返回每本书的：书名、分类、章节数、待消费章节数、最近入库时间、代表素材 ID
    （点书名进入明细时用 ?source=书名 精确过滤，列表项据此全部命中同一本书）。

    注意：本路由必须声明在 `/{material_id}` 之前，否则路径会被当作素材 ID 解析。
    """
    conds = []
    if channel_id is not None:
        conds.append(Material.channel_id == channel_id)
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        conds.append(Material.title.like(like) | Material.source.like(like))
    if status:
        conds.append(Material.status == status)

    total = (await db.execute(
        select(func.count(func.distinct(Material.source))).where(*conds)
    )).scalar() or 0

    pending_expr = func.sum(case((Material.status == MaterialStatus.pending.value, 1), else_=0))
    rows = (await db.execute(
        select(
            Material.source,
            func.count(Material.id).label("chapters"),
            pending_expr.label("pending"),
            func.min(Material.id).label("sample_id"),
            func.max(Material.category).label("category"),
            func.max(Material.crawled_at).label("latest_at"),
        )
        .where(*conds)
        .group_by(Material.source)
        .order_by(func.max(Material.crawled_at).desc())
        .offset((page - 1) * size)
        .limit(size)
    )).all()

    return success(data={
        "total": int(total),
        "list": [
            {
                "source": src,
                "category": cat,
                "chapters": int(ch),
                "pending_chapters": int(pd or 0),
                "sample_material_id": int(sid),
                "latest_at": latest.isoformat() if latest else None,
            }
            for src, ch, pd, sid, cat, latest in rows
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

    去重按 source_type 分流：list 走 dedup_key（合成 url），其余类型走 url 唯一约束。
    workflow_id 为运行期临时关联，可空。
    """
    # 应用层校验 source_type 合法性（DB 层已无 CHECK 约束，枚举扩展无需迁移）
    allowed_types = {t.value for t in MaterialSourceType}
    if req.source_type not in allowed_types:
        raise BizError(
            code=400,
            message=f"不支持的 source_type: {req.source_type}（允许：{', '.join(sorted(allowed_types))}）",
        )
    # list 类型无真实 URL（合成 url + dedup_key），其余类型必须提供真实 url
    is_list = req.source_type == MaterialSourceType.list.value
    m = await _persist_material(
        db,
        channel_id=req.channel_id,
        source=req.source,
        title=req.title,
        content=req.content,
        category=req.category,
        source_type=req.source_type,
        url=None if is_list else req.url,
        dedup_key=compute_content_hash(req.content) if is_list else None,
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


@router.delete("")
async def delete_materials_by_source(
    source: str = Query(..., min_length=1, max_length=64,
                        description="按书名（来源）精确删除该本书的全部章节素材"),
    channel_id: int = Query(None, description="限定频道，聚合视图删除应传当前筛选频道"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """按书名（source）批量删除整本书的素材（T00895）。

    素材库「按书聚合」视图一行对应一本书的多条章节素材；为保证事务一致，
    用一条 DELETE 按 source 精确删除，而非前端逐条调用 DELETE /{material_id}。
    与单条删除一致采用硬删除（Material 无被引用外键），并记录删除总数的审计日志。
    注意：本空路径路由须在 /{material_id} 之前声明，避免路径被当作素材 ID 解析。
    """
    conds = [Material.source == source]
    if channel_id is not None:
        conds.append(Material.channel_id == channel_id)
    ids = (await db.execute(select(Material.id).where(*conds))).scalars().all()
    if not ids:
        return success(data={"deleted": 0, "message": "该书名下无关联素材"})
    for mid in ids:
        await db.delete(await db.get(Material, mid))
    db.add(AuditLog(
        category="material", action="delete", target=source, operator=admin.username,
        detail=json.dumps({"source": source, "deleted_count": len(ids)}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"deleted": len(ids)})


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
    source: str = Form("文档上传", description="素材来源名称（即书名，用于按书聚合）"),
    category: Optional[str] = Form(None, description="可选分类"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """上传专业资料文档，解析为章节素材批量入库（MVP 输入适配器）。

    支持 .txt / .md；.pdf / .docx / .html 需安装对应解析库（见 UnsupportedFormatError 提示）。
    每个章节作为一条 source_type=list 素材入库，按 content_hash 去重，避免重复上传。
    """
    raw = await file.read()
    fname = file.filename or "document.txt"
    try:
        chapters = parse_document(fname, raw)
    except UnsupportedFormatError as e:
        raise BizError(code=400, message=str(e))

    # T00656 用户反馈：整本书按章节拆分后"零散难辨、无法整本挑选"。
    # 以文件名（去扩展名）作为**书名**：「来源」自动置为书名（用户显式填写非默认来源时尊重输入）、
    # 章节 title 加「书名 · 」前缀——素材库/讲书候选列表据此按书聚合（book_pool 的 book_key＝source），
    # 实现整本挑选与讲解顺序聚合。去重键为章节 content_hash，不受影响（重复上传仍会被跳过）。
    book_name = Path(fname).stem.strip() or "未命名书稿"
    if source in ("", "文档上传"):
        source = book_name

    created = []
    for ch in chapters:
        m = await _persist_material(
            db,
            channel_id=channel_id,
            source=source,
            title=f"{book_name} · {ch.title}"[:256],
            content=ch.content,
            category=category,
            source_type=MaterialSourceType.list.value,
            dedup_key=compute_content_hash(ch.content),
        )
        created.append(_material_to_dict(m))
    return success(data={"count": len(created), "list": created})


class ImportUrlRequest(BaseModel):
    """从 URL / API 拉取素材请求体。

    适用于「API 接口拉取」与「二维码/链接分享」两条渠道：
    - source_type=api：对接 CMS / 知识库 / 第三方接口返回的文章页或 JSON
    - source_type=qrcode：分享链接（运营扫码后在此拉取并人工复核）
    """
    url: str
    channel_id: int
    source: str = "URL拉取"
    category: Optional[str] = None
    source_type: str = MaterialSourceType.api.value


@router.post("/import-url")
async def import_from_url(
    req: ImportUrlRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """从 URL / API 拉取并解析为单条素材入库（课程/有声读物频道均可用）。

    复用 article_parser.extract 抓取正文（支持文章页与多数 API 返回内容），
    source_type 默认 api（API 拉取），分享场景可传 qrcode。
    解析失败（无正文）返回 400，由运营改用「手动录入」补充。
    """
    if req.source_type not in (MaterialSourceType.api.value, MaterialSourceType.qrcode.value):
        raise BizError(code=400, message="import-url 仅支持 source_type=api 或 qrcode")
    from app.workflow.crawler.article_parser import extract as extract_article
    try:
        article = await extract_article(req.url)
    except Exception as e:
        raise BizError(code=400, message=f"URL 拉取失败：{str(e)[:200]}")
    content = article.get("content")
    if not content:
        raise BizError(code=400, message="无法从该 URL 提取正文，请确认链接为文章页或有效 API")
    title = article.get("title") or req.url
    m = await _persist_material(
        db,
        channel_id=req.channel_id,
        source=req.source,
        title=title,
        content=content,
        category=req.category,
        source_type=req.source_type,
        url=req.url,
        cover_url=article.get("cover_url"),
    )
    return success(data=_material_to_dict(m))


class ImportCosRequest(BaseModel):
    """从云端对象存储（COS）导入素材请求体。

    适用于「云端存储导入」渠道：团队素材已存对象存储，按 key 取回后解析为章节素材。
    """
    key: str
    channel_id: int
    source: str = "COS导入"
    category: Optional[str] = None


@router.post("/import-cos")
async def import_from_cos(
    req: ImportCosRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """从 COS 对象导入并解析为章节素材批量入库（source_type=cos）。

    每个章节作为一条素材入库，按 content_hash 去重，避免重复导入。
    COS 未配置时返回 400 提示先配置；不支持的扩展名返回 400。
    """
    from app.services.cos_storage_service import CosStorageService
    from app.services.document_ingest import parse_document, compute_content_hash, UnsupportedFormatError

    svc = CosStorageService()
    try:
        raw = await svc.get_object_bytes(req.key)
    except BizError:
        raise
    except Exception as e:
        raise BizError(code=400, message=f"COS 对象读取失败：{str(e)[:200]}")

    filename = req.key.rsplit("/", 1)[-1] or "cos_object"
    try:
        chapters = parse_document(filename, raw)
    except UnsupportedFormatError as e:
        raise BizError(code=400, message=str(e))

    created = []
    for ch in chapters:
        m = await _persist_material(
            db,
            channel_id=req.channel_id,
            source=req.source,
            title=ch.title,
            content=ch.content,
            category=req.category,
            source_type=MaterialSourceType.cos.value,
            dedup_key=compute_content_hash(ch.content),
        )
        created.append(_material_to_dict(m))
    return success(data={"count": len(created), "list": created})


class SharePreviewRequest(BaseModel):
    """二维码/链接分享预览请求体。

    分享进入后先拉取链接内容预览，运营人工复核后再通过手动录入（source_type=qrcode）正式入库。
    """
    url: str
    channel_id: int


@router.post("/share")
async def share_preview(
    req: SharePreviewRequest,
    admin: AdminPayload = Depends(require_admin),
):
    """二维码/链接分享进入的预览门户（不直接入库）。

    拉取分享链接的正文预览，返回 title/content 供前端预填「手动录入」表单
    （source_type=qrcode），由运营复核后提交，避免自动入库脏数据。
    """
    from app.workflow.crawler.article_parser import extract as extract_article
    try:
        article = await extract_article(req.url)
    except Exception as e:
        return success(data={"url": req.url, "available": False, "error": str(e)[:200]})
    content = article.get("content")
    title = article.get("title") or req.url
    return success(data={
        "url": req.url,
        "title": title,
        "content": content,
        "source_type": MaterialSourceType.qrcode.value,
        "available": bool(content),
    })
