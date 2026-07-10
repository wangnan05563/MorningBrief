"""EventBus 事件总线测试。

覆盖：
- subscribe/publish 基本流程
- 异常隔离：单个 handler 失败不影响其他
- publish_nowait 同步入队
- 多 handler 并发执行
- 无订阅者事件静默
- request_id 自动注入（从 ContextVar）
"""
import asyncio
from unittest.mock import patch

import pytest

from app.core.event_bus import EventBus, Event, get_event_bus


@pytest.fixture
def bus():
    """每个测试独立的 EventBus 实例。"""
    return EventBus()


@pytest.mark.asyncio
async def test_subscribe_and_publish(bus):
    """订阅后发布事件，handler 应被调用。"""
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe("test.event", handler)
    await bus.publish(Event(type="test.event", data={"k": "v"}))
    # 触发一次消费
    task = asyncio.create_task(bus.run_forever())
    await asyncio.sleep(0.2)
    bus.stop()
    await asyncio.sleep(1.2)  # 等待 run_forever 退出

    assert len(received) == 1
    assert received[0].data == {"k": "v"}


@pytest.mark.asyncio
async def test_handler_exception_isolation(bus):
    """单个 handler 失败不影响其他 handler。"""
    results = []

    async def good_handler(event: Event):
        results.append("good")

    async def bad_handler(event: Event):
        raise RuntimeError("handler 故障")

    bus.subscribe("test.isolation", bad_handler)
    bus.subscribe("test.isolation", good_handler)
    await bus.publish(Event(type="test.isolation"))

    task = asyncio.create_task(bus.run_forever())
    await asyncio.sleep(0.3)
    bus.stop()
    await asyncio.sleep(1.2)

    assert "good" in results


@pytest.mark.asyncio
async def test_publish_nowait(bus):
    """publish_nowait 同步入队，不阻塞。"""
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe("sync.event", handler)
    bus.publish_nowait(Event(type="sync.event"))

    task = asyncio.create_task(bus.run_forever())
    await asyncio.sleep(0.2)
    bus.stop()
    await asyncio.sleep(1.2)

    assert len(received) == 1


@pytest.mark.asyncio
async def test_multiple_handlers_all_called(bus):
    """同一事件类型多个 handler 都被调用。"""
    counter = {"a": 0, "b": 0}

    async def h_a(event: Event):
        counter["a"] += 1

    async def h_b(event: Event):
        counter["b"] += 1

    bus.subscribe("multi", h_a)
    bus.subscribe("multi", h_b)
    await bus.publish(Event(type="multi"))

    task = asyncio.create_task(bus.run_forever())
    await asyncio.sleep(0.3)
    bus.stop()
    await asyncio.sleep(1.2)

    assert counter["a"] == 1
    assert counter["b"] == 1


@pytest.mark.asyncio
async def test_unsubscribe(bus):
    """取消订阅后不再收到事件。"""
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe("unsub.event", handler)
    bus.unsubscribe("unsub.event", handler)
    await bus.publish(Event(type="unsub.event"))

    task = asyncio.create_task(bus.run_forever())
    await asyncio.sleep(0.2)
    bus.stop()
    await asyncio.sleep(1.2)

    assert len(received) == 0


@pytest.mark.asyncio
async def test_no_subscriber_silent(bus):
    """无订阅者的事件静默处理，不抛异常。"""
    await bus.publish(Event(type="nobody.cares"))

    task = asyncio.create_task(bus.run_forever())
    await asyncio.sleep(0.2)
    bus.stop()
    await asyncio.sleep(1.2)
    # 无异常即视为通过


@pytest.mark.asyncio
async def test_event_auto_timestamp(bus):
    """Event 未指定 timestamp 时自动填充当前时间。"""
    captured = []

    async def handler(event: Event):
        captured.append(event)

    bus.subscribe("ts.event", handler)
    await bus.publish(Event(type="ts.event"))

    task = asyncio.create_task(bus.run_forever())
    await asyncio.sleep(0.2)
    bus.stop()
    await asyncio.sleep(1.2)

    assert len(captured) == 1
    assert captured[0].timestamp > 0


@pytest.mark.asyncio
async def test_request_id_auto_injection(bus):
    """request_id 未设置时从 ContextVar 自动注入。"""
    captured = []

    async def handler(event: Event):
        captured.append(event)

    bus.subscribe("rid.event", handler)
    # mock get_request_id 返回固定值
    with patch("app.core.request_context.get_request_id", return_value="req-abc"):
        await bus.publish(Event(type="rid.event"))
        task = asyncio.create_task(bus.run_forever())
        await asyncio.sleep(0.3)
        bus.stop()
        await asyncio.sleep(1.2)

    assert len(captured) == 1
    assert captured[0].request_id == "req-abc"


def test_get_event_bus_singleton():
    """get_event_bus 返回全局单例。"""
    bus1 = get_event_bus()
    bus2 = get_event_bus()
    assert bus1 is bus2
