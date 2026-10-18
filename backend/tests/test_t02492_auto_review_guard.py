"""T02492（FR-UX-204）自动审批护栏的断言。

改造前的缺陷链（G13）：配置为「开启 + 两条开关关闭 + 关键词白名单为空」时，
三条校验一条都没跑，matched_rules 与 fail_reasons 双双为空，
旧逻辑把它当作「全部命中」→ 任意稿件零检查自动发布。

本文件锁住四件事：
1. 配置层：三条全关不许开启；开启必须带风险确认；
2. 风险确认生命周期：勾选记录确认人/时间，关闭即清空，跳过项变化必须重新确认；
3. 运行期护栏：库里遗留的全关配置，代码层直接拒绝自动通过并转人工；
4. 留痕：每次自动通过都同时记下「命中」与「显式跳过」的校验。
"""
import json
from datetime import date

import pytest
from sqlalchemy import select

from app.core.exceptions import BizError
from app.models import (
    AuditLog, AutoReviewConfig, AutoReviewStat, Review, Script, Workflow,
    WorkflowStep, WorkflowStepName, WorkflowStepStatus,
)
from app.models.workflow import WorkflowSource, WorkflowStatus
from app.services.auto_review_service import AutoReviewService


class _SessionCtx:
    """把测试 db_session 包装为 async context manager，模拟 AsyncSessionLocal()。"""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


async def _svc(db, monkeypatch):
    """构造 AutoReviewService 并把其内部 AsyncSessionLocal 指向测试会话。"""
    import app.services.auto_review_service as mod
    monkeypatch.setattr(mod, "AsyncSessionLocal", lambda: _SessionCtx(db))
    return AutoReviewService(db)


async def _legacy_config(db, **overrides):
    """绕过 update_config 直接落一行配置（用于构造改造前遗留的危险组合）。"""
    row = AutoReviewConfig(
        id=1,
        enabled=overrides.pop("enabled", False),
        require_content_safe=overrides.pop("require_content_safe", True),
        require_steps_first_success=overrides.pop("require_steps_first_success", True),
        keyword_whitelist=json.dumps(overrides.pop("keyword_whitelist", [])),
        **overrides,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _seed_workflow(db, wid):
    """构造 工作流 → 稿件 → 待审 Review，并给 rewrite 步骤写入安全结果。"""
    db.add(Workflow(
        id=wid, episode_date=date.today(),
        source=WorkflowSource.cron, status=WorkflowStatus.success, started_at=None,
    ))
    sc = Script(
        workflow_id=wid, episode_date=date.today(),
        full_text="测试稿件正文", segments=[{"seq": 1, "title": "段1", "content": "内容"}],
    )
    db.add(sc)
    await db.flush()
    rv = Review(
        workflow_id=wid, episode_date=date.today(),
        script_id=sc.id, audio_url="http://example.com/a.mp3", status="pending",
    )
    db.add(rv)
    db.add(WorkflowStep(
        workflow_id=wid, step_name=WorkflowStepName.rewrite.value,
        status=WorkflowStepStatus.success.value, retry_count=0,
        result={"script_id": sc.id, "content_security": {"safe": True, "skipped": False}},
    ))
    await db.commit()
    await db.refresh(rv)
    return rv


async def _stats(db, workflow_id):
    rows = (await db.execute(
        select(AutoReviewStat).where(AutoReviewStat.workflow_id == workflow_id)
        .order_by(AutoReviewStat.id)
    )).scalars().all()
    return rows


# ===== 纯函数口径 =====

def test_split_rules_all_on_has_nothing_skipped():
    enforced, skipped = AutoReviewService.split_rules(True, True, ["a"])
    assert enforced == ["content_safe", "steps_first_success", "keyword_whitelist"]
    assert skipped == []


def test_split_rules_all_off_leaves_nothing_enforced():
    """G13 的危险组合：三条全关 → 生效校验为空，护栏据此拦截。"""
    enforced, skipped = AutoReviewService.split_rules(False, False, [])
    assert enforced == []
    assert skipped == ["content_safe", "steps_first_success", "keyword_whitelist"]


def test_parse_keywords_tolerates_broken_json():
    assert AutoReviewService.parse_keywords("not json") == []
    assert AutoReviewService.parse_keywords(None) == []
    assert AutoReviewService.parse_keywords('{"a": 1}') == []
    assert AutoReviewService.parse_keywords('["安全"]') == ["安全"]


# ===== 配置层护栏 =====

@pytest.mark.asyncio
async def test_update_config_blocks_all_rules_off(db_session, monkeypatch):
    svc = await _svc(db_session, monkeypatch)
    with pytest.raises(BizError) as exc:
        await svc.update_config(
            enabled=True, require_content_safe=False,
            require_steps_first_success=False, keyword_whitelist=[],
            operator="admin", risk_acknowledged=True,
        )
    assert "不能开启自动审批" in exc.value.message
    config = await svc.get_config()
    assert config.enabled is False


@pytest.mark.asyncio
async def test_update_config_requires_risk_ack(db_session, monkeypatch):
    svc = await _svc(db_session, monkeypatch)
    with pytest.raises(BizError) as exc:
        await svc.update_config(
            enabled=True, require_content_safe=True,
            require_steps_first_success=False, keyword_whitelist=[],
            operator="admin", risk_acknowledged=False,
        )
    msg = exc.value.message
    assert "风险确认" in msg
    # 跳过的校验项要写进提示，管理员得知道这次放行少查了什么
    assert "steps_first_success" in msg and "keyword_whitelist" in msg


@pytest.mark.asyncio
async def test_update_config_records_ack_and_skipped_rules(db_session, monkeypatch):
    svc = await _svc(db_session, monkeypatch)
    config = await svc.update_config(
        enabled=True, require_content_safe=True,
        require_steps_first_success=False, keyword_whitelist=["时政"],
        operator="admin", risk_acknowledged=True,
    )
    assert config.risk_acknowledged is True
    assert config.risk_acknowledged_by == "admin"
    assert config.risk_acknowledged_at is not None

    audit = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "update_auto_review_config")
        .order_by(AuditLog.id.desc())
    )).scalars().first()
    detail = json.loads(audit.detail)
    assert detail["skipped_rules"] == ["steps_first_success"]
    assert detail["enforced_rules"] == ["content_safe", "keyword_whitelist"]
    assert detail["risk_acknowledged"] is True


