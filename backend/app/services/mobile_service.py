"""移动端适配服务层（SRS INT-M101~M105）。

承载移动端专属业务逻辑，复用现有 StatsService / Review / AuditLog / NotificationLog：
- push_admin_message：向某运营人员写入收件箱消息，并记录触达日志（notification_log），
  最佳努力经已配置 IM 渠道（钉钉/企微）fan-out 真实下发（无渠道配置时优雅 no-op）
- get_inbox / mark_read：运营消息收件箱的读取与标记已读
- register_device：设备登记 / 推送 token 注册（幂等 upsert，支撑推送与登录风控）
- dashboard_summary：移动首页聚合（今日指标 + 待审数 + 未读数），减少首屏并发
- emergency_stop / resume_maintenance / get_maintenance：应急停服（持久化维护态标志 + 审计），
  维护态经 SystemFlag 落库，并由 workflow_scheduler.trigger_workflow 守卫拒绝新任务触发

约定：服务层只做 ORM 操作（含 flush），由路由层统一 await db.commit()。
"""
import json
import logging
import threading
import time
from datetime import date, datetime
from typing import Optional

from sqlalchemy import func, select, update

from app.models.audit_log import AuditLog
from app.models.mobile import AdminDevice, AdminInbox
from app.models.notification_log import NotificationLog
from app.models.review import Review, ReviewStatus
from app.models.system_flag import SystemFlag
from app.services.stats_service import StatsService

logger = logging.getLogger(__name__)

# ---- 维护态标志 ----
MAINTENANCE_KEY = "maintenance_mode"
_maint_cache_lock = threading.Lock()
_maint_cache: dict = {"value": None, "ts": 0.0}
_MAINT_CACHE_TTL = 5  # 秒


