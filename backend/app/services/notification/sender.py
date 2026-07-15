"""通知发送编排器：检查开关 → 频次去重 → 渲染 → NotifierHub 发送 → 记日志。

设计要点：
1. 开关检查：全局开关关闭或场景开关关闭时记 suppressed 日志，不发送
2. 频次去重：同 event_type+workflow_id 5 分钟内已发送则跳过（避免连续失败刷屏）
3. 渲染失败降级：模板渲染异常时使用最小化文本发送，确保通知不丢失
4. 发送异常降级：NotifierHub 异常时记 failed 日志，不向上抛出
"""
from __future__ import annotations

import logging
import time
from typing import Any

from cachetools import TTLCache
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.notification_template import NotificationTemplate
from app.services.notification.config_service import NotificationConfigService
from app.services.notification.log_service import LogService
from app.services.notification.renderer import TemplateRenderer
from app.services.notification.template_service import TemplateService, render_template
from app.services.notifier import get_notifier_hub, NotificationEvent

logger = logging.getLogger(__name__)

# 频次去重缓存：key = (event_type, workflow_id)，TTL 5 分钟
# 模块级单例，跨请求共享，避免短期内重复发送
_dedup_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)

# 事件类型 → actionCard 按钮配置（action_title/action_url_key）
# action_url_key 指向 context 中的 URL 字段，决定按钮跳转目标
_EVENT_ACTION_MAP: dict[str, dict[str, str]] = {
    "workflow.pending_review": {
        "action_title": "前往审核",
        "action_url_key": "review_url",
    },
    "workflow.failed": {
        "action_title": "查看详情",
        "action_url_key": "workflow_url",
    },
    "workflow.published": {
        "action_title": "查看详情",
        "action_url_key": "workflow_url",
    },
}


