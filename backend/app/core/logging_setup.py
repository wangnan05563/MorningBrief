"""日志系统配置（loguru + InterceptHandler）

对标 17_xianyu 项目的日志设计：
- 控制台 sink：彩色输出，含日期时间 + request_id + 模块路径
- 文件 sink：纯文本，按日滚动，保留 14 天
- InterceptHandler：将 uvicorn/SQLAlchemy 等标准库 logging 重定向到 loguru，
  统一所有日志格式（补全闲鱼项目的设计缺口）

颜色由 loguru color tag 声明，底层 colorama 处理 Windows cmd 终端兼容，
避免 uvicorn 默认 ANSI 码在 cmd 窗口显示为 [32m 乱码。
"""
import logging
import sys
from pathlib import Path

from loguru import logger

from app.core.request_context import get_request_id

_configured = False


class InterceptHandler(logging.Handler):
    """标准库 logging → loguru 桥接器。

    将 uvicorn.access / uvicorn.error / SQLAlchemy 等使用标准库 logging 的组件
    重定向到 loguru，使所有日志统一格式（含 request_id、颜色、文件落盘）。
    """

    def emit(self, record: logging.LogRecord) -> None:
        # 标准库 level → loguru level 映射
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 回溯到真正的调用栈帧，而非本 emit 方法
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _patcher(record) -> None:
    """loguru patcher：每条日志记录前自动从 ContextVar 注入 request_id。

    业务代码只需 `from loguru import logger; logger.info("...")`，
    无需手动 bind request_id。
    """
    record["extra"]["request_id"] = get_request_id() or "-"



def _admin_log_filter(record):
    """Filter: downgrade /admin/ access logs from INFO to DEBUG.

    The admin dashboard polls /queue/stats and /queue/tasks every 5-30s,
    generating?? INFO-level access logs that drown out real warnings.
    This filter silently drops INFO logs for /admin/ paths.
    """
    if getattr(record.get("level"), "no", 0) == 20 == 20:  # INFO
        msg = record.get("message", "")
        if "/admin/" in msg and ("GET /admin/" in msg or "POST /admin/" in msg):
            return False
    return True

def setup_logging(log_level: str = "INFO", log_dir: str | Path | None = None) -> None:
    """全局初始化日志系统：控制台（彩色）+ 文件（纯文本滚动）。

    幂等设计：多次调用不会重复添加 sink。
    """
    global _configured
    if _configured:
        return
    _configured = True

    # colorama 初始化：启用 Windows cmd 的 ANSI 转义码渲染支持
    # 不初始化时 Win10 cmd 可能将 \033[32m 显示为 [32m 乱码
    try:
        import colorama
        colorama.init()
    except ImportError:
        pass  # 非 Windows 或未安装 colorama 时 loguru 自有降级

    logger.remove()
    logger.configure(patcher=_patcher)

    # 控制台 sink：人类可读，颜色分明，含 request_id 便于排障定位
    # <level> 标签随日志级别动态变色：DEBUG蓝/INFO默认/WARNING黄/ERROR红
    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>[req={extra[request_id]}]</cyan> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # 文件 sink：纯文本（无颜色码），按日滚动，保留 14 天
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_path / "MorningBrief_{time:YYYY-MM-DD}.log",
            filter=_admin_log_filter,
            level="DEBUG",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "[req={extra[request_id]}] | "
                "{name}:{function}:{line} - {message}"
            ),
            rotation="00:00",
            retention="14 days",
            encoding="utf-8",
        )

    # 拦截 uvicorn 日志：将 uvicorn / uvicorn.access / uvicorn.error 重定向到 loguru
    # 这样 uvicorn 的访问日志也会带 request_id 和统一颜色格式
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = [InterceptHandler()]
        uv_logger.propagate = False


def get_logger():
    """获取已配置的 loguru logger。"""
    return logger
