"""广告服务测试。

覆盖 services/ad_service.py：
- create_material / list_materials：素材创建与分页列表
- create_placement：投放规则创建（含校验）
- get_active_placements：查询某日有效投放
- get_schedule：按月查询排期
"""
from datetime import date

import pytest
from sqlalchemy import select

from app.cache.manager import cache as cache_manager
from app.core.exceptions import BizError
from app.models import AdMaterial, AdPlacement
from app.services.ad_service import AdService


async def _create_material(db, name="测试素材", duration=15):
    """辅助：创建一条广告素材。"""
    m = AdMaterial(
        name=name,
        description="测试描述",
        file_url=f"http://cdn/{name}.mp4",
        duration=duration,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest.mark.asyncio
async def test_create_material(db_session):
    """create_material 返回素材 id，DB 中能查到。"""
    svc = AdService(db_session)
    mid = await svc.create_material(
        name="新品广告",
        description="夏季新品",
        file_url="http://cdn/new.mp4",
        duration=30,
    )
    assert mid > 0

    res = await db_session.execute(select(AdMaterial).where(AdMaterial.id == mid))
    m = res.scalar_one()
    assert m.name == "新品广告"
    assert m.duration == 30


@pytest.mark.asyncio
async def test_list_materials_pagination(db_session):
    """list_materials 分页：total 与每页条数正确。"""
    for i in range(5):
        await _create_material(db_session, name=f"素材{i}")

    svc = AdService(db_session)
    page1 = await svc.list_materials(page=1, size=2)
    assert page1["total"] == 5
    assert len(page1["list"]) == 2

    page3 = await svc.list_materials(page=3, size=2)
    assert len(page3["list"]) == 1


@pytest.mark.asyncio
async def test_list_materials_empty(db_session):
    """无素材时返回空列表。"""
    svc = AdService(db_session)
    result = await svc.list_materials(page=1, size=10)
    assert result == {"total": 0, "list": []}


@pytest.mark.asyncio
async def test_create_placement_success(db_session):
    """create_placement 校验通过后创建投放记录。"""
    m = await _create_material(db_session)

    svc = AdService(db_session)
    pid = await svc.create_placement(
        material_id=m.id,
        position="head",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
    )
    assert pid > 0

    res = await db_session.execute(select(AdPlacement).where(AdPlacement.id == pid))
    p = res.scalar_one()
    assert p.material_id == m.id
    assert p.position == "head"


@pytest.mark.asyncio
async def test_create_placement_invalid_material(db_session):
    """素材不存在时 create_placement 抛 BizError。"""
    svc = AdService(db_session)
    with pytest.raises(BizError) as exc_info:
        await svc.create_placement(
            material_id=99999,
            position="head",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
        )
    assert "素材不存在" in exc_info.value.message


@pytest.mark.asyncio
async def test_create_placement_invalid_position(db_session):
    """非法广告位抛 BizError。"""
    m = await _create_material(db_session)
    svc = AdService(db_session)
    with pytest.raises(BizError) as exc_info:
        await svc.create_placement(
            material_id=m.id,
            position="invalid-pos",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
        )
    assert "非法广告位" in exc_info.value.message


@pytest.mark.asyncio
async def test_create_placement_invalid_date_range(db_session):
    """start_date >= end_date 时抛 BizError。"""
    m = await _create_material(db_session)
    svc = AdService(db_session)
    with pytest.raises(BizError):
        await svc.create_placement(
            material_id=m.id,
            position="head",
            start_date=date(2026, 7, 31),
            end_date=date(2026, 7, 1),
        )


@pytest.mark.asyncio
async def test_get_active_placements(db_session):
    """查询某天生效的投放：只返回区间覆盖目标日期的投放。"""
    m = await _create_material(db_session)

    # 投放 1：7 月有效
    db_session.add(AdPlacement(
        material_id=m.id, position="head",
        start_date=date(2026, 7, 1), end_date=date(2026, 7, 31),
    ))
    # 投放 2：8 月有效（不应被查出）
    db_session.add(AdPlacement(
        material_id=m.id, position="mid",
        start_date=date(2026, 8, 1), end_date=date(2026, 8, 31),
    ))
    # 投放 3：tail 7 月有效
    db_session.add(AdPlacement(
        material_id=m.id, position="tail",
        start_date=date(2026, 7, 15), end_date=date(2026, 7, 20),
    ))
    await db_session.commit()

    svc = AdService(db_session)
    result = await svc.get_active_placements(date(2026, 7, 16))

    # head 与 tail 命中，mid 为 None
    assert result["head"] is not None
    assert result["mid"] is None
    assert result["tail"] is not None
    assert result["head"]["material_id"] == m.id


@pytest.mark.asyncio
async def test_get_active_placements_cache(db_session):
    """get_active_placements cache-aside：第二次从缓存返回。"""
    m = await _create_material(db_session)
    db_session.add(AdPlacement(
        material_id=m.id, position="head",
        start_date=date(2026, 7, 1), end_date=date(2026, 7, 31),
    ))
    await db_session.commit()

    svc = AdService(db_session)
    target = date(2026, 7, 10)

    # 第一次 miss
    r1 = await svc.get_active_placements(target)
    assert r1["head"] is not None

    # 缓存 key 应存在：get 返回非 None 即表示命中
    cache_key = f"ad:placement:{target.isoformat()}"
    assert await cache_manager.get(cache_key) is not None

    # 第二次 hit（即使删 DB 数据也返回缓存）
    res = await db_session.execute(select(AdPlacement))
    await db_session.delete(res.scalars().first())
    await db_session.commit()
    r2 = await svc.get_active_placements(target)
    assert r2["head"] is not None


@pytest.mark.asyncio
async def test_get_schedule(db_session):
    """get_schedule 返回与该月有重叠的投放。"""
    m = await _create_material(db_session)

    # 与 7 月有重叠
    db_session.add(AdPlacement(
        material_id=m.id, position="head",
        start_date=date(2026, 6, 25), end_date=date(2026, 7, 5),
    ))
    # 完全在 7 月内
    db_session.add(AdPlacement(
        material_id=m.id, position="mid",
        start_date=date(2026, 7, 10), end_date=date(2026, 7, 20),
    ))
    # 与 7 月无重叠（8 月）
    db_session.add(AdPlacement(
        material_id=m.id, position="tail",
        start_date=date(2026, 8, 1), end_date=date(2026, 8, 10),
    ))
    await db_session.commit()

    svc = AdService(db_session)
    result = await svc.get_schedule("2026-07")
    # 2 条与 7 月重叠
    assert len(result["placements"]) == 2
