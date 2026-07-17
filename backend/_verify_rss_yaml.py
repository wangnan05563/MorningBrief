"""端到端验证 rss.yaml 全部 RSS 源可达性。

复用项目 RSSSpider.fetch() 与 load_rss_sources()，与生产环境一致。
采用串行模式（间隔 0.5s），与 crawler 实际单源串行抓取一致，避免 plink 并发限流误判。
"""
import asyncio
import sys
from pathlib import Path

# 将 backend/ 加入 sys.path，使 app.* 可导入
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.services.rss_source_service import load_rss_sources
from app.workflow.crawler.rss_spider import RSSSpider


async def main() -> int:
    sources = load_rss_sources()
    if not sources:
        print("[FAIL] rss.yaml 加载为空或不存在")
        return 2

    print(f"共 {len(sources)} 个 RSS 源，开始端到端验证（串行 + 0.5s 间隔）...\n")

    ok, empty, fail = [], [], []
    for i, src in enumerate(sources, 1):
        spider = RSSSpider(src)
        try:
            entries = await spider.fetch()
            n = len(entries)
            if n > 0:
                ok.append((src["name"], src["url"], n))
                print(f"  [{i:>2}/{len(sources)}] ✅ [{n:>3}条] {src['name']}")
            else:
                empty.append((src["name"], src["url"]))
                print(f"  [{i:>2}/{len(sources)}] ⚠️  0 条  {src['name']}")
        except Exception as e:
            fail.append((src["name"], src["url"], str(e)))
            print(f"  [{i:>2}/{len(sources)}] ❌ 错误  {src['name']}: {e}")
        # 0.5s 间隔，避免 plink 限流
        if i < len(sources):
            await asyncio.sleep(0.5)

    print(f"\n=== 汇总 ===")
    print(f"  总 {len(sources)} | 可达 {len(ok)} | 0 条 {len(empty)} | 失败 {len(fail)}")

    if empty:
        print(f"\n=== ⚠️ HTTP 200 但 0 条目 ===")
        for name, url in empty:
            print(f"  {name}  →  {url}")

    if fail:
        print(f"\n=== ❌ 抓取失败 ===")
        for name, url, err in fail:
            print(f"  {name}  →  {url}  ({err})")

    return 0 if not fail and not empty else 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)

