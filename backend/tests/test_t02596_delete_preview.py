"""批量删除影响面预览测试（T02596 切片A）。

delete_preview 是只读接口，其唯一正确性标准是「预览条数 == batch_delete_workflows
实际会动到的行数」。本文件把两者钉在一起：
- 用同一套链构造，逐类断言 preview 数与库中真实行数一致；
- 断言 preview 不改动任何数据（只读）；
- 覆盖删除阶段的双条件（episode/review 按 workflow_id OR script_id），
  尤其是 workflow_id 为 NULL 的孤儿 Episode/Review 也必须被预览计入；
- 空列表 / 缺失 ID 的报错与 batch_delete 口径一致（前端据此禁提交）。
"""
from datetime import date, datetime

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundError, ParamError
from app.core.security import create_access_token
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
from app.models.channel import Channel  # noqa: F401  确保外键目标表已注册
from app.models.episode import EpisodeStatus
from app.models.material import MaterialSourceType, MaterialStatus
from app.models.review import ReviewStatus
from app.models.script import ScriptStatus
from app.models.workflow import (
    WorkflowSource,
    WorkflowStatus,
    WorkflowStepName,
    WorkflowStepStatus,
)
from app.services.workflow_service import WorkflowService


async def _chain(db, wid: str, ep_date: date, *, orphan_episode: bool = False):
    """构造一条工作流及其全链路关联数据。

    orphan_episode=True 时额外挂一个 workflow_id=NULL、仅靠 script_id 关联的
    孤儿 Episode——复现 batch_delete_workflows 按 `workflow_id OR script_id`
    删 Episode 的分支，验证预览同样计入它。
    """
    db.add(Workflow(
        id=wid, episode_date=ep_date, source=WorkflowSource.cron.value,
        status=WorkflowStatus.success.value,
        started_at=datetime(2026, 7, 8, 5, 0, 0), finished_at=datetime(2026, 7, 8, 5, 30, 0),
    ))
    await db.flush()
    db.add(WorkflowStep(
        workflow_id=wid, step_name=WorkflowStepName.crawl.value,
        status=WorkflowStepStatus.success.value,
        started_at=datetime(2026, 7, 8, 5, 0, 0), finished_at=datetime(2026, 7, 8, 5, 10, 0),
    ))
    script = Script(
        workflow_id=wid, episode_date=ep_date, full_text="正文", segments=[{"seq": 1}],
        status=ScriptStatus.approved.value,
    )
    db.add(script)
    await db.flush()
    db.add(Material(
        source="来源", source_type=MaterialSourceType.rss.value, title="素材",
        content="素材正文", url=f"https://example.com/{wid}", workflow_id=wid,
        status=MaterialStatus.selected.value,
    ))
    review = Review(
        workflow_id=wid, episode_date=ep_date, script_id=script.id,
        audio_url=f"https://example.com/a/{wid}.mp3", status=ReviewStatus.approved.value,
    )
    db.add(review)
    await db.flush()
    db.add(Episode(
        date=ep_date, title=f"节目 {wid}", duration=600,
        audio_url=f"https://example.com/e/{wid}.mp3", script_id=script.id,
        review_id=review.id, workflow_id=wid, status=EpisodeStatus.published.value,
        published_at=datetime(2026, 7, 8, 6, 0, 0),
    ))
    if orphan_episode:
        # 孤儿节目：workflow_id 为 NULL，只有 script_id 命中本批（早期未回填数据）
        db.add(Episode(
            date=date(2099, 1, 1), title=f"孤儿节目 {wid}", duration=1,
            audio_url=f"https://example.com/orphan/{wid}.mp3", script_id=script.id,
            review_id=review.id, workflow_id=None, status=EpisodeStatus.published.value,
            published_at=datetime(2026, 7, 8, 6, 0, 0),
        ))
        # 归属旧工作流的审核：workflow_id 不在本批，但 script_id 指向本批稿件
        # （重跑/换工作流后遗留的旧审核）。删除阶段按 OR(script_id) 命中，
        # 预览只按 workflow_id 统计就会漏掉它。
        db.add(Review(
            workflow_id=f"{wid}-old", episode_date=ep_date, script_id=script.id,
            audio_url=f"https://example.com/old/{wid}.mp3",
            status=ReviewStatus.approved.value,
        ))
    await db.flush()

    eps = (await db.execute(select(Episode.id).where(
        (Episode.workflow_id == wid) | (Episode.script_id == script.id)
    ))).scalars().all()
    for eid in eps:
        db.add(PlayLog(user_id=1, episode_id=eid, position=60, duration=120, completed=0))
        db.add(PlayProgress(user_id=1, episode_id=eid, position=60, duration=600, completed=0))
    await db.commit()
    return script


