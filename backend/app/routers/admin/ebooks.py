"""B 端「找书工具」路由（T00601 / T00603：听书频道资料渠道产品化）。

端点：
- GET /admin/api/v1/ebooks/categories  列出书源全部分类
- GET /admin/api/v1/ebooks/search      按关键词检索书名/作者，返回下载链接

定位：把「找书」自动化；**取件（下载）仍由人工完成**——书源链接指向城通网盘，实测其落地页为
JS 交互页、无下载直链，无法稳定程序化取件。下载到 EPUB/DOCX 后走现有「素材录入」上传入库
（document_ingest 支持 .epub/.docx/.html/.txt/.md），再由 outline 策略按章节改写为讲书稿。

⚠️ 授权提示（转载自书源仓库自带声明）：其内容均从网上搜集，明示「请勿用于商业目的」。
   对外发布频道内容前请自行确认授权。

所有端点需要管理员权限。书源仓库不可达时返回可读的业务错误。
"""
import asyncio

from fastapi import APIRouter, Depends, Query

from app.core.auth import AdminPayload, require_admin
from app.core.exceptions import BizError
from app.core.response import success
from app.services import ebook_source_service as svc

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
    category: str | None = Query(None, max_length=50, description="限定分类，如「文学」；不传则全量扫描"),
    limit: int = Query(20, ge=1, le=100, description="命中上限"),
    _: AdminPayload = Depends(require_admin),
):
    """按关键词检索书源，返回书名/作者/分类/下载链接。

    说明：`scanned_categories`/`failed_categories` 回传扫描覆盖范围，便于前端提示
    「全量扫描较慢」「部分分类拉取失败」等实情，避免结果被误读为「书源里没有这本书」。
    """
    try:
        res = await asyncio.to_thread(svc.search, keyword, category, limit, False)
    except Exception as e:
        raise BizError(code=400, message=f"书源仓库访问失败：{e}")
    return success(data=res)
