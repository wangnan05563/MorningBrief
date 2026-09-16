"""书源索引服务与「找书」检索策略测试（T00612）。

覆盖超时修复的核心行为：
- 索引构建（并发抓取 → 解析 → 原子落盘、进度状态复位、失败分类计数）；
- 本地检索（书名/作者/分类过滤/limit/索引缺失）；
- 索引状态；
- 后台构建不重复启动；
- 路由三条检索路径：索引优先 / 分类快路径 / 无索引无分类 → 触发构建返回可读提示（不再挂到超时）。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_ebook_index_service.py
"""
import json
import threading
import time

import pytest

from app.services import ebook_index_service as idx
from app.services import ebook_source_service as src_svc

CAT_FAKE = {
    "md/文学.md": "| 书名 | 作者 | x |\n| --- | --- | --- |\n| 活着 | 余华 | [下载](https://u/1) |\n| 许三观卖血记 | 余华 | [下载](https://u/2) |",
    "md/历史.md": "| 书名 | 作者 | x |\n| --- | --- | --- |\n| 万历十五年 | 黄仁宇 | [下载](https://u/3) |",
}


@pytest.fixture
def tmp_index(monkeypatch, tmp_path):
    """索引文件重定向到临时目录，并注入假的分类抓取。"""
    path = tmp_path / "ebook_index.json"
    monkeypatch.setattr(idx, "index_path", lambda: path)

    def _fetch(p, force=False):
        if p not in CAT_FAKE:
            raise RuntimeError(f"模拟抓取失败: {p}")
        return CAT_FAKE[p]

    monkeypatch.setattr(src_svc, "_fetch", _fetch)
    idx._BUILD_STATE.update(running=False, done=0, total=0, failed=0,
                            started_at=None, finished_at=None, error=None)
    return path


class TestBuildIndex:
    def test_build_writes_index_and_resets_state(self, tmp_index):
        data = idx.build_index(fetch_categories=["文学", "历史"], max_workers=2)
        assert data["book_count"] == 3
        assert data["category_count"] == 2
        assert data["failed_category_count"] == 0
        assert "built_at" in data and "elapsed_sec" in data
        # 原子落盘 + 内容可读
        on_disk = json.loads(tmp_index.read_text(encoding="utf-8"))
        assert on_disk["book_count"] == 3
        assert all(b["category"] for b in on_disk["books"]), "每条书目必须带分类"
        assert not list(tmp_index.parent.glob("*.tmp")), "临时文件应已被替换"
        # 状态复位
        st = idx.build_state()
        assert st["running"] is False and st["error"] is None
        assert st["done"] == st["total"] == 2

    def test_failed_category_counted_not_fatal(self, tmp_index):
        data = idx.build_index(fetch_categories=["文学", "不存在的分类"], max_workers=2)
        assert data["book_count"] == 2
        assert data["failed_category_count"] == 1, "抓取失败的分类应计数但不阻断整体"

    def test_status_reports_ready(self, tmp_index):
        assert idx.index_status()["ready"] is False
        idx.build_index(fetch_categories=["文学"], max_workers=1)
        st = idx.index_status()
        assert st["ready"] is True
        assert st["book_count"] == 2
        assert st["built_at"]

    def test_start_build_async_no_duplicate(self, tmp_index, monkeypatch):
        started = threading.Event()
        release = threading.Event()

        def _slow_build(**kwargs):
            started.set()
            release.wait(5)
            return {"book_count": 0, "built_at": "x", "elapsed_sec": 0,
                    "category_count": 0, "failed_category_count": 0, "books": []}

        monkeypatch.setattr(idx, "build_index", _slow_build)
        first = idx.start_build_async()
        assert first["running"] is True
        started.wait(5)
        second = idx.start_build_async()
        assert second["running"] is True
        assert second["total"] == 0, "第二次调用不应重启构建（状态未被重置）"
        release.set()
        time.sleep(0.05)


