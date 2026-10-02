"""素材多 source_type 入库与去重策略测试。

覆盖「多输入渠道」核心：_persist_material 按 source_type 分流去重，
并验证 create_material 路由层对非法 source_type 的应用层校验。

去重策略（见 routers/admin/materials.py::_persist_material）：
- list / cos：无真实 Web URL（cos 为对象 key），用合成 url
  {source_type}://{channel_id}/{dedup_key[:16]} + (source_type, channel_id, dedup_key)
  **频道级**查重（T01521：同内容可入不同频道，同频道内重复 409）
- rss / book_rss / api / qrcode：有真实 URL，走 url 唯一约束（全局）

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_material_source_types.py
"""
import pytest

from app.core.exceptions import BizError
from app.models import Material, MaterialSourceType
from app.services.document_ingest import compute_content_hash
from app.routers.admin.materials import _persist_material


async def test_persist_list_dedup_by_content_hash(db_session):
    """list 类型按 content_hash 去重，重复内容 -> 409。"""
    m1 = await _persist_material(
        db_session,
        channel_id=10,
        source="手动录入",
        title="T1",
        content="同一段正文",
        source_type=MaterialSourceType.list.value,
    )
    assert m1.id is not None
    assert m1.url.startswith("list://10/")
    assert m1.dedup_key == compute_content_hash("同一段正文")

    with pytest.raises(BizError) as exc:
        await _persist_material(
            db_session,
            channel_id=10,
            source="手动录入",
            title="T1",
            content="同一段正文",  # 相同内容 -> 命中 dedup_key
            source_type=MaterialSourceType.list.value,
        )
    assert exc.value.code == 409


async def test_persist_list_channel_scoped_dedup_cross_channel_allowed(db_session):
    """T01521 频道级查重：同内容录入不同频道成功，同频道重复仍 409。"""
    content = "跨频道分发的同一段正文"
    m1 = await _persist_material(
        db_session,
        channel_id=10,
        source="手动录入",
        title="A",
        content=content,
        source_type=MaterialSourceType.list.value,
    )
    # 不同频道：同 content_hash 不再 409，正常入库
    m2 = await _persist_material(
        db_session,
        channel_id=20,
        source="手动录入",
        title="A",
        content=content,
        source_type=MaterialSourceType.list.value,
    )
    assert m2.id != m1.id
    assert m2.dedup_key == m1.dedup_key
    # 合成 url 含 channel_id，DB 唯一约束天然不冲突
    assert m2.url.startswith("list://20/") and m1.url.startswith("list://10/")

    # 同频道重复仍 409
    with pytest.raises(BizError) as exc:
        await _persist_material(
            db_session,
            channel_id=20,
            source="手动录入",
            title="A",
            content=content,
            source_type=MaterialSourceType.list.value,
        )
    assert exc.value.code == 409


async def test_persist_list_channel_scoped_dedup_channel_none_isolated(db_session):
    """channel_id 为空与有值频道互不干扰（IS NULL 精确匹配）。"""
    content = "无频道归属的正文"
    m1 = await _persist_material(
        db_session,
        channel_id=None,
        source="手动录入",
        title="N",
        content=content,
        source_type=MaterialSourceType.list.value,
    )
    m2 = await _persist_material(
        db_session,
        channel_id=30,
        source="手动录入",
        title="N",
        content=content,
        source_type=MaterialSourceType.list.value,
    )
    assert m2.id != m1.id
    # NULL 频道内部重复仍 409
    with pytest.raises(BizError) as exc:
        await _persist_material(
            db_session,
            channel_id=None,
            source="手动录入",
            title="N",
            content=content,
            source_type=MaterialSourceType.list.value,
        )
    assert exc.value.code == 409


async def test_persist_list_synthetic_url_format_when_channel_none(db_session):
    """channel_id 为空时合成 url 用 0 兜底，避免 NOT NULL / 唯一约束冲突。"""
    m = await _persist_material(
        db_session,
        channel_id=None,
        source="手动录入",
        title="T",
        content="X",
        source_type=MaterialSourceType.list.value,
    )
    assert m.url == f"list://0/{compute_content_hash('X')[:16]}"


async def test_persist_cos_dedup_by_dedup_key(db_session):
    """cos 类型按 dedup_key 去重（cos 无真实可访问 URL）。"""
    key = "obj/book/ch1.txt"
    m1 = await _persist_material(
        db_session,
        channel_id=20,
        source="COS导入",
        title="C1",
        content="cos 内容",
        source_type=MaterialSourceType.cos.value,
        dedup_key=key,
    )
    assert m1.url == f"cos://20/{key[:16]}"

    # 相同 dedup_key 即便内容不同仍判定重复 -> 409
    with pytest.raises(BizError) as exc:
        await _persist_material(
            db_session,
            channel_id=20,
            source="COS导入",
            title="C1",
            content="不同内容",
            source_type=MaterialSourceType.cos.value,
            dedup_key=key,
        )
    assert exc.value.code == 409


async def test_persist_url_based_types_dedup_and_require_url(db_session):
    """rss/book_rss/api/qrcode 必须提供 url，且按 url 唯一去重。"""
    for st in (
        MaterialSourceType.rss,
        MaterialSourceType.book_rss,
        MaterialSourceType.api,
        MaterialSourceType.qrcode,
    ):
        # 缺 url -> 400（应用层提前拦截，不落到 DB 唯一约束）
        with pytest.raises(BizError) as exc_missing:
            await _persist_material(
                db_session,
                channel_id=30,
                source="S",
                title="t",
                content="c",
                source_type=st.value,
            )
        assert exc_missing.value.code == 400

        url = f"https://example.com/{st.value}/1"
        m = await _persist_material(
            db_session,
            channel_id=30,
            source="S",
            title="t",
            content="c",
            source_type=st.value,
            url=url,
        )
        assert m.url == url

        # 相同 url -> 409
        with pytest.raises(BizError) as exc_dup:
            await _persist_material(
                db_session,
                channel_id=30,
                source="S",
                title="t2",
                content="c2",
                source_type=st.value,
                url=url,
            )
        assert exc_dup.value.code == 409


async def test_create_material_validates_source_type(client, db_session, admin_token):
    """create_material 路由层校验 source_type 合法性；list 无需 url 自动合成。"""
    headers = {"Authorization": f"Bearer {admin_token['token']}"}

    # 非法 source_type -> 非 0（应用层拒绝，不进 DB）
    resp = client.post(
        "/admin/api/v1/materials",
        json={
            "workflow_id": "wf1",
            "source": "S",
            "title": "t",
            "content": "c",
            "url": "u",
            "source_type": "bogus",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["code"] != 0

    # list 类型无需 url，合成 url 入库成功
    resp2 = client.post(
        "/admin/api/v1/materials",
        json={
            "workflow_id": "wf2",
            "source": "手动录入",
            "title": "t",
            "content": "hello world",
        },
        headers=headers,
    )
    body = resp2.json()
    assert resp2.status_code == 200
    assert body["code"] == 0, body
    assert body["data"]["source_type"] == "list"
    assert body["data"]["url"].startswith("list://")
