"""讲书稿模式与素材池服务（T00656）。

职责：
1. **模式开关**（幂等）：`script_mode='book_pool'` = 讲书稿模式——忽略频道书源、改从素材池取书。
   开启时对 `rss_sources` / `book_rss_sources` 做**快照并清空**（关闭时按快照恢复），
   真正的采集隔离由 crawler 的 `script_mode` 分支保证（见 `workflow/crawler/runner.py`）。
2. **素材池管理**：增删、去重（按 material_id）、排序（sort_index 升序即取书顺序）。
3. **按天顺序取书**：`pick_next_book` 依 `interval_days`（1=每日/N=每 N 天）+ `cursor`
   （上次已取位置）+ `loop`（末尾循环/停止）决定本次该生成哪本书；**只读不推进**。
4. **进度推进**：`mark_published` 在**节目发布成功后**推进游标（失败不推进，避免丢书）；
   `reset_progress` 从头开始。

设计取舍：
- 进度/调度状态放在 `channel` 表（与频道生命周期一致），池项单独建表（一本书一条，可跨频道复用）；
- 池项冗余书名/作者/分类/封面快照，素材被改名或删除后池列表仍可读；
- `pick_next_book` 不写库（生成链路可能重试，写库应发生在确定的成功点）。
"""
from __future__ import annotations

import json
import logging
from datetime import date

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel, Material
from app.models.book_pool import BookPoolItem
from app.models.material import MaterialStatus

logger = logging.getLogger(__name__)

MODE_BOOK_POOL = "book_pool"
# 视为常规模式的取值（历史上该列可能为空串或 'channel'）
MODE_CHANNEL = "channel"


# --------------------------------------------------------------------------
# 模式开关（含书源快照/恢复，幂等）
# --------------------------------------------------------------------------

