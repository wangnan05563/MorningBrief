<template>
  <div class="page-container workflow-list">
    <!-- 顶部操作区：标题 + 手动触发按钮（仅 admin 可见） -->
    <div class="top-bar">
      <span class="page-title">工作流监控</span>
      <div class="top-actions">
        <el-select
          v-model="filterChannelId"
          placeholder="全部频道"
          clearable
          style="width: 160px"
          @change="handleFilterChange"
        >
          <el-option
            v-for="ch in channels"
            :key="ch.id"
            :label="ch.name"
            :value="ch.id"
          />
        </el-select>
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
        <el-table-column prop="started_at" label="开始时间" min-width="170" />
        <el-table-column prop="finished_at" label="结束时间" min-width="170" />
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
import { ElMessage } from '../../utils/message'
import { ElMessageBox } from 'element-plus'
import { VideoPlay, Delete } from '@element-plus/icons-vue'
import { useUserStore } from '../../stores/user'
import api from '../../api'
import { listChannels } from '../../api/channels'
import { subscribe, broadcastLocal } from '../../utils/sse'
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

const channels = ref([])
const filterChannelId = ref(null)

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
    const data = await api.get('/workflows', { params })
    list.value = data.list || []
    total.value = data.total || 0

    // 安全页码修正：删除后当前页可能变空（如第 3 页只剩 1 条被删），
    // 此时回退到上一页避免用户面对空白列表
    if (list.value.length === 0 && page.value > 1) {
      page.value -= 1
      await loadList()
    }
  } finally {
    loading.value = false
  }
}

async function handleTrigger() {
  try {
    await ElMessageBox.confirm('确认立即触发一期新闻工作流？', '提示', { type: 'warning' })
  } catch {
    return
  }
  triggering.value = true
  try {
    const data = await api.post('/workflows/trigger', {})
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
      `确认删除选中的 ${ids.length} 个工作流？将级联删除稿件、素材、审核、节目及播放记录，此操作不可撤销。`,
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

function handleResize() {
  // 预留：窗口尺寸变化时的响应式处理
}

onMounted(() => {
  loadList()
  loadChannels()
  setupSSE()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
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

    .page-title {
      font-size: 18px;
      font-weight: 600;
      color: $color-text-primary;
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

  .pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}
</style>
