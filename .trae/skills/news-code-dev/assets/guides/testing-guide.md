# 测试开发指南

本文档面向 MorningBrief 项目测试开发，涵盖单元测试、集成测试、E2E 测试的编写方法和最佳实践。

## 1. 测试架构

### 测试框架

项目使用 pytest 作为测试框架，配合以下插件：

| 插件 | 用途 |
|------|------|
| pytest-asyncio | 异步测试支持 |
| fakeredis | Redis 模拟 |
| aiosqlite | 内存 SQLite 数据库 |
| pytest-cov | 覆盖率统计 |
| pytest-mock | Mock 支持 |

### 测试目录结构

```
backend/tests/
├── conftest.py              # 共享 fixtures
├── unit/                    # 单元测试
│   ├── test_news_service.py
│   ├── test_llm_service.py
│   └── test_audio_processor.py
├── integration/             # 集成测试
│   ├── test_news_api.py
│   └── test_auth_api.py
├── e2e/                     # 端到端测试
│   └── test_workflow.py
├── fixtures/                # 测试数据
│   ├── news_data.json
│   └── user_data.json
└── utils/                   # 测试工具
    └── test_helpers.py
```

### 测试命名规范

```python
# 文件名：test_{模块名}.py
# 测试类：Test{服务名}
# 测试方法：test_{方法名}_{场景}_{预期结果}

def test_get_news_by_id_returns_data_when_exists():
    """获取新闻：存在时返回数据。"""

def test_get_news_by_id_returns_none_when_not_found():
    """获取新闻：不存在时返回 None。"""

def test_create_news_raises_error_when_title_empty():
    """创建新闻：标题为空时抛出错误。"""
```

## 2. 单元测试编写

### 服务层单元测试

```python
# tests/unit/test_news_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.news_service import NewsService


@pytest.fixture
def mock_db():
    """模拟数据库会话。"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def mock_redis():
    """模拟 Redis 客户端。"""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def news_service(mock_db, mock_redis):
    """创建新闻服务实例。"""
    return NewsService(db=mock_db, redis_client=mock_redis)


@pytest.mark.asyncio
async def test_get_by_id_returns_cached_data(news_service, mock_redis):
    """当缓存命中时，直接返回缓存数据。"""
    import json
    mock_redis.get.return_value = json.dumps({"id": 1, "title": "测试"})
    
    result = await news_service.get_by_id(1)
    
    assert result is not None
    assert result["title"] == "测试"
    mock_redis.get.assert_called_once()
    # 数据库查询不应执行
    mock_redis.setex.assert_not_called()


@pytest.mark.asyncio
async def test_get_by_id_fetches_from_db_when_cache_miss(news_service, mock_db, mock_redis):
    """缓存未命中时，从数据库获取。"""
    mock_redis.get.return_value = None  # 缓存未命中
    
    mock_news = MagicMock()
    mock_news.to_dict.return_value = {"id": 1, "title": "测试新闻"}
    mock_db.execute.return_value.scalar_one_or_none.return_value = mock_news
    
    result = await news_service.get_by_id(1)
    
    assert result["id"] == 1
    mock_redis.setex.assert_called_once()  # 写入缓存


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_found(news_service, mock_db, mock_redis):
    """不存在时返回 None。"""
    mock_redis.get.return_value = None
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    
    result = await news_service.get_by_id(999)
    
    assert result is None
```

**为什么使用 MagicMock**：隔离被测单元，只测试服务逻辑，不依赖真实的数据库和 Redis。

### 工作流模块测试

```python
# tests/unit/test_sensitive_filter.py
import pytest
from app.utils.sensitive_filter import SensitiveWordFilter


@pytest.fixture
def filter_instance():
    """创建并初始化敏感词过滤器。"""
    f = SensitiveWordFilter()
    f.load_words(["敏感词1", "敏感词2", "test"])
    return f


def test_check_detects_sensitive_words(filter_instance):
    """检测到敏感词时返回 matched=True。"""
    result = filter_instance.check("这是一段包含敏感词1的内容")
    assert result["matched"] is True
    assert "敏感词1" in result["words"]


def test_check_no_match_for_clean_text(filter_instance):
    """干净文本不匹配。"""
    result = filter_instance.check("这是一段正常的文本")
    assert result["matched"] is False
    assert result["words"] == []


def test_replace_sensitive_words(filter_instance):
    """替换敏感词。"""
    result = filter_instance.replace("包含敏感词2的内容")
    assert "敏感词2" not in result
    assert "***" in result
```

## 3. 集成测试编写

### API 路由集成测试

```python
# tests/integration/test_news_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client(db_session, redis_client):
    """创建测试客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.auth = ("test_user", "test_token")
        yield ac


@pytest.mark.asyncio
async def test_create_news(client, db_session):
    """创建新闻成功。"""
    response = await client.post(
        "/api/v1/news/",
        json={"title": "测试新闻", "content": "测试内容"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["title"] == "测试新闻"
    
    # 验证数据库中确实创建了记录
    news_count = await db_session.execute(
        select(NewsModel).where(NewsModel.title == "测试新闻")
    )
    assert news_count.scalar_one() is not None


@pytest.mark.asyncio
async def test_create_news_missing_title(client):
    """创建新闻缺少标题时返回 422。"""
    response = await client.post(
        "/api/v1/news/",
        json={"content": "测试内容"},
    )
    
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == 422
    assert "title" in data["message"].lower() or "required" in data["message"].lower()


@pytest.mark.asyncio
async def test_get_nonexistent_news(client):
    """获取不存在的新闻返回 404。"""
    response = await client.get("/api/v1/news/99999")
    
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == 404
```

