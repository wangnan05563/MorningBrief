"""B 端自动审批管理路由。

接口分组：
- GET  /config         获取配置（admin + operator）
- PUT  /config         更新配置（仅 admin）
- GET  /stats          统计指标（admin + operator）
- GET  /history        执行历史（admin + operator）
- POST /retry/{stat_id} 重试失败的自动审批（仅 admin，手动干预入口）
"""
import json
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.response import success, error
from app.database import get_db
from app.models import AuditLog, AutoReviewStat
from app.services.auto_review_service import AutoReviewService

router = APIRouter(prefix="/admin/api/v1/auto-review", tags=["B端-自动审批"])


class ConfigUpdateRequest(BaseModel):
    """更新自动审批配置请求体。

    所有字段必须显式传入，避免部分更新导致规则集不完整。
    """
    enabled: bool = Field(description="总开关，启用后满足规则的工作流将自动审批通过")
    require_content_safe: bool = Field(description="要求微信内容安全检测通过")
    require_steps_first_success: bool = Field(description="要求前 4 步全部一次成功（无重试）")
    keyword_whitelist: List[str] = Field(
        default_factory=list,
        description="关键词白名单（空列表表示不启用此规则）",
    )


@router.get("/config")
async def get_config(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """获取自动审批配置。admin + operator 均可查看。"""
    svc = AutoReviewService(db)
    config = await svc.get_config()
    # 解析 keyword_whitelist JSON 字符串为列表，便于前端直接使用
    import json as _json
    try:
        keywords = _json.loads(config.keyword_whitelist or "[]")
    except (ValueError, TypeError):
        keywords = []
    return success(data={
        "enabled": config.enabled,
        "require_content_safe": config.require_content_safe,
        "require_steps_first_success": config.require_steps_first_success,
        "keyword_whitelist": keywords,
        "updated_by": config.updated_by,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    })


@router.put("/config")
async def update_config(
    req: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """更新自动审批配置。仅 admin 可修改。

    配置变更会立即生效（下次工作流创建 Review 时按新配置判定）。
    变更记录写入 audit_log，便于追溯谁在何时切换了开关。
    """
    svc = AutoReviewService(db)
    config = await svc.update_config(
        enabled=req.enabled,
        require_content_safe=req.require_content_safe,
        require_steps_first_success=req.require_steps_first_success,
        keyword_whitelist=req.keyword_whitelist,
        operator=admin.username,
    )
    return success(data={
        "enabled": config.enabled,
        "require_content_safe": config.require_content_safe,
        "require_steps_first_success": config.require_steps_first_success,
        "keyword_whitelist": req.keyword_whitelist,
        "updated_by": config.updated_by,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    })


@router.get("/stats")
async def get_stats(
    start_date: Optional[date] = Query(None, description="开始日期，默认近 7 天"),
    end_date: Optional[date] = Query(None, description="结束日期，默认今天"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """获取自动审批统计指标。

    返回：总数、成功数、失败数、成功率、平均/总节省时间、失败原因分布。
    """
    svc = AutoReviewService(db)
    data = await svc.get_stats(start_date=start_date, end_date=end_date)
    return success(data=data)


@router.get("/history")
async def list_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    # 参数名不能与模块级导入的 success 函数重名，否则会遮蔽导致 None 调用错误
    success_filter: Optional[bool] = Query(None, alias="success", description="按成功/失败过滤，不传则全部"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """获取自动审批执行历史（分页）。

    按创建时间倒序，便于查看最新的自动审批尝试。
    """
    svc = AutoReviewService(db)
    data = await svc.list_history(page=page, size=size, success=success_filter)
    return success(data=data)


@router.post("/retry/{stat_id}")
async def retry_failed_auto_review(
    stat_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """手动重试失败的自动审批。仅 admin。

    场景：自动审批因临时错误（如数据库锁、网络抖动）失败后，
    管理员可手动触发重试。仅对 success=False 且关联 review 仍为 pending 的记录有效。
    """
    # 查询失败记录
    from sqlalchemy import select
    result = await db.execute(
        select(AutoReviewStat).where(AutoReviewStat.id == stat_id)
    )
    stat = result.scalar_one_or_none()
    if stat is None:
        return error(code=404, message="自动审批记录不存在")
    if stat.success:
        return error(code=400, message="该记录已成功，无需重试")
    if not stat.review_id:
        return error(code=400, message="该记录无关联审核记录，无法重试")

    # 检查关联 review 是否仍为 pending
    from app.models import Review
    from app.models.review import ReviewStatus
    review_result = await db.execute(
        select(Review).where(Review.id == stat.review_id)
    )
    review = review_result.scalar_one_or_none()
    if review is None:
        return error(code=404, message="关联审核记录不存在")
    if review.status != ReviewStatus.pending.value:
        return error(
            code=400,
            message=f"审核记录已被处理（status={review.status}），无法重试",
        )

    # 执行重试：复用 AutoReviewService.try_auto_approve
    from app.core.timeutil import localnow_naive
    svc = AutoReviewService(db)
    result_data = await svc.try_auto_approve(
        workflow_id=stat.workflow_id,
        review_id=stat.review_id,
        review_created_at=review.created_at or localnow_naive(),
    )

    # 审计日志：记录手动重试操作
    db.add(AuditLog(
        category="review",
        action="retry_auto_review",
        target=str(stat_id),
        operator=admin.username,
        detail=json.dumps({
            "stat_id": stat_id,
            "review_id": stat.review_id,
            "workflow_id": stat.workflow_id,
            "result": result_data,
        }, ensure_ascii=False),
    ))
    await db.commit()
    return success(data=result_data)
