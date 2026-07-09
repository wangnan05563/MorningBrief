# 前端开发指南

本文档面向 20_News 项目前端开发，涵盖 Vue 3（运营后台）和微信小程序的开发实践。

## 1. Vue 3 开发规范

### <script setup> 语法

**为什么使用 `<script setup>`**：
- 代码更简洁，无需 return
- 更好的 TypeScript 类型推导
- 编译优化更好

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { NewsItem } from '@/types'

// Props 定义（编译时宏）
const props = defineProps<{
  categoryId: string
  showActions?: boolean
}>()

// Emits 定义（编译时宏）
const emit = defineEmits<{
  select: [item: NewsItem]
  'update:visible': [value: boolean]
}>()

// 响应式状态
const loading = ref(false)
const newsList = ref<NewsItem[]>([])

// 计算属性
const displayedCount = computed(() => newsList.value.length)

// 方法
const handleSelect = (item: NewsItem) => {
  emit('select', item)
}

// 生命周期
onMounted(async () => {
  await fetchNews()
})

const fetchNews = async () => {
  loading.value = true
  try {
    newsList.value = await api.getNewsList(props.categoryId)
  } finally {
    loading.value = false
  }
}
</script>
```

### Props 验证

**为什么显式定义 Props 类型**：编译时检查类型错误，避免运行时 bug。

```typescript
const props = defineProps<{
  // 必填
  categoryId: string
  // 可选，带默认值
  pageSize?: number
  // 可选布尔
  loading?: boolean
}>()
```

### 响应式陷阱

```typescript
// 陷阱 1：给 ref 赋值新对象（丢失响应式）
let list = ref<Item[]>([])
list = newItemList  // 错误！

// 正确：修改 .value
list.value = newItemList

// 陷阱 2：解构 ref 丢失响应式
const { count } = state  // count 不再是响应式的

// 正确：使用 computed
const count = computed(() => state.count)

// 陷阱 3：深层对象修改不触发更新
state.user.name = 'new'  // 可能不触发

// 正确：使用 reactive 或 $set
const state = reactive({ user: { name: '' } })
state.user.name = 'new'  // reactive 会自动追踪
```

## 2. Element Plus 使用

### 表单

```vue
<template>
  <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
    <el-form-item label="标题" prop="title">
      <el-input v-model="form.title" placeholder="请输入标题" />
    </el-form-item>
    
    <el-form-item label="分类" prop="categoryId">
      <el-select v-model="form.categoryId" placeholder="请选择分类">
        <el-option
          v-for="cat in categories"
          :key="cat.id"
          :label="cat.name"
          :value="cat.id"
        />
      </el-select>
    </el-form-item>
    
    <el-form-item>
      <el-button type="primary" @click="handleSubmit">提交</el-button>
      <el-button @click="handleReset">重置</el-button>
    </el-form-item>
  </el-form>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'

const formRef = ref<FormInstance>()

const form = reactive({
  title: '',
  categoryId: '',
})

const rules: FormRules = {
  title: [
    { required: true, message: '请输入标题', trigger: 'blur' },
    { min: 2, max: 200, message: '长度在 2 到 200 个字符', trigger: 'blur' },
  ],
  categoryId: [
    { required: true, message: '请选择分类', trigger: 'change' },
  ],
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate()
  // 表单验证通过，提交数据
  await api.createNews(form)
  ElMessage.success('创建成功')
}

