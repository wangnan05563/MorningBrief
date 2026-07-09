"""播放进度表模型（V1.2 新增）。

设计原因：
- C 端主路径：播放进度写 COS 对象 play_progress/{user_id}/{episode_id}.json（云函数直写）
- B 端备用：APScheduler 定时从 COS 拉取进度聚合到 play_log 表后，此表作为本地快照
- 与 play_log 表的区别：
  - play_log：播放日志（统计用，每条记录一次播放会话）
  - play_progress：播放进度（断点续播用，每用户每节目仅一条记录）
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class PlayProgress(Base):
    """播放进度（断点续播，每用户每节目仅一条记录）。"""
    __tablename__ = "play_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "episode_id", name="uk_user_episode"),
        Index("idx_play_progress_user", "user_id"),
        {"comment": "播放进度表（V1.2 新增，C 端走 COS 为主，此表为单机端备用）"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="用户 ID")
    episode_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="节目 ID")
    position: Mapped[int] = mapped_column(Integer, default=0, comment="播放位置（秒）")
    duration: Mapped[int] = mapped_column(Integer, default=0, comment="节目总时长（秒）")
    completed: Mapped[int] = mapped_column(Integer, default=0, comment="是否完播 0/1")
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
