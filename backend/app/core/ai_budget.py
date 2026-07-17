"""AI 用量实时预算控制（对标 17_xianyu ai_usage.py）。

与 ai_config_service.AIConfigService 的区别：
- AIConfigService.record_usage：调用成功后写 DB（事后统计）
- ai_budget：调用前检查预算（事前拦截），调用后更新内存计数（事中累积）

三重预算控制：
1. 每日 token 上限（默认 50 万）
2. 每日费用上限（默认 $5）
3. 每分钟频率上限（默认 60 次，滑动窗口，按 service_type 分桶）

频率分桶：LLM 与 TTS 各自维护独立的滑动窗口，避免 TTS 密集调用挤占
LLM 配额导致改写失败。token/费用上限仍为全局共享（每日总预算）。

持久化：批量缓冲写盘。record_call 时只追加到内存缓冲区，达到阈值
（_FLUSH_THRESHOLD 条）或距上次刷盘超过 _FLUSH_INTERVAL_SEC 秒时才写文件，
避免高频 TTS（60 次/分钟）每秒触发全量 JSON 重写。服务退出/跨日/reset 时
强制 flush，确保不丢数据。服务重启后从文件回填今日记录，避免预算被绕过。

线程安全：所有可变状态用 threading.Lock 保护，因 LLM/TTS 调用在 asyncio
事件循环中执行，但记录写入是同步快速操作，用 threading.Lock 足够且避免
asyncio.Lock 的 await 开销。临界区内无 await/IO 阻塞，协程不会切换，因此
threading.Lock 在单线程事件循环中不会真正阻塞，仅起内存屏障作用。
"""
from __future__ import annotations

import atexit
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from app.config import get_settings


@dataclass
class _UsageRecord:
    """单次调用内存记录（与持久化文件结构一致）。"""
    timestamp: float
    service_type: str  # "llm" | "tts"
    model: str
    input_tokens: int
    output_tokens: int
    char_count: int
    cost_usd: float


@dataclass
class _DailySummary:
    """每日汇总（实时维护，避免每次 check 都遍历 records）。"""
    total_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    by_service: dict[str, int] = field(default_factory=dict)


# 批量持久化参数：高频 TTS（60 次/分钟）下若每条都全量重写 JSON 文件，
# 文件增长后单次 IO 耗时上升。缓冲 10 条或 30 秒后批量刷盘，可将磁盘
# 写次数降低一个数量级，同时保证崩溃时最多丢失 30 秒数据（预算软限制可接受）
_FLUSH_THRESHOLD = 10
_FLUSH_INTERVAL_SEC = 30

# 全局状态（模块级单例，与 cache.manager 一致的模式）
_lock = threading.Lock()
_today_records: list[_UsageRecord] = []
# 频率滑动窗口按 service_type 分桶：{"llm": [t1, t2], "tts": [t3]}
# 避免 TTS 密集调用挤占 LLM 频率配额导致改写失败
_minute_timestamps_by_service: dict[str, list[float]] = {}
_daily_summary = _DailySummary()
_last_persist_date: str = ""  # 上次持久化的日期，跨日时清空内存
# 持久化缓冲区与上次刷盘时间（必须在 _lock 内访问，避免并发竞态）
_pending_records: list[_UsageRecord] = []
_last_flush_time: float = 0.0


def _today_key() -> str:
    """本地日期键（香港时区 UTC+8）。

    与项目其他模块对齐：rewriter/crawler/scheduler 均按本地日期筛选，
    ai_budget 也必须用本地日期，否则本地跨日（UTC 仍为前一日）时
    预算会错误累加两天的用量，导致 token 上限被提前触发。
    """
    from datetime import datetime as _dt
    return _dt.now().strftime("%Y-%m-%d")


def _budget_file_path() -> Path:
    """预算文件路径（走 paths.py 解析打包态/开发态）。"""
    try:
        from app.paths import resolve_data_dir
        data_dir = resolve_data_dir()
    except Exception:
        data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "ai_budget.json"


def _estimate_cost(
    service_type: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    char_count: int,
) -> float:
    """估算单次调用费用（USD）。

    复用 ai_config_service 的定价表，避免两处维护。
    """
    from app.services.ai_config_service import _estimate_cost as _cfg_estimate
    return _cfg_estimate(
        service_type, model, input_tokens, output_tokens, char_count
    )


