"""AI 模型列表拉取 & 问答逻辑单测。

覆盖：
- _parse_models 解析（对象数组 / 字符串数组 / 去重排序 / 非法输入）
- fetch_llm_models 错误路径（401 / 不可达 / 404 回退 / 解析失败）
- fetch_llm_models 正常路径（模型解析 + 自动回退 /v1/models）
"""
import json
from unittest.mock import MagicMock, AsyncMock

import httpx
import pytest

import app.services.ai_config_service as svc_mod
from app.services.ai_config_service import AIConfigService


# ---- 解析辅助 ----

def test_parse_models_object_list():
    payload = {
        "object": "list",
        "data": [
            {"id": "gpt-4o", "owned_by": "openai"},
            {"id": "gpt-4o-mini", "owned_by": "openai"},
            {"id": "gpt-4o"},  # 缺 owned_by
        ],
    }
    out = AIConfigService._parse_models(payload)
    ids = [m["id"] for m in out]
    assert ids == ["gpt-4o", "gpt-4o-mini"]  # 排序 + 去重
    assert out[0]["owned_by"] == "openai"


def test_parse_models_string_list():
    out = AIConfigService._parse_models({"data": ["a", "b", "a"]})
    assert [m["id"] for m in out] == ["a", "b"]


def test_parse_models_invalid():
    assert AIConfigService._parse_models({}) == []
    assert AIConfigService._parse_models("not dict") == []
    assert AIConfigService._parse_models({"data": "nope"}) == []


# ---- 枚举/构造 fake httpx ----

class FakeResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class FakeClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None):
        return self._resp


class FailClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None):
        raise httpx.ConnectError("boom")


def _svc():
    svc = AIConfigService.__new__(AIConfigService)
    svc.db = MagicMock()
    return svc


@pytest.mark.asyncio
async def test_fetch_401(monkeypatch):
    monkeypatch.setattr(
        svc_mod.httpx, "AsyncClient", lambda *a, **k: FakeClient(FakeResp(401, text="unauthorized"))
    )
    result = await _svc().fetch_llm_models(base_url="https://api.openai.com/v1", api_key="sk-bad")
    assert result["success"] is False
    assert "401" in result["message"]


@pytest.mark.asyncio
async def test_fetch_unreachable(monkeypatch):
    monkeypatch.setattr(svc_mod.httpx, "AsyncClient", lambda *a, **k: FailClient())
    result = await _svc().fetch_llm_models(
        base_url="https://bad.example.com/v1", api_key="sk-ok"
    )
    assert result["success"] is False
    assert "无法连接" in result["message"]


@pytest.mark.asyncio
async def test_fetch_ok(monkeypatch):
    payload = {"object": "list", "data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}
    monkeypatch.setattr(
        svc_mod.httpx, "AsyncClient", lambda *a, **k: FakeClient(FakeResp(200, payload))
    )
    result = await _svc().fetch_llm_models(base_url="https://api.openai.com/v1", api_key="sk-ok")
    assert result["success"] is True
    assert len(result["models"]) == 2


@pytest.mark.asyncio
async def test_fetch_404_fallback(monkeypatch):
    # 第一次候选 /models 返回 404，回退到 /v1/models 成功
    class SeqClient:
        def __init__(self):
            self.n = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            self.n += 1
            if self.n == 1:
                return FakeResp(404, text="nf")
            return FakeResp(200, {"data": [{"id": "m1"}]})

    monkeypatch.setattr(svc_mod.httpx, "AsyncClient", lambda *a, **k: SeqClient())
    result = await _svc().fetch_llm_models(base_url="https://x.com/api", api_key="sk-ok")
    assert result["success"] is True
    assert result["models"][0]["id"] == "m1"


@pytest.mark.asyncio
async def test_fetch_bad_json(monkeypatch):
    monkeypatch.setattr(
        svc_mod.httpx, "AsyncClient", lambda *a, **k: FakeClient(FakeResp(200, None, "html"))
    )
    result = await _svc().fetch_llm_models(base_url="https://x.com/v1", api_key="sk-ok")
    assert result["success"] is False
    assert "JSON" in result["message"]


@pytest.mark.asyncio
async def test_fetch_empty_models(monkeypatch):
    monkeypatch.setattr(
        svc_mod.httpx, "AsyncClient", lambda *a, **k: FakeClient(FakeResp(200, {"data": []}))
    )
    result = await _svc().fetch_llm_models(base_url="https://x.com/v1", api_key="sk-ok")
    assert result["success"] is False
    assert "空" in result["message"]


@pytest.mark.asyncio
async def test_fetch_no_api_key(monkeypatch):
    # 未传 api_key 且 DB/settings 均无保存 → 明确提示未配置
    class FakeSettings:
        LLM_API_KEY = ""
        LLM_BASE_URL = ""
        LLM_TIMEOUT_SEC = 30

    monkeypatch.setattr(svc_mod, "get_settings", lambda: FakeSettings())
    svc = _svc()
    svc.get_config_value = AsyncMock(return_value=None)
    monkeypatch.setattr(svc_mod.httpx, "AsyncClient", lambda *a, **k: FailClient())
    result = await svc.fetch_llm_models(base_url="https://x.com/v1", api_key="")
    assert result["success"] is False
    assert "API Key" in result["message"]
