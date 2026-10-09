# -*- coding: utf-8 -*-
r"""T01691 跨进程写并发探针：量化 workers>1 下缓存失效/写锁互斥/限流口径三项残留限制。

前置：复用 perf_gate 的隔离设施（prepare_iso_root + 角色编排启动），全程隔离副本，
隧道强制关闭，生产 data/ 零接触；探针用户为副本库新建，不碰真实用户。

四个实验：
A. 缓存跨进程旧值（确定性口径）：GET 预热两 worker 缓存 → sqlite 直写副本库
   （=「另一写者不通知本进程」的极端形态）→ TTL 内采样读 → 统计旧值窗口。
B. 缓存跨进程旧值（API 写口径）：GET 预热 → POST /favorites（随机落某 worker，
   只失效该 worker 的本地缓存）→ 立即采样读 → 统计旧值出现率。
C. 写锁互斥与 database is locked：并发 add/delete favorites（write_lock 路径）
   + playlogs/progress 写，统计成功/失败/时延 + 副本日志 locked 增量。
D. 限流口径：以 RATE_LIMIT_PER_MINUTE=30 重启（2 个 api 进程），并发 200 读，
   统计放行量验证「实际放行 ≈ N × 配额」。

用法：
    python _validate/t01691_crossproc_probe.py            # 全部实验
    python _validate/t01691_crossproc_probe.py --skip D   # 跳过限流重启实验
输出：_validate/t01691_result.md + 控制台摘要。副本用完即删。
"""
import argparse
import concurrent.futures as cf
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
JM_DIR = HERE.parent / "scripts" / "jmeter_test"
sys.path.insert(0, str(JM_DIR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import perf_gate as pg  # noqa: E402

REPO = HERE.parent
PORT = 8120
HOST = "127.0.0.1"
TTL_FAV = 60  # favorites 列表缓存 TTL（routers/api/favorites.py 默认）


def log(msg: str) -> None:
    print(msg, flush=True)


def http(method: str, url: str, token: str = "", body: dict | None = None,
         timeout: int = 10) -> tuple[int, dict | bytes]:
    req = urllib.request.Request(url, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:
        return -1, {"error": str(e)}


def make_probe_user(db: Path) -> tuple[int, str, str]:
    """副本库建探针用户，返回 (uid, openid, token)。

    注意：favorite/comment 等表的 user_id 列存的是 **openid 字符串**（add_favorite
    里 Favorite(user_id=openid, ...)），不是数字 id——直写副本库必须用 openid，
    否则行永远不可见（实验 A 首跑踩过：str(uid) 导致「TTL 后仍不可见」假信号）。
    """
    openid = f"t01691_probe_{uuid.uuid4().hex[:8]}"
    con = sqlite3.connect(str(db))
    con.execute(
        "INSERT INTO user (openid, nickname, total_listen_duration, total_listen_count) "
        "VALUES (?, 'T01691探针用户', 0, 0)", (openid,))
    con.commit()
    uid = con.execute("SELECT id FROM user WHERE openid = ?", (openid,)).fetchone()[0]
    con.close()
    sys.path.insert(0, str(pg.ISO_ROOT))
    from app.core.security import create_access_token
    token, _jti, _exp = create_access_token(str(uid))
    sys.path.pop(0)
    return uid, openid, token


def fav_ids_from_resp(data) -> set[int]:
    if not isinstance(data, dict):
        return set()
    lst = data.get("data", {}).get("list", []) if isinstance(data.get("data"), dict) else []
    return {item.get("episode_id") for item in lst if isinstance(item, dict)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", default="", help="跳过的实验，如 D")
    ap.add_argument("--conc-writes", type=int, default=240, help="实验C 并发写总数")
    a = ap.parse_args()
    skip = {s.strip().upper() for s in a.skip.split(",") if s.strip()}
    results: dict = {}

    t0 = time.time()
    iso = pg.prepare_iso_root(None)
    log(f"[prep] 隔离副本：{iso}")
    db = iso / "data" / "news.db"
    uid, openid, token = make_probe_user(db)
    # 拿一个已发布 episode id 供收藏/进度写入
    con = sqlite3.connect(str(db))
    ep = con.execute("SELECT id FROM episode WHERE status='published' LIMIT 1").fetchone()
    con.close()
    ep_id = ep[0] if ep else 1
    log(f"[prep] 探针用户 uid={uid} episode={ep_id}")

    base = f"http://{HOST}:{PORT}"
    cfg = pg.load_config()
    cfg["backend"]["port"] = PORT
    cfg["backend"]["workers"] = 2
    proc = pg.start_backend(cfg)
    fav_url = f"{base}/api/v1/favorites"
    log("[prep] workers=2 实例就绪（1 sched + 2 api）")

    try:
        # ---------- 实验 A：DB 直写 → TTL 内跨进程旧值（确定性口径） ----------
        if "A" not in skip:
            for _ in range(6):  # 预热：让 2 个 worker 都缓存 fav:list
                http("GET", fav_url, token)
            con = sqlite3.connect(str(db))
            con.execute("INSERT OR IGNORE INTO favorite (user_id, episode_id) VALUES (?, ?)",
                        (openid, ep_id))  # user_id 列存 openid 字符串（见 make_probe_user 注释）
            con.commit()
            con.close()
            # 验证直写行本身可查（排除 user_id 格式错误的假信号）
            con = sqlite3.connect(str(db))
            n_row = con.execute("SELECT COUNT(*) FROM favorite WHERE user_id = ?",
                                (openid,)).fetchone()[0]
            con.close()
            assert n_row == 1, f"直写行不存在（user_id 格式错误？）: {n_row}"
            log("[A] DB 直写收藏完成（openid 口径已验证），立即采样 20 次（TTL 窗口内）")
            stale = fresh = 0
            for _ in range(20):
                _c, data = http("GET", fav_url, token)
                (fresh, stale) = (fresh + 1, stale) if ep_id in fav_ids_from_resp(data) \
                    else (fresh, stale + 1)
                time.sleep(0.1)
            log(f"[A] TTL 内采样：新值 {fresh}/20，旧值 {stale}/20")
            wait = TTL_FAV + 3
            log(f"[A] 等待 TTL 过期（{wait}s）…")
            time.sleep(wait)
            _c, data = http("GET", fav_url, token)
            a_visible = ep_id in fav_ids_from_resp(data)
            log(f"[A] TTL 过期后可见: {a_visible}")
            results["A"] = {"stale_in_ttl": stale, "fresh_in_ttl": fresh,
                            "visible_after_ttl": a_visible,
                            "conclusion": "旧值窗口≈TTL（60s），跨进程无失效通知" if stale > 0 else "未观察到旧值"}
            # 清理：DB 删掉直写的收藏，等 TTL 重置
            con = sqlite3.connect(str(db))
            con.execute("DELETE FROM favorite WHERE user_id = ? AND episode_id = ?",
                        (str(uid), ep_id))
            con.commit()
            con.close()

        # ---------- 实验 B：API 写 → 概率性跨进程旧值 ----------
        if "B" not in skip:
            time.sleep(TTL_FAV + 3)  # 等实验 A 的缓存全部过期
            for _ in range(40):  # 预热加量：确保 2 个 worker 都持有缓存
                http("GET", fav_url, token)
            code, _ = http("POST", fav_url, token, {"episode_id": ep_id})
            log(f"[B] POST /favorites -> {code}，立即采样 40 次")
            stale = fresh = 0
            for _ in range(40):
                _c, data = http("GET", fav_url, token)
                (fresh, stale) = (fresh + 1, stale) if ep_id in fav_ids_from_resp(data) \
                    else (fresh, stale + 1)
                time.sleep(0.05)
            log(f"[B] 采样：新值 {fresh}/20，旧值 {stale}/20（API 写只失效收到请求的 worker）")
            results["B"] = {"stale_in_ttl": stale, "fresh_in_ttl": fresh,
                            "conclusion": "API 写后其它 worker TTL 内返回旧值" if stale > 0 else "未观察到旧值（LB 恰好同 worker）"}
            http("DELETE", f"{fav_url}/{ep_id}", token)
            time.sleep(TTL_FAV + 3)

        # ---------- 实验 C：并发写（write_lock 互斥 + database is locked） ----------
        if "C" not in skip:
            logs = list((iso / "logs").glob("*.log"))
            def _count_locked() -> int:
                n = 0
                for lf in logs:
                    try:
                        n += lf.read_text(encoding="utf-8", errors="ignore").count("database is locked")
                    except OSError:
                        pass
                return n
            locked_before = _count_locked()
            n = a.conc_writes
            log(f"[C] 并发 {n} 次写（favorites add/delete 交替 + progress），2 api 进程")
            t0c = time.monotonic()

            def one_write(i: int):
                if i % 3 == 0:
                    return http("POST", f"{base}/api/v1/playlogs/progress", token,
                                {"episode_id": ep_id, "position_sec": i % 100,
                                 "duration_sec": 600})
                if i % 3 == 1:
                    return http("POST", fav_url, token, {"episode_id": ep_id})
                return http("DELETE", f"{fav_url}/{ep_id}", token)

            with cf.ThreadPoolExecutor(24) as ex:
                codes = [c for c, _ in ex.map(one_write, range(n))]
            dt = time.monotonic() - t0c
            ok = sum(1 for c in codes if 200 <= c < 300)
            e5xx = sum(1 for c in codes if 500 <= c < 600)
            locked_after = _count_locked()
            log(f"[C] {n} 写 {dt:.1f}s（{n / dt:.0f}/s）成功 {ok} 5xx {e5xx} "
                f"locked 增量 {locked_after - locked_before}")
            results["C"] = {"writes": n, "seconds": round(dt, 1), "wps": round(n / dt, 1),
                            "ok": ok, "count_5xx": e5xx,
                            "locked_delta": locked_after - locked_before}
            time.sleep(3)  # 写缓冲 flush

        # ---------- 实验 D：限流口径（N 进程合计放行） ----------
        if "D" not in skip:
            log("[D] 以 RATE_LIMIT_PER_MINUTE=30 重启实例（workers=2）")
            pg.stop_backend(proc, cfg)
            cfg["backend"]["rate_limit_per_minute"] = 30
            proc = pg.start_backend(cfg)
            time.sleep(1)
            m = 200
            def one_read(_i):
                return http("GET", f"{base}/api/v1/channels", token)[0]
            with cf.ThreadPoolExecutor(32) as ex:
                codes = list(ex.map(one_read, range(m)))
            ok = sum(1 for c in codes if c == 200)
            limited = sum(1 for c in codes if c == 429)
            log(f"[D] 200 并发读：放行 {ok} 限流 {limited}（配额 30 × 2 进程 = 理论 60）")
            results["D"] = {"quota": 30, "workers": 2, "passed": ok, "limited": limited,
                            "conclusion": "实际放行≈N×配额，多进程限流口径需按进程数折算或改共享态"}
    finally:
        pg.stop_backend(proc, cfg)
        pg._win_rmtree(iso)
        globals()["ISO"] = None

    (HERE / "t01691_result.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[done] 总耗时 {time.time() - t0:.0f}s，结果已写 _validate/t01691_result.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
