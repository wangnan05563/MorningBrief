"""有声读物频道创建 + schedule_time 简写归一化测试。

覆盖：
1. schedule_time 自由输入 '4:00'（前端 el-input 常见简写）经后端归一化为 '04:00:00'，
   不再触发 Pydantic 422（即修复用户报的「参数错误: schedule_time 格式应为 HH:MM:SS」）。
2. 自动生成 channel_type=audiobook 频道并落库校验。
3. _normalize_schedule_time 纯函数对 2 段/3 段/边界/非法输入的归一化与拒绝。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_audiobook_channel_schedule.py
"""
import pytest
from sqlalchemy import select

from app.models import Channel
from app.routers.admin.channels import _normalize_schedule_time


def test_normalize_schedule_time_lenient_accepts_short_forms():
    """2 段简写与 3 段完整形式均归一化为 HH:MM:SS。"""
    assert _normalize_schedule_time("4:00") == "04:00:00"
    assert _normalize_schedule_time("4:0:5") == "04:00:05"
    assert _normalize_schedule_time("23:59") == "23:59:00"
    assert _normalize_schedule_time(" 8:30 ") == "08:30:00"  # 容忍前后空格
    assert _normalize_schedule_time("08:30:00") == "08:30:00"


@pytest.mark.parametrize("bad", ["4", "4:00:00:00", "abc", "25:00", "99:99:99", "1:2:3:4", "1:2:3:4:5"])
def test_normalize_schedule_time_rejects_invalid(bad):
    """明显非时间格式 / 越界 / 段数异常应拒绝（转 422）。"""
    with pytest.raises(ValueError):
        _normalize_schedule_time(bad)


async def test_create_audiobook_channel_normalizes_schedule_time(client, db_session, admin_token):
    """修复验证：以 schedule_time='4:00' 创建有声读物频道应成功并归一化落库。"""
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    resp = client.post(
        "/admin/api/v1/channels",
        json={
            "name": "测试有声读物",
            "channel_type": "audiobook",
            "type_label": "有声读物",
            "schedule_time": "4:00",  # 用户实际输入，曾触发 422
            "book_rss_sources": '["豆瓣读书-最新书评"]',
            "selection_strategy": "outline",
            "disclaimer_level": "strong",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    ch = body["data"]
    assert ch["channel_type"] == "audiobook"
    assert ch["schedule_time"] == "04:00:00", ch

    # DB 落库确认（不只是响应体）
    result = await db_session.execute(select(Channel).where(Channel.id == ch["id"]))
    db_ch = result.scalar_one_or_none()
    assert db_ch is not None
    assert db_ch.schedule_time == "04:00:00"
    assert db_ch.channel_type == "audiobook"
