"""JWT 黑名单模型（V1.2 新增）。

设计原因：
- B 端（单机 exe）登出时写此表，本地验签快速查询
- C 端（云函数 SCF）登出时写 COS 对象 jwt_blacklist/{jti}.json，SCF 共享读取
- 双写策略：登出时同时写 SQLite（B 端用）+ COS（C 端用），保证两端都能识别黑名单

与原 Redis 黑名单的差异：
- Redis 用 TTL 自动过期；SQLite 需定时清理（APScheduler _cleanup_expired_blacklist）
- 查询频率低（仅 jti 命中时拒绝），SQLite 索引查询性能足够
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class JwtBlacklist(Base):
    """JWT 登出黑名单（B 端本地存储，C 端走 COS 共享）。"""
    __tablename__ = "jwt_blacklist"
    __table_args__ = (
        Index("idx_jwt_blacklist_jti", "jti"),
        Index("idx_jwt_blacklist_expires_at", "expires_at"),
        {"comment": "JWT 登出黑名单表（V1.2 新增）"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="JWT 唯一标识")
    token_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="user | admin"
    )
    user_id: Mapped[Optional[int]] = mapped_column(Integer, comment="关联用户 ID（admin 为空）")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="JWT 原始过期时间")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