async def _row_count(db, model, *conds):
    from sqlalchemy import or_
    res = await db.execute(select(model).where(or_(*conds)))
    return len(res.all())


@pytest.mark.asyncio
async def test_preview_counts_match_stored_rows(db_session):
    """预览各类条数应逐一等于库中该工作流关联的真实行数。"""
    await _chain(db_session, "wf-pv-1", date(2026, 7, 8))
    svc = WorkflowService(db_session)

    pv = await svc.delete_preview(["wf-pv-1"])

    assert pv["workflows"] == 1
    assert pv["scripts"] == 1
    assert pv["reviews"] == 1
    assert pv["episodes"] == 1
    assert pv["play_logs"] == 1
    assert pv["play_progress"] == 1
    assert pv["workflow_steps"] == 1
    # 素材不删只重置：预览用独立字段如实报保留条数，别把它当删除条数
    assert pv["materials_retained"] == 1
    assert pv["comments"] == 0
    assert pv["favorites"] == 0


@pytest.mark.asyncio
async def test_preview_counts_equal_delete_removed_rows(db_session):
    """最强一致性：先取预览，再实删，逐类被删行数必须等于预览报的数。"""
    await _chain(db_session, "wf-pv-2", date(2026, 7, 10))
    svc = WorkflowService(db_session)
    pv = await svc.delete_preview(["wf-pv-2"])

    # 删除前各类真实行数（与预览同源条件）
    before = {
        "scripts": await _row_count(db_session, Script, Script.workflow_id == "wf-pv-2"),
        "reviews": await _row_count(
            db_session, Review, Review.workflow_id == "wf-pv-2", Review.script_id.in_(
                [s.id for s in (await db_session.execute(select(Script).where(Script.workflow_id == "wf-pv-2"))).scalars()]
            )),
        "episodes": await _row_count(
            db_session, Episode, Episode.workflow_id == "wf-pv-2"),
    }
    assert pv["scripts"] == before["scripts"]
    assert pv["reviews"] == before["reviews"]
    assert pv["episodes"] == before["episodes"]

    await svc.batch_delete_workflows(["wf-pv-2"])
    # 删除后：脚本/审核/节目/播放记录应归零，素材应保留（workflow_id 置空）
    assert (await db_session.execute(select(Script))).all() == []
    assert (await db_session.execute(select(Review))).all() == []
    assert (await db_session.execute(select(Episode))).all() == []
    assert (await db_session.execute(select(PlayLog))).all() == []
    mats = (await db_session.execute(select(Material))).scalars().all()
    assert len(mats) == pv["materials_retained"]
    assert all(m.workflow_id is None for m in mats)


@pytest.mark.asyncio
async def test_preview_includes_orphan_episode_and_its_play_logs(db_session):
    """只有 script_id 命中的孤儿数据（节目/旧审核）也要计入预览，与删除的 OR 双条件一致。"""
    await _chain(db_session, "wf-pv-orph", date(2026, 7, 11), orphan_episode=True)
    svc = WorkflowService(db_session)
    pv = await svc.delete_preview(["wf-pv-orph"])

    # 主节目 + 孤儿节目 = 2；每条节目各 1 播放记录 + 1 进度 → 2/2
    assert pv["episodes"] == 2
    assert pv["play_logs"] == 2
    assert pv["play_progress"] == 2
    # 本批审核 + 归属旧工作流但 script_id 指向本批稿件的审核 = 2
    assert pv["reviews"] == 2

    await svc.batch_delete_workflows(["wf-pv-orph"])
    # 孤儿节目/旧审核也必须被删（否则删 Script 会触发外键约束），验证预览口径与删除一致
    assert (await db_session.execute(select(Episode))).all() == []
    assert (await db_session.execute(select(Review))).all() == []
    assert (await db_session.execute(select(PlayLog))).all() == []


