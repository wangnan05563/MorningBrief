"""TTS 主入口（LLD 5.3 / 7.5）。

从 script 表读取 segments，并发合成 → 后处理 → 上传。
支持多 Provider 切换（阿里云/Edge-TTS/腾讯云），通过工厂模式按配置选择。
失败段跳过并告警，成功率 < 50% 视为整期失败。
"""
import asyncio
import logging
import re
import time
import uuid

from sqlalchemy import select
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import get_settings
from app.core.ai_budget import check_budget, record_call
from app.database import AsyncSessionLocal
from app.models import Script
from app.workflow.tts.base_provider import (
    TTSError,
    TTSRateLimitError,
    TTSTimeoutError,
    TTSServiceError,
)
from app.workflow.tts.tts_factory import get_tts_provider
from app.workflow.tts.audio_postprocess import (
    normalize_loudness,
    trim_silence,
    get_audio_duration,
)
from app.workflow.tts.uploader import upload_to_cos

logger = logging.getLogger(__name__)
settings = get_settings()

# TTS 并发上限：与 LLM 模块对齐，避免瞬间打爆 TTS API 频率限制
# 阿里云 NLS / 腾讯云 TTS 均有 RPM 限制，10 段同时发起 + tenacity 重试会超限
_TTS_CONCURRENCY_LIMIT = 3
_tts_semaphore: asyncio.Semaphore | None = None


def _get_tts_semaphore() -> asyncio.Semaphore:
    """延迟初始化 TTS 信号量，避免在模块加载时创建事件循环依赖。"""
    global _tts_semaphore
    if _tts_semaphore is None:
        _tts_semaphore = asyncio.Semaphore(_TTS_CONCURRENCY_LIMIT)
    return _tts_semaphore


async def _wait_for_tts_rate_limit_slot(timeout: float = 65) -> bool:
    """等待 TTS 频率预算有空位（频率超限时的恢复策略）。

    与 LLM 模块的 _wait_for_rate_limit_slot 对齐：
    60s 滑动窗口内的旧记录会随时间过期，轮询 check_budget 直到通过或超时。
    避免 tenacity 短退避（1-2s）导致的"全部失败"连锁反应。

    Returns:
        True 如果等到空位；False 如果超时或遇到不可恢复的预算超限（token/费用）
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        allowed, reason = check_budget(service_type="tts")
        if allowed:
            return True
        if "频率超限" not in reason:
            # token/费用超限不可恢复，无需等待
            return False
        await asyncio.sleep(3)
    return False


# tenacity 重试装饰器（LLD 7.5）
# 异常类型从 base_provider 导入，保证所有 provider 抛出的可重试异常都能被识别
def _log_tts_retry(retry_state):
    """tenacity before_sleep 回调：重试前记录 warning 日志。

    替代 tenacity.before_sleep_log，因为后者依赖标准库 logging 接口，
    与项目其他模块使用的 loguru logger 不兼容，会导致日志格式不一致。
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    next_sleep = float(retry_state.next_sleep) if hasattr(retry_state, 'next_sleep') else 0
    logger.warning(
        "TTS 调用重试 attempt=%d wait=%.1fs exc=%s: %s",
        retry_state.attempt_number,
        next_sleep,
        type(exc).__name__ if exc else 'None',
        str(exc)[:200] if exc else '',
    )


tts_retry = retry(
    stop=stop_after_attempt(settings.TTS_RETRY_ATTEMPTS),
    wait=wait_exponential(min=1, max=10, multiplier=1),
    retry=retry_if_exception_type(
        (TTSRateLimitError, TTSTimeoutError, TTSServiceError)
    ),
    before_sleep=_log_tts_retry,
    reraise=True,
)


