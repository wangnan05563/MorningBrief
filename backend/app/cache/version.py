"""跨进程缓存版本号（T02600）。

问题：`app.cache.manager` 的 TTLCache 是**进程内**单例，写操作后的 `delete_pattern`
只能清当前 worker 的键。`UVICORN_WORKERS>1`（以及 launcher 的 sched/api 角色分裂）时，
落在 A 进程的「停用广告」对 B 进程不可见，生效投放缓存最长 25h 才自愈
（`ACTIVE_PLACEMENT_TTL`），表现成「同一个广告有时停得掉、有时停不掉」的随机失效。

做法：把「这批数据是第几版」放进所有进程都看得见的 `system_flag` 表，读方用版本号拼缓存键。
版本一跳，旧键立刻没人读、新键必然 miss 并回库——不需要跨进程通知，也不会重新引入
「并发读把旧数据写回缓存」那个老坑：写回用的仍是那次读到的版本键，新版本不认它。

成本与取舍：
- 读路径多一条单行 SELECT。生效投放只在音频拼接与取数时读，QPS 极低，可以接受。
- **不做进程内 memo**：memo 只是把「立刻生效」换成「最多滞后 memo TTL」，正是本单要消掉的窗口。
- bump 与数据写**同一个事务**提交（调用方 commit 之前 bump）：分开提交会留下
  「数据已改、版本未跳」的窗口，等于没修；回滚时版本也不该跳（由用例钉住）。
"""
import json
from typing import Optional

from sqlalchemy import Integer, Text, cast, func, select
from sqlalchemy.dialects import sqlite as sqlite_dialect

from app.models.system_flag import SystemFlag

KEY_PREFIX = "cache_version:"
# 生效投放（ad:placement:*）——本单要修的这一类
AD_PLACEMENT_CACHE = "ad_placement"


def flag_key(name: str) -> str:
    return f"{KEY_PREFIX}{name}"


def _parse(raw: Optional[str]) -> int:
    if raw is None or raw == "":
        return 0
    try:
        return int(json.loads(raw))
    except (TypeError, ValueError):
        # 脏值不能让读路径炸掉，也不能悄悄当 0（那会和「没人写过」撞键）——退回 0 但键仍可读
        return 0


async def current_version(db, name: str) -> int:
    """读当前版本号；行不存在（还没写过这类数据）时为 0。"""
    raw = (
        await db.execute(select(SystemFlag.value).where(SystemFlag.key == flag_key(name)))
    ).scalar_one_or_none()
    return _parse(raw)


async def bump_version(db, name: str, *, updated_by: str = "system") -> int:
    """原子地把版本 +1，返回新值。**不 commit**：由调用方与数据写同事务提交。

    为什么不用「读出来 +1 再写回」：两个并发写各自读到 7、各写回 8，版本只跳了一格，
    第三次的「跳版」被吃掉——旧键还会被另一个进程继续读，正是本单要消掉的窗口。
    这里让 SQLite 在 UPSERT 的 DO UPDATE 里自己算 `旧值 + 1`，单次写语句完成。
    """
    stmt = (
        sqlite_dialect.insert(SystemFlag)
        .values(key=flag_key(name), value=json.dumps(1), updated_by=updated_by)
        .on_conflict_do_update(
            index_elements=["key"],
            set_={
                "value": cast(cast(func.json_extract(SystemFlag.value, "$"), Integer) + 1, Text),
                "updated_at": func.now(),
                "updated_by": updated_by,
            },
        )
    )
    await db.execute(stmt)
    return await current_version(db, name)
