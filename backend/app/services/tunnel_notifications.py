"""内网穿透启动通知：桥接同步隧道生命周期与异步 NotifierHub。

设计决策：
- 隧道启动成功时发送 TUNNEL_STARTED 通知，severity=critical 穿透免打扰
- 自启动失败时发送 SYSTEM_ERROR 通知，确保用户必定获知失败原因
- 在子线程中用 asyncio.run 桥接异步 NotifierHub.send()，不阻塞 API 或自启动线程

移植自 17_xianyu 的 tunnel_notifications.py，
适配 MorningBrief 的 NotifierHub + NotificationEvent 架构。
"""
from __future__ import annotations

import asyncio
import logging
import threading

from app.services.notifier.base import NotificationEvent
from app.services.notifier.hub import get_notifier_hub

logger = logging.getLogger(__name__)

_PROVIDER_LABELS = {
    "cloudflare": "Cloudflare Tunnel",
    "cpolar": "cpolar",
    "tailscale": "Tailscale Funnel",
}


def _send_tunnel_started_notification(
    provider_name: str,
    public_url: str,
    local_port: int,
) -> None:
    """在线程内调用异步 NotifierHub，向所有已启用渠道发送启动通知。"""
    provider_label = _PROVIDER_LABELS.get(provider_name, provider_name)
    event = NotificationEvent(
        title="内网穿透隧道已启动",
        message=(
            f"{provider_label} 隧道已建立\n"
            f"公网地址：{public_url}\n"
            f"本地端口：{local_port}\n"
            f"点击地址即可远程访问管理后台"
        ),
        severity="critical",  # 穿透免打扰，确保用户及时获知
        source="tunnel_service",
        extra={
            "provider": provider_name,
            "provider_label": provider_label,
            "public_url": public_url,
            "local_port": local_port,
            "action_url": public_url,
        },
    )
    try:
        hub = get_notifier_hub()
        asyncio.run(hub.send(event))
    except Exception:
        logger.exception("发送内网穿透启动通知失败")


def notify_tunnel_started(
    provider_name: str,
    public_url: str,
    local_port: int,
) -> None:
    """异步调度启动通知，不阻塞 API 或开机自启动线程。"""
    threading.Thread(
        target=_send_tunnel_started_notification,
        args=(provider_name, public_url, local_port),
        daemon=True,
        name="tunnel-start-notification",
    ).start()


def _do_send_autostart_failed(error_message: str) -> None:
    """实际执行通知发送（在子线程中调用 asyncio.run 桥接异步 NotifierHub）。"""
    event = NotificationEvent(
        title="内网穿透自启动失败",
        message=(
            f"隧道自动启动失败，远程访问暂不可用\n"
            f"错误信息：{error_message}\n"
            f"请登录管理后台手动启动隧道或检查配置"
        ),
        severity="critical",  # 穿透免打扰，确保用户及时获知
        source="tunnel_service",
        extra={
            "error": error_message,
            "stage": "tunnel_autostart",
        },
    )
    try:
        hub = get_notifier_hub()
        asyncio.run(hub.send(event))
    except Exception:
        logger.exception("发送内网穿透自启动失败通知时出错")


def notify_autostart_failed(error_message: str) -> None:
    """自启动失败时发送通知，复用子线程 + asyncio.run 模式。

    用 severity=critical 穿透免打扰，
    确保用户不看日志也能通过通知渠道获知自启动失败原因。
    """
    threading.Thread(
        target=_do_send_autostart_failed,
        args=(error_message,),
        daemon=True,
        name="tunnel-autostart-fail-notify",
    ).start()
