"""移动端适配服务层（SRS INT-M101~M105）。

承载移动端专属业务逻辑，复用现有 StatsService / Review / AuditLog / NotificationLog：
- push_admin_message：向某运营人员写入收件箱消息，并记录触达日志（notification_log），
  最佳努力经已配置 IM 渠道（钉钉/企微）fan-out 真实下发（无渠道配置时优雅 no-op）
- notify_workflow_event：把「待审核 / 执行失败」两个需要人处置的工作流事件写进全体 admin 的收件箱
- get_inbox / mark_read：运营消息收件箱的读取与标记已读
- register_device：设备登记 / 推送 token 注册（幂等 upsert，支撑推送与登录风控）
- dashboard_summary：移动首页聚合（今日指标 + 待审数 + 未读数），减少首屏并发
- emergency_stop / resume_maintenance / get_maintenance：应急停服（持久化维护态标志 + 审计），
  维护态经 SystemFlag 落库，并由 workflow_scheduler.trigger_workflow 守卫拒绝新任务触发

约定：服务层只做 ORM 操作（含 flush），由路由层统一 await db.commit()。
"""
import asyncio
import json
import logging
import threading
import time
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.timeutil import localnow_naive
from app.models.admin_user import AdminRole, AdminUser
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
# 降级告警只在「健康 → 读失败」的跃迁发一次，恢复后重置（见 is_maintenance_enabled）
_maint_degraded = False


def _notify_maintenance_check_failed(error_type: str) -> None:
    """维护态检查降级告警（critical，走 NotifierHub 已配置渠道）。

    与内网穿透启动失败同法：守护线程里 asyncio.run，不阻塞 trigger_workflow；
    渠道未配置时 hub 内部 no-op。仅首次降级调用，避免数据库持续故障时刷屏。
    """
    def _send() -> None:
        try:
            from app.services.notifier.base import NotificationEvent
            from app.services.notifier.hub import get_notifier_hub

            event = NotificationEvent(
                title="维护态检查失败，新任务已按停服处理",
                message=(
                    f"读取维护态标志失败（{error_type}）。\n"
                    "数据库恢复前，新工作流触发会被拒绝（fail-closed）；"
                    "若这并非预期停服，请检查数据库连通性。"
                ),
                severity="critical",
                source="workflow_scheduler",
                extra={"error_type": error_type},
            )
            asyncio.run(get_notifier_hub().send(event))
        except Exception:
            logger.exception("发送维护态降级告警失败")

    threading.Thread(
        target=_send, daemon=True, name="maintenance-degrade-alert"
    ).start()


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
    dedup_key: Optional[str] = None,
    dispatch_im: bool = True,
) -> Optional[AdminInbox]:
    """向某运营人员写入一条收件箱消息（内部可调用，供告警 / 审批待办触发）。

    真实触达：① 落地 AdminInbox；② 记 notification_log（inbox 渠道，success）；
    ③ dispatch_im 且 level=critical 时，最佳努力经已配置 IM 渠道 fan-out。

    幂等：dedup_key 非空时按 (admin_id, msg_type, dedup_key) 唯一索引去重。
    重放命中已有消息返回 None——不写触达日志、也不重复 IM 下发，
    调用方据此知道「这次没有真正新增」。NULL 键不参与去重（手工/测试写入）。
    """
    values = {
        "admin_id": admin_id,
        "msg_type": msg_type,
        "level": level,
        "title": title,
        "body": body,
        "payload_json": json.dumps(payload, ensure_ascii=False) if payload else None,
        # 显式写本地时间：列的 server_default CURRENT_TIMESTAMP 是 UTC，与按天清理的
        # cutoff、移动端展示都对不上（同 Workflow 模型的既有结论）。存量行仍是 UTC，
        # 90 天窗口下 8 小时偏差不影响保留语义。
        "created_at": localnow_naive(),
    }
    if dedup_key:
        values["dedup_key"] = dedup_key
        inserted = (
            await db.execute(
                sqlite_insert(AdminInbox)
                .values(**values)
                .on_conflict_do_nothing(
                    index_elements=["admin_id", "msg_type", "dedup_key"]
                )
            )
        ).rowcount
        if not inserted:
            return None
        row = (
            await db.execute(
                select(AdminInbox).where(
                    AdminInbox.admin_id == admin_id,
                    AdminInbox.msg_type == msg_type,
                    AdminInbox.dedup_key == dedup_key,
                )
            )
        ).scalars().one()
    else:
        row = AdminInbox(**values)
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
    if dispatch_im and level == "critical":
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


