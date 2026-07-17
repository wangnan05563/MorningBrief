# 编码规范

本文档规定 MorningBrief 项目的编码规范，涵盖 Python 后端、Vue 3 前端、微信小程序三个技术栈。

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

## 并发控制规范

### PriorityQueue + Semaphore 模式

**为什么**：工作流调度需要同时控制任务优先级（PriorityQueue）和并发度（Semaphore），两者配合不当会导致任务泄漏或 ID 冲突。

```python
# 推荐：PriorityQueue + Semaphore + cancelled 标记的组合模式
from dataclasses import dataclass, field
from asyncio import PriorityQueue, Semaphore

@dataclass(order=True)
class QueueEntry:
    """队列条目，cancelled 标记用于取消（PriorityQueue 不支持随机删除）。"""
    priority: int
    id: str = field(compare=False)
    cancelled: bool = field(default=False, compare=False)

class WorkflowScheduler:
    def __init__(self, max_concurrent: int):
        self._queue: PriorityQueue[QueueEntry] = PriorityQueue()
        self._semaphore = Semaphore(max_concurrent)
        self._entry_index: dict[str, QueueEntry] = {}  # id → entry，用于取消查找
        self._trigger_lock = asyncio.Lock()  # 串行化入队（规范 32）

    async def trigger(self, priority: int, task_id: str):
        async with self._trigger_lock:  # 串行化入队防 ID 冲突
            entry = QueueEntry(priority=priority, id=task_id)
            self._entry_index[task_id] = entry
            await self._queue.put(entry)

    async def cancel(self, task_id: str) -> bool:
        # PriorityQueue 不支持随机删除，用 cancelled 标记
        entry = self._entry_index.get(task_id)
        if entry:
            entry.cancelled = True
            return True
        return False

    async def _worker(self):
        while True:
            entry = await self._queue.get()
            if entry.cancelled:  # 跳过已取消任务
                self._queue.task_done()
                continue
            async with self._semaphore:  # 限制并发度
                await self._process(entry)
            self._queue.task_done()
```

**规则**：
- PriorityQueue 入队必须用 Lock 串行化（防 ID 冲突，见规范 32）
- 任务取消用 `cancelled` 标记，不尝试随机删除（见规范 36）
- Semaphore 动态调整必须延迟重建（见规范 33 / 37）
- `_entry_index` 维护 id → entry 映射，用于取消查找

### Semaphore 配置热生效

**为什么**：运行时调整并发数不能立即重建 Semaphore，否则当前运行任务的 `finally release()` 会操作新信号量导致计数错乱，且旧信号量上等待的任务会永久泄漏。

```python
# 推荐：_config_dirty 标记 + 延迟重建
class ConcurrencyManager:
    def __init__(self, max_concurrent: int):
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._config_dirty = False
        self._active_count = 0

    async def acquire(self):
        # 仅当无活跃持有时才重建（安全时机）
        if self._config_dirty and self._active_count == 0:
            self._rebuild_semaphore()
            self._config_dirty = False
        return await self._semaphore.acquire()

    async def release(self):
        self._semaphore.release()

    def update_concurrency(self, new_max: int):
        self._max_concurrent = new_max
        self._config_dirty = True  # 标记，不立即重建

    def _rebuild_semaphore(self):
        old = self._semaphore
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        # 唤醒旧信号量上的等待者，防止永久泄漏
        for _ in range(old._value):
            old.release()
```

## 数据同步规范

### COS → SQLite 幂等同步模式

**为什么**：外部存储（COS/OSS/S3）对象同步到数据库时，服务重启或重试可能导致重复同步，必须用幂等保障避免 `IntegrityError`，同步后删除源对象防止重复处理。

```python
# 推荐：INSERT OR IGNORE + 删除源对象 双重幂等
from sqlalchemy import text

async def sync_external_objects(
    cos_client,
    db_session,
    sync_prefix: str,  # 从配置读取，如 settings.COS_SYNC_PREFIX
):
    """同步 COS 对象到数据库（幂等）。

    幂等保障：
    1. INSERT OR IGNORE：已存在则跳过，不报错
    2. 删除源对象：防止下次重复同步
    """
    objects = await cos_client.list_objects(prefix=sync_prefix)
    for obj in objects:
        # 幂等插入：已存在则跳过
        await db_session.execute(
            text("INSERT OR IGNORE INTO cos_sync_log (object_key, synced_at) VALUES (:key, :ts)"),
            {"key": obj.key, "ts": utcnow_naive()}
        )
        await db_session.commit()
        # 删除源对象，防止下次重复同步
        await cos_client.delete_object(obj.key)
        logger.info(f"Synced and deleted COS object: {obj.key}")
```