async def get_state(db: AsyncSession, channel_id: int) -> dict:
    """讲书稿模式状态（前端开关 + 进度展示）。"""
    ch = (await db.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    if ch is None:
        return {"exists": False}
    total = (await db.execute(
        select(func.count(BookPoolItem.id)).where(BookPoolItem.channel_id == channel_id)
    )).scalar() or 0
    return {
        "exists": True,
        "enabled": (ch.script_mode or "") == MODE_BOOK_POOL,
        "mode": ch.script_mode or MODE_CHANNEL,
        "pool_total": int(total),
        "cursor": int(ch.book_pool_cursor or 0),
        "interval_days": int(ch.book_pool_interval_days or 1),
        "loop": bool(ch.book_pool_loop),
        "last_run_date": ch.book_pool_last_run_date,
        "last_title": ch.book_pool_last_title,
        "sources_snapshot_saved": bool(ch.rss_sources_snapshot is not None or ch.book_rss_sources_snapshot is not None),
        "rss_sources": _loads(ch.rss_sources),
        "book_rss_sources": _loads(ch.book_rss_sources),
    }


async def set_script_mode(db: AsyncSession, channel_id: int, enabled: bool) -> dict:
    """切换讲书稿模式（幂等）。

    - 由关到开：**首次**进入时快照并清空频道书源；重复开启不覆盖快照、不清空二次；
    - 由开到关：按快照恢复频道书源，并清空快照列。

    Returns:
        {"changed": bool, "enabled": bool, "message": str, ...状态字段}
    """
    ch = (await db.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    if ch is None:
        raise ValueError(f"频道 {channel_id} 不存在")

    currently_on = (ch.script_mode or "") == MODE_BOOK_POOL
    if enabled == currently_on:
        state = await get_state(db, channel_id)
        return {"changed": False, **state,
                "message": "已处于讲书稿模式，无需重复操作" if enabled else "当前为常规模式（频道书源）"}

    if enabled:
        # 首次进入：快照 + 清空（保留原始 JSON 文本，便于原样恢复）
        ch.rss_sources_snapshot = ch.rss_sources if ch.rss_sources is not None else "[]"
        ch.book_rss_sources_snapshot = ch.book_rss_sources if ch.book_rss_sources is not None else "[]"
        ch.rss_sources = "[]"
        ch.book_rss_sources = "[]"
        ch.script_mode = MODE_BOOK_POOL
        message = "已开启讲书稿模式：已清除频道书源（快照已保存），当前内容来自素材库"
    else:
        # 关闭：按快照恢复
        if ch.rss_sources_snapshot is not None:
            ch.rss_sources = ch.rss_sources_snapshot
        if ch.book_rss_sources_snapshot is not None:
            ch.book_rss_sources = ch.book_rss_sources_snapshot
        ch.rss_sources_snapshot = None
        ch.book_rss_sources_snapshot = None
        ch.script_mode = MODE_CHANNEL
        message = "已关闭讲书稿模式：频道书源已按快照恢复"

    await db.commit()
    logger.info("[book_pool] 频道 %s 讲书稿模式 → %s", channel_id, "开启" if enabled else "关闭")
    state = await get_state(db, channel_id)
    return {"changed": True, **state, "message": message}


async def update_schedule(
    db: AsyncSession,
    channel_id: int,
    interval_days: int | None = None,
    loop: bool | None = None,
) -> dict:
    """更新取书调度参数（间隔天数 / 末尾是否循环）。"""
    ch = (await db.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    if ch is None:
        raise ValueError(f"频道 {channel_id} 不存在")
    if interval_days is not None:
        ch.book_pool_interval_days = max(1, int(interval_days))
    if loop is not None:
        ch.book_pool_loop = 1 if loop else 0
    await db.commit()
    return await get_state(db, channel_id)


# --------------------------------------------------------------------------
# 素材池 CRUD
# --------------------------------------------------------------------------

async def list_pool(db: AsyncSession, channel_id: int) -> list[dict]:
    """池内书单（按 sort_index 升序 = 取书顺序）。"""
    rows = (await db.execute(
        select(BookPoolItem)
        .where(BookPoolItem.channel_id == channel_id)
        .order_by(BookPoolItem.sort_index.asc(), BookPoolItem.id.asc())
    )).scalars().all()
    return [_item_to_dict(r) for r in rows]


async def add_books(db: AsyncSession, channel_id: int, material_ids: list[int]) -> dict:
    """把素材库中的书加入池（末尾追加；已存在的跳过——幂等）。"""
    if not material_ids:
        return {"added": 0, "skipped": 0, "message": "未选择书籍"}
    mats = (await db.execute(
        select(Material).where(Material.id.in_(material_ids))
    )).scalars().all()
    found = {m.id: m for m in mats}
    missing = [mid for mid in material_ids if mid not in found]

    existing_ids = set((await db.execute(
        select(BookPoolItem.material_id).where(BookPoolItem.channel_id == channel_id)
    )).scalars().all())

    next_sort = (await db.execute(
        select(func.coalesce(func.max(BookPoolItem.sort_index), -1)).where(BookPoolItem.channel_id == channel_id)
    )).scalar()
    next_sort = int(next_sort if next_sort is not None else -1) + 1

    added = 0
    for mid in material_ids:
        m = found.get(mid)
        if m is None or mid in existing_ids:
            continue
        db.add(BookPoolItem(
            channel_id=channel_id,
            material_id=mid,
            title=(m.title or f"素材 {mid}")[:256],
            author=None,
            category=m.category,
            cover_url=m.cover_url,
            sort_index=next_sort,
        ))
        next_sort += 1
        added += 1
    await db.commit()
    skipped = len(material_ids) - added
    msg = f"已加入 {added} 本" + (f"，跳过 {skipped} 本（重复或不存在）" if skipped else "")
    if missing:
        msg += f"；{len(missing)} 个素材不存在"
    return {"added": added, "skipped": skipped, "message": msg}


async def remove_item(db: AsyncSession, channel_id: int, item_id: int) -> bool:
    """从池中移除（不影响素材库本身）。移除后重排 sort_index 保持连续。"""
    row = (await db.execute(
        select(BookPoolItem).where(BookPoolItem.id == item_id, BookPoolItem.channel_id == channel_id)
    )).scalar_one_or_none()
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    await _resequence(db, channel_id)
    return True


async def reorder(db: AsyncSession, channel_id: int, item_ids: list[int]) -> int:
    """按给定 id 顺序重排（未列出的项保持相对顺序追加在后）。"""
    rows = (await db.execute(
        select(BookPoolItem).where(BookPoolItem.channel_id == channel_id)
        .order_by(BookPoolItem.sort_index.asc(), BookPoolItem.id.asc())
    )).scalars().all()
    if not rows:
        return 0
    by_id = {r.id: r for r in rows}
    ordered = [by_id[i] for i in item_ids if i in by_id]
    ordered += [r for r in rows if r.id not in set(item_ids)]
    for idx, r in enumerate(ordered):
        r.sort_index = idx
    await db.commit()
    return len(ordered)


async def move_item(db: AsyncSession, channel_id: int, item_id: int, direction: str) -> bool:
    """上移/下移一格（direction: 'up'|'down'）。"""
    rows = (await db.execute(
        select(BookPoolItem).where(BookPoolItem.channel_id == channel_id)
        .order_by(BookPoolItem.sort_index.asc(), BookPoolItem.id.asc())
    )).scalars().all()
    idx = next((i for i, r in enumerate(rows) if r.id == item_id), None)
    if idx is None:
        return False
    target = idx - 1 if direction == "up" else idx + 1
    if target < 0 or target >= len(rows):
        return False
    rows[idx].sort_index, rows[target].sort_index = rows[target].sort_index, rows[idx].sort_index
    await db.commit()
    await _resequence(db, channel_id)
    return True


async def _resequence(db: AsyncSession, channel_id: int) -> None:
    """把 sort_index 压实为 0..N-1（移除/移动后调用，保证游标语义稳定）。"""
    rows = (await db.execute(
        select(BookPoolItem).where(BookPoolItem.channel_id == channel_id)
        .order_by(BookPoolItem.sort_index.asc(), BookPoolItem.id.asc())
    )).scalars().all()
    for idx, r in enumerate(rows):
        if r.sort_index != idx:
            r.sort_index = idx
    await db.commit()


# --------------------------------------------------------------------------
# 按天顺序取书（只读）
# --------------------------------------------------------------------------

async def pick_next_book(db: AsyncSession, channel_id: int, today: date | None = None) -> dict:
    """决定本次该生成哪本书（**只读**，不推进进度）。

    Returns:
        {"status": "ok", "item": {...}, "cursor": n, "total": m}
        {"status": "empty"}       —— 池为空
        {"status": "exhausted"}   —— 已到末尾且未开启循环
        {"status": "not_due", "last_run_date": ..., "next_due_date": ...} —— 间隔未到
        {"status": "missing"}     —— 频道不存在
    """
    today = today or date.today()
    ch = (await db.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    if ch is None:
        return {"status": "missing"}

    rows = (await db.execute(
        select(BookPoolItem).where(BookPoolItem.channel_id == channel_id)
        .order_by(BookPoolItem.sort_index.asc(), BookPoolItem.id.asc())
    )).scalars().all()
    if not rows:
        return {"status": "empty"}

    # 间隔节流：last_run_date 存在且未满 interval_days 则本次跳过
    interval = max(1, int(ch.book_pool_interval_days or 1))
    if ch.book_pool_last_run_date:
        try:
            last = date.fromisoformat(ch.book_pool_last_run_date)
            elapsed = (today - last).days
            if elapsed < interval:
                from datetime import timedelta
                return {
                    "status": "not_due",
                    "last_run_date": ch.book_pool_last_run_date,
                    "next_due_date": (last + timedelta(days=interval)).isoformat(),
                    "interval_days": interval,
                }
        except ValueError:
            logger.warning("book_pool_last_run_date 解析失败: %s", ch.book_pool_last_run_date)

    cursor = int(ch.book_pool_cursor or 0)
    if cursor >= len(rows):
        if ch.book_pool_loop:
            cursor = 0
        else:
            return {"status": "exhausted", "cursor": cursor, "total": len(rows)}

    item = rows[cursor]
    return {"status": "ok", "item": _item_to_dict(item), "cursor": cursor, "total": len(rows)}


async def mark_published(db: AsyncSession, channel_id: int, title: str, today: date | None = None) -> dict:
    """节目发布成功后推进进度（游标 +1；到末尾且开启循环则归零）。"""
    today = today or date.today()
    ch = (await db.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    if ch is None:
        return {"advanced": False, "reason": "channel_not_found"}
    total = (await db.execute(
        select(func.count(BookPoolItem.id)).where(BookPoolItem.channel_id == channel_id)
    )).scalar() or 0
    cursor = int(ch.book_pool_cursor or 0) + 1
    if total and cursor >= total:
        cursor = 0 if ch.book_pool_loop else total
    ch.book_pool_cursor = cursor
    ch.book_pool_last_run_date = today.isoformat()
    ch.book_pool_last_title = (title or "")[:256]
    await db.commit()
    logger.info("[book_pool] 频道 %s 进度推进 → cursor=%s / total=%s（刚发布《%s》）", channel_id, cursor, total, title)
    return {"advanced": True, "cursor": cursor, "total": int(total)}


async def reset_progress(db: AsyncSession, channel_id: int) -> dict:
    """重置进度：从头开始（保留池与排序）。"""
    ch = (await db.execute(select(Channel).where(Channel.id == channel_id))).scalar_one_or_none()
    if ch is None:
        raise ValueError(f"频道 {channel_id} 不存在")
    ch.book_pool_cursor = 0
    ch.book_pool_last_run_date = None
    ch.book_pool_last_title = None
    await db.commit()
    return await get_state(db, channel_id)


async def list_candidates(
    db: AsyncSession, channel_id: int | None = None, keyword: str | None = None,
    page: int = 1, size: int = 20,
) -> dict:
    """可选书候选（来自素材库）：默认列出本频道素材，可按关键词过滤已排除池内已有的书。"""
    stmt = select(Material)
    if channel_id is not None:
        stmt = stmt.where(Material.channel_id == channel_id)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(Material.title.like(like))
    total = (await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar() or 0
    rows = (await db.execute(
        stmt.order_by(Material.id.desc()).offset((max(1, page) - 1) * size).limit(size)
    )).scalars().all()
    in_pool: set[int] = set()
    if channel_id is not None:
        in_pool = set((await db.execute(
            select(BookPoolItem.material_id).where(BookPoolItem.channel_id == channel_id)
        )).scalars().all())
    return {
        "total": int(total),
        "items": [
            {
                "material_id": m.id,
                "title": m.title,
                "category": m.category,
                "source": m.source,
                "source_type": m.source_type,
                "status": m.status,
                "cover_url": m.cover_url,
                "in_pool": m.id in in_pool,
            }
            for m in rows
        ],
    }


# --------------------------------------------------------------------------
# 内部工具
# --------------------------------------------------------------------------

def _item_to_dict(r: BookPoolItem) -> dict:
    return {
        "id": r.id,
        "channel_id": r.channel_id,
        "material_id": r.material_id,
        "title": r.title,
        "author": r.author,
        "category": r.category,
        "cover_url": r.cover_url,
        "sort_index": r.sort_index,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _loads(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        logger.warning("频道书源字段不是合法 JSON，按空列表处理: %s", str(raw)[:60])
        return []


async def collect_book_materials(db: AsyncSession, channel_id: int, item: dict) -> list[Material]:
    """取"该书"待消费的章节素材。

    关联规则（不新增外键、不改素材模型）：
    1. 池项绑定的那条素材本身；
    2. **同一来源（`Material.source`）**在该频道的其余 pending 素材——上传 EPUB 时若把
       「来源」填成书名（规范推荐），即可自动聚合全书章节，按 id 升序（解析顺序）返回。

    Returns:
        待消费素材列表（可能为空：书尚未上传书稿）
    """
    src = (await db.execute(
        select(Material.source).where(Material.id == item["material_id"])
    )).scalar()
    conds = [Material.id == item["material_id"]]
    if src:
        conds.append(Material.source == src)
    rows = (await db.execute(
        select(Material).where(
            Material.channel_id == channel_id,
            Material.status == MaterialStatus.pending.value,
            or_(*conds),
        ).order_by(Material.id.asc())
    )).scalars().all()
    return list(rows)


async def clear_progress_state(db: AsyncSession, channel_id: int) -> None:
    """清空进度相关状态（测试/运维用：池被清空后归零）。"""
    await db.execute(delete(BookPoolItem).where(BookPoolItem.channel_id == channel_id))
    await db.commit()
