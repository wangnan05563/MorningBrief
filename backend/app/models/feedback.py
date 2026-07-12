"""用户反馈表模型。

设计原因：
- C 端 SCF 云函数将反馈写入 COS 对象 feedbacks/{yyyymmdd}/{feedback_id}.json，
  与单机 exe 解耦（SCF 不访问 SQLite）
- 单机 exe 的 FeedbackSyncService 定时拉取 COS 对象写入此表后删除源对象，
  保证数据不重复（INSERT OR IGNORE + 删除 COS 源对象双重保障）
- id 直接复用 COS 对象名中的 feedback_id（uuid4 hex），无需自增主键
- user_id 用 String(64) 存放，兼容 SCF 端 int 类型 user_id（同步时转字符串）
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utcnow_naive
from app.database import Base


class Feedback(Base):
    """用户反馈（C 端走 COS 为主，此表为同步落地）。"""
    __tablename__ = "feedback"
    __table_args__ = (
        # 按 status + created_at 查询：后台列表筛选 + 时间倒序
        Index("ix_feedback_status_created", "status", "created_at"),
        {"comment": "用户反馈表（C 端走 COS 为主，此表为同步落地）"},
    )

    # 复用 COS 对象名中的 feedback_id（uuid4 hex），天然唯一，作为主键
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # SCF 端 user_id 为 int，同步时统一转字符串存储，便于跨端对齐
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="用户 ID")
    category: Mapped[str] = mapped_column(String(32), nullable=False, comment="反馈分类")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="反馈内容")
    contact: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="联系方式")
    # pending=待处理 / processed=处理中 / resolved=已解决
    status: Mapped[str] = mapped_column(String(16), default="pending", comment="处理状态")
    # 反馈创建时间（从 COS JSON 读取，SCF 端写入时已生成）
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="反馈创建时间")
    # 同步到 SQLite 的时间（用于排查同步延迟问题）
    synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=utcnow_naive, comment="同步入库时间"
    )
