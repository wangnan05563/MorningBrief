"""全网搜索采集链路测试（T04116）。

覆盖：提示词解析 → 三轮检索（中/英/交叉验证）→ 上一期同源事件去重 →
「据媒体报道」标注 → 密度补搜 → 与 RSS 合并入库（source_type=web_search）。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_web_search_collector.py
"""
from dataclasses import replace
from datetime import date, datetime

import pytest

from app.config import get_settings
from app.models import Channel, Episode, Material, Script
from app.workflow.crawler import search_collector as collector_mod
from app.workflow.crawler import web_search as ws
from app.workflow.crawler import runner as runner_mod


SAMPLE_PROMPT = """# 人工智能每日重点资讯收集指令

## 任务定位
你是一名「人工智能」领域的信息编辑。请通过全网搜索收集过去 24 小时内的重点资讯。

## 信息采集范围（子板块）
- 模型发布
- 行业资本
- 监管政策

## 多轮搜索策略（至少 3 轮）
- 第一轮：使用中文关键词「大模型,多模态、智能体」+ 昨日日期，覆盖国内视角；
- 第二轮：使用英文关键词「LLM,multimodal」+ 昨日日期，覆盖国际视角；
- 第三轮：对关键数据做交叉验证检索，仅保留可确认版本。

## 输出格式
- 全文使用简体中文。
"""


def _result(title, url, content="正文内容" * 60, source="测试站", published=None):
    return ws.SearchResult(
        title=title, url=url, content=content, source=source, published_at=published,
    )


class _FakeProvider:
    name = "fake"

    def __init__(self, responses: list[tuple[str, list[ws.SearchResult]]]):
        self._responses = responses
        self.queries: list[str] = []

    async def search(self, query: str, *, count: int) -> list[ws.SearchResult]:
        self.queries.append(query)
        for marker, results in self._responses:
            if marker in query:
                # 采集器会改写 round/confirmed/title，返回副本避免用例间串味
                return [replace(item) for item in results]
        return []


class _SessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def enable_search(monkeypatch):
    cfg = get_settings()
    for key, value in {
        "WEB_SEARCH_ENABLED": True,
        "WEB_SEARCH_PROVIDER": "fake",
        "WEB_SEARCH_API_KEY": "test-key",
        "WEB_SEARCH_MAX_QUERIES_PER_ROUND": 2,
        "WEB_SEARCH_CROSS_CHECK_TOP": 2,
        "WEB_SEARCH_MAX_DENSITY_QUERIES": 0,
        "WEB_SEARCH_MAX_QUERIES_TOTAL": 12,
        "WEB_SEARCH_MAX_RESULTS_PER_QUERY": 5,
        "WEB_SEARCH_MAX_ITEMS": 10,
        "WEB_SEARCH_PREV_SIMILARITY": 8,
        "WEB_SEARCH_CHARS_PER_SEC": 0.01,
        "WEB_SEARCH_TASK_CONCURRENCY": 2,
        "WEB_SEARCH_FETCH_CONCURRENCY": 2,
    }.items():
        monkeypatch.setattr(cfg, key, value, raising=False)
    return cfg


async def _seed_channel(session, *, prompt=SAMPLE_PROMPT, **kwargs) -> Channel:
    channel = Channel(
        name=kwargs.pop("name", "AI 前沿"),
        channel_type=kwargs.pop("channel_type", "news"),
        selection_strategy=kwargs.pop("selection_strategy", "rss"),
        search_prompt=prompt,
        **kwargs,
    )
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


async def _seed_previous_episode(session, channel_id: int, topics: list[str]) -> None:
    script = Script(
        workflow_id="wf-prev",
        episode_date=date(2026, 11, 2),
        full_text="上一期稿件",
        segments=[{"seq": i + 1, "title": t, "content": "上期内容"}
                  for i, t in enumerate(topics)],
    )
    session.add(script)
    await session.commit()
    await session.refresh(script)
    session.add(Episode(
        date=date(2026, 11, 2),
        channel_id=channel_id,
        title=topics[0] if topics else "上一期",
        duration=600,
        audio_url="https://example.com/prev.mp3",
        script_id=script.id,
        status="published",
    ))
    await session.commit()


# ===== 提示词解析 / 纯函数 =====

def test_parse_skeleton_prompt():
    spec = ws.parse_search_prompt(SAMPLE_PROMPT)
    assert spec.topic == "人工智能"
    assert spec.subsections == ["模型发布", "行业资本", "监管政策"]
    assert spec.keywords_zh == ["大模型", "多模态", "智能体"]
    assert spec.keywords_en == ["LLM", "multimodal"]
    assert spec.usable is True


