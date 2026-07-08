"""工作流调度服务：编排 4 个工作流模块的串行执行 + APScheduler 定时任务（LLD 5.1）。

职责：
1. 注册定时任务（每日 05:00 触发、06:00 兜底、06:30 备播检查、播放日志落库、分区维护）
2. 串行执行 crawl → rewrite → tts → stitch → review，每步失败重试 3 次
3. 审核通过后发布节目（调用 ContentService.publish_episode）
4. 备播机制：06:30 检查今日 episode 未发布则复用前一日音频

设计要点：
- 单进程内调度，避免多 worker 重复触发（Dockerfile 单 worker）
- Redis 互斥锁防止并发触发（cron 与手动可能重叠）
- 每步独立 session，避免长事务跨步骤持有连接
"""
import asyncio
import logging
from datetime import date, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Episode, EpisodeStatus, Review, ReviewStatus, Workflow, WorkflowStep
from app.models.workflow import (
    WorkflowSource,
    WorkflowStatus,
    WorkflowStepName,
    WorkflowStepStatus,
)
from app.redis_client import redis_client
from app.services.content_service import ContentService
from app.services.play_service import PlayService
from app.workflow.crawler import runner as crawler_mod
from app.workflow.llm import rewriter as llm_mod
from app.workflow.tts import synthesizer as tts_mod
from app.workflow.stitch import concat as stitch_mod

logger = logging.getLogger(__name__)
settings = get_settings()


# ===== 异常定义 =====
class WorkflowConflictError(Exception):
    """已有工作流在运行，拒绝并发触发。"""


class StepFailedError(Exception):
    """单步重试耗尽仍失败。

    携带 step_name 便于上层定位失败环节并决定后续动作（告警/备播）。
    """

    def __init__(self, step_name: str, original: Exception):
        self.step_name = step_name
        self.original = original
        super().__init__(f"步骤 {step_name} 失败: {original}")


