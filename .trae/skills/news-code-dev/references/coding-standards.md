# 编码规范

本文档规定 20_News 项目的编码规范，涵盖 Python 后端、Vue 3 前端、微信小程序三个技术栈。

## Python 后端规范

### 类型注解

**为什么**：类型注解提高代码可读性，便于静态检查工具（mypy/ruff）发现潜在错误。

```python
# 推荐：完整类型注解
async def get_news_list(
    page: int = 1,
    page_size: int = 20,
    category: NewsCategory | None = None,
) -> tuple[list[NewsModel], int]:
    ...

# 不推荐：缺少类型注解
def get_news(page, page_size):
    ...
```

**规则**：
- 函数签名必须包含参数和返回值类型
- 复杂类型使用 `typing` 模块（`list[dict[str, Any]]`、`Optional[T]`）
- 避免使用 `Any`，除非确实无法确定类型

### 异步规范

**为什么**：项目全面使用 async/await，混用同步代码会导致事件循环阻塞。

```python
# 推荐：正确使用异步
async def fetch_news(url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text

# 推荐：阻塞操作使用 to_thread
async def process_audio(file_path: str) -> bytes:
    loop = asyncio.get_event_loop()
    result = await asyncio.to_thread(read_audio_file, file_path)
    return result

# 不推荐：使用同步 HTTP 客户端
def fetch_news_sync(url: str) -> str:
    response = requests.get(url)  # 阻塞事件循环！
    return response.text
```

**规则**：
- 所有 IO 操作使用 async 版本（httpx.AsyncClient、aiomysql、redis.asyncio）
- 阻塞操作（如音频处理）使用 `asyncio.to_thread` 包装
- 禁止使用 `time.sleep()`，改用 `await asyncio.sleep()`

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块/包 | 小写 + 下划线 | `news_workflow.py` |
| 类名 | 大驼峰 | `NewsService` |
| 函数/变量 | 小写 + 下划线 | `get_news_list` |
| 常量 | 大写 + 下划线 | `MAX_RETRIES = 3` |
| 私有方法 | 单下划线前缀 | `_validate_input` |
| DB 表名 | 复数小写 + 下划线 | `news_items`, `user_roles` |

### 错误处理

**为什么**：统一的错误处理便于前端解析和日志追踪。

```python
# 推荐：自定义异常 + 全局异常处理器
class NewsAPIError(Exception):
    """新闻业务异常。"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(self.message)

# 全局异常映射
@app.exception_handler(NewsAPIError)
async def handle_api_error(request, exc: NewsAPIError):
    return JSONResponse(
        status_code=exc.code,
        content={"code": exc.code, "message": exc.message}
    )

# 不推荐：直接使用 HTTPException 传递业务错误
raise HTTPException(status_code=400, detail="标题不能为空")
```

**错误分类**：
- `400`：参数校验失败（业务规则）
- `401`：认证失败（token 无效/过期）
- `403`：权限不足（非管理员访问管理接口）
- `404`：资源不存在
- `429`：频率限制
- `500`：服务器内部错误

### 日志规范

**为什么**：结构化日志便于 ELK 等日志系统采集和分析。

```python
import logging

logger = logging.getLogger(__name__)

# 推荐：使用 logger 而非 print
logger.info("News fetched successfully", extra={"url": url, "duration_ms": duration})
logger.warning("LLM API timeout, using fallback", extra={"retry_count": 3})
logger.error("Failed to process audio", exc_info=True)

# 不推荐：使用 print
print(f"Error occurred: {e}")  # 生产环境不应有 print
```

**规则**：
- 使用 `logging.getLogger(__name__)` 获取模块级 logger
- 错误日志必须包含 `exc_info=True` 以记录 traceback
- 避免在日志中打印敏感信息（密码、token、用户隐私数据）

### 配置规范

**为什么**：配置驱动使代码可移植，不同环境无需修改代码。

```python
# 推荐：通过 settings 获取配置
from app.core.config import settings

database_url = settings.DATABASE_URL
cache_ttl = settings.CACHE_TTL_SEC

# 不推荐：硬编码配置值
database_url = "mysql+aiomysql://root:password@localhost:3306/news_db"
cache_ttl = 3600
```

## Vue 3 前端规范

### <script setup> 语法

**为什么**：`<script setup>` 是 Vue 3 推荐的 Composition API 写法，更简洁且类型推导更好。

```vue
<!-- 推荐 -->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { NewsItem } from '@/types'

const props = defineProps<{
  categoryId: string
}>()

const emit = defineEmits<{
  select: [item: NewsItem]
}>()

const loading = ref(false)
const newsList = ref<NewsItem[]>([])

const filteredList = computed(() =>
  newsList.value.filter(item => item.category === props.categoryId)
)

const handleSelect = (item: NewsItem) => {
  emit('select', item)
}

onMounted(async () => {
  loading.value = true
  try {
    newsList.value = await fetchNewsList(props.categoryId)
  } finally {
    loading.value = false
  }
})
</script>
```

### Props 和 Emits 类型定义

**为什么**：强类型 Props/Emits 可在编译时发现类型错误。

```typescript
// 推荐：使用 defineProps/defineEmits 泛型
const props = defineProps<{
  title: string
  visible: boolean
  items?: NewsItem[]  // 可选属性
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  select: [item: NewsItem]
}>()
```

### 响应式规范

**为什么**：理解响应式原理避免常见的 Vue 陷阱。

```typescript
// 推荐：ref 用于基本类型，reactive 用于对象
const count = ref(0)
const user = reactive({ name: '', age: 0 })

// 不推荐：直接给 ref.value 赋值新对象（丢失响应式）
let userList = ref<User[]>([])
userList.value = newUserList  // 可以
userList = newUserList  // 错误！丢失响应式

// 推荐：使用 computed 派生状态
const totalCount = computed(() => newsList.value.length)
```

### 组件通信

| 场景 | 方式 |
|------|------|
| 父 → 子 | Props |
| 子 → 父 | Emits |
| 跨层级 | Provide/Inject |
| 全局状态 | Pinia Store |
| 兄弟组件 | 共同父组件 + emits，或 Pinia |

## 小程序规范

### 生命周期

**为什么**：小程序生命周期与 Web 不同，理解生命周期避免内存泄漏和资源浪费。

```javascript
// Page 生命周期
Page({
  onLoad(options) {
    // 页面加载，可获取 URL 参数
    // 适合发起首次数据请求
  },
  onShow() {
    // 页面显示/切入前台时触发
    // 适合刷新数据、恢复音频播放
  },
  onHide() {
    // 页面隐藏/切入后台时触发
    // 适合暂停音频、保存状态
  },
  onUnload() {
    // 页面卸载
    // 适合清理定时器、取消订阅
  }
})
```

### 全局状态管理

**为什么**：小程序没有内置的全局状态管理，需要自行实现。

```javascript
// app.js 中定义全局状态
App({
  globalData: {
    userInfo: null,
    token: '',
    settings: {}
  },
  
  // 提供设置方法
  setUserInfo(info) {
    this.globalData.userInfo = info
    wx.setStorageSync('userInfo', JSON.stringify(info))
  }
})

// 页面中使用
const app = getApp()
Page({
  onLoad() {
    this.setData({
      userInfo: app.globalData.userInfo
    })
  }
})
```

### 音频管理

**为什么**：音频播放是小程序的核心功能，需要正确处理后台播放和跨页面状态。

```javascript
// 推荐使用 wx.getBackgroundAudioManager() 实现后台播放
const audioManager = wx.getBackgroundAudioManager()
audioManager.title = '新闻播报'
audioManager.src = audioUrl
audioManager.onPlay(() => {
  console.log('开始播放')
})
audioManager.onPause(() => {
  console.log('暂停播放')
})
audioManager.onStop(() => {
  console.log('停止播放')
})
```

