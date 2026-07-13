"""新闻频道模型。

Channel 作为工作流的分组标签，支持按内容分类频道独立产出节目。
每个频道可独立配置定时触发时间与改写提示词，实现频道级个性化播报。
提示词字段为空时回退到 rewriter.py 中的默认值。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Index, Text
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
    # 定时触发时间（HH:MM:SS 格式，如 "04:00:00"），为空则使用全局 cron 配置
    schedule_time: Mapped[Optional[str]] = mapped_column(String(8))
    # 频道级提示词：为空时 rewriter 回退到默认 INTRO_TEXT/OUTRO_TEXT/PROMPT_CONSTRAINT/rewrite.txt
    intro_prompt: Mapped[Optional[str]] = mapped_column(Text)
    outro_prompt: Mapped[Optional[str]] = mapped_column(Text)
    constraint_prompt: Mapped[Optional[str]] = mapped_column(Text)
    rewrite_template: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # SQLite 不支持 ON UPDATE，updated_at 由 ChannelService.update_channel 显式维护
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
