"""C56（FR-UX-202 / M2）：素材编辑不得把正文/来源清成空白。

红基线（改前）：`PUT /admin/api/v1/materials/{id}` 逐字段 `setattr`，
`content=""` / `source=""` 原样落库并返回成功；前端 `onSaveEdit` 只挡空标题。
后果不是「字段难看」：`source` 就是讲书稿的按书聚合键
（`book_pool_service.list_candidates` 明确写「聚合键 = Material.source」），
清空等于把这本书从书单候选里抹掉；`content` 清空后已选素材再也进不了改写。
用户看到的却是一句「已保存」。

这里断言的是**库里的值**，不是返回码——和 M16 同一套口径。
"""
import pytest
from sqlalchemy import select

from app.models import Material
from app.models.material import MaterialSourceType, MaterialStatus

URL = "/admin/api/v1/materials"


async def _seed(db_session, *, content="第一章正文", source="被讨厌的勇气"):
    m = Material(
        source=source,
        source_type=MaterialSourceType.list.value,
        title="第一章",
        content=content,
        url="http://example.com/1",
        category="tech",
        status=MaterialStatus.pending.value,
        channel_id=77,
    )
    db_session.add(m)
    await db_session.commit()
    return m.id


async def _reload(db_session, material_id):
    res = await db_session.execute(select(Material).where(Material.id == material_id))
    return res.scalar_one()


def _put(client, admin_token, material_id, payload):
    return client.put(
        f"{URL}/{material_id}",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )


async def test_clearing_content_is_rejected_and_body_survives(client, admin_token, db_session):
    """清空正文必须被拒，且库里那条正文一个字都不能少。"""
    mid = await _seed(db_session)
    resp = _put(client, admin_token, mid, {"content": "", "title": "第一章"})
    assert resp.json()["code"] == 400, f"清空正文被照单全收：{resp.json()}"
    assert (await _reload(db_session, mid)).content == "第一章正文"


async def test_clearing_source_is_rejected_and_book_key_survives(client, admin_token, db_session):
    """清空来源（书名）= 打断整本书聚合，必须拒。"""
    mid = await _seed(db_session)
    resp = _put(client, admin_token, mid, {"source": "   "})
    assert resp.json()["code"] == 400, f"空白来源被照单全收：{resp.json()}"
    assert (await _reload(db_session, mid)).source == "被讨厌的勇气"


async def test_rejection_names_each_offending_field(client, admin_token, db_session):
    """沿用 INT-UX-01 契约：data.errors[].field，前端不必切整句中文。"""
    mid = await _seed(db_session)
    body = _put(client, admin_token, mid, {"content": "", "source": ""}).json()
    fields = sorted(e["field"] for e in body["data"]["errors"])
    assert fields == ["content", "source"], f"字段级错误应点名两列，实际 {fields}"
    # 未牵连：同一次提交里的 title 是合法字段，不该出现在被拒列表里
    assert "title" not in fields


async def test_blank_message_explains_the_aggregation_consequence(client, admin_token, db_session):
    """错误说明要点名后果，只说「不能为空」运营不知道为什么要保留来源。"""
    mid = await _seed(db_session)
    entry = _put(client, admin_token, mid, {"source": ""}).json()["data"]["errors"][0]
    assert "聚合" in entry["message"], f"未解释清空来源的业务后果：{entry['message']}"


async def test_legitimate_edit_still_saves(client, admin_token, db_session):
    """改标题 + 换正文（都非空）不受影响：护栏不能顺手把正常编辑也堵了。"""
    mid = await _seed(db_session)
    resp = _put(client, admin_token, mid, {"title": "第一章（修订）", "content": "新正文"})
    assert resp.json()["code"] == 0, f"正常编辑被拒：{resp.json()}"
    m = await _reload(db_session, mid)
    assert m.title == "第一章（修订）" and m.content == "新正文"


async def test_untouched_critical_fields_are_not_required(client, admin_token, db_session):
    """PATCH 语义：请求里没出现 content/source 时不该被当成清空。"""
    mid = await _seed(db_session)
    resp = _put(client, admin_token, mid, {"status": MaterialStatus.selected.value})
    assert resp.json()["code"] == 0, f"只改状态被拒：{resp.json()}"
    m = await _reload(db_session, mid)
    assert m.content == "第一章正文" and m.source == "被讨厌的勇气"


async def test_row_already_empty_can_be_saved_again(client, admin_token, db_session):
    """护栏只拦「非空 → 空白」这一条转变。

    历史数据里本来就空的行（早期导入的素材）不该因此彻底无法编辑——
    那是把防护做成新bug。
    """
    mid = await _seed(db_session, content="", source="")
    resp = _put(client, admin_token, mid, {"content": "", "title": "第一章"})
    assert resp.json()["code"] == 0, f"原值本就为空的行被卡住：{resp.json()}"


async def test_source_rename_actually_persists(client, admin_token, db_session):
    """C56 的另一半：`source` 此前不在请求模型里，改书名是「提示成功但没改」。

    pydantic 默认 `extra='ignore'`，前端把 source 发上来直接被丢掉，接口回 success、
    界面提示「已保存」，书名却从没动过。请求模型补上该字段后，这条用例钉住
    它真的写进库——静默丢弃非空字段与静默清空同样不可接受。
    """
    mid = await _seed(db_session)
    resp = _put(client, admin_token, mid, {"source": "非暴力沟通"})
    assert resp.json()["code"] == 0, f"改书名被拒：{resp.json()}"
    m = await _reload(db_session, mid)
    assert m.source == "非暴力沟通", f"接口说成功但书名没改：{m.source!r}"


async def test_title_blanking_is_rejected_via_api(client, admin_token, db_session):
    """「只挡空标题」这句校验此前只存在于前端；直接调接口就能把标题清空。"""
    mid = await _seed(db_session)
    resp = _put(client, admin_token, mid, {"title": "   "})
    assert resp.json()["code"] == 400, f"空白标题被照单全收：{resp.json()}"
    assert (await _reload(db_session, mid)).title == "第一章"