### 循环依赖处理

**为什么**：小程序模块加载机制与 Node.js 不同，循环依赖会导致 undefined。

```javascript
// 不推荐：a.js 和 b.js 互相引用
// a.js
const b = require('./b')  // b 还未加载完
// b.js
const a = require('./a')  // 循环依赖！

// 推荐：提取公共模块
// utils/common.js - 存放共享逻辑
// a.js 引用 common.js
// b.js 引用 common.js
```

## 数据库规范

### 表命名

**为什么**：统一的表命名便于理解和管理。

- 表名：复数小写 + 下划线，如 `news_items`, `user_roles`
- 字段名：小写 + 下划线，如 `created_at`, `user_id`
- 索引名：`idx_{table}_{column(s)}`，如 `idx_news_items_category`
- 外键：`{referenced_table}_id`，如 `user_id`

### 字段类型选择

| 数据类型 | 推荐类型 | 说明 |
|----------|----------|------|
| 主键 | BIGINT UNSIGNED | 自增或使用 UUID |
| 字符串（短） | VARCHAR(255) | 标题、名称等 |
| 字符串（长） | TEXT | 正文、描述等 |
| 布尔 | TINYINT(1) | MySQL 无原生 bool |
| 日期时间 | DATETIME | 统一使用 UTC |
| 金额 | DECIMAL(10,2) | 不用 FLOAT/DOUBLE |
| JSON | JSON | 灵活结构数据 |

### 索引规范

**为什么**：合理的索引提升查询性能，过多索引影响写入性能。

```sql
-- 推荐：为高频查询字段加索引
ALTER TABLE news_items ADD INDEX idx_category_status (category, status);

-- 推荐：联合索引遵循最左前缀原则
-- (category, status) 可查询 category 或 (category, status)
-- 但不能单独查询 status

-- 不推荐：为所有字段加索引
-- 会降低写入性能，增加存储空间
```

### 迁移规范

**为什么**：数据库迁移必须幂等，支持重复执行。

```python
# 推荐：使用 Alembic 管理迁移
# migration 脚本中检查表/字段是否存在
from alembic import op
import sqlalchemy as sa

def upgrade():
    if not _table_exists('news_categories'):
        op.create_table(
            'news_categories',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(50)),
        )
```

## API 契约规范

### 请求/响应格式

**为什么**：统一的数据格式便于前后端协作和错误排查。

```python
# 统一响应格式
class ApiResponse(BaseModel):
    code: int = Field(description="业务状态码，0 表示成功")
    message: str = Field(description="响应消息")
    data: Any = Field(default=None, description="响应数据")

# 成功响应
{"code": 0, "message": "success", "data": {...}}

# 错误响应
{"code": 400, "message": "标题不能为空", "data": null}
```

### 错误码规范

| 范围 | 含义 |
|------|------|
| 0 | 成功 |
| 1000-1999 | 参数校验错误 |
| 2000-2999 | 认证/授权错误 |
| 3000-3999 | 业务规则错误 |
| 4000-4999 | 第三方服务错误（LLM/TTS/COS） |
| 5000-5999 | 系统内部错误 |

### 分页格式

```python
class PaginatedResponse(BaseModel):
    items: list[NewsItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages
    
    @property
    def has_prev(self) -> bool:
        return self.page > 1
```

### 前后端字段契约

**为什么**：前后端字段命名不一致是导致 Bug 的主要原因之一。

```
约定：
- 后端使用 snake_case（数据库风格）
- 前端使用 camelCase（JavaScript 风格）
- 转换在序列化/反序列化层完成，不在业务逻辑中
- Enum 字段始终传输 .value（字符串），不传输枚举名
- 日期时间统一 ISO8601 格式：YYYY-MM-DDTHH:mm:ssZ
```
