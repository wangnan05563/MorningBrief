"""爬虫去重表模型（V1.2 新增，替代 Redis Set）。

设计原因：
- URL 精确去重：原 Redis Set sismember/sadd → SQLite 表查询/插入
- SimHash 近似去重：原 Redis Set sscan_iter → SQLite 表全量遍历 + 汉明距离比较
- TTL 清理：原 Redis EXPIRE → SQLite 按 created_at 定时清理（APScheduler）

规模：50-100 条/天，全表遍历性能可接受（无需 VP-Tree）。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class CrawlerDedup(Base):
    """爬虫去重记录（URL 精确去重 + SimHash 近似去重）。"""
    __tablename__ = "crawler_dedup"
    __table_args__ = (
        Index("idx_crawler_dedup_url", "url"),
        Index("idx_crawler_dedup_created", "created_at"),
        {"comment": "爬虫去重表（V1.2 新增，替代 Redis Set）"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False, comment="素材 URL（精确去重）")
    url_hash: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, comment="URL MD5 哈希（加速查询）"
    )
    simhash: Mapped[Optional[str]] = mapped_column(
        String(64), comment="标题 SimHash 指纹（近似去重）"
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
