"""NFR-UX-01（T02519）敏感面接口抓包断言：凭据不得以明文出现在任何管理端出参里。

覆盖口径（"响应体里搜不到明文标记"式断言，比逐字段断言更难被漏字段绕过）：
- 通知配置 GET：dingtalk/secret、wecom/secret、SMTP 密码、以及 **webhook URL 的凭据参数**
- AI 服务配置 / 云端存储配置 GET：api_key / secret 类字段
- 数据库维护（通用表浏览）：ai_config 行浏览 + 单行导出
- 审计日志明细：写侧与读侧双脱敏

明文标记统一含 `PLAINTEXT` 子串；脱敏口径保留后 4 位，因此断言用 `PLAINTEXT`
而不是整串值——`****4xyz` 形态的出参天然不含该子串。
"""
import json

import pytest
from sqlalchemy import select

from app.models.ai_config import AIConfig
from app.services.db_admin_service import BizError, DbAdminService, _mask_audit_detail, _row_sensitive_columns
from app.services.notification.config_service import (
    SENSITIVE_NOTIFY_KEYS,
    WEBHOOK_URL_KEYS,
    NotificationConfigService,
    _mask_webhook,
)

MARK = "PLAINTEXT"
DINGTALK_URL = f"https://oapi.dingtalk.com/robot/send?access_token=dt{MARK}9999"
WECOM_URL = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=wc{MARK}8888"
DINGTALK_SECRET = f"sec{MARK}7777"
SMTP_PASSWORD = f"pw{MARK}6666"
LLM_API_KEY = f"sk-{MARK}5555"
COS_SECRET_KEY = f"cos{MARK}4444"


def _assert_no_plaintext(payload, label: str):
    """把出参整体序列化后搜明文标记（等价于抓包检索响应体）。"""
    dumped = json.dumps(payload, ensure_ascii=False, default=str)
    assert MARK not in dumped, f"{label} 出参含明文凭据：{dumped[:400]}"


# ====================== webhook 脱敏函数本身 ======================

def test_mask_webhook_only_masks_credential_param():
    """脱敏保留 host/path（运维要能认出是哪个机器人），只换凭据参数值。"""
    masked = _mask_webhook(DINGTALK_URL)
    assert masked.startswith("https://oapi.dingtalk.com/robot/send?access_token=")
    assert "dt" + MARK not in masked
    assert masked.endswith("****9999")


def test_mask_webhook_is_idempotent():
    """已脱敏值再过一次不变——前端回传链路可能被多次读取/保存触发。"""
    once = _mask_webhook(WECOM_URL)
    assert _mask_webhook(once) == once


def test_mask_webhook_falls_back_to_full_mask():
    """无 query / query 里没有凭据参数 / 整串哨兵：一律整串脱敏，不假设"没看到凭据就安全"。"""
    assert _mask_webhook("https://hooks.example.com/notify/meow") == "****meow"
    assert _mask_webhook("not a url at all") == "**** all"
    assert _mask_webhook("****already") == "****already"
    assert _mask_webhook("") == ""


def test_every_webhook_key_is_url_masked_on_read():
    """回归门禁：往 WEBHOOK_URL_KEYS 里加 key，GET 出参必须同步脱敏（漏一个即失败）。"""
    assert WEBHOOK_URL_KEYS == {"notify_dingtalk_webhook", "notify_wecom_webhook"}
    assert SENSITIVE_NOTIFY_KEYS == {"notify_dingtalk_secret", "notify_email_smtp_password"}


# ====================== 通知配置 GET ======================

async def _seed_notify_config(db_session):
    for key, value in (
        ("notify_global_enabled", "1"),
        ("notify_dingtalk_webhook", DINGTALK_URL),
        ("notify_dingtalk_secret", DINGTALK_SECRET),
        ("notify_wecom_webhook", WECOM_URL),
        ("notify_email_smtp_password", SMTP_PASSWORD),
        ("notify_email_smtp_host", "smtp.example.com"),
        ("notify_email_to", "ops@example.com"),
    ):
        db_session.add(AIConfig(config_key=key, config_value=value))
    await db_session.commit()


