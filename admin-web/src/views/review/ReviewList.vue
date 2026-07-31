<template>
  <div class="review-list page-container" v-loading="loading">
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="待审核" name="pending" />
      <el-tab-pane label="已通过" name="approved" />
      <el-tab-pane label="已打回" name="rejected" />
    </el-tabs>

    <!-- 批量操作栏：仅在待审核 tab 显示，选中后才可操作 -->
    <div v-if="activeTab === 'pending'" class="batch-bar">
      <span class="batch-info" v-if="selectedRows.length > 0">
        已选 {{ selectedRows.length }} 条
      </span>
      <span class="batch-info" v-else>勾选下方记录后可批量操作</span>
      <div class="batch-actions">
        <el-button
          type="success"
          size="small"
          :disabled="selectedRows.length === 0 || batchLoading"
          :loading="batchLoading && batchAction === 'approve'"
          @click="handleBatchApprove"
        >
          批量通过
        </el-button>
        <el-button
          type="danger"
          size="small"
          :disabled="selectedRows.length === 0 || batchLoading"
          :loading="batchLoading && batchAction === 'reject'"
          @click="handleBatchReject"
        >
          批量打回
        </el-button>
      </div>
    </div>

    <el-table
      ref="tableRef"
      :data="list"
      stripe
      class="list-table"
      @selection-change="handleSelectionChange"
    >
      <!-- 选择列仅在待审核 tab 显示，避免误操作已处理记录 -->
      <el-table-column
        v-if="activeTab === 'pending'"
        type="selection"
        width="48"
      />
      <el-table-column prop="episode_date" label="日期" width="140" />
      <el-table-column prop="workflow_id" label="工作流ID" min-width="160" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" effect="light">
            {{ statusText(row.status) }}
          </el-tag>
          <!-- 自动审批标记：仅在系统自动审批通过时显示 -->
          <el-tag
            v-if="row.auto_approved"
            size="small"
            type="primary"
            effect="plain"
            style="margin-left: 4px"
          >
            系统
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="审核人" width="140">
        <template #default="{ row }">
          {{ row.reviewer_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="200">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="goReview(row.id)">审核</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        :page-size="size"
        :total="total"
        layout="prev, pager, next, total"
        background
        @current-change="loadList"
      />
    </div>
  </div>
</template>

<script setup>
/**
 * 审核列表页：按状态分 tab 展示稿件
 *
 * 设计要点：
 * - tab 与分页联动：切换 tab 时重置到第一页，避免停留在不存在的页码
 * - 状态映射到 el-tag 颜色，直观区分审核进度
 * - 列表数据由后端按 status 过滤返回，前端不做本地过滤
 * - 批量审批仅在待审核 tab 启用：已通过/已打回的记录不允许批量操作
 * - 批量操作结果按 succeeded/failed/skipped 分类提示，便于用户识别
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../../api'
import { batchHandleReviewAction } from '../../api/reviews'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { formatTime } from '../../utils/format'

const router = useRouter()

const loading = ref(false)
const activeTab = ref('pending')
const list = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(10)

// 批量操作状态
const tableRef = ref(null)
const selectedRows = ref([])
const batchLoading = ref(false)
const batchAction = ref('')

async function loadList() {
  loading.value = true
  try {
    const data = await api.get('/reviews', {
      params: { status: activeTab.value, page: page.value, size: size.value },
    })
    list.value = data.list
    total.value = data.total
  } catch {
    // 错误提示由拦截器统一处理
  } finally {
    loading.value = false
  }
}

// 切换 tab 重置分页再加载
function handleTabChange() {
  page.value = 1
  // 切换 tab 时清空选中状态，避免选中其他 tab 的记录
  selectedRows.value = []
  tableRef.value?.clearSelection()
  loadList()
}

function goReview(id) {
  router.push(`/review/${id}`)
}

function statusTagType(status) {
  return { pending: 'warning', approved: 'success', rejected: 'danger' }[status] || 'info'
}

function statusText(status) {
  return { pending: '待审核', approved: '已通过', rejected: '已打回' }[status] || status
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

/**
 * 构造批量操作结果提示文本
 * 显示成功/跳过/失败/发布失败的统计，便于用户识别处理情况
 */
function buildBatchSummary(result) {
  const parts = []
  if (result.succeeded?.length) parts.push(`成功 ${result.succeeded.length}`)
  if (result.skipped?.length) parts.push(`跳过 ${result.skipped.length}`)
  if (result.failed?.length) parts.push(`失败 ${result.failed.length}`)
  if (result.publish_failed?.length) parts.push(`发布失败 ${result.publish_failed.length}`)
  return parts.join('，') || '无变更'
}

async function handleBatchApprove() {
  const ids = selectedRows.value.map((r) => r.id)
  if (ids.length === 0) return

  try {
    await ElMessageBox.confirm(
      `确认批量通过选中的 ${ids.length} 条审核记录？\n通过后将自动发布对应节目。`,
      '批量通过确认',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  batchAction.value = 'approve'
  batchLoading.value = true
  try {
    const data = await batchHandleReviewAction(ids, 'approve')
    const summary = buildBatchSummary(data)
    // 全部成功时 success，部分失败时 warning
    if (data.failed?.length || data.publish_failed?.length) {
      ElMessage.warning(`批量通过完成：${summary}`)
    } else {
      ElMessage.success(`批量通过完成：${summary}`)
    }
    // 清空选中状态并刷新列表
    tableRef.value?.clearSelection()
    selectedRows.value = []
    await loadList()
  } finally {
    batchLoading.value = false
    batchAction.value = ''
  }
}

async function handleBatchReject() {
  const ids = selectedRows.value.map((r) => r.id)
  if (ids.length === 0) return

  // 批量打回必须填写统一理由，使用 prompt 收集
  let reason
  try {
    const result = await ElMessageBox.prompt(
      `请输入批量打回理由（将应用于选中的 ${ids.length} 条记录）：`,
      '批量打回确认',
      {
        type: 'warning',
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputPlaceholder: '请输入打回理由',
        inputValidator: (val) => (val && val.trim() ? true : '打回理由不能为空'),
      }
    )
    reason = result.value
  } catch {
    return
  }

  batchAction.value = 'reject'
  batchLoading.value = true
  try {
    const data = await batchHandleReviewAction(ids, 'reject', reason)
    const summary = buildBatchSummary(data)
    if (data.failed?.length) {
      ElMessage.warning(`批量打回完成：${summary}`)
    } else {
      ElMessage.success(`批量打回完成：${summary}`)
    }
    tableRef.value?.clearSelection()
    selectedRows.value = []
    await loadList()
  } finally {
    batchLoading.value = false
    batchAction.value = ''
  }
}

onMounted(loadList)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: $radius-lg;

  .batch-info {
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }

  .batch-actions {
    display: flex;
    gap: 8px;
  }
}

.list-table {
  border-radius: $radius-lg;
  overflow: hidden;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
