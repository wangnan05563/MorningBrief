"""通知配置服务：读写 ai_config key-value 表中的通知配置项。

复用 AIConfig 表（key-value 结构）存储通知开关与钉钉凭证，
与 AI 服务配置共享同一张表，保持配置管理范式一致。

敏感字段（dingtalk_secret）GET 时脱敏，PUT 时脱敏值视为未修改。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.ai_config import AIConfig

# 通知配置 key 与默认值
# 含三类渠道：钉钉（dingtalk）、企业微信（wecom）、邮件（email）
# 三类渠道均通过 ai_config key-value 表持久化，前端可独立配置
NOTIFY_CONFIG_KEYS: dict[str, str] = {
    "notify_global_enabled": "0",
    "notify_failed_enabled": "1",
    "notify_review_enabled": "1",
    "notify_published_enabled": "0",
    "notify_dingtalk_webhook": "",
    "notify_dingtalk_secret": "",
    "notify_wecom_webhook": "",
    "notify_email_smtp_host": "",
    "notify_email_smtp_port": "587",
    "notify_email_smtp_user": "",
    "notify_email_smtp_password": "",
    "notify_email_to": "",
    "notify_admin_base_url": "",
}

# 需要脱敏的 key（前端回传 **** 开头视为未修改）
SENSITIVE_NOTIFY_KEYS = {"notify_dingtalk_secret", "notify_email_smtp_password"}

# 场景开关 key 与 event_type 的映射
SCENE_SWITCH_MAP: dict[str, str] = {
    "notify_failed_enabled": "workflow.failed",
    "notify_review_enabled": "workflow.pending_review",
    "notify_published_enabled": "workflow.published",
}


def _mask_value(value: str) -> str:
    """脱敏：保留后 4 位，前缀 ****。"""
    if not value:
        return ""
    return f"****{value[-4:]}" if len(value) > 4 else "****"


def _is_masked(value: str) -> bool:
    """判断前端回传值是否为脱敏值（未修改）。"""
    return value.startswith("****")


class NotificationConfigService:
    """通知配置 CRUD 服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _read_all(self) -> dict[str, str]:
        """读取所有通知配置项（含默认值兜底）。"""
        result = await self.db.execute(
            select(AIConfig).where(AIConfig.config_key.in_(NOTIFY_CONFIG_KEYS.keys()))
        )
        rows = result.scalars().all()
        stored = {row.config_key: row.config_value for row in rows}

        # 合并默认值：未存储的 key 用默认值
        return {key: stored.get(key, default) for key, default in NOTIFY_CONFIG_KEYS.items()}

    async def _upsert(self, key: str, value: str) -> None:
        """插入或更新单个配置项。"""
        existing = await self.db.execute(
            select(AIConfig).where(AIConfig.config_key == key)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.config_value = value
        else:
            self.db.add(AIConfig(config_key=key, config_value=value))

    async def get_config(self) -> dict[str, Any]:
        """获取通知配置（敏感字段脱敏）+ 自动检测的 base_url。"""
        raw = await self._read_all()

        # 自动检测 base_url：优先 tunnel_service.public_url，其次 localhost
        auto_url = self._detect_base_url()

        return {
            "global_enabled": raw["notify_global_enabled"] == "1",
            "failed_enabled": raw["notify_failed_enabled"] == "1",
            "review_enabled": raw["notify_review_enabled"] == "1",
            "published_enabled": raw["notify_published_enabled"] == "1",
            "dingtalk_webhook": raw["notify_dingtalk_webhook"],
            "dingtalk_secret": _mask_value(raw["notify_dingtalk_secret"]),
            "wecom_webhook": raw["notify_wecom_webhook"],
            "email_smtp_host": raw["notify_email_smtp_host"],
            "email_smtp_port": int(raw["notify_email_smtp_port"]) if raw["notify_email_smtp_port"] else 587,
            "email_smtp_user": raw["notify_email_smtp_user"],
            "email_smtp_password": _mask_value(raw["notify_email_smtp_password"]),
            "email_to": raw["notify_email_to"],
            "admin_base_url": raw["notify_admin_base_url"],
            "auto_detected_base_url": auto_url,
        }

    async def save_config(self, data: dict[str, Any]) -> None:  # NOSONAR S3776: 配置保存含脱敏值识别与多端同步，结构清晰
        """保存通知配置。

        脱敏值（****开头）视为未修改，跳过；
        webhook 与开关字段直接写入。
        保存后调用 NotifierHub.reload() 让新凭证立即生效。
        """
        updates: dict[str, str] = {}

        # 布尔开关 → "1"/"0"
        for key in ("global_enabled", "failed_enabled", "review_enabled", "published_enabled"):
            config_key = f"notify_{key}"
            if key in data:
                updates[config_key] = "1" if data[key] else "0"

        # webhook 直接写入
        if "dingtalk_webhook" in data:
            updates["notify_dingtalk_webhook"] = str(data["dingtalk_webhook"] or "")

        # secret 脱敏值跳过
        secret = data.get("dingtalk_secret", "")
        if secret and not _is_masked(secret):
            updates["notify_dingtalk_secret"] = str(secret)

        # 企业微信 webhook 直接写入
        if "wecom_webhook" in data:
            updates["notify_wecom_webhook"] = str(data["wecom_webhook"] or "")

        # 邮件 SMTP 配置：host/user/to 直接写入，password 脱敏值跳过，port 转 str
        if "email_smtp_host" in data:
            updates["notify_email_smtp_host"] = str(data["email_smtp_host"] or "")
        if "email_smtp_port" in data:
            updates["notify_email_smtp_port"] = str(data["email_smtp_port"] or "587")
        if "email_smtp_user" in data:
            updates["notify_email_smtp_user"] = str(data["email_smtp_user"] or "")
        email_pwd = data.get("email_smtp_password", "")
        if email_pwd and not _is_masked(email_pwd):
            updates["notify_email_smtp_password"] = str(email_pwd)
        if "email_to" in data:
            updates["notify_email_to"] = str(data["email_to"] or "")

        # admin_base_url 直接写入（允许空字符串，空时用自动检测值）
        if "admin_base_url" in data:
            updates["notify_admin_base_url"] = str(data["admin_base_url"] or "")

        if not updates:
            return

        for key, value in updates.items():
            await self._upsert(key, value)
        await self.db.commit()

        # 热更新 NotifierHub：让新凭证立即生效
        self._reload_notifier_hub(updates)

    def _detect_base_url(self) -> str:
        """自动检测公网 base_url。

        优先级：
        1. tunnel_service.public_url（运行时动态获取的内网穿透地址）
        2. http://localhost:{APP_PORT}（兜底，本地开发场景）
        """
        try:
            from app.services.tunnel_service import get_tunnel_service
            tunnel = get_tunnel_service()
            url = tunnel.public_url
            if url:
                return url
        except Exception:
            pass
        settings = get_settings()
        return f"http://localhost:{settings.APP_PORT}"

    def _reload_notifier_hub(self, updates: dict[str, str]) -> None:
        """保存配置后热更新 NotifierHub 渠道实例。

        将三类渠道凭证同步到 Settings 单例，再调用 hub.reload() 重新加载渠道，
        避免重启服务。hub.reload() 会重新遍历注册表，过滤未配置凭证的渠道。
        """
        settings = get_settings()
        if "notify_dingtalk_webhook" in updates:
            settings.ALERT_DINGTALK_WEBHOOK = updates["notify_dingtalk_webhook"]
        if "notify_dingtalk_secret" in updates:
            settings.ALERT_DINGTALK_SECRET = updates["notify_dingtalk_secret"]
        if "notify_wecom_webhook" in updates:
            settings.ALERT_WECOM_WEBHOOK = updates["notify_wecom_webhook"]
        if "notify_email_smtp_host" in updates:
            settings.ALERT_EMAIL_SMTP_HOST = updates["notify_email_smtp_host"]
        if "notify_email_smtp_port" in updates:
            try:
                settings.ALERT_EMAIL_SMTP_PORT = int(updates["notify_email_smtp_port"])
            except (ValueError, TypeError):
                pass
        if "notify_email_smtp_user" in updates:
            settings.ALERT_EMAIL_SMTP_USER = updates["notify_email_smtp_user"]
        if "notify_email_smtp_password" in updates:
            settings.ALERT_EMAIL_SMTP_PASSWORD = updates["notify_email_smtp_password"]
        if "notify_email_to" in updates:
            settings.ALERT_EMAIL_TO = updates["notify_email_to"]

        try:
            from app.services.notifier import get_notifier_hub
            get_notifier_hub().reload()
        except Exception:
            pass

    async def get_raw_value(self, key: str) -> str:
        """读取原始配置值（不脱敏），供 sender 内部使用。"""
        if key not in NOTIFY_CONFIG_KEYS:
            return ""
        result = await self.db.execute(
            select(AIConfig.config_value).where(AIConfig.config_key == key)
        )
        value = result.scalar_one_or_none()
        if value is not None:
            return value
        return NOTIFY_CONFIG_KEYS[key]

    async def is_scene_enabled(self, event_type: str) -> bool:
        """检查指定事件类型的场景开关是否开启。

        全局开关关闭时所有事件都不发送；
        场景开关关闭时对应事件不发送。
        """
        raw = await self._read_all()
        if raw["notify_global_enabled"] != "1":
            return False

        # 反向映射：event_type → config_key
        for config_key, mapped_event in SCENE_SWITCH_MAP.items():
            if mapped_event == event_type:
                return raw[config_key] == "1"
        # 未映射的事件类型默认允许（如测试通知）
        return True
