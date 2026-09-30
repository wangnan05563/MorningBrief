"""全文源爬虫（T00603：听书频道「整本书」资料渠道）。

与 feedparser 版 `_crawl_source` 平行的一种源类型：条目不是书评文章，而是
**书籍章节全文**（已预取正文，入库时跳过 extract_article 二次抓取）。

支持的 provider（均为免 key 公版/开放获取渠道，2026-09-15 实测）：
- wikisource：中文维基文库 MediaWiki API（`prop=extracts` 按页取全文）；
  ⚠️ Wikimedia 政策要求 UA 可联系，已带项目 UA；内容 CC BY-SA，对外发布需署名。
- gutendex：Gutenberg 的 JSON API（检索/按 id 取书 → 下载 text/plain 全文 → 切章）。

不再接入的渠道（实测记录）：
- CTEXT `gettext`：需注册 IP 或 API key（免费账号可申请，接入时在 source 配置 api_key 即可）；
- 盗版聚合仓库（如 ebook-treasure-chest 的网盘直链）：合规风险，仅保留人工取件工具。

条目形态与 feedparser entry 对齐（title/url/source/category_hint/published_at/summary），
另带 `_fulltext=True` 与预取的 `content` —— runner 的 `_extract_content` 据此跳过网络抓取。
超长文本用 document_ingest 的统一切分器切块，保证单条素材长度与 TTS/改写约束匹配。
"""
import asyncio
import re
from typing import Any

import requests
from loguru import logger

from app.services.document_ingest import split_text

_UA = {"User-Agent": "MorningBriefBot/1.0 (+audiobook fulltext source)"}
_TIMEOUT = 40

# 单章素材的软上限（字符）：超过则继续按章节切分器细切，匹配改写步 ~600-1000 字/段的预算
_SOFT_CHAPTER_CHARS = 1200


