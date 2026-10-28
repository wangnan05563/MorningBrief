"""C117：素材库按当前筛选导出 CSV 的契约测试。

评审口径（T02336 §4.3）：素材库确实没有导出，但不要照搬原建议——只做
「按当前筛选导出 CSV」，且导出必须与列表同口径（同一套过滤条件、不分页）。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_c117_material_export.py
"""
from datetime import date

import pytest

from app.models import Channel, Material

_EXPORT_URL = "/admin/api/v1/materials/export"


async def _seed(db_session, name: str) -> Channel:
    ch = Channel(name=name, channel_type="news", selection_strategy="outline")
    db_session.add(ch)
    await db_session.commit()
    await db_session.refresh(ch)
    return ch


async def _add_material(db_session, channel_id: int, title: str, *, source: str, source_type: str, status: str = "pending"):
    m = Material(
        source=source,
        source_type=source_type,
        title=title,
        content="正文" * 10,
        url=f"https://example.com/c117/{channel_id}/{title}",
        status=status,
        channel_id=channel_id,
        crawled_at=date.today(),
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    return m


@pytest.mark.asyncio
async def test_export_respects_filters_and_is_not_paginated(db_session, client, admin_token):
    """导出必须命中全部筛选结果（不受列表 100 条上限影响），且带 UTF-8 BOM。"""
    hdrs = {"Authorization": f"Bearer {admin_token['token']}"}
    ch = await _seed(db_session, "C117 导出频道")
    for i in range(3):
        await _add_material(db_session, ch.id, f"书稿 {i}", source="同一本书", source_type="list")
    await _add_material(db_session, ch.id, "资讯 1", source="资讯源", source_type="rss")

    r = client.get(_EXPORT_URL, params={"channel_id": ch.id, "source_type": "list"}, headers=hdrs)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv"), r.headers.get("content-type")
    assert "attachment;" in r.headers.get("content-disposition", "")

    body = r.content.decode("utf-8-sig")
    assert r.content.startswith(b"\xef\xbb\xbf"), "缺少 UTF-8 BOM，Excel 打开会乱码"
    lines = [ln for ln in body.splitlines() if ln.strip()]
    assert lines[0].startswith("素材ID,标题,来源")
    assert len(lines) == 4, f"表头 + 3 条书稿，实际 {len(lines)} 行：{lines}"
    # 过滤掉了 rss 那条：导出与列表同口径，而不是导出了整个频道
    assert all("书稿" in ln for ln in lines[1:])


@pytest.mark.asyncio
async def test_export_rejects_unknown_source_type(db_session, client, admin_token):
    """非法筛选值必须 400，不能静默导出全集（否则「按筛选导出」是假的）。"""
    hdrs = {"Authorization": f"Bearer {admin_token['token']}"}
    ch = await _seed(db_session, "C117 非法筛选")
    await _add_material(db_session, ch.id, "书稿", source="书", source_type="list")

    r = client.get(_EXPORT_URL, params={"channel_id": ch.id, "source_type": "not-a-type"}, headers=hdrs)
    # 项目约定：路由内 BizError 由全局处理器转成 HTTP 200 + body.code=400
    assert r.status_code == 200, r.text
    assert r.json()["code"] == 400, r.text
    assert "source_type" in r.json()["message"]


@pytest.mark.asyncio
async def test_export_quotes_commas_in_titles(db_session, client, admin_token):
    """书名/标题里的逗号必须被 CSV 正确转义，不能被拆成两列。"""
    hdrs = {"Authorization": f"Bearer {admin_token['token']}"}
    ch = await _seed(db_session, "C117 逗号")
    await _add_material(db_session, ch.id, "书名, 带逗号", source="来源, 也带逗号", source_type="list")

    r = client.get(_EXPORT_URL, params={"channel_id": ch.id}, headers=hdrs)
    assert r.status_code == 200, r.text
    body = r.content.decode("utf-8-sig")
    assert '"书名, 带逗号"' in body
    assert '"来源, 也带逗号"' in body
