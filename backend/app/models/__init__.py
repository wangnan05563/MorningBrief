"""SQLAlchemy ORM 模型层（V1.2：14 张表 = 11 业务 + 3 辅助）。

与 SQLite schema 的 14 张表一一对应：
- User          → user
- AdminUser     → admin_user
- Script        → script
- Material      → material
- AdMaterial    → ad_material
- AdPlacement   → ad_placement
- Workflow      → workflow
- WorkflowStep  → workflow_step
- Review        → review
- Episode       → episode
- PlayLog       → play_log
- JwtBlacklist      → jwt_blacklist       （V1.2 新增）
- CrawlerDedup      → crawler_dedup       （V1.2 新增）
- PlayProgress      → play_progress       （V1.2 新增）

用法：
    from app.models import User, Episode, Script
"""
from app.models.user import User
from app.models.admin_user import AdminUser
from app.models.script import Script, ScriptStatus
from app.models.material import Material, MaterialStatus, MaterialSourceType
from app.models.ad_material import AdMaterial
from app.models.ad_placement import AdPlacement, AdPosition
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
]
