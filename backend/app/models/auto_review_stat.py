"""自动审批统计模型。

设计原因：
- 每次自动审批尝试记录一条，便于统计成功率与失败原因分布
- time_saved_sec 字段量化自动审批节省的人工等待时间（从 review 创建到 approve 的耗时）
- 失败记录独立存储，避免与 Review 表的状态字段耦合
- 与 AuditLog 互补：AuditLog 记录操作动作，本表记录自动审批的执行详情与统计指标
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AutoReviewStat(Base):
    """自动审批执行记录（每次尝试一条，含成功与失败）。"""

    __tablename__ = "auto_review_stat"
    __table_args__ = (
        Index("idx_auto_review_stat_created", "created_at"),
        Index("idx_auto_review_stat_success", "success"),
        Index("idx_auto_review_stat_workflow", "workflow_id"),
        {"comment": "自动审批执行记录表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("review.id"),
        comment="关联审核记录 ID，失败前未创建 review 时为空",
    )
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # success=True 时记录触发条件命中的规则列表，False 时记录失败原因
    trigger_reason: Mapped[Optional[str]] = mapped_column(
        Text, comment="JSON 字符串：命中的规则列表或失败原因",
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, comment="失败时的错误信息，成功时为空",
    )
    # 节省时间：从 review.created_at 到自动审批完成的时间差（秒）
    # 仅 success=True 时有意义，量化自动审批的业务价值
    time_saved_sec: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(),
    )
