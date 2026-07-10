"""AI 服务配置与用量模型。

两张表：
- ai_config：key-value 结构存储 LLM/TTS 配置，支持前端动态修改
- ai_usage_log：记录每次 AI 调用的 token/字符消耗，用于用量统计

设计为 key-value 而非单行 JSON：便于按项更新，避免并发写冲突。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Float, Index, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AIConfig(Base):
    """AI 配置表（key-value 结构）。

    与 Settings 类桥接：启动时从本表加载覆盖 Settings 单例，
    前端修改时同步更新 SQLite + Settings 单例，实现配置热更新。
    API Key 类配置项存储明文（SQLite 文件级安全），GET 接口返回脱敏值。
    """

    __tablename__ = "ai_config"
    __table_args__ = (
        {"comment": "AI 服务配置表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, comment="配置项名"
    )
    config_value: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="配置值"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AIUsageLog(Base):
    """AI 用量日志表（记录每次 LLM/TTS 调用）。

    LLM 记录 input/output tokens，TTS 记录合成字符数，
    费用按模型定价表估算（USD），用于前端用量仪表盘。
    """

    __tablename__ = "ai_usage_log"
    __table_args__ = (
        Index("idx_ai_usage_created", "created_at"),
        Index("idx_ai_usage_service", "service_type"),
        {"comment": "AI 用量日志表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="服务类型: llm | tts"
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="TTS 合成字符数"
    )
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
