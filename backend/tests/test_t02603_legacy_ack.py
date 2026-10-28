"""T02603 裁决 3：存量「已开启但从未风险确认」的自动审批配置只点名，不改行为。

风险确认做在保存层，运行期 try_auto_approve 只拒绝「三条校验全关」；
升级前已 enabled=1 的配置 migration 后 risk_acknowledged=0，仍会照原规则
自动通过并发布。裁决为「维持现状 + 启动日志/配置页横幅点名」，因此这里锁：

1. 已开启且未确认 → 启动检查返回 1 并在日志里点名（带 updated_by/at）；
2. 已确认 / 已关闭 / 无配置 → 静默返回 0；
3. 只读：点名后配置行不得被顺手改写（尤其不能替管理员补确认）；
4. 接线：lifespan 里确实调用了这段检查（否则横幅之外的口径会悄悄消失）。
"""
import json
import logging
from pathlib import Path

import pytest

from app.models import AutoReviewConfig
from app.services.auto_review_service import log_legacy_unacknowledged

_LOGGER = "app.services.auto_review_service"


async def _config_row(db, **overrides):
    row = AutoReviewConfig(
        id=1,
        enabled=overrides.pop("enabled", True),
        require_content_safe=overrides.pop("require_content_safe", True),
        require_steps_first_success=overrides.pop("require_steps_first_success", True),
        keyword_whitelist=json.dumps(overrides.pop("keyword_whitelist", ["时政"])),
        **overrides,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.mark.asyncio
async def test_names_legacy_enabled_unacked(db_session, caplog):
    row = await _config_row(
        db_session, enabled=True, risk_acknowledged=False, updated_by="legacy_admin",
    )
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        named = await log_legacy_unacknowledged(db_session)

    assert named == 1
    text = caplog.text
    assert "从未做风险确认" in text
    assert "仍按现有校验自动通过并发布" in text
    assert "updated_by=legacy_admin" in text

    # 只读：不能替管理员补确认，也不能顺手关掉自动审批
    await db_session.refresh(row)
    assert row.enabled is True
    assert row.risk_acknowledged is False
    assert row.risk_acknowledged_by is None


@pytest.mark.asyncio
async def test_silent_when_acknowledged(db_session, caplog):
    await _config_row(
        db_session, enabled=True, risk_acknowledged=True, risk_acknowledged_by="admin",
    )
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        named = await log_legacy_unacknowledged(db_session)
    assert named == 0
    assert "从未做风险确认" not in caplog.text


@pytest.mark.asyncio
async def test_silent_when_disabled(db_session, caplog):
    await _config_row(db_session, enabled=False, risk_acknowledged=False)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        named = await log_legacy_unacknowledged(db_session)
    assert named == 0
    assert "从未做风险确认" not in caplog.text


@pytest.mark.asyncio
async def test_silent_when_config_missing(db_session, caplog):
    """首次启动还没 seed 配置：检查不能因此创建配置，也不能报错。"""
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        named = await log_legacy_unacknowledged(db_session)
    assert named == 0
    assert "从未做风险确认" not in caplog.text


def test_startup_wiring_calls_legacy_check():
    """接线锁：lifespan 里必须调用检查，否则只剩页面横幅、日志口径丢失。"""
    main_src = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    assert "from app.services.auto_review_service import log_legacy_unacknowledged" in main_src
    assert "await log_legacy_unacknowledged(session)" in main_src
    # 失败不得静默：必须走 log_key_failure 留痕
    assert "自动审批存量风险确认点名失败" in main_src
