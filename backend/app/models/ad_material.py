"""广告素材模型。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, String, Integer, SmallInteger, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class AdMaterial(Base):
    __tablename__ = "ad_material"
    __table_args__ = (
        Index("idx_default", "is_default"),
        {"comment": "广告素材表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(512))
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False, comment="时长（秒）")
    is_default: Mapped[Optional[int]] = mapped_column(
        SmallInteger, default=0, comment="是否默认自营占位素材"
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    # 反向关系：被投放规则引用
    placements: Mapped[list["AdPlacement"]] = relationship(
        "AdPlacement", back_populates="material"
    )
