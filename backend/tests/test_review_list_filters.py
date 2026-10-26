"""审核列表筛选扩参（T02804 / FR-UX-703 B4 剩余）。

工单要求补齐四类定位能力：workflow_id 已有，本单新增审核人 / 节目日期 / 频道。
两条口径必须由用例锁住，否则「界面上有框、跨页结果却错」会重新出现：

1. **日期按 episode_date**（列表「日期」列展示的那一列），不是 created_at。
   两者混用时用户筛了 10 月，列表里 10 月那行却不出现——本文件用「同一天创建的记录
   分别落在不同 episode_date」把口径差异固定下来。
2. **审核人前缀匹配要转义通配符**：`?reviewer=%` 若直接拼进 LIKE 会匹配所有人，
   表现为「筛选没生效」，且用户无法自查。

另外覆盖：区间两端闭区间（date_from == date_to）、跨月、频道过滤（含无工作流的孤儿审核）、
以及非法参数的 HTTP 口径（日期格式错 / from > to / channel_id=0 / reviewer 超长 → 400）。
"""
from datetime import date

import pytest

from app.core.exceptions import ParamError
from app.models import Channel, Review, Script, Workflow
from app.services.review_service import ReviewService

REVIEWS_API = "/admin/api/v1/reviews"


async def _review(
    db,
    *,
    workflow_id="wf-001",
    episode_date=None,
    reviewer_name=None,
    status="pending",
):
    """创建一条审核记录（含必需关联 script）。"""
    day = episode_date or date(2026, 10, 1)
    script = Script(
        workflow_id=workflow_id,
        episode_date=day,
        full_text="稿件全文",
        segments=[{"seq": 1, "content": "段"}],
    )
    db.add(script)
    await db.flush()
    review = Review(
        workflow_id=workflow_id,
        episode_date=day,
        script_id=script.id,
        audio_url="http://cdn/test.mp3",
        status=status,
        reviewer_name=reviewer_name,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


async def _channel_with_workflow(db, name, workflow_id):
    ch = Channel(name=name)
    db.add(ch)
    await db.flush()
    db.add(Workflow(
        id=workflow_id,
        episode_date=date(2026, 10, 1),
        source="cron",
        channel_id=ch.id,
    ))
    await db.commit()
    await db.refresh(ch)
    return ch


def _names(result):
    return sorted(item["reviewer_name"] or "" for item in result["list"])


# ---------------------------------------------------------------- 审核人


@pytest.mark.asyncio
async def test_reviewer_prefix_filter(db_session):
    """审核人按前缀匹配：'al' 命中 alice/alina，'alice' 只命中 alice。"""
    await _review(db_session, workflow_id="wf-1", reviewer_name="alice")
    await _review(db_session, workflow_id="wf-2", reviewer_name="alina")
    await _review(db_session, workflow_id="wf-3", reviewer_name="bob")
    await _review(db_session, workflow_id="wf-4", reviewer_name=None)

    svc = ReviewService(db_session)
    both = await svc.list_reviews(status="", page=1, size=10, reviewer="al")
    assert _names(both) == ["alice", "alina"]

    single = await svc.list_reviews(status="", page=1, size=10, reviewer="alice")
    assert _names(single) == ["alice"], "前缀匹配不应退化成包含匹配"

    none = await svc.list_reviews(status="", page=1, size=10, reviewer="zzz")
    assert none["total"] == 0


@pytest.mark.asyncio
async def test_reviewer_wildcards_are_literal(db_session):
    """`%` / `_` 必须当字面量：否则 ?reviewer=% 等于「不筛选」。"""
    await _review(db_session, workflow_id="wf-1", reviewer_name="alice")
    await _review(db_session, workflow_id="wf-2", reviewer_name="100%real_mark")

    svc = ReviewService(db_session)

    percent_only = await svc.list_reviews(status="", page=1, size=10, reviewer="%")
    assert percent_only["total"] == 0, "未转义的 % 会匹配所有审核人"

    literal = await svc.list_reviews(status="", page=1, size=10, reviewer="100%")
    assert _names(literal) == ["100%real_mark"]

    underscore = await svc.list_reviews(status="", page=1, size=10, reviewer="real_")
    assert underscore["total"] == 0, "未转义的 _ 会当成任意单字符（real% 才能命中）"


# ---------------------------------------------------------------- 日期


@pytest.mark.asyncio
async def test_date_range_single_day_is_inclusive(db_session):
    """date_from == date_to 时两端都算（闭区间），不能漏掉当天。"""
    await _review(db_session, workflow_id="wf-1", episode_date=date(2026, 1, 31))
    await _review(db_session, workflow_id="wf-2", episode_date=date(2026, 2, 1))

    svc = ReviewService(db_session)
    same_day = await svc.list_reviews(
        status="", page=1, size=10,
        date_from=date(2026, 1, 31), date_to=date(2026, 1, 31),
    )
    assert same_day["total"] == 1
    assert same_day["list"][0]["episode_date"] == "2026-01-31"


@pytest.mark.asyncio
async def test_date_range_cross_month(db_session):
    """跨月区间按字符串/日期比较都要正确。"""
    await _review(db_session, workflow_id="wf-1", episode_date=date(2026, 1, 31))
    await _review(db_session, workflow_id="wf-2", episode_date=date(2026, 2, 1))
    await _review(db_session, workflow_id="wf-3", episode_date=date(2026, 2, 2))

    svc = ReviewService(db_session)
    result = await svc.list_reviews(
        status="", page=1, size=10,
        date_from=date(2026, 1, 31), date_to=date(2026, 2, 1),
    )
    assert result["total"] == 2
    assert {item["episode_date"] for item in result["list"]} == {"2026-01-31", "2026-02-01"}


@pytest.mark.asyncio
async def test_date_range_uses_episode_date_not_created_at(db_session):
    """口径锁：筛选按 episode_date，不按 created_at。

    两条记录的 created_at 都是「现在」，但 episode_date 一个是 10-01、一个是 10-20。
    按 10-20 筛只能取到后者——如果有人把条件改成 created_at，这条会立刻变红。
    """
    early = await _review(db_session, workflow_id="wf-1", episode_date=date(2026, 10, 1))
    late = await _review(db_session, workflow_id="wf-2", episode_date=date(2026, 10, 20))

    svc = ReviewService(db_session)
    result = await svc.list_reviews(
        status="", page=1, size=10,
        date_from=date(2026, 10, 20), date_to=date(2026, 10, 20),
    )
    ids = [item["id"] for item in result["list"]]
    assert ids == [late.id]
    assert early.id not in ids


@pytest.mark.asyncio
async def test_inverted_date_range_raises_param_error(db_session):
    """from > to 是参数错误（HTTP 400），不是「查无数据」。"""
    svc = ReviewService(db_session)
    with pytest.raises(ParamError) as exc:
        await svc.list_reviews(
            status="", page=1, size=10,
            date_from=date(2026, 2, 2), date_to=date(2026, 2, 1),
        )
    assert exc.value.code == 400
    assert exc.value.http_status == 400
    assert "date_from" in exc.value.message


# ---------------------------------------------------------------- 频道


@pytest.mark.asyncio
async def test_channel_filter_matches_workflow_channel(db_session):
    """频道过滤走 Review.workflow_id → Workflow.channel_id。"""
    ch_a = await _channel_with_workflow(db_session, "频道A", "wf-a")
    ch_b = await _channel_with_workflow(db_session, "频道B", "wf-b")
    in_a = await _review(db_session, workflow_id="wf-a", reviewer_name="alice")
    in_b = await _review(db_session, workflow_id="wf-b", reviewer_name="bob")
    orphan = await _review(db_session, workflow_id="wf-missing", reviewer_name="carol")

    svc = ReviewService(db_session)
    only_a = await svc.list_reviews(status="", page=1, size=10, channel_id=ch_a.id)
    assert [item["id"] for item in only_a["list"]] == [in_a.id]
    assert only_a["list"][0]["channel_name"] == "频道A"

    only_b = await svc.list_reviews(status="", page=1, size=10, channel_id=ch_b.id)
    assert [item["id"] for item in only_b["list"]] == [in_b.id]
    assert orphan.id not in [item["id"] for item in only_b["list"]]


@pytest.mark.asyncio
async def test_filters_combine(db_session):
    """多个条件是与关系，且 count 与 list 口径一致。"""
    ch = await _channel_with_workflow(db_session, "频道A", "wf-a")
    hit = await _review(
        db_session, workflow_id="wf-a", episode_date=date(2026, 10, 20),
        reviewer_name="alice", status="approved",
    )
    await _review(
        db_session, workflow_id="wf-a", episode_date=date(2026, 10, 20),
        reviewer_name="bob", status="approved",
    )
    await _review(
        db_session, workflow_id="wf-a", episode_date=date(2026, 10, 19),
        reviewer_name="alice", status="approved",
    )

    svc = ReviewService(db_session)
    result = await svc.list_reviews(
        status="approved", page=1, size=10,
        reviewer="ali", date_from=date(2026, 10, 20), date_to=date(2026, 10, 20),
        channel_id=ch.id,
    )
    assert result["total"] == 1
    assert [item["id"] for item in result["list"]] == [hit.id]


# ---------------------------------------------------------------- HTTP 层


@pytest.fixture
def stub_blacklist(monkeypatch):
    """绕过 is_in_blacklist 的库查询，避免测试命中生产 SQLite（与各路由测试同法）。"""

    async def _always_false(jti: str) -> bool:
        return False

    monkeypatch.setattr("app.core.auth.is_in_blacklist", _always_false)


def _auth(token):
    return {"Authorization": f"Bearer {token['token']}"}


@pytest.mark.asyncio
async def test_http_filter_params_take_effect(client, db_session, admin_token, stub_blacklist):
    """HTTP 层把四个参数原样交给 service：用真实数据断言，而不是只看 200。"""
    ch = await _channel_with_workflow(db_session, "频道A", "wf-a")
    await _channel_with_workflow(db_session, "频道B", "wf-b")
    hit = await _review(
        db_session, workflow_id="wf-a", episode_date=date(2026, 10, 20),
        reviewer_name="alice", status="approved",
    )
    await _review(
        db_session, workflow_id="wf-b", episode_date=date(2026, 10, 20),
        reviewer_name="alice", status="approved",
    )

    resp = client.get(REVIEWS_API, params={
        "status": "approved",
        "reviewer": "ali",
        "date_from": "2026-10-20",
        "date_to": "2026-10-20",
        "channel_id": ch.id,
    }, headers=_auth(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["total"] == 1
    assert [item["id"] for item in body["data"]["list"]] == [hit.id]


@pytest.mark.asyncio
async def test_http_invalid_date_format_is_400(client, admin_token, stub_blacklist):
    """日期格式错走 RequestValidationError → HTTP 400 + code=400（不是 200 信封）。"""
    resp = client.get(REVIEWS_API, params={"date_from": "2026/10/20"},
                      headers=_auth(admin_token))
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["code"] == 400
    assert "date_from" in body["message"]


@pytest.mark.asyncio
async def test_http_invalid_calendar_date_is_400(client, admin_token, stub_blacklist):
    """2026-02-30 不是合法日期，不能被 pydantic 当成字符串放过去。"""
    resp = client.get(REVIEWS_API, params={"date_to": "2026-02-30"},
                      headers=_auth(admin_token))
    assert resp.status_code == 400, resp.text
    assert "date_to" in resp.json()["message"]


@pytest.mark.asyncio
async def test_http_inverted_range_is_400_with_message(client, admin_token, stub_blacklist):
    """区间反了要明确说「不能晚于」，而不是返回空列表让用户以为没数据。"""
    resp = client.get(REVIEWS_API, params={
        "date_from": "2026-10-21", "date_to": "2026-10-20",
    }, headers=_auth(admin_token))
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["code"] == 400
    assert "不能晚于" in body["message"]


@pytest.mark.asyncio
async def test_http_channel_id_must_be_positive(client, admin_token, stub_blacklist):
    resp = client.get(REVIEWS_API, params={"channel_id": 0}, headers=_auth(admin_token))
    assert resp.status_code == 400, resp.text
    assert "channel_id" in resp.json()["message"]


@pytest.mark.asyncio
async def test_http_reviewer_length_capped(client, admin_token, stub_blacklist):
    """审核人超过 64 字符直接判 400：与 reviewer_name 列宽一致，不静默截断。"""
    resp = client.get(REVIEWS_API, params={"reviewer": "a" * 65},
                      headers=_auth(admin_token))
    assert resp.status_code == 400, resp.text
    assert "reviewer" in resp.json()["message"]
