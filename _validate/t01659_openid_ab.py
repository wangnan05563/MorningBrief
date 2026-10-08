"""T01659：openid 二次查库削减的单变量 A/B（不依赖压测机负载）。

门禁 TPS 在本机 run-to-run 抖动 ±40%，无法分辨 1~3ms 的每请求差异；
这里用同进程交替采样，只比较「一次请求里取 openid」的两条路径：
  A（改造前）：新建 session → SELECT openid → 业务查询
  B（改造后）：新建 session → get_user_openid（命中进程内缓存，零查库）→ 业务查询
业务查询用 /api/v1/favorites 列表的实际 SQL（favorite join episode），
使两组承担相同的其余成本，差值即缓存削掉的部分。
"""
import asyncio
import os
import shutil
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "backend"))

SRC_DB = REPO / "backend" / "data" / "news.db"
TMP = HERE / "t01659_ab_tmp"

N_ROUND = 30          # 每个用户重复轮数
N_USER = 20           # 交替取样用户数


async def setup_db() -> str:
    TMP.mkdir(exist_ok=True)
    db = TMP / "news_copy.db"
    if db.exists():
        db.unlink()
    shutil.copy2(SRC_DB, db)
    for ext in ("-wal", "-shm"):
        src = Path(str(SRC_DB) + ext)
        if src.exists():
            shutil.copy2(src, Path(str(db) + ext))
    # 补造足够样本用户 + 每人 5 条收藏，保证列表 SQL 有真实工作量
    from sqlalchemy import text
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text("SELECT id FROM user ORDER BY id"))).fetchall()
        have = [r[0] for r in rows]
        while len(have) < N_USER:
            uid = 950_000 + len(have)
            await s.execute(text("INSERT INTO user(id, openid) VALUES(:i,:o)"),
                            {"i": uid, "o": f"ab_openid_{uid}"})
            have.append(uid)
        ep_ids = [r[0] for r in (await s.execute(
            text("SELECT id FROM episode ORDER BY id LIMIT 5"))).fetchall()]
        if not ep_ids:
            raise SystemExit("库中无 episode，A/B 无意义")
        for uid in have[:N_USER]:
            for eid in ep_ids:
                await s.execute(text(
                    "INSERT OR IGNORE INTO favorite(user_id, episode_id, created_at) "
                    "VALUES(:u,:e,datetime('now'))"), {"u": uid, "e": eid})
        await s.commit()
    return have[:N_USER], ep_ids


LIST_SQL = """
SELECT f.id, f.created_at, e.id, e.title, e.duration
FROM favorite f JOIN episode e ON e.id = f.episode_id
WHERE f.user_id = :u
ORDER BY f.created_at DESC LIMIT 50
"""


async def run_ab(user_ids, ep_ids):
    from sqlalchemy import text
    from app.database import AsyncSessionLocal
    from app.cache.manager import cache as cache_manager
    from app.services.user_service import get_user_openid

    # 预热缓存（B 组测的是「命中」路径，A 组测的是「查库」路径）
    async with AsyncSessionLocal() as s:
        for u in user_ids:
            await get_user_openid(s, u)

    a_ms, b_ms = [], []
    for rnd in range(N_ROUND):
        for u in user_ids:
            # A：改造前 —— openid 走一次 SELECT
            async with AsyncSessionLocal() as s:
                t0 = time.perf_counter()
                oid = (await s.execute(text("SELECT openid FROM user WHERE id=:i"),
                                       {"i": u})).scalar_one()
                await s.execute(text(LIST_SQL), {"u": u})
                a_ms.append((time.perf_counter() - t0) * 1000)
                assert isinstance(oid, str)
            # B：改造后 —— openid 命中进程内缓存
            async with AsyncSessionLocal() as s:
                t0 = time.perf_counter()
                oid2 = await get_user_openid(s, u)
                await s.execute(text(LIST_SQL), {"u": u})
                b_ms.append((time.perf_counter() - t0) * 1000)
                assert oid2 == oid, f"跨用户串号 user_id={u}"
    return a_ms, b_ms


def pct(xs, p):
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1)))))
    return xs[k]


async def main():
    os.environ["SQLITE_DB_PATH"] = str((TMP / "news_copy.db"))
    user_ids, ep_ids = await setup_db()
    a, b = await run_ab(user_ids, ep_ids)
    n = len(a)
    summary = {
        "样本": f"{n} 对（同进程交替，A=查库 B=缓存命中）",
        "A_p50_ms": round(statistics.median(a), 3),
        "B_p50_ms": round(statistics.median(b), 3),
        "A_p95_ms": round(pct(a, 95), 3),
        "B_p95_ms": round(pct(b, 95), 3),
        "A_mean_ms": round(statistics.fmean(a), 3),
        "B_mean_ms": round(statistics.fmean(b), 3),
        "每请求削减_ms": round(statistics.fmean(a) - statistics.fmean(b), 3),
        "削减占比_pct": round(100 * (statistics.fmean(a) - statistics.fmean(b)) / statistics.fmean(a), 1),
    }
    for k, v in summary.items():
        print(f"{k}: {v}")
    out = HERE / "t01659_openid_ab.json"
    import json
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    from app.database import engine
    await engine.dispose()
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