def check_budget(service_type: str | None = None) -> tuple[bool, str]:
    """检查是否允许发起下一次 AI 调用。

    Args:
        service_type: "llm" / "tts" 等，指定时只检查该 service 的频率桶；
            None 时检查所有桶（任一超限即拒绝，用于通用检查/向后兼容）。

    Returns:
        (允许, 原因说明)。允许时原因为空字符串。

    在 rewriter._call_llm / synthesizer.synthesize_segment 调用前先检查。
    频率按 service_type 分桶，token/费用为全局共享每日预算。
    """
    settings = get_settings()
    with _lock:
        _rollover_if_new_day()

        # 频率：滑动窗口最近 1 分钟调用次数，按 service_type 分桶
        cutoff = time.time() - 60
        # 决定要检查哪些桶：指定 service_type 只查该桶，None 查所有桶
        buckets_to_check = (
            [service_type] if service_type
            else list(_minute_timestamps_by_service.keys())
        )
        for svc in buckets_to_check:
            ts_list = _minute_timestamps_by_service.get(svc, [])
            # 原地清理过期时间戳，避免窗口堆积
            ts_list[:] = [t for t in ts_list if t > cutoff]
            if len(ts_list) >= settings.AI_BUDGET_RATE_LIMIT_PER_MIN:
                return False, (
                    f"频率超限：{svc} 每分钟最多 "
                    f"{settings.AI_BUDGET_RATE_LIMIT_PER_MIN} 次"
                )

        # 每日 token 上限（全局共享，不分桶）
        if _daily_summary.total_tokens >= settings.AI_BUDGET_DAILY_TOKEN_LIMIT:
            return False, (
                f"Token 超限：今日已用 {_daily_summary.total_tokens:,}，"
                f"上限 {settings.AI_BUDGET_DAILY_TOKEN_LIMIT:,}"
            )

        # 每日费用上限（全局共享，不分桶）
        if _daily_summary.total_cost_usd >= settings.AI_BUDGET_DAILY_COST_LIMIT_USD:
            return False, (
                f"费用超限：今日已用 ${_daily_summary.total_cost_usd:.2f}，"
                f"上限 ${settings.AI_BUDGET_DAILY_COST_LIMIT_USD:.2f}"
            )

    return True, ""


def record_call(
    service_type: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    char_count: int = 0,
) -> dict[str, Any]:
    """记录一次 AI 调用并更新预算计数。

    在 LLM/TTS 调用成功后调用（与 ai_config_service.record_usage 并存：
    后者写 DB 用于历史查询，本函数更新内存预算用于实时拦截）。

    Returns:
        用量摘要 dict，便于调用方日志记录
    """
    cost = _estimate_cost(
        service_type, model, input_tokens, output_tokens, char_count
    )
    record = _UsageRecord(
        timestamp=time.time(),
        service_type=service_type,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        char_count=char_count,
        cost_usd=cost,
    )

    # 批量持久化：锁内只做内存操作 + 判断是否需要刷盘，IO 放锁外避免阻塞
    global _last_flush_time
    flush_batch: list[_UsageRecord] | None = None
    with _lock:
        _rollover_if_new_day()
        _today_records.append(record)
        # 按 service_type 分桶记录频率时间戳，LLM/TTS 独立限流互不干扰
        _minute_timestamps_by_service.setdefault(service_type, []).append(time.time())
        _daily_summary.total_calls += 1
        _daily_summary.total_tokens += input_tokens + output_tokens
        _daily_summary.total_cost_usd += cost
        _daily_summary.by_service[service_type] = (
            _daily_summary.by_service.get(service_type, 0) + 1
        )

        # 加入缓冲区，达到阈值或间隔后 swap 出待写批次
        _pending_records.append(record)
        now = time.time()
        if (len(_pending_records) >= _FLUSH_THRESHOLD
                or (now - _last_flush_time) >= _FLUSH_INTERVAL_SEC):
            flush_batch = _pending_records.copy()
            _pending_records.clear()
            _last_flush_time = now

    # 锁外批量写盘，避免磁盘 IO 阻塞其他协程的预算检查
    if flush_batch:
        _persist_records(flush_batch)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
        "service_type": service_type,
        "model": model,
    }


def get_today_summary() -> dict[str, Any]:
    """获取今日实时预算摘要（供前端用量面板展示）。"""
    with _lock:
        _rollover_if_new_day()
        settings = get_settings()
        return {
            "date": _today_key(),
            "total_calls": _daily_summary.total_calls,
            "total_tokens": _daily_summary.total_tokens,
            "total_cost_usd": round(_daily_summary.total_cost_usd, 6),
            "by_service": dict(_daily_summary.by_service),
            "limits": {
                "daily_token_limit": settings.AI_BUDGET_DAILY_TOKEN_LIMIT,
                "daily_cost_limit_usd": settings.AI_BUDGET_DAILY_COST_LIMIT_USD,
                "rate_limit_per_min": settings.AI_BUDGET_RATE_LIMIT_PER_MIN,
            },
        }


