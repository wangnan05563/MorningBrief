"""B 端运营模型。"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, String, SmallInteger, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AdminRole(str, Enum):
    admin = "admin"
    operator = "operator"


class AdminUser(Base):
    __tablename__ = "admin_user"
    __table_args__ = {"comment": "B 端运营表"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False, comment="bcrypt 加盐哈希")
    role: Mapped[AdminRole] = mapped_column(
        SAEnum(AdminRole), nullable=False, default=AdminRole.operator
    )
    nickname: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[Optional[int]] = mapped_column(SmallInteger, default=1, comment="1启用 0禁用")
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
