"""时区工具：统一本地时间获取。

项目为单机部署（香港时区 UTC+8，无夏令时），所有时间字段存储为本地 naive datetime。
前端 .isoformat() 输出无时区后缀，浏览器按本地时区解析即可正确显示。

新代码一律使用 localnow_naive()（名称如实表达"本地"语义）。
"""
from datetime import datetime


def localnow_naive() -> datetime:
    """返回本地 naive datetime（香港时区 UTC+8，无夏令时）。

    项目为单机部署，所有时间字段统一存储为本地 naive datetime。
    SQLite DATETIME 列无时区，存本地 naive 时间与前端按本地时区显示一致。
    """
    return datetime.now()
