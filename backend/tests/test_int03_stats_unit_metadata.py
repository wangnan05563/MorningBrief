"""INT-UX-03：`GET /admin/api/v1/stats/*` 一律带 unit/scale 元数据。

FR-UX-501（T02506）已经把 overview / trend 的单位收进 `meta`，展示端不再猜「这是秒还是分」。
剩下的口子是同一族里最危险的两个：

- `/stats/llm-metrics` 的 `*_rate` 是**已经乘过 100 的百分数**，而 `/stats/overview`
  的 `completion_rate` 是 **0~1 的比值**。两端都叫 rate，换算方向却相反；页面各自写死
  `%` 时看不出来，一旦有人把 llm-metrics 也接到共用格式化器（`metricValue` 会乘
  `display.factor`）上，47% 就变成 4700%。
- `/stats/rss-health` 的 `latency_ms` 表头写死「 ms」，是 PRD 点名要消掉的「页面自己标单位」。
- `/stats/channel-health` 的折线不画坐标轴，峰值与悬停全靠「条」这个字，页面写「条」、
  别处写「次」时没人会发现不一致。

本文件钉三件事：响应带 meta、meta 与数值实际量级一致、换算规则全局统一
（`unit == percent ⇒ factor == 1`，`unit == ratio ⇒ factor == 100`）。
"""
import pytest

from app.services.stats_metrics import METRIC_META

BASE = "/admin/api/v1/stats"

LLM_FIELDS = [
    "total_calls", "triggered", "improved", "not_improved",
    "trigger_rate", "improve_rate", "not_improve_rate",
]


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


@pytest.fixture
def llm_counters():
    """把真实计数器设成已知值，让端点自己算率；用完原样还回去。

    不打桩 `get_word_count_retry_stats`：那样测的是「我 stub 返回什么，meta 就说什么」，
    派生率本身算错（比如忘了 ×100）就漏掉了。这里改 `rewriter._WORD_COUNT_RETRY_STATS`，
    走真实推导。
    """
    from app.workflow.llm import rewriter

    counters = rewriter._WORD_COUNT_RETRY_STATS
    saved = dict(counters)

    def _set(total, triggered, improved, not_improved):
        counters.update({
            "total_calls": total, "triggered": triggered,
            "improved": improved, "not_improved": not_improved,
        })

    yield _set
    counters.update(saved)


def _scale_rule(field, m):
    """换算方向必须跟着 unit 走——这是把两类 rate 区分开的唯一依据。"""
    unit = m["unit"]
    factor = m["display"]["factor"]
    if unit == "percent":
        assert factor == 1, f"{field}: 值已是 0~100，factor={factor} 会二次换算"
    if unit == "ratio":
        assert factor == 100, f"{field}: 值仍是 0~1，factor={factor} 会把比值当百分数显示"
    if unit in ("count", "millisecond", "second"):
        assert factor in (1, 1 / 60), f"{field}: 计数/时长类不该出现 {factor} 这种换算"


def test_scale_rule_holds_for_the_whole_registry():
    """整张登记表都守同一条换算规则。

    覆盖 T02506 已登记的 completion_rate（ratio→×100）与本单新增的 trigger_rate
    （percent→×1）。有人照抄隔壁条目把 factor 写错，这里就红。
    """
    for field, m in METRIC_META.items():
        _scale_rule(field, m)


async def test_llm_metrics_publishes_meta(client, auth, llm_counters):
    """触发率/改善率必须随数据下发单位，页面才能不再自己写死 %。"""
    llm_counters(8, 4, 1, 3)
    data = client.get(f"{BASE}/llm-metrics", headers=auth).json()["data"]

    for f in LLM_FIELDS:
        assert f in data["meta"], f
        assert data["meta"][f]["label"]
    # 值已经是百分数：meta 的换算必须是「不再乘任何数」，否则页面显示 5000%
    assert data["meta"]["trigger_rate"]["unit"] == "percent"
    assert data["meta"]["trigger_rate"]["display"]["unit"] == "%"
    assert data["meta"]["trigger_rate"]["display"]["factor"] == 1
    assert data["trigger_rate"] * data["meta"]["trigger_rate"]["display"]["factor"] == 50.0


