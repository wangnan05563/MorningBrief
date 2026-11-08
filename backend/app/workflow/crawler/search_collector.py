"""全网搜索素材采集编排（T04116）。

把「网络检索」与「频道上下文」汇合，产出与 RSS 素材同构的 prepared dict，
交给 runner 统一入库（channel_id / workflow_id / status 语义完全一致）：

1. 按 `search_prompt` 解析主题 / 子板块 / 中英文关键词；
2. 三轮检索：中文关键词 → 英文关键词 → 对头部候选交叉验证；
3. 与频道上一期节目稿件（Episode → Script.segments 标题）比对：同源事件默认丢弃，
   带进展词的以「新增进展」保留；
4. 密度不足（文本量撑不起目标语音时长）时按子板块补搜；
5. 交叉验证未通过的候选标注「据媒体报道」。

未启用 / 缺凭据时**不发起任何网络请求**，只回传关闭原因，采集行为与接入前一致。
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from typing import Optional

from sqlalchemy import select

from app.config import get_settings
from app.core.simhash import compute, is_similar
from app.core.timeutil import localnow_naive
from app.database import AsyncSessionLocal
from app.models import Channel, Episode, Script
from app.models.episode import EpisodeStatus
from app.workflow.crawler.article_parser import extract as extract_article
from app.workflow.crawler.web_search import (
    CROSS_SIMILARITY,
    MIN_SNIPPET_CHARS,
    SearchResult,
    build_density_queries,
    build_provider,
    build_round_queries,
    classify_candidate,
    mark_unverified,
    merge_results,
    normalize_url,
    parse_search_prompt,
)
from app.workflow.duration import resolve_channel_min_duration_sec

logger = logging.getLogger(__name__)

# 正文短于该长度视为「搜索摘要无检索价值」，不入库（避免空壳素材挤占选题池）
MIN_CONTENT_CHARS = 40

# 全部轮次合计的检索次数硬上限（防止提示词异常导致请求失控）
DEFAULT_MAX_QUERIES_TOTAL = 12


@dataclass
class _ChannelContext:
    prompt: str
    channel_type: Optional[str]
    min_duration_sec: Optional[int]
    previous_topics: list[str]


def _closed(enabled: bool, reason: str) -> dict:
    return {"enabled": enabled, "reason": reason, "materials": []}


def _disabled_reason(cfg) -> str:
    if not getattr(cfg, "WEB_SEARCH_ENABLED", False):
        return "未启用全网搜索（WEB_SEARCH_ENABLED=false）"
    if not str(getattr(cfg, "WEB_SEARCH_PROVIDER", "") or "").strip():
        return "未配置 WEB_SEARCH_PROVIDER（支持 bocha/tavily）"
    if not str(getattr(cfg, "WEB_SEARCH_API_KEY", "") or "").strip():
        return "未配置 WEB_SEARCH_API_KEY"
    return "未知 WEB_SEARCH_PROVIDER（支持 bocha/tavily）"


def _resolve_yesterday(date_str: str) -> date:
    try:
        anchor = date.fromisoformat(str(date_str or "")[:10])
    except (TypeError, ValueError):
        anchor = localnow_naive().date()
    return anchor - timedelta(days=1)


async def _load_channel_context(channel_id: int) -> Optional[_ChannelContext]:
    async with AsyncSessionLocal() as session:
        channel = await session.scalar(select(Channel).where(Channel.id == channel_id))
        if channel is None:
            await session.commit()
            return None
        context = _ChannelContext(
            prompt=(channel.search_prompt or "").strip(),
            channel_type=channel.channel_type,
            min_duration_sec=channel.min_duration_sec,
            previous_topics=await _load_previous_topics(session, channel_id),
        )
        await session.commit()
        return context


async def _load_previous_topics(session, channel_id: int) -> list[str]:
    """取频道上一期稿件的选题标题（Episode.title + Script.segments[].title）。

    优先已发布节目；没有已发布时退回最近一期（含草稿），保证重跑当天也能复用
    上一期内容判断「同源事件」。
    """
    rows = (await session.execute(
        select(Episode, Script)
        .join(Script, Episode.script_id == Script.id)
        .where(Episode.channel_id == channel_id, Episode.script_id.is_not(None))
        .order_by(Episode.date.desc(), Episode.id.desc())
        .limit(5)
    )).all()
    if not rows:
        return []

    chosen = next(
        ((ep, script) for ep, script in rows if (ep.status or "") == EpisodeStatus.published.value),
        rows[0],
    )
    episode, script = chosen

    topics: list[str] = []
    if episode.title:
        topics.append(episode.title)

    segments = script.segments or []
    if isinstance(segments, str):
        try:
            segments = json.loads(segments)
        except (json.JSONDecodeError, TypeError):
            segments = []
    if isinstance(segments, list):
        for seg in segments:
            if isinstance(seg, dict):
                title = str(seg.get("title") or "").strip()
                if title:
                    topics.append(title)

    # 去重但保持顺序：Episode.title 可能与首个 segment.title 相同
    return list(dict.fromkeys(t for t in topics if t))


async def _search_many(
    provider,
    queries: list[str],
    round_name: str,
    *,
    count: int,
    concurrency: int,
    errors: list[str],
) -> list[SearchResult]:
    """并发执行一组检索式；单条失败只记录错误，不影响其他检索式。"""
    if not queries:
        return []

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _one(query: str) -> list[SearchResult]:
        async with sem:
            try:
                return await provider.search(query, count=count)
            except Exception as exc:  # 单条检索失败隔离
                errors.append(f"{round_name}: {type(exc).__name__}: {str(exc)[:160]}")
                logger.warning(
                    "全网搜索失败 round=%s query=%s err=%s", round_name, query, exc,
                )
                return []

    groups = await asyncio.gather(*[_one(q) for q in queries])
    merged: list[SearchResult] = []
    for group in groups:
        for item in group:
            item.round = round_name
            merged.append(item)
    return merged


async def _cross_validate(
    provider,
    candidates: list[SearchResult],
    queries: list[str],
    *,
    count: int,
    concurrency: int,
    errors: list[str],
) -> list[SearchResult]:
    """第三轮：对头部候选按标题再检索一次，命中另一站点即视为交叉确认。

    返回本轮命中的结果（作为补充信源一并参与入库）。
    """
    top = candidates[:len(queries)]
    if not top or not queries:
        return []

    results = await _search_many(
        provider, queries, "cross",
        count=count, concurrency=concurrency, errors=errors,
    )

    for item in top:
        digest = compute(item.title)
        own_url = normalize_url(item.url)
        item.confirmed = any(
            normalize_url(other.url) != own_url
            and is_similar(digest, compute(other.title), CROSS_SIMILARITY)
            for other in results
        )
    # 交叉检索命中的页面本身即为第二信源
    for item in results:
        item.confirmed = True
    return results


def _classify_all(
    candidates: list[SearchResult],
    previous_topics: list[str],
    threshold: int,
    max_items: int,
) -> tuple[list[SearchResult], int, int]:
    kept: list[SearchResult] = []
    prev_skipped = 0
    progress_kept = 0
    for item in candidates:
        kind, title = classify_candidate(item, previous_topics, threshold)
        if kind == "duplicate":
            prev_skipped += 1
            continue
        item.title = title
        if kind == "progress":
            progress_kept += 1
        kept.append(item)
        if len(kept) >= max_items:
            break
    return kept, prev_skipped, progress_kept


async def _prepare_material(item: SearchResult, topic: str) -> Optional[dict]:
    """把检索结果补成可入库素材：不足时回源抓正文，未核实则加「据媒体报道」。"""
    # material.url 为 String(512)：超长 URL 直接放弃，避免入库时才因截断失败
    if len(item.url) > 512:
        return None
    content = (item.content or "").strip()
    cover_url = None
    images: list = []
    if len(content) < MIN_SNIPPET_CHARS:
        article = await extract_article(item.url)
        article_content = (article.get("content") or "").strip()
        if article_content:
            content = article_content
            cover_url = article.get("cover_url")
            images = article.get("images") or []
    if len(content) < MIN_CONTENT_CHARS:
        return None

    item.content = content
    if not item.confirmed:
        mark_unverified(item)
    content = item.content

    source = (item.source or "").strip() or "全网搜索"
    category = (topic or "").strip()[:32] or None
    return {
        "title": item.title[:256],
        "url": item.url,
        "simhash": compute(item.title),
        "content": content,
        "summary": content[:200],
        "source": source[:64],
        "category_hint": category,
        "published_at": item.published_at,
        "cover_url": cover_url,
        "images": images,
        "_source_type": "web_search",
    }


async def _prepare_all(
    kept: list[SearchResult], topic: str, concurrency: int,
) -> tuple[list[dict], int]:
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _one(item: SearchResult) -> Optional[dict]:
        async with sem:
            try:
                return await _prepare_material(item, topic)
            except Exception as exc:
                logger.warning("全网搜索素材整理失败 url=%s err=%s", item.url, exc)
                return None

    prepared = await asyncio.gather(*[_one(item) for item in kept])
    materials: list[dict] = []
    verified = 0
    for item, material in zip(kept, prepared):
        if material is None:
            continue
        materials.append(material)
        if item.confirmed:
            verified += 1
    return materials, verified


async def collect_search_materials(
    workflow_id: str,
    date_str: str,
    channel_id: Optional[int],
    *,
    existing_urls: Optional[set[str]] = None,
) -> dict:
    """采集频道全网搜索素材。

    Args:
        workflow_id: 工作流 ID（仅用于日志关联）
        date_str: 工作流日期（YYYY-MM-DD），检索窗口取其前一天
        channel_id: 频道 ID；None 时不采集（搜索必须按频道提示词执行）
        existing_urls: 已准备好的 RSS 素材 URL，避免同 URL 重复入库

    Returns:
        {
          "enabled": bool, "materials": [prepared dict], "reason"/"error": str,
          "queries": int, "candidates": int, "kept": int, ... 密度与去重统计
        }
    """
    cfg = get_settings()
    provider = build_provider(cfg)
    if provider is None:
        return _closed(False, _disabled_reason(cfg))
    if channel_id is None:
        return _closed(False, "工作流未关联频道，跳过全网搜索")

    try:
        context = await _load_channel_context(channel_id)
        if context is None:
            return _closed(False, f"频道 {channel_id} 不存在")
        if not context.prompt:
            return _closed(False, "频道未配置全网搜索提示词（search_prompt 为空）")

        spec = parse_search_prompt(context.prompt)
        if not spec.usable:
            return _closed(False, "频道全网搜索提示词无法解析出主题/关键词/子板块")

        yesterday = _resolve_yesterday(date_str)
        window_start = datetime.combine(yesterday, dtime.min)
        count = max(1, int(getattr(cfg, "WEB_SEARCH_MAX_RESULTS_PER_QUERY", 5)))
        per_round = max(1, int(getattr(cfg, "WEB_SEARCH_MAX_QUERIES_PER_ROUND", 3)))
        max_total = max(1, int(getattr(cfg, "WEB_SEARCH_MAX_QUERIES_TOTAL", DEFAULT_MAX_QUERIES_TOTAL)))
        concurrency = max(1, int(getattr(cfg, "WEB_SEARCH_TASK_CONCURRENCY", 3)))
        max_items = max(1, int(getattr(cfg, "WEB_SEARCH_MAX_ITEMS", 30)))
        threshold = int(getattr(cfg, "WEB_SEARCH_PREV_SIMILARITY", 8))
        chars_per_sec = float(getattr(cfg, "WEB_SEARCH_CHARS_PER_SEC", 4.5))

        errors: list[str] = []
        used_queries: list[str] = []

        def _take(queries: list[str]) -> list[str]:
            remaining = max_total - len(used_queries)
            selected = queries[: max(0, remaining)]
            used_queries.extend(selected)
            return selected

        zh_queries, en_queries = build_round_queries(spec, yesterday.isoformat(), per_round=per_round)
        round_counts: dict[str, int] = {}
        stage1: list[SearchResult] = []
        for round_name, queries in (("zh", zh_queries), ("en", en_queries)):
            selected = _take(queries)
            round_counts[round_name] = len(selected)
            stage1.extend(await _search_many(
                provider, selected, round_name,
                count=count, concurrency=concurrency, errors=errors,
            ))

        # 入库前新鲜度过滤：搜索服务通常已按一天收窄，这里再兜一层，
        # 防止部分站点回填历史页面（published_at 为空时保留，无法判断即不误杀）
        stage1 = [
            item for item in stage1
            if item.published_at is None or item.published_at >= window_start
        ]
        merged = merge_results(stage1)

        top_n = max(0, int(getattr(cfg, "WEB_SEARCH_CROSS_CHECK_TOP", 3)))
        cross_queries = _take([
            f"{item.title} {yesterday.isoformat()}" for item in merged[:top_n]
        ])
        round_counts["cross"] = len(cross_queries)
        cross_results = await _cross_validate(
            provider, merged, cross_queries,
            count=count, concurrency=concurrency, errors=errors,
        )
        merged = merge_results(merged + cross_results)

        excluded = {normalize_url(url) for url in (existing_urls or set()) if url}
        if excluded:
            merged = [item for item in merged if normalize_url(item.url) not in excluded]

        kept, prev_skipped, progress_kept = _classify_all(
            merged, context.previous_topics, threshold, max_items,
        )

        # 密度保障：以目标语音时长反算所需字数，不足则按子板块补搜
        effective_sec = resolve_channel_min_duration_sec(
            context.channel_type, context.min_duration_sec,
        ) or int(getattr(cfg, "TARGET_DURATION_SEC", 600))
        target_chars = max(0, int(effective_sec * chars_per_sec))
        density_queries_used = 0

        def _collected_chars() -> int:
            return sum(len(item.content or "") for item in kept)

        if _collected_chars() < target_chars:
            density_limit = max(0, int(getattr(cfg, "WEB_SEARCH_MAX_DENSITY_QUERIES", 3)))
            density_queries = _take(build_density_queries(
                spec, yesterday.isoformat(),
                limit=density_limit, used=set(used_queries),
            ))
            density_queries_used = len(density_queries)
            if density_queries:
                density_results = await _search_many(
                    provider, density_queries, "density",
                    count=count, concurrency=concurrency, errors=errors,
                )
                density_results = [
                    item for item in density_results
                    if item.published_at is None or item.published_at >= window_start
                ]
                merged = merge_results(merged + density_results)
                if excluded:
                    merged = [item for item in merged if normalize_url(item.url) not in excluded]
                kept, prev_skipped, progress_kept = _classify_all(
                    merged, context.previous_topics, threshold, max_items,
                )

        round_counts["density"] = density_queries_used

        materials, verified = await _prepare_all(
            kept, spec.topic,
            concurrency=max(1, int(getattr(cfg, "WEB_SEARCH_FETCH_CONCURRENCY", 4))),
        )
        collected_chars = sum(len(m["content"]) for m in materials)
        density_met = collected_chars >= target_chars
        if not density_met:
            logger.warning(
                "全网搜索密度不足 channel=%s: %d/%d 字（目标时长 %ss），已用检索 %d 次",
                channel_id, collected_chars, target_chars, effective_sec, len(used_queries),
            )

        logger.info(
            "全网搜索完成 workflow_id=%s channel=%s provider=%s: 检索 %d 次 → 候选 %d 条"
            " → 保留 %d 条（上一期同源剔除 %d，进展保留 %d），%d 字/%d 字目标",
            workflow_id, channel_id, provider.name, len(used_queries), len(merged),
            len(materials), prev_skipped, progress_kept, collected_chars, target_chars,
        )

        return {
            "enabled": True,
            "reason": None,
            "error": errors[0] if errors and not materials else None,
            "provider": provider.name,
            "queries": len(used_queries),
            "rounds": round_counts,
            "candidates": len(merged),
            "kept": len(materials),
            "prev_event_skipped": prev_skipped,
            "progress_kept": progress_kept,
            "verified": verified,
            "unverified": max(0, len(materials) - verified),
            "target_chars": target_chars,
            "collected_chars": collected_chars,
            "density_met": density_met,
            "errors": errors[:5],
            "materials": materials,
        }
    except Exception as exc:
        logger.exception("全网搜索采集异常 workflow_id=%s channel=%s", workflow_id, channel_id)
        return {
            "enabled": True,
            "reason": None,
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "materials": [],
        }
