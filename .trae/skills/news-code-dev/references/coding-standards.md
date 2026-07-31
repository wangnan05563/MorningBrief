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

### 多页面共享状态同步

**为什么**：多 Tab 页面共享同一份用户偏好/筛选状态时，状态可能被其他页面（如设置页）修改。若 `onShow` 仅依赖 `data` 镜像或时间戳单信号，会出现切换 Tab 后残留旧数据或漏刷新的情况。必须从权威源（`localData`/`globalData`）直接读取最新值，并采用"时间戳 + 内容"双校验判断是否需要刷新。

```javascript
// ✅ 正确：onShow 从权威源同步 + 时间戳/内容双校验
const localData = require('../../services/local-data')

Page({
  onShow() {
    const latestIds = localData.getPreferredChannels()  // 直接读权威源
    const app = getApp()
    // 时间戳变化 OR 内容不一致，任一满足即刷新
    const changedByTs = this._lastPreferredTs
      && this._lastPreferredTs !== app.globalData.preferredChannelsChanged
    const changedByContent = JSON.stringify(this.data.preferredIds)
      !== JSON.stringify(latestIds)
    if (changedByTs || changedByContent) {
      this.setData({ preferredIds: latestIds })
    }
    if (this.data.isPreferredMode) {
      this.loadPreferred()  // 处于偏爱模式则强制重新加载
    }
    this._lastPreferredTs = app.globalData.preferredChannelsChanged
  },

  async loadPreferred() {
    // 在数据加载入口再次从 localData 读取，避免 onShow 与 setData 之间的异步窗口
    const preferredIds = localData.getPreferredChannels()
    if (preferredIds.length === 0) {
      // 空状态必须显式标记，避免残留旧数据
      this.setData({ todayList: [], preferredEmpty: true, loading: false })
      getApp().globalData.todayList = []  // globalData 与 data 同步清空
      return
    }
    // ...加载并过滤数据
  }
})

// ❌ 错误：仅用时间戳判断，普通 Tab 切换不更新时间戳导致漏刷新
Page({
  onShow() {
    // 普通切 Tab 时 preferredChannelsChanged 不变，不会触发刷新
    if (this._lastPreferredTs !== getApp().globalData.preferredChannelsChanged) {
      this.loadPreferred()
    }
  }
})
```

**规则**：
- 跨页面共享的状态（用户偏好、筛选条件、登录态等）在 `onShow` 必须从权威源重新读取
- 变更检测采用"时间戳 OR 内容比对"双校验，单信号检测会漏掉 Tab 切换场景
- 在数据加载函数入口再次读取权威源，规避 `setData` 异步窗口
- 清空 `data` 时同步清空 `globalData` 中的镜像，避免其他页面读到残留数据
- 适用：跨页面共享的用户偏好、筛选条件、登录态；不适用：页面私有状态、单次加载的静态数据

### 过滤模式防御性二次过滤

**为什么**：上游（API/缓存）可能返回未过滤的全量数据，若下游渲染层不再过滤，会展示不应出现的内容。即使接口承诺过滤，下游也必须按当前过滤条件二次校验，防御性编程避免上游契约变更导致的问题。

```javascript
// ✅ 正确：在数据应用层按当前过滤模式二次过滤
Page({
  _applyTodayData(data) {
    let list = Array.isArray(data) ? data : []
    // 即使上游返回已过滤，下游按当前模式再次过滤
    if (this.data.currentChannelId === 'preferred' && list.length > 0) {
      const preferredIds = localData.getPreferredChannels()
      if (preferredIds.length > 0) {
        const idSet = new Set(preferredIds)
        list = list.filter(ep => idSet.has(ep.channel_id))
      } else {
        list = []  // 偏爱为空则结果必为空
      }
    }
    this.setData({ todayList: list.map(ep => this._enrichEpisode(ep)) })
  }
})

// ❌ 错误：信任上游已过滤，下游不再校验
Page({
  _applyTodayData(data) {
    // 若上游因缓存/预渲染返回全量数据，偏爱模式下会展示所有频道
    this.setData({ todayList: data })
  }
})
```

**规则**：
- 列表渲染层必须按当前过滤条件（频道/分类/偏好）二次校验数据
- 过滤条件为空时，结果必须显式置空，不能保留旧数据
- 过滤逻辑应从权威源读取过滤条件，不依赖 `data` 镜像
- 适用：按用户偏好/权限/频道过滤的列表展示；不适用：单一来源已保证过滤且契约稳定的场景

### 空状态显式标记

**为什么**：空状态（如未设置偏好、搜索无结果）若不显式标记，UI 会残留上一次的数据，导致"切 Tab 后又能看到已清空的内容"。每次数据加载必须显式设置 `xxxEmpty` 标志，wxml 通过该标志显示引导提示。

```javascript
// ✅ 正确：每次加载显式设置空状态标志
Page({
  async loadPreferred() {
    const preferredIds = localData.getPreferredChannels()
    if (preferredIds.length === 0) {
      this.setData({
        todayList: [],
        preferredEmpty: true,   // 显式标记空状态
        loading: false,
      })
      return
    }
    const filtered = await this._fetchAndFilter(preferredIds)
    this.setData({
      todayList: filtered,
      preferredEmpty: filtered.length === 0,  // 过滤后为空也标记
      loading: false,
    })
  }
})

// ❌ 错误：未显式重置 preferredEmpty，切 Tab 后残留 true/false
Page({
  async loadPreferred() {
    // 未设置 preferredEmpty，wxml 无法判断是"未加载"还是"空数据"
    const list = await fetchData()
    this.setData({ todayList: list })
  }
})
```

```xml
<!-- wxml 通过 preferredEmpty 显示引导提示 -->
<view wx:if="{{isPreferredMode && preferredEmpty}}" class="preferred-empty-card">
  <view>还没有偏爱频道</view>
  <view bindtap="onTapPreferredSettings">去设置偏爱频道</view>
</view>
```

**规则**：
- 每个可能为空的状态（列表、详情、计数）必须有对应的 `xxxEmpty` 标志
- 数据加载函数必须在所有分支（未设置、加载失败、过滤后为空）显式设置该标志
- wxml 通过 `wx:if="{{xxxEmpty}}"` 显示引导提示，而非依赖列表长度判断
- 适用：可能为空且影响 UI 展示的状态；不适用：始终有默认值或 fallback 的状态

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

**为什么**：工作流 TTS 步骤批量失败时，仅返回 /6 成功率过低 无法定位具体哪一段失败、失败原因是什么。必须在最终异常消息中包含脱敏后的分段失败摘要。

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

---

## 规范 45：模板字符串字面花括号转义

**Python str.format() 模板中，字面花括号必须双写转义 {{ }}，否则 str.format() 会把它当作变量去替换，触发 KeyError。**

**为什么**：str.format() 把所有 `{xxx}` 视为待替换的变量占位符。如果 xxx 是给下游（如 LLM）看的字面占位符而非 Python 变量，str.format() 找不到对应参数就会抛 KeyError，FastAPI 默认转换为 500 错误，业务功能完全不可用。

**判断信号**：grep 搜索 `.format(` 调用的模板字符串中含 `{xxx}` 但 xxx 不在 format 参数列表中

**正确做法**：
```python
# ✅ 正确：字面花括号双写转义
META_PROMPT_TEMPLATE = """
你是一个新闻编辑，请基于以下占位符生成稿件：
- {{date_placeholder}}：当前日期
- {{channel_name}}：频道名称

当前日期：{actual_date}
频道：{actual_channel}
""".format(actual_date=today, actual_channel=name)
# {{date_placeholder}} 输出为字面字符串 {date_placeholder} 给 LLM 使用

# ❌ 错误：字面花括号未转义
META_PROMPT_TEMPLATE = """
你是一个新闻编辑，请基于以下占位符生成稿件：
- {date_placeholder}：当前日期  # KeyError: date_placeholder

当前日期：{actual_date}
""".format(actual_date=today)
```

**规则**：
- 所有使用 `str.format()` 的模板字符串中，给下游（LLM/用户/日志）看的字面 `{xxx}` 占位符必须双写为 `{{xxx}}`
- 使用 f-string 时同理：字面花括号必须双写
- 评审时检查 `.format(` 调用，确认模板中所有 `{xxx}` 都有对应 format 参数或已双写转义
- 优先考虑用 `string.Template` / `%` 格式化或自定义替换函数，规避字面花括号冲突

**适用场景**：所有使用 str.format() / f-string 的模板字符串
**不适用场景**：raw string、不参与 format 的字符串

---

## 规范 46：API Key 脱敏值回传检测

**接收前端回传的密钥字段时，必须用 _is_masked() 判断是否为脱敏值（****xxxx 格式），若是则回退到已保存的真实密钥。**

**为什么**：前端在加载配置时通常会把密钥字段脱敏显示（如 `****5ba0`），用户保存配置时如果未重新输入完整密钥，前端会原样回传脱敏值。后端如果不检测，直接把脱敏值当作真实 token 调用第三方服务，必然报 token invalid / 401，用户误以为密钥填错反复重填无果。

**判断信号**：grep 搜索 `test_xxx_connection` 函数中 `if not api_key` 未同时判断 `_is_masked`

**正确做法**：
```python
# ✅ 正确：检测脱敏值并回退到已保存的真实密钥
def _is_masked(value: str) -> bool:
    """判断是否为前端脱敏值（如 ****5ba0）。"""
    return bool(value) and value.startswith("****") and len(value) < 50

async def test_tts_connection(api_key: str) -> dict:
    # 前端回传脱敏值时，从数据库读取真实 token
    if _is_masked(api_key):
        api_key = await get_saved_token_from_db("ALIYUN_TTS_TOKEN")
        if not api_key:
            return {"ok": False, "msg": "未读取到已保存的 Token，请重新输入"}
    # 用真实 token 调用阿里云 NLS
    return await _call_aliyun_nls(api_key)

# ❌ 错误：直接用前端回传值调用
async def test_tts_connection(api_key: str) -> dict:
    return await _call_aliyun_nls(api_key)  # ****5ba0 直接调 NLS 报 token invalid
```

**规则**：
- 所有密钥字段（API Key / Token / Secret / Password）的回传接口必须先经过 `_is_masked()` 检测
- 检测到脱敏值时必须从数据库回退到已保存的真实密钥，数据库无值时返回明确提示
- `_is_masked()` 实现须识别常见脱敏模式（`****` 前缀、长度小于真实密钥等）
- 测试连接、保存配置两类接口都必须做此检测

**适用场景**：所有密钥字段（API Key / Token / Secret）的测试连接、保存配置等回传场景
**不适用场景**：明文密钥输入（用户主动重新输入完整密钥）

---

## 规范 47：第三方服务错误码可读化映射

**第三方服务（阿里云 NLS / OpenAI / DeepSeek 等）的错误码必须维护 ERROR_CODE_HINTS 映射表，转换为可读中文提示返回给前端。**

**为什么**：第三方服务的原始错误码（如阿里云 NLS `40000001` / `40000010` / `40000004`）对用户完全不可读，用户无法判断是凭证填错、配额超限还是网络问题。直接返回原始错误码会引发大量"无法定位"的用户咨询。

