"""
测试基础设施

设计目标：所有测试在无 SQLite / cache / LLM / TTS / 外部包的环境下可运行。

实现策略：
1. 顶部为缺失的第三方库注入 stub，让 app 包能完成 import
2. SQLite 内存数据库（每个测试函数独立 engine，保证隔离）
3. 进程内 TTLCache 替代 Redis（无需 fixture，cache 是模块级单例）
4. TestClient 测试 API 时不启动 lifespan（避免触发 APScheduler）
"""
import sys
import types
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest

# ==========================================================================
# 第 1 步：为缺失的第三方库注入 stub（必须在 import app.* 之前完成）
# 设计原因：workflow_scheduler / rewriter 等模块 import 时
# 会触发对 apscheduler / openai / ahocorasick / qcloud_cos / feedparser
# 的导入。本地 Python 3.14 可能未安装这些包，直接 mock 以保证 app 包可加载。
# 真实包已安装时不覆盖，让单元能跑在真实环境里。
# V1.2：article_parser 改用 httpx + selectolax（均已安装），不再需要 newspaper stub。
# ==========================================================================


# ---- apscheduler.schedulers.asyncio ----
# workflow_scheduler 模块顶部 from apscheduler.schedulers.asyncio import AsyncIOScheduler
class _FakeAsyncIOScheduler:
    """APScheduler 占位：仅暴露 workflow_scheduler 调用的方法，避免真实调度。"""

    def __init__(self, *args, **kwargs):
        pass

    def add_job(self, *args, **kwargs):
        return None

    def start(self):
        return None

    def shutdown(self, *args, **kwargs):
        return None


_aps_mod = types.ModuleType("apscheduler")
_aps_sched_mod = types.ModuleType("apscheduler.schedulers")
_aps_asyncio_mod = types.ModuleType("apscheduler.schedulers.asyncio")
_aps_asyncio_mod.AsyncIOScheduler = _FakeAsyncIOScheduler
_aps_sched_mod.asyncio = _aps_asyncio_mod
_aps_mod.schedulers = _aps_sched_mod
sys.modules.setdefault("apscheduler", _aps_mod)
sys.modules.setdefault("apscheduler.schedulers", _aps_sched_mod)
sys.modules.setdefault("apscheduler.schedulers.asyncio", _aps_asyncio_mod)


# ---- ahocorasick ----
# sensitive_filter.py 中 import ahocorasick；用伪 Automaton 让 AC 自动机逻辑可测试
class _FakeAutomaton:
    """简易 AC 自动机占位：用 str.find 实现 contains/find_all/replace 行为。

    命中语义与 pyahocorasick 一致：iter 返回 (end_idx, value) 元组。
    仅用于测试环境；真实环境装了 ahocorasick 会优先使用真实包。
    """

    def __init__(self):
        self._words: dict[str, tuple] = {}

    def add_word(self, word: str, value) -> None:
        self._words[word] = value

    def make_automaton(self) -> None:
        pass

    def iter(self, text: str):
        # 按位置升序返回所有命中（end_idx, value），与真实 AC 行为对齐
        hits: list[tuple[int, object]] = []
        for word, value in self._words.items():
            start = 0
            while True:
                idx = text.find(word, start)
                if idx == -1:
                    break
                hits.append((idx + len(word) - 1, value))
                start = idx + 1
        hits.sort(key=lambda x: x[0])
        for hit in hits:
            yield hit


_aho_mod = types.ModuleType("ahocorasick")
_aho_mod.Automaton = _FakeAutomaton
sys.modules.setdefault("ahocorasick", _aho_mod)


# ---- feedparser ----
# rss_spider.py 中 import feedparser；测试不覆盖，仅 stub
_fp_mod = types.ModuleType("feedparser")
_fp_mod.parse = lambda *a, **k: {}
sys.modules.setdefault("feedparser", _fp_mod)


# ---- openai ----
# rewriter.py 中 from openai import AsyncOpenAI；stub 占位
_oai_mod = types.ModuleType("openai")
_oai_mod.AsyncOpenAI = type("AsyncOpenAI", (), {"__init__": lambda self, *a, **k: None})
sys.modules.setdefault("openai", _oai_mod)


# ---- qcloud_cos ----
# tts/uploader.py 中 from qcloud_cos import CosConfig, CosS3Client
_cos_mod = types.ModuleType("qcloud_cos")
_cos_mod.CosConfig = type("CosConfig", (), {"__init__": lambda self, **k: None})
_cos_mod.CosS3Client = type("CosS3Client", (), {"__init__": lambda self, *a, **k: None})
sys.modules.setdefault("qcloud_cos", _cos_mod)


