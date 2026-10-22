"""T02602：投放状态按「开关 + 日期闭区间」派生四态。

缺陷：列表与移动端 badge 只看 enabled，12 月排期、过期一个月的投放都显示
「投放中」，与 C 端 get_active_placements（enabled==1 且今天在闭区间内）不一致。
本文件钉住：
1. 四态派生与边界（开始/结束当天都算生效中）；
2. 停用优先于日期态；
3. 列表 status 与 get_active_placements 的取数口径一致；
4. 排期接口同样下发 status；
5. HTTP 层列表/排期/启停都回传服务端派生的 status。
"""
from calendar import monthrange
from datetime import date, timedelta

import pytest

from app.cache.manager import cache as cache_manager
from app.models import AdMaterial, AdPlacement
from app.services.ad_service import (
    PLACEMENT_ACTIVE,
    PLACEMENT_DISABLED,
    PLACEMENT_EXPIRED,
    PLACEMENT_PENDING,
    AdService,
    derive_placement_status,
)

TODAY = date.today()


@pytest.fixture(autouse=True)
async def _clear_ad_cache():
    """生效投放缓存是进程级单例，前后都清，避免跨用例串味。"""
    await cache_manager.delete_pattern("ad:placement:*")
    yield
    await cache_manager.delete_pattern("ad:placement:*")


def _month_range(offset: int) -> tuple[str, date, date]:
    """返回相对当前月 offset 个月的 (YYYY-MM, 首日, 末日)。"""
    idx = TODAY.year * 12 + (TODAY.month - 1) + offset
    year, month0 = divmod(idx, 12)
    month = month0 + 1
    last = monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}", date(year, month, 1), date(year, month, last)


async def _material(db, name):
    m = AdMaterial(name=name, description="t02602", file_url=f"http://cdn/{name}.mp3", duration=15)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _placement(db, material_id, position, start, end, enabled=1):
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


@pytest.mark.parametrize(
    ("enabled", "start", "end", "expected"),
    [
        # 闭区间：开始日、结束日当天都算生效中（与 get_active_placements 一致）
        (1, TODAY, TODAY, PLACEMENT_ACTIVE),
        (1, TODAY - timedelta(days=3), TODAY, PLACEMENT_ACTIVE),
        (1, TODAY, TODAY + timedelta(days=3), PLACEMENT_ACTIVE),
        (1, TODAY + timedelta(days=1), TODAY + timedelta(days=5), PLACEMENT_PENDING),
        (1, TODAY - timedelta(days=5), TODAY - timedelta(days=1), PLACEMENT_EXPIRED),
        # 停用优先：开关是显式干预，先显示这一个
        (0, TODAY, TODAY, PLACEMENT_DISABLED),
        (0, TODAY + timedelta(days=1), TODAY + timedelta(days=5), PLACEMENT_DISABLED),
        (0, TODAY - timedelta(days=5), TODAY - timedelta(days=1), PLACEMENT_DISABLED),
        (None, TODAY, TODAY, PLACEMENT_ACTIVE),
    ],
)
def test_derive_status_four_states_and_boundaries(enabled, start, end, expected):
    assert derive_placement_status(enabled, start, end, TODAY) == expected