class TestSearchIndex:
    def test_match_by_title_and_author(self, tmp_index):
        idx.build_index(fetch_categories=["文学", "历史"], max_workers=2)
        assert [h["title"] for h in idx.search_index("活着")["hits"]] == ["活着"]
        assert {h["title"] for h in idx.search_index("余华")["hits"]} == {"活着", "许三观卖血记"}

    def test_category_filter_and_limit(self, tmp_index):
        idx.build_index(fetch_categories=["文学", "历史"], max_workers=2)
        res = idx.search_index("余", limit=1)
        assert len(res["hits"]) == 1
        assert res["hits"][0]["category"] == "文学"
        assert idx.search_index("万历", category="文学")["hits"] == [], "分类过滤应生效"

    def test_no_index_returns_not_ready(self, tmp_index):
        res = idx.search_index("活着")
        assert res["hits"] == [] and res["index_ready"] is False

    def test_index_search_is_local_fast(self, tmp_index):
        """索引检索不得发起网络请求（超时修复的本质）。"""
        idx.build_index(fetch_categories=["文学"], max_workers=1)

        def _boom(*a, **kw):
            raise AssertionError("索引检索不应触网")

        src_svc._fetch = _boom
        t0 = time.time()
        idx.search_index("余华")
        assert time.time() - t0 < 0.5


# ---------------------------------------------------------------------------
# 路由层：三条检索路径（T00612）
# ---------------------------------------------------------------------------

@pytest.fixture
def stub_blacklist(monkeypatch):
    import app.core.auth

    async def _always_false(jti: str) -> bool:
        return False

    monkeypatch.setattr(app.core.auth, "is_in_blacklist", _always_false)


def _headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def test_search_uses_index_when_ready(client, admin_token, stub_blacklist, tmp_index, monkeypatch):
    idx.build_index(fetch_categories=["文学"], max_workers=1)
    resp = client.get("/admin/api/v1/ebooks/search", params={"keyword": "余华"},
                      headers=_headers(admin_token))
    body = resp.json()
    assert body["code"] == 0, body
    assert body["data"]["index_ready"] is True
    assert len(body["data"]["hits"]) == 2


def test_search_category_fast_path_without_index(client, admin_token, stub_blacklist, tmp_index, monkeypatch):
    """索引未就绪但指定分类 → 只抓该分类（秒级），不触发构建。"""
    called = {}

    def _fake_search(keyword, category=None, limit=20, force=False):
        called["category"] = category
        return {"keyword": keyword, "scanned_categories": [category], "failed_categories": [],
                "hits": [{"title": "活着", "author": "余华", "url": "https://u/1", "category": category}]}

    monkeypatch.setattr(src_svc, "search", _fake_search)
    resp = client.get("/admin/api/v1/ebooks/search",
                      params={"keyword": "余华", "category": "文学"}, headers=_headers(admin_token))
    body = resp.json()
    assert body["code"] == 0, body
    assert called["category"] == "文学"
    assert body["data"]["index_ready"] is False
    assert body["data"]["hits"][0]["title"] == "活着"


def test_search_without_index_triggers_build_and_hints(client, admin_token, stub_blacklist, tmp_index, monkeypatch):
    """无索引 + 无分类 → 不再全量抓取（原超时根因），触发构建并返回可读提示。"""
    started = {}

    def _fake_start():
        started["yes"] = True
        return {"running": True, "done": 0, "total": 0}

    monkeypatch.setattr(idx, "start_build_async", _fake_start)
    resp = client.get("/admin/api/v1/ebooks/search", params={"keyword": "余华"},
                      headers=_headers(admin_token))
    body = resp.json()
    assert body["code"] == 428, body
    assert "索引" in body["message"] and "分类" in body["message"]
    assert started.get("yes") is True, "应自动触发后台构建"


def test_index_status_and_rebuild_endpoints(client, admin_token, stub_blacklist, tmp_index, monkeypatch):
    st = client.get("/admin/api/v1/ebooks/index/status", headers=_headers(admin_token)).json()
    assert st["code"] == 0 and st["data"]["ready"] is False

    monkeypatch.setattr(idx, "start_build_async", lambda: {"running": True})
    rb = client.post("/admin/api/v1/ebooks/index/rebuild", headers=_headers(admin_token)).json()
    assert rb["code"] == 0 and rb["data"]["started"] is True

# ---------------------------------------------------------------------------
# T00619：索引过期检测与自动重建
# ---------------------------------------------------------------------------