# ---- 工作流事件 → 收件箱（T03304 / T03329）----

# 与 workflow_scheduler._WORKFLOW_FAILED_KEY 同值。这里写字面量而不是 import，
# 避免服务层反向依赖调度器（调度器才是调用方）。
WORKFLOW_FAILED_EVENT = "workflow.failed"
WORKFLOW_PENDING_REVIEW_EVENT = "workflow.pending_review"
WORKFLOW_PUBLISHED_EVENT = "workflow.published"
# T03329 事件清单裁决（按 AI 建议执行）：
# - 待审核 / 执行失败：需要人处置，T03304 已上线；
# - 发布成功：结果告知，进收件箱但不外发 IM（发布链路自己的结构化通知负责外部触达）；
# - 抓取异常：不单列——crawl 环节失败已由 workflow.failed 落库（dedup 含环节），
#   再立一个事件会让同一事故出现两条消息；
# - 审核驳回 / 用户反馈：走非工作流入口（notify_review_rejected / notify_feedback_created）。
WORKFLOW_INBOX_EVENTS = (
    WORKFLOW_PENDING_REVIEW_EVENT,
    WORKFLOW_FAILED_EVENT,
    WORKFLOW_PUBLISHED_EVENT,
)

# 失败原因进正文只留首行并截断：异常串常把整个调用栈/上游响应塞进来，
# 收件箱又有保留窗口（90 天，见 ADMIN_INBOX_KEEP_DAYS），存全文只会让表无谓膨胀。
_FAILURE_REASON_MAX = 200

# 反馈同步可能一次带回积压（COS 里存量的旧对象），只通知最近 N 天的反馈，
# 避免首次同步把历史反馈一次性灌进收件箱；存量反馈仍可在反馈页查看。
FEEDBACK_NOTIFY_MAX_AGE_DAYS = 7


def _first_line(text) -> str:
    lines = str(text or "").strip().splitlines()
    return lines[0][:_FAILURE_REASON_MAX] if lines else ""


async def _admin_recipients(db, exclude_admin_ids=None) -> list[int]:
    """收件人 = admin_user 里 role='admin' 且启用的账号（判词「全体 admin」）。

    不含 operator：失败消息的深链落点是 /m/manage/queue，该页 requireRole=admin，
    operator 点进去只会被守卫拦下——宁可不发，也不发一条点进去被拒的消息。
    exclude_admin_ids 用于「操作者不必收自己刚做的事」（如审核驳回）。
    """
    stmt = select(AdminUser.id).where(
        AdminUser.role == AdminRole.admin.value,
        AdminUser.status == 1,
    )
    if exclude_admin_ids:
        stmt = stmt.where(AdminUser.id.not_in(list(exclude_admin_ids)))
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def notify_admins(
    db,
    msg_type: str,
    level: str,
    title: str,
    body: Optional[str] = None,
    payload: Optional[dict] = None,
    dedup_key: Optional[str] = None,
    exclude_admin_ids=None,
) -> int:
    """把一条消息写给全体 admin，返回真正新增的条数（被幂等挡下的不计）。

    dispatch_im 固定 False：这些事件的外部触达由发布/失败链路的结构化通知
    （含 IM 渠道）负责，若这里再按 critical 逐人 fan-out，N 个 admin 会让同一件事
    在钉钉/企微里重复 N 遍。收件箱只是站内通道，不重复外发。
    """
    created = 0
    for admin_id in await _admin_recipients(db, exclude_admin_ids):
        row = await push_admin_message(
            db,
            admin_id,
            msg_type=msg_type,
            level=level,
            title=title,
            body=body,
            payload=payload,
            dedup_key=dedup_key,
            dispatch_im=False,
        )
        if row is not None:
            created += 1
    return created


