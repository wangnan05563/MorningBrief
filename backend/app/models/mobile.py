"""移动端适配模块数据模型（SRS INT-M101~M105）。

与既有 20+ 张表同源（Base.metadata.create_all 自动建表，无需手写迁移）：
- AdminDevice：运营人员设备登记（推送 token、设备指纹），支撑消息推送与登录风控。
- AdminInbox：运营人员自身消息收件箱，区别于 notification_log（后者面向终端用户下发）。

索引命名沿用现有约定 idx_<table>_<col>（normalize_metadata_for_sqlite 会加 ix_ 前缀，幂等）。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AdminDevice(Base):
    """运营设备登记表：每台设备一条记录，支撑推送与风控。"""

    __tablename__ = "admin_device"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="关联 admin_user.id")
    # ios | android | wecom | dingtalk —— 推送通道不同，需区分
    platform: Mapped[str] = mapped_column(String(16), nullable=False, comment="ios|android|wecom|dingtalk")
    # 厂商/APNs/企业微信推送 token；Web 端可留空
    push_token: Mapped[Optional[str]] = mapped_column(String(512), comment="推送 token")
    # 设备指纹，用于新设备登录风控（INT-M103）
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), comment="设备指纹")
    bound_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_admin_device_admin", "admin_id"),
        Index("idx_admin_device_fp", "device_fingerprint"),
    )


class AdminInbox(Base):
    """运营消息收件箱：面向运营人员自身的通知（审批待办、系统告警、系统通知）。

    与 notification_log 的区别：notification_log 记录的是「系统发给终端用户」的下发，
    本表记录的是「系统发给运营人员」的消息，是移动端消息中心的真实数据源（INT-M101）。
    """

    __tablename__ = "admin_inbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="接收人 admin_user.id")
    # review | alert | system
    msg_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="review|alert|system")
    # info | warning | critical；critical 强制推送（FR-M404）
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info", comment="info|warning|critical")
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    # 深链目标 JSON：如 {"target":"review","id":123} → 移动端点击跳审批详情
    payload_json: Mapped[Optional[str]] = mapped_column(Text, comment="JSON：{target,id}")
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_admin_inbox_admin", "admin_id"),
        Index("idx_admin_inbox_unread", "admin_id", "read"),
    )
