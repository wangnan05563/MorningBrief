"""T02529 / INT-UX-06 移动端应急停服：判重的原子性与审计的可追溯性。

PRD §7 INT-UX-06「幂等键/状态先行判重；审计含操作者与原因」。T02489 已把判重写成
「先读状态、已停服就 already=True 不写审计」，但读与写不在同一个临界区里：移动端连点
是两个**同时在飞**的请求，各自都读到「未停服」，于是判重形同虚设。

本文件全部在 HTTP 层取证（ASGITransport + 每请求独立 session + 与生产一致的 PRAGMA），
因为缺陷正好落在「请求 A 的读」与「请求 A 的写」之间，服务层单连接测不出来。
"""
import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import Base, get_db, normalize_metadata_for_sqlite
from app.main import create_app
from app.models.audit_log import AuditLog
from app.services import mobile_service

settings = get_settings()
BASE = "/admin/api/v1/m"


@pytest.fixture(autouse=True)
def _reset_maint_cache():
    mobile_service._maint_cache["value"] = None
    mobile_service._maint_cache["ts"] = 0.0
    yield
    mobile_service._maint_cache["value"] = None
    mobile_service._maint_cache["ts"] = 0.0


@pytest.fixture
async def race(tmp_path):
    """(client, session_maker)：文件库 + 每请求独立 session，并发写才各自一条连接。

    PRAGMA 照搬 app/database.py。不设 WAL/busy_timeout 的话第二击先撞
    ``database is locked``，把真正的判重缺陷掩盖成锁报错。
    """
    normalize_metadata_for_sqlite()
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'race.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _pragma(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        try:
            cur.execute(f"PRAGMA journal_mode={settings.SQLITE_JOURNAL_MODE}")
            cur.execute(f"PRAGMA busy_timeout={settings.SQLITE_BUSY_TIMEOUT_MS}")
            cur.execute(f"PRAGMA synchronous={settings.SQLITE_SYNCHRONOUS}")
        finally:
            cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    app = create_app()

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan

    async def _override_get_db():
        async with maker() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _override_get_db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, maker

    app.dependency_overrides.clear()
    await engine.dispose()


def _hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


async def _audit_rows(maker, action: str):
    """直接查库取审计行：读接口本身是被测对象，不能拿它当证据。"""
    async with maker() as s:
        return (
            (
                await s.execute(
                    select(AuditLog).where(
                        AuditLog.category == "mobile", AuditLog.action == action
                    )
                )
            )
            .scalars()
            .all()
        )


async def _state(maker):
    async with maker() as s:
        return await mobile_service.get_maintenance(s)


def _read_window(monkeypatch, seconds: float = 0.25) -> None:
    """把「已经读到旧状态」与「接着写状态」之间的间隙撑开，让连点必然踩进去。

    生产里这个间隙就是两次 await 之间的调度时间，靠运气复现的用例没有牙。
    注意是**读完再拖**：先睡后读会读到一个已经提交的新状态，反而把窗口关上了。
    只拖第一次：修好后第二击排在锁外，第一次读拖满也不影响判重。
    """
    real = mobile_service.get_maintenance
    calls = {"n": 0}

    async def _slow(db):
        result = await real(db)
        calls["n"] += 1
        if calls["n"] == 1:
            await asyncio.sleep(seconds)
        return result

    monkeypatch.setattr(mobile_service, "get_maintenance", _slow)


# ---- 判重的原子性 ----


@pytest.mark.asyncio
async def test_concurrent_stop_writes_only_one_audit(race, admin_token, monkeypatch):
    """连点＝两个同时在飞的停服请求：只能有一条停服审计。"""
    client, maker = race
    _read_window(monkeypatch)
    r1, r2 = await asyncio.gather(
        client.post(f"{BASE}/emergency/stop", json={"reason": "第一击：上游全部超时"}, headers=_hdr(admin_token)),
        client.post(f"{BASE}/emergency/stop", json={"reason": "第二击：重复点击"}, headers=_hdr(admin_token)),
    )
    # 500 也算失败：高危动作连点不能把其中一个变成一条没人看得懂的网络错误
    assert (r1.status_code, r2.status_code) == (200, 200), (r1.text[:200], r2.text[:200])
    bodies = [r1.json(), r2.json()]
    assert [b["code"] for b in bodies] == [0, 0], bodies
    assert sorted([b["data"]["already"] for b in bodies]) == [False, True], (
        "两击应为「一击生效 + 一击判重」，实测两击都以为自己生效了"
    )
    rows = await _audit_rows(maker, "emergency_stop")
    assert len(rows) == 1, f"连点产生了 {len(rows)} 条停服审计"


