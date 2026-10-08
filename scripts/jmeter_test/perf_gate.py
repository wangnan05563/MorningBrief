# -*- coding: utf-8 -*-
"""T01581 压测回归门禁：一条命令跑完 seed → 生成 jmx → 固定档位压测 → analyze → cleanup。

用法：
    python perf_gate.py --tier quick            # ~4 分钟，3 个档位
    python perf_gate.py --tier standard         # 默认档，含管理端
    python perf_gate.py --tier full --include-soak
    python perf_gate.py --only S1_read_200      # 单档复测
    python perf_gate.py --tier quick --update-baseline   # 把本轮结果写为新的延迟基线

退出码：0=全部达标；1=有档位破线（回归）；2=前置条件或执行失败（不视为回归结论）。

设计约束（沿用 T01518 实测口径，勿随意改动）：
- 后端固定 workers=1（单进程事件循环），压测结论只在单 worker 下可复现。
- 限流通过子进程环境变量 RATE_LIMIT_PER_MINUTE 临时解除，不改 backend/.env。
- token 只经 -Jauth_token / -Jadmin_token 注入 jmeter，不写进 jmx 文件。
- jtl 为 CSV（显式传 -Jjmeter.save.saveservice.output_format=csv）。
- 种子数据一律用标记行灌入/清理（seed_perf_data.py / cleanup_seed.py），
  压测结束无论成败都在 finally 里清理，开发库不残留。
- 管理端档位需要 admin token（环境变量 GATE_ADMIN_TOKEN 或 admin_token.txt），
  缺失时跳过 S3_* 并在报告中标 SKIPPED，不判失败。
"""
import argparse
import csv
import json
import os
import shutil
import sqlite3
import subprocess
import sys
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


def lock_errors() -> int:
    n, _ = analyze.count_db_locked()
    return n


def run_step(name: str, argv: list, cwd: Path = None) -> None:
    log(f"[step] {name}: {' '.join(str(a) for a in argv)}")
    proc = subprocess.run([str(a) for a in argv], cwd=str(cwd) if cwd else None)
    if proc.returncode != 0:
        abort(f"[ABORT] 步骤失败：{name}（退出码 {proc.returncode}）")


def refresh_tokens() -> str:
    """每轮都执行 setup.py 刷新 C 端 token。

    不能只判 test_token.txt 是否存在：token 有效期 1 天，且测试用户可能被历史清理
    脚本删掉——两种情况下复用旧 token 会让全部鉴权接口 401（实测错误率 100%、
    TPS 虚高），门禁结论完全失真。setup.py 用 INSERT OR IGNORE 保证幂等。
    """
    run_step("setup.py(建/复用测试用户 + 签发 token)", [PY, HERE / "setup.py"])
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


def start_backend(cfg: dict) -> subprocess.Popen:
    host, port = cfg["backend"]["host"], cfg["backend"]["port"]
    env = dict(os.environ)
    env["RATE_LIMIT_PER_MINUTE"] = str(cfg["backend"]["rate_limit_per_minute"])
    env["PYTHONIOENCODING"] = "utf-8"
    logf = (HERE / "gate_backend.log").open("w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port), "--workers", "1"],
        cwd=str(BACKEND_DIR), env=env, stdout=logf, stderr=subprocess.STDOUT)
    url = f"http://{host}:{port}/api/health/live"
    deadline = time.monotonic() + cfg["backend"]["health_timeout_sec"]
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            abort(f"[ABORT] 后端启动即退出（退出码 {proc.returncode}），见 gate_backend.log")
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status == 200:
                    log(f"[step] 后端就绪 {url}（pid {proc.pid}，workers=1，限流临时 {env['RATE_LIMIT_PER_MINUTE']}/min）")
                    return proc
        except Exception:
            time.sleep(1.0)
    proc.terminate()
    abort("[ABORT] 后端健康检查超时，见 gate_backend.log")


