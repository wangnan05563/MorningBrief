"""自动审批配置模型（单行配置表）。

设计原因：
- 复用 QueueConfig 的单行配置表模式，应用层保证仅 id=1 一行
- 运行时可切换 enabled 状态，无需重启服务
- 配置项变更需记录操作人与时间，便于追溯
- 规则字段使用 JSON 存储，便于扩展新条件而无需迁移 schema
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AutoReviewConfig(Base):
    """自动审批配置（单行表，id 固定为 1）。"""

    __tablename__ = "auto_review_config"
    __table_args__ = (
        {"comment": "自动审批配置表（单行，id=1）"},
    )

    # 默认值常量：首次启动 seed 时引用，避免硬编码不一致
    # 默认关闭：开启需管理员显式启用，避免误开导致未审核内容直接发布
    DEFAULT_ENABLED: bool = False
    # 默认要求内容安全检测通过：微信 msgSecCheck 通过是自动审批的最低安全底线
    DEFAULT_REQUIRE_CONTENT_SAFE: bool = True
    # 默认要求所有步骤一次成功：避免重试过的内容自动通过（重试可能掩盖上游不稳定）
    DEFAULT_REQUIRE_STEPS_FIRST_SUCCESS: bool = True
    # 默认关键词白名单为空：空表示不启用关键词匹配
    DEFAULT_KEYWORD_WHITELIST: str = "[]"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 总开关：False 时所有自动审批逻辑跳过
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=DEFAULT_ENABLED,
    )
    # 规则 1：要求 rewrite 步骤的微信内容安全检测为 safe
    require_content_safe: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=DEFAULT_REQUIRE_CONTENT_SAFE,
    )
    # 规则 2：要求工作流前 4 步全部一次成功（无重试）
    require_steps_first_success: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=DEFAULT_REQUIRE_STEPS_FIRST_SUCCESS,
    )
    # 规则 3：稿件需命中预设关键词白名单（JSON 数组，空数组表示不启用此规则）
    keyword_whitelist: Mapped[str] = mapped_column(
        Text, nullable=False, default=DEFAULT_KEYWORD_WHITELIST,
        comment="JSON 数组，空数组表示不启用关键词白名单规则",
    )
    # 配置变更追溯：记录最后修改人与时间
    updated_by: Mapped[Optional[str]] = mapped_column(String(64))
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(),
    )
