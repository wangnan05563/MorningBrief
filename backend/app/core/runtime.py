"""进程运行时元信息：给「自进程启动累计」类指标提供可展示的累计起点。

背景（T02508 / FR-UX-503）：LLM 字数重试指标、RSS 源连续失败次数这类计数
保存在模块级字典里，进程重启即清零。页面上只显示数字本身时，运维无法判断
「触发率 12%」是今天一天的还是上个月攒下来的，也无法在数字异常时确认
是不是刚重启过。因此接口必须把累计口径（起点时间 + 进程标识）一起回传，
前端才能如实写出「累计自 x 时间，重启清零」。

约定：
- 时间用 `localnow_naive()`（本地 naive，与全项目时间字段口径一致，见 core/timeutil.py），
  序列化成 `YYYY-MM-DDTHH:mm:ss`，不带时区后缀，前端按本地时区显示。
- `pid` 用于区分「多进程/多 worker 各自一份累计值」的场景：同机多个 worker 的
  计数互不相通，只看时间无法判断自己读到的是哪个进程。
- 本模块只做"读"，不做健康检查、不做持久化——重启清零是特性，不是缺陷。
"""
import os
from datetime import datetime

from app.core.timeutil import localnow_naive

# 进程启动时刻：本模块首次被 import 时取值。
# FastAPI 应用入口在启动阶段即 import 路由与服务链，因此这里与 lifespan 启动时间
# 一致到秒级；比在 lifespan 里赋值更可靠——单测/脚本直接调用 service 时同样有值。
PROCESS_STARTED_AT: datetime = localnow_naive()
PROCESS_PID: int = os.getpid()


def runtime_fields() -> dict:
    """返回累计口径字段，供「自进程启动累计」类接口合并进 data 里。

    Returns:
        {"started_at": "YYYY-MM-DDTHH:mm:ss", "pid": <int>}
        调用方把它与原指标 dict 合并即可；前端缺字段时必须退化为「起点未知」，
        不允许拿当前时间冒充累计起点。
    """
    return {
        "started_at": PROCESS_STARTED_AT.isoformat(timespec="seconds"),
        "pid": PROCESS_PID,
    }
