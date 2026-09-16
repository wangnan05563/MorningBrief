"""crawl 结果判定与上传驱动频道素材池兜底测试（T00649）。

背景：用户工作流 `wf-20260916-0002` 报
`步骤 crawl 失败: 爬虫未获取到有效素材（原始 1 条，提取 1 条，入库 0 条）`。
分析：audiobook 频道不爬通用资讯源、只爬「书籍书源」（如豆瓣书评），
该条书评 URL **上次已入库** → 去重命中 → 新增 0 → 旧逻辑把"入库 0"一律判失败，
用户重跑必然失败（而素材其实已在池中可复用）。

修复后的判定契约：
- `decide_crawl_outcome`：有新增→ok；无新增但去重命中→**reuse（成功复用）**；两者皆无→fail；
- `_count_channel_pending_materials`：仅**上传驱动**频道（outline/manual）才以素材池判断可用性，
  RSS 驱动频道仍严格按抓取结果（避免池内旧 pending 素材掩盖抓取失败、发布陈旧内容）。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_crawl_dedup_outcome.py
"""
from datetime import date

import pytest

from app.models import Channel, Material
from app.models.material import MaterialStatus
from app.workflow.crawler import runner as runner_mod
from app.workflow.crawler.runner import _count_channel_pending_materials, decide_crawl_outcome


class TestDecideCrawlOutcome:
    @pytest.mark.parametrize(
        "material_count,duplicates,expected,label",
        [
            (1, 0, "ok", "有新增素材"),
            (5, 2, "ok", "新增与去重混合仍以新增为准"),
            (0, 1, "reuse", "仅去重命中→成功复用（用户重跑场景）"),
            (0, 3, "reuse", "全部条目命中→成功复用"),
            (0, 0, "fail", "既无新增也无去重→真无素材，需阻断"),
        ],
    )
    def test_outcome(self, material_count, duplicates, expected, label):
        assert decide_crawl_outcome(material_count, duplicates) == expected, label


class _SessionCtx:
    """把测试会话包装成 async context manager（模拟 AsyncSessionLocal()）。"""

    def __init__(self, session):
        self._s = session

    async def __aenter__(self):
        return self._s

    async def __aexit__(self, *exc):
        return False


async def _seed_channel(session, strategy: str, channel_type: str = "audiobook") -> Channel:
    ch = Channel(name=f"T00649-{strategy}", channel_type=channel_type, selection_strategy=strategy)
    session.add(ch)
    await session.commit()
    await session.refresh(ch)
    return ch


async def _seed_material(session, channel_id: int, status: str, title: str = "章节一") -> Material:
    m = Material(
        source="我只知道人是什么",
        source_type="list",
        title=title,
        content="正文" * 50,
        url=f"https://example.com/t00649/{channel_id}/{title}",
        status=status,
        channel_id=channel_id,
        crawled_at=date.today(),
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


@pytest.mark.asyncio
async def test_pool_counted_for_outline_channel(db_session, monkeypatch):
    """outline（上传驱动）频道：池中有 pending 素材 → 计为可用。"""
    monkeypatch.setattr(runner_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))
    ch = await _seed_channel(db_session, "outline")
    await _seed_material(db_session, ch.id, MaterialStatus.pending.value)
    assert await _count_channel_pending_materials(ch.id) == 1


@pytest.mark.asyncio
async def test_pool_counted_for_manual_channel(db_session, monkeypatch):
    monkeypatch.setattr(runner_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))
    ch = await _seed_channel(db_session, "manual")
    await _seed_material(db_session, ch.id, MaterialStatus.pending.value, "章节A")
    await _seed_material(db_session, ch.id, MaterialStatus.pending.value, "章节B")
    assert await _count_channel_pending_materials(ch.id) == 2


@pytest.mark.asyncio
async def test_rss_channel_not_fallback_to_pool(db_session, monkeypatch):
    """RSS 驱动频道不得以素材池兜底（防止掩盖抓取失败 → 发布陈旧内容）。"""
    monkeypatch.setattr(runner_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))
    ch = await _seed_channel(db_session, "rss", channel_type="news")
    await _seed_material(db_session, ch.id, MaterialStatus.pending.value)
    assert await _count_channel_pending_materials(ch.id) == 0


@pytest.mark.asyncio
async def test_selected_materials_not_counted(db_session, monkeypatch):
    """已被上次选题消费（selected）的素材不计入可用，需重跑前重置为 pending。"""
    monkeypatch.setattr(runner_mod, "AsyncSessionLocal", lambda: _SessionCtx(db_session))
    ch = await _seed_channel(db_session, "outline")
    await _seed_material(db_session, ch.id, MaterialStatus.selected.value)
    assert await _count_channel_pending_materials(ch.id) == 0


@pytest.mark.asyncio
async def test_no_channel_returns_zero(monkeypatch):
    assert await _count_channel_pending_materials(None) == 0
