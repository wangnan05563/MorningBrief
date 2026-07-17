"""临时脚本：探测游民星空/3DM/游侠网 真实 RSS 路径 + 测试更多 RSSHub 镜像。

第一轮测试结论：
- rsshub.app / rsshub.rssforever.com / rss.shab.fun 均不可达
- 机核原生 https://www.gcores.com/rss 可用（20 条）
- 游民星空 rss.gamersky.com DNS 失败，需尝试主域
- 3DM /news.xml 404，需找正确路径
- 游侠网 /rss.xml 404，需找正确路径

本脚本测试可能的 RSS 路径变体和更多 RSSHub 镜像。
测试完成后此脚本会被删除。
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

import feedparser
import httpx

UA = "MorningBriefBot/1.0 (+https://github.com/xxx/MorningBrief)"

CANDIDATES = [
    # === 游民星空主域 RSS 路径变体 ===
    {"group": "gamersky", "name": "游民星空-主域/rss/news.xml",
     "url": "https://www.gamersky.com/rss/news.xml"},
    {"group": "gamersky", "name": "游民星空-主域/rss.xml",
     "url": "https://www.gamersky.com/rss.xml"},
    {"group": "gamersky", "name": "游民星空-主域/news/rss.xml",
     "url": "https://www.gamersky.com/news/rss.xml"},

    # === 3DM RSS 路径变体 ===
    {"group": "3dm", "name": "3DM-/rss/",
     "url": "https://www.3dmgame.com/rss/"},
    {"group": "3dm", "name": "3DM-/rss/index.xml",
     "url": "https://www.3dmgame.com/rss/index.xml"},
    {"group": "3dm", "name": "3DM-/news/rss.xml",
     "url": "https://news.3dmgame.com/rss.xml"},
    {"group": "3dm", "name": "3DM-news-/rss.xml",
     "url": "https://news.3dmgame.com/rss/"},

    # === 游侠网 RSS 路径变体 ===
    {"group": "ali213", "name": "游侠网-/rss/",
     "url": "https://www.ali213.net/rss/"},
    {"group": "ali213", "name": "游侠网-/news/rss.xml",
     "url": "https://news.ali213.net/rss.xml"},
    {"group": "ali213", "name": "游侠网-/rss/news.xml",
     "url": "https://www.ali213.net/rss/news.xml"},

    # === 其他 RSSHub 镜像（覆盖更全）===
    {"group": "mirror", "name": "rsshub.feeded.xyz-gamersky",
     "url": "https://rsshub.feeded.xyz/gamersky/news"},
    {"group": "mirror", "name": "rsshub.feeded.xyz-3dm",
     "url": "https://rsshub.feeded.xyz/3dm/news"},
    {"group": "mirror", "name": "rss.injahow.cn-gamersky",
     "url": "https://rss.injahow.cn/gamersky/news"},
    {"group": "mirror", "name": "rsshub.moeyy.xyz-gamersky",
     "url": "https://rsshub.moeyy.xyz/gamersky/news"},
    {"group": "mirror", "name": "rsshub.pseudoyu.com-gamersky",
     "url": "https://rsshub.pseudoyu.com/gamersky/news"},
]


async def test_one(src: dict) -> dict:
    """测试单个源。"""
    result = {**src, "status": None, "entries": 0, "sample_titles": [], "error": None}
    try:
        async with httpx.AsyncClient(
            timeout=12.0,
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            resp = await client.get(src["url"])
            result["status"] = resp.status_code
            resp.raise_for_status()
            xml_content = resp.text

        feed = await asyncio.to_thread(feedparser.parse, xml_content)
        result["entries"] = len(feed.entries)
        for entry in feed.entries[:2]:
            result["sample_titles"].append(getattr(entry, "title", "")[:50])
    except Exception as e:
        msg = str(e)
        if len(msg) > 70:
            msg = msg[:68] + ".."
        result["error"] = f"{type(e).__name__}: {msg}"
    return result


async def main():
    print(f"{'分组':<12} {'名称':<40} {'HTTP':<6} {'条目':<6} {'错误':<35} 样本标题")
    print("-" * 160)
    results = await asyncio.gather(*[test_one(s) for s in CANDIDATES])

    ok_sources = []
    by_group = {}
    for r in results:
        by_group.setdefault(r["group"], []).append(r)

    for group in ["gamersky", "3dm", "ali213", "mirror"]:
        for r in by_group.get(group, []):
            err = r["error"] or ""
            sample = r["sample_titles"][0] if r["sample_titles"] else ""
            print(f"{r['group']:<12} {r['name']:<40} {str(r['status']):<6} {r['entries']:<6} {err:<35} {sample}")
            if not r["error"] and r["entries"] > 0:
                ok_sources.append(r)

    print("-" * 160)
    print(f"可用源（HTTP 200 + 条目 > 0）: {len(ok_sources)} 个")
    for s in ok_sources:
        print(f"  [{s['group']}] {s['name']}  →  {s['url']}  ({s['entries']} 条)")
    return 0 if ok_sources else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
