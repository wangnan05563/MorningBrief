"""通知器抽象基类与结果模型（对标 17_xianyu notifier/base.py）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class NotifyResult:
    """单次通知结果。

    success=False 时 error 字段记录失败原因，便于 Hub 统计失败率。
    """
    channel: str       # 渠道名（如 "wecom"）
    success: bool       # 是否发送成功
    error: str = ""     # 失败原因（success=False 时填写）


@dataclass
class NotificationEvent:
    """通知事件（对标 17_xianyu domain.events.Event 的通知子集）。

    severity 决定是否穿透免打扰：critical 在 quiet_hours 内仍发送。
    """
    title: str                          # 标题
    message: str                        # 正文
    severity: str = "info"             # critical / important / info
    source: str = ""                    # 来源（如 "workflow_scheduler"）
    extra: dict[str, Any] = None        # 附加数据（如 workflow_id）

    def __post_init__(self) -> None:
        if self.extra is None:
            self.extra = {}


class INotifier(ABC):
    """通知器接口。

    所有渠道（wecom/dingtalk/email）实现此接口，
    NotifierHub 通过统一接口 fan-out 分发。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """渠道名（注册表 key，如 "wecom"）。"""
        ...

    @abstractmethod
    async def send(self, event: NotificationEvent) -> NotifyResult:
        """发送通知。返回 NotifyResult，异常不应向外抛出（Hub 统一捕获）。"""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """检查渠道是否已配置凭证。

        Hub 启动时过滤未配置的渠道，避免每次事件都触发 ERROR 日志。
        """
        ...
