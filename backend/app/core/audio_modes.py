"""音频段间（段间静音 / BGM）模式的共享真相源。

为什么单独成模块：
「段间 BGM 模式」这个取值同时被三处消费——
1. `app/workflow/stitch/concat.py`（拼接时按模式选择段间策略）；
2. `app/routers/admin/channels.py`（频道配置写入校验 + 字段说明）；
3. `app/config.py`（全局默认 BGM_GAP_MODE）。
原先白名单在 concat 与 channels 各自写了一份 ("silence", "bridge")，新增模式时
极易只改一处，导致「前端能存、后端拼接不认」这类静默不一致。收敛到这里后
任何新增模式只需改本文件一处。

模式语义：
- continuous：段间交叉淡化直连（无静音空档）+ BGM 单条连续铺满整期 → 切换丝滑
- silence   ：段间插入 SEGMENT_GAP_SEC 静音 + BGM 按段切片 → 停顿可感知
- bridge    ：段间插入静音 + BGM 循环铺满整段（旧版 BGM 桥接）
"""

# 合法取值（顺序即前端下拉展示顺序，首项为默认）
VALID_GAP_MODES: tuple[str, ...] = ("continuous", "silence", "bridge")

# 默认模式：continuous（双人播报切换无空档、BGM 不中断）
DEFAULT_GAP_MODE = "continuous"

# 各模式的中文说明：后端校验报错文案与前端提示可共用，避免两边措辞漂移
GAP_MODE_LABELS: dict[str, str] = {
    "continuous": "连续衔接（段间交叉淡化，BGM 全程连续）",
    "silence": "真实静音（段间停顿可感知）",
    "bridge": "BGM 桥接（旧版，段间无停顿感）",
}


def normalize_gap_mode(raw: object) -> str:
    """把任意输入归一化为合法模式；None / 空串 / 非法值一律回退默认模式。

    归一化而非抛错的原因：该值可能来自历史数据、手工写入的 DB 记录或旧版前端，
    拼接流程不应因为一个展示层枚举值把整期节目做失败。
    写入侧（Pydantic validator）仍会严格校验，保持「存进来的必然合法」。
    """
    if raw is None:
        return DEFAULT_GAP_MODE
    mode = str(raw).strip().lower()
    return mode if mode in VALID_GAP_MODES else DEFAULT_GAP_MODE
