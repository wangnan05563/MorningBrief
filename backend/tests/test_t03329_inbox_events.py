"""T03329 收件箱其余事件清单与保留/清理窗口。

判词（按 AI 建议执行）：
- 事件面：发布成功进收件箱（结果告知，不重复外发 IM）；抓取异常不单列，
  由 workflow.failed（dedup 含环节）承载；审核驳回 / 用户反馈走非工作流入口。
- 收件人：全体启用 admin；驳回排除刚点驳回的操作者。
- 保留窗口：ADMIN_INBOX_KEEP_DAYS（默认 90 天），sched 进程每日 03:30 清理，
  系统清理页 old_inbox 目标与定时任务共用同一张表/同一时间字段。

覆盖：
- 白名单事件面（published 进、crawl 不另立、未知事件不出）
- 幂等：发布/驳回/反馈各按自身主键去重，重放不重复入库/不重复触达日志
- 深链：反馈指向真实存在的 /m/manage/feedback；发布/驳回不给 path（页面会对不上）
- 收件范围：驳回排除操作者；反馈全体 admin
- 存量反馈窗口：只通知最近 7 天（UTC 口径，避免本地时区多算 8 小时）
- 保留/清理：purge 按 created_at 且读没读都清、可重放；维护页 dry_run 不删；
  all 聚合包含 old_inbox；get_status 下发窗口；调度器任务按配置窗口清理
- 接线：调度器注册每日任务、四个生产入口都调用了收件箱写入
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import re

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.timeutil import localnow_naive
from app.database import Base
from app.models.admin_user import AdminRole, AdminUser
from app.models.audit_log import AuditLog
from app.models.mobile import AdminInbox
from app.models.notification_log import NotificationLog
from app.services import mobile_service
from app.services.maintenance_service import MaintenanceService

WID = "wf-20261028-0001"
APP_DIR = Path(__file__).resolve().parents[1] / "app"


# ---------- helpers ----------


async def _add_admin(db, username: str, role: str = AdminRole.admin.value, status: int = 1):
    row = AdminUser(
        username=username, password_hash="x", role=role, status=status, nickname=username
    )
    db.add(row)
    await db.flush()
    return row


async def _seed_admins(db, names=("admin_a", "admin_b")):
    admins = [await _add_admin(db, n) for n in names]
    await _add_admin(db, "operator_c", role=AdminRole.operator.value)
    await _add_admin(db, "admin_off", status=0)
    return admins


async def _inbox_rows(db, msg_type=None):
    stmt = select(AdminInbox).order_by(AdminInbox.id)
    if msg_type:
        stmt = stmt.where(AdminInbox.msg_type == msg_type)
    return (await db.execute(stmt)).scalars().all()


def _inbox(admin_id, created_at, read=False):
    return AdminInbox(
        admin_id=admin_id,
        msg_type="system",
        level="info",
        title="历史消息",
        read=read,
        created_at=created_at,
    )


# ---------- 白名单事件面 ----------


async def test_published_event_enters_inbox_without_deeplink(db_session):
    admin_a, admin_b = await _seed_admins(db_session)

    created = await mobile_service.notify_workflow_event(
        db_session, mobile_service.WORKFLOW_PUBLISHED_EVENT, WID
    )
    replay = await mobile_service.notify_workflow_event(
        db_session, mobile_service.WORKFLOW_PUBLISHED_EVENT, WID
    )
    await db_session.commit()

    assert (created, replay) == (2, 0), "重放不得重复入库"
    rows = await _inbox_rows(db_session, "system")
    assert {r.admin_id for r in rows} == {admin_a.id, admin_b.id}
    assert all(r.level == "info" and r.read is False for r in rows)
    assert all(r.payload_json is None for r in rows), (
        "移动端没有已发布详情页，带深链会落到「暂无待审内容」"
    )
    assert rows[0].dedup_key == f"workflow.published:{WID}"
    logs = (
        await db_session.execute(
            select(NotificationLog).where(NotificationLog.channel == "inbox")
        )
    ).scalars().all()
    assert len(logs) == 2, "被幂等挡下的重放不再写触达日志"


async def test_crawl_failure_is_not_a_separate_event(db_session):
    await _seed_admins(db_session)

    # 抓取异常不单列事件：即使上游误传，也不该产生第二条消息
    stray = await mobile_service.notify_workflow_event(
        db_session, "workflow.crawl_failed", WID, {"failed_step": "crawl"}
    )
    assert stray == 0

    first = await mobile_service.notify_workflow_event(
        db_session, mobile_service.WORKFLOW_FAILED_EVENT, WID,
        {"failed_step": "crawl", "error_message": "RSS 超时"},
    )
    replay = await mobile_service.notify_workflow_event(
        db_session, mobile_service.WORKFLOW_FAILED_EVENT, WID,
        {"failed_step": "crawl"},
    )
    await db_session.commit()

    assert (first, replay) == (2, 0)
    rows = await _inbox_rows(db_session, "alert")
    assert len(rows) == 2, "同一抓取事故只有 workflow.failed 两条（每 admin 一条）"
    assert rows[0].dedup_key == f"workflow.failed:{WID}:crawl"
    assert "crawl" not in mobile_service.WORKFLOW_INBOX_EVENTS


async def test_whitelist_covers_exactly_three_workflow_events():
    assert set(mobile_service.WORKFLOW_INBOX_EVENTS) == {
        "workflow.pending_review",
        "workflow.failed",
        "workflow.published",
    }


# ---------- 审核驳回 ----------


async def test_rejected_event_excludes_actor_and_dedups_by_review(db_session):
    admin_a = (await _seed_admins(
        db_session, names=("admin_a", "admin_b", "admin_c")
    ))[0]
    admin_b = (await db_session.execute(
        select(AdminUser).where(AdminUser.username == "admin_b")
    )).scalar_one()
    admin_c = (await db_session.execute(
        select(AdminUser).where(AdminUser.username == "admin_c")
    )).scalar_one()

    created = await mobile_service.notify_review_rejected(
        db_session,
        workflow_id=WID,
        review_id=501,
        reviewer_name="admin_a",
        reason="画面太暗，重新选素材\n第二行不进正文",
        actor_admin_id=admin_a.id,
    )
    replay = await mobile_service.notify_review_rejected(
        db_session, WID, 501, "admin_a", "画面太暗", actor_admin_id=admin_a.id
    )
    other_review = await mobile_service.notify_review_rejected(
        db_session, WID, 502, "admin_a", "第二条稿件的问题", actor_admin_id=admin_a.id
    )
    await db_session.commit()

    assert (created, replay, other_review) == (2, 0, 2)
    rows = await _inbox_rows(db_session, "review")
    assert len(rows) == 4
    first_review = [r for r in rows if r.dedup_key == "review.rejected:501"]
    assert {r.admin_id for r in first_review} == {admin_b.id, admin_c.id}
    assert admin_a.id not in {r.admin_id for r in first_review}, "操作者不收自己刚做的动作"
    assert "画面太暗" in first_review[0].body
    assert "第二行不进正文" not in first_review[0].body
    assert first_review[0].payload_json is None
    assert first_review[0].level == "warning"


# ---------- 用户反馈 ----------


async def test_feedback_event_links_feedback_page_and_dedups(db_session):
    admin_a, admin_b = await _seed_admins(db_session)
    content = "甲" * 100 + "\n第二行不进正文"

    created = await mobile_service.notify_feedback_created(
        db_session, "fb-0001", "bug", content
    )
    replay = await mobile_service.notify_feedback_created(
        db_session, "fb-0001", "bug", content
    )
    await db_session.commit()

    assert (created, replay) == (2, 0)
    rows = await _inbox_rows(db_session, "system")
    assert {r.admin_id for r in rows} == {admin_a.id, admin_b.id}
    row = rows[0]
    assert row.dedup_key == "feedback.created:fb-0001"
    assert "第二行不进正文" not in row.body
    assert "甲" * 80 in row.body and "…" in row.body, "长反馈截断到 80 字加省略号"
    assert "fb-0001" in row.body
    assert json.loads(row.payload_json) == {"path": "/m/manage/feedback"}


async def test_feedback_backlog_only_notifies_recent(db_session):
    await _seed_admins(db_session, names=("admin_a",))
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 6 天 20 小时前（UTC 口径仍在 7 天内；按本地时间会多算 8 小时而误伤）
    recent = await mobile_service.notify_feedback_created(
        db_session, "fb-recent", "other", "刚提交的",
        created_at=utc_now - timedelta(days=6, hours=20),
    )
    stale = await mobile_service.notify_feedback_created(
        db_session, "fb-stale", "other", "积压的",
        created_at=utc_now - timedelta(days=8),
    )
    await db_session.commit()

    assert (recent, stale) == (1, 0)
    rows = await _inbox_rows(db_session)
    assert len(rows) == 1
    assert rows[0].dedup_key == "feedback.created:fb-recent"


# ---------- 保留窗口 / 清理 ----------


async def test_purge_deletes_by_age_regardless_of_read_and_is_idempotent(db_session):
    [admin_a] = await _seed_admins(db_session, names=("admin_a",))
    now = localnow_naive()
    db_session.add_all([
        _inbox(admin_a.id, now - timedelta(days=100), read=False),
        _inbox(admin_a.id, now - timedelta(days=95), read=True),
        _inbox(admin_a.id, now - timedelta(days=10), read=False),
    ])
    await db_session.commit()
    cutoff = now - timedelta(days=90)

    deleted = await mobile_service.purge_inbox_before(db_session, cutoff)
    await db_session.commit()
    again = await mobile_service.purge_inbox_before(db_session, cutoff)
    await db_session.commit()

    assert (deleted, again) == (2, 0), "读没读都按时间清；重放不重复计数"
    rows = await _inbox_rows(db_session)
    assert len(rows) == 1
    assert rows[0].created_at >= cutoff


async def test_maintenance_old_inbox_dry_run_then_delete(db_session):
    [admin_a] = await _seed_admins(db_session, names=("admin_a",))
    now = localnow_naive()
    db_session.add_all([
        _inbox(admin_a.id, now - timedelta(days=40)),
        _inbox(admin_a.id, now - timedelta(days=35), read=True),
        _inbox(admin_a.id, now - timedelta(days=10)),
    ])
    await db_session.commit()
    svc = MaintenanceService(db_session)

    preview = await svc.cleanup_database(
        target="old_inbox", days=30, dry_run=True, admin_name="tester"
    )
    assert preview["total_deleted"] == 2
    assert any("运营收件箱 将删除 2 条" in m for m in preview["cleaned"])
    assert len(await _inbox_rows(db_session)) == 3, "预览不得真删"

    real = await svc.cleanup_database(
        target="old_inbox", days=30, dry_run=False, admin_name="tester"
    )
    assert real["total_deleted"] == 2
    assert any("运营收件箱 已删除 2 条" in m for m in real["cleaned"])
    rows = await _inbox_rows(db_session)
    assert len(rows) == 1
    assert rows[0].created_at >= now - timedelta(days=30), "留下的是窗口内的那条"

    audits = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "cleanup_database")
    )).scalars().all()
    assert len(audits) == 2, "预览与真实清理都留审计"


async def test_all_target_includes_old_inbox(db_session, monkeypatch):
    [admin_a] = await _seed_admins(db_session, names=("admin_a",))
    now = localnow_naive()
    db_session.add_all([
        _inbox(admin_a.id, now - timedelta(days=40)),
        _inbox(admin_a.id, now - timedelta(days=10)),
    ])
    await db_session.commit()

    async def _skip_vacuum(self, dry_run, cleaned, errors):
        return None

    monkeypatch.setattr(MaintenanceService, "_db_step_vacuum", _skip_vacuum)
    result = await MaintenanceService(db_session).cleanup_database(
        target="all", days=30, dry_run=True, admin_name="tester"
    )

    assert any("运营收件箱 将删除 1 条" in m for m in result["cleaned"])
    assert result["total_deleted"] == 1


async def test_status_exposes_retention_window(db_session, monkeypatch):
    from app.services import maintenance_service as maint_mod

    monkeypatch.setattr(maint_mod.settings, "ADMIN_INBOX_KEEP_DAYS", 45)

    async def _empty_stats(self):
        return {}

    monkeypatch.setattr(MaintenanceService, "_get_db_stats", _empty_stats)
    monkeypatch.setattr(MaintenanceService, "_get_cache_stats", _empty_stats)
    monkeypatch.setattr(MaintenanceService, "_scan_log_dir", lambda self: {})

    status = await MaintenanceService(db_session).get_status()
    assert status["retention"]["admin_inbox_days"] == 45


# ---------- 定时清理 ----------


async def test_scheduler_cleanup_uses_configured_window(tmp_path, monkeypatch):
    from app.services import workflow_scheduler as wf_mod

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'inbox.db'}",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    now = localnow_naive()
    async with maker() as s:
        admin = await _add_admin(s, "admin_a")
        s.add_all([
            _inbox(admin.id, now - timedelta(days=40)),
            _inbox(admin.id, now - timedelta(days=20)),
        ])
        await s.commit()

    monkeypatch.setattr(wf_mod, "AsyncSessionLocal", maker)
    monkeypatch.setattr(wf_mod.settings, "ADMIN_INBOX_KEEP_DAYS", 30)

    await wf_mod.workflow_scheduler._cleanup_admin_inbox()

    async with maker() as s:
        rows = (await s.execute(select(AdminInbox))).scalars().all()
    assert len(rows) == 1
    assert rows[0].created_at >= now - timedelta(days=30)
    await engine.dispose()


def test_scheduler_registers_daily_inbox_cleanup_job():
    """落在 sched/all 单例进程，每日 03:30；api 进程不跑（避免多 worker 重复清）。"""
    src = (APP_DIR / "services" / "workflow_scheduler.py").read_text(encoding="utf-8")
    block = re.search(
        r"self\._cleanup_admin_inbox,(.*?)id=\"cleanup_admin_inbox\"", src, re.S
    )
    assert block, "start() 必须注册 cleanup_admin_inbox 任务"
    assert re.search(r"hour=3\b", block.group(1))
    assert re.search(r"minute=30\b", block.group(1))
    method = re.search(
        r"async def _cleanup_admin_inbox\(.*?ADMIN_INBOX_KEEP_DAYS", src, re.S
    )
    assert method, "定时任务必须读 ADMIN_INBOX_KEEP_DAYS 而不是写死天数"


# ---------- 隔离会话写入 ----------


async def test_notify_isolated_writes_in_derived_session(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'isolated.db'}",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as s:
        await _add_admin(s, "admin_a")
        await s.commit()

        await mobile_service.notify_isolated(
            s,
            lambda session: mobile_service.notify_workflow_event(
                session, mobile_service.WORKFLOW_PUBLISHED_EVENT, WID
            ),
        )

    async with maker() as s:
        rows = (await s.execute(select(AdminInbox))).scalars().all()
    assert len(rows) == 1, "业务事务已提交后，收件箱要在自己的会话里落库"

    # 收件箱不可用不得反噬主流程
    async def _boom(_session):
        raise RuntimeError("收件箱写失败")

    async with maker() as s:
        await mobile_service.notify_isolated(s, _boom)

    await engine.dispose()


# ---------- 生产入口接线 ----------


def test_producer_call_sites_are_wired():
    """四个入口必须真的调用收件箱写入，否则服务层测试全绿而线上没人写。"""
    reviews = (APP_DIR / "routers" / "admin" / "reviews.py").read_text(encoding="utf-8")
    assert "WORKFLOW_PUBLISHED_EVENT" in reviews
    assert "notify_review_rejected" in reviews

    auto = (APP_DIR / "services" / "auto_review_service.py").read_text(encoding="utf-8")
    assert "WORKFLOW_PUBLISHED_EVENT" in auto

    feedback_api = (APP_DIR / "routers" / "api" / "feedbacks.py").read_text(encoding="utf-8")
    assert "notify_feedback_created" in feedback_api

    feedback_sync = (
        APP_DIR / "services" / "feedback_sync_service.py"
    ).read_text(encoding="utf-8")
    assert "notify_feedback_created" in feedback_sync