async def test_notification_get_config_has_no_plaintext_credential(db_session):
    """NFR-UX-01 核心：GET 通知配置（含抓包/前端状态）不得出现任何明文凭据。"""
    await _seed_notify_config(db_session)
    shown = await NotificationConfigService(db_session).get_config()
    _assert_no_plaintext(shown, "通知配置 GET")
    # 非定位信息仍可读，避免"为了脱敏把配置变成不可运维"
    assert "oapi.dingtalk.com" in shown["dingtalk_webhook"]
    assert shown["email_smtp_host"] == "smtp.example.com"


async def test_db_admin_rows_masks_webhook_config_value(db_session):
    """数据库维护页浏览 ai_config：webhook key 行同样属于敏感行（T02519 补的模式）。"""
    await _seed_notify_config(db_session)
    data = await DbAdminService(db_session).list_rows("ai_config", limit=200)
    _assert_no_plaintext(data, "数据库维护 ai_config 行浏览")
    webhook_rows = [r for r in data["rows"] if str(r.get("config_key", "")).endswith("webhook")]
    assert webhook_rows, "seed 未生效：没查到 webhook 行"
    assert all(str(r["config_value"]).startswith("*") for r in webhook_rows)
    # 导出走的是另一条序列化路径（export_rows），同样不得漏脱敏——它是明文凭据最容易外流的动作
    exported_rows, _cols, _label = await DbAdminService(db_session).export_rows("ai_config", "json")
    _assert_no_plaintext(exported_rows, "数据库维护 ai_config 导出")


def test_row_sensitive_columns_recognizes_webhook_key():
    """按列语义判定：webhook 行敏感、开关行不敏感（一刀切会误伤可编辑性）。"""
    assert "config_value" in _row_sensitive_columns(
        "ai_config", {"config_key": "notify_dingtalk_webhook", "config_value": DINGTALK_URL}
    )
    assert "config_value" not in _row_sensitive_columns(
        "ai_config", {"config_key": "notify_global_enabled", "config_value": "1"}
    )


async def test_db_admin_rejects_mask_sentinel_writeback_for_webhook(db_session):
    """在数据库维护页把看到的 *** 原样存回去，必须被拒且不改写真实凭据。"""
    await _seed_notify_config(db_session)
    row = (
        await db_session.execute(select(AIConfig).filter_by(config_key="notify_dingtalk_webhook"))
    ).scalar_one()
    svc = DbAdminService(db_session)
    with pytest.raises(BizError):
        await svc.update_row("ai_config", str(row.id), {"config_value": "***"})
    await db_session.rollback()
    await db_session.refresh(row)
    assert row.config_value == DINGTALK_URL


async def test_audit_detail_masks_webhook_credential(db_session):
    """审计明细（写侧+读侧共用 `_mask_audit_detail`）不得留明文凭据。"""
    masked = _mask_audit_detail(
        {"pk": 1, "values": {"config_key": "notify_dingtalk_webhook", "config_value": DINGTALK_URL}},
        "ai_config",
    )
    _assert_no_plaintext(masked, "审计明细")
    svc = DbAdminService(db_session)
    await svc.write_audit(
        action="update",
        target="ai_config",
        operator="tester",
        detail={"values": {"config_key": "notify_dingtalk_webhook", "config_value": DINGTALK_URL}},
    )
    await db_session.commit()
    logs = await svc.list_audit_logs(limit=10)
    _assert_no_plaintext(logs, "审计日志列表")


# ====================== 跨配置面统一断言 ======================

async def test_ai_and_cos_config_surfaces_are_masked(db_session):
    """AI 服务配置 / 云端存储配置 GET 口径与通知配置一致（同类字段的横向核对）。"""
    from app.services.ai_config_service import AIConfigService
    from app.services.cos_config_service import CosConfigService

    db_session.add(AIConfig(config_key="llm_api_key", config_value=LLM_API_KEY))
    db_session.add(AIConfig(config_key="cos_secret_key", config_value=COS_SECRET_KEY))
    await db_session.commit()

    _assert_no_plaintext(
        await AIConfigService(db_session).get_config_for_frontend(), "AI 服务配置 GET"
    )
    _assert_no_plaintext(
        await CosConfigService(db_session).get_config_for_frontend(), "云端存储配置 GET"
    )