def test_parse_prompt_without_skeleton_falls_back_to_topic():
    spec = ws.parse_search_prompt("# 财经早报\n\n随便写的提示词")
    assert spec.topic == "财经早报"
    assert spec.keywords_zh == ["财经早报"]
    assert spec.usable is True


def test_parse_empty_prompt():
    assert ws.parse_search_prompt(None).usable is False
    assert ws.parse_search_prompt("").usable is False


def test_merge_results_dedupes_url_and_similar_titles():
    merged = ws.merge_results([
        _result("同一事件标题", "https://a.com/x"),
        _result("同一事件标题", "https://b.com/y"),  # 标题近似 → 合并
        _result("另一条新闻", "https://a.com/x"),     # URL 归一化后重复 → 合并
        _result("完全不同的内容", "https://c.com/z"),
    ])
    assert [item.url for item in merged] == ["https://a.com/x", "https://c.com/z"]


def test_classify_candidate_against_previous_topics():
    previous = ["某公司发布第三季度财报", "某行业年度峰会召开"]

    kind, _ = ws.classify_candidate(_result("某公司发布第三季度财报", "https://a/1"), previous, 8)
    assert kind == "duplicate"

    kind, title = ws.classify_candidate(
        _result("某行业年度峰会召开", "https://a/2", content="最新进展：新增两项合作"),
        previous, 8,
    )
    assert kind == "progress"
    assert title == "【新增进展】某行业年度峰会召开"

    kind, _ = ws.classify_candidate(_result("全新独立事件", "https://a/3"), previous, 8)
    assert kind == "new"


# ===== provider 契约 =====

async def test_bocha_provider_maps_payload_and_results(monkeypatch):
    seen = {}

    async def fake_post(url, payload, headers, timeout):
        seen.update(url=url, payload=payload, headers=headers, timeout=timeout)
        return {"code": 200, "data": {"webPages": {"value": [
            {"name": "标题一", "url": "https://x.com/1", "summary": "摘要",
             "siteName": "站点", "datePublished": "2026-11-02T08:00:00+08:00"},
            {"name": "", "url": "https://x.com/2"},  # 缺标题 → 丢弃
        ]}}}

    monkeypatch.setattr(ws, "_post_json", fake_post)
    results = await ws.BochaProvider("key-1").search("查询", count=3)

    assert seen["url"].endswith("/v1/web-search")
    assert seen["payload"]["freshness"] == "oneDay"
    assert seen["headers"]["Authorization"] == "Bearer key-1"
    assert len(results) == 1
    assert results[0].title == "标题一"
    assert results[0].source == "站点"
    assert results[0].published_at is not None


async def test_tavily_provider_maps_payload_and_results(monkeypatch):
    seen = {}

    async def fake_post(url, payload, headers, timeout):
        seen.update(url=url, payload=payload)
        return {"results": [{
            "title": "T", "url": "https://t.com/1", "content": "内容",
            "published_date": "2026-11-02",
        }]}

    monkeypatch.setattr(ws, "_post_json", fake_post)
    results = await ws.TavilyProvider("tk").search("query", count=4)

    assert seen["url"].endswith("/search")
    assert seen["payload"]["api_key"] == "tk"
    assert seen["payload"]["topic"] == "news"
    assert seen["payload"]["days"] == 1
    assert results[0].content == "内容"
    assert results[0].published_at is not None


async def test_unknown_provider_is_treated_as_disabled(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "WEB_SEARCH_ENABLED", True, raising=False)
    monkeypatch.setattr(cfg, "WEB_SEARCH_PROVIDER", "nope", raising=False)
    monkeypatch.setattr(cfg, "WEB_SEARCH_API_KEY", "k", raising=False)
    assert ws.build_provider(cfg) is None


def test_build_provider_from_settings(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "WEB_SEARCH_ENABLED", True, raising=False)
    monkeypatch.setattr(cfg, "WEB_SEARCH_PROVIDER", "Bocha", raising=False)
    monkeypatch.setattr(cfg, "WEB_SEARCH_API_KEY", "k", raising=False)
    monkeypatch.setattr(cfg, "WEB_SEARCH_ENDPOINT", "", raising=False)

    provider = ws.build_provider(cfg)
    assert isinstance(provider, ws.BochaProvider)


def test_material_source_type_registers_web_search():
    from app.models.material import MaterialSourceType

    assert MaterialSourceType.web_search.value == "web_search"


# ===== 采集编排 =====

