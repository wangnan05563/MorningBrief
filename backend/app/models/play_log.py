"""播放日志模型。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, SmallInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class PlayLog(Base):
    __tablename__ = "play_log"
    __table_args__ = (
        Index("idx_user_episode", "user_id", "episode_id"),
        Index("idx_played_at", "played_at"),
        Index("idx_episode", "episode_id"),
        {"comment": "播放日志表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"))
    episode_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("episode.id"), nullable=False
    )
    position: Mapped[Optional[int]] = mapped_column(
        Integer, default=0, comment="播放位置（秒）"
    )
    duration: Mapped[Optional[int]] = mapped_column(Integer, comment="本次会话已播放时长（秒）")
    completed: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0)
    played_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[Optional["User"]] = relationship("User")
    episode: Mapped["Episode"] = relationship("Episode", back_populates="play_logs")
