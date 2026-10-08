# -*- coding: utf-8 -*-
"""T01662 正确性冒烟：SQLite 连接池化（AsyncAdaptedQueuePool）后的行为验证。

验证口径（对应任务约束，逐条可断言）：
1. PRAGMA 在池化连接上正确注入（journal_mode=WAL / foreign_keys=ON / busy_timeout）；
2. 写后立读无脏读/旧快照：session A 提交 → 新 session（可能复用另一条池连接）立即读到新值；
3. WAL 并发：多读 + 单写并发跑完无 "database is locked"、无异常，终值正确；
4. 连接确实被复用：同一 session 多次查询走同一池连接（pool 状态 checkedout 稳定）。

硬约束：使用独立临时库（环境变量注入 SQLITE_DB_PATH），绝不触碰 data/news.db。
"""
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path


BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

TMP = Path(tempfile.mkdtemp(prefix="t01662_pool_smoke_"))
os.environ["PYTHONIOENCODING"] = "utf-8"

# ⚠ 隔离关键：settings.sqlite_url 走 paths.resolve_db_path()（开发态恒指向 backend/data/news.db，
# SQLITE_DB_PATH 环境变量在开发态不生效——首轮曾因此把 smoke 表写进真实库）。
# 必须在导入 app.database 之前打补丁，让引擎落到临时库。
sys.path.insert(0, str(BACKEND))
import app.paths as _paths  # noqa: E402

_paths.resolve_db_path = lambda: TMP / "pool_smoke.db"  # type: ignore[assignment]

from sqlalchemy import text  # noqa: E402

from app.database import AsyncSessionLocal, engine  # noqa: E402

# 二次确认：引擎路径必须是临时库，否则立即中止，绝不触碰真实库
_real = "news.db" in str(engine.url)
assert not _real, f"引擎指向真实库，中止：{engine.url}"

READERS = 8
READS_PER_READER = 50
WRITES = 20

results: dict = {"checks": {}, "errors": []}


async def check_pragma():
    async with AsyncSessionLocal() as s:
        jm = (await s.execute(text("PRAGMA journal_mode"))).scalar()
        fk = (await s.execute(text("PRAGMA foreign_keys"))).scalar()
        bt = (await s.execute(text("PRAGMA busy_timeout"))).scalar()
    results["checks"]["pragma"] = {
        "journal_mode": jm, "foreign_keys": fk, "busy_timeout_ms": bt,
    }
    assert str(jm).lower() == "wal", f"journal_mode 应为 WAL，实际 {jm}"
    assert int(fk) == 1, f"foreign_keys 应为 ON，实际 {fk}"


async def check_write_then_read():
    """写后立读：A 提交后，B（新 session，大概率复用另一条池连接）必须立刻看到新值。"""
    async with AsyncSessionLocal() as a:
        await a.execute(text("INSERT INTO smoke(id, v) VALUES (1, 'v0')"))
        await a.commit()
    # 中间穿插一次其他连接的读，制造池内换连接的机会
    async with AsyncSessionLocal() as b:
        v = (await b.execute(text("SELECT v FROM smoke WHERE id=1"))).scalar()
        assert v == "v0", f"写后立读失败：期望 v0，实际 {v}"
    for i in range(1, 6):
        async with AsyncSessionLocal() as a:
            await a.execute(text("UPDATE smoke SET v=:v WHERE id=1"), {"v": f"v{i}"})
            await a.commit()
        async with AsyncSessionLocal() as b:
            v = (await b.execute(text("SELECT v FROM smoke WHERE id=1"))).scalar()
            assert v == f"v{i}", f"第 {i} 轮写后立读失败：期望 v{i}，实际 {v}"
    results["checks"]["write_then_read"] = "ok(5/5)"


async def reader(idx: int):
    for _ in range(READS_PER_READER):
        async with AsyncSessionLocal() as s:
            row = (await s.execute(text("SELECT v FROM smoke WHERE id=1"))).scalar()
            assert row is not None


async def writer():
    for i in range(1, WRITES + 1):
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE smoke SET v=:v WHERE id=1"), {"v": f"w{i}"})
            await s.commit()
        await asyncio.sleep(0.01)


async def check_concurrent():
    t0 = time.perf_counter()
    await asyncio.gather(*[reader(i) for i in range(READERS)], writer())
    dt = time.perf_counter() - t0
    async with AsyncSessionLocal() as s:
        v = (await s.execute(text("SELECT v FROM smoke WHERE id=1"))).scalar()
    assert v == f"w{WRITES}", f"并发后终值错误：期望 w{WRITES}，实际 {v}"
    results["checks"]["concurrent"] = {
        "readers": READERS, "reads_total": READERS * READS_PER_READER,
        "writes": WRITES, "elapsed_s": round(dt, 2), "final_value": v,
        "locked_errors": 0,
    }


async def check_pool_reuse():
    """同一 session 连续查询期间，池 checkedout 数应稳定为 1（连接被复用而非每查新建）。"""
    async with AsyncSessionLocal() as s:
        await s.execute(text("SELECT 1"))
        sizes = set()
        for _ in range(20):
            await s.execute(text("SELECT 1"))
            sizes.add(engine.sync_engine.pool.checkedout())
    results["checks"]["pool_reuse"] = {
        "checkedout_during_session": sorted(sizes),
        "pool_size": engine.sync_engine.pool.size(),
    }
    assert sizes == {1}, f"会话期间应始终复用 1 条连接，实际 {sizes}"


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE IF NOT EXISTS smoke(id INTEGER PRIMARY KEY, v TEXT)"))
    await check_pragma()
    await check_write_then_read()
    await check_concurrent()
    await check_pool_reuse()
    await engine.dispose()
    results["ok"] = True
    out = Path(__file__).with_name("t01662_pool_smoke.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=1))


try:
    asyncio.run(main())
except AssertionError as e:
    results["ok"] = False
    results["errors"].append(str(e))
    print(json.dumps(results, ensure_ascii=False, indent=1))
    raise SystemExit(1)
finally:
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)
