"""订阅消息记录表模型。

设计原因：
- 微信订阅消息为一次性授权机制：每次用户点击授权仅允许推送一条模板消息
- 此表记录每次授权与推送状态，工作流发布成功后查询 used=0 的记录进行推送
- user_id 使用 int（与 User.id 对齐），便于跨表联查统计
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import localnow_naive
from app.database import Base


class Subscription(Base):
    """用户订阅消息授权记录（一次授权对应一次推送）。"""
    __tablename__ = "subscription"
    __table_args__ = (
        # 同一用户同一模板可多次授权（每次授权一条），故不加 UNIQUE 约束
        Index("idx_subscription_user_template", "user_id", "template_id"),
        Index("idx_subscription_used", "used"),
        {"comment": "订阅消息授权记录表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 关联 User.id（C 端用户主键），与 user_service 中 subject=user.id 对齐
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="用户 ID")
    # 微信订阅消息模板 ID，由微信公众平台配置
    template_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="模板 ID")
    # 用户的 openid，推送时直接使用，避免再联表查询
    openid: Mapped[str] = mapped_column(String(64), nullable=False, comment="用户 openid")
    subscribed_at: Mapped[datetime] = mapped_column(
        DateTime, default=localnow_naive, comment="用户授权时间"
    )
    # 0=未推送（待发送），1=已推送（已消费） # NOSONAR
    used: Mapped[int] = mapped_column(Integer, default=0, comment="是否已推送：0=未推送 1=已推送")
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="实际推送时间")
