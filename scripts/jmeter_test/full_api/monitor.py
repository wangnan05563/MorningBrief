"""SUT 资源采样 sidecar：RSS/峰值工作集/CPU/句柄 + DB/WAL/磁盘/日志体积。

用法：
    python monitor.py --out results/monitor_baseline.csv [--duration 600]
停止：写入 results/STOP，或到达 duration。
"""
from __future__ import annotations

import argparse
import ctypes
import csv
import json
import re
import shutil
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "perf_config.json").read_text(encoding="utf-8"))
PORT = int(CONFIG["sandbox"]["port"])
PID_FILE = HERE / "sandbox" / "server.pid"
DB = HERE / "sandbox" / "backend" / "data" / "news.db"
LOG = HERE / "sandbox" / "server.stdout.log"
STOP = HERE / "results" / "STOP"

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


class PROCESS_TIMES(ctypes.Structure):
    _fields_ = [
        ("CreationTime", wintypes.FILETIME),
        ("ExitTime", wintypes.FILETIME),
        ("KernelTime", wintypes.FILETIME),
        ("UserTime", wintypes.FILETIME),
    ]


def _ft(v: wintypes.FILETIME) -> int:
    return (v.dwHighDateTime << 32) | v.dwLowDateTime


def listener_pid(port: int) -> int:
    """以监听端口为准定位 SUT，pid 文件在重启/双重 fork 后会失真。"""
    out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stdout
    for line in out.splitlines():
        m = re.search(rf"[:.]{port}\s+\S+\s+LISTENING\s+(\d+)", line)
        if m:
            return int(m.group(1))
    return 0


def read_pid() -> int:
    pid = listener_pid(PORT)
    if pid:
        return pid
    return int(PID_FILE.read_text(encoding="utf-8").strip())


def sample(pid: int) -> dict:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return {"rss_mb": 0, "peak_ws_mb": 0, "handles": 0, "cpu_pct": 0.0}
    try:
        mem = PROCESS_MEMORY_COUNTERS()
        mem.cb = ctypes.sizeof(mem)
        psapi.GetProcessMemoryInfo(handle, ctypes.byref(mem), mem.cb)
        handles = wintypes.DWORD()
        k32.GetProcessHandleCount(handle, ctypes.byref(handles))
        times = PROCESS_TIMES()
        k32.GetProcessTimes(handle, *[ctypes.byref(f) for f in
                                      (times.CreationTime, times.ExitTime,
                                       times.KernelTime, times.UserTime)])
        io = IO_COUNTERS()
        k32.GetProcessIoCounters(handle, ctypes.byref(io))
        cpu_s = (_ft(times.KernelTime) + _ft(times.UserTime)) / 1e7
        return {
            "rss_mb": round(mem.WorkingSetSize / 1048576, 1),
            "peak_ws_mb": round(mem.PeakWorkingSetSize / 1048576, 1),
            "handles": handles.value,
            "cpu_s": cpu_s,
            "io_read_mb": round(io.ReadTransferCount / 1048576, 2),
            "io_write_mb": round(io.WriteTransferCount / 1048576, 2),
        }
    finally:
        k32.CloseHandle(handle)


def file_mb(p: Path) -> float:
    try:
        return round(p.stat().st_size / 1048576, 1) if p.exists() else 0.0
    except OSError:
        return 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--duration", type=float, default=0)
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    STOP.unlink(missing_ok=True)
    start = time.time()
    last_t, last_cpu = start, None
    last_io, last_io_t = None, start
    pid_cache = 0
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "pid", "rss_mb", "peak_ws_mb", "cpu_pct", "handles",
                    "io_read_mb", "io_write_mb", "io_read_kbps", "io_write_kbps",
                    "db_mb", "wal_mb", "disk_free_gb", "log_mb"])
        while True:
            now = time.time()
            try:
                # 固定采样首次定位到的监听进程：netstat 偶发命中 venv 启动器 stub，
                # 切换 PID 会让 CPU 差值跨进程计算，造出 5000%+ 假峰值
                if not pid_cache:
                    pid_cache = read_pid()
                pid = pid_cache
                s = sample(pid)
                if not s.get("rss_mb"):
                    pid_cache = read_pid()
                    pid = pid_cache
                    s = sample(pid)
            except Exception:
                pid_cache, pid, s = 0, 0, {"rss_mb": 0, "peak_ws_mb": 0, "handles": 0}
            cpu_pct = ""
            if "cpu_s" in s:
                if last_cpu is not None and now > last_t:
                    delta = s["cpu_s"] - last_cpu
                    if delta >= 0:
                        cpu_pct = round(delta / (now - last_t) * 100, 1)
                last_cpu, last_t = s["cpu_s"], now
            io_r, io_w, io_r_kbps, io_w_kbps = "", "", "", ""
            if "io_read_mb" in s:
                io_r, io_w = s["io_read_mb"], s["io_write_mb"]
                if last_io is not None and now > last_io_t:
                    dt = now - last_io_t
                    io_r_kbps = round((s["io_read_mb"] - last_io[0]) * 1024 / dt, 1)
                    io_w_kbps = round((s["io_write_mb"] - last_io[1]) * 1024 / dt, 1)
                last_io, last_io_t = (s["io_read_mb"], s["io_write_mb"]), now
            free = shutil.disk_usage(str(HERE)).free / 1073741824
            w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), pid, s["rss_mb"],
                        s["peak_ws_mb"], cpu_pct, s["handles"],
                        io_r, io_w, io_r_kbps, io_w_kbps,
                        file_mb(DB), file_mb(Path(str(DB) + "-wal")),
                        round(free, 2), file_mb(LOG)])
            fh.flush()
            if STOP.exists() or (args.duration and now - start >= args.duration):
                break
            time.sleep(args.interval)
    print(f"[ok] 资源采样结束 → {out}")


if __name__ == "__main__":
    main()
