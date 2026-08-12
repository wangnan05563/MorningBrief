"""工作流服务：查询工作流状态、手动触发、重跑。

注意：实际的工作流执行（爬虫→LLM→TTS→拼接）在 Phase 3 实现，
本服务仅提供查询和状态管理接口，供运营后台监控使用。
"""
from datetime import date

from sqlalchemy import delete, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError, NotFoundError, ParamError
from app.models import (
    AutoReviewStat,
    Episode,
    Material,
    PlayLog,
    PlayProgress,
    Review,
    Script,
    Workflow,
    WorkflowStep,
)
from app.models.material import MaterialStatus
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

    async def list_workflows(  # NOSONAR
        self,
        page: int,
        size: int,
        channel_id: int | None = None,
        episode_date: date | None = None,
        status: str | None = None,
        source: str | None = None,
    ) -> dict:
        """历史工作流分页列表（含每条工作流的 steps_summary，供列表页进度条展示）。

        支持按频道/节目日期/状态/来源过滤，所有过滤参数可选，None 表示不限制。
        Workflow.channel 关系 lazy="joined"，访问 wf.channel.name 不会触发额外查询。
        """
        # 动态构建 WHERE 条件：所有过滤参数 None 时退化为全表查询
        filters = []
        if channel_id is not None:
            filters.append(Workflow.channel_id == channel_id)
        if episode_date is not None:
            filters.append(Workflow.episode_date == episode_date)
        if status:
            filters.append(Workflow.status == status)
        if source:
            filters.append(Workflow.source == source)

        count_stmt = select(func.count(Workflow.id))
        if filters:
            count_stmt = count_stmt.where(*filters)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * size
        stmt = (
            select(Workflow)
            .order_by(Workflow.started_at.desc())
            .offset(offset)
            .limit(size)
        )
        if filters:
            stmt = stmt.where(*filters)
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
                    # 频道可能因 ON DELETE SET NULL 而悬空，需同时判断 channel_id 与 channel 对象
                    "channel_id": wf.channel_id,
                    "channel_name": wf.channel.name if wf.channel else None,
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
            "channel_id": workflow.channel_id,
            "channel_name": workflow.channel.name if workflow.channel else None,
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
        """批量删除工作流（事务级联删除关联数据，但保留素材）。

        级联范围（依赖反序）：
            play_log / play_progress → episode → review → script
            → material（重置为 pending + 解除关联，不删除）
            → workflow_step → workflow

        设计要点：
        - running / queued 状态拒绝删除：running 表示 worker 正在写数据，
          queued 表示内存队列已持有引用，强删会导致 worker 取出已删记录或外键悬空
        - 全部校验和删除放在单一事务（async with session.begin()）中：
          任一校验失败或删除异常都整批回滚，绝不留下部分删除的孤儿数据
        - 先查 episode_ids 再删 play_log/play_progress：PlayLog/PlayProgress
          通过 episode_id 关联，必须先收集再删，否则 episode 删除后无法定位
        - 素材保留并重置为 pending：素材是"原材料"，不应随工作流删除而丢失。
          重跑工作流时 rewrite 可直接复用，crawler_dedup 也保留避免重复爬取
        - SQL delete 不触发 ORM cascade，故所有从表显式删除
        """
        # 空列表拒绝：避免 no-op 调用掩盖上游 bug
        if not workflow_ids:
            raise ParamError("workflow_ids 不能为空")

        # 单一事务保证块内所有操作原子：正常 → commit；异常 → rollback。
        # 注意：不使用 async with self.db.begin()，因为该会话可能在请求链路上
        # 已被前置查询（如鉴权/中间件）autobegin 过，再显式 begin() 会抛
        # "A transaction is already begun" → 500。改为复用既有事务（autobegin 幂等）
        # + 结束时统一 commit/rollback，任意情况下都能正确回滚，不留孤儿数据。
        try:
            # ---- 校验阶段：任一失败立即抛出，事务回滚 ----
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
            # auto_review_stat.review_id 是 RESTRICT 外键指向 review.id，
            # 必须在删除 Review 之前清理，否则 foreign_keys=ON 下触发约束冲突 → 500。
            # 按 workflow_id 删除可覆盖本批工作流的全部自动审批统计（含 review_id 为空的失败记录）。
            await self.db.execute(
                delete(AutoReviewStat).where(AutoReviewStat.workflow_id.in_(workflow_ids))
            )
            await self.db.execute(
                delete(Review).where(Review.workflow_id.in_(workflow_ids))
            )
            await self.db.execute(
                delete(Script).where(Script.workflow_id.in_(workflow_ids))
            )
            # 素材是"原材料"，不随工作流删除而丢失：重置为 pending + 解除关联
            # 重跑工作流时 rewrite 可直接复用这些 pending 素材，无需重新爬取
            # crawler_dedup 也保留，防止爬虫重复爬取已入库的 URL
            await self.db.execute(
                update(Material)
                .where(Material.workflow_id.in_(workflow_ids))
                .values(status=MaterialStatus.pending.value, workflow_id=None)
            )
            await self.db.execute(
                delete(WorkflowStep).where(WorkflowStep.workflow_id.in_(workflow_ids))
            )
            await self.db.execute(
                delete(Workflow).where(Workflow.id.in_(workflow_ids))
            )

            # 统一提交：任一删除成功则整批生效；下方 except 负责回滚
            await self.db.commit()
        except Exception:
            # 整批回滚：校验失败或删除异常都不留部分删除的孤儿数据
            await self.db.rollback()
            raise

        return {"deleted": workflow_ids}
