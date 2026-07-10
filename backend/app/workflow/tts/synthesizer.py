"""TTS 主入口（LLD 5.3 / 7.5）。

从 script 表读取 segments，并发合成 → 后处理 → 上传 COS。
失败段跳过并告警，成功率 < 50% 视为整期失败。
"""
import asyncio
import logging
import uuid

from sqlalchemy import select
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.config import get_settings
from app.core.ai_budget import check_budget, record_call
from app.database import AsyncSessionLocal
from app.models import Script
from app.workflow.tts.aliyun_client import (
    AliyunSpeechClient,
    TTSError,
    TTSRateLimitError,
    TTSTimeoutError,
    TTSServiceError,
)
from app.workflow.tts.audio_postprocess import (
    normalize_loudness,
    trim_silence,
    get_audio_duration,
)
from app.workflow.tts.uploader import upload_to_cos

logger = logging.getLogger(__name__)
settings = get_settings()

# tenacity 重试装饰器（LLD 7.5）
# - stop_after_attempt(N): 最多 N 次（含首次），N 取自配置便于调参
# - wait_exponential(1, 10): 指数退避 1s 起、上限 10s，避免雪崩压垮下游
# - 仅限流/超时/5xx 重试，其他错误（鉴权/内容）立即抛出
# - reraise=True: 重试耗尽抛原异常，保留错误上下文
tts_retry = retry(
    stop=stop_after_attempt(settings.TTS_RETRY_ATTEMPTS),
    wait=wait_exponential(min=1, max=10, multiplier=1),
    retry=retry_if_exception_type(
        (TTSRateLimitError, TTSTimeoutError, TTSServiceError)
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

# 复用同一客户端实例，避免每段重建连接
_client = AliyunSpeechClient(settings.ALIYUN_TTS_API_KEY)


@tts_retry
async def synthesize_segment(text: str, voice: str = None) -> bytes:
    """合成单段文本（tenacity 自动重试可重试错误）。

    预算控制：调用前检查三重预算（token/费用/频率），超限直接抛 TTSRateLimitError
    避免无效请求打到外部 API；调用成功后按字符数记录用量更新预算计数。

    Args:
        text: 待合成文本
        voice: 音色 ID，缺省用配置默认值

    Returns:
        音频二进制
    """
    # 预算检查：超限时不发起请求（避免外部 API 计费）
    allowed, reason = check_budget()
    if not allowed:
        logger.warning("AI 预算超限，跳过 TTS 调用: %s", reason)
        raise TTSRateLimitError(f"AI 预算超限: {reason}")

    audio = await _client.synthesize(
        text,
        voice=voice,
        format=settings.ALIYUN_TTS_FORMAT,
        sample_rate=settings.ALIYUN_TTS_SAMPLE_RATE,
    )

    # 调用成功后记录用量（按字符数计费）
    record_call(
        service_type="tts",
        model=settings.ALIYUN_TTS_VOICE,
        char_count=len(text),
    )

    return audio


async def synthesize(workflow_id: str, script_id: int) -> dict:
    """TTS 主入口。

    Args:
        workflow_id: 工作流 ID（用于日志关联与 COS key 防覆盖）
        script_id: 稿件 ID

    Returns:
        {"audio_segments": [{"seg_seq": N, "audio_url": "...", "duration": N}]}

    Raises:
        TTSError: 稿件不存在/无分段，或成功率 < 50%
    """
    logger.info("TTS 启动 workflow_id=%s script_id=%s", workflow_id, script_id)

    # 1. 读取 script segments（JSON 字段，结构见 Script 模型注释）
    async with AsyncSessionLocal() as session:
        stmt = select(Script).where(Script.id == script_id)
        result = await session.execute(stmt)
        script = result.scalar_one_or_none()
        if script is None:
            raise TTSError(f"稿件不存在 script_id={script_id}")
        segments = script.segments or []

    if not segments:
        raise TTSError(f"稿件无分段 script_id={script_id}")

    total = len(segments)
    logger.info("待合成分段 %d 段", total)

    # 2. 并发合成所有分段（return_exceptions 隔离单段失败，避免整批中断）
    tasks = [
        synthesize_segment(seg.get("content", ""), voice=None)
        for seg in segments
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 3. 后处理 + 上传，逐段 try 跳过失败
    audio_segments: list[dict] = []
    for seg, res in zip(segments, results):
        seq = seg.get("seq")
        if isinstance(res, Exception):
            # 合成阶段失败（重试耗尽），跳过并告警
            logger.warning("分段 %s 合成失败，跳过: %s", seq, res)
            continue
        try:
            # 顺序：归一化 → 去静音 → 探测时长 → 上传
            audio = await normalize_loudness(res)
            audio = await trim_silence(audio)
            duration = await get_audio_duration(audio)
            # key 含 workflow_id + uuid，防止不同期/同段覆盖
            key = f"tts/{workflow_id}/{seq}_{uuid.uuid4().hex[:8]}.mp3"
            url = await upload_to_cos(audio, key)
            audio_segments.append(
                {"seg_seq": seq, "audio_url": url, "duration": duration}
            )
        except Exception as e:
            logger.warning("分段 %s 后处理/上传失败，跳过: %s", seq, e)

    # 4. 成功率检查：< 50% 视为整期失败（用 success*2 < total 避免浮点）
    success = len(audio_segments)
    if success * 2 < total:
        raise TTSError(
            f"TTS 成功率过低: {success}/{total}（< 50%）"
        )

    # 5. 按 seg_seq 升序返回，便于后续按顺序拼接
    audio_segments.sort(key=lambda x: x["seg_seq"])

    logger.info(
        "TTS 完成 workflow_id=%s script_id=%s success=%d/%d",
        workflow_id, script_id, success, total,
    )

    return {"audio_segments": audio_segments}