**规则**：
- 同步表必须有 `object_key` 唯一约束（UNIQUE INDEX）
- 用 `INSERT OR IGNORE`（SQLite）或 `INSERT ... ON CONFLICT DO NOTHING`（PostgreSQL）
- 同步成功后必须删除源对象（防止重复同步）
- 同步失败时源对象保留（下次重试）
- 批量同步用事务包裹（失败回滚），但单对象删除在 commit 后执行

### 备份数据库 VACUUM INTO

**为什么**：SQLite VACUUM INTO 不能在事务内执行，必须用 AUTOCOMMIT 隔离级别。

```python
# 推荐：AUTOCOMMIT 隔离级别执行 VACUUM INTO
async def backup_database(engine, backup_path: str):
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f"VACUUM INTO '{backup_path}'"))
```

## 组件抽取规范

### 小程序自定义组件抽取

**为什么**：小程序页面逻辑膨胀后需抽取自定义组件，抽取不当会导致数据传递混乱、事件监听泄漏。

```javascript
// 推荐：组件抽取四步法
// 1. 组件定义（components/audio-player/index.js）
Component({
  properties: {
    episode: { type: Object, value: null },
    // 明确声明所有外部传入属性
  },
  data: {
    isPlaying: false,
  },
  lifetimes: {
    attached() {
      // 组件挂载时初始化
      this._initPlayer()
    },
    detached() {
      // 组件卸载时必须清理监听器（防泄漏）
      this._cleanupPlayer()
    }
  },
  methods: {
    _initPlayer() {
      const player = getApp().globalData.player
      this._onPlay = () => this.setData({ isPlaying: true })
      this._onPause = () => this.setData({ isPlaying: false })
      player.onPlay(this._onPlay)
      player.onPause(this._onPause)
    },
    _cleanupPlayer() {
      const player = getApp().globalData.player
      if (player) {
        player.offPlay(this._onPlay)
        player.offPause(this._onPause)
      }
      this._onPlay = null
      this._onPause = null
    },
    handlePlay() {
      this.triggerEvent('play', { episode: this.data.episode })
    }
  }
})

// 2. 页面引用（pages/index/index.json）
{
  "usingComponents": {
    "audio-player": "/components/audio-player/index"
  }
}

// 3. 页面模板（pages/index/index.wxml）
<!-- <audio-player episode="{{episode}}" bind:play="onPlay" /> -->

// 4. 页面事件处理（pages/index/index.js）
Page({
  onPlay(e) {
    const episode = e.detail.episode
    // 处理播放逻辑
  }
})
```

**规则**：
- 组件 `properties` 必须声明类型和默认值
- 组件 `lifetimes.attached` 注册监听器，`lifetimes.detached` 必须清理
- 事件回调保存为实例属性（`this._onPlay`），便于精确 `off`
- 父子通信：父 → 子用 `properties`，子 → 父用 `triggerEvent`
- 组件不应直接操作 `globalData`（通过事件让页面处理）



## 工作流与外部服务调用规范

### 工作流分步重跑规范

**为什么**：工作流重跑（retry）必须从指定步骤开始，复用上游成功产物，而不是从头执行完整流水线。MVP 阶段的重跑接口接收了 step 参数但未使用，导致每次重跑都从 crawl 开始，浪费资源且与用户预期不符。

**正确做法**：
`python
# 路由层：接收 step 参数并透传
@router.post("/{workflow_id}/retry")
async def retry_workflow(
    workflow_id: str,
    req: RetryRequest,  # 包含 step 字段
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    svc = WorkflowService(db)
    data = await svc.retry_from_step(workflow_id, req.step)
    return success(data=data)

# Service 层：从指定步骤开始，复用上游产物
async def retry_from_step(self, workflow_id: str, step_name: str) -> dict:
    """从指定步骤重跑工作流。

    规则：
    1. 查找原工作流中 step_name 之前的成功步骤，提取其 result 产物
    2. 创建新 workflow_id，复用原 episode_date
    3. 将提取的产物注入新工作流的 context
    4. 仅执行 step_name 及其后续步骤
    """
    # 步骤依赖关系：tts 需要 rewrite 的 script_id
    # stitch 需要 tts 的 audio_segments
    # review 需要 stitch 的 audio_url
    upstream_deps = {
        "crawl": {},
        "rewrite": {"crawl": "materials"},
        "tts": {"rewrite": "script_id"},
        "stitch": {"tts": "audio_segments"},
        "review": {"stitch": "audio_url"},
    }
    deps = upstream_deps.get(step_name, {})
    context = {}
    for dep_step, dep_key in deps.items():
        # 从原工作流的 dep_step 成功记录中提取产物
        dep_result = self._extract_step_result(original_wf, dep_step, dep_key)
        if dep_result is None:
            raise ParamError(f"重跑 {step_name} 需要 {dep_step} 产物，但原工作流中 {dep_step} 未成功")
        context[dep_key] = dep_result
    return await self._execute_steps_from(workflow_id, step_name, context)
`

