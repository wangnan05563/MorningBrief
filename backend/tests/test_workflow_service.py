"""工作流查询与批量删除服务测试。

覆盖 services/workflow_service.py：
- get_today_workflow：查询今日工作流
- list_workflows：分页
- get_workflow_detail：详情含步骤
- batch_delete_workflows：事务级联删除（含状态校验、孤儿检查）
"""
from datetime import date, datetime

import pytest
from sqlalchemy import select

from app.core.exceptions import BizError, NotFoundError
from app.models import (
    Episode,
    Material,
    PlayLog,
    PlayProgress,
    Review,
    Script,
    Workflow,
    WorkflowStep,
)
# 显式导入 Channel 让 SQLAlchemy 将 channel 表注册到 Base.metadata，
# 否则 Workflow.channel_id 的 ForeignKey 在 create_all 时找不到目标表
from app.models.channel import Channel  # noqa: F401
from app.models.material import MaterialSourceType, MaterialStatus
from app.models.episode import EpisodeStatus
from app.models.review import ReviewStatus
from app.models.script import ScriptStatus
from app.models.workflow import (
    WorkflowSource,
    WorkflowStatus,
    WorkflowStepName,
    WorkflowStepStatus,
)
from app.services.workflow_service import WorkflowService


async def _create_workflow(
    db,
    wid="wf-20260708-0001",
    episode_date=None,
    status=WorkflowStatus.running,
    source=WorkflowSource.cron,
):
    """辅助：创建一条 workflow 记录。"""
    wf = Workflow(
        id=wid,
        episode_date=episode_date or date.today(),
        source=source,
        status=status,
        started_at=datetime.utcnow(),
    )
    db.add(wf)
    await db.commit()
    return wf


async def _add_step(db, workflow_id, step_name=WorkflowStepName.crawl, status=WorkflowStepStatus.success):
    """辅助：为 workflow 添加一条 step。"""
    step = WorkflowStep(
        workflow_id=workflow_id,
        step_name=step_name,
        status=status,
        started_at=datetime.utcnow(),
    )
    db.add(step)
    await db.commit()
    return step


@pytest.mark.asyncio
async def test_get_today_workflow_returns_none(db_session):
    """今日无工作流时返回 None。"""
    svc = WorkflowService(db_session)
    result = await svc.get_today_workflow()
    assert result is None


@pytest.mark.asyncio
async def test_get_today_workflow_returns_data(db_session):
    """今日有工作流时返回详情。"""
    await _create_workflow(db_session)

    svc = WorkflowService(db_session)
    result = await svc.get_today_workflow()
    assert result is not None
    assert result["workflow_id"] == "wf-20260708-0001"
    assert result["status"] == "running"
    assert "steps" in result


@pytest.mark.asyncio
async def test_get_today_workflow_returns_latest(db_session):
    """今日多条工作流时返回最新一条（按 started_at 倒序）。"""
    # 同一日期创建两条
    wf1 = Workflow(
        id="wf-a",
        episode_date=date.today(),
        source=WorkflowSource.cron,
        status=WorkflowStatus.success,
        started_at=datetime(2026, 7, 8, 5, 0, 0),
    )
    wf2 = Workflow(
        id="wf-b",
        episode_date=date.today(),
        source=WorkflowSource.manual,
        status=WorkflowStatus.running,
        started_at=datetime(2026, 7, 8, 6, 0, 0),  # 更晚
    )
    db_session.add_all([wf1, wf2])
    await db_session.commit()

    svc = WorkflowService(db_session)
    result = await svc.get_today_workflow()
    # 返回 started_at 更晚的 wf-b
    assert result["workflow_id"] == "wf-b"


