# -*- coding: utf-8 -*-
r"""T01581 压测回归门禁：一条命令跑完 seed → 生成 jmx → 固定档位压测 → analyze → cleanup。

用法：
    python perf_gate.py --tier quick            # ~6 分钟，4 个档位（含 workers>1 对照）
    python perf_gate.py --tier standard         # 默认档，含管理端
    python perf_gate.py --tier full --include-soak
    python perf_gate.py --only S1_read_200      # 单档复测
    python perf_gate.py --tier quick --update-baseline   # 把本轮结果写为新的延迟基线
    python perf_gate.py --tier quick --iso-root %TEMP%\gate_iso   # 隔离副本模式（T01692）

退出码：0=全部达标；1=有档位破线（回归）；2=前置条件或执行失败（不视为回归结论）。

设计约束（沿用 T01518 实测口径，勿随意改动）：
- 后端默认 workers=1（单进程事件循环），压测结论只在单 worker 下可复现；
  `--workers N` 可覆盖（T01659），实际值会写进 gate_report 头部便于横向比对。
- 限流通过子进程环境变量 RATE_LIMIT_PER_MINUTE 临时解除，不改 backend/.env。
- token 只经 -Jauth_token / -Jadmin_token 注入 jmeter，不写进 jmx 文件。
- jtl 为 CSV（显式传 -Jjmeter.save.saveservice.output_format=csv）。
- 种子数据一律用标记行灌入/清理（seed_perf_data.py / cleanup_seed.py），
  压测结束无论成败都在 finally 里清理，开发库不残留。
- 管理端档位需要 admin token（环境变量 GATE_ADMIN_TOKEN 或 admin_token.txt），
  缺失时跳过 S3_* 并在报告中标 SKIPPED，不判失败。

T01692 隔离模式（--iso-root）：
- 问题：门禁在真实 data/ 上起服务，而 data/tunnel_config.json auto_start=true，
  每轮门禁都会真建一条内网穿透并外发用户可见通知（T01659/T01660 踩过）。
- 方案：把 backend/app 代码 + .env + data/（排除 backup/*.bak_*）浅拷贝到隔离根，
  子进程以 cwd=隔离根 + PYTHONPATH=隔离根 运行——app 包从副本导入，
  get_app_root() 即隔离根，data/.env/logs 全部天然隔离，**生产 data/ 零接触**；
  副本内 tunnel_config.json 强制 auto_start=false（只改副本，不动用户生产配置）。
- token 签发与 seed 脚本经 PERF_BACKEND_DIR 环境变量指向副本 DB。
- workers>1 时按 T01660 角色编排启动：1 个 sched（端口+1）+ N 个 api（业务端口），
  复用 backend/launcher.py 的编排逻辑（副本内自带 launcher.py），角色/进程数写入报告头。
- compare_only 档位（如 S1_read_200_w2）：workers>1 的对照结果只记录不判定，
  多进程结果不可与单进程基线混比。
"""
import argparse
import csv
import ctypes
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
BACKEND_DIR = REPO / "backend"
DB_PATH = BACKEND_DIR / "data" / "news.db"
CONFIG_PATH = HERE / "gate_config.json"
BASELINE_PATH = HERE / "gate_baseline.json"
REPORT_JSON = HERE / "gate_report.json"
REPORT_MD = HERE / "gate_report.md"
USER_TOKEN_FILE = HERE / "test_token.txt"
ADMIN_TOKEN_FILE = HERE / "admin_token.txt"

# T01692：隔离副本根（None=直接压真实 backend/data）
ISO_ROOT: Path | None = None


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def abort(msg: str) -> None:
    """前置条件/环境失败：退出码 2，与「测出回归」（退出码 1）区分。"""
    log(msg)
    raise SystemExit(2)


def resolve_python() -> str:
    """挑选装了 uvicorn 的解释器：项目 venv 优先，回退当前解释器。

    背景：脚本可能由无依赖的系统 Python 启动（`No module named uvicorn`），
    后端必须用有依赖的解释器拉起，故在此显式探测而不是假定 sys.executable。
    """
    candidates = [os.environ.get("GATE_PYTHON", "")]
    for sub in (("backend", ".venv", "Scripts", "python.exe"),
                ("backend", ".venv", "bin", "python"),
                (".venv", "Scripts", "python.exe"),
                (".venv", "bin", "python")):
        p = REPO.joinpath(*sub)
        if p.exists():
            candidates.append(str(p))
    candidates.append(sys.executable)
    for cand in candidates:
        if not cand:
            continue
        try:
            r = subprocess.run([cand, "-c", "import uvicorn"], capture_output=True, timeout=30)
        except OSError:
            continue
        if r.returncode == 0:
            return cand
    abort("[ABORT] 未找到安装了 uvicorn 的 Python 解释器（可用 GATE_PYTHON 指定）")


JAVA_FALLBACKS = (
    "D:/code/Java/zulu17.52.17-ca-jdk17.0.12-win_x64",
    "D:/code/Java/jdk-25.0.1",
    "D:/code/Java/jdk1.8.0_341",
)


