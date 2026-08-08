"""队列查询与操作服务。

提供队列统计、任务列表、取消/改优先级/重试操作，以及执行模式配置管理。
队列状态以 SQLite workflow 表为权威源，PriorityQueue 为内存加速层。
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, update, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.core.exceptions import ParamError
from app.core.timeutil import localnow_naive
from app.models.channel import Channel
from app.models.queue_config import QueueConfig
from app.models.workflow import (
    Workflow, WorkflowStatus, WorkflowStep, WorkflowStepName, WorkflowStepStatus,
)

logger = logging.getLogger(__name__)

# 允许排序的字段白名单：避免外部传入任意字段名拼 SQL 造成注入风险
# channel_name 需通过 joinedload 的 Channel 关系排序
_SORT_FIELD_MAP = {
    "channel_name": Channel.name,
    "priority": Workflow.priority,
    "status": Workflow.status,
    "started_at": Workflow.started_at,
}


class QueueService:
    """队列查询与操作服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_queue_stats(self) -> dict:
        """各状态任务数统计。"""
        stmt = (
            select(Workflow.status, func.count(Workflow.id))
            .group_by(Workflow.status)
        )
        result = await self.db.execute(stmt)
        counts = {row[0]: row[1] for row in result.all()}
        return {
            "queued": counts.get(WorkflowStatus.queued.value, 0),
            "running": counts.get(WorkflowStatus.running.value, 0),
            "success": counts.get(WorkflowStatus.success.value, 0),
            "failed": counts.get(WorkflowStatus.failed.value, 0),
            "cancelled": counts.get(WorkflowStatus.cancelled.value, 0),
        }

    async def list_queue_tasks(
        self, status: Optional[str] = None,
        channel_id: Optional[int] = None,
        priority: Optional[int] = None,
        page: int = 1, size: int = 20,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """分页查询队列任务，返回 (任务列表, 总数)。

        排序策略：
        - 默认（sort_by/sort_order 任一为空或字段不在白名单）：
          failed 状态置顶 + started_at 倒序，确保最新失败任务优先可见
        - 指定字段：按 sort_by 字段 + sort_order 方向单一排序
        """
        conditions = []
        if status:
            conditions.append(Workflow.status == status)
        if channel_id is not None:
            conditions.append(Workflow.channel_id == channel_id)
        if priority is not None:
            conditions.append(Workflow.priority == priority)

        # 总数
        count_stmt = select(func.count(Workflow.id))
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 构建 order_by：白名单校验 + 方向控制
        # 双参数必须同时提供且字段在白名单内才走自定义排序，否则走默认
        order_clauses = self._build_order_clauses(sort_by, sort_order)

        # 显式 outerjoin Channel 并用 contains_eager 复用该 join 加载关系，
        # 避免 joinedload 自动生成 channel_1 别名导致 ORDER BY channel.name 失效
        list_stmt = (
            select(Workflow)
            .options(contains_eager(Workflow.channel))
            .outerjoin(Channel, Workflow.channel_id == Channel.id)
            .order_by(*order_clauses)
            .offset((page - 1) * size)
            .limit(size)
        )
        for cond in conditions:
            list_stmt = list_stmt.where(cond)
        result = await self.db.execute(list_stmt)
        workflows = result.scalars().unique().all()

        items = []
        for wf in workflows:
            items.append({
                "id": wf.id,
                "episode_date": wf.episode_date.isoformat(),
                "source": wf.source,
                "status": wf.status,
                "channel_id": wf.channel_id,
                "channel_name": wf.channel.name if wf.channel else None,
                "priority": wf.priority,
                "started_at": wf.started_at.isoformat() if wf.started_at else None,
                "finished_at": wf.finished_at.isoformat() if wf.finished_at else None,
                "error": wf.error,
            })
        return items, total

    @staticmethod
    def _build_order_clauses(
        sort_by: Optional[str], sort_order: Optional[str],
    ) -> list:
        """构建 order_by 子句列表。

        默认排序：failed 状态置顶（CASE 表达式）+ started_at 倒序，
        保证运维第一时间看到最新失败任务。
        自定义排序：白名单字段 + asc/desc 方向。

        双参数必须同时有效才走自定义排序，避免半残状态。
        """
        # 自定义排序：字段在白名单 + 方向有效
        if sort_by in _SORT_FIELD_MAP and sort_order in ("asc", "desc"):
            col = _SORT_FIELD_MAP[sort_by]
            return [col.asc() if sort_order == "asc" else col.desc()]

        # 默认排序：failed 状态置顶（0 < 1，failed 排前），再按 started_at 倒序
        # CASE 表达式避免在 Python 层排序，由 SQLite 完成排序
        status_priority = case(
            (Workflow.status == WorkflowStatus.failed.value, 0),
            else_=1,
        )
        return [status_priority.asc(), Workflow.started_at.desc()]

    async def cancel_task(self, workflow_id: str) -> None:
        """取消排队中任务。status=queued → cancelled，标记队列条目 cancelled=True。"""
        # DB 更新
        stmt = (
            update(Workflow)
            .where(Workflow.id == workflow_id, Workflow.status == WorkflowStatus.queued.value)
            .values(status=WorkflowStatus.cancelled.value, finished_at=localnow_naive())
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        if result.rowcount == 0:
            raise ValueError(f"任务不存在或非排队中状态: {workflow_id}")

        # 标记内存队列条目
        from app.services.workflow_scheduler import workflow_scheduler
        await workflow_scheduler.mark_entry_cancelled(workflow_id)
        logger.info("取消排队任务 workflow_id=%s", workflow_id)

    async def update_priority(self, workflow_id: str, priority: int) -> None:
        """修改优先级（仅 queued 状态）。旧条目标记 cancelled，新条目重新入队。"""
        if not 0 <= priority <= 10:
            raise ValueError("优先级范围 0-10")

        stmt = (
            update(Workflow)
            .where(Workflow.id == workflow_id, Workflow.status == WorkflowStatus.queued.value)
            .values(priority=priority)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        if result.rowcount == 0:
            raise ValueError(f"任务不存在或非排队中状态: {workflow_id}")

        # 重新入队（旧条目标记取消，新条目按新优先级入队）
        from app.services.workflow_scheduler import workflow_scheduler
        await workflow_scheduler.requeue_with_priority(workflow_id, priority)
        logger.info("修改优先级 workflow_id=%s priority=%d", workflow_id, priority)

    async def retry_task(self, workflow_id: str) -> str:
        """重试失败任务：在原工作流上从最早失败步骤断点续跑。

        自动定位 workflow_step 表中最早的 failed 步骤作为重跑起点，
        调用 workflow_scheduler.retry_workflow 保留已成功步骤的产出，
        避免重新爬取/LLM 改写等重复消耗。

        Returns:
            原工作流 ID（不创建新工作流）
        """
        # 1. 校验原工作流状态为 failed
        stmt = select(Workflow).where(
            Workflow.id == workflow_id, Workflow.status == WorkflowStatus.failed.value
        )
        wf = (await self.db.execute(stmt)).scalar_one_or_none()
        if wf is None:
            raise ValueError(f"任务不存在或非失败状态: {workflow_id}")

        # 2. 查询最早的 failed 步骤作为重跑起点
        step_stmt = (
            select(WorkflowStep)
            .where(
                WorkflowStep.workflow_id == workflow_id,
                WorkflowStep.status == WorkflowStepStatus.failed.value,
            )
            .order_by(WorkflowStep.id.asc())
            .limit(1)
        )
        failed_step = (await self.db.execute(step_stmt)).scalar_one_or_none()

        # 3a. 有明确失败步骤：从该步骤断点续跑
        if failed_step is not None:
            from app.services.workflow_scheduler import workflow_scheduler
            wf_id = await workflow_scheduler.retry_workflow(
                workflow_id,
                from_step=failed_step.step_name,
                triggered_by="queue_retry",
            )
            logger.info(
                "队列重试断点续跑 workflow_id=%s from_step=%s",
                workflow_id, failed_step.step_name,
            )
            return wf_id

        # 3b. 无 failed 步骤记录（workflow 整体异常退出未记录步骤）：
        #     兜底从第一个步骤 crawl 重跑，保留原工作流 ID
        from app.services.workflow_scheduler import workflow_scheduler
        wf_id = await workflow_scheduler.retry_workflow(
            workflow_id,
            from_step=WorkflowStepName.crawl.value,
            triggered_by="queue_retry",
        )
        logger.info(
            "队列重试兜底全量重跑 workflow_id=%s（无 failed 步骤记录）",
            workflow_id,
        )
        return wf_id

    async def batch_delete_tasks(self, workflow_ids: list[str]) -> dict:
        """批量删除队列任务（委托 WorkflowService 执行事务级联删除）。

        队列任务本质是 Workflow 记录，复用 workflow 批量删除的完整级联逻辑
        （play_log/play_progress → episode → review → script → material 重置 pending
         → workflow_step → workflow），避免重复实现导致逻辑漂移。
        running/queued 状态由 WorkflowService 统一拒绝（worker 可能正在写或即将取出）。
        任一 ID 不存在或含 blocked 状态则整批回滚，绝不留下部分删除的孤儿数据。
        """
        from app.services.workflow_service import WorkflowService
        return await WorkflowService(self.db).batch_delete_workflows(workflow_ids)

    async def get_queue_config(self) -> dict:
        """获取执行模式配置。首次调用时自动初始化默认配置。"""
        config = await self.db.get(QueueConfig, 1)
        if config is None:
            # 引用模型常量，与 workflow_scheduler._load_queue_config 保持一致
            config = QueueConfig(
                id=1,
                execution_mode=QueueConfig.DEFAULT_EXECUTION_MODE,
                max_concurrent=QueueConfig.DEFAULT_MAX_CONCURRENT,
            )
            self.db.add(config)
            await self.db.commit()
            await self.db.refresh(config)
        return {
            "execution_mode": config.execution_mode,
            "max_concurrent": config.max_concurrent,
        }

    async def update_queue_config(self, mode: str, max_concurrent: int) -> None:
        """更新配置并标记 _config_dirty（延迟生效）。"""
        if mode not in ("serial", "parallel"):
            raise ValueError("执行模式必须为 serial 或 parallel")
        if not 1 <= max_concurrent <= 5:
            raise ValueError("并发数范围 1-5")
        # 串行模式强制并发数为 1
        if mode == "serial":
            max_concurrent = 1

        config = await self.db.get(QueueConfig, 1)
        if config is None:
            # 引用模型常量初始化，再覆盖为用户指定值
            config = QueueConfig(
                id=1,
                execution_mode=QueueConfig.DEFAULT_EXECUTION_MODE,
                max_concurrent=QueueConfig.DEFAULT_MAX_CONCURRENT,
            )
            self.db.add(config)
        config.execution_mode = mode
        config.max_concurrent = max_concurrent
        config.updated_at = localnow_naive()
        await self.db.commit()

        # 通知调度器更新内存配置（延迟生效）
        from app.services.workflow_scheduler import workflow_scheduler
        await workflow_scheduler.apply_config_change(mode, max_concurrent)
        logger.info("更新队列配置 mode=%s max_concurrent=%d", mode, max_concurrent)
