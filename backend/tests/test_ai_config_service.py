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
