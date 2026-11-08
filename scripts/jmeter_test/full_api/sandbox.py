"""隔离沙箱管理：复制后端代码与数据库、拉起/回收被测实例。

安全边界：
- 只操作本目录下 sandbox/，不触碰 backend/data 生产库。
- 端口只取 `perf_config.json: sandbox.port`（当前 8021），与开发/打包端口分离；
  端口被占且不是本装置 pid 时拒绝启动，绝不改端口试运气。
- APP_ROLE=api 关闭建表/迁移/seed/APScheduler/隧道自启（避免外部调用污染压测）；
  因此 prepare 会用 `_align_schema()` 单独把库结构补到代码要求（迁移只 ALTER，不起调度）。
- 沙箱 .env 副本按 scrub_env_keys 清空外部服务凭据；书源索引预置占位，避免抓取 GitHub。
- 关停只按本进程写出的 pid 定向 taskkill /PID ... /T，绝不按映像名全局杀。
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONFIG = json.loads((HERE / "perf_config.json").read_text(encoding="utf-8"))
SB = CONFIG["sandbox"]
SANDBOX = HERE / "sandbox"
BACKEND_SB = SANDBOX / "backend"
# app/paths.py 用 get_app_root()/data 解析数据目录（不走 SQLITE_DB_PATH），
# 因此沙箱库必须放在代码副本的 backend/data 下，否则会静默新建空库。
DATA = BACKEND_SB / "data"
RUNTIME = HERE / "runtime"
PID_FILE = SANDBOX / "server.pid"


def _env_value(key: str) -> str:
    env_path = REPO / SB["env_source"]
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(key + "="):
            value = line.split("=", 1)[1].strip()
            if "  #" in value:
                value = value.split("  #")[0].strip()
            return value.strip('"').strip("'")
    return ""


def _scrub_env(path: Path, keys: list[str]) -> int:
    """把沙箱 .env 副本中的外部服务凭据置空，避免压测触发真实外呼/写生产存储。"""
    wanted = set(keys)
    if not wanted or not path.exists():
        return 0
    lines, hit = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
        if key in wanted:
            lines.append(f"{key}=")
            hit += 1
        else:
            lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return hit


def _seed_ebook_index(data_dir: Path) -> None:
    """预置一份「新鲜」书源索引占位文件。

    为何必须：`ebook/categories`、`ebooks/random` 在索引缺失或过期时会调用
    `maybe_auto_rebuild()`，后台线程向 raw.githubusercontent.com 抓取 943 个分类 md
    （实测 935 s、10 线程并发），既产生真实出站流量，又会在压测窗口内抢占线程与 GIL。
    """
    path = data_dir / "ebook_index.json"
    if path.exists():
        return
    path.write_text(json.dumps({
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "book_count": 0,
        "category_count": 0,
        "elapsed_sec": 0,
        "books": [],
    }, ensure_ascii=False), encoding="utf-8")


_ALIGN_PROG = """
import asyncio, inspect, json, sys
from app import main

names = json.loads(sys.argv[1])
out = {}


async def run():
    for n in names:
        fn = getattr(main, n, None)
        if fn is None:
            out[n] = "MISSING"
            continue
        try:
            if inspect.iscoroutinefunction(fn):
                await fn()
            else:
                fn()
            out[n] = "ok"
        except Exception as e:
            out[n] = f"{type(e).__name__}: {e}"
    print("ALIGN_RESULT " + json.dumps(out, ensure_ascii=False))


