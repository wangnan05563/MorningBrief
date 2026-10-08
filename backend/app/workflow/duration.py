"""频道时长口径（T00914）。

改写阶段（字数反算）与拼接阶段（时长校验区间）必须用同一个「生效目标时长」，
否则会出现「稿件按 30 分钟写、拼接按 10 分钟的上限判超长」的矛盾。本模块是
该口径的唯一定义处，供 `llm.rewriter` 与 `stitch.concat` 共用。
"""
from __future__ import annotations

# 频道类型：听书/有声读物（与 rewriter 的 _AUDIOBOOK_CHANNEL_TYPES 同源）
AUDIOBOOK_CHANNEL_TYPES = frozenset({"audiobook"})

# 频道级时长保底的安全范围（与全局目标时长的 clamp 一致，防误配极端值）
MIN_CHANNEL_DURATION_SEC = 180
MAX_CHANNEL_DURATION_SEC = 1800

# 听书频道未显式配置时的保底时长：30 分钟（历史实测未配置即回退全局 600s，
# 只产出 10 分钟节目，达不到听书栏目的保底标准）
AUDIOBOOK_DEFAULT_MIN_SEC = 1800

# 时长允许区间的容差（±20% 覆盖 LLM 字数波动 + TTS 语速波动 + 段间静音累加）
DURATION_LOW_RATIO = 0.80
DURATION_HIGH_RATIO = 1.20


def resolve_channel_min_duration_sec(
    channel_type: str | None, channel_min_sec: int | None
) -> int | None:
    """频道级最短时长（秒）；返回 None 表示沿用全局目标时长。

    显式配置永远优先；听书频道未配置时按 30 分钟保底——保底是栏目标准而非
    运营开关，依赖人工配置会导致「代码已支持但线上仍出 10 分钟」。
    """
    if channel_min_sec is not None:
        return max(
            MIN_CHANNEL_DURATION_SEC,
            min(MAX_CHANNEL_DURATION_SEC, int(channel_min_sec)),
        )
    if (channel_type or "") in AUDIOBOOK_CHANNEL_TYPES:
        return AUDIOBOOK_DEFAULT_MIN_SEC
    return None


def duration_range_sec(target_sec: int, channel_min_sec: int | None = None) -> tuple[int, int]:
    """允许的成品时长区间 [low, high]。

    频道级保底同时抬高上下限：下限取保底值，上限按「生效目标 = max(全局目标,
    保底)」×1.20。历史上限固定取全局目标×1.20，配 1800s 保底会得到 [1800, 720]
    这类区间倒挂，拼接阶段必然判超长并在 atempo 超出 1.15x 时抛错。
    """
    effective = max(_as_int(target_sec, 600), _as_int(channel_min_sec or 0, 0))
    if channel_min_sec is not None:
        low = max(MIN_CHANNEL_DURATION_SEC, _as_int(channel_min_sec, 600))
    else:
        low = max(MIN_CHANNEL_DURATION_SEC, int(effective * DURATION_LOW_RATIO))
    high = int(effective * DURATION_HIGH_RATIO)
    return low, max(low, high)


def _as_int(value: object, default: int) -> int:
    """把配置值收敛为 int（非法值回退默认，保持与原 _get_duration_range 一致）。"""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
