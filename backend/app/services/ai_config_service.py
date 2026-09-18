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
from openai import AsyncOpenAI
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import BizError, ParamError
from app.core.tc3_sign import TencentAPIError, utc_now_iso
from app.core.timeutil import localnow_naive
from app.models.ai_config import AIConfig, AIUsageLog

logger = logging.getLogger(__name__)

# ---- TTS 音色（T00388 音色同步） ----

# 同步缓存写 ai_config 表的 key 前缀（每 provider 一条，值为 JSON：
# {items: [{key,label}], synced_at: ISO8601, source: <官方接口标识>}）
VOICES_CACHE_KEY_PREFIX = "tts_voices_cache_"

# 支持从官方接口同步音色的引擎：edge（微软，无鉴权）/ tencent（DescribeVoices，TC3 签名）。
# aliyun 无公开音色列表 API；kokoro/piper 为本地离线引擎，音色清单天然静态。
VOICES_SYNC_SUPPORTED = ("edge", "tencent")

# 内置静态音色清单（同步前兜底 / 同步失败回退 / 不支持同步引擎的唯一来源）
_STATIC_VOICES: dict[str, list[dict]] = {
    "edge": [
        # 以下音色 ID 均与微软官方 zh-CN Neural 目录一致（已用 edge-tts --list-voices 实时核对）。
        # 注意：XiaomengNeural / YunfengNeural 在早期博客中常见，但当前线上服务已不存在，
        # 选中后会触发 NoAudioReceived，故已从列表移除。
        {"key": "zh-CN-XiaoxiaoNeural", "label": "晓晓（标准女声·温暖·新闻/小说，默认）"},
        {"key": "zh-CN-YunyangNeural", "label": "云扬（新闻男声·专业可靠，业界新闻播报标杆）"},
        {"key": "zh-CN-XiaoyiNeural", "label": "晓伊（活泼女声·卡通/小说）"},
        {"key": "zh-CN-YunxiNeural", "label": "云希（阳光男声·小说）"},
        {"key": "zh-CN-YunjianNeural", "label": "云健（男声·激情·体育/小说）"},
        {"key": "zh-CN-YunxiaNeural", "label": "云夏（可爱男声·卡通/小说）"},
        {"key": "zh-CN-liaoning-XiaobeiNeural", "label": "晓蓓（女声·东北话·幽默）"},
        {"key": "zh-CN-shaanxi-XiaoniNeural", "label": "晓妮（女声·陕西话·明亮）"},
    ],
    "tencent": [
        {"key": "101011", "label": "智燕（新闻女声，精品音色，推荐）"},
        {"key": "101013", "label": "智辉（新闻男声，精品音色）"},
        {"key": "101021", "label": "智瑞（新闻男声，精品音色）"},
        {"key": "501001", "label": "智兰（资讯女声，大模型音色，24k）"},
        {"key": "101001", "label": "智瑜（情感女声）"},
        {"key": "101004", "label": "智云（通用男声）"},
    ],
    "kokoro": [
        # 本地离线，免费高质量；须与 lang 匹配
        {"key": "zf_xiaobei", "label": "zf_xiaobei（女声·温柔甜美，有声书/客服）"},
        {"key": "zf_xiaoni", "label": "zf_xiaoni（女声·清亮活泼，短视频）"},
        {"key": "zf_xiaoxiao", "label": "zf_xiaoxiao（女声·成熟稳重，新闻播报·默认）"},
        {"key": "zf_xiaoyi", "label": "zf_xiaoyi（女声·专业正式，教程）"},
        {"key": "zm_yunjian", "label": "zm_yunjian（男声·青春活力，游戏）"},
        {"key": "zm_yunxi", "label": "zm_yunxi（男声·温柔细腻，有声小说）"},
        {"key": "zm_yunxia", "label": "zm_yunxia（男声·成熟稳重，企业）"},
        {"key": "zm_yunyang", "label": "zm_yunyang（男声·浑厚有力，纪录片旁白）"},
    ],
    "piper": [
        # 本地离线，轻量免费；模型需另行下载
        {"key": "zh_CN-huayan-medium", "label": "zh_CN-huayan-medium（中文女声·medium·默认）"},
        {"key": "zh_CN-huayan-x_low", "label": "zh_CN-huayan-x_low（中文女声·x_low 更小更快）"},
        {"key": "zh_CN-chenyang-medium", "label": "zh_CN-chenyang-medium（中文男声·medium）"},
        {"key": "zh_CN-lessac-medium", "label": "zh_CN-lessac-medium（中文·medium）"},
    ],
    "aliyun": [
        {"key": "xiaoyun", "label": "小芸（标准女声）"},
        {"key": "xiaoyi", "label": "小伊（温柔女声）"},
        {"key": "xiaoxiao", "label": "小晓（知性女声）"},
        {"key": "xiaomeng", "label": "小梦（甜美女声）"},
        {"key": "xiaowei", "label": "小维（沉稳男声）"},
        {"key": "aiya", "label": "艾雅（活泼女声）"},
    ],
}

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
    # 单期节目最大段数上限（T00584 得到式听书：20-30 分钟需 15-20 段）
    "llm_max_script_segments": "LLM_MAX_SCRIPT_SEGMENTS",
    # 图片生成（T00730：频道图标 AI 生成，OpenAI 兼容 agnes 接口）
    "image_api_key": "IMAGE_API_KEY",
    "image_api_base_url": "IMAGE_API_BASE_URL",
    "image_api_model": "IMAGE_API_MODEL",
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
    # Kokoro TTS（Apache 2.0 本地离线，免费高质量）
    "kokoro_lang": "KOKORO_LANG",
    "kokoro_voice": "KOKORO_VOICE",
    "kokoro_speed": "KOKORO_SPEED",
    # Piper TTS（MIT 本地离线，轻量免费）
    "piper_voice": "PIPER_VOICE",
    "piper_voice_dir": "PIPER_VOICE_DIR",
    "piper_length_scale": "PIPER_LENGTH_SCALE",
    "piper_volume": "PIPER_VOLUME",
    "piper_noise_scale": "PIPER_NOISE_SCALE",
    # TTS 交叉音色（段落间轮流换声，避免同质化）：JSON 字符串，按 provider 维度存音色列表
    "tts_cross_voice": "TTS_CROSS_VOICE",
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
    "kokoro_speed",
    "piper_length_scale",
    "piper_volume",
    "piper_noise_scale",
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


