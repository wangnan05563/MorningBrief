"""讲书稿素材池（T00656）。

设计要点：
- **引用而非拷贝**：池项通过 `material_id` 引用素材库书籍，素材库自身数据不受影响；
  同时冗余 title/author/category/cover_url 快照字段，便于列表展示与素材被删除后仍可读；
- **排序即取书顺序**：`sort_index` 升序即讲书稿模式的取书顺序（持久化，重启不丢）；
- **池项与频道绑定**：同一本书可在多个频道的池中独立排序（`channel_id + sort_index` 联合索引）。

进度字段（cursor / last_run_date / interval_days / loop）落在 `channel` 表上，
因为它们描述的是"该频道讲书稿模式的调度状态"，与频道生命周期一致（见 T00656）。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BookPoolItem(Base):
    """讲书稿素材池条目（一书一条，按 sort_index 升序取用）。"""

    __tablename__ = "book_pool_item"
    __table_args__ = (
        # 取书/排序都按 (channel_id, sort_index) 访问，联合索引覆盖
        Index("idx_book_pool_channel_sort", "channel_id", "sort_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channel.id", ondelete="CASCADE"), nullable=False,
        comment="所属频道（讲书稿模式的取书范围）",
    )
    material_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="代表章节的 material.id（该书任一章节，仅作展示引用）",
    )
    book_key: Mapped[str] = mapped_column(
        String(256), nullable=False, default="",
        comment="书籍聚合键＝素材 source（书名）。取书时按它聚合全书章节；池项以'书'为单位",
    )
    # 快照字段：素材改名/删除后列表仍可展示，避免联表与悬空引用
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="书名（快照）")
    author: Mapped[str | None] = mapped_column(String(128), comment="作者（快照）")
    category: Mapped[str | None] = mapped_column(String(64), comment="分类（快照）")
    cover_url: Mapped[str | None] = mapped_column(String(512), comment="封面（快照）")
    sort_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="池内排序（升序即取书顺序）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="入池时间",
    )
