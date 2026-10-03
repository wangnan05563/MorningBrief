"""电子书书目检索服务（T00601 / T00603：听书频道「找书」产品能力）。

数据源：GitHub 仓库 `jbiaojerry/ebook-treasure-chest`
- 结构：README 引用 1000 个分类 md（`md/<分类>.md`），条目为 Markdown 表格
  `| 书名 | 作者 | [下载](url) |`；
- 链接形态：**全部指向城通网盘**（`url89.ctfile.com/f/<id>?p=<提取参数>`）。实测其落地页为
  JS 交互页、HTML 内无下载直链 → **程序化取件不可行**，故本服务只自动化「找书」，
  取件仍由人工完成后走素材上传链路入库（document_ingest 支持 .epub/.docx/.html/.txt/.md）。

⚠️ 授权提示（转载自来源仓库自带声明，非本项目观点）：
  「本站内容均从网上搜集……下载链接仅供宽带测试研究用途，请下载后在 24 小时内删除，
   请勿用于商业目的。请支持正版！」用于对外发布的频道内容前请自行确认授权。

设计要点：
- `parse_category` 为**纯函数**（无 IO），便于单测与复用；
- 分类 md 单文件 150–250KB，采用**进程内 TTL 缓存**（默认 4h）避免重复拉取；
- 网络失败按分类隔离：单个分类失败只跳过，不阻断整体检索（返回 scanned 列表供前端展示覆盖范围）。
"""
from __future__ import annotations

import re
import time
from typing import Any

import requests
from loguru import logger

REPO = "jbiaojerry/ebook-treasure-chest"
BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"
_UA = {"User-Agent": "MorningBriefBot/1.0 (+audiobook-channel book search)"}

# 内存 TTL 缓存：{path: (expire_ts, text)}
_CACHE: dict[str, tuple[float, str]] = {}
CACHE_TTL_SEC = 4 * 3600

# 表格行：| 书名 | 作者 | [下载](url) |
_ROW_RE = re.compile(
    r"^\|\s*(?P<title>[^|]+?)\s*\|\s*(?P<author>[^|]*?)\s*\|\s*\[[^\]]*\]\((?P<url>https?://[^)]+)\)"
)


def _fetch(path: str, force: bool = False) -> str:
    """拉取仓库文件（进程内 TTL 缓存）。失败抛异常，由调用方决定隔离策略。"""
    now = time.time()
    hit = _CACHE.get(path)
    if not force and hit and hit[0] > now:
        return hit[1]
    r = requests.get(RAW_BASE + path, headers=_UA, timeout=40)
    r.raise_for_status()
    text = r.text
    _CACHE[path] = (now + CACHE_TTL_SEC, text)
    return text


def parse_category(md_text: str) -> list[dict]:
    """解析分类 md 的 Markdown 表格 → [{title, author, url}]（纯函数，跳过表头/无链接行）。"""
    books: list[dict] = []
    for line in md_text.splitlines():
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        title = m.group("title").strip()
        if not title or title == "书名" or set(title) <= set("-: "):
            continue
        books.append({
            "title": title,
            "author": m.group("author").strip(),
            "url": m.group("url").strip(),
        })
    return books


def list_categories(force: bool = False) -> list[str]:
    """列出全部分类名（按名称排序）。"""
    readme = _fetch("README.md", force=force)
    return sorted(set(re.findall(r"md/([^)\s]+?)\.md", readme)))


def _search_result(keyword: str, scanned: list[str], failed: list[str], hits: list[dict]) -> dict:
    """统一构造 search 返回结构。"""
    return {
        "keyword": keyword,
        "scanned_categories": scanned,
        "failed_categories": failed,
        "hits": hits,
    }


def _match_books_in_category(text: str, kw: str, category: str, hits: list[dict], limit: int) -> bool:
    """把该分类下命中关键词（书名/作者）的书目追加进 hits。

    达到 limit（防止全量扫描结果过大）时返回 True，调用方提前收口。
    """
    for b in parse_category(text):
        if kw in b["title"].lower() or kw in (b["author"] or "").lower():
            hits.append({**b, "category": category})
            if len(hits) >= max(1, limit):
                return True
    return False


def search(keyword: str, category: str | None = None, limit: int = 20, force: bool = False) -> dict:
    """按关键词检索书名/作者。

    Args:
        keyword: 关键词（书名或作者片段，大小写不敏感）
        category: 限定分类（如「文学」）；为空则扫描全部分类（较慢，1000 个文件）
        limit: 命中上限（防止全量扫描时结果过大）
        force: 忽略缓存强制重新拉取

    Returns:
        {"keyword", "scanned_categories": [...], "failed_categories": [...], "hits": [...]}
    """
    kw = (keyword or "").strip().lower()
    if not kw:
        return _search_result(keyword, [], [], [])

    cats = [category] if category else list_categories(force=force)
    hits: list[dict] = []
    scanned: list[str] = []
    failed: list[str] = []

    for c in cats:
        try:
            text = _fetch(f"md/{c}.md", force=force)
        except Exception as e:  # 单分类失败隔离，不阻断整体
            failed.append(c)
            logger.warning("[ebook_source] 分类 %s 拉取失败: %s", c, e)
            continue
        scanned.append(c)
        if _match_books_in_category(text, kw, c, hits, limit):
            return _search_result(keyword, scanned, failed, hits)

    logger.info("[ebook_source] 检索「%s」命中 %d 条（扫描 %d 分类，失败 %d）",
                keyword, len(hits), len(scanned), len(failed))
    return _search_result(keyword, scanned, failed, hits)
