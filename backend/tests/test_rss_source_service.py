"""RSS source service tests."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

# 测试文件位于 backend/tests/ 下，parent.parent 即 backend/ 根目录
# 无需再拼接 "backend" 子目录（否则路径变成 backend/backend/）
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

RSS_YAML_PATH = _BACKEND_DIR / "app" / "workflow" / "crawler" / "sources" / "rss.yaml"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / ".tmp" / "rss_tests"


def _ensure_dir():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    return str(FIXTURES_DIR)


@pytest.fixture(scope="session")
def tmp_rss_dir():
    d = _ensure_dir()
    yield d


@pytest.fixture
def mock_resolve_rss_path(monkeypatch, tmp_rss_dir):
    rss_file = f"{tmp_rss_dir}/test_rss.yaml"
    sources = [
        {"name": "\u6d4b\u8bd5\u6e901", "url": "http://example.com/rss1.xml", "authority": 0.9, "category_hint": "\u79d1\u6280", "qps": 1},
        {"name": "\u6d4b\u8bd5\u6e902", "url": "https://example.org/feed.xml", "authority": 0.8, "category_hint": "\u8d22\u7ecf", "qps": 1},
    ]
    with open(rss_file, "w", encoding="utf-8") as f:
        yaml.dump({"sources": sources, "global": {"timeout_sec": 30}}, f, allow_unicode=True)

    from pathlib import Path as _Path
    def _resolve():
        return _Path(rss_file)
    monkeypatch.setattr("app.services.rss_source_service.resolve_rss_sources_path", _resolve)
    return Path(rss_file)


@pytest.fixture
def fresh_service(monkeypatch, mock_resolve_rss_path):
    """Reset _SOURCE_STATUS between tests."""
    from app.services import rss_source_service
    original_status = rss_source_service._SOURCE_STATUS.copy()
    rss_source_service._SOURCE_STATUS.clear()
    yield rss_source_service
    rss_source_service._SOURCE_STATUS.clear()
    rss_source_service._SOURCE_STATUS.update(original_status)

def test_load_rss_returns_sources(fresh_service, mock_resolve_rss_path):
    sources = fresh_service.load_rss_sources()
    assert len(sources) == 2
    assert sources[0]["name"] == "测试源1"


def test_load_rss_returns_empty_when_no_file(fresh_service, monkeypatch):
    fake_path = MagicMock()
    fake_path.exists.return_value = False

    def mock_return():
        return fake_path
    monkeypatch.setattr("app.services.rss_source_service.resolve_rss_sources_path", mock_return)

    from app.services import rss_source_service
    result = rss_source_service.load_rss_sources()
    assert result == []


def test_load_rss_summary_format(fresh_service, mock_resolve_rss_path):
    summary = fresh_service.load_rss_sources_summary()
    assert len(summary) == 2
    assert set(summary[0].keys()) == {"name", "category_hint", "authority"}
    assert "url" not in summary[0]


def test_load_rss_invalid_yaml_fails(mock_resolve_rss_path, monkeypatch):
    with open(mock_resolve_rss_path, "w", encoding="utf-8") as f:
        f.write("not valid: yaml: {{{")

    from app.services import rss_source_service
    with pytest.raises(yaml.YAMLError):
        rss_source_service.load_rss_sources()


def test_load_rss_empty_sources_key(mock_resolve_rss_path, monkeypatch):
    with open(mock_resolve_rss_path, "w", encoding="utf-8") as f:
        yaml.dump({"sources": [], "global": {}}, f, allow_unicode=True)

    from app.services import rss_source_service
    result = rss_source_service.load_rss_sources()
    assert result == []


def test_load_rss_non_list_sources(mock_resolve_rss_path, monkeypatch):
    with open(mock_resolve_rss_path, "w", encoding="utf-8") as f:
        yaml.dump({"sources": "invalid", "global": {}}, f, allow_unicode=True)

    from app.services import rss_source_service
    result = rss_source_service.load_rss_sources()
    assert result == []


# ==========================================================================
# check_all_sources tests - httpx mock
# ==========================================================================


@pytest.mark.asyncio
async def test_check_all_sources_all_ok(fresh_service, mock_resolve_rss_path, monkeypatch):
    """All sources return ok=true."""
    from app.services import rss_source_service as svc

    test_source = {
        "name": "TestSource", "url": "http://example.com/rss.xml",
        "category_hint": "tech", "authority": 0.9, "qps": 1,
    }
    monkeypatch.setattr("app.services.rss_source_service.load_rss_sources", lambda: [test_source])

    # Build a proper context manager mock for httpx.AsyncClient
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers.get.return_value = "application/rss+xml"

    async def mock_head(*args, **kwargs):
        # Simulate 405 -> fallback to GET
        head_resp = MagicMock()
        head_resp.status_code = 405
        return head_resp

    async def mock_get(*args, **kwargs):
        return mock_resp

    mock_ac = MagicMock()
    mock_ac.head = mock_head
    mock_ac.get = mock_get
    mock_ac.__aenter__ = AsyncMock(return_value=mock_ac)
    mock_ac.__aexit__ = AsyncMock(return_value=None)

    svc.httpx.AsyncClient = MagicMock(return_value=mock_ac)

    try:
        result = await svc.check_all_sources()
        assert result["total"] == 1, f"total={result['total']}"
        assert result["ok"] == 1, f"ok={result['ok']} fail={result['fail']} sources={[s['status'] for s in result.get('sources', [])]}"
        assert result["fail"] == 0
        assert result["sources"][0]["status"] == "ok"
    finally:
        # Restore original
        import httpx
        svc.httpx.AsyncClient = httpx.AsyncClient


@pytest.mark.asyncio
async def test_check_all_sources_fail(fresh_service):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.rss_source_service.httpx.AsyncClient", return_value=mock_client):
        result = await fresh_service.check_all_sources()

    assert result["total"] == 2
    assert result["ok"] == 0
    assert result["fail"] == 2
    assert result["sources"][0]["status"] == "fail"


@pytest.mark.asyncio
async def test_check_all_sources_concurrency_limit(fresh_service, monkeypatch):
    from app.services import rss_source_service

    max_concurrent = 0
    current_concurrent = 0

    async def mock_get(*args, **kwargs):
        nonlocal max_concurrent, current_concurrent
        current_concurrent += 1
        if current_concurrent > max_concurrent:
            max_concurrent = current_concurrent
        await asyncio.sleep(0.05)
        current_concurrent -= 1

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/xml"}
        return mock_resp

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    test_sources = [
        {"name": f"Src{i}", "url": f"http://example{i}.com/rss.xml", "category_hint": "tech", "authority": 0.7, "qps": 1}
        for i in range(10)
    ]

    def mock_load():
        return test_sources
    monkeypatch.setattr("app.services.rss_source_service.load_rss_sources", mock_load)

    with patch("app.services.rss_source_service.httpx.AsyncClient", return_value=mock_client):
        result = await fresh_service.check_all_sources()

    assert max_concurrent <= rss_source_service._CHECK_CONCURRENCY
    assert result["total"] == 10


# ==========================================================================
# get_source_status tests
# ==========================================================================


def test_get_status_unknown_before_check(fresh_service, monkeypatch):
    test_sources = [
        {"name": "NewSource", "url": "http://new.local/rss.xml", "category_hint": "tech", "authority": 0.8, "qps": 1}
    ]

    def mock_load():
        return test_sources
    monkeypatch.setattr("app.services.rss_source_service.load_rss_sources", mock_load)

    status = fresh_service.get_source_status()
    assert status["unknown"] == 1
    assert status["sources"][0]["status"] == "unknown"


# ==========================================================================
# _build_suggestion tests
# ==========================================================================


def test_build_suggestion_plink_fails(fresh_service):
    suggestion = fresh_service._build_suggestion(
        "https://plink.anyfeeder.com/weixin/test", "fail", 1
    )
    assert suggestion is not None
    assert len(suggestion) > 0


def test_build_suggestion_http_fails(fresh_service):
    suggestion = fresh_service._build_suggestion(
        "http://example.com/rss.xml", "fail", 0
    )
    assert suggestion is not None
    assert len(suggestion) > 0


def test_build_suggestion_ok_returns_none(fresh_service):
    suggestion = fresh_service._build_suggestion(
        "https://example.com/rss.xml", "ok", 0
    )
    assert suggestion is None


# ==========================================================================
# Full RSS YAML structural validation
# ==========================================================================


def test_full_rss_yaml_has_valid_structure():
    with open(RSS_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    assert len(sources) >= 70, f"\u6765\u6e90\u6570\u91cf\u4e0d\u8db3\uff1a\u8981\u6c42 70 \u4e2a\uff0c\u5b9e\u9645 {len(sources)} \u4e2a"

    required_fields = ["name", "url"]
    for src in sources:
        for field in required_fields:
            assert field in src, f"\u7f3a\u5c11\u5fc5\u5907\u5b57\u6bb5: {field}"
        assert src["name"], f"name \u4e0d\u80fd\u4e3a\u7a7a: {name}"
        assert src["url"], f"url \u4e0d\u80fd\u4e3a\u7a7a: {url}"


def test_full_rss_yaml_has_global_config():
    with open(RSS_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "global" in data
    assert data["global"]["timeout_sec"] > 0
    assert data["global"]["retry"] >= 0


def test_full_rss_yaml_categories_covered():
    with open(RSS_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    categories = set()
    for src in sources:
        cat = src.get("category_hint", "")
        if cat:
            categories.add(cat)

    expected_cats = {chr(0x65f6) + chr(0x653f), chr(0x8d22) + chr(0x7ecf), chr(0x79d1) + chr(0x6280), chr(0x6e38) + chr(0x620f), chr(0x4f53) + chr(0x80b2)}
    for cat in expected_cats:
        assert cat in categories, f"\u7f3a\u5c11\u671f\u671b\u7c7b\u522b: {cat}"


def test_full_rss_yaml_urls_are_https_or_http():
    with open(RSS_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    for src in sources:
        url = src.get("url", "")
        name = src.get("name", "")
        assert url.startswith("http://") or url.startswith("https://"), f"URL \u4e0d\u5408\u6cd5: {name} -> {url}"


def test_full_rss_yaml_authority_range():
    with open(RSS_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    for src in sources:
        auth = src.get("authority", 0)
        name = src.get("name", "")
        assert 0.0 <= auth <= 1.0, f"{name} \u7684 authority={auth} \u8d85\u51fa\u8303\u56f4"


def test_full_rss_yaml_no_duplicate_names():
    with open(RSS_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    names = [s.get("name", "") for s in sources]
    dupes = [n for n in names if names.count(n) > 1]
    assert not dupes, f"\u5305\u542b\u91cd\u590d\u540d\u79f0: {set(dupes)}"


def test_full_rss_yaml_has_category_hint():
    with open(RSS_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    for src in sources:
        name = src.get("name", "?")
        assert src.get("category_hint"), f"missing category_hint: {name}"


def test_full_rss_yaml_qps_positive():
    with open(RSS_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    for src in sources:
        name = src.get("name", "?")
        qps = src.get("qps", 1)
        assert isinstance(qps, int) and qps > 0, f"{name} 的 qps={qps} 非正整数"
