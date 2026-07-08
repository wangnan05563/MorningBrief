"""工作流模型（含 workflow + workflow_step 两张表）。"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, String, Integer, Text, DateTime, Date, JSON, Enum as SAEnum, ForeignKey, Index
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
        {"comment": "工作流表"},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="workflow_id")
    episode_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    source: Mapped[WorkflowSource] = mapped_column(SAEnum(WorkflowSource), nullable=False)
    status: Mapped[Optional[WorkflowStatus]] = mapped_column(
        SAEnum(WorkflowStatus), default=WorkflowStatus.running
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
        {"comment": "工作流步骤表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflow.id"), nullable=False
    )
    step_name: Mapped[WorkflowStepName] = mapped_column(
        SAEnum(WorkflowStepName), nullable=False
    )
    status: Mapped[Optional[WorkflowStepStatus]] = mapped_column(
        SAEnum(WorkflowStepStatus), default=WorkflowStepStatus.pending
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    retry_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text)
    result: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="步骤产出（如素材数、稿件ID、音频URL）"
    )

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="steps")
