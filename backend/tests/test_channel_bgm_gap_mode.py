"""频道级段间 BGM 模式（bgm_gap_mode）校验测试。

bgm_gap_mode 仅接受 continuous / silence / bridge / None，非法值应在请求体校验阶段
被拒绝，避免脏数据进入段间拼接分支（concat.build_crossfade_cmd / build_bgm_overlay /
build_bgm_continuous / build_bgm_bridge）。

语义约定：
- None           -> 继承全局 settings.BGM_GAP_MODE（默认 continuous）
- ""（空串）      -> 兜底视为继承全局（归一为 None）
- 带空白的合法值  -> 去空白后归一（" bridge " -> "bridge"）
- 其余非法值      -> ValueError

注意：本层只做「去空白」，不做大小写归一——大小写不符仍按非法拒绝，
保持「存进来的必然是小写枚举」这一契约（读取侧 normalize_gap_mode 才做容错归一）。

纯请求体校验，无需 DB / ffmpeg。
"""
import pytest

from app.routers.admin.channels import ChannelCreateRequest, ChannelUpdateRequest

_VALID = [None, "continuous", "silence", "bridge"]

# (原始输入, 归一后期望)：带空白的合法值应被去空白后接受
_NORMALIZED = [(" bridge ", "bridge"), ("  silence  ", "silence"), ("BRIDGE".lower(), "bridge")]

# 真正非法的输入：大小写不符、无意义的字符串都应被拒绝
_INVALID = ["weird", "SILENCE", "b", "x"]


@pytest.mark.parametrize("mode", _VALID)
def test_create_request_accepts_valid_modes(mode):
    req = ChannelCreateRequest(name="测试频道", bgm_gap_mode=mode)
    assert req.bgm_gap_mode == mode


@pytest.mark.parametrize("mode", _VALID)
def test_update_request_accepts_valid_modes(mode):
    req = ChannelUpdateRequest(bgm_gap_mode=mode)
    assert req.bgm_gap_mode == mode


@pytest.mark.parametrize("raw,expected", _NORMALIZED)
def test_create_request_normalizes_padded_valid(raw, expected):
    req = ChannelCreateRequest(name="x", bgm_gap_mode=raw)
    assert req.bgm_gap_mode == expected


@pytest.mark.parametrize("raw,expected", _NORMALIZED)
def test_update_request_normalizes_padded_valid(raw, expected):
    req = ChannelUpdateRequest(bgm_gap_mode=raw)
    assert req.bgm_gap_mode == expected


def test_create_request_empty_string_is_none():
    # 空字符串兜底为继承全局（None）
    req = ChannelCreateRequest(name="x", bgm_gap_mode="")
    assert req.bgm_gap_mode is None


def test_update_request_empty_string_is_none():
    req = ChannelUpdateRequest(bgm_gap_mode="")
    assert req.bgm_gap_mode is None


@pytest.mark.parametrize("bad", _INVALID)
def test_create_request_rejects_invalid_mode(bad):
    with pytest.raises(ValueError):
        ChannelCreateRequest(name="x", bgm_gap_mode=bad)


@pytest.mark.parametrize("bad", _INVALID)
def test_update_request_rejects_invalid_mode(bad):
    with pytest.raises(ValueError):
        ChannelUpdateRequest(bgm_gap_mode=bad)
