"""B 端「找书工具」路由（T00601 / T00603：听书频道资料渠道产品化）。

端点：
- GET /admin/api/v1/ebooks/categories  列出书源全部分类
- GET /admin/api/v1/ebooks/search      按关键词检索书名/作者，返回下载链接
- GET /admin/api/v1/ebooks/index/status  书源索引状态（就绪/构建进度）
- POST /admin/api/v1/ebooks/index/rebuild 重建书源索引（后台执行）
- POST /admin/api/v1/ebooks/draft-material 加入待讲书单（写待上传书稿的素材占位）

定位：把「找书」自动化；**取件（下载）仍由人工完成**——书源链接指向城通网盘，实测其落地页为
JS 交互页、无下载直链，无法稳定程序化取件。下载到 EPUB/DOCX 后走现有「素材录入」上传入库
（document_ingest 支持 .epub/.docx/.html/.txt/.md），再由 outline 策略按章节改写为讲书稿。

⚠️ 授权提示（转载自书源仓库自带声明）：其内容均从网上搜集，明示「请勿用于商业目的」。
   对外发布频道内容前请自行确认授权。

所有端点需要管理员权限。书源仓库不可达时返回可读的业务错误。
"""
import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, require_admin
from app.core.exceptions import BizError
from app.core.response import success
from app.core.timeutil import localnow_naive
from app.database import get_db
from app.models import Material
from app.models.material import MaterialStatus
from app.services import ebook_index_service, ebook_source_service as svc

logger = logging.getLogger(__name__)


class DraftMaterialRequest(BaseModel):
    """找书工具「加入待讲书单」请求体（T00626 P2）。"""

    title: str = Field(..., max_length=200, description="书名")
    author: str | None = Field(None, max_length=120, description="作者")
    category: str | None = Field(None, max_length=50, description="书源分类")
    url: str = Field(..., max_length=512, description="书源链接（唯一，用于去重）")
    channel_id: int | None = Field(None, description="归属频道（可选，便于后续取材）")

router = APIRouter(prefix="/admin/api/v1/ebooks", tags=["admin-ebooks"])


@router.get("/categories")
async def list_categories(
    force: bool = Query(False, description="忽略缓存强制刷新"),
    _: AdminPayload = Depends(require_admin),
):
    """列出书源的全部图书分类（用于前端下拉筛选）。"""
    try:
        cats = await asyncio.to_thread(svc.list_categories, force)
    except Exception as e:
        raise BizError(code=400, message=f"书源仓库访问失败：{e}")
    return success(data={"count": len(cats), "categories": cats})


@router.get("/search")
async def search_ebooks(
    keyword: str = Query(..., min_length=1, max_length=50, description="书名或作者关键词"),
    category: str | None = Query(None, max_length=50, description="限定分类，如「文学」；不传则走全量索引"),
    limit: int = Query(20, ge=1, le=100, description="命中上限"),
    _: AdminPayload = Depends(require_admin),
):
    """按关键词检索书源，返回书名/作者/分类/下载链接。

    检索策略（T00612：修复全量搜索超时）——书源有 1000 个分类 md（全量 ≳200MB），
    「不选分类就全量抓取」必然超过前端 15s 超时，故改为：

    1. **索引优先**：索引就绪 → 本地毫秒级检索（`index_ready=true`）；
    2. **分类快路径**：索引未就绪但指定了分类 → 只抓该分类文件（秒级，立即可用）；
    3. **其余情况**：自动触发后台索引构建并返回可读业务提示（前端轮询 `/index/status`），
       不再让请求挂到超时。
    """
    idx_svc = ebook_index_service
    # T00619：索引缺失或过期时自动后台重建（自愈）；状态随响应回传，便于前端如实提示
    auto_rebuild = idx_svc.maybe_auto_rebuild()
    if idx_svc.index_status().get("ready"):
        res = idx_svc.search_index(keyword, category, limit)
        st = idx_svc.index_status()
        res["index_stale"] = bool(st.get("stale"))
        res["index_age_days"] = st.get("age_days")
        res["auto_rebuild"] = auto_rebuild
        return success(data=res)

    if category:
        try:
            res = await asyncio.to_thread(svc.search, keyword, category, limit, False)
        except Exception as e:
            raise BizError(code=400, message=f"书源仓库访问失败：{e}")
        res["index_ready"] = False
        res["auto_rebuild"] = auto_rebuild
        return success(data=res)

    # 无分类 + 无索引：不再全量抓取（必超时），改为触发构建
    st = idx_svc.start_build_async()
    raise BizError(
        code=428,
        message=(
            "书源索引尚未构建（首次需抓取全部 1000 个分类，约 2-5 分钟），"
            "已自动开始构建，请稍后重试；也可先选择具体分类立即搜索。"
            f"（构建中：{st.get('done', 0)}/{st.get('total', 0)}）"
        ),
    )


@router.post("/draft-material")
async def create_draft_material(
    req: DraftMaterialRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """T00626 P2：找书工具「加入待讲书单」——为检索命中的书写入一条**待上传书稿**的素材占位。

    为什么是占位素材而非直接建单：取件（下载 EPUB）必须人工完成，占位素材把"这本书要讲"
    落到素材库（status=pending），运营据此在「素材录入」补齐书稿，链路可跟踪、不丢书。

    幂等：url 唯一，同一本书重复点击返回已有素材（created=false）。
    """
    url = (req.url or "").strip()
    if not url:
        raise BizError(code=400, message="书源链接必填（用于去重与追溯）")
    title = (req.title or "").strip()
    if not title:
        raise BizError(code=400, message="书名必填")

    existing = (await db.execute(select(Material).where(Material.url == url))).scalar_one_or_none()
    if existing:
        return success(data={
            "created": False, "material_id": existing.id,
            "message": f"《{title}》已在素材库（第 {existing.id} 条），无需重复加入",
        })

    material = Material(
        source=title[:64],
        source_type="book_plan",
        title=(f"《{title}》" + (f" {req.author}" if req.author else ""))[:256],
        content=(
            f"【待上传书稿】书名：{title}；作者：{req.author or '未标注'}；分类：{req.category or '未分类'}。\n"
            "请在找书工具下载 EPUB/DOCX 后，到「内容运营 → 素材录入」上传本书稿；"
            "系统会按章节解析入库，再由听书频道按单本讲书流程（见《每日听书频道专有流程规范》）改写为讲书稿。\n"
            f"书源链接：{url}"
        ),
        summary="待上传书稿（找书工具加入待讲书单）",
        url=url[:512],
        category=(req.category or None),
        status=MaterialStatus.pending,
        channel_id=req.channel_id,
        crawled_at=localnow_naive(),
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    logger.info("[ebooks] 已加入待讲书单：%s（material_id=%s）", title, material.id)
    return success(data={"created": True, "material_id": material.id, "message": f"《{title}》已加入待讲书单"})


@router.get("/index/status")
async def ebook_index_status(_: AdminPayload = Depends(require_admin)):
    """书源索引状态（前端展示就绪状态与构建进度）。"""
    return success(data=ebook_index_service.index_status())


@router.post("/index/rebuild")
async def rebuild_ebook_index(
    background: BackgroundTasks,
    _: AdminPayload = Depends(require_admin),
):
    """重建书源索引（后台执行，立即返回；进度经 /index/status 轮询）。

    为何用后台任务：构建需抓取 1000 个分类 md（约 2-5 分钟），同步执行必然触发前端超时。
    """
    background.add_task(ebook_index_service.start_build_async)
    return success(data={"started": True, "build": ebook_index_service.build_state()})