**判断信号**：grep 搜索第三方 API 响应中的 `error_code` / `code` 字段直接返回前端，无映射表

**正确做法**：
```python
# ✅ 正确：维护 ERROR_CODE_HINTS 映射表
ALIYUN_NLS_ERROR_HINTS = {
    "40000001": "token invalid：请确认填写的是 NLS AccessToken，而非 AccessKey Secret",
    "40000010": "appkey invalid：请确认 NLS AppKey 与 AccessToken 属于同一项目",
    "40000004": "请求参数错误：请检查 voice / rate / pitch 配置",
    "40000002": "请求超时：请稍后重试",
}

def _translate_nls_error(error_code: str, raw_msg: str) -> str:
    hint = ALIYUN_NLS_ERROR_HINTS.get(error_code)
    if hint:
        return f"[{error_code}] {hint}"
    return f"[{error_code}] {raw_msg}"

# 调用层返回可读提示
try:
    result = await nls_client.synthesize(text)
except NLSError as e:
    return {"ok": False, "msg": _translate_nls_error(e.code, str(e))}

# ❌ 错误：直接返回原始错误码
try:
    result = await nls_client.synthesize(text)
except NLSError as e:
    return {"ok": False, "msg": f"error_code={e.code}, message={e}"}  # 用户看不懂
```

**规则**：
- 每个第三方服务（NLS / OpenAI / DeepSeek / 通义千问等）必须维护独立的 `ERROR_CODE_HINTS` 映射表
- 错误提示必须包含：原错误码 + 中文说明 + 排查建议（如"请确认填写的是 X 而非 Y"）
- 未在映射表中的错误码兜底返回 `[code] 原始消息`
- 错误提示禁止包含敏感信息（API Key / Secret / Token 完整值）

**适用场景**：所有第三方服务调用（LLM / TTS / 存储 / 内容安全）
**不适用场景**：内部业务错误码（已有统一错误码体系，见 API 契约规范）

---

## 规范 48：Settings 字段与 ORM/前端/服务层四端同步

**新增配置项时，Settings 类、ORM 模型、前端表单、服务层 CONFIG_KEY_MAP 四端必须同步，任一端缺失都会导致 setattr(settings, ...) 报 AttributeError 或配置无法持久化。**

**为什么**：项目使用 SQLite 持久化配置 + Settings 单例热生效模式。新增配置项时如果只更新了前端表单和 ORM 模型，但 Settings 类没有该字段，服务层执行 `setattr(settings, "ALIYUN_TTS_APPKEY", value)` 会失败（Pydantic BaseSettings 默认禁止额外属性），导致 500 错误。

**判断信号**：grep 搜索 `setattr(settings,` 中引用的属性名是否在 Settings 类定义中存在

**正确做法**：
```python
# ✅ 正确：新增 ALIYUN_TTS_APPKEY 配置项时四端同步

# 1. Settings 类（app/core/config.py）
class Settings(BaseSettings):
    ALIYUN_TTS_APPKEY: str = ""  # 新增字段

# 2. ORM 模型（app/models/config.py，如果用键值表则跳过）
# 若用键值表，无需新增字段；若用列存储，需 ALTER TABLE

# 3. 前端表单（admin-web/src/views/ai-config/index.vue）
# <el-form-item label="NLS AppKey">
#   <el-input v-model="form.aliyun_tts_appkey" />
# </el-form-item>

# 4. 服务层 CONFIG_KEY_MAP（app/services/ai_config_service.py）
CONFIG_KEY_MAP = {
    "aliyun_tts_appkey": "ALIYUN_TTS_APPKEY",  # 前端键 → Settings 属性
    # ...
}

# 保存时安全 setattr
for fe_key, value in form_data.items():
    settings_key = CONFIG_KEY_MAP.get(fe_key)
    if settings_key and hasattr(settings, settings_key):
        setattr(settings, settings_key, value)

# ❌ 错误：只更新前端和 CONFIG_KEY_MAP，Settings 类缺字段
# Settings 类未定义 ALIYUN_TTS_APPKEY
setattr(settings, "ALIYUN_TTS_APPKEY", value)  # AttributeError / 500
```

**规则**：
- 新增配置项时必须同步更新四端：Settings 类 / ORM 模型（或键值表） / 前端表单 / 服务层 `CONFIG_KEY_MAP`
- `setattr(settings, key, value)` 前必须用 `hasattr(settings, key)` 防御性检查
- 字段名约定：前端用 snake_case，Settings 类用 UPPER_SNAKE_CASE，`CONFIG_KEY_MAP` 负责映射
- 删除配置项时四端同步删除，避免遗留死字段

**适用场景**：所有通过 SQLite 持久化 + Settings 单例热生效的配置项
**不适用场景**：临时变量、一次性配置（不持久化）

---

## 规范 49：表单字段标签语义明确性

**表单字段标签必须明确字段含义，禁止使用"API Key"等通用名称混淆不同凭证。**

**为什么**：同一个第三方服务商通常有多种凭证（如阿里云有 AccessKey ID / AccessKey Secret / NLS AppKey / NLS AccessToken），如果表单标签统一写成"API Key"，用户无法区分该填哪一个，极易误填。误填后测试连接报 token invalid，但用户看不出是字段填错。

**判断信号**：grep 搜索 `el-form-item label="API Key"` 等通用标签

**正确做法**：
```vue
<!-- ✅ 正确：标签明确字段具体含义 -->
<el-form-item label="NLS AccessToken">
  <el-input v-model="form.aliyun_tts_token" type="password" show-password />
  <div class="form-hint">在 NLS 控制台 → 项目管理 → Token 获取</div>
</el-form-item>

<el-form-item label="NLS AppKey">
  <el-input v-model="form.aliyun_tts_appkey" />
  <div class="form-hint">在 NLS 控制台 → 项目管理 → AppKey 列获取</div>
</el-form-item>

<el-form-item label="AccessKey ID">
  <el-input v-model="form.aliyun_access_key_id" />
</el-form-item>

<el-form-item label="AccessKey Secret">
  <el-input v-model="form.aliyun_access_key_secret" type="password" show-password />
</el-form-item>

<!-- ❌ 错误：标签含义模糊 -->
<el-form-item label="API Key">
  <el-input v-model="form.aliyun_tts_token" />
  <!-- 用户误填 AccessKey Secret 到 NLS AccessToken 字段 -->
</el-form-item>
```

**规则**：
- 同一服务商有多种凭证时，标签必须使用凭证的具体名称（如 `NLS AccessToken` / `NLS AppKey` / `AccessKey ID` / `AccessKey Secret`）
- 禁止使用 `API Key` / `Secret` / `Token` 等通用单字段标签
- 凭证字段下方应补充获取路径提示（如"在 X 控制台 → Y 菜单获取"）
- 同类型凭证在不同服务商间也应区分（如 `OpenAI API Key` / `DeepSeek API Key`）

**适用场景**：所有含凭证字段的配置表单
**不适用场景**：单一凭证场景（无歧义）

---

## 规范 50：密钥获取入口超链接规范化

**所有配置表单中的密钥字段必须提供官方获取入口超链接（el-link target="_blank"），让用户知道在哪里申请。**

**为什么**：第三方服务的密钥获取入口分散在不同控制台（阿里云 AccessKey 在 RAM 控制台、NLS AppKey/Token 在 NLS 控制台、OpenAI Key 在 platform.openai.com），用户如果不熟悉控制台导航，根本找不到申请入口，导致配置流程卡住或填入错误凭证。

**判断信号**：grep 搜索 `el-form-item label.*Key|Token|Secret` 但对应字段无 `el-link href` 超链接

**正确做法**：
```vue
<!-- ✅ 正确：表单顶部提供官方获取入口 -->
<template>
  <el-alert type="info" :closable="false">
    <template #title>
      阿里云 NLS 凭证获取：
      <el-link href="https://nls-portal.console.aliyun.com/applist" target="_blank" type="primary">
        NLS 控制台（AppKey / Token）
      </el-link>
      <el-link href="https://ram.console.aliyun.com/manage/ak" target="_blank" type="primary">
        RAM 控制台（AccessKey）
      </el-link>
    </template>
  </el-alert>

  <el-form :model="form">
    <el-form-item label="NLS AppKey">
      <el-input v-model="form.aliyun_tts_appkey" />
    </el-form-item>
    <el-form-item label="NLS AccessToken">
      <el-input v-model="form.aliyun_tts_token" type="password" show-password />
    </el-form-item>
  </el-form>
</template>

<!-- ❌ 错误：仅有字段输入框，无获取入口 -->
<el-form :model="form">
  <el-form-item label="NLS AppKey">
    <el-input v-model="form.aliyun_tts_appkey" />
    <!-- 用户不知在哪里申请 AppKey -->
  </el-form-item>
</el-form>
```

**规则**：
- 超链接必须 `target="_blank"` 在新窗口打开，避免离开配置页面
- 超链接放在表单顶部或字段下方提示位置，确保用户在填写前看到
- 不同凭证（AccessKey / NLS Token / OpenAI Key）提供各自对应的官方控制台入口
- 超链接 URL 必须是官方域名（aliyuncs.com / openai.com 等），禁止跳转到第三方教程

**适用场景**：所有第三方服务凭证配置表单
**不适用场景**：内部系统凭证（无外部获取入口）

---

## 规范 51-60：2026-07-18 SonarQube 迭代闭环复盘新增规范

> 以下规范来源于 2026-07-18 SonarQube MCP 扫描 + 问题修复迭代闭环复盘，覆盖认知复杂度治理、async/await 语义、正则优化、未使用代码检测、数据驱动重构、import 组织、DOM API 现代化、空 except 块禁止、SQ 扫描闭环、三层测试验证共 10 个维度。所有阈值参数通过 `project-config.json#coding_standards` 管理。

---

## 规范 51：认知复杂度阈值治理

**函数 cognitive_complexity ≤ 15，超阈值必须抽取辅助函数或重构为数据驱动。**

**为什么**：SonarQube 默认 cognitive_complexity 阈值 15。复杂度超阈值函数可读性差、难以测试、易引入缺陷。本次迭代发现 `tunnel_providers.py`、`maintenance_service.py`、`db_admin_service.py` 等函数均因 if/elif 链嵌套过深超标，单次修复+二次扫描回归验证后所有问题归零。

**阈值参数**（通过 `project-config.json#coding_standards.complexity` 配置）：
```json
{
  "complexity": {
    "max_function_lines": 50,
    "max_nesting": 3,
    "max_cognitive_complexity": 15
  }
}
```

**判断信号**：
- grep `^    if` 在同一函数内连续出现 4 次以上
- ruff `C901` 警告
- SonarQube `cognitive_complexity` issue

**正确做法**：
```python
# ✅ 抽取辅助函数（首选）
def _validate_tunnel_config(config: dict) -> list[str]:
    errors = []
    if not config.get('provider'):
        errors.append('provider required')
    if not config.get('token'):
        errors.append('token required')
    return errors

def create_tunnel(config: dict) -> Tunnel:
    errors = _validate_tunnel_config(config)
    if errors:
        raise ValidationError(errors)
    # 主逻辑...

# ✅ 数据驱动重构（备选，见规范 56）
PROVIDER_HANDLERS: list[tuple[str, Callable]] = [
    ('ngrok', create_ngrok_tunnel),
    ('cloudflare', create_cloudflare_tunnel),
]
```