@pytest.mark.asyncio
async def test_list_status_matches_active_placements(db_session):
    """列表四态与 C 端真实播放同口径：只有 active 才会被 get_active_placements 取到。"""
    m_active = await _material(db_session, "生效中素材")
    m_pending = await _material(db_session, "待投放素材")
    m_expired = await _material(db_session, "已过期素材")
    m_disabled = await _material(db_session, "已停用素材")

    p_active = await _placement(db_session, m_active.id, "head", TODAY - timedelta(days=1), TODAY + timedelta(days=1))
    p_pending = await _placement(db_session, m_pending.id, "mid", TODAY + timedelta(days=1), TODAY + timedelta(days=5))
    p_expired = await _placement(db_session, m_expired.id, "tail", TODAY - timedelta(days=5), TODAY - timedelta(days=1))
    p_disabled = await _placement(db_session, m_disabled.id, "head", TODAY - timedelta(days=1), TODAY + timedelta(days=1), enabled=0)

    svc = AdService(db_session)
    data = await svc.list_placements(page=1, size=20)
    by_id = {item["id"]: item for item in data["list"]}

    assert by_id[p_active.id]["status"] == PLACEMENT_ACTIVE
    assert by_id[p_pending.id]["status"] == PLACEMENT_PENDING
    assert by_id[p_expired.id]["status"] == PLACEMENT_EXPIRED
    assert by_id[p_disabled.id]["status"] == PLACEMENT_DISABLED

    playing = await svc.get_active_placements(TODAY)
    for item in data["list"]:
        slot = playing.get(item["position"])
        actually_playing = slot is not None and slot["material_id"] == item["material_id"]
        assert (item["status"] == PLACEMENT_ACTIVE) == actually_playing, (
            f"{item['material_name']} 状态 {item['status']} 与真实播放 {actually_playing} 不一致"
        )


@pytest.mark.asyncio
async def test_schedule_exposes_status_for_current_past_and_future_months(db_session):
    current_month, cur_start, cur_end = _month_range(0)
    next_month, next_start, next_end = _month_range(1)
    prev_month, prev_start, prev_end = _month_range(-1)

    m1 = await _material(db_session, "本月生效")
    m2 = await _material(db_session, "本月停用")
    m3 = await _material(db_session, "下月待投放")
    m4 = await _material(db_session, "上月已过期")

    p_active = await _placement(db_session, m1.id, "head", cur_start, cur_end)
    p_disabled = await _placement(db_session, m2.id, "mid", cur_start, cur_end, enabled=0)
    p_pending = await _placement(db_session, m3.id, "tail", next_start, next_end)
    p_expired = await _placement(db_session, m4.id, "tail", prev_start, prev_end)

    svc = AdService(db_session)
    current = {p["id"]: p for p in (await svc.get_schedule(current_month))["placements"]}
    assert current[p_active.id]["status"] == PLACEMENT_ACTIVE
    assert current[p_disabled.id]["status"] == PLACEMENT_DISABLED

    future = {p["id"]: p for p in (await svc.get_schedule(next_month))["placements"]}
    assert future[p_pending.id]["status"] == PLACEMENT_PENDING

    past = {p["id"]: p for p in (await svc.get_schedule(prev_month))["placements"]}
    assert past[p_expired.id]["status"] == PLACEMENT_EXPIRED


@pytest.mark.asyncio
async def test_http_list_schedule_and_toggle_return_status(client, admin_token, db_session):
    m = await _material(db_session, "HTTP 投放")
    p = await _placement(db_session, m.id, "head", TODAY - timedelta(days=1), TODAY + timedelta(days=1))
    headers = {"Authorization": f"Bearer {admin_token['token']}"}

    resp = client.get("/admin/api/v1/ads/placements", headers=headers)
    assert resp.status_code == 200
    item = next(i for i in resp.json()["data"]["list"] if i["id"] == p.id)
    assert item["status"] == PLACEMENT_ACTIVE

    resp = client.get(
        "/admin/api/v1/ads/schedule",
        params={"month": f"{TODAY.year:04d}-{TODAY.month:02d}"},
        headers=headers,
    )
    assert resp.status_code == 200
    scheduled = next(i for i in resp.json()["data"]["placements"] if i["id"] == p.id)
    assert scheduled["status"] == PLACEMENT_ACTIVE

    # 启停响应带服务端派生状态：前端直接落位，不自行按 enabled 推算
    resp = client.put(f"/admin/api/v1/ads/placements/{p.id}", json={"enabled": 0}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == PLACEMENT_DISABLED
    resp = client.put(f"/admin/api/v1/ads/placements/{p.id}", json={"enabled": 1}, headers=headers)
    assert resp.json()["data"]["status"] == PLACEMENT_ACTIVE
