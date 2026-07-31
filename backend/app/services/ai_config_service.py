"""AI 配置管理服务。

职责：
1. 配置 CRUD（从 SQLite ai_config 表读写）
2. 配置热更新（同步覆盖 Settings 内存单例，无需重启）
3. API Key 脱敏（GET 返回 ****xxxx，前端回传脱敏值视为未修改）
4. 连接测试（LLM 走 OpenAI 兼容协议，TTS 走阿里云 NLS）
5. 用量记录与统计查询

桥接策略：ai_config 表的 config_key 与 Settings 类字段名一一对应，
启动时调用 apply_config_to_settings() 将数据库配置覆盖到 Settings 单例，
使现有的 rewriter.py / synthesizer.py 等代码无需修改即可读取最新配置。
"""
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import BizError, ParamError
from app.models.ai_config import AIConfig, AIUsageLog

logger = logging.getLogger(__name__)

# ---- 配置项与 Settings 字段的映射 ----
# key = ai_config 表的 config_key，value = Settings 类的属性名
# 覆盖 LLM + TTS 多 Provider（阿里云/Edge-TTS/腾讯云）全部字段
CONFIG_KEY_MAP = {
    # LLM 配置
    "llm_api_key": "LLM_API_KEY",
    "llm_base_url": "LLM_BASE_URL",
    "llm_model": "LLM_MODEL",
    "llm_timeout_sec": "LLM_TIMEOUT_SEC",
    "llm_retry_attempts": "LLM_RETRY_ATTEMPTS",
    # TTS 通用 + 阿里云（保留原 key 兼容前端旧表单）
    "tts_provider": "TTS_PROVIDER",
    "tts_api_key": "ALIYUN_TTS_API_KEY",
    "tts_appkey": "ALIYUN_TTS_APPKEY",
    "tts_voice": "ALIYUN_TTS_VOICE",
    "tts_sample_rate": "ALIYUN_TTS_SAMPLE_RATE",
    "tts_format": "ALIYUN_TTS_FORMAT",
    "tts_timeout_sec": "ALIYUN_TTS_TIMEOUT_SEC",
    "tts_retry_attempts": "TTS_RETRY_ATTEMPTS",
    # 阿里云 TTS 音量/语速/基频（NLS tts_request 参数）
    "aliyun_tts_volume": "ALIYUN_TTS_VOLUME",
    "aliyun_tts_speech_rate": "ALIYUN_TTS_SPEECH_RATE",
    "aliyun_tts_pitch_rate": "ALIYUN_TTS_PITCH_RATE",
    # Edge-TTS（微软免费方案，无需 API Key）
    # 前端字段名 = config_key = edge_*（与路由层 TTSConfigBody 字段名一致），
    # Settings 属性名 = EDGE_TTS_*（与 config.py 字段名一致）
    "edge_voice": "EDGE_TTS_VOICE",
    "edge_rate": "EDGE_TTS_RATE",
    "edge_volume": "EDGE_TTS_VOLUME",
    "edge_pitch": "EDGE_TTS_PITCH",
    # 腾讯云 TTS（凭证可复用 COS）
    "tencent_tts_secret_id": "TENCENT_TTS_SECRET_ID",
    "tencent_tts_secret_key": "TENCENT_TTS_SECRET_KEY",
    "tencent_tts_region": "TENCENT_TTS_REGION",
    "tencent_tts_voice_type": "TENCENT_TTS_VOICE_TYPE",
    "tencent_tts_volume": "TENCENT_TTS_VOLUME",
    "tencent_tts_speed": "TENCENT_TTS_SPEED",
    # 节目时长目标（秒）：与稿件字数反向关联，控制 rewriter 字数与 stitch 范围
    "target_duration_sec": "TARGET_DURATION_SEC",
    # TTS 段间静音时长（秒）：拼接时每段新闻之间的留白，影响节奏感与 BGM 浮现
    "segment_gap_sec": "SEGMENT_GAP_SEC",
}

# 需要脱敏的配置项（API Key / Secret 类）
SENSITIVE_KEYS = {
    "llm_api_key", "tts_api_key", "tts_appkey",
    "tencent_tts_secret_id", "tencent_tts_secret_key",
}

# 预设配置存储 key：在 ai_config 表中以 JSON 字符串形式存储每个预设的独立配置
# 结构：{"qwen": {"api_key": "sk-xxx", "base_url": "...", "model": "..."}, ...}
PRESET_CONFIGS_KEY = "llm_preset_configs"

# 恢复初始配置时需要清空的 LLM 配置 key（保留 timeout/retry 等通用项）
LLM_RESET_KEYS = ["llm_api_key", "llm_base_url", "llm_model", PRESET_CONFIGS_KEY]

# 需要转为 int 类型的配置项
INT_KEYS = {
    "llm_timeout_sec", "llm_retry_attempts",
    "tts_sample_rate", "tts_timeout_sec", "tts_retry_attempts",
    "aliyun_tts_volume", "aliyun_tts_speech_rate", "aliyun_tts_pitch_rate",
    "tencent_tts_voice_type", "tencent_tts_volume", "tencent_tts_speed",
    "target_duration_sec",
}

# 需要转为 float 类型的配置项（如段间静音时长，需支持小数精度）
FLOAT_KEYS = {
    "segment_gap_sec",
}