@pytest.mark.asyncio
async def test_list_workflows_pagination(db_session):
    """list_workflows 分页：total 与每页条数正确。"""
    for i in range(5):
        await _create_workflow(
            db_session, wid=f"wf-{i}", episode_date=date(2026, 7, i + 1)
        )

    svc = WorkflowService(db_session)
    page1 = await svc.list_workflows(page=1, size=2)
    assert page1["total"] == 5
    assert len(page1["list"]) == 2

    page3 = await svc.list_workflows(page=3, size=2)
    assert len(page3["list"]) == 1


@pytest.mark.asyncio
async def test_get_workflow_detail_with_steps(db_session):
    """get_workflow_detail 返回详情含步骤列表。"""
    await _create_workflow(db_session, wid="wf-detail")
    await _add_step(db_session, "wf-detail", WorkflowStepName.crawl, WorkflowStepStatus.success)
    await _add_step(db_session, "wf-detail", WorkflowStepName.rewrite, WorkflowStepStatus.running)

    svc = WorkflowService(db_session)
    detail = await svc.get_workflow_detail("wf-detail")
    assert detail["workflow_id"] == "wf-detail"
    assert len(detail["steps"]) == 2
    # 步骤按 id 排序
    assert detail["steps"][0]["name"] == "crawl"
    assert detail["steps"][0]["status"] == "success"
    assert detail["steps"][1]["name"] == "rewrite"
    assert detail["steps"][1]["status"] == "running"


@pytest.mark.asyncio
async def test_get_workflow_detail_not_found_raises(db_session):
    """workflow_id 不存在时抛 NotFoundError。"""
    svc = WorkflowService(db_session)
    with pytest.raises(NotFoundError):
        await svc.get_workflow_detail("not-exist")


@pytest.mark.asyncio
async def test_list_workflows_empty(db_session):
    """无工作流时返回空列表。"""
    svc = WorkflowService(db_session)
    result = await svc.list_workflows(page=1, size=10)
    assert result == {"total": 0, "list": []}


# ==========================================================================
# batch_delete_workflows 测试
#
# 设计要点：
# - 创建完整关联链（workflow → step → script → material → review → episode
#   → play_log / play_progress），验证级联删除覆盖所有从表
# - 校验 running/queued 状态被拒绝，且无部分删除副作用
# - 校验缺失 ID 报 NotFoundError
# ==========================================================================


async def _create_full_chain(
    db,
    wid: str,
    status: str = WorkflowStatus.success.value,
    episode_date=None,
):
    """构造完整关联链：workflow + step + script + material + review + episode + play_log + play_progress。

    返回 (workflow, script, material, review, episode, play_log, play_progress)，
    便于断言所有从表记录在删除后均不存在。
    """
    ep_date = episode_date or date(2026, 7, 8)

    workflow = Workflow(
        id=wid,
        episode_date=ep_date,
        source=WorkflowSource.cron.value,
        status=status,
        started_at=datetime(2026, 7, 8, 5, 0, 0),
        finished_at=datetime(2026, 7, 8, 5, 30, 0),
    )
    db.add(workflow)
    await db.flush()

    step = WorkflowStep(
        workflow_id=wid,
        step_name=WorkflowStepName.crawl.value,
        status=WorkflowStepStatus.success.value,
        started_at=datetime(2026, 7, 8, 5, 0, 0),
        finished_at=datetime(2026, 7, 8, 5, 10, 0),
    )
    db.add(step)

    script = Script(
        workflow_id=wid,
        episode_date=ep_date,
        full_text="测试稿件正文",
        segments=[{"seq": 1, "title": "头条", "content": "..."}],
        status=ScriptStatus.approved.value,
    )
    db.add(script)
    await db.flush()  # 需要 script.id

    material = Material(
        source="测试来源",
        source_type=MaterialSourceType.rss.value,
        title="测试素材",
        content="素材正文",
        url=f"https://example.com/{wid}",
        workflow_id=wid,
        status=MaterialStatus.selected.value,
    )
    db.add(material)

    review = Review(
        workflow_id=wid,
        episode_date=ep_date,
        script_id=script.id,
        audio_url=f"https://example.com/audio/{wid}.mp3",
        status=ReviewStatus.approved.value,
    )
    db.add(review)
    await db.flush()  # 需要 review.id

    # Episode 必须有唯一 date；多 workflow 用不同日期避免 unique 冲突
    episode = Episode(
        date=ep_date,
        title=f"测试节目 {wid}",
        duration=600,
        audio_url=f"https://example.com/episode/{wid}.mp3",
        script_id=script.id,
        review_id=review.id,
        workflow_id=wid,
        status=EpisodeStatus.published.value,
        published_at=datetime(2026, 7, 8, 6, 0, 0),
    )
    db.add(episode)
    await db.flush()  # 需要 episode.id

    play_log = PlayLog(
        user_id=1,
        episode_id=episode.id,
        position=60,
        duration=120,
        completed=0,
    )
    db.add(play_log)

    play_progress = PlayProgress(
        user_id=1,
        episode_id=episode.id,
        position=60,
        duration=600,
        completed=0,
    )
    db.add(play_progress)

    await db.commit()
    return workflow, script, material, review, episode, play_log, play_progress


