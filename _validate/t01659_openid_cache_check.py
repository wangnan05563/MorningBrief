"""T01659 验证：get_user_openid 进程内缓存的正确性（跨用户隔离 + 回源 + 无负缓存）。

用 dev 库的**只读副本**（不碰生产 ./data/news.db），取库里全部真实用户：
1. 首轮逐个查库得到 openid 基线；
2. 二轮全部走缓存，断言每个 user_id 拿回的仍是自己的 openid（跨用户零串号）；
3. 直接改库里某个用户的 openid，断言缓存期内返回旧值（=TTL 陈旧窗口，符合预期）、
   清缓存后回源得到新值；
4. 不存在的 user_id 断言抛 NotFoundError，且不留负缓存（下一次真实用户仍可正确取到）。
"""
import asyncio
import shutil
import sys
import time
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.cache.manager import cache as cache_manager  # noqa: E402
from app.core.exceptions import NotFoundError  # noqa: E402
from app.models import User  # noqa: E402
from app.services.user_service import get_user_openid  # noqa: E402

SRC_DB = Path(__file__).resolve().parent.parent / "backend" / "data" / "news.db"
TMP_DIR = Path(__file__).resolve().parent / "t01659_tmpdb"


async def main() -> int:
    TMP_DIR.mkdir(exist_ok=True)
    tmp_db = TMP_DIR / "news_copy.db"
    if tmp_db.exists():
        tmp_db.unlink()
    shutil.copy2(SRC_DB, tmp_db)
    for ext in ("-wal", "-shm"):
        src = Path(str(SRC_DB) + ext)
        if src.exists():
            shutil.copy2(src, Path(str(tmp_db) + ext))

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_db.as_posix()}")
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 库内真实用户仅 2 个，跨用户隔离样本太弱：向**副本**补造 50 个用户扩大矩阵
    async with Session() as s:
        existing = {r[0] for r in (await s.execute(select(User.id))).all()}
        seeded = 0
        for i in range(1, 51):
            uid = 900_000 + i
            if uid in existing:
                continue
            s.add(User(id=uid, openid=f"synthetic_openid_{uid}"))
            seeded += 1
        await s.commit()

    checks = []

    async with Session() as s:
        rows = (await s.execute(select(User.id, User.openid).order_by(User.id))).all()
    users = [(r[0], r[1]) for r in rows]
    checks.append(("库内用户数（含补造）", len(users) >= 50, f"{len(users)} 用户，补造 {seeded}"))
    if len(users) < 2:
        print("样本不足，无法验证跨用户隔离")
        return 1

    # 1) 首轮：全部未命中 → 回源查库
    async with Session() as s:
        base = {}
        t0 = time.perf_counter()
        for uid, _ in users:
            base[uid] = await get_user_openid(s, uid)
        cold_ms = (time.perf_counter() - t0) * 1000

    # 2) 二轮：全部命中缓存，逐用户比对基线（跨用户隔离）
    async with Session() as s:
        warm = {}
        t0 = time.perf_counter()
        for uid, _ in users:
            warm[uid] = await get_user_openid(s, uid)
        warm_ms = (time.perf_counter() - t0) * 1000
    checks.append(("缓存后仍逐用户返回自身 openid", warm == base, f"{len(base)} 用户全一致"))
    checks.append((
        "命中值与库内原始列一致",
        all(warm[uid] == openid for uid, openid in users),
        "",
    ))
    checks.append(("二轮耗时低于首轮（缓存生效）", warm_ms < cold_ms, f"cold={cold_ms:.2f}ms warm={warm_ms:.3f}ms"))
    cache_keys = [k for k in cache_manager._cache.keys() if str(k).startswith("user:openid:")]
    checks.append(("缓存键按 user_id 维度且无多余", len(cache_keys) == len(users), f"{len(cache_keys)} keys"))

    # 3) 直改库：缓存期内返回旧值；清 key 后回源得到新值（取真实用户，避开补造的固定 id 段）
    real = [(u, o) for u, o in users if u < 900_000]
    probe_uid, probe_old = real[0]
    probe_new = f"openid_changed_{probe_uid}"
    async with Session() as s:
        await s.execute(text("UPDATE user SET openid=:o WHERE id=:i"), {"o": probe_new, "i": probe_uid})
        await s.commit()
    async with Session() as s:
        cached_val = await get_user_openid(s, probe_uid)
    checks.append(("缓存期内不回源（返回旧值=TTL 陈旧窗口）", cached_val == probe_old, f"{cached_val} != {probe_new}"))
    await cache_manager.delete(f"user:openid:{probe_uid}")
    async with Session() as s:
        fresh_val = await get_user_openid(s, probe_uid)
    checks.append(("清缓存后回源得到新值", fresh_val == probe_new, fresh_val))

    # 其它用户不受该用户失效影响
    other = users[1][0]
    async with Session() as s:
        checks.append(("单用户失效不波及其它用户", await get_user_openid(s, other) == base[other], str(other)))

    # 4) 不存在的 id：抛 NotFoundError 且不写负缓存
    missing = max(uid for uid, _ in users) + 999_999
    raised = False
    async with Session() as s:
        try:
            await get_user_openid(s, missing)
        except NotFoundError:
            raised = True
    checks.append(("不存在用户抛 NotFoundError", raised, str(missing)))
    checks.append((
        "无负缓存残留",
        await cache_manager.get(f"user:openid:{missing}") is None,
        "",
    ))

    # 恢复副本库改动无意义（副本文件用完即删），生产库全程未写
    ok = True
    for name, passed, detail in checks:
        print(("PASS  " if passed else "FAIL  ") + name + (f"  [{detail}]" if detail else ""))
        ok = ok and passed
    await engine.dispose()
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    print("\n结论:", "ALL_PASS" if ok else "HAS_FAILURE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
