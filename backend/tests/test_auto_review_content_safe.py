"""T00914 D11：内容安全校验跳过不得放行自动审批的回归测试。

背景：每日听书某期 content_security.skipped=true（微信 msgSecCheck 返回
errcode=40003 invalid openid），但检测结果 safe=True，旧逻辑把它当作
"检测通过"，可能绕过发布门禁。修复后 skipped 一律视为"未真实检测"→不安全。
"""
import pytest

from app.models import WorkflowStep, WorkflowStepName, WorkflowStepStatus
from app.services.auto_review_service import AutoReviewService


class _SessionCtx:
    """把测试 db_session 包装为 async context manager，模拟 AsyncSessionLocal()。"""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


async def _add_rewrite_step(db, workflow_id, content_security):
    """向指定工作流写入一条含 content_security 的 rewrite 步骤结果。"""
    db.add(WorkflowStep(
        workflow_id=workflow_id,
        step_name=WorkflowStepName.rewrite.value,
        status=WorkflowStepStatus.success.value,
        retry_count=0,
        result={"script_id": 1, "segments": 3, "content_security": content_security},
    ))
    await db.commit()


async def _svc(db, monkeypatch):
    """构造 AutoReviewService 并把其内部 AsyncSessionLocal 指向测试会话。"""
    import app.services.auto_review_service as mod
    monkeypatch.setattr(mod, "AsyncSessionLocal", lambda: _SessionCtx(db))
    return AutoReviewService(db)


@pytest.mark.asyncio
async def test_skipped_content_security_is_unsafe(db_session, monkeypatch):
    """D11 核心：skipped=true 时 safe=True 也不算检测通过，视为不安全。"""
    await _add_rewrite_step(db_session, "wf-skip", {"safe": True, "skipped": True})
    svc = await _svc(db_session, monkeypatch)
    ok, msg = await svc._check_content_safe("wf-skip")
    assert ok is False
    assert "未真实执行" in msg


@pytest.mark.asyncio
async def test_risky_content_security_is_unsafe(db_session, monkeypatch):
    await _add_rewrite_step(db_session, "wf-risky", {"safe": False, "skipped": False})
    svc = await _svc(db_session, monkeypatch)
    ok, _ = await svc._check_content_safe("wf-risky")
    assert ok is False


@pytest.mark.asyncio
async def test_clean_content_security_is_safe(db_session, monkeypatch):
    await _add_rewrite_step(db_session, "wf-clean", {"safe": True, "skipped": False})
    svc = await _svc(db_session, monkeypatch)
    ok, _ = await svc._check_content_safe("wf-clean")
    assert ok is True


@pytest.mark.asyncio
async def test_missing_step_result_is_unsafe(db_session, monkeypatch):
    """rewrite 步骤无结果（如重写失败未落库）时保守不通放。"""
    db_session.add(WorkflowStep(
        workflow_id="wf-nostep", step_name=WorkflowStepName.rewrite.value,
        status=WorkflowStepStatus.success.value, retry_count=0, result=None,
    ))
    await db_session.commit()
    svc = await _svc(db_session, monkeypatch)
    ok, msg = await svc._check_content_safe("wf-nostep")
    assert ok is False
    assert "无结果" in msg


@pytest.mark.asyncio
async def test_missing_content_security_field_is_unsafe(db_session, monkeypatch):
    """result 存在但无 content_security 字段：未执行检测，视为不安全。"""
    db_session.add(WorkflowStep(
        workflow_id="wf-nofield", step_name=WorkflowStepName.rewrite.value,
        status=WorkflowStepStatus.success.value, retry_count=0,
        result={"script_id": 1},
    ))
    await db_session.commit()
    svc = await _svc(db_session, monkeypatch)
    ok, msg = await svc._check_content_safe("wf-nofield")
    assert ok is False
    assert "未执行内容安全检测" in msg