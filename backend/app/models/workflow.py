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
        CheckConstraint("source IN ('cron', 'manual')", name="ck_workflow_source"),
        CheckConstraint("status IN ('running', 'success', 'failed', 'cancelled')", name="ck_workflow_status"),
        {"comment": "工作流表"},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="workflow_id")
    episode_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[Optional[str]] = mapped_column(
        String(16), default=WorkflowStatus.running.value
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error: Mapped[Optional[str]] = mapped_column(Text)

    steps: Mapped[list["WorkflowStep"]] = relationship(
        "WorkflowStep", back_populates="workflow", cascade="all, delete-orphan"
    )


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
