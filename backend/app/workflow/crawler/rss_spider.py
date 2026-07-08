"""RSS 爬虫。

设计原因：RSS 是结构化数据源，比列表页爬取更稳定可靠，优先使用。
feedparser 是同步库，需 asyncio.to_thread 包装避免阻塞事件循环。
"""
import asyncio
import logging
from datetime import datetime
from time import mktime

import feedparser
import httpx

logger = logging.getLogger(__name__)


class RSSSpider:
    """单个 RSS 源爬虫。

    接收 rss.yaml 中一个 source 配置，负责抓取并解析该源全部条目。
    """

    def __init__(self, source_config: dict):
        self.config = source_config
        self.name = source_config["name"]
        self.url = source_config["url"]
        self.authority = source_config.get("authority", 0.5)
        self.category_hint = source_config.get("category_hint")
        # 从全局配置取 UA，未来可由 runner 注入覆盖
        self.user_agent = "20NewsBot/1.0"

    async def fetch(self) -> list[dict]:
        """爬取该 RSS 源所有条目。

        返回 [{title, url, summary, published_at, source, source_authority, category_hint}]。
        单源失败返回空列表，由上层日志记录后继续其他源（HLD 单源失败隔离）。
        """
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            ) as client:
                resp = await client.get(self.url)
                resp.raise_for_status()
                xml_content = resp.text

            # feedparser 解析含 CPU 计算与可能的同步 IO，放线程池避免阻塞事件循环
            feed = await asyncio.to_thread(feedparser.parse, xml_content)

            entries = []
            for entry in feed.entries:
                # published_parsed 是 time.struct_time，转 datetime 便于入库
                published_at = None
                if getattr(entry, "published_parsed", None):
                    published_at = datetime.fromtimestamp(
                        mktime(entry.published_parsed)
                    )

                # link 缺失的条目无法后续提取正文，跳过
                link = getattr(entry, "link", None)
                if not link:
                    continue

                entries.append({
                    "title": getattr(entry, "title", ""),
                    "url": link,
                    "summary": getattr(entry, "summary", ""),
                    "published_at": published_at,
                    "source": self.name,
                    "source_authority": self.authority,
                    "category_hint": self.category_hint,
                })

            logger.info("RSS 源 %s 抓取 %d 条", self.name, len(entries))
            return entries
        except Exception as e:
            # 单源失败不影响其他源，记录后返回空列表
            logger.error("RSS 源 %s 抓取失败: %s", self.name, e)
            return []
