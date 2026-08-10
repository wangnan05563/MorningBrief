"""Kokoro TTS Provider（Apache 2.0 开源，本地离线神经网络 TTS）。

基于 kokoro PyPI 包（hexgrad/Kokoro-82M，82M 参数，Apache 2.0），完全本地
离线运行，无需 API Key、无网络、无字符上限，质量与 Edge-TTS 同源或更高，
且支持多语言（中文普通话 lang_code='z' 需 pip install misaki[zh]）。

接入理由：
1. 完全免费、完全离线：模型权重本地加载，不依赖任何云服务，零运行成本
2. 音质对标/超越 Edge-TTS：82M 参数神经网络，中文音色自然度优于多数免费方案
3. 多语言：内置美/英/西/法/意/日/葡/中 等语言族，适合多语种新闻播报
4. 轻量：纯 CPU 推理（onnxruntime/torch），单段合成毫秒级，资源占用低

依赖（可选，仅启用本 provider 时需要）：
- kokoro>=0.9.4
- misaki[zh]（中文 G2P，首次使用需联网下载模型权重 ~165MB，之后离线）
- espeak-ng（misaki 底层 phonemizer，Windows 需手动安装）

局限：
- 单次合成建议 <= ~400 token（约 200 字），过长会导致语速偏快；上层 synthesizer
  已按段落分段，此处仅兜底
- lang_code 与 voice 必须匹配（如 'z' 配 zf_*/zm_*，'a' 配 af_*/am_*）
"""
import io
import logging
import wave
from typing import Optional