@pytest.mark.asyncio
async def test_batch_delete_removes_all_related_records(db_session):
    """批量删除成功时应级联清除所有从表记录（step/script/material/review/episode/play_log/play_progress）。"""
    wf, script, material, review, episode, play_log, play_progress = await _create_full_chain(
        db_session, wid="wf-del-001"
    )

    svc = WorkflowService(db_session)
    result = await svc.batch_delete_workflows(["wf-del-001"])

    assert result == {"deleted": ["wf-del-001"]}

    # 断言所有从表无残留
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "wf-del-001"))).scalar_one_or_none() is None
    assert (await db_session.execute(select(WorkflowStep).where(WorkflowStep.workflow_id == "wf-del-001"))).all() == []
    assert (await db_session.execute(select(Script).where(Script.workflow_id == "wf-del-001"))).all() == []
    assert (await db_session.execute(select(Material).where(Material.workflow_id == "wf-del-001"))).all() == []
    assert (await db_session.execute(select(Review).where(Review.workflow_id == "wf-del-001"))).all() == []
    assert (await db_session.execute(select(Episode).where(Episode.workflow_id == "wf-del-001"))).all() == []
    assert (await db_session.execute(select(PlayLog).where(PlayLog.episode_id == episode.id))).all() == []
    assert (await db_session.execute(select(PlayProgress).where(PlayProgress.episode_id == episode.id))).all() == []


@pytest.mark.asyncio
async def test_batch_delete_multiple_workflows(db_session):
    """批量删除多个工作流时每个工作流的关联数据均被清除。"""
    await _create_full_chain(db_session, wid="wf-batch-a", episode_date=date(2026, 7, 8))
    await _create_full_chain(db_session, wid="wf-batch-b", episode_date=date(2026, 7, 9))

    svc = WorkflowService(db_session)
    result = await svc.batch_delete_workflows(["wf-batch-a", "wf-batch-b"])

    assert set(result["deleted"]) == {"wf-batch-a", "wf-batch-b"}
    # 两条工作流及其关联记录应全部消失
    assert (await db_session.execute(select(Workflow))).all() == []
    assert (await db_session.execute(select(WorkflowStep))).all() == []
    assert (await db_session.execute(select(Script))).all() == []
    assert (await db_session.execute(select(Material))).all() == []
    assert (await db_session.execute(select(Review))).all() == []
    assert (await db_session.execute(select(Episode))).all() == []
    assert (await db_session.execute(select(PlayLog))).all() == []
    assert (await db_session.execute(select(PlayProgress))).all() == []


