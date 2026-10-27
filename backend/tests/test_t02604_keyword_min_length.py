"""T02604：关键词白名单的长度护栏（裁决方案1）。

口径：匹配方式（大小写不敏感的子串包含）**不动**，改在录入侧拦住过短的关键词。
所以本文件既测「短词被拦」，也测「判定语义没被顺手改掉」——
后者是裁决里明确要避免的事故：现有白名单不能突然全部不命中。
"""
import json
from datetime import date

import pytest

from app.core import keyword_guard
from app.core.exceptions import BizError
from app.models import Review, Script
from app.services.auto_review_service import AutoReviewService


class _SessionCtx:
    """`_check_keyword_whitelist` 内部自开 AsyncSessionLocal，这里把它接到测试会话。"""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


async def _seed_script(db, workflow_id: str, full_text: str) -> None:
    today = date(2026, 10, 27)
    script = Script(
        workflow_id=workflow_id, episode_date=today,
        full_text=full_text, segments=[{"seq": 1, "content": full_text}],
    )
    db.add(script)
    await db.flush()
    db.add(Review(
        workflow_id=workflow_id, episode_date=today,
        script_id=script.id, audio_url="local://t02604.mp3",
    ))
    await db.flush()


# ---- 规则本体 ----


def test_single_cjk_char_is_rejected():
    # 实测「中」「了」在 83 篇历史稿件里各命中 82 篇，等于无条件放行
    assert keyword_guard.too_short("中")
    assert keyword_guard.find_too_short(["时政", "中", "AI"]) == ["中", "AI"]


def test_ascii_abbreviation_is_rejected_but_longer_word_passes():
    assert keyword_guard.too_short("AI")
    assert keyword_guard.too_short("OK")
    assert not keyword_guard.too_short("OpenAI")


def test_three_letter_ascii_term_is_not_rejected():
    """下限取 3 而不是 4 的依据：3 字母词在 83 篇语料里没有内嵌误命中。

    PS5 8 篇 / CEO 3 篇 / iOS 2 篇，词边界与子串命中数相同（内嵌 0 篇）；
    把下限抬到 4 会连这类干净词一起拦掉，属于没有数据支持的过度收紧。
    """
    assert not keyword_guard.too_short("PS5")
    assert not keyword_guard.too_short("CEO")
    assert not keyword_guard.too_short("NBA")
    assert keyword_guard.min_length("PS5") == keyword_guard.MIN_LENGTH_ASCII
    assert keyword_guard.min_length("游戏") == keyword_guard.MIN_LENGTH_NON_ASCII


def test_two_char_cjk_word_passes():
    # 裁决只拦「过短」，两字词是管理员常用的有效粒度，不能被一并拦掉
    assert not keyword_guard.too_short("时政")
    assert not keyword_guard.too_short("人工智能")
    assert not keyword_guard.too_short("AI审核")


def test_limits_payload_carries_both_thresholds():
    assert keyword_guard.limits_payload() == {
        "min_length": keyword_guard.MIN_LENGTH_NON_ASCII,
        "ascii_min_length": keyword_guard.MIN_LENGTH_ASCII,
        "rule": "substring",
    }


def test_reject_message_names_the_word_and_the_rule():
    msg = keyword_guard.reject_message(["中"])
    assert "中" in msg and "子串" in msg


# ---- 保存路径：拦住，但匹配语义不动 ----


@pytest.mark.asyncio
async def test_update_config_rejects_short_keyword(db_session):
    svc = AutoReviewService(db_session)
    with pytest.raises(BizError) as exc:
        await svc.update_config(
            enabled=False, require_content_safe=True,
            require_steps_first_success=True, keyword_whitelist=["AI"],
            operator="admin",
        )
    assert exc.value.code == 400
    assert "AI" in exc.value.message
    # 被拦下就不能留下半截配置
    assert svc.parse_keywords((await svc.get_config()).keyword_whitelist) == []


@pytest.mark.asyncio
async def test_update_config_accepts_normal_keyword(db_session):
    svc = AutoReviewService(db_session)
    await svc.update_config(
        enabled=False, require_content_safe=True,
        require_steps_first_success=True, keyword_whitelist=["人工智能"],
        operator="admin",
    )
    assert svc.parse_keywords((await svc.get_config()).keyword_whitelist) == ["人工智能"]


@pytest.mark.asyncio
async def test_matcher_still_uses_substring_for_legacy_short_keyword(db_session, monkeypatch):
    """存量短词照旧按子串命中：本单只加录入护栏，不改判定，免得白名单突然全部不命中。"""
    import app.services.auto_review_service as mod
    monkeypatch.setattr(mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))

    config = await AutoReviewService(db_session).get_config()
    config.keyword_whitelist = json.dumps(["中"], ensure_ascii=False)
    await db_session.flush()

    await _seed_script(db_session, "wf-t02604-sub", "中国队夺冠")
    svc = AutoReviewService(db_session)
    keywords = svc.parse_keywords((await svc.get_config()).keyword_whitelist)

    ok, msg = await svc._check_keyword_whitelist("wf-t02604-sub", keywords)
    assert ok is True
    assert "命中关键词" in msg


@pytest.mark.asyncio
async def test_matcher_still_hits_inside_a_longer_word(db_session, monkeypatch):
    """大小写不敏感的子串语义不动：「AI」在「OpenAI」里仍算命中。

    这条是「别顺手改成词边界匹配」的钉子——裁决只拦长度，判定口径一个字都没动。
    """
    import app.services.auto_review_service as mod
    monkeypatch.setattr(mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))

    await _seed_script(db_session, "wf-t02604-inner", "OpenAI 发布了新模型")
    ok, msg = await AutoReviewService(db_session)._check_keyword_whitelist(
        "wf-t02604-inner", ["ai"],
    )
    assert ok is True
    assert "ai" in msg


# ---- 端点 ----


@pytest.mark.asyncio
async def test_config_endpoint_exposes_limits_for_the_ui(client, admin_token, db_session):
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    data = client.get("/admin/api/v1/auto-review/config", headers=headers).json()["data"]
    assert data["keyword_limits"] == keyword_guard.limits_payload()


@pytest.mark.asyncio
async def test_config_endpoint_rejects_short_keyword(client, admin_token, db_session):
    headers = {"Authorization": f"Bearer {admin_token['token']}"}
    resp = client.put(
        "/admin/api/v1/auto-review/config",
        json={
            "enabled": True, "require_content_safe": True,
            "require_steps_first_success": True, "keyword_whitelist": ["AI"],
            "risk_acknowledged": True,
        },
        headers=headers,
    )
    # 与其他护栏同口径：HTTP 200 + 业务码 400，前端才拿得到这句话
    assert resp.json()["code"] == 400
    assert "AI" in resp.json()["message"]

    ok = client.put(
        "/admin/api/v1/auto-review/config",
        json={
            "enabled": True, "require_content_safe": True,
            "require_steps_first_success": True, "keyword_whitelist": ["央视新闻"],
            "risk_acknowledged": True,
        },
        headers=headers,
    )
    assert ok.json()["code"] == 0
    assert ok.json()["data"]["keyword_whitelist"] == ["央视新闻"]
