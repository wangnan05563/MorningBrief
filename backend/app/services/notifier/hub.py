"""通知器 Hub - 多渠道聚合分发（对标 17_xianyu notifier/hub.py）。

职责：
1. 启动时扫描已注册渠道，过滤未配置凭证的渠道
2. fan-out 并发发送到所有已配置渠道（asyncio.gather）
3. 免打扰时段判定：critical 仍可达，其他静默（计入 suppressed_count）

与 17_xianyu 的差异：
- 不订阅 EventBus（20_News 的 EventBus 是可选的，Hub 提供直接 send 方法）
- 免打扰逻辑简化为时间区间判定，跨午夜场景用 minutes_since_midnight
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.config import get_settings
from app.services.notifier.base import INotifier, NotificationEvent, NotifyResult
from app.services.notifier.registry import registry

# 导入渠道实现触发 @registry.register 装饰器注册
# 必须在 Hub 使用前完成导入，否则 registry 为空
from app.services.notifier.channels import wecom, dingtalk, email  # noqa: F401


class NotifierHub:
    """多渠道通知聚合器。

    启动时从配置加载已配置的渠道实例，运行时 fan-out 并发发送。
    免打扰时段内非 critical 事件静默（计入 suppressed_count）。
    """

    def __init__(self) -> None:
        self._channels: list[INotifier] = []
        self._initialized = False
        # 免打扰时段（24h 制，如 22:00-08:00）
        self._quiet_start_hour: int = 22
        self._quiet_end_hour: int = 8

    def _init_channels(self) -> None:
        """从配置加载已配置凭证的渠道实例。

        幂等设计：多次调用只初始化一次，配置变更后需重启或手动调 reload。
        """
        if self._initialized:
            return
        self._initialized = True

        settings = get_settings()
        # 遍历注册表中的所有渠道，实例化已配置凭证的
        for name in registry.list_channels():
            try:
                instance = registry.create(name, settings=settings)
                if instance.is_configured():
                    self._channels.append(instance)
                    logger.info("通知渠道已加载: %s", name)
                else:
                    logger.debug("通知渠道未配置凭证，跳过: %s", name)
            except Exception:
                logger.exception("加载通知渠道 %s 失败", name)

        if not self._channels:
            logger.warning("无已配置的通知渠道，告警将无法发送")

    def reload(self) -> None:
        """重新加载渠道配置（配置热更新后调用）。"""
        self._channels.clear()
        self._initialized = False
        self._init_channels()

    async def send(self, event: NotificationEvent) -> dict[str, Any]:
        """向所有已配置渠道发送通知。

        Returns:
            {"total": N, "success": N, "failed": N, "suppressed": N,
             "results": [NotifyResult, ...]}

        免打扰时段内非 critical 事件静默，不发送但计入 suppressed。
        """
        self._init_channels()

        result: dict[str, Any] = {
            "total": len(self._channels),
            "success": 0,
            "failed": 0,
            "suppressed": 0,
            "results": [],
        }

        if not self._channels:
            logger.warning("无可用通知渠道，事件未发送: %s", event.title)
            return result

        # 免打扰判定：critical 穿透，其他在 quiet_hours 内静默
        if event.severity != "critical" and self._is_quiet_hours():
            logger.info(
                "免打扰时段，事件已静默: %s (severity=%s)",
                event.title, event.severity,
            )
            result["suppressed"] = len(self._channels)
            return result

        # fan-out 并发发送到所有渠道
        tasks = [ch.send(event) for ch in self._channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for ch, res in zip(self._channels, results):
            if isinstance(res, Exception):
                logger.error(
                    "通知渠道 %s 发送异常: %s", ch.name, res,
                    exc_info=res,
                )
                result["failed"] += 1
                result["results"].append(
                    NotifyResult(channel=ch.name, success=False, error=str(res))
                )
            elif res.success:
                result["success"] += 1
                result["results"].append(res)
            else:
                result["failed"] += 1
                result["results"].append(res)

        logger.info(
            "通知发送完成: total=%d success=%d failed=%d",
            result["total"], result["success"], result["failed"],
        )
        return result

    def _is_quiet_hours(self) -> bool:
        """判断当前是否在免打扰时段。

        支持跨午夜：如 22:00-08:00，当前时间 23:00 返回 True。
        用 UTC 时间避免时区问题（运维告警通常 UTC 对齐）。
        """
        now = datetime.now(timezone.utc)
        hour = now.hour
        if self._quiet_start_hour <= self._quiet_end_hour:
            # 同日区间（如 09:00-18:00）
            return self._quiet_start_hour <= hour < self._quiet_end_hour
        else:
            # 跨午夜区间（如 22:00-08:00）
            return hour >= self._quiet_start_hour or hour < self._quiet_end_hour


# 全局单例
_hub: NotifierHub | None = None


def get_notifier_hub() -> NotifierHub:
    """获取 NotifierHub 单例。

    首次调用时延迟初始化渠道，避免模块加载时读配置。
    """
    global _hub
    if _hub is None:
        _hub = NotifierHub()
    return _hub
