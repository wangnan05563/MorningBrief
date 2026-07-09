"""稿件模型。"""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Integer, Text, JSON, DateTime, Date, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ScriptStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"


class Script(Base):
    __tablename__ = "script"
    __table_args__ = (
        Index("idx_workflow", "workflow_id"),
        Index("idx_date", "episode_date"),
        CheckConstraint("status IN ('draft', 'approved', 'rejected')", name="ck_script_status"),
        {"comment": "稿件表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False)
    episode_date: Mapped[date] = mapped_column(Date, nullable=False)
    full_text: Mapped[str] = mapped_column(Text, nullable=False, comment="完整稿件")
    segments: Mapped[list] = mapped_column(
        JSON, nullable=False, comment="分段结构 JSON 字符串 [{seq,title,content,start_sec,end_sec,material_ids}]"
    )
    total_words: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_duration: Mapped[Optional[int]] = mapped_column(Integer, comment="估算时长（秒）")
    referenced_materials: Mapped[Optional[list]] = mapped_column(JSON, comment="引用素材 URL 列表 JSON 字符串")
    categories: Mapped[Optional[list]] = mapped_column(JSON, comment="分类列表 JSON 字符串")
    status: Mapped[Optional[str]] = mapped_column(
        String(16), default=ScriptStatus.draft.value
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    # 反向关系：被节目引用
    episodes: Mapped[list["Episode"]] = relationship(
        "Episode", back_populates="script", foreign_keys="Episode.script_id"
    )
    # 反向关系：被审核引用
    reviews: Mapped[list["Review"]] = relationship(
        "Review", back_populates="script", foreign_keys="Review.script_id"
    )