async def test_disabled_search_returns_reason_without_db(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "WEB_SEARCH_ENABLED", False, raising=False)

    stats = await collector_mod.collect_search_materials("wf-t", "2026-11-03", 999999)

    assert stats["enabled"] is False
    assert "WEB_SEARCH_ENABLED" in stats["reason"]
    assert stats["materials"] == []


async def test_missing_api_key_returns_reason(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "WEB_SEARCH_ENABLED", True, raising=False)
    monkeypatch.setattr(cfg, "WEB_SEARCH_PROVIDER", "bocha", raising=False)
    monkeypatch.setattr(cfg, "WEB_SEARCH_API_KEY", "", raising=False)

    stats = await collector_mod.collect_search_materials("wf-t", "2026-11-03", 1)

    assert stats["enabled"] is False
    assert "WEB_SEARCH_API_KEY" in stats["reason"]


async def test_channel_without_prompt_is_skipped(enable_search, db_session, monkeypatch):
    channel = await _seed_channel(db_session, prompt=None)
    monkeypatch.setattr(collector_mod, "build_provider", lambda cfg: _FakeProvider([]))
    monkeypatch.setattr(collector_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))

    stats = await collector_mod.collect_search_materials("wf-t", "2026-11-03", channel.id)

    assert stats["enabled"] is False
    assert "search_prompt" in stats["reason"]


async def test_collect_runs_three_rounds_and_marks_unverified(
    enable_search, db_session, monkeypatch,
):
    channel = await _seed_channel(db_session)
    provider = _FakeProvider([
        ("大模型", [_result("候选A", "https://a.com/1"), _result("候选B", "https://a.com/2")]),
        ("LLM", [_result("候选C", "https://c.com/3")]),
        ("候选A", [_result("候选A", "https://d.com/4")]),  # 交叉验证第二信源
    ])
    monkeypatch.setattr(collector_mod, "build_provider", lambda cfg: provider)
    monkeypatch.setattr(collector_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))

    stats = await collector_mod.collect_search_materials("wf-t", "2026-11-03", channel.id)

    assert stats["enabled"] is True
    assert stats["rounds"] == {"zh": 2, "en": 2, "cross": 2, "density": 0}
    # 中文/英文/交叉各 2 次 = 6 次检索，日期窗口为工作流前一天
    assert stats["queries"] == 6
    assert all("2026-11-02" in q for q in provider.queries)
    # 交叉验证结果与候选 A 标题近似 → 合并后仍是 3 条
    assert [m["title"] for m in stats["materials"]] == ["候选A", "候选B", "候选C"]
    assert all(m["_source_type"] == "web_search" for m in stats["materials"])
    # A 被第二信源确认；B/C 无交叉验证 → 标注「据媒体报道」
    by_title = {m["title"]: m for m in stats["materials"]}
    assert not by_title["候选A"]["content"].startswith("据媒体报道")
    assert by_title["候选B"]["content"].startswith("据媒体报道")
    assert by_title["候选C"]["content"].startswith("据媒体报道")
    assert stats["verified"] == 1
    assert stats["unverified"] == 2


async def test_previous_episode_same_event_dedup_and_progress_kept(
    enable_search, db_session, monkeypatch,
):
    channel = await _seed_channel(db_session)
    await _seed_previous_episode(
        db_session, channel.id, ["某公司发布第三季度财报", "某行业年度峰会召开"],
    )
    provider = _FakeProvider([
        ("大模型", [
            _result("某公司发布第三季度财报", "https://a.com/dup"),
            _result("某行业年度峰会召开", "https://a.com/progress",
                    content="最新进展：新增两项合作，双方签署备忘录。" * 8),
            _result("全新独立事件", "https://a.com/new"),
        ]),
        ("LLM", []),
    ])
    monkeypatch.setattr(collector_mod, "build_provider", lambda cfg: provider)
    monkeypatch.setattr(collector_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))

    stats = await collector_mod.collect_search_materials("wf-t", "2026-11-03", channel.id)

    assert stats["prev_event_skipped"] == 1
    assert stats["progress_kept"] == 1
    titles = [m["title"] for m in stats["materials"]]
    assert "某公司发布第三季度财报" not in titles
    assert "【新增进展】某行业年度峰会召开" in titles
    assert "全新独立事件" in titles


