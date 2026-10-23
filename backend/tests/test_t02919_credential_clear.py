"""T02919：LLM / TTS / 图片 / COS 四类凭据的显式清除通道。

口径：保存接口里「留空」永远表示不修改（前端把脱敏值折算成空串回传，
当成删除会在只改 base_url 时抹掉线上密钥）。清除只能走 reset-config：
- 行**真删除**（不是写空串），之后 GET 只能回落到 Settings；
- Settings 单例同步回退到 .env 默认值 → 旧密钥在本进程立刻不可用；
- 清除要落审计，detail 里只有 key 名，不含明文。

这些用例都断言 DB 行与 Settings 值，不看返回码——M16 刚踩过「返回成功而库里没动」。
"""
import json

import pytest
from sqlalchemy import select

from app.config import Settings, get_settings
from app.models.ai_config import AIConfig
from app.models.audit_log import AuditLog
from app.models.cos_config import CosConfig
from app.services.ai_config_service import (
    PRESET_CONFIGS_KEY,
    RESET_SCOPES,
    TTS_RESET_KEYS,
    AIConfigService,
)
from app.services.cos_config_service import CosConfigService, _mask_key


async def _seed_ai(db, rows: dict[str, str]):
    for key, value in rows.items():
        db.add(AIConfig(config_key=key, config_value=value))
    await db.commit()


async def _ai_value(db, key: str):
    return (
        await db.execute(select(AIConfig).where(AIConfig.config_key == key))
    ).scalar_one_or_none()


async def _seed_cos(db, rows: dict[str, str]):
    for key, value in rows.items():
        db.add(CosConfig(config_key=key, config_value=value))
    await db.commit()


async def _cos_value(db, key: str):
    return (
        await db.execute(select(CosConfig).where(CosConfig.config_key == key))
    ).scalar_one_or_none()


@pytest.fixture(autouse=True)
def _reset_settings_reference(monkeypatch):
    """隔离 Settings 单例：清除动作会改内存值，测试后还原避免污染同进程。"""
    s = get_settings()
    for attr in (
        "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL",
        "ALIYUN_TTS_API_KEY", "ALIYUN_TTS_APPKEY",
        "TENCENT_TTS_SECRET_ID", "TENCENT_TTS_SECRET_KEY",
        "IMAGE_API_KEY",
        "COS_SECRET_ID", "COS_SECRET_KEY", "COS_BUCKET", "COS_REGION",
    ):
        monkeypatch.setattr(s, attr, getattr(s, attr))


# ---- 服务层：scope 精确性 ----


async def test_reset_tts_deletes_rows_and_restores_settings(db_session):
    """scope=tts 只删四个 TTS 凭据行，LLM/图片的行不动。"""
    await _seed_ai(db_session, {
        "tts_api_key": "sk-tts-old",
        "tts_appkey": "appkey-old",
        "tencent_tts_secret_id": "AKID-old",
        "tencent_tts_secret_key": "SK-old",
        "llm_api_key": "sk-llm-keep",
        "image_api_key": "sk-img-keep",
    })
    settings = get_settings()
    settings.ALIYUN_TTS_API_KEY = "sk-tts-old"

    await AIConfigService(db_session).reset_to_defaults("tts")

    for key in TTS_RESET_KEYS:
        assert await _ai_value(db_session, key) is None, f"{key} 应被真正删除"
    assert (await _ai_value(db_session, "llm_api_key")).config_value == "sk-llm-keep"
    assert (await _ai_value(db_session, "image_api_key")).config_value == "sk-img-keep"

    defaults = Settings()
    assert settings.ALIYUN_TTS_API_KEY == defaults.ALIYUN_TTS_API_KEY
    assert settings.ALIYUN_TTS_API_KEY != "sk-tts-old", "内存单例仍握旧密钥＝清除没生效"


async def test_reset_image_only_clears_image_key(db_session):
    await _seed_ai(db_session, {
        "image_api_key": "sk-img-old",
        "llm_api_key": "sk-llm-keep",
        "tts_api_key": "sk-tts-keep",
    })
    settings = get_settings()
    settings.IMAGE_API_KEY = "sk-img-old"

    await AIConfigService(db_session).reset_to_defaults("image")

    assert await _ai_value(db_session, "image_api_key") is None
    assert (await _ai_value(db_session, "llm_api_key")).config_value == "sk-llm-keep"
    assert (await _ai_value(db_session, "tts_api_key")).config_value == "sk-tts-keep"
    assert settings.IMAGE_API_KEY != "sk-img-old"


async def test_reset_all_clears_llm_presets_and_every_credential(db_session):
    """scope=all 覆盖四类；llm 段沿用旧口径（含预设 JSON）。"""
    await _seed_ai(db_session, {
        "llm_api_key": "sk-llm-old",
        "llm_base_url": "https://old.example/v1",
        "llm_model": "old-model",
        PRESET_CONFIGS_KEY: json.dumps({"qwen": {"api_key": "sk-preset-old"}}),
        **{key: f"old-{key}" for key in TTS_RESET_KEYS},
        "image_api_key": "sk-img-old",
        # 非凭据通用项必须保留
        "llm_timeout_sec": "45",
    })
    settings = get_settings()
    settings.LLM_API_KEY = "sk-llm-old"

    await AIConfigService(db_session).reset_to_defaults("all")

    for key in RESET_SCOPES["all"]:
        assert await _ai_value(db_session, key) is None, f"{key} 应被删除"
    assert (await _ai_value(db_session, "llm_timeout_sec")).config_value == "45"
    assert settings.LLM_API_KEY != "sk-llm-old"


