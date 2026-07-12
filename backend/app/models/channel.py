"""新闻频道模型。

Channel 作为工作流的分组标签，支持按内容分类频道独立产出节目。
轻量级设计：仅 id/name/description/is_active，不绑定爬虫源/TTS音色/LLM模型配置。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Channel(Base):
    __tablename__ = "channel"
    __table_args__ = (
        Index("idx_channel_active", "is_active"),
        {"comment": "新闻频道表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(256))
    # SQLite 用 0/1 存储布尔值，应用层按 int 解释
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # SQLite 不支持 ON UPDATE，updated_at 由 ChannelService.update_channel 显式维护
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
