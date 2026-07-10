"""AI 用量实时预算控制（对标 17_xianyu ai_usage.py）。

与 ai_config_service.AIConfigService 的区别：
- AIConfigService.record_usage：调用成功后写 DB（事后统计）
- ai_budget：调用前检查预算（事前拦截），调用后更新内存计数（事中累积）

三重预算控制：
1. 每日 token 上限（默认 50 万）
2. 每日费用上限（默认 $5）
3. 每分钟频率上限（默认 20 次，滑动窗口）

持久化：每条记录追加到 JSON 文件，服务重启后从文件回填今日记录，
避免刷新页面/重启服务后预算计数归零被绕过。

线程安全：所有可变状态用 threading.Lock 保护，因 LLM/TTS 调用在 asyncio
事件循环中执行，但记录写入是同步快速操作，用 threading.Lock 足够且避免
asyncio.Lock 的 await 开销。
"""
from __future__ import annotations

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


# 全局状态（模块级单例，与 cache.manager 一致的模式）
_lock = threading.Lock()
_today_records: list[_UsageRecord] = []
_minute_timestamps: list[float] = []  # 滑动窗口：最近 1 分钟的调用时间戳
_daily_summary = _DailySummary()
_last_persist_date: str = ""  # 上次持久化的日期，跨日时清空内存


def _today_key() -> str:
    """UTC 日期键，与 17_xianyu 对齐避免时区漂移。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


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


def check_budget() -> tuple[bool, str]:
    """检查是否允许发起下一次 AI 调用。

    Returns:
        (允许, 原因说明)。允许时原因为空字符串。

    在 rewriter._call_llm / synthesizer.synthesize_segment 调用前先检查。
    """
    settings = get_settings()
    with _lock:
        _rollover_if_new_day()

        # 频率：滑动窗口最近 1 分钟调用次数
        cutoff = time.time() - 60
        _minute_timestamps[:] = [t for t in _minute_timestamps if t > cutoff]
        if len(_minute_timestamps) >= settings.AI_BUDGET_RATE_LIMIT_PER_MIN:
            return False, (
                f"频率超限：每分钟最多 "
                f"{settings.AI_BUDGET_RATE_LIMIT_PER_MIN} 次"
            )

        # 每日 token 上限
        if _daily_summary.total_tokens >= settings.AI_BUDGET_DAILY_TOKEN_LIMIT:
            return False, (
                f"Token 超限：今日已用 {_daily_summary.total_tokens:,}，"
                f"上限 {settings.AI_BUDGET_DAILY_TOKEN_LIMIT:,}"
            )

        # 每日费用上限
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

    with _lock:
        _rollover_if_new_day()
        _today_records.append(record)
        _minute_timestamps.append(time.time())
        _daily_summary.total_calls += 1
        _daily_summary.total_tokens += input_tokens + output_tokens
        _daily_summary.total_cost_usd += cost
        _daily_summary.by_service[service_type] = (
            _daily_summary.by_service.get(service_type, 0) + 1
        )

    # 持久化（同步写，文件小且调用频率受限流控制）
    _persist_record(record)

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
    _minute_timestamps.clear()
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
    """
    file_path = _budget_file_path()
    if not file_path.exists():
        return
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    for entry in data.get("records", []):
        try:
            entry_date = datetime.fromtimestamp(
                entry["timestamp"], tz=timezone.utc
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


def _persist_record(record: _UsageRecord) -> None:
    """将单条记录追加到 JSON 文件（对标 17_xianyu _persist_record）。

    保留最近 30 天数据（按条数估算：每天最多 1000 条，30 天 3 万条）。
    """
    file_path = _budget_file_path()
    try:
        data: dict[str, Any] = {"records": []}
        if file_path.exists():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        data.setdefault("records", []).append({
            "timestamp": record.timestamp,
            "service_type": record.service_type,
            "model": record.model,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "char_count": record.char_count,
            "cost_usd": record.cost_usd,
        })

        # 保留最近 30 天数据
        max_records = 30 * 1000
        if len(data["records"]) > max_records:
            data["records"] = data["records"][-max_records:]

        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning("AI 预算记录持久化失败: %s", e)


def reset_budget() -> None:
    """手动重置预算计数（运维应急用，如预算误判需要解锁）。

    清空内存计数与持久化文件中的今日记录。
    """
    with _lock:
        _today_records.clear()
        _minute_timestamps.clear()
        _daily_summary.total_calls = 0
        _daily_summary.total_tokens = 0
        _daily_summary.total_cost_usd = 0.0
        _daily_summary.by_service.clear()

    file_path = _budget_file_path()
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass
    logger.info("AI 预算计数已重置")
