"""LLM 改写模块：选题 → 并发改写 → 敏感词过滤 → 组装稿件（LLD 5.3 / 7.2 / 7.3 / 7.4）。

流程：
1. 从 SQLite material 表查询当日 pending 素材
2. 按热度（LLD 7.2）排序选 5-6 条
3. 并发改写（asyncio.gather），单条调用通义千问 API
4. 敏感词双层过滤（生成前 prompt 约束 + 生成后扫描，LLD 7.3）
5. 组装稿件（开场白 + 改写正文 + 结尾）
6. 存入 script 表
"""
import asyncio
import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from sqlalchemy import select

from app.config import get_settings
from app.core.ai_budget import check_budget, record_call
from app.database import AsyncSessionLocal
from app.models import Material, Script
from app.models.material import MaterialStatus
from app.models.script import ScriptStatus
from app.workflow.llm import sensitive_filter
from app.workflow.llm.heat_score import heat_score

logger = logging.getLogger(__name__)
settings = get_settings()

# Prompt 模板与敏感词表路径（与模块同级目录）
PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "rewrite.txt"
SENSITIVE_WORDS_PATH = Path(__file__).parent / "sensitive_words.txt"

# 模块加载时初始化敏感词自动机（避免每次改写重复加载）
sensitive_filter.load_words(str(SENSITIVE_WORDS_PATH))

# 选题数量：10 条新闻，覆盖主要品类又不超出单期时长
# 从 6 调整到 10：部分素材可能因敏感词/JSON 解析失败，增加候选提高成功率
# 最终组装稿件时仅使用成功段，不超过 MAX_SCRIPT_SEGMENTS 限制
SELECT_TOP_N = 10
SELECT_MIN_N = 5
# 有效段数下限：少于 3 段无法构成一期节目
MIN_VALID_SEGMENTS = 3
# 当日无 pending 素材时，向前回溯查询最近 N 天的 pending 素材
# 场景：RSS 源无新内容时爬虫去重导致当日采集 0 条，回溯避免工作流直接失败
FALLBACK_DAYS = 3
# 稿件最大段数：组装时仅取前 N 条成功段，避免段数过多导致节目超长
MAX_SCRIPT_SEGMENTS = 6
# 基础播报语速（字/分钟），对应阿里云 xiaoyun / Edge-TTS Xiaoxiao 等标准女声在 1.0 倍速下的实测值
# 注意：Edge-TTS 在 rate="" 时实际语速约 470 字/分（天然偏快），
# 但为统一估算口径，仍以 210 字/分为基准，倍率通过 _get_rate_multiplier() 校正
WORDS_PER_MINUTE = 210
# 默认目标节目时长（秒），与 settings.TARGET_DURATION_SEC 对齐
DEFAULT_TARGET_DURATION_SEC = 600

# 开场白与结尾（固定文案，约 150 字 ≈ 45s 播报）
# 扩充文案避免开场白/结尾过短导致实际 TTS 时长远低于预估
INTRO_TEXT = (
    "各位听众早上好，欢迎收听今日要闻。"
    "我是您的 AI 新闻主播，接下来为您播报今天最重要的新闻资讯。"
    "让我们一起了解今天发生了哪些值得关注的大事。"
)
OUTRO_TEXT = (
    "以上就是今天的全部内容，感谢您的收听。"
    "如果您觉得今天的节目对您有帮助，欢迎分享给身边的朋友。"
    "我们明天同一时间再会，祝您度过愉快的一天。"
)

# 第一层过滤：生成前 prompt 约束（写入 prompt 末尾，引导 LLM 主动规避）
PROMPT_CONSTRAINT = """
重要约束：
- 严禁出现以下类型词汇：政治敏感、暴力、色情、歧视性表达
- 严禁编造未经证实的信息
- 严禁出现具体人名负面评价
"""


