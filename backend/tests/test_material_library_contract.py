"""素材库管理页的接口契约测试（T00775）。

背景一：B 端「素材库管理」页曾按 `data.items` 取列表，而 `GET /admin/api/v1/materials`
返回的是 `{ total, list }` —— 取错键导致页面列表恒为空（「从素材库加入书籍」里能看到书，
点「管理素材」跳过去却查不到）。本测试把「响应体必须带 list 键」锁成契约，
后端若改键名会在此失败，而不是静默让前端列表变空。

背景二（T00775 遗留建议实施）：列表新增 `material_id` / `source` 精确过滤（深链定位与
按书聚合下钻用），并新增 `GET /admin/api/v1/materials/aggregate` 按书聚合视图。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_material_library_contract.py
"""
from datetime import date

import pytest

from app.models import Channel, Material
from app.models.material import MaterialStatus

_LIST_URL = "/admin/api/v1/materials"
_AGG_URL = "/admin/api/v1/materials/aggregate"


async def _seed_channel(db_session, name: str) -> Channel:
    ch = Channel(name=name, channel_type="audiobook", selection_strategy="outline")
    db_session.add(ch)
    await db_session.commit()
    await db_session.refresh(ch)
    return ch


async def _seed_material(db_session, channel_id: int, source: str, title: str, status: str = "pending") -> Material:
    m = Material(
        source=source, source_type="list", title=title, content="正文" * 20,
        url=f"https://example.com/t00775/{channel_id}/{title}", status=status,
        channel_id=channel_id, crawled_at=date.today(),
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    return m


@pytest.mark.asyncio
async def test_list_materials_returns_list_key(db_session, client, admin_token):
    """素材列表响应必须含 `list`（且不含易混淆的 `items` 键）。"""
    hdrs = {"Authorization": f"Bearer {admin_token['token']}"}
    ch = await _seed_channel(db_session, "T00775 频道")
    for t in ("我只知道人是什么 · 第一章", "我只知道人是什么 · 第二章"):
        await _seed_material(db_session, ch.id, "我只知道人是什么", t)

    r = client.get(_LIST_URL, params={"channel_id": ch.id}, headers=hdrs).json()
    assert r["code"] == 0, r
    assert "list" in r["data"], f"素材列表必须返回 list 键，实际键：{sorted(r['data'])}"
    assert "items" not in r["data"], "不应返回 items 键（避免前端取错键静默空列表）"
    assert r["data"]["total"] == 2
    assert len(r["data"]["list"]) == 2
    # 列表项需带素材库管理页表格渲染所需字段
    row = r["data"]["list"][0]
    for field in ("id", "title", "source", "status", "crawled_at"):
        assert field in row, f"列表项缺少字段 {field}"


class TestExactFiltersT00775:
    """material_id / source 精确过滤（深链定位与聚合下钻）。"""

    @pytest.mark.asyncio
    async def test_material_id_exact(self, db_session, client, admin_token):
        hdrs = {"Authorization": f"Bearer {admin_token['token']}"}
        ch = await _seed_channel(db_session, "T00775 精确过滤")
        m1 = await _seed_material(db_session, ch.id, "我只知道人是什么", "我只知道人是什么 · 第一章")
        await _seed_material(db_session, ch.id, "我只知道人是什么", "我只知道人是什么 · 第二章")

        r = client.get(_LIST_URL, params={"channel_id": ch.id, "material_id": m1.id}, headers=hdrs).json()
        assert r["code"] == 0, r
        assert r["data"]["total"] == 1
        assert [x["id"] for x in r["data"]["list"]] == [m1.id]

    @pytest.mark.asyncio
    async def test_source_exact_not_like(self, db_session, client, admin_token):
        """source 为精确等值：书名含 % / _ 也按字面匹配，不会被当成 LIKE 通配符。"""
        hdrs = {"Authorization": f"Bearer {admin_token['token']}"}
        ch = await _seed_channel(db_session, "T00775 通配符")
        await _seed_material(db_session, ch.id, "100%纯干货", "100%纯干货 · 第一章")
        await _seed_material(db_session, ch.id, "100abc纯干货", "100abc纯干货 · 第一章")
        await _seed_material(db_session, ch.id, "别的书", "别的书 · 第一章")

        r = client.get(_LIST_URL, params={"channel_id": ch.id, "source": "100%纯干货"}, headers=hdrs).json()
        assert r["code"] == 0, r
        assert r["data"]["total"] == 1, "source 精确过滤不应把 % 当通配符"
        assert r["data"]["list"][0]["source"] == "100%纯干货"


class TestAggregateByBookT00775:
    """按书聚合视图：一行一本书（章节数 / 待消费数 / 书名过滤）。"""

    @pytest.mark.asyncio
    async def test_aggregate_groups_by_source(self, db_session, client, admin_token):
        hdrs = {"Authorization": f"Bearer {admin_token['token']}"}
        ch = await _seed_channel(db_session, "T00775 聚合")
        for t in ("第一章", "第二章", "第三章"):
            await _seed_material(db_session, ch.id, "我只知道人是什么", f"我只知道人是什么 · {t}")
        await _seed_material(
            db_session, ch.id, "活着", "活着 · 序", status=MaterialStatus.selected.value,
        )

        r = client.get(_AGG_URL, params={"channel_id": ch.id}, headers=hdrs).json()
        assert r["code"] == 0, r
        assert r["data"]["total"] == 2, "应按来源聚合为 2 本书"
        by_src = {x["source"]: x for x in r["data"]["list"]}
        assert by_src["我只知道人是什么"]["chapters"] == 3
        assert by_src["我只知道人是什么"]["pending_chapters"] == 3
        assert by_src["活着"]["chapters"] == 1
        assert by_src["活着"]["pending_chapters"] == 0, "已选题章节不计入待消费"
        assert by_src["我只知道人是什么"]["sample_material_id"]

    @pytest.mark.asyncio
    async def test_aggregate_keyword_and_status(self, db_session, client, admin_token):
        hdrs = {"Authorization": f"Bearer {admin_token['token']}"}
        ch = await _seed_channel(db_session, "T00775 聚合过滤")
        await _seed_material(db_session, ch.id, "我只知道人是什么", "我只知道人是什么 · 第一章")
        await _seed_material(db_session, ch.id, "活着", "活着 · 序")

        r1 = client.get(_AGG_URL, params={"channel_id": ch.id, "keyword": "活着"}, headers=hdrs).json()
        assert [x["source"] for x in r1["data"]["list"]] == ["活着"]

        r2 = client.get(_AGG_URL, params={"channel_id": ch.id, "status": "selected"}, headers=hdrs).json()
        assert r2["data"]["total"] == 0, "无 selected 素材时应为空"

        r3 = client.get(_AGG_URL, params={"channel_id": ch.id}, headers=hdrs).json()
        assert r3["data"]["total"] == 2