const handleReset = () => {
  formRef.value?.resetFields()
}
</script>
```

### 表格

```vue
<template>
  <el-table :data="tableData" v-loading="loading" stripe>
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="title" label="标题" show-overflow-tooltip />
    <el-table-column prop="status" label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="getStatusType(row.status)">
          {{ getStatusLabel(row.status) }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="200">
      <template #default="{ row }">
        <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
        <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
  
  <el-pagination
    v-model:current-page="pagination.current"
    v-model:page-size="pagination.pageSize"
    :total="pagination.total"
    :page-sizes="[10, 20, 50, 100]"
    layout="total, sizes, prev, pager, next"
    @size-change="fetchData"
    @current-change="fetchData"
  />
</template>
```

### 对话框

```vue
<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="600px"
    :close-on-click-modal="false"
    @close="handleDialogClose"
  >
    <el-form :model="form" :rules="rules" ref="formRef">
      <!-- 表单内容 -->
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        确定
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const dialogVisible = ref(false)
const submitting = ref(false)

const dialogTitle = computed(() => form.id ? '编辑' : '新建')

const showDialog = (item?: NewsItem) => {
  if (item) {
    Object.assign(form, item)
  } else {
    resetForm()
  }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  submitting.value = true
  try {
    if (form.id) {
      await api.updateNews(form.id, form)
    } else {
      await api.createNews(form)
    }
    dialogVisible.value = false
    fetchData()
  } finally {
    submitting.value = false
  }
}
</script>
```

### 标签（Tag）

```typescript
const statusMap: Record<string, { type: 'success' | 'warning' | 'danger' | 'info', label: string }> = {
  pending: { type: 'warning', label: '待审核' },
  approved: { type: 'success', label: '已通过' },
  rejected: { type: 'danger', label: '已拒绝' },
}

const getStatusType = (status: string) => statusMap[status]?.type ?? 'info'
const getStatusLabel = (status: string) => statusMap[status]?.label ?? status
```

## 3. Pinia 状态管理

### Store 定义

```typescript
// stores/news.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { NewsItem } from '@/types'
import * as api from '@/api/news'

export const useNewsStore = defineStore('news', () => {
  // State
  const newsList = ref<NewsItem[]>([])
  const currentNews = ref<NewsItem | null>(null)
  const loading = ref(false)
  const pagination = ref({
    current: 1,
    pageSize: 20,
    total: 0,
  })

  // Getters
  const hasMore = computed(() => {
    return pagination.value.current * pagination.value.pageSize < pagination.value.total
  })

  // Actions
  async function fetchList(categoryId?: string) {
    loading.value = true
    try {
      const res = await api.getNewsList({
        page: pagination.value.current,
        page_size: pagination.value.pageSize,
        category: categoryId,
      })
      newsList.value = res.data.items
      pagination.value.total = res.data.total
    } finally {
      loading.value = false
    }
  }

  async function fetchDetail(id: number) {
    loading.value = true
    try {
      const res = await api.getNewsDetail(id)
      currentNews.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function createNews(data: NewsCreate) {
    await api.createNews(data)
    await fetchList()
  }

  // 重置分页
  function resetPagination() {
    pagination.value.current = 1
    pagination.value.pageSize = 20
  }

  return {
    newsList,
    currentNews,
    loading,
    pagination,
    hasMore,
    fetchList,
    fetchDetail,
    createNews,
    resetPagination,
  }
})
```

### Store 使用

```vue
<script setup lang="ts">
import { useNewsStore } from '@/stores/news'

const newsStore = useNewsStore()

// 直接访问 state
console.log(newsStore.newsList)

// 调用 action
newsStore.fetchList('tech')

// 计算属性
console.log(newsStore.hasMore)
</script>
```

## 4. API 调用规范

### Axios 配置

```typescript
// utils/request.ts
import axios from 'axios'
import type { AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器
request.interceptors.response.use(
  (response: AxiosResponse) => {
    const { code, message, data } = response.data
    if (code === 0) {
      return { code, message, data }
    }
    ElMessage.error(message || '请求失败')
    return Promise.reject(new Error(message))
  },
  (error) => {
    if (error.response?.status === 401) {
      // 跳转登录
      window.location.href = '/login'
    }
    ElMessage.error(error.response?.data?.message || '网络错误')
    return Promise.reject(error)
  }
)

export default request
```

### API 模块

```typescript
// api/news.ts
import request from '@/utils/request'
import type { NewsItem, NewsCreate, NewsUpdate } from '@/types'

export function getNewsList(params: {
  page: number
  page_size: number
  category?: string
}) {
  return request.get<{ items: NewsItem[]; total: number }>('/news/', { params })
}

export function getNewsDetail(id: number) {
  return request.get<NewsItem>(`/news/${id}`)
}

export function createNews(data: NewsCreate) {
  return request.post('/news/', data)
}

export function updateNews(id: number, data: NewsUpdate) {
  return request.put(`/news/${id}`, data)
}

export function deleteNews(id: number) {
  return request.delete(`/news/${id}`)
}
```

## 5. 路由设计

### 路由配置

```typescript
// router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/news',
    children: [
      {
        path: 'news',
        name: 'NewsList',
        component: () => import('@/views/news/index.vue'),
        meta: { title: '新闻管理' },
      },
      {
        path: 'news/:id',
        name: 'NewsDetail',
        component: () => import('@/views/news/detail.vue'),
        meta: { title: '新闻详情' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
  } else if (to.name === 'Login' && token) {
    next({ path: '/' })
  } else {
    next()
  }
})

export default router
```

**为什么使用懒加载**：减小首屏打包体积，提升加载速度。

## 6. 小程序开发

### 页面生命周期

```javascript
// pages/news/detail.js
Page({
  data: {
    news: null,
    loading: true,
  },

  onLoad(options) {
    // 页面加载，获取 ID 参数
    const newsId = options.id
    this.loadNews(newsId)
  },

  onShow() {
    // 页面显示，刷新数据
    if (this.data.news) {
      this.updatePlaybackStatus()
    }
  },

  onHide() {
    // 页面隐藏，暂停音频
    this.pauseAudio()
  },

  onUnload() {
    // 页面卸载，清理资源
    this.cleanupAudio()
  },

  async loadNews(newsId) {
    this.setData({ loading: true })
    try {
      const res = await wx.cloud.callFunction({
        name: 'getNews',
        data: { id: newsId }
      })
      this.setData({ news: res.result })
    } finally {
      this.setData({ loading: false })
    }
  },
})
```

### 全局状态

```javascript
// app.js
App({
  globalData: {
    userInfo: null,
    token: '',
  },

  // 设置 token
  setToken(token) {
    this.globalData.token = token
    wx.setStorageSync('token', token)
  },

  // 获取 token
  getToken() {
    if (!this.globalData.token) {
      this.globalData.token = wx.getStorageSync('token')
    }
    return this.globalData.token
  },

  // 清除 token
  logout() {
    this.globalData.token = ''
    this.globalData.userInfo = null
    wx.removeStorageSync('token')
    wx.removeStorageSync('userInfo')
  },
})
```

### 音频管理

```javascript
// 使用背景音频管理器支持后台播放
const audioManager = wx.getBackgroundAudioManager()

audioManager.title = '新闻播报'
audioManager.epname = '20_News'
audioManager.singer = 'AI主播'

audioManager.onPlay(() => {
  console.log('开始播放')
  this.setData({ isPlaying: true })
})

audioManager.onPause(() => {
  console.log('暂停播放')
  this.setData({ isPlaying: false })
})

audioManager.onStop(() => {
  console.log('停止播放')
  this.setData({ isPlaying: false })
})

audioManager.onEnded(() => {
  console.log('播放结束')
  this.setData({ isPlaying: false })
})

// 播放
playAudio(url) {
  audioManager.src = url
  audioManager.play()
}

// 暂停
pauseAudio() {
  audioManager.pause()
}
```

## 7. 前后端字段契约

### 字段映射

**为什么需要映射**：后端使用 snake_case（数据库风格），前端使用 camelCase（JavaScript 风格）。

```typescript
// 后端返回
{
  "news_id": 1,
  "title": "新闻标题",
  "created_at": "2026-07-10T12:00:00Z",
  "status": "approved"
}

// 前端使用（手动转换或使用映射函数）
const transformResponse = (data) => ({
  newsId: data.news_id,
  title: data.title,
  createdAt: data.created_at,
  status: data.status,
})
```

### Enum 处理

**为什么始终传输 .value**：枚举名是 Python 内部概念，前端无法解析。

```typescript
// 后端
NewsStatus.PENDING.value  // "pending"

// 前端
const statusLabels = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已拒绝',
}
```

### 日期格式

**为什么统一 ISO8601**：时区明确，解析可靠。

```typescript
// 后端输出
"2026-07-10T12:00:00Z"  // UTC

// 前端展示
new Date('2026-07-10T12:00:00Z').toLocaleString('zh-CN')
// "2026/7/10 20:00:00" (自动转北京时间)
```

## 8. 性能优化

### 路由懒加载

```typescript
// 已在使用（见第 5 节路由配置）
component: () => import('@/views/news/index.vue')
```

### 列表虚拟滚动

**为什么**：长列表渲染大量 DOM 节点会导致页面卡顿。

```vue
<el-virtual-list
  height="600"
  :data="longList"
  :item-size="50"
>
  <template #default="{ item }">
    <div class="list-item">{{ item.title }}</div>
  </template>
</el-virtual-list>
```

### 图片懒加载

**为什么**：首屏不需要加载所有图片，延迟加载提升首屏速度。

```vue
<el-image
  v-lazy="imageUrl"
  :preview-src-list="[imageUrl]"
  fit="cover"
>
  <template #placeholder>
    <div class="image-placeholder">加载中...</div>
  </template>
</el-image>
```

### 组件按需引入

**为什么**：减少打包体积。

```typescript
// 不推荐：全量引入
import ElementPlus from 'element-plus'
app.use(ElementPlus)

// 推荐：按需引入
import { ElButton, ElTable } from 'element-plus'
app.component('ElButton', ElButton)
app.component('ElTable', ElTable)
```