# ===== 时长/字数/语速三参数联动 =====
# 数学关系：时长(秒) = 总字数 / (基础语速 × 语速倍率) × 60
# 反算：总字数 = 时长 × 基础语速 × 语速倍率 / 60
# 用户在 AI 配置页调整 target_duration_sec 或 edge_rate 时，
# rewriter 按此公式反算所需字数，动态调整每段 prompt 的字数要求
def _parse_edge_rate(rate_str: str) -> float:
    """解析 Edge-TTS rate 字符串为倍率。

    支持格式："+50%" / "-10%" / "+50" / "-10" / "50%" / ""
    返回 1.0 + percent/100，如 "+50%" → 1.5，"-10%" → 0.9
    倍率限制在 [0.5, 2.5] 避免极端值导致字数反算失真。
    """
    if not rate_str:
        return 1.0
    s = str(rate_str).strip().replace('%', '').replace('+', '')
    try:
        percent = float(s)
        return max(0.5, min(2.5, 1.0 + percent / 100.0))
    except ValueError:
        return 1.0


def _get_rate_multiplier() -> float:
    """获取当前 TTS Provider 的实际语速倍率。

    按 settings.TTS_PROVIDER 分支解析对应 provider 的语速字段：
    - edge: 解析 EDGE_TTS_RATE（如 "+50%" → 1.5）
    - tencent: TENCENT_TTS_SPEED（0=1.0, 2=1.2, -2=0.8 近似线性映射）
    - aliyun: 默认 1.0（阿里云 NLS 无语速调节字段）

    rewriter 用此倍率校正估算时长，stitch 用此倍率动态计算允许范围。
    """
    provider = (settings.TTS_PROVIDER or "aliyun").lower()
    if provider == "edge":
        return _parse_edge_rate(settings.EDGE_TTS_RATE)
    if provider == "tencent":
        # 腾讯云 speed: 0=默认, 正数加快, 负数减慢，近似每 +1 = +10%
        return max(0.5, min(2.5, 1.0 + settings.TENCENT_TTS_SPEED * 0.1))
    return 1.0


def _get_target_duration_sec() -> int:
    """读取目标节目时长（秒），fallback 到默认值 600。"""
    val = getattr(settings, "TARGET_DURATION_SEC", None)
    if val is None:
        return DEFAULT_TARGET_DURATION_SEC
    try:
        return max(180, min(1800, int(val)))
    except (ValueError, TypeError):
        return DEFAULT_TARGET_DURATION_SEC


def _calc_target_words(target_sec: int, rate_multiplier: float) -> int:
    """按目标时长 + 实际语速反算所需总字数。

    公式：总字数 = 时长(秒) × 基础语速(字/分) × 倍率 / 60
    例：600s × 210 × 1.5 / 60 = 3150 字（1.5 倍速下需更多字数填满时长）
    """
    return int(target_sec * WORDS_PER_MINUTE * rate_multiplier / 60)


def _calc_segment_words(target_sec: int, rate_multiplier: float) -> tuple[int, int]:
    """计算每段目标字数与段数。

    策略：
    1. 总字数 = 目标时长 × 基础语速 × 倍率 / 60
    2. 扣除开场白+结尾固定字数（约 145 字）= 正文总字数
    3. 段数 = clamp(round(正文总字数 / 350), 3, 6)
       - 350 字/段是经验值：基础语速下约 100s/段，节奏适中
    4. 每段字数 = 正文总字数 / 段数

    Returns:
        (segment_count, words_per_segment)
    """
    total_words = _calc_target_words(target_sec, rate_multiplier)
    intro_outro_words = len(INTRO_TEXT) + len(OUTRO_TEXT)
    body_words = max(300, total_words - intro_outro_words)

    # 段数动态调整：正文越长段数越多，但限制在 [3, 6]
    target_segments = max(MIN_VALID_SEGMENTS, min(MAX_SCRIPT_SEGMENTS, round(body_words / 350)))
    words_per_seg = max(200, int(body_words / target_segments))
    return target_segments, words_per_seg


# ===== 异常定义（LLD 7.4） =====
# 可重试错误：网络抖动 / 服务端临时问题，指数退避后大概率成功
class LLMRateLimitError(Exception):
    """API 限流（HTTP 429），退避后重试。"""


class LLMTimeoutError(Exception):
    """请求超时，重试。"""


class LLMServiceError(Exception):
    """服务端 5xx 或连接异常，重试。"""


# 不可重试错误：参数/鉴权/内容问题，重试无意义
class LLMAuthError(Exception):
    """鉴权失败（HTTP 401），立即失败并告警运维。"""


class LLMContentError(Exception):
    """内容审核拒绝，改用约束 prompt 重生成一次。"""


class SensitiveHitError(Exception):
    """首次生成命中敏感词，触发二次重生成。"""


