"""素材库管理页的接口契约测试（T00775）。

背景：B 端「素材库管理」页曾按 `data.items` 取列表，而 `GET /admin/api/v1/materials`
返回的是 `{ total, list }` —— 取错键导致页面列表恒为空（「从素材库加入书籍」里能看到书，
点「管理素材」跳过去却查不到）。本测试把「响应体必须带 list 键」锁成契约，
后端若改键名会在此失败，而不是静默让前端列表变空。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_material_library_contract.py
"""
from datetime import date

import pytest

from app.models import Channel, Material
from app.models.material import MaterialStatus


@pytest.mark.asyncio
async def test_list_materials_returns_list_key(db_session, client, admin_token):
    """素材列表响应必须含 `list`（且不含易混淆的 `items` 键）。"""
    hdrs = {"Authorization": f"Bearer {admin_token['token']}"}
    ch = Channel(name="T00775 频道", channel_type="audiobook", selection_strategy="outline")
    db_session.add(ch)
    await db_session.commit()
    await db_session.refresh(ch)
    for t in ("我只知道人是什么 · 第一章", "我只知道人是什么 · 第二章"):
        db_session.add(Material(
            source="我只知道人是什么", source_type="list", title=t, content="正文" * 20,
            url=f"https://example.com/t00775/{t}", status=MaterialStatus.pending.value,
            channel_id=ch.id, crawled_at=date.today(),
        ))
    await db_session.commit()

    r = client.get("/admin/api/v1/materials", params={"channel_id": ch.id}, headers=hdrs).json()
    assert r["code"] == 0, r
    assert "list" in r["data"], f"素材列表必须返回 list 键，实际键：{sorted(r['data'])}"
    assert "items" not in r["data"], "不应返回 items 键（避免前端取错键静默空列表）"
    assert r["data"]["total"] == 2
    assert len(r["data"]["list"]) == 2
    # 列表项需带素材库管理页表格渲染所需字段
    row = r["data"]["list"][0]
    for field in ("id", "title", "source", "status", "crawled_at"):
        assert field in row, f"列表项缺少字段 {field}"
