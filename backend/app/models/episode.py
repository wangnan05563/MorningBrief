"""节目模型。"""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Integer, SmallInteger, DateTime, Date, Text, JSON, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class EpisodeStatus(str, Enum):
    draft = "draft"
    published = "published"
    offline = "offline"


class Episode(Base):
    __tablename__ = "episode"
    __table_args__ = (
        Index("idx_date", "date"),
        Index("idx_status", "status"),
        Index("idx_episode_channel", "channel_id"),
        CheckConstraint("status IN ('draft', 'published', 'offline')", name="ck_episode_status"),
        {"comment": "节目表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # 频道归属：多频道场景下同一日期可有多个频道的节目，故 date 不再 unique
    channel_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("channel.id", ondelete="SET NULL"), nullable=True,
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False, comment="时长（秒）")
    audio_url: Mapped[str] = mapped_column(String(512), nullable=False)
    # HLS m3u8 清单 URL：小程序 BackgroundAudioManager.protocol='hls' 时优先使用
    # 为什么单独存而非动态推导：HLS 是否生成由配置决定，且文件位于子目录，
    # 持久化避免每次请求探测文件系统；为空时客户端回退到 audio_url
    hls_url: Mapped[Optional[str]] = mapped_column(String(512))
    cover_url: Mapped[Optional[str]] = mapped_column(String(512))
    script_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("script.id")
    )
    categories: Mapped[Optional[list]] = mapped_column(JSON, comment="分类列表 JSON 字符串")
    status: Mapped[Optional[str]] = mapped_column(
        String(16), default=EpisodeStatus.draft.value
    )
    is_backup: Mapped[Optional[int]] = mapped_column(
        SmallInteger, default=0, comment="是否备播节目"
    )
    workflow_id: Mapped[Optional[str]] = mapped_column(String(64))
    review_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("review.id")
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    script: Mapped[Optional["Script"]] = relationship(
        "Script", back_populates="episodes", foreign_keys=[script_id]
    )
    review: Mapped[Optional["Review"]] = relationship(
        "Review", back_populates="episodes", foreign_keys=[review_id]
    )
    # 反向关系：被播放日志引用
    play_logs: Mapped[list["PlayLog"]] = relationship(
        "PlayLog", back_populates="episode"
    )