def _rollover_if_new_day() -> None:
    """跨日清空内存计数并从持久化文件回填今日记录。

    必须在 _lock 内调用。设计原因：服务可能跨日运行，
    若不清空 _today_records，昨日数据会被错误计入今日预算。
    """
    global _last_persist_date
    today = _today_key()
    if _last_persist_date == today:
        return

    # 跨日：清空内存，从文件回填今日记录
    _today_records.clear()
    _minute_timestamps_by_service.clear()
    # 原地重置属性而非重新赋值，避免 global 声明遗漏
    _daily_summary.total_calls = 0
    _daily_summary.total_tokens = 0
    _daily_summary.total_cost_usd = 0.0
    _daily_summary.by_service.clear()
    _last_persist_date = today

    # 从持久化文件回填今日记录（服务重启场景）
    _load_today_from_file(today)


def _load_today_from_file(today: str) -> None:
    """从 JSON 文件回填今日记录到内存。

    服务重启后 _today_records 为空，若不回填则预算计数从 0 开始，
    可被绕过（重启服务即可重置预算）。

    频率桶仅回填最近 60s 内的记录（滑动窗口语义），更早的记录
    对频率限流无意义且会占用内存。
    """
    file_path = _budget_file_path()
    if not file_path.exists():
        return
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    # 频率窗口截止线：只回填最近 60s 内的记录
    rate_cutoff = time.time() - 60

    for entry in data.get("records", []):
        try:
            # 用本地时区解析 timestamp，与 _today_key 保持一致
            # UTC 解析会导致本地跨日记录被错误归入前一日
            entry_date = datetime.fromtimestamp(
                entry["timestamp"]
            ).strftime("%Y-%m-%d")
        except (KeyError, ValueError, OSError):
            continue
        if entry_date != today:
            continue
        record = _UsageRecord(
            timestamp=entry["timestamp"],
            service_type=entry.get("service_type", ""),
            model=entry.get("model", ""),
            input_tokens=entry.get("input_tokens", 0),
            output_tokens=entry.get("output_tokens", 0),
            char_count=entry.get("char_count", 0),
            cost_usd=entry.get("cost_usd", 0.0),
        )
        _today_records.append(record)
        _daily_summary.total_calls += 1
        _daily_summary.total_tokens += record.input_tokens + record.output_tokens
        _daily_summary.total_cost_usd += record.cost_usd
        _daily_summary.by_service[record.service_type] = (
            _daily_summary.by_service.get(record.service_type, 0) + 1
        )
        # 频率桶仅回填滑动窗口内的记录，避免重启后频率限流失效
        if record.timestamp > rate_cutoff and record.service_type:
            _minute_timestamps_by_service.setdefault(
                record.service_type, []
            ).append(record.timestamp)


def _persist_records(records: list[_UsageRecord]) -> None:
    """批量将记录追加到 JSON 文件。

    保留最近 30 天数据（按条数估算：每天最多 1000 条，30 天 3 万条）。
    写盘失败时把记录回填到 pending 缓冲区，下次刷盘时重试，避免数据丢失。
    """
    if not records:
        return
    file_path = _budget_file_path()
    try:
        data: dict[str, Any] = {"records": []}
        if file_path.exists():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        records_list = data.setdefault("records", [])
        for r in records:
            records_list.append({
                "timestamp": r.timestamp,
                "service_type": r.service_type,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "char_count": r.char_count,
                "cost_usd": r.cost_usd,
            })

        # 保留最近 30 天数据（从头删除，避免 list[-N:] 创建大副本）
        max_records = 30 * 1000
        if len(records_list) > max_records:
            del records_list[: len(records_list) - max_records]

        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning("AI 预算记录批量持久化失败（已回填缓冲区待重试）: %s", e)
        # 写盘失败：把批次回填到 pending，下次 record_call 或 atexit 时重试
        with _lock:
            _pending_records[:0] = records


def _flush_pending() -> None:
    """强制刷盘所有 pending 记录（用于跨日/reset/atexit）。

    与 record_call 内的批量触发不同，本函数无条件 flush 全部 pending，
    确保关键节点（跨日清零、手动重置、进程退出）不丢数据。
    """
    with _lock:
        if not _pending_records:
            return
        batch = _pending_records.copy()
        _pending_records.clear()
        _last_flush_time = time.time()
    # 锁外写盘
    _persist_records(batch)


# 进程退出时强制 flush，避免缓冲区数据丢失
atexit.register(_flush_pending)


def reset_budget() -> None:
    """手动重置预算计数（运维应急用，如预算误判需要解锁）。

    清空内存计数、未刷盘的缓冲区与持久化文件。
    """
    with _lock:
        _today_records.clear()
        _minute_timestamps_by_service.clear()
        _daily_summary.total_calls = 0
        _daily_summary.total_tokens = 0
        _daily_summary.total_cost_usd = 0.0
        _daily_summary.by_service.clear()
        # 同步清空缓冲区：reset 语义是清除所有预算数据，pending 也属于待清除范围
        _pending_records.clear()
        _last_flush_time = 0.0

    file_path = _budget_file_path()
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass
    logger.info("AI 预算计数已重置")
