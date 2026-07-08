"""节目模型。"""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, String, Integer, SmallInteger, DateTime, Date, JSON, Enum as SAEnum, ForeignKey, Index
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
        {"comment": "节目表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False, comment="时长（秒）")
    audio_url: Mapped[str] = mapped_column(String(512), nullable=False)
    cover_url: Mapped[Optional[str]] = mapped_column(String(512))
    script_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("script.id")
    )
    categories: Mapped[Optional[list]] = mapped_column(JSON)
    status: Mapped[Optional[EpisodeStatus]] = mapped_column(
        SAEnum(EpisodeStatus), default=EpisodeStatus.draft
    )
    is_backup: Mapped[Optional[int]] = mapped_column(
        SmallInteger, default=0, comment="是否备播节目"
    )
    workflow_id: Mapped[Optional[str]] = mapped_column(String(64))
    review_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("review.id")
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
