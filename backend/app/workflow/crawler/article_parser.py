"""正文提取器。

设计原因：RSS 仅提供摘要，需要访问详情页提取完整正文供后续 LLM 改写。
newspaper3k 对大多数新闻站点通用性较好，失败时返回 None 由上层用 RSS summary 兜底。
newspaper3k 是同步库，需 asyncio.to_thread 包装避免阻塞事件循环。
"""
import asyncio
import logging
from typing import Optional

import newspaper

logger = logging.getLogger(__name__)


def _extract_sync(url: str, fallback_selectors: Optional[dict] = None) -> dict:
    """同步提取正文（在线程中执行）。

    newspaper3k 内部会下载页面并解析 DOM，单次约 1-3 秒。
    fallback_selectors 预留扩展点：未来可按域名走 CSS 选择器规则，
    当 newspaper3k 通用提取失败时回退；MVP 阶段暂不启用。
    """
    try:
        article = newspaper.article(url)
        return {
            "title": article.title or None,
            "content": article.text or None,
            "publish_time": article.publish_date,
        }
    except Exception as e:
        # newspaper3k 对非常规格式的站点会抛异常，记录后返回 None 由上层兜底
        logger.warning("正文提取失败 url=%s err=%s", url, e)
        return {"title": None, "content": None, "publish_time": None}


async def extract(url: str, fallback_selectors: Optional[dict] = None) -> dict:
    """异步提取正文。

    返回 {title, content, publish_time}，失败时三个字段均为 None。
    """
    return await asyncio.to_thread(_extract_sync, url, fallback_selectors)