**错误做法**：保持长函数 + 嵌套 if/elif

**适用场景**：业务逻辑复杂的 service/workflow 层
**不适用场景**：纯数据声明的 models 层、配置常量文件

---

## 规范 52：async 函数必须含 await

**`async def` 函数体内必须至少有一个 `await` 表达式，否则转为同步函数。**

**为什么**：SonarQube S7503 规则。`async def` 内无 `await` 会误导调用者认为该函数有 IO 操作可并发执行，实际是同步阻塞，徒增事件循环开销。本次迭代发现 `secrets.py` 中 `async def mask_secret()` 函数体内无 await。

**判断信号**：
- grep `async def` 后 50 行内无 `await` 关键字
- SonarQube S7503 issue

**正确做法**：
```python
# ✅ 方式 1：转同步函数
def mask_secret(value: str) -> str:
    if not value:
        return ''
    return value[:4] + '*' * (len(value) - 8) + value[-4:]

# ✅ 方式 2：补充 await 调用（如确有异步操作）
async def fetch_secret(key: str) -> str:
    value = await cache.get(key)
    return mask_secret(value)
```

**例外**：事件回调、`asyncio.create_task` 包装的 fire-and-forget 任务（需注释说明）

**适用场景**：所有 async 函数
**不适用场景**：事件回调函数（如 `async def on_event()` 注册回调）

---

## 规范 53：正则表达式捕获组优化

**正则表达式中未使用的捕获组必须改为非捕获组 `(?:...)`，仅保留需 `group()` 提取的捕获组。**

**为什么**：SonarQube S6395 规则。捕获组 `(...)` 比 `(?:...)` 慢（需分配内存记录匹配内容），且未使用的捕获组会误导维护者认为该子串会被提取。本次迭代发现 `secrets.py` 中多处 `re.match(r'(prefix)(.*)')` 仅用 `group(0)` 但定义了多个捕获组。

**判断信号**：
- grep `re.match` / `re.sub` / `re.compile` 中含 `(...)` 但后续无 `group(1)`/`group(2)` 等提取
- SonarQube S6395 issue

**正确做法**：
```python
# ✅ 使用非捕获组
match = re.match(r'(?:prefix)(.*)', value)
if match:
    return match.group(1)  # 仅提取需要的组

# ❌ 使用捕获组但未提取
match = re.match(r'(prefix)(.*)', value)  # 浪费内存
```

**适用场景**：所有使用 `re` 模块的代码
**不适用场景**：需要 `group(N)` 提取子串的场景（必须用捕获组）

---

## 规范 54：list() 调用必要性检测

**`list(iterable)` 仅在需要索引访问或多次迭代时使用，单一 `for` 循环直接迭代可迭代对象。**

**为什么**：SonarQube S7504 规则。`list(dict.keys())` 在 Python 3 中 dict.keys() 已是可迭代视图，无需转 list 即可迭代。`list()` 转换浪费内存（一次性加载所有元素到列表）。本次迭代发现 `ai_config_service.py` 中 `for key in list(config.keys())` 多余转换。

**判断信号**：
- grep `for \w+ in list\(` 模式
- SonarQube S7504 issue

**正确做法**：
```python
# ✅ 直接迭代
for key in config.keys():  # 或 for key in config:
    process(key)

# ❌ 多余 list() 转换
for key in list(config.keys()):
    process(key)
```

**例外**：需在迭代中修改 dict（迭代时增删 key 需先转 list 避免运行时错误）

**适用场景**：所有 `for` 循环代码
**不适用场景**：需索引访问 `lst[0]`、需多次迭代、迭代中修改集合

---

## 规范 55：未使用变量、参数与导入检测

**变量、参数、导入声明后必须使用，禁止死代码。**

**为什么**：SonarQube S1481（未使用局部变量）/ S1128（未使用导入）。未使用的代码增加维护负担、误导维护者认为该变量/导入有用途、增加打包体积。本次迭代发现 `workflow_scheduler.py`、`maintenance_service.py` 中多处未使用 import 和局部变量。

**判断信号**：
- ruff F841（未使用变量）/ F401（未使用导入）
- pylint W0612 / W0611
- SonarQube S1481 / S1128 issue

**正确做法**：直接删除未使用声明
```python
# ❌ 未使用
import os  # 未使用
from typing import Optional  # 未使用

def foo():
    unused_var = 42  # 未使用
    return "hello"

# ✅ 删除后
def foo():
    return "hello"
```

**例外**：协议要求的接口参数（如 `__init__(self, unused_param)` 协议签名）需用 `_unused_param` 前缀

**适用场景**：所有 Python 与前端代码
**不适用场景**：协议接口、抽象基类、`__all__` 导出列表

---

## 规范 56：数据驱动重构模式

**同一函数内 ≥3 个 elif 判断同一变量时，必须重构为 `list[tuple]` + 循环。**

**为什么**：if/elif 链超过 3 个分支时，复杂度线性增长，难以维护和扩展。数据驱动重构将判断条件与处理逻辑解耦，新增分支只需追加 tuple，不需修改主流程。本次迭代发现 `tunnel_providers.py` 中按 provider 类型分发逻辑有 5 个 elif 分支。

**配置参数**：`project-config.json#coding_standards.data_driven_refactor.min_elif_count` = 3

**判断信号**：
- 同一函数内 ≥3 个 `elif` 判断同一变量
- 函数行数 >50 且含 ≥3 个 elif

**正确做法**：
```python
# ✅ 数据驱动
PROVIDER_HANDLERS: list[tuple[str, Callable]] = [
    ('ngrok', create_ngrok_tunnel),
    ('cloudflare', create_cloudflare_tunnel),
    ('frp', create_frp_tunnel),
    ('localtunnel', create_localtunnel),
]

def create_tunnel(provider: str, config: dict) -> Tunnel:
    for name, handler in PROVIDER_HANDLERS:
        if provider == name:
            return handler(config)
    raise ValueError(f'Unknown provider: {provider}')

# ❌ if/elif 链
def create_tunnel(provider: str, config: dict) -> Tunnel:
    if provider == 'ngrok':
        return create_ngrok_tunnel(config)
    elif provider == 'cloudflare':
        return create_cloudflare_tunnel(config)
    elif provider == 'frp':
        return create_frp_tunnel(config)
    elif provider == 'localtunnel':
        return create_localtunnel(config)
    raise ValueError(f'Unknown provider: {provider}')
```

**适用场景**：分支数 ≥3 且处理逻辑相似的函数
**不适用场景**：分支逻辑差异大、仅 1-2 个分支、性能敏感场景（每次循环遍历开销）

---

## 规范 57：import 语句组织规范

**import 语句分三组（标准库→第三方库→项目内），每组内字母序排列。**

**为什么**：SonarQube S3863 规则。统一的 import 组织提升可读性、便于排查依赖来源、降低合并冲突概率。本次迭代发现 `DatabaseAdmin.vue`、`Maintenance.vue`、`Tunnel.vue` 中 import 顺序混乱。

**判断信号**：
- eslint `import/order` 警告
- isort `I001` 警告
- SonarQube S3863 issue

**正确做法**：
```python
# Python
# 1. 标准库
import os
import sys
from typing import Optional

# 2. 第三方库
from fastapi import FastAPI
from sqlalchemy import select

# 3. 项目内
from app.core.config import settings
from app.models.workflow import Workflow
```

```vue
<!-- Vue SFC -->
<script setup lang="ts">
// 1. Vue 内置
import { ref, computed, onMounted } from 'vue'
import type { PropType } from 'vue'

// 2. 第三方库
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

// 3. 项目内
import { getWorkflowList } from '@/api/workflow'
import type { WorkflowItem } from '@/types/workflow'
</script>
```

**适用场景**：所有 Python 与前端代码
**不适用场景**：无（强制规范）

---

## 规范 58：DOM API 现代化规范

**优先使用现代 DOM API，废弃 API 必须替换。**

**为什么**：SonarQube S7762 规则。现代 DOM API 更简洁、性能更好、跨浏览器兼容性更佳。本次迭代发现前端代码中 `removeChild`、`className` 字符串拼接等废弃写法。

**判断信号**：
- grep `removeChild(`
- grep `parentNode.appendChild`
- grep `className =` 后跟字符串拼接

**正确做法**：
```javascript
// ✅ 现代 API
element.remove()
parent.append(child)
element.classList.add('class1', 'class2')
element.classList.remove('class1')
element.dataset.userId = '123'  // 替代 getAttribute('data-user-id')

// ❌ 废弃 API
parent.removeChild(element)
parent.appendChild(child)
element.className = 'class1 class2'
element.getAttribute('data-user-id')
```

**适用场景**：所有前端 JavaScript/TypeScript 代码
**不适用场景**：需兼容 IE11 的项目（本项目仅支持现代浏览器，无此约束）

---

## 规范 59：SonarQube 扫描闭环规范

**发版前必须执行完整 SonarQube 扫描-修复-回归闭环，二次扫描 OPEN=0 且无新增问题方可发版。**

**为什么**：本次迭代通过 SonarQube MCP 扫描发现 23 个 OPEN 问题，单次修复后二次扫描又出现新问题（修复引入新缺陷），证明必须执行回归扫描验证。仅修复首次扫描问题不足以保证质量。

**闭环流程（7 步）**：
1. 启动扫描：`sonar-scanner` 命令（路径与 token 走环境变量）
2. 等待分析完成：轮询 `tasks/search` API status=SUCCESS
3. 拉取问题：`issues/search` API + `componentKeys=` 过滤
4. 问题分类（按 severity）：
   - BLOCKER/CRITICAL → 必须修复（P0）
   - MAJOR → 应修复（P1）
   - MINOR → 建议修复（P2）
   - INFO → 记录即可（P3）
5. 按问题类型应用修复模式（参考规范 51-58）
6. 单元测试验证：`pytest --asyncio-mode=auto`
7. 二次扫描回归：验证 OPEN=0 且无新增问题

**配置参数**（通过 `project-config.json#sonarqube` 配置）：
```json
{
  "sonarqube": {
    "scanner_path_env_var": "SONAR_SCANNER_HOME",
    "token_env_var": "SONAR_TOKEN",
    "project_key": "20_News",
    "sources": "backend/app,admin-web/src",
    "exclusions": "**/__pycache__/**,**/node_modules/**,**/dist/**",
    "severity_must_fix": ["BLOCKER", "CRITICAL"],
    "severity_should_fix": ["MAJOR"],
    "severity_record_only": ["MINOR", "INFO"],
    "max_regression_retries": 3
  }
}
```

**判断逻辑**：
- 二次扫描 OPEN 数量减少 → 继续验证
- 二次扫描 OPEN 数量持平或增加 → 触发回滚检查（修复方式错误）
- 二次扫描出现新问题 → 修复引入新缺陷，需重新修复

