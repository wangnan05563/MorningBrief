"""系统清理长任务编排（T02799 / FR-UX-702）。

执行模型：POST 只落一条任务记录并立刻返回 `task_id`，真正的清理在后台协程里跑；
前端用 `GET /maintenance/tasks/{id}` 看状态，不再挂着一条 300s 的请求。

几个必须写死的原因：
1. **独立会话**：请求结束后 FastAPI 会关掉注入的 session，后台任务必须自己开一个，
   否则拿到的是已关闭会话（表现为 `This session is provisioning a new connection` 或静默不落库）。
   会话工厂从请求 session 的 bind 派生，测试覆盖 get_db 时后台任务也写进同一个测试库。
2. **active_key 去重**：同一目标（如 `database:vacuum`）在执行中重复提交直接合并到原任务，
   不再靠文案劝阻——用户点第二次本来就是「怕没生效」。
3. **陈旧任务回收**：进程被杀时 active_key 会永久占位。超过 `STALE_TASK_SECONDS` 的活跃任务
   视为中断（VACUUM 在分钟级，30 分钟仍未结束只能是异常），提交时顺手标记 failed 再放行。
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.timeutil import localnow_naive
from app.models.maintenance_task import MaintenanceTask, MaintenanceTaskState
from app.services.maintenance_service import MaintenanceService

logger = logging.getLogger(__name__)

ACTIVE_STATES = (MaintenanceTaskState.queued.value, MaintenanceTaskState.running.value)
# 超过这个时长仍在「执行中」的任务视为进程中断遗留（VACUUM 是分钟级）
STALE_TASK_SECONDS = 1800

# keep-alive：asyncio 只持弱引用，不显式保存会被 GC 掉
_RUNNING: dict[str, asyncio.Task] = {}


def _active_key(category: str, target: str) -> str:
    return f"{category}:{target}"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def _elapsed_ms(row: MaintenanceTask, now: datetime | None = None) -> int | None:
    """已耗时：执行中按 now-started_at 实时算，结束后用落库值。"""
    if row.elapsed_ms is not None:
        return row.elapsed_ms
    if row.started_at is None:
        return None
    return int(((now or localnow_naive()) - row.started_at).total_seconds() * 1000)


def serialize(row: MaintenanceTask) -> dict:
    """任务对外视图：前端只认这几个字段，不暴露 active_key 这类内部去重键。"""
    return {
        "task_id": row.id,
        "category": row.category,
        "target": row.target,
        "state": row.state,
        "admin_name": row.admin_name,
        "created_at": _iso(row.created_at),
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "elapsed_ms": _elapsed_ms(row),
        "result": json.loads(row.result) if row.result else None,
        "error": row.error,
    }


async def get_task(db: AsyncSession, task_id: str) -> MaintenanceTask | None:
    return await db.get(MaintenanceTask, task_id)


async def _reclaim_stale(db: AsyncSession, row: MaintenanceTask) -> bool:
    """把陈旧活跃任务标记 failed 并释放 active_key；返回是否真的回收了。"""
    age = (localnow_naive() - (row.created_at or localnow_naive())).total_seconds()
    if age < STALE_TASK_SECONDS:
        return False
    row.state = MaintenanceTaskState.failed.value
    row.error = f"任务超过 {STALE_TASK_SECONDS // 60} 分钟没有结束，判定为进程中断"
    row.active_key = None
    row.finished_at = localnow_naive()
    row.elapsed_ms = _elapsed_ms(row)
    await db.commit()
    logger.warning("[maintenance] 回收陈旧任务 %s %s", row.id, row.error)
    return True


async def submit(
    db: AsyncSession,
    *,
    category: str,
    target: str,
    params: dict,
    admin_name: str,
) -> dict:
    """提交后台清理任务；同目标进行中时合并到已有任务。

    返回 serialized 视图 + `merged` 标记（前端据此提示「已在执行，正在跟踪同一任务」）。
    """
    key = _active_key(category, target)
    existing = (
        await db.execute(select(MaintenanceTask).where(MaintenanceTask.active_key == key))
    ).scalar_one_or_none()
    if existing is not None and not await _reclaim_stale(db, existing):
        return {**serialize(existing), "merged": True}

    # AsyncSession.get_bind() 返回的是同步 Engine，不能喂 return async_sessionmaker；
    # `.bind` 才是建池时的 AsyncEngine（见 database.py 的 AsyncSessionLocal）
    bind = db.bind
    row = MaintenanceTask(
        id=uuid.uuid4().hex,
        category=category,
        target=target,
        active_key=key,
        state=MaintenanceTaskState.queued.value,
        admin_name=admin_name or "",
        params=json.dumps(params, ensure_ascii=False),
        created_at=localnow_naive(),
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        # 两个请求同时通过了上面的查询：唯一索引兜底，合并到先落库的那条
        await db.rollback()
        winner = (
            await db.execute(select(MaintenanceTask).where(MaintenanceTask.active_key == key))
        ).scalar_one_or_none()
        if winner is None:
            raise
        return {**serialize(winner), "merged": True}

    await db.refresh(row)
    _launch(row.id, category, target, params, admin_name, bind)
    return {**serialize(row), "merged": False}


def _launch(task_id, category, target, params, admin_name, bind) -> None:
    """把协程挂到当前事件循环。测试里可直接 await `_RUNNING[task_id]` 等待终态。"""
    factory = async_sessionmaker(bind=bind, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    task = asyncio.create_task(
        _execute(task_id, category, target, params, admin_name, factory),
        name=f"maintenance-task-{task_id}",
    )
    _RUNNING[task_id] = task
    task.add_done_callback(lambda _t: _RUNNING.pop(task_id, None))


def _dispatch(
    svc: MaintenanceService, category: str, target: str, params: dict, admin_name: str
):
    """按分类调用服务层；任务后台一律 dry_run=False（预览走同步路径）。"""
    if category == "database":
        return svc.cleanup_database(
            target=target,
            days=int(params.get("days") or 0),
            dry_run=False,
            admin_name=admin_name,
        )
    if category == "logs":
        return svc.cleanup_logs(
            target=target,
            days=int(params.get("days") or 0),
            dry_run=False,
            admin_name=admin_name,
        )
    if category == "cache":
        return svc.cleanup_cache(
            target=target or "pycache",
            dry_run=False,
            admin_name=admin_name,
        )
    if category == "workflow_chain":
        return svc.cleanup_workflow_chain(
            workflow_id=target,
            dry_run=False,
            admin_name=admin_name,
        )
    raise ValueError(f"未知的清理分类：{category}")


async def _execute(task_id, category, target, params, admin_name, factory) -> None:
    async with factory() as db:
        row = await db.get(MaintenanceTask, task_id)
        if row is None:  # 被手工清掉了，没有可回写的行
            return
        row.state = MaintenanceTaskState.running.value
        row.started_at = localnow_naive()
        await db.commit()

        try:
            svc = MaintenanceService(db)
            result = await _dispatch(svc, category, target, params, admin_name)
            row.state = MaintenanceTaskState.succeeded.value
            row.result = json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:  # noqa: BLE001 —— 任务失败必须落库，前端才看得见原因
            logger.exception("[maintenance] 任务 %s 执行失败", task_id)
            row.state = MaintenanceTaskState.failed.value
            row.error = str(e) or e.__class__.__name__
        finally:
            row.finished_at = localnow_naive()
            row.elapsed_ms = _elapsed_ms(row)
            row.active_key = None  # 释放去重位，允许下一次提交
            await db.commit()