async def test_reset_rejects_unknown_scope(db_session):
    with pytest.raises(ValueError, match="不支持的清除范围"):
        await AIConfigService(db_session).reset_to_defaults("everything")


# ---- HTTP：默认 scope 兼容 + 参数校验 + 审计 ----


async def test_http_reset_default_scope_still_clears_llm(client, admin_token, db_session):
    """旧前端不带 scope 调用，行为必须还是「清 LLM」，不能 422 或空操作。"""
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    await _seed_ai(db_session, {"llm_api_key": "sk-llm-old", "llm_model": "old-model"})

    resp = client.post("/admin/api/v1/ai/reset-config", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert "llm" in body["data"]

    assert await _ai_value(db_session, "llm_api_key") is None
    assert await _ai_value(db_session, "llm_model") is None


async def test_http_reset_tts_clears_db_and_audits_without_plaintext(client, admin_token, db_session):
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    await _seed_ai(db_session, {
        "tts_api_key": "sk-tts-secret-value",
        "tts_appkey": "appkey-secret-value",
    })

    resp = client.post("/admin/api/v1/ai/reset-config?scope=tts", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0

    assert await _ai_value(db_session, "tts_api_key") is None
    assert await _ai_value(db_session, "tts_appkey") is None

    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.category == "ai"))
    ).scalars().all()
    assert len(audit) == 1
    assert audit[0].action == "reset_config"
    assert audit[0].target == "tts"
    assert audit[0].operator == "admin"
    detail = json.loads(audit[0].detail)
    assert detail["cleared_keys"] == TTS_RESET_KEYS
    assert "secret-value" not in audit[0].detail, "审计 detail 不得含明文凭据"


async def test_http_reset_invalid_scope_rejected(client, admin_token, db_session):
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    await _seed_ai(db_session, {"llm_api_key": "sk-llm-keep"})

    resp = client.post("/admin/api/v1/ai/reset-config?scope=root", headers=headers)
    # 全局异常处理器把参数校验错误包成 HTTP 400 业务信封
    assert resp.status_code == 400
    assert resp.json()["code"] == 400
    # 参数校验失败不得误删任何东西
    assert (await _ai_value(db_session, "llm_api_key")).config_value == "sk-llm-keep"


# ---- COS ----


async def test_cos_reset_credentials_keeps_bucket_and_region(db_session):
    await _seed_cos(db_session, {
        "cos_secret_id": "AKID-old",
        "cos_secret_key": "SK-old",
        "cos_region": "ap-shanghai",
        "cos_bucket": "news-1250000000",
        "cos_cdn_domain": "cdn.example.com",
    })
    settings = get_settings()
    settings.COS_SECRET_ID = "AKID-old"
    settings.COS_BUCKET = "news-1250000000"

    data = await CosConfigService(db_session).reset_credentials()

    assert await _cos_value(db_session, "cos_secret_id") is None
    assert await _cos_value(db_session, "cos_secret_key") is None
    assert (await _cos_value(db_session, "cos_region")).config_value == "ap-shanghai"
    assert (await _cos_value(db_session, "cos_bucket")).config_value == "news-1250000000"
    assert (await _cos_value(db_session, "cos_cdn_domain")).config_value == "cdn.example.com"

    defaults = Settings()
    assert settings.COS_SECRET_ID == defaults.COS_SECRET_ID
    assert settings.COS_SECRET_ID != "AKID-old"
    assert settings.COS_BUCKET == "news-1250000000"
    # 返回值即清除后的真实配置：库里的凭证已没了，只剩 .env 回落值与保留的桶。
    # 不钉 configured：.env 里若本来就有凭证，回落值仍算「已配置」——
    # 那是 .env 基线而不是「库里旧密钥还活着」。
    assert data["bucket"] == "news-1250000000"
    assert data["secret_id"] == _mask_key(defaults.COS_SECRET_ID)
    assert "AKID-old"[-4:] not in data["secret_id"]


async def test_http_cos_reset_audits_and_keeps_bucket(client, admin_token, db_session):
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    await _seed_cos(db_session, {
        "cos_secret_id": "AKID-secret-value",
        "cos_secret_key": "SK-secret-value",
        "cos_bucket": "news-1250000000",
    })

    resp = client.post("/admin/api/v1/cos/reset-config", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["bucket"] == "news-1250000000"

    assert await _cos_value(db_session, "cos_secret_id") is None
    assert await _cos_value(db_session, "cos_secret_key") is None
    assert (await _cos_value(db_session, "cos_bucket")).config_value == "news-1250000000"

    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.category == "cos"))
    ).scalars().all()
    assert len(audit) == 1
    assert audit[0].action == "reset_config"
    assert "secret-value" not in audit[0].detail
