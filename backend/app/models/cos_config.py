"""云端 COS 配置模型（V1.5 新增）。

与 AIConfig 同构的 key-value 表：前端「云端配置」页填写的腾讯云 COS 凭证
（SecretId / SecretKey / Region / Bucket / CDN 域名）落库后，启动时覆盖
Settings 单例，使工作流上传/代理等模块无需重启即可读取最新配置；同时支持
前端热更新与脱敏返显。

设计为 key-value 而非单行 JSON：便于按项更新，避免并发写冲突，且与
ai_config 表保持一致的运维心智。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class CosConfig(Base):
    """云端 COS 配置表（key-value 结构）。

    与 Settings 类桥接：启动时从本表加载覆盖 Settings 单例，
    前端修改时同步更新 SQLite + Settings 单例，实现配置热更新。
    SecretId / SecretKey 类配置项存储明文（SQLite 文件级安全），GET 接口返回脱敏值。
    """

    __tablename__ = "cos_config"
    __table_args__ = (
        {"comment": "云端 COS 配置表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, comment="配置项名"
    )
    config_value: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="配置值"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
