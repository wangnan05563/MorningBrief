"""TTS Provider 工厂与注册表。

按配置 TTS_PROVIDER 动态创建对应的 TTSProvider 实例，使上层 synthesizer.py
无需感知具体厂商实现。新增 provider 时只需：
1. 实现 TTSProvider 子类
2. 在 _PROVIDER_REGISTRY 注册 key → 工厂函数
3. 在 config.py / ai_config_service.py 增加对应配置项

设计要点：
- 延迟导入：各 provider 在 create_provider() 时才导入，避免未安装的依赖
  （如 edge-tts）影响其他 provider 加载
- 单例缓存：同一 provider 实例复用，避免每段重建连接
- 配置实时生效：每次 get_tts_provider() 读取最新 settings，支持前端热更新切换
"""
import logging
from typing import Optional

from app.config import get_settings
from app.workflow.tts.base_provider import (
    TTSProvider,
    TTSProviderError,
)

logger = logging.getLogger(__name__)

# Provider 实例缓存：key = provider 名，value = TTSProvider 实例
# 切换 provider 或修改配置时调用 invalidate() 清空缓存
_provider_cache: dict[str, TTSProvider] = {}


def _create_aliyun() -> "Union[TTSProvider, AliyunSpeechClient]":
    """创建阿里云 NLS TTS provider。"""
    from app.workflow.tts.aliyun_client import AliyunSpeechClient
    settings = get_settings()
    return AliyunSpeechClient(
        api_key=settings.ALIYUN_TTS_API_KEY,
        volume=settings.ALIYUN_TTS_VOLUME,
        speech_rate=settings.ALIYUN_TTS_SPEECH_RATE,
        pitch_rate=settings.ALIYUN_TTS_PITCH_RATE,
    )


def _create_edge() -> TTSProvider:
    """创建微软 Edge-TTS provider。"""
    from app.workflow.tts.edge_client import EdgeTTSProvider
    settings = get_settings()
    return EdgeTTSProvider(
        voice=settings.EDGE_TTS_VOICE,
        rate=settings.EDGE_TTS_RATE,
        volume=settings.EDGE_TTS_VOLUME,
        pitch=settings.EDGE_TTS_PITCH,
    )


def _create_tencent() -> TTSProvider:
    """创建腾讯云 TTS provider。

    凭证 fallback 链：TENCENT_TTS_SECRET_ID → COS_SECRET_ID
    （项目已用 COS，SecretId/SecretKey 可复用，零新增云账号成本）
    """
    from app.workflow.tts.tencent_client import TencentTTSProvider
    settings = get_settings()
    return TencentTTSProvider(
        secret_id=settings.TENCENT_TTS_SECRET_ID or settings.COS_SECRET_ID,
        secret_key=settings.TENCENT_TTS_SECRET_KEY or settings.COS_SECRET_KEY,
        region=settings.TENCENT_TTS_REGION,
        voice_type=settings.TENCENT_TTS_VOICE_TYPE,
    )


# Provider 注册表：key = 配置值，value = 工厂函数
# 新增 provider 时在此注册即可，无需修改 get_tts_provider 逻辑
_PROVIDER_REGISTRY = {
    "aliyun": _create_aliyun,
    "edge": _create_edge,
    "tencent": _create_tencent,
}


def get_tts_provider(provider: Optional[str] = None) -> TTSProvider:
    """获取 TTS provider 实例（带缓存）。

    Args:
        provider: provider 名称（aliyun/edge），缺省读 settings.TTS_PROVIDER

    Returns:
        TTSProvider 实例

    Raises:
        TTSProviderError: provider 未注册或依赖未安装
    """
    settings = get_settings()
    provider_name = provider or settings.TTS_PROVIDER

    if provider_name not in _PROVIDER_REGISTRY:
        raise TTSProviderError(
            f"未知的 TTS provider: {provider_name}，"
            f"已注册: {list(_PROVIDER_REGISTRY.keys())}"
        )

    # 命中缓存直接返回，避免重复创建
    if provider_name in _provider_cache:
        return _provider_cache[provider_name]

    try:
        instance = _PROVIDER_REGISTRY[provider_name]()
    except TTSProviderError:
        # 依赖未安装等配置错误，向上抛出
        raise
    except Exception as e:
        raise TTSProviderError(
            f"创建 TTS provider '{provider_name}' 失败: {e}"
        ) from e

    _provider_cache[provider_name] = instance
    logger.info("TTS provider 已创建: %s", provider_name)
    return instance


def invalidate() -> None:
    """清空 provider 缓存。

    前端切换 provider 或修改音色等配置后调用，使下次 get_tts_provider()
    重新创建实例读取最新配置。
    """
    _provider_cache.clear()
    logger.debug("TTS provider 缓存已清空")


def list_providers() -> list[str]:
    """返回已注册的 provider 名称列表。"""
    return list(_PROVIDER_REGISTRY.keys())
