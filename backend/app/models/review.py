"""审核模型。"""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, DateTime, Date, ForeignKey, Index, CheckConstraint
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
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'replaced')", name="ck_review_status"),
        {"comment": "审核表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False)
    episode_date: Mapped[date] = mapped_column(Date, nullable=False)
    script_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("script.id"), nullable=False
    )
    audio_url: Mapped[str] = mapped_column(String(512), nullable=False)
    # HLS 清单 URL：拼接阶段生成，发布时拷贝到 episode.hls_url；为空表示未生成 HLS
    hls_url: Mapped[Optional[str]] = mapped_column(String(512))
    # ===== 时长改造留痕（T02028）=====
    # 拼接阶段对成品时长做过两类改造：不足下限用 BGM/静音补足（concat.py:484+）、
    # 超上限用 atempo 压缩（concat.py:461+）。改造后的成品时长不能反映内容真实长度，
    # 而 episode.duration 又要落成品值（小程序按它算进度），所以这里把三个口径都存下来：
    # measured=成品实测，original=改造前实测，supplement=补入秒数（0/NULL 表示未补足）。
    measured_duration_sec: Mapped[Optional[int]] = mapped_column(
        Integer, comment="拼接成品实测时长（秒），发布时优先取此值"
    )
    original_duration_sec: Mapped[Optional[int]] = mapped_column(
        Integer, comment="时长改造前的实测时长（秒），未改造时与 measured 相同"
    )
    supplement_sec: Mapped[Optional[int]] = mapped_column(
        Integer, comment="为达时长下限补入的 BGM/静音秒数，>0 表示成品时长含凑时"
    )
    status: Mapped[Optional[str]] = mapped_column(
        String(16), default=ReviewStatus.pending.value
    )
    reviewer_id: Mapped[Optional[int]] = mapped_column(
        Integer, comment="审核人 admin_user.id"
    )
    reviewer_name: Mapped[Optional[str]] = mapped_column(String(64))
    reason: Mapped[Optional[str]] = mapped_column(Text, comment="打回/替换理由")
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    # 自动审批标记：True 表示由系统自动审批通过，False 或 NULL 表示人工审批
    # 用于审批历史中区分来源，便于追溯与统计
    auto_approved: Mapped[Optional[bool]] = mapped_column(
        Boolean, default=False, comment="是否系统自动审批",
    )
    # 自动审批触发的条件列表（JSON 字符串），仅 auto_approved=True 时有值
    # 例：["content_safe", "steps_first_success"]
    auto_trigger_reason: Mapped[Optional[str]] = mapped_column(
        Text, comment="自动审批触发条件 JSON，仅 auto_approved=True 时有值",
    )

    script: Mapped["Script"] = relationship(
        "Script", back_populates="reviews", foreign_keys=[script_id]
    )
    # 反向关系：被节目引用
    episodes: Mapped[list["Episode"]] = relationship(
        "Episode", back_populates="review", foreign_keys="Episode.review_id"
    )
