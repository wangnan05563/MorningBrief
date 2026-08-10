"""rewriter._fetch_materials 素材周期回溯天数「配置优先于动态值」测试。

回归意图：material_lookback_days 是用户需求里的新字段，用于将选材时间范围
放宽到「最近配置天数」，从选材侧扩展时间跨度获取更多素材（而非依赖 stitch 的
BGM 补足凑短节目）。本测试验证：
- 频道显式配置 material_lookback_days 时，回溯窗口直接用该值；
- 未配置（None）/ 配置为 0 时，回退 _calc_dynamic_fallback_days 动态值（3/7/14 天）；
- 动态值仍正常生效（窗口内的旧素材能被回溯拉入，窗口外的不拉入）；
- 当日素材已充足（>= SELECT_MIN_N）时不触发回溯，配置值不影响选材。

使用内存 DB + monkeypatch AsyncSessionLocal，与 test_rewriter_channel_isolation 同构。
"""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base, normalize_metadata_for_sqlite
# 显式导入 Channel：Material 外键依赖，create_all 时目标表需已注册
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
    """为 rewriter._fetch_materials 提供独立内存 DB 并 patch AsyncSessionLocal。"""
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
async def test_config_overrides_dynamic_when_larger(isolated_sessionlocal):
    """配置 30 天能拉入 20 天前的素材；未配置时动态值(14)拉不进 20 天前的素材。"""
    today = date.today()
    twenty_days_ago = datetime.combine(today - timedelta(days=20), datetime.min.time())

    async with isolated_sessionlocal() as session:
        # 仅 20 天前的一条素材，当日无素材（< SELECT_MIN_N 触发回溯）
        _add_material(session, source="游民星空-资讯", title="旧游戏资讯",
                      url="https://gamersky.com/news/mlb-1", channel_id=9,
                      crawled_at=twenty_days_ago)
        await session.commit()

    # 配置 30 天：20 < 30，回溯窗口覆盖该素材 → 拉入
    with_config = await rewriter._fetch_materials(
        today.isoformat(), channel_id=9, material_lookback_days=30
    )
    assert len(with_config) == 1
    assert with_config[0]["title"] == "旧游戏资讯"

    # 未配置：动态值对「近 7 天无入库」的频道返回 14；20 > 14 → 不拉入
    without_config = await rewriter._fetch_materials(
        today.isoformat(), channel_id=9, material_lookback_days=None
    )
    assert len(without_config) == 0


@pytest.mark.asyncio
async def test_config_zero_treated_as_none(isolated_sessionlocal):
    """配置为 0 视为未配置（>0 才算启用），回退动态值(14)，拉不进 20 天前的素材。"""
    today = date.today()
    twenty_days_ago = datetime.combine(today - timedelta(days=20), datetime.min.time())

    async with isolated_sessionlocal() as session:
        _add_material(session, source="3DM-资讯", title="旧单机资讯",
                      url="https://3dmgame.com/news/mlb-2", channel_id=9,
                      crawled_at=twenty_days_ago)
        await session.commit()

    results = await rewriter._fetch_materials(
        today.isoformat(), channel_id=9, material_lookback_days=0
    )
    assert len(results) == 0


@pytest.mark.asyncio
async def test_dynamic_still_includes_within_window(isolated_sessionlocal):
    """未配置时动态值(14)仍能拉入窗口内（10 天前）的素材，证明动态路径未退化。"""
    today = date.today()
    ten_days_ago = datetime.combine(today - timedelta(days=10), datetime.min.time())

    async with isolated_sessionlocal() as session:
        _add_material(session, source="游民星空-资讯", title="十天前资讯",
                      url="https://gamersky.com/news/mlb-3", channel_id=9,
                      crawled_at=ten_days_ago)
        await session.commit()

    # 未配置（动态=14）：10 < 14 → 拉入
    without_config = await rewriter._fetch_materials(
        today.isoformat(), channel_id=9, material_lookback_days=None
    )
    assert len(without_config) == 1

    # 配置 30：同样拉入（配置值更大，覆盖）
    with_config = await rewriter._fetch_materials(
        today.isoformat(), channel_id=9, material_lookback_days=30
    )
    assert len(with_config) == 1


@pytest.mark.asyncio
async def test_config_exact_window_excludes_beyond(isolated_sessionlocal):
    """配置值被直接使用（非仅比动态大才生效）：配置=14 时 20 天前的素材仍被排除。"""
    today = date.today()
    twenty_days_ago = datetime.combine(today - timedelta(days=20), datetime.min.time())

    async with isolated_sessionlocal() as session:
        _add_material(session, source="3DM-资讯", title="20天前资讯",
                      url="https://3dmgame.com/news/mlb-4", channel_id=9,
                      crawled_at=twenty_days_ago)
        await session.commit()

    results = await rewriter._fetch_materials(
        today.isoformat(), channel_id=9, material_lookback_days=14
    )
    assert len(results) == 0


@pytest.mark.asyncio
async def test_no_fallback_when_daily_sufficient(isolated_sessionlocal):
    """当日素材已 >= SELECT_MIN_N 时不触发回溯：即便配置 30 天，旧素材也不被拉入。"""
    today = date.today()
    midnight = datetime.combine(today, datetime.min.time())
    twenty_days_ago = datetime.combine(today - timedelta(days=20), datetime.min.time())

    async with isolated_sessionlocal() as session:
        # 当日 6 条（>= SELECT_MIN_N=5），足够无需回溯
        for i in range(6):
            _add_material(session, source="游民星空-资讯", title=f"今日游戏{i}",
                          url=f"https://gamersky.com/news/mnb-{i}", channel_id=9,
                          crawled_at=midnight)
        # 20 天前的旧素材：不应被拉入（未触发回溯）
        _add_material(session, source="3DM-资讯", title="20天前旧资讯",
                      url="https://3dmgame.com/news/mnb-old", channel_id=9,
                      crawled_at=twenty_days_ago)
        await session.commit()

    results = await rewriter._fetch_materials(
        today.isoformat(), channel_id=9, material_lookback_days=30
    )
    # 仅当日 6 条，旧素材不混入
    assert len(results) == 6
    assert all(r["title"].startswith("今日游戏") for r in results)