**适用场景**：所有发版前完整验证
**不适用场景**：热修复（hotfix）的快速验证、未集成 SonarQube 的项目

---

## 外部服务降级规范

### 规范 127：外部服务降级本地存储模式

**为什么**：COS/OSS/S3 等外部对象存储在生产环境可能因配置缺失、凭证失效、网络不可达等原因不可用。若代码直接 raise 会导致整个工作流失败，已生成的 TTS 音频浪费。必须实现优雅降级到本地文件系统，保证业务连续性。

**适用场景**：生产环境 COS 降级、开发环境无 COS、COS 配置缺失容错
**不适用场景**：纯本地开发环境（无需 COS 配置检测）、已配置 COS 的稳定生产环境

**规则**：
1. 所有外部对象存储上传操作必须实现 `is_xxx_configured()` 单一真相源检测函数
2. 未配置时降级到本地 `data/<service>_cache/` 目录，键名保持与 COS Key 一致
3. 必须挂载对应的静态目录路由（如 `/audio/<key>`），且挂载顺序在 SPA fallback 之前
4. URL 生成函数必须感知存储模式：COS 模式返回完整 URL，本地模式返回 `/audio/<key>` 相对路径
5. 下游消费者（如 ffmpeg download_file）必须支持本地 `/audio/` 前缀检测，使用 `shutil.copyfile` 而非 httpx 下载
6. 降级模式必须记录 INFO 日志：`External COS not configured, fallback to local storage`

**判断信号**：
- `cos_client.put_object` 后无 try/except 或无 fallback 分支 → 违规
- `if is_cos_configured():` 后无 else 分支 → 违规
- 多处重复 `if settings.COS_SECRET_ID:` 判断 → 违规（应复用 `is_cos_configured()`）
- 外部存储上传失败直接 raise 而非降级 → 违规

**示例**：

```python
# ❌ 反模式：多处重复判断 + 无降级
async def upload_audio(content: bytes, key: str) -> str:
    if settings.COS_SECRET_ID and settings.COS_SECRET_KEY:
        cos_client.put_object(Bucket=settings.COS_BUCKET, Key=key, Body=content)
        return f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
    raise RuntimeError("COS not configured")  # 直接失败，业务中断

# ✅ 正确：单一真相源 + 本地降级
from app.core.config import is_cos_configured

async def upload_audio(content: bytes, key: str) -> str:
    if is_cos_configured():
        try:
            cos_client.put_object(Bucket=settings.COS_BUCKET, Key=key, Body=content)
            return f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
        except Exception as e:
            logger.warning(f"COS upload failed, fallback to local: {e}")
    # 降级到本地存储
    local_dir = Path(settings.LOCAL_AUDIO_CACHE_DIR)  # data/audio_cache/
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / key).write_bytes(content)
    logger.info("External COS not configured, fallback to local storage")
    return f"/audio/{key}"  # 相对路径，由 StaticFiles 挂载提供
```

**配置驱动**：所有阈值通过 `project-config.json#external_storage_fallback` 管理（single_truth_source_fn/local_dir/static_mount_point/downstream_prefixes）。

### 规范 128：Windows asyncio ConnectionResetError 异常过滤

**为什么**：Windows 平台 FastAPI/uvicorn 服务，浏览器 audio 标签或客户端提前关闭连接时，`ProactorBasePipeTransport._call_connection_lost` 会抛出 `ConnectionResetError [WinError 10054]`。这是 Python + Windows 的已知行为，非业务 bug，但会污染日志，干扰真实问题定位。必须在事件循环异常处理器中过滤此类已知行为。

**适用场景**：Windows 平台部署、客户端连接频繁断开（如浏览器 audio 标签）
**不适用场景**：Linux/macOS（select/epoll 无此问题）、服务端长连接

**规则**：
1. Windows 平台必须在事件循环异常处理器中过滤 ProactorBasePipeTransport 相关的 ConnectionResetError
2. 过滤逻辑应通过配置开关控制：`asyncio.suppress_connection_reset: true`
3. 必须区分业务异常（保留堆栈）和平台已知行为（仅 DEBUG 日志）
4. 异常过滤清单必须配置驱动：`asyncio.ignored_exceptions: ["ConnectionResetError"]`
5. 不适用于 Linux/macOS（select/epoll 无此问题）

**判断信号**：
- 日志中重复出现 `Exception in callback _ProactorBasePipeTransport._call_connection_lost` → 违规
- `ConnectionResetError: [WinError 10054]` 频繁出现 → 违规
- 无自定义异常处理器过滤此类已知行为 → 违规

**示例**：

```python
# ❌ 反模式：无异常过滤，日志被污染
import asyncio
loop = asyncio.get_event_loop()
# 默认异常处理器会打印完整 traceback 到 stderr

# ✅ 正确：配置驱动过滤平台已知行为
import sys
from app.core.config import settings

def _on_loop_exception(loop, context):
    exc = context.get('exception')
    handle = context.get('handle', '')
    # 配置驱动过滤清单
    for rule in settings.ASYNCIO_IGNORED_EXCEPTIONS:
        if (isinstance(exc, getattr(__builtins__, rule['exception_type'], object))
                and rule['transport_class'] in str(handle)):
            logger.debug(f"Ignored platform exception: {rule['exception_type']}")
            return
    loop.default_exception_handler(context)

if sys.platform == 'win32' and settings.ASYNCIO_SUPPRESS_CONNECTION_RESET:
    loop.set_exception_handler(_on_loop_exception)
```

**配置驱动**：所有阈值通过 `project-config.json#asyncio_exception_filter` 管理（enabled_platforms/ignored_exceptions/handler_priority）。

### 规范 129：本地路径 URL 约定

**为什么**：外部存储降级模式或本地开发模式下，下游服务（如 ffmpeg、TTS 拼接器）需要通过 URL 访问本地文件。若用 httpx 自回路请求本机服务（`http://localhost:8000/audio/...`）会造成性能损耗和死锁风险。必须约定本地路径 URL 前缀，下游函数优先检测本地前缀，命中则直接文件拷贝。

**适用场景**：外部存储降级模式、本地开发联调、CI 测试环境
**不适用场景**：已配置 COS 的生产环境、跨主机访问场景

**规则**：
1. 本地降级模式下，URL 必须使用 `/audio/<key>` 相对路径约定
2. `/audio/<key>` 映射到 `data/audio_cache/<key>` 物理路径
3. 下游 `download_file` 函数必须优先检测本地路径前缀（`/audio/`），命中则用 `shutil.copyfile` 直接拷贝
4. 禁止通过 httpx 自回路请求本机服务下载文件（性能损耗 + 死锁风险）
5. 路径前缀清单必须配置驱动：`local_storage.url_prefixes: ["/audio/"]`

**判断信号**：
- `download_file(url)` 函数无 `url.startswith('/audio/')` 分支 → 违规
- 本地文件访问使用 `httpx.get('http://localhost:*/audio/...')` 自回路请求 → 违规
- 文件路径硬编码绝对路径 → 违规

**示例**：

```python
# ❌ 反模式：自回路请求本机服务下载本地文件
async def download_file(url: str, dest: str) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)  # 如果 url 是 http://localhost:8000/audio/xxx，性能极差
        with open(dest, 'wb') as f:
            f.write(resp.content)

# ✅ 正确：优先检测本地前缀，命中则直接拷贝
import shutil
from pathlib import Path

async def download_file(url: str, dest: str) -> None:
    # 配置驱动的本地前缀清单
    for prefix_config in settings.LOCAL_PATH_PREFIXES:
        prefix = prefix_config['prefix']
        physical_dir = Path(prefix_config['physical_dir'])
        if url.startswith(prefix):
            # 本地文件直接拷贝，避免 httpx 自回路
            key = url[len(prefix):]
            src = physical_dir / key
            shutil.copyfile(str(src), dest)
            return
    # 远程文件走 httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        with open(dest, 'wb') as f:
            f.write(resp.content)
```

**配置驱动**：所有阈值通过 `project-config.json#local_path_url` 管理（url_prefixes/forbidden_patterns/required_prefix_detection）。

---

## 规范 60：三层测试验证规范

**所有代码变更必须通过单元测试 + 集成测试 + E2E 测试三层验证，外加 SonarQube 二次扫描回归。**

**为什么**：单层测试不足以保证质量。单元测试覆盖业务逻辑，集成测试验证 API 契约，E2E 测试验证用户流程，SonarQube 二次扫描验证代码质量。本次迭代通过完整三层测试 + SQ 回归，将 23 个问题降至 0 且 146 单元测试 + 12 E2E 测试全部 PASS。

**配置参数**（通过 `project-config.json#testing` 配置）：
```json
{
  "testing": {
    "min_unit_coverage": 0.70,
    "require_integration_test": true,
    "require_e2e_test": true,
    "e2e_p0_must_pass": true,
    "unit_test_command": "pytest --asyncio-mode=auto",
    "integration_test_command": "pytest tests/integration/",
    "e2e_test_command": "python scripts/with_server.py -- python e2e_test.py"
  }
}
```

**三层验证流程**：
1. **单元测试层**：`pytest --asyncio-mode=auto`，目标覆盖率 ≥ `min_unit_coverage`
   - 覆盖业务逻辑、工具函数、模型验证
   - 失败 → 阻塞发版
2. **集成测试层**：API 端点测试（FastAPI TestClient 或 httpx）
   - 覆盖所有 router 的关键端点
   - 失败 → 阻塞发版
3. **E2E 测试层**：Playwright 脚本
   - 覆盖关键用户流程（登录/页面遍历/API 调用）
   - 仅当 P0 用例失败时阻塞发版
4. **SonarQube 二次扫描**：验证修复未引入新问题
   - OPEN > 0 或有新问题 → 阻塞发版

**判断逻辑**：
- 单元测试失败 → 阻塞发版
- 集成测试失败 → 阻塞发版
- E2E 失败 → 仅当 P0 用例失败时阻塞发版
- SonarQube 二次扫描有新问题 → 阻塞发版

**适用场景**：中大型项目（≥10 个 API 端点）的发版前完整验证
**不适用场景**：热修复（hotfix）的快速验证、小型项目（<5 个端点）

---

## 规范 61-65：2026-07-21 跨项目模块迁移与测试执行复盘新增规范

> 以下规范来源于参考 17_xianyu 项目实现"关于/帮助"模块的完整复盘，对应 meta-rules.md 规范 86-90。所有阈值通过 `project-config.json#cross_project_migration`、`project-config.json#frontend_nested_paths`、`project-config.json#icon_migration`、`project-config.json#cache_test_isolation`、`project-config.json#python_env_test` 配置管理。

### 规范 61：跨项目模块迁移 7 步法

**参考式跨项目模块迁移必须完整执行 7 个步骤，禁止跳过任一步骤。**

**为什么**：跨项目迁移时，参考项目的架构、技术栈、约定可能与目标项目不一致。直接复制代码会导致路径错误、图标不存在、构建失败等问题。

