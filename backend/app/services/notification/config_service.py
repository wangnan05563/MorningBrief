"""通知配置服务：读写 ai_config key-value 表中的通知配置项。

复用 AIConfig 表（key-value 结构）存储通知开关与钉钉凭证，
与 AI 服务配置共享同一张表，保持配置管理范式一致。

敏感字段（dingtalk_secret / email_smtp_password / 机器人 webhook URL）GET 时脱敏，
PUT 时脱敏值视为未修改。

NFR-UX-01（T02519）：webhook 不再算"非敏感"——钉钉/企微机器人地址形如
`https://oapi.dingtalk.com/robot/send?access_token=<凭据>`，URL 的 query 本身就承载凭据，
原样出现在 GET 响应 / 前端状态 / 抓包记录里等同于密钥泄露。
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging_setup import redact_credentials
from app.models.ai_config import AIConfig

logger = logging.getLogger(__name__)

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

# 需按「URL 脱敏」处理的机器人回调地址 key：整串可读、仅凭据参数值脱敏
WEBHOOK_URL_KEYS = {"notify_dingtalk_webhook", "notify_wecom_webhook"}

# webhook URL 中承载凭据的 query 参数名（小写匹配）
_WEBHOOK_SECRET_PARAMS = {"access_token", "token", "key", "secret", "signature", "sign"}

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


def _mask_webhook(url: str) -> str:
    """机器人 webhook URL 脱敏：只替换凭据型 query 参数的值，保留 host/path。

    保留 host/path 是为了运维仍能一眼认出"这是哪个群的机器人"；
    凭据参数值按 `_mask_value` 口径处理（****+ 后 4 位）。

    兜底：解析失败 / 无 query / query 里没有凭据参数时，整串脱敏——
    宁可多脱一层，也不假设"没看到凭据就是明文安全"。
    """
    if not url:
        return ""
    if _is_masked(url):
        return url  # 幂等：已脱敏的值不再二次处理
    try:
        parsed = urlparse(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
    except ValueError:
        return _mask_value(url)
    if not pairs or not any(name.lower() in _WEBHOOK_SECRET_PARAMS for name, _ in pairs):
        return _mask_value(url)
    masked_pairs = [
        (name, _mask_value(value) if name.lower() in _WEBHOOK_SECRET_PARAMS and value else value)
        for name, value in pairs
    ]
    # safe="*"：脱敏占位符里的 * 不能被 percent-encode 成 %2A（前端要能一眼读出 ****尾4）
    return urlunparse(parsed._replace(query=urlencode(masked_pairs, safe="*")))


class NotificationConfigService:
    """通知配置 CRUD 服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _read_stored(self) -> dict[str, str]:
        """只读库里实际存在的通知配置项（不做默认值合并）。"""
        result = await self.db.execute(
            select(AIConfig).where(AIConfig.config_key.in_(NOTIFY_CONFIG_KEYS.keys()))
        )
        return {row.config_key: row.config_value for row in result.scalars().all()}

    async def _read_all(self) -> dict[str, str]:
        """读取所有通知配置项（含默认值兜底）。"""
        stored = await self._read_stored()
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

    async def _resolve_webhook(self, config_key: str, incoming: Any) -> str | None:
        """判定 webhook 回传值该不该写库。

        返回 None 表示「视为未修改，跳过」——GET 已脱敏，前端把脱敏值原样回传时
        若直接写入，会用 `****xxxx` 覆盖真实凭据、通知静默失效；
        返回字符串（含空串）表示要写入的明文，空串是用户显式清空。
        """
        value = str(incoming or "")
        if not value:
            return ""
        if _is_masked(value):
            return None
        current = await self.get_raw_value(config_key)
        if current and value == _mask_webhook(current):
            return None
        return value

    async def get_config(self) -> dict[str, Any]:
        """获取通知配置（敏感字段脱敏）+ 自动检测的 base_url + 来源信息。

        除业务字段外返回 T02898 口径（与 INT-UX-04 同一契约）：
        - loaded: 本次是否真的读到了配置表；
        - load_error: 读表失败原因（已脱敏，长度有上界）；
        - updated_at: 通知类 key 的最后入库修改时间；读失败恒为 None；
        - fallback_fields: 库中未保存、屏上用的是默认值的字段名。

        通知配置的回落来源是 `NOTIFY_CONFIG_KEYS` 默认值（不是 .env），
        因此字段名按响应字段口径（去掉 `notify_` 前缀）给出，前端据此写清来源。
        """
        load_error: str | None = None
        try:
            stored = await self._read_stored()
        except Exception as exc:
            # 完整异常只进日志；响应里给可读且已脱敏的原因（NFR-01 / NFR-05）
            logger.exception("通知配置读取失败，前端将据 loaded=false 禁止保存")
            stored = {}
            load_error = f"{type(exc).__name__}: {redact_credentials(str(exc))[:200]}"

        raw = {key: stored.get(key, default) for key, default in NOTIFY_CONFIG_KEYS.items()}
        fallback_fields = [key.removeprefix("notify_") for key in NOTIFY_CONFIG_KEYS if key not in stored]

        # 自动检测 base_url：优先 tunnel_service.public_url，其次 localhost
        auto_url = self._detect_base_url()

        return {
            "global_enabled": raw["notify_global_enabled"] == "1",
            "failed_enabled": raw["notify_failed_enabled"] == "1",
            "review_enabled": raw["notify_review_enabled"] == "1",
            "published_enabled": raw["notify_published_enabled"] == "1",
            "dingtalk_webhook": _mask_webhook(raw["notify_dingtalk_webhook"]),
            "dingtalk_secret": _mask_value(raw["notify_dingtalk_secret"]),
            "wecom_webhook": _mask_webhook(raw["notify_wecom_webhook"]),
            "email_smtp_host": raw["notify_email_smtp_host"],
            "email_smtp_port": int(raw["notify_email_smtp_port"]) if raw["notify_email_smtp_port"] else 587,
            "email_smtp_user": raw["notify_email_smtp_user"],
            "email_smtp_password": _mask_value(raw["notify_email_smtp_password"]),
            "email_to": raw["notify_email_to"],
            "admin_base_url": raw["notify_admin_base_url"],
            "auto_detected_base_url": auto_url,
            "loaded": load_error is None,
            "load_error": load_error,
            "updated_at": await self._latest_updated_at(only_if_loaded=load_error is None),
            "fallback_fields": fallback_fields,
        }

    async def _latest_updated_at(self, only_if_loaded: bool) -> str | None:
        """通知配置最后一次入库修改时间（本地 naive）。

        只统计通知类 key：ai_config 与 AI 配置共用一张表，不过滤的话
        改一次 AI 配置就会刷新「通知配置最后修改时间」。
        """
        if not only_if_loaded:
            return None
        try:
            latest = (
                await self.db.execute(
                    select(func.max(AIConfig.updated_at)).where(
                        AIConfig.config_key.in_(NOTIFY_CONFIG_KEYS.keys())
                    )
                )
            ).scalar_one_or_none()
        except Exception:
            logger.exception("通知配置 updated_at 读取失败，按无修改时间处理")
            return None
        return latest.isoformat(timespec="seconds") if latest else None

    async def save_config(self, data: dict[str, Any]) -> None:  # NOSONAR S3776: 配置保存含脱敏值识别与多端同步，结构清晰
        """保存通知配置。

        脱敏值（****开头，或 webhook 的脱敏形态）视为未修改，跳过；
        其余开关与地址字段直接写入。
        保存后调用 NotifierHub.reload() 让新凭证立即生效。
        """
        updates: dict[str, str] = {}

        # 布尔开关 → "1"/"0"
        for key in ("global_enabled", "failed_enabled", "review_enabled", "published_enabled"):
            config_key = f"notify_{key}"
            if key in data:
                updates[config_key] = "1" if data[key] else "0"

        # webhook：GET 侧已脱敏，回传脱敏形态视为未修改（NFR-UX-01 / T02519）
        if "dingtalk_webhook" in data:
            resolved = await self._resolve_webhook("notify_dingtalk_webhook", data["dingtalk_webhook"])
            if resolved is not None:
                updates["notify_dingtalk_webhook"] = resolved

        # secret 脱敏值跳过
        secret = data.get("dingtalk_secret", "")
        if secret and not _is_masked(secret):
            updates["notify_dingtalk_secret"] = str(secret)

        # 企业微信 webhook：同钉钉口径
        if "wecom_webhook" in data:
            resolved = await self._resolve_webhook("notify_wecom_webhook", data["wecom_webhook"])
            if resolved is not None:
                updates["notify_wecom_webhook"] = resolved

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
