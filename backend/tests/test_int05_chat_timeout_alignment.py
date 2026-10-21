"""INT-UX-05（T02528）：后端问答超时与前端预算的「对齐」得由后端兜住。

PRD §7 第 219 行这条写的是「前端超时覆盖；后端超时与网关实测对齐」。前半句 T02515
已经做完（`api/aiChat.js` 的 130s 显式超时 + 跨端单测）。后半句原来只有一处**页面**
约束：`AIConfig.vue` 里 `<el-input-number :max="125">`。

页面上限拦不住真正的风险来源：
- `PUT /admin/api/v1/ai/config` 的 body 里 `chat_timeout_sec: int = 120` 没有范围校验，
  直接调接口（或以后加的任何写路径、历史脏数据）可以把它写成 600；
- 该值会经热更覆盖进程内 Settings 单例，下一次问答就用 600s；
- 于是「后端先到点、返回可重试提示」这条契约反过来了——先到点的是浏览器的 130s，
  用户看到的又是没有重试入口的网络错误，正是 FR-UX-701 当初要消灭的那个缺陷。

网关侧实测结论（DEC-UX-003，2026-10-22，见 result_T02528.md）：Tailscale Funnel 对
「请求已发出、origin 300 秒不返回任何字节」的 GET / 200 秒的 POST 都不截断，
所以这里唯一的时间预算是前端 130s，而不是网关。上限因此取 125（留 5s 回传余量），
并且要能在后端被强制执行。
"""

import pytest

from app.config import get_settings


async def _put_chat_timeout(client, admin_token, value):
    """照管理端的做法 PUT 整份配置，只改 chat_timeout_sec。"""
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    current = client.get("/admin/api/v1/ai/config", headers=headers).json()["data"]
    body = {
        "llm": {**current["llm"], "chat_timeout_sec": value},
        "tts": current["tts"],
        "selected_preset": current["llm"].get("selected_preset", ""),
    }
    return client.put("/admin/api/v1/ai/config", json=body, headers=headers), headers


@pytest.fixture(autouse=True)
def _default_timeout(client, admin_token):
    """每条用例跑完把问答超时放回默认值。

    要恢复两处：Settings 是进程级单例（热更写的就是它），而库里那条
    llm_chat_timeout_sec 要是留在 125，隔壁 test_ai_chat_timeout.py 的
    「读路径默认返显 120」断言就会无辜变红。
    """
    yield
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    current = client.get("/admin/api/v1/ai/config", headers=headers).json()["data"]
    client.put(
        "/admin/api/v1/ai/config",
        json={
            "llm": {**current["llm"], "chat_timeout_sec": 120},
            "tts": current["tts"],
            "selected_preset": current["llm"].get("selected_preset", ""),
        },
        headers=headers,
    )
    get_settings().LLM_CHAT_TIMEOUT_SEC = 120


async def test_timeout_beyond_frontend_budget_is_rejected(client, admin_token):
    """>前端 130s 的问答超时必须被拒：那种配置下先到点的永远是浏览器。"""
    resp, _ = await _put_chat_timeout(client, admin_token, 600)

    assert resp.status_code == 400, f"越界值被照单全收：{resp.status_code} {resp.text[:200]}"
    body = resp.json()
    assert body["code"] != 0
    # 提示要能被行动：说清上限是多少、为什么是这个数
    assert "125" in body["message"], body["message"]
    assert get_settings().LLM_CHAT_TIMEOUT_SEC == 120, "被拒的配置不应已经热更进 Settings"


async def test_timeout_below_useful_floor_is_rejected(client, admin_token):
    """下限 30s：比这小的值让「长回答（>60s）不中断」（ACC-UX-701）直接不成立。"""
    resp, _ = await _put_chat_timeout(client, admin_token, 5)

    assert resp.status_code == 400, resp.text[:200]
    assert "30" in resp.json()["message"]
    assert get_settings().LLM_CHAT_TIMEOUT_SEC == 120


async def test_timeout_within_budget_still_saves_and_hot_applies(client, admin_token):
    """合法区间不能被顺手拦掉——T01729 那类「白名单漏键」的反面是校验过宽。"""
    resp, headers = await _put_chat_timeout(client, admin_token, 125)
    assert resp.status_code == 200, resp.text[:200]
    assert get_settings().LLM_CHAT_TIMEOUT_SEC == 125

    back = client.get("/admin/api/v1/ai/config", headers=headers).json()["data"]
    assert back["llm"]["chat_timeout_sec"] == 125


async def test_floor_and_ceiling_come_from_one_place(client, admin_token):
    """边界值本身要可查：拒 124 与拒 126 用的是同一对常量，别在两处各写一个数。"""
    settings = get_settings()
    assert settings.LLM_CHAT_TIMEOUT_SEC == 120
    assert settings.LLM_CHAT_TIMEOUT_MIN_SEC == 30
    # 上限必须严格小于前端 130s（这条是跨端契约的后端半边）
    assert settings.LLM_CHAT_TIMEOUT_MAX_SEC < 130
    assert settings.LLM_CHAT_TIMEOUT_MIN_SEC <= settings.LLM_CHAT_TIMEOUT_SEC
    assert settings.LLM_CHAT_TIMEOUT_SEC <= settings.LLM_CHAT_TIMEOUT_MAX_SEC

    # 刚好在上限内 → 通过；刚过界 → 拒。用相邻值证明校验读的是常量而不是硬编码字面量
    ok, _ = await _put_chat_timeout(client, admin_token, settings.LLM_CHAT_TIMEOUT_MAX_SEC)
    assert ok.status_code == 200, ok.text[:200]
    bad, _ = await _put_chat_timeout(
        client, admin_token, settings.LLM_CHAT_TIMEOUT_MAX_SEC + 1
    )
    assert bad.status_code == 400
