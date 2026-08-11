"""工作流调度服务：编排 4 个工作流模块的串行执行 + APScheduler 定时任务（LLD 5.1）。

职责：
1. 注册定时任务（每日 05:00 触发、06:00 兜底、06:30 备播检查、播放日志落库、分区维护）
2. 串行执行 crawl → rewrite → tts → stitch → review，每步失败重试 3 次
3. 审核通过后发布节目（调用 ContentService.publish_episode）
4. 备播机制：06:30 检查今日 episode 未发布则复用前一日音频

设计要点：
- 单进程内调度，避免多 worker 重复触发（单机 exe 单进程）
- PriorityQueue + Semaphore 实现优先级排队与并发上限控制
- 配置驱动并发模式（serial/parallel），QueueConfig 单行配置表为唯一真相源
- trigger_lock 保证序号生成与入队的原子性，避免 cron 与手动触发竞态
- 每步独立 session，避免长事务跨步骤持有连接
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, delete, or_

from app.cache.manager import cache
from app.config import get_settings
from app.core.event_bus import Event, get_event_bus
from app.core.exceptions import ParamError
from app.core.timeutil import localnow_naive
from app.database import AsyncSessionLocal
from app.models import Episode, EpisodeStatus, Review, ReviewStatus, Script, Workflow, WorkflowStep
from app.models import CrawlerDedup, Material
from app.models.channel import Channel
from app.models.queue_config import QueueConfig
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

# 事件/通知 channel 字面量统一引用，避免多处硬编码导致改名时遗漏
_WORKFLOW_FAILED_KEY = "workflow.failed"


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


@dataclass(order=True)
class QueueEntry:
    """PriorityQueue 条目。sort_priority 为负数实现 DESC（最小堆）。"""
    sort_priority: int
    created_at: float
    workflow_id: str = field(compare=False)
    channel_id: Optional[int] = field(compare=False, default=None)
    priority: int = field(compare=False, default=5)
    episode_date: date = field(compare=False, default=None)
    cancelled: bool = field(compare=False, default=False)


class WorkflowScheduler:
    """工作流调度服务（单例，应用启动时创建）。"""

    def __init__(self):
        # V1.2 改造：Redis → TTLCache（互斥锁/原子计数/键值操作均走 cache）
        self.cache = cache
        # 时区固定 Asia/Shanghai，确保 cron 表达式按北京时间触发
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        # 保留后台任务强引用，避免被 GC 回收导致任务中途取消
        self._running_tasks: set[asyncio.Task] = set()
        # 队列与并发控制
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        # 引用 QueueConfig 默认常量，保持单一真相源
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(QueueConfig.DEFAULT_MAX_CONCURRENT)
        self._trigger_lock: asyncio.Lock = asyncio.Lock()
        self._config_dirty: bool = False
        self._entry_map: dict[str, QueueEntry] = {}
        self._execution_mode: str = QueueConfig.DEFAULT_EXECUTION_MODE
        self._max_concurrent: int = QueueConfig.DEFAULT_MAX_CONCURRENT
        self._running_count: int = 0

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

    async def _on_channel_active_changed(self, event: Event) -> None:
        """频道禁用时取消该频道所有 queued 工作流。"""
        channel_id = event.data.get("channel_id")
        is_active = event.data.get("is_active")
        if channel_id is None or is_active is None:
            return
        if is_active != 0:
            return
        cancelled_ids: list[str] = []
        for wf_id, entry in self._entry_map.items():
            if entry.channel_id == channel_id and not entry.cancelled:
                entry.cancelled = True
                cancelled_ids.append(wf_id)
        if cancelled_ids:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import update as sa_update
                stmt = (
                    sa_update(Workflow)
                    .where(
                        Workflow.id.in_(cancelled_ids),
                        Workflow.status == WorkflowStatus.queued.value,
                    )
                    .values(status=WorkflowStatus.cancelled.value, finished_at=localnow_naive())
                )
                await session.execute(stmt)
                await session.commit()
            logger.info("频道 %s 禁用，取消 %d 个 queued 工作流", channel_id, len(cancelled_ids))

    # ===== 频道级定时任务 =====

    async def _register_all_channel_crons(self) -> None:
        """启动时为所有 schedule_time 非空的活跃频道注册 cron 任务。

        频道未配置 schedule_time 时，使用全局 daily_workflow（05:00）触发。
        配置了 schedule_time 的频道，按各自时间独立触发。
        """
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Channel).where(
                    Channel.is_active == 1,
                    Channel.schedule_time.is_not(None),
                    Channel.schedule_time != "",
                )
                result = await session.execute(stmt)
                channels = result.scalars().all()

            for ch in channels:
                self._register_channel_cron(ch.id, ch.schedule_time)
            if channels:
                logger.info("已注册 %d 个频道级 cron 任务", len(channels))
        except Exception as e:
            logger.warning("注册频道级 cron 任务失败: %s", e)

    def _register_channel_cron(self, channel_id: int, schedule_time: str) -> None:
        """为单个频道注册 cron 任务。

        schedule_time 格式 HH:MM:SS，解析为 cron 的 hour/minute/second。
        任务 id 格式：channel_workflow_{channel_id}，replace_existing 确保幂等。
        args=[channel_id] 传递频道 ID 给 _channel_cron_trigger。
        """
        if not schedule_time:
            return
        parts = schedule_time.split(":")
        if len(parts) != 3:
            logger.warning("频道 %s schedule_time 格式错误: %s", channel_id, schedule_time)
            return
        try:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            logger.warning("频道 %s schedule_time 非数字: %s", channel_id, schedule_time)
            return

        job_id = f"channel_workflow_{channel_id}"
        self.scheduler.add_job(
            self._channel_cron_trigger,
            trigger="cron",
            hour=h, minute=m, second=s,
            args=[channel_id],
            id=job_id,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1,
            replace_existing=True,
        )
        logger.info("注册频道级 cron channel_id=%s schedule=%s", channel_id, schedule_time)

    def _unregister_channel_cron(self, channel_id: int) -> None:
        """移除频道的 cron 任务（频道删除或 schedule_time 清空时调用）。"""
        job_id = f"channel_workflow_{channel_id}"
        try:
            self.scheduler.remove_job(job_id)
            logger.info("移除频道级 cron channel_id=%s", channel_id)
        except Exception:
            # 任务不存在时静默（如频道未配置 schedule_time 时无任务可移除）
            pass

    async def _channel_cron_trigger(self, channel_id: int) -> None:
        """频道级 cron 触发入口：按频道独立触发工作流。

        与全局 _cron_trigger 的区别：携带 channel_id，rewrite 步骤据此读取频道级提示词。
        """
        today = date.today()
        logger.info("频道级 cron 触发 channel_id=%s date=%s", channel_id, today)
        await self.trigger_workflow(
            episode_date=today,
            source=WorkflowSource.cron.value,
            channel_id=channel_id,
        )

    async def _on_channel_schedule_changed(self, event: Event) -> None:  # NOSONAR
        """频道定时变更事件处理：重注册或移除 cron 任务。

        schedule_time 为空字符串表示移除（频道删除或清空 schedule_time）。
        schedule_time 非空且频道活跃时注册/更新 cron 任务。
        """
        channel_id = event.data.get("channel_id")
        schedule_time = event.data.get("schedule_time", "")
        is_active = event.data.get("is_active", 0)

        if not schedule_time or is_active != 1:
            # 清空 schedule_time 或频道禁用/删除：移除任务
            self._unregister_channel_cron(channel_id)
        else:
            # 注册或更新任务
            self._register_channel_cron(channel_id, schedule_time)

    # ===== 生命周期 =====

    async def _recover_orphan_workflows(self) -> None:
        """启动时恢复中间状态工作流：running→failed，queued→重新入队。

        服务重启后事件循环被销毁，之前 running 的协程已死但数据库状态仍为 running，
        queued 工作流的内存队列也丢失。必须在 start() 注册定时任务前清理：
        - running 工作流：协程已死，标记 failed + 重置 material
        - queued 工作流：内存队列丢失，重新入队让 worker 消费
        - 孤儿步骤：工作流已终态但步骤仍 running/retrying/pending，清理为 failed
        """
        from sqlalchemy import update as sa_update
        from app.models.material import MaterialStatus
        now = localnow_naive()
        requeue_list: list[tuple] = []  # [(workflow_id, channel_id, priority, episode_date), ...]

        try:
            async with AsyncSessionLocal() as session:
                # 1. running 工作流：协程已死，标记 failed + 重置 material
                result = await session.execute(
                    select(Workflow).where(Workflow.status == WorkflowStatus.running.value)
                )
                running_orphans = result.scalars().all()
                if running_orphans:
                    running_ids = [wf.id for wf in running_orphans]
                    logger.warning(
                        "发现 %d 个 running 孤儿工作流，标记为 failed: %s",
                        len(running_orphans), running_ids,
                    )
                    await session.execute(
                        sa_update(Workflow)
                        .where(Workflow.status == WorkflowStatus.running.value)
                        .values(
                            status=WorkflowStatus.failed.value,
                            finished_at=now,
                            error="服务重启后孤儿工作流恢复：协程已死",
                        )
                    )
                    # 重置关联 material 为 pending（避免 dedup 死锁）
                    await session.execute(
                        sa_update(Material)
                        .where(Material.workflow_id.in_(running_ids))
                        .values(status=MaterialStatus.pending.value, workflow_id=None)
                    )

                # 2. queued 工作流：内存队列丢失，收集待重新入队
                result = await session.execute(
                    select(Workflow).where(Workflow.status == WorkflowStatus.queued.value)
                )
                queued_workflows = result.scalars().all()
                if queued_workflows:
                    logger.info(
                        "发现 %d 个 queued 工作流，将重新入队: %s",
                        len(queued_workflows), [wf.id for wf in queued_workflows],
                    )
                    for wf in queued_workflows:
                        requeue_list.append((wf.id, wf.channel_id, wf.priority, wf.episode_date))

                # 3. 孤儿步骤：工作流已终态（success/failed/cancelled）但步骤仍中间态（running/retrying/pending）
                # 场景：_run_step 异常中断或服务在步骤执行中被 kill，步骤状态未更新
                result = await session.execute(
                    select(WorkflowStep.workflow_id).where(
                        WorkflowStep.status.in_([
                            WorkflowStepStatus.running.value,
                            WorkflowStepStatus.retrying.value,
                            WorkflowStepStatus.pending.value,
                        ])
                    ).distinct()
                )
                orphan_step_wf_ids = [r[0] for r in result.fetchall()]
                if orphan_step_wf_ids:
                    # 仅处理工作流已终态的孤儿步骤（running 工作流的步骤已在上面处理）
                    result = await session.execute(
                        select(Workflow.id).where(
                            Workflow.id.in_(orphan_step_wf_ids),
                            Workflow.status.in_([
                                WorkflowStatus.success.value,
                                WorkflowStatus.failed.value,
                                WorkflowStatus.cancelled.value,
                            ]),
                        )
                    )
                    terminal_wf_ids = [r[0] for r in result.fetchall()]
                    if terminal_wf_ids:
                        logger.warning(
                            "发现 %d 个终态工作流的孤儿步骤，清理为 failed: %s",
                            len(terminal_wf_ids), terminal_wf_ids,
                        )
                        await session.execute(
                            sa_update(WorkflowStep)
                            .where(
                                WorkflowStep.workflow_id.in_(terminal_wf_ids),
                                WorkflowStep.status.in_([
                                    WorkflowStepStatus.running.value,
                                    WorkflowStepStatus.retrying.value,
                                    WorkflowStepStatus.pending.value,
                                ]),
                            )
                            .values(
                                status=WorkflowStepStatus.failed.value,
                                finished_at=now,
                                error="服务重启后孤儿步骤恢复",
                            )
                        )

                await session.commit()
        except Exception as e:
            # 恢复失败不阻断启动，下次启动时再恢复
            logger.exception("恢复孤儿工作流失败: %s", e)
            return

        # 4. 重新入队 queued 工作流（在 session 提交后，避免 DB 操作与入队交错）
        for workflow_id, channel_id, priority, episode_date in requeue_list:
            entry = QueueEntry(
                sort_priority=-priority,
                created_at=localnow_naive().timestamp(),
                workflow_id=workflow_id,
                channel_id=channel_id,
                priority=priority,
                episode_date=episode_date,
            )
            await self._queue.put(entry)
            self._entry_map[workflow_id] = entry
            logger.info("重新入队 queued 工作流: %s", workflow_id)

    async def start(self) -> None:  # NOSONAR
        """应用启动时调用，注册全部 Cron 任务（LLD 5.1.1 / 7.5）。"""
        # 启动时恢复孤儿工作流：服务重启后，之前 running 的协程已死，
        # 但数据库状态仍为 running，必须清理否则前端永远显示"运行中"（wf-20260726-0001 复现）
        await self._recover_orphan_workflows()

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
        # 每日 04:00 执行 SQLite 数据库备份（在 05:00 cron 工作流触发前 1 小时）
        # 选择 04:00 是因为此时系统空闲（无工作流执行），VACUUM INTO 不会与工作流写入竞争
        self.scheduler.add_job(
            self._daily_backup,
            trigger="cron",
            hour=4,
            minute=0,
            id="daily_backup",
            misfire_grace_time=600,
            coalesce=True,
            max_instances=1,
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
        # 每 30 分钟清理 entry_map 中已完成/取消的条目，避免内存泄漏
        self.scheduler.add_job(
            self._cleanup_entry_map,
            trigger="cron",
            minute=30,
            id="cleanup_entry_map",
            replace_existing=True,
        )
        # 每 2 小时巡检 RSS 源可达性：及时发现失效源，连续失败 3 次发 WARNING
        # 不阻断 crawl：crawler 自身有单源失败隔离，巡检仅用于运维感知
        self.scheduler.add_job(
            self._check_rss_sources,
            trigger="cron",
            hour="*/2",
            id="check_rss_sources",
            misfire_grace_time=600,
            coalesce=True,
            max_instances=1,
            replace_existing=True,
        )
        # 加载队列配置（首次启动从 DB 读取，DB 无记录则用默认值）
        await self._load_queue_config()
        # 订阅频道启停事件：频道禁用时取消其 queued 工作流
        bus = get_event_bus()
        bus.subscribe("channel.active_changed", self._on_channel_active_changed)
        # 订阅频道定时变更事件：schedule_time 变化时重注册 cron 任务
        bus.subscribe("channel.schedule_changed", self._on_channel_schedule_changed)
        # 注册频道级定时任务（schedule_time 非空的活跃频道）
        await self._register_all_channel_crons()
        # 启动队列消费 worker（后台常驻任务，强引用防 GC 回收）
        worker_task = asyncio.create_task(self._queue_worker())
        self._running_tasks.add(worker_task)
        worker_task.add_done_callback(self._running_tasks.discard)
        self.scheduler.start()
        logger.info("WorkflowScheduler 已启动，注册 8 个定时任务 + 频道级 cron")

    async def stop(self) -> None:  # NOSONAR
        """应用关闭时关闭调度器，等待运行中任务完成。"""
        # 取消频道事件订阅，避免 shutdown 后回调访问已释放资源
        bus = get_event_bus()
        bus.unsubscribe("channel.active_changed", self._on_channel_active_changed)
        bus.unsubscribe("channel.schedule_changed", self._on_channel_schedule_changed)
        self.scheduler.shutdown(wait=True)
        logger.info("WorkflowScheduler 已停止")

    # ===== 触发入口 =====

    async def _cron_trigger(self) -> None:
        """APScheduler 全局 cron 触发入口（默认 05:00）。

        schedule_time 为空的频道使用此全局触发：为每个活跃且未配置独立定时的频道
        各触发一个工作流。schedule_time 非空的频道由各自独立的 cron 任务触发。
        """
        today = date.today()
        try:
            async with AsyncSessionLocal() as session:
                # 未配置 schedule_time 的活跃频道走全局 cron
                stmt = select(Channel.id).order_by(Channel.id).where(
                    Channel.is_active == 1,
                    or_(
                        Channel.schedule_time.is_(None),
                        Channel.schedule_time == "",
                    ),
                )
                result = await session.execute(stmt)
                channel_ids = [row[0] for row in result.all()]
        except Exception as e:
            logger.warning("全局 cron 查询频道列表失败，回退到无频道触发: %s", e)
            channel_ids = []

        if not channel_ids:
            # 无活跃频道或全部配置了独立定时：回退到原有行为（channel_id=None）  # NOSONAR
            logger.warning("全局 cron 触发：无未配置独立定时的活跃频道，触发默认工作流")
            await self.trigger_workflow(
                episode_date=today,
                source=WorkflowSource.cron.value,
            )
            return

        logger.info("全局 cron 触发：为 %d 个频道各触发工作流", len(channel_ids))
        for cid in channel_ids:
            try:
                await self.trigger_workflow(
                    episode_date=today,
                    source=WorkflowSource.cron.value,
                    channel_id=cid,
                )
            except Exception as e:
                logger.error("全局 cron 触发频道 %s 失败: %s", cid, e)

    async def trigger_workflow(
        self, episode_date: date, source: str,
        channel_id: Optional[int] = None, priority: int = 5,
        triggered_by: str = None, skip_crawl: bool = False,
    ) -> str:
        """触发工作流，返回 workflow_id。

        Args:
            episode_date: 目标节目日期
            source: cron / manual
            channel_id: 频道归属，频道禁用时据此取消排队
            priority: 优先级 0-10，默认 5（越大越先执行）
            triggered_by: 手动触发时记录 admin username
            skip_crawl: 业务范围扩展——文档上传/手动选题场景跳过爬虫步骤
                （素材已在 T3 入库），预置成功 crawl 步骤使 _run_workflow 从 rewrite 开始

        Returns:
            workflow_id（如 wf-20260708-0001）
        """
        if not 0 <= priority <= 10:
            raise ParamError("优先级范围 0-10")

        # trigger_lock 串行化序号生成与入队，避免并发触发产生重复 ID
        async with self._trigger_lock:
            date_str = episode_date.strftime("%Y%m%d")
            seq = await self.cache.incr(f"workflow:seq:{date_str}")
            # 序号当日有效，次日从 1 开始
            await self.cache.expire(f"workflow:seq:{date_str}", 48 * 3600)
            # DB 校正：缓存可能因重启丢失，取 max(缓存序号, DB最大序号+1)
            db_max = await self._get_db_max_seq(episode_date)
            if db_max >= seq:
                seq = db_max + 1
            workflow_id = f"wf-{date_str}-{seq:04d}"

            logger.info(
                "触发工作流 workflow_id=%s date=%s source=%s channel_id=%s priority=%d triggered_by=%s",
                workflow_id, episode_date, source, channel_id, priority, triggered_by,
            )

            # 创建 workflow 记录（status=queued，等待 worker 消费后转 running）
            async with AsyncSessionLocal() as session:
                wf = Workflow(
                    id=workflow_id,
                    episode_date=episode_date,
                    source=WorkflowSource(source),
                    status=WorkflowStatus.queued.value,
                    channel_id=channel_id,
                    priority=priority,
                    started_at=localnow_naive(),
                )
                session.add(wf)
                await session.commit()

                # 业务范围扩展：文档上传/手动选题场景跳过爬虫（素材已在 T3 入库），
                # 预置一条成功的 crawl 步骤，_run_workflow 据此跳过 crawl、从 rewrite 开始
                if skip_crawl:
                    seed = WorkflowStep(
                        workflow_id=workflow_id,
                        step_name=WorkflowStepName.crawl.value,
                        status=WorkflowStepStatus.success.value,
                        result={},
                        started_at=localnow_naive(),
                        finished_at=localnow_naive(),
                        retry_count=0,
                    )
                    session.add(seed)
                    await session.commit()
                    logger.info(
                        "跳过爬虫步骤（skip_crawl）workflow_id=%s channel_id=%s",
                        workflow_id, channel_id,
                    )

            # 入队 PriorityQueue（sort_priority 为负数实现 DESC 最小堆）
            entry = QueueEntry(
                sort_priority=-priority,
                created_at=localnow_naive().timestamp(),
                workflow_id=workflow_id,
                channel_id=channel_id,
                priority=priority,
                episode_date=episode_date,
            )
            await self._queue.put(entry)
            self._entry_map[workflow_id] = entry

        return workflow_id

    # ===== 队列管理 =====

    async def _queue_worker(self) -> None:
        """常驻消费者：从 PriorityQueue 取条目，获取 Semaphore 后执行。

        cancelled 条目直接丢弃，不消耗信号量配额。
        """
        while True:
            entry: QueueEntry = await self._queue.get()
            if entry.cancelled:
                self._entry_map.pop(entry.workflow_id, None)
                continue
            # 先获取信号量再创建任务，限制同时运行的 _run_workflow 数量
            await self._semaphore.acquire()
            self._running_count += 1
            task = asyncio.create_task(self._run_workflow_with_release(entry))
            self._running_tasks.add(task)
            task.add_done_callback(self._running_tasks.discard)

    async def _run_workflow_with_release(self, entry: QueueEntry) -> None:
        """执行工作流并在结束时释放信号量。

        finally 块确保即使 _run_workflow 抛异常也能释放资源，
        避免信号量泄漏导致后续任务永久阻塞。
        """
        try:
            await self._run_workflow(entry.workflow_id, entry.episode_date)
        finally:
            self._semaphore.release()
            self._running_count -= 1
            self._entry_map.pop(entry.workflow_id, None)
            # 配置变更延迟生效：等所有运行中任务完成后再重建信号量，  # NOSONAR
            # 避免在任务执行中途更换信号量导致计数错乱
            if self._config_dirty and self._running_count == 0:
                self._rebuild_semaphore()

    async def mark_entry_cancelled(self, workflow_id: str) -> None:  # NOSONAR
        """标记内存队列条目为已取消，worker 取出时跳过。"""
        entry = self._entry_map.get(workflow_id)
        if entry is not None:
            entry.cancelled = True

    async def requeue_with_priority(self, workflow_id: str, priority: int) -> None:
        """修改优先级后重新入队：旧条目标记 cancelled，新条目按新优先级入队。"""
        old = self._entry_map.get(workflow_id)
        if old is not None:
            old.cancelled = True
        # 从 DB 读取 episode_date 与 channel_id，保持与原记录一致
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )
            wf = result.scalar_one_or_none()
            if wf is None:
                return
            episode_date = wf.episode_date
            channel_id = wf.channel_id
        entry = QueueEntry(
            sort_priority=-priority,
            created_at=localnow_naive().timestamp(),
            workflow_id=workflow_id,
            channel_id=channel_id,
            priority=priority,
            episode_date=episode_date,
        )
        await self._queue.put(entry)
        self._entry_map[workflow_id] = entry

    async def apply_config_change(self, mode: str, max_concurrent: int) -> None:  # NOSONAR
        """标记配置待生效，不立即重建信号量（延迟到所有任务完成后）。"""
        self._execution_mode = mode
        self._max_concurrent = max_concurrent
        self._config_dirty = True
        logger.info("队列配置已标记待生效 mode=%s max_concurrent=%d", mode, max_concurrent)

    def _rebuild_semaphore(self) -> None:
        """根据 _max_concurrent 重建信号量并清除 dirty 标记。

        同步方法：仅在 _running_count==0 时调用，无需加锁。
        旧信号量可能仍有 pending acquire，但不影响新信号量的正确性——
        旧 acquire 会在旧信号量上永久等待，但 _queue_worker 已切换到新信号量。
        """
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._config_dirty = False
        logger.info("信号量已重建 max_concurrent=%d", self._max_concurrent)

    async def _load_queue_config(self) -> None:
        """从 DB 加载队列配置，DB 无记录则插入默认配置。"""
        async with AsyncSessionLocal() as session:
            config = await session.get(QueueConfig, 1)
            if config is None:
                # 首次启动插入默认配置，与 QueueConfig 常量保持一致
                config = QueueConfig(
                    id=1,
                    execution_mode=QueueConfig.DEFAULT_EXECUTION_MODE,
                    max_concurrent=QueueConfig.DEFAULT_MAX_CONCURRENT,
                )
                session.add(config)
                await session.commit()
            self._execution_mode = config.execution_mode
            self._max_concurrent = config.max_concurrent
        # 初始加载直接重建信号量（无需等 _running_count==0，此时无任务运行）
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._config_dirty = False
        logger.info(
            "队列配置已加载 mode=%s max_concurrent=%d",
            self._execution_mode, self._max_concurrent,
        )

    async def _rebuild_queue(self) -> None:
        """从 DB 重建 PriorityQueue（重启恢复场景）。

        查询所有 status=queued 的工作流，按 priority DESC + started_at ASC 入队。
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Workflow).where(
                    Workflow.status == WorkflowStatus.queued.value
                ).order_by(Workflow.priority.desc(), Workflow.started_at.asc())
            )
            workflows = result.scalars().all()

        # 清空内存队列与 entry_map，避免重启后重复
        self._queue = asyncio.PriorityQueue()
        self._entry_map.clear()

        for wf in workflows:
            entry = QueueEntry(
                sort_priority=-wf.priority,
                created_at=wf.started_at.timestamp() if wf.started_at else localnow_naive().timestamp(),
                workflow_id=wf.id,
                channel_id=wf.channel_id,
                priority=wf.priority,
                episode_date=wf.episode_date,
            )
            await self._queue.put(entry)
            self._entry_map[wf.id] = entry
        logger.info("队列重建完成，共 %d 个 queued 任务", len(workflows))

    async def _get_db_max_seq(self, episode_date: date) -> int:
        """查询 DB 中指定日期的最大 workflow 序号（从 workflow_id 解析）。

        缓存重启后序号丢失，用 DB 校正避免 ID 冲突。
        """
        date_str = episode_date.strftime("%Y%m%d")
        prefix = f"wf-{date_str}-"
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Workflow.id).where(Workflow.id.like(f"{prefix}%"))
            )
            max_seq = 0
            for (wid,) in result.all():
                try:
                    seq = int(wid.rsplit("-", 1)[-1])
                    if seq > max_seq:
                        max_seq = seq
                except ValueError:
                    continue
            return max_seq

    async def retry_workflow(  # NOSONAR
        self, workflow_id: str, from_step: str = None, triggered_by: str = None,
    ) -> str:
        """在原工作流上从指定步骤重跑（不创建新工作流）。

        删除 from_step 及其之后的所有步骤记录（含失败记录），
        保留之前的成功步骤，重置 workflow 状态为 queued 后重新入队。
        _run_workflow 执行时通过 _load_completed_step_context 跳过已成功步骤。

        Args:
            workflow_id: 工作流 ID
            from_step: 从哪一步开始重跑（WorkflowStepName 值，如 "tts"/"stitch"）
            triggered_by: 手动触发者用户名

        Returns:
            工作流 ID（与传入相同，不创建新工作流）

        Raises:
            ParamError: 工作流不存在/非失败状态/from_step 无效/前驱步骤缺 result
        """
        if not from_step:
            raise ParamError("必须指定重跑起始步骤")
        try:
            from_step_name = WorkflowStepName(from_step)
        except ValueError:
            raise ParamError(f"无效的步骤名: {from_step}")

        # 计算 from_step 之前的步骤（保留）和及其之后的步骤（删除）
        keep_steps: list[WorkflowStepName] = []
        delete_steps: list[WorkflowStepName] = []
        found = False
        for step in self._STEP_ORDER:
            if step == from_step_name:
                found = True
                delete_steps.append(step)
                continue
            if found:
                delete_steps.append(step)
            else:
                keep_steps.append(step)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Workflow).where(
                    Workflow.id == workflow_id,
                    Workflow.status == WorkflowStatus.failed.value,
                )
            )
            wf = result.scalar_one_or_none()
            if wf is None:
                raise ParamError(f"任务不存在或非失败状态: {workflow_id}")
            episode_date = wf.episode_date
            channel_id = wf.channel_id
            priority = wf.priority

            # 校验：keep_steps 中每个步骤都必须有成功记录且有 result
            result = await session.execute(
                select(WorkflowStep).where(
                    WorkflowStep.workflow_id == workflow_id,
                    WorkflowStep.step_name.in_([s.value for s in keep_steps]),
                    WorkflowStep.status == WorkflowStepStatus.success.value,
                ).order_by(WorkflowStep.id)
            )
            keep_records = result.scalars().all()
            keep_names = {r.step_name for r in keep_records}
            for step in keep_steps:
                if step.value not in keep_names:
                    raise ParamError(
                        f"步骤 {step.value} 未成功完成，无法从 {from_step} 重跑"
                    )
            for record in keep_records:
                if not record.result:
                    raise ParamError(
                        f"步骤 {record.step_name} 缺少 result，无法断点续跑"
                    )

            # 删除 from_step 及其之后的所有步骤记录（含失败/重试中）
            if delete_steps:
                await session.execute(
                    delete(WorkflowStep).where(
                        WorkflowStep.workflow_id == workflow_id,
                        WorkflowStep.step_name.in_([s.value for s in delete_steps]),
                    )
                )

            # 重置工作流状态为 queued，清空失败信息
            wf.status = WorkflowStatus.queued.value
            wf.error = None
            wf.finished_at = None
            await session.commit()

        # 取消内存队列中可能残留的旧条目（failed 状态一般已出队，防御性处理）
        old = self._entry_map.get(workflow_id)
        if old is not None:
            old.cancelled = True

        # 入队当前工作流（参考 requeue_with_priority 的入队逻辑）
        entry = QueueEntry(
            sort_priority=-priority,
            created_at=localnow_naive().timestamp(),
            workflow_id=workflow_id,
            channel_id=channel_id,
            priority=priority,
            episode_date=episode_date,
        )
        await self._queue.put(entry)
        self._entry_map[workflow_id] = entry

        logger.info(
            "重跑工作流 %s 从 %s 开始（triggered_by=%s，保留 %d 步，删除 %d 步）",
            workflow_id, from_step, triggered_by, len(keep_steps), len(delete_steps),
        )
        return workflow_id

    # ===== 工作流主流程 =====

    async def _get_workflow_channel_id(self, workflow_id: str) -> Optional[int]:
        """查询 workflow 的 channel_id，用于 rewrite 步骤读取频道级提示词。

        返回 None 表示工作流未关联频道，rewrite 将使用默认提示词。
        """
        async with AsyncSessionLocal() as session:
            wf = await session.get(Workflow, workflow_id)
            return wf.channel_id if wf else None

    async def _run_workflow(self, workflow_id: str, episode_date: date) -> None:
        """串行执行 6 个步骤（LLD 5.1.2）。

        前 4 步调用外部模块，第 5 步内置创建 review，第 6 步 publish 由审核通过后异步触发。
        并发控制由 _queue_worker + Semaphore 负责，本方法不再持有互斥锁。
        """
        try:
            await self.cache.set("workflow:current", workflow_id)
            await self._update_workflow_status(workflow_id, WorkflowStatus.running)
            self._publish_event("workflow.started", {
                "workflow_id": workflow_id, "episode_date": episode_date.isoformat(),
            })

            date_str = episode_date.isoformat()
            # 查询 workflow 的 channel_id，用于 rewrite 步骤读取频道级提示词
            channel_id = await self._get_workflow_channel_id(workflow_id)
            context = {
                "workflow_id": workflow_id,
                "episode_date": episode_date,
                "date_str": date_str,
                "channel_id": channel_id,
            }
            # 断点续跑：加载已完成步骤与上下文，跳过已成功的步骤
            completed_steps, resumed_context = await self._load_completed_step_context(workflow_id)
            context.update(resumed_context)

            # 步骤 1：爬虫（签名 run(workflow_id, date_str, channel_id)）
            # channel_id 用于频道级数据源隔离：按频道 rss_sources 白名单过滤源、
            # 按 keywords 过滤标题、入库写入 channel_id 供 rewriter 按频道选题
            if WorkflowStepName.crawl not in completed_steps:
                await self._run_step(
                    workflow_id, WorkflowStepName.crawl, 1,
                    lambda ctx: crawler_mod.run(
                        ctx["workflow_id"], ctx["date_str"], ctx.get("channel_id"),
                    ),
                    context,
                )

            # 步骤 2：LLM 改写（签名 rewrite(workflow_id, date_str, channel_id)）
            if WorkflowStepName.rewrite not in completed_steps:
                await self._run_step(
                    workflow_id, WorkflowStepName.rewrite, 2,
                    lambda ctx: llm_mod.rewrite(ctx["workflow_id"], ctx["date_str"], ctx.get("channel_id")),
                    context,
                )
            # 步骤 2.5：微信内容安全检测（不作为独立步骤，结果合并到 rewrite 步骤 result）
            # 放在此处而非 _run_step 内，是为了保持原步骤重试逻辑不变，同时确保只在
            # rewrite 首次成功执行后才检测（断点续跑场景 completed_steps 含 rewrite 时跳过）
            if WorkflowStepName.rewrite not in completed_steps:
                await self._run_content_security_check(workflow_id, context)

            # 步骤 3：TTS（签名 synthesize(workflow_id, script_id)）
            if WorkflowStepName.tts not in completed_steps:
                async def _tts_fn(ctx):
                    return await tts_mod.synthesize(ctx["workflow_id"], ctx["script_id"])

                await self._run_step(
                    workflow_id, WorkflowStepName.tts, 3, _tts_fn, context,
                )

            # 步骤 4：拼接（签名 concat(workflow_id, episode_date, audio_segments, channel_id)）
            # channel_id 用于生成频道级 COS key，避免同日多频道产物互相覆盖
            if WorkflowStepName.stitch not in completed_steps:
                async def _stitch_fn(ctx):
                    return await stitch_mod.concat(
                        ctx["workflow_id"], ctx["episode_date"],
                        ctx["audio_segments"], ctx.get("channel_id"),
                    )

                await self._run_step(
                    workflow_id, WorkflowStepName.stitch, 4, _stitch_fn, context,
                )

            # 步骤 5：创建审核记录（内置方法）
            if WorkflowStepName.review not in completed_steps:
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

            # 尝试自动审批：满足预设规则则自动 approve 并发布节目
            # 失败或不满足条件则继续走 pending_review 通知，由人工审核兜底
            # 将 review_id 写入 context（_run_step 把 step result 合并进 context）
            review_step_result = context.get("review_id")
            if review_step_result is None:
                # 兜底：若 context 无 review_id，从最后一条 review 步骤记录读取
                async with AsyncSessionLocal() as session:
                    step_result = await session.execute(
                        select(WorkflowStep.result).where(
                            WorkflowStep.workflow_id == workflow_id,
                            WorkflowStep.step_name == WorkflowStepName.review.value,
                        ).order_by(WorkflowStep.id.desc()).limit(1)
                    )
                    step_row = step_result.first()
                    if step_row and step_row[0]:
                        context["review_id"] = step_row[0].get("review_id")

            await self._try_auto_review(context)

            # 自动审批失败或未启用时，发送 pending_review 通知引导人工审核
            if not context.get("_auto_review_succeeded"):
                await self._send_notification(
                    "workflow.pending_review", workflow_id,
                )

        except StepFailedError as e:
            # 某步重试耗尽仍失败：置 failed + 告警，不立即备播（等 06:30 统一处理）
            await self._update_workflow_status(
                workflow_id, WorkflowStatus.failed, error=str(e),
            )
            self._publish_event(_WORKFLOW_FAILED_KEY, {
                "workflow_id": workflow_id,
                "step": e.step_name,
                "error": str(e),
            })
            # 走结构化通知（含 failed_step/error_message 变量），失败时降级到通用告警
            await self._send_notification(
                _WORKFLOW_FAILED_KEY, workflow_id,
                {"failed_step": e.step_name, "error_message": str(e)},
            )
        except Exception as e:
            # 未预期异常兜底
            logger.exception("工作流异常 workflow_id=%s", workflow_id)
            await self._update_workflow_status(
                workflow_id, WorkflowStatus.failed, error=str(e),
            )
            self._publish_event(_WORKFLOW_FAILED_KEY, {
                "workflow_id": workflow_id, "error": str(e),
            })
            await self._send_notification(
                _WORKFLOW_FAILED_KEY, workflow_id,
                {"error_message": str(e)},
            )
        finally:
            await self.cache.delete("workflow:current")

    async def _run_step(  # NOSONAR S3776: 工作流步骤执行含异常兜底与状态流转
        self, workflow_id: str, step_name: WorkflowStepName, seq: int,
        func, context: dict,
    ) -> None:
        """执行单步：记录状态 → 调用函数 → 失败重试 3 次（LLD 5.1.2）。

        退避策略：5s, 10s（指数退避），与 LLD 伪代码一致。
        """
        step_record = await self._create_step_record(workflow_id, step_name, seq)
        await self._update_step_status(step_record.id, WorkflowStepStatus.running)

        last_error = None
        # 单步总超时：复用 WORKFLOW_LOCK_TTL_SEC（默认 1800s）
        # 防止 func 内部网络 I/O 永久阻塞导致步骤状态卡在 running（wf-20260722-0011 复现）
        step_timeout = settings.WORKFLOW_LOCK_TTL_SEC
        for attempt in range(3):  # 最多 3 次（含首次）
            try:
                started = localnow_naive()
                result = await asyncio.wait_for(func(context), timeout=step_timeout)
                duration_ms = int((localnow_naive() - started).total_seconds() * 1000)
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
            except asyncio.TimeoutError as e:
                # 单步总超时：视为可重试错误，与其他异常一同进入重试流程
                last_error = TimeoutError(
                    f"步骤 {step_name.value} 执行超过 {step_timeout}s 总超时"
                )
                await self._update_step_status(
                    step_record.id, WorkflowStepStatus.retrying,
                    retry_count=attempt + 1, error=str(last_error),
                )
                logger.warning(
                    "步骤超时 workflow_id=%s step=%s attempt=%d timeout=%ds",
                    workflow_id, step_name.value, attempt + 1, step_timeout,
                )
                if attempt < 2:
                    await asyncio.sleep(5 * (attempt + 1))  # 5s, 10s 退避
            except asyncio.CancelledError:
                # Python 3.14: CancelledError 继承自 BaseException，
                # 普通 except Exception 无法捕获。步骤协程被取消（如 wait_for
                # 超时取消内部协程、或工作流任务被外部取消）时会逃逸到任务层，
                # 导致 workflow 以空 error 静默失败且 failed_step 为空。
                # 此处转为可读失败并带上 exc_info，便于定位根因；取消不可重试。
                logger.error(
                    "步骤被取消 workflow_id=%s step=%s attempt=%d（CancelledError）",
                    workflow_id, step_name.value, attempt + 1, exc_info=True,
                )
                last_error = RuntimeError(
                    f"步骤 {step_name.value} 被取消（可能单步超时 {step_timeout}s "
                    f"或任务被外部取消）"
                )
                await self._update_step_status(
                    step_record.id, WorkflowStepStatus.failed,
                    retry_count=attempt + 1, error=str(last_error),
                )
                break
            except Exception as e:
                last_error = e
                await self._update_step_status(
                    step_record.id, WorkflowStepStatus.retrying,
                    retry_count=attempt + 1, error=str(e),
                )
                logger.warning(
                    "步骤重试 workflow_id=%s step=%s attempt=%d error=%s",
                    workflow_id, step_name.value, attempt + 1, e,
                    exc_info=True,
                )
                if attempt < 2:
                    await asyncio.sleep(5 * (attempt + 1))  # 5s, 10s 退避

        # 3 次均失败
        # 若异常携带 failure_details（如 rewriter.LLMError），记录到 result 字段
        # 供前端工作流详情页展示每条素材的失败原因，便于运维快速定位
        failed_result = None
        if last_error is not None and hasattr(last_error, "failure_details"):
            details = getattr(last_error, "failure_details", None)
            if details:
                failed_result = {"failure_details": details}
        logger.error(
            "步骤最终失败 workflow_id=%s step=%s attempt=%d: %s",
            workflow_id, step_name.value, attempt, last_error,
            exc_info=last_error if last_error is not None else False,
        )
        await self._update_step_status(
            step_record.id, WorkflowStepStatus.failed,
            error=str(last_error), result=failed_result,
        )
        self._publish_event("workflow.step.failed", {
            "workflow_id": workflow_id,
            "step": step_name.value,
            "seq": seq,
            "error": str(last_error),
        })
        raise StepFailedError(step_name.value, last_error)

    # 步骤执行顺序：用于断点续跑时判断哪些步骤已完成
    _STEP_ORDER = [
        WorkflowStepName.crawl,
        WorkflowStepName.rewrite,
        WorkflowStepName.tts,
        WorkflowStepName.stitch,
        WorkflowStepName.review,
    ]

    async def _load_completed_step_context(
        self, workflow_id: str,
    ) -> tuple[set, dict]:
        """加载已成功完成的步骤及其 result，用于断点续跑跳过已完成步骤。

        Returns:
            (completed_step_names, resumed_context)
            - completed_step_names: 已成功步骤的 WorkflowStepName 集合
            - resumed_context: 已完成步骤 result 合并后的上下文字典
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(WorkflowStep).where(
                    WorkflowStep.workflow_id == workflow_id,
                    WorkflowStep.status == WorkflowStepStatus.success.value,
                )
            )
            steps = result.scalars().all()

        completed: set = set()
        resumed_context: dict = {}
        for step in steps:
            try:
                step_name = WorkflowStepName(step.step_name)
            except ValueError:
                continue
            completed.add(step_name)
            # 将已完成步骤的 result 合并到上下文，供后续步骤使用
            if step.result:
                resumed_context.update(step.result)
        return completed, resumed_context

    # ===== 内容安全检测（rewrite 步骤后执行） =====

    async def _run_content_security_check(self, workflow_id: str, context: dict) -> None:
        """rewrite 步骤后执行微信内容安全检测。

        设计为"告警不阻断"：任何异常都只记录日志，不影响后续 tts/stitch 步骤。
        原因：rewriter.py 中已有 AC 自动机敏感词替换作为硬兜底，
        本检测作为二次告警层，供运营在后台审核时参考。
        检测结果合并到 rewrite 步骤的 result.content_security 字段。
        """
        script_id = context.get("script_id")
        if not script_id:
            logger.warning("内容安全检测跳过：context 缺少 script_id")
            return

        # 查询稿件全文用于检测
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Script.full_text).where(Script.id == script_id)
                )
                full_text = result.scalar_one_or_none()
        except Exception as e:
            logger.warning(
                "内容安全检测跳过：查询稿件失败 script_id=%s error=%s", script_id, e,
            )
            return

        if not full_text:
            logger.warning("内容安全检测跳过：script_id=%s 稿件为空", script_id)
            return

        # 调用检测服务（内部已处理所有异常，不会抛出）
        try:
            from app.services.content_security_service import ContentSecurityService
            security_result = await ContentSecurityService.check_text(full_text)
        except Exception as e:
            # 防御性兜底：即使 check_text 内部漏处理异常也不影响工作流
            logger.warning(
                "内容安全检测异常（不阻断工作流）workflow_id=%s: %s", workflow_id, e,
            )
            return

        # 将检测结果合并到 rewrite 步骤的 result.content_security 字段
        try:
            await self._merge_step_result_field(
                workflow_id, WorkflowStepName.rewrite,
                "content_security", security_result,
            )
            # 命中违规时发事件，便于后台实时告警
            if not security_result.get("safe") and not security_result.get("skipped"):
                self._publish_event("workflow.content_security.risky", {
                    "workflow_id": workflow_id,
                    "detail": security_result.get("detail", []),
                })
        except Exception as e:
            logger.warning(
                "写入内容安全检测结果到 workflow_step 失败 workflow_id=%s: %s",
                workflow_id, e,
            )

    async def _merge_step_result_field(
        self, workflow_id: str, step_name: WorkflowStepName,
        field: str, value: Any,
    ) -> None:
        """合并更新 workflow_step.result 中的指定字段。

        避免覆盖整个 result（rewrite 步骤 result 含 script_id/segments/total_words
        等后续步骤依赖的字段），仅追加 content_security 等附加信息。
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(WorkflowStep).where(
                    WorkflowStep.workflow_id == workflow_id,
                    WorkflowStep.step_name == step_name.value,
                ).order_by(WorkflowStep.id.desc()).limit(1)
            )
            step = result.scalar_one_or_none()
            if step is None:
                logger.warning(
                    "合并 step result 失败：未找到步骤 %s workflow_id=%s",
                    step_name.value, workflow_id,
                )
                return
            # SQLAlchemy JSON 字段需整体赋值才会触发脏测试
            current_result = dict(step.result or {})
            current_result[field] = value
            step.result = current_result
            await session.commit()

    # ===== 审核与发布 =====

    async def _create_review(self, context: dict) -> dict:
        """步骤 5：从 context 取产出，创建 review 记录（status=pending）。

        review 表是审核流转的核心：运营在后台 approve/reject/replace，
        approve 时联动 ContentService.publish_episode 创建 episode。

        创建后将 review.created_at 写入 context，供后续自动审批计算节省时间。
        """
        workflow_id = context["workflow_id"]
        episode_date = context["episode_date"]
        script_id = context["script_id"]
        audio_url = context["final_audio_url"]
        # HLS 清单 URL：拼接阶段生成的 m3u8，为空表示未生成（HLS_ENABLE=false 或生成失败）
        hls_url = context.get("hls_url")

        async with AsyncSessionLocal() as session:
            review = Review(
                workflow_id=workflow_id,
                episode_date=episode_date,
                script_id=script_id,
                audio_url=audio_url,
                hls_url=hls_url,
                status=ReviewStatus.pending,
            )
            session.add(review)
            await session.commit()
            await session.refresh(review)
            review_id = review.id
            review_created_at = review.created_at

        # 写入 context 供 try_auto_approve 使用（计算节省时间）
        context["review_created_at"] = review_created_at

        logger.info(
            "审核记录已创建 workflow_id=%s review_id=%s",
            workflow_id, review_id,
        )
        return {"review_id": review_id}

    async def _try_auto_review(self, context: dict) -> None:
        """工作流完成后尝试自动审批。

        在主流程 status=success 之后、发送 pending_review 通知之前调用：
        - 自动审批成功：直接发布节目，不发 pending_review 通知（避免冗余）
        - 自动审批失败或不满足条件：继续发送 pending_review 通知，由人工审核

        所有异常都被捕获，绝不阻塞工作流主流程。
        """
        workflow_id = context["workflow_id"]
        review_id = context.get("review_id")
        review_created_at = context.get("review_created_at")

        if not review_id or not review_created_at:
            logger.warning(
                "自动审批跳过：context 缺少 review_id 或 review_created_at workflow_id=%s",
                workflow_id,
            )
            return

        try:
            from app.services.auto_review_service import AutoReviewService
            async with AsyncSessionLocal() as session:
                svc = AutoReviewService(session)
                result = await svc.try_auto_approve(
                    workflow_id=workflow_id,
                    review_id=review_id,
                    review_created_at=review_created_at,
                )
            if result.get("auto_approved"):
                # 自动审批成功：跳过 pending_review 通知，避免冗余打扰
                context["_auto_review_succeeded"] = True
                logger.info(
                    "自动审批成功，跳过 pending_review 通知 workflow_id=%s",
                    workflow_id,
                )
        except Exception as exc:
            # 自动审批失败不阻塞工作流，仍会发送 pending_review 通知
            logger.exception(
                "自动审批异常 workflow_id=%s review_id=%s: %s",
                workflow_id, review_id, exc,
            )

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
        """06:30 备播检查：对每个活跃频道独立检查备播（LLD 5.1.3）。

        多频道场景下按频道分组查询，避免 scalar_one_or_none 抛 MultipleResultsFound。
        单频道失败不影响其他频道，异常隔离。
        """
        today = date.today()
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Channel).where(Channel.is_active == 1)
            )
            channels = result.scalars().all()

        for ch in channels:
            try:
                await self._check_backup_single(channel_id=ch.id, today=today)
            except Exception:
                logger.exception("频道 %s 备播检查失败", ch.id)

    async def _check_backup_single(self, channel_id: int, today: date) -> None:
        """单频道备播检查：今日 episode 未发布则复用前一日音频。

        频道归属严格匹配：今日检查仅按 channel_id 精确匹配，避免跨频道误判。
        前一日节目查找优先按 channel_id 精确匹配，无结果时才回退到
        channel_id IS NULL 的历史节目（频道功能上线前的遗留数据）。
        """
        yesterday = today - timedelta(days=1)
        async with AsyncSessionLocal() as session:
            # 今日已发布则无需备播（严格按 channel_id 匹配，不兜底 NULL）
            result = await session.execute(
                select(Episode).where(
                    Episode.date == today,
                    Episode.status == EpisodeStatus.published,
                    Episode.channel_id == channel_id,
                ).limit(1)
            )
            if result.scalar_one_or_none() is not None:
                logger.info("频道 %s 备播检查：今日已发布，跳过", channel_id)
                return

            # 查前一日已发布节目：优先精确匹配 channel_id
            result = await session.execute(
                select(Episode).where(
                    Episode.date == yesterday,
                    Episode.status == EpisodeStatus.published,
                    Episode.channel_id == channel_id,
                ).limit(1)
            )
            prev = result.scalar_one_or_none()
            if prev is None:
                # 回退到 channel_id IS NULL 的历史节目（频道功能上线前的遗留数据）
                # 仅用于频道首次上线时的过渡期，多频道场景下不会跨频道误用
                result = await session.execute(
                    select(Episode).where(
                        Episode.date == yesterday,
                        Episode.status == EpisodeStatus.published,
                        Episode.channel_id.is_(None),
                    ).limit(1)
                )
                prev = result.scalar_one_or_none()
            if prev is None:
                await self._alert_operators(
                    f"频道 {channel_id} 备播失败：前一日 {yesterday} 节目不存在，需人工介入"
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
                channel_id=channel_id,
                is_backup=1,
                status=EpisodeStatus.published,
                published_at=localnow_naive(),
            )
            session.add(backup)
            await session.commit()

        # 失效今日节目缓存，让小程序能看到备播节目
        await self.cache.delete("episode:today")
        await self._alert_operators(
            f"频道 {channel_id} 已启用备播（复用 {yesterday} 节目音频），请事后排查原因"
        )
        logger.warning("频道 %s 已启用备播 date=%s 复用=%s", channel_id, today, yesterday)

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
        """每日 03:00 清理 crawler_dedup 表过期记录 + 孤儿记录 + 复活僵尸素材。

        替代原 Redis Set 的 EXPIRE 自动过期：SQLite 表需主动清理，
        按 CRAWLER_DEDUP_TTL_DAYS 配置保留窗口删除超出范围的记录。

        额外清理孤儿记录：dedup 表中 url 不在 material 表中的记录。
        场景：用户通过非标准方式删除了 material（如直接 SQL 操作），
        导致 dedup 表残留的 URL 锁阻止爬虫重新入库。
        正常流程下 batch_delete_workflows 已保留 material，不会产生孤儿，
        此清理是防御性兜底。

        僵尸素材复活：material 存在但 status=selected 且超过 TTL 窗口的素材，
        被历史工作流选中后因异常未回滚，dedup 锁住 URL 阻止爬虫重新入库，
        形成死锁。复活（重置为 pending）后 dedup 仍保留，爬虫可刷新内容。
        """
        cutoff = localnow_naive() - timedelta(days=settings.CRAWLER_DEDUP_TTL_DAYS)
        try:
            async with AsyncSessionLocal() as session:
                # 1. 清理过期记录（TTL 窗口外）
                result_ttl = await session.execute(
                    delete(CrawlerDedup).where(CrawlerDedup.created_at < cutoff)
                )
                deleted_ttl = result_ttl.rowcount

                # 2. 清理孤儿记录（url 不在 material 表中）+ 解锁僵尸 selected 素材
                # 原逻辑仅清理 url 不在 material 表的孤儿，但漏了一种场景：
                # material 存在但 status=selected 且超过 TTL 窗口（僵尸素材）。
                # 这些素材被历史工作流选中后未回滚，dedup 锁住 URL 阻止爬虫重新入库，
                # 形成死锁（wf-20260725-0009 channel_id=9 23 条素材全部 selected）。
                # 解法：对超过 TTL 窗口的 selected 素材，同时清理 dedup 记录，
                # 让爬虫能重新爬取并刷新素材内容。
                from sqlalchemy import update as sa_update
                from app.models.material import MaterialStatus

                # 2a. 先重置超期 selected 素材为 pending（僵尸复活）
                result_revive = await session.execute(
                    sa_update(Material)
                    .where(
                        Material.status == MaterialStatus.selected.value,
                        Material.crawled_at < cutoff,
                    )
                    .values(status=MaterialStatus.pending.value, workflow_id=None)
                )
                revived = result_revive.rowcount

                # 2b. 清理 url 不在 material 表的孤儿 dedup 记录
                material_urls = select(Material.url)
                result_orphan = await session.execute(
                    delete(CrawlerDedup).where(
                        CrawlerDedup.url.not_in(material_urls)
                    )
                )
                deleted_orphan = result_orphan.rowcount

                await session.commit()
            if deleted_ttl > 0 or deleted_orphan > 0 or revived > 0:
                logger.info(
                    "清理爬虫去重表：过期 %d 条，孤儿 %d 条，复活僵尸素材 %d 条",
                    deleted_ttl, deleted_orphan, revived,
                )
        except Exception as e:
            # 清理失败不中断调度器，下次调度继续处理
            logger.exception("清理爬虫去重表失败: %s", e)

    async def _daily_backup(self) -> None:
        """每日 04:00 执行数据库备份 + 过期备份清理。

        备份失败仅告警不中断调度器：备份是数据安全兜底，
        单日失败可由次日备份补回，但需告警让运维感知并及时排查。
        """
        from app.services.backup_service import BackupService
        try:
            backup_path = await BackupService.backup_database()
            logger.info("每日数据库备份完成 path=%s", backup_path)
        except Exception as e:
            logger.exception("每日数据库备份失败: %s", e)
            await self._alert_operators(f"每日数据库备份失败: {e}")
            # 备份失败仍尝试清理过期文件（独立失败不影响清理）
        try:
            deleted = await BackupService.cleanup_old_backups()
            if deleted > 0:
                logger.info("清理过期备份 %d 个", deleted)
        except Exception as e:
            logger.exception("清理过期备份失败: %s", e)

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

    async def _cleanup_entry_map(self) -> None:
        """定期清理 entry_map 中已离开 queued 状态的条目，避免内存泄漏。

        工作流从 queued 转 running/success/failed/cancelled 后，
        其 entry_map 条目不再有用但可能残留（如 _run_workflow_with_release
        执行前异常退出），需定期扫描清理。
        """
        if not self._entry_map:
            return
        # 查询仍处于 queued 状态的 workflow_id，其余状态可安全移除
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Workflow.id).where(
                    Workflow.id.in_(list(self._entry_map.keys())),
                    Workflow.status == WorkflowStatus.queued.value,
                )
            )
            active_ids = {row[0] for row in result.all()}

        stale_ids = set(self._entry_map.keys()) - active_ids
        for wid in stale_ids:
            self._entry_map.pop(wid, None)
        if stale_ids:
            logger.debug("清理 entry_map 中 %d 个过期条目", len(stale_ids))

    async def _check_rss_sources(self) -> None:
        """每 2 小时巡检所有 RSS 源可达性。

        委托 rss_source_service.check_all_sources 执行并发探测，
        连续失败 3 次的源在 service 内部发 WARNING 日志。
        巡检失败不中断调度器，下次调度继续处理。
        """
        try:
            from app.services.rss_source_service import check_all_sources
            result = await check_all_sources()
            # 失败率超过 30% 时发告警，提示运维介入
            fail_rate = result["fail"] / result["total"] if result["total"] > 0 else 0
            if fail_rate > 0.30:
                logger.warning(
                    "RSS 源可达性告警：失败率 %.0f%%（%d/%d 失败）",
                    fail_rate * 100, result["fail"], result["total"],
                )
        except Exception as e:
            logger.exception("RSS 源巡检失败: %s", e)

    # ===== 通知 =====

    async def _send_notification(
        self,
        event_type: str,
        workflow_id: str,
        extra_vars: dict | None = None,
    ) -> None:
        """发送结构化工作流通知（基于模板 + actionCard 卡片）。

        - sender 内部已处理开关检查、频次去重、模板渲染、日志记录
        - 任何异常都不向上抛出，避免中断工作流主流程
        - sender 返回 failed 时降级调用 _alert_operators 兜底，确保运维一定收到消息
        """
        try:
            from app.services.notification import get_notification_sender
            sender = get_notification_sender()
            result = await sender.send_workflow_event(
                event_type, workflow_id, extra_vars,
            )
            status = result.get("status")
            if status == "failed":
                # 结构化通知失败时降级走通用告警，确保运维一定收到
                await self._alert_operators(
                    f"工作流 {workflow_id} 通知发送失败 "
                    f"(event={event_type}): {result.get('message', '')}"
                )
        except Exception as e:
            logger.exception(
                "通知发送异常 workflow_id=%s event_type=%s: %s",
                workflow_id, event_type, e,
            )
            await self._alert_operators(
                f"工作流 {workflow_id} 通知发送异常 (event={event_type}): {e}"
            )

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
            title="MorningBrief 工作流告警",
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
        """更新 workflow 状态，失败时附加 error + finished_at。

        工作流失败时自动重置关联的 material 状态为 pending：
        rewriter 选中素材后若后续步骤（tts/stitch）失败，material 会卡在 selected，
        加上 crawler_dedup 拦截 URL，爬虫无法重新入库，形成死锁。
        在此统一兜底，避免失败工作流的素材被永久锁定。
        """
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
                wf.finished_at = localnow_naive()
                # 工作流终态（无论成功失败）：解除素材关联，重置为 pending 供后续工作流复用
                # 成功时也重置：素材已完成使命（产出 episode），下次工作流应爬取新素材
                # 失败时必须重置：否则素材卡在 selected 形成 dedup 死锁（wf-20260725-0009 复现）
                from sqlalchemy import update as sa_update
                from app.models.material import MaterialStatus
                await session.execute(
                    sa_update(Material)
                    .where(Material.workflow_id == workflow_id)
                    .values(status=MaterialStatus.pending.value, workflow_id=None)
                )
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
                started_at=localnow_naive(),
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
                step.finished_at = localnow_naive()
            await session.commit()


# 模块级单例，供 main.py lifespan 与路由层共享
workflow_scheduler = WorkflowScheduler()
