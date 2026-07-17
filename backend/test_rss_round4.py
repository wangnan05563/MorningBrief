"""临时脚本：第四轮 RSS 探测，全网搜索后的候选源可达性测试。

候选来自 juejin 订阅人数最多的中文 RSS 源清单 + oryoy 盘点。
分两类测试：
A. 原生 RSS（站点自带，无需转换服务）
B. plink.anyfeeder.com 转换服务（中文媒体/微信公众号/外媒中文版）

测试完成后此脚本会被删除。
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

import feedparser
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# === A. 原生 RSS 候选（站点自带）===
NATIVE = [
    # 综合/新闻
    {"batch": "原生", "category": "综合", "name": "好奇心日报",
     "url": "http://www.qdaily.com/feed.xml"},
    {"batch": "原生", "category": "综合", "name": "雪球今日话题",
     "url": "https://xueqiu.com/hots/topic/rss"},
    {"batch": "原生", "category": "国际", "name": "联合早报-中港台",
     "url": "https://plink.anyfeeder.com/zaobao/realtime/china"},
    {"batch": "原生", "category": "国际", "name": "联合早报-国际",
     "url": "https://plink.anyfeeder.com/zaobao/realtime/world"},
    {"batch": "原生", "category": "国际", "name": "纽约时报中文",
     "url": "http://cn.nytimes.com/rss/news.xml"},
    {"batch": "原生", "category": "国际", "name": "华尔街日报中文",
     "url": "https://cn.wsj.com/zh-hans/rss"},
    # 科技
    {"batch": "原生", "category": "科技", "name": "奇客Solidot",
     "url": "https://www.solidot.org/index.rss"},
    {"batch": "原生", "category": "科技", "name": "IT之家",
     "url": "https://www.ithome.com/rss/"},
    {"batch": "原生", "category": "科技", "name": "月光博客",
     "url": "https://www.williamlong.info/rss.xml"},
    {"batch": "原生", "category": "科技", "name": "极客公园",
     "url": "https://www.geekpark.net/rss"},
    {"batch": "原生", "category": "科技", "name": "小众软件",
     "url": "https://www.appinn.com/feed/"},
    {"batch": "原生", "category": "科技", "name": "异次元软件世界",
     "url": "https://feed.iplaysoft.com/"},
    {"batch": "原生", "category": "科技", "name": "V2EX",
     "url": "https://v2ex.com/index.xml"},
    {"batch": "原生", "category": "科技", "name": "酷壳CoolShell",
     "url": "http://coolshell.cn/feed"},
    {"batch": "原生", "category": "科技", "name": "美团技术团队",
     "url": "https://tech.meituan.com/feed/"},
    {"batch": "原生", "category": "科技", "name": "有赞技术团队",
     "url": "https://tech.youzan.com/rss/"},
    {"batch": "原生", "category": "科技", "name": "HelloGitHub",
     "url": "http://hellogithub.com/rss"},
    {"batch": "原生", "category": "科技", "name": "Engadget中国",
     "url": "https://cn.engadget.com/rss.xml"},
    {"batch": "原生", "category": "科技", "name": "知乎每日精选",
     "url": "https://www.zhihu.com/rss"},
    {"batch": "原生", "category": "科技", "name": "阮一峰",
     "url": "https://www.ruanyifeng.com/blog/atom.xml"},
    # 游戏
    {"batch": "原生", "category": "游戏", "name": "游研社-rss/feed",
     "url": "https://www.yystv.cn/rss/feed"},
    # 财经
    {"batch": "原生", "category": "财经", "name": "DBA Notes",
     "url": "http://dbanotes.net/feed"},
]

# === B. plink.anyfeeder.com 转换服务候选 ===
PLINK = [
    # 综合/时政
    {"batch": "plink", "category": "综合", "name": "澎湃新闻",
     "url": "https://plink.anyfeeder.com/thepaper"},
    {"batch": "plink", "category": "综合", "name": "新京报",
     "url": "https://plink.anyfeeder.com/bjnews"},
    {"batch": "plink", "category": "综合", "name": "央视新闻",
     "url": "https://plink.anyfeeder.com/weixin/cctvnewscenter"},
    {"batch": "plink", "category": "综合", "name": "参考消息",
     "url": "https://plink.anyfeeder.com/weixin/ckxxwx"},
    {"batch": "plink", "category": "综合", "name": "半月谈",
     "url": "https://plink.anyfeeder.com/weixin/banyuetan-weixin"},
    {"batch": "plink", "category": "综合", "name": "Vista看天下",
     "url": "https://plink.anyfeeder.com/weixin/vistaweek"},
    {"batch": "plink", "category": "综合", "name": "新京报-评论",
     "url": "https://plink.anyfeeder.com/weixin/xjbpinglun"},
    {"batch": "plink", "category": "国际", "name": "BBC中文",
     "url": "https://plink.anyfeeder.com/bbc/cn"},
    # 财经
    {"batch": "plink", "category": "财经", "name": "华尔街见闻",
     "url": "https://plink.anyfeeder.com/weixin/wallstreetcn"},
    {"batch": "plink", "category": "财经", "name": "21世纪经济报道",
     "url": "https://plink.anyfeeder.com/weixin/jjbd21"},
    {"batch": "plink", "category": "财经", "name": "经济观察网",
     "url": "https://plink.anyfeeder.com/eeo"},
    {"batch": "plink", "category": "财经", "name": "央视财经",
     "url": "https://plink.anyfeeder.com/weixin/cctvyscj"},
    {"batch": "plink", "category": "财经", "name": "吴晓波频道",
     "url": "https://plink.anyfeeder.com/weixin/wuxiaobopd"},
    {"batch": "plink", "category": "财经", "name": "财新网",
     "url": "https://plink.anyfeeder.com/weixin/caixinwang"},
    {"batch": "plink", "category": "财经", "name": "界面-商业",
     "url": "https://plink.anyfeeder.com/jiemian/business"},
    {"batch": "plink", "category": "财经", "name": "财富中文",
     "url": "https://plink.anyfeeder.com/fortunechina"},
    {"batch": "plink", "category": "财经", "name": "MIT科技评论热榜",
     "url": "https://plink.anyfeeder.com/mittrchina/hot"},
    # 科技
    {"batch": "plink", "category": "科技", "name": "腾讯科技",
     "url": "https://plink.anyfeeder.com/weixin/qqtech"},
    {"batch": "plink", "category": "科技", "name": "CSDN",
     "url": "https://plink.anyfeeder.com/weixin/CSDNnews"},
    {"batch": "plink", "category": "科技", "name": "新智元",
     "url": "https://plink.anyfeeder.com/weixin/AI_era"},
    {"batch": "plink", "category": "科技", "name": "微软研究院AI",
     "url": "https://plink.anyfeeder.com/weixin/MSRAsia"},
    {"batch": "plink", "category": "科技", "name": "InfoQ推荐",
     "url": "https://plink.anyfeeder.com/infoq/recommend"},
    {"batch": "plink", "category": "科技", "name": "Readhub-开发者",
     "url": "https://plink.anyfeeder.com/readhub/technews"},
    {"batch": "plink", "category": "科技", "name": "Readhub-热门话题",
     "url": "https://plink.anyfeeder.com/readhub/topic"},
    {"batch": "plink", "category": "科技", "name": "Linux中国",
     "url": "https://plink.anyfeeder.com/linux.cn"},
    {"batch": "plink", "category": "科技", "name": "雷峰网",
     "url": "https://plink.anyfeeder.com/leiphone"},
    {"batch": "plink", "category": "科技", "name": "果壳网",
     "url": "https://plink.anyfeeder.com/weixin/Guokr42"},
    {"batch": "plink", "category": "科技", "name": "虎嗅",
     "url": "https://plink.anyfeeder.com/weixin/huxiu_com"},
    {"batch": "plink", "category": "科技", "name": "36氪",
     "url": "https://plink.anyfeeder.com/36kr"},
    # 体育
    {"batch": "plink", "category": "体育", "name": "新浪体育",
     "url": "https://plink.anyfeeder.com/weixin/sports_sina"},
    # 娱乐
    {"batch": "plink", "category": "娱乐", "name": "三联生活周刊",
     "url": "https://plink.anyfeeder.com/weixin/lifeweek"},
    # 健康
    {"batch": "plink", "category": "健康", "name": "医学界",
     "url": "https://plink.anyfeeder.com/weixin/yixuejiezazhi"},
    # 教育
    {"batch": "plink", "category": "教育", "name": "MOOC",
     "url": "https://plink.anyfeeder.com/weixin/mooc"},
    # 文化/读书
    {"batch": "plink", "category": "综合", "name": "十点读书",
     "url": "https://plink.anyfeeder.com/weixin/duhaoshu"},
    {"batch": "plink", "category": "综合", "name": "有书",
     "url": "https://plink.anyfeeder.com/weixin/youshucc"},
    {"batch": "plink", "category": "综合", "name": "读库小报",
     "url": "https://plink.anyfeeder.com/weixin/dukuxiaobao"},
    # 国际
    {"batch": "plink", "category": "国际", "name": "路透中文",
     "url": "https://plink.anyfeeder.com/reuters/cn"},
    {"batch": "plink", "category": "国际", "name": "法广中文",
     "url": "https://plink.anyfeeder.com/rfi/cn"},
    {"batch": "plink", "category": "国际", "name": "美国之音",
     "url": "https://plink.anyfeeder.com/voa/chinese"},
    {"batch": "plink", "category": "国际", "name": "纽约时报",
     "url": "https://plink.anyfeeder.com/nytimes/cn"},
    {"batch": "plink", "category": "国际", "name": "华尔街日报",
     "url": "https://plink.anyfeeder.com/wsj/cn"},
    # iDaily 环球视野
    {"batch": "plink", "category": "国际", "name": "iDaily环球视野",
     "url": "https://plink.anyfeeder.com/idaily/today"},
    # 双语/学习
    {"batch": "plink", "category": "教育", "name": "中国日报双语",
     "url": "https://plink.anyfeeder.com/chinadaily/dual"},
    {"batch": "plink", "category": "教育", "name": "一天一篇经济学人",
     "url": "https://plink.anyfeeder.com/weixin/Economist_fans"},
    # 知识科普
    {"batch": "plink", "category": "综合", "name": "知识分子",
     "url": "https://plink.anyfeeder.com/weixin/The-Intellectual"},
    {"batch": "plink", "category": "综合", "name": "环球科学",
     "url": "https://plink.anyfeeder.com/weixin/ScientificAmerican"},
    {"batch": "plink", "category": "综合", "name": "地球知识局",
     "url": "https://plink.anyfeeder.com/weixin/diqiuzhishiju"},
    {"batch": "plink", "category": "综合", "name": "国家人文历史",
     "url": "https://plink.anyfeeder.com/weixin/gjrwls"},
    {"batch": "plink", "category": "综合", "name": "中国国家地理",
     "url": "https://plink.anyfeeder.com/weixin/dili360"},
    # 安全
    {"batch": "plink", "category": "科技", "name": "FreeBuf安全",
     "url": "https://plink.anyfeeder.com/freebuf"},
    # 知乎日报
    {"batch": "plink", "category": "综合", "name": "知乎日报",
     "url": "https://plink.anyfeeder.com/zhihu/daily"},
    # 数字尾巴
    {"batch": "plink", "category": "科技", "name": "数字尾巴",
     "url": "https://plink.anyfeeder.com/dgtle"},
    # 看雪/喷嚏等
    {"batch": "plink", "category": "综合", "name": "喷嚏-铂程斋",
     "url": "https://plink.anyfeeder.com/dapenti/xilei"},
]


async def test_one(src: dict) -> dict:
    result = {**src, "status": None, "entries": 0, "sample_titles": [], "error": None}
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": UA},
            follow_redirects=True,
        ) as client:
            resp = await client.get(src["url"])
            result["status"] = resp.status_code
            resp.raise_for_status()
            xml_content = resp.text

        feed = await asyncio.to_thread(feedparser.parse, xml_content)
        result["entries"] = len(feed.entries)
        for entry in feed.entries[:1]:
            title = getattr(entry, "title", "")
            if title:
                result["sample_titles"].append(title[:45])
    except Exception as e:
        msg = str(e)
        if len(msg) > 55:
            msg = msg[:53] + ".."
        result["error"] = f"{type(e).__name__}: {msg}"
    return result


async def main():
    all_candidates = NATIVE + PLINK
    print(f"第四轮测试 {len(all_candidates)} 个候选（原生 {len(NATIVE)} + plink {len(PLINK)}）")
    print(f"\n{'批次':<4} {'品类':<6} {'名称':<20} {'HTTP':<6} {'条目':<5} {'错误':<30} 样本标题")
    print("-" * 145)

    results = await asyncio.gather(*[test_one(s) for s in all_candidates])

    for batch in ["原生", "plink"]:
        for r in results:
            if r["batch"] != batch:
                continue
            err = r["error"] or ""
            sample = r["sample_titles"][0] if r["sample_titles"] else ""
            print(f"{r['batch']:<4} {r['category']:<6} {r['name']:<20} {str(r['status']):<6} {r['entries']:<5} {err:<30} {sample}")
        print()

    ok = [r for r in results if not r["error"] and r["entries"] > 0]
    print("=" * 145)
    print(f"可用源: {len(ok)} 个")
    print("=" * 145)
    for r in ok:
        print(f"  [{r['batch']}/{r['category']}] {r['name']:<20}  →  {r['url']}  ({r['entries']} 条)")
    return 0


if __name__ == "__main__":
    asyncio.run(main())
