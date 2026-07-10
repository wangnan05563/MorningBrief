"""工作流调度服务：编排 4 个工作流模块的串行执行 + APScheduler 定时任务（LLD 5.1）。

职责：
1. 注册定时任务（每日 05:00 触发、06:00 兜底、06:30 备播检查、播放日志落库、分区维护）
2. 串行执行 crawl → rewrite → tts → stitch → review，每步失败重试 3 次
3. 审核通过后发布节目（调用 ContentService.publish_episode）
4. 备播机制：06:30 检查今日 episode 未发布则复用前一日音频

设计要点：
- 单进程内调度，避免多 worker 重复触发（单机 exe 单进程）
- TTLCache 互斥锁防止并发触发（cron 与手动可能重叠）
- 每步独立 session，避免长事务跨步骤持有连接
"""
import asyncio
import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, delete

from app.cache.manager import cache
from app.config import get_settings
from app.core.event_bus import Event, get_event_bus
from app.core.timeutil import utcnow_naive
from app.database import AsyncSessionLocal
from app.models import Episode, EpisodeStatus, Review, ReviewStatus, Workflow, WorkflowStep
from app.models import CrawlerDedup
from app.models.workflow import (
    WorkflowSource,
    WorkflowStatus,
    WorkflowStepName,
    WorkflowStepStatus,
)
from app.services.content_service import ContentService
from app.services.play_service import PlayService
from app.workflow.crawler import runner as crawler_mod
from app.workflow.llm import rewriter as llm_mod
from app.workflow.tts import synthesizer as tts_mod
from app.workflow.stitch import concat as stitch_mod

logger = logging.getLogger(__name__)
settings = get_settings()