async def notify_workflow_event(
    db,
    event_type: str,
    workflow_id: str,
    extra_vars: Optional[dict] = None,
) -> int:
    """工作流事件 → admin 收件箱（白名单见 WORKFLOW_INBOX_EVENTS）。

    幂等键 = 事件 + 工作流（失败再带上环节）：同一事件重放（cron 重试、进程重启后
    重新入队）只入库一条；同一工作流换一个环节失败是新信息，会再发一条。

    深链契约（与已上线口径对齐）：
    - 待审核：payload 只给 workflow_id，Message.vue 拼 /m/review?workflow_id=...
      刻意不写 payload.path——messageTarget 里 path 优先级更高，带上 path 会把
      workflow_id 丢掉，落到「全部待审」而不是这条工作流。
    - 失败：payload.path=/m/manage/queue。移动端只有队列页能重跑/处置失败任务；
      /m/review 对失败工作流只会显示「暂无待审稿件」，是误导性落点。
    - 发布成功：不带 payload。移动端没有「已发布节目」详情页，硬塞 /m/review 会
      落到待审列表并显示「暂无待审内容」——结果告知不需要一个点进去就打脸的链接。
    """
    extra = extra_vars or {}
    if event_type == WORKFLOW_PENDING_REVIEW_EVENT:
        return await notify_admins(
            db,
            "review",
            "warning",
            "有新的待审稿件",
            f"工作流 {workflow_id} 已完成制作，等待人工审核。",
            {"workflow_id": workflow_id},
            f"workflow.pending_review:{workflow_id}",
        )
    if event_type == WORKFLOW_PUBLISHED_EVENT:
        return await notify_admins(
            db,
            "system",
            "info",
            "节目已发布上线",
            f"工作流 {workflow_id} 的节目已发布上线。",
            None,
            f"workflow.published:{workflow_id}",
        )
    if event_type == WORKFLOW_FAILED_EVENT:
        step = extra.get("failed_step") or "unknown"
        reason = _first_line(extra.get("error_message"))
        body = f"工作流 {workflow_id} 在「{step}」环节失败"
        body += f"：{reason}" if reason else "。"
        return await notify_admins(
            db,
            "alert",
            "critical",
            "工作流执行失败",
            body,
            {"path": "/m/manage/queue"},
            f"workflow.failed:{workflow_id}:{step}",
        )
    return 0


async def notify_review_rejected(
    db,
    workflow_id: str,
    review_id: int,
    reviewer_name: str,
    reason: Optional[str],
    actor_admin_id: Optional[int] = None,
) -> int:
    """审核驳回 → 收件箱（T03329），排除刚点驳回的操作者。

    收件人仍是全体启用 admin：Workflow 没有发起人/频道 owner 字段，
    不为了通知臆造一条归属关系；被驳回的稿件需要任何一位编导接手修改，
    但「你刚做的动作」不必再回给你一条消息。理由必填（ReviewService 校验），
    正文只留首行并截断——修改意见可能是整段文字，收件箱不是编辑器。
    """
    reason_line = _first_line(reason)
    body = f"{reviewer_name or '管理员'} 驳回了工作流 {workflow_id} 的稿件"
    body += f"：{reason_line}" if reason_line else "。"
    exclude = {actor_admin_id} if actor_admin_id is not None else None
    return await notify_admins(
        db,
        "review",
        "warning",
        "稿件被驳回",
        body,
        # 移动端审核页固定请求 status=pending，带 workflow_id 也只会显示「暂无待审」；
        # 不给 payload 是避免一个点进去就打脸的深链（同发布成功的口径）。
        None,
        f"review.rejected:{review_id}",
        exclude_admin_ids=exclude,
    )


