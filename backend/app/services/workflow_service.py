"""工作流服务：查询工作流状态、手动触发、重跑。

注意：实际的工作流执行（爬虫→LLM→TTS→拼接）在 Phase 3 实现，
本服务仅提供查询和状态管理接口，供运营后台监控使用。
"""
from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError, NotFoundError
from app.models import Workflow, WorkflowStep
from app.redis_client import redis_client


class WorkflowService:
    def __init__(self, db: AsyncSession, redis=None):
        self.db = db
        self.redis = redis or redis_client

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

    async def list_workflows(self, page: int, size: int) -> dict:
        """历史工作流分页列表。"""
        count_result = await self.db.execute(
            select(func.count(Workflow.id))
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * size
        result = await self.db.execute(
            select(Workflow)
            .order_by(Workflow.started_at.desc())
            .offset(offset)
            .limit(size)
        )
        workflows = result.scalars().all()

        return {
            "total": total,
            "list": [
                {
                    "id": wf.id,
                    "episode_date": wf.episode_date.isoformat() if wf.episode_date else None,
                    "source": wf.source,
                    "status": wf.status.value if wf.status else None,
                    "started_at": wf.started_at.isoformat() if wf.started_at else None,
                    "finished_at": wf.finished_at.isoformat() if wf.finished_at else None,
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
            "source": workflow.source,
            "status": workflow.status.value if workflow.status else None,
            "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
            "finished_at": workflow.finished_at.isoformat() if workflow.finished_at else None,
            "error": workflow.error,
            "steps": [
                {
                    "name": s.step_name.value if s.step_name else None,
                    "status": s.status.value if s.status else None,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                    "retry_count": s.retry_count,
                    "error": s.error,
                }
                for s in steps
            ],
        }
