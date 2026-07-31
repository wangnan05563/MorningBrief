"""腾讯云 TTS Provider（TextToVoice 基础语音合成）。

基于腾讯云云 API 3.0（TC3-HMAC-SHA256 签名）调用 TextToVoice 接口，
一次性返回 base64 编码的音频数据。

接入理由：
1. 项目已使用腾讯云 COS，SecretId/SecretKey 可复用，零新增云账号管理成本
2. 免费额度：精品音色 800 万字符（3 个月内，需控制台领取）
3. 101011（智燕）为精品新闻女声，专攻新闻播报场景
4. 完整 SSML + 多音色支持，与阿里云功能对等

限制：
- 单次请求最大 150 汉字（上层 synthesizer.py 已分段，此处兜底保护）
- 仅支持 8k/16k/24k 采样率（非支持值自动降级到 16k）
"""
import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import get_settings
from app.workflow.tts.base_provider import (
    TTSError,
    TTSProvider,
    TTSRateLimitError,
    TTSTimeoutError,
    TTSServiceError,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class TencentTTSProvider(TTSProvider):
    """腾讯云 TTS 基础语音合成客户端。

    通过云 API 3.0 调用 TextToVoice 接口，返回 base64 音频。
    签名算法 TC3-HMAC-SHA256 完整实现，无需腾讯云 SDK。

    音色（VoiceType）：
    - 101011: 智燕（新闻女声，精品音色，推荐新闻播报）
    - 101013: 智辉（新闻男声，精品音色）
    - 101021: 智瑞（新闻男声，精品音色）
    - 501001: 智兰（资讯女声，大模型音色，24k 采样率）
    - 101001: 智瑜（情感女声）
    - 101004: 智云（通用男声）
    """

    # API 固定参数
    ACTION = "TextToVoice"
    VERSION = "2019-08-23"
    SERVICE = "tts"
    # 单次合成文本上限（腾讯云限制 150 汉字，保守取 140 留余量）
    MAX_TEXT_LENGTH = 140
    # 腾讯云支持的采样率白名单
    SUPPORTED_SAMPLE_RATES = (8000, 16000, 24000)

    def __init__(
        self,
        secret_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: Optional[str] = None,
        voice_type: Optional[int] = None,
        volume: Optional[int] = None,
        speed: Optional[int] = None,
    ):
        """初始化腾讯云 TTS provider。

        凭证 fallback 链：显式参数 → settings.TENCENT_TTS_* → settings.COS_*
        （项目已用 COS，SecretId/SecretKey 可复用）

        Args:
            secret_id: 腾讯云 SecretId，留空读 settings
            secret_key: 腾讯云 SecretKey，留空读 settings
            region: 地域，留空读 settings
            voice_type: 音色 ID，留空读 settings
            volume: 音量 [-10, 10]，留空读 settings（试音时传入临时值）
            speed: 语速 [-2, 6]，留空读 settings（试音时传入临时值）
        """
        self._secret_id = (
            secret_id
            or settings.TENCENT_TTS_SECRET_ID
            or settings.COS_SECRET_ID
        )
        self._secret_key = (
            secret_key
            or settings.TENCENT_TTS_SECRET_KEY
            or settings.COS_SECRET_KEY
        )
        self._region = region or settings.TENCENT_TTS_REGION
        self._voice_type = voice_type or settings.TENCENT_TTS_VOICE_TYPE
        # 音量/语速：显式参数优先，未传则回退到 settings（试音时传入临时值）
        self._volume = volume if volume is not None else settings.TENCENT_TTS_VOLUME
        self._speed = speed if speed is not None else settings.TENCENT_TTS_SPEED
        # endpoint 与 host 从 settings 读取，避免硬编码
        # host 从 endpoint URL 派生（用 urllib 避免手写字符串拆分）
        from urllib.parse import urlparse
        self._endpoint = settings.TENCENT_TTS_ENDPOINT
        self._host = urlparse(self._endpoint).hostname or "tts.tencentcloudapi.com"

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        format: str = "mp3",
        sample_rate: int = 44100,
    ) -> bytes:
        """合成单段文本为音频二进制。

        腾讯云 TextToVoice 返回 base64 音频，解码后返回二进制。
        不支持的采样率自动降级到 16k；不支持的非 mp3 格式降级为 mp3。

        Args:
            text: 待合成文本（<= 140 汉字，超出由上层分段）
            voice: 音色 ID（数字字符串，如 "101011"），缺省用默认音色
            format: 输出格式（wav/mp3/pcm）
            sample_rate: 采样率（8k/16k/24k，其他值降级到 16k）

        Raises:
            TTSError: 文本为空/过长/凭证缺失
            TTSRateLimitError: 限流或免费额度用尽
            TTSTimeoutError: 超时
            TTSServiceError: 服务异常
        """
        if not self._secret_id or not self._secret_key:
            raise TTSError(
                "腾讯云 TTS 凭证未配置（TENCENT_TTS_SECRET_ID/SECRET_KEY "
                "或 COS_SECRET_ID/SECRET_KEY）"
            )

        if not text.strip():
            raise TTSError("腾讯云 TTS 合成文本为空")

        if len(text) > self.MAX_TEXT_LENGTH:
            raise TTSError(
                f"腾讯云 TTS 单次合成文本过长: {len(text)} > {self.MAX_TEXT_LENGTH}"
            )

        # 音色解析：字符串转 int，失败则用默认
        actual_voice = self._voice_type
        if voice:
            try:
                actual_voice = int(voice)
            except ValueError:
                logger.warning(
                    "腾讯云 TTS 音色 ID 无效 %s，使用默认 %s",
                    voice, self._voice_type,
                )

        # 采样率降级：腾讯云仅支持 8k/16k/24k
        if sample_rate not in self.SUPPORTED_SAMPLE_RATES:
            logger.debug(
                "腾讯云 TTS 不支持采样率 %d，降级到 16000", sample_rate,
            )
            sample_rate = 16000

        # 构造请求体
        payload = {
            "Text": text,
            "SessionId": f"MorningBrief-{uuid.uuid4().hex[:12]}",
            "ModelType": 1,
            "PrimaryLanguage": 1,  # 中文
            "VoiceType": actual_voice,
            "SampleRate": sample_rate,
            "Codec": format if format in ("mp3", "wav", "pcm") else "mp3",
            "Volume": self._volume,
            "Speed": self._speed,
        }

        # 签名 + 发送请求
        try:
            audio = await self._post_signed(payload)
        except httpx.TimeoutException as e:
            raise TTSTimeoutError(f"腾讯云 TTS 请求超时: {e}") from e
        except httpx.RequestError as e:
            raise TTSServiceError(f"腾讯云 TTS 连接异常: {e}") from e

        logger.debug(
            "腾讯云 TTS 合成成功 voice=%s chars=%d audio_bytes=%d",
            actual_voice, len(text), len(audio),
        )
        return audio

    async def _post_signed(self, payload: dict) -> bytes:
        """发送带 TC3-HMAC-SHA256 签名的 POST 请求，返回音频二进制。

        签名算法见 https://cloud.tencent.com/document/api/213/30654
        关键：请求体 JSON 字符串在签名和发送时必须字节一致，
        因此用 content= 而非 json=，避免 httpx 重新序列化。
        """
        # 序列化请求体（签名和发送共用此字符串）
        payload_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        payload_bytes = payload_str.encode("utf-8")

        # 计算签名
        timestamp = int(time.time())
        auth_header = self._build_auth_header(payload_bytes, timestamp)

        # 构造请求头（Content-Type 必须与签名时完全一致）
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json; charset=utf-8",
            "Host": self._host,
            "X-TC-Action": self.ACTION,
            "X-TC-Version": self.VERSION,
            "X-TC-Timestamp": str(timestamp),
        }
        if self._region:
            headers["X-TC-Region"] = self._region

        async with httpx.AsyncClient(timeout=settings.ALIYUN_TTS_TIMEOUT_SEC) as client:
            resp = await client.post(self._endpoint, content=payload_bytes, headers=headers)

        # 状态码异常映射
        if resp.status_code == 429:
            raise TTSRateLimitError("腾讯云 TTS 限流（429）")
        if resp.status_code >= 500:
            raise TTSServiceError(
                f"腾讯云 TTS 服务异常 status={resp.status_code} body={resp.text[:200]}"
            )
        if resp.status_code != 200:
            raise TTSError(
                f"腾讯云 TTS 调用失败 status={resp.status_code} body={resp.text[:200]}"
            )

        # 解析响应
        try:
            data = resp.json()
        except Exception as e:
            raise TTSError(f"腾讯云 TTS 响应解析失败: {e}") from e

        response = data.get("Response", {})

        # 错误处理
        if "Error" in response:
            err = response["Error"]
            code = err.get("Code", "")
            msg = err.get("Message", "")
            # 限流/额度用尽映射为可重试
            if "LimitExceeded" in code or "PkgExhausted" in code or "NoFreeAccount" in code:
                raise TTSRateLimitError(f"腾讯云 TTS {code}: {msg}")
            raise TTSError(f"腾讯云 TTS {code}: {msg}")

        # base64 解码音频
        audio_b64 = response.get("Audio")
        if not audio_b64:
            raise TTSError(
                f"腾讯云 TTS 响应无 Audio 字段 request_id={response.get('RequestId')}"
            )

        try:
            return base64.b64decode(audio_b64)
        except Exception as e:
            raise TTSError(f"腾讯云 TTS 音频 base64 解码失败: {e}") from e

    def _build_auth_header(self, payload_bytes: bytes, timestamp: int) -> str:
        """构造 TC3-HMAC-SHA256 Authorization 头。

        算法步骤：
        1. 拼接 CanonicalRequest（方法/URI/查询串/规范头/签名头/请求体哈希）
        2. 拼接 StringToSign（算法/时间戳/凭证范围/规范请求哈希）
        3. 派生签名密钥：SecretDate → SecretService → SecretSigning
        4. HMAC-SHA256 签名 StringToSign
        5. 拼接 Authorization 头
        """
        # 步骤 1：CanonicalRequest
        # POST 请求无 query string，URI 固定为 /
        canonical_uri = "/"
        canonical_querystring = ""

        # 规范头：key 小写，按 ASCII 升序
        content_type = "application/json; charset=utf-8"
        canonical_headers = (
            f"content-type:{content_type}\n"
            f"host:{self._host}\n"
            f"x-tc-action:{self.ACTION.lower()}\n"
        )
        signed_headers = "content-type;host;x-tc-action"

        # 请求体哈希
        hashed_payload = hashlib.sha256(payload_bytes).hexdigest()

        canonical_request = (
            f"POST\n{canonical_uri}\n{canonical_querystring}\n"
            f"{canonical_headers}\n{signed_headers}\n{hashed_payload}"
        )

        # 步骤 2：StringToSign
        # Date 必须从 timestamp 换算为 UTC+0 日期，不能加本地时区
        date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
        credential_scope = f"{date}/{self.SERVICE}/tc3_request"
        hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = (
            f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashed_canonical}"
        )

        # 步骤 3：派生签名密钥
        # HMAC 返回二进制，每层作为下一层的 key
        secret_date = hmac.new(
            ("TC3" + self._secret_key).encode("utf-8"),
            date.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        secret_service = hmac.new(
            secret_date, self.SERVICE.encode("utf-8"), hashlib.sha256
        ).digest()
        secret_signing = hmac.new(
            secret_service, b"tc3_request", hashlib.sha256
        ).digest()

        # 步骤 4：计算签名
        signature = hmac.new(
            secret_signing,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # 步骤 5：拼接 Authorization
        return (
            f"TC3-HMAC-SHA256 "
            f"Credential={self._secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

    async def test_connection(self) -> bool:
        """测试腾讯云 TTS 是否可用（合成一句测试文本）。"""
        if not self._secret_id or not self._secret_key:
            return False
        try:
            await self.synthesize("测试", format="mp3", sample_rate=16000)
            return True
        except Exception as e:
            logger.warning("腾讯云 TTS 连接测试失败: %s", e)
            return False
