"""T02799：系统清理的长任务改后台作业（FR-UX-702）。

此前 `/database`、`/logs`、`/cache` 在 `async def` 里直接 `await svc.cleanup_*`：
VACUUM 与批量 DELETE 是分钟级操作，HTTP 请求要一直挂着，前端 300s 长超时只是兜底。
现在非预览执行改为「提交任务 → 立刻返回 task_id → 轮询状态」，预览仍同步返回。

这里守的几条口径（都是线上会真实遇到的）：
1. **预览必须仍然同步**：轮询化不能把「先看看会删多少」也变成异步——确认框要当场可用。
2. **后台任务真的执行并落结果**：任务结束时 result.total_deleted 与库里行数一致，
   审计仍按操作人落库（task 的 admin_name 与请求 JWT 同一口径）。
3. **同目标重复提交合并**：用户点第二次本来就是「怕没生效」，不能再跑一份 VACUUM。
4. **失败/中断可回收**：执行异常要落成 failed 并释放 active_key；进程被杀留下的
   陈旧活跃记录要在下次提交时被判失败，否则该目标永远提交不进去。

数据库用临时文件而非 `:memory:`：后台任务走独立 session，内存库的 StaticPool
会把两条连接挤到同一条上（并发事务互相打断），测出来的失败是测试设施假象。
"""
import asyncio
import json
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.timeutil import localnow_naive
from app.database import Base, get_db, normalize_metadata_for_sqlite
from app.main import create_app
from app.models.audit_log import AuditLog
from app.models.crawler_dedup import CrawlerDedup
from app.models.maintenance_task import MaintenanceTask
from app.services import maintenance_task_service as task_service

BASE = "/admin/api/v1/maintenance"
TERMINAL = ("succeeded", "failed")


def _auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


@pytest.fixture
def env(tmp_path):
    """文件库 + 持久事件循环（TestClient 以 with 进入，后台任务才能跨请求存活）。"""
    normalize_metadata_for_sqlite()
    db_path = (tmp_path / "t02799.db").as_posix()
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    async def _create_all():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_all())

    app = create_app()

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, factory=factory)

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def _add_dedup(env, count, age_days):
    async def _add():
        async with env.factory() as s:
            for _ in range(count):
                s.add(CrawlerDedup(
                    url=f"https://example.com/{uuid.uuid4().hex}",
                    url_hash=uuid.uuid4().hex,
                    created_at=localnow_naive() - timedelta(days=age_days),
                ))
            await s.commit()

    asyncio.run(_add())


def _count_dedup(env):
    async def _count():
        async with env.factory() as s:
            rows = (await s.execute(select(CrawlerDedup))).scalars().all()
            return len(rows)

    return asyncio.run(_count())


def _add_row(env, row):
    async def _add():
        async with env.factory() as s:
            s.add(row)
            await s.commit()

    asyncio.run(_add())


def _latest_audit(env, action):
    async def _get():
        async with env.factory() as s:
            rows = (
                await s.execute(
                    select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id.desc())
                )
            ).scalars().all()
            return rows[0] if rows else None

    return asyncio.run(_get())


def _get_task(env, admin_token, task_id):
    return env.client.get(f"{BASE}/tasks/{task_id}", headers=_auth(admin_token))


