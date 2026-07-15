"""通知模板服务：模板 CRUD + 变量插值渲染。

变量插值使用简单的 {{var}} → str(value) 替换，缺失变量降级为空字符串，
避免模板中引用不存在的变量导致 KeyError 中断发送流程。
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_template import NotificationTemplate

# 预设模板：lifespan 启动时若表为空则插入这 3 条
PRESET_TEMPLATES: list[dict] = [
    {
        "event_type": "workflow.pending_review",
        "name": "待审核通知",
        "title_template": "📋 待审核 - {{workflow_id}}",
        "body_template": (
            "# 📋 新闻待审核\n\n"
            "**工作流：** `{{workflow_id}}`\n\n"
            "**节目日期：** {{episode_date}}\n\n"
            "**频道：** {{channel_name}}\n\n"
            "**时长：** <font color=\"#1890FF\">{{duration_sec}}秒</font>\n\n"
            "> 音频已合成完成，等待管理员审核发布\n\n"
            "🔗 [在线试听]({{review_url}})"
        ),
        "is_preset": 1,
        "enabled": 1,
    },
    {
        "event_type": "workflow.failed",
        "name": "失败通知",
        "title_template": "🔴 工作流失败 - {{workflow_id}}",
        "body_template": (
            "# 🔴 工作流执行失败\n\n"
            "**工作流：** `{{workflow_id}}`\n\n"
            "**失败步骤：** <font color=\"#F5222D\">{{failed_step}}</font>\n\n"
            "**错误：** {{error_message}}\n\n"
            "> 已自动重试 3 次，请人工介入排查"
        ),
        "is_preset": 1,
        "enabled": 1,
    },
    {
        "event_type": "workflow.published",
        "name": "已发布通知",
        "title_template": "🚀 节目已发布 - {{workflow_id}}",
        "body_template": (
            "# 🚀 节目已发布\n\n"
            "**工作流：** `{{workflow_id}}`\n\n"
            "**节目日期：** {{episode_date}}\n\n"
            "**频道：** {{channel_name}}\n\n"
            "> 审核通过，节目已发布上线"
        ),
        "is_preset": 1,
        "enabled": 1,
    },
]

# 变量插值正则：匹配 {{ var_name }} 或 {{var_name}}（允许任意空白）
_VAR_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_template(template: str, variables: dict) -> str:
    """渲染模板：将 {{var}} 替换为变量值，缺失变量替换为空字符串。

    简单字符串替换而非 Jinja2，因为通知模板只需变量插值，
    不需要条件/循环等复杂逻辑，引入 Jinja2 会增加不必要的依赖与安全面。
    """
    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        value = variables.get(var_name, "")
        return str(value) if value is not None else ""

    return _VAR_PATTERN.sub(_replace, template)


def extract_variables(template: str) -> list[str]:
    """提取模板中引用的所有变量名（用于前端展示可用变量列表）。"""
    return list(set(_VAR_PATTERN.findall(template)))


class TemplateService:
    """通知模板 CRUD 服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_templates(self) -> list[NotificationTemplate]:
        """获取所有模板（按 event_type 排序）。"""
        result = await self.db.execute(
            select(NotificationTemplate).order_by(NotificationTemplate.event_type)
        )
        return list(result.scalars().all())

    async def get_template(self, event_type: str) -> Optional[NotificationTemplate]:
        """按事件类型获取启用的模板。"""
        result = await self.db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.event_type == event_type,
                NotificationTemplate.enabled == 1,
            )
        )
        return result.scalar_one_or_none()

    async def get_template_by_id(self, template_id: int) -> Optional[NotificationTemplate]:
        """按 ID 获取模板。"""
        result = await self.db.execute(
            select(NotificationTemplate).where(NotificationTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def update_template(
        self, template_id: int, data: dict
    ) -> Optional[NotificationTemplate]:
        """更新模板（仅允许修改 name/title_template/body_template/enabled）。

        event_type 与 is_preset 不可修改，避免破坏预设模板的事件映射。
        """
        tpl = await self.get_template_by_id(template_id)
        if tpl is None:
            return None

        for field in ("name", "title_template", "body_template"):
            if field in data:
                setattr(tpl, field, data[field])
        if "enabled" in data:
            tpl.enabled = 1 if data["enabled"] else 0

        await self.db.commit()
        await self.db.refresh(tpl)
        return tpl

    async def seed_preset_templates(self) -> int:
        """启动时初始化预设模板（幂等：已存在的 event_type 跳过）。

        在 main.py lifespan 中调用，确保首次启动有可用模板。
        """
        inserted = 0
        for preset in PRESET_TEMPLATES:
            existing = await self.db.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.event_type == preset["event_type"]
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            self.db.add(NotificationTemplate(**preset))
            inserted += 1
        if inserted > 0:
            await self.db.commit()
        return inserted
