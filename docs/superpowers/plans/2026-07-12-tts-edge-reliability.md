# TTS Edge Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Edge TTS failures diagnosable and recoverable without changing the user's active provider or credentials.

**Architecture:** Preserve the existing provider factory and workflow API. Normalize Edge configuration under the keys already used by the UI, translate empty-audio Edge responses into retryable service failures, and persist sanitized segment failure summaries when the TTS success threshold is not met.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, pytest, edge-tts.

## Global Constraints

- Do not write, display, or change API credentials.
- Do not switch the active TTS provider or add a fallback provider automatically.
- Keep persisted failure diagnostics free of script text and credentials.

---

### Task 1: Normalize and validate Edge configuration

**Files:**
- Modify: `backend/app/services/ai_config_service.py`
- Test: `backend/tests/test_ai_config_service.py`

**Interfaces:**
- Produces canonical `edge_rate`, `edge_volume`, and `edge_pitch` settings entries consumed by `EdgeTTSProvider`.

- [ ] **Step 1: Write the failing tests**

```python
def test_normalize_tts_keeps_valid_edge_adjustments():
    service = AIConfigService.__new__(AIConfigService)
    result = service._normalize_tts({"edge_rate": "+10%", "edge_volume": "-5%"})
    assert result["edge_rate"] == "+10%"
    assert result["edge_volume"] == "-5%"

def test_normalize_tts_treats_legacy_numeric_zero_as_no_adjustment():
    service = AIConfigService.__new__(AIConfigService)
    result = service._normalize_tts({"edge_rate": "0.0", "edge_volume": 0})
    assert result["edge_rate"] == ""
    assert result["edge_volume"] == ""
```

- [ ] **Step 2: Run the tests to verify the legacy-zero test fails**

Run: `pytest backend/tests/test_ai_config_service.py -q`

Expected: the legacy numeric value remains `"0.0"` before normalization is implemented.

- [ ] **Step 3: Implement the minimal normalization and align config key mappings**

```python
def _normalize_edge_adjustment(value: object) -> str:
    text = str(value or "").strip()
    return "" if text in {"0", "0.0", "0.00"} else text
```

Use the UI keys (`edge_rate`, `edge_volume`, `edge_pitch`) consistently in persistence, frontend reads, and `CONFIG_KEY_MAP`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest backend/tests/test_ai_config_service.py -q`

Expected: PASS.

### Task 2: Classify Edge empty audio as a recoverable service failure

**Files:**
- Modify: `backend/app/workflow/tts/edge_client.py`
- Test: `backend/tests/test_edge_tts_provider.py`

**Interfaces:**
- Produces `TTSServiceError` for `edge_tts.NoAudioReceived`, allowing the existing retry and fallback machinery to handle it.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_empty_edge_response_is_retryable_service_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "edge_tts", fake_edge_tts_that_raises_no_audio())
    provider = EdgeTTSProvider(voice="zh-CN-XiaoxiaoNeural")
    with pytest.raises(TTSServiceError, match="未收到音频"):
        await provider.synthesize("诊断文本")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest backend/tests/test_edge_tts_provider.py -q`

Expected: FAIL because the provider currently raises the non-retryable `TTSError`.

- [ ] **Step 3: Implement the minimal exception classification**

```python
except Exception as exc:
    if exc.__class__.__name__ == "NoAudioReceived":
        raise TTSServiceError("Edge-TTS 未收到音频数据") from exc
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest backend/tests/test_edge_tts_provider.py -q`

Expected: PASS.

### Task 3: Persist sanitized segment diagnostics for a failed TTS batch

**Files:**
- Modify: `backend/app/workflow/tts/synthesizer.py`
- Test: `backend/tests/test_synthesizer.py`

**Interfaces:**
- Raises `TTSError` with the failed sequence numbers and sanitized exception summaries only when successful segments are below the existing 50% threshold.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_failed_batch_includes_segment_error_summary(monkeypatch):
    # Arrange six failed segment results without external provider calls.
    with pytest.raises(TTSError, match=r"失败分段: 1: Edge-TTS 未收到音频"):
        await synthesize("wf-test", 1)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest backend/tests/test_synthesizer.py -q`

Expected: FAIL because the current message only reports `0/6`.

- [ ] **Step 3: Implement a bounded diagnostic summary**

```python
failure_summaries.append(f"{seq}: {type(error).__name__}: {str(error)[:160]}")
raise TTSError(f"TTS 成功率过低: {success}/{total}；失败分段: {' | '.join(failure_summaries[:5])}")
```

- [ ] **Step 4: Run the targeted and related test suites**

Run: `pytest backend/tests/test_ai_config_service.py backend/tests/test_edge_tts_provider.py backend/tests/test_synthesizer.py backend/tests/test_ffmpeg_service.py -q`

Expected: PASS.
