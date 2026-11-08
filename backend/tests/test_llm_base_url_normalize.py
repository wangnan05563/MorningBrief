"""T04117：LLM base_url 归一化 + AI 生成失败可见化。

背景（2026-11 实测四个 provider 全部不可用）：
- 配置页把 base_url 误存成 `.../v1/chat/completions` → 测试连接拼成双路径，
  上游 404 被误读为「模型不存在」；归一后真实原因是 402 余额不足；
- 频道创建/重新生成提示词时 LLM 失败只写日志并静默跳过字段，管理端看起来
  「AI 没反应」。账号级错误（401/402/403）重试无效，必须把原因带回前端。

覆盖：
- normalize_llm_base_url 单元口径（保留 /v1、削 /chat/completions、不动各家根路径）；
- 预设配置读/写两侧归一（历史脏行不落库也能自愈）；
- test_llm_connection 的 402/404/5xx 可操作文案 + 请求 URL 不再重复拼接；
- 频道创建 / 重新生成提示词失败时 ai_generate_warnings 与 502 文案。
"""
import json

import pytest
from sqlalchemy import select

import app.services.ai_config_service as svc_mod
from app.models.ai_config import AIConfig
from app.services.ai_config_service import (
    AIConfigService,
    PRESET_CONFIGS_KEY,
    normalize_llm_base_url,
)


# ---------------------------------------------------------------------------
# 归一化单元口径
# ---------------------------------------------------------------------------


class TestNormalizeBaseUrl:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            # 正确写法保持不变
            ("https://api.siliconflow.cn/v1", "https://api.siliconflow.cn/v1"),
            ("https://dashscope.aliyuncs.com/api/paas/v4", "https://dashscope.aliyuncs.com/api/paas/v4"),
            ("https://api.moonshot.cn/v1/api/v3", "https://api.moonshot.cn/v1/api/v3"),
            ("https://api.example.com/v2", "https://api.example.com/v2"),
            # 尾部斜杠
            ("https://api.siliconflow.cn/v1/", "https://api.siliconflow.cn/v1"),
            ("  https://api.siliconflow.cn/v1  ", "https://api.siliconflow.cn/v1"),
            # 误填 chat 路径（本次故障的实际存量值）
            (
                "https://api.siliconflow.cn/v1/chat/completions",
                "https://api.siliconflow.cn/v1",
            ),
            (
                "https://api.siliconflow.cn/v1/chat/completions/",
                "https://api.siliconflow.cn/v1",
            ),
            ("https://api.example.com/v1/completions", "https://api.example.com/v1"),
            # 大小写
            (
                "https://api.example.com/v1/CHAT/COMPLETIONS",
                "https://api.example.com/v1",
            ),
            # 空值透传
            ("", ""),
            (None, ""),
        ],
    )
    def test_normalize(self, raw, expected):
        assert normalize_llm_base_url(raw) == expected


def test_normalize_llm_writes_normalized_base_url():
    """写路径（PUT /ai/config）落库前就削平，避免脏值再次进库。"""
    svc = AIConfigService.__new__(AIConfigService)

    result = svc._normalize_llm({"base_url": "https://api.siliconflow.cn/v1/chat/completions"})

    assert result["llm_base_url"] == "https://api.siliconflow.cn/v1"


async def test_preset_read_self_heals_legacy_row(db_session):
    """历史脏行不改库也能自愈：读出口统一归一。"""
    db_session.add(AIConfig(
        config_key=PRESET_CONFIGS_KEY,
        config_value=json.dumps({
            "openai": {
                "api_key": "sk-legacy",
                "base_url": "https://api.siliconflow.cn/v1/chat/completions",
                "model": "Qwen/Qwen3-8B",
            },
        }),
    ))
    await db_session.commit()

    raw = await AIConfigService(db_session)._get_preset_configs_raw()

    assert raw["openai"]["base_url"] == "https://api.siliconflow.cn/v1"
    # 原始行不被读操作改写
    row = (await db_session.execute(
        select(AIConfig).where(AIConfig.config_key == PRESET_CONFIGS_KEY)
    )).scalar_one()
    assert "/chat/completions" in row.config_value


async def test_preset_save_normalizes_on_write(db_session):
    svc = AIConfigService(db_session)

    await svc._save_preset_config(
        "preset:test", "sk-x", "https://api.example.com/v1/chat/completions/", "m"
    )
    await db_session.commit()

    row = (await db_session.execute(
        select(AIConfig).where(AIConfig.config_key == PRESET_CONFIGS_KEY)
    )).scalar_one()
    stored = json.loads(row.config_value)["preset:test"]
    assert stored["base_url"] == "https://api.example.com/v1"


# ---------------------------------------------------------------------------
# 测试连接的请求 URL 与错误文案
# ---------------------------------------------------------------------------


class _PostResp:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text

    def json(self):
        return {"usage": {}}


class _PostClient:
    def __init__(self, resp, seen):
        self._resp = resp
        self._seen = seen

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None, headers=None):
        self._seen.append(url)
        return self._resp


def _svc_no_db():
    svc = AIConfigService.__new__(AIConfigService)
    svc.db = None  # 传明文 key 时不触碰 db
    return svc


