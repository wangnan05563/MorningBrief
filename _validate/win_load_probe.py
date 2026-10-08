"""轻量 CPU/内存采样（无第三方依赖）：GetSystemTimes 的 FILETIME 必须按 64 位取。"""
import ctypes
import sys
import time


def _snap(k):
    vals = []
    for _ in range(3):
        ft = ctypes.c_ulonglong(0)
        vals.append(ft)
    k.GetSystemTimes(ctypes.byref(vals[0]), ctypes.byref(vals[1]), ctypes.byref(vals[2]))
    idle = vals[0].value
    total = vals[1].value + vals[2].value
    return idle, total


def cpu_busy_pct(sample_sec: float = 1.0) -> float:
    k = ctypes.windll.kernel32
    i0, t0 = _snap(k)
    time.sleep(sample_sec)
    i1, t1 = _snap(k)
    dt = t1 - t0
    if dt <= 0:
        return float("nan")
    return 100.0 * (1.0 - (i1 - i0) / dt)


def mem_load_pct() -> int:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return int(m.dwMemoryLoad)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    for _ in range(n):
        print(f"cpu_busy={cpu_busy_pct():.1f}% mem_load={mem_load_pct()}%", flush=True)