class LLMError(Exception):
    """改写流程整体失败的兜底异常。

    携带 failure_details 属性时，包含每条素材的失败原因（供 workflow_step
    记录详细错误，便于前端详情页展示与运维定位）。
    """

    def __init__(self, message: str, failure_details: list[dict] | None = None):
        super().__init__(message)
        # failure_details 结构：[{material_id, title, stage, error_type, error_message}]
        # 仅在 rewrite() 中聚合并发失败时填充，单点失败场景为 None
        self.failure_details = failure_details


# tenacity 重试装饰器（LLD 7.4）
# - stop_after_attempt(3)：最多 3 次（含首次），总耗时上限可控
# - wait_exponential(1, 10)：1s, 2s, 4s... 退避上限 10s，避免雪崩压垮下游
# - retry_if_exception_type：仅可重试错误重试，不可重试错误立即抛出
# - reraise=True：重试耗尽后抛出原异常，保留错误上下文
llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10, multiplier=1),
    retry=retry_if_exception_type(
        (LLMRateLimitError, LLMTimeoutError, LLMServiceError)
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

# 通义千问兼容 OpenAI SDK，复用同一客户端连接池
# 延迟初始化：模块加载时 settings.LLM_API_KEY 可能仍是 .env 占位符，
# 前端通过 AIConfigService 热更新后才会注入真实 key。
# 若在此处固化 _client，前端配置的 Key 无法生效。
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """按需构建 OpenAI 客户端，每次读取最新 settings，兼容配置热更新。

    模块加载时 _client=None，首次调用 _call_llm 时才创建实例。
    若 settings.LLM_API_KEY 变更（前端配置或 .env 修改），
    下次调用会重建客户端，避免占位符固化导致 401。
    """
    global _client
    # 用 (api_key, base_url) 元组作为缓存键，配置变更时自动重建
    cache_key = (settings.LLM_API_KEY, settings.LLM_BASE_URL)
    if _client is None or getattr(_client, "_cache_key", None) != cache_key:
        _client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
        # 附加缓存键到实例，避免重建时丢失
        _client._cache_key = cache_key  # type: ignore[attr-defined]
    return _client


def _is_placeholder_api_key(key: str) -> bool:
    """检测 API key 是否为占位符或无效值。

    覆盖以下场景：
    - 空字符串或纯空白
    - .env.example 中的 <...> 占位符（含 < 或 >）
    - 含中文说明文本（真实 key 只含 ASCII 字符）

    提前拦截避免无效 key 浪费网络往返和重试配额（401 拒绝耗时虽短
    但会消耗 3 次重试 + 退避时间，且日志被笼统的"段数不足"掩盖）。
    """
    if not key or not key.strip():
        return True
    key = key.strip()
    # .env.example 占位符以 < 开头或 > 结尾
    if key.startswith("<") or key.endswith(">"):
        return True
    # 真实 API key 只含 ASCII 字符，含中文说明是未替换的占位符
    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        return True
    return False


@llm_retry
async def _call_llm(prompt: str) -> str:
    """调用通义千问 API（LLD 7.4 重试策略）。

    异常映射：
    - HTTP 429 RateLimitError → LLMRateLimitError（重试）
    - HTTP 401 AuthenticationError → LLMAuthError（不重试）
    - 超时 APITimeoutError → LLMTimeoutError（重试）
    - 连接异常 APIConnectionError → LLMServiceError（重试）
    - HTTP 5xx InternalServerError → LLMServiceError（重试）

    预算控制：调用前检查三重预算（token/费用/频率），超限直接抛 LLMAuthError
    避免无效请求打到外部 API；调用成功后记录用量更新预算计数。

    其他异常（含内容审核）不在此处映射，由调用方按不可重试处理。
    """
    # 预算检查：超限时不发起请求（避免外部 API 计费）
    allowed, reason = check_budget()
    if not allowed:
        logger.warning("AI 预算超限，跳过 LLM 调用: %s", reason)
        raise LLMServiceError(f"AI 预算超限: {reason}")

    try:
        resp = await _get_client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            timeout=settings.LLM_TIMEOUT_SEC,
        )
    except Exception as e:
        # 按异常类型映射，便于 tenacity 精准判断是否重试
        # 用类名字符串匹配，避免直接 import openai 异常类造成耦合
        type_name = type(e).__name__
        if type_name == "RateLimitError":
            raise LLMRateLimitError(str(e)) from e
        elif type_name == "AuthenticationError":
            raise LLMAuthError(str(e)) from e
        elif type_name == "APITimeoutError":
            raise LLMTimeoutError(str(e)) from e
        elif type_name in ("APIConnectionError", "InternalServerError"):
            raise LLMServiceError(str(e)) from e
        # 其他异常原样抛出，tenacity 不会重试（不在 retry_if_exception_type 列表）
        raise

    # 调用成功后记录用量（更新预算计数 + 持久化）
    usage = getattr(resp, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    record_call(
        service_type="llm",
        model=settings.LLM_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return resp.choices[0].message.content


def _build_prompt(
    material: dict,
    words_per_segment: int = 450,
    segment_duration: int = 60,
    extra_constraint: str = None,
    template_text: str = None,
) -> str:
    """构建改写 prompt（读 rewrite.txt 模板，填入素材信息 + 动态字数要求）。

    Args:
        material: 素材 dict，含 title/content/source/category/source_url
        words_per_segment: 每段目标字数（由目标时长 + 语速倍率反算得出）
        segment_duration: 每段预估时长（秒），供 LLM 输出 estimated_duration
        extra_constraint: 额外约束（如敏感词命中后追加的规避要求）
        template_text: 频道级自定义模板，为 None 则读默认 rewrite.txt
    """
    template = template_text if template_text else PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        title=material["title"],
        content=material["content"],
        source=material["source"],
        category=material.get("category") or "未分类",
        source_url=material["url"],
        words_per_segment=words_per_segment,
        segment_duration=segment_duration,
    )
    # 第一层过滤：在 prompt 末尾追加敏感词规避约束，引导 LLM 主动避开
    if extra_constraint:
        prompt = prompt + "\n" + extra_constraint
    return prompt


async def _rewrite_one(
    material: dict,
    words_per_segment: int = 450,
    segment_duration: int = 60,
    retry_with_constraint: bool = False,
    template_text: str = None,
    constraint_text: str = None,
) -> dict:
    """改写单条素材（LLD 7.3 双层过滤）。

    流程：
    1. 构建 prompt（首次无约束，二次追加 constraint）
    2. 调用 LLM（tenacity 自动重试可重试错误）
    3. 解析 JSON 响应
    4. 敏感词检查：
       - 首次命中 → 抛 SensitiveHitError，由上层触发二次重生成
       - 二次仍命中 → 替换兜底（保证稿件可用，记录 warning）

    Args:
        material: 素材 dict
        words_per_segment: 每段目标字数（动态注入 prompt）
        segment_duration: 每段预估时长（秒）
        retry_with_constraint: 是否为二次重生成（追加敏感词约束 prompt）
        template_text: 频道级自定义改写模板，None 则用默认 rewrite.txt
        constraint_text: 频道级敏感词约束，None 则用默认 PROMPT_CONSTRAINT

    Returns:
        {title, content, estimated_duration, source_url, material_id}
    """
    # 频道级约束优先，回退到默认 PROMPT_CONSTRAINT
    effective_constraint = constraint_text if constraint_text is not None else PROMPT_CONSTRAINT
    prompt = _build_prompt(
        material,
        words_per_segment=words_per_segment,
        segment_duration=segment_duration,
        extra_constraint=effective_constraint if retry_with_constraint else None,
        template_text=template_text,
    )
    raw = await _call_llm(prompt)

    # LLM 偶尔会输出 Markdown 代码块包裹，剥离后再解析
    text = raw.strip()
    if text.startswith("```"):
        # 去掉首尾 ``` 行，兼容 ```json 与 ``` 两种写法
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        # JSON 解析失败视为不可重试错误，记录原始响应便于排查
        logger.error(
            "LLM 响应 JSON 解析失败 material_id=%s raw=%s",
            material["id"],
            raw[:200],
        )
        raise LLMContentError(f"JSON 解析失败: {e}") from e

    # 第二层过滤：生成后词表扫描
    content = data.get("content", "")
    if sensitive_filter.contains(content):
        if retry_with_constraint:
            # 二次仍命中，替换兜底（不完美但保证可用）
            data["content"] = sensitive_filter.replace(content)
            logger.warning(
                "素材 %s 二次生成仍含敏感词，已替换",
                material["id"],
            )
        else:
            # 首次命中，抛异常触发上层二次重生成
            raise SensitiveHitError(
                f"素材 {material['id']} 首次生成命中敏感词"
            )

    return {
        "title": data.get("title", material["title"]),
        "content": data.get("content", ""),
        "estimated_duration": data.get("estimated_duration", 90),
        "source_url": data.get("source_url", material["url"]),
        "material_id": material["id"],
    }


def _select_top_materials(materials: list[dict], top_n: int = SELECT_TOP_N) -> list[dict]:
    """按品类分组选题，保证多样性与数量充足（LLD 5.3.2）。

    策略：
    1. 按品类分组，每品类按热度降序
    2. 轮询各品类取热度最高的 1 篇（第一轮保证品类覆盖）
    3. 若总量不足 top_n，第二轮从各品类补取次高热度的素材
    4. 单品类素材池很大时仍受 top_n 上限约束

    避免单一品类（如爬虫未分类导致全归"综合"）只能取 2 篇 < MIN_VALID_SEGMENTS 的缺陷。
    """
    by_category = defaultdict(list)
    for m in materials:
        cat = m.get("category") or "未分类"
        by_category[cat].append(m)

    # 每品类按热度降序
    for cat in by_category:
        by_category[cat].sort(key=lambda m: heat_score(m), reverse=True)

    selected = []
    # 第一轮：每个品类取 1 篇，保证品类覆盖
    cats = list(by_category.keys())
    for cat in cats:
        if by_category[cat]:
            selected.append(by_category[cat].pop(0))
        if len(selected) >= top_n:
            return selected[:top_n]

    # 第二轮：从剩余素材中按品类轮询补取，直到达到 top_n 或素材耗尽
    # 收集所有剩余素材，按热度全局排序后补足
    remaining = []
    for cat in cats:
        remaining.extend(by_category[cat])
    remaining.sort(key=lambda m: heat_score(m), reverse=True)
    for m in remaining:
        if len(selected) >= top_n:
            break
        selected.append(m)

    return selected[:top_n]


def _build_aggregated_error(segments: list[dict], failure_details: list[dict]) -> LLMError:
    """根据并发失败的 failure_details 聚合错误信息，构建 LLMError。

    策略：
    - 若同一 error_type 出现次数 >= 总失败数的 2/3，认为这是根因，
      错误消息中明确指出根因类型和示例，便于运维直接定位
      （例：6 条全部 LLMAuthError → 明确报鉴权失败而非"段数不足"）
    - 否则回退到笼统的"段数不足"消息，但附带 failure_details 供 workflow_step 展示

    始终把完整 failure_details 附加到 LLMError.failure_details 属性，
    供 workflow_scheduler._run_step 在 failed 状态下写入 workflow_step.result。
    """
    base_msg = (
        f"有效改写段数 {len(segments)} < {MIN_VALID_SEGMENTS}，无法生成节目"
    )

    if not failure_details:
        # 无单条素材失败（如素材总量不足选不够 top_n），构造诊断摘要写入 workflow_step.result
        # 否则 result 为 NULL，前端详情页无法展示失败原因
        return LLMError(base_msg, failure_details=[{
            "stage": "insufficient_segments",
            "error_type": "InsufficientSegments",
            "error_message": base_msg,
        }])

    # 统计 error_type 分布，识别主导错误
    from collections import Counter
    type_counter = Counter(d["error_type"] for d in failure_details)
    most_common_type, most_common_count = type_counter.most_common(1)[0]
    threshold = max(2, len(failure_details) * 2 // 3)

    if most_common_count >= threshold:
        # 同类型错误占主导：透传根因类型 + 代表性错误消息
        representative = next(
            d for d in failure_details if d["error_type"] == most_common_type
        )
        msg = (
            f"有效改写段数 {len(segments)} < {MIN_VALID_SEGMENTS}，"
            f"根因：{most_common_count}/{len(failure_details)} 条素材"
            f"因 {most_common_type} 失败"
            f"（示例: {representative['error_message'][:200]}）"
        )
    else:
        # 错误类型分散：保留笼统消息，详情见 failure_details
        type_summary = ", ".join(
            f"{t}={c}" for t, c in type_counter.most_common()
        )
        msg = f"{base_msg}（失败分布: {type_summary}）"

    return LLMError(msg, failure_details=failure_details)


def _assemble_script(
    segments: list[dict],
    rate_multiplier: float = 1.0,
    intro_text: str = None,
    outro_text: str = None,
) -> dict:
    """组装整稿（开场白 + 改写正文 + 结尾）。

    Args:
        segments: 改写后的分段列表 [{seq, title, content, ...}]
        rate_multiplier: TTS 实际语速倍率（如 1.5 = 1.5 倍速），
            用于校正估算时长，避免与实际 TTS 输出时长偏差过大
        intro_text: 频道级开场白，None 则用默认 INTRO_TEXT
        outro_text: 频道级结尾，None 则用默认 OUTRO_TEXT

    Returns:
        {full_text, segments_json, total_words, estimated_duration}
    """
    # 频道级文案优先，回退到默认 INTRO_TEXT/OUTRO_TEXT
    effective_intro = intro_text if intro_text else INTRO_TEXT
    effective_outro = outro_text if outro_text else OUTRO_TEXT

    # 实际播报速率 = 基础语速 × 倍率（如 210 × 1.5 = 315 字/分）
    actual_words_per_min = WORDS_PER_MINUTE * rate_multiplier

    # 开场白与结尾作为独立分段，便于 TTS 单独合成与时长控制
    # 时长按实际字数 + 实际语速估算
    intro_duration = int(len(effective_intro) / actual_words_per_min * 60)
    intro_segment = {
        "seq": 1,
        "title": "开场白",
        "content": effective_intro,
        "start_sec": 0,
        "end_sec": intro_duration,
        "material_ids": [],
    }

    body_segments = []
    # 正文段 seq 从 2 开始，衔接开场白
    current_sec = intro_duration
    for idx, seg in enumerate(segments, start=2):
        # 每段时长按实际字数 + 实际语速估算，避免 LLM 返回的 estimated_duration 不准
        seg_words = len(seg.get("content", ""))
        duration = int(seg_words / actual_words_per_min * 60) if seg_words else seg.get("estimated_duration", 90)
        body_segments.append(
            {
                "seq": idx,
                "title": seg["title"],
                "content": seg["content"],
                "start_sec": current_sec,
                "end_sec": current_sec + duration,
                "material_ids": [seg["material_id"]],
            }
        )
        current_sec += duration

    outro_duration = int(len(effective_outro) / actual_words_per_min * 60)
    outro_segment = {
        "seq": len(segments) + 2,
        "title": "结尾",
        "content": effective_outro,
        "start_sec": current_sec,
        "end_sec": current_sec + outro_duration,
        "material_ids": [],
    }

    all_segments = [intro_segment] + body_segments + [outro_segment]

    # 拼接完整稿件文本，用于全文检索与人工审阅
    full_text = "\n\n".join(s["content"] for s in all_segments)
    total_words = sum(len(s["content"]) for s in all_segments)
    # 总时长按实际语速估算，与 TTS 实际输出对齐
    estimated_duration = int(total_words / actual_words_per_min * 60)

    return {
        "full_text": full_text,
        "segments_json": all_segments,
        "total_words": total_words,
        "estimated_duration": estimated_duration,
    }


async def _fetch_materials(date_str: str) -> list[dict]:
    """查询当日 pending 素材，当日无素材时回溯最近 FALLBACK_DAYS 天。

    按 crawled_at 当日筛选，避免历史积压素材混入当日节目。
    status=pending 确保不重复消费已被选题的素材。
    当日爬虫去重可能导致 0 条新素材（RSS 源无新内容），回溯避免工作流直接失败。
    """
    async with AsyncSessionLocal() as session:
        day = date.fromisoformat(date_str)
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time())

        stmt = select(Material).where(
            Material.status == MaterialStatus.pending,
            Material.crawled_at >= start,
            Material.crawled_at <= end,
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        # 当日无 pending 素材时，回溯最近 FALLBACK_DAYS 天
        # 场景：RSS 源周末/夜间无更新，爬虫去重后当日 0 条新素材
        if not rows and FALLBACK_DAYS > 0:
            fb_start = datetime.combine(
                day - timedelta(days=FALLBACK_DAYS), datetime.min.time()
            )
            fb_stmt = select(Material).where(
                Material.status == MaterialStatus.pending,
                Material.crawled_at >= fb_start,
                Material.crawled_at <= end,
            ).order_by(Material.crawled_at.desc())
            fb_result = await session.execute(fb_stmt)
            rows = fb_result.scalars().all()
            if rows:
                logger.warning(
                    "当日 %s 无 pending 素材，回溯最近 %d 天获取 %d 条",
                    date_str, FALLBACK_DAYS, len(rows),
                )

        # ORM 对象转 dict，便于热度计算与并发传递
        # 注：schema 未含 source_authority 字段，heat_score 内部默认 0.5
        return [
            {
                "id": r.id,
                "source": r.source,
                "title": r.title,
                "content": r.content,
                "url": r.url,
                "published_at": r.published_at,
                "category": r.category,
                "workflow_id": r.workflow_id,
            }
            for r in rows
        ]


async def _fetch_channel_prompts(channel_id: int) -> dict:
    """查询频道级提示词。空值字段返回 None，由调用方回退默认值。

    Args:
        channel_id: 频道 ID

    Returns:
        {intro_prompt, outro_prompt, constraint_prompt, rewrite_template}
        频道不存在或字段为空时对应值为 None
    """
    from app.models import Channel
    async with AsyncSessionLocal() as session:
        ch = await session.get(Channel, channel_id)
        if ch is None:
            return {
                "intro_prompt": None,
                "outro_prompt": None,
                "constraint_prompt": None,
                "rewrite_template": None,
            }
        return {
            "intro_prompt": ch.intro_prompt,
            "outro_prompt": ch.outro_prompt,
            "constraint_prompt": ch.constraint_prompt,
            "rewrite_template": ch.rewrite_template,
        }


async def rewrite(workflow_id: str, date_str: str, channel_id: int = None) -> dict:
    """改写主入口（LLD 5.3）。

    整合目标时长 + TTS 实际语速，动态反算每段字数要求，注入 prompt。
    channel_id 非空时使用频道级提示词，空值字段回退默认值。

    Args:
        workflow_id: 工作流 ID，用于关联稿件与回溯
        date_str: 日期字符串（如 "2026-07-08"），筛选当日素材
        channel_id: 频道 ID，用于读取频道级提示词

    Returns:
        {"script_id": N, "segments": 6, "total_words": 2100}

    Raises:
        LLMError: 有效改写段数 < 3，无法生成节目
    """
    logger.info("改写启动 workflow_id=%s date=%s channel_id=%s", workflow_id, date_str, channel_id)

    # 0. 占位符前置检测：避免无效 API key 浪费重试配额
    # 若 .env 未替换占位符或前端未配置真实 key，立即抛出明确错误
    if _is_placeholder_api_key(settings.LLM_API_KEY):
        masked = settings.LLM_API_KEY[:8] + "***" if settings.LLM_API_KEY else "(空)"
        raise LLMError(
            f"LLM_API_KEY 未配置或仍为占位符（当前值: {masked}），"
            f"请在 .env 文件或前端 AI 配置页填入真实 API Key"
        )

    # 0.3 读取频道级提示词（channel_id 为空或字段为空时，回退默认值）
    channel_prompts = None
    if channel_id:
        channel_prompts = await _fetch_channel_prompts(channel_id)
        logger.info(
            "频道提示词 channel_id=%s intro=%s outro=%s template=%s",
            channel_id,
            bool(channel_prompts["intro_prompt"]),
            bool(channel_prompts["outro_prompt"]),
            bool(channel_prompts["rewrite_template"]),
        )

    # 0.5 读取目标时长 + TTS 语速倍率，反算每段目标字数
    # 数学关系：总字数 = 目标时长 × 基础语速 × 倍率 / 60
    # 用户调整目标时长或 TTS 语速时，自动协同调整稿件字数
    target_sec = _get_target_duration_sec()
    rate_multiplier = _get_rate_multiplier()
    target_segments, words_per_segment = _calc_segment_words(target_sec, rate_multiplier)
    segment_duration = int(words_per_segment / (WORDS_PER_MINUTE * rate_multiplier) * 60)
    logger.info(
        "时长/字数联动 target_sec=%d rate=%.2f 目标段数=%d 每段字数=%d 每段时长=%ds",
        target_sec, rate_multiplier, target_segments, words_per_segment, segment_duration,
    )

    # 1. 拉取当日 pending 素材
    materials = await _fetch_materials(date_str)
    logger.info("当日 pending 素材 %d 条", len(materials))

    if not materials:
        raise LLMError(f"当日 {date_str} 无 pending 素材，无法改写")

    # 2. 选题：按品类分组，每品类选 1-2 篇热度最高
    selected = _select_top_materials(materials, top_n=SELECT_TOP_N)
    logger.info("选题 %d 条（按热度排序）", len(selected))

    # 3. 并发改写（注入动态字数要求 + 频道级模板/约束，return_exceptions 隔离单条失败）
    tasks = [
        _rewrite_one(
            m,
            words_per_segment=words_per_segment,
            segment_duration=segment_duration,
            template_text=channel_prompts["rewrite_template"] if channel_prompts else None,
            constraint_text=channel_prompts["constraint_prompt"] if channel_prompts else None,
        )
        for m in selected
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 4. 过滤失败项 + 敏感词扫描
    segments = []
    failure_details: list[dict] = []  # 记录每条素材失败原因，供 workflow_step 展示
    for m, r in zip(selected, results):
        if isinstance(r, SensitiveHitError):
            # 首次命中敏感词，带约束 prompt 二次重生成
            try:
                r = await _rewrite_one(
                    m,
                    words_per_segment=words_per_segment,
                    segment_duration=segment_duration,
                    retry_with_constraint=True,
                    template_text=channel_prompts["rewrite_template"] if channel_prompts else None,
                    constraint_text=channel_prompts["constraint_prompt"] if channel_prompts else None,
                )
                segments.append({**r, "seq": len(segments) + 1})
            except Exception as e:
                logger.warning("素材 %s 二次改写失败: %s", m["id"], e)
                failure_details.append({
                    "material_id": m["id"],
                    "title": m["title"][:50],
                    "stage": "retry_with_constraint",
                    "error_type": type(e).__name__,
                    "error_message": str(e)[:300],
                })
        elif isinstance(r, Exception):
            # 其他异常（LLM 调用失败、JSON 解析失败等）跳过该条
            logger.warning("素材 %s 改写失败: %s", m["id"], r)
            failure_details.append({
                "material_id": m["id"],
                "title": m["title"][:50],
                "stage": "initial_rewrite",
                "error_type": type(r).__name__,
                "error_message": str(r)[:300],
            })
        else:
            segments.append({**r, "seq": len(segments) + 1})

    if len(segments) < MIN_VALID_SEGMENTS:
        # 错误聚合：若多数失败属同一类型，透传根因异常而非笼统报"段数不足"
        # 避免掩盖真实问题（如全部 LLMAuthError 应明确报鉴权失败）
        raise _build_aggregated_error(segments, failure_details)

    # 4.5 限制最终段数，避免选题数增加后节目时长过长
    # 按 target_segments 截取，避免段数超出目标时长对应的需求
    if len(segments) > target_segments:
        logger.info(
            "成功段数 %d 超过目标段数 %d，截取前 %d 段",
            len(segments), target_segments, target_segments,
        )
        segments = segments[:target_segments]

    # 5. 组装整稿（频道级开场白/结尾 + 改写段），用实际语速估算时长
    assembled = _assemble_script(
        segments,
        rate_multiplier=rate_multiplier,
        intro_text=channel_prompts["intro_prompt"] if channel_prompts else None,
        outro_text=channel_prompts["outro_prompt"] if channel_prompts else None,
    )

    # 6. 落库 script 表
    referenced_materials = [
        {"title": m["title"], "url": m["url"]} for m in selected
    ]
    categories = list({m.get("category") or "未分类" for m in selected})

    script = Script(
        workflow_id=workflow_id,
        episode_date=date.fromisoformat(date_str),
        full_text=assembled["full_text"],
        segments=assembled["segments_json"],
        total_words=assembled["total_words"],
        estimated_duration=assembled["estimated_duration"],
        referenced_materials=referenced_materials,
        categories=categories,
        status=ScriptStatus.draft,
    )
    async with AsyncSessionLocal() as session:
        async with session.begin():
            session.add(script)
            await session.flush()
            script_id = script.id

    logger.info(
        "改写完成 workflow_id=%s script_id=%s segments=%d total_words=%d",
        workflow_id,
        script_id,
        len(segments),
        assembled["total_words"],
    )

    return {
        "script_id": script_id,
        "segments": len(segments),
        "total_words": assembled["total_words"],
    }
