"""事件总线 - asyncio 实现的进程内事件分发（对标 17_xianyu event_bus.py）。

设计要点：
- 基于 asyncio.Queue 异步入队，主循环消费分发到订阅者
- 异常隔离：单个 handler 失败不影响其他 handler（_safe_call 捕获所有异常）
- request_id 自动注入：在 _dispatch（而非 publish）从 ContextVar 读取，
  因为 publish 只是入队，实际分发发生在异步任务恢复后

使用方式：
    bus = get_event_bus()
    bus.subscribe("workflow.completed", my_handler)
    await bus.publish(Event(type="workflow.completed", data={...}))
    await bus.run_forever()

与 17_xianyu 的差异：
- 不依赖 domain.events.EventType 枚举，用字符串作为事件类型更灵活
- Event 用 dataclass 简化，不绑定特定领域
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger

# 事件处理函数类型：async 函数，接收 Event 参数
EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]


@dataclass
class Event:
    """事件对象（对标 17_xianyu domain.events.Event）。

    用 dataclass 而非 pydantic 模型：事件是进程内传递的轻量数据结构，
    不需要序列化校验，dataclass 性能更好且无额外依赖。
    """
    type: str                          # 事件类型（如 "workflow.completed"）
    data: dict[str, Any] = field(default_factory=dict)  # 事件数据
    timestamp: float = 0.0            # 事件时间戳（Unix epoch）
    request_id: str | None = None     # 请求流水号（_dispatch 自动注入）

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).timestamp()


class EventBus:
    """基于 asyncio.Queue 的事件总线。

    异步分发：publish 只入队不阻塞调用方，run_forever 在后台消费。
    异常隔离：_safe_call 捕获所有异常，单个 handler 失败不影响其他。
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """订阅某类事件。

        同一事件类型可有多个 handler，按订阅顺序执行。
        """
        self._subscribers[event_type].append(handler)
        logger.trace("订阅 %s → %s", event_type, handler.__name__)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """取消订阅。"""
        if handler in self._subscribers.get(event_type, []):
            self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        """发布事件（异步入队，不阻塞调用方）。"""
        await self._queue.put(event)

    def publish_nowait(self, event: Event) -> None:
        """发布事件（同步入队，不阻塞）。

        用于不能 await 的场景（如同步回调中发布事件）。
        """
        self._queue.put_nowait(event)

    async def run_forever(self) -> None:
        """主循环：消费队列，分发到订阅者。

        应在 asyncio.create_task 中启动，shutdown 时调用 stop()。
        超时 1s 轮询一次，避免 stop() 时长时间等待。
        """
        self._running = True
        logger.info("EventBus 启动")
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            await self._dispatch(event)
        logger.info("EventBus 已停止")

    def stop(self) -> None:
        """停止主循环（设置标志位，run_forever 下次轮询时退出）。"""
        self._running = False

    async def _dispatch(self, event: Event) -> None:
        """分发事件到所有订阅者（异常隔离 + request_id 注入）。

        request_id 在 _dispatch 而非 publish 注入：
        publish 只是入队，实际分发发生在异步任务恢复后，
        此时 ContextVar 才是当前请求的作用域。
        """
        if not event.request_id:
            from app.core.request_context import get_request_id
            rid = get_request_id()
            if rid:
                event.request_id = rid

        handlers = self._subscribers.get(event.type, [])
        if not handlers:
            logger.debug("事件 %s 无订阅者", event.type)
            return

        # 并发执行所有 handler，单个失败不影响其他
        await asyncio.gather(
            *(self._safe_call(h, event) for h in handlers),
            return_exceptions=False,
        )

    @staticmethod
    async def _safe_call(handler: EventHandler, event: Event) -> None:
        """安全调用 handler，捕获所有异常防止单个 handler 崩溃影响其他。"""
        try:
            await handler(event)
        except Exception:
            logger.exception(
                "Handler %s 处理 %s 失败",
                handler.__name__, event.type,
            )


# 全局单例（与 cache.manager 一致的模块级单例模式）
_default_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取默认 EventBus 单例。

    首次调用时创建，后续调用返回同一实例。
    需在 lifespan 中启动 run_forever 任务。
    """
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus
