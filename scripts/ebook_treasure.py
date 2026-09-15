#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ebook-treasure-chest 书目检索工具（T00601/T00603：听书频道资料渠道接入）

定位：把「**找书**」自动化——在 jbiaojerry/ebook-treasure-chest 的 1000 个分类清单里按关键词
检索书名/作者，直接给出下载链接；「**取件**」由人工完成。

为什么取件不自动化（实测结论，2026-09-15）：
  仓库所有下载链接指向 **城通网盘**（url89.ctfile.com/f/<id>?p=<提取参数>），实测 GET 返回
  4.7KB 的 JS 交互落地页、HTML 内无任何下载直链（需页面交互/客户端，免费通道另有等待与限速），
  故无法稳定程序化取件。拿到 EPUB 后走既有上传链路即可入库（T00585 支持 .epub/.docx/.html/.txt/.md）。

⚠️ 授权提示（转载自来源仓库自带声明，非本工具观点）：
  「本站内容均从网上搜集，版权归著作人及版权方所有……下载链接仅供宽带测试研究用途，
   请下载后在 24 小时内删除，**请勿用于商业目的**。请支持正版！」
  用于对外发布的频道内容前，请自行确认授权。

用法：
  python scripts/ebook_treasure.py list-categories
  python scripts/ebook_treasure.py search 论语 --limit 10
  python scripts/ebook_treasure.py search 王小波 --category 文学 --json
  python scripts/ebook_treasure.py selftest        # 解析器自测（无需联网）

缓存：分类 md 落在 runtime/cache/ebook_treasure/（单文件 150-250KB，避免重复拉取）
"""
import argparse
import json
import os
import re
import sys

REPO = "jbiaojerry/ebook-treasure-chest"
BRANCH = "main"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime", "cache", "ebook_treasure")
UA = {"User-Agent": "MorningBriefBot/1.0 (+book-channel research)"}

# 表格行：| 书名 | 作者 | [下载](url) |
_ROW_RE = re.compile(r"^\|\s*(?P<title>[^|]+?)\s*\|\s*(?P<author>[^|]*?)\s*\|\s*\[[^\]]*\]\((?P<url>https?://[^)]+)\)")


def _fetch(path: str, use_cache: bool = True) -> str:
    """拉取仓库文件（默认走本地缓存）。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, path.replace("/", "__"))
    if use_cache and os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
        with open(cache_file, "r", encoding="utf-8") as f:
            return f.read()
    import requests  # 延迟导入：--selftest 无需依赖

    r = requests.get(RAW + path, headers=UA, timeout=40)
    r.raise_for_status()
    text = r.text
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def list_categories() -> list:
    """从 README 解析全部分类名（md/<分类>.md）。"""
    readme = _fetch("README.md")
    cats = sorted(set(re.findall(r"md/([^)\s]+?)\.md", readme)))
    return cats


def parse_category(md_text: str) -> list:
    """解析分类 md 的 Markdown 表格 → [{title, author, url}]。"""
    books = []
    for line in md_text.splitlines():
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        title = m.group("title").strip()
        # 跳过表头/分隔行
        if not title or title in ("书名",) or set(title) <= set("-: "):
            continue
        books.append({
            "title": title,
            "author": m.group("author").strip(),
            "url": m.group("url").strip(),
        })
    return books


def search(keyword: str, category: str = None, limit: int = 20, use_cache: bool = True) -> dict:
    """按关键词检索书名/作者。category 为空时按分类名精确匹配，否则全量扫描（较慢）。"""
    kw = (keyword or "").strip().lower()
    cats = [category] if category else list_categories()
    hits = []
    scanned = []
    for c in cats:
        try:
            text = _fetch(f"md/{c}.md", use_cache=use_cache)
        except Exception as e:  # 单分类失败不影响整体
            continue
        scanned.append(c)
        for b in parse_category(text):
            if kw in b["title"].lower() or kw in (b["author"] or "").lower():
                b["category"] = c
                hits.append(b)
                if len(hits) >= limit:
                    return {"keyword": keyword, "scanned_categories": scanned, "hits": hits}
    return {"keyword": keyword, "scanned_categories": scanned, "hits": hits}


def _selftest() -> int:
    """解析器自测（离线，用内置样例）。"""
    sample = """
    # 版权声明
    | 书名 | 作者 | epub/mobi/azw3 |
    | --- | --- | --- |
    | 磨坊信札（作家榜经典文库） | 阿尔封斯・都德 | [下载](https://url89.ctfile.com/f/31084289-1375491025-903fa5?p=8866) |
    | 百年百部红色经典系列：第一辑（套装共20册） | 周梅森等 | [下载](https://url89.ctfile.com/f/31084289-1375491169-00db51?p=8866) |
    """
    books = parse_category(sample)
    assert len(books) == 2, books
    assert books[0]["title"].startswith("磨坊信札"), books[0]
    assert books[0]["author"] == "阿尔封斯・都德", books[0]
    assert books[0]["url"].startswith("https://url89.ctfile.com/f/"), books[0]
    assert parse_category("| 书名 | 作者 | x |\n| --- | --- | --- |") == [], "表头应被跳过"
    print("selftest OK：解析器可正确提取 书名/作者/下载链接，并跳过表头")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ebook-treasure-chest 书目检索工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-categories", help="列出全部 1000 个分类名")
    sp = sub.add_parser("search", help="按关键词检索书名/作者")
    sp.add_argument("keyword")
    sp.add_argument("--category", default=None, help="限定分类（如 文学），不传则全量扫描")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--json", action="store_true", help="JSON 输出")
    sp.add_argument("--no-cache", action="store_true", help="强制重新拉取分类文件")
    sub.add_parser("selftest", help="解析器离线自测")

    args = ap.parse_args()
    if args.cmd == "selftest":
        return _selftest()
    if args.cmd == "list-categories":
        cats = list_categories()
        print(f"共 {len(cats)} 个分类：")
        for c in cats:
            print(" ", c)
        return 0

    res = search(args.keyword, args.category, args.limit, use_cache=not args.no_cache)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    print(f"关键词「{args.keyword}」命中 {len(res['hits'])} 条（扫描 {len(res['scanned_categories'])} 个分类）")
    for b in res["hits"]:
        print(f"  [{b['category']}] {b['title']} / {b['author']}\n      {b['url']}")
    if res["hits"]:
        print("\n提示：链接为城通网盘（无直链），需人工下载；拿到 EPUB 后走素材上传入库（T00585）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