**规则**：
- 重跑接口必须使用 step 参数，不能忽略
- 上游产物缺失时明确报错，不静默跳过
- 新工作流复用原 episode_date 和 channel_id
- 前端确认对话框必须显示从哪一步开始重跑

### 外部服务空响应分类规范

**为什么**：第三方 TTS 服务（如 Edge-TTS）返回空音频时，如果直接抛出非重试型异常，会导致整个批次失败且无法进入降级链路。必须将"未收到音频"识别为可重试的服务级故障。

**正确做法**：
`python
# 在 provider 层识别特定异常并分类
except Exception as exc:
    # 将 "NoAudioReceived" 分类为可重试的服务故障
    if exc.__class__.__name__ == "NoAudioReceived":
        raise TTSServiceError(
            "Edge-TTS 未收到音频数据，请检查网络、代理或稍后重试"
        ) from exc
    # 其他异常走原有分类逻辑
    msg = str(exc).lower()
    if "429" in msg or "rate" in msg:
        raise TTSRateLimitError(f"Edge-TTS 限流: {exc}") from exc
    # ...

# 上层通过异常类型判断是否重试/降级
tts_retry = retry(
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(
        (TTSRateLimitError, TTSTimeoutError, TTSServiceError)
    ),
)
`

**规则**：
- 外部服务的"空响应"（无音频、无数据、无结果）必须归类为 TTSServiceError 或等效的可重试异常
- 认证失败、限流、超时各有独立的异常类型，便于上层差异化处理
- 不要将外部服务异常统一包装为通用 TTSError，这会丢失重试/降级决策所需的语义

### 配置键一致性规范

**为什么**：前端表单字段名、后端路由模型字段名、数据库配置键名、Settings 属性名必须保持一致或通过明确的映射关系连接。本项目中发现 edge_rate / edge_volume 在路由层定义为前端键名，但 i_config_service.py 中映射到 edge_tts_rate / edge_tts_volume，导致前端保存的值在服务端读取时被忽略。

**正确做法**：
`python
# 方案 1：统一键名（推荐）
# 前端表单、路由模型、数据库配置键、Settings 全部使用 edge_rate / edge_volume

# 方案 2：明确的双向映射
CONFIG_KEY_MAP = {
    "edge_rate": "EDGE_TTS_RATE",
    "edge_volume": "EDGE_TTS_VOLUME",
    "edge_pitch": "EDGE_TTS_PITCH",
    # 兼容旧键名
    "edge_tts_rate": "EDGE_TTS_RATE",
    "edge_tts_volume": "EDGE_TTS_VOLUME",
    "edge_tts_pitch": "EDGE_TTS_PITCH",
}

# 读取时优先新键，fallback 到旧键
def _get(key: str, settings_attr: str, default: str = "",
         legacy_keys: tuple[str, ...] = ()) -> str:
    for candidate in (key, *legacy_keys):
        val = raw.get(candidate)
        if val is not None:
            return val
    return str(getattr(settings, settings_attr, default))
`

**规则**：
- 新增配置项时，前端表单、路由模型、数据库配置键、Settings 属性四者必须同步
- 字段变更时保留旧键名的兼容读取（legacy_keys）
- 前端提交的配置值在写入数据库前做规范化（如将 "0.0" 转为 ""）

### 批量失败诊断信息规范

**为什么**：工作流 TTS 步骤批量失败时，仅返回  /6 成功率过低 无法定位具体哪一段失败、失败原因是什么。必须在最终异常消息中包含脱敏后的分段失败摘要。

