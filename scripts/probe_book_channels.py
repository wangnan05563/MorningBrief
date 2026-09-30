#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T00601：每日听书频道「资料收集渠道」候选源实测探针。
用与 crawler 同链路（requests + 标准库 json/xml）验证各候选渠道是否可用、是否含中文内容。
"""
import json
import concurrent.futures as cf
import requests

UA = "MorningBriefBot/1.0"
TIMEOUT = 25


def get_json(url, params=None):
    r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=TIMEOUT)
    return r.status_code, (r.json() if r.status_code == 200 else None), r.content


def probe(name, fn):
    try:
        return (name,) + tuple(fn())
    except Exception as e:
        return ("ERR", f"{type(e).__name__}: {str(e)[:70]}", "")


def p_gutendex_zh():
    """Gutendex（Project Gutenberg 的 JSON API）中文书目"""
    st, data, _ = get_json("https://gutendex.com/books", {"languages": "zh"})
    n = (data or {}).get("count")
    sample = ""
    if data and data.get("results"):
        b = data["results"][0]
        sample = f'{b.get("title","")[:30]} / authors={len(b.get("authors") or [])} 格式={list((b.get("formats") or {}).keys())[:2]}'
    return (st, f"count={n}", sample)


def p_gutendex_en():
    st, data, _ = get_json("https://gutendex.com/books", None)
    return (st, f"count={(data or {}).get('count')}", "")


def p_ctext_api():
    """CTEXT 中国哲学书电子化计划 官方 JSON API"""
    st, data, _ = get_json("https://api.ctext.org/searchtexts", {"title": "论语"})
    n = len(data) if isinstance(data, list) else (len(data or {}) if data else 0)
    return (st, f"命中条目={n}", str(data)[:90] if data else "")


def p_wikisource_zh():
    """中文维基文库 MediaWiki API（分类成员 + 全文提取）"""
    st, data, _ = get_json("https://zh.wikisource.org/w/api.php", {
        "action": "query", "list": "search", "srsearch": "论语",
        "srlimit": 5, "format": "json",
    })
    hits = ((data or {}).get("query") or {}).get("search") or []
    titles = [h.get("title") for h in hits][:3]
    return (st, f"检索命中={len(hits)}", str(titles))


def p_wikisource_extract():
    """中文维基文库：正文提取（Extracts 扩展）——验证能否拿到「篇章全文」"""
    st, data, _ = get_json("https://zh.wikisource.org/w/api.php", {
        "action": "query", "prop": "extracts", "explaintext": 1,
        "titles": "論語/學而第一", "format": "json",
    })
    pages = ((data or {}).get("query") or {}).get("pages") or {}
    text = ""
    for p in pages.values():
        text = (p.get("extract") or "").strip()
    return (st, f"正文字数={len(text)}", text[:80].replace("\n", " "))


def p_openlibrary_search():
    """Open Library 搜索 API（跨语言书目元数据）"""
    st, data, _ = get_json("https://openlibrary.org/search.json", {"q": "论语", "limit": 3})
    return (st, f"numFound={(data or {}).get('numFound')}",
            str([d.get("title") for d in ((data or {}).get("docs") or [])][:3]))


def p_standard_ebooks_opds():
    """Standard Ebooks OPDS/Atom feed（公版 EPUB 目录）"""
    r = requests.get("https://standardebooks.org/feeds/all.atom", headers={"User-Agent": UA}, timeout=TIMEOUT)
    body = r.content[:200]
    return (r.status_code, f"len={len(r.content)} is_feed={b'<feed' in r.content[:500]}", str(body[:80]))


def p_internet_archive():
    """Internet Archive 高级检索 API（公版扫描本，可下载全文）"""
    st, data, _ = get_json("https://archive.org/advancedsearch.php", {
        "q": "collection:gutenberg AND mediatype:texts", "fl[]": "identifier,title,language",
        "rows": 3, "output": "json",
    })
    docs = ((data or {}).get("response") or {}).get("docs") or []
    return (st, f"返回={len(docs)}", str([d.get("title") for d in docs][:2])[:90])


def p_opds_gutendex_feeds():
    """Project Gutenberg 官方 RDF/OPDS 入口（验证 feed 类入口是否可用）"""
    r = requests.get("https://www.gutenberg.org/cache/epub/feeds/", headers={"User-Agent": UA}, timeout=TIMEOUT)
    return (r.status_code, f"len={len(r.content)}", r.content[:70].decode("utf-8", "ignore"))


PROBES = [
    ("Gutendex-中文书目", p_gutendex_zh),
    ("Gutendex-全量", p_gutendex_en),
    ("CTEXT-官方API", p_ctext_api),
    ("中文维基文库-检索", p_wikisource_zh),
    ("中文维基文库-正文提取", p_wikisource_extract),
    ("OpenLibrary-书目检索", p_openlibrary_search),
    ("StandardEbooks-Atom", p_standard_ebooks_opds),
    ("InternetArchive-检索", p_internet_archive),
    ("Gutenberg-RDF入口", p_opds_gutendex_feeds),
]

if __name__ == "__main__":
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        for res in ex.map(lambda nf: probe(nf[0], nf[1]), PROBES):
            res = (list(res) + [""] * 4)[:4]  # 统一补齐为 4 元组，避免个别探针少返回字段导致解包失败
            n, st, info, sample = res
            print(f"{n:24s} | HTTP={st} | {info}\n{'':24s} | 样例: {sample[:110]}")
