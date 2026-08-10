"""频道管理服务。

Channel 作为工作流的分组标签，支持按内容分类频道独立产出节目。
轻量级设计：仅 CRUD + 活跃频道查询，不绑定业务配置。

性能优化：频道列表缓存 5 分钟（路由层），增删改时通过 invalidate_list_cache 失效。
频道启停时通过 EventBus 发布 channel.active_changed 事件，
WorkflowScheduler 订阅该事件以取消已入队的禁用频道工作流，保持状态同步。
"""
import logging
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache as cache_manager
from app.core.event_bus import Event, get_event_bus
from app.core.timeutil import localnow_naive
from app.models.channel import Channel
from app.models.workflow import Workflow

logger = logging.getLogger(__name__)

_TTL_CHANNELS = 300

# 更新操作的哨兵：区分"调用方未传该字段（保持原值）"与"显式传 None（清空为继承动态）"
# material_lookback_days 的语义里 None=继承系统动态回溯，前端"取消勾选自定义"会显式发 null，
# 故不能用 None 既当默认值又当清空值；用独立哨兵让 null 能被真正写入。
_UNSET = object()


class ChannelService:
    """频道管理服务（基于传入的 AsyncSession，无独立状态）。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache = cache_manager

    async def list_channels(self, active_only: bool = False) -> list[Channel]:
        """查询频道列表。active_only=True 时仅返回 is_active=1 的频道。"""
        stmt = select(Channel).order_by(Channel.id)
        if active_only:
            stmt = stmt.where(Channel.is_active == 1)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_channel(self, channel_id: int) -> Optional[Channel]:
        """查询单个频道。"""
        return await self.db.get(Channel, channel_id)

    async def invalidate_list_cache(self) -> None:
        """频道增删改后失效列表缓存。

        同时失效 C 端频道列表缓存（api:channels:list_active），
        保证小程序 tab 在后台调整频道/排序后及时刷新（TTL 兜底 60s）。
        """
        await self.cache.delete("channels:list:all")
        await self.cache.delete("channels:list:active")
        await self.cache.delete("api:channels:list_active")

    async def create_channel(
        self, name: str, description: str = "",
        schedule_time: Optional[str] = None,
        intro_prompt: Optional[str] = None,
        outro_prompt: Optional[str] = None,
        constraint_prompt: Optional[str] = None,
        rewrite_template: Optional[str] = None,
        bgm_path: Optional[str] = None,
        bgm_volume: Optional[float] = None,
        segment_gap_sec: Optional[float] = None,
        bgm_gap_mode: Optional[str] = None,
        enable_thinking_question: Optional[int] = None,
        rss_sources: Optional[str] = None,
        keywords: Optional[str] = None,
        min_duration_sec: Optional[int] = None,
        display_order: int = 0,
        material_lookback_days: Optional[int] = None,
    ) -> Channel:
        """新增频道。name 唯一约束，冲突抛 ValueError。

        支持 schedule_time（定时触发）与 4 个提示词字段 + BGM 配置 + 段间静音 + 思考问题开关
        + RSS 源白名单 + 关键词过滤 + 最短时长 + 展示排序权重 + 素材周期回溯天数，均为可选。
        """
        channel = Channel(
            name=name, description=description, is_active=1,
            schedule_time=schedule_time,
            intro_prompt=intro_prompt,
            outro_prompt=outro_prompt,
            constraint_prompt=constraint_prompt,
            rewrite_template=rewrite_template,
            bgm_path=bgm_path,
            bgm_volume=bgm_volume,
            segment_gap_sec=segment_gap_sec,
            bgm_gap_mode=bgm_gap_mode,
            enable_thinking_question=enable_thinking_question,
            rss_sources=rss_sources,
            keywords=keywords,
            min_duration_sec=min_duration_sec,
            display_order=display_order,
            material_lookback_days=material_lookback_days,
        )
        self.db.add(channel)
        try:
            await self.db.commit()
        except IntegrityError as e:
            await self.db.rollback()
            raise ValueError(f"频道名称已存在: {name}") from e
        await self.db.refresh(channel)
        await self.invalidate_list_cache()
        logger.info("新增频道 channel_id=%s name=%s schedule=%s", channel.id, name, schedule_time)
        return channel

    async def update_channel(  # NOSONAR
        self, channel_id: int, name: Optional[str] = None, # NOSONAR
        description: Optional[str] = None, is_active: Optional[int] = None,
        schedule_time: Optional[str] = None,
        intro_prompt: Optional[str] = None,
        outro_prompt: Optional[str] = None,
        constraint_prompt: Optional[str] = None,
        rewrite_template: Optional[str] = None,
        bgm_path: Optional[str] = None,
        bgm_volume: Optional[float] = None,
        segment_gap_sec: Optional[float] = None,
        bgm_gap_mode: Optional[str] = None,
        enable_thinking_question: Optional[int] = None,
        rss_sources: Optional[str] = None,
        keywords: Optional[str] = None,
        min_duration_sec: Optional[int] = None,
        display_order: Optional[int] = None,
        material_lookback_days: Optional[int] = _UNSET,
    ) -> Channel:
        """修改频道。显式设置 updated_at（SQLite 不支持 ON UPDATE）。

        is_active 变更时发布 channel.active_changed 事件，
        WorkflowScheduler 取消已入队的禁用频道工作流。
        schedule_time 变更时发布 channel.schedule_changed 事件，
        WorkflowScheduler 重注册该频道的定时任务。
        """
        channel = await self.get_channel(channel_id)
        if channel is None:
            raise ValueError(f"频道不存在: {channel_id}")

        # 记录变更前的原值，用于判断是否需要发布事件
        old_is_active = channel.is_active
        old_schedule_time = channel.schedule_time

        if name is not None:
            channel.name = name
        if description is not None:
            channel.description = description
        if is_active is not None:
            channel.is_active = is_active
        if schedule_time is not None:
            channel.schedule_time = schedule_time
        if intro_prompt is not None:
            channel.intro_prompt = intro_prompt
        if outro_prompt is not None:
            channel.outro_prompt = outro_prompt
        if constraint_prompt is not None:
            channel.constraint_prompt = constraint_prompt
        if rewrite_template is not None:
            channel.rewrite_template = rewrite_template
        if bgm_path is not None:
            channel.bgm_path = bgm_path
        if bgm_volume is not None:
            channel.bgm_volume = bgm_volume
        if segment_gap_sec is not None:
            channel.segment_gap_sec = segment_gap_sec
        if bgm_gap_mode is not None:
            channel.bgm_gap_mode = bgm_gap_mode
        if enable_thinking_question is not None:
            channel.enable_thinking_question = enable_thinking_question
        if rss_sources is not None:
            channel.rss_sources = rss_sources
        if keywords is not None:
            channel.keywords = keywords
        if min_duration_sec is not None:
            channel.min_duration_sec = min_duration_sec
        if display_order is not None:
            channel.display_order = display_order
        # material_lookback_days 用哨兵区分：未传(_UNSET)保持原值；显式传 None 则清空为继承动态
        if material_lookback_days is not _UNSET:
            channel.material_lookback_days = material_lookback_days
        channel.updated_at = localnow_naive()

        try:
            await self.db.commit()
        except IntegrityError as e:
            await self.db.rollback()
            raise ValueError(f"频道名称已存在: {name}") from e
        await self.db.refresh(channel)
        await self.invalidate_list_cache()

        # is_active 实际变化时发布事件，避免重复发布相同状态
        if is_active is not None and is_active != old_is_active:
            self._publish_active_changed(channel_id, is_active)

        # schedule_time 变化时发布事件，触发调度器重注册定时任务
        if schedule_time is not None and schedule_time != old_schedule_time:
            self._publish_schedule_changed(channel_id, schedule_time, channel.is_active)

        logger.info("修改频道 channel_id=%s", channel_id)
        return channel

    @staticmethod
    def _publish_active_changed(channel_id: int, is_active: int) -> None:
        """发布频道启停事件（非阻塞，失败不影响主流程）。

        用 publish_nowait 而非 await publish：频道更新已在事务中，
        事件入队即返回，避免事务长时间持有连接。
        """
        try:
            bus = get_event_bus()
            bus.publish_nowait(Event(
                type="channel.active_changed",
                data={"channel_id": channel_id, "is_active": is_active},
            ))
        except Exception:
            logger.debug("EventBus 发布 channel.active_changed 失败（不影响主流程）", exc_info=True)

    @staticmethod
    def _publish_schedule_changed(channel_id: int, schedule_time: str, is_active: int) -> None:
        """发布频道定时变更事件，触发调度器重注册 cron 任务。

        与 active_changed 同样用 publish_nowait 避免事务长时间持连接。
        """
        try:
            bus = get_event_bus()
            bus.publish_nowait(Event(
                type="channel.schedule_changed",
                data={
                    "channel_id": channel_id,
                    "schedule_time": schedule_time,
                    "is_active": is_active,
                },
            ))
        except Exception:
            logger.debug("EventBus 发布 channel.schedule_changed 失败（不影响主流程）", exc_info=True)

    async def delete_channel(self, channel_id: int) -> None:
        """删除频道。关联 workflow 的 channel_id 手动置 NULL。

        不依赖 SQLite 外键 ON DELETE SET NULL：测试环境默认未开启
        PRAGMA foreign_keys，手动 UPDATE 保证行为一致。
        同时发布 schedule_changed 事件（schedule_time 置空），
        让调度器移除该频道的定时任务。
        """
        channel = await self.get_channel(channel_id)
        if channel is None:
            raise ValueError(f"频道不存在: {channel_id}")
        # 先解除关联 workflow 的 channel_id，避免删除时外键约束（若开启）报错
        await self.db.execute(
            update(Workflow)
            .where(Workflow.channel_id == channel_id)
            .values(channel_id=None)
        )
        await self.db.delete(channel)
        await self.db.commit()
        await self.invalidate_list_cache()
        # 移除该频道的定时任务（schedule_time 置空表示移除）
        self._publish_schedule_changed(channel_id, "", channel.is_active)
        logger.info("删除频道 channel_id=%s name=%s", channel_id, channel.name)
