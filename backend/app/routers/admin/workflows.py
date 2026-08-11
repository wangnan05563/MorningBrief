"""B 端工作流路由。"""
import asyncio
import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.response import success
from app.database import get_db
from app.models import AuditLog, Channel, Workflow, WorkflowStatus
from app.services.workflow_service import WorkflowService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/v1/workflows", tags=["B端-工作流"])


class RetryRequest(BaseModel):
    """重跑请求体。step 指定从哪一步重跑，Phase 3 生效。"""
    step: str


class TriggerRequest(BaseModel):
    """手动触发请求体。channel_id 可选，携带时使用频道级提示词。

    skip_crawl：文档上传/手动选题场景为 True，跳过爬虫步骤（素材已入库），
    工作流从 rewrite 开始。episode_date：可选节目日期，默认今天。
    """
    channel_id: int | None = None
    skip_crawl: bool = False
    episode_date: date | None = None


class BatchDeleteRequest(BaseModel):
    """批量删除请求体。

    约束 1-100 个 ID 是为了：
    - 下限 1：避免 no-op 调用掩盖上游 bug
    - 上限 100：避免单次事务过大导致长事务/锁表
    """
    workflow_ids: list[str] = Field(..., min_length=1, max_length=100, description="待删除工作流 ID 列表")

    @field_validator("workflow_ids")
    @classmethod
    def normalize_ids(cls, v: list[str]) -> list[str]:
        """去空白 + 去重 + 拒绝空串，保证下游 service 拿到规范 ID 列表。"""
        cleaned = [s.strip() for s in v if s and s.strip()]
        if not cleaned:
            raise ValueError("workflow_ids 不能全为空")
        # 去重：同一 ID 重复传入无意义且会放大删除范围断言
        unique = list(dict.fromkeys(cleaned))
        if len(unique) != len(cleaned):
            raise ValueError("workflow_ids 包含重复 ID")
        return unique


