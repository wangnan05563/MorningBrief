"""全文源爬虫（fulltext_spider）单元测试（T00603）。

用 monkeypatch 替换 requests 层，不依赖真实网络：
- wikisource：MediaWiki extracts 响应 → 章节条目（标题/URL/正文/预取标记）；
- gutendex：检索解析 → text/plain 下载 → 分章 + max_chapters 截断 + 去重键唯一性；
- 未知 provider 报错；缺 pages 配置报错；
- book_fulltext.yaml 加载器（含缺 provider 条目过滤）；
- runner._extract_content 对 `_fulltext` 条目短路（不再走 article_parser）。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_fulltext_spider.py
"""
import types

import pytest

from app.services import rss_source_service
from app.workflow.crawler import fulltext_spider
from app.workflow.crawler.runner import _extract_content


def _patch_requests(monkeypatch, responses):
    """responses: {url 前缀: 响应体(str|dict)}；按前缀匹配返回。"""
    class _Resp:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200
            self.text = payload if isinstance(payload, str) else ""
        def json(self):
            return self._payload
        def raise_for_status(self):
            pass

    def fake_get(url, params=None, headers=None, timeout=None):
        for prefix, payload in responses.items():
            if url.startswith(prefix):
                return _Resp(payload)
        raise AssertionError(f"未预期的请求: {url}")

    monkeypatch.setattr(fulltext_spider.requests, "get", fake_get)


class TestWikisource:
    async def test_extract_page_to_entry(self, monkeypatch):
        _patch_requests(monkeypatch, {
            "https://zh.wikisource.org/w/api.php": {
                "query": {"pages": {"1": {"extract": "子曰：「學而時習之。」有子曰：「其爲人也孝弟。」"}}},
            },
        })
        src = {"name": "维基文库-論語", "provider": "wikisource",
               "pages": ["論語/學而第一"], "category_hint": "古籍"}
        entries = await fulltext_spider.crawl_fulltext_source(src)
        assert len(entries) == 1
        e = entries[0]
        assert e["_fulltext"] is True
        assert e["title"].startswith("論語/學而第一")
        assert e["url"].startswith("https://zh.wikisource.org/wiki/")
        assert "學而時習之" in e["content"]
        assert e["published_at"] is None  # 公版内容：新鲜度过滤会保留

    async def test_empty_page_skipped(self, monkeypatch):
        _patch_requests(monkeypatch, {
            "https://zh.wikisource.org/w/api.php": {"query": {"pages": {"1": {}}}},
        })
        src = {"name": "维基文库-空页", "provider": "wikisource", "pages": ["不存在的页面"]}
        assert await fulltext_spider.crawl_fulltext_source(src) == []

    async def test_missing_pages_config_raises(self):
        with pytest.raises(ValueError, match="pages"):
            await fulltext_spider.crawl_fulltext_source({"name": "坏配置", "provider": "wikisource"})


class TestGutendex:
    async def test_query_resolve_and_split(self, monkeypatch):
        book = {
            "id": 3330, "title": "The Analects of Confucius",
            "formats": {"text/plain; charset=utf-8": "https://www.gutenberg.org/files/3330/3330-0.txt"},
        }
        long_text = "第一章 子曰。「學而時習之。」\n\n" + "入孝出弟。禮義以為坊。\n\n" * 60
        _patch_requests(monkeypatch, {
            "https://gutendex.com/books": {"results": [book]},  # 检索响应
            "https://www.gutenberg.org/files/3330": long_text,  # 全文下载
        })
        src = {"name": "Gutendex-論語", "provider": "gutendex", "languages": "zh",
               "query": "論語", "max_chapters": 40}
        entries = await fulltext_spider.crawl_fulltext_source(src)
        assert entries, "应切出至少一条章节素材"
        assert all(e["_fulltext"] for e in entries)
        urls = [e["url"] for e in entries]
        assert len(set(urls)) == len(urls), "去重键（URL#序号）必须唯一"

    async def test_max_chapters_truncates_with_unique_urls(self, monkeypatch):
        book = {
            "id": 999, "title": "長書",
            "formats": {"text/plain; charset=utf-8": "https://www.gutenberg.org/files/999/999-0.txt"},
        }
        long_text = "第一章 起頭。\n\n" + "正文內容。每句都很有分量。\n\n" * 300
        _patch_requests(monkeypatch, {
            "https://gutendex.com/books": {"results": [book]},
            "https://www.gutenberg.org/files/999": long_text,
        })
        src = {"name": "Gutendex-長書", "provider": "gutendex", "max_chapters": 5}
        entries = await fulltext_spider.crawl_fulltext_source(src)
        assert len(entries) <= 5
        assert len(set(e["url"] for e in entries)) == len(entries), "截断后 URL 仍需唯一"

    async def test_no_text_format_raises(self, monkeypatch):
        _patch_requests(monkeypatch, {
            "https://gutendex.com/books": {"results": [{"id": 1, "title": "仅EPUB", "formats": {"application/epub+zip": "x.epub"}}]},
        })
        with pytest.raises(ValueError, match="text/plain"):
            await fulltext_spider.crawl_fulltext_source({"name": "坏书", "provider": "gutendex", "query": "x"})


class TestDispatch:
    async def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="provider"):
            await fulltext_spider.crawl_fulltext_source({"name": "x", "provider": "nope"})


class TestLoader:
    def test_load_book_fulltext_sources(self):
        sources = rss_source_service.load_book_fulltext_sources()
        assert sources, "book_fulltext.yaml 应可加载"
        assert all(s.get("provider") for s in sources), "每条都必须声明 provider"
        names = [s["name"] for s in sources]
        assert "维基文库-論語" in names

    def test_summary_has_kind(self):
        summary = rss_source_service.load_book_fulltext_sources_summary()
        assert summary and all(s["kind"] == "fulltext" for s in summary)


class TestExtractShortCircuit:
    @pytest.mark.asyncio
    async def test_fulltext_entry_skips_article_parser(self, monkeypatch):
        """`_fulltext` 条目必须短路：不再对维基文库页面跑 article_parser。"""
        called = {"n": 0}

        async def _fake_extract(url):
            called["n"] += 1
            return {"content": "不应被调用的 HTML 噪声"}

        import app.workflow.crawler.runner as runner_mod
        monkeypatch.setattr(runner_mod, "extract_article", _fake_extract)

        entry = {"title": "論語/學而第一", "url": "https://zh.wikisource.org/wiki/x",
                 "source": "维基文库-論語", "category_hint": "古籍",
                 "published_at": None, "content": "子曰：「學而時習之。」", "_fulltext": True}
        prepared = await _extract_content(entry)
        assert called["n"] == 0, "全文条目不应触发 extract_article"
        assert prepared["content"] == "子曰：「學而時習之。」"
        assert prepared["summary"].startswith("子曰")
        assert prepared["cover_url"] is None


def test_yaml_loadable_by_real_loader():
    """真实 yaml 文件可被 loader 加载（无 BOM/编码问题）。"""
    sources = rss_source_service.load_book_fulltext_sources()
    providers = {s["provider"] for s in sources}
    assert providers <= {"wikisource", "gutendex"}, providers