@pytest.mark.asyncio
async def test_risk_ack_carried_only_while_skipped_rules_unchanged(db_session, monkeypatch):
    """日常改关键词不必反复勾选；一旦跳过项变化（风险面变了）必须重新确认。"""
    svc = await _svc(db_session, monkeypatch)
    await svc.update_config(
        enabled=True, require_content_safe=True, require_steps_first_success=True,
        keyword_whitelist=[], operator="admin", risk_acknowledged=True,
    )
    # 跳过项未变（仍跳过 keyword_whitelist），只是加关键词 → 沿用旧确认
    config = await svc.update_config(
        enabled=True, require_content_safe=True, require_steps_first_success=True,
        keyword_whitelist=["时政"], operator="admin", risk_acknowledged=False,
    )
    assert config.risk_acknowledged is True

    # 再关掉内容安全：跳过项增加 → 必须重新确认
    with pytest.raises(BizError) as exc:
        await svc.update_config(
            enabled=True, require_content_safe=False, require_steps_first_success=True,
            keyword_whitelist=["时政"], operator="admin", risk_acknowledged=False,
        )
    assert "风险确认" in exc.value.message


@pytest.mark.asyncio
async def test_disabling_auto_review_clears_ack(db_session, monkeypatch):
    """关闭总开关即撤销确认状态：下次开启要重新勾选，不会沿用旧确认。"""
    svc = await _svc(db_session, monkeypatch)
    await svc.update_config(
        enabled=True, require_content_safe=True, require_steps_first_success=True,
        keyword_whitelist=["时政"], operator="admin", risk_acknowledged=True,
    )
    config = await svc.update_config(
        enabled=False, require_content_safe=True, require_steps_first_success=True,
        keyword_whitelist=["时政"], operator="admin", risk_acknowledged=False,
    )
    assert config.risk_acknowledged is False
    assert config.risk_acknowledged_by is None

    with pytest.raises(BizError):
        await svc.update_config(
            enabled=True, require_content_safe=True, require_steps_first_success=True,
            keyword_whitelist=["时政"], operator="admin", risk_acknowledged=False,
        )


# ===== 运行期护栏与留痕 =====

