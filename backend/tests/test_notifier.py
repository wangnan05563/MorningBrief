"""通知器模块测试。

覆盖：
- NotifierRegistry register/create/contains/list_channels
- WeComNotifier is_configured/send（mock httpx）
- DingTalkNotifier 加签 URL 计算（mock httpx）
- EmailNotifier send（mock smtplib）
- NotifierHub fan-out / 免打扰 / critical 穿透

为避免真实网络调用，所有 httpx.AsyncClient.post 和 smtplib 连接均 mock。
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notifier.base import INotifier, NotificationEvent, NotifyResult
from app.services.notifier.hub import NotifierHub, get_notifier_hub
from app.services.notifier.registry import NotifierRegistry


# ====================== Registry 测试 ======================

class _DummyNotifier(INotifier):
    """测试用桩通知器。"""

    def __init__(self, **kwargs):
        self._kwargs = kwargs

    @property
    def name(self) -> str:
        return "dummy"

    async def send(self, event: NotificationEvent) -> NotifyResult:
        return NotifyResult(channel="dummy", success=True)

    def is_configured(self) -> bool:
        return True


def test_registry_register_and_create():
    """装饰器注册 + 工厂方法实例化。"""
    reg = NotifierRegistry()

    @reg.register("dummy")
    class Dummy(INotifier):
        @property
        def name(self): return "dummy"

        async def send(self, event): return NotifyResult(channel="dummy", success=True)

        def is_configured(self): return True

    assert reg.contains("dummy")
    instance = reg.create("dummy")
    assert isinstance(instance, INotifier)


def test_registry_create_unknown_raises():
    """未注册的渠道 create 抛 KeyError。"""
    reg = NotifierRegistry()
    with pytest.raises(KeyError):
        reg.create("not_registered")


def test_registry_rejects_non_inotifier():
    """register 拒绝非 INotifier 子类。"""
    reg = NotifierRegistry()
    with pytest.raises(TypeError):
        reg.register("bad")(object)


def test_registry_list_channels():
    """list_channels 返回已注册渠道名列表。"""
    reg = NotifierRegistry()

    @reg.register("ch1")
    class Ch1(_DummyNotifier):
        @property
        def name(self): return "ch1"

    @reg.register("ch2")
    class Ch2(_DummyNotifier):
        @property
        def name(self): return "ch2"

    channels = reg.list_channels()
    assert "ch1" in channels
    assert "ch2" in channels


# ====================== WeComNotifier 测试 ======================

def _make_settings(**kwargs):
    """构造测试 Settings 对象。"""
    defaults = {
        "ALERT_WECOM_WEBHOOK": "",
        "ALERT_DINGTALK_WEBHOOK": "",
        "ALERT_DINGTALK_SECRET": "",
        "ALERT_EMAIL_SMTP_HOST": "",
        "ALERT_EMAIL_SMTP_PORT": 587,
        "ALERT_EMAIL_SMTP_USER": "",
        "ALERT_EMAIL_SMTP_PASSWORD": "",
        "ALERT_EMAIL_TO": "",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_wecom_is_configured_with_real_webhook():
    """配置真实 webhook 时 is_configured=True。"""
    from app.services.notifier.channels.wecom import WeComNotifier
    settings = _make_settings(ALERT_WECOM_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send/xxx")
    notifier = WeComNotifier(settings=settings)
    assert notifier.is_configured() is True


def test_wecom_not_configured_with_placeholder():
    """占位符 webhook 视为未配置。"""
    from app.services.notifier.channels.wecom import WeComNotifier
    settings = _make_settings(ALERT_WECOM_WEBHOOK="https://example.com/webhook")
    notifier = WeComNotifier(settings=settings)
    assert notifier.is_configured() is False


def test_wecom_not_configured_empty():
    """空 webhook 视为未配置。"""
    from app.services.notifier.channels.wecom import WeComNotifier
    settings = _make_settings(ALERT_WECOM_WEBHOOK="")
    notifier = WeComNotifier(settings=settings)
    assert notifier.is_configured() is False


@pytest.mark.asyncio
async def test_wecom_send_success():
    """企微 webhook 成功响应返回 success=True。"""
    from app.services.notifier.channels.wecom import WeComNotifier
    settings = _make_settings(ALERT_WECOM_WEBHOOK="https://qyapi.weixin.qq.com/real")
    notifier = WeComNotifier(settings=settings)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}

    with patch("app.services.notifier.channels.wecom.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        event = NotificationEvent(title="测试告警", message="内容", severity="critical", source="test")
        result = await notifier.send(event)

    assert result.success is True
    assert result.channel == "wecom"


@pytest.mark.asyncio
async def test_wecom_send_api_error():
    """企微返回 errcode 非 0 时 success=False。"""
    from app.services.notifier.channels.wecom import WeComNotifier
    settings = _make_settings(ALERT_WECOM_WEBHOOK="https://qyapi.weixin.qq.com/real")
    notifier = WeComNotifier(settings=settings)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errcode": 93000, "errmsg": "invalid webhook"}

    with patch("app.services.notifier.channels.wecom.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await notifier.send(NotificationEvent(title="t", message="m"))

    assert result.success is False
    assert "invalid webhook" in result.error


# ====================== DingTalkNotifier 测试 ======================

def test_dingtalk_is_configured():
    """钉钉真实 webhook 时 is_configured=True。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    settings = _make_settings(ALERT_DINGTALK_WEBHOOK="https://oapi.dingtalk.com/robot/send")
    notifier = DingTalkNotifier(settings=settings)
    assert notifier.is_configured() is True


