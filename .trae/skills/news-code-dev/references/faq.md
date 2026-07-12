# 常见问题

本文档收录 20_News 项目开发过程中的常见问题及解决方案。

## 1. 如何添加新的 API 接口？

**步骤**：

1. 在 `backend/app/models/` 中确认或创建对应的 ORM 模型
2. 在 `backend/app/schemas/` 中创建 Pydantic 请求/响应模型
3. 在 `backend/app/services/` 中创建或扩展 Service 类
4. 在 `backend/app/routers/` 中添加路由定义
5. 在 `admin-web/src/api/` 中添加前端 API 调用函数
6. 在 `admin-web/src/views/` 中添加页面或组件
7. 编写测试用例

**示例**：添加"分类管理"接口

```python
# 1. 模型（如已存在则跳过）
# backend/app/models/news_category.py
class NewsCategory(Base):
    __tablename__ = "news_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)

# 2. Schema
# backend/app/schemas/category.py
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)

class CategoryResponse(BaseModel):
    id: int
    name: str

# 3. Service
# backend/app/services/category_service.py
class CategoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, data: CategoryCreate) -> NewsCategory:
        category = NewsCategory(name=data.name)
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)
        return category

# 4. Router
# backend/app/routers/categories.py
router = APIRouter(prefix="/api/v1/categories", tags=["categories"])

@router.post("/", response_model=CategoryResponse)
async def create_category(
    data: CategoryCreate,
    service: CategoryService = Depends(get_category_service),
):
    category = await service.create(data)
    return CategoryResponse(id=category.id, name=category.name)

# 5. 前端 API
# admin-web/src/api/category.ts
export function createCategory(name: string) {
  return request.post('/api/v1/categories/', { name })
}

# 6. 前端页面
# admin-web/src/views/category/index.vue
```

## 2. 如何添加新的数据库表？

**步骤**：

1. 在 `backend/app/models/` 中创建模型文件
2. 确保模型被导入到 `backend/app/models/__init__.py`（Alembic 需要）
3. 生成 Alembic 迁移：`alembic revision --autogenerate -m "add new_table"`
4. 执行迁移：`alembic upgrade head`

**注意事项**：
- 表名使用复数小写下划线（如 `user_roles`）
- 字段名使用小写下划线（如 `created_at`）
- 外键命名遵循 `{referenced_table}_id` 约定
- 添加必要的索引（高频查询字段）

## 3. 如何添加新的工作流步骤？

**步骤**：

1. 在 `backend/app/workflows/` 中创建新的步骤类
2. 实现 `execute(context: WorkflowContext) -> StepResult` 接口
3. 在状态机配置中注册新步骤
4. 添加重试和降级逻辑
5. 编写单元测试

**示例**：添加"摘要生成"步骤

```python
class SummaryGenerationStep:
    """生成新闻摘要。"""
    
    def __init__(self, llm_client, redis_client):
        self.llm = llm_client
        self.redis = redis_client
    
    async def execute(self, context) -> StepResult:
        prompt = self._build_prompt(context.raw_news)
        try:
            summary = await self.llm.generate(prompt)
            return StepResult(success=True, data={"summary": summary})
        except LLMError as e:
            # 降级：使用原始新闻前 100 字
            return StepResult(
                success=True,
                data={"summary": context.raw_news[:100]},
                degraded=True
            )
```

## 4. 如何修改 LLM Prompt？

**位置**：`backend/app/services/llm_service.py` 中的 prompt 模板

**修改步骤**：
1. 找到对应的 prompt 模板（如 `NEWS_REWRITE_PROMPT`）
2. 修改模板内容
3. 测试不同输入的改写效果
4. 观察线上改写质量指标

**注意事项**：
- Prompt 变更会影响所有使用该 prompt 的工作流
- 建议先在 staging 环境验证
- 记录每次 prompt 变更的原因和效果

## 5. 如何添加新的 TTS 配置？

**位置**：`backend/app/core/config.py` 和 `.env` 文件

**配置项**：
```python
class Settings(BaseSettings):
    TTS_APP_KEY: str = Field(..., env="TTS_APP_KEY")
    TTS_ACCESS_TOKEN: str = Field(..., env="TTS_ACCESS_TOKEN")
    TTS_VOICE_NAME: str = Field("xiaoyan", env="TTS_VOICE_NAME")
    TTS_SPEED: int = Field(50, env="TTS_SPEED")
    TTS_PITCH: int = Field(50, env="TTS_PITCH")
```

**注意**：`.env` 文件不应提交到版本控制

## 6. 如何添加新的审核规则？

**位置**：`backend/app/services/moderation_service.py`

**审核规则类型**：
1. 敏感词过滤（AC 自动机）
2. 长度校验（过短/过长）
3. 重复检测（相似度阈值）
4. 图片/链接校验

**添加新规则**：
```python
class LengthCheckRule:
    """长度校验规则。"""
    
    MIN_LENGTH = 50
    MAX_LENGTH = 5000
    
    def validate(self, content: str) -> bool:
        if len(content) < self.MIN_LENGTH:
            return False
        if len(content) > self.MAX_LENGTH:
            return False
        return True
```

