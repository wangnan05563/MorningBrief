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
CONFIG_KEY_MAP = {
    "llm_api_key": "LLM_API_KEY",
    "llm_base_url": "LLM_BASE_URL",
    "llm_model": "LLM_MODEL",
    "llm_timeout_sec": "LLM_TIMEOUT_SEC",
    "llm_retry_attempts": "LLM_RETRY_ATTEMPTS",
    "tts_api_key": "ALIYUN_TTS_API_KEY",
    "tts_appkey": "ALIYUN_TTS_APPKEY",
    "tts_voice": "ALIYUN_TTS_VOICE",
    "tts_sample_rate": "ALIYUN_TTS_SAMPLE_RATE",
    "tts_format": "ALIYUN_TTS_FORMAT",
    "tts_timeout_sec": "ALIYUN_TTS_TIMEOUT_SEC",
    "tts_retry_attempts": "TTS_RETRY_ATTEMPTS",
}

# 需要脱敏的配置项（API Key 类）
SENSITIVE_KEYS = {"llm_api_key", "tts_api_key", "tts_appkey"}

# 需要转为 int 类型的配置项
INT_KEYS = {
    "llm_timeout_sec", "llm_retry_attempts",
    "tts_sample_rate", "tts_timeout_sec", "tts_retry_attempts",
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
        "base_url": "https://api.agnes-ai.com/v1",
        "model": "Agnes-2.0-Flash",
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
    "Agnes-2.0-Flash": {"input": 0.0, "output": 0.0},
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

    async def get_config_for_frontend(self) -> dict:
        """获取配置（前端展示用，API Key 脱敏）。

        返回结构：
        {
            "llm": {"api_key": "****xxxx", "base_url": "...", ...},
            "tts": {"api_key": "****xxxx", "voice": "...", ...},
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

        llm_config = {
            "api_key": _mask_key(_get("llm_api_key", "LLM_API_KEY")),
            "base_url": _get("llm_base_url", "LLM_BASE_URL"),
            "model": _get("llm_model", "LLM_MODEL"),
            "timeout_sec": int(_get("llm_timeout_sec", "LLM_TIMEOUT_SEC", "30")),
            "retry_attempts": int(_get("llm_retry_attempts", "LLM_RETRY_ATTEMPTS", "3")),
        }
        tts_config = {
            "api_key": _mask_key(_get("tts_api_key", "ALIYUN_TTS_API_KEY")),
            "appkey": _mask_key(_get("tts_appkey", "ALIYUN_TTS_APPKEY", "")),
            "voice": _get("tts_voice", "ALIYUN_TTS_VOICE"),
            "sample_rate": int(_get("tts_sample_rate", "ALIYUN_TTS_SAMPLE_RATE", "44100")),
            "format": _get("tts_format", "ALIYUN_TTS_FORMAT", "mp3"),
            "timeout_sec": int(_get("tts_timeout_sec", "ALIYUN_TTS_TIMEOUT_SEC", "60")),
            "retry_attempts": int(_get("tts_retry_attempts", "TTS_RETRY_ATTEMPTS", "3")),
        }

        return {"llm": llm_config, "tts": tts_config}

    # ---- 配置更新 ----

    async def update_config(self, llm_config: dict, tts_config: dict) -> None:
        """保存配置到 SQLite 并热更新 Settings 单例。

        API Key 脱敏值（****开头）视为未修改，跳过；
        空字符串视为清除 Key。
        """
        updates: dict[str, str] = {}

        for key, value in self._normalize_llm(llm_config).items():
            updates[key] = value
        for key, value in self._normalize_tts(tts_config).items():
            updates[key] = value

        if not updates:
            return

        # 写入 SQLite（upsert）
        for key, value in updates.items():
            await self._upsert_config(key, value)

        await self.db.commit()

        # 热更新 Settings 内存单例
        self._apply_to_settings(updates)

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
        return result

    def _normalize_tts(self, config: dict) -> dict[str, str]:
        """将前端 TTS 配置转为 config_key -> value 映射。"""
        result: dict[str, str] = {}
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
        self, api_key: str, appkey: str
    ) -> dict:
        """测试 TTS 连接（阿里云 NLS 鉴权验证）。

        发送最小化合成请求验证 token/appkey 有效性。
        不等待合成完成，仅检查创建任务是否成功。
        """
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

        endpoint = "https://nls-gateway.cn-shanghai.aliyuncs.com/rest/v1/tts/async"
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
        # 400 状态码下 error_code 更具诊断价值，统一解析后提示
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
            return {"success": True, "message": "TTS 鉴权成功"}
        if error_code in NLS_ERROR_HINTS:
            return {
                "success": False,
                "message": f"{error_msg}（{error_code}）— {NLS_ERROR_HINTS[error_code]}",
            }
        return {
            "success": False,
            "message": f"TTS 鉴权失败 error_code={error_code} msg={error_msg}",
        }

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

    def get_presets(self) -> list[dict]:
        """返回 LLM 提供商预设列表。"""
        return LLM_PRESETS

    def get_voices(self) -> list[dict]:
        """返回常用 TTS 音色列表。"""
        return [
            {"key": "xiaoyun", "label": "小芸（标准女声）"},
            {"key": "xiaoyi", "label": "小伊（温柔女声）"},
            {"key": "xiaoxiao", "label": "小晓（知性女声）"},
            {"key": "xiaomeng", "label": "小梦（甜美女声）"},
            {"key": "xiaowei", "label": "小维（沉稳男声）"},
            {"key": "aiya", "label": "艾雅（活泼女声）"},
        ]

