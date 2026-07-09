"""正文提取器（V1.2：httpx + selectolax 替代 newspaper3k）。

设计原因：RSS 仅提供摘要，需要访问详情页提取完整正文供后续 LLM 改写。
httpx 负责异步下载页面，selectolax 负责高效解析 HTML（基于 Lexbor C 库）。
通用启发式：移除非正文标签后，收集 <article> 或全页 <p> 文本作为正文。
失败时返回 None 由上层用 RSS summary 兜底。
"""
import logging
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 非正文标签：解析前移除，避免导航/广告/页脚文本污染正文
_NOISE_TAGS = ("script", "style", "nav", "footer", "aside", "header", "form", "noscript")


async def extract(url: str, fallback_selectors: Optional[dict] = None) -> dict:
    """异步提取正文。

    返回 {title, content, publish_time}，失败时三个字段均为 None。
    fallback_selectors 预留扩展点（按域名走 CSS 选择器规则），MVP 暂不启用。
    """
    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": settings.CRAWLER_USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        # 网络错误、404、超时等：记录后返回 None 由上层兜底
        logger.warning("正文页面下载失败 url=%s err=%s", url, e)
        return {"title": None, "content": None, "publish_time": None}

    try:
        return _parse_html(html)
    except Exception as e:
        logger.warning("正文解析失败 url=%s err=%s", url, e)
        return {"title": None, "content": None, "publish_time": None}


def _parse_html(html: str) -> dict:
    """从 HTML 提取标题与正文。

    启发式策略：优先取 <article> 容器内的 <p>；无 <article> 时取全页 <p>。
    publish_date 无通用可靠提取方式，返回 None（上层有 RSS published_at 兜底）。
    """
    tree = HTMLParser(html)

    # 移除噪声标签，避免正文混入导航/脚本文本
    for tag in _NOISE_TAGS:
        for node in tree.css(tag):
            node.decompose()

    # 标题：优先 <meta property="og:title">（新闻站点常用），回退 <title>
    title = None
    og_title = tree.css_first('meta[property="og:title"]')
    if og_title and og_title.attrs.get("content"):
        title = og_title.attrs["content"].strip()
    if not title:
        title_node = tree.css_first("title")
        if title_node and title_node.text():
            # <title> 常含 "正文 - 站点名" 后缀，取第一段
            title = title_node.text().split(" - ")[0].split(" | ")[0].strip()

    # 正文：优先 <article> 容器，回退全页
    content_parts: list[str] = []
    article_node = tree.css_first("article")
    paragraphs = article_node.css("p") if article_node else tree.css("p")
    for p in paragraphs:
        text = p.text(strip=True)
        # 过滤过短片段（导航残留、广告占位等通常 < 20 字）
        if text and len(text) >= 20:
            content_parts.append(text)

    content = "\n\n".join(content_parts) if content_parts else None

    return {"title": title, "content": content, "publish_time": None}