@tts_retry
async def synthesize_segment(text: str, voice: str = None) -> bytes:
    """合成单段文本（tenacity 自动重试可重试错误）。

    并发控制：通过 Semaphore 限制并发数为 3，避免瞬间打爆 TTS API 频率限制。
    频率超限时主动等待 60s 滑动窗口滑过，而非立即抛错（对齐 LLM 模块设计）。

    通过工厂获取当前配置的 TTS Provider 实例，上层无需感知具体厂商。
    预算控制：调用前检查三重预算（token/费用/频率），超限直接抛
    TTSRateLimitError 避免无效请求打到外部 API；调用成功后按字符数
    记录用量更新预算计数。
    """
    # 预算检查：超限时不发起请求（避免外部 API 计费）
    allowed, reason = check_budget(service_type="tts")
    if not allowed:
        if "频率超限" in reason:
            # 频率超限：等待 60s 滑动窗口滑过后重试，而非立即抛错
            # tenacity 短退避（1-2s）无法突破 60s 频率窗口，立即抛错会导致
            # 10 段并发全部失败（tenacity 3 次重试均在窗口内，全部被拦截）
            logger.warning("TTS 频率超限，等待滑动窗口滑过后重试: %s", reason)
            if not await _wait_for_tts_rate_limit_slot(timeout=65):
                raise TTSRateLimitError(f"AI 预算超限(不可重试): {reason}")
        else:
            # token/费用超限：不可恢复，立即失败
            logger.warning("AI 预算超限(不可重试)，跳过 TTS 调用: %s", reason)
            raise TTSRateLimitError(f"AI 预算超限(不可重试): {reason}")

    # Semaphore 并发控制：限制同时发起的 TTS 请求数
    sem = _get_tts_semaphore()
    async with sem:
        # 工厂模式：按 settings.TTS_PROVIDER 动态选择阿里云/Edge/腾讯云
        provider = get_tts_provider()
        audio = await provider.synthesize(
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


# 凭证脱敏正则：捕获组 1 为键名（token/secret/key/... + 分隔符），值为 \S+
# 替换时保留键名只抹去值，便于排查时定位是哪个凭证出错
_CREDS_PATTERN = re.compile(
    r"(?i)((?:token|secret|key|password|appkey)\s*[:=]\s*)\S+"
)


def _redact_credentials(text: str) -> str:
    """脱敏文本中的凭证信息，避免日志泄露 API Key。

    保留键名（token= / secret: 等）只抹去值，使日志仍能定位是哪个凭证出错。
    """
    return _CREDS_PATTERN.sub(
        lambda m: m.group(1) + "***",
        text,
    )


def _summarize_segment_failures(
    failures: list[tuple[int, str, Exception]],
) -> str:
    """汇总分段失败信息为可读字符串，用于日志和告警。

    Args:
        failures: [(seg_seq, stage, exception), ...]
            stage 为 "合成" 或 "后处理"，标识失败环节

    Returns:
        多行字符串，每行 "seq（stage）: ExceptionType: message"
        message 中的凭证信息已脱敏（token=xxx → token=***）
    """
    lines = []
    for seq, stage, exc in failures:
        msg = _redact_credentials(str(exc))
        lines.append(f"{seq}（{stage}）: {type(exc).__name__}: {msg}")
    return "\n".join(lines)


async def synthesize(workflow_id: str, script_id: int) -> dict:
    """TTS 主入口。

    Args:
        workflow_id: 工作流 ID（用于日志关联与上传 key 防覆盖）
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
    failures: list[tuple[int, str, Exception]] = []
    for seg, res in zip(segments, results):
        seq = seg.get("seq")
        if isinstance(res, Exception):
            # 合成阶段失败（重试耗尽），记录并跳过
            logger.warning("分段 %s 合成失败，跳过: %s", seq, res)
            failures.append((seq, "合成", res))
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
            failures.append((seq, "后处理", e))

    # 4. 成功率检查：< 50% 视为整期失败（用 success*2 < total 避免浮点）
    success = len(audio_segments)
    if success * 2 < total:
        summary = _summarize_segment_failures(failures)
        raise TTSError(
            f"TTS 成功率过低: {success}/{total}（< 50%）\n失败明细:\n{summary}"
        )

    # 5. 按 seg_seq 升序返回，便于后续按顺序拼接
    audio_segments.sort(key=lambda x: x["seg_seq"])

    # 失败段摘要写入日志（即使成功率达标，也便于排查零星失败）
    if failures:
        logger.warning(
            "TTS 部分段失败 workflow_id=%s\n%s",
            workflow_id,
            _summarize_segment_failures(failures),
        )

    logger.info(
        "TTS 完成 workflow_id=%s script_id=%s success=%d/%d",
        workflow_id, script_id, success, total,
    )

    return {"audio_segments": audio_segments}
