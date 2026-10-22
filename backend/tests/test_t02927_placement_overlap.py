"""T02927（M2 / D24 派生）：投放重叠裁决与 C 端选播确定性。

裁决：同一广告位、同一时段只允许一条**启用中**的投放。
- 新建时同位区间相交 → 拒绝，错误里点名冲突对象的 id / 素材名 / 区间；
- 重新启用同样校验（否则「两条都停用再依次启用」即可绕过）；
- 停用的投放不参与冲突判定：「先停用旧的再建新的」是运营唯一的可逆替换路径。

确定性的另一半：`get_active_placements` 必须稳定排序。历史脏数据里仍可能
存在同位同日多条，修复前没有 ORDER BY，dict 后写覆盖 → 播哪条由执行计划
决定，且这个不确定结果会被缓存 25h。
"""
from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.exceptions import BizError
from app.models import AdMaterial, AdPlacement
from app.services.ad_service import AdService

TARGET = date(2026, 11, 10)
OTHER = date(2026, 11, 11)


async def _material(db, name="重叠测试素材"):
    m = AdMaterial(
        name=name,
        description="t02927",
        file_url=f"http://cdn/{name}.mp3",
        duration=15,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _placement(db, material_id, position="head", start=TARGET, end=OTHER, enabled=1):
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


async def _count_placements(db) -> int:
    return (await db.execute(select(func.count(AdPlacement.id)))).scalar() or 0


@pytest.mark.asyncio
async def test_create_rejects_overlap_and_names_conflict(db_session):
    """同位区间相交：第二次插入被拒，错误点名素材与区间，且库里没有第二条。"""
    mat_a = await _material(db_session, "品牌广告A")
    mat_b = await _material(db_session, "新品广告B")

    svc = AdService(db_session)
    first_id = await svc.create_placement(
        material_id=mat_a.id,
        position="head",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 30),
    )

    with pytest.raises(BizError) as ei:
        await svc.create_placement(
            material_id=mat_b.id,
            position="head",
            start_date=date(2026, 11, 15),
            end_date=date(2026, 12, 15),
        )

    err = ei.value
    assert err.code == 400
    # 人读消息必须点名冲突素材与区间，而不是一句「保存失败」
    assert "品牌广告A" in err.message
    assert "2026-11-01" in err.message and "2026-11-30" in err.message
    assert err.data["errors"][0]["field"] == "dateRange"
    conflict = err.data["conflicts"][0]
    assert conflict["id"] == first_id
    assert conflict["material_name"] == "品牌广告A"
    assert conflict["start_date"] == "2026-11-01"
    assert conflict["end_date"] == "2026-11-30"

    # 断言打 DB：被拒的那条不能已经写进去
    assert await _count_placements(db_session) == 1


@pytest.mark.asyncio
async def test_adjacent_dates_are_not_overlap(db_session):
    """闭区间首尾相接（7/5 结束、7/6 开始）不算重叠，两条都能建。"""
    mat = await _material(db_session)
    svc = AdService(db_session)

    await svc.create_placement(
        material_id=mat.id,
        position="head",
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 5),
    )
    await svc.create_placement(
        material_id=mat.id,
        position="head",
        start_date=date(2026, 12, 6),
        end_date=date(2026, 12, 10),
    )
    assert await _count_placements(db_session) == 2


@pytest.mark.asyncio
async def test_different_positions_may_overlap(db_session):
    """不同广告位互不冲突：头/中/尾本就各播各的。"""
    mat = await _material(db_session)
    svc = AdService(db_session)

    await svc.create_placement(
        material_id=mat.id,
        position="head",
        start_date=TARGET,
        end_date=OTHER,
    )
    await svc.create_placement(
        material_id=mat.id,
        position="mid",
        start_date=TARGET,
        end_date=OTHER,
    )
    assert await _count_placements(db_session) == 2


@pytest.mark.asyncio
async def test_single_day_overlap_rejected(db_session):
    """单日投放也按闭区间判重叠：同一天两条仍会争同一个位置。"""
    mat = await _material(db_session)
    svc = AdService(db_session)

    await svc.create_placement(
        material_id=mat.id,
        position="tail",
        start_date=TARGET,
        end_date=TARGET,
    )
    with pytest.raises(BizError) as ei:
        await svc.create_placement(
            material_id=mat.id,
            position="tail",
            start_date=TARGET,
            end_date=TARGET,
        )
    assert "已有启用中的投放" in ei.value.message
    assert await _count_placements(db_session) == 1