def _get_json(url: str, params: dict | None = None) -> Any:
    r = requests.get(url, params=params, headers=_UA, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _get_text(url: str) -> str:
    r = requests.get(url, headers=_UA, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.text


def _make_entry(source_name: str, title: str, url: str, content: str, category_hint: str | None) -> dict:
    """构造与 feedparser entry 同构的条目；`_fulltext` 标记使 runner 跳过正文二次抓取。"""
    return {
        "title": title,
        "url": url,
        "source": source_name,
        "category_hint": category_hint,
        "published_at": None,  # 公版内容无发布时间：runner 的新鲜度过滤会保留
        "summary": content[:200],
        "content": content,
        "_fulltext": True,
    }


def _entries_from_text(source_name: str, base_title: str, base_url: str, text: str, category_hint: str | None) -> list[dict]:
    """把整篇/整本书文本切分为条目：先按章节标题分章，超长章再切块。"""
    chapters = split_text(text, default_title=base_title)
    entries: list[dict] = []
    for i, ch in enumerate(chapters, 1):
        # 切分器的默认标题（正文 / 第N节）视为「无章节标题」：用源配置的篇名 + 序号，
        # 避免多页书的素材标题互相覆盖语义（如 两页都叫「第1节」）
        if ch["title"] == base_title or re.match(r"^第\d+节$", ch["title"]):
            title = f"{base_title}（{i}）"
        else:
            title = ch["title"]
        if not title.startswith(base_title) and len(chapters) > 1:
            title = f"{base_title}·{title}"
        # 章内仍超长的（如无标题结构的整本书）由 split_text 内部已切块，这里兜底再切一次
        pieces = [ch["content"]]
        if len(ch["content"]) > _SOFT_CHAPTER_CHARS * 2:
            pieces = [p["content"] for p in split_text(ch["content"], default_title=title)]
        for j, piece in enumerate(pieces, 1):
            piece_title = title if len(pieces) == 1 else f"{title}（{j}）"
            entries.append(_make_entry(
                source_name, piece_title, f"{base_url}#{len(entries) + 1}", piece, category_hint,
            ))
    return entries


# ---------------------------------------------------------------------------
# provider: wikisource（中文维基文库）
# ---------------------------------------------------------------------------

_WIKI_API = "https://zh.wikisource.org/w/api.php"


def _wikisource(src: dict) -> list[dict]:
    """按 `pages` 列表逐页取全文（MediaWiki extracts，纯文本）。"""
    pages = src.get("pages") or []
    if not pages:
        raise ValueError(f"书源 {src.get('name')} 缺少 pages 配置")
    entries: list[dict] = []
    for page in pages:
        data = _get_json(_WIKI_API, {
            "action": "query", "prop": "extracts", "explaintext": 1,
            "titles": page, "format": "json", "redirects": 1,
        })
        pages_map = (data.get("query") or {}).get("pages") or {}
        text = ""
        for p in pages_map.values():
            if p.get("extract"):
                text = p["extract"].strip()
                break
        if not text:
            logger.warning("[fulltext] 维基文库页面无正文，跳过: %s", page)
            continue
        url = f"https://zh.wikisource.org/wiki/{requests.utils.quote(page.replace(' ', '_'))}"
        entries.extend(_entries_from_text(src["name"], page, url, text, src.get("category_hint")))
    return entries


# ---------------------------------------------------------------------------
# provider: gutendex（Project Gutenberg JSON API）
# ---------------------------------------------------------------------------

_GUTENDEX = "https://gutendex.com/books"


def _pick_text_format(formats: dict) -> str | None:
    for k, v in formats.items():
        if k.startswith("text/plain") and ("utf-8" in k.lower() or "us-ascii" in k.lower()):
            return v
    for k, v in formats.items():
        if k.startswith("text/plain"):
            return v
    return None


def _gutendex(src: dict) -> list[dict]:
    """按 `gutenberg_id` 或 `query(+languages)` 解析书目 → 下载 text/plain 全文 → 切章。"""
    if src.get("gutenberg_id"):
        data = _get_json(_GUTENDEX, {"ids": src["gutenberg_id"]})
    else:
        params: dict = {}
        if src.get("languages"):
            params["languages"] = src["languages"]
        if src.get("query"):
            params["search"] = src["query"]
        data = _get_json(_GUTENDEX, params)
    results = (data or {}).get("results") or []
    book = None
    for b in results:
        if _pick_text_format(b.get("formats") or {}):
            book = b
            break
    if not book:
        raise ValueError(f"书源 {src.get('name')} 未找到可下载的 text/plain 文本")

    text_url = _pick_text_format(book["formats"])
    text = _get_text(text_url)
    # Gutenberg 头尾有许可证样板，粗略去头（从首个空行分隔块开始）
    max_chapters = int(src.get("max_chapters") or 40)
    entries = _entries_from_text(
        src["name"], book.get("title") or src["name"],
        f"https://www.gutenberg.org/ebooks/{book['id']}", text, src.get("category_hint"),
    )
    if len(entries) > max_chapters:
        logger.warning("[fulltext] Gutendex《%s》切出 %d 条，截断为 %d 条",
                       book.get("title"), len(entries), max_chapters)
        entries = entries[:max_chapters]
        for i, e in enumerate(entries, 1):
            e["url"] = f"https://www.gutenberg.org/ebooks/{book['id']}#{i}"  # 截断后重排去重键
    return entries


# ---------------------------------------------------------------------------
# 调度入口
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "wikisource": _wikisource,
    "gutendex": _gutendex,
}


async def crawl_fulltext_source(src: dict) -> list[dict]:
    """全文源抓取入口（runner 按 `provider` 字段分派）。同步网络调用经 to_thread 隔离。"""
    provider = (src.get("provider") or "").lower()
    fn = _PROVIDERS.get(provider)
    if fn is None:
        raise ValueError(f"书源 {src.get('name')} 的 provider 未知: {provider or '(空)'}")
    entries = await asyncio.to_thread(fn, src)
    logger.info("[fulltext] 源 %s（%s）产出 %d 条章节素材", src.get("name"), provider, len(entries))
    return entries
