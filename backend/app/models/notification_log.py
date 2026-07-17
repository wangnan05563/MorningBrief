"""通知发送日志模型。

记录每条通知的实际发送结果（success/failed/suppressed），
含渲染时使用的 payload（JSON 字符串），便于审计与失败重发。
"""
from datetime import datetime

from sqlalchemy import Index, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class NotificationLog(Base):
    """通知发送日志表。

    status 三态：
    - success：实际发送且钉钉返回 errcode=0
    - failed：发送失败或钉钉返回错误
    - suppressed：因开关关闭/频次去重/未配置渠道而跳过
    """

    __tablename__ = "notification_log"
    __table_args__ = (
        Index("ix_notification_log_created", "created_at"),
        Index("ix_notification_log_workflow", "workflow_id"),
        {"comment": "通知发送日志表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="触发事件类型")
    channel: Mapped[str] = mapped_column(String(16), nullable=False, comment="渠道名")
    title: Mapped[str] = mapped_column(String(128), nullable=False, comment="实际发送标题")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="success | failed | suppressed",
    )
    error: Mapped[str] = mapped_column(Text, default="", comment="失败原因")
    payload: Mapped[str] = mapped_column(
        Text, default="", comment="JSON 字符串，渲染时的上下文变量",
    )
    workflow_id: Mapped[str] = mapped_column(
        String(64), default="", nullable=False, comment="关联工作流 ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )
