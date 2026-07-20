"""爬取素材模型。"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MaterialSourceType(str, Enum):
    rss = "rss"
    list = "list"


class MaterialStatus(str, Enum):
    pending = "pending"
    selected = "selected"
    skipped = "skipped"


class Material(Base):
    __tablename__ = "material"
    __table_args__ = (
        Index("idx_crawled_at", "crawled_at"),
        Index("idx_workflow", "workflow_id"),
        Index("idx_category", "category"),
        Index("idx_simhash", "simhash"),
        Index("idx_material_channel", "channel_id"),
        CheckConstraint("source_type IN ('rss', 'list')", name="ck_material_source_type"),
        CheckConstraint("status IN ('pending', 'selected', 'skipped')", name="ck_material_status"),
        {"comment": "爬取素材表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, comment="来源名称")
    source_type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="正文全文")
    summary: Mapped[Optional[str]] = mapped_column(String(512), comment="摘要（前200字）")
    url: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, comment="原始 URL（去重）")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    category: Mapped[Optional[str]] = mapped_column(String(32), comment="品类")
    status: Mapped[Optional[str]] = mapped_column(
        String(16), default=MaterialStatus.pending.value
    )
    simhash: Mapped[Optional[str]] = mapped_column(String(64), comment="标题指纹（SimHash 去重）")
    workflow_id: Mapped[Optional[str]] = mapped_column(String(64))
    # 素材归属频道 ID：crawler 入库时按采集频道写入，rewriter 选题时按频道过滤
    # 为空表示历史遗留数据（未关联频道），rewriter 回退到全局素材池
    channel_id: Mapped[Optional[int]] = mapped_column(Integer, comment="素材归属频道 ID")
    # 封面图 URL：article_parser 从 og:image 提取，小程序文稿页按段展示
    # 仅存原站 URL 不下载，避免爬虫耗时与存储成本；原站删图时小程序自然降级为纯文本
    cover_url: Mapped[Optional[str]] = mapped_column(String(512), comment="封面图 URL（og:image）")