def _wait_task(env, admin_token, task_id, timeout=10.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = _get_task(env, admin_token, task_id)
        assert resp.status_code == 200, resp.text
        last = resp.json()["data"]
        if last["state"] in TERMINAL:
            return last
        time.sleep(0.05)
    raise AssertionError(f"任务 {task_id} 未在 {timeout}s 内结束：{last}")


def _post(env, admin_token, category, payload):
    return env.client.post(f"{BASE}/{category}", json=payload, headers=_auth(admin_token))


def test_dry_run_stays_synchronous(env, admin_token):
    """预览仍是一次请求就拿到结果：确认框要用它，不能变成先提交再轮询。"""
    _add_dedup(env, 2, age_days=10)
    resp = _post(env, admin_token, "database", {"target": "old_dedup", "days": 1, "dry_run": True})
    body = resp.json()
    assert body.get("code") == 0, body
    data = body["data"]
    assert "task_id" not in data, f"预览被改成异步了：{data}"
    assert data["dry_run"] is True
    assert any("将删除 2 条" in line for line in data["cleaned"]), data["cleaned"]
    # 预览不得真的删数据
    assert _count_dedup(env) == 2


def test_real_cleanup_runs_as_background_task(env, admin_token):
    """真实执行：立刻返回 task_id，结果与审计在任务结束时可见。"""
    _add_dedup(env, 2, age_days=10)
    _add_dedup(env, 1, age_days=0)

    resp = _post(env, admin_token, "database", {"target": "old_dedup", "days": 1, "dry_run": False})
    body = resp.json()
    assert body.get("code") == 0, body
    submitted = body["data"]
    task_id = submitted.get("task_id")
    assert task_id, f"非预览没有返回 task_id：{submitted}"
    assert submitted["state"] in ("queued", "running"), submitted
    assert submitted.get("result") is None, "执行中不该有结果"

    done = _wait_task(env, admin_token, task_id)
    assert done["state"] == "succeeded", done
    assert done["result"]["total_deleted"] == 2, done["result"]
    assert done["elapsed_ms"] is not None and done["finished_at"] is not None
    # 只删了超过 1 天的两条，当天那条必须还在
    assert _count_dedup(env) == 1

    audit = _latest_audit(env, "cleanup_database")
    assert audit is not None, "后台任务也要落审计"
    assert audit.operator == "admin", f"审计操作人与 JWT 不一致：{audit.operator}"
    assert json.loads(audit.detail)["days"] == 1


def test_duplicate_submit_merges_into_running_task(env, admin_token, monkeypatch):
    """同目标执行中再次提交：合并到同一任务，而不是跑第二份。"""
    gate = threading.Event()
    dispatched = []

    async def gated_dispatch(svc, category, target, params, admin_name):
        dispatched.append((category, target))
        await asyncio.to_thread(gate.wait, 10)
        return {"cleaned": ["模拟清理"], "errors": [], "total_deleted": 0}

    monkeypatch.setattr(task_service, "_dispatch", gated_dispatch)

    first = _post(env, admin_token, "cache", {"target": "ttlcache", "dry_run": False}).json()["data"]
    assert first["merged"] is False
    # 等任务真的进入 running，再点第二次
    deadline = time.time() + 5
    while time.time() < deadline:
        state = _get_task(env, admin_token, first["task_id"]).json()["data"]["state"]
        if state == "running":
            break
        time.sleep(0.05)

    second = _post(env, admin_token, "cache", {"target": "ttlcache", "dry_run": False}).json()["data"]
    assert second["merged"] is True, second
    assert second["task_id"] == first["task_id"], "重复提交没有合并到原任务"

    gate.set()
    done = _wait_task(env, admin_token, first["task_id"])
    assert done["state"] == "succeeded", done
    assert dispatched == [("cache", "ttlcache")], f"同目标被派发多次：{dispatched}"

    # 任务结束后 active_key 释放：再提交应创建新任务
    gate.set()
    third = _post(env, admin_token, "cache", {"target": "ttlcache", "dry_run": False}).json()["data"]
    assert third["merged"] is False and third["task_id"] != first["task_id"]
    _wait_task(env, admin_token, third["task_id"])


def test_failure_is_recorded_and_releases_active_key(env, admin_token, monkeypatch):
    async def boom(svc, category, target, params, admin_name):
        raise RuntimeError("模拟清理失败")

    monkeypatch.setattr(task_service, "_dispatch", boom)

    first = _post(env, admin_token, "cache", {"target": "pycache", "dry_run": False}).json()["data"]
    done = _wait_task(env, admin_token, first["task_id"])
    assert done["state"] == "failed", done
    assert "模拟清理失败" in (done["error"] or ""), done
    assert done["result"] is None

    # 失败也要释放去重位，否则这个目标永远提交不进去
    second = _post(env, admin_token, "cache", {"target": "pycache", "dry_run": False}).json()["data"]
    assert second["merged"] is False, "失败任务占着 active_key，后续提交被吞了"
    assert second["task_id"] != first["task_id"]
    _wait_task(env, admin_token, second["task_id"])


def test_stale_active_task_is_reclaimed_on_submit(env, admin_token):
    """进程被杀留下的活跃记录：超时后判 failed 并放行新提交。"""
    stale_id = uuid.uuid4().hex
    _add_row(env, MaintenanceTask(
        id=stale_id,
        category="database",
        target="old_dedup",
        active_key="database:old_dedup",
        state="running",
        admin_name="admin",
        created_at=localnow_naive() - timedelta(minutes=40),
        started_at=localnow_naive() - timedelta(minutes=40),
    ))

    fresh = _post(env, admin_token, "database", {"target": "old_dedup", "days": 1, "dry_run": False}).json()["data"]
    assert fresh["task_id"] != stale_id, "陈旧任务没被回收，新提交被合并进去了"
    assert fresh["merged"] is False

    stale = _get_task(env, admin_token, stale_id).json()["data"]
    assert stale["state"] == "failed"
    assert "进程中断" in (stale["error"] or ""), stale

    _wait_task(env, admin_token, fresh["task_id"])


def test_unknown_task_returns_404(env, admin_token):
    resp = _get_task(env, admin_token, "not-a-real-task")
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["code"] == 404
    assert "清理任务不存在" in body["message"]
