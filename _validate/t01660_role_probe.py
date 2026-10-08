"""T01660 角色拆分真实进程验证探针（对隔离副本实例打读写流量）。

用法（先按 runbook 起好 1 sched + N api 的隔离实例，再从 backend 目录跑本脚本）：
    python ../_validate/t01660_role_probe.py --port 8200 --reads 40 --writes 40

做三件事：
1. 读：并发请求 /api/v1/episodes/today 与 /api/v1/channels，统计状态码分布；
2. 写：并发 POST /api/v1/playlogs/progress（token 由隔离副本的用户签发，不落任何真实用户），
   等待写缓冲 flush 后直接查副本库断言进度行已落库 —— 同时证明「api 进程必须自带
   play_write_buffer」这一设计修正是有效的；
3. 扫描实例日志中的 `database is locked` 计数（写前/写后差值即本探针引入的增量）。

安全：只连本机回环端口；密钥从副本 .env 读取且不打印；副本库路径可显式指定。
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def create_token(iso_root: str, user_id: int) -> str:
    """用隔离副本自己的 security.create_access_token 签发 C 端 token。

    为什么不用脚本手写 HMAC：签名密钥由副本实例的 Settings 解析（.env 里同名键
    以末条为准、还可能有引号/注释），脚本自己拼 .env 很容易签出后端验不过的 token
    （实测 401）。直接复用被测代码的签发函数既准确又不用把密钥带进本脚本。
    """
    import sys

    sys.path.insert(0, iso_root)
    from app.core.security import create_access_token

    token, _jti, _exp = create_access_token(str(user_id))
    return token


def make_fixture_user(db_path: str) -> tuple[int, int]:
    """在副本库建一个探针专用用户（隔离副本，不动真实用户）。"""
    openid = f"t01660_probe_{uuid.uuid4().hex[:8]}"
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO user (openid, nickname, total_listen_duration, total_listen_count) "
        "VALUES (?, 'T01660探针用户', 0, 0)",
        (openid,),
    )
    con.commit()
    uid = con.execute("SELECT id FROM user WHERE openid = ?", (openid,)).fetchone()[0]
    ep = con.execute("SELECT id FROM episode LIMIT 1").fetchone()
    con.close()
    return uid, (ep[0] if ep else 1)


def http(method: str, url: str, token: str | None = None, body: dict | None = None) -> tuple[int, float]:
    """返回 (状态码, 客户端耗时 ms)。耗时用于对照 TPS/P95（T01660 验证项 4）。"""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=20) as r:  # NOSONAR: 本机回环探针
            return r.status, (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, (time.perf_counter() - t0) * 1000
    except Exception:
        return 0, (time.perf_counter() - t0) * 1000


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[idx]


def _report(label: str, results: list[tuple[int, float]], secs: float, ok_codes: set) -> dict:
    codes = [r[0] for r in results]
    lats = [r[1] for r in results if r[0] in ok_codes]
    ok = sum(1 for c in codes if c in ok_codes)
    stats = {
        "label": label,
        "n": len(codes),
        "secs": round(secs, 2),
        "tps": round(len(codes) / secs, 1) if secs else 0,
        "ok": ok,
        "codes": {str(k): codes.count(k) for k in set(codes)},
        "p50_ms": round(_pct(lats, 0.50), 1),
        "p95_ms": round(_pct(lats, 0.95), 1),
        "p99_ms": round(_pct(lats, 0.99), 1),
        "max_ms": round(max(lats), 1) if lats else 0,
    }
    print(f"[{label}] n={stats['n']} / {secs:.2f}s → TPS={stats['tps']} 成功={ok} "
          f"失败={len(codes) - ok} 分布={json.dumps(stats['codes'])}")
    if lats:
        print(f"[{label}] 延迟 ms：p50={stats['p50_ms']} p95={stats['p95_ms']} "
              f"p99={stats['p99_ms']} max={stats['max_ms']}")
    return stats


def count_locked(log_path: str) -> int:
    if not os.path.exists(log_path):
        return -1
    raw = open(log_path, "rb").read()
    txt = raw.decode("utf-8", errors="replace") if raw[:1] != b"\x00" else ""
    return len(re.findall(r"database is locked", txt, re.I))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8200)
    ap.add_argument("--reads", type=int, default=200)
    ap.add_argument("--writes", type=int, default=60)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--label", default="probe", help="本轮标识（A/B 对照用，如 all_w1 / split_w2）")
    ap.add_argument("--out", default=None, help="把本轮统计追加写入该 JSON 文件（每轮一行）")
    ap.add_argument("--iso-root", default=".", help="隔离副本 backend 目录（数据目录与 token 签发都取自它）")
    ap.add_argument("--db", default=None, help="副本 news.db 路径，默认 <iso-root>/data/news.db")
    ap.add_argument("--log", default=None, help="实例合并日志，默认 <iso-root>/run_orchestrate.log")
    args = ap.parse_args()
    args.db = args.db or os.path.join(args.iso_root, "data", "news.db")
    args.log = args.log or os.path.join(args.iso_root, "run_orchestrate.log")

    base = f"http://127.0.0.1:{args.port}"
    locked_before = count_locked(args.log)

    uid, episode_id = make_fixture_user(args.db)

    t0 = time.time()
    read_paths = [
        "/api/v1/episodes/today",
        "/api/v1/channels",
        f"/api/v1/episodes/{episode_id}",
    ]
    with cf.ThreadPoolExecutor(args.workers) as ex:
        reads = list(ex.map(lambda i: http("GET", base + read_paths[i % len(read_paths)]), range(args.reads)))
    read_secs = time.time() - t0
    read_stats = _report(f"{args.label}.reads", reads, read_secs, {200})

    token = create_token(args.iso_root, uid)

    t0 = time.time()
    with cf.ThreadPoolExecutor(args.workers) as ex:
        writes = list(ex.map(
            lambda i: http("POST", base + "/api/v1/playlogs/progress", token,
                           {"episode_id": episode_id, "position": 30 + i, "duration": 600}),
            range(args.writes)))
    write_secs = time.time() - t0
    write_stats = _report(f"{args.label}.writes", writes, write_secs, {200, 201})

    # 写缓冲周期 flush 间隔 1s，留 3s 余量后直接查副本库断言落库
    time.sleep(3)
    con = sqlite3.connect(args.db)
    row = con.execute(
        "select position, updated_at from play_progress where user_id=? and episode_id=?",
        (uid, episode_id),
    ).fetchone()
    buf_flushed = con.execute("select count(*) from play_log where user_id=?", (uid,)).fetchone()[0]
    con.close()
    print(f"[persist] play_progress 行={row is not None} position={row[0] if row else None} "
          f"play_log 行数={buf_flushed}")

    locked_after = count_locked(args.log)
    locked_delta = locked_after - locked_before
    print(f"[locked] database is locked 计数：写前={locked_before} 写后={locked_after} 增量={locked_delta}")

    summary = {
        "label": args.label,
        "port": args.port,
        "reads": read_stats,
        "writes": write_stats,
        "persisted": bool(row),
        "play_log_rows": buf_flushed,
        "locked_delta": locked_delta,
    }
    if args.out:
        rows = []
        if os.path.exists(args.out):
            try:
                rows = json.load(open(args.out, encoding="utf-8"))
            except Exception:
                rows = []
        rows.append(summary)
        json.dump(rows, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[out] 统计已写入 {args.out}（累计 {len(rows)} 轮）")

    return 0 if (
        read_stats["ok"] >= args.reads * 0.98
        and write_stats["ok"] >= args.writes * 0.98
        and row
        and locked_delta == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
