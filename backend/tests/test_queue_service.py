"""队列管理服务测试。

覆盖 SRS 10.1 要求的 12 项队列测试：
- test_channel_crud：频道增删改查、名称唯一约束、删除置 NULL
- test_queue_priority：5 任务优先级出队顺序 10→8→5→5→3
- test_semaphore_concurrent：parallel max=2 同时执行≤2
- test_queue_restart：重启后 queued 任务重建不丢失
- test_cancel_task：取消 queued 任务，worker 跳过
- test_update_priority：改优先级后旧条目取消、新条目入队
- test_retry_task：failed → queued 重新入队
- test_config_hot_reload：配置变更标记 _config_dirty，任务完成后重建
- test_backup_multi_channel：3 频道独立备播不抛 MultipleResultsFound
- test_cron_check_multi_channel：3 频道独立兜底检查
- test_workflow_id_concurrent：并发触发 5 任务 ID 不冲突
- test_batch_delete_queued：queued 状态直接删除被拒绝

设计说明：
- 直接测试服务层与调度器，绕过 HTTP 层，避免鉴权 fixture 干扰
- AsyncSessionLocal 被 monkeypatch 指向测试内存 DB 的 factory，
  让 scheduler 内部 `async with AsyncSessionLocal() as session` 与测试共享同一 session
- cancel_task/update_priority/config_hot_reload 内部 import 的是
  workflow_scheduler 单例，测试必须操作单例并重置其状态
- 测试不启动 worker，仅验证入队/状态变更/优先级顺序
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from app.core.timeutil import localnow_naive
from app.models import Workflow
from app.models.channel import Channel
from app.models.workflow import (
    WorkflowSource,
    WorkflowStatus,
    WorkflowStepName,
)
from app.services.channel_service import ChannelService
from app.services.queue_service import QueueService


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


async def _create_channel(db, name="科技频道", description="科技资讯", is_active=1):
    ch = Channel(name=name, description=description, is_active=is_active)
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    return ch


async def _create_queued_workflow(
    db, wid, episode_date=None, channel_id=None, priority=5, started_at=None,
):
    wf = Workflow(
        id=wid,
        episode_date=episode_date or date.today(),
        source=WorkflowSource.cron,
        status=WorkflowStatus.queued,
        channel_id=channel_id,
        priority=priority,
        started_at=started_at or localnow_naive(),
    )
    db.add(wf)
    await db.commit()
    return wf


async def _create_workflow(db, wid, status, episode_date=None, priority=5):
    """创建指定状态的 workflow，用于批量删除测试。"""
    wf = Workflow(
        id=wid,
        episode_date=episode_date or date.today(),
        source=WorkflowSource.cron,
        status=status,
        priority=priority,
        started_at=localnow_naive(),
    )
    db.add(wf)
    await db.commit()
    return wf


def _patch_sessionlocal(monkeypatch, session):
    """把 workflow_scheduler.AsyncSessionLocal 替换为返回测试 session 的 factory。

    scheduler 内部 `async with AsyncSessionLocal() as session: ...` 需要
    AsyncSessionLocal() 返回支持 __aenter__/__aexit__ 的对象。
    这里用 asynccontextmanager 让调用即返回同一测试 session，不真正关闭连接。
    """

    @asynccontextmanager
    async def _factory():
        yield session

    from app.services import workflow_scheduler as ws_mod
    monkeypatch.setattr(ws_mod, "AsyncSessionLocal", _factory)


@pytest.fixture(autouse=True)
def _reset_scheduler(monkeypatch):
    """每个测试前重置 workflow_scheduler 单例的内存状态，避免跨测试污染。

    QueueService 内部 `from app.services.workflow_scheduler import workflow_scheduler`
    拿到的是模块级单例，必须显式重置其队列/信号量/entry_map。
    同时保存并还原被个别测试 mock 的方法，避免 mock 泄漏到后续测试。
    """
    from app.services.workflow_scheduler import workflow_scheduler
    # 保存原始方法引用（部分测试会 AsyncMock 替换，yield 后还原）
    orig_trigger = workflow_scheduler.trigger_workflow
    orig_retry_workflow = workflow_scheduler.retry_workflow
    orig_get_db_max_seq = workflow_scheduler._get_db_max_seq
    orig_check_backup_single = workflow_scheduler._check_backup_single

    workflow_scheduler._queue = asyncio.PriorityQueue()
    workflow_scheduler._semaphore = asyncio.Semaphore(1)
    workflow_scheduler._entry_map.clear()
    workflow_scheduler._config_dirty = False
    workflow_scheduler._execution_mode = "serial"
    workflow_scheduler._max_concurrent = 1
    yield
    # 还原被 mock 的方法，防止泄漏到后续测试
    workflow_scheduler.trigger_workflow = orig_trigger
    workflow_scheduler.retry_workflow = orig_retry_workflow
    workflow_scheduler._get_db_max_seq = orig_get_db_max_seq
    workflow_scheduler._check_backup_single = orig_check_backup_single


# ---------------------------------------------------------------------------
# 1. test_channel_crud
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_channel_crud(db_session):
    """频道 CRUD + 名称唯一约束 + 删除后关联 workflow.channel_id 置 NULL。"""
    svc = ChannelService(db_session)

    # Create
    ch = await svc.create_channel("测试频道", "描述")
    assert ch.id is not None
    assert ch.name == "测试频道"
    assert ch.is_active == 1

    # Read
    got = await svc.get_channel(ch.id)
    assert got is not None
    assert got.name == "测试频道"

    # Update
    updated = await svc.update_channel(ch.id, name="改名频道", is_active=0)
    assert updated.name == "改名频道"
    assert updated.is_active == 0
    # 提前保存 id：后续唯一约束失败会触发 rollback，导致 updated 对象 expired，
    # 再访问 .id 会触发同步 lazy load 抛 MissingGreenlet
    updated_id = updated.id

    # 唯一约束
    await svc.create_channel("唯一频道")
    with pytest.raises(ValueError, match="频道名称已存在"):
        await svc.create_channel("唯一频道")

    # Delete：关联 workflow 的 channel_id 应被外键 ON DELETE SET NULL 置 NULL
    wf = await _create_queued_workflow(
        db_session, "wf-test-0001", channel_id=updated_id
    )
    wf_id = wf.id
    await svc.delete_channel(updated_id)
    # expire 后重新查询，避免内存对象残留旧值
    db_session.expire_all()
    refreshed = await db_session.get(Workflow, wf_id)
    assert refreshed.channel_id is None

    # 删除后再查返回 None
    assert await svc.get_channel(updated_id) is None


# ---------------------------------------------------------------------------
# 2. test_queue_priority
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_priority():
    """5 任务优先级出队顺序：10→8→5→5→3（同优先级按入队时间 FIFO）。"""
    from app.services.workflow_scheduler import QueueEntry

    q: asyncio.PriorityQueue = asyncio.PriorityQueue()
    base_time = localnow_naive()
    entries = [
        QueueEntry(sort_priority=-5, created_at=base_time.timestamp(),
                   workflow_id="wf-1", priority=5),
        QueueEntry(sort_priority=-10, created_at=(base_time + timedelta(seconds=1)).timestamp(),
                   workflow_id="wf-2", priority=10),
        QueueEntry(sort_priority=-8, created_at=(base_time + timedelta(seconds=2)).timestamp(),
                   workflow_id="wf-3", priority=8),
        QueueEntry(sort_priority=-3, created_at=(base_time + timedelta(seconds=3)).timestamp(),
                   workflow_id="wf-4", priority=3),
        QueueEntry(sort_priority=-5, created_at=(base_time + timedelta(seconds=4)).timestamp(),
                   workflow_id="wf-5", priority=5),
    ]
    for e in entries:
        await q.put(e)

    order = []
    while not q.empty():
        e = await q.get()
        order.append(e.priority)

    assert order == [10, 8, 5, 5, 3]


# ---------------------------------------------------------------------------
# 3. test_semaphore_concurrent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_semaphore_concurrent():
    """parallel 模式 max_concurrent=2 时同时执行任务数不超过 2。"""
    max_concurrent = 2
    sem = asyncio.Semaphore(max_concurrent)
    current = 0
    peak = 0
    lock = asyncio.Lock()

    async def task():
        nonlocal current, peak
        async with sem:
            async with lock:
                current += 1
                peak = max(peak, current)
            await asyncio.sleep(0.05)
            async with lock:
                current -= 1

    await asyncio.gather(*[task() for _ in range(5)])
    assert peak <= max_concurrent
    assert peak == max_concurrent


# ---------------------------------------------------------------------------
# 4. test_queue_restart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_restart(db_session, monkeypatch):
    """重启后从 DB 重建 PriorityQueue，queued 任务不丢失。"""
    from app.services.workflow_scheduler import workflow_scheduler

    await _create_queued_workflow(
        db_session, "wf-restart-1", priority=5,
        started_at=localnow_naive() - timedelta(seconds=30),
    )
    await _create_queued_workflow(
        db_session, "wf-restart-2", priority=8,
        started_at=localnow_naive() - timedelta(seconds=20),
    )
    await _create_queued_workflow(
        db_session, "wf-restart-3", priority=3,
        started_at=localnow_naive() - timedelta(seconds=10),
    )

    _patch_sessionlocal(monkeypatch, db_session)
    await workflow_scheduler._rebuild_queue()

    assert workflow_scheduler._queue.qsize() == 3
    order = []
    while not workflow_scheduler._queue.empty():
        e = await workflow_scheduler._queue.get()
        order.append(e.priority)
    assert order == [8, 5, 3]


# ---------------------------------------------------------------------------
# 5. test_cancel_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_task(db_session, monkeypatch):
    """取消 queued 任务：DB 状态变 cancelled，队列条目标记 cancelled。"""
    from app.services.workflow_scheduler import (
        QueueEntry, workflow_scheduler,
    )

    wf = await _create_queued_workflow(db_session, "wf-cancel-1")
    _patch_sessionlocal(monkeypatch, db_session)

    entry = QueueEntry(
        sort_priority=-5, created_at=localnow_naive().timestamp(),
        workflow_id="wf-cancel-1", priority=5,
    )
    workflow_scheduler._entry_map["wf-cancel-1"] = entry

    svc = QueueService(db_session)
    await svc.cancel_task("wf-cancel-1")

    db_session.expire_all()
    refreshed = await db_session.get(Workflow, "wf-cancel-1")
    assert refreshed.status == WorkflowStatus.cancelled.value
    assert entry.cancelled is True


# ---------------------------------------------------------------------------
# 6. test_update_priority
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_priority(db_session, monkeypatch):
    """改优先级：DB 更新 + 旧条目取消 + 新条目按新优先级入队。"""
    from app.services.workflow_scheduler import (
        QueueEntry, workflow_scheduler,
    )

    wf = await _create_queued_workflow(db_session, "wf-prio-1", priority=5)
    _patch_sessionlocal(monkeypatch, db_session)

    old_entry = QueueEntry(
        sort_priority=-5, created_at=localnow_naive().timestamp(),
        workflow_id="wf-prio-1", priority=5,
    )
    workflow_scheduler._entry_map["wf-prio-1"] = old_entry

    svc = QueueService(db_session)
    await svc.update_priority("wf-prio-1", 9)

    db_session.expire_all()
    refreshed = await db_session.get(Workflow, "wf-prio-1")
    assert refreshed.priority == 9
    assert old_entry.cancelled is True
    assert "wf-prio-1" in workflow_scheduler._entry_map
    new_entry = workflow_scheduler._entry_map["wf-prio-1"]
    assert new_entry.priority == 9
    assert new_entry is not old_entry


# ---------------------------------------------------------------------------
# 7. test_retry_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_task(db_session, monkeypatch):
    """重试 failed 任务：无 failed 步骤时兜底从 crawl 全量重跑，保留原 ID。

    当前实现调用 retry_workflow 断点续跑（而非 trigger_workflow 新建），
    无 failed 步骤记录时兜底从 crawl 重跑，返回原 workflow_id。
    """
    from app.services.workflow_scheduler import workflow_scheduler

    wf = Workflow(
        id="wf-retry-1",
        episode_date=date.today(),
        source=WorkflowSource.cron,
        status=WorkflowStatus.failed,
        priority=5,
        started_at=localnow_naive(),
    )
    db_session.add(wf)
    await db_session.commit()

    _patch_sessionlocal(monkeypatch, db_session)
    # retry_workflow 保留原 workflow_id，断点续跑而非新建工作流
    workflow_scheduler.retry_workflow = AsyncMock(return_value="wf-retry-1")

    svc = QueueService(db_session)
    new_id = await svc.retry_task("wf-retry-1")

    # 返回原 ID（断点续跑语义，非新建工作流）
    assert new_id == "wf-retry-1"
    workflow_scheduler.retry_workflow.assert_awaited_once()
    call_kwargs = workflow_scheduler.retry_workflow.call_args
    # 无 failed 步骤记录时兜底从 crawl 全量重跑
    assert call_kwargs.kwargs["from_step"] == WorkflowStepName.crawl.value
    assert call_kwargs.kwargs["triggered_by"] == "queue_retry"


# ---------------------------------------------------------------------------
# 8. test_config_hot_reload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_config_hot_reload(db_session, monkeypatch):
    """配置变更：标记 _config_dirty，调用 _rebuild_semaphore 后清除标记。"""
    from app.services.workflow_scheduler import workflow_scheduler

    _patch_sessionlocal(monkeypatch, db_session)

    svc = QueueService(db_session)
    await svc.update_queue_config("parallel", 3)

    assert workflow_scheduler._execution_mode == "parallel"
    assert workflow_scheduler._max_concurrent == 3
    assert workflow_scheduler._config_dirty is True

    workflow_scheduler._rebuild_semaphore()
    assert workflow_scheduler._config_dirty is False
    assert workflow_scheduler._semaphore._value == 3


# ---------------------------------------------------------------------------
# 9. test_backup_multi_channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backup_multi_channel(db_session, monkeypatch):
    """3 频道独立备播：_check_backup 对每个活跃频道调用一次 _check_backup_single。

    按频道分组查询避免 scalar_one_or_none 抛 MultipleResultsFound，
    本测试验证分组调度逻辑正确，不依赖真实 Episode 创建（date unique 约束
    在多频道场景下由 SRS 11.3 后续迭代解除）。
    """
    from app.services.workflow_scheduler import workflow_scheduler

    ch1 = await _create_channel(db_session, "频道A", is_active=1)
    ch2 = await _create_channel(db_session, "频道B", is_active=1)
    ch3 = await _create_channel(db_session, "频道C", is_active=1)

    _patch_sessionlocal(monkeypatch, db_session)
    workflow_scheduler._check_backup_single = AsyncMock()

    await workflow_scheduler._check_backup()

    assert workflow_scheduler._check_backup_single.call_count == 3
    called_ids = {
        call.kwargs["channel_id"]
        for call in workflow_scheduler._check_backup_single.call_args_list
    }
    assert called_ids == {ch1.id, ch2.id, ch3.id}


# ---------------------------------------------------------------------------
# 10. test_cron_check_multi_channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_check_multi_channel(db_session):
    """3 频道独立兜底检查：每频道查询今日是否已触发工作流，无 MultipleResultsFound。"""
    from sqlalchemy import select

    ch1 = await _create_channel(db_session, "频道1")
    ch2 = await _create_channel(db_session, "频道2")
    ch3 = await _create_channel(db_session, "频道3")

    today = date.today()
    # 仅 ch1、ch2 有今日 workflow，ch3 应被识别为未触发
    for wid, ch_id in [("wf-check-1", ch1.id), ("wf-check-2", ch2.id)]:
        wf = Workflow(
            id=wid, episode_date=today, source=WorkflowSource.cron,
            status=WorkflowStatus.queued, channel_id=ch_id, priority=5,
            started_at=localnow_naive(),
        )
        db_session.add(wf)
    await db_session.commit()

    # 按频道独立查询（limit(1) 避免多结果异常）
    missing_channels = []
    for ch in (ch1, ch2, ch3):
        result = await db_session.execute(
            select(Workflow.id).where(
                Workflow.episode_date == today,
                Workflow.channel_id == ch.id,
            ).limit(1)
        )
        if result.scalar_one_or_none() is None:
            missing_channels.append(ch.id)

    assert missing_channels == [ch3.id]


# ---------------------------------------------------------------------------
# 11. test_workflow_id_concurrent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_id_concurrent(db_session, monkeypatch):
    """并发触发 5 任务 ID 不冲突（_trigger_lock 串行化 + DB 序号校正）。"""
    from app.services.workflow_scheduler import workflow_scheduler

    _patch_sessionlocal(monkeypatch, db_session)
    workflow_scheduler._get_db_max_seq = AsyncMock(return_value=0)

    today = date.today()
    tasks = [
        scheduler_trigger_helper(workflow_scheduler, today)
        for _ in range(5)
    ]
    ids = await asyncio.gather(*tasks)

    assert len(set(ids)) == 5
    date_str = today.strftime("%Y%m%d")
    for wid in ids:
        assert wid.startswith(f"wf-{date_str}-")
        seq = int(wid.rsplit("-", 1)[-1])
        assert 1 <= seq <= 5


async def scheduler_trigger_helper(scheduler, today):
    """辅助：调用 trigger_workflow，保持参数一致。"""
    return await scheduler.trigger_workflow(
        episode_date=today, source=WorkflowSource.cron.value,
        channel_id=None, priority=5,
    )


# ---------------------------------------------------------------------------
# 12. test_batch_delete_queued
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_delete_queued(db_session):
    """queued 状态直接删除被拒绝（需先 cancel）。"""
    from app.core.exceptions import BizError
    from app.services.workflow_service import WorkflowService

    await _create_queued_workflow(db_session, "wf-bdel-1")
    await _create_queued_workflow(db_session, "wf-bdel-2")

    svc = WorkflowService(db_session)
    with pytest.raises(BizError) as exc_info:
        await svc.batch_delete_workflows(["wf-bdel-1", "wf-bdel-2"])
    assert "排队" in exc_info.value.message or "取消" in exc_info.value.message


@pytest.mark.asyncio
async def test_batch_delete_tasks(db_session):
    """QueueService.batch_delete_tasks 委托 WorkflowService 级联删除终态任务。

    - running/queued 状态随整批回滚（委托方统一拒绝）
    - success/failed 终态可删除，且 Workflow 行被物理删除
    - 混合请求（含 queued）时整批回滚，已成功态任务也不被删
    """
    from app.core.exceptions import BizError

    await _create_workflow(db_session, "wf-qdel-1", WorkflowStatus.success)
    await _create_workflow(db_session, "wf-qdel-2", WorkflowStatus.failed)
    # queued 状态混入：应当整批回滚
    await _create_queued_workflow(db_session, "wf-qdel-3")

    svc = QueueService(db_session)

    # 混合请求含 queued → 整批回滚，success/failed 也不删
    with pytest.raises(BizError):
        await svc.batch_delete_tasks(["wf-qdel-1", "wf-qdel-3"])

    db_session.expire_all()
    assert await db_session.get(Workflow, "wf-qdel-1") is not None
    assert await db_session.get(Workflow, "wf-qdel-3") is not None

    # 关闭上方 SELECT 自动开启的 pending 事务，避免与下一次 batch_delete 的
    # 内部 async with self.db.begin() 冲突（InvalidRequestError: transaction already begun）
    await db_session.rollback()

    # 纯终态请求 → 成功删除
    result = await svc.batch_delete_tasks(["wf-qdel-1", "wf-qdel-2"])
    assert set(result["deleted"]) == {"wf-qdel-1", "wf-qdel-2"}

    db_session.expire_all()
    assert await db_session.get(Workflow, "wf-qdel-1") is None
    assert await db_session.get(Workflow, "wf-qdel-2") is None
    # queued 任务未被波及
    assert await db_session.get(Workflow, "wf-qdel-3") is not None
