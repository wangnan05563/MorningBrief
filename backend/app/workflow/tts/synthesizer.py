"""TTS 主入口（LLD 5.3 / 7.5）。

从 script 表读取 segments，并发合成 → 后处理 → 上传。
支持多 Provider 切换（阿里云/Edge-TTS/腾讯云），通过工厂模式按配置选择。
失败段跳过并告警，成功率 < 50% 视为整期失败。
"""
import asyncio
import logging
import random
import re
import time
import uuid

from sqlalchemy import select
# 从 attributes 子模块直接导入：sqlalchemy.orm.__init__ 在某些环境下未导出
# flag_modified（如本仓库测试 venv 的 SQLAlchemy 2.0.25），而 attributes 是定义所在模块，
# 两种环境均可正常导入，避免 ImportError 导致 synthesizer 模块无法加载。
from sqlalchemy.orm.attributes import flag_modified
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


async def _wait_for_tts_rate_limit_slot(timeout: float = 65) -> bool:  # NOSONAR
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
        # model 标签如实反映「provider:voice」，便于用量统计区分引擎与具体音色；
        # 交叉音色未启用或 provider 为单说话人模型时 voice 为 None，标 default。
        record_call(
            service_type="tts",
            model=f"{settings.TTS_PROVIDER}:{voice or 'default'}",
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


async def _persist_segment_audio_urls(
    script_id: int,
    audio_segments: list[dict],
    workflow_id: str,
    session=None,
) -> None:
    """把每段的 COS audio_url 写回 script.segments，按 seg_seq 匹配。

    COS 模式下本地 audio_cache/tts 目录为空，详情页 list_audio 接口回退读取
    script.segments[].audio_url 展示 TTS 片段；若此处不回写，分段无 audio_url，
    导致「语音合成 · TTS 片段」面板在 COS 模式（已配置 COS_BUCKET）下恒为空。
    本地模式下列表走本地目录不受影响，此处回写仅为补齐 COS 兜底的必要数据，
    并让每个分段对应的云端音频地址持久化，便于重生成/审核复用。

    session 为 None 时使用模块级 AsyncSessionLocal（生产路径）；
    传入 session 时复用（测试路径，便于隔离），调用方负责生命周期。
    回写失败仅告警、不抛异常，避免中断 TTS 主流程（音频已上传成功）。
    """
    if not audio_segments:
        return
    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()
    try:
        scr = (await session.execute(
            select(Script).where(Script.id == script_id)
        )).scalar_one_or_none()
        if scr is None:
            return
        segs = scr.segments or []
        url_by_seq = {a["seg_seq"]: a["audio_url"] for a in audio_segments}
        changed = False
        for seg in segs:
            u = url_by_seq.get(seg.get("seq"))
            if u:
                seg["audio_url"] = u
                changed = True
        if changed:
            scr.segments = segs
            # 就地修改 JSON 列表后若重新赋同一对象，SQLAlchemy 可能因身份未变而不标记脏，
            # 导致 UPDATE 不发出、audio_url 回写丢失（失败工作流常见）。强制标记脏确保落库。
            flag_modified(scr, "segments")
            await session.commit()
    except Exception:  # 回写失败为可选兜底，禁止中断 TTS 主流程；logger.exception 保留 traceback 便于排查
        logger.exception(
            "TTS audio_url 回写 script 失败 workflow_id=%s script_id=%s",
            workflow_id, script_id,
        )
    finally:
        if own_session:
            await session.close()


def assign_cross_voices(total: int, cfg: dict, provider: str) -> list:
    """根据交叉音色配置，为 total 个段落（按播放顺序编号 0..total-1）计算各自使用的音色 key。

    Returns:
        长度 = total 的列表，每个元素为音色 key（str）或 None（使用默认音色）。
        当未启用、或当前 provider 音色不足 2 个时，全部返回 None（保持原有单音色行为）。

    Args:
        total: 段落数
        cfg: 解析后的交叉音色配置（_parse_cross_voice 结果），结构见 ai_config_service._parse_cross_voice
        provider: 当前 TTS provider（edge/aliyun/tencent/kokoro/piper）
    """
    if not cfg or not cfg.get("enabled"):
        return [None] * total
    voices = (cfg.get("voices") or {}).get(provider) or []
    if len(voices) < 2:
        # 音色不足 2 个无法交替，回退默认音色（含 Piper 单说话人模型场景）
        return [None] * total
    strategy = cfg.get("strategy", "round_robin")
    interval = max(1, int(cfg.get("interval") or 1))
    n = len(voices)
    assigned: list = []
    prev = None
    for i in range(total):
        if strategy == "interval":
            idx = (i // interval) % n
        elif strategy == "random":
            # 随机但避免与上一段落同音色，提升交替感、避免相邻重复
            choices = [v for v in voices if v != prev] or voices
            chosen = random.choice(choices)
            prev = chosen
            assigned.append(chosen)
            continue
        else:  # round_robin（默认）
            idx = i % n
        assigned.append(voices[idx])
    return assigned


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

    # 按播放顺序（seg_seq）排序，保证交叉音色在真实播放顺序上交替
    segments = sorted(segments, key=lambda s: s.get("seq", 0))

    total = len(segments)
    logger.info("待合成分段 %d 段", total)

    # 交叉音色：按 provider + 策略为每段计算音色（禁用或不足 2 音色则全程默认音色）
    cross_cfg = None
    try:
        # 懒导入避免与 ai_config_service 的潜在循环依赖
        from app.services.ai_config_service import _parse_cross_voice
        cross_cfg = _parse_cross_voice(settings.TTS_CROSS_VOICE)
    except Exception:  # 解析失败不应阻断整期合成
        logger.exception("交叉音色配置解析失败，回退默认单音色")
        cross_cfg = None
    voice_plan = assign_cross_voices(total, cross_cfg, settings.TTS_PROVIDER)
    if any(voice_plan):
        logger.info(
            "交叉音色已启用 provider=%s 策略=%s 段落分配=%s",
            settings.TTS_PROVIDER, cross_cfg.get("strategy"), voice_plan,
        )

    # 2. 并发合成所有分段（return_exceptions 隔离单段失败，避免整批中断）
    tasks = [
        synthesize_segment(seg.get("content", ""), voice=voice_plan[i])
        for i, seg in enumerate(segments)
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

    # 4.5 回写 audio_url 到 script.segments（按 seg_seq 匹配），补齐 COS 模式详情页兜底数据
    if audio_segments:
        await _persist_segment_audio_urls(script_id, audio_segments, workflow_id)

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