## 7. 如何添加新的告警渠道？

**位置**：`backend/app/services/alert_service.py`

**支持的渠道**：
- 钉钉机器人（Webhook）
- 企业微信群机器人
- 邮件（SMTP）
- 飞书机器人

**添加新渠道**：
```python
class FeishuAlertChannel:
    """飞书机器人告警。"""
    
    def __init__(self, webhook_url: str):
        self.webhook = webhook_url
    
    async def send(self, level: str, message: str):
        payload = {
            "msg_type": "interactive",
            "card": {
                "elements": [{"tag": "markdown", "content": message}]
            }
        }
        async with httpx.AsyncClient() as client:
            await client.post(self.webhook, json=payload)
```

## 8. 如何调试工作流？

**调试方法**：

1. **日志调试**：在工作流各步骤添加详细日志
   ```python
   logger.info(f"Step started", extra={"step": step_name, "task_id": task_id})
   ```

2. **单步执行**：通过 API 手动触发单个步骤
   ```bash
   curl -X POST http://localhost:8000/api/v1/workflows/{task_id}/steps/{step_name}/execute
   ```

3. **状态检查**：查看工作流实例的当前状态
   ```bash
   curl http://localhost:8000/api/v1/workflows/{task_id}
   ```

4. **本地模拟**：使用 mock 数据模拟上下游服务
   ```python
   @pytest.fixture
   def mock_llm():
       return MockLLMClient(response="mocked rewrite")
   ```

## 9. 如何优化缓存命中率？

**优化方向**：

1. **缓存键设计**：避免过于细碎或过于宽泛
   ```python
   # 好：按业务维度缓存
   cache_key = f"news:list:category:{category}:page:{page}"
   
   # 差：每个请求都不同
   cache_key = f"news:list:{timestamp}"  # 永远不命中
   ```

2. **TTL 设置**：根据数据更新频率设置合理过期时间
   - 新闻列表：5-10 分钟
   - 新闻详情：30 分钟
   - 配置信息：1 小时

3. **预热策略**：应用启动时预加载热点数据
   ```python
   @app.on_event("startup")
   async def warmup_cache():
       popular_news = await get_popular_news(limit=100)
       for news in popular_news:
           await cache_news_detail(news)
   ```

4. **监控命中率**：添加缓存命中率指标
   ```python
   cache_hits.inc() if hit else cache_misses.inc()
   ```

## 10. 如何修复跨端字段不一致？

**症状**：前端展示的字段名与后端返回的不一致

**排查步骤**：

1. 检查后端 Pydantic model 的 `Field(alias=...)` 配置
2. 检查前端 API 调用的字段映射
3. 使用浏览器开发者工具查看网络请求的实际响应
4. 对比前后端字段定义文档

**常见不一致场景**：
- `created_at` vs `createdAt`
- `user_id` vs `userId`
- `is_active` vs `isActive`

**修复方案**：
- 方案 A：后端统一输出 snake_case，前端转换（推荐）
- 方案 B：后端使用 `alias` 输出 camelCase
- 方案 C：前后端统一使用一种命名风格

**预防措施**：
- 在 CI/CD 中添加字段契约检查
- 维护一份字段映射文档
- 使用代码生成工具自动生成类型定义

## 11. 开发模式登录失败（admin 用户不存在）？

**症状**：双击 `启动服务.bat` 启动开发模式后，使用 admin/admin123 登录报"用户名或密码错误"

**根因**：`seed_admin.py` 默认数据库路径指向 `dist/20-news/data/news.db`（打包产物路径），与开发态运行时数据库 `backend/data/news.db` 不一致，导致开发态数据库中 `admin_user` 表为空

**排查步骤**：

1. 确认当前启动模式（dev/dev-sys/exe），参考 `scripts/start.ps1` 模式选择逻辑
2. 确认运行时数据库路径：dev 模式 → `backend/data/news.db`，exe 模式 → `dist/20-news/data/news.db`
3. 检查 `admin_user` 表是否有数据：
   ```python
   import sqlite3
   conn = sqlite3.connect(r'backend/data/news.db')
   print(conn.execute('SELECT COUNT(*) FROM admin_user').fetchone())
   ```
4. 若 count=0，确认是 seed 路径不一致问题

**修复方案**：

- **方案 A（立即修复）**：手动 seed 到正确的数据库路径
  ```bash
  python backend/seed_admin.py backend/data/news.db
  ```

- **方案 B（长期修复，已实施）**：
  1. `seed_admin.py` 默认路径改用 `app.paths.resolve_db_path()`，与运行时路径解析保持一致
  2. `main.py` lifespan 中添加 `_seed_default_admin()`，建表后自动 seed（幂等），确保无论何种模式启动都有 admin 用户

**预防措施**：
- 所有 seed 脚本的默认路径必须通过 `app.paths.resolve_db_path()` 解析，禁止硬编码 `dist/` 路径
- 关键初始数据（admin 用户、默认配置）应在应用 lifespan 中自动 seed，不依赖外部脚本
- 数据库路径相关的排查，优先检查 `paths.py` 的 `is_frozen()` 判定和 `get_app_root()` 返回值
