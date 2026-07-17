"""rewriter 频道级素材隔离回归测试。

回归场景：wf-20260717-0010 主机游戏频道（channel_id=9）已配置 4 个游戏 RSS 源
与 9 个游戏关键词，但最终生成的节目消费了 36氪/人民网等非游戏历史遗留素材。

根因：_fetch_materials 当日查询与回溯查询均使用 `OR channel_id IS NULL`
兼容历史遗留素材，导致已配置 rss_sources/keywords 的专门频道绕过
频道级数据源白名单与关键词过滤，混入不相关内容。

修复后：channel_id 非空时严格按 channel_id 过滤，历史遗留 NULL 素材
仅允许被全局工作流（channel_id=None）消费。
"""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base, normalize_metadata_for_sqlite
# 显式导入 Channel 让 SQLAlchemy 将 channel 表注册到 Base.metadata，
# 否则 Material 的外键依赖在 create_all 时找不到目标表
from app.models.channel import Channel  # noqa: F401
from app.models.material import Material, MaterialSourceType, MaterialStatus
from app.workflow.llm import rewriter


def _add_material(session, *, source, title, url, channel_id, crawled_at):
    """插入一条 pending 素材，封装必填字段。"""
    session.add(Material(
        source=source,
        source_type=MaterialSourceType.rss.value,
        title=title,
        content=f"{title} 正文",
        url=url,
        crawled_at=crawled_at,
        status=MaterialStatus.pending.value,
        channel_id=channel_id,
    ))


@pytest.fixture
async def isolated_sessionlocal(monkeypatch):
    """为 rewriter._fetch_materials 提供独立内存 DB 并 patch AsyncSessionLocal。

    _fetch_materials 使用模块级 AsyncSessionLocal，无法通过 db_session fixture
    注入；这里自建 engine + sessionmaker 并 monkeypatch，测试结束自动还原。
    """
    normalize_metadata_for_sqlite()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_local = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(rewriter, "AsyncSessionLocal", session_local)
    yield session_local
    await engine.dispose()


@pytest.mark.asyncio
async def test_dedicated_channel_excludes_null_legacy(isolated_sessionlocal):
    """专门频道当日查询不消费 channel_id IS NULL 的历史遗留素材。"""
    today = date.today()
    midnight = datetime.combine(today, datetime.min.time())

    async with isolated_sessionlocal() as session:
        # 历史遗留 NULL 素材（36氪，非游戏）——修复前会被错误选中
        _add_material(session, source="36氪", title="科技公司融资新闻",
                      url="https://36kr.com/p/iso-1", channel_id=None,
                      crawled_at=midnight)
        # 本频道素材（游民星空，游戏）——应被选中
        _add_material(session, source="游民星空-资讯", title="PS5新作首发评测",
                      url="https://gamersky.com/news/iso-1", channel_id=9,
                      crawled_at=midnight)
        await session.commit()

    results = await rewriter._fetch_materials(today.isoformat(), channel_id=9)

    assert len(results) == 1
    assert results[0]["source"] == "游民星空-资讯"
    assert results[0]["title"] == "PS5新作首发评测"


@pytest.mark.asyncio
async def test_global_mode_includes_null_legacy(isolated_sessionlocal):
    """全局工作流（channel_id=None）仍可消费 NULL 历史遗留素材，保持向后兼容。"""
    today = date.today()
    midnight = datetime.combine(today, datetime.min.time())

    async with isolated_sessionlocal() as session:
        _add_material(session, source="36氪", title="科技公司融资新闻",
                      url="https://36kr.com/p/iso-2", channel_id=None,
                      crawled_at=midnight)
        _add_material(session, source="游民星空-资讯", title="PS5新作首发评测",
                      url="https://gamersky.com/news/iso-2", channel_id=9,
                      crawled_at=midnight)
        await session.commit()

    # channel_id=None → 全局模式，查询全部 pending（含 NULL）
    results = await rewriter._fetch_materials(today.isoformat(), channel_id=None)

    assert len(results) == 2


@pytest.mark.asyncio
async def test_fallback_excludes_null_legacy_for_dedicated_channel(isolated_sessionlocal):
    """当日素材不足触发回溯时，专门频道也不消费 NULL 历史素材。

    回归场景：channel_id=9 当日 pending=0，触发 FALLBACK_DAYS=3 回溯，
    修复前回溯查询带 OR channel_id IS NULL，混入 2 天前的 36氪 素材。
    """
    today = date.today()
    two_days_ago = datetime.combine(today - timedelta(days=2), datetime.min.time())

    async with isolated_sessionlocal() as session:
        # 2 天前的 NULL 历史素材——修复前回溯会错误选中
        _add_material(session, source="36氪", title="旧科技新闻",
                      url="https://36kr.com/p/iso-3", channel_id=None,
                      crawled_at=two_days_ago)
        # 2 天前的 channel_id=9 游戏素材——回溯应选中
        _add_material(session, source="3DM-资讯", title="旧游戏资讯",
                      url="https://3dmgame.com/news/iso-3", channel_id=9,
                      crawled_at=two_days_ago)
        await session.commit()

    results = await rewriter._fetch_materials(today.isoformat(), channel_id=9)

    # 回溯只返回 channel_id=9 的素材，不含 NULL 历史遗留
    assert len(results) == 1
    assert results[0]["source"] == "3DM-资讯"
