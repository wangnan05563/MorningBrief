"""按 ai_config 表里的用户配置构造可用通知渠道（T02138 口径统一）。

为什么单独成模块：判定「渠道配没配好」此前有三份各自为政的写法——
- `NotifierHub._init_channels()` 走 `Settings` + `is_configured()`（T02030 已修）
- 管理端 `NotificationSender` 收集渠道时走 ai_config + 裸 truthiness
- 移动端运营告警 `mobile_service._dispatch_admin_alert()` 又抄了一遍裸 truthiness

后两份只看「字段非空」，占位符文本照样被收进渠道，发送时死在 httpx 里伪装成网络错误。
统一到这里后，三条路径共用同一套 `is_configured()` 形态校验与同一份跳过原因。
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from loguru import logger

from app.services.notifier.base import INotifier
from app.services.notifier.channels.dingtalk import DingTalkNotifier
from app.services.notifier.channels.email import EmailNotifier
from app.services.notifier.channels.wecom import WeComNotifier

ALL_CHANNELS = ("dingtalk", "wecom", "email")


async def build_configured_channels(
    config_svc: Any,
    *,
    names: tuple[str, ...] = ALL_CHANNELS,
) -> tuple[list[tuple[str, INotifier]], list[dict[str, str]]]:
    """从 ai_config 读凭证，返回 (可用渠道 [(name, notifier)], 跳过项 [{"channel","reason"}])。

    config_svc 需提供 `get_raw_value(key)`（NotificationConfigService）。
    """
    raw = {
        "notify_dingtalk_webhook": await config_svc.get_raw_value("notify_dingtalk_webhook"),
        "notify_dingtalk_secret": await config_svc.get_raw_value("notify_dingtalk_secret"),
        "notify_wecom_webhook": await config_svc.get_raw_value("notify_wecom_webhook"),
        "notify_email_smtp_host": await config_svc.get_raw_value("notify_email_smtp_host"),
        "notify_email_smtp_user": await config_svc.get_raw_value("notify_email_smtp_user"),
        "notify_email_smtp_password": await config_svc.get_raw_value("notify_email_smtp_password"),
        "notify_email_smtp_port": await config_svc.get_raw_value("notify_email_smtp_port"),
        "notify_email_to": await config_svc.get_raw_value("notify_email_to"),
    }
    try:
        email_port = int(raw["notify_email_smtp_port"]) if raw["notify_email_smtp_port"] else 587
    except ValueError:
        email_port = 587

    built = {
        "dingtalk": DingTalkNotifier(settings=SimpleNamespace(
            ALERT_DINGTALK_WEBHOOK=raw["notify_dingtalk_webhook"] or "",
            ALERT_DINGTALK_SECRET=raw["notify_dingtalk_secret"] or "",
        )),
        "wecom": WeComNotifier(settings=SimpleNamespace(
            ALERT_WECOM_WEBHOOK=raw["notify_wecom_webhook"] or "",
        )),
        "email": EmailNotifier(settings=SimpleNamespace(
            ALERT_EMAIL_SMTP_HOST=raw["notify_email_smtp_host"] or "",
            ALERT_EMAIL_SMTP_PORT=email_port,
            ALERT_EMAIL_SMTP_USER=raw["notify_email_smtp_user"] or "",
            ALERT_EMAIL_SMTP_PASSWORD=raw["notify_email_smtp_password"] or "",
            ALERT_EMAIL_TO=raw["notify_email_to"] or "",
        )),
    }

    channels: list[tuple[str, INotifier]] = []
    skipped: list[dict[str, str]] = []
    for name in names:
        notifier = built[name]
        if notifier.is_configured():
            channels.append((name, notifier))
        else:
            reason = notifier.configuration_error() or "未配置凭证"
            skipped.append({"channel": name, "reason": reason})
            logger.info("通知渠道 {} 未配置凭证，跳过: {}", name, reason)
    return channels, skipped


def format_skipped(skipped: list[dict[str, str]]) -> str:
    """跳过原因拼成一句人话（空列表返回空串）。"""
    return "; ".join(f"{s['channel']}: {s['reason']}" for s in skipped)
