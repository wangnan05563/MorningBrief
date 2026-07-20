"""用户评论表模型（任务8）。

设计原因：
- Comment 存储用户对节目的评论，记录 user_id（openid 字符串，与 Favorite 对齐）
- CommentLike 记录点赞关系（user_id + comment_id 唯一），保证点赞/取消点赞幂等
- like_count 字段冗余存于 Comment 表，避免每次查询都做聚合 count
- 索引：episode_id（按节目列评论）、user_id（按用户列评论）
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Text, UniqueConstraint, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utcnow_naive
from app.database import Base


class Comment(Base):
    """节目评论（用户对节目的文字评论，含点赞计数）。"""
    __tablename__ = "comment"
    __table_args__ = (
        Index("idx_comment_episode", "episode_id"),
        Index("idx_comment_user", "user_id"),
        Index("idx_comment_created", "created_at"),
        {"comment": "用户评论表（任务8）"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 用 openid 字符串，与 Favorite 表保持一致，便于和 SCF 端 COS 路径对齐
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="用户 openid")
    user_name: Mapped[str] = mapped_column(String(64), nullable=False, default="匿名听众", comment="用户昵称")
    user_avatar: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="用户头像 URL")
    episode_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="节目 ID")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="评论内容")
    like_count: Mapped[int] = mapped_column(Integer, default=0, comment="点赞数")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=utcnow_naive, comment="评论时间"
    )


class CommentLike(Base):
    """评论点赞关系（保证点赞/取消点赞幂等）。"""
    __tablename__ = "comment_like"
    __table_args__ = (
        UniqueConstraint("user_id", "comment_id", name="uq_comment_like_user_comment"),
        Index("idx_comment_like_comment", "comment_id"),
        Index("idx_comment_like_user", "user_id"),
        {"comment": "评论点赞关系表（任务8）"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="用户 openid")
    comment_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="评论 ID")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=utcnow_naive, comment="点赞时间"
    )