async def notify_feedback_created(
    db,
    feedback_id: str,
    category: str,
    content: str,
    created_at=None,
) -> int:
    """用户反馈 → 收件箱（T03329）。

    收件人 = 全体启用 admin；深链指向移动端反馈页（真实存在的 /m/manage/feedback）。
    存量积压只通知最近 FEEDBACK_NOTIFY_MAX_AGE_DAYS 天：首次从 COS 同步时可能
    一次带回大量历史反馈，全部灌进收件箱会把真正的新反馈淹掉。
    created_at 按 feedback_sync 的存储口径是 naive UTC；本地 now 直接相减会多算
    8 小时，临界值附近会误伤，统一按 UTC 比较。
    """
    if created_at is not None:
        utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
        if (utc_now - created_at).days > FEEDBACK_NOTIFY_MAX_AGE_DAYS:
            return 0
    snippet = _first_line(content)
    if len(snippet) > 80:
        snippet = snippet[:80] + "…"
    category_text = category or "other"
    body = f"{category_text}：{snippet}" if snippet else category_text
    return await notify_admins(
        db,
        "system",
        "info",
        "收到新的用户反馈",
        f"{body}（{feedback_id}）",
        {"path": "/m/manage/feedback"},
        f"feedback.created:{feedback_id}",
    )


async def notify_isolated(db, notify_callable) -> None:
    """在派生会话里执行一次收件箱写入，失败只记日志、不影响主流程。

    调用时机是业务事务已提交之后：站内消息不可用不能反过来让审核/发布/反馈失败。
    会话从请求 session 的 bind 派生，测试覆盖 get_db 时也写进同一个测试库
    （与 maintenance_task_service 同一做法）。
    """
    bind = getattr(db, "bind", None)
    try:
        if bind is None:
            await notify_callable(db)
            await db.commit()
            return
        factory = async_sessionmaker(
            bind=bind, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )
        async with factory() as session:
            await notify_callable(session)
            await session.commit()
    except Exception:
        logger.exception("收件箱写入失败（已忽略，不影响主流程）")


async def purge_inbox_before(db, cutoff) -> int:
    """删除 cutoff 之前的收件箱消息，返回删除条数（调用方负责 commit）。

    读没读都按时间清：保留窗口的意义是「过了窗口的提醒不再占位」，与读态无关。
    系统清理页与 sched 进程的每日任务共用本函数，保证两边删的是同一张表、
    同一个时间字段（created_at）。
    """
    result = await db.execute(
        delete(AdminInbox).where(AdminInbox.created_at < cutoff)
    )
    await db.flush()
    return result.rowcount or 0


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

    读库异常时不再放行（T02612）：先沿用最后一次已知值（即使缓存已过期），
    从未成功读到过就按维护态处理（fail-closed）——数据库超时往往正是故障现场，
    此时放行新任务等于把刚下的应急停服指令静默绕过。首次降级发 critical 告警。
    """
    global _maint_degraded
    now = time.time()
    with _maint_cache_lock:
        cached = _maint_cache["value"]
        if cached is not None and now - _maint_cache["ts"] < _MAINT_CACHE_TTL:
            return cached
        # ts>0 才代表「曾经读到过真实值」；reset 后的 0.0 是未知态
        known = cached is not None and _maint_cache["ts"] > 0

    try:
        on = (await get_maintenance(db)).get("enabled", False)
    except Exception as e:
        with _maint_cache_lock:
            on = cached if known else True
            _maint_cache["value"] = on
            _maint_cache["ts"] = now
            first_degrade = not _maint_degraded
            _maint_degraded = True
        logger.error(
            "读取维护态失败 type=%s，%s",
            type(e).__name__,
            "沿用最后已知值 %s" % on if known else "无已知值，按维护态拒绝新任务（fail-closed）",
            exc_info=e,
        )
        if first_degrade:
            _notify_maintenance_check_failed(type(e).__name__)
        return on

    with _maint_cache_lock:
        _maint_cache["value"] = on
        _maint_cache["ts"] = now
        _maint_degraded = False
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
