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
        # T01579：历史列表 WHERE status='published' ORDER BY date,id 单列索引需排序，
        # 复合索引可顺序扫描（SQLite 亦支持反向扫描实现 DESC 排序）
        Index("idx_episode_status_date", "status", "date"),
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
    # ===== 时长改造留痕（T02028，发布时从 review 快照）=====
    # duration 是成品时长（小程序据此算进度），但它可能含拼接阶段为达下限补入的 BGM/静音，
    # 或被 atempo 压缩过。列表要能标出「这个时长是凑出来的」，故同时留：
    # supplement_sec=补入秒数（>0 即被凑时长），original_duration_sec=改造前实测（内容真实长度）
    supplement_sec: Mapped[Optional[int]] = mapped_column(
        Integer, comment="为达时长下限补入的 BGM/静音秒数，>0 表示成品时长含凑时"
    )
    original_duration_sec: Mapped[Optional[int]] = mapped_column(
        Integer, comment="时长改造前的实测时长（秒），按内容核验用"
    )
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