**正确做法**：
`python
# 在批量失败时收集每段的失败原因
segment_failures: list[tuple[object, str, Exception]] = []
for seg, res in zip(segments, results):
    if isinstance(res, Exception):
        segment_failures.append((seq, "合成", res))
    # ...

if success * 2 < total:
    failure_summary = _summarize_segment_failures(segment_failures)
    raise TTSError(
        f"TTS 成功率过低: {success}/{total}；失败分段: {failure_summary}"
    )

def _summarize_segment_failures(
    failures: list[tuple[object, str, Exception]], limit: int = 5,
) -> str:
    """生成可持久化的分段失败摘要，不包含稿件正文或凭证。"""
    summaries = []
    for seq, stage, error in failures[:limit]:
        message = " ".join(str(error).split())[:160]
        # 脱敏：替换 api_key/token/secret/password 后的值
        message = re.sub(r"(?i)(api[_ -]?key|token|secret|password)\s*[=:]\s*\S+",
                         r"\1=***", message)
        summaries.append(f"{seq}（{stage}）: {type(error).__name__}: {message}")
    return " | ".join(summaries)
`

**规则**：
- 批量操作的失败必须包含每步/每段的失败原因摘要
- 摘要中不得包含稿件正文、API 密钥等敏感信息
- 失败摘要长度有限制（如前 5 段、每段 160 字符），防止日志膨胀

---

## 工作流步骤自动调整规范

### 规范 23：时长/容量约束的自动填充与切除

所有有时间、容量、大小等硬性约束的拼接/聚合操作，必须在最终校验前实现自动调整能力。

**为什么**：硬性约束是业务要求（如节目时长 9:30-10:30），不是错误。当内容不足时应自动填充，而非直接失败导致工作流中断。

**正确做法**：
`python
# 音频拼接示例
duration = await get_audio_duration(final_path)
if duration < MIN_DURATION_SEC:
    pad_sec = MIN_DURATION_SEC - duration
    await generate_silence(pad_sec, pad_path)
    # 追加静音到末尾
    await run_ffmpeg(build_concat_cmd([final_path, pad_path], padded_path))
    final_path = padded_path
    duration = await get_audio_duration(final_path)
elif duration > MAX_DURATION_SEC:
    excess = duration - MAX_DURATION_SEC
    # 从末尾切除
    await run_ffmpeg([ffmpeg, "-i", final_path, "-af",
        f"atrim=start:0:end={MAX_DURATION_SEC}", trimmed_path])
    final_path = trimmed_path
    duration = await get_audio_duration(final_path)
# 二次校验兜底
assert MIN_DURATION_SEC <= duration <= MAX_DURATION_SEC
`

**判断信号**：grep 搜索 duration.*超出.*范围 或 length.*exceed 后直接 raise → 违规
**适用范围**：音频拼接、文档生成、报表输出、批量数据处理
**不适用场景**：实时流处理（不能追加/切除）、精确时长要求（如音乐视频同步）

### 规范 24：确定性失败的重试无效性

工作流步骤的重试只对瞬态失败有意义。对于确定性失败，应在步骤内部自动调整。

**为什么**：重试相同输入不会产生不同结果，只会浪费时间和资源。例如音频拼接时长不足，重试 3 次仍然不足。

**正确做法**：
- 瞬态失败（网络超时、IO 错误）→ 使用重试机制
- 确定性失败（输入数据导致）→ 在步骤内部自动调整
- 判断方法：检查步骤函数是否依赖外部可变状态

**判断信号**：grep 搜索步骤函数内部无网络调用、无文件读写、无 DB 查询，却有重试逻辑 → 应改为自动调整

---

## 第三方服务模型名称与定价规范

### 规范 25：第三方服务模型名称以官方文档为准

所有第三方 AI 服务商（LLM/TTS/存储）的模型名称、API 端点、密钥格式必须以官方文档为事实源，技能文档中不得自行编造或猜测。

**为什么**：模型名称是区分大小写的字符串，deepseek-v4-flash 与 DeepSeek-V4-Flash 是不同的标识符。使用错误的模型名会导致 API 调用失败或路由到错误的模型。

**判断信号**：grep 搜索预设配置中的模型名，与官网文档逐字核对
**正确做法**：
- 新接入服务商时，先查阅官方文档确认模型名称大小写
- 修改预设默认模型时，同步更新 MODEL_PRICING 中的定价条目
- 模型名称是区分大小写的字符串，deepseek-v4-flash != DeepSeek-V4-Flash

**已确认的模型名称大小写（截至 2026-07-12）**：