def test_dingtalk_sign_url_with_secret():
    """配置 secret 时 _sign_url 附加 timestamp 和 sign 参数。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    settings = _make_settings(
        ALERT_DINGTALK_WEBHOOK="https://oapi.dingtalk.com/robot/send?access_token=xxx",
        ALERT_DINGTALK_SECRET="SECxxx",
    )
    notifier = DingTalkNotifier(settings=settings)
    signed_url = notifier._sign_url()
    assert "timestamp=" in signed_url
    assert "sign=" in signed_url


def test_dingtalk_sign_url_without_secret():
    """未配置 secret 时 _sign_url 返回原 webhook。"""
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    settings = _make_settings(ALERT_DINGTALK_WEBHOOK="https://oapi.dingtalk.com/robot/send?access_token=xxx")
    notifier = DingTalkNotifier(settings=settings)
    assert notifier._sign_url() == settings.ALERT_DINGTALK_WEBHOOK


# ====================== EmailNotifier 测试 ======================

def test_email_is_configured_all_fields():
    """所有 SMTP 字段齐全时 is_configured=True。"""
    from app.services.notifier.channels.email import EmailNotifier
    settings = _make_settings(
        ALERT_EMAIL_SMTP_HOST="smtp.example.com",
        ALERT_EMAIL_SMTP_PORT=587,
        ALERT_EMAIL_SMTP_USER="alert@example.com",
        ALERT_EMAIL_SMTP_PASSWORD="pass",
        ALERT_EMAIL_TO="ops@example.com",
    )
    notifier = EmailNotifier(settings=settings)
    assert notifier.is_configured() is True


def test_email_not_configured_missing_fields():
    """缺少任一字段时 is_configured=False。"""
    from app.services.notifier.channels.email import EmailNotifier
    settings = _make_settings(
        ALERT_EMAIL_SMTP_HOST="smtp.example.com",
        ALERT_EMAIL_SMTP_USER="",
        ALERT_EMAIL_SMTP_PASSWORD="pass",
        ALERT_EMAIL_TO="ops@example.com",
    )
    notifier = EmailNotifier(settings=settings)
    assert notifier.is_configured() is False


@pytest.mark.asyncio
async def test_email_send_success():
    """邮件发送成功调用 SMTP starttls。"""
    from app.services.notifier.channels.email import EmailNotifier
    settings = _make_settings(
        ALERT_EMAIL_SMTP_HOST="smtp.example.com",
        ALERT_EMAIL_SMTP_PORT=587,
        ALERT_EMAIL_SMTP_USER="alert@example.com",
        ALERT_EMAIL_SMTP_PASSWORD="pass",
        ALERT_EMAIL_TO="ops@example.com",
    )
    notifier = EmailNotifier(settings=settings)

    mock_server = MagicMock()
    mock_server.starttls = MagicMock()
    mock_server.login = MagicMock()
    mock_server.sendmail = MagicMock()
    mock_server.__enter__ = MagicMock(return_value=mock_server)
    mock_server.__exit__ = MagicMock(return_value=None)

    with patch("app.services.notifier.channels.email.smtplib.SMTP", return_value=mock_server):
        result = await notifier.send(NotificationEvent(title="告警", message="内容", severity="important"))

    assert result.success is True
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("alert@example.com", "pass")


@pytest.mark.asyncio
async def test_email_send_ssl_port():
    """端口 465 使用 SMTP_SSL 直连。"""
    from app.services.notifier.channels.email import EmailNotifier
    settings = _make_settings(
        ALERT_EMAIL_SMTP_HOST="smtp.example.com",
        ALERT_EMAIL_SMTP_PORT=465,
        ALERT_EMAIL_SMTP_USER="alert@example.com",
        ALERT_EMAIL_SMTP_PASSWORD="pass",
        ALERT_EMAIL_TO="ops@example.com",
    )
    notifier = EmailNotifier(settings=settings)

    mock_server = MagicMock()
    mock_server.login = MagicMock()
    mock_server.sendmail = MagicMock()
    mock_server.__enter__ = MagicMock(return_value=mock_server)
    mock_server.__exit__ = MagicMock(return_value=None)

    with patch("app.services.notifier.channels.email.smtplib.SMTP_SSL", return_value=mock_server) as mock_ssl:
        result = await notifier.send(NotificationEvent(title="t", message="m"))

    assert result.success is True
    mock_ssl.assert_called_once()


# ====================== NotifierHub 测试 ======================

@pytest.fixture
def fresh_hub():
    """每个测试独立的 NotifierHub（不走全局单例）。"""
    return NotifierHub()


def test_hub_no_channels_returns_zero(fresh_hub):
    """无已配置渠道时 send 返回 total=0。

    mock get_settings 返回全占位符配置，确保 _init_channels 加载 0 个渠道。
    避免测试环境 .env 中有真实 webhook 配置导致渠道被加载。
    """
    import asyncio
    # mock settings 全为空/占位符，确保所有渠道 is_configured=False
    empty_settings = _make_settings(
        ALERT_WECOM_WEBHOOK="",
        ALERT_DINGTALK_WEBHOOK="",
        ALERT_EMAIL_SMTP_HOST="",
        ALERT_EMAIL_TO="",
    )
    event = NotificationEvent(title="t", message="m")

    async def _run():
        with patch("app.services.notifier.hub.get_settings", return_value=empty_settings):
            return await fresh_hub.send(event)

    result = asyncio.run(_run())
    assert result["total"] == 0
    assert result["success"] == 0


def test_hub_quiet_hours_suppresses_non_critical(fresh_hub):
    """免打扰时段非 critical 事件被静默。"""
    fresh_hub._init_channels()
    # 手动塞入一个 mock 渠道绕过 is_configured
    mock_channel = AsyncMock(spec=INotifier)
    mock_channel.name = "mock"
    mock_channel.send = AsyncMock(return_value=NotifyResult(channel="mock", success=True))
    fresh_hub._channels = [mock_channel]
    fresh_hub._quiet_start_hour = 0
    fresh_hub._quiet_end_hour = 24  # 全天免打扰

    import asyncio
    event = NotificationEvent(title="t", message="m", severity="info")

    async def _run():
        return await fresh_hub.send(event)

    result = asyncio.run(_run())
    assert result["suppressed"] == 1
    assert result["success"] == 0
    mock_channel.send.assert_not_called()


def test_hub_critical_bypasses_quiet_hours(fresh_hub):
    """critical 事件穿透免打扰。"""
    mock_channel = AsyncMock(spec=INotifier)
    mock_channel.name = "mock"
    mock_channel.send = AsyncMock(return_value=NotifyResult(channel="mock", success=True))
    fresh_hub._channels = [mock_channel]
    fresh_hub._quiet_start_hour = 0
    fresh_hub._quiet_end_hour = 24  # 全天免打扰

    import asyncio
    event = NotificationEvent(title="t", message="m", severity="critical")

    async def _run():
        return await fresh_hub.send(event)

    result = asyncio.run(_run())
    assert result["success"] == 1
    assert result["suppressed"] == 0
    mock_channel.send.assert_called_once()


def test_hub_is_quiet_hours_cross_midnight():
    """跨午夜免打扰区间判定。"""
    from datetime import datetime, timezone

    hub = NotifierHub()
    hub._quiet_start_hour = 22
    hub._quiet_end_hour = 8

    # mock UTC 时间 23:00（在免打扰区间）
    with patch("app.services.notifier.hub.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc)
        assert hub._is_quiet_hours() is True

    # mock UTC 时间 03:00（在免打扰区间）
    with patch("app.services.notifier.hub.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
        assert hub._is_quiet_hours() is True

    # mock UTC 时间 10:00（不在免打扰区间）
    with patch("app.services.notifier.hub.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        assert hub._is_quiet_hours() is False


def test_get_notifier_hub_singleton():
    """get_notifier_hub 返回全局单例。"""
    hub1 = get_notifier_hub()
    hub2 = get_notifier_hub()
    assert hub1 is hub2
