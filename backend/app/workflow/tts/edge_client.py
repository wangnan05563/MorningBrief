"""微软 Edge-TTS Provider（免费降级方案）。

基于 edge-tts Python 库，调用 Edge 浏览器在线 TTS 接口（与 Azure 神经网络
音色同源）。完全免费、无字符上限、无需 API Key，适合作为阿里云 TTS 的
零成本降级方案。

接入理由：
1. 零成本零门槛：无字符上限、无 API Key、无注册流程
2. 音色质量与阿里云同源：均基于微软 Azure 神经网络音色
3. 纯 Python + asyncio，与项目 httpx/tenacity/async 技术栈无缝衔接
4. zh-CN-YunyangNeural（云扬）为业界公认的新闻播报男声标杆

风险提示：
- 非官方接口，理论上微软可随时封禁；建议作为降级而非唯一方案
- 需能访问 edge-tts WebSocket 服务（ss/proxy 环境下可能需配置代理）
"""
import asyncio
import logging
import os
from typing import Optional

from app.config import get_settings
from app.workflow.tts.base_provider import (
    TTSError,
    TTSProvider,
    TTSProviderError,
    TTSRateLimitError,
    TTSTimeoutError,
    TTSServiceError,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class EdgeTTSProvider(TTSProvider):
    """微软 Edge-TTS 客户端。

    通过 edge-tts 库调用 Edge 浏览器在线 TTS 接口，输出 MP3 音频。
    无需 API Key，开箱即用。

    音色示例（zh-CN-*）：
    - XiaoxiaoNeural: 晓晓（标准女声，与阿里云 xiaoyun 听感接近）
    - YunyangNeural:  云扬（新闻男声，业界新闻播报标杆）
    - XiaoyiNeural:   晓伊（温柔女声）
    - YunxiNeural:    云希（沉稳男声）
    """

    # Edge-TTS 单次合成文本上限（保守值，避免 WebSocket 帧过大）
    MAX_TEXT_LENGTH = 5000

    def __init__(
        self,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None,
        pitch: Optional[str] = None,
    ):
        """初始化 Edge-TTS provider。

        Args:
            voice: 默认音色 ID（如 zh-CN-XiaoxiaoNeural）
            rate: 语速调节（如 "+10%" 加快、"-10%" 减慢）
            volume: 音量调节（如 "+20%"、"-10%"）
            pitch: 基频调节（如 "+5Hz"、"-3Hz"）
        """
        # 延迟导入 edge_tts，避免未安装时影响其他 provider 加载
        try:
            import edge_tts  # noqa: F401
        except ImportError as e:
            raise TTSProviderError(
                "edge-tts 包未安装，请执行 pip install edge-tts"
            ) from e

        self._voice = voice or settings.EDGE_TTS_VOICE
        self._rate = rate or settings.EDGE_TTS_RATE
        self._volume = volume or settings.EDGE_TTS_VOLUME
        self._pitch = pitch or settings.EDGE_TTS_PITCH

    async def synthesize(  # NOSONAR
        self,
        text: str,
        voice: Optional[str] = None,
        format: str = "mp3",
        sample_rate: int = 44100,
    ) -> bytes:
        """合成单段文本为 MP3 音频二进制。

        Edge-TTS 仅支持 MP3 输出，format 参数非 mp3 时自动降级为 mp3
        （上层 audio_postprocess.py 通过 ffmpeg 统一处理后可按需转码）。

        Args:
            text: 待合成文本（<= 5000 字，超出由上层分段）
            voice: 音色 ID，缺省用默认音色
            format: 输出格式（Edge-TTS 仅支持 mp3，其他值降级为 mp3）
            sample_rate: 采样率（Edge-TTS 固定 24kHz，参数忽略）

        Raises:
            TTSError: 文本为空或过长
            TTSRateLimitError: Edge-TTS 返回 429
            TTSTimeoutError: 合成超时
            TTSServiceError: 连接异常或服务端错误
        """
        import edge_tts

        if not text.strip():
            raise TTSError("Edge-TTS 合成文本为空")

        if len(text) > self.MAX_TEXT_LENGTH:
            # 上层已分段，此处兜底防止超长文本导致 WebSocket 帧过大
            raise TTSError(
                f"Edge-TTS 单次合成文本过长: {len(text)} > {self.MAX_TEXT_LENGTH}"
            )

        actual_voice = voice or self._voice
        if not actual_voice:
            raise TTSError("Edge-TTS 音色未配置（EDGE_TTS_VOICE）")

        # 非 mp3 格式降级：Edge-TTS 仅输出 mp3，上层 ffmpeg 可转码
        if format.lower() != "mp3":
            logger.debug(
                "Edge-TTS 仅支持 mp3，格式 %s 降级为 mp3（上层 ffmpeg 可转码）",
                format,
            )

        # 构造合成参数：rate/volume/pitch 为空时不下发，避免 edge-tts 警告
        kwargs = {}
        if self._rate:
            kwargs["rate"] = self._rate
        if self._volume:
            kwargs["volume"] = self._volume
        if self._pitch:
            kwargs["pitch"] = self._pitch

        try:
            communicate = edge_tts.Communicate(text, actual_voice, **kwargs)
            # 流式收集音频块，避免大文件一次性占用内存
            chunks: list[bytes] = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
        except asyncio.TimeoutError as e:
            raise TTSTimeoutError(f"Edge-TTS 合成超时: {e}") from e
        except ConnectionError as e:
            raise TTSServiceError(f"Edge-TTS 连接异常: {e}") from e
        except Exception as e:
            # edge-tts 内部异常类型不固定，统一映射为 TTSError
            if e.__class__.__name__ == "NoAudioReceived":
                raise TTSServiceError(
                    "Edge-TTS 未收到音频数据，请检查网络、代理或稍后重试"
                ) from e
            msg = str(e).lower()
            if "429" in msg or "rate" in msg:
                raise TTSRateLimitError(f"Edge-TTS 限流: {e}") from e
            if "403" in msg:
                # 403 通常因 SSL 证书缺失或地区限制导致
                # 打包后 certifi CA 证书未收集是最常见原因
                raise TTSServiceError(
                    "Edge-TTS 连接被拒绝(403)，可能原因："
                    "1) SSL 证书缺失（打包后未包含 certifi CA 证书）；"
                    "2) 网络限制（需能访问 WebSocket 服务）；"
                    f"3) 音色配置无效。详情: {e}"
                ) from e
            if "timeout" in msg:
                raise TTSTimeoutError(f"Edge-TTS 超时: {e}") from e
            if "connection" in msg or "websocket" in msg:
                raise TTSServiceError(f"Edge-TTS 连接异常: {e}") from e
            raise TTSError(f"Edge-TTS 合成失败: {e}") from e

        if not chunks:
            raise TTSError("Edge-TTS 未返回音频数据（可能文本被过滤或音色无效）")

        audio = b"".join(chunks)
        logger.debug(
            "Edge-TTS 合成成功 voice=%s chars=%d audio_bytes=%d",
            actual_voice, len(text), len(audio),
        )
        return audio

    async def test_connection(self) -> bool:
        """测试 Edge-TTS 是否可用。

        合成一句短文本验证网络连通性与音色有效性。
        Edge-TTS 无鉴权概念，测试即实际合成。
        """
        try:
            # 先检查 SSL 证书是否可用（打包后常见问题）
            import certifi
            ca_path = certifi.where()
            if not os.path.isfile(ca_path):
                logger.warning(
                    "Edge-TTS SSL 证书缺失: %s 不存在，"
                    "打包后请确认 certifi 数据文件已收集",
                    ca_path,
                )

            await self.synthesize(
                "测试", voice=self._voice, format="mp3", sample_rate=16000
            )
            return True
        except Exception as e:
            logger.warning("Edge-TTS 连接测试失败: %s", e)
            return False
