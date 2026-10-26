"""系统清理后台任务模型（T02799 / FR-UX-702）。

为什么需要一张表，而不是只放进程内字典：
- 部署支持 `UVICORN_WORKERS>1`（backend/launcher.py），提交与轮询可能落在不同进程；
  进程内状态会让「刚提交完就 404」，任务进度不可信；
- 页面刷新或换 worker 后仍要能查到同一个任务；
- 同一目标重复提交要靠数据库唯一约束合并（见 active_key），进程内锁只在单进程成立。

active_key 是「排队中/执行中」的去重键（如 `database:vacuum`），任务结束即置空。
SQLite 的唯一索引允许多个 NULL，因此已完成任务不会互相冲突。
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MaintenanceTaskState(str, Enum):
    """任务状态（前端展示文案在 src/constants/enums.js 的 MAINTENANCE_TASK_STATE）。"""

    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class MaintenanceTask(Base):
    """系统清理的长任务记录（提交 → 执行 → 结果/错误）。"""

    __tablename__ = "maintenance_task"
    __table_args__ = (
        Index("idx_maintenance_task_state", "state"),
        Index("idx_maintenance_task_created", "created_at"),
        # 唯一：同一 active_key 只允许一条活跃任务；结束后置 NULL 让位给下一次
        Index("uq_maintenance_task_active_key", "active_key", unique=True),
        {"comment": "系统清理后台任务表（T02799）"},
    )

    # 任务 ID：uuid4().hex，直接给前端轮询用
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # 端点分类：database | logs | cache | workflow_chain（决定调用哪个 service 方法）
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    # 清理目标（未按天数的 workflow_chain 存工作流 ID）
    target: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # 执行中标记：`database:vacuum` / `workflow_chain:<id>`；完成的记录置 NULL
    active_key: Mapped[Optional[str]] = mapped_column(String(128))
    # queued | running | succeeded | failed
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    admin_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # 原始请求参数（days 等），JSON 字符串；便于复现「按几天清的」
    params: Mapped[Optional[str]] = mapped_column(Text, comment="JSON 字符串")
    # 成功时的清理结果（cleaned/errors/total_deleted 等），JSON 字符串
    result: Mapped[Optional[str]] = mapped_column(Text, comment="JSON 字符串")
    error: Mapped[Optional[str]] = mapped_column(Text)
    elapsed_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
