<template>
  <div class="page-container workflow-list">
    <!-- 顶部操作区：查询条件 + 手动触发按钮（仅 admin 可见）
         去掉页面标题：导航栏已展示页面名称，避免重复 -->
    <div class="top-bar">
      <div class="filter-bar">
        <el-select
          v-model="filterChannelId"
          placeholder="频道"
          clearable
          style="width: 150px"
          @change="handleFilterChange"
        >
          <el-option
            v-for="ch in channels"
            :key="ch.id"
            :label="ch.name"
            :value="ch.id"
          />
        </el-select>
        <el-date-picker
          v-model="filterEpisodeDate"
          type="date"
          placeholder="节目日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          clearable
          style="width: 160px"
          @change="handleFilterChange"
        />
        <el-select
          v-model="filterStatus"
          placeholder="状态"
          clearable
          style="width: 130px"
          @change="handleFilterChange"
        >
          <el-option label="排队中" value="queued" />
          <el-option label="运行中" value="running" />
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
        <el-select
          v-model="filterSource"
          placeholder="来源"
          clearable
          style="width: 120px"
          @change="handleFilterChange"
        >
          <el-option label="定时" value="cron" />
          <el-option label="手动" value="manual" />
        </el-select>
        <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
      </div>
      <div class="top-actions">
        <el-button
          v-if="userStore.isAdmin"
          type="primary"
          :icon="VideoPlay"
          :loading="triggering"
          @click="handleTrigger"
        >
          手动触发
        </el-button>
        <!-- 批量删除：仅 admin 可见，未选中时禁用；选中时显示计数 -->
        <el-button
          v-if="userStore.isAdmin"
          type="danger"
          :icon="Delete"
          :disabled="selectedRows.length === 0 || deleting"
          :loading="deleting"
          @click="handleBatchDelete"
        >
          批量删除
        </el-button>
        <!-- 选中计数提示：让用户明确即将删除的范围，避免误操作 -->
        <span v-if="selectedRows.length > 0" class="selected-count">
          已选 {{ selectedRows.length }} 项
        </span>
      </div>
    </div>

    <!-- 工作流列表 -->
    <el-card shadow="never">
      <!--
        el-table 多选模式：
        - @selection-change 同步选中行到 selectedRows
        - ref 用于删除后调用 clearSelection() 重置选中状态
      -->
      <el-table
        ref="tableRef"
        :data="list"
        v-loading="loading"
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column label="工作流 ID" width="180">
          <template #default="{ row }">
            <!-- 点击跳详情：使用 replace 避免列表页堆积历史 -->
            <el-link type="primary" @click="goDetail(row.id)">{{ row.id }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="频道" width="130">
          <template #default="{ row }">
            <!-- channel_id 悬空（频道被删除）时显示占位，避免空白列 -->
            <el-tag v-if="row.channel_name" size="small" type="info">{{ row.channel_name }}</el-tag>
            <span v-else class="text-muted">默认</span>
          </template>
        </el-table-column>
        <el-table-column prop="episode_date" label="节目日期" width="130" />
        <el-table-column prop="source" label="来源" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.source === 'cron' ? 'info' : 'warning'">
              {{ row.source === 'cron' ? '定时' : '手动' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <!-- 进度条列：5 阶段状态灯可视化，点击 failed 灯可看错误详情 -->
        <el-table-column label="进度" min-width="280">
          <template #default="{ row }">
            <WorkflowProgressIndicator
              :steps="row.steps_summary"
              :workflow-status="row.status"
              compact
            />
          </template>
        </el-table-column>
        <el-table-column label="开始时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="结束时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadList"
          @current-change="loadList"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { VideoPlay, Delete, Refresh } from '@element-plus/icons-vue'
import { useUserStore } from '../../stores/user'
import api from '../../api'
import { listChannels } from '../../api/channels'
import { subscribe, broadcastLocal } from '../../utils/sse'
import { cleanupLoadingMasks } from '../../utils/window-guard'
import { formatTime } from '../../utils/format'
import WorkflowProgressIndicator from './components/WorkflowProgressIndicator.vue'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const triggering = ref(false)
const deleting = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)

// 多选状态：selectedRows 保存选中行，tableRef 用于清除选中
const selectedRows = ref([])
const tableRef = ref(null)

// 查询条件：四项均可空，空时不传给后端（退化为不限制）
const channels = ref([])
const filterChannelId = ref(null)
const filterEpisodeDate = ref(null)
const filterStatus = ref(null)
const filterSource = ref(null)

async function loadChannels() {
  try {
    const data = await listChannels(false)
    channels.value = Array.isArray(data) ? data : (data.list || [])
  } catch {
    channels.value = []
  }
}

function handleFilterChange() {
  page.value = 1
  loadList()
}

function resetFilters() {
  filterChannelId.value = null
  filterEpisodeDate.value = null
  filterStatus.value = null
  filterSource.value = null
  page.value = 1
  loadList()
}

// 状态到 el-tag 类型的映射：保持与 UI 语义一致（橙/绿/红/灰）
const STATUS_TAG_MAP = {
  running: 'warning',
  success: 'success',
  failed: 'danger',
  cancelled: 'info',
  queued: 'info',
}
const STATUS_LABEL_MAP = {
  running: '运行中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
  queued: '排队中',
}
function statusTagType(s) {
  return STATUS_TAG_MAP[s] || 'info'
}
function statusLabel(s) {
  return STATUS_LABEL_MAP[s] || s
}

async function loadList() {
  loading.value = true
  try {
    const params = { page: page.value, size: size.value }
    if (filterChannelId.value !== null) {
      params.channel_id = filterChannelId.value
    }
    if (filterEpisodeDate.value) {
      params.episode_date = filterEpisodeDate.value
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    if (filterSource.value) {
      params.source = filterSource.value
    }
    const data = await api.get('/workflows', { params })
    list.value = data.list || []
    total.value = data.total || 0

    // 安全页码修正：删除后当前页可能变空（如第 3 页只剩 1 条被删），
    // 此时回退到上一页避免用户面对空白列表
    if (list.value.length === 0 && page.value > 1) {
      page.value -= 1
      await loadList()
    }

    // 根据最新列表状态启停轮询：有活跃工作流时启动，全部终态时停止
    startPollingIfNeeded()
  } finally {
    loading.value = false
  }
}

async function handleTrigger() {
  // 若已选择频道筛选，触发时携带频道 ID，rewrite 步骤据此读取频道级提示词
  const channelId = filterChannelId.value
  const tip = channelId
    ? '确认立即触发该频道的工作流？将使用频道级提示词生成语音新闻。'
    : '确认立即触发一期新闻工作流？（未选频道，使用默认提示词）'
  try {
    await ElMessageBox.confirm(tip, '提示', { type: 'warning' })
  } catch {
    return
  }
  triggering.value = true
  try {
    const payload = channelId ? { channel_id: channelId } : {}
    const data = await api.post('/workflows/trigger', payload)
    ElMessage.success(`已触发，工作流 ID: ${data.workflow_id}`)
    page.value = 1
    await loadList()
  } finally {
    triggering.value = false
  }
}

function handleSelectionChange(rows) {
  // el-table 的 selection-change 事件：rows 是当前选中行数组
  selectedRows.value = rows
}

async function handleBatchDelete() {
  const ids = selectedRows.value.map((r) => r.id)
  if (ids.length === 0) return

  // 二次确认：显示具体 ID 数量让用户明确操作范围
  try {
    await ElMessageBox.confirm(
      `确认删除选中的 ${ids.length} 个工作流？\n\n将删除：稿件、审核、节目及播放记录。\n将保留：素材（重置为待处理状态，可被后续工作流复用）。\n\n此操作不可撤销。`,
      '危险操作',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  deleting.value = true
  try {
    const data = await api.post('/workflows/batch-delete', { workflow_ids: ids })
    const deletedCount = data.deleted?.length || ids.length
    ElMessage.success(`已删除 ${deletedCount} 个工作流`)

    // 重置选中状态：避免删除后 selectedRows 仍引用已删记录
    tableRef.value?.clearSelection()
    selectedRows.value = []

    // 刷新列表：删除后总数减少，可能需要页码修正
    await loadList()
  } finally {
    deleting.value = false
  }
}

function goDetail(id) {
  router.push(`/workflows/${id}`)
}

let unsubscribeSse = null
let unsubscribeLocalDelete = null
function setupSSE() {
  const eventTypes = [
    'workflow.started', 'workflow.completed', 'workflow.failed',
    'workflow.step.completed', 'workflow.step.failed',
  ]
  const handlers = eventTypes.map((type) =>
    subscribe(type, () => {
      if (!document.hidden) loadList()
    })
  )
  unsubscribeLocalDelete = subscribe('local.workflow.deleted', () => {
    if (!document.hidden) loadList()
  })
  unsubscribeSse = () => {
    handlers.forEach((fn) => fn())
    if (unsubscribeLocalDelete) unsubscribeLocalDelete()
  }
}

// ===== 轮询兜底：SSE 断连或漏事件时仍能感知工作流状态变化 =====
// 仅当列表中存在 running/queued 工作流时启动 5s 轮询，全部终态时停止
// 避免无工作流运行时持续轮询浪费资源
let pollTimer = null
const RUNNING_STATUSES = new Set(['running', 'queued'])

function hasActiveWorkflow() {
  return list.value.some((w) => RUNNING_STATUSES.has(w.status))
}

function startPollingIfNeeded() {
  if (pollTimer && !hasActiveWorkflow()) {
    // 已无活跃工作流，停止轮询
    clearInterval(pollTimer)
    pollTimer = null
    return
  }
  if (!pollTimer && hasActiveWorkflow()) {
    // 有活跃工作流，启动 5s 轮询
    pollTimer = setInterval(() => {
      if (!document.hidden) loadList()
    }, 5000)
  }
}

// 页面恢复可见时立即刷新：弥补隐藏期间错过的 SSE 事件
// SSE 在页面隐藏时会断开（sse.js 的 visibilitychange 处理），
// 恢复可见后重连前的状态变化无法感知，需主动刷新一次
//
// 修复遮罩残留：页面最小化时浏览器暂停 CSS transition 和 setTimeout，
// Element Plus v-loading 指令的 mask 隐藏流程不执行，DOM 永久残留。
// 之前用 toggle (true→nextTick→false) 修复不可靠：值未变化时 watch 不触发，
// transitionend 不触发，setTimeout 被 throttle。改为直接调用
// cleanupLoadingMasks() 强制从 DOM 移除残留 mask，不依赖任何时序。
function handleVisibilityChange() {
  if (!document.hidden) {
    // 强制重置 Vue 状态：覆盖残留的 loading=true 情况
    loading.value = false
    triggering.value = false
    deleting.value = false
    // 直接清理所有残留 mask（包括当前页面外的，保持全局一致性）
    cleanupLoadingMasks()
    // rAF 等待浏览器完成一帧渲染后加载新数据，确保 mask 清理后立即重建数据
    requestAnimationFrame(() => {
      loadList()
      startPollingIfNeeded()
    })
  }
}

function handleResize() {
  // 预留：窗口尺寸变化时的响应式处理
}

onMounted(() => {
  // 兜底：进入页面时清理可能的残留 mask（来自其他页面的最小化过程）
  cleanupLoadingMasks()
  // loadList 内部会调用 startPollingIfNeeded，无需在此额外调用
  loadList()
  loadChannels()
  setupSSE()
  window.addEventListener('resize', handleResize)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (unsubscribeSse) unsubscribeSse()
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.workflow-list {
  .top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    flex-wrap: wrap;
    gap: 12px;

    .filter-bar {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .top-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    // 选中计数：与按钮区分，用次要文字色避免抢眼
    .selected-count {
      font-size: 13px;
      color: $color-text-secondary;
    }
  }

  // 频道悬空时的占位文字：弱化显示，与有值时形成视觉对比
  .text-muted {
    font-size: 13px;
    color: $color-text-secondary;
  }

  .pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}
</style>
