"""
MorningBrief EXE 启动入口

PyInstaller 打包后的入口脚本，负责：
1. 定位 exe 同目录的 .env 配置文件
2. 将 backend 目录加入 sys.path（让 app 包可被导入）
3. 启动 uvicorn 加载 FastAPI 应用

V1.2 起架构调整：
- SQLite 数据库文件落在 exe 同目录的 data/ 子目录（嵌入式，无需外部容器）
- 进程内 TTLCache 替代 Redis（无需外部中间件）
- 启动时由 FastAPI lifespan 自动建表，无需运维干预

T01660（路线 A 前置）：workers>1 时不再让 N 个进程各跑一份调度器/隧道，
而是拆成「1 个 sched 进程（承担全应用只需跑一次的副作用）+ N 个 api 进程（纯 HTTP）」。
"""
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def get_app_dir() -> Path:
    """
    获取应用根目录。

    PyInstaller 打包后 sys.frozen 为 True，exe 路径在 sys.executable。
    开发模式下使用 __file__ 定位。返回 exe 同目录（.env 与配置文件所在位置）。
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包模式：exe 所在目录
        return Path(sys.executable).parent
    # 开发模式：backend/ 目录
    return Path(__file__).parent


def setup_environment():
    """
    配置运行时环境。

    将 backend 目录加入 sys.path，确保 app 包可被导入。
    切换工作目录到 exe 同目录，让 .env 和相对路径配置生效。
    """
    app_dir = get_app_dir()

    # backend 目录包含 app 包，需加入 sys.path
    # 打包后 app 包在 _internal/app/ 下（PyInstaller COLLECT 模式）
    if getattr(sys, 'frozen', False):
        # 打包模式：_internal 目录包含所有 Python 包
        internal_dir = app_dir / "_internal"
        if internal_dir.exists():
            sys.path.insert(0, str(internal_dir))
    else:
        # 开发模式：backend 目录本身
        sys.path.insert(0, str(app_dir))

    # 切换工作目录，让 .env 文件能被 pydantic-settings 加载
    os.chdir(app_dir)

    # 设置环境变量，确保日志目录指向 exe 同目录而非容器内路径
    if not os.environ.get("LOG_DIR"):
        os.environ["LOG_DIR"] = str(app_dir / "logs")


def _kill_tree(proc: subprocess.Popen) -> None:
    """结束 sched 子进程及其子进程树。

    Windows 上 proc.terminate() 只杀父进程，uvicorn/APScheduler 所在的子孙进程会残留
    并继续占用端口与调度器（T01659 实测），故 Windows 走 taskkill /F /T。
    """
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True, timeout=15,
            )
        else:
            proc.terminate()
        proc.wait(timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _wait_sched_ready(sched_port: int, proc: subprocess.Popen, timeout_sec: int) -> bool:
    """等待 sched 进程就绪（lifespan 完成建表/迁移/seed）后再放 api 起来。

    api 进程以 APP_ROLE=api 启动会跳过 DDL，若 sched 还没建好表就会 500，
    所以这里用 /api/health 作为「一次性初始化已完成」的就绪探针。
    """
    url = f"http://127.0.0.1:{sched_port}/api/health"
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            print(f"[launcher] sched 进程已退出（exit={proc.returncode}），放弃编排")
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:  # NOSONAR: 本机回环健康检查
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    print(f"[launcher] 等待 sched 就绪超时（{timeout_sec}s）: {url}")
    return False


def _run_split_roles(host: str, port: int, workers: int, settings) -> None:
    """workers>1 时的进程编排：1 个 sched 进程 + workers 个 api 进程（T01660）。

    sched 用独立内部端口（默认业务端口 +1，可用 SCHED_PORT 覆盖）只绑回环地址，
    避免与 api 抢同一个对外端口；api 进程由 uvicorn 的多进程 supervisor 起，
    通过 APP_ROLE=api 跳过建表/迁移/调度器/隧道这些一次性副作用。
    """
    sched_port = int(os.environ.get("SCHED_PORT") or (port + 1))
    env = {
        **os.environ,
        "APP_ROLE": "sched",
        "APP_HOST": "127.0.0.1",   # 内部角色，不对外提供服务
        "APP_PORT": str(sched_port),
        "UVICORN_WORKERS": "1",    # sched 必须单进程，否则重复调度
    }
    # 打包模式下 exe 自身就是 launcher 入口；开发模式用 python 重新执行本文件
    cmd = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(Path(__file__).resolve())]
    print(f"[launcher] workers={workers} → 启动 sched 进程（端口 {sched_port}）+ {workers} 个 api 进程")
    proc = subprocess.Popen(cmd, env=env, cwd=str(get_app_dir()))
    try:
        if not _wait_sched_ready(sched_port, proc, int(os.environ.get("SCHED_READY_TIMEOUT_SEC") or 120)):
            print("[launcher] sched 未就绪，回退为单进程默认角色启动（保证服务可用优先）")
            _kill_tree(proc)
            os.environ["APP_ROLE"] = "all"
            import uvicorn

            uvicorn.run("app.main:app", host=host, port=port, workers=1,
                        log_level=settings.LOG_LEVEL.lower(), log_config=None)
            return
        print(f"[launcher] sched 已就绪，启动 {workers} 个 api 进程（端口 {port}）")
        os.environ["APP_ROLE"] = "api"
        import uvicorn

        uvicorn.run("app.main:app", host=host, port=port, workers=workers,
                    log_level=settings.LOG_LEVEL.lower(), log_config=None)
    finally:
        _kill_tree(proc)
        print("[launcher] sched 进程已结束")


def main():
    """启动 uvicorn 服务。"""
    setup_environment()

    # 初始化日志系统（必须在 uvicorn.run 之前，以便 InterceptHandler 拦截 uvicorn 日志）
    # loguru + colorama 统一颜色渲染，避免 uvicorn 默认 ANSI 码在 cmd 窗口显示为 [32m 乱码
    from app.config import get_settings
    from app.core.logging_setup import setup_logging

    settings = get_settings()
    try:
        from app.paths import resolve_log_dir
        log_dir = str(resolve_log_dir())
    except Exception:
        log_dir = settings.LOG_DIR

    setup_logging(
        log_level=settings.LOG_LEVEL,
        log_dir=log_dir,
        log_file_max_mb=settings.LOG_FILE_MAX_MB,
    )

    import uvicorn

    app_dir = get_app_dir()

    # 从 .env 读取配置（已由 pydantic-settings 处理）
    # 默认绑定 0.0.0.0:8000，可通过 .env 的 APP_HOST/APP_PORT 覆盖
    host = os.environ.get("APP_HOST", "0.0.0.0")
    port = int(os.environ.get("APP_PORT", "8000"))
    # T01659：此前这里硬编码 workers=1，config.py 的 UVICORN_WORKERS 是从不被读取的死配置。
    # 接成真实生效，默认值仍取 settings（=1），行为与改造前完全一致。
    workers = int(settings.UVICORN_WORKERS or 1)

    # 角色已由上层编排注入（APP_ROLE=api/sched）时，本进程不再拆分，直接按该角色跑，
    # 否则 sched 子进程会再次进入编排逻辑形成递归启动。
    # sched 进程只跑一次性职责，必须是单进程（workers>1 等于又变回重复调度）。
    injected_role = (os.environ.get("APP_ROLE") or "").strip().lower()
    if injected_role == "sched":
        workers = 1

    print("=" * 50)
    print("  MorningBrief 语音新闻播报服务")
    print("=" * 50)
    print(f"  工作目录: {app_dir}")
    print(f"  监听地址: http://{host}:{port}")
    print(f"  工作进程: {workers}")
    print(f"  进程角色: {injected_role or 'all（默认，单进程全部职责）'}")
    print(f"  API 文档: http://{host}:{port}/docs")
    print(f"  健康检查: http://{host}:{port}/api/health")
    print("=" * 50)
    print()

    # log_config=None：禁用 uvicorn 默认日志配置，日志已由 loguru InterceptHandler 接管
    # workers>1 的前置约束见 config.py 的 UVICORN_WORKERS 注释（写锁/缓存均为进程内状态）
    if workers > 1 and injected_role not in ("api", "sched"):
        _run_split_roles(host, port, workers, settings)
        return

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        workers=workers,
        log_level=settings.LOG_LEVEL.lower(),
        log_config=None,
    )


if __name__ == "__main__":
    main()