**7 步流程**：
1. 需求确认 → 明确迁移目标、范围、验收标准
2. 架构对齐 → 对比目录结构、技术栈、依赖库、命名约定、路径风格
3. 后端开发 → 按目标项目分层架构（routers → services → models → core）实现
4. 前端开发 → 按目标项目目录结构实现，校验相对路径
5. 测试编写 → 编写单元测试（后端）+ 测试用例（前端）
6. 测试执行 → 运行 pytest + vite build，确保测试通过且构建成功
7. 构建验证 → 实际启动服务/打开页面验证功能可用

**配置参数**（通过 `project-config.json#cross_project_migration` 配置）：
```json
{
  "cross_project_migration": {
    "required_steps": ["requirement_confirm", "architecture_align", "backend_dev", "frontend_dev", "test_write", "test_execute", "build_verify"],
    "architecture_align_checklist": ["目录结构对齐", "技术栈对齐", "依赖库对齐", "命名约定对齐", "路径风格对齐"],
    "build_verify_required": true,
    "test_execute_required": true
  }
}
```

**判断信号**：跨项目迁移任务跳过架构对齐步骤；迁移后未执行 vite build / py_compile 验证
**适用场景**：所有参考式跨项目模块迁移
**不适用场景**：从零开发（无参考项目）、纯配置迁移（无代码）

### 规范 62：前端嵌套目录相对路径校验

**Vue 项目采用 `views/<module>/<Page>.vue` 嵌套目录结构时，SCSS `@use` 和 JS `import` 的相对路径必须按嵌套层级计算。**

**为什么**：扁平目录（views/Page.vue）用 `@use '../styles/'`，嵌套目录（views/about/About.vue）需用 `@use '../../styles/'`。照搬扁平目录路径会导致 vite build 报错。

**配置参数**（通过 `project-config.json#frontend_nested_paths` 配置）：
```json
{
  "frontend_nested_paths": {
    "nested_dir_pattern": "views/<module>/<Page>.vue",
    "parent_level_required": 2,
    "path_types_to_check": ["scss_use", "js_import", "ts_import", "vue_import"],
    "build_verify_required": true
  }
}
```

**正确做法**：
```vue
<!-- views/about/About.vue 嵌套目录 -->
<style lang="scss">
@use '../../styles/variables.scss' as *;  // 两级 ../
</style>
<script setup>
import { someUtil } from '../../utils/someUtil'  // 两级 ../
</script>
```

**判断信号**：grep `@use '\.\./styles/'` 在 `views/<module>/*.vue` 文件中（应为 `../../styles/`）
**适用场景**：所有 `views/<module>/<Page>.vue` 嵌套目录结构
**不适用场景**：扁平目录结构、绝对路径（@/）

### 规范 63：UI 图标跨库迁移存在性验证

**从参考项目迁移 UI 图标到目标项目时，必须验证图标在目标 UI 库中存在。**

**为什么**：React 图标库（lucide-react）与 Vue 图标库（@element-plus/icons-vue）覆盖范围差异较大，照搬图标名会导致 vite build 报错 "X is not exported by"。

**配置参数**（通过 `project-config.json#icon_migration` 配置）：
```json
{
  "icon_migration": {
    "target_icon_library": "@element-plus/icons-vue",
    "verify_command": "node -e \"const icons = require('@element-plus/icons-vue'); console.log(Object.keys(icons))\"",
    "fallback_icon": "MagicStick",
    "verify_before_build": true
  }
}
```

**正确做法**：
```javascript
// 迁移前先验证图标存在性
// node -e "const icons = require('@element-plus/icons-vue'); console.log(Object.keys(icons))"
import { MagicStick } from '@element-plus/icons-vue'  // Rocket 不存在，替换为 MagicStick
```

**判断信号**：grep `from '@element-plus/icons-vue'` 后跟参考项目特有图标名
**适用场景**：所有跨 UI 库图标迁移
**不适用场景**：同 UI 库内的图标调整、自定义 SVG 图标

### 规范 64：模块级单例缓存的测试隔离

**进程内模块级单例缓存的单元测试，必须通过 `_reset_cache_for_test()` 显式清理函数重置缓存。**

**为什么**：模块级单例在进程生命周期内只初始化一次，pytest 多个测试用例共享同一进程，前一个用例修改的缓存状态会影响后一个用例，导致测试结果与执行顺序相关。

**配置参数**（通过 `project-config.json#cache_test_isolation` 配置）：
```json
{
  "cache_test_isolation": {
    "require_reset_function": true,
    "reset_function_naming": "_reset_cache_for_test",
    "reset_in_fixture": true,
    "cache_types_to_reset": ["TTLCache", "dict_module_level", "lru_cache", "functools.cache"]
  }
}
```

**正确做法**：
```python
# app/core/cache.py
from cachetools import TTLCache
_cache: TTLCache = TTLCache(maxsize=100, ttl=300)

def _reset_cache_for_test() -> None:
    """测试专用：重置模块级缓存，确保用例间隔离。"""
    _cache.clear()

# tests/test_cache.py
@pytest.fixture(autouse=True)
def reset_cache():
    _reset_cache_for_test()
    yield
```

**判断信号**：测试用例依赖执行顺序；测试模块级单例的代码无 `_reset_cache_for_test()` 调用
**适用场景**：所有进程内缓存模块（TTLCache / dict 模块级单例 / lru_cache / functools.cache）
**不适用场景**：函数局部变量、数据库状态（用事务回滚隔离）

### 规范 65：多版本 Python 环境下的测试执行

**Windows + 多 Python 版本共存时，执行 pytest 必须显式指定 Python 解释器完整路径。**

**为什么**：Trae 内置 Python 可能优先于系统 Python，但其不含 pytest 等开发依赖。直接 `python -m pytest` 会报 `No module named pytest`，但 `python --version` 显示正常版本号，误导排查方向。

**配置参数**（通过 `project-config.json#python_env_test` 配置）：
```json
{
  "python_env_test": {
    "require_explicit_python_path": true,
    "system_python_path": "F:\\Program Files\\Python3.14\\python.exe",
    "required_test_deps": ["pytest", "pytest-asyncio", "aiosqlite"],
    "verify_command": "python -c \"import pytest; print(pytest.__version__)\""
  }
}
```

**正确做法**：
```powershell
# 显式指定系统 Python 完整路径
& "F:\Program Files\Python3.14\python.exe" -m pytest tests/ -v
# 先验证 pytest 已安装
& "F:\Program Files\Python3.14\python.exe" -c "import pytest; print(pytest.__version__)"
```

**判断信号**：`python -m pytest` 报 `No module named pytest` 但 `python --version` 正常
**适用场景**：Windows + 多 Python 版本共存环境
**不适用场景**：Linux/Mac 单版本 Python 环境、虚拟环境（venv 已激活）

---

## 规范 66-75：2026-07-21 综合复盘新增规范

> 以下规范来源于 2026-07-21 图片爬虫功能开发、工作流多步骤失败修复、P0/P1 改进实施、菜单分组功能开发、PWA 图标生成、监控告警、批量回填脚本等综合复盘，对应 meta-rules.md 规范 91-100。所有阈值通过 `project-config.json#image_crawl`、`project-config.json#workflow_orchestration`、`project-config.json#frontend_menu_grouping`、`project-config.json#pwa_icon_generation`、`project-config.json#monitoring_thresholds`、`project-config.json#backfill_script` 配置管理。

---

## 规范 66：图片封面三级 fallback 提取

**文章封面图提取必须实现 og:image → article <img> → 页面首个非装饰 <img> 三级 fallback，禁止仅依赖单一来源。**

**为什么**：文章封面图来源多样且不稳定。og:image 缺失（部分站点不设置 meta 标签）、article <img> 为空（部分文章纯图文混排无主图）、页面 <img> 含装饰图（logo/icon 等）。仅依赖单一来源会导致 30%+ 文章无封面，影响小程序展示效果。

**配置参数**（通过 `project-config.json#image_crawl` 配置）：
```json
{
  "image_crawl": {
    "fallback_chain": ["og_image", "article_img", "page_first_img"],
    "timeout_per_source_sec": 5,
    "min_image_size_bytes": 1024,
    "decorative_filter": {
      "url_keyword_blacklist": ["logo", "icon", "arrow", "btn", "button", "sprite", "placeholder"],
      "template_path_blacklist": ["/static/", "/assets/img/", "/images/common/"],
      "extension_blacklist": [".gif", ".svg"],
      "min_aspect_ratio": 0.3
    }
  }
}
```

**判断信号**：
- grep `og:image` 后无 `elif`/`try/except` fallback 逻辑
- grep 封面提取函数无 `fallback_chain` 配置读取
- 测试覆盖率：30%+ 文章无封面返回 None

**正确做法**：
```python
# ✅ 三级 fallback + 配置驱动 + 异常隔离
async def extract_cover_image(html: str, url: str) -> str | None:
    sources = settings.image_crawl.fallback_chain  # 从配置读取
    for source in sources:
        try:
            img_url = await asyncio.wait_for(
                _extract_from_source(source, html, url),
                timeout=settings.image_crawl.timeout_per_source_sec,
            )
            if img_url and await _validate_image_size(img_url):
                if not is_decorative_image(img_url):  # 规范 67
                    return img_url
        except Exception as e:
            logger.warning(f"Cover extraction via {source} failed: {e}")
            continue
    return None  # 全部失败返回 None，由上层降级处理
```

**错误做法**：
```python
# ❌ 仅依赖 og:image，无 fallback
def extract_cover_image(html: str) -> str | None:
    match = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
    return match.group(1) if match else None

# ❌ 无超时控制，单源卡住整体超时
async def extract_cover_image(html: str) -> str | None:
    return await _extract_og_image(html)  # 站点慢时整体卡死
```

**适用场景**：所有需要封面图的文章/新闻类业务
**不适用场景**：无图片需求的纯文本内容；用户主动上传封面的场景

---

## 规范 67：装饰图过滤规则

**封面图提取必须过滤装饰图（logo/icon/arrow 等 URL 关键词、特定站点模板路径、GIF 扩展名），禁止将装饰图作为封面。**

**为什么**：页面首个 <img> 常常是站点 logo、导航 icon、箭头装饰等，这些图作为封面会严重影响阅读体验。GIF 动图作为封面在 iOS 上不显示动效且体积过大。本次迭代未过滤时，小程序封面图 40% 是站点 logo。

**配置参数**（通过 `project-config.json#image_crawl.decorative_filter` 配置）：
```json
{
  "decorative_filter": {
    "url_keyword_blacklist": ["logo", "icon", "arrow", "btn", "button", "sprite", "placeholder"],
    "template_path_blacklist": ["/static/", "/assets/img/", "/images/common/"],
    "extension_blacklist": [".gif", ".svg"],
    "min_aspect_ratio": 0.3
  }
}
```

**判断信号**：
- grep `cover_url` 提取逻辑无装饰图过滤（无 keyword_blacklist 检查）
- 封面图列表中存在 logo/icon/arrow 等关键词
- 封面图为 GIF 格式