@pytest.mark.asyncio
async def test_preview_is_read_only(db_session):
    """调用预览不得改动任何数据：所有行原样保留。"""
    await _chain(db_session, "wf-pv-ro", date(2026, 7, 12))
    svc = WorkflowService(db_session)
    await svc.delete_preview(["wf-pv-ro"])

    assert (await db_session.execute(select(Workflow))).all() != []
    assert (await db_session.execute(select(Script))).all() != []
    assert (await db_session.execute(select(Episode))).all() != []
    assert (await db_session.execute(select(PlayLog))).all() != []


@pytest.mark.asyncio
async def test_preview_empty_list_raises_param(db_session):
    svc = WorkflowService(db_session)
    with pytest.raises(ParamError):
        await svc.delete_preview([])


@pytest.mark.asyncio
async def test_preview_missing_id_raises_notfound(db_session):
    await _chain(db_session, "wf-pv-exist", date(2026, 7, 13))
    svc = WorkflowService(db_session)
    with pytest.raises(NotFoundError):
        await svc.delete_preview(["wf-pv-exist", "wf-pv-nope"])


@pytest.mark.asyncio
async def test_preview_workflow_without_children_reports_zero_play_rows(db_session):
    """只有 workflow、没有任何从表：播放类计数为 0，不得因 `IN ()` 误报或报错。"""
    db_session.add(Workflow(
        id="wf-pv-bare", episode_date=date(2026, 7, 14), source=WorkflowSource.cron.value,
        status=WorkflowStatus.success.value,
    ))
    await db_session.commit()
    svc = WorkflowService(db_session)
    pv = await svc.delete_preview(["wf-pv-bare"])
    assert pv["workflows"] == 1
    assert pv["episodes"] == 0
    assert pv["play_logs"] == 0
    assert pv["play_progress"] == 0
    assert pv["comments"] == 0
    assert pv["favorites"] == 0


# ==========================================================================
# 路由层：POST /admin/api/v1/workflows/batch-delete/preview
# ==========================================================================


@pytest.fixture
def stub_blacklist(monkeypatch):
    async def _always_false(jti: str) -> bool:
        return False
    monkeypatch.setattr("app.core.auth.is_in_blacklist", _always_false)


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


@pytest.mark.asyncio
async def test_preview_route_success(
    client, db_session, admin_token, stub_blacklist
):
    """admin 调预览返回 200 + 各类条数，且不删除任何数据。"""
    await _chain(db_session, "wf-pv-route", date(2026, 7, 15))
    resp = client.post(
        "/admin/api/v1/workflows/batch-delete/preview",
        json={"workflow_ids": ["wf-pv-route"]},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["episodes"] == 1
    assert data["data"]["play_logs"] == 1
    assert data["data"]["materials_retained"] == 1
    # 只读：预览后工作流仍在
    assert (await db_session.execute(
        select(Workflow).where(Workflow.id == "wf-pv-route")
    )).scalar_one_or_none() is not None


def test_preview_route_rejects_non_admin(client, stub_blacklist):
    token, _, _ = create_access_token(
        "2", token_type="admin", extra_claims={"username": "op01", "role": "operator"}
    )
    resp = client.post(
        "/admin/api/v1/workflows/batch-delete/preview",
        json={"workflow_ids": ["x"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_preview_route_static_path_not_captured_by_dynamic(
    client, admin_token, stub_blacklist
):
    """`/batch-delete/preview` 命中静态预览路由，而非被 `/batch-delete` 或 `/{workflow_id}` 捕获。

    用一个不存在的工作流 ID：若命中预览路由 → NotFoundError → 404 且消息含该 ID；
    若误命中 batch-delete 之外的路径会是别的错误。
    """
    resp = client.post(
        "/admin/api/v1/workflows/batch-delete/preview",
        json={"workflow_ids": ["wf-pv-ghost"]},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 404
    assert "wf-pv-ghost" in resp.json()["message"]
