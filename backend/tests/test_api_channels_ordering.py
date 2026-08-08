"""C 端频道列表排序测试。

验证 /api/v1/channels 按 display_order 升序返回（相等时按 id 兜底），
且仅返回启用频道；返回体含 display_order 字段，供小程序 tab 按后端顺序渲染。
"""
import pytest
from sqlalchemy import select

from app.models import Channel


async def _seed(db_session, name, display_order, is_active=1):
    ch = Channel(name=name, is_active=is_active, display_order=display_order)
    db_session.add(ch)
    await db_session.commit()
    await db_session.refresh(ch)
    return ch


async def test_channels_ordered_by_display_order_and_id(client, db_session):
    # 乱序插入：display_order 不同 + 同 display_order 用 id 兜底
    await _seed(db_session, "科技", display_order=2)
    b = await _seed(db_session, "财经", display_order=1)  # id 较小
    await _seed(db_session, "体育", display_order=1, is_active=0)  # 禁用，应被排除
    await _seed(db_session, "国际", display_order=3)
    e = await _seed(db_session, "国内", display_order=1)  # 同 display_order=1，id 较大

    resp = client.get("/api/v1/channels")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0

    items = body["data"]["list"]
    names = [it["name"] for it in items]
    orders = [it["display_order"] for it in items]

    # 禁用频道「体育」必须被排除
    assert "体育" not in names
    # 排序：display_order 1(B, 国内按 id 升序) -> 2(科技) -> 3(国际)
    assert names == ["财经", "国内", "科技", "国际"], names
    assert orders == [1, 1, 2, 3], orders
    # 同 display_order=1 的两个频道按 id 升序：财经(b.id) 应在 国内(e.id) 之前
    assert b.id < e.id
    # 返回体必须含 display_order 字段（小程序据此排序渲染）
    assert all("display_order" in it for it in items)


async def test_channels_empty_when_no_active(client, db_session):
    await _seed(db_session, "仅禁用", display_order=0, is_active=0)
    resp = client.get("/api/v1/channels")
    assert resp.status_code == 200
    assert resp.json()["data"]["list"] == []
