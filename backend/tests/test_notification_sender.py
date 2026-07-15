"""通知发送器编排逻辑测试。

覆盖：
- 开关检查：全局/场景开关关闭时返回 suppressed
- 频次去重：5 分钟内重复发送返回 suppressed
- 模板缺失：自愈 seed 后发送成功
- 发送成功/失败：mock DingTalkNotifier.send
- 异常不向上抛出

测试策略：
- patch AsyncSessionLocal 让 sender 使用测试 db_session
- 预先 seed 模板与配置（含 webhook）
- mock DingTalkNotifier.send 控制成功/失败
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from app.services.notification.sender import NotificationSender, _dedup_cache


@asynccontextmanager
async def _fake_session_ctx(db_session):
    """让 sender 内部 AsyncSessionLocal() 返回测试 db_session。"""
    yield db_session


def _patch_session(db_session):
    """patch sender 模块的 AsyncSessionLocal 为测试 session。"""
    return patch(
        "app.services.notification.sender.AsyncSessionLocal",
        lambda: _fake_session_ctx(db_session),
    )


async def _seed_template_and_enable(db_session):
    """seed 预设模板并开启全局+场景开关 + 配置 webhook。"""
    from app.services.notification.template_service import TemplateService
    from app.services.notification.config_service import NotificationConfigService

    svc = TemplateService(db_session)
    await svc.seed_preset_templates()

    config_svc = NotificationConfigService(db_session)
    await config_svc.save_config({
        "global_enabled": True,
        "failed_enabled": True,
        "review_enabled": True,
        "published_enabled": True,
        "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=test",
        "dingtalk_secret": "SECtest",
    })


def _mock_dingtalk_send_success():
    """mock DingTalkNotifier.send 返回成功。"""
    from app.services.notifier.base import NotifyResult
    return AsyncMock(return_value=NotifyResult(channel="dingtalk", success=True))


def _mock_dingtalk_send_failure():
    """mock DingTalkNotifier.send 返回失败。"""
    from app.services.notifier.base import NotifyResult
    return AsyncMock(return_value=NotifyResult(
        channel="dingtalk", success=False, error="webhook 错误",
    ))


# ====================== 开关检查测试 ======================

@pytest.mark.asyncio
async def test_send_global_disabled_returns_suppressed(db_session):
    """全局开关关闭时返回 suppressed。"""
    await _seed_template_and_enable(db_session)
    from app.services.notification.config_service import NotificationConfigService
    await NotificationConfigService(db_session).save_config({"global_enabled": False})

    sender = NotificationSender()
    with _patch_session(db_session), patch(
        "app.services.notifier.channels.dingtalk.DingTalkNotifier.send",
        new=_mock_dingtalk_send_success(),
    ):
        result = await sender.send_workflow_event("workflow.pending_review", "wf-1")

    assert result["status"] == "suppressed"


@pytest.mark.asyncio
async def test_send_scene_disabled_returns_suppressed(db_session):
    """场景开关关闭时返回 suppressed。"""
    await _seed_template_and_enable(db_session)
    from app.services.notification.config_service import NotificationConfigService
    await NotificationConfigService(db_session).save_config({"review_enabled": False})

    sender = NotificationSender()
    with _patch_session(db_session), patch(
        "app.services.notifier.channels.dingtalk.DingTalkNotifier.send",
        new=_mock_dingtalk_send_success(),
    ):
        result = await sender.send_workflow_event("workflow.pending_review", "wf-1")

    assert result["status"] == "suppressed"


# ====================== 频次去重测试 ======================

@pytest.mark.asyncio
async def test_send_dedup_returns_suppressed(db_session):
    """5 分钟内重复发送返回 suppressed。"""
    await _seed_template_and_enable(db_session)
    import time
    _dedup_cache[("workflow.pending_review", "wf-1")] = time.time()

    try:
        sender = NotificationSender()
        with _patch_session(db_session), patch(
            "app.services.notifier.channels.dingtalk.DingTalkNotifier.send",
            new=_mock_dingtalk_send_success(),
        ):
            result = await sender.send_workflow_event("workflow.pending_review", "wf-1")

        assert result["status"] == "suppressed"
        assert "去重" in result["message"]
    finally:
        _dedup_cache.clear()


# ====================== 模板缺失测试 ======================

@pytest.mark.asyncio
async def test_send_no_template_auto_seed_then_success(db_session):
    """未 seed 模板时自愈 seed 后发送成功。"""
    from app.services.notification.config_service import NotificationConfigService
    await NotificationConfigService(db_session).save_config({
        "global_enabled": True,
        "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=test",
        "dingtalk_secret": "SECtest",
    })

    sender = NotificationSender()
    with _patch_session(db_session), patch(
        "app.services.notifier.channels.dingtalk.DingTalkNotifier.send",
        new=_mock_dingtalk_send_success(),
    ):
        result = await sender.send_workflow_event("workflow.pending_review", "wf-1")

    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_send_unknown_event_type_returns_failed(db_session):
    """非预设事件类型（自愈 seed 也不会有）返回 failed。"""
    from app.services.notification.config_service import NotificationConfigService
    await NotificationConfigService(db_session).save_config({
        "global_enabled": True,
        "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=test",
    })

    sender = NotificationSender()
    with _patch_session(db_session), patch(
        "app.services.notifier.channels.dingtalk.DingTalkNotifier.send",
        new=_mock_dingtalk_send_success(),
    ):
        result = await sender.send_workflow_event("workflow.unknown_event", "wf-1")

    assert result["status"] == "failed"
    assert "模板" in result["message"]


# ====================== 发送成功/失败测试 ======================

@pytest.mark.asyncio
async def test_send_success(db_session):
    """发送成功返回 success 并标记去重缓存。"""
    await _seed_template_and_enable(db_session)
    _dedup_cache.clear()

    sender = NotificationSender()
    with _patch_session(db_session), patch(
        "app.services.notifier.channels.dingtalk.DingTalkNotifier.send",
        new=_mock_dingtalk_send_success(),
    ):
        result = await sender.send_workflow_event("workflow.pending_review", "wf-1")

    assert result["status"] == "success"
    assert ("workflow.pending_review", "wf-1") in _dedup_cache
    _dedup_cache.clear()


@pytest.mark.asyncio
async def test_send_dingtalk_failure_returns_failed(db_session):
    """DingTalkNotifier.send 失败时返回 failed。"""
    await _seed_template_and_enable(db_session)
    _dedup_cache.clear()

    sender = NotificationSender()
    with _patch_session(db_session), patch(
        "app.services.notifier.channels.dingtalk.DingTalkNotifier.send",
        new=_mock_dingtalk_send_failure(),
    ):
        result = await sender.send_workflow_event("workflow.failed", "wf-1")

    assert result["status"] == "failed"
    assert "webhook 错误" in result["message"]
    assert ("workflow.failed", "wf-1") not in _dedup_cache


# ====================== 异常不向上抛出测试 ======================

@pytest.mark.asyncio
async def test_send_exception_does_not_raise(db_session):
    """send_workflow_event 内部异常不向上抛出。"""
    await _seed_template_and_enable(db_session)
    _dedup_cache.clear()

    sender = NotificationSender()
    with _patch_session(db_session), patch(
        "app.services.notifier.channels.dingtalk.DingTalkNotifier.send",
        side_effect=RuntimeError("notor 初始化失败"),
    ):
        result = await sender.send_workflow_event("workflow.pending_review", "wf-1")

    assert result["status"] == "failed"


# ====================== webhook 缺失测试 ======================

@pytest.mark.asyncio
async def test_send_no_webhook_returns_failed(db_session):
    """未配置 webhook 时返回 failed（含友好错误信息）。"""
    from app.services.notification.template_service import TemplateService
    from app.services.notification.config_service import NotificationConfigService

    await TemplateService(db_session).seed_preset_templates()
    # 只开开关，不配 webhook
    await NotificationConfigService(db_session).save_config({"global_enabled": True})

    sender = NotificationSender()
    with _patch_session(db_session):
        result = await sender.send_workflow_event("workflow.pending_review", "wf-1")

    assert result["status"] == "failed"
    assert "Webhook" in result["message"] or "webhook" in result["message"]


# ====================== send_test 测试 ======================

@pytest.mark.asyncio
async def test_send_test_success(db_session):
    """send_test 从 ai_config 表读取 webhook，临时创建 notifier 发送。"""
    from app.services.notification.config_service import NotificationConfigService
    await NotificationConfigService(db_session).save_config({
        "global_enabled": True,
        "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=test",
        "dingtalk_secret": "SECtest",
    })

    sender = NotificationSender()
    with _patch_session(db_session), patch(
        "app.services.notifier.channels.dingtalk.DingTalkNotifier.send",
        new=_mock_dingtalk_send_success(),
    ):
        result = await sender.send_test()

    assert result["success"] is True


@pytest.mark.asyncio
async def test_send_test_no_webhook_returns_failed(db_session):
    """send_test 未配置 webhook 时返回友好错误。"""
    sender = NotificationSender()
    with _patch_session(db_session):
        result = await sender.send_test()

    assert result["success"] is False
    assert "未配置" in result["message"]


# ====================== resend_log 测试 ======================

@pytest.mark.asyncio
async def test_resend_log_success(db_session):
    """resend_log 用日志 payload 重新渲染并发送。"""
    from app.services.notification.log_service import LogService
    from app.services.notification.template_service import TemplateService
    from app.services.notification.config_service import NotificationConfigService

    await TemplateService(db_session).seed_preset_templates()
    await NotificationConfigService(db_session).save_config({
        "global_enabled": True,
        "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=test",
    })

    log_svc = LogService(db_session)
    log = await log_svc.create_log(
        event_type="workflow.failed", channel="dingtalk",
        title="原始标题", status="failed", error="err",
        payload={"workflow_id": "wf-1", "error_message": "原始错误"},
        workflow_id="wf-1",
    )

    sender = NotificationSender()
    with _patch_session(db_session), patch(
        "app.services.notifier.channels.dingtalk.DingTalkNotifier.send",
        new=_mock_dingtalk_send_success(),
    ):
        result = await sender.resend_log(log.id)

    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_resend_log_not_found(db_session):
    """resend_log 不存在的日志返回 failed。"""
    sender = NotificationSender()
    with _patch_session(db_session):
        result = await sender.resend_log(99999)

    assert result["status"] == "failed"
    assert "不存在" in result["message"]
