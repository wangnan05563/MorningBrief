"""B 端稿件查询与编辑路由。

供运营后台工作流产物查看使用：按 script_id 查稿件详情，或按 workflow_id 查稿件。
一个工作流只产出一份稿件，workflow_id 查询返回单条（非列表）。
支持稿件级手动编辑：编辑/增删 segment，重算 full_text/total_words/estimated_duration。
"""
import json
import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.exceptions import BizError, NotFoundError
from app.core.response import success
from app.database import get_db
from app.models import AuditLog, Script
from app.models.script import ScriptStatus
from app.workflow.llm import sensitive_filter
from app.workflow.llm.rewriter import WORDS_PER_MINUTE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/v1/scripts", tags=["B端-稿件管理"])

# 稿件不存在错误消息常量（统一字面量，避免 S1192 字符串重复告警）
_SCRIPT_NOT_FOUND_MSG = "稿件不存在"


def _script_to_dict(s: Script) -> dict:
    """序列化稿件（含分段、全文、引用素材、分类等完整字段）。"""
    return {
        "id": s.id,
        "workflow_id": s.workflow_id,
        "episode_date": s.episode_date.isoformat() if s.episode_date else None,
        "full_text": s.full_text,
        "segments": s.segments or [],
        "total_words": s.total_words,
        "estimated_duration": s.estimated_duration,
        "referenced_materials": s.referenced_materials or [],
        "categories": s.categories or [],
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("")
async def get_script_by_workflow(
    workflow_id: str = Query(..., description="按工作流 ID 查询稿件"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """按 workflow_id 查询稿件（一个工作流只有一份稿件）。

    用 GET + query 参数而非路径参数，避免与 /{script_id} 路由冲突。
    """
    result = await db.execute(
        select(Script).where(Script.workflow_id == workflow_id).limit(1)
    )
    s = result.scalar_one_or_none()
    if s is None:
        raise NotFoundError("该工作流暂无稿件")
    return success(data=_script_to_dict(s))


@router.get("/{script_id}")
async def get_script(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """按 script_id 查询稿件详情。"""
    result = await db.execute(select(Script).where(Script.id == script_id))
    s = result.scalar_one_or_none()
    if s is None:
        raise NotFoundError(_SCRIPT_NOT_FOUND_MSG)
    return success(data=_script_to_dict(s))


# ===== 稿件级手动编辑（方案 B） =====


class SegmentItem(BaseModel):
    """单个分段的结构校验。"""
    title: str = Field(..., min_length=1, max_length=256, description="段标题")
    content: str = Field(..., min_length=1, description="段正文")
    material_ids: list[int] = Field(default_factory=list, description="引用素材 ID 列表")


class UpdateSegmentsRequest(BaseModel):
    """更新稿件分段的请求体。"""
    segments: list[SegmentItem] = Field(..., min_length=1, description="完整分段列表（覆盖写入）")


@router.put("/{script_id}/segments")
async def update_segments(
    script_id: int,
    req: UpdateSegmentsRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """手动编辑稿件分段（覆盖写入）。

    运营在改写稿件 Tab 编辑/增删 segment 后调用，后端：
    1. 校验稿件状态为 draft（approved/rejected 锁定不可编辑）
    2. 敏感词扫描（命中返回 warning 但仍保存，与 LLM 二次替换策略一致）
    3. 重排 seq（1,2,3...）保证连续
    4. 重算 full_text / total_words / estimated_duration
    """
    result = await db.execute(select(Script).where(Script.id == script_id))
    s = result.scalar_one_or_none()
    if s is None:
        raise NotFoundError(_SCRIPT_NOT_FOUND_MSG)

    # approved/rejected 稿件已进入或退出审核流程，锁定不可编辑
    if s.status != ScriptStatus.draft.value:
        raise BizError(f"稿件状态为 {s.status}，仅 draft 状态可编辑")

    # 敏感词扫描：收集所有命中段，返回 warning 但不阻断保存
    sensitive_hits = []
    for idx, seg in enumerate(req.segments, start=1):
        if sensitive_filter.contains(seg.content):
            sensitive_hits.append({"seq": idx, "title": seg.title})

    # 重排 seq 并组装 segments JSON
    # 保留原 segments 中的 start_sec/end_sec 若存在，但按新内容重算
    new_segments = []
    for idx, seg in enumerate(req.segments, start=1):
        new_segments.append({
            "seq": idx,
            "title": seg.title,
            "content": seg.content,
            "material_ids": seg.material_ids,
        })

    # 重算 full_text / total_words / estimated_duration
    full_text = "\n\n".join(seg["content"] for seg in new_segments)
    total_words = sum(len(seg["content"]) for seg in new_segments)
    estimated_duration = int(total_words / WORDS_PER_MINUTE * 60)

    s.segments = new_segments
    s.full_text = full_text
    s.total_words = total_words
    s.estimated_duration = estimated_duration
    await db.commit()

    if sensitive_hits:
        logger.warning(
            "稿件 %s 手动编辑后含敏感词 %d 段: %s",
            script_id, len(sensitive_hits), sensitive_hits,
        )

    return success(data={
        **_script_to_dict(s),
        "sensitive_warning": sensitive_hits,
    })


@router.delete("/{script_id}")
async def delete_script(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """硬删除稿件记录。

    仅 admin 角色可调用。不做状态校验：审核流程外的物理清理场景
    （如脏数据清理、运营误操作回滚）需要无前置条件删除。
    关联数据（segments 等存储在 JSON 字段内）随记录一并清除。
    """
    result = await db.execute(select(Script).where(Script.id == script_id))
    s = result.scalar_one_or_none()
    if s is None:
        raise NotFoundError(_SCRIPT_NOT_FOUND_MSG)

    await db.execute(delete(Script).where(Script.id == script_id))
    # 审计日志：稿件硬删除不可恢复，记录关联 workflow_id 便于追溯历史节目归属
    db.add(AuditLog(
        category="script",
        action="delete",
        target=str(script_id),
        operator=admin.username,
        detail=json.dumps({"script_id": script_id, "workflow_id": s.workflow_id}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"deleted": script_id})
