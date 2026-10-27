"""T03304 收件箱生产侧写入：两条事件 + 幂等索引 + 深链口径。

判词（2026-10-27）：只补「待审核」与「执行失败」两个需要人处置的事件，
收件人=全体 admin；幂等靠 (admin_id, msg_type, dedup_key) 唯一索引 + 迁移；
深链与已上线口径一致（payload.path 以 / 开头，workflow_id 走 SCOPED_REVIEW_SPECS）。

覆盖：
- 真实写入链路：notify_workflow_event → admin_inbox 有行 → /admin/api/v1/m/inbox 取得到
- 幂等：同一事件重放不重复入库，也不重复写触达日志
- 深链：待审核只给 workflow_id（带 path 会把 workflow_id 丢掉），失败给队列页
- 收件范围：只发启用的 role=admin，operator/禁用账号不写
- 调度器钩子：sender 抛错时收件箱照样落库（站内通道不依赖外部渠道）
- 迁移：历史库补列 + 唯一索引幂等；新建库的索引名与迁移同名
"""
import asyncio
import json
import sqlite3

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.models.admin_user import AdminRole, AdminUser
from app.models.mobile import AdminInbox
from app.models.notification_log import NotificationLog
from app.services import mobile_service

BASE = "/admin/api/v1/m"
WID = "wf-20261027-0001"


async def _add_admin(db, username: str, role: str = AdminRole.admin.value, status: int = 1):
    row = AdminUser(
        username=username,
        password_hash="x",
        role=role,
        status=status,
        nickname=username,
    )
    db.add(row)
    await db.flush()
    return row


async def _inbox_rows(db, msg_type: str | None = None):
    stmt = select(AdminInbox).order_by(AdminInbox.id)
    if msg_type:
        stmt = stmt.where(AdminInbox.msg_type == msg_type)
    return (await db.execute(stmt)).scalars().all()


async def _inbox_logs(db):
    return (
        await db.execute(
            select(NotificationLog).where(NotificationLog.channel == "inbox")
        )
    ).scalars().all()


async def _seed_recipients(db):
    admin_a = await _add_admin(db, "admin_a")
    admin_b = await _add_admin(db, "admin_b")
    await _add_admin(db, "operator_c", role=AdminRole.operator.value)
    await _add_admin(db, "admin_off", status=0)
    return admin_a, admin_b


# ---------- 生产侧写入 ----------


async def test_pending_review_writes_one_row_per_enabled_admin(db_session):
    admin_a, admin_b = await _seed_recipients(db_session)

    created = await mobile_service.notify_workflow_event(
        db_session, "workflow.pending_review", WID
    )
    await db_session.commit()

    assert created == 2
    rows = await _inbox_rows(db_session, "review")
    assert {r.admin_id for r in rows} == {admin_a.id, admin_b.id}
    row = rows[0]
    assert row.level == "warning"
    assert row.read is False
    payload = json.loads(row.payload_json)
    # 深链契约：待审核只给 workflow_id。一旦带 path，Message.vue 会优先用 path，
    # workflow_id 被丢掉 → 落到「全部待审」而不是这条工作流。
    assert "path" not in payload
    assert payload == {"workflow_id": WID}
    assert row.dedup_key == f"workflow.pending_review:{WID}"

    logs = await _inbox_logs(db_session)
    assert len(logs) == 2, "每个真正新增的收件人各一条 inbox 触达日志"


async def test_replayed_event_is_deduplicated(db_session):
    await _seed_recipients(db_session)
    first = await mobile_service.notify_workflow_event(
        db_session, "workflow.pending_review", WID
    )
    second = await mobile_service.notify_workflow_event(
        db_session, "workflow.pending_review", WID
    )
    await db_session.commit()

    assert (first, second) == (2, 0)
    assert len(await _inbox_rows(db_session)) == 2
    assert len(await _inbox_logs(db_session)) == 2, "被幂等挡下的重放不得再写触达日志"