from app.config import get_settings
from app.workflow.tts.base_provider import (
    TTSError,
    TTSProvider,
    TTSProviderError,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Kokoro 输出采样率固定 24kHz（模型决定，与 format/sample_rate 入参无关）
_KOKORO_SAMPLE_RATE = 24000


class KokoroProvider(TTSProvider):
    """Kokoro 本地离线 TTS 客户端。

    通过 kokoro.KPipeline 加载本地模型权重合成音频，返回 WAV 字节
    （24kHz 单声道 16bit）。合成结果交由 audio_postprocess 统一做响度归一化 /
    去静音 / 转码为 44.1kHz mp3，因此本 provider 固定输出 WAV。
    """

    # 单次合成文本上限（token 维度保守值，避免语音 rushed）
    MAX_TEXT_LENGTH = 400

    # 各语言默认音色（新闻播报场景优选女声/男声标杆）
    DEFAULT_VOICE_BY_LANG = {
        "a": "af_heart",     # 美式英语
        "b": "bf_emma",      # 英式英语
        "e": "ef_dora",      # 西班牙语
        "f": "ff_siwis",     # 法语
        "h": "hf_alpha",     # 印地语
        "i": "if_sara",      # 意大利语
        "j": "jf_alpha",     # 日语
        "p": "pf_dora",      # 巴西葡萄牙语
        "z": "zf_xiaoxiao",  # 中文普通话（成熟稳重·新闻播报）
    }

    def __init__(
        self,
        lang: Optional[str] = None,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ):
        """初始化 Kokoro provider。

        Args:
            lang: 语言代码（'z' 中文 / 'a' 美式 / 'b' 英式 等），缺省读 settings.KOKORO_LANG
            voice: 音色 ID（如 zf_xiaoxiao），缺省读 settings.KOKORO_VOICE 或语言默认
            speed: 语速倍率（>1 加快，<1 减慢），缺省读 settings.KOKORO_SPEED
        """
        try:
            from kokoro import KPipeline  # noqa: F401
        except ImportError as e:
            raise TTSProviderError(
                "kokoro 包未安装，请执行 pip install kokoro misaki[zh] "
                "（启用 Kokoro TTS 引擎时需要）"
            ) from e

        self._lang = lang or settings.KOKORO_LANG
        self._voice = (
            voice
            or settings.KOKORO_VOICE
            or self.DEFAULT_VOICE_BY_LANG.get(self._lang, "af_heart")
        )
        # speed 为 0 或 None 时视为默认 1.0（避免把 0 误当作静音）
        self._speed = speed if speed not in (None, 0) else (
            settings.KOKORO_SPEED or 1.0
        )

        # 延迟到首次 synthesize 才真正加载模型（模型权重首次下载/加载较慢，
        # 且单例化避免每次合成重建）。此处仅保存类引用。
        self._KPipeline = KPipeline
        self._pipeline = None

    def _ensure_pipeline(self):
        """懒加载 KPipeline 实例（线程安全由调用方单线程保证）。"""
        if self._pipeline is None:
            # lang_code 不匹配会触发 kokoro 内部错误，提前校验
            if not self._lang:
                raise TTSProviderError("Kokoro lang_code 未配置（KOKORO_LANG）")
            self._pipeline = self._KPipeline(lang_code=self._lang)
            logger.info(
                "Kokoro 模型已加载 lang=%s voice=%s", self._lang, self._voice,
            )
        return self._pipeline

    @staticmethod
    def _to_wav_bytes(audio) -> bytes:
        """将 Kokoro 输出的 float32 音频（24kHz 单声道）转为 16bit PCM WAV 字节。

        Kokoro 返回 numpy float32 数组（部分版本为 torch.Tensor），
        统一转 numpy 后量化到 int16，再用 wave 写入内存缓冲区。
        """
        import numpy as np

        # torch.Tensor 或其他类数组 → numpy
        if not isinstance(audio, np.ndarray):
            try:
                audio = np.asarray(audio)
            except Exception as e:
                raise TTSError(f"Kokoro 音频格式无法解析: {e}") from e

        # 单声道：确保 shape 为 (n,) 或 (n, 1)
        if audio.ndim > 1:
            audio = audio.reshape(-1)

        # float32 [-1, 1] → int16
        clipped = np.clip(audio, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype("<i2")

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(_KOKORO_SAMPLE_RATE)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    async def synthesize(  # NOSONAR
        self,
        text: str,
        voice: Optional[str] = None,
        format: str = "mp3",
        sample_rate: int = 44100,
    ) -> bytes:
        """合成单段文本为 WAV 音频二进制（24kHz 单声道）。

        Kokoro 仅输出 24kHz 单声道 WAV；format/sample_rate 入参被忽略，
        由上游 audio_postprocess 统一重采样/转码为 44.1kHz mp3。

        Args:
            text: 待合成文本（建议 <= 400 字，超出由上层分段）
            voice: 音色 ID，缺省用默认音色
            format: 忽略（Kokoro 固定 WAV）
            sample_rate: 忽略（Kokoro 固定 24kHz）

        Raises:
            TTSError: 文本为空或过长
            TTSProviderError: 依赖未安装
            TTSServiceError: 合成失败（模型/音色不匹配等）
        """
        if not text.strip():
            raise TTSError("Kokoro 合成文本为空")

        if len(text) > self.MAX_TEXT_LENGTH:
            raise TTSError(
                f"Kokoro 单次合成文本过长: {len(text)} > {self.MAX_TEXT_LENGTH}，"
                "请交由上层分段"
            )

        actual_voice = voice or self._voice
        if not actual_voice:
            raise TTSError("Kokoro 音色未配置（KOKORO_VOICE）")

        try:
            pipeline = self._ensure_pipeline()
            # KPipeline 返回生成器：(graphemes, phonemes, audio) 元组列表
            # 长文本会被内部按 split_pattern 切分，需聚合所有片段
            import numpy as np

            chunks: list[np.ndarray] = []
            for _gs, _ps, audio in pipeline(
                text, voice=actual_voice, speed=self._speed
            ):
                if audio is None:
                    continue
                arr = audio if isinstance(audio, np.ndarray) else np.asarray(audio)
                chunks.append(arr.reshape(-1))
        except TTSProviderError:
            raise
        except Exception as e:
            msg = str(e).lower()
            if "voice" in msg or "lang" in msg or "model" in msg:
                raise TTSServiceError(
                    f"Kokoro 模型/音色加载失败（lang={self._lang} voice={actual_voice}）: {e}"
                ) from e
            raise TTSServiceError(f"Kokoro 合成失败: {e}") from e

        if not chunks:
            raise TTSError("Kokoro 未返回音频数据（可能文本被过滤或音色无效）")

        merged = np.concatenate(chunks)
        audio = self._to_wav_bytes(merged)

        logger.debug(
            "Kokoro 合成成功 lang=%s voice=%s chars=%d audio_bytes=%d",
            self._lang, actual_voice, len(text), len(audio),
        )
        return audio
