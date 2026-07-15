"""通知模块（钉钉消息通知）。

职责：
1. 工作流事件 → 渲染模板 → NotifierHub 发送 → 记日志
2. 配置开关管理（复用 ai_config key-value 表）
3. 模板 CRUD（独立 notification_template 表）
4. 发送日志审计与重发

与现有 notifier/（渠道层）的关系：
- notifier/ 负责"如何发送"（HTTP 调用、加签、渠道适配）
- notification/ 负责"发什么、何时发、发给谁"（事件编排、模板渲染、开关控制）
"""
from app.services.notification.sender import NotificationSender, get_notification_sender

__all__ = [
    "NotificationSender",
    "get_notification_sender",
]
