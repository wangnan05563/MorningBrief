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
import re
import sys
import time
from pathlib import Path

from loguru import logger

from app.core.request_context import get_request_id

_configured = False

# ---- 第三方内部日志封顶 ----
# 根因（NFR-UX-05 日志抽样，2026-10-08 那两天刷出 195MB）：本模块把 InterceptHandler
# 挂在 root 上且 root.setLevel(0)，文件 sink 又固定 level="DEBUG"，于是所有第三方库的
# DEBUG/INFO 内部日志都原样落盘。实测后果有两层：
#   1. 凭据落盘 —— 抽样命中 2538 行 COS v5 签名字符串
#      `q-sign-algorithm=sha1&q-ak=<SecretId>&...&q-signature=<签名>`，
#      以及 18 行 SQLAlchemy 异常回显的 `[SQL: ...] [parameters: ...]`（绑定参数=真实写入值）。
#   2. 磁盘被内部日志淹没，真正的关键失败行反而看不见。
# 这些库的 DEBUG 不是本项目产生的，业务排障不依赖它们，故一律封到 WARNING；
# 需要临时打开时按库名单调本表，不要改 root。
NOISY_LOGGERS: tuple[str, ...] = (
    "sqlalchemy",     # engine echo 会连 SQL 文本 + 绑定参数一起打 INFO/DEBUG
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    "aiosqlite",      # 驱动层 DEBUG 把 cursor.execute(sql, params) 整参回显（实测含明文配置值）
    "cos",            # COS SDK 打整条 Authorization 签名
    "qcloud",
    "httpx",
    "httpcore",
    "urllib3",
    "asyncio",
    "watchfiles",
    "multipart",
)
_NOISY_FLOOR = logging.WARNING


def _cap_noisy_loggers() -> None:
    """把第三方命名空间的标准库 logger 封到 WARNING（已更严格的保持不动）。"""
    for name in NOISY_LOGGERS:
        lg = logging.getLogger(name)
        # max() 而非 getEffectiveLevel()：level=0 是 NOTSET（继承 root=0），
        # 直接取 max 就把它抬到 WARNING；调用方已设得更严（如 ERROR）时保持不动。
        lg.setLevel(max(lg.level, _NOISY_FLOOR))


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

        # 回溯到真正的调用栈帧，而非本 emit 方法（loguru 官方给的配方）。
        # NFR-UX-05（T02523）修前的坑：循环判断的是「当前帧在不在 logging 里」，
        # 而当前帧是本 emit（不在 logging.__file__）⇒ 一次都不前进，depth 恒为 2，
        # 每条桥接日志的 {name}:{function}:{line} 全被写成 logging:callHandlers:1762。
        # 上面那 2538 行明文凭据因此查不出是谁打的 —— 归属错乱本身就是可观测性缺陷。
        # 首帧无条件前进（depth==0 分支）才是关键：emit 自己不在 logging 里，
        # 少了这一步就永远停在标准库内部帧上。
        frame, depth = logging.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        # 把标准库 logger 名带上，供下游按来源过滤/检索（loguru 的 {name} 是模块路径，
        # 拿不到 `logging.getLogger("cos")` 这种自定义名字）。
        # record.getMessage() 是 `msg % args`：占位符与参数不匹配时它会抛 TypeError。
        # 桥接器一旦让它抛出，异常会沿 callHandlers 冒回**业务调用点** ——
        # 抽到的真实样本正是这样：main 的 `[startup] 加载 AI 配置失败: not all arguments
        # converted during string formatting`，一条写歪的日志把整段配置加载打回 .env 默认值。
        # 标准库的契约是 handler 失败不外泄（handleError），这里照办。
        try:
            message = record.getMessage()
        except Exception as exc:
            self.handleError(record)
            # 不回显 record.args —— 那正是可能躺着凭据的部分
            message = f"[日志格式化失败 type={type(exc).__name__}] msg={record.msg!r}"

        try:
            logger.bind(stdlib_logger=record.name).opt(
                depth=depth, exception=record.exc_info
            ).log(level, message)
        except Exception:
            self.handleError(record)


# ---- 落盘前凭据脱敏（兜底层）----
# _cap_noisy_loggers 挡的是「第三方自己打的凭据」；这里挡的是「凭据从任何来源
# 挤进一行日志」的路径 —— 例如 app/core/exceptions.py 把 SQLAlchemy 异常原样
# `{exc}` 插进消息，异常文本自带 `[SQL: ...] [parameters: ...]` 绑定参数。
# 按形状遮而不是按字段遮：日志到了这一层已经是一行字符串，无法再区分键值语义。
_REDACT_TRIGGERS = (
    "q-ak", "akid", "sk-", "key", "token", "secret", "password", "passwd",
    "bearer", "signature", "parameters:", "$2a$", "$2b$", "$2y$",
)

_REDACT_RULES: tuple[tuple[re.Pattern, str], ...] = (
    # COS SecretId 裸形态、私钥块
    (re.compile(r"\bAKID[A-Za-z0-9]{8,}"), "AKID<已脱敏>"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "<私钥块已脱敏>"),
    # 通用 `key: value` / `key=value` 形态的凭据值
    (
        re.compile(
            r"(?i)(api[_-]?key|apikey|access[_-]?key|secret[_-]?key|secret[_-]?id|"
            r"password|passwd|token|authorization|q-ak|q-signature)"
            r"""(["']?\s*[=:]\s*["']?)"""
            r"""([^\s"',;&]{4,})"""
        ),
        r"\1\2<已脱敏>",
    ),
    # 裸形态
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}"), "sk-<已脱敏>"),
    (re.compile(r"(?i)\bBearer\s+[A-Z0-9._~+/-]{8,}"), "Bearer <已脱敏>"),
    (re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{20,}"), "bcrypt<已脱敏>"),
    # SQLAlchemy 异常回显：保留「有条 SQL 出错」这件事，丢掉绑定参数
    (re.compile(r"\[parameters: .*?\](?=\s*(?:\n|$))", re.S), "[parameters: <已脱敏>]"),
)


