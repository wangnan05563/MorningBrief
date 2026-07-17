"""测试替代 URL 与新候选源。

4 个仍异常源尝试替代 URL：
- 联合早报-国际 → 试 main /zaobao/world、试 /zaobao/realtime/china
- 财新网 → 试 caixin 直接 RSS
- 新智元 → 试 AI 科技评论 plink
- 果壳网 → 试科学网博客

新候选源（来自全网搜索，全部待验证）：
- 知乎每日精选、阮一峰、极客公园、虎嗅、Python工匠、月光博客、Mac玩儿法
- 云风BLOG、Decohack、卡瓦邦噶、离别歌、风雪之隅、理想生活实验室、每日一文
- 联合早报-中港台、知乎日报、每日一文
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.workflow.crawler.rss_spider import RSSSpider


# 替代 URL + 新候选源
CANDIDATES = [
    # 替代 4 个失效源
    ("联合早报-国际(alt1)", "https://plink.anyfeeder.com/zaobao/realtime/china"),
    ("联合早报-国际(alt2)", "https://plink.anyfeeder.com/zaobao/world"),
    ("财新网(alt)", "http://rss.caixin.com/feed.jsp"),
    ("财新网(alt2)", "https://rss.caixin.com/feed"),
    ("AI科技评论(替代新智元)", "https://plink.anyfeeder.com/weixin/aitechtalk"),
    ("科学网博客(替代果壳)", "https://plink.anyfeeder.com/weixin/kexueji"),
    ("知识分子(替代果壳)", "https://plink.anyfeeder.com/weixin/The-Intellectual"),
    # 新增候选源
    ("知乎每日精选", "https://www.zhihu.com/rss"),
    ("阮一峰的网络日志", "https://www.ruanyifeng.com/blog/atom.xml"),
    ("极客公园", "http://www.geekpark.net/rss"),
    ("虎嗅网", "https://www.huxiu.com/rss/0.xml"),
    ("Python工匠", "https://www.zlovezl.cn/feeds/latest/"),
    ("月光博客", "http://www.williamlong.info/rss.xml"),
    ("Mac玩儿法", "http://www.waerfa.com/feed"),
    ("云风的BLOG", "http://blog.codingnow.com/atom.xml"),
    ("Decohack", "https://www.decohack.com/feed"),
    ("卡瓦邦噶", "https://www.kawabangga.com/feed"),
    ("离别歌", "https://www.leavesongs.com/feed/"),
    ("风雪之隅", "http://www.laruence.com/feed"),
    ("理想生活实验室", "https://www.toodaylab.com/feed"),
    ("每日一文", "http://node2.feed43.com/mryw.xml"),
    ("联合早报-中港台", "https://plink.anyfeeder.com/zaobao/realtime/china"),
    ("知乎日报", "https://feeds.feedburner.com/zhihu-daily"),
    ("南方周末", "https://plink.anyfeeder.com/infzm/2"),
    ("极客公园-快讯", "https://plink.anyfeeder.com/geekpark"),
    ("丁香园", "https://plink.anyfeeder.com/weixin/DingXiangY"),
    ("健康时报", "https://plink.anyfeeder.com/weixin/jkbsb"),
    ("新华视点", "https://plink.anyfeeder.com/weixin/xhsd"),
    ("央视新闻", "https://plink.anyfeeder.com/weixin/cctvxw"),
    ("人民日报", "https://plink.anyfeeder.com/weixin/rmrb"),
    ("三联生活周刊", "https://plink.anyfeeder.com/weixin/lifeweek"),
    ("南方周末-人物", "https://plink.anyfeeder.com/weixin/infzm"),
    ("虎嗅-24小时", "https://plink.anyfeeder.com/weixin/huxiu"),
    ("PingWest品玩", "https://plink.anyfeeder.com/weixin/pingwest"),
    ("36氪-每日资讯", "https://plink.anyfeeder.com/weixin/36kr"),
    ("极客公园-首页", "http://www.geekpark.net/rss/"),
    ("CnBeta", "https://rss.cnbeta.com/rss"),
    ("推酷", "https://www.tuicool.com/mags"),
]


async def test_one(name: str, url: str, sem: asyncio.Semaphore) -> tuple[str, str, int, str]:
    async with sem:
        src = {"name": name, "url": url, "authority": 0.5}
        spider = RSSSpider(src)
        try:
            entries = await spider.fetch()
            n = len(entries)
            status = "ok" if n > 0 else "empty"
            return name, url, n, status
        except Exception as e:
            return name, url, 0, f"error: {e}"


async def main() -> int:
    print(f"测试 {len(CANDIDATES)} 个候选源（并发 3，避免限流）...\n")
    sem = asyncio.Semaphore(3)
    results = await asyncio.gather(*[test_one(n, u, sem) for n, u in CANDIDATES])

    ok, empty, fail = [], [], []
    for name, url, count, status in results:
        if status == "ok":
            ok.append((name, url, count))
        elif status == "empty":
            empty.append((name, url))
        else:
            fail.append((name, url, status))

    print("=== ✅ 可用 ===")
    for name, url, count in ok:
        print(f"  [{count:>3}条] {name}  →  {url}")

    print(f"\n=== ⚠️  HTTP 200 但 0 条 ===")
    for name, url in empty:
        print(f"  {name}  →  {url}")

    print(f"\n=== ❌ 失败 ===")
    for name, url, status in fail:
        print(f"  {name}  →  {url}")
        print(f"      {status}")

    print(f"\n汇总: 可用 {len(ok)} | 0 条 {len(empty)} | 失败 {len(fail)}")
    return 0


if __name__ == "__main__":
    asyncio.run(main())
