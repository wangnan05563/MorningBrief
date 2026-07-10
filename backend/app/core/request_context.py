"""请求上下文管理：全局流水号（request_id）生成与 ContextVar 传递。

request_id 贯穿一次 HTTP 请求的全部日志，便于全链路排障。
格式：req-{YYYYMMDDHHMMSSfff}-{6位hex}，示例：req-20260710150000537-a3b2c1
- 17 位毫秒级时间戳保证有序性
- 6 位 hex 随机数保证同毫秒唯一性（16^6≈1670万分之一碰撞）

通过 ContextVar 实现 asyncio 协程安全 + 线程安全的上下文传递，
业务代码无需手动传参，loguru patcher 自动从 ContextVar 读取并注入日志。
"""
import re
import secrets
import threading
from contextvars import ContextVar
from datetime import datetime, timezone

_REQUEST_ID_PREFIX = "req"
# 严格校验格式：req-17位数字-6位hex，防止客户端通过 X-Request-Id 头注入任意字符串
_REQUEST_ID_PATTERN = re.compile(r"^req-\d{17}-[0-9a-f]{6}$")

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_gen_lock = threading.Lock()


def generate_request_id() -> str:
    """生成新的全局流水号。threading.Lock 防止并发时间戳回拨。"""
    with _gen_lock:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")[:-3]
        rand = secrets.token_hex(3)
        return f"{_REQUEST_ID_PREFIX}-{ts}-{rand}"


def is_valid_request_id(rid: str) -> bool:
    """校验 request_id 格式，防止客户端注入任意字符串到日志。"""
    return bool(rid and _REQUEST_ID_PATTERN.match(rid))


def get_request_id() -> str | None:
    """读取当前上下文的流水号（asyncio 协程安全）。"""
    return _request_id_var.get()


def set_request_id(rid: str) -> None:
    """设置当前上下文的流水号。"""
    _request_id_var.set(rid)


def clear_request_id() -> None:
    """清除当前上下文的流水号，防止跨请求泄漏。"""
    _request_id_var.set(None)
