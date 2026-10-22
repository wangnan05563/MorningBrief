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

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

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

    渠道凭证与判定口径统一走 `notifier.factory.build_configured_channels`（与 Hub/管理端一致），
    无渠道配置时返回 no-op；任何异常不向上抛出。
    """
    from app.services.notifier import NotificationEvent
    from app.services.notifier.factory import build_configured_channels
    from app.services.notification.config_service import NotificationConfigService

    log_entries: list[tuple[str, str, str]] = []
    try:
        config_svc = NotificationConfigService(db)
        # 口径与 Hub/管理端一致：走 is_configured() 形态校验，占位符凭证不算已配置（T02138）
        channels, _skipped = await build_configured_channels(
            config_svc, names=("dingtalk", "wecom")
        )
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

# json_extract 取出的 on：1=停服中，0=运行中，NULL=行不存在或 value 为空
_MAINT_ON = func.json_extract(SystemFlag.value, "$.on")


async def _claim_maintenance(db, target_on: bool, admin_name: str, value_dict: dict) -> bool:
    """原子地把维护态翻到 target_on；没抢下来返回 False（并发的另一击已经翻了）。

    为什么不写成「先 select 判断、再写」：移动端连点是两个同时在飞的请求，各自都读到
    旧状态，判重形同虚设（实测两击都返回 already=False、审计 2 条）；而且 SQLite 下
    读事务再升成写事务、撞上并发写时是**立刻** SQLITE_BUSY（busy_timeout 也不等），
    第二击直接变成 500。这里让事务以一条带条件的写语句开场：赢家 rowcount=1，
    输家要么 rowcount=0（行已在且状态不符），要么被主键挡回（行还不存在时）。
    """
    payload = json.dumps(value_dict, ensure_ascii=False)
    if target_on:
        cond = or_(_MAINT_ON.is_(None), _MAINT_ON != 1)
    else:
        cond = _MAINT_ON == 1
    res = await db.execute(
        update(SystemFlag)
        .where(SystemFlag.key == MAINTENANCE_KEY, cond)
        .values(value=payload, updated_by=admin_name)
    )
    if res.rowcount:
        return True
    if not target_on:
        # 解除：行不存在或本来就是运行态，本来就是目标态，不补一行垃圾数据
        return False
    ins = (
        sqlite_insert(SystemFlag)
        .values(key=MAINTENANCE_KEY, value=payload, updated_by=admin_name)
        .on_conflict_do_nothing(index_elements=["key"])
    )
    return (await db.execute(ins)).rowcount == 1


async def get_maintenance(db) -> dict:
    """读取维护态（结构化）。

    不需要 populate_existing：写路径用的是 ORM-enabled UPDATE/INSERT，
    AsyncSession 执行后会把该映射类的实例在身份图里过期，所以「写完立刻读」拿到的
    就是新值（这一点由 test_same_session_read_after_core_write_sees_new_state 钉住——
    探针实测：把 populate_existing 删掉、用例仍然全绿，说明这个执行选项在此并无用，
    留着只会让下一个人以为「不加就会读到脏的」，而事实不是）。
    """
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

    幂等（FR-UX-201）：已是停服态时返回当前状态（``already=True``），既不重写标志也不
    追加审计——否则连点会把首次停服时间/原因覆盖掉，审计里全是同名重复条目。

    INT-UX-06：判重不能靠「先读再写」，那只在两个请求不重叠时成立。真正的判定发生在
    ``_claim_maintenance`` 的那条条件写语句里：抢到了才写审计，抢不到就如实回 already。
    """
    claimed = await _claim_maintenance(
        db,
        True,
        admin.username,
        {
            "on": True,
            "reason": reason,
            "by": admin.username,
            "at": datetime.now().isoformat(),
        },
    )
    if claimed:
        db.add(
            AuditLog(
                category="mobile",
                action="emergency_stop",
                # target 留空时这条审计既按对象检索不到、也和状态里的原因对不上号（INT-UX-06）
                target=MAINTENANCE_KEY,
                operator=admin.username,
                detail=json.dumps(
                    {"reason": reason, "note": "emergency stop via mobile"}, ensure_ascii=False
                ),
            )
        )
        await db.flush()
    state = await get_maintenance(db)
    # 立即刷新进程内缓存，避免最长 5s 的守卫延迟；输家也按赢家落库后的真实状态刷
    with _maint_cache_lock:
        _maint_cache["value"] = state["enabled"]
        _maint_cache["ts"] = time.time()
    return {**state, "already": not claimed}


async def resume_maintenance(db, admin, reason: str = "") -> dict:
    """解除应急停服：关闭维护态标志 + 审计落库。

    与停服同一套判重（INT-UX-06）：本来就是运行态时不重写标志、也不堆审计，
    否则连点恢复会把「谁在何时恢复的」埋进一串重复条目里。
    """
    claimed = await _claim_maintenance(
        db,
        False,
        admin.username,
        {
            "on": False,
            "reason": reason or None,
            "by": admin.username,
            "at": datetime.now().isoformat(),
        },
    )
    if claimed:
        db.add(
            AuditLog(
                category="mobile",
                action="emergency_resume",
                target=MAINTENANCE_KEY,
                operator=admin.username,
                detail=json.dumps(
                    {"reason": reason, "note": "resume production via mobile"}, ensure_ascii=False
                ),
            )
        )
        await db.flush()
    state = await get_maintenance(db)
    with _maint_cache_lock:
        _maint_cache["value"] = state["enabled"]
        _maint_cache["ts"] = time.time()
    return {**state, "already": not claimed}


EMERGENCY_ACTIONS = ("emergency_stop", "emergency_resume")


async def emergency_audit(db, limit: int = 20) -> list[dict]:
    """停服 / 恢复操作记录（倒序）：值班要的是「谁、什么时候、因为什么」三列。

    这些数据一直有写，但唯一的审计接口 GET /db-admin/audit-log 硬过滤
    ``category='db_admin'``，停服写的是 ``category='mobile'``，任何界面都读不到
    ——写了等于没写（INT-UX-06）。这里按动作白名单取，不给越读他模块审计的口子。
    """
    limit = max(1, min(int(limit or 20), 100))
    rows = (
        (
            await db.execute(
                select(AuditLog)
                .where(AuditLog.category == "mobile", AuditLog.action.in_(EMERGENCY_ACTIONS))
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    items = []
    for r in rows:
        try:
            detail = json.loads(r.detail) if r.detail else {}
        except (json.JSONDecodeError, TypeError):
            detail = {}
        items.append(
            {
                "action": r.action,
                "operator": r.operator,
                "reason": detail.get("reason"),
                "at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return items