**正确做法**：
```python
# ✅ 多维度过滤（URL 关键词 + 模板路径 + 扩展名 + 宽高比）
def is_decorative_image(img_url: str) -> bool:
    cfg = settings.image_crawl.decorative_filter
    url_lower = img_url.lower()
    # URL 关键词过滤
    if any(kw in url_lower for kw in cfg.url_keyword_blacklist):
        return True
    # 模板路径过滤
    if any(path in url_lower for path in cfg.template_path_blacklist):
        return True
    # 扩展名过滤
    if any(url_lower.endswith(ext) for ext in cfg.extension_blacklist):
        return True
    return False
```

**错误做法**：
```python
# ❌ 直接取首个 <img> 不做过滤
def extract_first_img(html: str) -> str | None:
    match = re.search(r'<img[^>]+src="([^"]+)"', html)
    return match.group(1) if match else None  # 可能是 logo/icon

# ❌ 硬编码关键词，无法配置
DECORATIVE_KEYWORDS = ["logo", "icon"]  # 缺 arrow/btn/sprite 等
```

**适用场景**：所有图片提取场景（封面图、列表缩略图、OG 图）
**不适用场景**：用户主动上传的图片（无需过滤）；图标库素材站（图标本就是有效内容）

---

## 规范 68：FALLBACK_DAYS 动态计算

**素材回溯天数应根据频道入库天数动态计算（3/7/14 天三档），而非固定值。**

**为什么**：新频道入库天数 <3 天时，固定 7 天回溯会查到 0 条素材导致工作流失败；老频道入库天数 >30 天时，3 天回溯过短，无法覆盖节假日内容空窗。本次迭代固定 FALLBACK_DAYS=3 导致新频道首日 0 素材失败。

**配置参数**（通过 `project-config.json#workflow_orchestration.fallback_days_tiers` 配置）：
```json
{
  "workflow_orchestration": {
    "fallback_days_tiers": {
      "tiers": [
        {"max_channel_age_days": 3, "fallback_days": 1},
        {"max_channel_age_days": 14, "fallback_days": 3},
        {"max_channel_age_days": 9999, "fallback_days": 7}
      ],
      "default_tier_index": 1
    }
  }
}
```

**判断信号**：
- grep `FALLBACK_DAYS` 为硬编码数字（如 `FALLBACK_DAYS = 3`）
- grep 回溯逻辑无 `channel_created_at` 字段使用

**正确做法**：
```python
# ✅ 按频道入库天数动态计算
def calculate_fallback_days(channel_created_at: datetime) -> int:
    channel_age_days = (datetime.now() - channel_created_at).days
    tiers = settings.workflow_orchestration.fallback_days_tiers.tiers
    for tier in tiers:
        if channel_age_days <= tier["max_channel_age_days"]:
            return tier["fallback_days"]
    # 兜底：使用默认档位
    default_idx = settings.workflow_orchestration.fallback_days_tiers.default_tier_index
    return tiers[default_idx]["fallback_days"]
```

**错误做法**：
```python
# ❌ 硬编码固定值
FALLBACK_DAYS = 3  # 新频道首日不够 3 天，查不到素材

async def get_recent_materials(channel_id: int):
    since = datetime.now() - timedelta(days=FALLBACK_DAYS)
    return await db.execute(select(Material).where(Material.created_at >= since))

# ❌ 频道创建时间作为参数但未使用
def get_fallback_days(channel_created_at: datetime) -> int:
    return 7  # 参数被忽略
```

**适用场景**：多频道/多租户的素材回溯场景；新频道冷启动场景
**不适用场景**：单频道项目（无频道差异化需求）；无历史数据的全新项目

---

## 规范 69：LLM 语义过滤 fallback

**关键词过滤结果为 0 时必须降级到 LLM 语义过滤，LLM 失败时保留全部条目供 rewriter 二次筛选。**

**为什么**：关键词过滤依赖词表覆盖度，新话题/同义词/隐喻表达会全部漏掉。若过滤后 0 条直接报错，工作流中断。LLM 语义过滤能理解语义相似性，但仍可能失败（API 超时/限流）。最坏情况下保留全部条目让 rewriter 自行筛选，保证工作流不中断。本次迭代关键词过滤 0 条导致工作流失败 30 分钟。

**配置参数**（通过 `project-config.json#workflow_orchestration.llm_semantic_fallback` 配置）：
```json
{
  "workflow_orchestration": {
    "llm_semantic_fallback": {
      "trigger_when_keyword_result_zero": true,
      "llm_filter_batch_size": 10,
      "fallback_strategy_on_llm_failure": "keep_all",
      "llm_filter_timeout_sec": 30
    }
  }
}
```

**判断信号**：
- grep 关键词过滤后无 LLM fallback 分支（`if not filtered: raise` 无降级）
- grep LLM 过滤无 timeout 控制

**正确做法**：
```python
# ✅ 三级 fallback：关键词 → LLM 语义 → 保留全部
async def filter_materials(materials: list, keywords: list[str]) -> list:
    # 第一级：关键词过滤
    filtered = [m for m in materials if any(kw in m.title for kw in keywords)]
    if filtered:
        return filtered
    # 第二级：LLM 语义过滤
    cfg = settings.workflow_orchestration.llm_semantic_fallback
    try:
        return await asyncio.wait_for(
            _llm_semantic_filter(materials, keywords),
            timeout=cfg.llm_filter_timeout_sec,
        )
    except Exception as e:
        logger.warning(f"LLM semantic filter failed, keep all materials: {e}")
        # 第三级：保留全部条目
        return materials
```

**错误做法**：
```python
# ❌ 关键词过滤 0 条直接报错
async def filter_materials(materials: list, keywords: list[str]) -> list:
    filtered = [m for m in materials if any(kw in m.title for kw in keywords)]
    if not filtered:
        raise BusinessError("无匹配素材")  # 工作流中断
    return filtered

# ❌ LLM 失败时整体失败
try:
    filtered = await llm_filter(materials, keywords)
except Exception:
    raise  # 上层工作流直接失败
```

**适用场景**：所有基于关键词的内容过滤场景（素材筛选/文章分类/评论审核）
**不适用场景**：纯精确匹配场景（如 ID 过滤、SKU 过滤）；安全敏感场景（不能保留全部，必须严格过滤）

---

## 规范 70：LLM 字数达标约束

**LLM 生成内容必须达到目标字数的 70%，低于阈值触发硬约束重试；超过目标×1.20 时丢弃多余段（保留至少 3 主段+intro+outro）；低于目标×0.80 时追加最多 2 段。**

**为什么**：LLM 生成稿件字数偏差过大会导致音频时长异常（TTS 时长与字数正相关）。字数不足音频过短（小程序显示节目时长 <5 分钟用户体验差），字数超长音频过长（超出 10:30 上限触发切除丢内容）。本次迭代未约束时稿件字数从 800-3500 字波动，音频时长 4-15 分钟。

**配置参数**（通过 `project-config.json#workflow_orchestration.llm_word_count` 配置）：
```json
{
  "workflow_orchestration": {
    "llm_word_count": {
      "target_word_count": 1500,
      "min_achievement_ratio": 0.70,
      "trim_threshold_ratio": 1.20,
      "append_threshold_ratio": 0.80,
      "max_append_segments": 2,
      "min_main_segments": 3
    }
  }
}
```

**判断信号**：
- grep LLM 调用后无字数验证逻辑（无 `len(content)` / `word_count` 检查）
- grep 重试循环无字数 break 条件

**正确做法**：
```python
# ✅ 三段约束：硬重试 + 超长修剪 + 过短追加
async def generate_script_with_constraint(topic: str) -> str:
    cfg = settings.workflow_orchestration.llm_word_count
    target = cfg.target_word_count
    # 硬约束重试
    for attempt in range(3):
        content = await llm.generate(topic, target_words=target)
        actual = len(content)
        if actual >= target * cfg.min_achievement_ratio:
            break
        logger.warning(f"Word count {actual} < {target * cfg.min_achievement_ratio}, retry {attempt+1}")
    # 超长修剪
    if actual > target * cfg.trim_threshold_ratio:
        content = _trim_to_target(content, target, cfg.min_main_segments)
    # 过短追加
    elif actual < target * cfg.append_threshold_ratio:
        content = await _append_segments(content, topic, cfg.max_append_segments)
    return content
```

**错误做法**：
```python
# ❌ 无字数约束，LLM 生成什么用什么
async def generate_script(topic: str) -> str:
    return await llm.generate(topic)  # 字数可能 200 也可能 5000

# ❌ 仅重试不修剪/追加
for _ in range(3):
    content = await llm.generate(topic)
    if len(content) >= 1000:
        break
# 超长内容直接使用，TTS 时长溢出
```

**适用场景**：所有 LLM 生成内容场景（稿件/标题/摘要/口播文案）
**不适用场景**：自由创作场景（无字数要求）；结构化输出（如 JSON 数据）

---

## 规范 71：BGM 时长不足兜底

**视频拼接时 BGM 时长不足必须用 BGM 尾段扩展或静音降级，禁止直接报错。**

**为什么**：BGM 库素材时长固定（通常 3-5 分钟），但视频时长可能 6-10 分钟。BGM 短于视频时直接报错会导致整个工作流失败，用户体验断裂。本次迭代 BGM 4:30 视频 6:00 时报错失败。

**配置参数**（通过 `project-config.json#workflow_orchestration.bgm_fallback` 配置）：
```json
{
  "workflow_orchestration": {
    "bgm_fallback": {
      "extension_strategy": "tail_loop",
      "tail_loop_max_count": 2,
      "silence_fadeout_sec": 2
    }
  }
}
```

**判断信号**：
- grep BGM 拼接逻辑无时长不足处理（`if bgm_duration < video_duration: raise`）
- grep BGM 处理函数无 fallback 分支

**正确做法**：
```python
# ✅ 三级处理：正常裁剪 → 尾段扩展 → 静音降级
async def merge_bgm_with_video(bgm_path: str, video_path: str) -> str:
    bgm_duration = await get_audio_duration(bgm_path)
    video_duration = await get_video_duration(video_path)
    cfg = settings.workflow_orchestration.bgm_fallback

    if bgm_duration >= video_duration:
        # 正常裁剪
        return await _trim_bgm(bgm_path, video_duration)
    # 时长不足：尾段扩展
    extended_bgm = await _extend_bgm_tail_loop(
        bgm_path, video_duration, cfg.tail_loop_max_count
    )
    if extended_bgm:
        return extended_bgm
    # 兜底：静音降级
    logger.warning(
        f"BGM extend failed, fallback to silence for {video_duration - bgm_duration}s"
    )
    return await _pad_with_silence(bgm_path, video_duration, cfg.silence_fadeout_sec)
```

**错误做法**：
```python
# ❌ BGM 时长不足直接报错
async def merge_bgm(bgm_path: str, video_path: str) -> str:
    bgm_duration = await get_audio_duration(bgm_path)
    video_duration = await get_video_duration(video_path)
    if bgm_duration < video_duration:
        raise WorkflowError(f"BGM {bgm_duration}s < video {video_duration}s")  # 工作流中断
    return await _merge(bgm_path, video_path)

# ❌ 仅静音降级，无尾段扩展尝试
async def merge_bgm(bgm_path: str, video_path: str) -> str:
    if bgm_duration < video_duration:
        return await _pad_with_silence(bgm_path, video_duration)  # 跳过 tail_loop
```

