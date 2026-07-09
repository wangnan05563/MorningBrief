"""时区工具：统一 UTC 时间获取，避免全项目 utcnow/now 混用。"""
from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """返回 naive UTC datetime（SQLite DATETIME 列无时区，需存 naive）。

    替代已弃用的 datetime.utcnow()，保持返回值类型一致（naive）。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
