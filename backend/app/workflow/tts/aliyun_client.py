"""阿里云 TTS API 客户端（LLD 7.5）。

封装阿里云 NLS 长文本语音合成 HTTP 异步调用，统一异常类型供 tenacity 精准重试。

实现流程（按 NLS 异步长文本 RESTful API）：
1. POST 创建合成任务 → 返回 task_id
2. GET 轮询任务状态 → 直到 audio_address 可用
3. GET 下载音频二进制
"""
import asyncio
import logging
import os
import time
from typing import Optional

import httpx

from app.config import get_settings
from app.workflow.tts.base_provider import (
    TTSError,
    TTSRateLimitError,
    TTSTimeoutError,
    TTSServiceError,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class AliyunSpeechClient:
    """阿里云 NLS 长文本语音合成客户端。

    基于 NLS 异步长文本 RESTful API 实现，适合新闻播报这类分钟级长音频：
    创建任务 → 轮询状态 → 下载音频。鉴权使用 appkey + token。
    """

    # 异步长文本语音合成入口（创建与轮询共用同一 URL，按 HTTP 方法区分语义）
    ENDPOINT = "https://nls-gateway.cn-shanghai.aliyuncs.com/rest/v1/tts/async"
    # 轮询间隔：NLS 长文本合成为异步批处理，过密轮询浪费配额且无收益
    POLL_INTERVAL_SEC = 2

    def __init__(
        self,
        api_key: str,
        volume: Optional[int] = None,
        speech_rate: Optional[int] = None,
        pitch_rate: Optional[int] = None,
    ):
        # api_key 实为阿里云 NLS 访问令牌(token)，由 AccessKeyId/Secret 换取
        self._token = api_key
        # appkey 是 NLS 项目标识，与 token 不同；优先从 settings 读取，
        # 未定义则 fallback 到环境变量，保证调用方构造代码无需改动
        self._appkey = (
            getattr(settings, "ALIYUN_TTS_APPKEY", "")
            or os.environ.get("ALIYUN_TTS_APPKEY", "")
        )
        # 音量/语速/基频：显式参数优先，未传则回退到 settings 默认值
        # 试音时传入临时值，生产合成时用 settings 配置
        self._volume = volume if volume is not None else getattr(settings, "ALIYUN_TTS_VOLUME", 50)
        self._speech_rate = speech_rate if speech_rate is not None else getattr(settings, "ALIYUN_TTS_SPEECH_RATE", 0)
        self._pitch_rate = pitch_rate if pitch_rate is not None else getattr(settings, "ALIYUN_TTS_PITCH_RATE", 0)

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
        # 鉴权要素缺失时直接失败，避免发无效请求浪费连接
        if not self._token:
            raise TTSError("阿里云 TTS token 未配置（ALIYUN_TTS_API_KEY）")
        if not self._appkey:
            raise TTSError("阿里云 TTS appkey 未配置（ALIYUN_TTS_APPKEY）")

        voice = voice or settings.ALIYUN_TTS_VOICE
        # 单请求超时与轮询总超时共用同一配置，便于统一调参
        timeout = settings.ALIYUN_TTS_TIMEOUT_SEC

        # 复用同一 client 覆盖创建/轮询/下载三阶段，减少握手开销
        async with httpx.AsyncClient(timeout=timeout) as client:
            task_id, request_id = await self._create_task(
                client, text, voice, format, sample_rate
            )
            logger.info("阿里云 TTS 任务已创建 task_id=%s", task_id)

            audio_url = await self._poll_task(
                client, task_id, request_id, timeout
            )
            logger.info("阿里云 TTS 合成完成 task_id=%s", task_id)

            return await self._download_audio(client, audio_url)

    async def _create_task(
        self, client, text, voice, format, sample_rate
    ):
        """提交长文本合成任务，返回 (task_id, request_id)。"""
        # 请求体三段式结构遵循 NLS 规范：
        # header(鉴权) + context(设备标识) + payload(合成参数与回调配置)
        payload = {
            "header": {"appkey": self._appkey, "token": self._token},
            "context": {"device_id": "20_news_workflow"},
            "payload": {
                # 不启用回调，采用轮询模式，避免暴露公网回调地址
                "enable_notify": False,
                "notify_url": "",
                "tts_request": {
                    "voice": voice,
                    "sample_rate": sample_rate,
                    "format": format,
                    "enable_subtitle": False,
                    "text": text,
                    # 音量/语速/基频调节（NLS tts_request 可选参数）
                    "volume": self._volume,
                    "speech_rate": self._speech_rate,
                    "pitch_rate": self._pitch_rate,
                },
            },
        }
        headers = {"Content-Type": "application/json"}
        resp = await self._request(
            client, "POST", self.ENDPOINT, json=payload, headers=headers
        )
        data = resp.json()
        # NLS 约定 error_code == 20000000 表示请求被服务端接受
        error_code = data.get("error_code")
        if error_code != 20000000:
            raise TTSError(
                f"阿里云 TTS 创建任务失败 error_code={error_code} "
                f"msg={data.get('error_msg')}"
            )
        task_id = data.get("data", {}).get("task_id")
        request_id = data.get("request_id")
        if not task_id:
            raise TTSError(f"阿里云 TTS 创建任务未返回 task_id body={data}")
        return task_id, request_id

    async def _poll_task(self, client, task_id, request_id, timeout):  # NOSONAR
        """轮询任务状态直到合成完成，返回音频下载 URL。"""
        # 轮询 query 需带 appkey/token/task_id/request_id 四要素，
        # NLS 据此鉴权并定位任务
        params = {
            "appkey": self._appkey,
            "token": self._token,
            "task_id": task_id,
            "request_id": request_id or "",
        }
        # 用单调时钟计时，避免系统时间回拨导致超时判断异常
        deadline = time.monotonic() + timeout
        while True:
            if time.monotonic() > deadline:
                raise TTSTimeoutError(
                    f"阿里云 TTS 轮询超时 task_id={task_id} timeout={timeout}s"
                )
            resp = await self._request(
                client, "GET", self.ENDPOINT, params=params
            )
            data = resp.json()
            error_code = data.get("error_code")
            # audio_address 非空即合成完成，可直接下载
            audio_url = data.get("data", {}).get("audio_address")
            if audio_url:
                return audio_url
            # 非成功错误码（且非处理中的 20000000/None）→ 任务失败
            if error_code not in (20000000, None):
                raise TTSError(
                    f"阿里云 TTS 任务失败 task_id={task_id} "
                    f"error_code={error_code} msg={data.get('error_msg')}"
                )
            await asyncio.sleep(self.POLL_INTERVAL_SEC)

    async def _download_audio(self, client, audio_url):
        """从 audio_url 下载音频二进制。"""
        resp = await self._request(client, "GET", audio_url)
        return resp.content

    async def _request(self, client, method, url, **kwargs):
        """统一 HTTP 请求入口，将 httpx 异常映射为 TTS 异常层级。"""
        try:
            resp = await client.request(method, url, **kwargs)
        except httpx.TimeoutException as e:
            raise TTSTimeoutError(f"阿里云 TTS 请求超时: {e}") from e
        except httpx.RequestError as e:
            raise TTSServiceError(f"阿里云 TTS 连接异常: {e}") from e

        if resp.status_code == 429:
            raise TTSRateLimitError("阿里云 TTS 限流（429）")
        if resp.status_code >= 500:
            raise TTSServiceError(
                f"阿里云 TTS 服务异常 status={resp.status_code} "
                f"body={resp.text[:200]}"
            )
        if resp.status_code != 200:
            raise TTSError(
                f"阿里云 TTS 调用失败 status={resp.status_code} "
                f"body={resp.text[:200]}"
            )
        return resp
