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
from datetime import date, datetime
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

# 选题数量：5-6 条新闻，覆盖主要品类又不超出单期时长
SELECT_TOP_N = 6
SELECT_MIN_N = 5
# 有效段数下限：少于 3 段无法构成一期节目
MIN_VALID_SEGMENTS = 3
# 播报语速（字/分钟），用于估算时长
WORDS_PER_MINUTE = 210

# 开场白与结尾（固定文案，约 30s 播报）
INTRO_TEXT = "各位听众早上好，欢迎收听今日要闻。"
OUTRO_TEXT = "以上就是今天的全部内容，感谢收听，明天见。"

# 第一层过滤：生成前 prompt 约束（写入 prompt 末尾，引导 LLM 主动规避）
PROMPT_CONSTRAINT = """
重要约束：
- 严禁出现以下类型词汇：政治敏感、暴力、色情、歧视性表达
- 严禁编造未经证实的信息
- 严禁出现具体人名负面评价
"""


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
    """改写流程整体失败的兜底异常。"""


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
_client = AsyncOpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
)


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
        resp = await _client.chat.completions.create(
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


def _build_prompt(material: dict, extra_constraint: str = None) -> str:
    """构建改写 prompt（读 rewrite.txt 模板，填入素材信息）。

    Args:
        material: 素材 dict，含 title/content/source/category/source_url
        extra_constraint: 额外约束（如敏感词命中后追加的规避要求）
    """
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        title=material["title"],
        content=material["content"],
        source=material["source"],
        category=material.get("category") or "未分类",
        source_url=material["url"],
    )
    # 第一层过滤：在 prompt 末尾追加敏感词规避约束，引导 LLM 主动避开
    if extra_constraint:
        prompt = prompt + "\n" + extra_constraint
    return prompt


async def _rewrite_one(material: dict, retry_with_constraint: bool = False) -> dict:
    """改写单条素材（LLD 7.3 双层过滤）。

    流程：
    1. 构建 prompt（首次无约束，二次追加 PROMPT_CONSTRAINT）
    2. 调用 LLM（tenacity 自动重试可重试错误）
    3. 解析 JSON 响应
    4. 敏感词检查：
       - 首次命中 → 抛 SensitiveHitError，由上层触发二次重生成
       - 二次仍命中 → 替换兜底（保证稿件可用，记录 warning）

    Args:
        material: 素材 dict
        retry_with_constraint: 是否为二次重生成（追加敏感词约束 prompt）

    Returns:
        {title, content, estimated_duration, source_url, material_id}
    """
    prompt = _build_prompt(
        material,
        extra_constraint=PROMPT_CONSTRAINT if retry_with_constraint else None,
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
    """按品类分组，每品类选 1-2 篇热度最高（LLD 5.3.2）。

    分组策略避免单品类霸占整期节目，保证内容多样性。
    """
    by_category = defaultdict(list)
    for m in materials:
        # category 可能为 None，统一归入"未分类"
        cat = m.get("category") or "未分类"
        by_category[cat].append(m)

    selected = []
    for cat, items in by_category.items():
        # 每品类按热度降序，取前 2 篇
        items.sort(key=lambda m: heat_score(m), reverse=True)
        selected.extend(items[:2])
        if len(selected) >= top_n:
            break
    return selected[:top_n]


def _assemble_script(segments: list[dict]) -> dict:
    """组装整稿（开场白 + 改写正文 + 结尾）。

    Args:
        segments: 改写后的分段列表 [{seq, title, content, ...}]

    Returns:
        {full_text, segments_json, total_words, estimated_duration}
    """
    # 开场白与结尾作为独立分段，便于 TTS 单独合成与时长控制
    intro_segment = {
        "seq": 1,
        "title": "开场白",
        "content": INTRO_TEXT,
        "start_sec": 0,
        "end_sec": 30,
        "material_ids": [],
    }

    body_segments = []
    # 正文段 seq 从 2 开始，衔接开场白
    current_sec = 30
    for idx, seg in enumerate(segments, start=2):
        duration = seg.get("estimated_duration", 90)
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

    outro_segment = {
        "seq": len(segments) + 2,
        "title": "结尾",
        "content": OUTRO_TEXT,
        "start_sec": current_sec,
        "end_sec": current_sec + 30,
        "material_ids": [],
    }

    all_segments = [intro_segment] + body_segments + [outro_segment]

    # 拼接完整稿件文本，用于全文检索与人工审阅
    full_text = "\n\n".join(s["content"] for s in all_segments)
    total_words = sum(len(s["content"]) for s in all_segments)
    # 按 210 字/分钟估算总时长
    estimated_duration = int(total_words / WORDS_PER_MINUTE * 60)

    return {
        "full_text": full_text,
        "segments_json": all_segments,
        "total_words": total_words,
        "estimated_duration": estimated_duration,
    }


async def _fetch_materials(date_str: str) -> list[dict]:
    """查询当日 pending 素材。

    按 crawled_at 当日筛选，避免历史积压素材混入当日节目。
    status=pending 确保不重复消费已被选题的素材。
    """
    async with AsyncSessionLocal() as session:
        # 当日 00:00 ~ 次日 00:00，覆盖完整一天的工作流产出
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


async def rewrite(workflow_id: str, date_str: str) -> dict:
    """改写主入口（LLD 5.3）。

    Args:
        workflow_id: 工作流 ID，用于关联稿件与回溯
        date_str: 日期字符串（如 "2026-07-08"），筛选当日素材

    Returns:
        {"script_id": N, "segments": 6, "total_words": 2100}

    Raises:
        LLMError: 有效改写段数 < 3，无法生成节目
    """
    logger.info("改写启动 workflow_id=%s date=%s", workflow_id, date_str)

    # 1. 拉取当日 pending 素材
    materials = await _fetch_materials(date_str)
    logger.info("当日 pending 素材 %d 条", len(materials))

    if not materials:
        raise LLMError(f"当日 {date_str} 无 pending 素材，无法改写")

    # 2. 选题：按品类分组，每品类选 1-2 篇热度最高
    selected = _select_top_materials(materials, top_n=SELECT_TOP_N)
    logger.info("选题 %d 条（按热度排序）", len(selected))

    # 3. 并发改写（5-6 条同时调用 LLM，return_exceptions 隔离单条失败）
    tasks = [_rewrite_one(m) for m in selected]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 4. 过滤失败项 + 敏感词扫描
    segments = []
    for m, r in zip(selected, results):
        if isinstance(r, SensitiveHitError):
            # 首次命中敏感词，带约束 prompt 二次重生成
            try:
                r = await _rewrite_one(m, retry_with_constraint=True)
                segments.append({**r, "seq": len(segments) + 1})
            except Exception as e:
                logger.warning("素材 %s 二次改写失败: %s", m["id"], e)
        elif isinstance(r, Exception):
            # 其他异常（LLM 调用失败、JSON 解析失败等）跳过该条
            logger.warning("素材 %s 改写失败: %s", m["id"], r)
        else:
            segments.append({**r, "seq": len(segments) + 1})

    if len(segments) < MIN_VALID_SEGMENTS:
        raise LLMError(
            f"有效改写段数 {len(segments)} < {MIN_VALID_SEGMENTS}，无法生成节目"
        )

    # 5. 组装整稿（开场白 + 改写段 + 结尾）
    assembled = _assemble_script(segments)

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
