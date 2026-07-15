"""钉钉通知器 actionCard 升级测试。

覆盖：
- _build_payload：actionCard 模式（有 action_url）
- _build_payload：markdown 降级模式（无 action_url）
- 标题截断到 24 字符
- send 方法：成功/失败/未配置/网络异常

测试目标：确保 actionCard 与 markdown 两种模式正确切换。
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notifier.base import NotificationEvent, NotifyResult


def _make_settings(**kwargs):
    """构造测试 Settings 对象。"""
    defaults = {
        "ALERT_DINGTALK_WEBHOOK": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
        "ALERT_DINGTALK_SECRET": "",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_event(**kwargs):
    """构造 NotificationEvent，默认带 action_url（actionCard 模式）。"""
    defaults = {
        "title": "📰 新闻频道 2026-07-14 待审核",
        "message": "## 待审核\n工作流 wf-001 已完成",
        "severity": "critical",
        "source": "notification_sender",
        "extra": {
            "action_url": "https://example.com/review/1",
            "action_title": "前往审核",
            "audio_url": "https://example.com/audio.mp3",
        },
    }
    defaults.update(kwargs)
    return NotificationEvent(**defaults)


# ====================== _build_payload 测试 ======================

def test_build_payload_actioncard_with_action_url():
    """有 action_url 时构建 actionCard payload。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    notifier = DingTalkNotifier(settings=_make_settings())
    event = _make_event()
    payload = notifier._build_payload(event)

    assert payload["msgtype"] == "actionCard"
    assert payload["actionCard"]["title"] == event.title
    assert payload["actionCard"]["text"] == event.message
    assert payload["actionCard"]["singleTitle"] == "前往审核"
    assert payload["actionCard"]["singleURL"] == "https://example.com/review/1"


def test_build_payload_markdown_without_action_url():
    """无 action_url 时降级为 markdown。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    notifier = DingTalkNotifier(settings=_make_settings())
    event = _make_event(extra={"action_url": "", "action_title": ""})
    payload = notifier._build_payload(event)

    assert payload["msgtype"] == "markdown"
    assert "markdown" in payload
    assert payload["markdown"]["text"].startswith("### ")
    assert event.title in payload["markdown"]["text"]


def test_build_payload_title_truncated_to_24():
    """标题超 24 字符时截断。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    notifier = DingTalkNotifier(settings=_make_settings())
    long_title = "这是一个非常非常非常非常非常长的标题超过二十四字符应该被截断"
    event = _make_event(title=long_title)
    payload = notifier._build_payload(event)

    assert len(payload["actionCard"]["title"]) == 24
    assert payload["actionCard"]["title"] == long_title[:24]


def test_build_payload_title_not_truncated_when_short():
    """短标题不截断。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    notifier = DingTalkNotifier(settings=_make_settings())
    short_title = "短标题"
    event = _make_event(title=short_title)
    payload = notifier._build_payload(event)
    assert payload["actionCard"]["title"] == short_title


def test_build_payload_default_action_title():
    """action_title 为空时默认 '查看详情'。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    notifier = DingTalkNotifier(settings=_make_settings())
    event = _make_event(extra={"action_url": "https://x.com", "action_title": ""})
    payload = notifier._build_payload(event)
    assert payload["actionCard"]["singleTitle"] == "查看详情"


def test_build_payload_markdown_includes_severity_emoji():
    """markdown 模式按 severity 显示 emoji。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    notifier = DingTalkNotifier(settings=_make_settings())
    event = _make_event(
        severity="critical",
        extra={"action_url": ""},
    )
    payload = notifier._build_payload(event)
    assert "🔴" in payload["markdown"]["text"]


# ====================== send 方法测试 ======================

@pytest.mark.asyncio
async def test_send_actioncard_success():
    """actionCard 模式发送成功。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    notifier = DingTalkNotifier(settings=_make_settings())

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}

    with patch("app.services.notifier.channels.dingtalk.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await notifier.send(_make_event())

    assert result.success is True
    assert result.channel == "dingtalk"
    # 验证 post 调用的 payload 是 actionCard
    mock_client.post.assert_called_once()
    sent_payload = mock_client.post.call_args.kwargs.get("json", {})
    assert sent_payload["msgtype"] == "actionCard"


@pytest.mark.asyncio
async def test_send_not_configured():
    """未配置 webhook 时返回失败。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    notifier = DingTalkNotifier(settings=_make_settings(ALERT_DINGTALK_WEBHOOK=""))
    result = await notifier.send(_make_event())
    assert result.success is False
    assert "未配置" in result.error


@pytest.mark.asyncio
async def test_send_api_error():
    """钉钉返回 errcode 非 0 时失败。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    notifier = DingTalkNotifier(settings=_make_settings())

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errcode": 300001, "errmsg": "token is invalid"}

    with patch("app.services.notifier.channels.dingtalk.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await notifier.send(_make_event())

    assert result.success is False
    assert "token is invalid" in result.error


@pytest.mark.asyncio
async def test_send_timeout():
    """请求超时返回失败。"""
    import httpx
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    notifier = DingTalkNotifier(settings=_make_settings())

    with patch("app.services.notifier.channels.dingtalk.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await notifier.send(_make_event())

    assert result.success is False
    assert "超时" in result.error


@pytest.mark.asyncio
async def test_send_http_error_status():
    """HTTP 状态码非 200 时失败。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    notifier = DingTalkNotifier(settings=_make_settings())

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("app.services.notifier.channels.dingtalk.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await notifier.send(_make_event())

    assert result.success is False
    assert "HTTP 500" in result.error