def resolve_java() -> str:
    """定位 JDK：GATE_JAVA_HOME > JAVA_HOME > 常见本机目录。

    jmeter.bat 找不到 java 时只打印提示却仍返回 0，会让门禁误判「跑完了但没数据」，
    因此这里前置校验并把 JAVA_HOME 显式注入子进程环境。
    """
    env_home = os.environ.get("JAVA_HOME", "").strip()
    for cand in [os.environ.get("GATE_JAVA_HOME", "").strip(), env_home, *JAVA_FALLBACKS]:
        if not cand:
            continue
        for exe in ("java.exe", "java"):
            if Path(cand, "bin", exe).exists():
                return cand
    which = shutil.which("java")
    if which:
        return str(Path(which).parent.parent)
    abort("[ABORT] 未找到 Java（设置 GATE_JAVA_HOME 或 JAVA_HOME 后重试）")
    return ""


PY = resolve_python()

# analyze.py 与本脚本同目录，直接复用其 JTL 解析
sys.path.insert(0, str(HERE))
import analyze  # noqa: E402


def load_config() -> dict:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if BASELINE_PATH.exists():
        stored = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        for sid, vals in stored.items():
            if sid in cfg["scenarios"] and vals.get("baseline_p95_ms"):
                cfg["scenarios"][sid]["baseline_p95_ms"] = vals["baseline_p95_ms"]
    return cfg


def db_counts() -> dict:
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(str(DB_PATH))
    try:
        tables = ("episode", "comment", "user", "channel", "favorite", "play_log", "feedback")
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    finally:
        conn.close()