def stop_backend(proc: subprocess.Popen) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
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
         f"> 后端：{'自管理 uvicorn workers=1' if report['backend_mode'] == 'auto' else '外部实例'} "
         f"#{report['port']}  限流：临时 {report['rate_limit']}/min（未改 .env）\n",
         "\n| 档位 | 并发 | 样本 | TPS | P50 | P95 | 错误率 | 5xx | 判定 |\n|--|--|--|--|--|--|--|--|--|\n"]
    for r in report["results"]:
        if r["status"] == "SKIPPED":
            L.append(f"| {r['id']} | {r['threads']} | - | - | - | - | - | - | SKIPPED（{r.get('reason')}） |\n")
            continue
        L.append(f"| {r['id']} | {r['threads']} | {r['total']} | {r['tps']} | {r['p50_ms']} "
                 f"| {r['p95_ms']} | {r['error_rate']}% | {r['count_5xx']} | {r['status']} |\n")
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
    a = ap.parse_args()

    cfg = load_config()
    gate = cfg["gate"]
    if a.port:
        cfg["backend"]["port"] = a.port
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
        plan_lines.append(f"  {i:14s} scenario={s['scenario']:8s} threads={s['threads']:<5d} "
                          f"ramp={s['ramp']:<3d} duration={s['duration']}s"
                          + ("  [SKIPPED 无 admin token]" if skip else ""))
    total_min = sum(cfg["scenarios"][i]["duration"] + 20 for i in ids) / 60.0
    print(f"档位集合：{a.tier}（{len(ids)} 个） 预估耗时 ≈ {total_min:.1f} 分钟（不含 seed/cleanup）")
    print("\n".join(plan_lines))
    if a.dry_run:
        print("[dry-run] 未执行。")
        return 0

    if not DB_PATH.exists():
        abort(f"[ABORT] 数据库不存在：{DB_PATH}")

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
        if not a.no_seed:
            run_step("cleanup_seed.py(清理上轮残留)", [PY, HERE / "cleanup_seed.py"])
        token = refresh_tokens()
        if not a.no_seed:
            run_step("seed_perf_data.py(灌入夹具)", [PY, HERE / "seed_perf_data.py"])
        after_seed = db_counts()
        if after_seed.get("episode", 0) < gate["require_min_episodes"]:
            abort(f"[ABORT] seed 后 episode={after_seed.get('episode')} < "
                  f"{gate['require_min_episodes']}，数据量不达标，指标无意义")
        ranges = id_ranges()
        run_step("gen_perf_jmx.py(重新生成测试计划)", [PY, HERE / "gen_perf_jmx.py"])
        clean_result_dirs(ids)
        backend_proc = start_backend(cfg) if a.backend == "auto" else None
        if a.backend == "external":
            log(f"[step] 复用外部实例 http://{cfg['backend']['host']}:{cfg['backend']['port']}"
                f"（限流需自行确认已放宽）")

        for sid in ids:
            spec = cfg["scenarios"][sid]
            if spec["scenario"] == "admin" and not atok:
                skipped.append(sid)
                results.append({"id": sid, "threads": spec["threads"], "status": "SKIPPED",
                                "reason": "无 admin token"})
                log(f"[skip] {sid}：管理端档位缺 admin token")
                continue
            jtl = run_jmeter(cfg, sid, spec, token, atok, java_home, ranges)
            m = analyze.analyze_jtl(str(jtl))
            n5 = count_5xx(jtl) if jtl.exists() else 0
            row = {"id": sid, "threads": spec["threads"], "scenario": spec["scenario"],
                   "total": m.get("total_requests", 0), "tps": m.get("tps", 0),
                   "p50_ms": m.get("p50_ms", 0), "p95_ms": m.get("p95_ms", 0),
                   "p99_ms": m.get("p99_ms", 0), "error_rate": m.get("error_rate", 0),
                   "count_5xx": n5}
            row["breaches"] = judge(sid, spec, m, n5, gate)
            row["status"] = "FAIL" if row["breaches"] else "PASS"
            breaches.extend(row["breaches"])
            results.append(row)
            log(f"[gate] {sid} -> {row['status']}  TPS {row['tps']}  P95 {row['p95_ms']}ms  "
                f"错误率 {row['error_rate']}%")
    finally:
        stop_backend(backend_proc)
        if not a.no_seed:
            try:
                run_step("cleanup_seed.py(还原开发库)", [PY, HERE / "cleanup_seed.py"])
            except SystemExit as e:
                log(f"[WARN] 清理失败，需手动执行 cleanup_seed.py：{e}")
        after_cleanup = db_counts()

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
              "port": cfg["backend"]["port"], "rate_limit": cfg["backend"]["rate_limit_per_minute"],
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
