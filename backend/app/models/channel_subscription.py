"""频道订阅表模型。

设计原因：
- 多频道架构下用户需主动订阅感兴趣的频道，首页据此优先展示
- UNIQUE(user_id, channel_id) 保证每用户对每频道仅订阅一次
- 与 Subscription（订阅消息）表完全独立，此表仅记录频道关注关系
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, DateTime, Index, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utcnow_naive
from app.database import Base


class ChannelSubscription(Base):
    """用户频道订阅关系（每用户每频道仅一条）。"""
    __tablename__ = "channel_subscription"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_channel_sub_user_channel"),
        Index("idx_channel_sub_user", "user_id"),
        Index("idx_channel_sub_channel", "channel_id"),
        {"comment": "用户频道订阅关系表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="用户 ID")
    # 外键引用 channel.id，频道删除时级联删除订阅关系
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channel.id", ondelete="CASCADE"), nullable=False,
        comment="频道 ID"
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=utcnow_naive, comment="订阅时间"
    )