async def test_density_gap_triggers_subsection_queries(
    enable_search, db_session, monkeypatch,
):
    # 目标字数抬高到 60000：前两轮的内容（约 300 字/条）必然不足
    monkeypatch.setattr(enable_search, "WEB_SEARCH_CHARS_PER_SEC", 100, raising=False)
    monkeypatch.setattr(enable_search, "WEB_SEARCH_MAX_DENSITY_QUERIES", 2, raising=False)

    channel = await _seed_channel(db_session)
    provider = _FakeProvider([
        ("大模型", [_result("候选A", "https://a.com/1")]),
        ("LLM", [_result("候选C", "https://c.com/3")]),
        ("模型发布", [_result("补搜素材", "https://a.com/extra", content="补" * 61000)]),
    ])
    monkeypatch.setattr(collector_mod, "build_provider", lambda cfg: provider)
    monkeypatch.setattr(collector_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))

    stats = await collector_mod.collect_search_materials("wf-t", "2026-11-03", channel.id)

    assert stats["rounds"]["density"] == 2
    assert any("人工智能 模型发布 2026-11-02" == q for q in provider.queries)
    assert "补搜素材" in [m["title"] for m in stats["materials"]]
    assert stats["density_met"] is True
    assert stats["collected_chars"] >= stats["target_chars"]


async def test_short_snippet_falls_back_to_article_extract(
    enable_search, db_session, monkeypatch,
):
    channel = await _seed_channel(db_session)
    provider = _FakeProvider([
        ("大模型", [_result("短摘要条目", "https://a.com/short", content="短讯")]),
        ("LLM", []),
    ])

    async def fake_extract(url):
        return {"content": "抓取到的正文" * 40, "cover_url": "https://a.com/cover.jpg",
                "images": ["https://a.com/cover.jpg"]}

    monkeypatch.setattr(collector_mod, "build_provider", lambda cfg: provider)
    monkeypatch.setattr(collector_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))
    monkeypatch.setattr(collector_mod, "extract_article", fake_extract)

    stats = await collector_mod.collect_search_materials("wf-t", "2026-11-03", channel.id)

    material = stats["materials"][0]
    assert material["content"].startswith("据媒体报道：抓取到的正文")
    assert material["cover_url"] == "https://a.com/cover.jpg"
    assert material["images"] == ["https://a.com/cover.jpg"]


# ===== 与 runner 合并入库 =====

async def test_runner_merges_web_search_materials_with_channel_id(
    db_session, monkeypatch,
):
    channel = await _seed_channel(db_session)
    prepared = {
        "title": "搜索素材标题",
        "url": "https://search.example.com/a",
        "simhash": "0" * 16,
        "content": "搜索正文" * 50,
        "summary": "搜索摘要",
        "source": "测试站",
        "category_hint": "人工智能",
        "published_at": None,
        "cover_url": None,
        "images": [],
        "_source_type": "web_search",
    }

    async def fake_search(workflow_id, date_str, channel_id, *, existing_urls=None):
        return {
            "enabled": True, "reason": None, "error": None, "provider": "fake",
            "queries": 3, "rounds": {"zh": 1, "en": 1, "cross": 1, "density": 0},
            "candidates": 1, "kept": 1, "prev_event_skipped": 0, "progress_kept": 0,
            "verified": 1, "unverified": 0, "target_chars": 100,
            "collected_chars": 200, "density_met": True, "errors": [],
            "materials": [prepared],
        }

    monkeypatch.setattr(runner_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))
    monkeypatch.setattr(runner_mod, "load_rss_sources", lambda: [])
    monkeypatch.setattr(runner_mod, "collect_search_materials", fake_search)

    result = await runner_mod.run("wf-t04116", "2026-11-03", channel.id)

    assert result["material_count"] == 1
    assert result["web_search"]["enabled"] is True
    assert any(sd["name"] == "全网搜索" for sd in result["source_details"])

    row = (await db_session.execute(
        Material.__table__.select().where(Material.url == prepared["url"])
    )).mappings().one()
    assert row["source_type"] == "web_search"
    assert row["channel_id"] == channel.id
    assert row["workflow_id"] == "wf-t04116"


async def test_runner_keeps_zero_material_failure_when_search_disabled(
    db_session, monkeypatch,
):
    channel = await _seed_channel(db_session)

    async def fake_search(workflow_id, date_str, channel_id, *, existing_urls=None):
        return {"enabled": False, "reason": "未启用", "materials": []}

    monkeypatch.setattr(runner_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))
    monkeypatch.setattr(runner_mod, "load_rss_sources", lambda: [])
    monkeypatch.setattr(runner_mod, "collect_search_materials", fake_search)

    with pytest.raises(RuntimeError) as excinfo:
        await runner_mod.run("wf-t04116-off", "2026-11-03", channel.id)

    assert "未获取到有效素材" in str(excinfo.value)
    details = excinfo.value.failure_details
    assert details["web_search"]["enabled"] is False
