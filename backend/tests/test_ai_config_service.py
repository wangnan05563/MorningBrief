import pytest

from app.services.ai_config_service import AIConfigService, CONFIG_KEY_MAP


def test_normalize_tts_keeps_valid_edge_adjustments():
    service = AIConfigService.__new__(AIConfigService)

    result = service._normalize_tts(
        {"edge_rate": "+10%", "edge_volume": "-5%", "edge_pitch": "+2Hz"}
    )

    assert result["edge_rate"] == "+10%"
    assert result["edge_volume"] == "-5%"
    assert result["edge_pitch"] == "+2Hz"


def test_normalize_tts_treats_legacy_numeric_zero_as_no_edge_adjustment():
    service = AIConfigService.__new__(AIConfigService)

    result = service._normalize_tts({"edge_rate": "0.0", "edge_volume": 0})

    assert result["edge_rate"] == ""
    assert result["edge_volume"] == ""


def test_edge_form_keys_map_to_runtime_settings():
    assert CONFIG_KEY_MAP["edge_voice"] == "EDGE_TTS_VOICE"
    assert CONFIG_KEY_MAP["edge_rate"] == "EDGE_TTS_RATE"
    assert CONFIG_KEY_MAP["edge_volume"] == "EDGE_TTS_VOLUME"
    assert CONFIG_KEY_MAP["edge_pitch"] == "EDGE_TTS_PITCH"


# ---------------------------------------------------------------------------
# 用量统计（/usage）逻辑验证
# 根因：此前 workflow 只调用 ai_budget.record_call（内存+JSON），从不调用
# AIConfigService.record_usage，导致 ai_usage_log 表永远为空，/usage 恒为 0。
# 以下测试验证“统计聚合逻辑本身正确”，修复后真实数据即可被正确聚合展示。
# ---------------------------------------------------------------------------


async def test_get_usage_summary_aggregates_today(db_session):
    """今日统计应按 service_type 正确聚合 LLM/TTS 的调用数、token/字符、费用。"""
    from datetime import datetime as _dt, timedelta as _td
    from app.models.ai_config import AIUsageLog

    today = _dt.now().date()
    today_noon = _dt.combine(today, _dt.min.time()).replace(hour=12)
    yesterday_noon = _dt.combine(today - _td(days=1), _dt.min.time()).replace(hour=12)

    # LLM: 2 次调用
    db_session.add(AIUsageLog(service_type="llm", model="m", input_tokens=100,
                               output_tokens=50, char_count=0, cost_usd=0.01,
                               created_at=today_noon))
    db_session.add(AIUsageLog(service_type="llm", model="m", input_tokens=200,
                               output_tokens=80, char_count=0, cost_usd=0.02,
                               created_at=today_noon))
    # TTS: 3 次调用
    db_session.add(AIUsageLog(service_type="tts", model="v", input_tokens=0,
                               output_tokens=0, char_count=300, cost_usd=0.03,
                               created_at=today_noon))
    db_session.add(AIUsageLog(service_type="tts", model="v", input_tokens=0,
                               output_tokens=0, char_count=500, cost_usd=0.05,
                               created_at=today_noon))
    db_session.add(AIUsageLog(service_type="tts", model="v", input_tokens=0,
                               output_tokens=0, char_count=700, cost_usd=0.07,
                               created_at=today_noon))
    # 昨日数据不应计入今日
    db_session.add(AIUsageLog(service_type="llm", model="m", input_tokens=999,
                               output_tokens=999, char_count=0, cost_usd=9.99,
                               created_at=yesterday_noon))
    await db_session.commit()

    svc = AIConfigService(db_session)
    result = await svc.get_usage_summary()
    today_stats = result["today"]

    assert today_stats["llm_calls"] == 2
    assert today_stats["llm_tokens"] == (100 + 50) + (200 + 80)  # 430
    assert today_stats["tts_calls"] == 3
    assert today_stats["tts_chars"] == 300 + 500 + 700  # 1500
    assert today_stats["cost_usd"] == pytest.approx(0.01 + 0.02 + 0.03 + 0.05 + 0.07)

    # 7 天趋势结构正确，且今日条目聚合一致
    assert len(result["trend"]) == 7
    today_entry = next(t for t in result["trend"] if t["date"] == today.isoformat())
    assert today_entry["llm_calls"] == 2
    assert today_entry["tts_calls"] == 3
    assert today_entry["cost_usd"] == pytest.approx(0.18)


async def test_record_usage_persists_and_summary_reflects(db_session):
    """record_usage 应写库，且 get_usage_summary 立即反映该条记录。"""
    svc = AIConfigService(db_session)
    await svc.record_usage(
        service_type="llm", model="m", input_tokens=10, output_tokens=20
    )
    await db_session.commit()

    result = await svc.get_usage_summary()
    assert result["today"]["llm_calls"] == 1
    assert result["today"]["llm_tokens"] == 30



# ---------------------------------------------------------------------------
# T01729：ai_config 写路径补齐 llm_max_script_segments
# 根因：LLMConfigBody 与 _normalize_llm 均无该键 → PUT 被静默丢弃，
# T00584「管理端热调段数（30 分钟听书档 18~20）」实际不可用。
# ---------------------------------------------------------------------------


def test_normalize_llm_persists_max_script_segments():
    """写路径应把 llm_max_script_segments 转为 config_key -> 字符串值。"""
    service = AIConfigService.__new__(AIConfigService)

    result = service._normalize_llm({"llm_max_script_segments": 18})

    assert result["llm_max_script_segments"] == "18"


def test_int_keys_cover_max_script_segments_for_hot_apply():
    """热更链 _apply_to_settings 依赖 INT_KEYS 做 int 转换，漏掉会存成字符串。"""
    from app.services.ai_config_service import INT_KEYS

    assert "llm_max_script_segments" in INT_KEYS


async def test_put_then_get_roundtrip_max_script_segments(client, admin_token):
    """API 级闭环：PUT 落库 + Settings 热更 + GET 回读。"""
    headers = {"Authorization": f"Bearer {admin_token['token']}"}

    # 先 GET 组装完整 body 再改段数，避免 PUT 清空其他 llm 字段（与前端保存行为一致）
    current = client.get("/admin/api/v1/ai/config", headers=headers).json()["data"]
    body = {
        "llm": {**current["llm"], "llm_max_script_segments": 18},
        "tts": current["tts"],
        "selected_preset": current["llm"].get("selected_preset", ""),
    }

    resp = client.put("/admin/api/v1/ai/config", json=body, headers=headers)
    assert resp.status_code == 200, resp.text

    from app.config import get_settings

    assert get_settings().LLM_MAX_SCRIPT_SEGMENTS == 18

    back = client.get("/admin/api/v1/ai/config", headers=headers).json()["data"]
    assert back["llm"]["llm_max_script_segments"] == 18

    # 恢复默认：settings 为进程级单例，防止污染同进程后续测试
    body["llm"]["llm_max_script_segments"] = 10
    client.put("/admin/api/v1/ai/config", json=body, headers=headers)
    assert get_settings().LLM_MAX_SCRIPT_SEGMENTS == 10