@pytest.mark.asyncio
async def test_concurrent_stop_keeps_winner_reason_and_time(race, admin_token, monkeypatch):
    """判重的那一击不得覆盖首次停服的原因与时间（追责起点会漂）。"""
    client, maker = race
    _read_window(monkeypatch)
    await asyncio.gather(
        client.post(f"{BASE}/emergency/stop", json={"reason": "第一击原因"}, headers=_hdr(admin_token)),
        client.post(f"{BASE}/emergency/stop", json={"reason": "第二击原因"}, headers=_hdr(admin_token)),
    )
    state = await _state(maker)
    assert state["enabled"] is True
    rows = await _audit_rows(maker, "emergency_stop")
    assert len(rows) == 1
    # 状态与那条唯一审计必须记同一个原因，否则「审计里的原因」是假的
    assert json.loads(rows[0].detail)["reason"] == state["reason"]
    assert state["reason"] in ("第一击原因", "第二击原因")


@pytest.mark.asyncio
async def test_concurrent_resume_writes_one_audit_and_no_500(race, admin_token, monkeypatch):
    """恢复同样是高危动作：连点不报错，且不重复堆审计。"""
    client, maker = race
    await client.post(f"{BASE}/emergency/stop", json={"reason": "故障"}, headers=_hdr(admin_token))
    _read_window(monkeypatch)
    r1, r2 = await asyncio.gather(
        client.post(f"{BASE}/emergency/resume", headers=_hdr(admin_token)),
        client.post(f"{BASE}/emergency/resume", headers=_hdr(admin_token)),
    )
    assert (r1.status_code, r2.status_code) == (200, 200), (r1.text[:200], r2.text[:200])
    bodies = [r1.json(), r2.json()]
    flags = [b["data"].get("already") for b in bodies]
    assert sorted(flags) == [False, True], f"两击恢复应「一击生效 + 一击判重」，实测 {flags}"
    rows = await _audit_rows(maker, "emergency_resume")
    assert len(rows) == 1, f"连点恢复产生了 {len(rows)} 条审计"


@pytest.mark.asyncio
async def test_triple_click_all_200_and_single_audit(race, admin_token, monkeypatch):
    """三击并发：谁都不许拿到 500。

    改成条件写之前，两击撞同一行的写法在 SQLite 下会把后到的那个顶成
    ``database is locked``（读事务升写事务不等 busy_timeout），高危动作换来一条
    没人看得懂的网络错误。
    """
    client, maker = race
    _read_window(monkeypatch, seconds=0.15)
    resps = await asyncio.gather(
        *[
            client.post(f"{BASE}/emergency/stop", json={"reason": f"第{i}击"}, headers=_hdr(admin_token))
            for i in range(3)
        ]
    )
    assert [r.status_code for r in resps] == [200, 200, 200], [r.text[:150] for r in resps]
    bodies = [r.json() for r in resps]
    assert [b["code"] for b in bodies] == [0, 0, 0], bodies
    assert sum(1 for b in bodies if b["data"]["already"] is False) == 1, bodies
    assert len(await _audit_rows(maker, "emergency_stop")) == 1


# ---- 审计可追溯（含操作者与原因）----


@pytest.mark.asyncio
async def test_stop_audit_records_operator_and_reason(race, admin_token):
    """落库那条审计本身：操作者、原因、目标都得在，且原因不是空串。"""
    client, maker = race
    await client.post(
        f"{BASE}/emergency/stop", json={"reason": "上游 TTS 全部超时"}, headers=_hdr(admin_token)
    )
    row = (await _audit_rows(maker, "emergency_stop"))[0]
    assert row.operator == "admin", "审计没有操作者"
    detail = json.loads(row.detail)
    assert detail["reason"] == "上游 TTS 全部超时"
    assert row.target, "审计没有操作目标，事后按对象检索不到"


@pytest.mark.asyncio
async def test_emergency_audit_is_readable(race, admin_token):
    """停服/恢复记录要有人能读到：值班场景在移动端出「谁在何时因为什么」。

    唯一的老审计接口 GET /db-admin/audit-log 硬过滤 category='db_admin'，
    停服写的是 category='mobile'，任何界面都查不到——写了等于没写。
    """
    client, _maker = race
    await client.post(f"{BASE}/emergency/stop", json={"reason": "磁盘写满"}, headers=_hdr(admin_token))
    resp = await client.get(f"{BASE}/emergency/audit", headers=_hdr(admin_token))
    assert resp.status_code == 200, resp.text[:200]
    body = resp.json()
    assert body["code"] == 0
    items = body["data"]["items"]
    assert len(items) == 1
    first = items[0]
    assert first["action"] == "emergency_stop"
    assert first["operator"] == "admin", "列表里没有操作者"
    assert first["reason"] == "磁盘写满", "列表里没有原因"
    assert first["at"], "没有时间点，无法还原停服时长"


@pytest.mark.asyncio
async def test_emergency_audit_newest_first_and_bounded(race, admin_token):
    """倒序 + 有上限：移动端一屏要看到最近一次，而不是最早那次。"""
    client, _maker = race
    for reason in ("第一轮", "第二轮", "第三轮"):
        await client.post(f"{BASE}/emergency/stop", json={"reason": reason}, headers=_hdr(admin_token))
        await client.post(f"{BASE}/emergency/resume", headers=_hdr(admin_token))
    resp = await client.get(f"{BASE}/emergency/audit?limit=2", headers=_hdr(admin_token))
    items = resp.json()["data"]["items"]
    assert len(items) == 2
    assert [it["action"] for it in items] == ["emergency_resume", "emergency_stop"], items
    assert items[1]["reason"] == "第三轮"


