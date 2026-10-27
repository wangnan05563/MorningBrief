"""T02491（FR-UX-203）广告启停修复的断言。

覆盖「停用即不播」的三环：
1. get_active_placements 按 enabled 过滤；
2. 启停写库后必须失效 ad:placement:* 缓存（否则 25h TTL 让停用等到次日）；
3. PUT /ads/placements/{id} 对不存在的 id 返回业务 404，而不是 error() 未导入造成的 500。
"""
from datetime import date

import pytest
from sqlalchemy import select

from app.cache.manager import cache as cache_manager
from app.cache.version import AD_PLACEMENT_CACHE, current_version
from app.models import AdMaterial, AdPlacement
from app.services.ad_service import AdService, placement_cache_key

# 与其它广告测试错开的日期，避免共享进程内 TTLCache 相互污染
TARGET = date(2026, 9, 15)
OTHER = date(2026, 9, 16)


async def _warm_key(db, target):
    """取「此刻正在被读」的缓存键（T02600 后键名带共享版本号）。

    必须在写入/停用**之前**求值并留存：写操作会把版本跳上去，事后再算键名
    得到的是新键，旧键是否被清掉就查不出来了——那正是本文件要防的事。
    """
    return placement_cache_key(await current_version(db, AD_PLACEMENT_CACHE), target)


async def _material(db, name="启停测试素材"):
    m = AdMaterial(name=name, description="t02491", file_url=f"http://cdn/{name}.mp4", duration=15)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _placement(db, material_id, position="head", *, start=TARGET, end=TARGET, enabled=1):
    p = AdPlacement(
        material_id=material_id,
        position=position,
        start_date=start,
        end_date=end,
        enabled=enabled,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest.fixture(autouse=True)
async def _clear_ad_cache():
    """缓存是进程级单例：用例前后都清干净，防止跨用例串味。"""
    await cache_manager.delete_pattern("ad:placement:*")
    yield
    await cache_manager.delete_pattern("ad:placement:*")


@pytest.mark.asyncio
async def test_active_placements_filter_disabled(db_session):
    m = await _material(db_session)
    await _placement(db_session, m.id, "head", enabled=1)
    await _placement(db_session, m.id, position="mid", enabled=0)

    svc = AdService(db_session)
    result = await svc.get_active_placements(TARGET)
    assert result["head"] is not None
    # 停用位不再下发（修复前：enabled=0 照样返回，开关形同虚设）
    assert result["mid"] is None


@pytest.mark.asyncio
async def test_toggle_effective_immediately_after_cache_invalidation(db_session):
    """停用后重新查询必须立刻不播——依赖失效缓存，否则命中 25h 旧缓存。"""
    m = await _material(db_session)
    p = await _placement(db_session, m.id)

    svc = AdService(db_session)
    assert (await svc.get_active_placements(TARGET))["head"] is not None
    warm_key = await _warm_key(db_session, TARGET)
    assert await cache_manager.get(warm_key) is not None

    await svc.set_placement_enabled(p.id, 0)
    await db_session.commit()
    await svc.invalidate_active_cache()

    assert await cache_manager.get(warm_key) is None
    assert (await svc.get_active_placements(TARGET))["head"] is None

    # 重新启用后恢复播放（可逆）
    await svc.set_placement_enabled(p.id, 1)
    await db_session.commit()
    await svc.invalidate_active_cache()
    assert (await svc.get_active_placements(TARGET))["head"] is not None


@pytest.mark.asyncio
async def test_invalidate_active_cache_clears_all_dates(db_session):
    m = await _material(db_session)
    await _placement(db_session, m.id, start=TARGET, end=OTHER)

    svc = AdService(db_session)
    await svc.get_active_placements(TARGET)
    await svc.get_active_placements(OTHER)
    target_key = await _warm_key(db_session, TARGET)
    other_key = await _warm_key(db_session, OTHER)
    assert await cache_manager.get(target_key) is not None
    assert await cache_manager.get(other_key) is not None

    await svc.invalidate_active_cache()
    assert await cache_manager.get(target_key) is None
    assert await cache_manager.get(other_key) is None


@pytest.mark.asyncio
async def test_delete_placement_invalidates_cache(db_session):
    """删除投放同样要失效缓存，否则 C 端继续播已删除的素材。"""
    m = await _material(db_session)
    p = await _placement(db_session, m.id)

    svc = AdService(db_session)
    await svc.get_active_placements(TARGET)
    warm_key = await _warm_key(db_session, TARGET)
    await svc.delete_placement(p.id)
    assert await cache_manager.get(warm_key) is None
    res = await db_session.execute(select(AdPlacement).where(AdPlacement.id == p.id))
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_update_placement_missing_id_returns_business_404(client, admin_token):
    """修复前 ads.py 未导入 error()，走异常分支时 NameError → 500。"""
    resp = client.put(
        "/admin/api/v1/ads/placements/999999",
        json={"enabled": 0},
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 404
    assert "投放不存在" in body["message"]


@pytest.mark.asyncio
async def test_update_placement_endpoint_toggles_and_clears_cache(client, admin_token, db_session):
    m = await _material(db_session)
    p = await _placement(db_session, m.id)

    svc = AdService(db_session)
    await svc.get_active_placements(TARGET)
    warm_key = await _warm_key(db_session, TARGET)
    assert await cache_manager.get(warm_key) is not None

    resp = client.put(
        f"/admin/api/v1/ads/placements/{p.id}",
        json={"enabled": 0},
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] == 0

    # 路由提交后失效缓存：停用即时生效
    assert await cache_manager.get(warm_key) is None
    assert (await svc.get_active_placements(TARGET))["head"] is None


@pytest.mark.asyncio
async def test_update_placement_rejects_invalid_enabled(client, admin_token, db_session):
    m = await _material(db_session)
    p = await _placement(db_session, m.id)
    resp = client.put(
        f"/admin/api/v1/ads/placements/{p.id}",
        json={"enabled": 7},
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    assert resp.status_code == 400
    res = await db_session.execute(select(AdPlacement).where(AdPlacement.id == p.id))
    assert res.scalar_one().enabled == 1
