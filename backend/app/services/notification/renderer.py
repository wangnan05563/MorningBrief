"""模板渲染器：从 workflow_id 查询关联数据，构建变量上下文。

变量上下文是模板插值的数据源，包含工作流/频道/审核/音频等元信息。
查询失败时降级为空字符串，避免渲染中断影响通知发送。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.channel import Channel
from app.models.episode import Episode
from app.models.review import Review
from app.models.workflow import Workflow, WorkflowStep, WorkflowStepStatus
from app.services.notification.config_service import NotificationConfigService
from app.services.notification.template_service import render_template

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """模板渲染器：构建变量上下文 + 渲染标题/正文。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _build_base_url(self, config_svc: NotificationConfigService) -> str:
        """获取 admin-web base_url。

        优先级：配置项 notify_admin_base_url > 自动检测值（tunnel/localhost）。
        """
        configured = await config_svc.get_raw_value("notify_admin_base_url")
        if configured:
            return configured.rstrip("/")
        return config_svc._detect_base_url().rstrip("/")

    async def build_context(
        self,
        event_type: str,
        workflow_id: str,
        extra_vars: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建模板变量上下文。

        extra_vars 优先级最高（覆盖数据库查询值），用于传入失败步骤名等
        无法从数据库直接获取的临时信息。
        """
        config_svc = NotificationConfigService(self.db)
        base_url = await self._build_base_url(config_svc)

        ctx: dict[str, Any] = {
            "workflow_id": workflow_id,
            "episode_date": "",
            "channel_name": "",
            "audio_url": "",
            "review_url": "",
            "workflow_url": f"{base_url}/workflows/{workflow_id}",
            "steps_summary": "",
            "error_message": "",
            "duration_sec": "",
            "failed_step": "",
        }

        # 查询 workflow 关联数据
        try:
            result = await self.db.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )
            wf = result.scalar_one_or_none()
            if wf:
                ctx["episode_date"] = wf.episode_date.isoformat() if wf.episode_date else ""
                if wf.error:
                    ctx["error_message"] = wf.error
                if wf.channel_id:
                    ch_result = await self.db.execute(
                        select(Channel).where(Channel.id == wf.channel_id)
                    )
                    channel = ch_result.scalar_one_or_none()
                    if channel:
                        ctx["channel_name"] = channel.name
        except Exception as e:
            logger.warning("构建通知上下文查询 workflow 失败: %s", e)

        # 查询 Review（pending_review 事件需要 review_url/audio_url）
        try:
            review_result = await self.db.execute(
                select(Review).where(Review.workflow_id == workflow_id).order_by(Review.id.desc())
            )
            review = review_result.scalars().first()
            if review:
                ctx["review_url"] = f"{base_url}/review/{review.id}"
                ctx["audio_url"] = review.audio_url or ""
        except Exception as e:
            logger.warning("构建通知上下文查询 review 失败: %s", e)

        # 查询 Episode（duration_sec，published 事件需要）
        try:
            ep_result = await self.db.execute(
                select(Episode).where(Episode.workflow_id == workflow_id).order_by(Episode.id.desc())
            )
            episode = ep_result.scalars().first()
            if episode:
                ctx["duration_sec"] = str(episode.duration) if episode.duration else ""
        except Exception as e:
            logger.warning("构建通知上下文查询 episode 失败: %s", e)

        # extra_vars 覆盖（优先级最高）
        if extra_vars:
            ctx.update(extra_vars)

        return ctx

    async def render(
        self,
        title_template: str,
        body_template: str,
        context: dict[str, Any],
    ) -> tuple[str, str]:
        """渲染标题与正文模板。"""
        title = render_template(title_template, context)
        body = render_template(body_template, context)
        return title, body
