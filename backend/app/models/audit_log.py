"""审计日志模型（数据库维护与系统清理模块共用）。

设计原因：
- MorningBrief 原无通用事件表（17_xianyu 用 events 表），数据库维护的 DML 审计
  与系统清理的操作记录需要可查询的持久化存储，故新建本表
- 记录所有危险操作（删除/批量删除/导入/清理）的操作人、目标、结果，
  便于事后追溯误操作
- 查询频率低（仅审计页拉取），写入频率低（仅危险操作触发），SQLite 足够
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):
    """审计日志（数据库维护 + 系统清理模块的写操作记录）。"""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_log_category", "category"),
        Index("idx_audit_log_created", "created_at"),
        {"comment": "审计日志表（数据库维护与系统清理模块共用）"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 操作分类：db_admin | maintenance，便于按模块筛选
    category: Mapped[str] = mapped_column(String(32), nullable=False, comment="db_admin | maintenance")
    # 具体动作：create | update | delete | batch_delete | import | vacuum | cleanup
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    # 操作目标表名（数据库维护）或清理对象（系统清理）
    target: Mapped[Optional[str]] = mapped_column(String(64))
    # 操作人用户名（从 JWT 解析）
    operator: Mapped[Optional[str]] = mapped_column(String(64))
    # 操作详情 JSON 字符串（如级联影响、清理行数、导入统计等）
    detail: Mapped[Optional[str]] = mapped_column(Text, comment="JSON 字符串")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now()
    )
