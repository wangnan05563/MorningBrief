"""讲书稿模式与素材池服务测试（T00656）。

覆盖：
- 模式开关：幂等（重复开启/关闭无副作用）、开启时**快照并清空**频道书源、关闭时**按快照恢复**；
- 素材池：加入（去重幂等）、移除（重排）、上移/下移、批量重排；
- 取书与进度：空池/正常/到末尾停止/开启循环归零/间隔未到；发布后推进；重置；
- 章节聚合：同来源素材按 id 升序纳入（上传时「来源」填书名即可聚合全书章节）。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_book_pool_service.py
"""
import json
from datetime import date, timedelta

import pytest

from app.models import Channel, Material
from app.models.material import MaterialStatus
from app.services import book_pool_service as svc


async def _seed_channel(session, name="听书频道", rss='["人民网-国内"]', book_rss='["豆瓣读书-最新书评"]') -> Channel:
    ch = Channel(
        name=name, channel_type="audiobook", selection_strategy="outline",
        rss_sources=rss, book_rss_sources=book_rss,
    )
    session.add(ch)
    await session.commit()
    await session.refresh(ch)
    return ch


async def _seed_book(session, channel_id: int, title: str, source: str = "文档上传") -> Material:
    m = Material(
        source=source, source_type="list", title=title, content="正文" * 20,
        url=f"https://example.com/{channel_id}/{title}", status=MaterialStatus.pending.value,
        channel_id=channel_id, crawled_at=date.today(),
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


class TestScriptMode:
    @pytest.mark.asyncio
    async def test_enable_snapshots_and_clears_sources(self, db_session):
        ch = await _seed_channel(db_session)
        res = await svc.set_script_mode(db_session, ch.id, True)
        assert res["changed"] is True and res["enabled"] is True
        assert "已清除频道书源" in res["message"]

        await db_session.refresh(ch)
        assert ch.script_mode == "book_pool"
        assert json.loads(ch.rss_sources) == [] and json.loads(ch.book_rss_sources) == []
        # 快照保留原始配置，供关闭时恢复
        assert json.loads(ch.rss_sources_snapshot) == ["人民网-国内"]
        assert json.loads(ch.book_rss_sources_snapshot) == ["豆瓣读书-最新书评"]

    @pytest.mark.asyncio
    async def test_enable_twice_is_idempotent(self, db_session):
        ch = await _seed_channel(db_session)
        await svc.set_script_mode(db_session, ch.id, True)
        # 二次开启：不改快照、不重复清空
        res2 = await svc.set_script_mode(db_session, ch.id, True)
        assert res2["changed"] is False
        assert "已处于讲书稿模式" in res2["message"]
        await db_session.refresh(ch)
        assert json.loads(ch.rss_sources_snapshot) == ["人民网-国内"]

    @pytest.mark.asyncio
    async def test_disable_restores_sources(self, db_session):
        ch = await _seed_channel(db_session)
        await svc.set_script_mode(db_session, ch.id, True)
        res = await svc.set_script_mode(db_session, ch.id, False)
        assert res["changed"] is True and res["enabled"] is False
        assert "已按快照恢复" in res["message"]
        await db_session.refresh(ch)
        assert json.loads(ch.rss_sources) == ["人民网-国内"]
        assert json.loads(ch.book_rss_sources) == ["豆瓣读书-最新书评"]
        assert ch.rss_sources_snapshot is None and ch.book_rss_sources_snapshot is None

    @pytest.mark.asyncio
    async def test_disable_twice_is_idempotent(self, db_session):
        ch = await _seed_channel(db_session)
        res = await svc.set_script_mode(db_session, ch.id, False)
        assert res["changed"] is False and res["enabled"] is False


class TestPoolCrud:
    @pytest.mark.asyncio
    async def test_add_books_appends_and_dedupes(self, db_session):
        ch = await _seed_channel(db_session)
        b1 = await _seed_book(db_session, ch.id, "我只知道人是什么")
        b2 = await _seed_book(db_session, ch.id, "活着")

        r1 = await svc.add_books(db_session, ch.id, [b1.id, b2.id])
        assert r1["added"] == 2
        # 重复加入幂等：全部跳过
        r2 = await svc.add_books(db_session, ch.id, [b1.id, b2.id])
        assert r2["added"] == 0 and r2["skipped"] == 2

        items = await svc.list_pool(db_session, ch.id)
        assert [i["sort_index"] for i in items] == [0, 1], "顺序即加入顺序"

    @pytest.mark.asyncio
    async def test_add_missing_material_reported(self, db_session):
        ch = await _seed_channel(db_session)
        res = await svc.add_books(db_session, ch.id, [99999])
        assert res["added"] == 0 and "不存在" in res["message"]

    @pytest.mark.asyncio
    async def test_move_and_reorder(self, db_session):
        ch = await _seed_channel(db_session)
        mats = [await _seed_book(db_session, ch.id, f"书{i}") for i in range(1, 4)]
        await svc.add_books(db_session, ch.id, [m.id for m in mats])
        items = await svc.list_pool(db_session, ch.id)

        # 第三项上移一格 → 顺序 1,3,2
        assert await svc.move_item(db_session, ch.id, items[2]["id"], "up") is True
        titles = [i["title"] for i in await svc.list_pool(db_session, ch.id)]
        assert titles == ["书1", "书3", "书2"]
        # 首位再上移：无变化（边界）
        first = (await svc.list_pool(db_session, ch.id))[0]
        assert await svc.move_item(db_session, ch.id, first["id"], "up") is False

        # 批量重排为 2,1,3
        by_title = {i["title"]: i["id"] for i in await svc.list_pool(db_session, ch.id)}
        await svc.reorder(db_session, ch.id, [by_title["书2"], by_title["书1"], by_title["书3"]])
        assert [i["title"] for i in await svc.list_pool(db_session, ch.id)] == ["书2", "书1", "书3"]

    @pytest.mark.asyncio
    async def test_remove_resequences(self, db_session):
        ch = await _seed_channel(db_session)
        mats = [await _seed_book(db_session, ch.id, f"书{i}") for i in range(1, 4)]
        await svc.add_books(db_session, ch.id, [m.id for m in mats])
        items = await svc.list_pool(db_session, ch.id)
        assert await svc.remove_item(db_session, ch.id, items[0]["id"]) is True
        rest = await svc.list_pool(db_session, ch.id)
        assert [i["sort_index"] for i in rest] == [0, 1], "移除后应压实排序"
        assert await svc.remove_item(db_session, ch.id, 99999) is False


class TestPickAndProgress:
    @pytest.mark.asyncio
    async def test_empty_pool(self, db_session):
        ch = await _seed_channel(db_session)
        assert (await svc.pick_next_book(db_session, ch.id))["status"] == "empty"

    @pytest.mark.asyncio
    async def test_sequential_pick_and_advance(self, db_session):
        ch = await _seed_channel(db_session)
        mats = [await _seed_book(db_session, ch.id, f"书{i}") for i in range(1, 4)]
        await svc.add_books(db_session, ch.id, [m.id for m in mats])

        today = date(2026, 9, 17)
        pick = await svc.pick_next_book(db_session, ch.id, today)
        assert pick["status"] == "ok" and pick["item"]["title"] == "书1" and pick["cursor"] == 0

        # 发布后推进（同日不触发间隔节流：interval=1 时同日 <1 天 → not_due）
        await svc.mark_published(db_session, ch.id, "书1", today)
        assert (await svc.pick_next_book(db_session, ch.id, today))["status"] == "not_due"

        # 次日继续取下一本（顺序拾取，不重复）
        nxt = await svc.pick_next_book(db_session, ch.id, today + timedelta(days=1))
        assert nxt["status"] == "ok" and nxt["item"]["title"] == "书2"

    @pytest.mark.asyncio
    async def test_exhausted_then_loop(self, db_session):
        ch = await _seed_channel(db_session)
        b1 = await _seed_book(db_session, ch.id, "唯一一本书")
        await svc.add_books(db_session, ch.id, [b1.id])

        d0 = date(2026, 9, 17)
        assert (await svc.pick_next_book(db_session, ch.id, d0))["status"] == "ok"
        await svc.mark_published(db_session, ch.id, "唯一一本书", d0)
        # 到末尾且未开启循环 → exhausted，跳过当日生成
        assert (await svc.pick_next_book(db_session, ch.id, d0 + timedelta(days=1)))["status"] == "exhausted"

        # 开启循环后可继续（从池首重新开始）
        await svc.update_schedule(db_session, ch.id, loop=True)
        await db_session.refresh(ch)
        assert ch.book_pool_loop == 1
        again = await svc.pick_next_book(db_session, ch.id, d0 + timedelta(days=2))
        assert again["status"] == "ok" and again["item"]["title"] == "唯一一本书"

    @pytest.mark.asyncio
    async def test_interval_days_throttle(self, db_session):
        ch = await _seed_channel(db_session)
        b1 = await _seed_book(db_session, ch.id, "书A")
        await svc.add_books(db_session, ch.id, [b1.id])
        await svc.update_schedule(db_session, ch.id, interval_days=3)

        d0 = date(2026, 9, 17)
        assert (await svc.pick_next_book(db_session, ch.id, d0))["status"] == "ok"
        await svc.mark_published(db_session, ch.id, "书A", d0)

        d1 = await svc.pick_next_book(db_session, ch.id, d0 + timedelta(days=1))
        assert d1["status"] == "not_due" and d1["next_due_date"] == (d0 + timedelta(days=3)).isoformat()

    @pytest.mark.asyncio
    async def test_reset_progress(self, db_session):
        ch = await _seed_channel(db_session)
        mats = [await _seed_book(db_session, ch.id, f"书{i}") for i in range(1, 3)]
        await svc.add_books(db_session, ch.id, [m.id for m in mats])
        d0 = date(2026, 9, 17)
        await svc.mark_published(db_session, ch.id, "书1", d0)

        state = await svc.reset_progress(db_session, ch.id)
        assert state["cursor"] == 0 and state["last_run_date"] is None
        pick = await svc.pick_next_book(db_session, ch.id, d0)
        assert pick["item"]["title"] == "书1", "重置后应从头开始"

    @pytest.mark.asyncio
    async def test_missing_channel(self, db_session):
        assert (await svc.pick_next_book(db_session, 99999))["status"] == "missing"
        with pytest.raises(ValueError):
            await svc.set_script_mode(db_session, 99999, True)


class TestCollectBookMaterials:
    @pytest.mark.asyncio
    async def test_aggregate_same_source_chapters(self, db_session):
        """上传时「来源」填书名 → 同来源章节素材自动聚合（按 id 升序＝解析顺序）。"""
        ch = await _seed_channel(db_session)
        book = await _seed_book(db_session, ch.id, "我只知道人是什么", source="我只知道人是什么")
        for i, t in enumerate(["第一章", "第二章", "第三章"], start=1):
            await _seed_book(db_session, ch.id, t, source="我只知道人是什么")
        await svc.add_books(db_session, ch.id, [book.id])

        pick = await svc.pick_next_book(db_session, ch.id, date(2026, 9, 17))
        materials = await svc.collect_book_materials(db_session, ch.id, pick["item"])
        assert len(materials) == 4, "书本身 + 3 章应全部纳入"
        assert [m.id for m in materials] == sorted(m.id for m in materials), "按解析顺序"

    @pytest.mark.asyncio
    async def test_selected_materials_excluded(self, db_session):
        """已被上次消费（selected）的章节不再纳入，避免重复讲解。"""
        ch = await _seed_channel(db_session)
        book = await _seed_book(db_session, ch.id, "书B", source="书B")
        consumed = await _seed_book(db_session, ch.id, "已讲章节", source="书B")
        consumed.status = MaterialStatus.selected.value
        await db_session.commit()
        await svc.add_books(db_session, ch.id, [book.id])

        pick = await svc.pick_next_book(db_session, ch.id, date(2026, 9, 17))
        materials = await svc.collect_book_materials(db_session, ch.id, pick["item"])
        assert [m.id for m in materials] == [book.id]

    @pytest.mark.asyncio
    async def test_book_not_uploaded_returns_empty(self, db_session):
        """池项没有对应书稿素材（如来自"加入书单"的占位素材未被解析入库）→ 空列表。"""
        ch = await _seed_channel(db_session)
        placeholder = Material(
            source="論語", source_type="book_plan", title="《論語》 孔子",
            content="待上传书稿", url="https://example.com/lunyu",
            status=MaterialStatus.selected.value, channel_id=ch.id,  # 非 pending
        )
        db_session.add(placeholder)
        await db_session.commit()
        await db_session.refresh(placeholder)
        await svc.add_books(db_session, ch.id, [placeholder.id])

        pick = await svc.pick_next_book(db_session, ch.id, date(2026, 9, 17))
        materials = await svc.collect_book_materials(db_session, ch.id, pick["item"])
        assert materials == []