asyncio.run(run())
"""


def _singleton_schema_calls() -> list[str]:
    """从被拷贝的 main.py 里解析 lifespan 的 `if singleton:` 块实际调用的建表/迁移函数。

    不写死名单：后端新增一个 `_migrate_*` 时，沙箱自动跟上；
    若启动编排改名或不再是 `singleton` 判断，这里返回空并打出 warn。
    """
    tree = ast.parse((BACKEND_SB / "app" / "main.py").read_text(encoding="utf-8", errors="replace"))
    fn = next((n for n in tree.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "lifespan"), None)
    if fn is None:
        return []
    names: list[str] = []
    for block in ast.walk(fn):
        if not (isinstance(block, ast.If) and getattr(block.test, "id", None) == "singleton"):
            continue
        for call in ast.walk(block):
            f = call.func if isinstance(call, ast.Call) else None
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            if (name == "_init_sqlite_schema" or name.startswith("_migrate")) and name not in names:
                names.append(name)
    return names


def _align_schema() -> None:
    """把生产库副本的表结构对齐到所拷贝代码的要求。

    为何必须：`APP_ROLE=api` 会跳过 lifespan 里 `if singleton:` 的建表/迁移，
    于是代码新增列（首个撞上的案例是 `channel.search_prompt`，T04111）不会出现在沙箱库里，
    所有触达该表的接口整批 500 —— 看起来像性能缺陷，其实是装置与代码不同期。
    """
    names = _singleton_schema_calls()
    if not names:
        print("[warn] 未解析到 lifespan 的 singleton 迁移块，跳过结构对齐（后端启动编排变更时需同步这里）")
        return
    env = os.environ.copy()
    env.update({
        "APP_ROLE": "api",
        "LOG_DIR": str(SANDBOX / "logs"),
        "PYTHONPATH": str(BACKEND_SB),
        "PYTHONIOENCODING": "utf-8",
    })
    proc = subprocess.run(
        [str(REPO / SB["python"]), "-c", _ALIGN_PROG, json.dumps(names)],
        cwd=str(BACKEND_SB), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("ALIGN_RESULT ")), None)
    if line is None:
        raise SystemExit(f"[fail] 结构对齐无结果：{proc.stdout[-300:]} | {proc.stderr[-300:]}")
    result = json.loads(line[len("ALIGN_RESULT "):])
    bad = {k: v for k, v in result.items() if v != "ok"}
    print(f"[ok] 沙箱库结构对齐代码：{len(result) - len(bad)}/{len(result)} 步成功")
    for k, v in bad.items():
        print(f"[warn] 迁移未成功 {k}: {v}")


def prepare(force: bool) -> None:
    if SANDBOX.exists():
        if not force:
            print(f"[skip] sandbox 已存在：{SANDBOX}")
            return
        shutil.rmtree(SANDBOX)
    (SANDBOX / "logs").mkdir(parents=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)

    # 代码副本：只复制 app 与启动所需文件，隔离 get_app_root() 推导出的 data/logs
    shutil.copytree(REPO / SB["app_source"], BACKEND_SB / "app")
    shutil.copy2(REPO / SB["env_source"], BACKEND_SB / ".env")
    scrubbed = _scrub_env(BACKEND_SB / ".env", SB.get("scrub_env_keys") or [])
    if scrubbed:
        print(f"[ok] 已清空沙箱外部凭据 {scrubbed} 项（生产凭据不进压测实例）")

    for sub in ("audio_cache", "avatars", "bgm", "backup", "channel_assets"):
        (DATA / sub).mkdir(parents=True, exist_ok=True)
    if SB.get("seed_ebook_index", True):
        _seed_ebook_index(DATA)
        print("[ok] 已预置书源索引占位文件（压测期间不抓 raw.githubusercontent）")

    # SQLite 在线备份（含 WAL 中已提交数据），得到一致快照
    source = sqlite3.connect(f"file:{REPO / SB['db_source']}?mode=ro", uri=True)
    target = sqlite3.connect(DATA / "news.db")
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()

    if SB.get("align_schema", True):
        _align_schema()
    print(f"[ok] 沙箱已准备：{SANDBOX}（DB {round((DATA / 'news.db').stat().st_size / 1048576, 1)} MB）")


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def _pid_alive(pid: int) -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    return str(pid) in out


def start() -> None:
    port = int(SB["port"])
    if _port_in_use(port):
        pid = _pid()
        if pid and _pid_alive(pid):
            print(f"[ok] 实例已在运行 pid={pid} port={port}")
            return
        raise SystemExit(f"[fail] 端口 {port} 被其它进程占用，拒绝启动（防止打错目标）")

    env = os.environ.copy()
    env.update({
        "APP_ROLE": "api",
        "SQLITE_DB_PATH": str(DATA / "news.db"),
        "LOG_DIR": str(SANDBOX / "logs"),
        "RATE_LIMIT_PER_MINUTE": str(SB["rate_limit_per_minute"]),
        "PYTHONPATH": str(BACKEND_SB),
        "APP_HOST": SB["host"],
        "APP_PORT": str(port),
        "APP_DEBUG": "false",
        "PYTHONIOENCODING": "utf-8",
    })
    # 测试专用运行时覆盖（如把管理端 token 有效期拉到覆盖整段 soak），不写生产配置
    env.update({str(k): str(v) for k, v in (SB.get("env_overrides") or {}).items()})
    # 保留真实 JWT_SECRET 供签发测试 token；其余外部服务配置不动，但不调用。
    log = open(SANDBOX / "server.stdout.log", "ab")
    proc = subprocess.Popen(
        [str(REPO / SB["python"]), "-m", "uvicorn", "app.main:app",
         "--host", SB["host"], "--port", str(port), "--log-level", "warning"],
        cwd=str(BACKEND_SB), env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")

    deadline = time.time() + int(SB["startup_timeout_sec"])
    url = f"http://{SB['host']}:{port}{SB['health_path']}"
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"[fail] 实例启动即退出，pid={proc.pid}，见 sandbox/server.stdout.log")
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status < 500:
                    print(f"[ok] 实例就绪 pid={proc.pid} {url}")
                    return
        except Exception:
            time.sleep(2)
    stop()
    raise SystemExit("[fail] 健康检查超时")


def stop() -> None:
    pid = _pid()
    if not pid:
        print("[skip] 无 pid 文件")
        return
    if _pid_alive(pid):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        print(f"[ok] 已定向关停 pid={pid}")
    PID_FILE.unlink(missing_ok=True)


def status() -> None:
    pid = _pid()
    port = int(SB["port"])
    print(f"pid={pid} alive={bool(pid and _pid_alive(pid))} port={port} in_use={_port_in_use(port)}")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "prepare":
        prepare("--force" in sys.argv)
    elif action == "start":
        start()
    elif action == "stop":
        stop()
    elif action == "restart":
        stop()
        time.sleep(1)
        start()
    else:
        status()
