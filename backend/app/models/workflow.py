"""工作流模型（含 workflow + workflow_step 两张表）。"""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Integer, Text, JSON, DateTime, Date, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class WorkflowSource(str, Enum):
    cron = "cron"
    manual = "manual"


class WorkflowStatus(str, Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class WorkflowStepName(str, Enum):
    crawl = "crawl"
    rewrite = "rewrite"
    tts = "tts"
    stitch = "stitch"
    review = "review"
    publish = "publish"


class WorkflowStepStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    retrying = "retrying"


class Workflow(Base):
    __tablename__ = "workflow"
    __table_args__ = (
        Index("idx_date", "episode_date"),
        Index("idx_status", "status"),
        Index("idx_workflow_channel", "channel_id"),
        CheckConstraint("source IN ('cron', 'manual')", name="ck_workflow_source"),
        CheckConstraint("status IN ('queued', 'running', 'success', 'failed', 'cancelled')", name="ck_workflow_status"),
        {"comment": "工作流表"},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="workflow_id")
    episode_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[Optional[str]] = mapped_column(
        String(16), default=WorkflowStatus.queued.value
    )
    # 频道归属：频道删除时 ON DELETE SET NULL，避免频道删除连带删除工作流
    channel_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("channel.id", ondelete="SET NULL"), nullable=True,
    )
    # 优先级 0-10，默认 5；sort_priority = -priority 实现 PriorityQueue DESC
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    # 不用 server_default=func.now()：SQLite 的 CURRENT_TIMESTAMP 返回 UTC，与本地时间混合导致前端显示偏差 8 小时
    # Python 端在创建 Workflow 时显式赋值 utcnow_naive()（本地时间）
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error: Mapped[Optional[str]] = mapped_column(Text)

    steps: Mapped[list["WorkflowStep"]] = relationship(
        "WorkflowStep", back_populates="workflow", cascade="all, delete-orphan"
    )
    # joinedload 场景：queue_service.list_queue_tasks 需展示频道名
    channel: Mapped[Optional["Channel"]] = relationship("Channel", lazy="joined")


class WorkflowStep(Base):
    __tablename__ = "workflow_step"
    __table_args__ = (
        Index("idx_workflow_step", "workflow_id", "step_name"),
        CheckConstraint("step_name IN ('crawl', 'rewrite', 'tts', 'stitch', 'review', 'publish')", name="ck_workflow_step_step_name"),
        CheckConstraint("status IN ('pending', 'running', 'success', 'failed', 'retrying')", name="ck_workflow_step_status"),
        {"comment": "工作流步骤表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflow.id"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    status: Mapped[Optional[str]] = mapped_column(
        String(16), default=WorkflowStepStatus.pending.value
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    retry_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text)
    result: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="步骤产出 JSON 字符串（如素材数、稿件ID、音频URL）"
    )

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="steps")
