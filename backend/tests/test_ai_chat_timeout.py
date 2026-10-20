"""知识库问答超时与「超时可重试」（FR-UX-701 / T02515）。

为什么要单独成文件而不是塞进 test_ai_config_service.py：本组用例断言的是
「问答这条同步请求的时间预算」，它与批量任务的 LLM_TIMEOUT_SEC 是一对容易互相
污染的值——历史缺陷正是 /ai/chat 沿用 15s 全局前端超时 + 30s 后端批量超时，
模型还没答完就先炸，而且用户看到的是一句没有重试入口的网络错误。

与 apps/admin-web/tests/unit/ai-chat.test.mjs 互为对岸：那边锁前端的 130s 与
「后端必须先到点」，这边锁后端的 120s、关掉 SDK 自动重试、以及超时被归成可重试。
两边都由单测守住，任何一侧改值都会红。
"""

import httpx
import pytest
from openai import APITimeoutError

from app.config import get_settings
from app.services.ai_config_service import CONFIG_KEY_MAP, INT_KEYS, AIConfigService


def test_normalize_llm_persists_chat_timeout_sec():
    """写路径应把管理端表单的 chat_timeout_sec 落成 llm_chat_timeout_sec。

    T01729 的教训：PUT body 与 _normalize_llm 都是逐字段白名单，漏一个键就是
    「页面能改、保存不报错、值却不生效」，比直接报错更难发现。
    """
    service = AIConfigService.__new__(AIConfigService)

    result = service._normalize_llm({"chat_timeout_sec": 90})

    assert result["llm_chat_timeout_sec"] == "90"


def test_chat_timeout_registered_for_hot_apply():
    """热更链需要 CONFIG_KEY_MAP + INT_KEYS 双登记，缺一则设置不生效或类型错。"""
    assert CONFIG_KEY_MAP["llm_chat_timeout_sec"] == "LLM_CHAT_TIMEOUT_SEC"
    assert "llm_chat_timeout_sec" in INT_KEYS


async def test_put_then_get_roundtrip_chat_timeout_sec(client, admin_token):
    """API 级闭环：PUT 落库 + Settings 热更 + GET 回读（与段数上限同一条验证路径）。"""
    headers = {"Authorization": f"Bearer {admin_token['token']}"}

    current = client.get("/admin/api/v1/ai/config", headers=headers).json()["data"]
    assert current["llm"]["chat_timeout_sec"] == 120, "读路径没把问答超时返显给管理端"

    body = {
        "llm": {**current["llm"], "chat_timeout_sec": 95},
        "tts": current["tts"],
        "selected_preset": current["llm"].get("selected_preset", ""),
    }
    resp = client.put("/admin/api/v1/ai/config", json=body, headers=headers)
    assert resp.status_code == 200, resp.text

    assert get_settings().LLM_CHAT_TIMEOUT_SEC == 95, "热更新未生效（int 转换或 key 映射漏登记）"

    back = client.get("/admin/api/v1/ai/config", headers=headers).json()["data"]
    assert back["llm"]["chat_timeout_sec"] == 95

    # settings 是进程级单例，恢复默认防止污染同进程后续测试
    body["llm"]["chat_timeout_sec"] = 120
    client.put("/admin/api/v1/ai/config", json=body, headers=headers)
    assert get_settings().LLM_CHAT_TIMEOUT_SEC == 120


class _FakeCompletions:
    """替身：记录 create 收到的 timeout，并按脚本抛出/返回。"""

    def __init__(self, *, raise_exc=None, reply="好的"):
        self.raise_exc = raise_exc
        self.reply = reply
        self.timeouts = []
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        self.timeouts.append(kwargs.get("timeout"))
        if self.raise_exc:
            raise self.raise_exc
        usage = type("U", (), {"prompt_tokens": 1, "completion_tokens": 2})()
        msg = type("M", (), {"content": self.reply})()
        return type("R", (), {"choices": [type("C", (), {"message": msg})()], "usage": usage})()


class _FakeAsyncOpenAI:
    """替身：记住构造参数（用于断言 max_retries 被显式关掉）。"""

    last_kwargs = None
    completions = None

    def __init__(self, **kwargs):
        type(self).last_kwargs = kwargs
        self.chat = type("Chat", (), {"completions": type(self).completions})()


