"""通知模块集成测试。

验证 WorkflowScheduler._send_notification 与 NotificationSender 的集成行为：
- 成功路径：sender 返回 success，不触发降级告警
- 降级路径 1：sender 返回 failed，触发 _alert_operators 兜底
- 降级路径 2：sender 抛异常，触发 _alert_operators 兜底，不向上抛出
- 参数传递：extra_vars 正确传递到 sender

测试目标：确保工作流异常时通知一定能送达（结构化通知失败 → 通用告警兜底）。
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.workflow_scheduler import WorkflowScheduler


@pytest.fixture
def scheduler():
    """WorkflowScheduler 实例（conftest 已 stub AsyncIOScheduler）。"""
    return WorkflowScheduler()


# ====================== _send_notification 集成测试 ======================

@pytest.mark.asyncio
async def test_send_notification_calls_sender(scheduler):
    """_send_notification 成功调用 sender.send_workflow_event。"""
    mock_sender = AsyncMock()
    mock_sender.send_workflow_event = AsyncMock(return_value={
        "status": "success",
        "message": "发送成功",
        "success": 1,
        "failed": 0,
    })

    with patch(
        "app.services.notification.get_notification_sender",
        return_value=mock_sender,
    ), patch.object(
        scheduler, "_alert_operators", new=AsyncMock(),
    ) as mock_alert:
        await scheduler._send_notification(
            "workflow.pending_review", "wf-integration-1",
        )

    # 验证 sender 被正确调用
    mock_sender.send_workflow_event.assert_called_once_with(
        "workflow.pending_review", "wf-integration-1", None,
    )
    # 成功路径不触发降级告警
    mock_alert.assert_not_called()


@pytest.mark.asyncio
async def test_send_notification_fallback_on_failed(scheduler):
    """sender 返回 failed 时降级调用 _alert_operators。"""
    mock_sender = AsyncMock()
    mock_sender.send_workflow_event = AsyncMock(return_value={
        "status": "failed",
        "message": "webhook 未配置",
        "success": 0,
        "failed": 1,
    })

    with patch(
        "app.services.notification.get_notification_sender",
        return_value=mock_sender,
    ), patch.object(
        scheduler, "_alert_operators", new=AsyncMock(),
    ) as mock_alert:
        await scheduler._send_notification(
            "workflow.failed", "wf-integration-2",
            {"failed_step": "stitch", "error_message": "concat failed"},
        )

    # 验证 sender 被调用（含 extra_vars）
    mock_sender.send_workflow_event.assert_called_once_with(
        "workflow.failed", "wf-integration-2",
        {"failed_step": "stitch", "error_message": "concat failed"},
    )
    # failed 状态触发降级告警
    mock_alert.assert_called_once()
    # 告警消息包含 workflow_id 和 event_type
    alert_msg = mock_alert.call_args[0][0]
    assert "wf-integration-2" in alert_msg
    assert "workflow.failed" in alert_msg


@pytest.mark.asyncio
async def test_send_notification_fallback_on_exception(scheduler):
    """sender 抛异常时降级调用 _alert_operators，不向上抛出。"""
    mock_sender = AsyncMock()
    mock_sender.send_workflow_event = AsyncMock(
        side_effect=RuntimeError("sender 初始化失败"),
    )

    with patch(
        "app.services.notification.get_notification_sender",
        return_value=mock_sender,
    ), patch.object(
        scheduler, "_alert_operators", new=AsyncMock(),
    ) as mock_alert:
        # 异常不向上抛出（_send_notification 内部捕获）
        await scheduler._send_notification(
            "workflow.pending_review", "wf-integration-3",
        )

    # 异常触发降级告警
    mock_alert.assert_called_once()
    alert_msg = mock_alert.call_args[0][0]
    assert "wf-integration-3" in alert_msg
    assert "异常" in alert_msg


@pytest.mark.asyncio
async def test_send_notification_passes_extra_vars(scheduler):
    """extra_vars 正确传递到 sender。"""
    mock_sender = AsyncMock()
    mock_sender.send_workflow_event = AsyncMock(return_value={
        "status": "success", "message": "ok", "success": 1, "failed": 0,
    })

    with patch(
        "app.services.notification.get_notification_sender",
        return_value=mock_sender,
    ), patch.object(
        scheduler, "_alert_operators", new=AsyncMock(),
    ):
        extra = {"failed_step": "rewrite", "error_message": "LLM 超时"}
        await scheduler._send_notification(
            "workflow.failed", "wf-4", extra,
        )

    mock_sender.send_workflow_event.assert_called_once_with(
        "workflow.failed", "wf-4", extra,
    )


@pytest.mark.asyncio
async def test_send_notification_none_extra_vars(scheduler):
    """extra_vars=None 时正确传递（不传额外变量）。"""
    mock_sender = AsyncMock()
    mock_sender.send_workflow_event = AsyncMock(return_value={
        "status": "success", "message": "ok", "success": 1, "failed": 0,
    })

    with patch(
        "app.services.notification.get_notification_sender",
        return_value=mock_sender,
    ), patch.object(
        scheduler, "_alert_operators", new=AsyncMock(),
    ):
        await scheduler._send_notification("workflow.published", "wf-5")

    mock_sender.send_workflow_event.assert_called_once_with(
        "workflow.published", "wf-5", None,
    )


# ====================== 通知事件类型覆盖测试 ======================

@pytest.mark.parametrize("event_type", [
    "workflow.pending_review",
    "workflow.failed",
    "workflow.published",
])
@pytest.mark.asyncio
async def test_send_notification_all_event_types(scheduler, event_type):
    """3 种事件类型都能正确调用 sender。"""
    mock_sender = AsyncMock()
    mock_sender.send_workflow_event = AsyncMock(return_value={
        "status": "success", "message": "ok", "success": 1, "failed": 0,
    })

    with patch(
        "app.services.notification.get_notification_sender",
        return_value=mock_sender,
    ), patch.object(
        scheduler, "_alert_operators", new=AsyncMock(),
    ):
        await scheduler._send_notification(event_type, "wf-param-test")

    mock_sender.send_workflow_event.assert_called_once_with(
        event_type, "wf-param-test", None,
    )
