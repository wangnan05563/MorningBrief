"""审计日志统一读口（T02909，派生自 T02529 / INT-UX-06）。

背景：写侧 15 个 category、37 处 `AuditLog(...)` 写入，读侧此前只有
`/db-admin/audit-log`（硬过滤 category='db_admin'）与移动端停服两条。backup /
maintenance / review / user 等高危动作写了等于没写，出事只能手工 sqlite3 捞表。

权限裁决（T02909）：**全量管理员可读**——不按模块切分。任何已登录管理员都能
按 category 读全部审计；非管理员/匿名一律 401（由路由依赖保证）。

脱敏边界：读侧复用 `db_admin_service._mask_audit_detail`。修复前写入的历史行
可能仍是明文，只有展示层也过滤，新读口才不会是第二条泄露通道（T02486 / T02591）。
"""
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.services.db_admin_service import _mask_audit_detail

# 写入口径的单一事实源：`backend/tests/test_t02909_audit_read.py` 会扫描源码里
# 所有 `category="..."`，漏登记的类别直接红。新增写入口时请同步这里。
AUDIT_CATEGORIES: tuple[str, ...] = (
    "ad",
    "ai",
    "audio",
    "backup",
    "channel",
    "cos",
    "db_admin",
    "maintenance",
    "material",
    "mobile",
    "queue",
    "review",
    "script",
    "user",
    "workflow",
)


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite 的 created_at 是 naive UTC（func.now()），带时区的入参先换算再比。"""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _serialize(row: AuditLog) -> dict:
    detail = row.detail
    if detail:
        try:
            detail = json.loads(detail)
        except (ValueError, TypeError):
            pass
    if isinstance(detail, (dict, list)):
        detail = _mask_audit_detail(detail, row.target)
    return {
        "id": row.id,
        "category": row.category,
        "action": row.action,
        "target": row.target,
        "operator": row.operator,
        "detail": detail,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_logs(
    db: AsyncSession,
    *,
    category: Optional[str] = None,
    action: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """按类别/动作/时间范围分页查询审计，倒序（新的在前）。"""
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 100))

    conds = []
    if category:
        conds.append(AuditLog.category == category)
    if action:
        conds.append(AuditLog.action == action)
    start_at, end_at = _naive_utc(start), _naive_utc(end)
    if start_at:
        conds.append(AuditLog.created_at >= start_at)
    if end_at:
        conds.append(AuditLog.created_at <= end_at)

    total = (
        await db.execute(select(func.count(AuditLog.id)).where(*conds))
    ).scalar_one()
    rows = (
        (
            await db.execute(
                select(AuditLog)
                .where(*conds)
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [_serialize(r) for r in rows],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
    }


async def category_summary(db: AsyncSession) -> dict:
    """各类别条数与最近一条时间；未落过库的类别也返回（count=0）。

    一次调用即可复核「所有写入类别都有读口」——这是验收用的可观测面。
    """
    rows = (
        await db.execute(
            select(
                AuditLog.category,
                func.count(AuditLog.id),
                func.max(AuditLog.created_at),
            ).group_by(AuditLog.category)
        )
    ).all()
    found = {
        c: {
            "category": c,
            "count": int(n),
            "latest_at": latest.isoformat() if latest else None,
        }
        for c, n, latest in rows
    }
    items = [
        found.get(c, {"category": c, "count": 0, "latest_at": None})
        for c in AUDIT_CATEGORIES
    ]
    return {"items": items, "registered": list(AUDIT_CATEGORIES)}
