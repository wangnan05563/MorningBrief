"""C103（T02536 / M4「界面声称未发生的事」）：找书工具「加入待讲书单」的占位素材。

修复前的事实：
- 前端 `createDraftMaterial` 不传 `channel_id`，后端也不校验 → 落库 `channel_id=NULL`；
  讲书稿候选按频道过滤，因此这本书**既不在该频道的书单候选里，也不在任何频道视图的素材库里**，
  而按钮当时照样弹「已加入待讲书单」——界面声称了一件没有发生的事。
- `source_type='book_plan'` 从未登记进 `MaterialSourceType`（也不在前端字典里），
  素材库里显示成裸英文枚举、无法按「待讲书单」筛选。
- 占位素材和真书稿同为 material 行、同样按 `source` 聚合，三处消费路径不排除它：
  候选列表 / 入池绑定代表素材 / 取章生成。不排除的话，系统会把
  「【待上传书稿】请在找书工具下载 EPUB 后…」当讲书稿改写并念出去。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_book_plan_placeholder.py
"""
from datetime import date

import pytest
from sqlalchemy import select

from app.models import Channel, Material, MaterialSourceType
from app.models.material import MaterialStatus
from app.services import book_pool_service as svc


def _headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


@pytest.fixture
def stub_blacklist(monkeypatch):
    import app.core.auth

    async def _always_false(jti: str) -> bool:
        return False

    monkeypatch.setattr(app.core.auth, "is_in_blacklist", _always_false)


async def _seed_channel(session, name="听书频道") -> Channel:
    ch = Channel(name=name, channel_type="audiobook", selection_strategy="outline")
    session.add(ch)
    await session.commit()
    await session.refresh(ch)
    return ch


async def _seed_manuscript(session, channel_id: int, title: str, source: str) -> Material:
    """真书稿素材（模拟「素材录入」上传后按章节入库）。"""
    m = Material(
        source=source, source_type="list", title=title, content="正文" * 20,
        url=f"https://example.com/ms/{channel_id}/{title}",
        status=MaterialStatus.pending.value, channel_id=channel_id, crawled_at=date.today(),
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


async def _seed_placeholder(session, channel_id: int, title: str) -> Material:
    m = Material(
        source=title[:64], source_type=MaterialSourceType.book_plan.value,
        title=f"《{title}》", content="【待上传书稿】请在找书工具下载 EPUB 后上传。",
        url=f"https://example.com/plan/{channel_id}/{title}",
        status=MaterialStatus.pending.value, channel_id=channel_id, crawled_at=date.today(),
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


class TestEnumRegistered:
    def test_book_plan_is_a_declared_source_type(self):
        """裸字符串写库不算数：枚举里必须有这一值（前端字典由构建期门禁比对）。"""
        assert MaterialSourceType("book_plan") is MaterialSourceType.book_plan
        assert MaterialSourceType.book_plan.value == "book_plan"


class TestDraftMaterialChannel:
    @pytest.mark.asyncio
    async def test_valid_channel_persisted(self, db_session, client, admin_token, stub_blacklist):
        ch = await _seed_channel(db_session)
        resp = client.post("/admin/api/v1/ebooks/draft-material", json={
            "title": "我只知道人是什么", "author": "余华", "category": "文学",
            "url": "https://example.com/plan/yh-1", "channel_id": ch.id,
        }, headers=_headers(admin_token)).json()
        assert resp["code"] == 0, resp
        assert resp["data"]["created"] is True
        assert resp["data"]["channel_id"] == ch.id
        # 文案点名归属频道，用户才知道这本书落去了哪里
        assert ch.name in resp["data"]["message"]

        row = (await db_session.execute(
            select(Material).where(Material.url == "https://example.com/plan/yh-1")
        )).scalar_one()
        assert row.channel_id == ch.id
        assert row.source_type == MaterialSourceType.book_plan.value

    @pytest.mark.asyncio
    async def test_unknown_channel_rejected_with_field_error(self, client, admin_token, stub_blacklist):
        resp = client.post("/admin/api/v1/ebooks/draft-material", json={
            "title": "书", "url": "https://example.com/plan/bad-ch", "channel_id": 999999,
        }, headers=_headers(admin_token)).json()
        assert resp["code"] != 0
        assert "频道" in resp["message"], resp
        # 中文文案，不把英文字段名/枚举裸值弹给运营
        assert "channel_id" not in resp["message"]
        assert resp["data"]["errors"][0]["field"] == "channel_id"

    @pytest.mark.asyncio
    async def test_missing_channel_says_so_in_message(self, client, admin_token, stub_blacklist):
        """接口仍允许不带频道（给脚本/迁移用），但响应必须如实说「未归属频道」。"""
        resp = client.post("/admin/api/v1/ebooks/draft-material", json={
            "title": "書", "url": "https://example.com/plan/no-ch",
        }, headers=_headers(admin_token)).json()
        assert resp["code"] == 0, resp
        assert "未归属频道" in resp["data"]["message"], resp["data"]["message"]


class TestPlaceholderNeverNarrated:
    @pytest.mark.asyncio
    async def test_candidates_exclude_placeholder(self, db_session):
        ch = await _seed_channel(db_session)
        await _seed_placeholder(db_session, ch.id, "论语")
        await _seed_manuscript(db_session, ch.id, "论语 第一章", "论语")
        res = await svc.list_candidates(db_session, channel_id=ch.id, page=1, size=20)
        assert res["total"] == 1
        assert [i["book_key"] for i in res["items"]] == ["论语"]

    @pytest.mark.asyncio
    async def test_add_books_binds_manuscript_not_placeholder(self, db_session):
        """入池的代表素材不能是那条没有正文的占位记录（它 id 更小，此前会被 min(id) 选中）。"""
        ch = await _seed_channel(db_session)
        ph = await _seed_placeholder(db_session, ch.id, "论语")
        ms = await _seed_manuscript(db_session, ch.id, "论语 第一章", "论语")
        assert ph.id < ms.id
        await svc.add_books(db_session, ch.id, ["论语"])
        pool = await svc.list_pool(db_session, ch.id)
        assert pool[0]["material_id"] == ms.id

    @pytest.mark.asyncio
    async def test_collect_book_materials_excludes_placeholder(self, db_session):
        ch = await _seed_channel(db_session)
        await _seed_placeholder(db_session, ch.id, "论语")
        ms = await _seed_manuscript(db_session, ch.id, "论语 第一章", "论语")
        rows = await svc.collect_book_materials(
            db_session, ch.id, {"book_key": "论语", "title": "论语"}
        )
        assert [r.id for r in rows] == [ms.id]
        assert all("待上传书稿" not in (r.content or "") for r in rows)