async def test_failed_event_dedups_per_step_and_links_queue(db_session):
    await _seed_recipients(db_session)

    created = await mobile_service.notify_workflow_event(
        db_session,
        "workflow.failed",
        WID,
        {"failed_step": "tts", "error_message": "Edge TTS 超时\n第二行不该进正文"},
    )
    # 同一环节再次失败：同一事件重放，不新增
    again = await mobile_service.notify_workflow_event(
        db_session, "workflow.failed", WID, {"failed_step": "tts"}
    )
    # 换环节是新信息
    other_step = await mobile_service.notify_workflow_event(
        db_session, "workflow.failed", WID, {"failed_step": "stitch"}
    )
    await db_session.commit()

    assert (created, again, other_step) == (2, 0, 2)
    rows = await _inbox_rows(db_session, "alert")
    assert len(rows) == 4
    tts_rows = [r for r in rows if "tts" in (r.body or "")]
    assert len(tts_rows) == 2
    assert tts_rows[0].level == "critical"
    assert json.loads(tts_rows[0].payload_json) == {"path": "/m/manage/queue"}
    assert "第二行不该进正文" not in tts_rows[0].body, "失败原因只留首行"
    assert tts_rows[0].dedup_key == f"workflow.failed:{WID}:tts"


async def test_unknown_event_writes_nothing(db_session):
    await _seed_recipients(db_session)
    created = await mobile_service.notify_workflow_event(
        db_session, "workflow.completed", WID
    )
    await db_session.commit()
    assert created == 0
    assert await _inbox_rows(db_session) == []


async def test_manual_push_without_dedup_key_still_allows_duplicates(db_session):
    """手工/测试写入不带 dedup_key：NULL 在唯一索引里互不相等，不该被误伤。"""
    admin = await _add_admin(db_session, "admin_a")
    first = await mobile_service.push_admin_message(
        db_session, admin.id, "system", "info", "同一标题", "同一正文"
    )
    second = await mobile_service.push_admin_message(
        db_session, admin.id, "system", "info", "同一标题", "同一正文"
    )
    await db_session.commit()
    assert first is not None and second is not None
    assert len(await _inbox_rows(db_session)) == 2


async def test_broadcast_critical_does_not_fanout_im_per_admin(db_session, monkeypatch):
    """critical 广播只落库、不逐人外发：外部触达由工作流结构化通知负责。"""
    await _seed_recipients(db_session)
    calls = []

    async def _noop_dispatch(db, title, body, level):
        calls.append(title)
        return {"dispatched": 0}

    monkeypatch.setattr(mobile_service, "_dispatch_admin_alert", _noop_dispatch)
    await mobile_service.notify_workflow_event(
        db_session, "workflow.failed", WID, {"failed_step": "tts"}
    )
    await db_session.commit()
    assert len(await _inbox_rows(db_session)) == 2
    assert calls == [], "收件箱广播不应把同一告警按人头重复外发"


# ---------- 移动端接口真实取到 ----------


