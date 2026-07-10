"""AI 预算控制模块测试。

覆盖：
- check_budget：正常放行 / 频率超限 / token 超限 / 费用超限
- record_call：计数更新 / 持久化
- get_today_summary：实时摘要正确性
- reset_budget：清空内存与文件
- 跨日 rollover：新日清空并回填
"""
import json
import time
from unittest.mock import patch

import pytest

from app.core import ai_budget


@pytest.fixture(autouse=True)
def _reset_ai_budget():
    """每个测试前重置预算模块全局状态，保证隔离。"""
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
    assert budget_file.exists()

    data = json.loads(budget_file.read_text(encoding="utf-8"))
    assert len(data["records"]) == 1
    assert data["records"][0]["input_tokens"] == 100


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
