"""T03322：C 端频道列表缓存键单源。

红基线（改前）：读侧 `api:channels:list_active:v2`，`invalidate_list_cache()` 删的却是
`api:channels:list_active`——一个没人写入的键。后果不是「永久旧数据」，而是
「后台改完频道名/图标/排序/上下线，小程序 tab 最长 60 秒才变」，只在代码层比对
字符串的用例抓不到这条，所以断言全落在可观察行为上：

1. 把值写进这个键 → 让失效逻辑跑一遍 → 键必须不在了（改前这里会 red）；
2. C 端路由读的必须就是同一个键：先塞哨兵值，GET 拿到哨兵才证明读口认它
   （读口若另起一个串，第 1 条仍会假绿）；
3. 键串只允许出现在 `app/cache/keys.py` 一处，防止下一次「加 :v3 只改一半」。
"""
from pathlib import Path

import pytest

from app.cache.keys import (
    CHANNELS_LIST_ACTIVE,
    CHANNELS_LIST_ALL,
    C_CHANNELS_LIST_ACTIVE,
)
from app.cache.manager import cache
from app.services.channel_service import ChannelService

APP_DIR = Path(__file__).resolve().parents[1] / "app"
KEYS_FILE = APP_DIR / "cache" / "keys.py"


@pytest.mark.asyncio
async def test_invalidate_clears_c_side_read_key(db_session):
    """写进 C 端键的值，必须被 invalidate_list_cache 清掉。"""
    await cache.set(C_CHANNELS_LIST_ACTIVE, [{"id": 1, "name": "旧频道"}], ttl=60)

    await ChannelService(db_session).invalidate_list_cache()

    assert await cache.get(C_CHANNELS_LIST_ACTIVE) is None


@pytest.mark.asyncio
async def test_invalidate_clears_admin_keys(db_session):
    """管理端两个键同样要被清：三处键名一起单源，不允许只对 C 端生效。"""
    await cache.set(CHANNELS_LIST_ALL, [{"id": 1}], ttl=60)
    await cache.set(CHANNELS_LIST_ACTIVE, [{"id": 1}], ttl=60)

    await ChannelService(db_session).invalidate_list_cache()

    assert await cache.get(CHANNELS_LIST_ALL) is None
    assert await cache.get(CHANNELS_LIST_ACTIVE) is None


@pytest.mark.asyncio
async def test_route_reads_the_key_invalidation_targets(db_session, client):
    """路由读的键 == 失效逻辑删的键：哨兵能盖住真实列表，失效后哨兵消失。"""
    sentinel = {"list": [{"id": 999999, "name": "哨兵频道"}]}
    await cache.set(C_CHANNELS_LIST_ACTIVE, sentinel, ttl=60)

    resp = client.get("/api/v1/channels")
    assert resp.status_code == 200
    assert resp.json()["data"] == sentinel, "C 端列表没有读这个键，失效就会删到空处"

    await ChannelService(db_session).invalidate_list_cache()

    ids = [c["id"] for c in client.get("/api/v1/channels").json()["data"]["list"]]
    assert 999999 not in ids


def test_key_literals_have_exactly_one_home():
    """静态门禁：三个键串只允许出现在 app/cache/keys.py。"""
    offenders = {}
    for path in APP_DIR.rglob("*.py"):
        if path == KEYS_FILE:
            continue
        text = path.read_text(encoding="utf-8")
        for literal in (CHANNELS_LIST_ALL, CHANNELS_LIST_ACTIVE, C_CHANNELS_LIST_ACTIVE):
            if literal in text:
                offenders.setdefault(str(path.relative_to(APP_DIR)), []).append(literal)

    assert offenders == {}, f"缓存键出现了第二处字面量（应改为 import app.cache.keys）：{offenders}"
