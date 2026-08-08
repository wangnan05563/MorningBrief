"""AI 预算控制模块测试。

覆盖：
- check_budget：正常放行 / 频率超限 / token 超限 / 费用超限
- record_call：计数更新 / 持久化
- get_today_summary：实时摘要正确性
- reset_budget：清空内存与文件
- 跨日 rollover：新日清空并回填
"""
import asyncio
import json
import time
from unittest.mock import patch

import pytest

from app.core import ai_budget


@pytest.fixture(autouse=True)
def _reset_ai_budget(tmp_path, monkeypatch):
    """每个测试前重置预算模块全局状态，保证隔离。

    把预算文件重定向到 tmp_path：safe-delete 沙箱会拦截 unlink，
    原本 reset_budget 的 file.unlink() 失效会导致 data/ai_budget.json
    残留，下一个用例 rollover 时 _load_today_from_file 回填陈旧记录，
    造成 total_calls 计数泄漏（期望 1 实得 2）。重定向到 tmp_path 后
    读写完全隔离，不再依赖 unlink 是否成功。
    """
    monkeypatch.setattr(
        ai_budget, "_budget_file_path", lambda: tmp_path / "ai_budget.json"
    )
    ai_budget.reset_budget()
    ai_budget._last_persist_date = ""  # 强制下次触发 rollover
    yield
    ai_budget.reset_budget()


def test_check_budget_initially_allowed():
    """初始状态下预算检查应放行。"""
    allowed, reason = ai_budget.check_budget()
    assert allowed is True
    assert reason == ""


def test_record_call_updates_summary():
    """记录调用后摘要应反映新计数。"""
    ai_budget.record_call(
        service_type="llm",
        model="qwen-max",
        input_tokens=100,
        output_tokens=50,
    )
    summary = ai_budget.get_today_summary()
    assert summary["total_calls"] == 1
    assert summary["total_tokens"] == 150
    assert summary["by_service"]["llm"] == 1


def test_record_call_tts_by_char_count():
    """TTS 按字符数记录，token 为 0。"""
    ai_budget.record_call(
        service_type="tts",
        model="xiaoyun",
        char_count=500,
    )
    summary = ai_budget.get_today_summary()
    assert summary["total_calls"] == 1
    assert summary["total_tokens"] == 0  # TTS 无 token
    assert summary["by_service"]["tts"] == 1


def test_check_budget_rate_limit(monkeypatch):
    """频率超限时应拒绝。"""
    # 临时把频率限制设为 2
    from app.config import get_settings
    monkeypatch.setattr(
        get_settings(), "AI_BUDGET_RATE_LIMIT_PER_MIN", 2
    )

    ai_budget.record_call("llm", "qwen-max", 10, 5)
    ai_budget.record_call("llm", "qwen-max", 10, 5)

    allowed, reason = ai_budget.check_budget()
    assert allowed is False
    assert "频率超限" in reason


def test_check_budget_token_limit(monkeypatch):
    """token 超限时应拒绝。"""
    from app.config import get_settings
    monkeypatch.setattr(
        get_settings(), "AI_BUDGET_DAILY_TOKEN_LIMIT", 100
    )

    ai_budget.record_call("llm", "qwen-max", input_tokens=60, output_tokens=50)

    allowed, reason = ai_budget.check_budget()
    assert allowed is False
    assert "Token 超限" in reason


def test_check_budget_cost_limit(monkeypatch):
    """费用超限时应拒绝。"""
    from app.config import get_settings
    monkeypatch.setattr(
        get_settings(), "AI_BUDGET_DAILY_COST_LIMIT_USD", 0.001
    )

    # qwen-max 费率较高，足以触发费用超限
    ai_budget.record_call(
        "llm", "qwen-max",
        input_tokens=1000, output_tokens=500,
    )

    allowed, reason = ai_budget.check_budget()
    assert allowed is False
    assert "费用超限" in reason


