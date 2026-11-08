"""压测编排：基线/阶梯/soak + 资源采样 + 阶段时间标记。

用法：
    python run_suite.py --stress        # 9 档阶梯，约 17 分钟
    python run_suite.py --soak          # 4 小时稳定性
    python run_suite.py --baseline      # 两份基线
每次运行 JTL 前先删除同名文件（JMeter -l 是追加语义）。
长跑（--soak）必须用脱离父进程树的方式启动（例如 Start-Process cmd /c 批处理），
否则本会话的工具进程树回收或本机休眠都会把沙箱与 JMeter 一起带走，整批作废；
中断后只补跑受影响的那一段，不要混用不同批次的 JTL。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONFIG = json.loads((HERE / "perf_config.json").read_text(encoding="utf-8"))
TOK = json.loads((HERE / "runtime" / "tokens.json").read_text(encoding="utf-8"))
JMX = HERE / "jmx"
RES = HERE / "results"
RES.mkdir(parents=True, exist_ok=True)
JAVA = str(Path(CONFIG["sandbox"]["java_home"]) / "bin" / "java.exe")
JMETER_JAR = str(Path(CONFIG["sandbox"]["jmeter_home"]) / "bin" / "ApacheJMeter.jar")
_py = Path(CONFIG["sandbox"]["python"])
PY = str(_py if _py.is_absolute() else REPO / _py)
PORT = CONFIG["sandbox"]["port"]


def jmeter_props(token: str) -> list[str]:
    """凭据只从 runtime/tokens.json（已 gitignore）注入命令行，不写进 JMX。

    刻意不传 `-Jinternal_token`：本批 JMX 里的 `/api/internal/*` 一直是空令牌跑的，
    注入后这些端点的期望状态码会变，会让复跑结果与已归档批次不可比。
    """
    return [f"-Jport={PORT}", f"-Jtoken={token}", f"-Jadmin_password={TOK['admin_password']}"]


def log_phase(name: str, event: str) -> None:
    with (RES / "phases.csv").open("a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')},{name},{event}\n")


def run(name: str, jmx_name: str, token: str) -> float:
    jtl = RES / f"{name}.jtl"
    jtl.unlink(missing_ok=True)
    cmd = [
        JAVA, "-jar", JMETER_JAR, "-n",
        "-t", str(JMX / f"{jmx_name}.jmx"),
        "-l", str(jtl),
        *jmeter_props(token),
    ]
    log_phase(name, "start")
    t0 = time.time()
    with (RES / f"{name}.log").open("w", encoding="utf-8") as fh:
        subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False)
    dur = time.time() - t0
    lines = [l for l in (RES / f"{name}.log").read_text(encoding="utf-8", errors="replace").splitlines()
             if l.startswith("summary =")]
    log_phase(name, "end")
    print(f"[{name}] {dur:.0f}s {lines[-1] if lines else ''}", flush=True)
    return dur


def with_monitor(fn, tag: str) -> None:
    stop = RES / "STOP"
    stop.unlink(missing_ok=True)
    mon = subprocess.Popen([PY, str(HERE / "monitor.py"), "--out",
                            str(RES / f"monitor_{tag}.csv"),
                            "--interval", str(CONFIG["monitor"]["interval_sec"])])
    try:
        fn()
    finally:
        stop.write_text("1", encoding="utf-8")
        mon.wait(timeout=30)


def stress() -> None:
    read_tiers = CONFIG["stress"]["read_tiers"]
    write_tiers = CONFIG["stress"]["write_tiers"]
    admin_tiers = CONFIG["stress"]["admin_tiers"]

    def body() -> None:
        for t in read_tiers:
            run(f"stress_c_read_{t}", f"stress_c_read_{t}", TOK["c_token"])
        for t in write_tiers:
            run(f"stress_c_write_{t}", f"stress_c_write_{t}", TOK["c_token"])
        for t in admin_tiers:
            run(f"stress_admin_read_{t}", f"stress_admin_read_{t}", TOK["admin_token"])

    with_monitor(body, "stress")


def _soak_body() -> None:
    specs = [
        ("soak_c", "soak_c", TOK["c_token"]),
        ("soak_admin", "soak_admin", TOK["admin_token"]),
    ]
    procs = []
    for name, jmx_name, token in specs:
        jtl = RES / f"{name}.jtl"
        jtl.unlink(missing_ok=True)
        cmd = [JAVA, "-jar", JMETER_JAR, "-n", "-t", str(JMX / f"{jmx_name}.jmx"),
               "-l", str(jtl), f"-Jport={PORT}", f"-Jtoken={token}"]
        log_phase(name, "start")
        fh = (RES / f"{name}.log").open("w", encoding="utf-8")
        procs.append((name, subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT), fh))

    for name, proc, fh in procs:
        proc.wait()
        fh.close()
        log_phase(name, "end")
        print(f"[{name}] exit={proc.returncode}", flush=True)


def soak() -> None:
    with_monitor(_soak_body, "soak")


def baseline() -> None:
    with_monitor(lambda: (
        run("baseline_c", "baseline_c", TOK["c_token"]),
        run("baseline_admin", "baseline_admin", TOK["admin_token"]),
    ), "baseline")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stress", action="store_true")
    ap.add_argument("--soak", action="store_true")
    ap.add_argument("--baseline", action="store_true")
    a = ap.parse_args()
    if a.stress:
        stress()
    elif a.soak:
        soak()
    elif a.baseline:
        baseline()
    else:
        print(__doc__)
        sys.exit(1)