**为什么使用真实数据库会话**：集成测试需要验证数据库操作是否正确，使用真实的（内存）数据库比 mock 更有价值。

### 数据库集成测试

```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.models.base import Base


@pytest.fixture
async def db_engine():
    """创建内存 SQLite 引擎。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(Base.metadata.create_all())
    yield engine
    async with engine.begin() as conn:
        await conn.execute(Base.metadata.drop_all())
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """创建数据库会话。"""
    async with AsyncSession(db_engine) as session:
        yield session
        await session.rollback()
```

## 4. E2E 测试编写

### Playwright 前端测试

```python
# tests/e2e/test_admin_frontend.py
import pytest
from playwright.async_api import async_playwright


@pytest.mark.asyncio
async def test_login_flow():
    """登录流程测试。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 访问登录页
        await page.goto("http://localhost:5173/login")
        await page.fill('input[name="username"]', "admin")
        await page.fill('input[name="password"]', "password")
        await page.click('button[type="submit"]')
        
        # 验证跳转成功
        await page.wait_for_url("**/dashboard**")
        assert "dashboard" in page.url
        
        await browser.close()


@pytest.mark.asyncio
async def test_news_list_pagination():
    """新闻列表分页测试。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto("http://localhost:5173/news")
        
        # 验证第一页数据
        rows = await page.query_selector_all(".el-table__body tr")
        assert len(rows) > 0
        
        # 点击第二页
        await page.click('.el-pagination .btn-next')
        await page.wait_for_load_state("networkidle")
        
        # 验证数据已更新
        new_rows = await page.query_selector_all(".el-table__body tr")
        assert len(new_rows) > 0
        
        await browser.close()
```

### 工作流 E2E 测试

```python
# tests/e2e/test_news_workflow.py
import pytest
from app.workflows.news_workflow import NewsWorkflow


@pytest.mark.asyncio
async def test_full_workflow_pipeline(mock_settings, mock_redis, mock_db):
    """完整工作流：从 RSS 抓取到入库。"""
    workflow = NewsWorkflow(redis_client=mock_redis)
    
    # 模拟 RSS 数据
    mock_rss_items = [
        {
            "title": "测试新闻",
            "link": "http://example.com/1",
            "description": "这是一条测试新闻的内容",
        }
    ]
    
    # 模拟 LLM 改写
    mock_rewrite = "这是一条口语化的测试新闻内容"
    
    # 执行工作流（各步骤使用 mock）
    result = await workflow.execute_single(mock_rss_items[0])
    
    assert result["status"] == "success"
    assert result["rewritten"] == mock_rewrite
    # 验证数据库写入
    mock_db.commit.assert_called_once()
```

## 5. Fixture 设计

### 共享 Fixtures

```python
# tests/conftest.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from fakeredis.aioredis import FakeRedis


@pytest.fixture
def fake_redis():
    """Fake Redis 实例（支持 async）。"""
    return FakeRedis()


@pytest.fixture
def mock_http_client():
    """模拟 httpx.AsyncClient。"""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def sample_news_data():
    """示例新闻数据。"""
    return {
        "title": "测试新闻标题",
        "content": "这是一段测试新闻内容",
        "category": "tech",
        "source": "rss",
    }


@pytest.fixture
def sample_user_token():
    """示例 JWT token。"""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_payload"
```

### 参数化测试

```python
import pytest


@pytest.mark.parametrize(
    "input_text,expected_matched,expected_words",
    [
        ("正常文本", False, []),
        ("包含敏感词1", True, ["敏感词1"]),
        ("包含敏感词1和敏感词2", True, ["敏感词1", "敏感词2"]),
    ],
)
def test_sensitive_word_check(
    filter_instance, input_text, expected_matched, expected_words
):
    """参数化测试敏感词检测。"""
    result = filter_instance.check(input_text)
    assert result["matched"] == expected_matched
    assert set(result["words"]) == set(expected_words)
```

## 6. 测试覆盖率

### 覆盖率配置

```ini
# pyproject.toml 或 .coveragerc
[tool.pytest.ini_options]
addopts = --cov=app --cov-report=term-missing --cov-report=html

[tool.coverage.run]
source = ["app"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/__init__.py",
]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 运行特定文件
pytest tests/unit/test_news_service.py -v

# 运行特定测试
pytest tests/unit/test_news_service.py::test_get_by_id_returns_data_when_exists -v

# 生成覆盖率报告
pytest --cov=app --cov-report=html

# 查看覆盖率
coverage report
```

### 覆盖率解读

| 范围 | 说明 |
|------|------|
| 90%+ | 优秀，核心模块应达到 |
| 80%+ | 良好，大多数模块应达到 |
| 60-80% | 一般，需要补充测试 |
| <60% | 较差，优先补充核心路径测试 |

**注意**：覆盖率不是越高越好，关键是要覆盖核心业务逻辑和边界条件。
