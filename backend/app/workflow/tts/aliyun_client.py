"""阿里云 TTS API 客户端（LLD 7.5）。

封装阿里云 NLS 长文本语音合成 HTTP 调用，统一异常类型供 tenacity 精准重试。
注：当前为符合签名的占位实现，生产环境需按阿里云 NLS 文档补全签名与参数。
"""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ===== 异常定义 =====
# 异常分层便于 tenacity 精准判断是否重试：可重试错误继承 TTSError，
# 不可重试错误直接抛 TTSError，调用方按需处理
class TTSError(Exception):
    """TTS 流程兜底异常基类。"""


class TTSRateLimitError(TTSError):
    """API 限流（HTTP 429），退避后重试。"""


class TTSTimeoutError(TTSError):
    """请求超时，重试。"""


class TTSServiceError(TTSError):
    """服务端 5xx 或连接异常，重试。"""


class AliyunSpeechClient:
    """阿里云 NLS 语音合成客户端。

    占位实现：用 httpx 发起 POST 请求，签名与参数构造已简化。
    生产环境需按阿里云 NLS 文档补全：
    - API-KEY 鉴权签名（HMAC-SHA256）
    - 长文本合成任务创建/轮询流程（异步任务模式）
    - 音频格式参数（aformat / sampleRate / voice）
    """

    # 阿里云 NLS 长文本语音合成入口
    ENDPOINT = "https://nls-meta.cn-shanghai.aliyuncs.com/"

    def __init__(self, api_key: str):
        # 仅保存 api_key，httpx.AsyncClient 按请求创建避免连接池泄漏
        self._api_key = api_key

    async def synthesize(
        self,
        text: str,
        voice: str = None,
        format: str = "mp3",
        sample_rate: int = 44100,
    ) -> bytes:
        """合成单段文本为音频二进制。

        Args:
            text: 待合成文本（<= 1000 字，长文本需上层分段）
            voice: 音色 ID，缺省用 settings.ALIYUN_TTS_VOICE
            format: 输出格式（mp3/wav/pcm）
            sample_rate: 采样率

        Raises:
            TTSRateLimitError: 429
            TTSTimeoutError: 请求超时
            TTSServiceError: 5xx / 连接异常
            TTSError: 其他失败
        """
        voice = voice or settings.ALIYUN_TTS_VOICE
        # 占位请求体：真实环境需补 token、task_id、签名等字段
        payload = {
            "text": text,
            "voice": voice,
            "format": format,
            "sample_rate": sample_rate,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        timeout = settings.ALIYUN_TTS_TIMEOUT_SEC
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    self.ENDPOINT, json=payload, headers=headers
                )
        except httpx.TimeoutException as e:
            raise TTSTimeoutError(f"阿里云 TTS 请求超时: {e}") from e
        except httpx.RequestError as e:
            raise TTSServiceError(f"阿里云 TTS 连接异常: {e}") from e

        if resp.status_code == 429:
            raise TTSRateLimitError("阿里云 TTS 限流（429）")
        if resp.status_code >= 500:
            raise TTSServiceError(
                f"阿里云 TTS 服务异常 status={resp.status_code} body={resp.text[:200]}"
            )
        if resp.status_code != 200:
            raise TTSError(
                f"阿里云 TTS 调用失败 status={resp.status_code} body={resp.text[:200]}"
            )

        # 真实环境响应多为 JSON 包含音频下载 URL，这里假设直接返回二进制
        return resp.content
