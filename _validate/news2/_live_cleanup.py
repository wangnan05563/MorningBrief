"""清理我起的联测进程 + 副本目录（一次性）。"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"D:\code\otherProjects\20_News\backend\.tmp\t02508-live")

o = subprocess.run(["wmic", "process", "get", "ProcessId,CommandLine", "/format:csv"],
                   capture_output=True, text=True).stdout
mine = []
for ln in o.splitlines():
    if "_live_backend.py" in ln or "_live_probe2.py" in ln or "_live_restart.py" in ln:
        pid = ln.rstrip().split(",")[-1]
        if pid.isdigit():
            mine.append(pid)
print("orphan 联测进程:", mine)
for pid in mine:
    r = subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True, text=True)
    print("kill", pid, r.returncode, (r.stdout or r.stderr).strip()[:80])
time.sleep(3)
net = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
print(":8000 占用者", sorted({l.split()[-1] for l in net.splitlines()
                            if ":8000 " in l and "LISTENING" in l}))
shutil.rmtree(ROOT, ignore_errors=True)
print("副本目录 exists=", ROOT.exists())