# ---- LLM 提供商预设 ----
LLM_PRESETS = [
    {
        "key": "qwen", "label": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-max",
        "api_key_url": "https://dashscope.console.aliyun.com/apiKey",
    },
    {
        "key": "openai", "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_url": "https://platform.openai.com/api-keys",
    },
    {
        "key": "deepseek", "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-v4-flash",
        "api_key_url": "https://platform.deepseek.com/api_keys",
    },
    {
        "key": "zhipu", "label": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "api_key_url": "https://open.bigmodel.cn/usercenter/apikeys",
    },
    {
        "key": "moonshot", "label": "Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "api_key_url": "https://platform.moonshot.cn/console/api-keys",
    },
    {
        "key": "ernie", "label": "百度文心",
        "base_url": "https://qianfan.baidubce.com/v2",
        "model": "ernie-4.0-8k",
        "api_key_url": "https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application",
    },
    {
        "key": "doubao", "label": "字节豆包",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-pro-4k",
        "api_key_url": "https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey",
    },
    {
        "key": "ollama", "label": "Ollama 本地",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2.5:7b",
        "api_key_url": "",
    },
    {
        "key": "agnes", "label": "Agnes AI",
        # base_url 以 Agnes AI 官方文档为准（https://wiki.agnes-ai.com/zh-Hans/docs/overview），
        # 旧值 https://api.agnes-ai.com/v1 不可达，正确入口为 apihub.agnes-ai.com
        "base_url": "https://apihub.agnes-ai.com/v1",
        # 模型名以官方文档为准（小写 agnes-2.0-flash），避免大小写敏感导致 404
        "model": "agnes-2.0-flash",
        "api_key_url": "https://platform.agnes-ai.com/",
    },
]

# ---- 模型定价表（每 1K token 价格 USD）----
# 未识别模型按 gpt-4o-mini 默认费率计价
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "qwen-max": {"input": 0.0028, "output": 0.0084},
    "qwen-plus": {"input": 0.0004, "output": 0.0012},
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-v4-flash": {"input": 0.00014, "output": 0.00028},
    "glm-4-flash": {"input": 0.0, "output": 0.0},
    "moonshot-v1-8k": {"input": 0.0017, "output": 0.0017},
    # Agnes AI 当前免费开放，定价为 0
    # 同时支持大小写两种模型名，避免预设改名后定价失效
    "Agnes-2.0-Flash": {"input": 0.0, "output": 0.0},
    "agnes-2.0-flash": {"input": 0.0, "output": 0.0},
}
DEFAULT_PRICING = MODEL_PRICING["gpt-4o-mini"]

# TTS 每千字符费用（阿里云 NLS 定价约 0.2 元/千字符 ≈ $0.028）
TTS_COST_PER_1K_CHARS = 0.028


def _mask_key(key: str) -> str:
    """API Key 脱敏：保留后 4 位，前缀 ****。"""
    if not key:
        return ""
    return f"****{key[-4:]}" if len(key) > 4 else "****"


def _is_masked(value: str) -> bool:
    """判断前端回传值是否为脱敏值（未修改）。"""
    return value.startswith("****")


def _estimate_cost(
    service_type: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    char_count: int = 0,
) -> float:
    """估算单次调用费用（USD）。"""
    if service_type == "llm":
        pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
        cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
        return round(cost, 6)
    elif service_type == "tts":
        return round((char_count / 1000) * TTS_COST_PER_1K_CHARS, 6)
    return 0.0


