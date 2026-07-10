"""邮件通知渠道（SMTP）。

通过 SMTP 发送告警邮件，适合需要存档的运维告警。
支持 TLS/SSL 加密连接。
"""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

from loguru import logger

from app.services.notifier.base import INotifier, NotificationEvent, NotifyResult
from app.services.notifier.registry import registry


@registry.register("email")
class EmailNotifier(INotifier):
    """SMTP 邮件通知器。

    凭证来自 Settings：
    - ALERT_EMAIL_SMTP_HOST: SMTP 服务器地址
    - ALERT_EMAIL_SMTP_PORT: 端口（587 TLS / 465 SSL）
    - ALERT_EMAIL_SMTP_USER: 发件人账号
    - ALERT_EMAIL_SMTP_PASSWORD: 发件人密码
    - ALERT_EMAIL_TO: 收件人（逗号分隔多个）
    """

    def __init__(self, settings: Any = None) -> None:
        if settings is None:
            from app.config import get_settings
            settings = get_settings()
        self._smtp_host: str = getattr(settings, "ALERT_EMAIL_SMTP_HOST", "")
        self._smtp_port: int = getattr(settings, "ALERT_EMAIL_SMTP_PORT", 587)
        self._smtp_user: str = getattr(settings, "ALERT_EMAIL_SMTP_USER", "")
        self._smtp_password: str = getattr(settings, "ALERT_EMAIL_SMTP_PASSWORD", "")
        self._from_addr: str = self._smtp_user
        self._to_addrs: str = getattr(settings, "ALERT_EMAIL_TO", "")

    @property
    def name(self) -> str:
        return "email"

    def is_configured(self) -> bool:
        return all([
            self._smtp_host,
            self._smtp_user,
            self._smtp_password,
            self._to_addrs,
        ])

    async def send(self, event: NotificationEvent) -> NotifyResult:
        if not self.is_configured():
            return NotifyResult(
                channel=self.name,
                success=False,
                error="SMTP 配置不完整",
            )

        # 构建邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{event.severity.upper()}] {event.title}"
        msg["From"] = self._from_addr
        msg["To"] = self._to_addrs

        # 纯文本正文（简洁，适合运维快速扫描）
        body = (
            f"来源: {event.source or '系统'}\n"
            f"级别: {event.severity}\n"
            f"时间: {event.extra.get('timestamp', '') if event.extra else ''}\n\n"
            f"{event.message}\n"
        )
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # SMTP 发送（同步操作，用 asyncio.to_thread 包装避免阻塞事件循环）
        import asyncio
        try:
            await asyncio.to_thread(self._smtp_send, msg.as_string())
        except Exception as e:
            logger.exception("邮件发送失败")
            return NotifyResult(
                channel=self.name,
                success=False,
                error=str(e),
            )
        return NotifyResult(channel=self.name, success=True)

    def _smtp_send(self, message_str: str) -> None:
        """同步 SMTP 发送（在 to_thread 中调用）。

        根据端口自动选择 TLS/SSL：
        - 465: SSL 直连
        - 587/25: STARTTLS（先明文再升级）
        """
        recipients = [addr.strip() for addr in self._to_addrs.split(",") if addr.strip()]

        if self._smtp_port == 465:
            # SSL 直连
            with smtplib.SMTP_SSL(
                self._smtp_host, self._smtp_port, timeout=15
            ) as server:
                server.login(self._smtp_user, self._smtp_password)
                server.sendmail(self._from_addr, recipients, message_str)
        else:
            # STARTTLS（端口 587/25）
            with smtplib.SMTP(
                self._smtp_host, self._smtp_port, timeout=15
            ) as server:
                server.starttls()
                server.login(self._smtp_user, self._smtp_password)
                server.sendmail(self._from_addr, recipients, message_str)
