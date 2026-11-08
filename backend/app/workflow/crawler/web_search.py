"""全网搜索采集（T04116）。

职责：把频道 `search_prompt` 解析成可执行的检索参数，调用搜索服务执行多轮检索，
并把结果整理成与 RSS 条目同构的候选（标题 / URL / 正文 / 来源 / 发布时间）。

设计约束：
- **不新增第三方依赖**：检索统一走 HTTP JSON，内置博查（bocha）与 Tavily 两种契约；
- **无凭据即整体关闭**：`WEB_SEARCH_ENABLED=false` 或缺 provider/api_key 时返回 None，
  采集链路与接入前完全一致（不发起任何网络请求）；
- **不臆造**：交叉验证未通过的候选在正文前缀「据媒体报道」，由调用方落库。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.simhash import compute, hamming_distance, is_similar

logger = logging.getLogger(__name__)

# 「新增进展」判定词：与上一期同源时，命中任一词才以进展角度保留（否则视为重复事件）
PROGRESS_MARKERS = (
    "进展", "更新", "回应", "宣布", "发布", "最新", "新增", "上调", "下调",
    "突破", "首次", "达成", "签署", "获批", "召回", "下架", "开庭", "判决",
    "通报", "辟谣", "涨幅", "跌幅", "创下",
)

# 候选正文短于此长度时视为「只有搜索摘要」，回源抓取正文再比对密度
MIN_SNIPPET_CHARS = 120

# 交叉验证时判定「同一事件」的宽松阈值：同一事件的不同措辞汉明距离通常 > 3
CROSS_SIMILARITY = 6


@dataclass(frozen=True)
class SearchSpec:
    """从 search_prompt 解析出的可执行检索参数。"""

    topic: str = ""
    subsections: list[str] = field(default_factory=list)
    keywords_zh: list[str] = field(default_factory=list)
    keywords_en: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return bool(self.keywords_zh or self.keywords_en or self.subsections)


@dataclass
class SearchResult:
    """单条检索结果（与 Material 入库前字段对齐）。"""

    title: str
    url: str
    content: str = ""
    source: str = ""
    published_at: Optional[datetime] = None
    round: str = ""
    confirmed: bool = False


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, *, count: int) -> list[SearchResult]:
        ...


_H1_TOPIC_RE = re.compile(r"^#\s*(.+?)\s*每日重点资讯", re.MULTILINE)
_ANY_H1_RE = re.compile(r"^#\s*(.+?)\s*$", re.MULTILINE)
_SUBSECTION_BLOCK_RE = re.compile(
    r"^##\s*信息采集范围[^\n]*\n(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL
)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$", re.MULTILINE)
_KEYWORDS_ZH_RE = re.compile(r"第一轮[^\n]*?「([^」]+)」")
_KEYWORDS_EN_RE = re.compile(r"第二轮[^\n]*?「([^」]+)」")
_KEYWORD_SEP_RE = re.compile(r"[,，、;；]")


def _split_keywords(raw: str) -> list[str]:
    return [k.strip() for k in _KEYWORD_SEP_RE.split(raw or "") if k.strip()]


def parse_search_prompt(prompt: str | None) -> SearchSpec:
    """解析频道全网搜索提示词（兼容 T04111 骨架与手写文本）。

    骨架中可稳定抽取的四类信息：主题（一级标题）、子板块（「信息采集范围」下的
    列表项）、第一轮中文关键词、第二轮英文关键词。解析不到的部分留空，由调用方
    用频道名/子板块兜底，不因提示词风格差异直接失败。
    """
    text = (prompt or "").strip()
    if not text:
        return SearchSpec()

    match = _H1_TOPIC_RE.search(text)
    topic = match.group(1).strip() if match else ""
    if not topic:
        fallback = _ANY_H1_RE.search(text)
        topic = fallback.group(1).strip() if fallback else ""

    subsections: list[str] = []
    block = _SUBSECTION_BLOCK_RE.search(text)
    if block:
        subsections = [s.strip() for s in _BULLET_RE.findall(block.group(1)) if s.strip()]

    zh_match = _KEYWORDS_ZH_RE.search(text)
    en_match = _KEYWORDS_EN_RE.search(text)
    keywords_zh = _split_keywords(zh_match.group(1)) if zh_match else []
    keywords_en = _split_keywords(en_match.group(1)) if en_match else []
    if not keywords_zh and topic:
        keywords_zh = [topic]

    return SearchSpec(topic=topic, subsections=subsections,
                      keywords_zh=keywords_zh, keywords_en=keywords_en)


def normalize_url(url: str) -> str:
    """URL 归一化（去 fragment、统一 scheme/host 大小写、去尾部斜杠）。"""
    raw = (url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if parts.scheme.lower() not in ("http", "https"):
        return ""
    return urlunsplit((
        parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/",
        parts.query, "",
    ))


def merge_results(results: list[SearchResult]) -> list[SearchResult]:
    """按 URL 精确 + 标题 SimHash 近似合并多轮结果，保留首次出现顺序。"""
    merged: list[SearchResult] = []
    seen_urls: set[str] = set()
    seen_hashes: list[str] = []
    for item in results:
        key = normalize_url(item.url)
        if not key or key in seen_urls:
            continue
        digest = compute(item.title)
        # 同一事件被不同站点转载时保留首条即可（后续正文可由回源抓取补足）
        if any(hamming_distance(digest, other) <= 3 for other in seen_hashes):
            continue
        seen_urls.add(key)
        seen_hashes.append(digest)
        merged.append(item)
    return merged


def classify_candidate(
    item: SearchResult, previous_topics: list[str], threshold: int,
) -> tuple[str, str]:
    """判定候选与上一期报告的关系。

    判断进展词时以「最相近的上一期标题」为基准并排除其自带词：像「发布」常是
    事件本身的一部分（「某公司发布财报」），若上一期已这么写，同一个标题再出现
    应判重复而不是进展；只有候选带来上一期标题之外的新信号（进展/回应/上调…）
    才以进展角度保留。

    Returns:
        ("new", title)        从未覆盖过的事件
        ("progress", title)   上一期同源、但带新进展信号 → 标题前缀「新增进展」保留
        ("duplicate", title)  上一期已覆盖且无新进展 → 丢弃
    """
    if not previous_topics:
        return "new", item.title
    digest = compute(item.title)
    matched = [topic for topic in previous_topics
               if is_similar(digest, compute(topic), threshold)]
    if not matched:
        return "new", item.title

    baseline = min(matched, key=lambda topic: hamming_distance(digest, compute(topic)))
    markers = [marker for marker in PROGRESS_MARKERS if marker not in baseline]
    haystack = f"{item.title} {item.content[:300]}"
    if any(marker in haystack for marker in markers):
        return "progress", f"【新增进展】{item.title}"
    return "duplicate", item.title


def mark_unverified(item: SearchResult) -> None:
    """交叉验证未通过的候选：正文前缀「据媒体报道」，避免把单一信源当已核实事实。"""
    content = (item.content or "").strip()
    if content.startswith("据媒体报道"):
        return
    item.content = f"据媒体报道：{content}" if content else "据媒体报道。"


def _parse_datetime(raw: object) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc).astimezone().replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(raw).strip()
    if not text:
        return None
    parsed: Optional[datetime] = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


async def _post_json(
    url: str, payload: dict, headers: dict, timeout: float,
) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"检索服务返回非 JSON 对象: {str(data)[:120]}")
    return data


class BochaProvider:
    """博查 Web Search（https://api.bochaai.com/v1/web-search）。

    请求体 freshness=oneDay + summary=true：检索服务侧已按「最近一天」收窄，
    正文摘要用于密度判定，长度不足时由调用方回源抓取全文。
    """

    name = "bocha"
    DEFAULT_ENDPOINT = "https://api.bochaai.com/v1/web-search"

    def __init__(self, api_key: str, endpoint: str = "", timeout: float = 20.0):
        self._api_key = api_key
        self._url = (endpoint or "").strip() or self.DEFAULT_ENDPOINT
        self._timeout = timeout

    async def search(self, query: str, *, count: int) -> list[SearchResult]:
        data = await _post_json(
            self._url,
            {"query": query, "freshness": "oneDay", "summary": True, "count": count},
            {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            self._timeout,
        )
        code = data.get("code")
        if isinstance(code, int) and code not in (0, 200):
            raise RuntimeError(f"博查检索失败 code={code} msg={str(data.get('msg') or data.get('message') or '')[:120]}")
        pages = (((data.get("data") or {}).get("webPages") or {}).get("value") or [])
        results: list[SearchResult] = []
        for page in pages:
            if not isinstance(page, dict):
                continue
            title = str(page.get("name") or "").strip()
            url = str(page.get("url") or "").strip()
            if not title or not normalize_url(url):
                continue
            results.append(SearchResult(
                title=title,
                url=url,
                content=str(page.get("summary") or page.get("snippet") or "").strip(),
                source=str(page.get("siteName") or ""),
                published_at=_parse_datetime(page.get("datePublished")),
            ))
        return results


class TavilyProvider:
    """Tavily Search（https://api.tavily.com/search），topic=news + days=1。"""

    name = "tavily"
    DEFAULT_ENDPOINT = "https://api.tavily.com/search"

    def __init__(self, api_key: str, endpoint: str = "", timeout: float = 20.0):
        self._api_key = api_key
        self._url = (endpoint or "").strip() or self.DEFAULT_ENDPOINT
        self._timeout = timeout

    async def search(self, query: str, *, count: int) -> list[SearchResult]:
        data = await _post_json(
            self._url,
            {
                "api_key": self._api_key,
                "query": query,
                "topic": "news",
                "days": 1,
                "search_depth": "basic",
                "include_raw_content": False,
                "max_results": count,
            },
            {"Content-Type": "application/json"},
            self._timeout,
        )
        results: list[SearchResult] = []
        for item in data.get("results") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            if not title or not normalize_url(url):
                continue
            results.append(SearchResult(
                title=title,
                url=url,
                content=str(item.get("content") or "").strip(),
                source=str(item.get("source") or ""),
                published_at=_parse_datetime(item.get("published_date")),
            ))
        return results