def redact_credentials(message: str) -> str:
    """把消息里长得像凭据的片段换成占位符。

    先用一次子串预检再跑正则：日志量大时（单日曾达 68MB）逐条跑十条正则是纯浪费，
    而绝大多数行本来就不含凭据形状。
    """
    low = message.lower()
    if not any(t in low for t in _REDACT_TRIGGERS):
        return message
    for pattern, repl in _REDACT_RULES:
        message = pattern.sub(repl, message)
    return message


def unwrap_echo_exception(exc: BaseException | None) -> BaseException | None:
    """把 SQLAlchemy 的「回显型」包装异常换成底层 DBAPI 异常，供记日志用。

    为什么单独处理：redact_credentials 只能遮 record["message"]，而 loguru 渲染堆栈时
    用的是异常对象自己的字符串，绕不过去。SQLAlchemy 的 DBAPIError.__str__ 恰好把
    `[SQL: ...] [parameters: ...]` 拼进去（抽样实测 18 行），等于堆栈一落盘就把本次写入
    的绑定参数（含凭据列明文）抄进日志。底层 `exc.orig`（如 sqlite3.IntegrityError）
    带同样的错误语义但不带参数，堆栈与局部变量信息也不受影响。
    """
    if exc is None:
        return None
    if not type(exc).__module__.startswith("sqlalchemy"):
        return exc
    return getattr(exc, "orig", None) or exc


def _patcher(record) -> None:
    """loguru patcher：注入 request_id，并在写盘前遮掉凭据形状。

    业务代码只需 `from loguru import logger; logger.info("...")`，
    无需手动 bind request_id。
    """
    record["extra"]["request_id"] = get_request_id() or "-"
    # 桥接记录由 InterceptHandler.bind() 带上标准库 logger 名；loguru 直发记录补个占位，
    # 否则文件格式里的 {extra[stdlib_logger]} 会在第一条业务日志上 KeyError。
    record["extra"].setdefault("stdlib_logger", "-")
    msg = record["message"]
    if isinstance(msg, str):
        record["message"] = redact_credentials(msg)



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
                "{name}:{function}:{line} | src={extra[stdlib_logger]} - "
                "{message}"
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

    # 第三方命名空间单独封顶 —— root.setLevel(0) + 文件 sink level="DEBUG" 的组合
    # 会让 sqlalchemy/COS SDK 的内部日志（含签名字符串与 SQL 绑定参数）原样落盘。
    _cap_noisy_loggers()


def get_logger():
    """获取已配置的 loguru logger。"""
    return logger


# ---- 关键失败的结构化日志出口（NFR-UX-05）----
# PRD 点名的四类关键失败（配置加载 / 停服 / 导入 / 自动审批）原先各处写法不一：
# 有的只有 `... 失败: {str(e)}` 一行（抽到的真实样本「加载 AI 配置失败: not all
# arguments converted during string formatting」就是这样 —— 没有异常类型、没有堆栈，
# 事后完全查不出抛点），有的干脆不落日志。统一走这里，日志里可按 `域=` 直接检索。
# T02847：启动期各步骤（迁移/seed/隧道自动启动等）失败同样只落了 `... 失败: {str(e)}`，
# 事后分不清是哪种异常，故新增 startup 域并入同一出口（可用 `域=startup` 一次捞全）。
KEY_FAILURE_DOMAINS = ("config_load", "shutdown", "import", "auto_approve", "startup")


def log_key_failure(
    *,
    domain: str,
    event: str,
    exc: BaseException | None = None,
    level: str = "error",
    with_traceback: bool = True,
    **fields,
) -> None:
    """写一条 `[关键失败] domain=… event=… k=v … exc_type=…` 的结构化日志。

    Args:
        domain: 关键失败域，取 KEY_FAILURE_DOMAINS 之一；写错不阻断业务，但会被断言测试挡住。
        event: 具体事件（中文可读，如「加载 AI 配置」）。
        exc: 触发的异常。给了就带上异常类型字段，并按需附堆栈。
        level: loguru 级别名；启动期可降级的失败用 warning，真正失败用 error。
        with_traceback: 只想要一行时（如逐行导入失败）可关掉，避免日志被堆栈淹没。
        fields: 定位用的字段，**只放 id / 表名 / 行号这类坐标**，不要放值或凭据
            （落盘前 redact_credentials 会兜一道，但兜底不是随便传的理由）。
    """
    parts = [f"[关键失败] domain={domain} event={event}"]
    for key in sorted(fields):
        parts.append(f"{key}={fields[key]}")
    logged_exc = unwrap_echo_exception(exc)
    if exc is not None:
        parts.append(f"exc_type={type(logged_exc).__name__}")
        parts.append(f"exc_msg={logged_exc}")
    message = " ".join(parts)
    # depth=1：不抬高栈帧的话，{name}:{function}:{line} 会全指向本模块的 log_key_failure，
    # 等于把刚修好的调用点归属又弄丢一次。
    # level 必须大写：loguru 校验的是 "WARNING"/"ERROR" 这类名字，传 "warning" 直接
    # ValueError（第一版就栽在这里，被自己的断言测试抓到）。
    log = logger.bind(domain=domain).opt(
        depth=1,
        exception=logged_exc if (logged_exc is not None and with_traceback) else None,
    )
    log.log(level.upper(), message)