**适用场景**：所有音频/视频拼接场景（BGM 配音/背景音乐/片头片尾）
**不适用场景**：无 BGM 的纯人声拼接；BGM 必须完整播放的场景（如音乐 MV）

---

## 规范 72：菜单分组与角色可见性

**管理后台菜单数量 ≥10 时必须按功能分组（el-sub-menu），通过 meta.group 字段配置分组，groupConfig 数组定义分组渲染，支持角色可见性控制（RBAC），启用 unique-opened 手风琴效果，路由变化时自动展开当前分组。**

**为什么**：菜单 ≥10 项时扁平列表视觉拥挤，用户查找困难。功能分组让相关菜单聚合（如"内容管理"含文章/评论/标签）。RBAC 让 operator 看不到"系统设置"等敏感菜单。unique-opened 避免多个分组同时展开挤占屏幕。本次迭代菜单从 8 项增加到 14 项后，扁平列表查找成本激增。

**配置参数**（通过 `project-config.json#frontend_menu_grouping` 配置）：
```json
{
  "frontend_menu_grouping": {
    "group_threshold": 10,
    "unique_opened": true,
    "auto_expand_on_route_change": true,
    "group_field": "meta.group",
    "default_visible_roles": ["admin"]
  }
}
```

**判断信号**：
- grep 菜单数量 ≥10 但无 `meta.group` 字段
- grep `<el-sub-menu` 无 `unique-opened` 属性
- grep 路由 watch 无 `activeGroup` / `expandGroup` 调用

**正确做法**：
```javascript
// ✅ router/routes.js - meta.group + roles
const routes = [
  {
    path: '/content',
    meta: { group: 'content', roles: ['admin', 'operator'] },
    component: ArticleList,
  },
  {
    path: '/system',
    meta: { group: 'system', roles: ['admin'] },  // 仅 admin 可见
    component: SystemConfig,
  },
]

// ✅ Layout.vue - el-sub-menu + unique-opened + 自动展开
<el-menu :unique-opened="groupConfig.unique_opened" @select="handleSelect">
  <el-sub-menu v-for="group in visibleGroups" :key="group.id" :index="group.id">
    <template #title>{{ group.title }}</template>
    <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
      {{ item.title }}
    </el-menu-item>
  </el-sub-menu>
</el-menu>

// 路由变化时自动展开当前分组
watch(() => route.path, (newPath) => {
  const group = findGroupByPath(newPath)
  if (group) activeGroup.value = group.id
})
```

**错误做法**：
```javascript
// ❌ 14 项菜单扁平渲染，无分组
<el-menu>
  <el-menu-item v-for="item in allMenus" :key="item.path" :index="item.path">
    {{ item.title }}
  </el-menu-item>
</el-menu>

// ❌ 多分组同时展开，挤占屏幕
<el-menu>  <!-- 缺少 unique-opened -->
  <el-sub-menu v-for="g in groups" :key="g.id" :index="g.id">...</el-sub-menu>
</el-menu>

// ❌ 路由跳转后菜单不自动展开当前分组
// 缺少 watch(() => route.path, ...) 逻辑
```

**适用场景**：所有管理后台菜单（≥10 项）；多角色权限系统
**不适用场景**：菜单数量 <10 的简单后台；无角色区分的内部工具

---

## 规范 73：PWA 图标生成与 MIME 注册

**PWA 应用图标必须同时生成 PNG（192/512）和 ICO（多尺寸 16/32/48），main.py 必须注册 `.ico` 的 MIME 类型（image/x-icon），manifest.json 必须声明 icons 数组含 maskable purpose。**

**为什么**：不同平台对图标格式要求不同——iOS Safari 仅识别 PNG 且需 apple-touch-icon；Windows 桌面 PWA 仅识别 ICO；Android Chrome 要求 maskable purpose 图标（自适应裁剪）。若 main.py 未注册 .ico MIME 类型，浏览器默认按 text/plain 解析导致图标 404/损坏。本次迭代 PWA 安装到 Windows 桌面后图标显示为白板。

**配置参数**（通过 `project-config.json#pwa_icon_generation` 配置）：
```json
{
  "pwa_icon_generation": {
    "png_sizes": [192, 512],
    "ico_sizes": [16, 32, 48],
    "ico_mime_type": "image/x-icon",
    "manifest_purposes": ["any", "maskable"],
    "source_icon_path": "assets/source-icon.png"
  }
}
```

**判断信号**：
- grep `manifest.json` 无 `maskable` purpose
- grep `main.py` 无 `mimetypes.add_type` for `.ico`
- grep icons 目录无 `.ico` 文件

**正确做法**：
```python
# ✅ main.py - 注册 .ico MIME 类型
import mimetypes
mimetypes.add_type(settings.pwa_icon_generation.ico_mime_type, ".ico")

app.mount("/icons", StaticFiles(directory="admin-web/dist/icons"), name="icons")
```

```json
// ✅ manifest.json - 含 maskable purpose 的 icons 数组
{
  "icons": [
    {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
    {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    {"src": "/icons/icon-192-maskable.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
    {"src": "/icons/icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    {"src": "/favicon.ico", "sizes": "16x16 32x32 48x48", "type": "image/x-icon"}
  ]
}
```

**错误做法**：
```python
# ❌ 未注册 .ico MIME 类型
# main.py
app.mount("/icons", StaticFiles(directory="dist/icons"))  # .ico 按 text/plain 返回

# ❌ manifest.json 无 maskable purpose
{
  "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"}]
}

# ❌ 仅生成 PNG，无 ICO（Windows 桌面 PWA 无图标）
```

**适用场景**：所有 PWA 应用（含 manifest.json 的 Web 应用）
**不适用场景**：非 PWA 的纯 SPA 应用（无离线能力要求）；原生应用（使用原生图标资源）

---

## 规范 74：关键指标监控告警

**关键业务指标（关键词命中率、LLM 字数达成率、TTS 成功率、工作流成功率）低于阈值时必须记录 WARNING 级别日志，阈值通过配置管理。**

**为什么**：关键指标下滑是系统健康度的领先指标。关键词命中率从 80% 降到 30% 意味着关键词表过期或 RSS 源失效；LLM 字数达成率低意味着 LLM 服务降级；TTS 成功率低意味着 TTS 服务故障或配额耗尽。仅记录 INFO 级别日志会被埋没，必须 WARNING 级别触发运维关注。本次迭代 TTS 成功率 50% 持续 2 小时未被发现。

**配置参数**（通过 `project-config.json#monitoring_thresholds` 配置）：
```json
{
  "monitoring_thresholds": {
    "keyword_hit_rate_min": 0.30,
    "llm_word_count_achievement_min": 0.70,
    "tts_success_rate_min": 0.80,
    "workflow_success_rate_min": 0.90,
    "alert_log_level": "WARNING"
  }
}
```

**判断信号**：
- grep 关键业务流程无 WARNING 阈值判断（无 `if rate < threshold: logger.warning`）
- grep 指标上报函数仅 `logger.info`，无 `logger.warning`

**正确做法**：
```python
# ✅ 四指标阈值告警 + WARNING 级别
async def report_workflow_metrics(metrics: dict) -> None:
    cfg = settings.monitoring_thresholds
    if metrics["keyword_hit_rate"] < cfg.keyword_hit_rate_min:
        logger.warning(
            f"Keyword hit rate {metrics['keyword_hit_rate']:.2%} "
            f"below threshold {cfg.keyword_hit_rate_min:.2%}"
        )
    if metrics["llm_word_count_achievement"] < cfg.llm_word_count_achievement_min:
        logger.warning(
            f"LLM word count achievement {metrics['llm_word_count_achievement']:.2%} "
            f"below threshold"
        )
    if metrics["tts_success_rate"] < cfg.tts_success_rate_min:
        logger.warning(
            f"TTS success rate {metrics['tts_success_rate']:.2%} below threshold"
        )
    if metrics["workflow_success_rate"] < cfg.workflow_success_rate_min:
        logger.warning(
            f"Workflow success rate {metrics['workflow_success_rate']:.2%} "
            f"below threshold"
        )
```

**错误做法**：
```python
# ❌ 关键指标仅记录 INFO，无 WARNING 阈值
async def report_metrics(metrics: dict):
    logger.info(f"keyword_hit_rate={metrics['keyword_hit_rate']}")  # 阈值下滑被埋没

# ❌ 硬编码阈值，无法配置
if metrics["tts_success_rate"] < 0.8:  # 应从配置读取
    logger.warning("TTS rate low")

# ❌ 仅告警部分指标，遗漏工作流成功率
if metrics["keyword_hit_rate"] < 0.3:
    logger.warning("Keyword rate low")
# 缺少 LLM/TTS/工作流成功率检查
```

**适用场景**：所有关键业务流程（工作流/LLM/TTS/爬虫/审核）
**不适用场景**：调试日志（DEBUG 级别）；非关键路径（如 UI 点击统计）；已对接 APM 系统（由 APM 告警）

---

## 规范 75：批量数据回填脚本规范

**新增 ORM 字段后必须编写批量回填脚本（backfill_*.py），脚本必须支持 dry_run 预览模式、分批处理（默认 100 条/批）、幂等执行（重复运行不报错）、进度输出。**

**为什么**：ORM 新增字段后，存量数据该字段为 NULL，业务代码读取 NULL 会报错或降级。回填脚本必须 dry_run 让运维预览影响范围；分批处理避免单次事务过大锁表；幂等执行保证重试安全（部分失败后重跑不报错）；进度输出便于长时间任务监控。本次迭代新增 `cover_url` 字段后无回填脚本，导致小程序 80% 文章无封面。

**配置参数**（通过 `project-config.json#backfill_script` 配置）：
```json
{
  "backfill_script": {
    "batch_size": 100,
    "dry_run_default": true,
    "progress_log_interval": 10,
    "idempotent_check_field": "updated_at",
    "script_naming_pattern": "backfill_{model}_{field}.py"
  }
}
```

**判断信号**：
- grep ORM 模型新增字段但无对应 `backfill_*.py` 脚本
- grep 回填脚本无 `--execute` / `dry_run` 参数
- grep 回填脚本无 `limit(batch_size)` 分批

**正确做法**：
```python
# ✅ backfill_material_cover_url.py - dry_run + 分批 + 幂等 + 进度
import argparse
from app.core.config import settings
from app.models.material import Material

async def backfill(dry_run: bool = None, batch_size: int = None):
    cfg = settings.backfill_script
    dry_run = cfg.dry_run_default if dry_run is None else dry_run
    batch_size = batch_size or cfg.batch_size

    total = await db.scalar(
        select(func.count(Material.id)).where(Material.cover_url.is_(None))
    )
    logger.info(f"Backfill {total} materials, dry_run={dry_run}, batch_size={batch_size}")

    offset = 0
    processed = 0
    while offset < total:
        # 幂等：仅查询 cover_url IS NULL 的记录
        batch = await db.execute(
            select(Material).where(Material.cover_url.is_(None))
            .limit(batch_size).offset(offset)
        )
        materials = batch.scalars().all()
        if dry_run:
            logger.info(f"[DRY-RUN] Would update {len(materials)} materials (offset={offset})")
        else:
            for m in materials:
                m.cover_url = await extract_cover_image(m.content, m.source_url)
            await db.commit()
        processed += len(materials)
        offset += batch_size
        if offset % (batch_size * cfg.progress_log_interval) == 0:
            logger.info(f"Progress: {processed}/{total} ({processed/total:.1%})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Real execute (default dry_run)")
    parser.add_argument("--batch-size", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(backfill(dry_run=not args.execute, batch_size=args.batch_size))
```