@pytest.mark.asyncio
async def test_batch_delete_rejects_running_workflow(db_session):
    """running 状态工作流拒绝删除。"""
    await _create_full_chain(
        db_session, wid="wf-running", status=WorkflowStatus.running.value
    )

    svc = WorkflowService(db_session)
    with pytest.raises(BizError) as exc_info:
        await svc.batch_delete_workflows(["wf-running"])

    # 错误码 409 表示冲突（运行中不能删除）
    assert exc_info.value.code == 409
    # 工作流及其关联记录应仍然存在（无部分删除）
    wf = (await db_session.execute(select(Workflow).where(Workflow.id == "wf-running"))).scalar_one_or_none()
    assert wf is not None
    assert (await db_session.execute(select(WorkflowStep).where(WorkflowStep.workflow_id == "wf-running"))).all() != []


@pytest.mark.asyncio
async def test_batch_delete_rejects_queued_workflow(db_session):
    """queued 状态工作流拒绝删除（排队中不可删，避免 worker 取出已删记录）。"""
    await _create_full_chain(
        db_session, wid="wf-queued", status=WorkflowStatus.queued.value
    )

    svc = WorkflowService(db_session)
    with pytest.raises(BizError) as exc_info:
        await svc.batch_delete_workflows(["wf-queued"])

    assert exc_info.value.code == 409
    # 关联记录保留
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "wf-queued"))).scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_batch_delete_rejects_partial_when_one_running(db_session):
    """批量中混入 running 工作流时整批拒绝，已完成的工作流也不被删除。"""
    await _create_full_chain(
        db_session, wid="wf-ok", status=WorkflowStatus.success.value, episode_date=date(2026, 7, 8)
    )
    await _create_full_chain(
        db_session, wid="wf-running-mix", status=WorkflowStatus.running.value, episode_date=date(2026, 7, 9)
    )

    svc = WorkflowService(db_session)
    with pytest.raises(BizError):
        await svc.batch_delete_workflows(["wf-ok", "wf-running-mix"])

    # 两条工作流均保留（事务回滚）
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "wf-ok"))).scalar_one_or_none() is not None
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "wf-running-mix"))).scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_batch_delete_raises_not_found_for_missing_id(db_session):
    """批量删除中包含不存在的 ID 时抛 NotFoundError。"""
    await _create_full_chain(db_session, wid="wf-exists", episode_date=date(2026, 7, 8))

    svc = WorkflowService(db_session)
    with pytest.raises(NotFoundError) as exc_info:
        await svc.batch_delete_workflows(["wf-exists", "wf-missing"])

    assert "wf-missing" in str(exc_info.value)
    # 已存在的工作流不应被删除（校验失败回滚）
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "wf-exists"))).scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_batch_delete_empty_list_raises(db_session):
    """空 ID 列表应拒绝（避免误调用导致 no-op 难以排查）。"""
    svc = WorkflowService(db_session)
    with pytest.raises(Exception):
        await svc.batch_delete_workflows([])


@pytest.mark.asyncio
async def test_batch_delete_does_not_touch_unrelated_workflow(db_session):
    """删除工作流不应影响其他工作流的关联数据。"""
    await _create_full_chain(db_session, wid="wf-target", episode_date=date(2026, 7, 8))
    await _create_full_chain(db_session, wid="wf-keep", episode_date=date(2026, 7, 9))

    svc = WorkflowService(db_session)
    await svc.batch_delete_workflows(["wf-target"])

    # wf-keep 及其关联记录应完整保留
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "wf-keep"))).scalar_one_or_none() is not None
    assert (await db_session.execute(select(WorkflowStep).where(WorkflowStep.workflow_id == "wf-keep"))).all() != []
    assert (await db_session.execute(select(Script).where(Script.workflow_id == "wf-keep"))).all() != []
    assert (await db_session.execute(select(Material).where(Material.workflow_id == "wf-keep"))).all() != []
    assert (await db_session.execute(select(Review).where(Review.workflow_id == "wf-keep"))).all() != []
    assert (await db_session.execute(select(Episode).where(Episode.workflow_id == "wf-keep"))).all() != []


