"""停摆告警护栏（T01696）。

背景：2026-09 起流水线停摆 34 天，失败只写在 workflow.error 里，
没有面向人的告警收敛（用户需自己翻库才知道停了）。

检测两类异常并经 NotifierHub 发告警（severity=critical，穿透免打扰）：
1. 停摆：最近 N 天（默认 2，STALL_ALERT_DAYS）无 status='success' 的工作流
2. 余额/鉴权：最近 24h 工作流步骤错误含 402/401（LLM 余额不足 / 凭证失效）

防抖：同一告警当日已成功发送过则跳过（查 notification_log），
避免停摆期每日 cron 重复轰炸。

触发时机（双保险，防"桌面端几天不开机永远不检查"）：
- 调度器每日 STALL_ALERT_CHECK_HOUR:STALL_ALERT_CHECK_MINUTE 定时检查
- 调度器启动时立即检查一次（幂等，靠当日去重兜底）

不引入新外部依赖：查询走 SQLAlchemy text()，发送复用 NotifierHub。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.timeutil import localnow_naive
from app.database import AsyncSessionLocal
from app.services.notification.log_service import LogService
from app.services.notifier import NotificationEvent

ALERT_EVENT_TYPE = "system.stall_alert"


@dataclass
class StallReport:
    """停摆检测结果（供告警文案与测试断言）。"""

    now: datetime
    stall_days: int                     # 检测窗口（天）
    last_success_at: Optional[str]      # 最后一次成功工作流时间（本地串）
    success_in_window: int              # 窗口内成功工作流数
    auth_errors_24h: int                # 24h 内 402/401 错误步骤数
    last_auth_error_at: Optional[str]   # 最后一次 402/401 时间
    recent_failures: dict[str, int] = field(default_factory=dict)  # 近 3 天失败步骤分布

    @property
    def stalled(self) -> bool:
        """窗口内成功数为 0 即判定停摆。"""
        return self.success_in_window == 0

    @property
    def has_auth_error(self) -> bool:
        return self.auth_errors_24h > 0

    def summary(self) -> str:
        """人类可读的一屏式摘要（告警正文主体）。"""
        lines: list[str] = []
        if self.stalled:
            lines.append(
                f"⚠️ 工作流停摆：最近 {self.stall_days} 天 0 次成功"
                + (f"（最后成功: {self.last_success_at}）" if self.last_success_at else "（从未有过成功记录）")
            )
        if self.has_auth_error:
            lines.append(
                f"⚠️ LLM 余额/鉴权异常：24h 内 {self.auth_errors_24h} 次 402/401 错误"
                + (f"（最近: {self.last_auth_error_at}）" if self.last_auth_error_at else "")
            )
        if self.recent_failures:
            dist = ", ".join(f"{k}×{v}" for k, v in self.recent_failures.items())
            lines.append(f"近 3 天失败步骤分布: {dist}")
        return "\n".join(lines)


async def detect_stall(
    session: AsyncSession,
    *,
    stall_days: Optional[int] = None,
    now: Optional[datetime] = None,
) -> StallReport:
    """只读检测：不停摆不报错，返回结构化报告。

    时间口径：workflow.started_at 为本地 naive 时间（localnow_naive 写入），
    cutoff 一律用 localnow_naive 对齐，避免 UTC/本地混比。
    """
    settings = get_settings()
    days = stall_days if stall_days is not None else settings.STALL_ALERT_DAYS
    now = now or localnow_naive()
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff24 = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff3d = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")

    last_success = (await session.execute(
        text("SELECT MAX(started_at) FROM workflow WHERE status = 'success'")
    )).scalar()
    success_in_window = (await session.execute(
        text("SELECT COUNT(*) FROM workflow WHERE status = 'success' AND started_at >= :c"),
        {"c": cutoff},
    )).scalar()
    auth_row = (await session.execute(
        text(
            "SELECT COUNT(*), MAX(started_at) FROM workflow_step "
            "WHERE status = 'failed' AND started_at >= :c "
            "AND (error LIKE '%402%' OR error LIKE '%401%')"
        ),
        {"c": cutoff24},
    )).one()
    failure_rows = (await session.execute(
        text(
            "SELECT step_name, COUNT(*) c FROM workflow_step "
            "WHERE status = 'failed' AND started_at >= :c "
            "GROUP BY step_name ORDER BY c DESC LIMIT 5"
        ),
        {"c": cutoff3d},
    )).all()

    def _fmt(v) -> Optional[str]:
        return str(v) if v else None

    return StallReport(
        now=now,
        stall_days=days,
        last_success_at=_fmt(last_success),
        success_in_window=int(success_in_window or 0),
        auth_errors_24h=int(auth_row[0] or 0),
        last_auth_error_at=_fmt(auth_row[1]),
        recent_failures={r[0]: int(r[1]) for r in failure_rows},
    )


async def _already_alerted_today(session: AsyncSession, now: datetime) -> bool:
    """当日防抖：今天（本地日期）已有本告警的成功记录则跳过。

    时区口径：notification_log.created_at 是 server_default=func.now()，
    SQLite 的 CURRENT_TIMESTAMP 返回 **UTC**；直接 LIKE 本地日期在 UTC+8
    下会整体错位 8 小时（07:30 本地告警记为前一日 UTC）。因此取最近一条
    成功记录的 created_at，按 UTC 解析后转本地时区再比日期。
    """
    row = (await session.execute(
        text(
            "SELECT created_at FROM notification_log "
            "WHERE event_type = :et AND status = 'success' "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"et": ALERT_EVENT_TYPE},
    )).scalar()
    if not row:
        return False
    last_dt = row if isinstance(row, datetime) else datetime.fromisoformat(str(row))
    last_local = last_dt.replace(tzinfo=timezone.utc).astimezone()
    return last_local.date() == now.date()


async def check_and_alert(
    session: Optional[AsyncSession] = None,
    *,
    stall_days: Optional[int] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """检测停摆/余额异常并发告警（调度器定时任务与启动检查共用入口）。

    session 可注入（测试用）；缺省自建（生产路径）。
    返回 {"status": ok|alerted|skipped|quiet, ...}，任何异常由调用方兜底。
    """
    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()
    try:
        now = now or localnow_naive()
        report = await detect_stall(session, stall_days=stall_days, now=now)

        if not report.stalled and not report.has_auth_error:
            return {"status": "ok", "report": report}

        if await _already_alerted_today(session, now):
            logger.info("[stall_alert] 当日已告警过，跳过（停摆={} 鉴权={}）",
                        report.stalled, report.has_auth_error)
            return {"status": "skipped", "reason": "今日已告警", "report": report}

        title = "【MorningBrief】流水线停摆/余额告警"
        if report.stalled and report.has_auth_error:
            title = "【MorningBrief】流水线停摆 + LLM 余额异常"
        elif report.has_auth_error:
            title = "【MorningBrief】LLM 余额/鉴权异常"
        elif report.stalled:
            title = "【MorningBrief】流水线停摆告警"

        event = NotificationEvent(
            title=title,
            message=report.summary(),
            severity="critical",  # 停摆属重大异常，穿透免打扰
            source="stall_alert",
            extra={"event_type": ALERT_EVENT_TYPE},
        )

        # 延迟导入避免循环依赖（notifier.hub 导入链较重）
        from app.services.notifier.hub import get_notifier_hub

        result = await get_notifier_hub().send(event)
        success = result.get("success", 0) > 0
        suppressed = result.get("suppressed", 0) > 0
        if result.get("total", 0) == 0:
            status, err = "failed", "未配置任何通知渠道"
        elif suppressed:
            status, err = "suppressed", "免打扰时段静默（critical 不应被静默，疑似异常）"
        elif success:
            status, err = "success", ""
        else:
            status, err = "failed", "所有渠道发送失败"

        await LogService(session).create_log(
            event_type=ALERT_EVENT_TYPE,
            channel="multi",
            title=title,
            status=status,
            error=err,
            payload={
                "stalled": report.stalled,
                "stall_days": report.stall_days,
                "last_success_at": report.last_success_at,
                "auth_errors_24h": report.auth_errors_24h,
                "summary": report.summary(),
            },
        )
        logger.warning("[stall_alert] {} status={} result={}", title, status, result)
        return {"status": status, "report": report, "send": result}
    finally:
        if own_session:
            await session.close()
