"""爬取素材模型。"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MaterialSourceType(str, Enum):
    # rss：通用资讯 RSS 爬取（news 频道）
    rss = "rss"
    # list：手动录入 / 文档上传，无真实 URL，用 content_hash 去重
    list = "list"
    # book_rss：书籍 RSS 预制源（仅 audiobook 频道），条目即书/章
    book_rss = "book_rss"
    # cos：从云端对象存储（COS）导入的对象，按 key 取回后解析
    cos = "cos"
    # api：通过 API / 网页 URL 拉取并解析的内容（含第三方接口、文章页）
    api = "api"
    # qrcode：二维码 / 链接分享进入的手动录入门户（来源标记为 qrcode）
    qrcode = "qrcode"


class MaterialStatus(str, Enum):
    pending = "pending"
    selected = "selected"
    skipped = "skipped"


class MaterialMediaType(str, Enum):
    # 文本素材（默认，语音链路唯一消费类型）；image/video 为多媒体素材（仅管理/预览）
    text = "text"
    image = "image"
    video = "video"


class Material(Base):
    __tablename__ = "material"
    __table_args__ = (
        Index("idx_crawled_at", "crawled_at"),
        Index("idx_workflow", "workflow_id"),
        Index("idx_category", "category"),
        Index("idx_simhash", "simhash"),
        Index("idx_material_channel", "channel_id"),
        # 注意：source_type 不再加 CHECK 约束。
        # 早期仅 rss/list 两值并加了 ck_material_source_type 约束，扩展 book_rss/cos/api/qrcode
        # 后约束会拒绝新值。启动期迁移 _migrate_material_source_type_constraint 会删除旧约束，
        # 新库由 create_all 直接不带该约束；枚举取值的合法性统一在应用层校验（materials 路由）。
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
    # T00766：文章全量图片（JSON 数组文本，按正文出现顺序、封面在前）
    # 供小程序详情页轮播；NULL/[] 表示无图，前端回退 segments 封面
    images_json: Mapped[Optional[str]] = mapped_column(Text, comment="文章全量图片 URL JSON 数组（T00766）")
    # T00716：多媒体素材扩展——类型 + 媒体 URL + 缩略图 URL。
    # 默认 text（既有文本素材 media_url 为空），image/video 均由管理/录入页手动写入，
    # 语音链路（crawler→rewriter→tts）仅消费 text 素材，媒体素材不进语音生成。
    media_type: Mapped[str] = mapped_column(
        String(16), default=MaterialMediaType.text.value, nullable=False,
    )
    media_url: Mapped[Optional[str]] = mapped_column(String(1024), comment="媒体资源 URL（图片/视频）")
    media_thumb_url: Mapped[Optional[str]] = mapped_column(String(1024), comment="媒体缩略图 URL")
    # 去重键（MVP 输入适配器）：list 类型素材（手动录入/文档上传）无真实 URL，
    # 用正文 content_hash 作为去重键；rss 类型可空（沿用 url 唯一约束）。
    # 唯一性判定：list/cos 类型按 (source_type, channel_id, dedup_key) 频道级查重（T01521），
    # rss 类型按 url 查重（全局）。
    dedup_key: Mapped[Optional[str]] = mapped_column(
        String(64), comment="去重键：list 类型存 content_hash，rss 类型为空"
    )