def test_persist_and_load_from_file(tmp_path, monkeypatch):
    """记录应持久化到文件，并能从文件回填。"""
    budget_file = tmp_path / "ai_budget.json"
    monkeypatch.setattr(ai_budget, "_budget_file_path", lambda: budget_file)

    ai_budget.record_call("llm", "qwen-max", 100, 50)
    # 批量持久化模式下，record_call 只加入缓冲区，需手动 flush 才写盘
    ai_budget._flush_pending()
    assert budget_file.exists()

    data = json.loads(budget_file.read_text(encoding="utf-8"))
    assert len(data["records"]) == 1
    assert data["records"][0]["input_tokens"] == 100


def test_batch_persist_threshold(tmp_path, monkeypatch):
    """缓冲区达到 _FLUSH_THRESHOLD 时应自动批量刷盘。"""
    budget_file = tmp_path / "ai_budget.json"
    monkeypatch.setattr(ai_budget, "_budget_file_path", lambda: budget_file)
    # 重置缓冲区状态，避免受前面测试影响
    ai_budget._pending_records.clear()
    # 设为当前时间避免时间间隔触发 flush（仅测试阈值触发逻辑）
    ai_budget._last_flush_time = time.time()

    # 写入 threshold - 1 条，不应触发刷盘
    threshold = ai_budget._FLUSH_THRESHOLD
    for _ in range(threshold - 1):
        ai_budget.record_call("llm", "qwen-max", 10, 5)
    assert not budget_file.exists()
    assert len(ai_budget._pending_records) == threshold - 1

    # 再写一条达到阈值，应自动刷盘
    ai_budget.record_call("llm", "qwen-max", 10, 5)
    assert budget_file.exists()
    data = json.loads(budget_file.read_text(encoding="utf-8"))
    assert len(data["records"]) == threshold
    assert len(ai_budget._pending_records) == 0


def test_reset_budget_clears_all():
    """reset_budget 应清空内存与文件。"""
    ai_budget.record_call("llm", "qwen-max", 100, 50)
    assert ai_budget.get_today_summary()["total_calls"] == 1

    ai_budget.reset_budget()

    summary = ai_budget.get_today_summary()
    assert summary["total_calls"] == 0
    assert summary["total_tokens"] == 0


def test_get_today_summary_includes_limits():
    """摘要应包含限额配置供前端展示进度条。"""
    summary = ai_budget.get_today_summary()
    assert "limits" in summary
    assert "daily_token_limit" in summary["limits"]
    assert "daily_cost_limit_usd" in summary["limits"]
    assert "rate_limit_per_min" in summary["limits"]


async def test_record_call_dispatches_db_usage(monkeypatch):
    """record_call 在事件循环中应把用量 fire-and-forget 写入 DB（验证 wiring）。

    此前 record_call 只更新内存预算 + JSON 文件，从不调用 record_usage，
    导致 ai_usage_log 永远为空、/usage 恒为 0。本次修复在 record_call 末尾
    派发后台任务调 AIConfigService.record_usage。该路径在测试环境默认禁用，
    本测试显式开启并断言 record_usage 被以正确参数调用，从而验证
    「统计逻辑 → 数据落库」这一此前缺失的链路真实接通。
    """
    from app.services.ai_config_service import AIConfigService

    captured = []

    async def _fake_record_usage(
        self,
        service_type: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        char_count: int = 0,
    ) -> None:
        captured.append(
            (service_type, model, input_tokens, output_tokens, char_count)
        )

    monkeypatch.setattr(AIConfigService, "record_usage", _fake_record_usage)
    # 测试环境默认禁用派发，显式开启以覆盖真实路径
    monkeypatch.setattr(ai_budget, "_DB_USAGE_DISPATCH_ENABLED", True)

    # record_call 是同步函数，但在运行中的事件循环内调用会派发后台任务
    ai_budget.record_call(
        "llm", "qwen-max", input_tokens=10, output_tokens=5
    )

    # 等待 fire-and-forget 后台任务被事件循环调度完成
    for _ in range(100):
        if captured:
            break
        await asyncio.sleep(0.01)

    assert captured, "record_call 未派发 DB 用量写入"
    assert captured[0] == ("llm", "qwen-max", 10, 5, 0)
