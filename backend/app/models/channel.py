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
    # 频道级段间 BGM 模式："silence"=段间真实静音（默认）；"bridge"=段间 BGM 桥接（旧版）；
    # 为空(None)时回退到全局 settings.BGM_GAP_MODE
    bgm_gap_mode: Mapped[Optional[str]] = mapped_column(String(16), default=None)
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
    # 展示排序权重：值越小越靠前；相等时按 id 升序兜底。
    # 运营在频道管理后台调整此值即可控制小程序 tab 顺序，无需改动小程序（适配动态增删频道）。
    # 存量频道迁移时回填 0，保持原有按 id 的展示顺序。
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 频道级素材周期回溯天数：当日 pending 素材不足 SELECT_MIN_N 时，
    # 自动将选材时间范围放宽至最近 N 天内的素材（向上游扩展时间跨度获取更多素材，
    # 而非依赖 stitch 的 BGM/静音补足，从选材侧杜绝短节目场景）。
    # 为空(None)时，rewriter 回退到 _calc_dynamic_fallback_days 的动态值（按频道入库频率 3/7/14 天）。
    # 例如素材稀疏的频道可设为 14~30，避免单日素材不足导致工作流失败。
    material_lookback_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 选题策略（业务范围扩展 MVP）：heat=按热度（默认，存量兼容）/outline=按文档章节顺序/
    # manual=按手动指定素材 ID 列表。为空(None)时回退 heat。
    selection_strategy: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    # 是否投放广告：1=投放（默认，存量兼容）/0=不投放（课程/资料频道关广告）。
    # concat.py 据此跳过 AdService 调用，实现零广告。
    enable_ad: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    # manual 选题策略的素材 ID 列表（JSON 数组文本，如 "[12,13,14]"）。
    # 仅当 selection_strategy=manual 时读取，按列表顺序选题；为空则 manual 退化为空选。
    manual_material_ids: Mapped[Optional[str]] = mapped_column(Text, comment="manual 选题策略的素材 ID 列表（JSON 数组）")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # SQLite 不支持 ON UPDATE，updated_at 由 ChannelService.update_channel 显式维护
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
