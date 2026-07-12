"""工作流服务：查询工作流状态、手动触发、重跑。

注意：实际的工作流执行（爬虫→LLM→TTS→拼接）在 Phase 3 实现，
本服务仅提供查询和状态管理接口，供运营后台监控使用。
"""
from datetime import date

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError, NotFoundError, ParamError
from app.models import (
    Episode,
    Material,
    PlayLog,
    PlayProgress,
    Review,
    Script,
    Workflow,
    WorkflowStep,
)
from app.models.workflow import WorkflowStatus


class WorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_today_workflow(self) -> dict | None:
        """获取今日工作流状态（含步骤明细）。"""
        today = date.today()
        result = await self.db.execute(
            select(Workflow)
            .where(Workflow.episode_date == today)
            .order_by(Workflow.started_at.desc())
            .limit(1)
        )
        workflow = result.scalar_one_or_none()
        if workflow is None:
            return None
        return await self._workflow_to_dict(workflow)

    async def list_workflows(self, page: int, size: int, channel_id: int | None = None) -> dict:
        """历史工作流分页列表（含每条工作流的 steps_summary，供列表页进度条展示）。"""
        count_stmt = select(func.count(Workflow.id))
        if channel_id is not None:
            count_stmt = count_stmt.where(Workflow.channel_id == channel_id)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * size
        stmt = (
            select(Workflow)
            .order_by(Workflow.started_at.desc())
            .offset(offset)
            .limit(size)
        )
        if channel_id is not None:
            stmt = stmt.where(Workflow.channel_id == channel_id)
        result = await self.db.execute(stmt)
        workflows = result.scalars().all()

        # 批量查询当前页所有工作流的步骤，按 workflow_id 分组
        # 避免逐条查询导致 N+1 问题
        workflow_ids = [wf.id for wf in workflows]
        steps_by_wf: dict[str, list[dict]] = {}
        if workflow_ids:
            step_result = await self.db.execute(
                select(WorkflowStep)
                .where(WorkflowStep.workflow_id.in_(workflow_ids))
                .order_by(WorkflowStep.id)
            )
            for s in step_result.scalars().all():
                steps_by_wf.setdefault(s.workflow_id, []).append({
                    "name": s.step_name,
                    "status": s.status,
                    "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                    "error": s.error,
                })

        return {
            "total": total,
            "list": [
                {
                    "id": wf.id,
                    "episode_date": wf.episode_date.isoformat() if wf.episode_date else None,
                    "source": wf.source if wf.source else None,
                    "status": wf.status if wf.status else None,
                    "started_at": wf.started_at.isoformat() if wf.started_at else None,
                    "finished_at": wf.finished_at.isoformat() if wf.finished_at else None,
                    "steps_summary": steps_by_wf.get(wf.id, []),
                }
                for wf in workflows
            ],
        }

    async def get_workflow_detail(self, workflow_id: str) -> dict:
        """工作流详情（含步骤状态）。"""
        result = await self.db.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        if workflow is None:
            raise NotFoundError("工作流不存在")

        return await self._workflow_to_dict(workflow)

    async def _workflow_to_dict(self, workflow: Workflow) -> dict:
        """序列化工作流，含步骤明细。"""
        # 查步骤
        result = await self.db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == workflow.id)
            .order_by(WorkflowStep.id)
        )
        steps = result.scalars().all()

        return {
            "workflow_id": workflow.id,
            "episode_date": workflow.episode_date.isoformat() if workflow.episode_date else None,
            "source": workflow.source if workflow.source else None,
            "status": workflow.status if workflow.status else None,
            "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
            "finished_at": workflow.finished_at.isoformat() if workflow.finished_at else None,
            "error": workflow.error,
            "steps": [
                {
                    "name": s.step_name if s.step_name else None,
                    "status": s.status if s.status else None,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                    "retry_count": s.retry_count,
                    "error": s.error,
                }
                for s in steps
            ],
        }

    async def batch_delete_workflows(self, workflow_ids: list[str]) -> dict:
        """批量删除工作流（事务级联删除全部关联数据）。

        级联范围（依赖反序）：
            play_log / play_progress → episode → review → script → material
            → workflow_step → workflow

        设计要点：
        - running / queued 状态拒绝删除：running 表示 worker 正在写数据，
          queued 表示内存队列已持有引用，强删会导致 worker 取出已删记录或外键悬空
        - 全部校验和删除放在单一事务（async with session.begin()）中：
          任一校验失败或删除异常都整批回滚，绝不留下部分删除的孤儿数据
        - 先查 episode_ids 再删 play_log/play_progress：PlayLog/PlayProgress
          通过 episode_id 关联，必须先收集再删，否则 episode 删除后无法定位
        - SQL delete 不触发 ORM cascade，故所有从表显式删除
        """
        # 空列表拒绝：避免 no-op 调用掩盖上游 bug
        if not workflow_ids:
            raise ParamError("workflow_ids 不能为空")

        # async with session.begin() 保证块内所有操作在同一事务中：
        # 正常退出 → commit；抛异常 → 自动 rollback
        async with self.db.begin():
            # ---- 校验阶段：任一失败立即抛出，事务自动回滚 ----
            result = await self.db.execute(
                select(Workflow.id, Workflow.status).where(Workflow.id.in_(workflow_ids))
            )
            workflows = {row[0]: row[1] for row in result.all()}

            # 所有 ID 必须存在，避免静默跳过不存在的记录
            missing_ids = set(workflow_ids) - set(workflows.keys())
            if missing_ids:
                raise NotFoundError(f"工作流不存在: {', '.join(sorted(missing_ids))}")

            # running/queued 状态拒绝删除（worker 可能正在写或即将取出）
            blocked_statuses = {WorkflowStatus.running.value, WorkflowStatus.queued.value}
            blocked_ids = [
                wf_id for wf_id, status in workflows.items() if status in blocked_statuses
            ]
            if blocked_ids:
                raise BizError(
                    code=409,
                    message=f"运行中或排队中的工作流不能删除: {', '.join(sorted(blocked_ids))}",
                    http_status=409,
                )

            # ---- 删除阶段：依赖反序，先删叶子表 ----
            # 先收集 episode_ids：PlayLog/PlayProgress 通过 episode_id 关联，
            # 必须在 Episode 删除前取出列表，否则后续无法定位播放数据
            ep_result = await self.db.execute(
                select(Episode.id).where(Episode.workflow_id.in_(workflow_ids))
            )
            episode_ids = [row[0] for row in ep_result.all()]

            if episode_ids:
                await self.db.execute(
                    delete(PlayLog).where(PlayLog.episode_id.in_(episode_ids))
                )
                await self.db.execute(
                    delete(PlayProgress).where(PlayProgress.episode_id.in_(episode_ids))
                )

            await self.db.execute(
                delete(Episode).where(Episode.workflow_id.in_(workflow_ids))
            )
            await self.db.execute(
                delete(Review).where(Review.workflow_id.in_(workflow_ids))
            )
            await self.db.execute(
                delete(Script).where(Script.workflow_id.in_(workflow_ids))
            )
            await self.db.execute(
                delete(Material).where(Material.workflow_id.in_(workflow_ids))
            )
            await self.db.execute(
                delete(WorkflowStep).where(WorkflowStep.workflow_id.in_(workflow_ids))
            )
            await self.db.execute(
                delete(Workflow).where(Workflow.id.in_(workflow_ids))
            )

        return {"deleted": workflow_ids}
