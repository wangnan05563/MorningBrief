"""正文提取器（V1.2：httpx + selectolax 替代 newspaper3k）。

设计原因：RSS 仅提供摘要，需要访问详情页提取完整正文供后续 LLM 改写。
httpx 负责异步下载页面，selectolax 负责高效解析 HTML（基于 Lexbor C 库）。
通用启发式：移除非正文标签后，收集 <article> 或全页 <p> 文本作为正文。
失败时返回 None 由上层用 RSS summary 兜底。
"""
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 非正文标签：解析前移除，避免导航/广告/页脚文本污染正文
_NOISE_TAGS = ("script", "style", "nav", "footer", "aside", "header", "form", "noscript")


async def extract(url: str, fallback_selectors: Optional[dict] = None) -> dict:
    """异步提取正文。

    返回 {title, content, publish_time, cover_url}，失败时字段均为 None。
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
        return {"title": None, "content": None, "publish_time": None, "cover_url": None}

    try:
        return _parse_html(html, url)
    except Exception as e:
        logger.warning("正文解析失败 url=%s err=%s", url, e)
        return {"title": None, "content": None, "publish_time": None, "cover_url": None}


def _is_decorative_image(url: str) -> bool:
    """识别装饰性图片（站点 logo、导航图标、箭头按钮、栏目导读图、二维码等，非文章内容图）。

    依据：URL 路径包含装饰关键词或匹配已知栏目图模式。
    - logo/icon/arrow/btn/sprite/avatar/banner 等通用装饰关键词
    - code/qrcode：二维码图（17173cdn 有 code-x.jpg）
    - more/rmwjia：人民网"更多"按钮、人民号图标
    - 2020peopleindex/2020wbc：人民网站点模板资源路径（年份+站点名，非文章图）
    - dyz/：人民网栏目导读图路径
    - counter：统计计数器域名（counter.people.cn:8000/c.gif）
    - .gif：GIF 多为动画图标或统计像素，新闻文章封面几乎不用 GIF
    """
    if not url:
        return False
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    host_lower = parsed.hostname or ""
    keywords = (
        "logo", "icon", "arrow", "btn", "button", "sprite",
        "avatar", "share_icon", "default_cover", "site_icon",
        "placeholder", "loading", "blank", "ad_", "banner",
        "qrcode", "code-", "_code.", "code.", "ewm",
        # 人民网装饰图：dyz 栏目导读、more 更多按钮、rmwjia 人民号图标
        "dyz/", "more", "rmwjia",
        # 人民网站点模板资源路径：年份+站点名，属全站共用模板图
        "2020peopleindex", "2020wbc",
    )
    if any(kw in path_lower for kw in keywords):
        return True
    # 统计计数器域名：counter.people.cn:8000/c.gif 这类 1x1 像素统计图
    if "counter" in host_lower:
        return True
    # GIF 多为动画图标或统计像素，新闻文章封面几乎不用 GIF
    if path_lower.endswith(".gif"):
        return True
    return False


def _normalize_img_url(src: str, base_url: str) -> str | None:
    """规范化图片 URL：补全协议相对路径与相对路径，过滤 data: URI。"""
    if not src:
        return None
    src = src.strip()
    if not src or src.startswith("data:"):
        return None
    if src.startswith("//"):
        return "https:" + src
    if not src.startswith(("http://", "https://")):
        if base_url:
            return urljoin(base_url, src)
        return None
    return src


def _parse_html(html: str, base_url: str = "") -> dict:
    """从 HTML 提取标题、正文与封面图。

    启发式策略：优先取 <article> 容器内的 <p>；无 <article> 时取全页 <p>。
    publish_date 无通用可靠提取方式，返回 None（上层有 RSS published_at 兜底）。
    封面图优先级：
    1. og:image（站点级 meta，需过滤站点 logo）
    2. article 内首个 <img>（与正文强相关）
    3. 全页首个非装饰 <img>（兜底，过滤 logo/icon/arrow 等）
    相对路径用 base_url 补全为绝对路径，小程序才能直接加载。
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

    # 封面图提取：三级回退策略
    cover_url = None
    # 1. og:image（标准化 meta，但需过滤站点 logo）
    og_image = tree.css_first('meta[property="og:image"]')
    if og_image and og_image.attrs.get("content"):
        og_url = og_image.attrs["content"].strip()
        if og_url and not _is_decorative_image(og_url):
            cover_url = _normalize_img_url(og_url, base_url)
    # 2. article 内首个 <img>
    article_node = tree.css_first("article")
    if not cover_url and article_node:
        first_img = article_node.css_first("img")
        if first_img:
            src = first_img.attrs.get("src") or first_img.attrs.get("data-src") or ""
            if src and not _is_decorative_image(src):
                cover_url = _normalize_img_url(src, base_url)
    # 3. 全页首个非装饰 <img>（兜底）
    if not cover_url:
        for img in tree.css("img"):
            src = img.attrs.get("src") or img.attrs.get("data-src") or ""
            if src and not _is_decorative_image(src):
                normalized = _normalize_img_url(src, base_url)
                if normalized:
                    cover_url = normalized
                    break

    # 正文：复用上面的 article_node，避免重复 CSS 查询
    content_parts: list[str] = []
    paragraphs = article_node.css("p") if article_node else tree.css("p")
    for p in paragraphs:
        text = p.text(strip=True)
        # 过滤过短片段（导航残留、广告占位等通常 < 20 字）
        if text and len(text) >= 20:
            content_parts.append(text)

    content = "\n\n".join(content_parts) if content_parts else None

    return {"title": title, "content": content, "publish_time": None, "cover_url": cover_url}