class NotificationSender:
    """通知发送编排器。

    每次发送都创建独立 session（AsyncSessionLocal），
    避免长事务跨请求持有连接，与 workflow_scheduler 的模式一致。
    """

    async def send_workflow_event(
        self,
        event_type: str,
        workflow_id: str,
        extra_vars: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """工作流事件通知编排入口。

        返回 {status, message} 供调用方判断结果。
        任何异常都不向上抛出（通知失败不应中断工作流主流程）。
        """
        try:
            return await self._send_safe(event_type, workflow_id, extra_vars)
        except Exception as e:
            logger.exception("通知发送异常 event_type=%s workflow_id=%s: %s",
                             event_type, workflow_id, e)
            return {"status": "failed", "message": str(e)}

    async def _send_safe(
        self,
        event_type: str,
        workflow_id: str,
        extra_vars: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """实际发送逻辑（异常向上抛出由 send_workflow_event 统一捕获）。"""
        async with AsyncSessionLocal() as session:
            config_svc = NotificationConfigService(session)
            log_svc = LogService(session)

            # 1. 检查开关
            if not await config_svc.is_scene_enabled(event_type):
                await log_svc.create_log(
                    event_type=event_type,
                    channel="dingtalk",
                    title=f"[suppressed] {event_type}",
                    status="suppressed",
                    error="场景开关关闭或全局开关关闭",
                    payload={"workflow_id": workflow_id, **(extra_vars or {})},
                    workflow_id=workflow_id,
                )
                return {"status": "suppressed", "message": "通知开关关闭"}

            # 2. 频次去重
            dedup_key = (event_type, workflow_id)
            if dedup_key in _dedup_cache:
                await log_svc.create_log(
                    event_type=event_type,
                    channel="dingtalk",
                    title=f"[deduped] {event_type}",
                    status="suppressed",
                    error="5 分钟内已发送，频次去重",
                    payload={"workflow_id": workflow_id, **(extra_vars or {})},
                    workflow_id=workflow_id,
                )
                return {"status": "suppressed", "message": "频次去重"}

            # 3. 加载模板（含自愈：模板缺失时自动 seed 预设模板后重试）
            tpl_svc = TemplateService(session)
            template = await tpl_svc.get_template(event_type)
            if template is None:
                # 自愈：可能是服务在 seed 代码添加前启动，DB 中无模板
                # 尝试 seed 预设模板后再查一次
                try:
                    seeded = await tpl_svc.seed_preset_templates()
                    if seeded > 0:
                        logger.info("[notification] 自愈 seed 预设模板 %d 条", seeded)
                        template = await tpl_svc.get_template(event_type)
                except Exception as e:
                    logger.warning("[notification] 自愈 seed 模板失败: %s", e)
            if template is None:
                await log_svc.create_log(
                    event_type=event_type,
                    channel="dingtalk",
                    title=f"[no_template] {event_type}",
                    status="failed",
                    error=f"未找到 event_type={event_type} 的启用模板",
                    payload={"workflow_id": workflow_id, **(extra_vars or {})},
                    workflow_id=workflow_id,
                )
                return {"status": "failed", "message": "未找到启用模板"}

            # 4. 构建变量上下文
            renderer = TemplateRenderer(session)
            context = await renderer.build_context(event_type, workflow_id, extra_vars)

            # 5. 渲染模板
            title, body = await renderer.render(
                template.title_template, template.body_template, context,
            )

            # 6. 构建 NotificationEvent（含 actionCard 按钮配置）
            action_config = _EVENT_ACTION_MAP.get(event_type, {})
            action_url = ""
            if action_config:
                action_url = context.get(action_config["action_url_key"], "")
            extra = {
                "event_type": event_type,
                "workflow_id": workflow_id,
                "action_url": action_url,
                "action_title": action_config.get("action_title", ""),
                "audio_url": context.get("audio_url", ""),
            }
            event = NotificationEvent(
                title=title,
                message=body,
                severity="critical",  # 工作流事件穿透免打扰
                source="notification_sender",
                extra=extra,
            )

            # 7. 发送：直接从 ai_config 表读取最新凭证创建 DingTalkNotifier
            # 不依赖 NotifierHub 单例（避免服务启动时 webhook 为空导致渠道未加载、
            # 以及 hub.reload 热更新链路在长时间运行后的状态不一致问题）
            from types import SimpleNamespace
            from app.services.notifier.channels.dingtalk import DingTalkNotifier
            webhook = await config_svc.get_raw_value("notify_dingtalk_webhook")
            secret = await config_svc.get_raw_value("notify_dingtalk_secret")
            if not webhook:
                await log_svc.create_log(
                    event_type=event_type,
                    channel="dingtalk",
                    title=title,
                    status="failed",
                    error="未配置钉钉 Webhook 地址，请在通知管理页配置",
                    payload={"workflow_id": workflow_id, **(extra_vars or {})},
                    workflow_id=workflow_id,
                )
                return {"status": "failed", "message": "未配置钉钉 Webhook"}

            notifier = DingTalkNotifier(settings=SimpleNamespace(
                ALERT_DINGTALK_WEBHOOK=webhook,
                ALERT_DINGTALK_SECRET=secret,
            ))
            notify_result = await notifier.send(event)

            # 8. 记日志
            if notify_result.success:
                status = "success"
                error_msg = ""
                _dedup_cache[dedup_key] = time.time()
            else:
                status = "failed"
                error_msg = notify_result.error or "发送失败"

            await log_svc.create_log(
                event_type=event_type,
                channel="dingtalk",
                title=title,
                status=status,
                error=error_msg,
                payload=context,
                workflow_id=workflow_id,
            )

            return {
                "status": status,
                "message": error_msg or "发送成功",
                "success": success_count,
                "failed": failed_count,
            }

    async def send_test(self) -> dict[str, Any]:
        """发送测试通知（供前端"测试发送"按钮调用）。

        不走开关检查与频次去重，直接发送一条测试消息。
        直接从 ai_config 表读取最新 webhook/secret，临时创建 DingTalkNotifier
        发送，不依赖 hub 单例的热更新（避免 settings 属性修改链路的不确定性）。
        """
        async with AsyncSessionLocal() as session:
            log_svc = LogService(session)

            # 从 ai_config 表读取用户配置的 webhook/secret（最新值）
            config_svc = NotificationConfigService(session)
            webhook = await config_svc.get_raw_value("notify_dingtalk_webhook")
            secret = await config_svc.get_raw_value("notify_dingtalk_secret")

            if not webhook:
                return {
                    "success": False,
                    "message": "发送失败: 未配置钉钉 Webhook 地址，请先填写并保存配置",
                    "results": [],
                }

            # 临时创建 DingTalkNotifier 实例，直接用 ai_config 表中的凭证
            # 绕过 hub 单例和 settings 热更新，确保读到用户最新配置
            from types import SimpleNamespace
            from app.services.notifier.channels.dingtalk import DingTalkNotifier
            test_settings = SimpleNamespace(
                ALERT_DINGTALK_WEBHOOK=webhook,
                ALERT_DINGTALK_SECRET=secret,
            )
            notifier = DingTalkNotifier(settings=test_settings)

            event = NotificationEvent(
                title="🔔 通知测试",
                message=(
                    "# 🔔 通知测试\n\n"
                    "这是一条来自 MorningBrief 的测试通知。\n\n"
                    "如果您收到此消息，说明钉钉 Webhook 配置正确。"
                ),
                severity="info",
                source="notification_test",
                extra={"action_url": "", "action_title": "", "audio_url": ""},
            )
            result = await notifier.send(event)

            status = "success" if result.success else "failed"
            error_msg = result.error or ""

            await log_svc.create_log(
                event_type="test",
                channel="dingtalk",
                title="🔔 通知测试",
                status=status,
                error=error_msg,
                payload={"type": "test"},
                workflow_id="",
            )

            return {
                "success": result.success,
                "message": "测试通知已发送" if result.success else f"发送失败: {error_msg}",
                "results": [
                    {"channel": result.channel, "success": result.success, "error": result.error}
                ],
            }

    async def resend_log(self, log_id: int) -> dict[str, Any]:
        """重发某条日志（用日志中记录的 payload 重新渲染并发送）。

        重发不走开关检查与频次去重，确保运维可以强制重发。
        """
        async with AsyncSessionLocal() as session:
            log_svc = LogService(session)
            log = await log_svc.get_log(log_id)
            if log is None:
                return {"status": "failed", "message": "日志不存在"}

            payload = await log_svc.get_payload(log_id)
            if payload is None:
                payload = {}

            # 用日志记录的 payload 重新渲染
            tpl_svc = TemplateService(session)
            template = await tpl_svc.get_template(log.event_type)
            if template is None:
                return {"status": "failed", "message": "模板不存在或已禁用"}

            title, body = await TemplateRenderer(session).render(
                template.title_template, template.body_template, payload,
            )

            action_config = _EVENT_ACTION_MAP.get(log.event_type, {})
            action_url = ""
            if action_config:
                action_url = payload.get(action_config["action_url_key"], "")
            extra = {
                "event_type": log.event_type,
                "workflow_id": log.workflow_id,
                "action_url": action_url,
                "action_title": action_config.get("action_title", ""),
                "audio_url": payload.get("audio_url", ""),
            }
            event = NotificationEvent(
                title=title,
                message=body,
                severity="critical",
                source="notification_resend",
                extra=extra,
            )

            hub = get_notifier_hub()
            result = await hub.send(event)

            success_count = result.get("success", 0)
            status = "success" if success_count > 0 else "failed"
            errors = [r.error for r in result.get("results", []) if not r.success]
            error_msg = "; ".join(errors) if errors else ""

            await log_svc.create_log(
                event_type=log.event_type,
                channel="dingtalk",
                title=title,
                status=status,
                error=error_msg,
                payload=payload,
                workflow_id=log.workflow_id,
            )

            return {
                "status": status,
                "message": error_msg or "重发成功",
                "success": success_count,
                "failed": result.get("failed", 0),
            }


# 全局单例
_sender: NotificationSender | None = None


def get_notification_sender() -> NotificationSender:
    """获取 NotificationSender 单例。"""
    global _sender
    if _sender is None:
        _sender = NotificationSender()
    return _sender
