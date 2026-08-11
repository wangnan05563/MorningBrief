# 代码评审报告：TTS 交叉音色 + Edge 音色扩充

- **日期**：2026-08-10
- **触发**：`@skill:news-backend-code-review`（skill 本机未安装，按上下文规则手动评审）
- **评审范围**：本会话内改动的代码
  - `backend/app/workflow/tts/synthesizer.py`（`assign_cross_voices` + `synthesize` 接线 + `record_call`）
  - `backend/app/services/ai_config_service.py`（`get_voices` edge 分支 + `_parse_cross_voice` + `_normalize_tts` + `get_config_for_frontend`）
  - `backend/app/config.py`（`TTS_CROSS_VOICE`）
  - `backend/app/routers/admin/ai_config.py`（`TTSConfigBody.cross_voice`）
  - `admin-web/src/views/ai/AIConfig.vue`（cross_voice UI / state）

## 结论

**改动逻辑正确，无 CRITICAL / 阻塞性缺陷，零回归。**

验证：`py_compile` 全过；cross-voice 测试 **17 项全绿**（8 + 7 原始 + 2 收尾补充）；**全量后端测试 508 passed / 0 failed（零回归）**。

## 已确认正确的关键不变量

| # | 不变量 | 结论 |
|---|--------|------|
| 1 | 热更新路径 | `_apply_to_settings` 经 `CONFIG_KEY_MAP["tts_cross_voice"]→TTS_CROSS_VOICE` 把 JSON 字符串写回 Settings 单例；`synthesize` 热读到最新配置 ✓ |
| 2 | `_parse_cross_voice` 容错 | 对 `str` / `dict` / 非法 JSON / `None` 全容错，始终返回 4 字段归一结构（`enabled/strategy/interval/voices`），永不抛异常 ✓ |
| 3 | `assign_cross_voices` 安全回退 | 禁用 / 音色 < 2 / 未知 strategy 均不崩；unknown strategy → `round_robin` ✓ |
| 4 | `synthesize` 主流程 | 段按 `seq` 排序后按播放顺序分配 voice；解析失败 `try/except` 不阻断整期；`any(voice_plan)` 守卫日志避免 `cross_cfg=None` 时 NPE ✓ |
| 5 | 前端状态隔离 | `currentCrossVoiceList` getter/setter 按 provider 维度隔离；`handleProviderChange` 重载 `voices` 列表，交叉音色多选随引擎切换 ✓ |
| 6 | Piper 单说话人 | provider 忽略 `voice` 参数，交叉音色天然不生效；前端对 piper 禁用多选并提示，前后端一致 ✓ |
| 7 | Pydantic 字段透传 | `TTSConfigBody.cross_voice: Optional[dict]` 防止严格模式丢弃该字段；`PUT /config` 自动透传 ✓ |

## 发现的问题与处置

### P2 — `record_call` 用量标签失真（已修复）
- **现象**：`synthesize_segment` 中 `record_call(model=settings.ALIYUN_TTS_VOICE, ...)` 硬编码阿里云音色标签。
  当 provider 为 edge / tencent / kokoro，或交叉音色生效后各段使用不同音色时，用量统计的 `model` 列恒显示阿里云音色（如 `xiaoyun`），与实际引擎/音色不符。
- **影响**：仅用量展示失真；预算按 `char_count` 计、`model` 不参与计费，无计费副作用。
- **修复**：改为 `model=f"{settings.TTS_PROVIDER}:{voice or 'default'}"`，如实反映「引擎:音色」。
  无测试断言旧标签，低级低风险；复测 15 项 cross-voice 用例仍全绿。

### P3 — 启用但当前 provider 音色不足时的静默 no-op（已闭环）
- **原建议**：管理端开启交叉音色、为 `edge` 选了 2 个音色，但当前 `TTS_PROVIDER` 是 `tencent` 且未给 tencent 选音色时，`assign_cross_voices` 返回全 `None`，配置 `enabled:true` 实际不生效且无告警。
- **收尾（前端告警）**：`AIConfig.vue` 新增 `crossVoiceInsufficientForProvider` computed（`enabled` 且非 `piper` 且当前 provider 已选音色 < 2 → true），并在交叉音色分区「音色组合」表单项后追加 `el-alert`（warning、`:closable=false`、show-icon），提示「已启用交叉音色但当前引擎仅选不足 2 个音色，保存后将回退单音色」。
- **验证**：`vite build` 成功（AIConfig chunk 31.49kB，较 31.18kB +0.31kB）。

### P3 — `random` 策略未固定随机种子（已闭环）
- **原信息项**：`random.choice` 未种子化，同稿件重合成可能换声，仅影响可复现性。
- **收尾（确定性可复现）**：新增模块级专用 `_cross_voice_rng = random.Random()`；调用前以输入派生种子重置：`seed_src = "|".join(voices) + f"#{total}#{provider}"`，取 `md5(seed_src).digest()[:8]` 转 int 作为 seed。同一配置 → 同一声音分配（可复现），不影响全局 `random` 状态；不相邻重复约束（循环内排除 `prev`）保留。
- **验证**：新增 `test_random_strategy_is_deterministic`（同输入两次调用 ==、不相邻重复）全绿。

### P3 — `interval` 默认值双写（已闭环）
- **原无害项**：`_parse_cross_voice` 默认 `interval=2`，`assign_cross_voice` 内 `or 1`，冗余防御。
- **收尾（统一真相源）**：改为区分「缺失 → 缺省 2」「0/负 → clamp 下界 1」：`raw_interval = cfg.get("interval"); interval = 2 if raw_interval is None else max(1, int(raw_interval))`，消除双默认不一致。
- **验证**：新增 `test_interval_default_when_missing`（缺失 interval → 每 2 段 `["a","a","b","b","a","a"]`）全绿；既有 `test_interval_strategy_clamps_minimum`（interval=0 → clamp 到 1）仍绿。

## 附：本次改动文件清单
- 新增：`backend/tests/test_synthesizer_cross_voice.py`、`backend/tests/test_cross_voice_config.py`
- 修改：`synthesizer.py`（+`assign_cross_voices`、接线、record_call 修正）、`ai_config_service.py`（`get_voices` edge 分支 + 交叉音色存取）、`config.py`、`routers/admin/ai_config.py`、`AIConfig.vue`
