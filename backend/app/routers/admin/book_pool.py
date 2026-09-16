"""讲书稿模式与素材池接口（T00656）。

端点（均需管理员权限）：
- GET  /admin/api/v1/channels/{id}/script-mode            模式状态（含进度/池量/书源）
- PUT  /admin/api/v1/channels/{id}/script-mode            开关切换（幂等，含书源快照/恢复）
- PUT  /admin/api/v1/channels/{id}/script-mode/schedule   取书调度参数（间隔天数/末尾循环）
- GET  /admin/api/v1/channels/{id}/book-pool              池列表（按取书顺序）
- POST /admin/api/v1/channels/{id}/book-pool/items        加入书籍（末尾追加，幂等）
- DELETE /admin/api/v1/channels/{id}/book-pool/items/{item_id}  移出池
- POST /admin/api/v1/channels/{id}/book-pool/items/{item_id}/move  上移/下移
- PUT  /admin/api/v1/channels/{id}/book-pool/order        批量重排（拖拽后保存）
- POST /admin/api/v1/channels/{id}/book-pool/progress/reset  重置进度（从头开始）
- GET  /admin/api/v1/channels/{id}/book-pool/candidates   可选书候选（素材库）
"""
import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, require_admin
from app.core.exceptions import BizError
from app.core.response import success
from app.database import get_db
from app.services import book_pool_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/v1/channels", tags=["admin-book-pool"])


class ScriptModeRequest(BaseModel):
    enabled: bool = Field(..., description="true=讲书稿模式（忽略频道书源，从素材池取书）")


class ScheduleRequest(BaseModel):
    interval_days: int | None = Field(None, ge=1, le=365, description="取书间隔天数（1=每日）")
    loop: bool | None = Field(None, description="池末尾后是否循环")


class AddBooksRequest(BaseModel):
    material_ids: list[int] = Field(default_factory=list, description="素材库中的书籍素材 ID 列表")


class ReorderRequest(BaseModel):
    item_ids: list[int] = Field(default_factory=list, description="按期望顺序排列的池项 ID")


@router.get("/{channel_id}/script-mode")
async def get_script_mode(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """讲书稿模式状态（开关 + 进度 + 池量）。"""
    state = await svc.get_state(db, channel_id)
    if not state.get("exists"):
        raise BizError(code=404, message=f"频道 {channel_id} 不存在")
    return success(data=state)


@router.put("/{channel_id}/script-mode")
async def set_script_mode(
    channel_id: int,
    req: ScriptModeRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """切换讲书稿模式：开启时快照并清空频道书源，关闭时按快照恢复（幂等）。"""
    try:
        result = await svc.set_script_mode(db, channel_id, req.enabled)
    except ValueError as e:
        raise BizError(code=404, message=str(e))
    return success(data=result)


@router.put("/{channel_id}/script-mode/schedule")
async def update_schedule(
    channel_id: int,
    req: ScheduleRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """更新取书调度：间隔天数（每日/每 N 天）与末尾是否循环。"""
    try:
        return success(data=await svc.update_schedule(db, channel_id, req.interval_days, req.loop))
    except ValueError as e:
        raise BizError(code=404, message=str(e))


@router.get("/{channel_id}/book-pool")
async def list_pool(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """池内书单（按取书顺序）+ 进度。"""
    items = await svc.list_pool(db, channel_id)
    state = await svc.get_state(db, channel_id)
    return success(data={"items": items, "total": len(items), "state": state})


@router.post("/{channel_id}/book-pool/items")
async def add_books(
    channel_id: int,
    req: AddBooksRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """把素材库中的书加入池（末尾追加；已存在则跳过，幂等）。"""
    return success(data=await svc.add_books(db, channel_id, req.material_ids))


@router.delete("/{channel_id}/book-pool/items/{item_id}")
async def remove_item(
    channel_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """从池中移除（不影响素材库；移除后重排顺序与游标语义）。"""
    ok = await svc.remove_item(db, channel_id, item_id)
    if not ok:
        raise BizError(code=404, message="池项不存在")
    return success(data={"removed": True, "items": await svc.list_pool(db, channel_id)})


@router.post("/{channel_id}/book-pool/items/{item_id}/move")
async def move_item(
    channel_id: int,
    item_id: int,
    direction: str = Query(..., pattern="^(up|down)$"),
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """上移/下移一格（小屏与无需拖拽的简单场景）。"""
    ok = await svc.move_item(db, channel_id, item_id, direction)
    if not ok:
        raise BizError(code=400, message="无法移动（已是首/末位或池项不存在）")
    return success(data={"items": await svc.list_pool(db, channel_id)})


@router.put("/{channel_id}/book-pool/order")
async def reorder(
    channel_id: int,
    req: ReorderRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """批量重排（前端拖拽后保存整体顺序）。"""
    count = await svc.reorder(db, channel_id, req.item_ids)
    return success(data={"count": count, "items": await svc.list_pool(db, channel_id)})


@router.post("/{channel_id}/book-pool/progress/reset")
async def reset_progress(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """重置进度（保留池与排序，从头开始取书）。"""
    try:
        return success(data=await svc.reset_progress(db, channel_id))
    except ValueError as e:
        raise BizError(code=404, message=str(e))


@router.get("/{channel_id}/book-pool/candidates")
async def list_candidates(
    channel_id: int,
    keyword: str = Query(None, description="按书名关键词过滤"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """可选书候选（来自素材库本频道素材；标记 in_pool 便于前端禁用）。"""
    return success(data=await svc.list_candidates(db, channel_id, keyword, page, size))


@router.post("/{channel_id}/book-pool/pick-preview")
async def pick_preview(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """预览"下一次将生成哪本书"（只读，便于运营确认顺序与间隔是否符合预期）。"""
    return success(data=await svc.pick_next_book(db, channel_id))
