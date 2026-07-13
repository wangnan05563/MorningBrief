"""时区工具：统一本地时间获取。

项目为单机部署（香港时区 UTC+8，无夏令时），所有时间字段存储为本地 naive datetime。
前端 .isoformat() 输出无时区后缀，浏览器按本地时区解析即可正确显示。
"""
from datetime import datetime


def utcnow_naive() -> datetime:
    """返回本地 naive datetime（香港时区 UTC+8）。

    历史原因函数名保留 utcnow，但实际返回本地时间。
    SQLite DATETIME 列无时区，存 naive 本地时间与前端显示一致。
    """
    return datetime.now()
