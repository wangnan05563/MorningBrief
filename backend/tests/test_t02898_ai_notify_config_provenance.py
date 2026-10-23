"""T02898：AI / 通知配置接口同样要回答「这些值是库里存的，还是回落来的」。

T02527（INT-UX-04）只修了 `cos/config`，但同一段代码模式在另外两个配置面一模一样：
`AIConfigService.get_config_for_frontend` 的 `_get*` 与通知服务的 `_read_all`
都是「取不到库值就用默认值」，于是「表是空的」与「表里有记录」在响应里长得一样。
管理员在这类页面上点保存，会把 .env / 代码默认值静默固化进库，且没有 updated_at
可回溯。这里按 T02527 的 `test_int04_cos_config_provenance.py` 同构断言：

- 库里有值 → loaded=true、updated_at 对齐表内 max、fallback_fields 为空；
- 表为空 → loaded=true 但 updated_at=null，且逐个点名回落字段（AI 按 llm./tts./image. 路径）；
- 读表失败 → loaded=false、load_error 已脱敏且有长度上界、updated_at 强制 null；
- 「先播种再炸」→ 读失败时绝不把上一次的时间当成本次加载证据；
- HTTP 层能看到这四个字段。
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models.ai_config import AIConfig
from app.services.ai_config_service import (
    CONFIG_KEY_MAP,
    PRESET_CONFIGS_KEY,
    AIConfigService,
)
from app.services.notification.config_service import (
    NOTIFY_CONFIG_KEYS,
    NotificationConfigService,
)

SECRET_KEY = "sk-secret-value-8f3a2b"


async def _seed_ai_all(db_session):
    """把 get_config_for_frontend 会读到的 key 全部按当前 Settings 值入库。"""
    settings = get_settings()
    for key, attr in CONFIG_KEY_MAP.items():
        db_session.add(AIConfig(config_key=key, config_value=str(getattr(settings, attr))))
    db_session.add(AIConfig(config_key=PRESET_CONFIGS_KEY, config_value="{}"))
    await db_session.commit()


def _ai_updated_at_query():
    return select(func.max(AIConfig.updated_at)).where(
        AIConfig.config_key.in_(list(CONFIG_KEY_MAP) + [PRESET_CONFIGS_KEY])
    )


# ---------- AI 配置 ----------


async def test_ai_values_from_db_are_marked_loaded_with_timestamp(db_session):
    await _seed_ai_all(db_session)
    data = await AIConfigService(db_session).get_config_for_frontend()

    assert data["loaded"] is True
    assert data["load_error"] is None
    assert data["fallback_fields"] == []
    assert data["updated_at"]
    # 与表里 AI key 的 max(updated_at) 对齐，不是页面自己算的「刚刚」
    assert datetime.fromisoformat(data["updated_at"]) == (
        await db_session.execute(_ai_updated_at_query())
    ).scalar_one()


async def test_ai_empty_table_exposes_env_fallback_by_path(db_session):
    """表为空但 .env 有值：字段必须按 llm./tts./image. 路径逐个点名。"""
    settings = get_settings()
    saved = (settings.LLM_API_KEY, settings.LLM_BASE_URL, settings.ALIYUN_TTS_VOICE)
    settings.LLM_API_KEY, settings.LLM_BASE_URL, settings.ALIYUN_TTS_VOICE = (
        "sk-from-env",
        "https://llm.example/v1",
        "xiaoyun",
    )
    try:
        data = await AIConfigService(db_session).get_config_for_frontend()
    finally:
        settings.LLM_API_KEY, settings.LLM_BASE_URL, settings.ALIYUN_TTS_VOICE = saved

    assert data["loaded"] is True          # 读库成功
    assert data["updated_at"] is None      # 但库里没有任何入库记录
    assert "llm.api_key" in data["fallback_fields"]
    assert "llm.base_url" in data["fallback_fields"]
    assert "tts.voice" in data["fallback_fields"]
    assert "image.api_key" in data["fallback_fields"]
    # 值本身仍是 .env 那套（口径不变，只是多了来源说明），凭证照旧脱敏
    assert data["llm"]["api_key"] == "****-env"
    assert data["llm"]["base_url"] == "https://llm.example/v1"


async def test_ai_read_failure_reports_not_loaded(db_session, monkeypatch):
    """读库异常不能装作一份正常配置；表里已有时间也不能端出来当证据。"""
    await _seed_ai_all(db_session)

    async def _boom(self):
        raise RuntimeError(
            f"no such column: config_value; bound params api_key='{SECRET_KEY}'"
        )

    monkeypatch.setattr(AIConfigService, "get_all_config", _boom)
    data = await AIConfigService(db_session).get_config_for_frontend()

    assert data["loaded"] is False
    assert "no such column" in data["load_error"]
    assert data["updated_at"] is None
    # 失败原因可读，但不得把异常文本里的凭据原样带到前端（NFR-01）
    assert SECRET_KEY not in str(data)


async def test_ai_preset_read_failure_also_blocks_save(db_session, monkeypatch):
    """预设配置是第二条读库路径：它失败时同样不能说「整份配置可信」。"""
    await _seed_ai_all(db_session)

    async def _boom(self):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(AIConfigService, "get_preset_configs", _boom)
    data = await AIConfigService(db_session).get_config_for_frontend()

    assert data["loaded"] is False
    assert "database is locked" in data["load_error"]
    assert data["llm"]["preset_configs"] == {}


async def test_ai_load_error_is_bounded(db_session, monkeypatch):
    async def _boom(self):
        raise RuntimeError("database is locked " + ("retry later " * 400))

    monkeypatch.setattr(AIConfigService, "get_all_config", _boom)
    data = await AIConfigService(db_session).get_config_for_frontend()

    assert data["loaded"] is False
    assert data["load_error"].startswith("RuntimeError: database is locked")
    assert len(data["load_error"]) <= len("RuntimeError: ") + 200


async def test_ai_updated_at_ignores_notification_keys(db_session):
    """ai_config 与通知配置共用一张表：改通知不能刷新「AI 配置最后修改时间」。"""
    await _seed_ai_all(db_session)
    ai_time = (await db_session.execute(_ai_updated_at_query())).scalar_one()

    # 显式晚 60s：CURRENT_TIMESTAMP 只有秒级精度，同一秒内入库会让过滤缺失也测不出来
    db_session.add(
        AIConfig(
            config_key="notify_global_enabled",
            config_value="1",
            updated_at=ai_time + timedelta(seconds=60),
        )
    )
    await db_session.commit()
    data = await AIConfigService(db_session).get_config_for_frontend()

    assert datetime.fromisoformat(data["updated_at"]) == ai_time


async def test_ai_route_exposes_the_new_fields(client, admin_token, db_session):
    await _seed_ai_all(db_session)
    body = client.get(
        "/admin/api/v1/ai/config",
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    ).json()
    assert body["code"] == 0
    for f in ("loaded", "updated_at", "fallback_fields", "load_error"):
        assert f in body["data"], f


# ---------- 通知配置 ----------

NOTIFY_FRONT_FIELDS = [key.removeprefix("notify_") for key in NOTIFY_CONFIG_KEYS]


async def test_notify_values_from_db_are_marked_loaded(db_session):
    db_session.add(AIConfig(config_key="notify_global_enabled", config_value="1"))
    db_session.add(AIConfig(config_key="notify_email_smtp_host", config_value="smtp.test"))
    await db_session.commit()

    data = await NotificationConfigService(db_session).get_config()

    assert data["loaded"] is True
    assert data["load_error"] is None
    assert data["updated_at"]
    expected_time = (
        await db_session.execute(
            select(func.max(AIConfig.updated_at)).where(
                AIConfig.config_key.in_(NOTIFY_CONFIG_KEYS.keys())
            )
        )
    ).scalar_one()
    assert datetime.fromisoformat(data["updated_at"]) == expected_time
    # 入库的两个不再点名，其余仍是默认值
    assert sorted(data["fallback_fields"]) == sorted(
        set(NOTIFY_FRONT_FIELDS) - {"global_enabled", "email_smtp_host"}
    )


async def test_notify_empty_table_exposes_all_default_fields(db_session):
    data = await NotificationConfigService(db_session).get_config()

    assert data["loaded"] is True
    assert data["updated_at"] is None
    assert sorted(data["fallback_fields"]) == sorted(NOTIFY_FRONT_FIELDS)


async def test_notify_read_failure_reports_not_loaded(db_session, monkeypatch):
    db_session.add(AIConfig(config_key="notify_global_enabled", config_value="1"))
    await db_session.commit()

    async def _boom(self):
        raise RuntimeError(f"no such column: config_value; token='{SECRET_KEY}'")

    monkeypatch.setattr(NotificationConfigService, "_read_stored", _boom)
    data = await NotificationConfigService(db_session).get_config()

    assert data["loaded"] is False
    assert "no such column" in data["load_error"]
    assert data["updated_at"] is None
    assert SECRET_KEY not in str(data)


async def test_notify_load_error_is_bounded(db_session, monkeypatch):
    async def _boom(self):
        raise RuntimeError("database is locked " + ("retry later " * 400))

    monkeypatch.setattr(NotificationConfigService, "_read_stored", _boom)
    data = await NotificationConfigService(db_session).get_config()

    assert data["loaded"] is False
    assert data["load_error"].startswith("RuntimeError: database is locked")
    assert len(data["load_error"]) <= len("RuntimeError: ") + 200


async def test_notify_route_exposes_the_new_fields(client, admin_token, db_session):
    body = client.get(
        "/admin/api/v1/notification/config",
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    ).json()
    assert body["code"] == 0
    for f in ("loaded", "updated_at", "fallback_fields", "load_error"):
        assert f in body["data"], f
