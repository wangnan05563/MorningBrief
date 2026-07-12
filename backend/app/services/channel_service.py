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
from app.core.timeutil import utcnow_naive
from app.models.channel import Channel

logger = logging.getLogger(__name__)

_TTL_CHANNELS = 300


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
        """频道增删改后失效列表缓存。"""
        await self.cache.delete("channels:list:all")
        await self.cache.delete("channels:list:active")

    async def create_channel(self, name: str, description: str = "") -> Channel:
        """新增频道。name 唯一约束，冲突抛 ValueError。"""
        channel = Channel(name=name, description=description, is_active=1)
        self.db.add(channel)
        try:
            await self.db.commit()
        except IntegrityError as e:
            await self.db.rollback()
            raise ValueError(f"频道名称已存在: {name}") from e
        await self.db.refresh(channel)
        await self.invalidate_list_cache()
        logger.info("新增频道 channel_id=%s name=%s", channel.id, name)
        return channel

    async def update_channel(
        self, channel_id: int, name: Optional[str] = None,
        description: Optional[str] = None, is_active: Optional[int] = None,
    ) -> Channel:
        """修改频道。显式设置 updated_at（SQLite 不支持 ON UPDATE）。

        is_active 变更时通过 EventBus 发布 channel.active_changed 事件，
        WorkflowScheduler 订阅该事件取消已入队的禁用频道工作流。
        """
        channel = await self.get_channel(channel_id)
        if channel is None:
            raise ValueError(f"频道不存在: {channel_id}")

        # 记录启停变更前的原值，用于判断是否需要发布事件
        old_is_active = channel.is_active

        if name is not None:
            channel.name = name
        if description is not None:
            channel.description = description
        if is_active is not None:
            channel.is_active = is_active
        channel.updated_at = utcnow_naive()

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

    async def delete_channel(self, channel_id: int) -> None:
        """删除频道。关联 workflow 的 channel_id 由外键 ON DELETE SET NULL 自动置 NULL。"""
        channel = await self.get_channel(channel_id)
        if channel is None:
            raise ValueError(f"频道不存在: {channel_id}")
        await self.db.delete(channel)
        await self.db.commit()
        await self.invalidate_list_cache()
        logger.info("删除频道 channel_id=%s name=%s", channel_id, channel.name)
