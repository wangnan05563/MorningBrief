"""SQLAlchemy ORM 模型层（V1.2：20 张表 = 12 业务 + 3 辅助 + 2 AI 服务 + 1 队列配置 + 2 用户互动）。

与 SQLite schema 的表一一对应：
- User          → user
- AdminUser     → admin_user
- Script        → script
- Material      → material
- AdMaterial    → ad_material
- AdPlacement   → ad_placement
- Channel       → channel
- Workflow      → workflow
- WorkflowStep  → workflow_step
- Review        → review
- Episode       → episode
- PlayLog       → play_log
- JwtBlacklist      → jwt_blacklist       （V1.2 新增）
- CrawlerDedup      → crawler_dedup       （V1.2 新增）
- PlayProgress      → play_progress       （V1.2 新增）
- AIConfig          → ai_config           （AI 服务模块新增）
- AIUsageLog        → ai_usage_log        （AI 服务模块新增）
- QueueConfig       → queue_config        （队列配置，单行表）
- Favorite          → favorite            （用户收藏）
- Feedback          → feedback            （用户反馈）

用法：
    from app.models import User, Episode, Script
"""
from app.models.user import User
from app.models.admin_user import AdminUser
from app.models.script import Script, ScriptStatus
from app.models.material import Material, MaterialStatus, MaterialSourceType
from app.models.ad_material import AdMaterial
from app.models.ad_placement import AdPlacement, AdPosition
# Channel 必须在 Workflow 之前导入：workflow.channel_id 外键引用 channel.id，
# 若 Channel 未注册到 Base.metadata，create_all 会抛 NoReferencedTableError
from app.models.channel import Channel
from app.models.workflow import (
    Workflow,
    WorkflowStep,
    WorkflowSource,
    WorkflowStatus,
    WorkflowStepName,
    WorkflowStepStatus,
)
from app.models.review import Review, ReviewStatus
from app.models.episode import Episode, EpisodeStatus
from app.models.play_log import PlayLog
# V1.2 新增辅助表
from app.models.jwt_blacklist import JwtBlacklist
from app.models.crawler_dedup import CrawlerDedup
from app.models.play_progress import PlayProgress
# AI 服务模块
from app.models.ai_config import AIConfig, AIUsageLog
# 队列配置（单行配置表，首次启动插入默认值）
from app.models.queue_config import QueueConfig
# 用户互动表（收藏与反馈）
from app.models.favorite import Favorite
from app.models.feedback import Feedback
# 任务8：评论与点赞
from app.models.comment import Comment, CommentLike
# V1.3 新增：订阅消息授权记录 + 频道订阅关系
from app.models.subscription import Subscription
from app.models.channel_subscription import ChannelSubscription
# 数据库维护与系统清理模块（V1.2 新增）
from app.models.audit_log import AuditLog
# 通知模块（钉钉消息通知，含模板与发送日志）
from app.models.notification_template import NotificationTemplate
from app.models.notification_log import NotificationLog
# 自动审批模块（配置表 + 统计表）
from app.models.auto_review_config import AutoReviewConfig
from app.models.auto_review_stat import AutoReviewStat

__all__ = [
    # 业务表
    "User",
    "AdminUser",
    "Script",
    "ScriptStatus",
    "Material",
    "MaterialStatus",
    "MaterialSourceType",
    "AdMaterial",
    "AdPlacement",
    "AdPosition",
    "Channel",
    "Workflow",
    "WorkflowStep",
    "WorkflowSource",
    "WorkflowStatus",
    "WorkflowStepName",
    "WorkflowStepStatus",
    "Review",
    "ReviewStatus",
    "Episode",
    "EpisodeStatus",
    "PlayLog",
    # V1.2 辅助表
    "JwtBlacklist",
    "CrawlerDedup",
    "PlayProgress",
    # AI 服务模块
    "AIConfig",
    "AIUsageLog",
    # 队列配置
    "QueueConfig",
    # 用户互动表
    "Favorite",
    "Feedback",
    # 任务8：评论与点赞
    "Comment",
    "CommentLike",
    # V1.3 订阅相关
    "Subscription",
    "ChannelSubscription",
    # 数据库维护与系统清理模块
    "AuditLog",
    # 通知模块
    "NotificationTemplate",
    "NotificationLog",
    # 自动审批模块
    "AutoReviewConfig",
    "AutoReviewStat",
]
