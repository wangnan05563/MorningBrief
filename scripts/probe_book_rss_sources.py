#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T00581：书籍 RSS 源可用性探针（与 crawler 相同的 requests + feedparser 链路）。"""
import sys
import concurrent.futures as cf
import requests
import feedparser

UA = "MorningBriefBot/1.0"
TIMEOUT = 20

URLS = [
    # --- 存量 6 源 ---
    ("存量", "豆瓣读书-最新书评", "https://www.douban.com/feed/review/book"),
    ("存量", "豆瓣读书-新书速递", "https://www.douban.com/feed/latest"),
    ("存量", "书格-古籍善本", "https://new.shuge.org/feed/"),
    ("存量", "Kindle伴侣-电子书资讯", "https://bookfere.com/feed"),
    ("存量", "看理想-人文谈话", "https://www.vistopia.com.tw/rss"),
    ("存量", "机核-游戏文化播客", "https://www.gcores.com/rss"),
    # --- 候选新源 ---
    ("候选", "古登堡计划-新书", "https://www.gutenberg.org/feed/"),
    ("候选", "StandardEbooks-新书", "https://standardebooks.org/feeds/books/new-releases"),
    ("候选", "LibriVox-最新有声书", "https://librivox.org/rss/latest_releases"),
    ("候选", "FT中文网-Book", "https://www.ftchinese.com/rss/book"),
    ("候选", "少数派-主feed", "https://sspai.com/feed"),
    ("候选", "豆瓣-读书tag", "https://www.douban.com/feed/tag/%E8%AF%BB%E4%B9%A6"),
    ("候选", "新京报-书评", "https://www.bjnews.com.cn/rss/book"),
    ("候选", " sspai-读书tag", "https://sspai.com/tag/%E8%AF%BB%E4%B9%A6/feed"),
    # --- 第二批：搜索所得 ---
    ("候选", "新京报书评周刊-rsshub", "https://rsshub.app/weixin/ibookreview"),
    ("候选", "新京报书评周刊-anyfeeder", "https://plink.anyfeeder.com/weixin/ibookreview"),
    ("候选", "上海书评-feedx", "https://feedx.net/rss/shanghaishuping.xml"),
    ("候选", "四季书评-官网", "https://www.4sbooks.com/feed"),
    ("候选", "单读-anyfeeder", "https://plink.anyfeeder.com/weixin/dandureading"),
    ("候选", "看理想-anyfeeder", "https://plink.anyfeeder.com/weixin/ikanlixiang"),
    ("候选", "看理想-官方cn", "https://www.vistopia.com.cn/rss"),
    ("候选", "左岸读书-rsshub", "https://rsshub.app/zreading"),
    ("候选", "豆瓣读书公众号-rsshub", "https://rsshub.app/weixin/doubanbooks"),
    ("候选", "LitHub", "https://lithub.com/feed/"),
    ("候选", "Guardian-Books", "https://www.theguardian.com/books/rss"),
    ("候选", "OpenCulture", "https://www.openculture.com/feed"),
    ("候选", "Tor-com", "https://www.tor.com/feed/"),
    ("候选", "豆瓣-新书速递book", "https://book.douban.com/feed/latest"),
]


def probe(item):
    kind, name, url = item
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        feed = feedparser.parse(r.content)
        entries = feed.entries or []
        title = (feed.feed.get("title") or "")[:40]
        e0 = (entries[0].get("title") or "")[:40] if entries else ""
        ok = r.status_code == 200 and len(entries) > 0
        return (kind, name, url, r.status_code, len(entries), title, e0, ok)
    except Exception as e:
        return (kind, name, url, "ERR", 0, type(e).__name__, str(e)[:60], False)


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    items = [u for u in URLS if not only or only in u[1] or only in u[2]]
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for res in ex.map(probe, items):
            print("%s | %s | %s\n    http=%s entries=%s feed=%r entry0=%r -> %s"
                  % (res[0], res[1], res[2], res[3], res[4], res[5], res[6], "OK" if res[7] else "FAIL"))
