"""测试科学类替代源 + 二次确认 环球科学 是否真失效。"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.workflow.crawler.rss_spider import RSSSpider


CANDIDATES = [
    # 二次确认 环球科学
    {"name": "环球科学(重测)", "url": "https://plink.anyfeeder.com/weixin/ScientificAmerican", "authority": 0.86},
    # 替代候选
    {"name": "科普中国", "url": "https://plink.anyfeeder.com/weixin/kepuchina", "authority": 0.82},
    {"name": "科学网", "url": "https://plink.anyfeeder.com/weixin/kexueji", "authority": 0.82},
    {"name": " Nature科研", "url": "https://plink.anyfeeder.com/weixin/NatureResearch", "authority": 0.88},
    {"name": "生物谷", "url": "https://plink.anyfeeder.com/weixin/bioon", "authority": 0.78},
    {"name": "丁香园", "url": "https://plink.anyfeeder.com/weixin/DingXiangY", "authority": 0.80},
    {"name": "科研圈", "url": "https://plink.anyfeeder.com/weixin/keyanquan", "authority": 0.82},
    {"name": "环球科学(alt)", "url": "https://plink.anyfeeder.com/weixin/huanqiukexue", "authority": 0.84},
]


async def main() -> int:
    print(f"测试 {len(CANDIDATES)} 个候选源（3s 间隔）...\n")
    for i, src in enumerate(CANDIDATES, 1):
        spider = RSSSpider(src)
        try:
            entries = await spider.fetch()
            n = len(entries)
            mark = "✅" if n > 0 else "⚠️ "
            print(f"  [{i}/{len(CANDIDATES)}] {mark} [{n:>3}条] {src['name']}")
        except Exception as e:
            print(f"  [{i}/{len(CANDIDATES)}] ❌ {src['name']}: {e}")
        if i < len(CANDIDATES):
            await asyncio.sleep(3)
    return 0


if __name__ == "__main__":
    asyncio.run(main())
