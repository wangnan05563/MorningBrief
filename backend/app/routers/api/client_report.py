"""C 端客户端告警上报路由（FR-MC-12 后续增强）。

POST /api/v1/client/report
接收小程序端 best-effort 上报的客户端告警（如 skin.normalizeType 检测到的
未知 channel_type），便于服务端集中发现「后端误下发未知类型」等问题。

设计原则：
- 匿名可用（无需登录），但受全局 RateLimitMiddleware 限流保护，防刷。
- 仅做结构校验 + 服务端结构化 logging（[client_report] 前缀），不落库，
  避免引入新表与迁移；如需持久化聚合（看板/告警），后续可加 client_reports 表。
- 失败绝不影响端上体验：端上 reportClientWarn 为 fire-and-forget，本端点
  即便 4xx/5xx 也不回传任何会影响 UI 的信息。
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from app.core.response import success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/client", tags=["C端-客户端告警"])


class ClientReportIn(BaseModel):
    """客户端告警上报体。

    category：告警类别（如 unknown_channel_type），≤64 字符。
    message：人读描述，≤1024 字符。
    payload：可选结构化上下文（如 {unknown_type:'xxx'}），序列化后 ≤4KB。
    client_ts：可选客户端时间戳（毫秒），用于服务端时序对齐。
    """

    category: str = Field(min_length=1, max_length=64)
    message: str = Field(max_length=1024)
    payload: Optional[dict] = None
    client_ts: Optional[int] = None

    @field_validator("payload")
    @classmethod
    def _cap_payload(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("payload 必须为对象")
        if len(json.dumps(v, ensure_ascii=False)) > 4096:
            raise ValueError("payload 过大（≤4KB）")
        return v


@router.post("/report")
async def report_client_event(body: ClientReportIn, request: Request):
    """接收客户端告警并结构化记录到服务端日志。

    不要求鉴权：告警本身可能就源于鉴权/配置异常，且匿名上报足以支撑「集中发现」。
    全局限流中间件已按 IP 滑动窗口限流，避免被滥用。
    """
    client_ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")[:256]
    logger.warning(
        "[client_report] category=%s message=%s payload=%s client_ts=%s ip=%s ua=%s",
        body.category,
        body.message,
        json.dumps(body.payload or {}, ensure_ascii=False),
        body.client_ts,
        client_ip,
        ua,
    )
    return success(data={"accepted": True}, message="received")
