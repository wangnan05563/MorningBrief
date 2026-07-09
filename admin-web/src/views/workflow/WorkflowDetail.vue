<template>
  <div class="page-container workflow-detail">
    <!-- 顶部：返回 + 标题 -->
    <div class="top-bar">
      <el-button :icon="ArrowLeft" plain @click="router.back()">返回</el-button>
      <span class="page-title">工作流详情</span>
      <span class="spacer" />
    </div>

    <el-card v-loading="loading" shadow="never" class="info-card">
      <!-- 基础信息：用 descriptions 紧凑展示元数据 -->
      <el-descriptions :column="3" border>
        <el-descriptions-item label="工作流 ID">{{ detail.workflow_id }}</el-descriptions-item>
        <el-descriptions-item label="节目日期">{{ detail.episode_date }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ sourceLabel(detail.source) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTagType(detail.status)">{{ statusLabel(detail.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ detail.started_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ detail.finished_at || '-' }}</el-descriptions-item>
      </el-descriptions>

      <!-- 错误信息：仅失败时展示，避免成功时占用空间 -->
      <el-alert
        v-if="detail.error"
        class="error-alert"
        :title="detail.error"
        type="error"
        :closable="false"
        show-icon
      />
    </el-card>

    <!-- 步骤进度条：5 步流水线可视化 -->
    <el-card shadow="never" class="steps-card">
      <el-steps :active="activeStep" align-center>
        <el-step
          v-for="(s, i) in orderedSteps"
          :key="s.name"
          :title="stepLabel(s.name)"
          :status="stepElStatus(s.status)"
          :description="i === activeStep ? stepStatusText(s.status) : ''"
        />
      </el-steps>
    </el-card>

    <!-- 步骤详情表格 -->
    <el-card shadow="never" class="table-card">
      <el-table :data="orderedSteps" stripe>
        <el-table-column label="步骤" width="160">
          <template #default="{ row }">{{ stepLabel(row.name) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="stepTagType(row.status)" size="small">{{ stepStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" min-width="170" />
        <el-table-column prop="finished_at" label="结束时间" min-width="170" />
        <el-table-column label="耗时(秒)" width="110">
          <template #default="{ row }">{{ formatDuration(row) }}</template>
        </el-table-column>
        <el-table-column prop="retry_count" label="重试次数" width="100" />
        <el-table-column prop="error" label="错误信息" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- 底部操作区：选步骤重跑 -->
    <el-card shadow="never" class="action-card">
      <div class="action-bar">
        <span class="action-label">从指定步骤重跑：</span>
        <el-select v-model="retryStep" placeholder="选择步骤" style="width: 200px">
          <el-option v-for="s in STEP_ORDER" :key="s" :label="stepLabel(s)" :value="s" />
        </el-select>
        <el-button
          type="primary"
          :icon="RefreshRight"
          :disabled="!retryStep"
          :loading="retrying"
          @click="handleRetry"
        >
          重跑
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, RefreshRight } from '@element-plus/icons-vue'
import api from '../../api'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const retrying = ref(false)
const detail = ref({})
// 重跑步骤默认不选，强制用户明确选择，避免误操作整个流水线
const retryStep = ref('')

// 步骤固定顺序：与流水线执行顺序一致
const STEP_ORDER = ['crawl', 'rewrite', 'tts', 'stitch', 'review']
const STEP_LABEL_MAP = {
  crawl: '爬虫采集',
  rewrite: 'LLM改写',
  tts: '语音合成',
  stitch: '音频拼接',
  review: '创建审核',
}

// 步骤状态映射到 el-step status：retrying 视为 process（运行中）
const STEP_EL_STATUS_MAP = {
  success: 'success',
  failed: 'error',
  running: 'process',
  pending: 'wait',
  retrying: 'process',
}
// 步骤状态中文文案
const STEP_STATUS_TEXT = {
  pending: '等待中',
  running: '运行中',
  success: '成功',
  retrying: '重试中',
  failed: '失败',
}
// 步骤状态映射到 el-tag 类型（wait 用 info 灰色）
const STEP_TAG_TYPE_MAP = {
  success: 'success',
  failed: 'danger',
  running: 'warning',
  pending: 'info',
  retrying: 'warning',
}

// 工作流整体状态映射（与列表页保持一致）
const STATUS_TAG_MAP = {
  running: 'warning',
  success: 'success',
  failed: 'danger',
  cancelled: 'info',
}
const STATUS_LABEL_MAP = {
  running: '运行中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
}

function statusTagType(s) {
  return STATUS_TAG_MAP[s] || 'info'
}
function statusLabel(s) {
  return STATUS_LABEL_MAP[s] || s
}
function sourceLabel(s) {
  if (s === 'cron') return '定时'
  if (s === 'manual') return '手动'
  return s || '-'
}
function stepLabel(name) {
  return STEP_LABEL_MAP[name] || name
}
function stepElStatus(s) {
  return STEP_EL_STATUS_MAP[s] || 'wait'
}
function stepStatusText(s) {
  return STEP_STATUS_TEXT[s] || s
}
function stepTagType(s) {
  return STEP_TAG_TYPE_MAP[s] || 'info'
}

// 按固定顺序输出步骤，保证进度条始终是 5 步
// 后端步骤对象用 name 字段（而非 step_name），缺失则补默认占位
const orderedSteps = computed(() => {
  const steps = detail.value.steps || []
  return STEP_ORDER.map((name) => steps.find((s) => s.name === name) || { name, status: 'pending' })
})

// active = 第一个非 success 的步骤索引：让进度条停在实际执行/失败处
const activeStep = computed(() => {
  const idx = orderedSteps.value.findIndex((s) => s.status !== 'success')
  return idx === -1 ? orderedSteps.value.length : idx
})

// 耗时由 finished_at - started_at 计算（后端不返回 duration_ms）
// 时间字符串均为 ISO 格式，可直接用 Date 解析；缺值或未完成时显示 -
function formatDuration(row) {
  if (!row || !row.started_at || !row.finished_at) return '-'
  const ms = new Date(row.finished_at).getTime() - new Date(row.started_at).getTime()
  if (Number.isNaN(ms) || ms < 0) return '-'
  return (ms / 1000).toFixed(1)
}

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await api.get(`/workflows/${route.params.id}`)
  } finally {
    loading.value = false
  }
}

async function handleRetry() {
  if (!retryStep.value) return
  // 重跑会消耗资源并生成新工作流，需二次确认
  await ElMessageBox.confirm(
    `确认从「${stepLabel(retryStep.value)}」步骤开始重跑？将生成新的工作流。`,
    '提示',
    { type: 'warning' },
  )
  retrying.value = true
  try {
    const data = await api.post(`/workflows/${route.params.id}/retry`, { step: retryStep.value })
    ElMessage.success('已创建重跑工作流')
    // 跳转到新工作流详情页，replace 避免回退回到旧工作流造成困惑
    router.replace(`/workflows/${data.new_workflow_id}`)
  } finally {
    retrying.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.workflow-detail {
  .top-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;

    .page-title {
      font-size: 18px;
      font-weight: 600;
      color: $color-text-primary;
    }

    .spacer {
      flex: 1;
    }
  }

  .info-card,
  .steps-card,
  .table-card,
  .action-card {
    margin-bottom: 16px;
  }

  .error-alert {
    margin-top: 12px;
  }

  .action-bar {
    display: flex;
    align-items: center;
    gap: 12px;

    .action-label {
      font-size: 14px;
      color: $color-text-primary;
    }
  }
}
</style>