class AIConfigService:
    """AI 配置管理服务。

    所有方法注入 AsyncSession，与项目其他 service 保持一致的调用方式。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- 配置读取 ----

    async def get_all_config(self) -> dict[str, str]:
        """读取全部 AI 配置，返回 {config_key: config_value} 字典。"""
        result = await self.db.execute(select(AIConfig))
        rows = result.scalars().all()
        return {row.config_key: row.config_value for row in rows}

    async def get_config_value(self, key: str) -> Optional[str]:
        """读取单个配置项。"""
        result = await self.db.execute(
            select(AIConfig.config_value).where(AIConfig.config_key == key)
        )
        return result.scalar_one_or_none()

    async def _get_preset_configs_raw(self) -> dict:
        """读取预设配置 JSON（明文）。

        返回结构：{preset_key: {"api_key": "明文", "base_url": "...", "model": "..."}}
        若未配置则返回空 dict。
        """
        raw = await self.get_config_value(PRESET_CONFIGS_KEY)
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            logger.warning("预设配置 JSON 解析失败，重置为空")
            return {}

    async def get_preset_configs(self) -> dict:
        """获取预设配置（前端展示用，API Key 脱敏）。

        返回结构：{preset_key: {"api_key": "****xxxx", "base_url": "...", "model": "..."}}
        """
        raw = await self._get_preset_configs_raw()
        masked: dict[str, dict] = {}
        for key, cfg in raw.items():
            if not isinstance(cfg, dict):
                continue
            masked[key] = {
                "api_key": _mask_key(cfg.get("api_key", "")),
                "base_url": cfg.get("base_url", ""),
                "model": cfg.get("model", ""),
            }
        return masked

    async def _save_preset_config(
        self, preset_key: str, api_key: str, base_url: str, model: str
    ) -> None:
        """保存单个预设的配置到 JSON 字段。

        API Key 为脱敏值时保留原有明文（视为未修改）。
        """
        configs = await self._get_preset_configs_raw()
        existing = configs.get(preset_key, {})

        # 脱敏值视为未修改，保留原有明文
        if api_key and not _is_masked(api_key):
            final_key = api_key
        else:
            final_key = existing.get("api_key", "")

        configs[preset_key] = {
            "api_key": final_key,
            "base_url": base_url,
            "model": model,
        }
        await self._upsert_config(PRESET_CONFIGS_KEY, json.dumps(configs, ensure_ascii=False))

    async def reset_to_defaults(self) -> dict:
        """恢复 LLM 初始配置（清空用户保存的预设配置和当前 LLM 配置）。

        清空 llm_api_key / llm_base_url / llm_model / llm_preset_configs，
        保留 timeout/retry 等通用项。热更新 Settings 单例回退到 .env 默认值。

        返回重置后的 LLM 配置（供前端刷新表单）。
        """
        for key in LLM_RESET_KEYS:
            await self.db.execute(
                delete(AIConfig).where(AIConfig.config_key == key)
            )
        await self.db.commit()

        # 热更新 Settings 单例回退到 .env 默认值
        settings = get_settings()
        # 通过重新实例化 Settings 获取 .env 默认值，避免污染现有单例
        from app.config import Settings
        defaults = Settings()
        settings.LLM_API_KEY = defaults.LLM_API_KEY
        settings.LLM_BASE_URL = defaults.LLM_BASE_URL
        settings.LLM_MODEL = defaults.LLM_MODEL

        logger.info("LLM 配置已恢复初始状态，清空 key=%s", LLM_RESET_KEYS)

        # 返回重置后的配置（脱敏）
        return {
            "api_key": _mask_key(settings.LLM_API_KEY),
            "base_url": settings.LLM_BASE_URL,
            "model": settings.LLM_MODEL,
        }

    async def get_config_for_frontend(self) -> dict:
        """获取配置（前端展示用，API Key 脱敏）。

        返回结构：
        {
            "llm": {
                "api_key": "****xxxx", "base_url": "...", "model": "...",
                "timeout_sec": N, "retry_attempts": N,
                "preset_configs": {preset_key: {"api_key": "****xxxx", "base_url": "...", "model": "..."}},
                "selected_preset": "qwen|openai|...",
            },
            "tts": {...},
        }
        """
        raw = await self.get_all_config()
        settings = get_settings()

        # 合并：SQLite 优先，fallback 到 Settings 默认值
        def _get(key: str, settings_attr: str, default: str = "") -> str:
            val = raw.get(key)
            if val is not None:
                return val
            return str(getattr(settings, settings_attr, default))

        def _get_int(key: str, settings_attr: str, default: int) -> int:
            val = raw.get(key)
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
            return getattr(settings, settings_attr, default)

        def _get_float(key: str, settings_attr: str, default: float) -> float:
            val = raw.get(key)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
            return getattr(settings, settings_attr, default)

        llm_base_url = _get("llm_base_url", "LLM_BASE_URL")
        llm_config = {
            "api_key": _mask_key(_get("llm_api_key", "LLM_API_KEY")),
            "base_url": llm_base_url,
            "model": _get("llm_model", "LLM_MODEL"),
            "timeout_sec": int(_get("llm_timeout_sec", "LLM_TIMEOUT_SEC", "30")),
            "retry_attempts": int(_get("llm_retry_attempts", "LLM_RETRY_ATTEMPTS", "3")),
            # 目标节目时长（秒）：控制 rewriter 字数与 stitch 范围
            # 默认 600s = 10 分钟，与稿件字数反向关联
            "target_duration_sec": _get_int("target_duration_sec", "TARGET_DURATION_SEC", 600),
            # TTS 段间静音时长（秒）：拼接时每段新闻之间的留白
            # 默认 0.5s，过大影响节奏紧凑度，过小衔接生硬且 BGM 无浮现空间
            "segment_gap_sec": _get_float("segment_gap_sec", "SEGMENT_GAP_SEC", 0.5),
            # 预设配置（每个 provider 独立保存的 API Key/Base URL/Model，API Key 脱敏）
            "preset_configs": await self.get_preset_configs(),
            # 当前选中预设（根据 base_url 反向匹配）
            "selected_preset": self._match_preset_by_base_url(llm_base_url),
        }
        tts_config = {
            # Provider 选择（前端切换热生效）
            "provider": _get("tts_provider", "TTS_PROVIDER", "aliyun"),
            # 阿里云 NLS 字段（保留原 key 兼容）
            "api_key": _mask_key(_get("tts_api_key", "ALIYUN_TTS_API_KEY")),
            "appkey": _mask_key(_get("tts_appkey", "ALIYUN_TTS_APPKEY", "")),
            "voice": _get("tts_voice", "ALIYUN_TTS_VOICE"),
            "sample_rate": _get_int("tts_sample_rate", "ALIYUN_TTS_SAMPLE_RATE", 44100),
            "format": _get("tts_format", "ALIYUN_TTS_FORMAT", "mp3"),
            "timeout_sec": _get_int("tts_timeout_sec", "ALIYUN_TTS_TIMEOUT_SEC", 60),
            "retry_attempts": _get_int("tts_retry_attempts", "TTS_RETRY_ATTEMPTS", 3),
            # 阿里云 TTS 音量/语速/基频（NLS tts_request 参数）
            "aliyun_volume": _get_int("aliyun_tts_volume", "ALIYUN_TTS_VOLUME", 50),
            "aliyun_speech_rate": _get_int("aliyun_tts_speech_rate", "ALIYUN_TTS_SPEECH_RATE", 0),
            "aliyun_pitch_rate": _get_int("aliyun_tts_pitch_rate", "ALIYUN_TTS_PITCH_RATE", 0),
            # Edge-TTS 字段（config_key = edge_*，与前端字段名一致）
            "edge_voice": _get("edge_voice", "EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural"),
            "edge_rate": _get("edge_rate", "EDGE_TTS_RATE", ""),
            "edge_volume": _get("edge_volume", "EDGE_TTS_VOLUME", ""),
            "edge_pitch": _get("edge_pitch", "EDGE_TTS_PITCH", ""),
            # 腾讯云 TTS 字段
            "tencent_secret_id": _mask_key(_get("tencent_tts_secret_id", "TENCENT_TTS_SECRET_ID", "")),
            "tencent_secret_key": _mask_key(_get("tencent_tts_secret_key", "TENCENT_TTS_SECRET_KEY", "")),
            "tencent_region": _get("tencent_tts_region", "TENCENT_TTS_REGION", "ap-guangzhou"),
            "tencent_voice_type": _get_int("tencent_tts_voice_type", "TENCENT_TTS_VOICE_TYPE", 101011),
            "tencent_volume": _get_int("tencent_tts_volume", "TENCENT_TTS_VOLUME", 0),
            "tencent_speed": _get_int("tencent_tts_speed", "TENCENT_TTS_SPEED", 0),
        }

        return {"llm": llm_config, "tts": tts_config}

    # ---- 配置更新 ----

    async def update_config(
        self, llm_config: dict, tts_config: dict, selected_preset: str = ""
    ) -> None:
        """保存配置到 SQLite 并热更新 Settings 单例。

        API Key 脱敏值（****开头）视为未修改，跳过；
        空字符串视为清除 Key。

        当 selected_preset 非空时，同步将当前 LLM 配置（api_key/base_url/model）
        保存到预设配置 JSON 中，实现切换预设时返显之前保存的配置。

        切换 TTS provider 或修改音色等配置后，清空 tts_factory 的 provider
        缓存，使下次 synthesize 调用时重新创建实例读取最新配置。
        """
        updates: dict[str, str] = {}

        for key, value in self._normalize_llm(llm_config).items():
            updates[key] = value
        for key, value in self._normalize_tts(tts_config).items():
            updates[key] = value

        # 同步保存预设配置（即使 updates 为空也需要更新预设配置）
        if selected_preset:
            # 解析实际的 api_key 明文值：
            # 脱敏值 → 从数据库读取当前明文，fallback 到 Settings 默认值（与 get_config_for_frontend 一致）
            # 新值/空值 → 直接使用（用户修改或清空了 API Key）
            api_key_for_preset = llm_config.get("api_key", "")
            if api_key_for_preset and _is_masked(api_key_for_preset):
                api_key_for_preset = await self.get_config_value("llm_api_key")
                if not api_key_for_preset:
                    api_key_for_preset = get_settings().LLM_API_KEY or ""
            await self._save_preset_config(
                preset_key=selected_preset,
                api_key=api_key_for_preset,
                base_url=llm_config.get("base_url", ""),
                model=llm_config.get("model", ""),
            )

        if not updates:
            return

        # 写入 SQLite（upsert）
        for key, value in updates.items():
            await self._upsert_config(key, value)

        await self.db.commit()

        # 热更新 Settings 内存单例
        self._apply_to_settings(updates)

        # TTS 配置变更时清空 provider 工厂缓存，确保下次合成使用新配置
        # edge_* 前缀覆盖 Edge-TTS 的 config_key（voice/rate/volume/pitch）
        if any(k.startswith(("tts_", "edge_", "tencent_tts_")) for k in updates):
            try:
                from app.workflow.tts.tts_factory import invalidate
                invalidate()
                logger.info("TTS provider 工厂缓存已清空（配置变更）")
            except Exception as e:
                logger.warning("清空 TTS provider 缓存失败: %s", e)

        logger.info("AI 配置已更新 keys=%s", list(updates.keys()))

    def _normalize_llm(self, config: dict) -> dict[str, str]:
        """将前端 LLM 配置转为 config_key -> value 映射。

        API Key 脱敏值跳过（未修改），空字符串清除。
        """
        result: dict[str, str] = {}
        api_key = config.get("api_key", "")
        if api_key and not _is_masked(api_key):
            result["llm_api_key"] = api_key

        if "base_url" in config:
            result["llm_base_url"] = config["base_url"]
        if "model" in config:
            result["llm_model"] = config["model"]
        if "timeout_sec" in config:
            result["llm_timeout_sec"] = str(config["timeout_sec"])
        if "retry_attempts" in config:
            result["llm_retry_attempts"] = str(config["retry_attempts"])
        # 目标节目时长（秒）：与稿件字数反向关联
        if "target_duration_sec" in config:
            result["target_duration_sec"] = str(config["target_duration_sec"])
        # TTS 段间静音时长（秒）：拼接时每段新闻之间的留白
        if "segment_gap_sec" in config:
            result["segment_gap_sec"] = str(config["segment_gap_sec"])
        return result

    def _normalize_tts(self, config: dict) -> dict[str, str]:  # NOSONAR
        """将前端 TTS 配置转为 config_key -> value 映射。

        覆盖三套 Provider 字段：阿里云（api_key/appkey/voice/...）、
        Edge-TTS（edge_voice/edge_rate/...）、腾讯云（tencent_secret_id/...）。
        脱敏值跳过，空字符串清除。
        """
        result: dict[str, str] = {}

        # Provider 选择
        if "provider" in config:
            result["tts_provider"] = config["provider"]

        # 阿里云 NLS 字段
        api_key = config.get("api_key", "")
        if api_key and not _is_masked(api_key):
            result["tts_api_key"] = api_key

        appkey = config.get("appkey", "")
        if appkey and not _is_masked(appkey):
            result["tts_appkey"] = appkey

        if "voice" in config:
            result["tts_voice"] = config["voice"]
        if "sample_rate" in config:
            result["tts_sample_rate"] = str(config["sample_rate"])
        if "format" in config:
            result["tts_format"] = config["format"]
        if "timeout_sec" in config:
            result["tts_timeout_sec"] = str(config["timeout_sec"])
        if "retry_attempts" in config:
            result["tts_retry_attempts"] = str(config["retry_attempts"])

        # 阿里云 TTS 音量/语速/基频（NLS tts_request 参数）
        if "aliyun_volume" in config:
            result["aliyun_tts_volume"] = str(config["aliyun_volume"])
        if "aliyun_speech_rate" in config:
            result["aliyun_tts_speech_rate"] = str(config["aliyun_speech_rate"])
        if "aliyun_pitch_rate" in config:
            result["aliyun_tts_pitch_rate"] = str(config["aliyun_pitch_rate"])

        # Edge-TTS 字段（config_key = edge_*，前端字段名即 config_key）
        # rate/volume/pitch 的数值零（0 / 0.0 / "0" / "0.0"）等价于空字符串（无调整），
        # 统一标准化避免 Edge-TTS 把 "0" 当成有效调整值
        def _normalize_edge_adjustment(value) -> str:
            """Edge-TTS rate/volume/pitch 零值标准化：数值零转为空字符串。"""
            if value is None:
                return ""
            s = str(value).strip()
            if s in ("0", "0.0", "0.00", "-0", "+0"):
                return ""
            return s

        if "edge_voice" in config:
            result["edge_voice"] = config["edge_voice"]
        if "edge_rate" in config:
            result["edge_rate"] = _normalize_edge_adjustment(config["edge_rate"])
        if "edge_volume" in config:
            result["edge_volume"] = _normalize_edge_adjustment(config["edge_volume"])
        if "edge_pitch" in config:
            result["edge_pitch"] = _normalize_edge_adjustment(config["edge_pitch"])

        # 腾讯云 TTS 字段
        tencent_secret_id = config.get("tencent_secret_id", "")
        if tencent_secret_id and not _is_masked(tencent_secret_id):
            result["tencent_tts_secret_id"] = tencent_secret_id

        tencent_secret_key = config.get("tencent_secret_key", "")
        if tencent_secret_key and not _is_masked(tencent_secret_key):
            result["tencent_tts_secret_key"] = tencent_secret_key

        if "tencent_region" in config:
            result["tencent_tts_region"] = config["tencent_region"]
        if "tencent_voice_type" in config:
            result["tencent_tts_voice_type"] = str(config["tencent_voice_type"])
        if "tencent_volume" in config:
            result["tencent_tts_volume"] = str(config["tencent_volume"])
        if "tencent_speed" in config:
            result["tencent_tts_speed"] = str(config["tencent_speed"])

        return result

    async def _upsert_config(self, key: str, value: str) -> None:
        """插入或更新单个配置项。"""
        existing = await self.db.execute(
            select(AIConfig).where(AIConfig.config_key == key)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.config_value = value
        else:
            self.db.add(AIConfig(config_key=key, config_value=value))

    def _apply_to_settings(self, updates: dict[str, str]) -> None:
        """将更新同步到 Settings 内存单例。

        直接修改 lru_cache 单例的属性，避免重启即可让 rewriter.py /
        synthesizer.py 读到新配置。
        """
        settings = get_settings()
        for key, value in updates.items():
            attr = CONFIG_KEY_MAP.get(key)
            if not attr:
                continue
            # int 类型字段转换
            if key in INT_KEYS:
                try:
                    setattr(settings, attr, int(value))
                except (ValueError, TypeError):
                    pass
            # float 类型字段转换（如段间静音时长）
            elif key in FLOAT_KEYS:
                try:
                    setattr(settings, attr, float(value))
                except (ValueError, TypeError):
                    pass
            else:
                setattr(settings, attr, value)

    # ---- 启动时加载 ----

    async def apply_config_to_settings(self) -> None:
        """启动时从 SQLite 加载 AI 配置覆盖到 Settings 单例。

        在 main.py lifespan 中调用，使 .env 中的配置可被前端修改覆盖。
        """
        raw = await self.get_all_config()
        if not raw:
            return

        settings = get_settings()
        applied = []
        for key, value in raw.items():
            attr = CONFIG_KEY_MAP.get(key)
            if not attr:
                continue
            if key in INT_KEYS:
                try:
                    setattr(settings, attr, int(value))
                except (ValueError, TypeError):
                    pass
            elif key in FLOAT_KEYS:
                try:
                    setattr(settings, attr, float(value))
                except (ValueError, TypeError):
                    pass
            else:
                setattr(settings, attr, value)
            applied.append(key)

        if applied:
            logger.info("从 SQLite 加载 AI 配置 %d 项: %s", len(applied), applied)

    # ---- 连接测试 ----

    async def test_llm_connection(
        self, base_url: str, api_key: str, model: str
    ) -> dict:
        """测试 LLM 连接（走 OpenAI 兼容协议）。

        发送最小化请求（max_tokens=5），验证鉴权与网络连通性。
        超时 15s，避免长时间阻塞。
        """
        if not api_key or _is_masked(api_key):
            # 使用已保存的配置（前端传脱敏值时也回退到已保存值）
            saved_key = await self.get_config_value("llm_api_key")
            if not saved_key:
                return {"success": False, "message": "API Key 未配置"}
            api_key = saved_key

        url = base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            return {"success": False, "message": "连接超时（>15s），请检查网络或 base_url"}
        except httpx.RequestError as e:
            return {"success": False, "message": f"网络错误: {e}"}

        if resp.status_code == 200:
            # 尝试提取返回的 token 用量
            usage = resp.json().get("usage", {})
            return {
                "success": True,
                "message": "连接成功",
                "model": model,
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            }
        elif resp.status_code == 401:
            return {"success": False, "message": "API Key 无效或已过期（401）"}
        elif resp.status_code == 429:
            return {"success": False, "message": "API 限流（429），请稍后重试"}
        else:
            snippet = resp.text[:200]
            return {
                "success": False,
                "message": f"服务返回 {resp.status_code}: {snippet}",
            }

    async def test_tts_connection(
        self,
        provider: str = "aliyun",
        api_key: str = "",
        appkey: str = "",
        edge_voice: str = "",
        tencent_secret_id: str = "",
        tencent_secret_key: str = "",
        tencent_region: str = "",
        tencent_voice_type: int = 0,
    ) -> dict:
        """测试 TTS 连接，按 provider 分支选择测试逻辑。

        aliyun：发送最小化合成请求验证 token/appkey 有效性（不等待合成完成）
        edge：合成一句测试文本验证网络连通性（Edge-TTS 无鉴权概念）
        tencent：合成一句测试文本验证凭证有效性

        脱敏值（****开头）视为未修改，回退到已保存配置。
        """
        provider = provider or get_settings().TTS_PROVIDER or "aliyun"

        if provider == "aliyun":
            return await self._test_aliyun(api_key, appkey)
        elif provider == "edge":
            return await self._test_edge(edge_voice)
        elif provider == "tencent":
            return await self._test_tencent(
                tencent_secret_id, tencent_secret_key,
                tencent_region, tencent_voice_type,
            )
        return {"success": False, "message": f"未知的 TTS provider: {provider}"}

    async def _test_aliyun(self, api_key: str, appkey: str) -> dict:
        """测试阿里云 NLS 鉴权（发送最小化合成任务创建请求）。"""
        if not api_key or _is_masked(api_key):
            saved_key = await self.get_config_value("tts_api_key")
            if not saved_key:
                return {"success": False, "message": "TTS API Key 未配置"}
            api_key = saved_key

        if not appkey or _is_masked(appkey):
            saved_appkey = await self.get_config_value("tts_appkey")
            if not saved_appkey:
                return {"success": False, "message": "TTS AppKey 未配置"}
            appkey = saved_appkey

        # 从 settings 读取 endpoint，避免硬编码（与 AliyunSpeechClient 保持单一可信源）
        endpoint = get_settings().ALIYUN_TTS_ENDPOINT
        payload = {
            "header": {"appkey": appkey, "token": api_key},
            "context": {"device_id": "config_test"},
            "payload": {
                "enable_notify": False,
                "notify_url": "",
                "tts_request": {
                    "voice": "xiaoyun",
                    "sample_rate": 44100,
                    "format": "mp3",
                    "enable_subtitle": False,
                    "text": "测试",
                },
            },
        }
        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
        except httpx.TimeoutException:
            return {"success": False, "message": "连接超时（>15s）"}
        except httpx.RequestError as e:
            return {"success": False, "message": f"网络错误: {e}"}

        # 阿里云 NLS 错误码 → 可读提示映射
        NLS_ERROR_HINTS = {
            40000001: "请确认填写的是 NLS AccessToken，而非 AccessKey Secret",
            40000010: "阿里云 NLS 免费试用已过期，请在控制台开通正式服务",
            40000004: "appkey 无效，请确认是 NLS 项目的 AppKey",
        }

        try:
            data = resp.json()
        except Exception:
            return {
                "success": False,
                "message": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }

        error_code = data.get("error_code")
        error_msg = data.get("error_message", "")

        if error_code == 20000000:
            return {"success": True, "message": "阿里云 TTS 鉴权成功"}
        if error_code in NLS_ERROR_HINTS:
            return {
                "success": False,
                "message": f"{error_msg}（{error_code}）— {NLS_ERROR_HINTS[error_code]}",
            }
        return {
            "success": False,
            "message": f"TTS 鉴权失败 error_code={error_code} msg={error_msg}",
        }

    async def _test_edge(self, edge_voice: str) -> dict:
        """测试 Edge-TTS 连通性（合成一句测试文本）。

        Edge-TTS 无鉴权概念，测试即实际合成。需能访问 edge-tts WebSocket 服务。
        """
        try:
            from app.workflow.tts.edge_client import EdgeTTSProvider
        except ImportError as e:
            return {"success": False, "message": f"edge-tts 模块加载失败: {e}"}

        # voice 留空时由 provider fallback 到 settings.EDGE_TTS_VOICE
        voice = edge_voice or None
        try:
            provider = EdgeTTSProvider(voice=voice)
        except Exception as e:
            return {"success": False, "message": f"Edge-TTS 初始化失败: {e}"}

        ok = await provider.test_connection()
        if ok:
            return {"success": True, "message": "Edge-TTS 连接成功（免费方案无鉴权）"}
        return {
            "success": False,
            "message": "Edge-TTS 连接失败，请检查网络（需能访问 WebSocket 服务）或音色配置",
        }

    async def _test_tencent(
        self,
        secret_id: str,
        secret_key: str,
        region: str,
        voice_type: int,
    ) -> dict:
        """测试腾讯云 TTS 凭证（合成一句测试文本）。

        凭证脱敏值回退到已保存配置，再回退到 COS 凭证。
        """
        if not secret_id or _is_masked(secret_id):
            saved_id = await self.get_config_value("tencent_tts_secret_id")
            secret_id = saved_id or get_settings().COS_SECRET_ID
        if not secret_key or _is_masked(secret_key):
            saved_key = await self.get_config_value("tencent_tts_secret_key")
            secret_key = saved_key or get_settings().COS_SECRET_KEY

        if not secret_id or not secret_key:
            return {
                "success": False,
                "message": "腾讯云 TTS 凭证未配置（TENCENT_TTS_SECRET_ID/SECRET_KEY 或 COS 凭证）",
            }

        from app.workflow.tts.tencent_client import TencentTTSProvider
        try:
            provider = TencentTTSProvider(
                secret_id=secret_id,
                secret_key=secret_key,
                region=region or None,
                voice_type=voice_type or None,
            )
        except Exception as e:
            return {"success": False, "message": f"腾讯云 TTS 初始化失败: {e}"}

        ok = await provider.test_connection()
        if ok:
            return {"success": True, "message": "腾讯云 TTS 连接成功"}
        return {
            "success": False,
            "message": "腾讯云 TTS 连接失败，请检查凭证与音色配置",
        }

    # ---- 试音合成 ----

    async def preview_tts(
        self, # NOSONAR
        text: str,
        provider: str = "edge",
        # 阿里云参数
        aliyun_api_key: str = "",
        aliyun_appkey: str = "",
        aliyun_voice: str = "",
        aliyun_volume: int = 50,
        aliyun_speech_rate: int = 0,
        aliyun_pitch_rate: int = 0,
        # Edge-TTS 参数
        edge_voice: str = "",
        edge_rate: str = "",
        edge_volume: str = "",
        edge_pitch: str = "",
        # 腾讯云参数
        tencent_secret_id: str = "",
        tencent_secret_key: str = "",
        tencent_region: str = "",
        tencent_voice_type: int = 0,
        tencent_volume: int = 0,
        tencent_speed: int = 0,
    ) -> bytes:
        """用传入的临时参数合成试音音频（不依赖已保存配置）。

        与 test_tts_connection 的区别：测试连接只验证鉴权，试音返回实际音频
        供前端播放判断效果。所有参数从当前表单实时传入，用户调整参数后无需
        保存即可试听。

        Raises:
            ValueError: provider 未知或凭证缺失
            TTSError: 合成失败（网络/鉴权/音色等）
        """
        provider = provider or get_settings().TTS_PROVIDER or "edge"

        if not text.strip():
            raise ValueError("试音文本不能为空")

        if provider == "aliyun":
            return await self._preview_aliyun(
                text, aliyun_api_key, aliyun_appkey, aliyun_voice,
                aliyun_volume, aliyun_speech_rate, aliyun_pitch_rate,
            )
        elif provider == "edge":
            return await self._preview_edge(
                text, edge_voice, edge_rate, edge_volume, edge_pitch,
            )
        elif provider == "tencent":
            return await self._preview_tencent(
                text, tencent_secret_id, tencent_secret_key,
                tencent_region, tencent_voice_type,
                tencent_volume, tencent_speed,
            )
        raise ValueError(f"未知的 TTS provider: {provider}")

    async def _preview_aliyun(
        self, text, api_key, appkey, voice,
        volume, speech_rate, pitch_rate,
    ) -> bytes:
        """阿里云试音：脱敏值回退到已保存配置，用临时参数创建实例合成。"""
        if not api_key or _is_masked(api_key):
            api_key = await self.get_config_value("tts_api_key") or ""
        if not appkey or _is_masked(appkey):
            appkey = await self.get_config_value("tts_appkey") or ""
        if not api_key:
            raise ValueError("阿里云 TTS API Key 未配置")
        if not appkey:
            raise ValueError("阿里云 TTS AppKey 未配置")

        from app.workflow.tts.aliyun_client import AliyunSpeechClient
        client = AliyunSpeechClient(
            api_key=api_key,
            volume=volume,
            speech_rate=speech_rate,
            pitch_rate=pitch_rate,
        )
        return await client.synthesize(
            text, voice=voice or None,
            format=get_settings().ALIYUN_TTS_FORMAT,
            sample_rate=get_settings().ALIYUN_TTS_SAMPLE_RATE,
        )

    async def _preview_edge(
        self, text, voice, rate, volume, pitch,
    ) -> bytes:
        """Edge-TTS 试音：用临时参数创建实例合成。"""
        from app.workflow.tts.edge_client import EdgeTTSProvider
        provider = EdgeTTSProvider(
            voice=voice or None,
            rate=rate or None,
            volume=volume or None,
            pitch=pitch or None,
        )
        return await provider.synthesize(text, format="mp3", sample_rate=16000)

    async def _preview_tencent(
        self, text, secret_id, secret_key, region, voice_type,
        volume, speed,
    ) -> bytes:
        """腾讯云试音：脱敏值回退到已保存配置，用临时参数创建实例合成。"""
        if not secret_id or _is_masked(secret_id):
            secret_id = await self.get_config_value("tencent_tts_secret_id") or ""
        if not secret_id:
            secret_id = get_settings().COS_SECRET_ID
        if not secret_key or _is_masked(secret_key):
            secret_key = await self.get_config_value("tencent_tts_secret_key") or ""
        if not secret_key:
            secret_key = get_settings().COS_SECRET_KEY
        if not secret_id or not secret_key:
            raise ValueError("腾讯云 TTS 凭证未配置")

        from app.workflow.tts.tencent_client import TencentTTSProvider
        provider = TencentTTSProvider(
            secret_id=secret_id,
            secret_key=secret_key,
            region=region or None,
            voice_type=voice_type or None,
            volume=volume,
            speed=speed,
        )
        return await provider.synthesize(text, format="mp3", sample_rate=16000)

    # ---- 用量记录 ----

    async def record_usage(
        self,
        service_type: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        char_count: int = 0,
    ) -> None:
        """记录一次 AI 调用的用量。

        供 rewriter.py / synthesizer.py 在调用成功后调用。
        费用按模型定价表自动估算。
        """
        cost = _estimate_cost(
            service_type, model, input_tokens, output_tokens, char_count
        )
        log = AIUsageLog(
            service_type=service_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            char_count=char_count,
            cost_usd=cost,
        )
        self.db.add(log)
        await self.db.commit()

    async def get_usage_summary(self) -> dict:
        """获取用量统计（今日 + 7 天趋势）。

        返回结构：
        {
            "today": {"llm_calls": N, "llm_tokens": N, "tts_calls": N, "tts_chars": N, "cost_usd": F},
            "trend": [{"date": "2026-07-04", "llm_calls": N, ...}, ...]
        }
        """
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())

        # 今日统计
        today_rows = (
            await self.db.execute(self._build_usage_query(today_start, None))
        ).all()
        today_stats = self._aggregate_usage_rows(today_rows)

        # 7 天趋势
        trend = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day + timedelta(days=1), datetime.min.time())
            day_rows = (
                await self.db.execute(self._build_usage_query(day_start, day_end))
            ).all()
            day_stats = self._aggregate_usage_rows(day_rows)
            day_stats["date"] = day.isoformat()
            trend.append(day_stats)

        return {
            "today": today_stats,
            "trend": trend,
        }

    @staticmethod
    def _build_usage_query(start: datetime, end: datetime | None):
        """构建按 service_type 聚合的用量查询（今日/单日复用）。

        end=None 表示仅设下界（今日统计到当前时刻）。
        """
        conditions = [AIUsageLog.created_at >= start]
        if end is not None:
            conditions.append(AIUsageLog.created_at < end)
        return (
            select(
                AIUsageLog.service_type,
                func.sum(AIUsageLog.input_tokens + AIUsageLog.output_tokens).label("tokens"),
                func.sum(AIUsageLog.char_count).label("chars"),
                func.sum(AIUsageLog.cost_usd).label("cost"),
                func.count(AIUsageLog.id).label("calls"),
            ).where(*conditions).group_by(AIUsageLog.service_type)
        )

    @staticmethod
    def _aggregate_usage_rows(rows) -> dict:
        """将 SQL 聚合行合并为标准用量统计结构。"""
        stats = {
            "llm_calls": 0,
            "llm_tokens": 0,
            "tts_calls": 0,
            "tts_chars": 0,
            "cost_usd": 0.0,
        }
        for row in rows:
            stats["cost_usd"] += float(row.cost or 0)
            if row.service_type == "llm":
                stats["llm_calls"] = row.calls or 0
                stats["llm_tokens"] = row.tokens or 0
            elif row.service_type == "tts":
                stats["tts_calls"] = row.calls or 0
                stats["tts_chars"] = row.chars or 0
        stats["cost_usd"] = round(stats["cost_usd"], 6)
        return stats

    # ---- 预设列表 ----

    @staticmethod
    def _match_preset_by_base_url(base_url: str) -> str:
        """根据 base_url 反向匹配预设 key，未匹配返回空字符串。"""
        if not base_url:
            return ""
        for preset in LLM_PRESETS:
            if preset["base_url"] == base_url:
                return preset["key"]
        return ""

    def get_presets(self) -> list[dict]:
        """返回 LLM 提供商预设列表。"""
        return LLM_PRESETS

    def get_voices(self, provider: str = None) -> list[dict]:
        """返回对应 provider 的 TTS 音色列表。

        不同 provider 的音色 ID 体系不同，前端切换 provider 时需重新加载音色列表。
        """
        provider = provider or get_settings().TTS_PROVIDER or "aliyun"

        if provider == "edge":
            return [
                {"key": "zh-CN-XiaoxiaoNeural", "label": "晓晓（标准女声，与阿里云 xiaoyun 听感接近）"},
                {"key": "zh-CN-YunyangNeural", "label": "云扬（新闻男声，业界新闻播报标杆）"},
                {"key": "zh-CN-XiaoyiNeural", "label": "晓伊（温柔女声）"},
                {"key": "zh-CN-YunxiNeural", "label": "云希（沉稳男声）"},
                {"key": "zh-CN-XiaomengNeural", "label": "晓梦（甜美女声）"},
                {"key": "zh-CN-YunfengNeural", "label": "云枫（磁性男声）"},
            ]
        elif provider == "tencent":
            return [
                {"key": "101011", "label": "智燕（新闻女声，精品音色，推荐）"},
                {"key": "101013", "label": "智辉（新闻男声，精品音色）"},
                {"key": "101021", "label": "智瑞（新闻男声，精品音色）"},
                {"key": "501001", "label": "智兰（资讯女声，大模型音色，24k）"},
                {"key": "101001", "label": "智瑜（情感女声）"},
                {"key": "101004", "label": "智云（通用男声）"},
            ]
        # 默认阿里云
        return [
            {"key": "xiaoyun", "label": "小芸（标准女声）"},
            {"key": "xiaoyi", "label": "小伊（温柔女声）"},
            {"key": "xiaoxiao", "label": "小晓（知性女声）"},
            {"key": "xiaomeng", "label": "小梦（甜美女声）"},
            {"key": "xiaowei", "label": "小维（沉稳男声）"},
            {"key": "aiya", "label": "艾雅（活泼女声）"},
        ]