@pytest.mark.asyncio
async def test_test_connection_strips_chat_path(monkeypatch):
    """存量 `.../chat/completions` 不能再拼成双路径（原 404 假象的根因）。"""
    seen = []
    monkeypatch.setattr(
        svc_mod.httpx, "AsyncClient", lambda *a, **k: _PostClient(_PostResp(200), seen)
    )

    result = await _svc_no_db().test_llm_connection(
        "https://api.siliconflow.cn/v1/chat/completions", "sk-test", "Qwen/Qwen3-8B"
    )

    assert result["success"] is True
    assert seen == ["https://api.siliconflow.cn/v1/chat/completions"]


@pytest.mark.asyncio
async def test_test_connection_402_is_account_level(monkeypatch):
    seen = []
    monkeypatch.setattr(
        svc_mod.httpx,
        "AsyncClient",
        lambda *a, **k: _PostClient(
            _PostResp(402, '{"code":30001,"message":"Sorry, your account balance is insufficient"}'),
            seen,
        ),
    )

    result = await _svc_no_db().test_llm_connection("https://api.siliconflow.cn/v1", "sk-test", "m")

    assert result["success"] is False
    assert "余额不足" in result["message"]
    assert "更换提供商" in result["message"]


@pytest.mark.asyncio
async def test_test_connection_404_points_at_base_url(monkeypatch):
    seen = []
    monkeypatch.setattr(
        svc_mod.httpx, "AsyncClient", lambda *a, **k: _PostClient(_PostResp(404, "nf"), seen)
    )

    result = await _svc_no_db().test_llm_connection("https://api.example.com/v1", "sk-test", "m")

    assert result["success"] is False
    assert "不要填成" in result["message"]


@pytest.mark.asyncio
async def test_test_connection_5xx_says_upstream(monkeypatch):
    seen = []
    monkeypatch.setattr(
        svc_mod.httpx,
        "AsyncClient",
        lambda *a, **k: _PostClient(_PostResp(500, "get_channel_failed"), seen),
    )

    result = await _svc_no_db().test_llm_connection("https://apihub.agnes-ai.com/v1", "sk-test", "m")

    assert result["success"] is False
    assert "上游服务暂不可用" in result["message"]


# ---------------------------------------------------------------------------
# 频道接口：AI 失败必须可见
# ---------------------------------------------------------------------------


class _AccountLevelError(Exception):
    """模拟 OpenAI SDK 的 APIStatusError（402 余额不足）。"""

    status_code = 402


def _auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


@pytest.fixture
def stub_blacklist(monkeypatch):
    import app.core.auth

    async def _always_false(jti: str) -> bool:
        return False

    monkeypatch.setattr(app.core.auth, "is_in_blacklist", _always_false)


def _boom_prompts(name, description):
    raise _AccountLevelError("Error code: 402 - insufficient balance")


def test_create_channel_returns_ai_warning(client, admin_token, stub_blacklist, monkeypatch):
    """创建仍成功（不阻塞），但 AI 失败原因必须随响应返回。"""
    from app.services import channel_prompt_service as cps

    monkeypatch.setattr(cps, "generate_prompts_for_channel", _boom_prompts)

    resp = client.post(
        "/admin/api/v1/channels",
        json={"name": "T04117 告警频道", "channel_type": "news", "auto_generate_prompts": True},
        headers=_auth(admin_token),
    ).json()

    assert resp["code"] == 0, resp
    assert isinstance(resp["data"]["id"], int)
    warnings = resp["data"]["ai_generate_warnings"]
    assert any("频道提示词未自动生成" in w for w in warnings)
    # 账号级错误要走 account_error_hint，而不是裸异常文本
    assert any("余额不足" in w for w in warnings)


def test_create_channel_warns_when_only_search_prompt_fails(
    client, admin_token, stub_blacklist, monkeypatch
):
    """4 类播报提示词成功、搜索提示词失败：部分成功也要如实说明。"""
    from app.services import channel_prompt_service as cps

    async def _ok_prompts(name, description):
        return {
            "intro_prompt": "开场白",
            "outro_prompt": "结尾",
            "constraint_prompt": "约束",
            "rewrite_template": "模板",
        }

    monkeypatch.setattr(cps, "generate_prompts_for_channel", _ok_prompts)
    monkeypatch.setattr(cps, "generate_search_prompt_for_channel", _boom_prompts)

    resp = client.post(
        "/admin/api/v1/channels",
        json={"name": "T04117 搜索告警频道", "channel_type": "news", "auto_generate_prompts": True},
        headers=_auth(admin_token),
    ).json()

    assert resp["code"] == 0, resp
    assert resp["data"]["intro_prompt"] == "开场白"
    assert resp["data"]["search_prompt"] is None
    warnings = resp["data"]["ai_generate_warnings"]
    assert any("全网搜索提示词未生成" in w for w in warnings)


def test_generate_prompts_failure_returns_actionable_502(
    client, admin_token, stub_blacklist, monkeypatch
):
    """重新生成是用户显式动作，失败不能落成裸 500。"""
    from app.services import channel_prompt_service as cps

    created = client.post(
        "/admin/api/v1/channels",
        json={"name": "T04117 重新生成频道", "channel_type": "news"},
        headers=_auth(admin_token),
    ).json()
    cid = created["data"]["id"]

    monkeypatch.setattr(cps, "generate_prompts_for_channel", _boom_prompts)

    resp = client.post(
        f"/admin/api/v1/channels/{cid}/generate-prompts", headers=_auth(admin_token)
    ).json()

    assert resp["code"] == 502, resp
    assert "余额不足" in resp["message"]
