"""日志系统配置（loguru + InterceptHandler）

对标 17_xianyu 项目的日志设计：
- 控制台 sink：彩色输出，含日期时间 + request_id + 模块路径
- 文件 sink：纯文本，单文件达 LOG_FILE_MAX_MB（默认 10MB）或跨日滚动，
  保留 LOG_RETENTION_DAYS 天（默认 7），并有目录总量上限 LOG_DIR_MAX_MB
- InterceptHandler：将 uvicorn/SQLAlchemy 等标准库 logging 重定向到 loguru，
  统一所有日志格式（补全闲鱼项目的设计缺口）

颜色由 loguru color tag 声明，底层 colorama 处理 Windows cmd 终端兼容，
避免 uvicorn 默认 ANSI 码在 cmd 窗口显示为 [32m 乱码。
"""
import logging
import os
import sys
import time
from pathlib import Path

from loguru import logger

from app.core.request_context import get_request_id

_configured = False


def _make_rotation(max_mb: int):
    """loguru 自定义 rotation 谓词：文件达到 max_mb 或跨日即滚动。

    loguru 单个 sink 只接受一个 rotation 条件，无法原生同时支持
    「大小滚动 + 每日零点滚动」，故用谓词函数组合两者：
    - 大小滚动：os.path.getsize 超过 max_mb（兜底单日刷爆磁盘，
      2026-09-10 单日曾达 68MB）
    - 每日滚动：本地日期变化时滚动（保留原 rotation="00:00" 语义，
      文件名中的 {time:YYYY-MM-DD} 保持按日期可读）
    """
    max_bytes = max(1, int(max_mb)) * 1024 * 1024
    state = {"day": None}

    def _should_rotate(message, file=None) -> bool:
        # 兼容不同 loguru 版本：部分版本回调 (message)，较新版本回调 (message, file)
        f = file if file is not None else getattr(message, "file", None)
        try:
            if os.path.getsize(f.name) >= max_bytes:
                return True
        except (OSError, AttributeError):
            pass  # 文件暂不可 stat 时跳过大小判断，下条日志再试
        day = time.strftime("%Y-%m-%d", time.localtime())
        if state["day"] is None:
            state["day"] = day  # 首条日志仅记录基准日，不触发滚动
            return False
        if day != state["day"]:
            state["day"] = day
            return True
        return False

    return _should_rotate


def _enforce_dir_quota(log_dir: Path, max_mb: int) -> int:
    """启动时清理超出总量上限的日志分片，返回释放的字节数。

    与 loguru 的 retention 构成双保险：
    - retention 按**单文件 mtime** 清理，压测/批量导入等高频场景可在数小时内
      刷出数十个当日分片，它们 mtime 全在保留窗口内 → retention 一个都删不掉。
    - 本函数按**目录总量**兜底，超限时从 mtime 最旧的分片开始删。

    只删 MorningBrief_*.log 本系统产生的文件，不碰同目录下的其他文件。
    保留当前活动文件（当天最新那个），避免删掉正在写入的分片。
    """
    limit = max(0, int(max_mb)) * 1024 * 1024
    if limit == 0 or not log_dir.is_dir():
        return 0

    try:
        shards = [
            p for p in log_dir.glob("MorningBrief_*.log")
            if p.is_file() and not p.is_symlink()
        ]
    except OSError:
        return 0
    if not shards:
        return 0

    # mtime 由旧到新（st_mtime, name 保证同刻稳定排序）
    # 用 stat 存根吸收「枚举后文件恰好被外部删掉」的竞态（Windows 上
    # startup 与其他进程并发时可能发生），否则 FileNotFoundError 会阻断启动。
    def _mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    def _size(p: Path) -> int:
        try:
            return p.stat().st_size
        except OSError:
            return 0

    shards.sort(key=lambda p: (_mtime(p), p.name))

    total = sum(_size(p) for p in shards)
    freed = 0
    # shards[:-1] 跳过最新那个 —— 它是正在写入的活动分片，永不删
    for p in shards[:-1]:
        # 注意只累加 freed，不再同时扣 total —— 两个变量都表示"已删除量"，
        # 重复扣减会让 total-freed 提前跌破 limit，导致删不够就停手。
        if total - freed <= limit:
            break
        try:
            size = _size(p)
            p.unlink()
            freed += size
        except OSError:
            # 文件被占用/沙箱拦截 unlink；清理是尽力而为，不阻断启动。
            continue

    if freed:
        logger.warning(
            "日志目录超出 {}MB 上限，已清理最旧分片释放 {:.1f}MB",
            max_mb, freed / 1024 / 1024,
        )
    return freed


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

def setup_logging(
    log_level: str = "INFO",
    log_dir: str | Path | None = None,
    log_file_max_mb: int = 10,
    retention_days: int = 7,
    dir_max_mb: int = 200,
) -> None:
    """全局初始化日志系统：控制台（彩色）+ 文件（纯文本滚动）。

    幂等设计：多次调用不会重复添加 sink。

    Args:
        log_level: 控制台/文件日志级别。
        log_dir: 日志目录，None 则不落文件。
        log_file_max_mb: 单文件大小上限（MB），达到即滚动。
        retention_days: 日志保留天数（按 mtime 清理过期分片）。
        dir_max_mb: 日志目录总量上限（MB），超出时从最旧的分片开始删。
            与 retention 构成双保险：retention 只看单文件年龄，
            压测等高频场景可在数小时内刷出数十个当日分片（年龄全在窗口内）。
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

    # 文件 sink：纯文本（无颜色码），单文件达 log_file_max_mb 或跨日即滚动，
    # 保留 retention_days 天，并受 dir_max_mb 总量上限兜底
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
            rotation=_make_rotation(log_file_max_mb),
            retention=f"{max(1, int(retention_days))} days",
            encoding="utf-8",
        )
        # 目录总量兜底：retention 只看单文件年龄，压测等高频场景可在数小时内
        # 刷出数十个当日分片（mtime 全在窗口内），单靠 retention 挡不住磁盘被撑满。
        _enforce_dir_quota(log_path, max_mb=dir_max_mb)

    # 拦截 uvicorn 日志：将 uvicorn / uvicorn.access / uvicorn.error 重定向到 loguru
    # 这样 uvicorn 的访问日志也会带 request_id 和统一颜色格式
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = [InterceptHandler()]
        uv_logger.propagate = False

    # 拦截 root logger：将所有标准库 logging（crawler/article_parser/dedup 等业务模块
    # 使用 logging.getLogger(__name__)）重定向到 loguru。
    # 不配置时，业务模块的日志走标准 logging 继承链到 root logger，
    # root logger 无 handler 导致日志丢失（wf-20260728-0011 排查时 crawler 业务日志
    # 在 9:11-9:14 时间段完全缺失，无法定位 10 条 insert_failures 的具体异常）。
    # InterceptHandler.emit 调用 record.getMessage() 会正确执行 %s/%d 格式化，
    # 因此业务模块可继续使用标准 logging 的 %-style 占位符。
    root_logger = logging.getLogger()
    root_logger.handlers = [InterceptHandler()]
    root_logger.setLevel(0)  # 不过滤，由 loguru sink 的 level 决定最终输出


def get_logger():
    """获取已配置的 loguru logger。"""
    return logger