class WorkflowScheduler:
    """工作流调度服务（单例，应用启动时创建）。"""

    def __init__(self):
        self.redis = redis_client
        # 时区固定 Asia/Shanghai，确保 cron 表达式按北京时间触发
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    # ===== 生命周期 =====

    async def start(self) -> None:
        """应用启动时调用，注册全部 Cron 任务（LLD 5.1.1 / 7.5）。"""
        # 每日 05:00 触发工作流（主任务）
        self.scheduler.add_job(
            self._cron_trigger,
            trigger="cron",
            hour=settings.WORKFLOW_CRON_HOUR,
            minute=0,
            second=0,
            id="daily_workflow",
            misfire_grace_time=300,      # 错过 5 分钟内仍执行（系统休眠恢复场景）
            coalesce=True,               # 多次错过只执行一次，避免堆积
            max_instances=1,             # 同一任务最多 1 个实例在跑
            replace_existing=True,       # 应用重启时覆盖旧任务定义
        )
        # 06:00 兜底检查：若今日 workflow 未触发则补触发一次
        self.scheduler.add_job(
            self._check_workflow_started,
            trigger="cron",
            hour=6,
            minute=0,
            id="workflow_check",
            replace_existing=True,
        )
        # 06:30 备播检查：今日 episode 未发布则启用备播
        self.scheduler.add_job(
            self._check_backup,
            trigger="cron",
            hour=settings.WORKFLOW_BACKUP_CHECK_HOUR,
            minute=settings.WORKFLOW_BACKUP_CHECK_MINUTE,
            id="backup_check",
            replace_existing=True,
        )
        # 每 1 分钟消费播放日志队列（与 PlayService.flush_playlog_queue 配合）
        self.scheduler.add_job(
            self._flush_playlog_queue,
            trigger="interval",
            minutes=1,
            id="flush_playlog",
            max_instances=1,
            coalesce=True,
        )
        # 每月 1 号 02:00 维护 play_log 分区（MVP 未分区，预留扩展点）
        self.scheduler.add_job(
            self._add_playlog_partition,
            trigger="cron",
            day=1,
            hour=2,
            id="add_partition",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("WorkflowScheduler 已启动，注册 5 个定时任务")

    async def stop(self) -> None:
        """应用关闭时关闭调度器，等待运行中任务完成。"""
        self.scheduler.shutdown(wait=True)
        logger.info("WorkflowScheduler 已停止")

    # ===== 触发入口 =====

    async def _cron_trigger(self) -> None:
        """APScheduler cron 触发入口：自动确定日期与来源。"""
        today = date.today()
        await self.trigger_workflow(
            episode_date=today,
            source=WorkflowSource.cron.value,
        )

    async def trigger_workflow(
        self, episode_date: date, source: str, triggered_by: str = None
    ) -> str:
        """触发工作流，返回 workflow_id。

        Args:
            episode_date: 目标节目日期
            source: cron / manual
            triggered_by: 手动触发时记录 admin username

        Returns:
            workflow_id（如 wf-20260708-0001）

        Raises:
            WorkflowConflictError: 已有工作流在运行
        """
        # 生成 workflow_id：日期 + 当日序号，便于人工识别与日志检索
        date_str = episode_date.strftime("%Y%m%d")
        seq = await self.redis.incr(f"workflow:seq:{date_str}")
        # 序号当日有效，次日从 1 开始
        await self.redis.expire(f"workflow:seq:{date_str}", 48 * 3600)
        workflow_id = f"wf-{date_str}-{seq:04d}"

        logger.info(
            "触发工作流 workflow_id=%s date=%s source=%s triggered_by=%s",
            workflow_id, episode_date, source, triggered_by,
        )

        # 创建 workflow 记录（status=running）
        async with AsyncSessionLocal() as session:
            wf = Workflow(
                id=workflow_id,
                episode_date=episode_date,
                source=WorkflowSource(source),
                status=WorkflowStatus.running,
            )
            session.add(wf)
            await session.commit()

        # 异步执行主流程，不阻塞调度器（cron 触发后立即返回）
        asyncio.create_task(self._run_workflow(workflow_id, episode_date))
        return workflow_id

    # ===== 工作流主流程 =====

    async def _run_workflow(self, workflow_id: str, episode_date: date) -> None:
        """串行执行 6 个步骤（LLD 5.1.2）。

        前 4 步调用外部模块，第 5 步内置创建 review，第 6 步 publish 由审核通过后异步触发。
        """
        try:
            # 抢 Redis 互斥锁，防止 cron 与手动触发并发
            lock_ok = await self.redis.set(
                "workflow:lock", workflow_id,
                nx=True, ex=settings.WORKFLOW_LOCK_TTL_SEC,
            )
            if not lock_ok:
                raise WorkflowConflictError("已有工作流在运行")

            await self.redis.set("workflow:current", workflow_id)
            await self._update_workflow_status(workflow_id, WorkflowStatus.running)

            date_str = episode_date.isoformat()
            context = {
                "workflow_id": workflow_id,
                "episode_date": episode_date,
                "date_str": date_str,
            }

            # 步骤 1：爬虫（签名 run(workflow_id, date_str)）
            await self._run_step(
                workflow_id, WorkflowStepName.crawl, 1,
                lambda ctx: crawler_mod.run(ctx["workflow_id"], ctx["date_str"]),
                context,
            )

            # 步骤 2：LLM 改写（签名 rewrite(workflow_id, date_str)）
            await self._run_step(
                workflow_id, WorkflowStepName.rewrite, 2,
                lambda ctx: llm_mod.rewrite(ctx["workflow_id"], ctx["date_str"]),
                context,
            )

            # 步骤 3：TTS（签名 synthesize(workflow_id, script_id)）
            async def _tts_fn(ctx):
                return await tts_mod.synthesize(ctx["workflow_id"], ctx["script_id"])

            await self._run_step(
                workflow_id, WorkflowStepName.tts, 3, _tts_fn, context,
            )

            # 步骤 4：拼接（签名 concat(workflow_id, episode_date, audio_segments)）
            async def _stitch_fn(ctx):
                return await stitch_mod.concat(
                    ctx["workflow_id"], ctx["episode_date"], ctx["audio_segments"],
                )

            await self._run_step(
                workflow_id, WorkflowStepName.stitch, 4, _stitch_fn, context,
            )

            # 步骤 5：创建审核记录（内置方法）
            await self._run_step(
                workflow_id, WorkflowStepName.review, 5,
                self._create_review, context,
            )

            # 主流程结束（publish 由审核通过后异步触发）
            await self._update_workflow_status(workflow_id, WorkflowStatus.success)
            logger.info("工作流主流程完成 workflow_id=%s", workflow_id)

        except StepFailedError as e:
            # 某步重试耗尽仍失败：置 failed + 告警，不立即备播（等 06:30 统一处理）
            await self._update_workflow_status(
                workflow_id, WorkflowStatus.failed, error=str(e),
            )
            await self._alert_operators(
                f"工作流 {workflow_id} 失败于步骤 {e.step_name}: {e}"
            )
        except WorkflowConflictError as e:
            # 并发冲突，不算失败，仅记录
            logger.warning("工作流触发冲突 workflow_id=%s: %s", workflow_id, e)
            await self._update_workflow_status(
                workflow_id, WorkflowStatus.cancelled, error=str(e),
            )
        except Exception as e:
            # 未预期异常兜底
            logger.exception("工作流异常 workflow_id=%s", workflow_id)
            await self._update_workflow_status(
                workflow_id, WorkflowStatus.failed, error=str(e),
            )
            await self._alert_operators(f"工作流 {workflow_id} 未预期异常: {e}")
        finally:
            await self.redis.delete("workflow:lock")
            await self.redis.delete("workflow:current")

    async def _run_step(
        self, workflow_id: str, step_name: WorkflowStepName, seq: int,
        func, context: dict,
    ) -> None:
        """执行单步：记录状态 → 调用函数 → 失败重试 3 次（LLD 5.1.2）。

        退避策略：5s, 10s（指数退避），与 LLD 伪代码一致。
        """
        step_record = await self._create_step_record(workflow_id, step_name, seq)
        await self._update_step_status(step_record.id, WorkflowStepStatus.running)

        last_error = None
        for attempt in range(3):  # 最多 3 次（含首次）
            try:
                started = datetime.utcnow()
                result = await func(context)
                duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
                await self._update_step_status(
                    step_record.id, WorkflowStepStatus.success,
                    result=result, retry_count=attempt, duration_ms=duration_ms,
                )
                # 将本步产出合并到上下文供后续步骤使用
                context.update(result or {})
                logger.info(
                    "步骤完成 workflow_id=%s step=%s attempt=%d duration=%dms",
                    workflow_id, step_name.value, attempt, duration_ms,
                )
                return
            except Exception as e:
                last_error = e
                await self._update_step_status(
                    step_record.id, WorkflowStepStatus.retrying,
                    retry_count=attempt + 1, error=str(e),
                )
                logger.warning(
                    "步骤重试 workflow_id=%s step=%s attempt=%d error=%s",
                    workflow_id, step_name.value, attempt + 1, e,
                )
                if attempt < 2:
                    await asyncio.sleep(5 * (attempt + 1))  # 5s, 10s 退避

        # 3 次均失败
        await self._update_step_status(
            step_record.id, WorkflowStepStatus.failed, error=str(last_error),
        )
        raise StepFailedError(step_name.value, last_error)

    # ===== 审核与发布 =====

    async def _create_review(self, context: dict) -> dict:
        """步骤 5：从 context 取产出，创建 review 记录（status=pending）。

        review 表是审核流转的核心：运营在后台 approve/reject/replace，
        approve 时联动 ContentService.publish_episode 创建 episode。
        """
        workflow_id = context["workflow_id"]
        episode_date = context["episode_date"]
        script_id = context["script_id"]
        audio_url = context["final_audio_url"]

        async with AsyncSessionLocal() as session:
            review = Review(
                workflow_id=workflow_id,
                episode_date=episode_date,
                script_id=script_id,
                audio_url=audio_url,
                status=ReviewStatus.pending,
            )
            session.add(review)
            await session.commit()
            await session.refresh(review)
            review_id = review.id

        logger.info(
            "审核记录已创建 workflow_id=%s review_id=%s",
            workflow_id, review_id,
        )
        return {"review_id": review_id}

    async def publish(self, workflow_id: str, review_id: int) -> int:
        """审核通过后发布节目（LLD 5.1.2 第 6 步）。

        委托 ContentService.publish_episode 创建 episode 并失效缓存。
        """
        async with AsyncSessionLocal() as session:
            content_svc = ContentService(session)
            episode_id = await content_svc.publish_episode(workflow_id, review_id)

        logger.info(
            "节目已发布 workflow_id=%s review_id=%s episode_id=%s",
            workflow_id, review_id, episode_id,
        )
        return episode_id

    # ===== 备播与兜底 =====

    async def _check_workflow_started(self) -> None:
        """06:00 兜底检查：若今日无 workflow 记录则补触发一次（LLD 7.5）。

        场景：05:00 cron 因系统重启/休眠错过，misfire_grace_time 已超时。
        """
        today = date.today()
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.episode_date == today)
            )
            if result.scalar_one_or_none() is not None:
                logger.info("兜底检查：今日 workflow 已存在，跳过")
                return

        logger.warning("兜底检查：今日无 workflow 记录，补触发一次")
        await self.trigger_workflow(today, source=WorkflowSource.cron.value)

    async def _check_backup(self) -> None:
        """06:30 备播检查：今日 episode 未发布则启用备播（LLD 5.1.3）。

        策略：复用前一日已发布节目的音频，标记 is_backup=1。
        若前一日也无节目，告警人工介入。
        """
        today = date.today()

        async with AsyncSessionLocal() as session:
            # 今日已发布则无需备播
            result = await session.execute(
                select(Episode).where(
                    Episode.date == today,
                    Episode.status == EpisodeStatus.published,
                )
            )
            if result.scalar_one_or_none() is not None:
                logger.info("备播检查：今日已发布，跳过")
                return

            # 查前一日已发布节目
            yesterday = today - timedelta(days=1)
            result = await session.execute(
                select(Episode).where(
                    Episode.date == yesterday,
                    Episode.status == EpisodeStatus.published,
                )
            )
            prev = result.scalar_one_or_none()
            if prev is None:
                await self._alert_operators(
                    f"备播失败：前一日 {yesterday} 节目也不存在，需人工介入"
                )
                return

            # 创建备播 episode，复用前一日音频
            backup = Episode(
                date=today,
                title=f"{today.month}月{today.day}日 · 今日要闻（备播）",
                duration=prev.duration,
                audio_url=prev.audio_url,
                cover_url=prev.cover_url,
                script_id=prev.script_id,
                is_backup=1,
                status=EpisodeStatus.published,
                published_at=datetime.utcnow(),
            )
            session.add(backup)
            await session.commit()

        # 失效今日节目缓存，让小程序能看到备播节目
        await self.redis.delete("episode:today")
        await self._alert_operators(
            f"已启用备播（复用 {yesterday} 节目音频），请事后排查原因"
        )
        logger.warning("已启用备播 date=%s 复用=%s", today, yesterday)

    # ===== 辅助任务 =====

    async def _flush_playlog_queue(self) -> None:
        """每 1 分钟消费播放日志队列，批量落库。"""
        try:
            async with AsyncSessionLocal() as session:
                play_svc = PlayService(session)
                count = await play_svc.flush_playlog_queue()
            if count > 0:
                logger.info("播放日志落库 %d 条", count)
        except Exception as e:
            # 落库失败不中断调度器，下次调度继续处理（队列保留）
            logger.exception("播放日志落库失败: %s", e)

    async def _add_playlog_partition(self) -> None:
        """每月 1 号 02:00 维护 play_log 分区。

        MVP 阶段 play_log 未使用分区表，此方法预留扩展点。
        生产环境若启用分区，此处执行 ALTER TABLE ... ADD PARTITION。
        """
        next_month = (date.today().replace(day=1) + timedelta(days=32)).replace(day=1)
        logger.info(
            "play_log 分区维护任务触发（MVP 未分区，跳过）next_month=%s",
            next_month,
        )

    # ===== 告警 =====

    async def _alert_operators(self, message: str) -> None:
        """告警运维人员（短信 + 企业微信 webhook）。

        两种通道独立发送，任一失败不影响另一通道。
        MVP 阶段仅记录日志 + 企业微信 webhook（若配置）。
        """
        logger.error("【告警】%s", message)

        # 企业微信 webhook（若配置则发送）
        webhook = settings.ALERT_WECOM_WEBHOOK
        if webhook:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    await client.post(
                        webhook,
                        json={
                            "msgtype": "text",
                            "text": {"content": f"【20_News 告警】\n{message}"},
                        },
                        timeout=10,
                    )
            except Exception as e:
                logger.error("企业微信告警发送失败: %s", e)

    # ===== 数据库操作辅助 =====

    async def _update_workflow_status(
        self, workflow_id: str, status: WorkflowStatus, error: str = None,
    ) -> None:
        """更新 workflow 状态，失败时附加 error + finished_at。"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )
            wf = result.scalar_one_or_none()
            if wf is None:
                return
            wf.status = status
            if error:
                wf.error = error
            if status in (WorkflowStatus.success, WorkflowStatus.failed, WorkflowStatus.cancelled):
                wf.finished_at = datetime.utcnow()
            await session.commit()

    async def _create_step_record(
        self, workflow_id: str, step_name: WorkflowStepName, seq: int,
    ) -> WorkflowStep:
        """创建步骤记录（status=pending），返回 ORM 对象供后续更新。"""
        async with AsyncSessionLocal() as session:
            step = WorkflowStep(
                workflow_id=workflow_id,
                step_name=step_name,
                status=WorkflowStepStatus.pending,
                started_at=datetime.utcnow(),
            )
            session.add(step)
            await session.commit()
            await session.refresh(step)
            return step

    async def _update_step_status(
        self, step_id: int, status: WorkflowStepStatus,
        result: dict = None, retry_count: int = None,
        error: str = None, duration_ms: int = None,
    ) -> None:
        """更新步骤状态与产出。"""
        async with AsyncSessionLocal() as session:
            result_q = await session.execute(
                select(WorkflowStep).where(WorkflowStep.id == step_id)
            )
            step = result_q.scalar_one_or_none()
            if step is None:
                return
            step.status = status
            if result is not None:
                step.result = result
            if retry_count is not None:
                step.retry_count = retry_count
            if error:
                step.error = error
            if status in (WorkflowStepStatus.success, WorkflowStepStatus.failed):
                step.finished_at = datetime.utcnow()
            await session.commit()


# 模块级单例，供 main.py lifespan 与路由层共享
workflow_scheduler = WorkflowScheduler()