class TestStaleAndAutoRebuild:
    def test_fresh_index_not_stale(self, tmp_index):
        idx.build_index(fetch_categories=["文学"], max_workers=1)
        st = idx.index_status()
        assert st["ready"] is True
        assert st["stale"] is False
        assert st["age_days"] is not None and st["age_days"] < 1
        assert st["stale_days"] == 14.0

    def test_old_index_marked_stale(self, tmp_index):
        """把 built_at 回拨 20 天 → stale=True。"""
        import json as _json
        from datetime import datetime, timedelta, timezone as _tz
        idx.build_index(fetch_categories=["文学"], max_workers=1)
        data = _json.loads(tmp_index.read_text(encoding="utf-8"))
        data["built_at"] = (datetime.now(_tz.utc) - timedelta(days=20)).isoformat()
        tmp_index.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
        st = idx.index_status()
        assert st["stale"] is True, st
        assert st["age_days"] >= 19

    def test_threshold_env_override(self, tmp_index, monkeypatch):
        monkeypatch.setenv("EBOOK_INDEX_STALE_DAYS", "0.5")
        assert idx.index_stale_days() == 0.5

    def test_auto_rebuild_when_missing(self, tmp_index, monkeypatch):
        started = {}
        monkeypatch.setattr(idx, "start_build_async", lambda: started.setdefault("yes", True))
        res = idx.maybe_auto_rebuild()
        assert res == {"triggered": True, "reason": "missing"}
        assert started.get("yes") is True

    def test_auto_rebuild_when_stale(self, tmp_index, monkeypatch):
        import json as _json
        from datetime import datetime, timedelta, timezone as _tz
        idx.build_index(fetch_categories=["文学"], max_workers=1)
        data = _json.loads(tmp_index.read_text(encoding="utf-8"))
        data["built_at"] = (datetime.now(_tz.utc) - timedelta(days=30)).isoformat()
        tmp_index.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
        started = {}
        monkeypatch.setattr(idx, "start_build_async", lambda: started.setdefault("yes", True))
        res = idx.maybe_auto_rebuild()
        assert res == {"triggered": True, "reason": "stale"}
        assert started.get("yes") is True

    def test_auto_rebuild_skipped_when_fresh(self, tmp_index, monkeypatch):
        idx.build_index(fetch_categories=["文学"], max_workers=1)
        monkeypatch.setattr(idx, "start_build_async", lambda: pytest.fail("不应触发重建"))
        assert idx.maybe_auto_rebuild() == {"triggered": False, "reason": "fresh"}

    def test_auto_rebuild_skipped_while_building(self, tmp_index, monkeypatch):
        monkeypatch.setattr(idx, "start_build_async", lambda: pytest.fail("构建中不应重复触发"))
        idx._BUILD_STATE.update(running=True, done=1, total=10)
        try:
            assert idx.maybe_auto_rebuild() == {"triggered": False, "reason": "building"}
        finally:
            idx._BUILD_STATE.update(running=False)


def test_search_response_carries_stale_flags(client, admin_token, stub_blacklist, tmp_index, monkeypatch):
    """检索响应回传 index_stale / index_age_days / auto_rebuild（前端据此提示）。"""
    idx.build_index(fetch_categories=["文学"], max_workers=1)
    monkeypatch.setattr(idx, "maybe_auto_rebuild", lambda: {"triggered": False, "reason": "fresh"})
    body = client.get("/admin/api/v1/ebooks/search", params={"keyword": "余华"},
                      headers=_headers(admin_token)).json()
    assert body["code"] == 0, body
    assert body["data"]["index_stale"] is False
    assert body["data"]["index_age_days"] is not None
    assert body["data"]["auto_rebuild"] == {"triggered": False, "reason": "fresh"}


def test_index_status_exposes_stale_fields(client, admin_token, stub_blacklist, tmp_index):
    body = client.get("/admin/api/v1/ebooks/index/status", headers=_headers(admin_token)).json()
    assert body["code"] == 0
    assert body["data"]["stale"] is False and body["data"]["ready"] is False
    assert body["data"]["stale_days"] == 14.0