| 提供商 | 模型名称 | 大小写规则 |
|--------|---------|-----------|
| 通义千问 | qwen-max, qwen-plus, qwen-turbo | 全小写 |
| OpenAI | gpt-4o-mini, gpt-4o | 全小写 |
| DeepSeek | deepseek-v4-flash, deepseek-chat | 全小写连字符 |
| 智谱 GLM | glm-4-flash | 全小写连字符 |
| Moonshot | moonshot-v1-8k | 全小写连字符 |
| 百度文心 | ernie-4.0-8k | 全小写连字符 |
| 字节豆包 | doubao-pro-4k | 全小写连字符 |
| Ollama | qwen2.5:7b | 小写 + 冒号分隔 |
| Agnes AI | Agnes-2.0-Flash | 首字母大写 + 连字符 |

### 规范 26：模型定价表同步更新

每当修改或新增模型名称时，必须同步检查 MODEL_PRICING 定价表中是否包含该模型条目。缺失定价条目的模型将使用默认费率（gpt-4o-mini），导致费用统计不准确。

**判断信号**：grep 搜索新增模型名是否在 MODEL_PRICING 中存在
**正确做法**：修改预设模型时，同时检查并更新定价表

### 规范 27：配置持久化与返显完整性

所有配置输入框的值必须完整持久化到数据库，并在页面加载时正确返显。预设切换时不应覆盖已保存的 API Key。

**判断信号**：grep 搜索预设切换函数，确认是否保留 api_key
**正确做法**：
- 预设切换只更新 ase_url 和 model，保留 pi_key
- 页面加载后自动匹配预设（基于 ase_url）
- 前端 selectedPreset 状态必须与下拉框实际选中值同步

### 规范 28：PowerShell 文件编辑安全

使用 PowerShell 进行文件内容替换时，避免使用 -replace 操作符处理多行字符串，应使用索引直接赋值。

**判断信号**：grep 搜索 -replace 命令中是否包含 \r\n 等转义序列
**正确做法**：使用 $lines[index] = "new value" 直接赋值，而非正则替换

---

## 前端规范（续）

### 规范 29：批量删除前端交互标准

**所有涉及批量删除的表格必须实现：选择列、选中计数、二次确认、删除后分页修正。**

**为什么**：批量删除是不可逆操作，必须通过前端交互防止误操作，并确保删除后列表状态正确。

**正确做法**：
`ue
<!-- 表格添加选择列 -->
<el-table
  @selection-change="handleSelectionChange"
>
  <el-table-column
    v-if="userStore.isAdmin"
    type="selection"
    width="48"
    :selectable="isRowSelectable"
  />
</el-table>

<!-- 批量操作按钮显示选中数量 -->
<el-button
  type="danger"
  :disabled="selectedRows.length === 0"
  @click="handleBatchDelete"
>
  批量删除（{{ selectedRows.length }}）
</el-button>
`

**判断信号**：grep 搜索 el-table 无 	ype="selection"、批量操作无 ElMessageBox.confirm
**适用范围**：所有需要批量操作的数据表格
**不适用场景**：仅单条操作的页面、软删除场景

---

---

## 规范 33：共享构建依赖包完整提取

**为什么**：FFmpeg 等共享构建（shared build）的 EXE 文件依赖同目录的 DLL。只复制 EXE 而不提取配套 DLL 会导致运行时 找不到 avdevice-63.dll 等系统错误。

- 适用：所有共享构建压缩包（gpl-shared、shared 等）
- 不适用：static build（不依赖额外 DLL）
- 判断信号：grep 搜索 zf.open(ffmpeg_member) 后只提取 exe 文件
- 正确做法：
  1. 通过 fmpeg.exe 定位 zip 内动态顶层目录
  2. 提取该 in/ 目录下的所有普通文件（含 DLL）
  3. 提取前清除残缺或不同版本的旧文件，避免 DLL 版本混用
  4. 提取后验证所有关键依赖文件存在
- 安装流程：前端点击下载 → 后端流式下载 zip → 	o_thread 解压 → 重新检测可用性


---

## 规范 34：日志格式与异常信息透传

**为什么**：Loguru 使用 {} 占位符，旧代码使用 %s 会导致异常对象被当作字符串格式化，真实错误信息被吞掉。日志格式中的 %s 占位符会让 logger.warning("msg: %s", e) 输出 msg: %s 而非 msg: <actual error>。

- 适用：所有使用 loguru 的项目
- 不适用：使用标准 logging 模块的项目
- 判断信号：grep 搜索 logger\.(warning|error|info).*%s
- 正确做法：
  1. 统一使用 {} 占位符：logger.warning("msg: {}", e)
  2. 日志消息中的格式化参数必须与 loguru 语义一致
  3. 异常日志必须包含 exc_info=True 以记录 traceback
- 运行环境验证：日志格式应与源码版本一致，不一致说明运行的是旧构建产物


