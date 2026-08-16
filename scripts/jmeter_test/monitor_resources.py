"""后端进程资源监控 sidecar（性能测试期间采样）。

采样后端 uvicorn 进程（按 PID）的 CPU%、RSS 内存、线程数、句柄数，
以及 SQLite 数据文件 news.db 与 WAL 文件大小，输出 CSV 供分析阶段与 JTL 时间轴叠加。

用法：
  python monitor_resources.py --pid <后端PID> --out resources.csv \
      --db backend/data/news.db --wal backend/data/news.db-wal \
      --interval 2 --duration 3900
"""
import argparse
import csv
import os
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--db", default="")
    ap.add_argument("--wal", default="")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--duration", type=float, default=3900.0)
    args = ap.parse_args()

    try:
        import psutil
    except ImportError:
        print("[ERROR] 需要 psutil：pip install psutil", file=sys.stderr)
        return 2

    try:
        proc = psutil.Process(args.pid)
    except Exception as e:
        print(f"[ERROR] 无法附加到 PID={args.pid}: {e}", file=sys.stderr)
        return 2

    is_win = sys.platform.startswith("win")
    start = time.time()
    rows = []
    print(f"[monitor] 开始采样 PID={args.pid}，间隔={args.interval}s，时长={args.duration}s -> {args.out}")
    # 首次 cpu_percent 调用返回 0，先预热一次
    try:
        proc.cpu_percent()
    except Exception:
        pass
    while True:
        elapsed = time.time() - start
        if elapsed >= args.duration:
            break
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            cpu = proc.cpu_percent()
            mem = proc.memory_info()
            rss_mb = mem.rss / (1024 * 1024)
            threads = proc.num_threads()
            handles = proc.num_handles() if is_win else 0
        except Exception as e:
            print(f"[monitor] 进程已退出或采样失败: {e}")
            break
        db_mb = (os.path.getsize(args.db) / (1024 * 1024)) if args.db and os.path.exists(args.db) else 0.0
        wal_mb = (os.path.getsize(args.wal) / (1024 * 1024)) if args.wal and os.path.exists(args.wal) else 0.0
        rows.append({
            "ts": ts, "elapsed_s": round(elapsed, 1), "cpu_percent": round(cpu, 1),
            "rss_mb": round(rss_mb, 1), "threads": threads, "handles": handles,
            "db_mb": round(db_mb, 2), "wal_mb": round(wal_mb, 2),
        })
        # 进度打印（每 30 次）
        if len(rows) % 30 == 0:
            print(f"[monitor] t={round(elapsed)}s cpu={cpu:.1f}% rss={rss_mb:.0f}MB wal={wal_mb:.1f}MB samples={len(rows)}")
        time.sleep(args.interval)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "elapsed_s", "cpu_percent", "rss_mb", "threads", "handles", "db_mb", "wal_mb"])
        w.writeheader()
        w.writerows(rows)
    print(f"[monitor] 结束，共 {len(rows)} 个采样点 -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
