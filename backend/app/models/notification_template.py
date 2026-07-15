"""通知消息模板模型。

每条模板对应一个工作流事件类型（如 workflow.pending_review），
title_template / body_template 支持 {{var}} 变量插值，
由 renderer.py 在发送时填充实际值。
"""
from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class NotificationTemplate(Base):
    """通知消息模板表。

    每个事件类型仅允许一条启用模板（unique event_type）。
    预设模板 is_preset=1 不可删除但可编辑，便于管理员微调文案。
    """

    __tablename__ = "notification_template"
    __table_args__ = ({"comment": "通知消息模板表"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
        comment="事件类型: workflow.failed | workflow.pending_review | workflow.published",
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="模板名称")
    title_template: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="标题模板，支持 {{var}} 插值",
    )
    body_template: Mapped[str] = mapped_column(
        Text, nullable=False, comment="正文模板，markdown + {{var}} 插值",
    )
    is_preset: Mapped[int] = mapped_column(
        Integer, default=1, comment="1=预设（不可删，可编辑） 0=自定义",
    )
    enabled: Mapped[int] = mapped_column(Integer, default=1, comment="1=启用 0=禁用")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(),
    )
