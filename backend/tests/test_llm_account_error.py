"""T00582 —— AI 服务账号级错误（余额不足/鉴权失败）识别与聚合单元测试。

背景：audiobook 频道（每日听书）连续多天因硅基流动
402 {'code':30001,'message':'Sorry, your account balance is insufficient'} 失败，
且被「逐条素材改写 × 3 次步骤重试」无意义放大（如 10 条素材 × 3 = 30 次无效调用）。

改进：
1. `is_account_level_error` / `account_error_hint`：识别账号级错误并给出运维指引；
2. `_build_aggregated_error`：账号级错误 → 返回 `LLMAccountError`（带 account_level 标记），
   workflow_scheduler 据此跳过步骤重试；
3. 聚合消息使用**动态**有效段数下限（原实现硬编码 MIN_VALID_SEGMENTS=3，素材稀缺时误导）。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_llm_account_error.py
"""
import pytest

from app.workflow.llm.rewriter import (
    LLMAccountError,
    LLMError,
    _build_aggregated_error,
    account_error_hint,
    is_account_level_error,
)


class FakeAPIStatusError(Exception):
    """模拟 openai SDK 的 APIStatusError（带 status_code 属性）。"""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _siliconflow_402() -> FakeAPIStatusError:
    """复刻 T00582 实测的硅基流动余额不足错误。"""
    return FakeAPIStatusError(
        "Error code: 402 - {'code': 30001, 'message': "
        "'Sorry, your account balance is insufficient', 'data': None}",
        402,
    )


def test_siliconflow_402_is_account_level():
    assert is_account_level_error(_siliconflow_402()) is True


def test_status_401_and_403_are_account_level():
    assert is_account_level_error(FakeAPIStatusError("Unauthorized", 401)) is True
    assert is_account_level_error(FakeAPIStatusError("Forbidden", 403)) is True


def test_message_marker_without_status_is_account_level():
    # 无 status_code 属性的异常，靠文本标记识别（兼容不同 SDK 封装）
    err = Exception(" Sorry, your account balance is insufficient ")
    assert is_account_level_error(err) is True


def test_generic_error_is_not_account_level():
    assert is_account_level_error(Exception("JSON 解析失败")) is False
    assert is_account_level_error(Exception("TimeoutError")) is False
    assert is_account_level_error(ValueError("敏感词命中")) is False


def test_hint_contains_actionable_guidance():
    hint = account_error_hint(_siliconflow_402())
    assert "余额不足" in hint
    assert "充值" in hint
    assert "重试无效" in hint


def test_aggregated_error_becomes_account_error_when_hint_present():
    details = [{"material_id": 1, "error_type": "APIStatusError", "error_message": "402"}]
    err = _build_aggregated_error(
        segments=[], failure_details=details, min_segments=2,
        account_hint="请充值或更换 API Key",
    )
    assert isinstance(err, LLMAccountError)
    assert err.account_level is True
    assert "充值" in str(err)
    # 动态下限参与消息（素材 2 条时有效下限为 2，而不是硬编码 3）
    assert "< 2" in str(err)
    assert err.failure_details == details


def test_aggregated_error_without_hint_stays_plain_llmerror():
    details = [
        {"material_id": 1, "error_type": "JSONDecodeError", "error_message": "bad json"},
        {"material_id": 2, "error_type": "TimeoutError", "error_message": "timeout"},
    ]
    err = _build_aggregated_error(segments=[], failure_details=details, min_segments=3)
    assert isinstance(err, LLMError)
    assert not isinstance(err, LLMAccountError)
    assert getattr(err, "account_level", False) is False


def test_aggregated_message_uses_dynamic_min_segments():
    # 回归：原实现对主导根因分支硬编码 MIN_VALID_SEGMENTS=3，
    # 素材稀缺（如 2 条）动态下调后消息仍显示 "< 3"，误导运维
    details = [{"material_id": i, "error_type": "APIStatusError", "error_message": "boom"}
               for i in range(2)]
    err = _build_aggregated_error(segments=[], failure_details=details, min_segments=2)
    assert "< 2" in str(err)


def test_aggregated_error_no_failure_details_provides_diagnosis():
    err = _build_aggregated_error(segments=[], failure_details=[], min_segments=3)
    assert isinstance(err, LLMError)
    assert not isinstance(err, LLMAccountError)
    assert err.failure_details and err.failure_details[0]["stage"] == "insufficient_segments"


@pytest.mark.parametrize("status", [400, 429, 500])
def test_other_http_status_not_account_level(status):
    assert is_account_level_error(FakeAPIStatusError("boom", status)) is False
