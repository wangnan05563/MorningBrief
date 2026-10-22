"""T02902：AI 配置数值区间必须在接口层校验（对照 AIConfig.vue 的 :min/:max）。

判据：用越界值直接 PUT /admin/api/v1/ai/config，接口必须 4xx，
且进程内 Settings 与 GET 回读都不变（不得半份写入/热更脏值）。
"""
import pytest

from app.config import get_settings

URL = "/admin/api/v1/ai/config"

# (section, field, 越界值, Settings 属性名)
OUT_OF_RANGE = [
    ("llm", "timeout_sec", 4, "LLM_TIMEOUT_SEC"),
    ("llm", "timeout_sec", 121, "LLM_TIMEOUT_SEC"),
    ("llm", "retry_attempts", 11, "LLM_RETRY_ATTEMPTS"),
    ("llm", "target_duration_sec", 179, "TARGET_DURATION_SEC"),
    ("llm", "target_duration_sec", 1201, "TARGET_DURATION_SEC"),
    ("llm", "segment_gap_sec", 3.1, "SEGMENT_GAP_SEC"),
    ("llm", "llm_max_script_segments", 41, "LLM_MAX_SCRIPT_SEGMENTS"),
    ("tts", "sample_rate", 48001, "ALIYUN_TTS_SAMPLE_RATE"),
    ("tts", "timeout_sec", 301, "ALIYUN_TTS_TIMEOUT_SEC"),
    ("tts", "retry_attempts", -1, "TTS_RETRY_ATTEMPTS"),
    ("tts", "aliyun_volume", 101, "ALIYUN_TTS_VOLUME"),
    ("tts", "aliyun_speech_rate", 501, "ALIYUN_TTS_SPEECH_RATE"),
    ("tts", "aliyun_pitch_rate", -501, "ALIYUN_TTS_PITCH_RATE"),
    ("tts", "tencent_volume", 11, "TENCENT_TTS_VOLUME"),
    ("tts", "tencent_speed", 7, "TENCENT_TTS_SPEED"),
]


@pytest.fixture
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def _current(client, headers):
    return client.get(URL, headers=headers).json()["data"]


def _body(current):
    return {
        "llm": dict(current["llm"]),
        "tts": dict(current["tts"]),
        "selected_preset": current["llm"].get("selected_preset", ""),
    }


@pytest.mark.parametrize("section,field,bad,settings_attr", OUT_OF_RANGE)
def test_out_of_range_rejected_and_not_hot_applied(
    client, headers, section, field, bad, settings_attr
):
    current = _current(client, headers)
    body = _body(current)
    body[section][field] = bad
    before_attr = getattr(get_settings(), settings_attr)

    resp = client.put(URL, json=body, headers=headers)

    assert resp.status_code == 400, f"{section}.{field}={bad} 应被拒绝：{resp.text[:300]}"
    assert resp.json()["code"] == 400
    loc = resp.json()["data"]["errors"][0]["loc"]
    assert loc[:3] == ["body", section, field], f"错误未指出字段：{loc}"

    assert getattr(get_settings(), settings_attr) == before_attr, "越界值不得热更进 Settings"
    back = _current(client, headers)[section][field]
    assert back == current[section][field], "越界值不得落库"


def test_cross_voice_interval_out_of_range_rejected(client, headers):
    current = _current(client, headers)
    body = _body(current)
    body["tts"]["cross_voice"] = {
        "enabled": True,
        "strategy": "interval",
        "interval": 21,
        "voices": {},
    }
    before = getattr(get_settings(), "TTS_CROSS_VOICE")

    resp = client.put(URL, json=body, headers=headers)

    assert resp.status_code == 400, resp.text[:300]
    assert getattr(get_settings(), "TTS_CROSS_VOICE") == before