@router.get("/today")
async def get_today_workflow(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = WorkflowService(db)
    data = await svc.get_today_workflow()
    return success(data=data)


@router.get("")
async def list_workflows(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    channel_id: int | None = Query(None, description="频道 ID 筛选"),
    episode_date: date | None = Query(None, description="节目日期筛选（ISO 格式 YYYY-MM-DD）"),
    status: str | None = Query(None, description="状态筛选：queued/running/success/failed/cancelled"),
    source: str | None = Query(None, description="来源筛选：cron/manual"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """工作流分页列表，支持按频道/节目日期/状态/来源组合过滤。"""
    svc = WorkflowService(db)
    data = await svc.list_workflows(
        page=page, size=size, channel_id=channel_id,
        episode_date=episode_date, status=status, source=source,
    )
    return success(data=data)


# 静态路由必须定义在 /{workflow_id} 之前：FastAPI 按定义顺序匹配，
# 否则 "batch-delete" 会被当作 workflow_id 参数捕获
@router.post("/batch-delete")
async def batch_delete_workflows(
    req: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """批量删除工作流（仅管理员）。

    级联删除 workflow 及其全部关联数据（step/script/material/review/episode/play_log/play_progress）。
    running/queued 状态拒绝删除；任一 ID 不存在或状态非法时整批回滚。
    """
    svc = WorkflowService(db)
    data = await svc.batch_delete_workflows(req.workflow_ids)
    # 审计日志：批量删除为不可恢复的级联删除，必须记录操作人与目标 ID 便于追溯
    db.add(AuditLog(
        category="workflow",
        action="batch_delete",
        target="workflows",
        operator=admin.username,
        detail=json.dumps({"workflow_ids": req.workflow_ids, "result": data}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data=data)


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = WorkflowService(db)
    data = await svc.get_workflow_detail(workflow_id=workflow_id)
    return success(data=data)


@router.post("/trigger")
async def trigger_workflow(
    req: TriggerRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """手动触发工作流（运营后台调用）。

    支持携带 channel_id，rewrite 步骤据此读取频道级提示词。
    skip_crawl=True 时跳过爬虫（文档上传场景，素材已入库），
    episode_date 可指定节目日期（默认今天）。
    """
    from app.services.workflow_scheduler import workflow_scheduler

    workflow_id = await workflow_scheduler.trigger_workflow(
        episode_date=req.episode_date or date.today(),
        source="manual",
        channel_id=req.channel_id,
        triggered_by=admin.username,
        skip_crawl=req.skip_crawl,
    )
    # 审计日志：手动触发区别于 cron 自动触发，记录操作人便于追溯异常触发的来源
    db.add(AuditLog(
        category="workflow",
        action="trigger",
        target=workflow_id,
        operator=admin.username,
        detail=json.dumps({
            "channel_id": req.channel_id,
            "workflow_id": workflow_id,
            "skip_crawl": req.skip_crawl,
            "episode_date": (req.episode_date or date.today()).isoformat(),
        }, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"workflow_id": workflow_id, "status": "running"})


@router.post("/trigger-all")
async def trigger_all_workflows(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """全频道触发工作流（仅管理员）。

    对每个活跃频道：
    - 检查当日是否已有 running/queued 状态工作流，有则跳过并记录原因
    - 否则并发调用 trigger_workflow 入队
    - 失败的频道记录到 failed 列表，前端可对失败频道重试

    工作流实际执行进度通过现有 SSE（workflow.started/completed/failed 事件）
    + 前端 5s 轮询自动感知，无需额外推送机制。
    """
    from app.services.workflow_scheduler import workflow_scheduler

    today = date.today()

    # 按 id 排序保证返回结果稳定，便于审计日志对比与前端展示
    result = await db.execute(
        select(Channel).where(Channel.is_active == 1).order_by(Channel.id)
    )
    channels = result.scalars().all()

    if not channels:
        return success(data={
            "total": 0, "triggered": [], "skipped": [], "failed": [],
        }, message="无活跃频道")

    # 查询当日所有 running/queued 状态工作流的 channel_id，用于跳过重复触发
    # 避免同一频道多个工作流并发执行导致资源浪费和内容重复
    result = await db.execute(
        select(Workflow.channel_id).where(
            Workflow.episode_date == today,
            Workflow.status.in_([
                WorkflowStatus.queued.value,
                WorkflowStatus.running.value,
            ]),
        )
    )
    running_channel_ids = {row[0] for row in result.all()}

    async def _trigger_one(ch):
        """单频道触发协程：返回 (status, channel, reason, workflow_id)。"""
        if ch.id in running_channel_ids:
            return ("skipped", ch, "当日已有运行中工作流", None)
        try:
            wf_id = await workflow_scheduler.trigger_workflow(
                episode_date=today,
                source="manual",
                channel_id=ch.id,
                triggered_by=admin.username,
            )
            return ("triggered", ch, None, wf_id)
        except Exception as e:
            logger.exception("触发频道 %s 工作流失败", ch.id)
            return ("failed", ch, str(e), None)

    # 并发触发：trigger_workflow 仅入队（创建 queued 记录 + 放入 PriorityQueue），
    # 实际工作流执行由后台 _queue_worker 异步进行，不会阻塞本请求
    results = await asyncio.gather(*[_trigger_one(ch) for ch in channels])

    triggered, skipped, failed = [], [], []
    for status, ch, reason, wf_id in results:
        item = {"channel_id": ch.id, "channel_name": ch.name}
        if status == "triggered":
            item["workflow_id"] = wf_id
            triggered.append(item)
        elif status == "skipped":
            item["reason"] = reason
            skipped.append(item)
        else:
            item["error"] = reason
            failed.append(item)

    # 审计日志双写：AuditLog 表持久化便于后续查询统计，loguru 文件日志便于实时排查
    detail = {
        "total_channels": len(channels),
        "triggered_count": len(triggered),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "triggered": triggered,
        "skipped": skipped,
        "failed": failed,
    }
    db.add(AuditLog(
        category="workflow",
        action="trigger_all",
        target="channels",
        operator=admin.username,
        detail=json.dumps(detail, ensure_ascii=False),
    ))
    await db.commit()

    logger.info(
        "全频道触发完成 operator=%s total=%d triggered=%d skipped=%d failed=%d",
        admin.username, len(channels), len(triggered), len(skipped), len(failed),
    )

    return success(data={
        "total": len(channels),
        "triggered": triggered,
        "skipped": skipped,
        "failed": failed,
    })


@router.post("/{workflow_id}/retry")
async def retry_workflow(
    workflow_id: str,
    req: RetryRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """在原工作流上从指定步骤重跑（断点续跑）。

    删除 from_step 及其之后的步骤记录，保留之前的成功步骤，
    重置状态为 queued 后重新入队，_run_workflow 跳过已成功步骤。
    """
    from app.services.workflow_scheduler import workflow_scheduler
    from app.core.exceptions import ParamError
    from app.core.response import error

    try:
        wf_id = await workflow_scheduler.retry_workflow(
            workflow_id, from_step=req.step, triggered_by=admin.username,
        )
    except ParamError as e:
        return error(code=400, message=str(e))
    # 审计日志：断点续跑会删除部分步骤记录，记录重跑起点便于追溯内容变更范围
    db.add(AuditLog(
        category="workflow",
        action="retry",
        target=wf_id,
        operator=admin.username,
        detail=json.dumps({"from_step": req.step, "workflow_id": wf_id}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={
        "workflow_id": wf_id,
        "retry_step": req.step,
        "status": "queued",
    })
