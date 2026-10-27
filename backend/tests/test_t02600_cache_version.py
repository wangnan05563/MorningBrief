"""T02600：广告「生效投放」缓存的跨 worker 失效。

缺陷本体：`AdService.invalidate_active_cache()` 清的是 `app.cache.manager.cache`
这个**进程内** TTLCache 单例。`launcher.py:187` 在 `UVICORN_WORKERS>1` 时拆成
sched/api 两个角色进程（`_run_split_roles`），管理端进程停用了投放，播放进程
仍会命中自己的旧键，直到 `ACTIVE_PLACEMENT_TTL`（25h）到期——「停用」这个唯一的
可逆干预手段，对 C 端最长有一天不生效。

修法：缓存键带上存放在共享表 `system_flag` 里的版本号；任何进程的写操作与数据
同事务 bump 版本，所有进程的下一次读落到新键，旧键没人再读、随 TTL 自然淘汰。

本文件的用例分两层：
- 版本原语（默认 0、跨连接原子、回滚不跳）；
- 跨 worker 语义（两个独立 CacheManager + 两个独立连接读写同一个文件库，
  这是对「两个进程」的最小可信替身）。
"""
import asyncio
import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.cache.manager import CacheManager
from app.cache.manager import cache as shared_cache
from app.cache.version import AD_PLACEMENT_CACHE, bump_version, current_version, flag_key
from app.database import Base, normalize_metadata_for_sqlite
from app.models import AdMaterial, AdPlacement
from app.services.ad_service import (
    AdService,
    placement_cache_key,
)

# 与其它广告测试错开的日期（进程级单例缓存在 autouse fixture 里清，但日期仍旧错开）
TARGET = date(2026, 10, 1)
NAME = "t02600-专属版本名"


@pytest.fixture(autouse=True)
async def _clear_ad_cache():
    await shared_cache.delete_pattern("ad:placement:*")
    yield
    await shared_cache.delete_pattern("ad:placement:*")


