"""队列管理批量删除路由测试（HTTP 层）。

覆盖 SRS 队列管理批量删除的交互契约：
- admin 成功删除终态任务 → 200 + deleted 列表 + DB 物理删除
- queued 任务随整批拒绝 → 409（worker 可能持有/即将取出）
- 非 admin（operator）拒绝 → 403
- 静态路由 /tasks/batch-delete 不被 /tasks/{workflow_id}/* 动态路由捕获（不存在 ID → 404）

复用 workflow 批量删除的级联逻辑（委托 WorkflowService），故级联正确性由
test_workflow_service / test_queue_service 保证，本文件只验证队列路由层。
"""
from datetime import date

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models import Workflow
from app.models.workflow import WorkflowSource, WorkflowStatus


@pytest.fixture
def stub_blacklist(monkeypatch):
    """黑名单恒为未命中，避免测试 token 被当失效。"""
    async def _always_false(jti: str) -> bool:
        return False
    monkeypatch.setattr("app.core.auth.is_in_blacklist", _always_false)


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


async def _create_workflow(db, wid, status, priority=5):
    wf = Workflow(
        id=wid,
        episode_date=date.today(),
        source=WorkflowSource.cron,
        status=status,
        priority=priority,
        started_at=None,
    )
    db.add(wf)
    await db.commit()
    return wf


@pytest.mark.asyncio
async def test_queue_batch_delete_route_success(client, db_session, admin_token, stub_blacklist):
    """admin 调用队列批量删除成功：返回 200 + deleted 列表，DB 物理删除。"""
    await _create_workflow(db_session, "q-wf-del-1", WorkflowStatus.success)
    await _create_workflow(db_session, "q-wf-del-2", WorkflowStatus.failed)

    resp = client.post(
        "/admin/api/v1/queue/tasks/batch-delete",
        json={"workflow_ids": ["q-wf-del-1", "q-wf-del-2"]},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert set(data["data"]["deleted"]) == {"q-wf-del-1", "q-wf-del-2"}

    # 数据库中两行应已删除
    remaining = (await db_session.execute(
        select(Workflow.id).where(Workflow.id.in_(["q-wf-del-1", "q-wf-del-2"]))
    )).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_queue_batch_delete_route_rejects_queued(client, db_session, admin_token, stub_blacklist):
    """含 queued 任务的整批请求应被拒绝（409），且不删除任何记录。"""
    await _create_workflow(db_session, "q-wf-q-1", WorkflowStatus.queued)
    await _create_workflow(db_session, "q-wf-s-1", WorkflowStatus.success)

    resp = client.post(
        "/admin/api/v1/queue/tasks/batch-delete",
        json={"workflow_ids": ["q-wf-q-1", "q-wf-s-1"]},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 409

    # 整批回滚：success 任务也不应被删
    remaining = (await db_session.execute(
        select(Workflow.id).where(Workflow.id.in_(["q-wf-q-1", "q-wf-s-1"]))
    )).scalars().all()
    assert set(remaining) == {"q-wf-q-1", "q-wf-s-1"}


def test_queue_batch_delete_route_rejects_non_admin(client, admin_token, stub_blacklist):
    """operator 角色调用队列批量删除应返回 403。"""
    token, _, _ = create_access_token(
        "2", token_type="admin", extra_claims={"username": "op01", "role": "operator"}
    )
    resp = client.post(
        "/admin/api/v1/queue/tasks/batch-delete",
        json={"workflow_ids": ["q-wf-x"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_queue_batch_delete_static_path_not_captured(client, admin_token, stub_blacklist):
    """POST /tasks/batch-delete 命中批量路由而非被动态路由捕获（不存在 ID → 404）。"""
    resp = client.post(
        "/admin/api/v1/queue/tasks/batch-delete",
        json={"workflow_ids": ["q-wf-not-exist"]},
        headers=_admin_headers(admin_token),
    )
    # NotFoundError → 404，证明路由命中 batch-delete 而非被 /tasks/{workflow_id}/* 捕获
    assert resp.status_code == 404
    assert "q-wf-not-exist" in resp.json()["message"]
