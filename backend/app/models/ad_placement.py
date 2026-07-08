"""广告投放规则模型。"""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class AdPosition(str, Enum):
    head = "head"
    mid = "mid"
    tail = "tail"


class AdPlacement(Base):
    __tablename__ = "ad_placement"
    __table_args__ = (
        Index("idx_date_range", "start_date", "end_date"),
        Index("idx_position", "position"),
        {"comment": "广告投放规则表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ad_material.id"), nullable=False
    )
    position: Mapped[AdPosition] = mapped_column(SAEnum(AdPosition), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    material: Mapped["AdMaterial"] = relationship(
        "AdMaterial", back_populates="placements"
    )
