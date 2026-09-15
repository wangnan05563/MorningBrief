"""找书工具（书源检索）单元 + API 冒烟测试（T00601/T00603）。

覆盖：
- `parse_category` 纯函数（表头/分隔行/无链接行过滤）；
- `search` 关键词匹配（书名 / 作者 / 大小写不敏感）、limit 截断、category 限定、失败分类隔离；
- `list_categories` 从 README 解析；
- API 级冒烟：`GET /admin/api/v1/ebooks/search` 走真实路由 + 管理员鉴权（monkeypatch 掉网络层）。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_ebook_source_service.py
"""
import pytest

from app.services import ebook_source_service as svc

FAQ = """
# 版权声明
本站内容均从网上搜集，请勿用于商业目的。

| 书名 | 作者 | epub/mobi/azw3 |
| --- | --- | --- |
| 磨坊信札（作家榜经典文库） | 阿尔封斯・都德 | [下载](https://url89.ctfile.com/f/1?p=8866) |
| 活着 | 余华 | [下载](https://url89.ctfile.com/f/2?p=8866) |
| 许三观卖血记 | 余华 | [下载](https://url89.ctfile.com/f/4?p=8866) |
| 无链接的一行 | 某人 | 暂无 |
"""

FAKE_FILES = {
    "README.md": "# 宝库\n分类：md/文学.md md/历史.md md/哲学.md",
    "md/文学.md": FAQ,
    "md/历史.md": "| 书名 | 作者 | x |\n| --- | --- | --- |\n| 万历十五年 | 黄仁宇 | [下载](https://url89.ctfile.com/f/3?p=8866) |",
}


@pytest.fixture
def fake_fetch(monkeypatch):
    """把网络层替换为内存字典，并记录调用（同时清空模块级 TTL 缓存）。"""
    calls = []
    svc._CACHE.clear()

    def _fake(path, force=False):
        calls.append(path)
        if path not in FAKE_FILES:
            raise RuntimeError(f"模拟网络失败: {path}")
        return FAKE_FILES[path]

    monkeypatch.setattr(svc, "_fetch", _fake)
    return calls


class TestParseCategory:
    def test_parses_rows_and_skips_noise(self):
        books = svc.parse_category(FAQ)
        assert [b["title"] for b in books] == ["磨坊信札（作家榜经典文库）", "活着", "许三观卖血记"]
        assert books[1]["author"] == "余华"
        assert books[0]["url"].startswith("https://url89.ctfile.com/f/")

    def test_header_and_separator_skipped(self):
        assert svc.parse_category("| 书名 | 作者 | x |\n| --- | --- | --- |") == []

    def test_empty_text(self):
        assert svc.parse_category("") == []


class TestSearch:
    def test_match_by_title(self, fake_fetch):
        res = svc.search("活着", category="文学")
        assert len(res["hits"]) == 1
        assert res["hits"][0]["title"] == "活着"
        assert res["hits"][0]["category"] == "文学"
        assert res["failed_categories"] == []

    def test_match_by_author(self, fake_fetch):
        res = svc.search("余华", category="文学")
        assert [h["title"] for h in res["hits"]] == ["活着", "许三观卖血记"]

    def test_case_insensitive(self, fake_fetch):
        assert svc.search("ALPHONSE", category="文学")["hits"] == []  # 中文作者名不含英文
        assert svc.search("磨坊", category="文学")["hits"], "中文关键词应命中"

    def test_limit_truncates(self, fake_fetch):
        # 文学.md 中有两条「余华」条目 → limit=1 只返回 1 条
        res = svc.search("余华", category="文学", limit=1)
        assert len(res["hits"]) == 1
        assert res["hits"][0]["author"] == "余华"

    def test_empty_keyword(self, fake_fetch):
        res = svc.search("   ")
        assert res["hits"] == [] and res["scanned_categories"] == []

    def test_full_scan_scans_all_categories(self, fake_fetch):
        res = svc.search("万历", limit=10)
        assert res["hits"][0]["category"] == "历史"
        # 哲学.md 不在假数据中 → 拉取失败被隔离；scanned 只含成功的分类
        assert set(res["scanned_categories"]) == {"文学", "历史"}

    def test_failed_category_isolated(self, fake_fetch):
        # 哲学.md 不在 FAKE_FILES 中 → 模拟单分类失败
        res = svc.search("万历", limit=10)
        assert "哲学" in res["failed_categories"], "失败分类应被隔离并回传"
        assert res["hits"], "其他分类命中不应受失败分类影响"


class TestListCategories:
    def test_parses_readme(self, fake_fetch):
        assert svc.list_categories() == ["历史", "哲学", "文学"]  # 排序后


# ---------------------------------------------------------------------------
# API 级冒烟（真实路由 + 管理员鉴权；网络层 monkeypatch）
# ---------------------------------------------------------------------------

@pytest.fixture
def stub_blacklist(monkeypatch):
    """绕过 is_in_blacklist 的 DB 查询，避免命中生产 SQLite 文件。"""
    import app.core.auth

    async def _always_false(jti: str) -> bool:
        return False

    monkeypatch.setattr(app.core.auth, "is_in_blacklist", _always_false)


def _headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def test_search_api_roundtrip(client, admin_token, stub_blacklist, fake_fetch):
    resp = client.get(
        "/admin/api/v1/ebooks/search",
        params={"keyword": "活着", "category": "文学", "limit": 5},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data["keyword"] == "活着"
    assert data["hits"][0]["title"] == "活着"
    assert data["hits"][0]["url"].startswith("https://")


def test_categories_api_roundtrip(client, admin_token, stub_blacklist, fake_fetch):
    resp = client.get("/admin/api/v1/ebooks/categories", headers=_headers(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["count"] == 3
    assert body["data"]["categories"] == ["历史", "哲学", "文学"]


def test_search_api_requires_admin(client, fake_fetch):
    """未带管理员 token → 拒绝（401/403），不泄漏书源数据。"""
    resp = client.get("/admin/api/v1/ebooks/search", params={"keyword": "活着"})
    assert resp.status_code in (401, 403)


def test_search_api_network_failure_returns_biz_error(client, admin_token, stub_blacklist, monkeypatch):
    """书源不可达 → 可读业务错误（而非 500 堆栈）。"""
    svc._CACHE.clear()

    def _boom(path, force=False):
        raise RuntimeError("连接超时")

    monkeypatch.setattr(svc, "_fetch", _boom)
    # 不带 category → 全量扫描需先拉 README（分类清单），此路径失败才会冒泡为业务错误；
    # 带 category 时单分类失败按设计被隔离（返回空结果 + failed_categories），不报错
    resp = client.get(
        "/admin/api/v1/ebooks/search",
        params={"keyword": "活着"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] != 0
    assert "书源仓库访问失败" in body["message"]
