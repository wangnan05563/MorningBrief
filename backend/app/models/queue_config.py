"""队列配置模型（单行配置表）。

存储全局执行模式（串行/并行）与最大并发数。
单行约束：应用层保证仅 id=1 一行，首次启动时插入默认配置。

默认值统一通过类常量引用，避免多处硬编码导致不一致。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class QueueConfig(Base):
    __tablename__ = "queue_config"
    __table_args__ = (
        {"comment": "队列配置表（单行）"},
    )

    # 默认配置常量：所有创建 QueueConfig 的位置统一引用，避免硬编码不一致
    # 首次启动默认串行单并发：安全可预测，用户可通过 UI 切换为并行多并发
    DEFAULT_EXECUTION_MODE: str = "serial"
    DEFAULT_MAX_CONCURRENT: int = 1

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # serial: 串行模式（max_concurrent 强制为 1）
    # parallel: 并行模式（max_concurrent 可配置 1-5）
    execution_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DEFAULT_EXECUTION_MODE,
    )
    max_concurrent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_MAX_CONCURRENT,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
