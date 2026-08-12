"""B 端 SSE 事件流路由：将 EventBus 中的工作流/频道事件实时推送到前端。

设计要点：
- 每个连接独立 asyncio.Queue 缓冲，handler put_nowait 不阻塞 EventBus 主循环
- 连接断开时必须取消订阅，否则 handler 仍会被调用导致内存泄漏
- 15s 心跳防止代理超时（nginx 默认 60s 超时，留足余量）
- 队列满时丢弃最旧事件：客户端消费慢不应阻塞其他订阅者
- admin + operator 均可订阅（SSE 只读不写，与列表页权限一致）
"""
import asyncio
import json
import logging
from typing import AsyncIterator

import jwt
from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from app.core.auth import AdminPayload, ADMIN_TOKEN_COOKIE
from app.core.event_bus import Event, get_event_bus
from app.core.exceptions import AuthError
from app.core.security import decode_token
from app.services.blacklist_service import is_in_blacklist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/v1/events", tags=["B端-事件流"])

# SSE 关心的事件类型白名单：覆盖工作流状态机 + 频道启停
# 不直接订阅所有事件，避免无关事件占用带宽
_SUBSCRIBED_EVENTS = (
    "workflow.started",
    "workflow.completed",
    "workflow.failed",
    "workflow.step.completed",
    "workflow.step.failed",
    "channel.active_changed",
)

# 单连接缓冲区上限：超过则丢弃最旧事件
# 100 足以应对前端瞬时刷新延迟，过大会导致陈旧事件堆积
_MAX_QUEUE_SIZE = 100

# 心跳间隔：必须小于代理超时（nginx 默认 60s），15s 留足重连余量
_HEARTBEAT_INTERVAL = 15.0


async def _resolve_sse_admin(
    authorization: str | None,
    token: str | None,
    cookie_token: str | None = None,
) -> AdminPayload:
    """SSE 专用鉴权：优先 header，回退 query token，再回退 HttpOnly Cookie（NFR-M103）。

    EventSource API 不支持自定义 header；迁移后同源连接由浏览器自动携带 Cookie，
    前端不再拼接 ?token=xxx（避免 token 落入 URL/代理日志）。
    """
    raw = authorization
    if not raw and token:
        raw = f"Bearer {token}"
    if not raw and cookie_token:
        raw = f"Bearer {cookie_token}"
    if not raw:
        raise AuthError("缺少认证信息")
    raw_token = raw.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(raw_token)
    except jwt.ExpiredSignatureError:
        raise AuthError("登录已过期，请重新登录")
    except jwt.PyJWTError:
        raise AuthError("无效的认证信息")
    if payload.get("type") != "admin":
        raise AuthError("认证类型错误")
    jti = payload.get("jti", "")
    if await is_in_blacklist(jti):
        raise AuthError("登录已失效，请重新登录")
    return AdminPayload(
        admin_id=int(payload["sub"]),
        username=payload.get("username", ""),
        role=payload.get("role", "operator"),
        jti=jti,
        token_type=payload["type"],
        exp=int(payload.get("exp", 0)),
    )


@router.get("/stream")
async def event_stream(  # NOSONAR
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Query(None, description="EventSource 不支持 header 时的回退 token"),
):
    """SSE 端点：实时推送 EventBus 事件到前端。

    返回 text/event-stream，前端用 EventSource 订阅。
    连接断开（页面关闭/路由切换）时自动取消订阅。
    """
    # SSE 专用鉴权：不能用 Depends(get_current_admin)，因 EventSource 不传 header
    admin = await _resolve_sse_admin(authorization, token, request.cookies.get(ADMIN_TOKEN_COOKIE))
    bus = get_event_bus()
    queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)

    async def _on_event(event: Event) -> None:  # NOSONAR
        """EventBus handler：将事件放入连接私有队列。

        put_nowait 不阻塞 EventBus 主循环；队列满时丢弃最旧事件
        保留最新状态（前端最关心当前态而非历史轨迹）。
        """
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
                queue.put_nowait(event)
            except asyncio.QueueEmpty:
                pass  # 极端竞态，忽略

    async def _event_generator() -> AsyncIterator[str]:
        # subscribe 在 generator 内部执行，确保 generator 未被消费时不会泄漏订阅
        # 与 finally 中的 unsubscribe 严格配对
        for event_type in _SUBSCRIBED_EVENTS:
            bus.subscribe(event_type, _on_event)
        logger.debug("SSE 订阅建立 admin=%s events=%s", admin.username, _SUBSCRIBED_EVENTS)
        try:
            # 首帧：连接确认事件，前端据此切换到 SSE 模式（停止轮询）
            yield _format_sse({
                "type": "connected",
                "data": {"operator": admin.username},
            })
            heartbeat_seq = 0
            while True:
                # 客户端断开检测：避免对已关闭连接继续推送
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL)
                    yield _format_sse({
                        "type": event.type,
                        "data": event.data,
                        "timestamp": event.timestamp,
                    })
                except asyncio.TimeoutError:
                    # 心跳：维持连接活跃，防止代理/CDN 因空闲超时断开
                    heartbeat_seq += 1
                    yield _format_sse({
                        "type": "heartbeat",
                        "data": {"seq": heartbeat_seq},
                    })
        finally:
            # 无论正常退出还是异常，都要取消订阅以释放 handler 引用
            for event_type in _SUBSCRIBED_EVENTS:
                bus.unsubscribe(event_type, _on_event)
            logger.debug("SSE 订阅取消 admin=%s", admin.username)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # 禁用 nginx 缓冲：单机 exe 无 nginx 但预留生产部署兼容
            "X-Accel-Buffering": "no",
        },
    )


def _format_sse(payload: dict) -> str:
    """格式化为 SSE 数据帧。

    标准 SSE 格式：
        event: <type>
        data: <json>

    两个换行结尾表示事件结束。
    """
    event_type = payload.get("type", "message")
    # default=str 兜底 datetime/date 等非 JSON 原生类型
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {data}\n\n"