@pytest.mark.asyncio
async def test_emergency_audit_does_not_leak_other_categories(race, admin_token):
    """读接口按「category=mobile + 动作白名单」双条件取，不能变成「顺手把别人的审计也捞出来」的口子。

    两条假数据各挡一个方向的松绑：只删 category 条件时「别的模块的同名动作」会漏进来，
    只删 action 条件时「同模块的其他动作」会漏进来。少一条，另一个谓词就成了没牙的摆设。
    """
    client, maker = race
    async with maker() as s:
        s.add(
            AuditLog(
                category="db_admin",
                action="delete",
                target="user",
                operator="someone",
                detail=json.dumps({"reason": "不该出现在移动端"}),
            )
        )
        s.add(
            AuditLog(
                category="db_admin",
                action="emergency_stop",
                target="maintenance_mode",
                operator="db_admin_operator",
                detail=json.dumps({"reason": "别的模块的同名动作"}),
            )
        )
        s.add(
            AuditLog(
                category="mobile",
                action="device_register",
                target="device",
                operator="admin",
                detail=json.dumps({"reason": "同模块的其他动作"}),
            )
        )
        await s.commit()
    await client.post(f"{BASE}/emergency/stop", json={"reason": "故障"}, headers=_hdr(admin_token))

    body = (await client.get(f"{BASE}/emergency/audit", headers=_hdr(admin_token))).json()
    items = body["data"]["items"]
    assert len(items) == 1, items
    assert [it["action"] for it in items] == ["emergency_stop"], items
    assert items[0]["operator"] == "admin", "捞到了别的模块的操作者"
    assert items[0]["reason"] == "故障", items


@pytest.mark.asyncio
async def test_emergency_audit_rejects_out_of_range_limit(race, admin_token):
    """limit 有边界：移动端一次最多要 100 条，传 0 或 5000 都不该放行。"""
    client, _maker = race
    for bad in ("0", "5000"):
        resp = await client.get(
            f"{BASE}/emergency/audit?limit={bad}", headers=_hdr(admin_token)
        )
        # 全站把 FastAPI 的 422 收敛成业务信封里的 400（app/core/exceptions 的校验处理器）
        assert resp.status_code == 400, (bad, resp.status_code, resp.text[:120])
        assert resp.json()["code"] != 0, (bad, resp.text[:120])


@pytest.mark.asyncio
async def test_emergency_audit_caps_rows_at_service_level(race, admin_token):
    """服务层的上限自己守住：调用方绕过路由校验传 5000，也不能把整张审计表捞出来。

    路由的 `le=100` 只挡 HTTP 入口，服务函数还有内部调用方（将来的值班报表之类），
    这条用例钉的是「上限 100 / 下限 1」这个契约本身，不是入口参数校验。
    """
    _client, maker = race
    async with maker() as s:
        s.add_all(
            [
                AuditLog(
                    category="mobile",
                    action="emergency_stop",
                    target="maintenance_mode",
                    operator="admin",
                    detail=json.dumps({"reason": f"第{i}次"}),
                )
                for i in range(102)
            ]
        )
        await s.commit()
    async with maker() as s:
        assert len(await mobile_service.emergency_audit(s, 5000)) == 100
    async with maker() as s:
        # 下限：负数会被 SQLite 当成「无限制 / 语法异常」，服务层自己兜到 1 条
        assert len(await mobile_service.emergency_audit(s, -3)) == 1


@pytest.mark.asyncio
async def test_emergency_audit_requires_auth(race):
    client, _maker = race
    assert (await client.get(f"{BASE}/emergency/audit")).status_code in (401, 403)


@pytest.mark.asyncio
async def test_same_session_read_after_core_write_sees_new_state(race):
    """同一个 session 里「停服 → 提交 → 恢复 → 再读」必须一路读到写完的那一份。

    写用的是 ORM-enabled UPDATE/INSERT，执行后该映射类的实例会在身份图里过期，
    所以后面的 select 会真取一次。这条用例钉的是这个性质本身：
    哪天把写改成 `text("UPDATE …")`（不通知 ORM）或给读取加回 `populate_existing`
    之类的补丁，这里会先红。
    它同时也是「删掉 populate_existing 后行为不变」的证据——探针就是这么证的。
    """
    from types import SimpleNamespace

    _client, maker = race
    admin = SimpleNamespace(username="admin")
    async with maker() as s:
        first = await mobile_service.emergency_stop(s, admin, "同会话写后读")
        await s.commit()
        assert first["enabled"] is True

        # 身份图里此刻已有一行 on=True 的实例；恢复走 ORM-enabled UPDATE 把它翻掉
        resumed = await mobile_service.resume_maintenance(s, admin)
        await s.commit()
        assert resumed["enabled"] is False, "写后同 session 读到的是旧状态"
        assert resumed["already"] is False, "明明翻了状态却自称 already，值班会以为没人恢复"

        again = await mobile_service.get_maintenance(s)
        assert again["enabled"] is False