def build_provider(cfg) -> Optional[SearchProvider]:
    """按配置构造检索 provider；未启用/缺凭据/未知 provider 时返回 None。

    默认关闭是刻意的：仓库内没有任何搜索服务凭据，开启后若静默退化为 RSS
    会让运营误以为「全网搜索已生效」。因此缺少条件时由调用方把原因写进
    crawl 结果（web_search.reason），而不是发请求失败。
    """
    if not getattr(cfg, "WEB_SEARCH_ENABLED", False):
        return None
    provider = str(getattr(cfg, "WEB_SEARCH_PROVIDER", "") or "").strip().lower()
    api_key = str(getattr(cfg, "WEB_SEARCH_API_KEY", "") or "").strip()
    if not provider or not api_key:
        return None
    endpoint = str(getattr(cfg, "WEB_SEARCH_ENDPOINT", "") or "").strip()
    timeout = float(getattr(cfg, "WEB_SEARCH_TIMEOUT_SEC", 20.0))
    if provider == "bocha":
        return BochaProvider(api_key, endpoint, timeout)
    if provider == "tavily":
        return TavilyProvider(api_key, endpoint, timeout)
    logger.warning("未知的全网搜索 provider: %s（支持 bocha/tavily）", provider)
    return None


def build_round_queries(
    spec: SearchSpec, yesterday: str, *, per_round: int,
) -> tuple[list[str], list[str]]:
    """第一轮中文 / 第二轮英文检索式（各取前 per_round 个关键词）。"""
    zh = [f"{kw} {yesterday}" for kw in spec.keywords_zh[:per_round]]
    en = [f"{kw} {yesterday}" for kw in spec.keywords_en[:per_round]]
    return zh, en


def build_density_queries(
    spec: SearchSpec, yesterday: str, *, limit: int, used: set[str],
) -> list[str]:
    """密度补充检索式：按子板块补搜，跳过已用过的检索式。"""
    queries: list[str] = []
    for sub in spec.subsections:
        query = f"{spec.topic} {sub} {yesterday}".strip()
        if query in used:
            continue
        queries.append(query)
        if len(queries) >= limit:
            break
    return queries
