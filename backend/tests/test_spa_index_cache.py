"""SPA 入口缓存策略测试（T00775）。

背景：`index.html` 引用按内容哈希命名的 assets chunk，而升级安装不会删除旧 chunk
（实测安装目录里同时存在多批 `MaterialLibrary-*.js`）。若浏览器沿用启发式缓存里的旧
index.html，就会静默加载旧版页面——「代码已修但页面上看不到」正是这个机制造成的。

因此 SPA 入口必须每次回源校验（`Cache-Control: no-cache, must-revalidate`），
带哈希的 chunk 则可长缓存。本测试把该策略锁住，防止后续误加长缓存。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_spa_index_cache.py
"""
import pytest
from fastapi.testclient import TestClient

from app.paths import resolve_admin_dist

pytestmark = pytest.mark.skipif(
    resolve_admin_dist() is None,
    reason="前端 dist 未构建（apps/admin-web/dist 不存在），无法验证 SPA fallback",
)


@pytest.mark.parametrize("path", ["/news/", "/news/channels/material-library"])
def test_index_html_is_revalidated(app, path):
    """SPA 入口响应必须带 no-cache，避免浏览器复用旧 index.html 加载旧 chunk。"""
    client = TestClient(app)
    r = client.get(path)
    assert r.status_code == 200, r.status_code
    assert r.headers.get("cache-control") == "no-cache, must-revalidate", (
        f"index.html 必须每次回源校验，实际 header：{r.headers.get('cache-control')!r}"
    )
    assert "<!doctype html>" in r.text[:200].lower()


def test_api_404_not_fallback_to_index(app):
    """API 路径 404 不得被 SPA fallback 兜成 index.html（否则前端拿到 HTML 却以为是 JSON）。"""
    client = TestClient(app)
    r = client.get("/news/admin/api/v1/not-exist")
    assert r.status_code == 404
    assert "text/html" not in r.headers.get("content-type", "")
