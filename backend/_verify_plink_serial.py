"""串行重测 plink.anyfeeder.com 源，排除并发限流假阳性。

并发放宽至 5 时 plink 出现 0 条目，怀疑是该服务对并发敏感。
串行测试加 1.5s 间隔，确认是否真的不可达。
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.services.rss_source_service import load_rss_sources
from app.workflow.crawler.rss_spider import RSSSpider


PLINK_NAMES = {
    "联合早报-国际", "华尔街日报-中文", "华尔街见闻", "财新网",
    "MIT科技评论热榜", "CSDN", "新智元", "果壳网",
    "中国国家地理", "环球科学", "MOOC", "一天一篇经济学人",
}


async def main() -> int:
    all_sources = load_rss_sources()
    plink_sources = [s for s in all_sources if s["name"] in PLINK_NAMES]
    print(f"串行重测 {len(plink_sources)} 个 plink 源（间隔 1.5s）...\n")

    recovered, still_bad = [], []
    for i, src in enumerate(plink_sources, 1):
        spider = RSSSpider(src)
        try:
            entries = await spider.fetch()
            n = len(entries)
            if n > 0:
                recovered.append((src["name"], src["url"], n))
                print(f"  [{i:>2}/{len(plink_sources)}] ✅ [{n:>3}条] {src['name']}")
            else:
                still_bad.append((src["name"], src["url"], "0 entries"))
                print(f"  [{i:>2}/{len(plink_sources)}] ⚠️  0 条  {src['name']}")
        except Exception as e:
            still_bad.append((src["name"], src["url"], str(e)))
            print(f"  [{i:>2}/{len(plink_sources)}] ❌ 错误  {src['name']}: {e}")
        # 间隔避免限流
        if i < len(plink_sources):
            await asyncio.sleep(1.5)

    print(f"\n汇总: 恢复 {len(recovered)} | 仍异常 {len(still_bad)}")
    if still_bad:
        print("\n仍异常源：")
        for name, url, msg in still_bad:
            print(f"  {name}  →  {url}  ({msg})")
    return 0


if __name__ == "__main__":
    asyncio.run(main())
