"""用户收藏表模型。

设计原因：
- 与 play_progress 类似，C 端主路径走 COS 对象 favorites/{user_id}/index.json（云函数直写）
- 此表作为本地快照，便于后台统计与异地容灾
- user_id 使用 String(64) 存放 openid，与 SCF 端 COS 路径保持一致
- UniqueConstraint 保证每用户对每节目仅收藏一次
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utcnow_naive
from app.database import Base


class Favorite(Base):
    """用户收藏（每用户每节目仅一条记录）。"""
    __tablename__ = "favorite"
    __table_args__ = (
        UniqueConstraint("user_id", "episode_id", name="uq_favorite_user_episode"),
        Index("idx_favorite_user", "user_id"),
        Index("idx_favorite_episode", "episode_id"),
        {"comment": "用户收藏表（C 端走 COS 为主，此表为本地快照）"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 用 openid 字符串，便于和 SCF 端 COS 路径 favorites/{user_id}/index.json 对齐
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="用户 openid")
    episode_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="节目 ID")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=utcnow_naive, comment="收藏时间"
    )