---

## 规范 35：环境隔离与静态资源 URL 配置化

**为什么**：开发态用 localhost/127.0.0.1，真机测试时手机访问不到电脑（127.0.0.1 指向手机自己），生产用域名。如果硬编码 localhost，会导致真机测试"网络异常"误判为"音频过大"等问题，浪费排查时间。

**判断信号**：
- grep 搜索 `'http://localhost` 或 `'http://127.0.0.1` 硬编码在业务代码（非配置文件、非 .env）
- grep 搜索 `audio_url` / `cover_url` 拼接逻辑中含硬编码 host
- 后端 `app.host` 配置为 `127.0.0.1` 但期望真机访问

**正确做法**：
```python
# 后端：所有对外 URL 通过 settings 配置项管理
from app.config import get_settings

class ContentService:
    @staticmethod
    def _episode_to_dict(episode: Episode) -> dict:
        # 从配置读取 base URL，未配置时回退 localhost（仅开发工具可用）
        base = get_settings().AUDIO_BASE_URL or 'http://localhost:8000'
        audio_url = episode.audio_url
        if audio_url and audio_url.startswith('/audio/') and not audio_url.startswith('http'):
            audio_url = base + audio_url
        return {"audio_url": audio_url, ...}

# config.py 新增配置项
class Settings(BaseSettings):
    AUDIO_BASE_URL: str = ""  # 留空回退 localhost，真机测试设为电脑局域网 IP
```

```javascript
// 前端：BASE_URL 按环境切换，禁止硬编码单一环境
const BASE_URL = (typeof __wxConfig !== 'undefined' && __wxConfig.envVersion === 'release')
  ? 'https://api.example.com/api/v1'  // 生产环境
  : 'http://10.232.253.113:8000/api/v1';  // 开发环境（真机测试用电脑局域网 IP）
```

**环境地址选择规则**：

| 场景 | 后端 APP_HOST | AUDIO_BASE_URL | 前端 BASE_URL |
|------|---------------|----------------|---------------|
| 开发者工具调试 | 127.0.0.1 | 留空（回退 localhost） | http://localhost:8000 |
| 真机测试 | 0.0.0.0 | http://<电脑局域网IP>:8000 | http://<电脑局域网IP>:8000 |
| 生产部署 | 0.0.0.0 | https://<公网域名> | https://<公网域名> |

**规则**：
- 后端 `APP_HOST=0.0.0.0` 才能让局域网/公网访问，`127.0.0.1` 仅本机
- 所有静态资源 URL（音频/封面/上传文件）通过 `AUDIO_BASE_URL` 配置项管理
- 前端 BASE_URL 按 `__wxConfig.envVersion` 切换，禁止硬编码单一环境
- IP 变化时只需修改 `.env` 和前端 BASE_URL 两处

**适用场景**：小程序 + 后端服务架构、前后端分离项目
**不适用场景**：纯前端 SPA（无后端）、单机内部工具

---

## 规范 36：小程序页面四件套完整性

**为什么**：小程序页面由 .json/.js/.wxml/.wxss 四件套组成，缺一会导致编译错误或样式失效。历史问题：index/detail/profile 三个核心页面 .json 缺失，导致默认配置无 navigationBarTitleText；history.wxss 缺 top-bar/channel-pill 样式定义，导致频道胶囊垂直堆叠显示丑陋。

**判断信号**：
- 用 Glob 检查 `miniprogram/pages/*/*.json` 是否每个页面都有对应 .json
- 用 Grep 检查 .wxml 中使用的 CSS 类是否在对应 .wxss 中定义
- 检查 app.json pages 数组中每个路径是否都有四件套

**正确做法**：
```
// 新建页面时必须同步创建四件套
pages/
  new-page/
    new-page.json    // 页面配置（标题/下拉刷新/组件注册）
    new-page.js      // 页面逻辑（onLoad/onShow/onUnload）
    new-page.wxml    // 页面结构
    new-page.wxss    // 页面样式（所有 wxml 用到的类必须在此定义）

// new-page.json 最小配置
{
  "navigationBarTitleText": "页面标题",
  "enablePullDownRefresh": false
}
```

**规则**：
- 新建页面必须同步创建 .json/.js/.wxml/.wxss 四个文件
- .wxml 中用到的所有 CSS 类必须在对应 .wxss 中定义（或 app.wxss 全局定义）
- app.json pages 数组必须包含新页面路径
- 自定义组件在页面 .json 的 usingComponents 中注册后才能在 .wxml 中使用