async def test_llm_rate_meta_agrees_with_the_derivation(client, auth, llm_counters):
    """meta 说的量级，要和 rewriter 真正算出来的数一致（不能 meta 一套、算另一套）。"""
    llm_counters(8, 2, 1, 1)
    data = client.get(f"{BASE}/llm-metrics", headers=auth).json()["data"]
    # 2/8 = 0.25 → 后端给的是 25（百分数），不是 0.25（比值）
    assert data["trigger_rate"] == pytest.approx(25.0)
    assert data["meta"]["trigger_rate"]["unit"] == "percent"
    # 计数器为零时率是 0，不是 null：meta 仍要能解释这个 0
    llm_counters(0, 0, 0, 0)
    empty = client.get(f"{BASE}/llm-metrics", headers=auth).json()["data"]
    assert empty["trigger_rate"] == 0.0
    assert empty["meta"]["trigger_rate"]["unit"] == "percent"


async def test_rss_health_publishes_latency_unit(client, auth, monkeypatch):
    """latency_ms 的单位由接口下发，表头不再写死「 ms」。"""
    monkeypatch.setattr(
        "app.services.rss_source_service.get_source_status",
        lambda: {
            "sources": [{"name": "A", "url": "http://a/rss", "status": "ok",
                         "last_check": None, "consecutive_failures": 0,
                         "latency_ms": 812, "last_error": None, "suggestion": None}],
            "ok_count": 1, "fail_count": 0, "unknown_count": 0, "total": 1,
        },
    )
    data = client.get(f"{BASE}/rss-health", headers=auth).json()["data"]
    assert data["meta"]["latency_ms"]["unit"] == "millisecond"
    assert data["meta"]["latency_ms"]["display"]["factor"] == 1
    assert data["meta"]["consecutive_failures"]["unit"] == "count"


async def test_channel_health_publishes_count_unit(client, auth):
    """`/stats/*` 里最后一条：折线峰值/悬停写死「条」，单位同样要由接口下发。"""
    data = client.get(
        f"{BASE}/channel-health", params={"range_days": 7}, headers=auth
    ).json()["data"]
    assert data["meta"]["count"]["unit"] == "count"
    assert data["meta"]["count"]["display"]["unit"] == "条"
    assert data["meta"]["count"]["display"]["factor"] == 1


async def test_every_stats_endpoint_carries_meta(client, auth):
    """PRD 写的是 `/stats/*`，不是其中两条：漏一条就没人知道它漏了。

    新增统计端点时这里会红，逼作者把单位登记进 stats_metrics 而不是页面里写死。
    """
    queries = {
        "overview": {"date": "2026-01-05"},
        "trend": {"metric": "dau", "range": "7d"},
        "channel-health": {"range_days": 7},
        "rss-health": {},
        "llm-metrics": {},
    }
    for ep, params in queries.items():
        body = client.get(f"{BASE}/{ep}", params=params, headers=auth).json()
        assert body["code"] == 0, ep
        assert body["data"].get("meta"), f"{ep} 未下发 unit/scale 元数据"


async def test_existing_stats_endpoints_keep_their_meta(client, auth):
    """T02506 已交付的两条不受影响：overview / trend 仍各自带 meta。"""
    ov = client.get(f"{BASE}/overview", params={"date": "2026-01-05"}, headers=auth).json()
    assert ov["code"] == 0
    assert ov["data"]["meta"]["completion_rate"]["display"]["factor"] == 100
    tr = client.get(
        f"{BASE}/trend", params={"metric": "avg_listen_duration", "range": "7d"}, headers=auth
    ).json()["data"]
    assert tr["meta"]["avg_listen_duration"]["display"]["unit"] == "分钟"