@pytest.mark.asyncio
async def test_runtime_guard_refuses_legacy_all_off_config(db_session, monkeypatch):
    """遗留的「开启 + 三条全关」配置在运行期被拦下，改前会零检查放行。"""
    await _legacy_config(
        db_session, enabled=True, require_content_safe=False,
        require_steps_first_success=False, keyword_whitelist=[],
    )
    rv = await _seed_workflow(db_session, "g2-wf-guard")
    svc = await _svc(db_session, monkeypatch)

    result = await svc.try_auto_approve(
        workflow_id="g2-wf-guard", review_id=rv.id,
        review_created_at=rv.created_at,
    )
    assert result["auto_approved"] is False
    assert "无生效校验规则" in result["reason"]

    review = (await db_session.execute(
        select(Review).where(Review.id == rv.id)
    )).scalar_one()
    assert review.status == "pending"

    stats = await _stats(db_session, "g2-wf-guard")
    assert len(stats) == 1
    assert stats[0].success is False
    assert json.loads(stats[0].trigger_reason)["guard"] == "no_enforced_rule"


@pytest.mark.asyncio
async def test_auto_approve_records_matched_and_skipped(db_session, monkeypatch):
    """跳过校验本身合法，但每次自动通过都要把「命中了什么 / 跳过了什么」留痕。"""
    from app.services.content_service import ContentService

    async def _fake_publish(self, workflow_id, review_id):
        return 8801

    monkeypatch.setattr(ContentService, "publish_episode", _fake_publish)

    await _legacy_config(
        db_session, enabled=True, require_content_safe=True,
        require_steps_first_success=False, keyword_whitelist=[],
    )
    rv = await _seed_workflow(db_session, "g2-wf-pass")
    svc = await _svc(db_session, monkeypatch)

    result = await svc.try_auto_approve(
        workflow_id="g2-wf-pass", review_id=rv.id, review_created_at=rv.created_at,
    )
    assert result["auto_approved"] is True

    review = (await db_session.execute(
        select(Review).where(Review.id == rv.id)
    )).scalar_one()
    reason = json.loads(review.auto_trigger_reason)
    assert reason["matched_rules"] == ["content_safe"]
    assert reason["skipped_rules"] == ["steps_first_success", "keyword_whitelist"]

    stats = await _stats(db_session, "g2-wf-pass")
    assert stats[-1].success is True
    assert json.loads(stats[-1].trigger_reason)["skipped_rules"] == [
        "steps_first_success", "keyword_whitelist",
    ]


# ===== 路由出参与入参 =====

@pytest.mark.asyncio
async def test_config_endpoint_exposes_guard_fields(client, admin_token, db_session):
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    resp = client.get("/admin/api/v1/auto-review/config", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert set(["risk_acknowledged", "enforced_rules", "skipped_rules"]) <= set(data)
    # 默认配置三条校验全开（关键词白名单为空属可选规则，允许跳过）
    assert data["enforced_rules"] == ["content_safe", "steps_first_success"]


@pytest.mark.asyncio
async def test_config_endpoint_rejects_all_off(client, admin_token, db_session):
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    resp = client.put(
        "/admin/api/v1/auto-review/config",
        json={
            "enabled": True, "require_content_safe": False,
            "require_steps_first_success": False, "keyword_whitelist": [],
            "risk_acknowledged": True,
        },
        headers=headers,
    )
    # 业务错误走 {code:400} 信封（HTTP 200），与管理端其他护栏一致
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 400
    assert "不能开启自动审批" in body["message"]


@pytest.mark.asyncio
async def test_config_endpoint_requires_risk_ack(client, admin_token, db_session):
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    resp = client.put(
        "/admin/api/v1/auto-review/config",
        json={
            "enabled": True, "require_content_safe": True,
            "require_steps_first_success": True, "keyword_whitelist": ["时政"],
            "risk_acknowledged": False,
        },
        headers=headers,
    )
    body = resp.json()
    assert body["code"] == 400
    assert "风险确认" in body["message"]

    ok = client.put(
        "/admin/api/v1/auto-review/config",
        json={
            "enabled": True, "require_content_safe": True,
            "require_steps_first_success": True, "keyword_whitelist": ["时政"],
            "risk_acknowledged": True,
        },
        headers=headers,
    )
    assert ok.json()["code"] == 0
    data = ok.json()["data"]
    assert data["risk_acknowledged"] is True
    assert data["enforced_rules"] == ["content_safe", "steps_first_success", "keyword_whitelist"]
    assert data["skipped_rules"] == []
