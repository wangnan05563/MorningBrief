"""新闻频道模型。

Channel 作为工作流的分组标签，支持按内容分类频道独立产出节目。
每个频道可独立配置定时触发时间与改写提示词，实现频道级个性化播报。
提示词字段为空时回退到 rewriter.py 中的默认值。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Channel(Base):
    __tablename__ = "channel"
    __table_args__ = (
        Index("idx_channel_active", "is_active"),
        {"comment": "新闻频道表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(256))
    # SQLite 用 0/1 存储布尔值，应用层按 int 解释
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    # 定时触发时间（HH:MM:SS 格式，如 "04:00:00"），为空则使用全局 cron 配置
    schedule_time: Mapped[Optional[str]] = mapped_column(String(8))
    # 频道级提示词：为空时 rewriter 回退到默认 INTRO_TEXT/OUTRO_TEXT/PROMPT_CONSTRAINT/rewrite.txt
    intro_prompt: Mapped[Optional[str]] = mapped_column(Text)
    outro_prompt: Mapped[Optional[str]] = mapped_column(Text)
    constraint_prompt: Mapped[Optional[str]] = mapped_column(Text)
    rewrite_template: Mapped[Optional[str]] = mapped_column(Text)
    # 频道级 BGM：相对路径（相对 data/bgm/），为空时 stitch 回退到全局 settings.BGM_PATH
    # 值形如 "preset/calm.mp3" 或 "custom/2_intro.mp3"，前端通过 /audio/bgm/{path} 试听
    bgm_path: Mapped[Optional[str]] = mapped_column(String(256))
    # BGM 音量覆盖（0.0-1.0）：为空时使用全局 settings.BGM_VOLUME
    bgm_volume: Mapped[Optional[float]] = mapped_column(default=None)
    # 频道级段间静音时长（秒）：为空时使用全局 settings.SEGMENT_GAP_SEC
    segment_gap_sec: Mapped[Optional[float]] = mapped_column(default=None)
    # 是否在每段新闻末尾追加思考问题（0=关闭，1=开启，None=开启默认行为） # NOSONAR
    enable_thinking_question: Mapped[Optional[int]] = mapped_column(default=None)
    # 频道专属 RSS 源列表（JSON 数组，存储 rss.yaml 中的 source name，如 ["人民网-国内"]）
    # 为空时 crawler 回退到全局所有源；非空时仅采集列表中的源，实现频道级数据源隔离
    rss_sources: Mapped[Optional[str]] = mapped_column(Text, comment="频道专属 RSS 源列表（JSON 数组）")
    # 频道关键词过滤（逗号分隔，如 "游戏,主机,PS5,Xbox,任天堂"）
    # crawler 入库前按关键词过滤标题/内容，为空表示不关键词过滤
    keywords: Mapped[Optional[str]] = mapped_column(Text, comment="频道关键词过滤（逗号分隔）")
    # 频道级最短时长（秒）：为空时使用全局 settings.TARGET_DURATION_SEC×0.80 作为下限
    # 冷门/小众频道素材稀疏时，可设置较短时长避免 padding 补足后仍不足下限的问题
    # 例如教育资讯可设为 300（下限 240s），体育速递可设为 360（下限 288s）
    min_duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # SQLite 不支持 ON UPDATE，updated_at 由 ChannelService.update_channel 显式维护
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
