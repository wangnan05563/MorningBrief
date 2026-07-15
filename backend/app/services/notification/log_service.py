"""通知日志服务：查询日志 + 失败重发。

日志记录每条通知的实际发送结果（success/failed/suppressed），
suppressed 状态用于审计开关关闭/频次去重场景，证明通知被有意跳过而非遗漏。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_log import NotificationLog


class LogService:
    """通知日志查询与重发服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict[str, Any]:
        """分页查询日志列表（按创建时间倒序）。

        返回 {items: [...], total: N, page: N, page_size: N}。
        """
        conditions = []
        if event_type:
            conditions.append(NotificationLog.event_type == event_type)
        if status:
            conditions.append(NotificationLog.status == status)

        # 总数
        count_query = select(func.count(NotificationLog.id))
        if conditions:
            count_query = count_query.where(*conditions)
        total = (await self.db.execute(count_query)).scalar_one()

        # 分页查询
        query = select(NotificationLog).order_by(desc(NotificationLog.created_at))
        if conditions:
            query = query.where(*conditions)
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await self.db.execute(query)
        rows = result.scalars().all()

        return {
            "items": [
                {
                    "id": row.id,
                    "event_type": row.event_type,
                    "channel": row.channel,
                    "title": row.title,
                    "status": row.status,
                    "error": row.error,
                    "payload": row.payload,
                    "workflow_id": row.workflow_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_log(self, log_id: int) -> Optional[NotificationLog]:
        """按 ID 获取日志。"""
        result = await self.db.execute(
            select(NotificationLog).where(NotificationLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def create_log(
        self,
        event_type: str,
        channel: str,
        title: str,
        status: str,
        error: str = "",
        payload: Optional[dict] = None,
        workflow_id: str = "",
    ) -> NotificationLog:
        """创建日志记录。

        payload 序列化为 JSON 字符串存储，便于审计与重发时还原变量上下文。
        """
        log = NotificationLog(
            event_type=event_type,
            channel=channel,
            title=title,
            status=status,
            error=error,
            payload=json.dumps(payload or {}, ensure_ascii=False),
            workflow_id=workflow_id,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def get_payload(self, log_id: int) -> Optional[dict]:
        """获取日志的 payload（反序列化为 dict），用于重发。"""
        log = await self.get_log(log_id)
        if log is None or not log.payload:
            return None
        try:
            return json.loads(log.payload)
        except (json.JSONDecodeError, TypeError):
            return None
