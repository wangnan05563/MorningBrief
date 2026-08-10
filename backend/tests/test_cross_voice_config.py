"""交叉音色配置往返（前端对象 <-> 后端 JSON 字符串）单元测试。

验证 _normalize_tts 序列化与 _parse_cross_voice 规范化解析，确保配置落库结构稳定、
解析失败安全回退，不阻断配置读写主流程。
"""
import json

from app.services.ai_config_service import (
    AIConfigService,
    CONFIG_KEY_MAP,
    _parse_cross_voice,
)


def _svc():
    # 不触发 __init__（避免依赖 DB session）
    return AIConfigService.__new__(AIConfigService)


def test_cross_voice_key_maps_to_settings():
    assert CONFIG_KEY_MAP["tts_cross_voice"] == "TTS_CROSS_VOICE"


def test_normalize_tts_serializes_cross_voice():
    cv = {
        "enabled": True,
        "strategy": "round_robin",
        "interval": 2,
        "voices": {"edge": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunyangNeural"]},
    }
    result = _svc()._normalize_tts({"cross_voice": cv})
    assert "tts_cross_voice" in result
    stored = json.loads(result["tts_cross_voice"])
    assert stored["enabled"] is True
    assert stored["voices"]["edge"] == ["zh-CN-XiaoxiaoNeural", "zh-CN-YunyangNeural"]


def test_normalize_tts_cross_voice_none_clears():
    result = _svc()._normalize_tts({"cross_voice": None})
    assert json.loads(result["tts_cross_voice"]) == {}


def test_parse_cross_voice_handles_invalid_json():
    assert _parse_cross_voice("not-json")["enabled"] is False
    assert _parse_cross_voice(None)["enabled"] is False
    assert _parse_cross_voice(123)["enabled"] is False


def test_parse_cross_voice_round_trip():
    raw = {
        "enabled": True,
        "strategy": "interval",
        "interval": 3,
        "voices": {"edge": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunjianNeural"]},
    }
    parsed = _parse_cross_voice(raw)
    assert parsed["enabled"] is True
    assert parsed["strategy"] == "interval"
    assert parsed["interval"] == 3
    assert parsed["voices"]["edge"] == ["zh-CN-XiaoxiaoNeural", "zh-CN-YunjianNeural"]


def test_parse_cross_voice_normalizes_voice_list_types():
    # 非字符串元素被过滤，保证落库结构干净
    parsed = _parse_cross_voice({"voices": {"edge": ["a", 2, None, "b"]}})
    assert parsed["voices"]["edge"] == ["a", "b"]


def test_parse_cross_voice_missing_voices_defaults_empty():
    parsed = _parse_cross_voice({"enabled": True})
    assert parsed["voices"] == {}
    assert parsed["enabled"] is True