**适用场景**：微信小程序原生开发、uni-app
**不适用场景**：React/Vue SPA（单文件组件）

---

## 规范 37：事件绑定对称性（on/off 配对）

**为什么**：小程序全局 player 的 onPlay/onPause/onTimeUpdate/onEnded 等监听器如果在 onLoad 注册但 onUnload 未 off，reLaunch 后 onLoad 重复绑定会导致回调叠加，UI 串扰（如多个 setData 竞争）。

**判断信号**：
- grep 搜索 `player.on\w+\(` 或 `audioManager.on\w+\(` 后检查 onUnload 是否有对应 `off\w+`
- grep 搜索 `this._onPlay = ` 检查回调是否保存为实例属性（用于精确 off）

**正确做法**：
```javascript
Page({
  onLoad() {
    this.bindPlayerEvents();
  },
  bindPlayerEvents() {
    const player = getApp().globalData.player;
    if (!player) return;
    // 回调保存为实例属性，供 onUnload 精确解绑
    this._onPlay = () => { this.setData({ isPlaying: true }); };
    this._onPause = () => { this.setData({ isPlaying: false }); };
    this._onTimeUpdate = () => {
      this.setData({
        currentTime: Math.floor(player.currentTime),
        duration: Math.floor(player.duration),
      });
    };
    this._onEnded = () => { this.setData({ isPlaying: false, currentTime: 0 }); };
    player.onPlay(this._onPlay);
    player.onPause(this._onPause);
    player.onTimeUpdate(this._onTimeUpdate);
    player.onEnded(this._onEnded);
  },
  onUnload() {
    const player = getApp().globalData.player;
    if (player) {
      // 必须精确 off 同一引用，不能 off 匿名函数
      player.offPlay?.(this._onPlay);
      player.offPause?.(this._onPause);
      player.offTimeUpdate?.(this._onTimeUpdate);
      player.offEnded?.(this._onEnded);
    }
    // 清除引用避免内存泄漏
    this._onPlay = null;
    this._onPause = null;
    this._onTimeUpdate = null;
    this._onEnded = null;
  },
});
```

**规则**：
- 所有 onXxx 监听器必须有对应 offXxx 解绑
- 回调必须保存为实例属性（this._onXxx），禁止匿名函数（无法精确 off）
- onUnload 中必须 off 所有监听器，并清除引用
- 一次性事件（如 onCanplay seek 后即 off）必须自清理

**适用场景**：小程序 Page/Component、Node.js EventEmitter、浏览器 addEventListener
**不适用场景**：一次性 Promise、async/await（自动清理）

---

## 规范 38：模型字段名验证（禁止凭记忆假设）

**为什么**：历史问题：content_service.py 中写了 `Workflow.workflow_id == workflow_id`，但 Workflow 模型主键字段名是 `id`（comment="workflow_id"），导致查询永远返回 None。凭记忆假设字段名是高频错误源。

**判断信号**：
- 代码中出现 `Model.field_name` 但未先 Read 模型定义文件确认
- PR review 时发现字段访问未对照模型源文件
- 查询条件 `where(Model.xxx == value)` 中 xxx 字段名拼写错误

**正确做法**：
```python
# ❌ 错误：凭记忆假设字段名
async def publish_episode(self, workflow_id: str):
    wf = await self.db.execute(
        select(Workflow.channel_id).where(Workflow.workflow_id == workflow_id)  # 字段名错误
    )

# ✅ 正确：先 Read 模型定义确认字段名
# Read backend/app/models/workflow.py
# 确认 class Workflow: id = mapped_column(...)  # comment="workflow_id"
async def publish_episode(self, workflow_id: str):
    # 主键字段名为 id（comment 标注为 workflow_id），不是 workflow_id
    wf = await self.db.execute(
        select(Workflow.channel_id).where(Workflow.id == workflow_id)
    )
```

**规则**：
- 编写涉及模型字段访问的代码前，必须先 Read 模型定义文件
- PR review 时，reviewer 必须对照模型源文件验证字段名
- 字段名有歧义时（如 id vs workflow_id），以模型定义为准，comment 仅作参考
- ORM 模型的 `__table__.columns` 是字段名的唯一可信源

**适用场景**：所有 ORM（SQLAlchemy/Django ORM/Tortoise）
**不适用场景**：原生 SQL（字段名在 SQL 中可见）

---

## 规范 39：统计口径校验（聚合查询前确认字段语义）