@pytest.fixture
def patch_openai(monkeypatch):
    def _apply(fake):
        import app.services.ai_config_service as mod

        _FakeAsyncOpenAI.completions = fake
        monkeypatch.setattr(mod, "AsyncOpenAI", _FakeAsyncOpenAI)
        return _FakeAsyncOpenAI

    return _apply


async def test_chat_uses_chat_timeout_and_disables_sdk_retry(patch_openai, monkeypatch):
    """问答必须用 LLM_CHAT_TIMEOUT_SEC，且关掉 SDK 自动重试。

    max_retries 默认是 2：120s × 3 次会跑到 360s，而前端只等 130s——
    先到点的是浏览器，用户既拿不到「可重试」提示，服务端那几次重试还在照样扣费。
    """
    fake = _FakeCompletions(reply="今天有三条新闻")
    patch_openai(fake)
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_CHAT_TIMEOUT_SEC", 111, raising=False)
    monkeypatch.setattr(settings, "LLM_TIMEOUT_SEC", 30, raising=False)

    service = AIConfigService.__new__(AIConfigService)
    result = await service.chat_with_model(
        base_url="https://example.test/v1",
        api_key="sk-not-masked",
        model="qwen-max",
        messages=[{"role": "user", "content": "今天有什么"}],
    )

    assert result["success"] is True
    assert fake.timeouts == [111.0], "问答没有用独立超时值（仍在吃批量任务的 LLM_TIMEOUT_SEC）"
    assert _FakeAsyncOpenAI.last_kwargs["max_retries"] == 0
    assert fake.calls == 1


async def test_chat_timeout_returns_retryable_hint(patch_openai, monkeypatch):
    """超时归成 timeout + retryable，并把「可重试」写进给用户的那句话里。"""
    err = APITimeoutError(request=httpx.Request("POST", "https://example.test/v1/chat/completions"))
    fake = _FakeCompletions(raise_exc=err)
    patch_openai(fake)
    monkeypatch.setattr(get_settings(), "LLM_CHAT_TIMEOUT_SEC", 111, raising=False)

    service = AIConfigService.__new__(AIConfigService)
    result = await service.chat_with_model(
        base_url="https://example.test/v1",
        api_key="sk-not-masked",
        model="qwen-max",
        messages=[{"role": "user", "content": "今天有什么"}],
    )

    assert result["success"] is False
    assert result["timeout"] is True
    assert result["retryable"] is True
    assert "重试" in result["message"]
    assert "111 秒" in result["message"], "提示要让用户知道等到哪儿停了"


async def test_auth_error_is_not_marked_retryable(patch_openai, monkeypatch):
    """鉴权类失败标 retryable=False：对同一个错反复重试没有意义，要的是去改配置。"""
    from openai import AuthenticationError

    req = httpx.Request("POST", "https://example.test/v1/chat/completions")
    resp = httpx.Response(status_code=401, request=req)
    fake = _FakeCompletions(raise_exc=AuthenticationError("bad key", response=resp))
    patch_openai(fake)
    monkeypatch.setattr(get_settings(), "LLM_CHAT_TIMEOUT_SEC", 111, raising=False)

    service = AIConfigService.__new__(AIConfigService)
    result = await service.chat_with_model(
        base_url="https://example.test/v1",
        api_key="sk-not-masked",
        model="qwen-max",
        messages=[{"role": "user", "content": "x"}],
    )

    assert result["success"] is False
    assert result["timeout"] is False
    assert result["retryable"] is False


async def test_non_openai_error_still_propagates(patch_openai, monkeypatch):
    """非 openai 异常继续抛出（原设计如此）：代码 bug 不该被兜底成「调用模型失败」。"""
    fake = _FakeCompletions(raise_exc=ZeroDivisionError("boom"))
    patch_openai(fake)
    monkeypatch.setattr(get_settings(), "LLM_CHAT_TIMEOUT_SEC", 111, raising=False)

    service = AIConfigService.__new__(AIConfigService)
    with pytest.raises(ZeroDivisionError):
        await service.chat_with_model(
            base_url="https://example.test/v1",
            api_key="sk-not-masked",
            model="qwen-max",
            messages=[{"role": "user", "content": "x"}],
        )
