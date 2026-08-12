"""C 端用户模型。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "user"
    __table_args__ = (
        Index("idx_openid", "openid"),
        {"comment": "C 端用户表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    unionid: Mapped[Optional[str]] = mapped_column(String(64))
    nickname: Mapped[Optional[str]] = mapped_column(String(64))
    avatar: Mapped[Optional[str]] = mapped_column(String(512))
    total_listen_duration: Mapped[Optional[int]] = mapped_column(Integer, default=0, comment="累计收听时长（秒）")
    total_listen_count: Mapped[Optional[int]] = mapped_column(Integer, default=0, comment="累计收听期数")
    # 运营端可禁用终端用户（M5 FR-M502）；0=正常，1=禁用
    disabled: Mapped[int] = mapped_column(Integer, default=0, comment="禁用状态：0=正常，1=禁用")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
