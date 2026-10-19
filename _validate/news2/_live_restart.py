"""T02508 真机联测 · 重启对照（一次性，跑完即删）。

在「已有一次实测（PID 30996 / started_at 2026-10-20T01:37:06）」的基础上，
重新起一个真实后端进程，验证：
1) started_at 随进程刷新（不是写死的历史值）；
2) pid 就是本进程 OS PID（与 netstat/tasklist/wmic 外部佐证一致）；
3) 进程内累计计数随重启归零（LLM 重试计数、RSS 连续失败次数）。

安全边界：数据库用生产库副本（backend/.tmp/t02508-live/data/news.db），
APP_ROLE=api 不启动 APScheduler/迁移/隧道 → 不会真实抓 RSS、不会调用 LLM；
只调用两个只读统计接口，rss-health 不带 refresh。
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(r"D:\code\otherProjects\20_News\backend")
ROOT = BACKEND / ".tmp" / "t02508-live"
HERE = Path(__file__).resolve().parent
BOOT_LOG = HERE / "_live_boot.log"
PROD_DB = BACKEND / "data" / "news.db"
PORT = 8000
BASE = f"http://127.0.0.1:{PORT}"
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def http(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:200]}
    except Exception as e:  # noqa: BLE001
        return None, {"err": type(e).__name__ + ": " + str(e)[:140]}


def port_owner():
    return sorted({ln.split()[-1] for ln in run(["netstat", "-ano"]).splitlines()
                   if f":{PORT} " in ln and "LISTENING" in ln})


def main():
    prod_before = (PROD_DB.stat().st_size, PROD_DB.stat().st_mtime)
    print(f"[pre] :{PORT} 占用者={port_owner()} 生产库 size={prod_before[0]}B")

    if ROOT.exists():
        shutil.rmtree(ROOT, ignore_errors=True)
    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROD_DB, ROOT / "data" / "news.db")
    print(f"[setup] 已复制生产库副本 {(ROOT / 'data' / 'news.db').stat().st_size}B")

    env = dict(os.environ, APP_ROLE="api")
    t0 = time.time()
    child = subprocess.Popen(
        [PY, str(HERE / "_live_backend.py")],
        cwd=str(BACKEND), env=env,
        stdout=open(BOOT_LOG, "w", encoding="utf-8", errors="replace"),
        stderr=subprocess.STDOUT,
    )
    print(f"[boot] 新实例 PID={child.pid} 启动于 {time.strftime('%H:%M:%S')}")
    deadline = time.time() + 180
    ready = False
    while time.time() < deadline:
        if child.poll() is not None:
            print(f"[boot] FAIL 子进程退出 rc={child.returncode}\n" +
                  "\n".join(BOOT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]))
            return 1
        with socket.socket() as s:
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", PORT)) == 0:
                ready = True
                break
        time.sleep(1)
    if not ready:
        print("[boot] FAIL 超时")
        child.kill()
        return 1
    print(f"[boot] 端口就绪（{time.strftime('%H:%M:%S')}，耗时 {int(time.time() - t0)}s）")

    st, r = http("POST", "/admin/api/v1/auth/login", {"username": "admin", "password": "admin123"})
    token = (r.get("data") or {}).get("token")
    print(f"[auth] HTTP {st} code={r.get('code')} token={bool(token)}")

    st, rl = http("GET", "/admin/api/v1/stats/llm-metrics", token=token)
    dl = rl.get("data") or {}
    st2, rr = http("GET", "/admin/api/v1/stats/rss-health", token=token)
    dr = rr.get("data") or {}
    print(f"[api] llm-metrics HTTP {st} started_at={dl.get('started_at')} pid={dl.get('pid')} "
          f"total_calls={dl.get('total_calls')} triggered={dl.get('triggered')} improved={dl.get('improved')}")
    print(f"[api] rss-health  HTTP {st2} started_at={dr.get('started_at')} pid={dr.get('pid')} "
          f"total={dr.get('total')} ok={dr.get('ok')} fail={dr.get('fail')} sources={len(dr.get('sources') or [])}")

    pid = dl.get("pid")
    create = run(["wmic", "process", "where", f"processid={pid}", "get", "CreationDate", "/value"]).strip()
    print(f"[proof] started_at/pid 两接口一致="
          f"{(dl.get('started_at'), dl.get('pid')) == (dr.get('started_at'), dr.get('pid'))}")
    print(f"[proof] 接口 pid={pid} == 子进程 pid={child.pid} → {pid == child.pid}；"
          f":{PORT} 监听归属={port_owner()}")
    print(f"[proof] OS 进程创建时刻 → {create}")
    print(f"[proof] 与上一轮实测对照：上一实例 pid=30996 started_at=2026-10-20T01:37:06 "
          f"→ 本轮 pid={pid} started_at={dl.get('started_at')}")

    child.kill()
    child.wait(timeout=30)
    time.sleep(3)
    shutil.rmtree(ROOT, ignore_errors=True)
    prod_after = (PROD_DB.stat().st_size, PROD_DB.stat().st_mtime)
    print(f"[cleanup] 实例已终止，:8000 占用者={port_owner()}，副本目录 exists={ROOT.exists()}")
    print(f"[cleanup] 生产库未被写入：size={prod_after[0]}B mtime 变化={prod_before[1] != prod_after[1]}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
