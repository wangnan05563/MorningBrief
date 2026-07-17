"""用 3s 间隔重测 8 个间歇性失败源，确认是否为 plink 限流。

plink.anyfeeder.com 对单 IP 的会话级限流较敏感。
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.workflow.crawler.rss_spider import RSSSpider


# 8 个间歇性失败源
SOURCES = [
    {"name": "联合早报-中港台", "url": "https://plink.anyfeeder.com/zaobao/realtime/china", "authority": 0.88},
    {"name": "央视财经", "url": "https://plink.anyfeeder.com/weixin/cctvyscj", "authority": 0.88},
    {"name": "V2EX", "url": "https://v2ex.com/index.xml", "authority": 0.76},
    {"name": "中国国家地理", "url": "https://plink.anyfeeder.com/weixin/dili360", "authority": 0.84},
    {"name": "环球科学", "url": "https://plink.anyfeeder.com/weixin/ScientificAmerican", "authority": 0.86},
    {"name": "MOOC", "url": "https://plink.anyfeeder.com/weixin/mooc", "authority": 0.80},
    {"name": "一天一篇经济学人", "url": "https://plink.anyfeeder.com/weixin/Economist_fans", "authority": 0.82},
    {"name": "有书", "url": "https://plink.anyfeeder.com/weixin/youshucc", "authority": 0.78},
]


async def main() -> int:
    print(f"用 3s 间隔重测 {len(SOURCES)} 个源...\n")
    for i, src in enumerate(SOURCES, 1):
        spider = RSSSpider(src)
        try:
            entries = await spider.fetch()
            n = len(entries)
            mark = "✅" if n > 0 else "⚠️ "
            print(f"  [{i}/{len(SOURCES)}] {mark} [{n:>3}条] {src['name']}")
        except Exception as e:
            print(f"  [{i}/{len(SOURCES)}] ❌ {src['name']}: {e}")
        if i < len(SOURCES):
            await asyncio.sleep(3)
    return 0


if __name__ == "__main__":
    asyncio.run(main())
