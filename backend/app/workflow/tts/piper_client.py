"""Piper TTS Provider（MIT 开源，本地离线轻量 TTS）。

基于 piper-tts PyPI 包（rhasspy/piper，MIT），完全本地离线运行，无需 API Key、
无网络、无字符上限。模型体积仅 40-100MB，CPU 实时因子（RTF）<0.2，是资源受限
设备（树莓派/低配服务器）上替代 Edge-TTS 的优质免费方案。

接入理由：
1. 完全免费、完全离线：模型本地加载，零运行成本，不依赖任何云服务
2. 极轻量：模型 40-100MB，CPU 推理快（RTF 常 <0.1），适合嵌入式/低配部署
3. 多语言：官方提供 40+ 语言语音模型（含 zh_CN-huayan-medium 中文女声）
4. 音质稳定：基于 VITS/HiFi-GAN，听感自然、延迟低，适合新闻播报

依赖（可选，仅启用本 provider 时需要）：
- piper-tts（pip install piper-tts）
- 语音模型文件（.onnx + .onnx.json）：python -m piper.download_voices zh_CN-huayan-medium

局限：
- 需要单独下载语音模型文件（不随包分发），路径通过 PIPER_VOICE_DIR 配置
- 音色表现力略逊于 Kokoro/Edge-TTS，但胜在轻便、可控、零外部依赖
"""
import asyncio
import io
import logging
import os
from typing import Optional

from app.config import get_settings
from app.workflow.tts.base_provider import (
    TTSError,
    TTSProvider,
    TTSProviderError,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class PiperProvider(TTSProvider):
    """Piper 本地离线 TTS 客户端。

    通过 piper.PiperVoice.load 加载本地模型，合成后写入内存 WAV 缓冲区返回。
    PiperVoice.load / synthesize 为同步 CPU 操作，用 asyncio.to_thread 包裹
    避免阻塞事件循环。
    """

    # 单次合成文本上限（Piper 对超长文本处理良好，但过长的单行仍建议分段）
    MAX_TEXT_LENGTH = 2000

    def __init__(
        self,
        voice: Optional[str] = None,
        voice_dir: Optional[str] = None,
        length_scale: Optional[float] = None,
        volume: Optional[float] = None,
        noise_scale: Optional[float] = None,
    ):
        """初始化 Piper provider。

        Args:
            voice: 语音模型名（如 zh_CN-huayan-medium），缺省读 settings.PIPER_VOICE
            voice_dir: 模型文件目录（含 {voice}.onnx + {voice}.onnx.json），
                缺省读 settings.PIPER_VOICE_DIR
            length_scale: 语速（>1 变慢，<1 变快），缺省读 settings.PIPER_LENGTH_SCALE
            volume: 音量 [0, 1]，缺省读 settings.PIPER_VOLUME
            noise_scale: 音色随机性，缺省读 settings.PIPER_NOISE_SCALE
        """
        try:
            from piper import PiperVoice  # noqa: F401
        except ImportError as e:
            raise TTSProviderError(
                "piper-tts 包未安装，请执行 pip install piper-tts "
                "（启用 Piper TTS 引擎时需要）"
            ) from e

        self._voice = voice or settings.PIPER_VOICE
        self._voice_dir = voice_dir or settings.PIPER_VOICE_DIR
        # 0 视为默认（1.0 / 0.5 / 0.667）
        self._length_scale = length_scale if length_scale not in (None, 0) else (
            settings.PIPER_LENGTH_SCALE or 1.0
        )
        self._volume = volume if volume not in (None, 0) else (
            settings.PIPER_VOLUME or 0.5
        )
        self._noise_scale = noise_scale if noise_scale is not None else (
            settings.PIPER_NOISE_SCALE or 0.667
        )

        self._PiperVoice = PiperVoice
        self._voice_model = None

    def _resolve_paths(self) -> tuple[str, Optional[str]]:
        """解析模型与配置路径，校验存在性。

        Returns:
            (model_path, config_path) —— config_path 不存在时返回 None（Piper 自动推断）

        Raises:
            TTSProviderError: 模型文件缺失（不可重试）
        """
        if not self._voice:
            raise TTSProviderError("Piper 语音模型名未配置（PIPER_VOICE）")
        base_dir = self._voice_dir or "."
        model_path = os.path.join(base_dir, f"{self._voice}.onnx")
        config_path = os.path.join(base_dir, f"{self._voice}.onnx.json")
        if not os.path.isfile(model_path):
            raise TTSProviderError(
                f"Piper 模型文件不存在: {model_path}，"
                "请先下载（python -m piper.download_voices <voice>）"
            )
        return model_path, (config_path if os.path.isfile(config_path) else None)

    def _ensure_model(self):
        """懒加载 PiperVoice 实例（模型加载较慢，单例化）。"""
        if self._voice_model is None:
            model_path, config_path = self._resolve_paths()
            self._voice_model = self._PiperVoice.load(
                model_path,
                config_path=config_path,
                use_cuda=False,
            )
            logger.info("Piper 模型已加载 voice=%s", self._voice)
        return self._voice_model

    def _synthesize_sync(self, text: str, voice: Optional[str]) -> bytes:
        """同步合成（在 to_thread 中调用）。"""
        # voice 参数在 Piper 中对应不同说话人（多说话人模型）；单说话人模型忽略
        _ = voice
        model = self._ensure_model()

        buf = io.BytesIO()
        import wave

        with wave.open(buf, "wb") as wf:
            model.synthesize(
                text,
                wf,
                length_scale=self._length_scale,
                volume=self._volume,
                noise_scale=self._noise_scale,
            )
        return buf.getvalue()

    async def synthesize(  # NOSONAR
        self,
        text: str,
        voice: Optional[str] = None,
        format: str = "mp3",
        sample_rate: int = 44100,
    ) -> bytes:
        """合成单段文本为 WAV 音频二进制。

        Piper 输出采样率由模型决定（中文 medium 为 22050Hz），format/sample_rate
        入参被忽略，由上游 audio_postprocess 统一重采样/转码为 44.1kHz mp3。

        Args:
            text: 待合成文本
            voice: 说话人标识（多说话人模型），缺省用默认
            format: 忽略（Piper 固定 WAV）
            sample_rate: 忽略（Piper 采样率由模型决定）

        Raises:
            TTSError: 文本为空或过长
            TTSProviderError: 依赖/模型文件缺失
            TTSServiceError: 合成失败
        """
        if not text.strip():
            raise TTSError("Piper 合成文本为空")

        if len(text) > self.MAX_TEXT_LENGTH:
            raise TTSError(
                f"Piper 单次合成文本过长: {len(text)} > {self.MAX_TEXT_LENGTH}"
            )

        try:
            audio = await asyncio.to_thread(
                self._synthesize_sync, text, voice
            )
        except TTSProviderError:
            raise
        except Exception as e:
            msg = str(e).lower()
            if "model" in msg or "onnx" in msg or "config" in msg:
                raise TTSProviderError(
                    f"Piper 模型加载失败: {e}"
                ) from e
            raise TTSServiceError(f"Piper 合成失败: {e}") from e

        if not audio or len(audio) < 44:  # 小于 WAV 头，视为无效
            raise TTSError("Piper 未返回有效音频数据")

        logger.debug(
            "Piper 合成成功 voice=%s chars=%d audio_bytes=%d",
            self._voice, len(text), len(audio),
        )
        return audio