# ==========================================================================
# 路由层测试：POST /admin/api/v1/workflows/batch-delete
#
# 覆盖：
# - 静态路由匹配（不被 /{workflow_id} 捕获）
# - 非管理员 403
# - 请求体校验（空列表 / 重复 ID / 超长）
# - 成功路径
#
# 注意：require_admin → is_in_blacklist 会用 app/database.py 的 AsyncSessionLocal
# 连接生产 SQLite 文件，测试环境用 monkeypatch 绕过黑名单查询，
# 让鉴权链路不触发外部 DB 访问。
# ==========================================================================


@pytest.fixture
def stub_blacklist(monkeypatch):
    """绕过 is_in_blacklist 的 DB 查询，避免命中生产 SQLite 文件。"""
    async def _always_false(jti: str) -> bool:
        return False
    # 替换 app.core.auth 模块中已绑定的 is_in_blacklist 引用
    monkeypatch.setattr("app.core.auth.is_in_blacklist", _always_false)


def _admin_headers(admin_token):
    """构造 admin 请求头。"""
    return {"Authorization": f"Bearer {admin_token['token']}"}


def test_batch_delete_route_rejects_non_admin(client, admin_token, stub_blacklist):
    """非 admin 角色调用批量删除应返回 403。"""
    from app.core.security import create_access_token
    token, _, _ = create_access_token(
        "2", token_type="admin", extra_claims={"username": "op01", "role": "operator"}
    )
    resp = client.post(
        "/admin/api/v1/workflows/batch-delete",
        json={"workflow_ids": ["wf-001"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_batch_delete_route_rejects_empty_list(client, admin_token, stub_blacklist):
    """空 workflow_ids 列表应被 Pydantic 拒绝（422）。"""
    resp = client.post(
        "/admin/api/v1/workflows/batch-delete",
        json={"workflow_ids": []},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code in (400, 422)


def test_batch_delete_route_rejects_duplicate_ids(client, admin_token, stub_blacklist):
    """重复 ID 应被 field_validator 拒绝。"""
    resp = client.post(
        "/admin/api/v1/workflows/batch-delete",
        json={"workflow_ids": ["wf-001", "wf-001"]},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code in (400, 422)


def test_batch_delete_route_rejects_too_many_ids(client, admin_token, stub_blacklist):
    """超过 100 个 ID 应被 Field(max_length=100) 拒绝。"""
    ids = [f"wf-{i:04d}" for i in range(101)]
    resp = client.post(
        "/admin/api/v1/workflows/batch-delete",
        json={"workflow_ids": ids},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code in (400, 422)


def test_batch_delete_route_static_path_not_captured_by_dynamic(client, admin_token, stub_blacklist):
    """POST /batch-delete 应命中批量删除路由，而非被 GET /{workflow_id} 拦截。

    验证方式：空数据库下调用批量删除不存在的 ID，应返回 404（NotFoundError），
    而非 405 Method Not Allowed（说明 /batch-delete 被当作 workflow_id）。
    """
    resp = client.post(
        "/admin/api/v1/workflows/batch-delete",
        json={"workflow_ids": ["wf-not-exist"]},
        headers=_admin_headers(admin_token),
    )
    # NotFoundError → 404，证明路由命中了 batch-delete 而非被动态路由捕获
    assert resp.status_code == 404
    data = resp.json()
    assert "wf-not-exist" in data["message"]


@pytest.mark.asyncio
async def test_batch_delete_route_success(client, db_session, admin_token, stub_blacklist):
    """admin 调用批量删除成功路径：返回 200 + deleted 列表。"""
    await _create_full_chain(db_session, wid="wf-route-del", episode_date=date(2026, 7, 8))

    resp = client.post(
        "/admin/api/v1/workflows/batch-delete",
        json={"workflow_ids": ["wf-route-del"]},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"] == {"deleted": ["wf-route-del"]}
    # 数据库中应已删除
    assert (await db_session.execute(select(Workflow).where(Workflow.id == "wf-route-del"))).scalar_one_or_none() is None
