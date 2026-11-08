"""全频道触发：审计原因不得被频道级原因覆盖（S1226 修复的回归门禁）。

`trigger_all_workflows` 的 `reason` 是运营在界面填的触发原因，循环里解包出来的
第三个字段是每个频道的跳过/失败原因。两者同名时，循环结束会把前者改写掉，
审计里那条操作的「为什么」就变成了最后一个频道的「当日已有运行中工作流」——
事后查审计只能看到系统的拒绝话术，看不到当初是谁为什么点的按钮。
"""
import json
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import AuditLog, Channel, Workflow, WorkflowStatus
from app.routers.admin.workflows import trigger_all_workflows
from app.services.workflow_scheduler import workflow_scheduler

_OPERATOR_REASON = "突发专题：临时补一档早报"


async def _add_channel(db_session, name):
    ch = Channel(name=name, channel_type="news", selection_strategy="heat")
    db_session.add(ch)
    await db_session.flush()
    return ch


async def _add_running_workflow(db_session, channel_id):
    db_session.add(Workflow(
        id=f"wf_{channel_id}",
        episode_date=date.today(),
        source="manual",
        status=WorkflowStatus.running.value,
        channel_id=channel_id,
    ))
    await db_session.flush()


async def _audit_detail(db_session):
    row = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "trigger_all")
    )).scalars().one()
    return json.loads(row.detail)


@pytest.mark.asyncio
async def test_skip_branch_does_not_overwrite_operator_reason(db_session):
    """频道被跳过时，审计原因仍是运营填写的内容，跳过原因只进频道项。"""
    ch = await _add_channel(db_session, "早报频道")
    await _add_running_workflow(db_session, ch.id)

    resp = await trigger_all_workflows(
        reason=_OPERATOR_REASON, db=db_session, admin=SimpleNamespace(username="admin")
    )
    data = resp["data"]
    assert [i["channel_id"] for i in data["skipped"]] == [ch.id]
    assert data["skipped"][0]["reason"] == "当日已有运行中工作流"

    detail = await _audit_detail(db_session)
    assert detail["reason"] == _OPERATOR_REASON
    assert detail["skipped_count"] == 1
    # 跳过原因仍然如实记在频道项上，只是不能顶替操作者填写的原因
    assert detail["skipped"][0]["reason"] == "当日已有运行中工作流"


@pytest.mark.asyncio
async def test_failed_channel_error_and_audit_reason_stay_separate(db_session, monkeypatch):
    """触发失败时频道项带异常文本，审计原因不被串台；成功频道不受影响。"""
    bad = await _add_channel(db_session, "故障频道")
    good = await _add_channel(db_session, "正常频道")

    async def _boom(**kwargs):
        if kwargs["channel_id"] == bad.id:
            raise RuntimeError("爬虫服务不可用")
        return "wf_new_2"

    monkeypatch.setattr(workflow_scheduler, "trigger_workflow", _boom)

    resp = await trigger_all_workflows(
        reason=_OPERATOR_REASON, db=db_session, admin=SimpleNamespace(username="admin")
    )
    data = resp["data"]
    assert data["failed"][0]["error"] == "爬虫服务不可用"
    assert data["triggered"][0]["workflow_id"] == "wf_new_2"
    assert data["triggered"][0]["channel_id"] == good.id
    assert data["failed"][0]["channel_id"] == bad.id

    detail = await _audit_detail(db_session)
    assert detail["reason"] == _OPERATOR_REASON
