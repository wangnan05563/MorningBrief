"""系统级键值标志表（移动端应急停服 / 维护态等复用）。

轻量 key-value 存储，避免为单一布尔标志新建专用表。
value 存 JSON 字符串（如维护态存 {"on":true,"reason":...,"by":...,"at":...}）。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class SystemFlag(Base):
    """系统标志键值表。"""

    __tablename__ = "system_flag"
    __table_args__ = ({"comment": "系统级键值标志表（维护态/特性开关等）"},)

    key: Mapped[str] = mapped_column(String(64), primary_key=True, comment="标志键")
    value: Mapped[Optional[str]] = mapped_column(
        Text, default=None, comment="JSON 字符串值"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[Optional[str]] = mapped_column(String(64), default=None)