def _parse_cross_voice(raw) -> dict:
    """解析交叉音色配置 JSON，返回带默认值的规范化结构。

    结构：{"enabled": bool, "strategy": str, "interval": int,
           "voices": {provider: [voice_key, ...]}}
    解析失败时返回全默认（disabled），不抛异常，保证前端表单始终可渲染、
    synthesizer 永远拿到合法结构。

    Args:
        raw: JSON 字符串或已解析的 dict（前端可能直接传对象）。
    """
    defaults = {
        "enabled": False,
        "strategy": "round_robin",
        "interval": 2,
        "voices": {},
    }
    if not raw:
        return defaults
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("交叉音色配置 JSON 解析失败，使用默认关闭")
            return defaults
    elif isinstance(raw, dict):
        data = raw
    else:
        return defaults
    if not isinstance(data, dict):
        return defaults
    voices = data.get("voices")
    norm_voices: dict[str, list] = {}
    if isinstance(voices, dict):
        for k, v in voices.items():
            if isinstance(v, list):
                # 仅保留非空字符串音色 key，过滤 None/数字等非法项，保证落库结构干净
                norm_voices[str(k)] = [x for x in v if isinstance(x, str) and x]
    return {
        "enabled": bool(data.get("enabled", False)),
        "strategy": str(data.get("strategy", "round_robin")),
        "interval": int(data.get("interval", 2) or 2),
        "voices": norm_voices,
    }


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
            # Kokoro TTS（本地离线，免费高质量）
            "kokoro_lang": _get("kokoro_lang", "KOKORO_LANG", "z"),
            "kokoro_voice": _get("kokoro_voice", "KOKORO_VOICE", "zf_xiaoxiao"),
            "kokoro_speed": _get_float("kokoro_speed", "KOKORO_SPEED", 1.0),
            # Piper TTS（本地离线，轻量免费）
            "piper_voice": _get("piper_voice", "PIPER_VOICE", "zh_CN-huayan-medium"),
            "piper_voice_dir": _get("piper_voice_dir", "PIPER_VOICE_DIR", "./models/piper"),
            "piper_length_scale": _get_float("piper_length_scale", "PIPER_LENGTH_SCALE", 1.0),
            "piper_volume": _get_float("piper_volume", "PIPER_VOLUME", 0.5),
            "piper_noise_scale": _get_float("piper_noise_scale", "PIPER_NOISE_SCALE", 0.667),
            # TTS 交叉音色（段落间轮流换声，避免同质化）
            # 解析 JSON 字符串为对象返回前端；缺省/解析失败回退到关闭的默认结构
            "cross_voice": _parse_cross_voice(_get("tts_cross_voice", "TTS_CROSS_VOICE", "{}")),
        }

        return {"llm": llm_config, "tts": tts_config, "image": self._get_image_config(raw)}

    def _get_image_config(self, raw: dict[str, str] | None = None) -> dict:
        """图片生成配置段（T00730）：SQLite 覆盖优先，回退 Settings 默认值。"""
        raw = raw if raw is not None else {}
        settings = get_settings()

        def _get(key: str, settings_attr: str, default: str = "") -> str:
            val = raw.get(key)
            if val is not None:
                return val
            return str(getattr(settings, settings_attr, default))

        return {
            "api_key": _mask_key(_get("image_api_key", "IMAGE_API_KEY")),
            "base_url": _get("image_api_base_url", "IMAGE_API_BASE_URL"),
            "model": _get("image_api_model", "IMAGE_API_MODEL"),
        }

    # ---- 配置更新 ----

    async def update_config(
        self,
        llm_config: dict,
        tts_config: dict,
        selected_preset: str = "",
        image_config: dict | None = None,
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
        # 图片生成配置（T00730）：可选段，旧前端不传时跳过
        if image_config:
            for key, value in self._normalize_image(image_config).items():
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
        if any(k.startswith(("tts_", "edge_", "tencent_tts_", "kokoro_", "piper_")) for k in updates):
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

    def _normalize_image(self, config: dict) -> dict[str, str]:
        """将前端图片生成配置转为 config_key -> value 映射（T00730）。

        API Key 脱敏值跳过（未修改），空字符串清除。
        """
        result: dict[str, str] = {}
        api_key = config.get("api_key", "")
        if api_key and not _is_masked(api_key):
            result["image_api_key"] = api_key
        if "base_url" in config:
            result["image_api_base_url"] = str(config["base_url"] or "")
        if "model" in config:
            result["image_api_model"] = str(config["model"] or "")
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

        # Kokoro TTS（本地离线，免费高质量）
        if "kokoro_lang" in config:
            result["kokoro_lang"] = config["kokoro_lang"]
        if "kokoro_voice" in config:
            result["kokoro_voice"] = config["kokoro_voice"]
        if "kokoro_speed" in config:
            # 0 视为默认 1.0，统一标准化避免把 0 当成静音
            result["kokoro_speed"] = str(config["kokoro_speed"] or 1.0)

        # Piper TTS（本地离线，轻量免费）
        if "piper_voice" in config:
            result["piper_voice"] = config["piper_voice"]
        if "piper_voice_dir" in config:
            result["piper_voice_dir"] = config["piper_voice_dir"]
        if "piper_length_scale" in config:
            result["piper_length_scale"] = str(config["piper_length_scale"] or 1.0)
        if "piper_volume" in config:
            result["piper_volume"] = str(config["piper_volume"] or 0.5)
        if "piper_noise_scale" in config:
            result["piper_noise_scale"] = str(config["piper_noise_scale"] or 0.667)

        # TTS 交叉音色（段落间轮流换声）：前端传对象，规范化后序列化为 JSON 字符串存储
        if "cross_voice" in config:
            cv = config["cross_voice"]
            if cv is None:
                # 显式清空
                result["tts_cross_voice"] = "{}"
            else:
                # 先规范化再序列化，保证落库结构稳定（去除非法字段/类型）
                result["tts_cross_voice"] = json.dumps(
                    _parse_cross_voice(cv), ensure_ascii=False
                )

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
        kokoro_lang: str = "",
        kokoro_voice: str = "",
        piper_voice: str = "",
        piper_voice_dir: str = "",
    ) -> dict:
        """测试 TTS 连接，按 provider 分支选择测试逻辑。

        aliyun：发送最小化合成请求验证 token/appkey 有效性（不等待合成完成）
        edge：合成一句测试文本验证网络连通性（Edge-TTS 无鉴权概念）
        tencent：合成一句测试文本验证凭证有效性
        kokoro：合成一句测试文本验证本地模型是否可用（完全离线）
        piper：合成一句测试文本验证本地模型文件是否可用（完全离线）

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
        elif provider == "kokoro":
            return await self._test_kokoro(kokoro_lang, kokoro_voice)
        elif provider == "piper":
            return await self._test_piper(piper_voice, piper_voice_dir)
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

    async def _test_kokoro(self, lang: str, voice: str) -> dict:
        """测试 Kokoro 本地模型是否可用（合成一句测试文本，完全离线）。"""
        try:
            from app.workflow.tts.kokoro_client import KokoroProvider
        except ImportError as e:
            return {"success": False, "message": f"kokoro 模块加载失败: {e}"}

        lang = lang or None
        voice = voice or None
        try:
            provider = KokoroProvider(lang=lang, voice=voice)
        except Exception as e:
            return {"success": False, "message": f"Kokoro 初始化失败（依赖/模型缺失）: {e}"}

        ok = await provider.test_connection()
        if ok:
            return {"success": True, "message": "Kokoro 连接成功（本地离线，免费）"}
        return {
            "success": False,
            "message": "Kokoro 连接失败，请确认已安装 kokoro misaki[zh] 且模型可加载",
        }

    async def _test_piper(self, voice: str, voice_dir: str) -> dict:
        """测试 Piper 本地模型文件是否可用（合成一句测试文本，完全离线）。"""
        try:
            from app.workflow.tts.piper_client import PiperProvider
        except ImportError as e:
            return {"success": False, "message": f"piper-tts 模块加载失败: {e}"}

        voice = voice or None
        voice_dir = voice_dir or None
        try:
            provider = PiperProvider(voice=voice, voice_dir=voice_dir)
        except Exception as e:
            return {"success": False, "message": f"Piper 初始化失败（依赖/模型缺失）: {e}"}

        ok = await provider.test_connection()
        if ok:
            return {"success": True, "message": "Piper 连接成功（本地离线，免费）"}
        return {
            "success": False,
            "message": "Piper 连接失败，请确认已安装 piper-tts 且模型文件存在",
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
        # Kokoro 参数
        kokoro_lang: str = "",
        kokoro_voice: str = "",
        kokoro_speed: float = 0.0,
        # Piper 参数
        piper_voice: str = "",
        piper_voice_dir: str = "",
        piper_length_scale: float = 0.0,
        piper_volume: float = 0.0,
        piper_noise_scale: float = 0.0,
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
        elif provider == "kokoro":
            return await self._preview_kokoro(
                text, kokoro_lang, kokoro_voice, kokoro_speed,
            )
        elif provider == "piper":
            return await self._preview_piper(
                text, piper_voice, piper_voice_dir,
                piper_length_scale, piper_volume, piper_noise_scale,
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

    async def _preview_kokoro(
        self, text, lang, voice, speed,
    ) -> bytes:
        """Kokoro 试音：用临时参数创建实例合成（完全离线）。"""
        from app.workflow.tts.kokoro_client import KokoroProvider
        provider = KokoroProvider(
            lang=lang or None,
            voice=voice or None,
            speed=speed or None,
        )
        return await provider.synthesize(text, format="wav", sample_rate=24000)

    async def _preview_piper(
        self, text, voice, voice_dir,
        length_scale, volume, noise_scale,
    ) -> bytes:
        """Piper 试音：用临时参数创建实例合成（完全离线）。"""
        from app.workflow.tts.piper_client import PiperProvider
        provider = PiperProvider(
            voice=voice or None,
            voice_dir=voice_dir or None,
            length_scale=length_scale or None,
            volume=volume or None,
            noise_scale=noise_scale or None,
        )
        return await provider.synthesize(text, format="wav", sample_rate=22050)

    # ---- 模型列表拉取 & 问答 ----

    async def fetch_llm_models(self, base_url: str, api_key: str) -> dict:
        """从 OpenAI 兼容接口拉取可用模型列表并解析。

        解析 {base_url}/models 返回的 {"object":"list","data":[{id,...}]}。
        兼容 base_url 是否带 /v1（404 时回退 /v1/models）。
        明确区分四类错误：API Key 未配置 / base_url 不可达 / API Key 无效(401) /
        返回内容无法解析为模型列表。

        返回结构：{"success": bool, "models": [{"id","owned_by"}], "message": str}
        """
        settings = get_settings()

        # API Key 解析：脱敏值或未传 → 回退到已保存明文
        if not api_key or _is_masked(api_key):
            saved_key = await self.get_config_value("llm_api_key")
            api_key = saved_key or settings.LLM_API_KEY or ""
        if not base_url:
            base_url = settings.LLM_BASE_URL

        if not api_key:
            return {
                "success": False,
                "models": [],
                "message": "API Key 未配置，请先在「LLM 大模型」中填写并保存",
            }
        if not base_url:
            return {
                "success": False,
                "models": [],
                "message": "API Base URL 未配置，请先在「LLM 大模型」中填写",
            }

        # 候选地址：base_url 可能已含 /v1，也可能不含
        normalized = base_url.rstrip("/")
        candidates = [normalized + "/models"]
        if not normalized.endswith("/v1"):
            candidates.append(normalized + "/v1/models")

        headers = {"Authorization": f"Bearer {api_key}"}
        timeout = float(settings.LLM_TIMEOUT_SEC or 30)
        last_net_err = None

        async with httpx.AsyncClient(timeout=timeout) as client:
            for url in candidates:
                try:
                    resp = await client.get(url, headers=headers)
                except httpx.TimeoutException:
                    return {
                        "success": False,
                        "models": [],
                        "message": f"连接超时（>{int(timeout)}s），请检查 API Base URL 是否可达：{base_url}",
                    }
                except httpx.RequestError as e:
                    # 候选地址逐个尝试，仅当全部失败才报不可达
                    last_net_err = f"无法连接到 {base_url}：{e}"
                    continue

                if resp.status_code == 200:
                    try:
                        payload = resp.json()
                    except Exception:
                        return {
                            "success": False,
                            "models": [],
                            "message": "接口返回内容不是合法 JSON，请确认 Base URL 指向 OpenAI 兼容的 /models 接口",
                        }
                    models = self._parse_models(payload)
                    if not models:
                        return {
                            "success": False,
                            "models": [],
                            "message": "接口返回模型列表为空，请确认该账户是否有可用模型",
                        }
                    return {
                        "success": True,
                        "models": models,
                        "message": f"成功获取 {len(models)} 个模型",
                    }
                elif resp.status_code == 401:
                    return {
                        "success": False,
                        "models": [],
                        "message": "API Key 无效或已过期（401），请检查后重试",
                    }
                elif resp.status_code == 404:
                    # 尝试下一个候选地址（/v1/models）
                    continue
                else:
                    snippet = resp.text[:200]
                    return {
                        "success": False,
                        "models": [],
                        "message": f"服务返回 {resp.status_code}: {snippet}",
                    }

        if last_net_err:
            return {"success": False, "models": [], "message": last_net_err}
        return {
            "success": False,
            "models": [],
            "message": "未找到模型接口（已尝试 /models 与 /v1/models），请确认 Base URL 是否正确",
        }

    @staticmethod
    def _parse_models(payload: dict) -> list[dict]:
        """从 OpenAI /models 响应解析模型列表。

        返回 [{"id": str, "owned_by": str}]，去重并按 id 升序，保证展示稳定。
        兼容 data 为对象数组或纯字符串数组两种形态。
        """
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if not isinstance(data, list):
            return []

        parsed: list[dict] = []
        for item in data:
            if isinstance(item, str):
                parsed.append({"id": item, "owned_by": ""})
            elif isinstance(item, dict) and item.get("id"):
                parsed.append({
                    "id": str(item["id"]),
                    "owned_by": str(item.get("owned_by", "")),
                })

        seen: set[str] = set()
        unique: list[dict] = []
        for m in sorted(parsed, key=lambda x: x["id"]):
            if m["id"] in seen:
                continue
            seen.add(m["id"])
            unique.append(m)
        return unique

    async def chat_with_model(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict],
    ) -> dict:
        """用指定模型进行问答（OpenAI 兼容 chat/completions）。

        优先使用传入的 base_url/api_key（来自已保存配置），缺失时回退到 settings。
        返回结构：{"success": bool, "reply": str, "model": str,
                  "input_tokens": int, "output_tokens": int, "message": str}
        """
        settings = get_settings()

        if not api_key or _is_masked(api_key):
            saved_key = await self.get_config_value("llm_api_key")
            api_key = saved_key or settings.LLM_API_KEY or ""
        if not base_url:
            base_url = settings.LLM_BASE_URL
        if not model:
            model = settings.LLM_MODEL

        if not api_key:
            return {
                "success": False,
                "reply": "",
                "model": model,
                "input_tokens": 0,
                "output_tokens": 0,
                "message": "API Key 未配置，请先在「LLM 大模型」中填写并保存",
            }
        if not base_url:
            return {
                "success": False,
                "reply": "",
                "model": model,
                "input_tokens": 0,
                "output_tokens": 0,
                "message": "API Base URL 未配置",
            }

        try:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                timeout=float(settings.LLM_TIMEOUT_SEC or 30),
            )
        except Exception as e:
            # openai 各类异常（鉴权/超时/限流等）统一兜底为可读提示；
            # 非 openai 异常（如代码 bug）继续抛出，避免被静默吞掉
            if "openai" not in type(e).__module__:
                raise
            return {
                "success": False,
                "reply": "",
                "model": model,
                "input_tokens": 0,
                "output_tokens": 0,
                "message": f"调用模型失败（{type(e).__name__}）：{e}",
            }

        reply = resp.choices[0].message.content or ""
        usage = resp.usage
        in_tok = usage.prompt_tokens if usage else 0
        out_tok = usage.completion_tokens if usage else 0

        # 记录用量（不阻塞主流程，失败仅告警）
        try:
            await self.record_usage(
                "llm", model, input_tokens=in_tok, output_tokens=out_tok
            )
        except Exception as e:  # NOSONAR
            logger.warning("问答用量记录失败: %s", e)

        return {
            "success": True,
            "reply": reply,
            "model": model,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "message": "ok",
        }

    async def get_selected_model(self) -> str:
        """读取上次选择的默认模型（llm_selected_model 配置项）。"""
        return await self.get_config_value("llm_selected_model") or ""

    async def set_selected_model(self, model: str) -> None:
        """保存用户最后选择的模型为默认选项。"""
        await self._upsert_config("llm_selected_model", model or "")
        await self.db.commit()

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
        # created_at 显式设为本地 naive 时间（localnow_naive）：模型列
        # server_default=func.now() 在 SQLite 下返回 UTC，而 get_usage_summary 的
        # today 区间用本地 naive 日期切分，若不显式置本地时间会造成约 8 小时
        # （UTC vs 本地）归属偏差。项目约定统一用本地日期做按日分桶。
        log = AIUsageLog(
            service_type=service_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            char_count=char_count,
            cost_usd=cost,
            created_at=localnow_naive(),
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
        """返回内置静态音色清单（同步兜底接口，保留给无 DB 的调用场景）。"""
        provider = provider or get_settings().TTS_PROVIDER or "aliyun"
        return self._static_voices(provider)

    async def get_voices_cached(self, provider: str = None) -> list[dict]:
        """返回音色列表（异步版，供路由使用）。

        优先级（T00388 音色同步）：
        1. ai_config 表中的同步缓存（tts_voices_cache_<provider>，来自官方接口）
        2. 内置静态清单 _STATIC_VOICES（同步前 / 缓存读取失败 / 不支持同步的引擎）
        """
        provider = provider or get_settings().TTS_PROVIDER or "aliyun"
        cache = await self._read_voices_cache(provider)
        if cache:
            return cache["items"]
        return self._static_voices(provider)

    @staticmethod
    def _static_voices(provider: str) -> list[dict]:
        """返回内置静态音色清单（兜底，不做 IO）。"""
        return _STATIC_VOICES.get(provider, _STATIC_VOICES["aliyun"])

    async def get_voice_meta(self, provider: str = None) -> dict:
        """返回音色列表的同步元信息（是否官方同步 / 同步时间 / 数量）。"""
        provider = provider or get_settings().TTS_PROVIDER or "aliyun"
        cache = await self._read_voices_cache(provider)
        if cache:
            return {
                "provider": provider,
                "is_custom": True,
                "synced_at": cache.get("synced_at", ""),
                "source": cache.get("source", ""),
                "count": len(cache.get("items", [])),
            }
        return {
            "provider": provider,
            "is_custom": False,
            "synced_at": "",
            "source": "builtin",
            "count": len(self._static_voices(provider)),
        }

    async def _read_voices_cache(self, provider: str) -> Optional[dict]:
        """读取音色同步缓存；损坏/为空/表缺失时返回 None（上层回退静态清单）。"""
        result = await self.db.execute(
            select(AIConfig.config_value).where(
                AIConfig.config_key == f"{VOICES_CACHE_KEY_PREFIX}{provider}"
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        try:
            data = json.loads(row)
        except (TypeError, ValueError) as e:
            logger.warning("[ai_config] 音色缓存 JSON 损坏，回退内置清单: %s", e)
            return None
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list) or not items:
            return None
        return data

    async def sync_voices(self, provider: str) -> dict:
        """从官方接口拉取最新音色列表并持久化（T00388 同步按钮）。

        - edge：微软官方 Azure Neural 目录（edge-tts list_voices，无鉴权）
        - tencent：腾讯云 DescribeVoices（TC3 签名，复用 COS/TTS SecretId/Key）
        - aliyun / kokoro / piper：无公开官方列表接口（本地引擎音色为静态清单），
          明确报错提示，不做伪同步。

        拉取结果规范化为 [{key, label}]（key/label 字段与既有前端契约完全一致），
        写入 ai_config 表 tts_voices_cache_<provider>，get_voices 读取时优先返回。
        """
        provider = (provider or "").strip().lower()
        if provider not in VOICES_SYNC_SUPPORTED:
            raise ParamError(
                f"引擎「{provider}」无官方音色列表接口，音色清单为内置静态维护，不支持同步"
            )

        if provider == "edge":
            items, source = await self._fetch_edge_voices()
        else:
            items, source = await self._fetch_tencent_voices()

        if not items:
            raise BizError("官方接口返回空音色列表，已保留原列表不变")

        synced_at = utc_now_iso()
        await self._upsert_config(
            f"{VOICES_CACHE_KEY_PREFIX}{provider}",
            json.dumps({"items": items, "synced_at": synced_at, "source": source}, ensure_ascii=False),
        )
        # _upsert_config 只做 add/改值不提交，这里必须显式 commit，
        # 否则请求结束后事务回滚、同步结果丢失
        await self.db.commit()
        logger.info("[ai_config] 音色同步完成 provider=%s count=%s source=%s", provider, len(items), source)
        return {"provider": provider, "items": items, "synced_at": synced_at, "source": source, "count": len(items)}

    async def reset_voices_cache(self, provider: str) -> dict:
        """清除音色同步缓存，回退到内置静态清单（同步结果异常时的逃生口）。"""
        provider = (provider or "").strip().lower()
        await self.db.execute(
            delete(AIConfig).where(AIConfig.config_key == f"{VOICES_CACHE_KEY_PREFIX}{provider}")
        )
        await self.db.commit()
        return {"provider": provider, "is_custom": False, "count": len(self._static_voices(provider))}

    @staticmethod
    async def _fetch_edge_voices() -> tuple[list[dict], str]:
        """拉取微软 Edge/Azure 官方 Neural 音色目录，仅保留中文（与静态清单口径一致）。"""
        try:
            import edge_tts
        except ImportError as e:
            raise BizError("edge-tts 库未安装，无法同步官方音色列表") from e

        try:
            raw = await edge_tts.list_voices()
        except Exception as e:
            raise BizError(f"微软官方音色目录拉取失败：{type(e).__name__}: {e}") from e

        _GENDER = {"Female": "女声", "Male": "男声"}
        _LOCALE_ZH = {
            "zh-CN": "普通话", "zh-HK": "粤语", "zh-TW": "台湾国语",
            "zh-CN-liaoning": "东北话", "zh-CN-shaanxi": "陕西话",
        }
        items: list[dict] = []
        seen: set[str] = set()
        for v in raw:
            locale = str(v.get("Locale") or "")
            short = str(v.get("ShortName") or "")
            # 与静态清单同口径：只收中文（zh-CN / zh-HK 等中文变体）
            if not short or not locale.lower().startswith("zh") or short in seen:
                continue
            seen.add(short)
            gender = _GENDER.get(str(v.get("Gender") or ""), str(v.get("Gender") or "未知"))
            # VoicePersonalities 是官方标签数组（如 ["Warm"]），需 join 成字符串避免 list repr 泄漏
            tag_obj = v.get("VoiceTag") or {}
            raw_tag = tag_obj.get("VoicePersonalities") or []
            if isinstance(raw_tag, list):
                personalities = "·".join(str(x) for x in raw_tag)
            else:
                personalities = str(raw_tag)
            # 展示名：完整 ShortName（即配置值，便于核对）+ 口语化 locale/性别/风格标注
            display = short
            locale_desc = _LOCALE_ZH.get(locale, locale)
            parts = [p for p in (locale_desc, gender, personalities) if p]
            items.append({"key": short, "label": f"{display}（{'·'.join(parts)}）" if parts else display})
        items.sort(key=lambda x: (0 if x["key"].startswith("zh-CN") else 1, x["key"]))
        return items, "microsoft-edge-list-voices"

    @staticmethod
    async def _fetch_tencent_voices() -> tuple[list[dict], str]:
        """拉取腾讯云官方音色列表（DescribeVoices，实测 Version=2019-08-23 + WebsiteType=1）。

        响应结构（实测）：CategoryVoiceList[] { CategoryName, VoiceList[] }，
        VoiceList 元素含 VoiceType（音色 ID）/ VoiceName / VoiceDesc / VoiceGender /
        VoiceHumanStyle / VoiceTypeTag（如"大模型,超自然"）。
        """
        settings = get_settings()
        secret_id = settings.TENCENT_TTS_SECRET_ID or settings.COS_SECRET_ID
        secret_key = settings.TENCENT_TTS_SECRET_KEY or settings.COS_SECRET_KEY
        if not (secret_id and secret_key):
            raise ParamError("未配置腾讯云 SecretId/SecretKey（TTS 或 COS 任一即可），无法同步官方音色")

        region = settings.TENCENT_TTS_REGION or ""
        try:
            from app.core.tc3_sign import signed_tencent_post

            response = await signed_tencent_post(
                host="tts.tencentcloudapi.com",
                service="tts",
                action="DescribeVoices",
                version="2019-08-23",
                payload={"WebsiteType": 1},
                secret_id=secret_id,
                secret_key=secret_key,
                region=region,
                timeout_sec=settings.ALIYUN_TTS_TIMEOUT_SEC,
            )
        except TencentAPIError as e:
            raise BizError(f"腾讯云官方音色拉取失败 [{e.code}]：{e.message}") from e

        items: list[dict] = []
        seen: set[str] = set()
        for category in response.get("CategoryVoiceList") or []:
            for v in category.get("VoiceList") or []:
                voice_type = str(v.get("VoiceType") or "").strip()
                name = str(v.get("VoiceName") or "").strip()
                if not voice_type or voice_type in seen:
                    continue
                seen.add(voice_type)
                desc = str(v.get("VoiceDesc") or "").strip()
                style = str(v.get("VoiceHumanStyle") or "").strip()
                tag = str(v.get("VoiceTypeTag") or "").strip().replace(",", "·")
                gender_raw = str(v.get("VoiceGender") or "")
                gender = "女声" if gender_raw == "female" else ("男声" if gender_raw == "male" else "")
                # VoiceDesc（如"阳光男声"）常已含性别，去重避免出现"阳光男声·男声"
                if gender and (gender[0] in desc or gender[0] in style):
                    gender = ""
                parts = [p for p in (style or desc, gender, tag) if p]
                label = f"{name or voice_type}（{'·'.join(parts)}）" if parts else f"{name or voice_type}"
                items.append({"key": voice_type, "label": label})
        return items, "tencent-describe-voices"

