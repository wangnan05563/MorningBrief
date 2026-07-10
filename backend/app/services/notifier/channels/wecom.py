"""企业微信 Webhook 通知渠道。

通过群机器人 Webhook 发送 Markdown 消息，适合运维告警群。
"""
from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from app.services.notifier.base import INotifier, NotificationEvent, NotifyResult
from app.services.notifier.registry import registry


@registry.register("wecom")
class WeComNotifier(INotifier):
    """企业微信 Webhook 通知器。

    凭证来自 Settings.ALERT_WECOM_WEBHOOK。
    """

    def __init__(self, settings: Any = None) -> None:
        if settings is None:
            from app.config import get_settings
            settings = get_settings()
        self._webhook: str = getattr(settings, "ALERT_WECOM_WEBHOOK", "")

    @property
    def name(self) -> str:
        return "wecom"

    def is_configured(self) -> bool:
        # 占位符值视为未配置（避免误判空字符串为已配置）
        return bool(self._webhook) and "example.com" not in self._webhook

    async def send(self, event: NotificationEvent) -> NotifyResult:
        if not self.is_configured():
            return NotifyResult(
                channel=self.name,
                success=False,
                error="Webhook 未配置",
            )

        # 企微 Markdown 格式：severity 用颜色标识
        severity_emoji = {
            "critical": "🔴",
            "important": "🟡",
            "info": "🔵",
        }.get(event.severity, "ℹ️")

        markdown = (
            f"### {severity_emoji} {event.title}\n\n"
            f"> **来源**: {event.source or '系统'}\n"
            f"> **级别**: {event.severity}\n\n"
            f"{event.message}"
        )
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": markdown},
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._webhook, json=payload)
        except httpx.TimeoutException:
            return NotifyResult(
                channel=self.name, success=False, error="请求超时"
            )
        except httpx.RequestError as e:
            return NotifyResult(
                channel=self.name, success=False, error=f"网络错误: {e}"
            )

        if resp.status_code == 200:
            data = resp.json()
            if data.get("errcode") == 0:
                return NotifyResult(channel=self.name, success=True)
            return NotifyResult(
                channel=self.name,
                success=False,
                error=f"企微返回错误: {data.get('errmsg')}",
            )
        return NotifyResult(
            channel=self.name,
            success=False,
            error=f"HTTP {resp.status_code}: {resp.text[:200]}",
        )