# ---- jieba ----
# simhash.py 中 import jieba；用按字符切分替代中文分词
# SimHash 测试只依赖分词的确定性（相同输入相同输出），不依赖具体分词质量
_jieba_mod = types.ModuleType("jieba")
_jieba_mod.lcut = lambda text, *a, **k: list(text)
sys.modules.setdefault("jieba", _jieba_mod)


# ==========================================================================
# 第 2 步：导入 app 模块（此时所有依赖已 stub）
# ==========================================================================
# SQLAlchemy 默认 Base 来自 app.database；测试用同一个 Base 才能让 metadata 一致
from app.database import Base, get_db  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from fastapi.testclient import TestClient  # noqa: E402

# create_app 不调用 lifespan：TestClient(app) 不 with 即可避免启动调度器
from app.main import create_app  # noqa: E402
from app.core.security import create_access_token  # noqa: E402


# ==========================================================================
# 第 3 步：fixtures
# ==========================================================================


# SQLite 索引名规范化：复用 app.database 中的实现（避免重复代码）
# 索引名跨表唯一 + BigInteger 主键改 Integer 让 SQLite AUTOINCREMENT 生效
# 详见 app/database.py:normalize_metadata_for_sqlite
from app.database import normalize_metadata_for_sqlite  # noqa: E402


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """每个测试函数独立的内存 SQLite session，保证测试间完全隔离。

    使用 function scope：每个测试新建一张干净表，避免上一测试残留数据干扰。
    expire_on_commit=False 让 commit 后对象仍可访问，与生产配置一致。
    """
    # 适配 SQLite 元数据差异（仅第一次执行时实际修改）
    normalize_metadata_for_sqlite()

    # SQLite 内存库 + aiosqlite 驱动，无外部依赖
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        # metadata.create_all 一次性创建所有表，自动处理外键依赖顺序
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clear_cache_manager():
    """每个测试前清空进程内 TTLCache 单例，保证测试间缓存隔离。

    V1.2 起 cache 是 app.cache.manager.cache 模块级单例，跨测试会残留
    episode:today / ad:placement:* 等键，导致下一个测试命中旧缓存。
    原 fake_redis 通过独立 FakeServer 保证隔离，现在改为每个测试前显式清空。
    yield 之前清空保证进入测试时 cache 为空，无需 tearDown。
    """
    from app.cache.manager import cache as _cache
    _cache._cache.clear()
    _cache._counters.clear()
    _cache._counters_ttl.clear()
    yield


@pytest.fixture
def app(monkeypatch):
    """FastAPI 应用实例。

    V1.2 起不再有 redis_client 模块：health 路由直接用 app.cache.manager.cache
    单例做读写探测，cache 是进程内 TTLCache，无需任何 patch 即可在测试中工作。
    仅用空 lifespan 替换原 lifespan，避免 TestClient with 时启动 APScheduler。
    """
    from contextlib import asynccontextmanager

    app = create_app()
    # 用空 lifespan 替换原 lifespan：原 lifespan 会启动 APScheduler，
    # 测试环境不需要这些副作用
    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield
    app.router.lifespan_context = _noop_lifespan
    return app


@pytest.fixture
def client(app, db_session):
    """同步 TestClient：覆盖 get_db 依赖，路由层拿到的就是测试 session。

    TestClient(app) 不进入 with 块，避免触发 lifespan；通过 dependency_overrides
    把 get_db 替换为返回 db_session 的生成器。
    """
    async def _override_get_db():
        # 路由层通过 Depends(get_db) 拿 session，这里直接 yield 测试 session
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def user_token():
    """C 端用户 token（type=user），用于带鉴权接口测试。

    返回 (token, jti, exp) 三元组，便于 logout/黑名单测试断言。
    """
    token, jti, expires_in = create_access_token("1", token_type="user")
    exp = int((datetime.now(timezone.utc) + timedelta(seconds=expires_in)).timestamp())
    return {"token": token, "jti": jti, "exp": exp}


@pytest.fixture
def admin_token():
    """B 端运营 token（type=admin），带 role=admin claims。"""
    token, jti, expires_in = create_access_token(
        "1",
        token_type="admin",
        extra_claims={"username": "admin", "role": "admin"},
    )
    exp = int((datetime.now(timezone.utc) + timedelta(seconds=expires_in)).timestamp())
    return {"token": token, "jti": jti, "exp": exp}
