"""讲书稿模式与素材池服务测试（T00656 + 用户反馈修正）。

覆盖：
- 模式开关：幂等；**开启后书源配置保留（灰显，不再清空）**——采集隔离由 crawler 行为分支保证；
- 素材池：**按书为单位**加入（book_key=素材 source/书名，一本书一个池项）、去重幂等、
  移除重排、上移/下移、批量重排；
- 取书与进度：空池/正常顺序/到末尾停止/开启循环归零/间隔节流/发布后推进/重置；
- 章节聚合：**同来源（书名）章节自动整本纳入**（按 id 升序＝解析顺序），selected 章节排除；
- 候选列表：按书聚合（一行一本书，含章节数/待讲数/in_pool）。

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


async def _seed_book(session, channel_id: int, title: str, source: str | None = None) -> Material:
    """播种一条素材；默认 source=title（＝书名，模拟上传时后端自动写书名来源）。"""
    m = Material(
        source=source or title, source_type="list", title=title, content="正文" * 20,
        url=f"https://example.com/{channel_id}/{title}", status=MaterialStatus.pending.value,
        channel_id=channel_id, crawled_at=date.today(),
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


class TestScriptMode:
    @pytest.mark.asyncio
    async def test_enable_keeps_sources_and_sets_mode(self, db_session):
        """开启：script_mode=book_pool，**书源配置保留**（灰显由前端处理，隔离靠行为层）。"""
        ch = await _seed_channel(db_session)
        res = await svc.set_script_mode(db_session, ch.id, True)
        assert res["changed"] is True and res["enabled"] is True
        assert "素材池" in res["message"]
        await db_session.refresh(ch)
        assert ch.script_mode == "book_pool"
        # 书源配置原样保留（用户反馈：灰显而非清空）
        assert json.loads(ch.rss_sources) == ["人民网-国内"]
        assert json.loads(ch.book_rss_sources) == ["豆瓣读书-最新书评"]

    @pytest.mark.asyncio
    async def test_enable_twice_is_idempotent(self, db_session):
        ch = await _seed_channel(db_session)
        await svc.set_script_mode(db_session, ch.id, True)
        res2 = await svc.set_script_mode(db_session, ch.id, True)
        assert res2["changed"] is False and "已处于讲书稿模式" in res2["message"]
        await db_session.refresh(ch)
        assert json.loads(ch.rss_sources) == ["人民网-国内"]

    @pytest.mark.asyncio
    async def test_disable_keeps_sources(self, db_session):
        ch = await _seed_channel(db_session)
        await svc.set_script_mode(db_session, ch.id, True)
        res = await svc.set_script_mode(db_session, ch.id, False)
        assert res["changed"] is True and res["enabled"] is False
        assert "频道书源" in res["message"]
        await db_session.refresh(ch)
        assert ch.script_mode in ("", "channel")
        # 书源从未被改动，关闭后自然还是原配置
        assert json.loads(ch.rss_sources) == ["人民网-国内"]

    @pytest.mark.asyncio
    async def test_disable_twice_is_idempotent(self, db_session):
        ch = await _seed_channel(db_session)
        res = await svc.set_script_mode(db_session, ch.id, False)
        assert res["changed"] is False and res["enabled"] is False


class TestPoolCrud:
    @pytest.mark.asyncio
    async def test_add_books_by_book_key(self, db_session):
        """按书加入：一本书一个池项（book_key=书名），同书重复加入幂等。"""
        ch = await _seed_channel(db_session)
        await _seed_book(db_session, ch.id, "我只知道人是什么")
        await _seed_book(db_session, ch.id, "活着")

        r1 = await svc.add_books(db_session, ch.id, ["我只知道人是什么", "活着"])
        assert r1["added"] == 2
        r2 = await svc.add_books(db_session, ch.id, ["我只知道人是什么", "活着"])
        assert r2["added"] == 0 and r2["skipped"] == 2

        items = await svc.list_pool(db_session, ch.id)
        assert [i["sort_index"] for i in items] == [0, 1]
        assert {i["book_key"] for i in items} == {"我只知道人是什么", "活着"}
        assert items[0]["title"] == "我只知道人是什么"

    @pytest.mark.asyncio
    async def test_add_book_without_material_skipped(self, db_session):
        """书键在频道内无对应素材（如仅"加入书单"但从未上传书稿）→ 跳过并提示。"""
        ch = await _seed_channel(db_session)
        res = await svc.add_books(db_session, ch.id, ["不存在的书"])
        assert res["added"] == 0 and res["skipped"] == 1

    @pytest.mark.asyncio
    async def test_move_and_reorder(self, db_session):
        ch = await _seed_channel(db_session)
        for t in ("书1", "书2", "书3"):
            await _seed_book(db_session, ch.id, t)
        await svc.add_books(db_session, ch.id, ["书1", "书2", "书3"])
        items = await svc.list_pool(db_session, ch.id)

        assert await svc.move_item(db_session, ch.id, items[2]["id"], "up") is True
        titles = [i["title"] for i in await svc.list_pool(db_session, ch.id)]
        assert titles == ["书1", "书3", "书2"]
        first = (await svc.list_pool(db_session, ch.id))[0]
        assert await svc.move_item(db_session, ch.id, first["id"], "up") is False

        by_title = {i["title"]: i["id"] for i in await svc.list_pool(db_session, ch.id)}
        await svc.reorder(db_session, ch.id, [by_title["书2"], by_title["书1"], by_title["书3"]])
        assert [i["title"] for i in await svc.list_pool(db_session, ch.id)] == ["书2", "书1", "书3"]

    @pytest.mark.asyncio
    async def test_remove_resequences(self, db_session):
        ch = await _seed_channel(db_session)
        for t in ("书1", "书2", "书3"):
            await _seed_book(db_session, ch.id, t)
        await svc.add_books(db_session, ch.id, ["书1", "书2", "书3"])
        items = await svc.list_pool(db_session, ch.id)
        assert await svc.remove_item(db_session, ch.id, items[0]["id"]) is True
        rest = await svc.list_pool(db_session, ch.id)
        assert [i["sort_index"] for i in rest] == [0, 1]
        assert await svc.remove_item(db_session, ch.id, 99999) is False


class TestPickAndProgress:
    @pytest.mark.asyncio
    async def test_empty_pool(self, db_session):
        ch = await _seed_channel(db_session)
        assert (await svc.pick_next_book(db_session, ch.id))["status"] == "empty"

    @pytest.mark.asyncio
    async def test_sequential_pick_and_advance(self, db_session):
        ch = await _seed_channel(db_session)
        for t in ("书1", "书2", "书3"):
            await _seed_book(db_session, ch.id, t)
        await svc.add_books(db_session, ch.id, ["书1", "书2", "书3"])

        today = date(2026, 9, 17)
        pick = await svc.pick_next_book(db_session, ch.id, today)
        assert pick["status"] == "ok" and pick["item"]["title"] == "书1" and pick["cursor"] == 0

        await svc.mark_published(db_session, ch.id, "书1", today)
        assert (await svc.pick_next_book(db_session, ch.id, today))["status"] == "not_due"

        nxt = await svc.pick_next_book(db_session, ch.id, today + timedelta(days=1))
        assert nxt["status"] == "ok" and nxt["item"]["title"] == "书2"

    @pytest.mark.asyncio
    async def test_exhausted_then_loop(self, db_session):
        ch = await _seed_channel(db_session)
        await _seed_book(db_session, ch.id, "唯一一本书")
        await svc.add_books(db_session, ch.id, ["唯一一本书"])

        d0 = date(2026, 9, 17)
        assert (await svc.pick_next_book(db_session, ch.id, d0))["status"] == "ok"
        await svc.mark_published(db_session, ch.id, "唯一一本书", d0)
        assert (await svc.pick_next_book(db_session, ch.id, d0 + timedelta(days=1)))["status"] == "exhausted"

        await svc.update_schedule(db_session, ch.id, loop=True)
        await db_session.refresh(ch)
        assert ch.book_pool_loop == 1
        again = await svc.pick_next_book(db_session, ch.id, d0 + timedelta(days=2))
        assert again["status"] == "ok" and again["item"]["title"] == "唯一一本书"

    @pytest.mark.asyncio
    async def test_interval_days_throttle(self, db_session):
        ch = await _seed_channel(db_session)
        await _seed_book(db_session, ch.id, "书A")
        await svc.add_books(db_session, ch.id, ["书A"])
        await svc.update_schedule(db_session, ch.id, interval_days=3)

        d0 = date(2026, 9, 17)
        assert (await svc.pick_next_book(db_session, ch.id, d0))["status"] == "ok"
        await svc.mark_published(db_session, ch.id, "书A", d0)

        d1 = await svc.pick_next_book(db_session, ch.id, d0 + timedelta(days=1))
        assert d1["status"] == "not_due" and d1["next_due_date"] == (d0 + timedelta(days=3)).isoformat()

    @pytest.mark.asyncio
    async def test_reset_progress(self, db_session):
        ch = await _seed_channel(db_session)
        for t in ("书1", "书2"):
            await _seed_book(db_session, ch.id, t)
        await svc.add_books(db_session, ch.id, ["书1", "书2"])
        d0 = date(2026, 9, 17)
        await svc.mark_published(db_session, ch.id, "书1", d0)

        state = await svc.reset_progress(db_session, ch.id)
        assert state["cursor"] == 0 and state["last_run_date"] is None
        pick = await svc.pick_next_book(db_session, ch.id, d0)
        assert pick["item"]["title"] == "书1"

    @pytest.mark.asyncio
    async def test_missing_channel(self, db_session):
        assert (await svc.pick_next_book(db_session, 99999))["status"] == "missing"
        with pytest.raises(ValueError):
            await svc.set_script_mode(db_session, 99999, True)


class TestCollectBookMaterials:
    @pytest.mark.asyncio
    async def test_aggregate_same_source_chapters(self, db_session):
        """同来源（书名）章节自动整本纳入（按 id 升序＝解析顺序）。"""
        ch = await _seed_channel(db_session)
        await _seed_book(db_session, ch.id, "我只知道人是什么")
        for t in ("第一章", "第二章", "第三章"):
            await _seed_book(db_session, ch.id, t, source="我只知道人是什么")
        await svc.add_books(db_session, ch.id, ["我只知道人是什么"])

        pick = await svc.pick_next_book(db_session, ch.id, date(2026, 9, 17))
        materials = await svc.collect_book_materials(db_session, ch.id, pick["item"])
        assert len(materials) == 4, "书本身 + 3 章应全部纳入"
        assert [m.id for m in materials] == sorted(m.id for m in materials), "按解析顺序"

    @pytest.mark.asyncio
    async def test_selected_materials_excluded(self, db_session):
        """已被上次消费（selected）的章节不再纳入，避免重复讲解。"""
        ch = await _seed_channel(db_session)
        book = await _seed_book(db_session, ch.id, "书B")
        consumed = await _seed_book(db_session, ch.id, "已讲章节", source="书B")
        consumed.status = MaterialStatus.selected.value
        await db_session.commit()
        await svc.add_books(db_session, ch.id, ["书B"])

        pick = await svc.pick_next_book(db_session, ch.id, date(2026, 9, 17))
        materials = await svc.collect_book_materials(db_session, ch.id, pick["item"])
        assert [m.id for m in materials] == [book.id]


class TestCandidates:
    @pytest.mark.asyncio
    async def test_candidates_aggregated_by_book(self, db_session):
        """候选按书聚合：一行一本书（含章节数/待讲数/in_pool）。"""
        ch = await _seed_channel(db_session)
        for t in ("第一章", "第二章", "第三章"):
            await _seed_book(db_session, ch.id, t, source="我只知道人是什么")
        await _seed_book(db_session, ch.id, "序", source="活着")

        res = await svc.list_candidates(db_session, ch.id)
        by_key = {i["book_key"]: i for i in res["items"]}
        assert set(by_key) == {"我只知道人是什么", "活着"}
        assert by_key["我只知道人是什么"]["chapters"] == 3
        assert by_key["我只知道人是什么"]["pending_chapters"] == 3
        assert by_key["我只知道人是什么"]["in_pool"] is False

        await svc.add_books(db_session, ch.id, ["活着"])
        res2 = await svc.list_candidates(db_session, ch.id)
        by_key2 = {i["book_key"]: i for i in res2["items"]}
        assert by_key2["活着"]["in_pool"] is True
        assert by_key2["我只知道人是什么"]["in_pool"] is False

    @pytest.mark.asyncio
    async def test_candidates_keyword_filter(self, db_session):
        ch = await _seed_channel(db_session)
        for t in ("我只知道人是什么", "活着"):
            await _seed_book(db_session, ch.id, t)
        res = await svc.list_candidates(db_session, ch.id, keyword="活着")
        assert [i["book_key"] for i in res["items"]] == ["活着"]
