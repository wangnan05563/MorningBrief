"""通知器抽象基类、结果模型与凭证形态校验（对标 17_xianyu notifier/base.py）。

凭证校验放在这里而不是各渠道内联：T02030 实测——`is_configured()` 只排除
`example.com` 一种形态，模板占位文本被判「已配置」，渠道被 Hub 加载后每次
发送都死在 httpx（缺 scheme），失败原因伪装成网络错误而非「没配好」。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

# 模板/示例文本里常见的标记（小写比对）
_PLACEHOLDER_TOKENS = (
    "<", ">", "请填写", "请输入", "填入", "placeholder", "changeme",
    "your-", "your_", "todo",
)


def placeholder_error(value: str) -> str:
    """空值或模板占位文本 → 返回原因；可用值返回空串。"""
    v = (value or "").strip()
    if not v:
        return "空值"
    low = v.lower()
    hit = next((tok for tok in _PLACEHOLDER_TOKENS if tok in low), None)
    if hit:
        return f"疑似模板占位符（含「{hit}」）"
    return ""


def webhook_error(value: str) -> str:
    """Webhook URL 形态校验：必须 http(s) + 可解析主机名 + 非占位。

    返回 "" 表示形态合法；否则返回不通过原因（进日志与 NotifyResult.error）。
    """
    reason = placeholder_error(value)
    if reason:
        return reason
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in ("http", "https"):
        return f"不是 http(s) URL（scheme={parts.scheme or '空'}）"
    if not parts.hostname:
        return "URL 解析不出主机名"
    host = parts.hostname.lower()
    if host == "example.com" or host.endswith(".example.com"):
        return "示例域名占位（example.com）"
    return ""


def host_field_error(value: str) -> str:
    """SMTP / 主机名类字段校验：非占位、不带协议前缀、无空白。"""
    reason = placeholder_error(value)
    if reason:
        return reason
    v = value.strip()
    if "://" in v:
        return "主机名不应带协议前缀"
    if any(c.isspace() for c in v):
        return "主机名含空白字符"
    return ""


def email_field_error(value: str) -> str:
    """邮箱/收件人字段校验：非占位且含 @。"""
    reason = placeholder_error(value)
    if reason:
        return reason
    if "@" not in value:
        return "不是邮箱地址（缺 @）"
    return ""


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

    def configuration_error(self) -> str:
        """未配置的原因（供 Hub 日志与排查）。

        已配置时返回空串；未配置时区分「没填」和「填了但形态不对」。
        """
        return ""
