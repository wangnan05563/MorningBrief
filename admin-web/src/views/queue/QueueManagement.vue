<template>
  <div class="page-container queue-management">
    <!-- 顶部统计卡片：4 种状态计数，左边框色区分 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-queued">
          <div class="stat-label">等待中</div>
          <div class="stat-value">{{ stats.queued || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-running">
          <div class="stat-label">执行中</div>
          <div class="stat-value">{{ stats.running || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-success">
          <div class="stat-label">已完成</div>
          <div class="stat-value">{{ stats.success || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-failed">
          <div class="stat-label">失败</div>
          <div class="stat-value">{{ stats.failed || 0 }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 配置面板：模式 + 并发数（仅并行模式显示） -->
    <el-card shadow="never" class="config-panel glass">
      <div class="config-row">
        <span class="config-label">执行模式</span>
        <el-radio-group v-model="config.mode">
          <el-radio value="serial">串行</el-radio>
          <el-radio value="parallel">并行</el-radio>
        </el-radio-group>
        <template v-if="config.mode === 'parallel'">
          <span class="config-label">并发数</span>
          <el-slider v-model="config.concurrency" :min="1" :max="5" class="concurrency-slider" />
          <span class="config-value">{{ config.concurrency }}</span>
        </template>
        <el-button type="primary" :loading="savingConfig" @click="saveConfig">保存配置</el-button>
      </div>
    </el-card>

    <!-- 筛选区 -->
    <el-card shadow="never" class="filter-panel">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-select
            v-model="filter.status"
            placeholder="状态筛选"
            clearable
            style="width: 100%"
            @change="handleFilterChange"
          >
            <el-option label="等待中" value="queued" />
            <el-option label="执行中" value="running" />
            <el-option label="已完成" value="success" />
            <el-option label="失败" value="failed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-select
            v-model="filter.channel_id"
            placeholder="频道筛选"
            clearable
            style="width: 100%"
            @change="handleFilterChange"
          >
            <el-option v-for="c in channels" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-select
            v-model="filter.priority"
            placeholder="优先级筛选"
            clearable
            style="width: 100%"
            @change="handleFilterChange"
          >
            <el-option v-for="p in 10" :key="p" :label="`优先级 ${p}`" :value="p" />
          </el-select>
        </el-col>
      </el-row>
    </el-card>

    <!-- 任务表格 -->
    <el-card shadow="never">
      <el-table :data="tasks" v-loading="loading" stripe>
        <el-table-column prop="channel_name" label="频道" min-width="120" />
        <el-table-column prop="priority" label="优先级" width="90" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" min-width="170">
          <template #default="{ row }">{{ row.started_at || '-' }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="120">
          <template #default="{ row }">{{ formatDuration(row) }}</template>
        </el-table-column>
        <!-- 操作列：admin 可执行取消/改优先级/重试，operator 只能查看详情 -->
        <el-table-column v-if="canOperate" label="操作" width="300">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'queued'"
              size="small"
              type="danger"
              :loading="cancelingIds.has(row.id)"
              @click="handleCancel(row.id)"
            >
              取消
            </el-button>
            <el-popover trigger="click" width="240" placement="top" @show="editingPriority = row.priority">
              <template #reference>
                <el-button size="small" type="warning" :loading="priorityIds.has(row.id)">改优先级</el-button>
              </template>
              <div class="priority-popover">
                <el-input-number v-model="editingPriority" :min="1" :max="10" />
                <el-button size="small" type="primary" :loading="priorityIds.has(row.id)" @click="handlePriority(row)">确定</el-button>
              </div>
            </el-popover>
            <el-button
              v-if="row.status === 'failed'"
              size="small"
              type="primary"
              :loading="retryingIds.has(row.id)"
              @click="handleRetry(row.id)"
            >
              重试
            </el-button>
            <el-button size="small" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
        <el-table-column v-else label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadTasks"
          @current-change="loadTasks"
        />
      </div>
    </el-card>

    <!-- 详情抽屉：展示任务基本信息 + 步骤时间线 -->
    <el-drawer v-model="detailVisible" title="任务详情" size="480px">
      <template v-if="currentTask">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="任务 ID">{{ currentTask.id }}</el-descriptions-item>
          <el-descriptions-item label="频道">{{ currentTask.channel_name }}</el-descriptions-item>
          <el-descriptions-item label="优先级">{{ currentTask.priority }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(currentTask.status)">{{ statusLabel(currentTask.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ currentTask.started_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ currentTask.finished_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatDuration(currentTask) }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="steps-title">步骤时间线</h4>
        <el-timeline v-if="currentTask.steps && currentTask.steps.length">
          <el-timeline-item
            v-for="(step, i) in currentTask.steps"
            :key="i"
            :timestamp="step.finished_at || step.started_at || ''"
            :type="stepStatusType(step.status)"
          >
            <div class="step-name">{{ step.name }}</div>
            <div class="step-status">
              <el-tag size="small" :type="stepStatusType(step.status)">{{ statusLabel(step.status) }}</el-tag>
            </div>
            <div v-if="step.started_at" class="step-time">
              {{ step.started_at }} ~ {{ step.finished_at || '进行中' }}
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无步骤数据" />
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
defineOptions({ name: 'QueueManagement' })
import { ref, reactive, onMounted, onUnmounted, onActivated, onDeactivated } from 'vue'
import { ElMessage, ElMessageBox } from '../../utils/message'
import {
  getQueueStats,
  listQueueTasks,
  cancelTask,
  updatePriority,
  retryTask,
  getQueueConfig,
  updateQueueConfig,
} from '../../api/queue'
import { listChannels } from '../../api/channels'
import { subscribe } from '../../utils/sse'

// 角色控制：直接读 localStorage，operator 隐藏操作按钮
const role = localStorage.getItem('admin_role') || ''
const canOperate = role === 'admin'

// 状态到 el-tag 类型映射（保持与 UI 语义一致）
const STATUS_TAG_MAP = {
  queued: 'warning',
  running: 'primary',
  success: 'success',
  failed: 'danger',
  cancelled: 'info',
}
const STATUS_LABEL_MAP = {
  queued: '等待中',
  running: '执行中',
  success: '已完成',
  failed: '失败',
  cancelled: '已取消',
}
function statusTagType(s) {
  return STATUS_TAG_MAP[s] || 'info'
}
function statusLabel(s) {
  return STATUS_LABEL_MAP[s] || s
}
function stepStatusType(s) {
  return STATUS_TAG_MAP[s] || 'info'
}

// 统计数据
const stats = ref({})
// 配置（串行/并行 + 并发数）
const config = reactive({ mode: 'serial', concurrency: 1 })
const savingConfig = ref(false)
// 筛选条件
const filter = reactive({ status: '', channel_id: '', priority: '' })
// 频道列表（供筛选下拉使用）
const channels = ref([])
// 任务列表
const tasks = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)

// 详情抽屉
const detailVisible = ref(false)
const currentTask = ref(null)

// 改优先级 popover 的临时编辑值（单例，show 时初始化为当前行优先级）
const editingPriority = ref(1)

// 行级按钮 loading 状态（P1-2.2 防重复点击）
// 用 Set 而非单个 ref，因为表格中多个按钮可能同时操作不同行
const cancelingIds = ref(new Set())
const priorityIds = ref(new Set())
const retryingIds = ref(new Set())

// 轮询定时器
let pollTimer = null

// 耗时计算：已完成用 finished-started，未完成用 now-started
function formatDuration(task) {
  if (!task.started_at) return '-'
  const start = new Date(task.started_at).getTime()
  if (Number.isNaN(start)) return '-'
  const end = task.finished_at ? new Date(task.finished_at).getTime() : Date.now()
  if (Number.isNaN(end)) return '-'
  const ms = Math.max(0, end - start)
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rs = s % 60
  if (m < 60) return `${m}m ${rs}s`
  const h = Math.floor(m / 60)
  const rm = m % 60
  return `${h}h ${rm}m`
}

// 是否存在活动任务（决定轮询频率）
function hasActiveTasks() {
  return tasks.value.some((t) => t.status === 'queued' || t.status === 'running')
}

async function loadStats() {
  try {
    stats.value = await getQueueStats()
  } catch {
    // 统计仅辅助展示，静默失败避免淹没真实错误
  }
}

async function loadConfig() {
  try {
    const data = await getQueueConfig()
    // 后端字段为 execution_mode / max_concurrent，对齐 SRS 5.1 API 规范
    config.mode = data.execution_mode || 'serial'
    config.concurrency = data.max_concurrent || 1
  } catch {
    // 配置加载失败时使用默认值，不阻塞页面
  }
}

async function saveConfig() {
  savingConfig.value = true
  try {
    // 后端字段为 execution_mode / max_concurrent，串行模式并发数无意义统一传 1
    await updateQueueConfig({
      execution_mode: config.mode,
      max_concurrent: config.mode === 'parallel' ? config.concurrency : 1,
    })
    ElMessage.success('配置已保存')
  } finally {
    savingConfig.value = false
  }
}

async function loadChannels() {
  try {
    const data = await listChannels(false)
    // 兼容后端返回数组或 { list } 两种结构
    channels.value = Array.isArray(data) ? data : (data.list || [])
  } catch {
    // 频道列表仅用于筛选，失败时不影响主表格
  }
}

async function loadTasks() {
  loading.value = true
  try {
    const params = { page: page.value, size: size.value }
    if (filter.status) params.status = filter.status
    if (filter.channel_id) params.channel_id = filter.channel_id
    if (filter.priority) params.priority = filter.priority
    const data = await listQueueTasks(params)
    // 后端返回 items 字段，对齐 SRS 5.1 API 规范
    tasks.value = data.items || []
    total.value = data.total || 0
  } catch {
    // 响应拦截器已弹出 ElMessage，此处兜底防止轮询链断裂
    tasks.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// 筛选变化时回到第一页，避免在旧页码上找不到数据
function handleFilterChange() {
  page.value = 1
  loadTasks()
}

async function handleCancel(id) {
  // 防重复点击：同一任务取消中直接忽略
  if (cancelingIds.value.has(id)) return
  try {
    await ElMessageBox.confirm('确认取消该任务？', '提示', { type: 'warning' })
  } catch {
    // 用户点取消，静默退出
    return
  }
  cancelingIds.value.add(id)
  try {
    await cancelTask(id)
    ElMessage.success('已取消')
    await Promise.all([loadTasks(), loadStats()])
  } catch (e) {
    console.warn('handleCancel failed:', e)
  } finally {
    cancelingIds.value.delete(id)
  }
}

async function handlePriority(row) {
  if (priorityIds.value.has(row.id)) return
  priorityIds.value.add(row.id)
  try {
    await updatePriority(row.id, editingPriority.value)
    row.priority = editingPriority.value
    ElMessage.success('优先级已更新')
  } catch (e) {
    console.warn('handlePriority failed:', e)
  } finally {
    priorityIds.value.delete(row.id)
  }
}

async function handleRetry(id) {
  if (retryingIds.value.has(id)) return
  try {
    await ElMessageBox.confirm('确认重试该任务？', '提示', { type: 'warning' })
  } catch {
    return
  }
  retryingIds.value.add(id)
  try {
    await retryTask(id)
    ElMessage.success('已加入重试队列')
    await Promise.all([loadTasks(), loadStats()])
  } catch (e) {
    console.warn('handleRetry failed:', e)
  } finally {
    retryingIds.value.delete(id)
  }
}

function openDetail(row) {
  currentTask.value = row
  detailVisible.value = true
}

// 轮询策略：有 queued/running 任务时 5s 轮询，否则降到 30s 减少无效请求
// 页面不可见时不轮询，避免最小化窗口时产生无效请求
// SSE 正常推送时轮询仍保留作为兜底（SSE 断开时仍能感知状态变化）
function scheduleNextPoll() {
  if (pollTimer) clearTimeout(pollTimer)
  if (document.hidden) return
  const interval = hasActiveTasks() ? 5000 : 30000
  pollTimer = setTimeout(async () => {
    // 用 try-finally 确保 scheduleNextPoll 总是被调用，避免单次请求失败导致轮询链断裂
    try {
      await Promise.all([loadTasks(), loadStats()])
    } finally {
      scheduleNextPoll()
    }
  }, interval)
}

// SSE 订阅：收到工作流状态变更事件后刷新任务列表和统计
// 频道启停事件也触发刷新（频道禁用会取消该频道 queued 任务）
let unsubscribeSseHandlers = []
let unsubscribeLocalDelete = null
function setupSSE() {
  const eventTypes = [
    'workflow.started',
    'workflow.completed',
    'workflow.failed',
    'workflow.step.completed',
    'workflow.step.failed',
    'channel.active_changed',
  ]
  unsubscribeSseHandlers = eventTypes.map((type) =>
    subscribe(type, () => {
      if (document.hidden) return
      // SSE 事件触发即刷新，无需等待轮询周期
      // .catch 防止 unhandled rejection（loadTasks/loadStats 内部已有 catch，此处兜底）
      Promise.all([loadTasks(), loadStats()]).catch(() => {})
    })
  )
  // 跨标签页本地事件：其他标签页删除工作流后刷新
  unsubscribeLocalDelete = subscribe('local.workflow.deleted', () => {
    if (document.hidden) return
    Promise.all([loadTasks(), loadStats()]).catch(() => {})
  })
}

// 页面可见性变化：恢复可见时延迟 500ms 重启轮询
function handleVisibilityChange() {
  if (!document.hidden) {
    setTimeout(scheduleNextPoll, 500)
  }
}

onMounted(() => {
  loadStats()
  loadConfig()
  loadChannels()
  loadTasks()
  setupSSE()
  scheduleNextPoll()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

// keep-alive 缓存时暂停轮询，恢复时重启轮询
onActivated(() => {
  scheduleNextPoll()
})
onDeactivated(() => {
  if (pollTimer) clearTimeout(pollTimer)
})

onUnmounted(() => {
  // 离开页面时清理定时器和事件监听，避免内存泄漏与无效请求
  if (pollTimer) clearTimeout(pollTimer)
  unsubscribeSseHandlers.forEach((fn) => fn())
  unsubscribeSseHandlers = []
  if (unsubscribeLocalDelete) unsubscribeLocalDelete()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.queue-management {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-row {
  .stat-card {
    border-left: 4px solid transparent;

    .stat-label {
      font-size: 13px;
      color: $color-text-secondary;
      margin-bottom: 8px;
    }

    .stat-value {
      font-size: 28px;
      font-weight: 700;
      color: $color-text-primary;
    }

    &.stat-queued { border-left-color: $color-warning; }
    &.stat-running { border-left-color: $color-primary; }
    &.stat-success { border-left-color: $color-success; }
    &.stat-failed { border-left-color: $color-danger; }
  }
}

.config-panel {
  .config-row {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;

    .config-label {
      font-size: 14px;
      color: $color-text-primary;
      font-weight: 500;
    }

    .config-value {
      font-size: 14px;
      color: $color-primary-dark;
      font-weight: 600;
    }

    .concurrency-slider {
      width: 160px;
    }
  }
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.priority-popover {
  display: flex;
  gap: 8px;
  align-items: center;
}

.steps-title {
  margin: 20px 0 12px;
  font-size: 15px;
  color: $color-text-primary;
}

.step-name {
  font-weight: 600;
  color: $color-text-primary;
}

.step-status {
  margin-top: 4px;
}

.step-time {
  margin-top: 4px;
  font-size: 12px;
  color: $color-text-secondary;
}
</style>