async def test_inbox_api_returns_produced_message(app, db_session, admin_token):
    """真实链路：服务层写入 → GET /m/inbox 能取到（含 deep-link payload）。"""
    admin = await _add_admin(db_session, "admin")
    created = await mobile_service.notify_workflow_event(
        db_session, "workflow.pending_review", WID
    )
    await db_session.commit()
    assert created == 1

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.get(
                f"{BASE}/inbox",
                headers={"Authorization": f"Bearer {admin_token['token']}"},
                params={"page": 1, "page_size": 20},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # admin_token 的 sub 固定为 "1"（conftest），行必须落在 admin_id=1 名下
    assert admin.id == 1
    assert data["unread_count"] == 1
    assert data["items"][0]["msg_type"] == "review"
    assert data["items"][0]["payload"] == {"workflow_id": WID}


# ---------- 调度器钩子 ----------


async def test_scheduler_hook_writes_inbox_even_if_sender_raises(tmp_path, monkeypatch):
    """sender 抛错走降级告警，但收件箱已经落库——站内通道不依赖外部渠道成败。"""
    from app.services import workflow_scheduler as wf_mod

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'hook.db'}",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as s:
        await _add_admin(s, "admin_a")
        await s.commit()

    monkeypatch.setattr(wf_mod, "AsyncSessionLocal", maker)

    def _sender_raises():
        raise RuntimeError("渠道不可用")

    monkeypatch.setattr(
        "app.services.notification.get_notification_sender", _sender_raises
    )
    alerts = []

    async def _record_alert(self, message):
        alerts.append(message)

    monkeypatch.setattr(wf_mod.WorkflowScheduler, "_alert_operators", _record_alert)

    await wf_mod.workflow_scheduler._send_notification(
        "workflow.pending_review", WID
    )
    async with maker() as s:
        rows = (await s.execute(select(AdminInbox))).scalars().all()
    assert len(rows) == 1
    assert alerts, "sender 失败仍应按既有逻辑降级告警"

    # 非白名单事件不写收件箱
    await wf_mod.workflow_scheduler._send_notification("workflow.completed", WID)
    async with maker() as s:
        assert len((await s.execute(select(AdminInbox))).scalars().all()) == 1

    # 失败事件同样在白名单内：确保调度器这一侧真的会为失败写收件箱，而不只是服务层单独能用
    await wf_mod.workflow_scheduler._send_notification(
        "workflow.failed", WID, {"failed_step": "tts", "error_message": "超时"}
    )
    async with maker() as s:
        rows = (await s.execute(select(AdminInbox).order_by(AdminInbox.id))).scalars().all()
    assert [r.msg_type for r in rows] == ["review", "alert"]
    assert json.loads(rows[1].payload_json) == {"path": "/m/manage/queue"}

    await engine.dispose()


# ---------- 迁移 ----------


def _legacy_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE admin_inbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            msg_type VARCHAR(32) NOT NULL,
            level VARCHAR(16) NOT NULL,
            title VARCHAR(128) NOT NULL,
            body TEXT,
            payload_json TEXT,
            read BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME
        )
        """
    )
    conn.execute(
        "INSERT INTO admin_inbox (admin_id, msg_type, level, title) "
        "VALUES (1, 'system', 'info', '历史消息')"
    )
    conn.commit()
    conn.close()


def test_migration_adds_column_and_unique_index_idempotently(tmp_path, monkeypatch):
    from app import main as main_mod

    db_path = tmp_path / "legacy.db"
    _legacy_db(db_path)
    monkeypatch.setattr("app.paths.resolve_db_path", lambda: db_path)

    asyncio.run(main_mod._migrate_admin_inbox_dedup_column())
    asyncio.run(main_mod._migrate_admin_inbox_dedup_column())

    conn = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(admin_inbox)")}
        assert "dedup_key" in cols
        indexes = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='admin_inbox'"
            )
        }
        assert "ix_admin_inbox_dedup" in indexes
        assert conn.execute("SELECT COUNT(*) FROM admin_inbox").fetchone()[0] == 1
    finally:
        conn.close()


async def test_fresh_schema_uses_same_index_name_as_migration(db_session):
    """新建库（create_all）与历史库（迁移）必须用同一个索引名，否则两条路径结构不一致。"""
    names = {
        r[0]
        for r in (
            await db_session.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='index' AND tbl_name='admin_inbox'"
                )
            )
        ).all()
    }
    assert "ix_admin_inbox_dedup" in names


async def test_unique_index_rejects_same_dedup_key_for_same_admin(db_session):
    """数据库层兜底：绕过服务层直接插同键，必须被唯一索引挡回。"""
    admin = await _add_admin(db_session, "admin_a")
    await db_session.commit()
    insert_sql = (
        "INSERT INTO admin_inbox (admin_id, msg_type, level, title, read, dedup_key) "
        "VALUES (:admin_id, 'review', 'warning', '待审', 0, :dedup_key)"
    )
    params = {"admin_id": admin.id, "dedup_key": f"workflow.pending_review:{WID}"}
    await db_session.execute(text(insert_sql), params)
    await db_session.commit()
    with pytest.raises(Exception):
        await db_session.execute(text(insert_sql), params)
        await db_session.commit()
