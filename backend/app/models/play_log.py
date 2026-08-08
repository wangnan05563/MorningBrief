"""播放日志模型。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, SmallInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlayLog(Base):
    __tablename__ = "play_log"
    __table_args__ = (
        Index("idx_user_episode", "user_id", "episode_id"),
        Index("idx_played_at", "played_at"),
        Index("idx_episode", "episode_id"),
        # /recent 查询为 WHERE user_id=? ORDER BY played_at DESC，
        # 单列 idx_played_at 无法高效支持带用户过滤的排序，
        # 复合索引 (user_id, played_at) 可直接定位用户并按时间倒序扫描
        Index("idx_user_played_at", "user_id", "played_at"),
        {"comment": "播放日志表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user.id"))
    episode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("episode.id"), nullable=False
    )
    position: Mapped[Optional[int]] = mapped_column(
        Integer, default=0, comment="播放位置（秒）"
    )
    duration: Mapped[Optional[int]] = mapped_column(Integer, comment="本次会话已播放时长（秒）")
    completed: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0)
    # played_at 必须由业务代码显式赋值 localnow_naive()（本地 naive datetime），
    # 禁止用 server_default=func.now()：SQLite func.now() 返回 UTC，
    # 与 stats_service 用 datetime.combine(target_date) 本地时间切分窗口冲突，
    # 会导致凌晨 0-8 点数据查不到（R162/R170 时区一致性）
    played_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped[Optional["User"]] = relationship("User")
    episode: Mapped["Episode"] = relationship("Episode", back_populates="play_logs")
