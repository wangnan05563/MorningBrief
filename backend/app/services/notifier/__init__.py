"""通知器模块（对标 17_xianyu modules/notifier/）。

注册表 + 工厂模式：
- NotifierRegistry：字典映射 name→class，create(name, **kwargs) 工厂方法
- INotifier：抽象基类，定义 send(event) → NotifyResult 接口
- NotifierHub：多渠道聚合器，fan-out 并发发送到所有已配置渠道

支持的渠道：wecom（企微）/ dingtalk（钉钉）/ email（邮件）
新增渠道只需实现 INotifier 并在 registry 注册，无需改动 Hub。

与 17_xianyu 的差异：
- 去掉闲鱼专有渠道（serverchan/pushplus/bark/ntfy/telegram/webhook）
- 新增 email 渠道（SMTP），适配新闻系统运维告警场景
- 保留 quiet_hours 免打扰（critical 仍可达）
"""
from app.services.notifier.base import INotifier, NotifyResult
from app.services.notifier.hub import NotifierHub, get_notifier_hub
from app.services.notifier.registry import NotifierRegistry, registry

__all__ = [
    "INotifier",
    "NotifyResult",
    "NotifierRegistry",
    "registry",
    "NotifierHub",
    "get_notifier_hub",
]
