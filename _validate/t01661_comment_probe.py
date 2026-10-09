"""T01661 写路径每请求归因驱动（配合 `_t01661_probe` 分段计时补丁）。

前置：按 `_validate/t01661_runbook.md` 在**隔离副本**上打好探针补丁并起好实例。

用法：
    backend/.venv/Scripts/python.exe _validate/t01661_comment_probe.py \
        --port 8411 --iso-root "C:/path/to/iso/backend" --seq 12 --burst 20

做三件事：
1. 顺序写（无并发）→ 拿到「每请求固定开销」的分段分解（鉴权/查库/建连 PRAGMA/等锁/提交/日志 sink）；
2. 并发写（burst）→ 看 `lock_wait` 是否随并发放大（全局写锁的串行代价）；
3. 解析实例日志中的 `[T01661PROBE]` 行，输出分段中位数与占比表（结果口径模板即本表）。

安全：只连本机回环；token 由被测副本自身的 `create_access_token` 签发；
探针用户写在**副本库**，绝不触碰 dev 库真实用户（id 1、2）。
"""
import argparse
import concurrent.futures as cf
import io
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t01660_role_probe import create_token, http, make_fixture_user  # noqa: E402

PROBE_RE = re.compile(
    r"\[T01661PROBE\] endpoint=(?P<ep>.+?) total=(?P<total>[\d.]+)ms"
)
SEG_RE = re.compile(r"(?P<name>[a-z_]+)=(?P<ms>[\d.]+)ms")
_SEG_EXCLUDE = {"total", "conn_pragma", "sink_prev"}
TAIL_RE = re.compile(
    r"conn_new=(?P<cn>\d+) conn_pragma=(?P<cp>[\d.]+)ms sink_prev=(?P<sp>[\d.]+)ms"
)


def parse_probe_lines(path: str, since_offset: int) -> list[dict]:
    """读取日志新增部分中的探针行（Windows 控制台落盘常为 GBK，双编码兜底）。"""
    raw = io.open(path, "rb").read()[since_offset:]
    for enc in ("utf-8", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            text = raw.decode(enc, errors="replace")
    rows = []
    for line in text.splitlines():
        head = PROBE_RE.search(line)
        if not head:
            continue
        tail = TAIL_RE.search(line)
        segs = {
            m.group("name"): float(m.group("ms"))
            for m in SEG_RE.finditer(line)
            if m.group("name") not in _SEG_EXCLUDE
        }
        rows.append({
            "endpoint": head.group("ep"),
            "total": float(head.group("total")),
            "segs": segs,
            "conn_new": int(tail.group("cn")) if tail else 0,
            "conn_pragma": float(tail.group("cp")) if tail else 0.0,
            "sink_prev": float(tail.group("sp")) if tail else 0.0,
        })
    return rows


def report(title: str, rows: list[dict], client_ms: list[float]) -> None:
    print(f"\n=== {title}（n={len(rows)}）===")
    if not rows:
        print("  无探针行——检查补丁是否打在运行中的那份代码上、日志路径/偏移是否正确")
        return
    names = sorted({k for r in rows for k in r["segs"]})
    total = statistics.median([r["total"] for r in rows])
    print(f"  {'段':<14}{'中位ms':>9}{'占比':>8}")
    print(f"  {'服务端 total':<13}{total:>9.1f}{100:>7.0f}%")
    if client_ms:
        print(f"  {'客户端往返':<14}{statistics.median(client_ms):>9.1f}{'—':>8}")
    for n in names:
        vals = [r["segs"][n] for r in rows if n in r["segs"]]
        med = statistics.median(vals)
        print(f"  {n:<14}{med:>9.1f}{med / total * 100:>7.0f}%")
    for extra in ("conn_pragma", "sink_prev"):
        print(f"  {extra:<14}{statistics.median([r[extra] for r in rows]):>9.1f}"
              f"{statistics.median([r[extra] for r in rows]) / total * 100:>7.0f}%")
    print(f"  本批新建连接数合计={sum(r['conn_new'] for r in rows)}"
          f"（连接池开启后应为 0；>0 说明 PRAGMA 建连成本仍在请求路径内）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8411)
    ap.add_argument("--iso-root", required=True, help="隔离副本 backend 目录（Windows 路径）")
    ap.add_argument("--log", default=None,
                    help="实例 app 日志，默认 <iso-root>/logs/MorningBrief_<date>.log"
                         "（loguru 文件 sink；stdout 重定向文件里没有探针行）")
    ap.add_argument("--seq", type=int, default=12, help="顺序写样本数（每请求固定开销归因）")
    ap.add_argument("--burst", type=int, default=20, help="并发写样本数（等锁放大归因）")
    ap.add_argument("--gap-ms", type=int, default=300)
    ap.add_argument("--out", default=None, help="把原始探针行落盘为 JSON（结果口径附证）")
    args = ap.parse_args()
    args.log = args.log or os.path.join(
        args.iso_root, "logs", f"MorningBrief_{time.strftime('%Y-%m-%d')}.log")

    db = os.path.join(args.iso_root, "data", "news.db")
    uid, episode_id = make_fixture_user(db)
    token = create_token(args.iso_root, uid)
    base = f"http://127.0.0.1:{args.port}/api/v1/comments"
    offset = os.path.getsize(args.log) if os.path.exists(args.log) else 0

    seq_ms = []
    for i in range(args.seq):
        code, ms = http("POST", base, token,
                        {"episode_id": episode_id, "content": f"T01661顺序探针 {i}"})
        seq_ms.append(ms)
        if code not in (200, 201):
            print(f"  [warn] 顺序写 #{i} 返回 {code}")
        time.sleep(args.gap_ms / 1000)

    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(8) as ex:
        burst = list(ex.map(
            lambda i: http("POST", base, token,
                           {"episode_id": episode_id, "content": f"T01661并发探针 {i}"}),
            range(args.burst)))
    burst_secs = time.perf_counter() - t0
    print(f"并发写 {args.burst} 次：状态码 {sorted({c for c, _ in burst})}，"
          f"耗时 {burst_secs:.1f}s → TPS≈{args.burst / burst_secs:.1f}")

    time.sleep(1.5)
    rows = parse_probe_lines(args.log, offset)
    n_seq = min(args.seq, len(rows))
    report("顺序写（无并发）每请求分段", rows[:n_seq], seq_ms)
    report("并发写分段（看 lock_wait 放大）", rows[n_seq:], [m for _, m in burst])
    if args.out:
        import json
        json.dump({"cpu_busy_note": "采样见 runbook，非空闲机绝对值不可引用",
                   "seq_client_ms": seq_ms,
                   "burst_client_ms": [m for _, m in burst],
                   "rows": rows},
                  io.open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[out] 原始探针行已落盘 {args.out}")
    print(f"\n[fixture] 探针用户 id={uid}（副本库，非真实用户）episode={episode_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