**为什么**：历史问题：用户收听统计用 `sum(PlayLog.duration)` 计算累计收听时长，但 `PlayLog.duration` 是节目总时长（每条日志记录节目时长），不是实际收听时长。结果"9 分钟"实际是"9 个节目总时长之和"，严重偏高。应改用 `PlayProgress.position`（每用户每节目一条 upsert 记录，position 是最后播放位置）。

**判断信号**：
- 聚合查询 `sum(field)` / `count(field)` 前未确认 field 的语义
- 统计结果与业务预期不符（如"累计收听 9 分钟"但用户只听了 3 分钟）
- 用日志表（PlayLog）做统计而非状态表（PlayProgress）

**正确做法**：
```python
# ❌ 错误：用 PlayLog.duration 统计收听时长
# PlayLog.duration 是节目总时长，sum(duration) = 节目总时长之和，严重偏高
total_seconds = await db.execute(
    select(func.sum(PlayLog.duration)).where(PlayLog.user_id == user_id)
)

# ✅ 正确：用 PlayProgress.position 统计收听时长
# PlayProgress 每用户每节目一条 upsert 记录，position 是最后播放位置
total_seconds = await db.execute(
    select(func.coalesce(func.sum(PlayProgress.position), 0))
    .where(PlayProgress.user_id == user_id)
)
```

**字段语义对照表**：

| 表 | 字段 | 语义 | 适用统计场景 |
|----|------|------|--------------|
| PlayLog | duration | 节目总时长（每条日志） | 播放次数统计、节目热度 |
| PlayLog | position | 播放位置（每条日志） | 历史播放位置追踪 |
| PlayProgress | position | 最后播放位置（upsert 单条） | 累计收听时长、断点续播 |
| PlayProgress | completed | 是否完播（0/1） | 完播率统计 |

**规则**：
- 聚合查询（sum/count/avg）前必须确认字段的业务语义
- 日志表（append-only）用于次数/热度统计，状态表（upsert）用于累计/当前值统计
- 统计结果与业务预期偏差 >20% 时必须复核字段语义
- 新增统计接口必须字段语义对照表

**适用场景**：所有数据库聚合查询、统计接口、报表
**不适用场景**：单条记录查询（字段语义直接可见）

---

## 规范 40：工具层与代码层 bug 分离原则

**为什么**：历史问题：微信开发者工具基础库 3.17.0 灰度版的 webview bug（`routeDone with a webviewId N is not found`）和 `appservice/mainframe 500` 被误判为代码问题，浪费修复时间。工具层 bug 无法通过代码修复，必须先排工具层后查代码层。

**判断信号**：
- 错误信息含 `system error` / `webviewId` / `appservice` / `mainframe` → 工具层
- 错误信息含 `SyntaxError` / `TypeError` / `KeyError` / `ImportError` → 代码层
- 错误仅在特定环境（开发者工具/真机/特定基础库版本）出现 → 工具层
- 错误在所有环境一致出现 → 代码层

**处理流程**：
```
1. 错误分类：先判断是工具层还是代码层
   - 工具层信号：system error / webviewId / appservice / 环境特定
   - 代码层信号：语法/类型/逻辑错误 / 全环境复现

2. 工具层 bug 处理：
   a. 降基础库版本（灰度版 → 稳定版）
   b. 清除工具缓存（菜单：工具 → 清除缓存 → 全选）
   c. 彻底重启工具（任务栏右键退出，非关窗口）
   d. 兜底：卸载重装工具（重置 profile，类似 Edge user data 损坏案例）

3. 代码层 bug 处理：
   a. 现象采集 → 代码定位 → 根因假设 → 验证假设 → 修复 → 测试验证
   b. 每个修复遵循：语法检查 → 测试套件 → 路由注册冒烟

4. 防御性代码（工具层 bug 的代码侧缓解）：
   - navigateTo 失败时降级为 reLaunch（避免页面栈满静默失败）
   - 播放器事件 off 时用可选链（player.offPlay?.(cb)）兼容 API 差异
```

**规则**：
- 遇到 `system error` / `webviewId` / `appservice` 类错误，先排工具层（降版本+清缓存+重启）
- 工具层 bug 的代码侧缓解措施仍需实施（防御性编程），但不是根治
- 代码层 bug 必须修复根因，不能仅靠工具层规避
- 已知工具层 bug（如 Edge 浏览器最小化自动恢复、开发者工具 webview 路由错误）记录到项目 memory

**适用场景**：所有依赖开发工具的项目（微信开发者工具、VS Code、IDEA 等）
**不适用场景**：纯命令行项目（无 IDE 依赖）