@pytest.mark.asyncio
async def test_disabled_overlap_allowed_but_reenable_blocked(db_session):
    """停用不参与冲突判定；但把旧的重启必须被拦下，否则护栏可绕过。"""
    mat_a = await _material(db_session, "旧广告")
    mat_b = await _material(db_session, "新广告")
    svc = AdService(db_session)

    old = await _placement(
        db_session, mat_a.id, "head",
        start=date(2026, 12, 1), end=date(2026, 12, 31),
    )
    await svc.set_placement_enabled(old.id, 0)
    await db_session.commit()

    # 旧投放停用后，同位同区间的新投放可以建（可逆替换路径）
    new_id = await svc.create_placement(
        material_id=mat_b.id,
        position="head",
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 31),
    )
    assert new_id > 0

    # 想把旧的重新启用 → 与新的冲突，必须拒绝且不能改库
    with pytest.raises(BizError) as ei:
        await svc.set_placement_enabled(old.id, 1)
    assert "新广告" in ei.value.message
    assert ei.value.data["errors"][0]["field"] == "enabled"
    assert ei.value.data["conflicts"][0]["id"] == new_id

    await db_session.refresh(old)
    assert old.enabled == 0

    # 不存在重叠时重启必须成功（防止 exclude_id 漏掉、自己和自己冲突）
    lonely = await _placement(
        db_session, mat_a.id, "mid",
        start=date(2027, 1, 1), end=date(2027, 1, 5), enabled=0,
    )
    result = await svc.set_placement_enabled(lonely.id, 1)
    assert result["enabled"] == 1
    await db_session.refresh(lonely)
    assert lonely.enabled == 1

    # 已启用态再发一次启用（幂等重试/接口直连）不能被自身拦下
    result = await svc.set_placement_enabled(lonely.id, 1)
    assert result["enabled"] == 1


@pytest.mark.asyncio
async def test_active_placements_deterministic_with_legacy_overlap(db_session):
    """历史脏数据同位同日多条：两次独立查询结果必须一致（最新创建的那条生效）。"""
    mat_a = await _material(db_session, "历史A")
    mat_b = await _material(db_session, "历史B")

    # 绕过服务层直接写库，模拟本次修复前已经存在的重叠数据
    await _placement(db_session, mat_a.id, "head", start=TARGET, end=TARGET)
    latest = await _placement(db_session, mat_b.id, "head", start=TARGET, end=TARGET)

    svc = AdService(db_session)
    first = await svc.get_active_placements(TARGET)
    # 清掉 cache-aside 后重新查库，避免第二条断言只是读到同一个缓存对象
    await svc.invalidate_active_cache()
    second = await svc.get_active_placements(TARGET)

    assert first == second
    assert first["head"]["material_id"] == latest.id
    assert first["mid"] is None and first["tail"] is None


@pytest.mark.asyncio
async def test_http_create_overlap_returns_field_error_and_conflicts(client, admin_token, db_session):
    """接口直连同样拦得住：HTTP 200 信封 code=400，带字段级明细与冲突列表。"""
    mat_a = await _material(db_session, "接口素材A")
    mat_b = await _material(db_session, "接口素材B")
    svc = AdService(db_session)
    existing_id = await svc.create_placement(
        material_id=mat_a.id,
        position="head",
        start_date=date(2027, 2, 1),
        end_date=date(2027, 2, 28),
    )

    resp = client.post(
        "/admin/api/v1/ads/placements",
        json={
            "material_id": mat_b.id,
            "position": "head",
            "start_date": "2027-02-10",
            "end_date": "2027-03-10",
        },
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 400
    assert body["data"]["errors"][0]["field"] == "dateRange"
    assert body["data"]["conflicts"][0]["id"] == existing_id
    assert body["data"]["conflicts"][0]["material_name"] == "接口素材A"

    assert await _count_placements(db_session) == 1


@pytest.mark.asyncio
async def test_http_reenable_overlap_rejected_and_db_unchanged(client, admin_token, db_session):
    """PUT 启用与新建同口径：冲突时拒绝，DB 里仍是停用。"""
    mat_a = await _material(db_session, "在投广告")
    mat_b = await _material(db_session, "待启用广告")

    active = await _placement(
        db_session, mat_a.id, "tail",
        start=date(2027, 3, 1), end=date(2027, 3, 31),
    )
    paused = await _placement(
        db_session, mat_b.id, "tail",
        start=date(2027, 3, 10), end=date(2027, 3, 20), enabled=0,
    )

    resp = client.put(
        f"/admin/api/v1/ads/placements/{paused.id}",
        json={"enabled": 1},
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 400
    assert body["data"]["conflicts"][0]["id"] == active.id
    assert "在投广告" in body["message"]

    res = await db_session.execute(select(AdPlacement).where(AdPlacement.id == paused.id))
    assert res.scalar_one().enabled == 0
