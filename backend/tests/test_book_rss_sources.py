"""书籍 RSS 预制源加载测试。

验证 book_rss.yaml 的加载逻辑与 load_rss_sources 完全对称，
且面向 audiobook 频道的 9 个预制源字段完整、摘要接口不泄漏内部字段。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_book_rss_sources.py
"""
from app.services.rss_source_service import (
    load_book_rss_sources,
    load_book_rss_sources_summary,
)
from app.paths import resolve_book_rss_sources_path

# 与 book_rss.yaml 中 9 个 name 保持一致（增删源时同步更新）
EXPECTED_NAMES = {
    "豆瓣读书-最新书评",
    "书格-古籍善本",
    "Kindle伴侣-电子书资讯",
    "看理想-人文谈话",
    "机核-游戏文化播客",
    "新京报书评周刊",
    "上海书评",
    "单读",
    "LibriVox-最新有声书",
}


def test_book_rss_yaml_path_resolves():
    """路径解析与 rss.yaml 对称：开发态指向 crawler/sources/book_rss.yaml。"""
    p = resolve_book_rss_sources_path()
    assert p.exists(), f"book_rss.yaml 未找到: {p}"
    assert p.name == "book_rss.yaml"


def test_load_book_rss_sources():
    """加载 9 个书籍 RSS 预制源，字段完整且 URL 合法。"""
    sources = load_book_rss_sources()
    assert isinstance(sources, list)
    assert len(sources) == 9, [s.get("name") for s in sources]
    names = {s["name"] for s in sources}
    assert names == EXPECTED_NAMES, names

    for s in sources:
        # 必填字段
        assert s.get("name"), "name 缺失"
        assert isinstance(s.get("url"), str) and s["url"].startswith("http"), \
            f"url 非法: {s.get('url')}"
        # 可选字段有默认值兜底
        assert "authority" in s
        assert "category_hint" in s
        assert "qps" in s


def test_load_book_rss_sources_summary_strips_internal_fields():
    """摘要接口仅返回 name/category_hint/authority，不泄漏 url/qps。"""
    summary = load_book_rss_sources_summary()
    assert len(summary) == 9
    allowed = {"name", "category_hint", "authority"}
    for s in summary:
        assert set(s.keys()) == allowed, set(s.keys())
        assert "url" not in s and "qps" not in s