**错误做法**：
```python
# ❌ 一次性 UPDATE 全表，无 dry_run 无分批
async def backfill_cover_url():
    await db.execute(update(Material).values(cover_url=None))  # 锁表风险
    # 实际上没调用 extract_cover_image，字段仍为 NULL

# ❌ 无幂等检查，重复执行覆盖已回填数据
async def backfill_cover_url():
    materials = await db.execute(select(Material))  # 未过滤 cover_url IS NULL
    for m in materials.scalars():
        m.cover_url = await extract_cover_image(m.content, m.source_url)
    await db.commit()  # 已有 cover_url 的也被覆盖

# ❌ 无进度输出，长时间任务不可监控
async def backfill_cover_url():
    materials = await db.execute(select(Material).where(Material.cover_url.is_(None)))
    for m in materials.scalars():
        m.cover_url = await extract_cover_image(...)  # 不知进度
```

**适用场景**：所有 ORM 模型字段新增场景；数据迁移场景（字段类型变更/数据格式转换）
**不适用场景**：纯查询字段（computed property）；临时字段（一次性使用后删除）；少量数据（<100 条可直接事务处理）

---

## 规范 76：响应拦截器特殊响应类型处理

**响应拦截器必须先判断响应类型，对二进制响应类型（如 blob/arraybuffer）直接返回原始数据，不走统一 `{code, message, data}` 解构流程。**

**为什么**：项目统一响应格式为 `{code, message, data}`，前端 axios 响应拦截器默认按此结构解构 `response.data.data`。但二进制响应（文件下载、音频流、图片二进制）的 `response.data` 是 Blob/ArrayBuffer，无 `code` 字段。若拦截器先解构再判断，会因 `data.code` 为 undefined 触发错误提示，导致文件下载功能不可用。

**判断信号**：
- grep `responseType.*blob` 或 `responseType.*arraybuffer` 但拦截器无对应分支
- grep 拦截器 `response.data.code` 无前置 `responseType` 判断
- 文件下载接口返回 200 但前端报"业务错误"

**正确做法**：
```javascript
// ✅ 拦截器开头判断 responseType，二进制响应直接返回原始数据
axios.interceptors.response.use(
  (response) => {
    // 二进制响应类型不走统一解构，避免把 Blob 当作 {code,message,data} 解析
    if (response.config?.responseType === 'blob'
        || response.config?.responseType === 'arraybuffer') {
      return response.data
    }
    // 统一响应格式解构
    const { code, message, data } = response.data
    if (code === 0) {
      return data
    }
    ElMessage.error(message || '请求失败')
    return Promise.reject(new Error(message))
  }
)
```

**错误做法**：
```javascript
// ❌ 不判断 responseType，二进制响应被当作 JSON 解构
axios.interceptors.response.use((response) => {
  const { code, message, data } = response.data  // Blob 无 code 字段，触发错误
  if (code === 0) return data
  return Promise.reject(new Error(message))
})

// ❌ 判断顺序错误：先解构后判断
axios.interceptors.response.use((response) => {
  const { code, data } = response.data
  if (response.config?.responseType === 'blob') return data  // 已解构，data 是 undefined
  // ...
})
```

**适用场景**：文件下载、音频/视频流请求、图片二进制数据获取
**不适用场景**：JSON API 响应（统一走 `{code, message, data}` 解构）

---

## 规范 77：配置字段命名一致性

**配置字段在前后端字段名、路由层模型字段名、CONFIG_KEY_MAP 的 key、Settings 属性名之间必须保持一致或通过明确的映射关系连接，四端必须同步。**

**为什么**：项目使用 SQLite 持久化配置 + Settings 单例热生效模式。多 Provider 场景下（如 TTS 多服务商），前端字段名、后端路由 Body 字段名、CONFIG_KEY_MAP 的 key 三者必须一致；Settings 属性名虽为全大写下划线（Python 规范），但通过 CONFIG_KEY_MAP 映射后必须能正确写入。任一端命名不一致会导致前端保存的值在服务端读取时被静默忽略，配置无法生效。

**判断逻辑**：
- `config_key`（前端字段名）= 全小写下划线（如 `edge_voice`）
- `Settings 属性名` = 全大写下划线（如 `EDGE_TTS_VOICE`）
- `CONFIG_KEY_MAP` 映射 `config_key` → `Settings 属性名`
- 前端表单字段、路由层 Body 字段、CONFIG_KEY_MAP 的 key 三者必须完全一致
- Settings 属性名通过 CONFIG_KEY_MAP 的 value 映射，可独立命名

**判断信号**：
- grep `CONFIG_KEY_MAP` 中同一业务域出现多种前缀风格（如 `edge_*` 与 `edge_tts_*` 混用）
- grep 路由 Body 模型字段名与 CONFIG_KEY_MAP 的 key 不一致
- grep 前端表单 `v-model` 字段名与路由 Body 字段名不一致

**正确做法**：
```python
# ✅ 四端命名一致（前端/路由/CONFIG_KEY_MAP 的 key 用逑名，Settings 用大写）
# 前端表单：form.edge_voice
# 路由 Body 模型：edge_voice: str = ""
# CONFIG_KEY_MAP 的 key：edge_voice
# Settings 属性名：EDGE_TTS_VOICE（通过 CONFIG_KEY_MAP 的 value 映射）

CONFIG_KEY_MAP = {
    "edge_voice": "EDGE_TTS_VOICE",
    "edge_rate": "EDGE_TTS_RATE",
    "edge_volume": "EDGE_TTS_VOLUME",
    # 兼容旧键名（LEGACY_KEY_MAP 单独维护，不混入主映射）
}

# 读取时优先新键，fallback 到旧键
def _get(key: str, settings_attr: str, default: str = "",
         legacy_keys: tuple[str, ...] = ()) -> str:
    for candidate in (key, *legacy_keys):
        val = raw.get(candidate)
        if val is not None:
            return val
    return str(getattr(settings, settings_attr, default))
```

**错误做法**：
```python
# ❌ 同一业务域混用多种前缀风格
CONFIG_KEY_MAP = {
    "edge_voice": "EDGE_TTS_VOICE",       # edge_ 前缀
    "edge_tts_rate": "EDGE_TTS_RATE",     # edge_tts_ 前缀（混用）
    "edge_volume": "EDGE_TTS_VOLUME",     # edge_ 前缀
}
# 前端保存 edge_rate，但 CONFIG_KEY_MAP 中是 edge_tts_rate，配置无法生效
```

**规则**：
- 新增配置项时，前端表单字段、路由 Body 字段、CONFIG_KEY_MAP 的 key 三者必须同步
- 同一业务域（如同一 Provider）的 config_key 必须使用统一前缀风格
- Settings 属性名通过 CONFIG_KEY_MAP 的 value 映射，可独立命名（Python 大写规范）
- 旧键名兼容通过 LEGACY_KEY_MAP 单独维护，不混入主映射
- 字段变更时必须保留旧键名的兼容读取（legacy_keys fallback）

**适用场景**：多 Provider 配置管理、全链路字段传递、SQLite 持久化配置热生效
**不适用场景**：内部变量名（无前后端传递需求）、临时配置（一次性使用）

---

## 规范 78：时区一致性

**生产代码统一使用 `utcnow_naive()`（本地时间 naive datetime），测试代码必须用 `datetime.now()`，禁止测试用 `datetime.utcnow()`（UTC）与本地时间混用。**

**为什么**：项目为单机部署（香港时区 UTC+8），所有时间字段存储为本地 naive datetime（无时区信息）。`utcnow_naive()` 是项目封装的本地时间获取函数，与 `datetime.now()` 行为一致。但测试中如果用 `datetime.utcnow()`（UTC 时间），与生产代码的本地时间会有 8 小时偏差，导致时间比较断言失败或时间窗口判断错误。

**判断逻辑**：
- 生产代码：统一用 `utcnow_naive()` 获取当前时间（本地 naive）
- 测试代码：必须用 `datetime.now()` 获取当前时间（本地 naive）
- 禁止测试用 `datetime.utcnow()`（UTC 时间）与生产代码的本地时间比较
- 所有时间字段存储为本地 naive datetime，不存储 UTC 时间

**判断信号**：
- grep 测试代码中 `datetime.utcnow()` 与生产代码 `utcnow_naive()` 混用
- grep 测试代码中 `datetime.utcnow()` 用于时间比较断言
- 测试时间比较失败，偏差恰好为 8 小时（UTC+8 时区差）

**正确做法**：
```python
# ✅ 生产代码：统一用 utcnow_naive()（本地 naive）
from app.core.timeutil import utcnow_naive

async def create_record(db: AsyncSession):
    record = Workflow(
        started_at=utcnow_naive(),  # 本地时间 naive
        # ...
    )

# ✅ 测试代码：用 datetime.now()（本地 naive，与生产一致）
from datetime import datetime

async def test_workflow_time_window():
    # 测试时间窗口判断逻辑
    now = datetime.now()  # 本地时间 naive，与 utcnow_naive() 行为一致
    record = await create_record(db)
    assert record.started_at <= now + timedelta(seconds=1)
```

**错误做法**：
```python
# ❌ 测试用 datetime.utcnow()，与生产代码 utcnow_naive() 偏差 8 小时
from datetime import datetime

async def test_workflow_time_window():
    now = datetime.utcnow()  # UTC 时间，比本地时间晚 8 小时
    record = await create_record(db)  # started_at 用 utcnow_naive()（本地）
    # 断言会失败：record.started_at（本地）> now（UTC）+ 1秒
    assert record.started_at <= now + timedelta(seconds=1)

# ❌ 生产代码混用 utcnow_naive() 和 datetime.utcnow()
async def create_record(db: AsyncSession):
    record = Workflow(
        started_at=utcnow_naive(),        # 本地时间
        completed_at=datetime.utcnow(),   # UTC 时间（混用！）
    )
```

**规则**：
- 生产代码统一用 `utcnow_naive()` 获取当前时间
- 测试代码统一用 `datetime.now()` 获取当前时间（与 `utcnow_naive()` 行为一致）
- 禁止测试用 `datetime.utcnow()` 与本地时间比较
- 所有时间字段存储为本地 naive datetime，不存储 UTC 时间
- 单机部署（香港时区 UTC+8），无需考虑跨时区场景

**适用场景**：所有涉及时间计算/比较的测试、所有时间字段存储场景
**不适用场景**：明确需要存储 UTC 时间的场景（如跨时区分布式系统）