def _is_cos_configured() -> bool:
    """检测 COS 是否已配置真实可用值（非空且非占位符）。

    开发态常无 COS 配置，flush_playlog 等依赖 COS 的任务跳过注册，
    避免每分钟触发 list_objects 报错刷日志。生产态填入真实配置后自动恢复。
    """
    bucket = (settings.COS_BUCKET or "").strip()
    secret_id = (settings.COS_SECRET_ID or "").strip()
    secret_key = (settings.COS_SECRET_KEY or "").strip()
    if not bucket or not secret_id or not secret_key:
        return False
    # 占位符检测：.env.example 的 <...> 占位符或中文提示
    if bucket.startswith("<") or "<" in bucket or ">" in bucket:
        return False
    return True


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
        # V1.2 改造：Redis → TTLCache（互斥锁/原子计数/键值操作均走 cache）
        self.cache = cache
        # 时区固定 Asia/Shanghai，确保 cron 表达式按北京时间触发
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        # 保留后台任务强引用，避免被 GC 回收导致任务中途取消
        self._running_tasks: set[asyncio.Task] = set()

    # ===== 事件发布 =====

    def _publish_event(self, event_type: str, data: dict) -> None:
        """向 EventBus 发布工作流状态事件。

        用 publish_nowait 而非 await publish：事件入队即返回，不阻塞工作流主流程。
        若 EventBus 未启动（如单元测试），事件积压在队列中不影响主逻辑。
        """
        try:
            bus = get_event_bus()
            bus.publish_nowait(Event(type=event_type, data=data))
        except Exception:
            logger.debug("EventBus 发布事件失败（不影响主流程）", exc_info=True)

    # ===== 生命周期 =====

    async def start(self) -> None:  # NOSONAR
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
        # COS 未配置时跳过注册：开发态常无 COS，避免每分钟刷 list_objects 错误日志
        if _is_cos_configured():
            self.scheduler.add_job(
                self._flush_playlog_queue,
                trigger="interval",
                minutes=1,
                id="flush_playlog",
                max_instances=1,
                coalesce=True,
            )
        else:
            logger.warning(
                "COS 未配置（COS_BUCKET/SECRET_ID/SECRET_KEY 为空或占位符），"
                "跳过 flush_playlog 任务注册。生产部署请配置 COS 后重启。"
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
        # 每日 03:00 清理 crawler_dedup 表过期记录（替代原 Redis Set EXPIRE 自动过期）
        self.scheduler.add_job(
            self._cleanup_crawler_dedup,
            trigger="cron",
            hour=3,
            minute=0,
            id="cleanup_crawler_dedup",
            replace_existing=True,
        )
        # 每小时清理 jwt_blacklist 表过期记录（替代原 Redis TTL 自动过期）
        self.scheduler.add_job(
            self._cleanup_blacklist,
            trigger="cron",
            minute=0,
            id="cleanup_blacklist",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("WorkflowScheduler 已启动，注册 7 个定时任务")

    async def stop(self) -> None:  # NOSONAR
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
        seq = await self.cache.incr(f"workflow:seq:{date_str}")
        # 序号当日有效，次日从 1 开始
        await self.cache.expire(f"workflow:seq:{date_str}", 48 * 3600)
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
        # 任务加入 _running_tasks 保留强引用，完成时通过回调自动移除
        task = asyncio.create_task(self._run_workflow(workflow_id, episode_date))
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)
        return workflow_id

    # ===== 工作流主流程 =====

    async def _run_workflow(self, workflow_id: str, episode_date: date) -> None:
        """串行执行 6 个步骤（LLD 5.1.2）。

        前 4 步调用外部模块，第 5 步内置创建 review，第 6 步 publish 由审核通过后异步触发。
        """
        # lock_acquired 标记本进程是否抢到锁；finally 仅在抢到时删 lock，
        # 避免误删其他正在运行的工作流持有的锁
        lock_acquired = False
        try:
            # 抢 TTLCache 互斥锁（替代 Redis SET NX EX），防止 cron 与手动触发并发
            lock_ok = await self.cache.acquire_lock(
                "workflow:lock", workflow_id, ttl_sec=settings.WORKFLOW_LOCK_TTL_SEC,
            )
            if not lock_ok:
                raise WorkflowConflictError("已有工作流在运行")
            lock_acquired = True

            await self.cache.set("workflow:current", workflow_id)
            await self._update_workflow_status(workflow_id, WorkflowStatus.running)
            self._publish_event("workflow.started", {
                "workflow_id": workflow_id, "episode_date": episode_date.isoformat(),
            })

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
            self._publish_event("workflow.completed", {
                "workflow_id": workflow_id,
            })
            logger.info("工作流主流程完成 workflow_id=%s", workflow_id)

        except StepFailedError as e:
            # 某步重试耗尽仍失败：置 failed + 告警，不立即备播（等 06:30 统一处理）
            await self._update_workflow_status(
                workflow_id, WorkflowStatus.failed, error=str(e),
            )
            self._publish_event("workflow.failed", {
                "workflow_id": workflow_id,
                "step": e.step_name,
                "error": str(e),
            })
            await self._alert_operators(
                f"工作流 {workflow_id} 失败于步骤 {e.step_name}: {e}"
            )
        except WorkflowConflictError as e:
            # 并发冲突，不算失败，仅记录
            logger.warning("工作流触发冲突 workflow_id=%s: %s", workflow_id, e)
            await self._update_workflow_status(
                workflow_id, WorkflowStatus.cancelled, error=str(e),
            )
            self._publish_event("workflow.cancelled", {
                "workflow_id": workflow_id, "reason": str(e),
            })
        except Exception as e:
            # 未预期异常兜底
            logger.exception("工作流异常 workflow_id=%s", workflow_id)
            await self._update_workflow_status(
                workflow_id, WorkflowStatus.failed, error=str(e),
            )
            self._publish_event("workflow.failed", {
                "workflow_id": workflow_id, "error": str(e),
            })
            await self._alert_operators(f"工作流 {workflow_id} 未预期异常: {e}")
        finally:
            # 仅本进程抢到锁才释放 lock，避免误删其他工作流的锁
            # release_lock 内部校验 value 匹配，双重保险
            if lock_acquired:
                await self.cache.release_lock("workflow:lock", workflow_id)
            await self.cache.delete("workflow:current")

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
                started = utcnow_naive()
                result = await func(context)
                duration_ms = int((utcnow_naive() - started).total_seconds() * 1000)
                await self._update_step_status(
                    step_record.id, WorkflowStepStatus.success,
                    result=result, retry_count=attempt, _duration_ms=duration_ms,
                )
                # 将本步产出合并到上下文供后续步骤使用
                context.update(result or {})
                self._publish_event("workflow.step.completed", {
                    "workflow_id": workflow_id,
                    "step": step_name.value,
                    "seq": seq,
                    "duration_ms": duration_ms,
                })
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
        self._publish_event("workflow.step.failed", {
            "workflow_id": workflow_id,
            "step": step_name.value,
            "seq": seq,
            "error": str(last_error),
        })
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
                published_at=utcnow_naive(),
            )
            session.add(backup)
            await session.commit()

        # 失效今日节目缓存，让小程序能看到备播节目
        await self.cache.delete("episode:today")
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

    async def _add_playlog_partition(self) -> None:  # NOSONAR
        """每月 1 号 02:00 维护 play_log 分区。

        MVP 阶段 play_log 未使用分区表，此方法预留扩展点。
        生产环境若启用分区，此处执行 ALTER TABLE ... ADD PARTITION。
        """
        next_month = (date.today().replace(day=1) + timedelta(days=32)).replace(day=1)
        logger.info(
            "play_log 分区维护任务触发（MVP 未分区，跳过）next_month=%s",
            next_month,
        )

    async def _cleanup_crawler_dedup(self) -> None:
        """每日 03:00 清理 crawler_dedup 表过期记录。

        替代原 Redis Set 的 EXPIRE 自动过期：SQLite 表需主动清理，
        按 CRAWLER_DEDUP_TTL_DAYS 配置保留窗口删除超出范围的记录。
        """
        cutoff = utcnow_naive() - timedelta(days=settings.CRAWLER_DEDUP_TTL_DAYS)
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    delete(CrawlerDedup).where(CrawlerDedup.created_at < cutoff)
                )
                await session.commit()
                deleted = result.rowcount
            if deleted > 0:
                logger.info("清理爬虫去重过期记录 %d 条", deleted)
        except Exception as e:
            # 清理失败不中断调度器，下次调度继续处理
            logger.exception("清理爬虫去重表失败: %s", e)

    async def _cleanup_blacklist(self) -> None:
        """每小时清理 jwt_blacklist 表过期记录。

        替代原 Redis 黑名单的 TTL 自动过期：SQLite 需定时清理已过期的 jti，
        避免表无限增长。委托 blacklist_service.cleanup_expired_blacklist 执行。
        """
        from app.services.blacklist_service import cleanup_expired_blacklist
        try:
            deleted = await cleanup_expired_blacklist()
            if deleted > 0:
                logger.info("清理黑名单过期记录 %d 条", deleted)
        except Exception as e:
            # 清理失败不中断调度器，下次调度继续处理
            logger.exception("清理黑名单失败: %s", e)

    # ===== 告警 =====

    async def _alert_operators(self, message: str) -> None:
        """告警运维人员（通过 NotifierHub 多渠道分发）。

        使用 NotifierHub 替代直接 webhook 调用：
        - 自动 fan-out 到所有已配置渠道（企微/钉钉/邮件）
        - 免打扰时段 critical 仍可达
        - 单渠道失败不影响其他渠道
        """
        logger.error("【告警】%s", message)

        from app.services.notifier import get_notifier_hub, NotificationEvent
        hub = get_notifier_hub()
        event = NotificationEvent(
            title="20_News 工作流告警",
            message=message,
            severity="critical",  # 工作流故障为 critical，穿透免打扰
            source="workflow_scheduler",
        )
        try:
            result = await hub.send(event)
            if result["failed"] > 0 and result["success"] == 0:
                logger.error(
                    "所有通知渠道发送失败: %s",
                    [r.error for r in result["results"] if not r.success],
                )
        except Exception as e:
            logger.error("NotifierHub 告警发送异常: %s", e)

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
                wf.finished_at = utcnow_naive()
            await session.commit()

    async def _create_step_record(
        self, workflow_id: str, step_name: WorkflowStepName, _seq: int,
    ) -> WorkflowStep:
        """创建步骤记录（status=pending），返回 ORM 对象供后续更新。"""
        async with AsyncSessionLocal() as session:
            step = WorkflowStep(
                workflow_id=workflow_id,
                step_name=step_name,
                status=WorkflowStepStatus.pending,
                started_at=utcnow_naive(),
            )
            session.add(step)
            await session.commit()
            await session.refresh(step)
            return step

    async def _update_step_status(
        self, step_id: int, status: WorkflowStepStatus,
        result: dict = None, retry_count: int = None,
        error: str = None, _duration_ms: int = None,
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
                step.finished_at = utcnow_naive()
            await session.commit()


# 模块级单例，供 main.py lifespan 与路由层共享
workflow_scheduler = WorkflowScheduler()