def _serialize_message(row: AdminInbox) -> dict:
    """收件箱行 → 前端可消费结构（payload 安全反序列化）。"""
    payload = None
    if row.payload_json:
        try:
            payload = json.loads(row.payload_json)
        except (json.JSONDecodeError, TypeError):
            payload = None
    return {
        "id": row.id,
        "msg_type": row.msg_type,
        "level": row.level,
        "title": row.title,
        "body": row.body,
        "payload": payload,
        "read": row.read,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def push_admin_message(
    db,
    admin_id: int,
    msg_type: str,
    level: str,
    title: str,
    body: Optional[str] = None,
    payload: Optional[dict] = None,
) -> AdminInbox:
    """向某运营人员写入一条收件箱消息（内部可调用，供告警 / 审批待办触发）。

    真实触达：① 落地 AdminInbox；② 记 notification_log（inbox 渠道，success）；
    ③ 最佳努力经已配置 IM 渠道（钉钉/企微）fan-out 实际下发（仅 critical 级穿透）。
    """
    row = AdminInbox(
        admin_id=admin_id,
        msg_type=msg_type,
        level=level,
        title=title,
        body=body,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
    )
    db.add(row)
    await db.flush()

    # ① 收件箱触达日志
    db.add(
        NotificationLog(
            event_type="admin.inbox",
            channel="inbox",
            title=title,
            status="success",
            payload=json.dumps({"admin_id": admin_id, "level": level}, ensure_ascii=False),
        )
    )
    # ② 最佳努力 IM fan-out（critical 级穿透；无渠道配置时 no-op）
    if level == "critical":
        try:
            dispatch = await _dispatch_admin_alert(db, title, body or "", level)
            logger.info("运营告警 IM 下发 admin_id=%s result=%s", admin_id, dispatch)
        except Exception as e:  # 通知失败不影响主流程
            logger.warning("运营告警 IM 下发失败（已忽略）: %s", e)

    await db.flush()
    return row


async def _dispatch_admin_alert(db, title: str, body: str, level: str) -> dict:
    """最佳努力经已配置 IM 渠道（钉钉/企微）下发运营告警。

    直接复用现有 notifier 类与 ai_config 凭证（与 NotificationSender._collect_configured_channels 一致），
    无渠道配置时返回 no-op；任何异常不向上抛出。
    """
    from types import SimpleNamespace

    from app.services.notifier import NotificationEvent
    from app.services.notifier.channels.dingtalk import DingTalkNotifier
    from app.services.notifier.channels.wecom import WeComNotifier
    from app.services.notification.config_service import NotificationConfigService

    log_entries: list[tuple[str, str, str]] = []
    try:
        config_svc = NotificationConfigService(db)
        channels: list = []
        dt_webhook = await config_svc.get_raw_value("notify_dingtalk_webhook")
        dt_secret = await config_svc.get_raw_value("notify_dingtalk_secret")
        if dt_webhook:
            channels.append((
                "dingtalk",
                DingTalkNotifier(settings=SimpleNamespace(
                    ALERT_DINGTALK_WEBHOOK=dt_webhook,
                    ALERT_DINGTALK_SECRET=dt_secret,
                )),
            ))
        wecom_webhook = await config_svc.get_raw_value("notify_wecom_webhook")
        if wecom_webhook:
            channels.append((
                "wecom",
                WeComNotifier(settings=SimpleNamespace(ALERT_WECOM_WEBHOOK=wecom_webhook)),
            ))
        if not channels:
            return {"dispatched": 0, "note": "no_im_channel_configured"}

        event = NotificationEvent(
            title=title,
            message=body or "",
            severity="critical",
            source="mobile_admin",
            extra={},
        )
        for name, notifier in channels:
            try:
                res = await notifier.send(event)
                ok = getattr(res, "success", False)
                log_entries.append((name, "success" if ok else "failed", getattr(res, "error", "") or ""))
            except Exception as e:  # 单渠道失败不影响其他渠道
                log_entries.append((name, "failed", str(e)))
    except Exception as e:
        logger.warning("admin alert dispatch skipped: %s", e)
        return {"dispatched": 0, "note": f"dispatch_error: {e}"}

    # 记触达日志（满足 SRS 7.3 复用 notification_log）
    for name, status, err in log_entries:
        db.add(
            NotificationLog(
                event_type="admin.message",
                channel=name,
                title=title,
                status=status,
                error=err,
                payload=json.dumps({"level": level}, ensure_ascii=False),
            )
        )
    await db.flush()
    return {"dispatched": sum(1 for _, s, _ in log_entries if s == "success")}


async def get_inbox(
    db,
    admin_id: int,
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
) -> dict:
    """分页拉取收件箱，并附带未读总数（前端角标用）。"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    count_stmt = select(func.count(AdminInbox.id)).where(AdminInbox.admin_id == admin_id)
    if unread_only:
        count_stmt = count_stmt.where(AdminInbox.read.is_(False))
    total = (await db.execute(count_stmt)).scalar() or 0

    unread = (
        await db.execute(
            select(func.count(AdminInbox.id)).where(
                AdminInbox.admin_id == admin_id, AdminInbox.read.is_(False)
            )
        )
    ).scalar() or 0

    rows = (
        await db.execute(
            select(AdminInbox)
            .where(AdminInbox.admin_id == admin_id)
            .order_by(AdminInbox.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return {
        "items": [_serialize_message(r) for r in rows],
        "total": total,
        "unread_count": unread,
        "page": page,
        "page_size": page_size,
    }


async def mark_read(
    db,
    admin_id: int,
    message_ids: Optional[list[int]] = None,
    mark_all: bool = False,
) -> int:
    """标记已读：可指定消息 id 列表，或 mark_all 全部未读。返回受影响行数。"""
    stmt = update(AdminInbox).where(
        AdminInbox.admin_id == admin_id, AdminInbox.read.is_(False)
    )
    if not mark_all and message_ids:
        stmt = stmt.where(AdminInbox.id.in_(message_ids))
    # mark_all=True 时不再附加 id 条件，覆盖该 admin 全部未读
    result = await db.execute(stmt.values(read=True))
    await db.flush()
    return result.rowcount or 0


async def register_device(
    db,
    admin_id: int,
    platform: str,
    push_token: Optional[str] = None,
    device_fingerprint: Optional[str] = None,
) -> AdminDevice:
    """设备登记 / 推送 token 注册（幂等 upsert）。

    优先按 device_fingerprint 定位（登录风控用）；无指纹时按 (admin_id, platform, push_token) 定位。
    命中则更新字段，未命中则新增。
    """
    existing = None
    if device_fingerprint:
        existing = (
            await db.execute(
                select(AdminDevice).where(AdminDevice.device_fingerprint == device_fingerprint)
            )
        ).scalars().first()
    if existing is None and push_token:
        existing = (
            await db.execute(
                select(AdminDevice).where(
                    AdminDevice.admin_id == admin_id,
                    AdminDevice.platform == platform,
                    AdminDevice.push_token == push_token,
                )
            )
        ).scalars().first()
    if existing is not None:
        existing.platform = platform
        if push_token:
            existing.push_token = push_token
        if device_fingerprint:
            existing.device_fingerprint = device_fingerprint
        await db.flush()
        return existing

    row = AdminDevice(
        admin_id=admin_id,
        platform=platform,
        push_token=push_token,
        device_fingerprint=device_fingerprint,
    )
    db.add(row)
    await db.flush()
    return row


async def dashboard_summary(db, admin_id: int) -> dict:
    """移动首页聚合：今日指标 + 待审数 + 未读数，减少首屏并发请求。"""
    today_stats = await StatsService(db).get_overview(target_date=date.today())
    pending = (
        await db.execute(
            select(func.count(Review.id)).where(Review.status == ReviewStatus.pending.value)
        )
    ).scalar() or 0
    unread = (
        await db.execute(
            select(func.count(AdminInbox.id)).where(
                AdminInbox.admin_id == admin_id, AdminInbox.read.is_(False)
            )
        )
    ).scalar() or 0
    return {
        "today": today_stats,
        "pending_review": pending,
        "unread_message": unread,
    }


# ---- 维护态 / 应急停服 ----

async def _upsert_flag(db, key: str, value_dict: dict, admin_name: str) -> None:
    """写入 / 更新系统标志（JSON 值）。"""
    payload = json.dumps(value_dict, ensure_ascii=False)
    row = (
        await db.execute(select(SystemFlag).where(SystemFlag.key == key))
    ).scalars().first()
    if row is None:
        row = SystemFlag(key=key)
        db.add(row)
    row.value = payload
    row.updated_by = admin_name
    await db.flush()


async def get_maintenance(db) -> dict:
    """读取维护态（结构化）。"""
    row = (
        await db.execute(select(SystemFlag).where(SystemFlag.key == MAINTENANCE_KEY))
    ).scalars().first()
    if not row or not row.value:
        return {"enabled": False, "reason": None, "by": None, "at": None}
    try:
        d = json.loads(row.value)
    except (json.JSONDecodeError, TypeError):
        d = {}
    return {
        "enabled": bool(d.get("on", False)),
        "reason": d.get("reason"),
        "by": d.get("by"),
        "at": d.get("at"),
    }


async def is_maintenance_enabled(db) -> bool:
    """维护态判定（进程内缓存 TTL 5s，避免每次 trigger_workflow 都查库）。

    缓存未命中 / 过期时查库并回填；任何异常按"非维护态"处理，保证安全默认。
    """
    now = time.time()
    with _maint_cache_lock:
        cached = _maint_cache["value"]
        if cached is not None and now - _maint_cache["ts"] < _MAINT_CACHE_TTL:
            return cached
    on = False
    try:
        on = (await get_maintenance(db)).get("enabled", False)
    except Exception as e:
        logger.warning("读取维护态失败，按非维护态处理: %s", e)
        on = False
    with _maint_cache_lock:
        _maint_cache["value"] = on
        _maint_cache["ts"] = now
    return on


async def emergency_stop(db, admin, reason: str) -> dict:
    """应急停服：持久化维护态标志（on=true）+ 审计落库。

    高危操作——路由层已用 require_admin 限定超级管理员，并强制 reason 必填。
    维护态由 workflow_scheduler.trigger_workflow 守卫拒绝新任务触发（FR-M902）。
    """
    await _upsert_flag(
        db,
        MAINTENANCE_KEY,
        {
            "on": True,
            "reason": reason,
            "by": admin.username,
            "at": datetime.now().isoformat(),
        },
        admin.username,
    )
    db.add(
        AuditLog(
            category="mobile",
            action="emergency_stop",
            operator=admin.username,
            detail=json.dumps(
                {"reason": reason, "note": "emergency stop via mobile"}, ensure_ascii=False
            ),
        )
    )
    await db.flush()
    # 立即刷新进程内缓存，避免最长 5s 的守卫延迟
    with _maint_cache_lock:
        _maint_cache["value"] = True
        _maint_cache["ts"] = time.time()
    return await get_maintenance(db)


async def resume_maintenance(db, admin, reason: str = "") -> dict:
    """解除应急停服：关闭维护态标志 + 审计落库。"""
    await _upsert_flag(
        db,
        MAINTENANCE_KEY,
        {
            "on": False,
            "reason": reason or None,
            "by": admin.username,
            "at": datetime.now().isoformat(),
        },
        admin.username,
    )
    db.add(
        AuditLog(
            category="mobile",
            action="emergency_resume",
            operator=admin.username,
            detail=json.dumps(
                {"reason": reason, "note": "resume production via mobile"}, ensure_ascii=False
            ),
        )
    )
    await db.flush()
    with _maint_cache_lock:
        _maint_cache["value"] = False
        _maint_cache["ts"] = time.time()
    return await get_maintenance(db)
