"""通知发送日志模型。

记录每条通知的实际发送结果（success/failed/failed_capped/suppressed），
含渲染时使用的 payload（JSON 字符串，多渠道发送时带 channels 逐渠道结果），
便于审计与失败重发。
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import Index, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class NotificationDeliveryStatus(str, Enum):
    """通知投递结果（T02702 / FR-UX-405）。

    值集是前端 `enums.js` 的 `NOTIFICATION_DELIVERY_STATUS` 字典与后端的唯一对账来源：
    此前取值只写在列注释里，前端同一组文案在一份文件里写了三遍且门禁无从校验。
    枚举值字符串保持不变，存量数据无需迁移。
    """

    success = "success"
    failed = "failed"
    failed_capped = "failed_capped"
    suppressed = "suppressed"


class NotificationLog(Base):
    """通知发送日志表。

    status 四态（见 NotificationDeliveryStatus）：
    - success：实际发送且钉钉返回 errcode=0
    - failed：发送失败或钉钉返回错误
    - failed_capped：同日发送失败达上限后停写重试标记（停摆告警收敛，T02030）
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
        String(16), nullable=False,
        comment=" | ".join(s.value for s in NotificationDeliveryStatus),
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
