"""有声读物频道 book_rss 爬虫入库集成测试（离线，mock 网络）。

验证 crawler runner.run 对 channel_type=audiobook 的书籍 RSS 预制源处理链路：
- 仅 audiobook 频道加载 book_rss.yaml 书籍源（并受频道 book_rss_sources 白名单过滤）
- 来自书籍源的条目入库时标记为 source_type='book_rss'（而非通用 rss）
- channel_id 正确透传到素材
- material_count >= 1（即爬虫阶段"执行成功"）

网络相关调用（RSSSpider.fetch / extract_article）均被 mock，无需外网即可验证
book_rss 特征逻辑——这是本功能（有声读物书籍 RSS 预制源）的核心验收点。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_audiobook_workflow_book_rss.py
"""
from datetime import datetime

from app.workflow.crawler import runner


def _make_fake_entries():
    return [
        {
            "title": "测试书评一",
            "url": "https://example.com/book/1",
            "source": "豆瓣读书-最新书评",
            "summary": "这是一段书评摘要",
            "category_hint": "书评",
            "published_at": datetime(2026, 8, 19, 9, 0, 0),
        },
        {
            "title": "测试书评二",
            "url": "https://example.com/book/2",
            "source": "豆瓣读书-最新书评",
            "summary": "另一段书评摘要",
            "category_hint": "书评",
            "published_at": datetime(2026, 8, 19, 10, 0, 0),
        },
    ]


async def test_audiobook_crawler_tags_book_rss(monkeypatch):
    """audiobook 频道的书籍源条目应入库为 source_type=book_rss 且带 channel_id。"""
    captured = []

    # 1) 频道级过滤：直接返回 audiobook + 书籍源白名单（绕过 DB 查频道）
    async def fake_load_channel_filter(channel_id):
        return ([], [], "audiobook", ["豆瓣读书-最新书评"])

    monkeypatch.setattr(runner, "_load_channel_filter", fake_load_channel_filter)

    # 2) RSS 抓取：返回本地假条目（无网络）
    async def fake_fetch(self):
        return _make_fake_entries()

    monkeypatch.setattr(runner.RSSSpider, "fetch", fake_fetch)

    # 3) 正文提取：返回本地内容（无网络）
    async def fake_extract(url):
        return {"content": f"正文内容 for {url}", "title": url, "cover_url": None}

    monkeypatch.setattr(runner, "extract_article", fake_extract)

    # 4) 捕获入库参数，不实际落库（与 DB 解耦，纯逻辑验证）
    async def fake_insert(prepared, workflow_id, session, channel_id=None, source_type="rss"):
        captured.append(
            {
                "title": prepared["title"],
                "url": prepared["url"],
                "source": prepared.get("source"),
                "source_type": source_type,
                "channel_id": channel_id,
            }
        )
        return True

    monkeypatch.setattr(runner, "_insert_material", fake_insert)

    result = await runner.run("wf-test-001", "2026-08-19", channel_id=999)

    assert result["material_count"] >= 1, result
    assert len(captured) == 2, captured
    for c in captured:
        assert c["source_type"] == "book_rss", c
        assert c["channel_id"] == 999, c
        assert c["source"] == "豆瓣读书-最新书评", c


async def test_audiobook_crawler_skips_generic_rss(monkeypatch):
    """audiobook 频道未配置通用 RSS 白名单时，不混入新闻源（sources 仅书籍源）。"""
    captured = []

    async def fake_load_channel_filter(channel_id):
        # rss_sources_filter 为空 + channel_type=audiobook → run() 内部 sources=[] 仅合并书籍源
        return ([], [], "audiobook", [])

    monkeypatch.setattr(runner, "_load_channel_filter", fake_load_channel_filter)

    async def fake_fetch(self):
        return _make_fake_entries()

    monkeypatch.setattr(runner.RSSSpider, "fetch", fake_fetch)

    async def fake_extract(url):
        return {"content": "x", "title": url, "cover_url": None}

    monkeypatch.setattr(runner, "extract_article", fake_extract)

    async def fake_insert(prepared, workflow_id, session, channel_id=None, source_type="rss"):
        captured.append(source_type)
        return True

    monkeypatch.setattr(runner, "_insert_material", fake_insert)

    # T00603：audiobook 频道还会加载 book_fulltext.yaml 全文源 → 必须一并 monkeypatch，
    # 否则测试会对维基文库/Gutendex 发起真实网络请求（不确定性 + 慢）
    async def fake_fulltext(src):
        return [{
            "title": f"{src['name']}·第一章",
            "url": f"https://example.com/{src['name']}#1",
            "source": src["name"], "category_hint": src.get("category_hint"),
            "published_at": None, "summary": "x", "content": "全文章节正文",
            "_fulltext": True,
        }]

    monkeypatch.setattr(runner, "crawl_fulltext_source", fake_fulltext)

    # book_rss_sources_filter 为空 → 加载全部书籍 RSS 源 + 全部全文源；fake_fetch 仅对调用到的源返回条目
    # 所有入库条目的 source_type 都应是书籍类（book_rss / book_fulltext），绝不混入通用 rss
    result = await runner.run("wf-test-002", "2026-08-19", channel_id=1)
    assert result["material_count"] >= 1
    assert captured, captured
    assert all(st in ("book_rss", "book_fulltext") for st in captured), captured
    assert "rss" not in captured, captured
