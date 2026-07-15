"""钉钉 Webhook 通知渠道。

支持两种消息格式：
1. actionCard：extra 含 action_url 时使用，含单按钮跳转（工作流审核/详情）
2. markdown：无 action_url 时降级使用（测试通知、系统告警）

加签验证：配置 ALERT_DINGTALK_SECRET 时自动计算 HmacSHA256 签名。
"""
from __future__ import annotations

import hashlib
import hmac
import base64
import time
import urllib.parse
from typing import Any

import httpx
from loguru import logger

from app.services.notifier.base import INotifier, NotificationEvent, NotifyResult
from app.services.notifier.registry import registry


@registry.register("dingtalk")
class DingTalkNotifier(INotifier):
    """钉钉 Webhook 通知器。

    凭证来自 Settings.ALERT_DINGTALK_WEBHOOK 和可选的 ALERT_DINGTALK_SECRET。
    """

    def __init__(self, settings: Any = None) -> None:
        if settings is None:
            from app.config import get_settings
            settings = get_settings()
        self._webhook: str = getattr(settings, "ALERT_DINGTALK_WEBHOOK", "")
        self._secret: str = getattr(settings, "ALERT_DINGTALK_SECRET", "")

    @property
    def name(self) -> str:
        return "dingtalk"

    def is_configured(self) -> bool:
        return bool(self._webhook) and "example.com" not in self._webhook

    def _sign_url(self) -> str:
        """计算加签 URL（配置了 SECRET 时）。

        钉钉加签算法：HmacSHA256(timestamp + "\\n" + secret) → base64 → urlencode
        """
        if not self._secret:
            return self._webhook

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            self._secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        sign_encoded = urllib.parse.quote_plus(sign)
        separator = "&" if "?" in self._webhook else "?"
        return f"{self._webhook}{separator}timestamp={timestamp}&sign={sign_encoded}"

    def _build_payload(self, event: NotificationEvent) -> dict:
        """构建钉钉消息 payload。

        actionCard 模式：extra 含 action_url 时使用单按钮卡片，提升交互体验。
        markdown 模式：无 action_url 时降级（测试通知、系统告警等场景）。
        """
        # 钉钉 PC 端卡片标题宽度限制，截断到 24 字符避免显示不全
        title = event.title[:24] if len(event.title) > 24 else event.title

        action_url = (event.extra or {}).get("action_url", "")
        action_title = (event.extra or {}).get("action_title", "") or "查看详情"

        if action_url:
            return {
                "msgtype": "actionCard",
                "actionCard": {
                    "title": title,
                    "text": event.message,
                    "singleTitle": action_title,
                    "singleURL": action_url,
                },
            }

        # 降级为 markdown：保留 severity 标识便于运维快速识别级别
        severity_emoji = {
            "critical": "🔴",
            "important": "🟡",
            "info": "🔵",
        }.get(event.severity, "ℹ️")

        markdown = (
            f"### {severity_emoji} {event.title}\n\n"
            f"**来源**: {event.source or '系统'}\n\n"
            f"**级别**: {event.severity}\n\n"
            f"{event.message}"
        )
        return {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": markdown},
        }

    async def send(self, event: NotificationEvent) -> NotifyResult:
        if not self.is_configured():
            return NotifyResult(
                channel=self.name,
                success=False,
                error="Webhook 未配置",
            )

        payload = self._build_payload(event)

        url = self._sign_url()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
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
                error=f"钉钉返回错误: {data.get('errmsg')}",
            )
        return NotifyResult(
            channel=self.name,
            success=False,
            error=f"HTTP {resp.status_code}: {resp.text[:200]}",
        )