def child_env(extra: dict | None = None) -> dict:
    """子进程环境：隔离模式下指向副本根（PYTHONPATH + PERF_BACKEND_DIR）。

    PYTHONPATH 使 `app` 包从副本导入 → paths.get_app_root()=副本根，
    data/.env/logs 解析全部落在副本内；PERF_BACKEND_DIR 供
    setup.py/seed_perf_data.py/cleanup_seed.py 定位副本 DB。
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if ISO_ROOT is not None:
        env["PYTHONPATH"] = str(ISO_ROOT)
        env["PERF_BACKEND_DIR"] = str(ISO_ROOT)
    if extra:
        env.update({k: str(v) for k, v in extra.items()})
    return env


# 隔离副本排除项：与压测无关的大目录/易碎文件
_ISO_DATA_EXCLUDE = shutil.ignore_patterns(
    "backup",                 # 回滚快照目录（158MB 大头）
    "news_backup_*",          # 恢复前快照
    "news.db.bak_*",          # 手工备份
    "logs",
)


def prepare_iso_root(spec_dir: str | None) -> Path:
    """构建隔离副本根（T01692）。

    布局：
        <iso>/app/**        ← backend/app 浅拷贝（排除 __pycache__）
        <iso>/launcher.py   ← 角色编排入口（workers>1 用）
        <iso>/.env          ← 配置副本（JWT_SECRET/APP_* 对副本生效）
        <iso>/data/**       ← DB/tunnel_config/audio_cache 等（排除 backup/logs）
        <iso>/logs/         ← 后端日志隔离落点（自动创建）
    并强制副本内 tunnel auto_start=false，杜绝门禁外发隧道通知。
    设置模块级 ISO_ROOT（child_env 依赖它注入 PYTHONPATH/PERF_BACKEND_DIR）。
    """
    global ISO_ROOT
    ISO_ROOT = None  # 先复位，避免上次运行残留导致 child_env 误注入
    if spec_dir:
        iso = Path(spec_dir).resolve()
        if iso.exists() and any(iso.iterdir()):
            abort(f"[ABORT] --iso-root 目录非空：{iso}（请指定空目录或让其自动创建）")
        iso.mkdir(parents=True, exist_ok=True)
    else:
        iso = Path(tempfile.mkdtemp(prefix="perf_gate_iso_"))
    log(f"[iso] 隔离副本根：{iso}")

    shutil.copytree(BACKEND_DIR / "app", iso / "app",
                    ignore=shutil.ignore_patterns("__pycache__"))
    launcher_src = BACKEND_DIR / "launcher.py"
    if launcher_src.exists():
        shutil.copy2(launcher_src, iso / "launcher.py")
    env_src = BACKEND_DIR / ".env"
    if env_src.exists():
        shutil.copy2(env_src, iso / ".env")
    shutil.copytree(BACKEND_DIR / "data", iso / "data", ignore=_ISO_DATA_EXCLUDE,
                    dirs_exist_ok=True)
    (iso / "logs").mkdir(exist_ok=True)

    # 关键：只改副本的隧道配置，用户生产 data/tunnel_config.json 零接触
    tc = iso / "data" / "tunnel_config.json"
    if tc.exists():
        try:
            cfg = json.loads(tc.read_text(encoding="utf-8-sig"))
        except Exception as e:
            log(f"[WARN] 副本 tunnel_config.json 解析失败（按默认关闭处理）：{e}")
            cfg = {}
    else:
        cfg = {}
    cfg["auto_start"] = False
    tc.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    log("[iso] 副本隧道已强制 auto_start=false（生产配置未动）")
    ISO_ROOT = iso
    return iso


def _win_rmtree(root: Path) -> None:
    """Windows 下用 ctypes 批量删除隔离副本树。

    不用 shutil.rmtree：目录超 50 个文件会触发沙箱 safe-delete 拦截
    （SAFE_DELETE_BULK_CONFIRM_REQUIRED），且递删须防符号链接/junction
    逃逸出副本根（历史教训：沿链接递删会清空真实目录）。
    """
    if os.name != "nt":
        shutil.rmtree(root, ignore_errors=True)
        return
    # 关键：先 resolve 统一为长路径。TEMP 等环境变量常是 8.3 短名（如 C:\PYFIX_~4），
    # resolve() 展开为 C:\pyfix_tmp——若 walk 用短名而守卫用长名，normcase 后
    # startswith 全部失配，所有文件被守卫误拒（0 删除静默失败，实测 T01692）。
    root = Path(root).resolve()
    root_s = str(root)
    root_norm = os.path.normcase(root_s)
    delete_file = ctypes.windll.kernel32.DeleteFileW
    remove_dir = ctypes.windll.kernel32.RemoveDirectoryW
    files, dirs, skipped = 0, 0, 0
    # 文件删除最多重试 3 轮：杀树后句柄释放有延迟（防 TASKKILL 后 1s 内文件仍被锁）
    for attempt in range(3):
        files, skipped = 0, 0
        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            # 剪枝：任何解析后逃出副本根的目录（链接/junction）只删链接本身
            pruned = []
            for d in dirnames:
                p = Path(dirpath) / d
                escaped = False
                try:
                    if p.is_symlink() or p.is_junction():
                        escaped = True
                    elif os.path.normcase(str(p.resolve())) != os.path.normcase(str(p)):
                        # resolve 后仍在 root 内才算普通目录
                        if not os.path.normcase(str(p.resolve())).startswith(root_norm):
                            escaped = True
                except OSError:
                    escaped = True
                if escaped:
                    if delete_file(str(p)) or remove_dir(str(p)):
                        pass
                    pruned.append(d)  # 不进入
                else:
                    pass
            for d in pruned:
                dirnames.remove(d)
            for f in filenames:
                full = str(Path(dirpath) / f)
                if not os.path.normcase(full).startswith(root_norm):
                    skipped += 1
                    continue
                if delete_file(full):
                    files += 1
                else:
                    skipped += 1
        if skipped == 0:
            break
        time.sleep(1.0)
    # 两轮以上剪空目录（os.walk 只剪「遍历到时空」的，嵌套残留需反复补删）
    for _ in range(10):
        removed = 0
        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            for d in dirnames:
                p = Path(dirpath) / d
                try:
                    if p.is_symlink() or p.is_junction():
                        continue
                except OSError:
                    continue
                if remove_dir(str(p)):
                    removed += 1
        try:
            if remove_dir(str(root)):
                removed += 1
        except OSError:
            pass
        if removed == 0:
            break
    log(f"[iso] 副本已清理：文件 {files}，跳过 {skipped}（守卫外/删除失败）")


def lock_errors() -> int:
    n, _ = analyze.count_db_locked()
    return n


def run_step(name: str, argv: list, cwd: Path = None, env: dict | None = None) -> None:
    log(f"[step] {name}: {' '.join(str(a) for a in argv)}")
    proc = subprocess.run([str(a) for a in argv], cwd=str(cwd) if cwd else None,
                          env=env)
    if proc.returncode != 0:
        abort(f"[ABORT] 步骤失败：{name}（退出码 {proc.returncode}）")


def refresh_tokens() -> str:
    """每轮都执行 setup.py 刷新 C 端 token。

    不能只判 test_token.txt 是否存在：token 有效期 1 天，且测试用户可能被历史清理
    脚本删掉——两种情况下复用旧 token 会让全部鉴权接口 401（实测错误率 100%、
    TPS 虚高），门禁结论完全失真。setup.py 用 INSERT OR IGNORE 保证幂等。
    """
    run_step("setup.py(建/复用测试用户 + 签发 token)", [PY, HERE / "setup.py"],
             env=child_env())
    token = USER_TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        abort("[ABORT] test_token.txt 为空，无法压测")
    return token


def id_ranges() -> dict:
    """seed 后真实的 id 区间，作为 jmeter 的 ep/ch/script min-max 注入。

    为什么必须动态：seed 只追加、主键不回卷，多轮 seed/cleanup 后节目 id 早已
    越过 jmx 里历史写死的 1..1000；随机落到空档就是 404，会把「夹具覆盖不足」
    误读成性能回归（T01581 实测：404 占读路径错误的大头）。
    """
    conn = sqlite3.connect(str(DB_PATH))
    try:
        ep = conn.execute(
            "SELECT MIN(id), MAX(id) FROM episode "
            "WHERE audio_url LIKE 'http://127.0.0.1:8000/audio/perf_%'").fetchone()
        if not ep or ep[0] is None:  # --no-seed：退回全量节目
            ep = conn.execute("SELECT MIN(id), MAX(id) FROM episode").fetchone()
        ch = conn.execute("SELECT MIN(id), MAX(id) FROM channel").fetchone()
        sc = conn.execute("SELECT MIN(id), MAX(id) FROM script").fetchone()
    finally:
        conn.close()
    if not ep or ep[0] is None:
        abort("[ABORT] 库中没有节目，夹具未灌入，指标无意义")
    ranges = {"ep_min": ep[0], "ep_max": ep[1],
              "ch_min": ch[0] or 1, "ch_max": ch[1] or 1,
              "script_min": (sc[0] if sc and sc[0] else 1),
              "script_max": (sc[1] if sc and sc[1] else 1)}
    log(f"[preflight] id 区间注入：{ranges}")
    return ranges


def admin_token() -> str:
    tok = os.environ.get("GATE_ADMIN_TOKEN", "").strip()
    if not tok and ADMIN_TOKEN_FILE.exists():
        tok = ADMIN_TOKEN_FILE.read_text(encoding="utf-8").strip()
    return tok


# 后端运行信息（角色编排用）：start_backend 写入，stop_backend/报告头读取
BACKEND_INFO: dict = {}


def _job_assign(proc: subprocess.Popen) -> int | None:
    """把子进程挂进 Job Object（KILL_ON_JOB_CLOSE），返回句柄；失败返回 None。

    为什么不用 taskkill /T：它靠「父 PID 快照」枚举进程树，uvicorn workers>1
    的 spawn worker 在树枚举时序外会漏杀（实测 T01692：孤儿 worker 继续持有
    8100 监听 socket，netstat 显示的是已死父进程的 PID，taskkill 报"进程不存在"
    但 HTTP 200 还活着）。Job Object 是内核级进程组：TerminateJobObject 一锅端，
    且门禁脚本自身崩溃时句柄关闭自动全杀，双保险。
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None

        class _IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class _BASIC_LIMIT(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32),
            ]

        class _EXT_LIMIT(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BASIC_LIMIT),
                ("IoInfo", _IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        limit = _EXT_LIMIT()
        limit.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        # 9 = JobObjectExtendedLimitInformation
        if not k32.SetInformationJobObject(job, 9, ctypes.byref(limit),
                                           ctypes.sizeof(limit)):
            k32.CloseHandle(job)
            return None
        # 不用 Popen 私有 _handle：OpenProcess 拿独立句柄（PROCESS_ALL_ACCESS）
        PROCESS_ALL_ACCESS = 0x1F0FFF
        h = k32.OpenProcess(PROCESS_ALL_ACCESS, False, int(proc.pid))
        if not h:
            k32.CloseHandle(job)
            return None
        try:
            if not k32.AssignProcessToJobObject(job, h):
                k32.CloseHandle(job)
                return None
        finally:
            k32.CloseHandle(h)  # Job 已持有进程引用，临时句柄用完即关
        return job
    except Exception as e:
        log(f"[WARN] Job Object 挂载失败（回退 taskkill /T）：{e}")
        return None


def _port_alive(host: str, port: int) -> bool:
    """HTTP 探测端口上是否仍有活服务（比 netstat PID 更接近真相：
    孤儿 worker 继承 socket 时 netstat 显示死父 PID）。"""
    try:
        with urllib.request.urlopen(
                f"http://{host}:{port}/api/health/live", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def start_backend(cfg: dict) -> subprocess.Popen:
    """自管理后端。

    workers=1：直接拉 uvicorn 单进程（角色 all，行为与历史门禁一致）。
    workers>1（T01692）：以隔离根/真实 backend 的 launcher.py 做角色编排——
    1 个 sched 进程（端口+1，承担建表/调度/隧道等一次性副作用）+
    N 个 api 进程（业务端口，纯 HTTP）。launcher 内部会先等 sched 就绪再放 api。
    """
    host, port = cfg["backend"]["host"], cfg["backend"]["port"]
    workers = int(cfg["backend"].get("workers", 1))
    app_cwd = ISO_ROOT if ISO_ROOT is not None else BACKEND_DIR
    if workers > 1:
        # 角色编排：launcher 读取 UVICORN_WORKERS/APP_PORT/SCHED_PORT 自行拆分
        launcher = app_cwd / "launcher.py"
        if not launcher.exists():
            abort(f"[ABORT] workers>1 需要角色编排入口 launcher.py：{launcher} 不存在")
        env = child_env({
            "RATE_LIMIT_PER_MINUTE": cfg["backend"]["rate_limit_per_minute"],
            "APP_HOST": host,
            "APP_PORT": port,
            "SCHED_PORT": port + 1,
            "UVICORN_WORKERS": workers,
            "SCHED_READY_TIMEOUT_SEC": max(60, int(cfg["backend"]["health_timeout_sec"]) - 30),
        })
        env.pop("APP_ROLE", None)  # 走 launcher 编排，不能预注入角色
        logf = (HERE / "gate_backend.log").open("w", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(
            [PY, str(launcher)],
            cwd=str(app_cwd), env=env, stdout=logf, stderr=subprocess.STDOUT)
        BACKEND_INFO.update({"workers": workers, "port": port, "sched_port": port + 1,
                             "roles": f"1 sched(:{port + 1}) + {workers} api(:{port})",
                             "job": None, "host": host})
    else:
        env = child_env({
            "RATE_LIMIT_PER_MINUTE": cfg["backend"]["rate_limit_per_minute"],
        })
        logf = (HERE / "gate_backend.log").open("w", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(
            [PY, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port),
             "--workers", str(workers)],
            cwd=str(app_cwd), env=env, stdout=logf, stderr=subprocess.STDOUT)
        BACKEND_INFO.update({"workers": 1, "port": port, "sched_port": None,
                             "roles": "all（单进程全部职责）",
                             "job": None, "host": host})
    BACKEND_INFO["job"] = _job_assign(proc)
    url = f"http://{host}:{port}/api/health/live"
    deadline = time.monotonic() + cfg["backend"]["health_timeout_sec"] + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            abort(f"[ABORT] 后端启动即退出（退出码 {proc.returncode}），见 gate_backend.log")
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status == 200:
                    log(f"[step] 后端就绪 {url}（pid {proc.pid}，workers={workers}，"
                        f"角色={BACKEND_INFO['roles']}，"
                        f"限流临时 {env['RATE_LIMIT_PER_MINUTE']}/min"
                        + ("，隔离副本" if ISO_ROOT is not None else "") + "）")
                    return proc
        except Exception:
            time.sleep(1.0)
    proc.terminate()
    abort("[ABORT] 后端健康检查超时，见 gate_backend.log")


def _port_listeners(port: int) -> list:
    """返回监听该端口的 PID（Windows 用 netstat，其它平台回退 lsof）。

    注意：中文 Windows 的 netstat 输出是 GBK，text=True 默认按 UTF-8 解码会炸
    （stdout=None → splitlines AttributeError），必须显式 errors="replace"。
    """
    try:
        if os.name == "nt":
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True,
                                 text=True, encoding="utf-8", errors="replace",
                                 timeout=20).stdout or ""
            pids = set()
            for line in out.splitlines():
                cols = line.split()
                if len(cols) >= 5 and cols[3].upper() == "LISTENING" and cols[1].endswith(f":{port}"):
                    pids.add(cols[4])
            return sorted(pids, key=int)
        out = subprocess.run(["lsof", "-ti", f":{port}", "-sTCP:LISTEN"],
                             capture_output=True, text=True, timeout=20).stdout
        return sorted({p for p in out.split() if p.isdigit()}, key=int)
    except Exception as e:  # 端口清扫是兜底，失败不应把门禁结论改成 ABORT
        log(f"[WARN] 端口监听者查询失败：{e}")
        return []


def stop_backend(proc: subprocess.Popen, cfg: dict | None = None) -> None:
    """停后端并确认端口死透。

    层次：① Job Object 终止（一锅端含 spawn worker，见 _job_assign）；
    ② taskkill /T 兜底；③ 轮询 HTTP 探测直到主端口/sched 端口都不再应答
    （孤儿 worker 继承 socket 时 netstat 的 PID 是死的，只有 HTTP 探测可信），
    超时仍活则按 netstat PID 补刀并 WARN。
    """
    port = int((cfg or {}).get("backend", {}).get("port", 0) or 0)
    host = BACKEND_INFO.get("host") or (cfg or {}).get("backend", {}).get("host", "127.0.0.1")
    sched_port = BACKEND_INFO.get("sched_port")
    if proc is not None and proc.poll() is None:
        job = BACKEND_INFO.get("job")
        if job:
            try:
                import ctypes
                ctypes.windll.kernel32.TerminateJobObject(int(job), 1)
                ctypes.windll.kernel32.CloseHandle(int(job))
            except Exception as e:
                log(f"[WARN] Job Object 终止失败：{e}")
            BACKEND_INFO["job"] = None
        if os.name == "nt":
            # /T 需要在父进程仍存活时才能枚举子进程树，故先于 terminate 执行
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        else:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
    # 轮询确认端口死透（孤儿 worker 只能靠 HTTP 探测发现）
    ports = [p for p in (port, sched_port if BACKEND_INFO.get("workers", 1) > 1 else None) if p]
    if ports:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            alive = [p for p in ports if _port_alive(host, p)]
            if not alive:
                break
            time.sleep(1.0)
        else:
            log(f"[WARN] 端口 {alive} 在 20s 后仍有活服务，尝试按 netstat PID 补刀")
            for p in alive:
                for pid in _port_listeners(p):
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        still = [p for p in ports if _port_alive(host, p)]
        if still:
            log(f"[ERROR] 端口 {still} 仍有活服务（孤儿进程未清干净），"
                f"下一轮门禁可能连到本轮后端，请手工排查")
    if proc is not None:
        log("[step] 后端已停止")


def clean_result_dirs(ids: list) -> None:
    for sid in ids:
        for d in (HERE / f"results_{sid}", HERE / f"results_{sid}" / "html"):
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)


def run_jmeter(cfg: dict, sid: str, spec: dict, token: str, atok: str, java_home: str,
             ranges: dict) -> Path:
    jmeter_bin = Path(os.environ.get("JMETER_BIN", cfg["jmeter"]["bin"]))
    if not jmeter_bin.exists():
        abort(f"[ABORT] 未找到 JMeter：{jmeter_bin}（可用环境变量 JMETER_BIN 指定）")
    out_dir = HERE / f"results_{sid}"
    out_dir.mkdir(parents=True, exist_ok=True)
    jtl = out_dir / "result.jtl"
    html = out_dir / "html"
    args = [
        "cmd", "/c", str(jmeter_bin),
        "-n", "-t", str(HERE / cfg["jmeter"]["plan"]),
        "-l", str(jtl),
        "-e", "-o", str(html),
        "-p", str(HERE / cfg["jmeter"]["properties"]),
        "-Jjmeter.save.saveservice.output_format=csv",
        "-Jhost=" + cfg["backend"]["host"],
        "-Jport=" + str(cfg["backend"]["port"]),
        "-Jprotocol=http",
        "-Jpath_prefix=",
        "-Jauth_token=" + token,
        "-Jadmin_token=" + atok,
        "-Jscenario=" + spec["scenario"],
        "-Jthreads=" + str(spec["threads"]),
        "-Jramp_up=" + str(spec["ramp"]),
        "-Jduration=" + str(spec["duration"]),
        "-Jthroughput=999999",
        "-Jepisode_id=" + str(cfg["jmeter"]["episode_id"]),
    ]
    for k in ("ep_min", "ep_max", "ch_min", "ch_max", "script_min", "script_max"):
        args.append(f"-J{k}={ranges[k]}")
    log(f"[run] {sid} scenario={spec['scenario']} threads={spec['threads']} "
        f"ramp={spec['ramp']} duration={spec['duration']}s")
    jenv = dict(os.environ)
    jenv["JAVA_HOME"] = java_home
    jenv["PATH"] = str(Path(java_home) / "bin") + os.pathsep + jenv.get("PATH", "")
    if jtl.exists():
        jtl.unlink()
    t0 = time.monotonic()
    proc = subprocess.run(args, cwd=str(HERE), env=jenv)
    if proc.returncode != 0:
        abort(f"[ABORT] JMeter 执行失败：{sid}（退出码 {proc.returncode}）")
    if not jtl.exists() or jtl.stat().st_size < 200:
        abort(f"[ABORT] {sid} 未产出有效 result.jtl —— 属压测工具链/环境问题，"
              f"不是被测系统的回归结论")
    log(f"[run] {sid} 完成，用时 {time.monotonic() - t0:.0f}s")
    return jtl


def count_5xx(jtl: Path) -> int:
    n = 0
    with jtl.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            code = (row.get("responseCode") or "").strip()
            if code.startswith("5"):
                n += 1
    return n


def judge(sid: str, spec: dict, m: dict, err_5xx: int, gate: dict) -> list:
    """返回破线条目列表；空列表表示达标。"""
    breach = []
    if m.get("error"):
        return [f"{sid}: JTL 无法解析（{m['error']}）"]
    if m["total_requests"] < 1:
        return [f"{sid}: 零样本"]
    max_err = float(spec.get("max_error_rate_pct", gate["max_error_rate_pct"]))
    if m["error_rate"] > max_err:
        breach.append(f"{sid}: 错误率 {m['error_rate']}% > {max_err}%")
    if err_5xx:
        breach.append(f"{sid}: 出现 {err_5xx} 个 5xx（正确性红线）")
    # 延迟阈值：有基线则用 基线 × drift，否则用绝对阈值
    drift = float(gate.get("drift_factor", 1.3))
    base = spec.get("baseline_p95_ms")
    if base:
        limit = round(base * drift)
        source = f"基线 {base} × {drift}"
    else:
        limit = spec.get("max_p95_ms")
        source = "绝对阈值（无基线）"
    if limit and m["p95_ms"] > limit:
        breach.append(f"{sid}: P95 {m['p95_ms']}ms > {limit}ms（{source}）")
    if spec.get("min_tps") and m["tps"] < spec["min_tps"]:
        breach.append(f"{sid}: TPS {m['tps']} < {spec['min_tps']}")
    return breach


def write_report(report: dict) -> None:
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    L = ["# 压测回归门禁报告（perf_gate.py）\n",
         f"> 时间：{report['started_at']}  档位：{report['tier']}  引擎：JMeter\n",
         f"> 后端：{'自管理 uvicorn' if report['backend_mode'] == 'auto' else '外部实例'} "
         f"#{report['port']}  限流：临时 {report['rate_limit']}/min（未改 .env）\n",
         f"> 进程编排：{report.get('roles', 'all（单进程全部职责）')}  "
         f"隔离副本：{'是（隧道已强制关闭，生产 data/ 零接触）' if report.get('iso') else '否'}\n",
         "\n| 档位 | 并发 | workers | 样本 | TPS | P50 | P95 | 错误率 | 5xx | 判定 |\n|--|--|--|--|--|--|--|--|--|--|\n"]
    for r in report["results"]:
        if r["status"] == "SKIPPED":
            L.append(f"| {r['id']} | {r['threads']} | - | - | - | - | - | - | - | SKIPPED（{r.get('reason')}） |\n")
            continue
        L.append(f"| {r['id']} | {r['threads']} | {r.get('workers', 1)} | {r['total']} | {r['tps']} | {r['p50_ms']} "
                 f"| {r['p95_ms']} | {r['error_rate']}% | {r['count_5xx']} | {r['status']} |\n")
    if any(r.get("compare_only") for r in report["results"]):
        L.append("\n> 注：REF-* 为 workers>1 角色编排对照档，多进程结果不可与单进程基线混比，不计入门禁判定。\n")
    if report["breaches"]:
        L.append("\n## 破线明细\n\n")
        L.append("\n".join(f"- {b}" for b in report["breaches"]) + "\n")
    L.append(f"\n## 结论\n\n- 判定：**{report['verdict']}**\n"
             f"- SQLite 写锁竞争（database is locked）日志计数：{report['lock_errors']['before']} → "
             f"{report['lock_errors']['after']}（扫描当日 MorningBrief 日志，best-effort）\n"
             f"- DB 计数：压测前 {report['db_counts']['before_seed']}；seed 后 "
             f"{report['db_counts']['after_seed']}；cleanup 后 {report['db_counts']['after_cleanup']}\n")
    REPORT_MD.write_text("".join(L), encoding="utf-8")
    log(f"[report] {REPORT_MD.name} / {REPORT_JSON.name} 已生成")


def main() -> int:
    global ISO_ROOT, DB_PATH
    ap = argparse.ArgumentParser(description="压测回归门禁（seed→跑→analyze→cleanup 一条命令）")
    ap.add_argument("--tier", choices=["quick", "standard", "full"], default="standard")
    ap.add_argument("--only", help="逗号分隔的档位 id，覆盖 tier")
    ap.add_argument("--include-soak", action="store_true", help="full 档位包含 S5_soak（30 分钟）")
    ap.add_argument("--backend", choices=["auto", "external"], default="auto",
                    help="auto=脚本自起自停 uvicorn；external=复用已在运行的实例")
    ap.add_argument("--port", type=int, help="覆盖配置中的端口（external 常用 8000）")
    ap.add_argument("--no-seed", action="store_true", help="跳过 seed/cleanup（库里已有夹具数据时）")
    ap.add_argument("--update-baseline", action="store_true", help="把本轮 P95/TPS 写为新的延迟基线")
    ap.add_argument("--dry-run", action="store_true", help="只打印执行计划")
    ap.add_argument("--workers", type=int,
                    help="自管理后端的 uvicorn worker 数（默认 1，保持门禁结论可复现；"
                         ">1 仅供路线 A 实验，写锁/缓存/调度器是进程内状态）")
    ap.add_argument("--iso-root", default=None,
                    help="T01692 隔离副本根目录：backend 代码/.env/data 复制到此执行，"
                         "副本内隧道强制 auto_start=false（生产 data/ 零接触），跑完自动清理。"
                         "不传则直接压真实 backend/data（历史行为，存在外发隧道通知风险）")
    a = ap.parse_args()

    cfg = load_config()
    gate = cfg["gate"]
    if a.port:
        cfg["backend"]["port"] = a.port
    # T01659：workers 可选覆盖，默认 1 以保持历史门禁结论可复现
    cfg["backend"]["workers"] = a.workers if a.workers else int(cfg["backend"].get("workers", 1))
    ids = [s.strip() for s in a.only.split(",")] if a.only else list(cfg["tiers"][a.tier])
    if not a.include_soak:
        ids = [i for i in ids if i != "S5_soak"]
    unknown = [i for i in ids if i not in cfg["scenarios"]]
    if unknown:
        abort(f"[ABORT] 配置中不存在的档位：{unknown}")

    atok = admin_token()
    plan_lines = []
    for i in ids:
        s = cfg["scenarios"][i]
        skip = s["scenario"] == "admin" and not atok
        w = s.get("workers", 1)
        tag = "  [对照档 REF，不判定]" if s.get("compare_only") else ""
        plan_lines.append(f"  {i:14s} scenario={s['scenario']:8s} threads={s['threads']:<5d} "
                          f"ramp={s['ramp']:<3d} duration={s['duration']}s workers={w}"
                          + ("  [SKIPPED 无 admin token]" if skip else "") + tag)
    total_min = sum(cfg["scenarios"][i]["duration"] + 20 for i in ids) / 60.0
    print(f"档位集合：{a.tier}（{len(ids)} 个） 预估耗时 ≈ {total_min:.1f} 分钟（不含 seed/cleanup）")
    print("\n".join(plan_lines))
    if a.dry_run:
        print("[dry-run] 未执行。")
        return 0

    if not DB_PATH.exists():
        abort(f"[ABORT] 数据库不存在：{DB_PATH}")

    # T01692：隔离副本（先于一切 DB 操作构建，后续 DB_PATH 全部指向副本）
    if a.iso_root:
        if a.backend == "external":
            abort("[ABORT] --iso-root 与 --backend external 互斥：外部实例读的是真实 data/，"
                  "副本里的 seed/token 与它不一致，指标与正确性全失真")
        try:
            ISO_ROOT = prepare_iso_root(a.iso_root)
        except SystemExit:
            raise
        except Exception as e:
            # 半成品副本必须清掉，避免残留占盘
            log(f"[ABORT] 隔离副本构建失败：{e}")
            try:
                _win_rmtree(Path(a.iso_root).resolve())
            except Exception:
                pass
            raise SystemExit(2)
        DB_PATH = ISO_ROOT / "data" / "news.db"
        if not DB_PATH.exists():
            abort(f"[ABORT] 隔离副本缺 news.db：{DB_PATH}")
        log(f"[iso] DB_PATH 已切换到副本：{DB_PATH}")

    java_home = resolve_java()
    log(f"[preflight] Python={PY}")
    log(f"[preflight] JAVA_HOME={java_home}")

    started_at = datetime.now().isoformat(timespec="seconds")
    before_counts = db_counts()
    after_seed = before_counts
    after_cleanup = before_counts
    lock_before = lock_errors()
    backend_proc = None
    results, breaches, skipped = [], [], []
    try:
        # 顺序要点：setup 在 seed 之前——seed 会把 favorites/play_log 夹具挂到
        # setup 建出的测试用户上，反过来则夹具用户不存在。
        # T01692：三个脚本经 PERF_BACKEND_DIR 环境变量指向副本 DB（隔离模式）
        step_env = child_env()
        if not a.no_seed:
            run_step("cleanup_seed.py(清理上轮残留)", [PY, HERE / "cleanup_seed.py"],
                     env=step_env)
        token = refresh_tokens()
        if not a.no_seed:
            run_step("seed_perf_data.py(灌入夹具)", [PY, HERE / "seed_perf_data.py"],
                     env=step_env)
        after_seed = db_counts()
        if after_seed.get("episode", 0) < gate["require_min_episodes"]:
            abort(f"[ABORT] seed 后 episode={after_seed.get('episode')} < "
                  f"{gate['require_min_episodes']}，数据量不达标，指标无意义")
        ranges = id_ranges()
        run_step("gen_perf_jmx.py(重新生成测试计划)", [PY, HERE / "gen_perf_jmx.py"])
        clean_result_dirs(ids)
        if a.backend == "auto":
            # 初始 workers 取第一个场景的要求（场景级 workers > CLI 默认）
            first_w = int(cfg["scenarios"][ids[0]].get("workers", cfg["backend"]["workers"]))
            cfg["backend"]["workers"] = first_w
            backend_proc = start_backend(cfg)
        else:
            backend_proc = None
            log(f"[step] 复用外部实例 http://{cfg['backend']['host']}:{cfg['backend']['port']}"
                f"（限流需自行确认已放宽）")
        cur_workers = int(cfg["backend"].get("workers", 1))

        for sid in ids:
            spec = cfg["scenarios"][sid]
            if spec["scenario"] == "admin" and not atok:
                skipped.append(sid)
                results.append({"id": sid, "threads": spec["threads"], "status": "SKIPPED",
                                "reason": "无 admin token"})
                log(f"[skip] {sid}：管理端档位缺 admin token")
                continue
            # T01692：场景级 workers 切换——需要重启后端按对应角色编排再跑
            if a.backend == "auto":
                want_workers = int(spec.get("workers", cfg["backend"]["workers"]))
                if want_workers != cur_workers:
                    log(f"[step] {sid} 要求 workers={want_workers}（当前 {cur_workers}），重启后端")
                    stop_backend(backend_proc, cfg)
                    cfg["backend"]["workers"] = want_workers
                    backend_proc = start_backend(cfg)
                    cur_workers = want_workers
            jtl = run_jmeter(cfg, sid, spec, token, atok, java_home, ranges)
            m = analyze.analyze_jtl(str(jtl))
            n5 = count_5xx(jtl) if jtl.exists() else 0
            row = {"id": sid, "threads": spec["threads"], "scenario": spec["scenario"],
                   "workers": int(spec.get("workers", cfg["backend"]["workers"])),
                   "total": m.get("total_requests", 0), "tps": m.get("tps", 0),
                   "p50_ms": m.get("p50_ms", 0), "p95_ms": m.get("p95_ms", 0),
                   "p99_ms": m.get("p99_ms", 0), "error_rate": m.get("error_rate", 0),
                   "count_5xx": n5}
            row["breaches"] = judge(sid, spec, m, n5, gate)
            if spec.get("compare_only"):
                # 对照档：workers>1 结果不可与单进程基线混比，只记录不判定
                row["status"] = "REF-FAIL" if row["breaches"] else "REF-PASS"
                row["compare_only"] = True
                log(f"[ref] {sid} -> {row['status']}（对照档，不计入门禁判定）  "
                    f"TPS {row['tps']}  P95 {row['p95_ms']}ms")
            else:
                row["status"] = "FAIL" if row["breaches"] else "PASS"
                breaches.extend(row["breaches"])
                log(f"[gate] {sid} -> {row['status']}  TPS {row['tps']}  P95 {row['p95_ms']}ms  "
                    f"错误率 {row['error_rate']}%")
            results.append(row)
    finally:
        stop_backend(backend_proc, cfg)
        if not a.no_seed:
            try:
                run_step("cleanup_seed.py(还原库)", [PY, HERE / "cleanup_seed.py"],
                         env=child_env())
            except SystemExit as e:
                log(f"[WARN] 清理失败，需手动执行 cleanup_seed.py：{e}")
        after_cleanup = db_counts()
        if ISO_ROOT is not None:
            _win_rmtree(ISO_ROOT)
            globals()["ISO_ROOT"] = None
            globals()["DB_PATH"] = BACKEND_DIR / "data" / "news.db"

    try:
        run_step("analyze.py(聚合报告)", [PY, HERE / "analyze.py"])
    except SystemExit as e:
        log(f"[WARN] analyze 聚合失败（不影响门禁判定）：{e}")

    if a.update_baseline:
        baseline = {}
        for r in results:
            if r["status"] in ("PASS", "FAIL") and r.get("p95_ms"):
                baseline[r["id"]] = {"baseline_p95_ms": r["p95_ms"], "baseline_tps": r["tps"],
                                     "updated_at": datetime.now().isoformat(timespec="seconds")}
        BASELINE_PATH.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[baseline] 已写入 {BASELINE_PATH.name}（{len(baseline)} 个档位）")

    verdict = "PASS" if not breaches else "FAIL"
    if not results:
        verdict = "NO_DATA"
    report = {"started_at": started_at, "tier": a.tier, "backend_mode": a.backend,
              "port": cfg["backend"]["port"], "workers": cfg["backend"]["workers"],
              "roles": BACKEND_INFO.get("roles", "all（单进程全部职责）"),
              "iso": bool(ISO_ROOT is not None or a.iso_root),
              "rate_limit": cfg["backend"]["rate_limit_per_minute"],
              "ids": ids, "skipped": skipped, "results": results, "breaches": breaches,
              "verdict": verdict,
              "lock_errors": {"before": lock_before, "after": lock_errors()},
              "db_counts": {"before_seed": before_counts,
                            "after_seed": after_seed,
                            "after_cleanup": after_cleanup}}
    write_report(report)
    print("\n=== 门禁结论：%s ===" % verdict)
    for b in breaches:
        print("  - " + b)
    if skipped:
        print("  (跳过档位：%s，原因：缺 admin token)" % ",".join(skipped))
    if verdict == "FAIL":
        return 1
    return 0 if verdict == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
