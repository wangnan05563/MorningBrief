"""T00914 D11 补充：content_security_service.check_text 对微信 result 字符串的兼容单测。

背景：验证隔离流程发现，微信 msgSecCheck 返回的 result 字段在部分合法场景下可能是
字符串而非数组，旧代码直接 `item.get` 导致 AttributeError，把 content_security 合并
整体拖垮（fail-closed），安全门禁无法把检测结果写回 workflow_step。本组单测验证：
result 为字符串时不再崩溃，视为无违规项，正常返回检测完成结果。
"""
import pytest

from app.services.content_security_service import ContentSecurityService


@pytest.fixture
def mock_wx(monkeypatch):
    """把微信 access_token 与 msgSecCheck POST 都替换为可控桩。"""

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeClient:
        def __init__(self, payload):
            self._payload = payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *args, **kwargs):
            return _Resp(self._payload)

    async def _fake_token():
        return "fake_token"

    monkeypatch.setattr(ContentSecurityService, "_get_access_token", _fake_token)

    payload_box = {}

    import httpx
    class _ClientWrapper:
        def __init__(self, *a, **k):
            self._timeout = k.get("timeout")
        async def __aenter__(self):
            return _FakeClient(payload_box.get("payload", {}))
        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(httpx, "AsyncClient", _ClientWrapper)
    return payload_box


@pytest.mark.asyncio
async def test_result_as_string_does_not_crash(mock_wx):
    """result 为字符串（异常但合法响应）时不得崩溃，应视为无违规并通过。"""
    mock_wx["payload"] = {
        "errcode": 0,
        "errmsg": "ok",
        "result": "pass",  # 触发旧代码 AttributeError 的形状
    }
    res = await ContentSecurityService.check_text("测试文本", openid="o-abc")
    assert res["safe"] is True
    assert res["skipped"] is False
    assert res["detail"] == []


@pytest.mark.asyncio
async def test_result_as_plain_string(mock_wx):
    """result 为任意非 list 字符串时同断容错，判定安全不崩溃。"""
    mock_wx["payload"] = {"errcode": 0, "result": "risky-string"}
    res = await ContentSecurityService.check_text("今天天气不错")
    assert res["safe"] is True
    assert res["detail"] == []


@pytest.mark.asyncio
async def test_result_normal_list_still_flagged(mock_wx):
    """保持既有行为：result 为正常数组且命中 risky 时仍返回不安全。"""
    mock_wx["payload"] = {
        "errcode": 0,
        "result": [{"trace_id": "t1", "suggest": "risky", "label": 21000}],
    }
    res = await ContentSecurityService.check_text("含违规内容的稿件", openid="o-1")
    assert res["safe"] is False
    assert res["detail"][0]["label"] == 21000
    assert res["skipped"] is False


@pytest.mark.asyncio
async def test_empty_content_skips_without_api():
    """空内容直接跳过，不触碰微信 API，也不需要 token。"""
    res = await ContentSecurityService.check_text("  ")
    assert res["safe"] is True
    assert res["skipped"] is True