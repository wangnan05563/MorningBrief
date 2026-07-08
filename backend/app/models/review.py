"""审核模型。"""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, String, Text, DateTime, Date, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    replaced = "replaced"


class Review(Base):
    __tablename__ = "review"
    __table_args__ = (
        Index("idx_status", "status"),
        Index("idx_date", "episode_date"),
        {"comment": "审核表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False)
    episode_date: Mapped[date] = mapped_column(Date, nullable=False)
    script_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("script.id"), nullable=False
    )
    audio_url: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[Optional[ReviewStatus]] = mapped_column(
        SAEnum(ReviewStatus), default=ReviewStatus.pending
    )
    reviewer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, comment="审核人 admin_user.id"
    )
    reviewer_name: Mapped[Optional[str]] = mapped_column(String(64))
    reason: Mapped[Optional[str]] = mapped_column(Text, comment="打回/替换理由")
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    script: Mapped["Script"] = relationship(
        "Script", back_populates="reviews", foreign_keys=[script_id]
    )
    # 反向关系：被节目引用
    episodes: Mapped[list["Episode"]] = relationship(
        "Episode", back_populates="review", foreign_keys="Episode.review_id"
    )