async def _seed(db: AsyncSession):
    """一条素材 + 一条启用中的投放，覆盖 TARGET。"""
    m = AdMaterial(
        name="T02600素材", description="probe", file_url="http://cdn/t02600.mp3", duration=12
    )
    db.add(m)
    await db.commit()
    p = AdPlacement(
        material_id=m.id,
        position="head",
        start_date=TARGET,
        end_date=TARGET,
        enabled=1,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return m, p


# ---------------------------------------------------------------- 版本原语


@pytest.mark.asyncio
async def test_version_is_zero_before_any_write(db_session):
    """还没写过这类数据时版本读 0，而不是报错或 None。"""
    assert await current_version(db_session, NAME) == 0


@pytest.mark.asyncio
async def test_bump_returns_new_value_and_is_readable(db_session):
    assert await bump_version(db_session, NAME) == 1
    assert await current_version(db_session, NAME) == 1
    assert await bump_version(db_session, NAME) == 2
    assert await current_version(db_session, NAME) == 2


@pytest.mark.asyncio
async def test_rollback_leaves_version_unchanged(db_session):
    """bump 不自己 commit：事务回滚时版本必须一起回退。

    否则「写失败但版本跳了」会凭空打穿全端缓存；反过来「数据已提交、版本没跳」
    才是本单要防的那个跨 worker 窗口。
    """
    await bump_version(db_session, AD_PLACEMENT_CACHE)
    in_tx = await current_version(db_session, AD_PLACEMENT_CACHE)
    assert in_tx == 1, "同一事务里读不到自己刚 bump 的版本，说明 bump 与读取不在一个事务"
    await db_session.rollback()
    assert await current_version(db_session, AD_PLACEMENT_CACHE) == 0, (
        "回滚后版本被留下了，说明 bump 里藏了独立提交"
    )


@pytest.mark.asyncio
async def test_garbage_value_degrades_to_zero(db_session):
    """版本行被写成非 JSON 时读 0，而不是让每次投放读取 500。"""
    from app.models.system_flag import SystemFlag

    db_session.add(SystemFlag(key=flag_key(NAME), value="not-json"))
    await db_session.commit()
    assert await current_version(db_session, NAME) == 0


@pytest.mark.asyncio
async def test_bumps_from_two_connections_are_atomic(tmp_path: Path):
    """两个连接（= 两个进程的替身）并发 bump 不得互相覆盖。

    这是本单的命门：`UPDATE system_flag SET value=value+1` 在 SQLite 上不是
    原子的（读-改-写），必须走 `INSERT ... ON CONFLICT DO UPDATE` 一条语句。
    并发下丢更新的话，A 进程的 bump 被 B 覆盖 → 版本没跳 → C 端继续吃旧缓存。
    """
    normalize_metadata_for_sqlite()
    url = f"sqlite+aiosqlite:///{tmp_path / 't02600_concurrent.db'}"
    engines = [create_async_engine(url, echo=False) for _ in range(2)]
    for engine in engines:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _bump_twice(engine):
        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        for _ in range(5):
            async with maker() as session:
                await bump_version(session, AD_PLACEMENT_CACHE)
                await session.commit()

    try:
        await asyncio.gather(*[_bump_twice(e) for e in engines])
        maker = async_sessionmaker(engines[0], class_=AsyncSession, expire_on_commit=False)
        async with maker() as session:
            final = await current_version(session, AD_PLACEMENT_CACHE)
        assert final == 10, f"并发 bump 丢了更新：期望 10，实际 {final}"
    finally:
        for engine in engines:
            await engine.dispose()


# ---------------------------------------------------------------- 写入侧


@pytest.mark.asyncio
@pytest.mark.parametrize("op", ["create", "toggle_off", "toggle_on", "delete"])
async def test_every_placement_write_path_bumps(db_session, op):
    """四条写路径（新建/停用/启用/删除）都要跳版本，漏一条就是半个修复。"""
    svc = AdService(db_session)
    m, p = await _seed(db_session)
    before = await current_version(db_session, AD_PLACEMENT_CACHE)

    if op == "create":
        await svc.create_placement(
            material_id=m.id, position="tail", start_date=TARGET, end_date=TARGET
        )
    elif op == "toggle_off":
        await svc.set_placement_enabled(p.id, 0)
        await db_session.commit()
    elif op == "toggle_on":
        await svc.set_placement_enabled(p.id, 0)
        await db_session.commit()
        before = await current_version(db_session, AD_PLACEMENT_CACHE)
        await svc.set_placement_enabled(p.id, 1)
        await db_session.commit()
    else:
        await svc.delete_placement(p.id)

    after = await current_version(db_session, AD_PLACEMENT_CACHE)
    assert after > before, f"{op} 写了库却没跳版本，别的 worker 仍会命中旧键"


@pytest.mark.asyncio
async def test_rejected_write_does_not_bump(db_session):
    """被护栏拦下的写（同位重叠）不该跳版本——什么都没变，跳了是白白打穿全端缓存。"""
    from app.core.exceptions import BizError

    svc = AdService(db_session)
    m, _ = await _seed(db_session)  # head 已有一条启用中、覆盖 TARGET 的投放
    before = await current_version(db_session, AD_PLACEMENT_CACHE)

    with pytest.raises(BizError):
        await svc.create_placement(
            material_id=m.id, position="head", start_date=TARGET, end_date=TARGET
        )
    assert await current_version(db_session, AD_PLACEMENT_CACHE) == before
    await db_session.rollback()
    assert await current_version(db_session, AD_PLACEMENT_CACHE) == before


@pytest.mark.asyncio
async def test_bump_and_data_write_commit_together(db_session):
    """版本与数据在同一次提交里落库，不留「数据已改、版本未跳」的中间态。"""
    from app.models.system_flag import SystemFlag

    svc = AdService(db_session)
    m, _ = await _seed(db_session)
    await svc.create_placement(
        material_id=m.id, position="tail", start_date=TARGET, end_date=TARGET
    )
    # create_placement 内部提交后，同事务里应同时看到新投放与版本行
    row = (
        await db_session.execute(
            select(SystemFlag).where(SystemFlag.key == flag_key(AD_PLACEMENT_CACHE))
        )
    ).scalar_one()
    assert json.loads(row.value) >= 1
    assert row.updated_by, "版本行没记操作者，出问题查不到谁改的"


# ---------------------------------------------------------------- 读取侧


@pytest.mark.asyncio
async def test_read_key_follows_the_shared_version(db_session):
    svc = AdService(db_session)
    await _seed(db_session)

    first = await svc.get_active_placements(TARGET)
    v0 = await current_version(db_session, AD_PLACEMENT_CACHE)
    assert await shared_cache.get(placement_cache_key(v0, TARGET)) == first

    await bump_version(db_session, AD_PLACEMENT_CACHE)
    await db_session.commit()
    v1 = await current_version(db_session, AD_PLACEMENT_CACHE)
    assert v1 == v0 + 1
    assert await shared_cache.get(placement_cache_key(v1, TARGET)) is None, (
        "版本跳了却还读到旧键——说明读键没带版本号"
    )


@pytest.mark.asyncio
async def test_other_worker_sees_toggle_without_shared_memory(tmp_path: Path):
    """本单验收本体：worker B 停用并清了**自己**的缓存，worker A 下一次读必须不播。

    A/B 各持一个独立 `CacheManager`（进程内单例的替身）与一条独立连接，只共享
    同一个文件库。修复前 A 会命中自己的旧键，返回已停用素材，最长 25h。
    """
    normalize_metadata_for_sqlite()
    url = f"sqlite+aiosqlite:///{tmp_path / 't02600_workers.db'}"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with maker() as boot:
            await _seed(boot)

        # worker A 先读热自己的缓存
        async with maker() as session_a:
            cache_a = CacheManager()
            svc_a = AdService(session_a)
            svc_a.cache = cache_a
            warm = await svc_a.get_active_placements(TARGET)
            assert warm["head"] is not None, "A 预热后应拿到投放"
            warm_key = placement_cache_key(
                await current_version(session_a, AD_PLACEMENT_CACHE), TARGET
            )
            pid = (await session_a.execute(select(AdPlacement.id))).scalars().first()

        # worker B 走真实代码路径停用，并像路由那样只清本地缓存
        async with maker() as session_b:
            cache_b = CacheManager()
            svc_b = AdService(session_b)
            svc_b.cache = cache_b
            await svc_b.set_placement_enabled(pid, 0)
            await session_b.commit()
            await svc_b.invalidate_active_cache()

        # A 的进程内存里那份旧值谁也清不掉；只能靠版本号让它读不到
        assert await cache_a.get(warm_key) is not None, (
            "A 的旧键应仍留在它自己的进程内存里（这才叫跨进程）"
        )
        assert await cache_b.get(warm_key) is None, "B 至少要把自己那份清掉"
        async with maker() as session_a2:
            svc_a = AdService(session_a2)
            svc_a.cache = cache_a
            after = await svc_a.get_active_placements(TARGET)
            assert after["head"] is None, (
                f"B 停用后 A 仍在播旧素材：{after}（版本键没生效）"
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stale_key_is_never_served_back(db_session):
    """进程内存里残留的旧版本键，绝不能被后来的读命中（防「接错对象」：
    键算对了但取数时又退回按日期取）。
    """
    svc = AdService(db_session)
    await _seed(db_session)
    await svc.get_active_placements(TARGET)
    stale_key = placement_cache_key(await current_version(db_session, AD_PLACEMENT_CACHE), TARGET)
    # 把旧键里的值改脏，再跳版本：读到的必须是库里的真实结果，而不是脏值
    await shared_cache.set(stale_key, {"head": {"material_id": 999999}, "mid": None, "tail": None})
    await bump_version(db_session, AD_PLACEMENT_CACHE)
    await db_session.commit()

    result = await svc.get_active_placements(TARGET)
    assert result["head"]["material_id"] != 999999, "读到了上一个版本键里的脏缓存"


# ---------------------------------------------------------------- 端点与本地失效


@pytest.mark.asyncio
async def test_put_endpoint_bumps_shared_version(client, admin_token, db_session):
    """真实调用链（PUT /ads/placements/{id}）必须跳版本，而不只是清本进程缓存。

    管理端路由的提交发生在 `routers/admin/ads.py`，服务层只 flush + bump；
    如果哪天有人把 bump 从 `set_placement_enabled` 挪走，这条会红。
    """
    m, p = await _seed(db_session)
    before = await current_version(db_session, AD_PLACEMENT_CACHE)

    resp = client.put(
        f"/admin/api/v1/ads/placements/{p.id}",
        json={"enabled": 0},
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] == 0

    after = await current_version(db_session, AD_PLACEMENT_CACHE)
    assert after > before, "端点停用后没跳版本，播放进程要等 25h 才停"


@pytest.mark.asyncio
async def test_versioned_key_is_still_covered_by_local_delete_pattern(db_session):
    """键名加了版本前缀段后，`delete_pattern("ad:placement:*")` 必须还能清到它。

    `CacheManager.delete_pattern` 只支持末尾 `*` 前缀匹配；一旦有人把键前缀改了，
    本进程那句「提交后立刻清本地」会静默失效（虽然跨进程正确性还在，
    但每个进程都白回源一次）。
    """
    svc = AdService(db_session)
    await _seed(db_session)
    await svc.get_active_placements(TARGET)
    warmed = [k for k in shared_cache._cache.keys() if k.startswith("ad:placement:")]
    assert warmed, "预热后应有 ad:placement: 前缀的键"

    await svc.invalidate_active_cache()
    assert not [k for k in shared_cache._cache.keys() if k.startswith("ad:placement:")]
