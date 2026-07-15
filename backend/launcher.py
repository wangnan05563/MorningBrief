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
"""
import os
import sys
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

    setup_logging(log_level=settings.LOG_LEVEL, log_dir=log_dir)

    import uvicorn

    app_dir = get_app_dir()

    # 从 .env 读取配置（已由 pydantic-settings 处理）
    # 默认绑定 0.0.0.0:8000，可通过 .env 的 APP_HOST/APP_PORT 覆盖
    host = os.environ.get("APP_HOST", "0.0.0.0")
    port = int(os.environ.get("APP_PORT", "8000"))

    print("=" * 50)
    print("  MorningBrief 语音新闻播报服务")
    print("=" * 50)
    print(f"  工作目录: {app_dir}")
    print(f"  监听地址: http://{host}:{port}")
    print(f"  API 文档: http://{host}:{port}/docs")
    print(f"  健康检查: http://{host}:{port}/api/health")
    print("=" * 50)
    print()

    # workers=1：APScheduler 仅在主进程运行，多 worker 会导致重复调度
    # log_config=None：禁用 uvicorn 默认日志配置，日志已由 loguru InterceptHandler 接管
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        workers=1,
        log_level=settings.LOG_LEVEL.lower(),
        log_config=None,
    )


if __name__ == "__main__":
    main()
