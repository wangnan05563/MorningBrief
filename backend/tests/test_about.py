"""关于页面路由测试。

覆盖：
- GET /admin/api/v1/about：系统元信息（版本/构建日期/Git SHA/Python/平台）
- GET /admin/api/v1/about/check-update：检查更新（缓存命中/GitHub API 比对/失败降级）

测试目标：
- 鉴权：非 admin token 拒绝（401/403）
- 元信息字段完整且类型正确
- 版本比较 semver 逻辑：相同/更新/降级/无法解析
- 缓存：5 分钟内复用结果，过期后重新请求
- 失败降级：GitHub API 异常时返回 source='local', has_update=False
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.routers.admin.about import (
    _is_newer,
    _parse_version,
    _reset_cache_for_test,
)


def _admin_headers(admin_token):
    """构造 admin 请求头。"""
    return {"Authorization": f"Bearer {admin_token['token']}"}


# ====================== 鉴权测试 ======================

def test_about_requires_admin(client, user_token):
    """非 admin token 访问 /about 被拒。"""
    resp = client.get(
        "/admin/api/v1/about",
        headers={"Authorization": f"Bearer {user_token['token']}"},
    )
    assert resp.status_code in (401, 403)


def test_check_update_requires_admin(client, user_token):
    """非 admin token 访问 /check-update 被拒。"""
    resp = client.get(
        "/admin/api/v1/about/check-update",
        headers={"Authorization": f"Bearer {user_token['token']}"},
    )
    assert resp.status_code in (401, 403)


def test_about_requires_token(client):
    """无 token 访问 /about 被拒。"""
    resp = client.get("/admin/api/v1/about")
    assert resp.status_code in (401, 403)


# ====================== 元信息测试 ======================

def test_get_about_returns_metadata(client, admin_token):
    """/about 返回完整元信息字段。"""
    resp = client.get(
        "/admin/api/v1/about",
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # 字段完整性
    assert "product" in data
    assert "version" in data
    assert "build_date" in data
    assert "git_sha" in data
    assert "python" in data
    assert "platform" in data
    # 类型正确性
    assert isinstance(data["product"], str)
    assert isinstance(data["version"], str)
    assert isinstance(data["python"], str)
    # Python 版本格式：X.Y.Z
    assert data["python"].count(".") == 2
    # 平台为小写字符串
    assert data["platform"] == data["platform"].lower()


def test_get_about_reflects_build_info(client, admin_token):
    """/about 返回的版本号与 _build_info.py 一致。"""
    from app import _build_info

    resp = client.get(
        "/admin/api/v1/about",
        headers=_admin_headers(admin_token),
    )
    data = resp.json()["data"]
    assert data["version"] == _build_info.__version__
    assert data["build_date"] == _build_info.build_date
    assert data["git_sha"] == _build_info.git_sha


# ====================== 版本号解析与比较测试 ======================

@pytest.mark.parametrize("raw,expected", [
    ("1.0.0", (1, 0, 0)),
    ("v1.2.3", (1, 2, 3)),
    ("V2.0.1", (2, 0, 1)),
    ("1.2.3-beta", (1, 2, 3)),
    ("v3.0.0-rc.1", (3, 0, 0)),
    ("0.0.1", (0, 0, 1)),
])
def test_parse_version_valid(raw, expected):
    """合法 semver 字符串解析为三元组。"""
    assert _parse_version(raw) == expected


@pytest.mark.parametrize("raw", [
    "",
    None,
    "unknown",
    "main",
    "abc",
    "v",
    "1",
    "1.2",
])
def test_parse_version_invalid(raw):
    """非 semver 字符串返回 None（保守降级）。"""
    assert _parse_version(raw) is None


def test_is_newer_same_version():
    """相同版本不算更新。"""
    assert _is_newer("1.0.0", "1.0.0") is False


def test_is_newer_higher_patch():
    """patch 号更大算更新。"""
    assert _is_newer("1.0.0", "1.0.1") is True


def test_is_newer_higher_minor():
    """minor 号更大算更新。"""
    assert _is_newer("1.0.0", "1.1.0") is True


def test_is_newer_higher_major():
    """major 号更大算更新。"""
    assert _is_newer("1.0.0", "2.0.0") is True


def test_is_newer_lower_version():
    """低版本不算更新（避免 GitHub 上 release 回退误判）。"""
    assert _is_newer("2.0.0", "1.0.0") is False


def test_is_newer_current_unknown():
    """current 无法解析时返回 False（保守策略，避免误报）。"""
    assert _is_newer("unknown", "1.0.0") is False


def test_is_newer_latest_unknown():
    """latest 无法解析时返回 False。"""
    assert _is_newer("1.0.0", "unknown") is False


def test_is_newer_both_unknown():
    """两端都未知时返回 False。"""
    assert _is_newer("unknown", "unknown") is False


def test_is_newer_with_v_prefix():
    """带 v 前缀的版本号正确比较。"""
    assert _is_newer("v1.0.0", "v1.0.1") is True
    assert _is_newer("v1.0.0", "v1.0.0") is False


# ====================== check-update 端点测试 ======================

@pytest.fixture(autouse=True)
def _reset_cache():
    """每个测试前后清空 about 模块缓存，保证测试间隔离。

    同时 patch 仓库地址常量：REPO_URL 默认为空时 check-update 端点会提前降级返回，
    导致 mock 的 _fetch_latest_release 从未被调用，故测试需模拟已配置仓库场景。
    """
    _reset_cache_for_test()
    with patch("app.routers.admin.about._REPO_URL", "https://github.com/test/repo"), \
         patch("app.routers.admin.about._RELEASES_API", "https://github.com/test/repo/releases/latest"), \
         patch("app.routers.admin.about._RELEASE_URL", "https://github.com/test/repo/releases"):
        yield
    _reset_cache_for_test()


def test_check_update_github_failure_degrades_to_local(client, admin_token):
    """GitHub API 失败时降级返回 source='local'，has_update=False。"""
    mock_fetch = AsyncMock(return_value=None)
    with patch(
        "app.routers.admin.about._fetch_latest_release",
        mock_fetch,
    ):
        resp = client.get(
            "/admin/api/v1/about/check-update",
            headers=_admin_headers(admin_token),
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source"] == "local"
    assert data["has_update"] is False
    assert data["current"] == data["latest"]
    assert "checked_at" in data
    assert "release_url" in data
    # 失败不写缓存，便于下次重试
    mock_fetch.assert_awaited_once()


def test_check_update_same_version_returns_no_update(client, admin_token):
    """远端版本与本地一致时 has_update=False。"""
    from app import _build_info
    current_version = _build_info.__version__

    mock_fetch = AsyncMock(return_value={
        "tag_name": current_version,
        "html_url": "https://github.com/your-org/MorningBrief/releases/tag/" + current_version,
        "published_at": "2026-07-20T00:00:00Z",
        "name": "Release " + current_version,
    })
    with patch(
        "app.routers.admin.about._fetch_latest_release",
        mock_fetch,
    ):
        resp = client.get(
            "/admin/api/v1/about/check-update",
            headers=_admin_headers(admin_token),
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source"] == "remote"
    assert data["has_update"] is False
    assert data["current"] == current_version
    assert data["latest"] == current_version


def test_check_update_higher_version_returns_update(client, admin_token):
    """远端版本更高时 has_update=True，release_url 指向具体 release 页面。"""
    mock_fetch = AsyncMock(return_value={
        "tag_name": "v99.99.99",
        "html_url": "https://github.com/your-org/MorningBrief/releases/tag/v99.99.99",
        "published_at": "2026-07-21T00:00:00Z",
        "name": "Release v99.99.99",
    })
    with patch(
        "app.routers.admin.about._fetch_latest_release",
        mock_fetch,
    ):
        resp = client.get(
            "/admin/api/v1/about/check-update",
            headers=_admin_headers(admin_token),
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source"] == "remote"
    assert data["has_update"] is True
    assert data["latest"] == "v99.99.99"
    # has_update=True 时 release_url 指向具体 release 页面
    assert data["release_url"].endswith("v99.99.99")
    assert "published_at" in data


def test_check_update_lower_version_returns_no_update(client, admin_token):
    """远端版本更低时 has_update=False（避免回退误判）。"""
    mock_fetch = AsyncMock(return_value={
        "tag_name": "v0.0.1",
        "html_url": "https://github.com/your-org/MorningBrief/releases/tag/v0.0.1",
        "published_at": "2020-01-01T00:00:00Z",
        "name": "Release v0.0.1",
    })
    with patch(
        "app.routers.admin.about._fetch_latest_release",
        mock_fetch,
    ):
        resp = client.get(
            "/admin/api/v1/about/check-update",
            headers=_admin_headers(admin_token),
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source"] == "remote"
    assert data["has_update"] is False


def test_check_update_cache_hit_avoids_refetch(client, admin_token):
    """缓存命中时不再次调用 GitHub API。"""
    mock_fetch = AsyncMock(return_value={
        "tag_name": "v1.0.0",
        "html_url": "https://github.com/your-org/MorningBrief/releases/tag/v1.0.0",
        "published_at": "2026-07-20T00:00:00Z",
        "name": "Release v1.0.0",
    })
    with patch(
        "app.routers.admin.about._fetch_latest_release",
        mock_fetch,
    ):
        # 第一次请求：触发 GitHub API
        resp1 = client.get(
            "/admin/api/v1/about/check-update",
            headers=_admin_headers(admin_token),
        )
        assert resp1.status_code == 200
        # 第二次请求：应命中缓存，不再调用 _fetch_latest_release
        resp2 = client.get(
            "/admin/api/v1/about/check-update",
            headers=_admin_headers(admin_token),
        )
        assert resp2.status_code == 200

    # _fetch_latest_release 仅被调用一次（第一次请求）
    assert mock_fetch.await_count == 1
    # 两次响应数据一致
    assert resp1.json()["data"] == resp2.json()["data"]


def test_check_update_invalid_tag_treated_as_no_update(client, admin_token):
    """远端 tag_name 非语义化版本时 has_update=False（保守策略）。"""
    mock_fetch = AsyncMock(return_value={
        "tag_name": "main",
        "html_url": "https://github.com/your-org/MorningBrief",
        "published_at": "2026-07-20T00:00:00Z",
        "name": "main branch",
    })
    with patch(
        "app.routers.admin.about._fetch_latest_release",
        mock_fetch,
    ):
        resp = client.get(
            "/admin/api/v1/about/check-update",
            headers=_admin_headers(admin_token),
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["has_update"] is False
    assert data["source"] == "remote"


# ====================== _fetch_latest_release 异常处理测试 ======================

@pytest.mark.asyncio
async def test_fetch_latest_release_returns_none_on_404():
    """GitHub 404（无 release）返回 None。"""
    import httpx
    from app.routers.admin.about import _fetch_latest_release

    mock_response = httpx.Response(404, json={})
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        result = await _fetch_latest_release()
    assert result is None


@pytest.mark.asyncio
async def test_fetch_latest_release_returns_none_on_403():
    """GitHub 限速 403 返回 None。"""
    import httpx
    from app.routers.admin.about import _fetch_latest_release

    mock_response = httpx.Response(
        403,
        headers={"X-RateLimit-Remaining": "0"},
        json={},
    )
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        result = await _fetch_latest_release()
    assert result is None


@pytest.mark.asyncio
async def test_fetch_latest_release_returns_none_on_missing_tag():
    """响应缺少 tag_name 字段时返回 None。"""
    import httpx
    from app.routers.admin.about import _fetch_latest_release

    mock_response = httpx.Response(200, json={"html_url": "x"})
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        result = await _fetch_latest_release()
    assert result is None


@pytest.mark.asyncio
async def test_fetch_latest_release_parses_valid_response():
    """有效响应解析为 dict，含 tag_name/html_url/published_at/name 字段。"""
    import httpx
    from app.routers.admin.about import _fetch_latest_release

    mock_response = httpx.Response(200, json={
        "tag_name": "v1.2.3",
        "html_url": "https://github.com/your-org/MorningBrief/releases/tag/v1.2.3",
        "published_at": "2026-07-20T00:00:00Z",
        "name": "Release v1.2.3",
    })
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        result = await _fetch_latest_release()
    assert result is not None
    assert result["tag_name"] == "v1.2.3"
    assert result["html_url"].endswith("v1.2.3")
    assert result["published_at"] == "2026-07-20T00:00:00Z"


@pytest.mark.asyncio
async def test_fetch_latest_release_handles_timeout():
    """网络超时返回 None（不抛异常）。"""
    import httpx
    from app.routers.admin.about import _fetch_latest_release

    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(side_effect=httpx.TimeoutException("timeout")),
    ):
        result = await _fetch_latest_release()
    assert result is None
