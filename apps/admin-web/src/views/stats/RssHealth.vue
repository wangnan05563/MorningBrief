<template>
  <div class="page-container rss-health-page">
    <!-- 顶部操作区：标题 + 刷新按钮 -->
    <div class="top-bar">
      <span class="page-title">RSS 源可达性</span>
      <div class="actions">
        <span v-if="lastCheckedAt" class="last-check">
          最近巡检：{{ formatTime(lastCheckedAt) }}
        </span>
        <el-button
          type="primary"
          :loading="refreshing"
          :icon="Refresh"
          @click="refresh"
        >
          立即巡检
        </el-button>
      </div>
    </div>

    <!-- 汇总卡片：总数 / OK / 失败 / 未知 -->
    <el-row :gutter="16" class="summary-row">
      <el-col v-for="s in summaryCards" :key="s.key" :xs="12" :sm="6">
        <el-card shadow="hover">
          <div class="summary-card" :class="s.cls">
            <div class="summary-label">{{ s.label }}</div>
            <div class="summary-value">{{ s.value }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选区：状态筛选 + 品类筛选 + 搜索 -->
    <div class="filter-bar">
      <el-radio-group v-model="statusFilter" @change="applyFilter">
        <el-radio-button value="all">全部（{{ allCount }}）</el-radio-button>
        <el-radio-button value="ok">正常（{{ okCount }}）</el-radio-button>
        <el-radio-button value="fail">失败（{{ failCount }}）</el-radio-button>
        <el-radio-button value="unknown">未巡检（{{ unknownCount }}）</el-radio-button>
      </el-radio-group>
      <el-input
        v-model="keyword"
        placeholder="按源名/URL/品类搜索"
        clearable
        :prefix-icon="Search"
        class="filter-input"
        @input="applyFilter"
      />
    </div>

    <!-- 源状态表格 -->
    <el-card shadow="never" class="table-card">
      <el-table
        v-loading="loading"
        :data="filteredSources"
        stripe
        :default-sort="{ prop: 'status', order: 'ascending' }"
      >
        <el-table-column label="源名" prop="name" min-width="180" show-overflow-tooltip />

        <el-table-column label="品类" prop="category_hint" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.category_hint" size="small" type="info" effect="plain">
              {{ row.category_hint }}
            </el-tag>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="状态" prop="status" width="100" sortable>
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small" effect="light">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="延迟" prop="latency_ms" width="100" sortable>
          <template #default="{ row }">
            <span v-if="row.latency_ms > 0" :class="latencyClass(row.latency_ms)">
              {{ row.latency_ms }} ms
            </span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="连续失败" prop="consecutive_failures" width="110" sortable>
          <template #default="{ row }">
            <el-badge
              v-if="row.consecutive_failures > 0"
              :value="row.consecutive_failures"
              :type="row.consecutive_failures >= 3 ? 'danger' : 'warning'"
            />
            <span v-else class="muted">0</span>
          </template>
        </el-table-column>

        <el-table-column label="最近巡检" prop="last_check" width="170" sortable>
          <template #default="{ row }">
            <span v-if="row.last_check">{{ formatTime(row.last_check) }}</span>
            <span v-else class="muted">未巡检</span>
          </template>
        </el-table-column>

        <el-table-column label="URL" prop="url" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <a
              v-if="row.url"
              :href="row.url"
              target="_blank"
              rel="noopener noreferrer"
              class="url-link"
            >{{ row.url }}</a>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="错误信息" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.last_error" class="error-text">{{ row.last_error }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <!-- 修复建议列：后端根据 URL 模式 + 失败次数给出可执行建议 -->
        <el-table-column label="修复建议" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.suggestion" class="suggestion-text">{{ row.suggestion }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import api from '../../api'

const loading = ref(false)
const refreshing = ref(false)
const rawData = ref({ total: 0, ok: 0, fail: 0, unknown: 0, sources: [] })
const lastCheckedAt = ref(null)

// 筛选状态：statusFilter 多状态单选 + keyword 模糊搜索
const statusFilter = ref('all')
const keyword = ref('')
const filteredSources = ref([])

const allCount = computed(() => rawData.value.total)
const okCount = computed(() => rawData.value.ok)
const failCount = computed(() => rawData.value.fail)
const unknownCount = computed(() => rawData.value.unknown || 0)

// 汇总卡片：4 个数字染色区分，便于快速识别整体可达性
const summaryCards = computed(() => [
  { key: 'total', label: '源总数', value: rawData.value.total, cls: 'is-total' },
  { key: 'ok', label: '正常', value: rawData.value.ok, cls: 'is-ok' },
  { key: 'fail', label: '失败', value: rawData.value.fail, cls: 'is-fail' },
  { key: 'unknown', label: '未巡检', value: rawData.value.unknown || 0, cls: 'is-unknown' },
])

function statusTagType(status) {
  if (status === 'ok') return 'success'
  if (status === 'fail') return 'danger'
  return 'info'
}

function statusLabel(status) {
  if (status === 'ok') return '正常'
  if (status === 'fail') return '失败'
  return '未巡检'
}

// 延迟颜色编码：<500ms 绿、500-2000ms 橙、>2000ms 红
function latencyClass(ms) {
  if (ms < 500) return 'latency-ok'
  if (ms < 2000) return 'latency-warn'
  return 'latency-bad'
}

function formatTime(iso) {
  if (!iso) return '-'
  return dayjs(iso).format('YYYY-MM-DD HH:mm')
}

// 本地筛选：避免每次筛选都打后端
function applyFilter() {
  const kw = keyword.value.trim().toLowerCase()
  filteredSources.value = rawData.value.sources.filter((s) => {
    if (statusFilter.value !== 'all' && s.status !== statusFilter.value) return false
    if (kw) {
      const hay = `${s.name || ''} ${s.url || ''} ${s.category_hint || ''}`.toLowerCase()
      if (!hay.includes(kw)) return false
    }
    return true
  })
}

async function loadData() {
  loading.value = true
  try {
    const data = await api.get('/stats/rss-health')
    rawData.value = {
      total: data.total || 0,
      ok: data.ok || 0,
      fail: data.fail || 0,
      unknown: data.unknown || 0,
      sources: data.sources || [],
    }
    // 推导最近巡检时间：所有源中最大的 last_check
    const checks = rawData.value.sources
      .map((s) => s.last_check)
      .filter(Boolean)
      .sort()
    lastCheckedAt.value = checks.length ? checks[checks.length - 1] : null
    applyFilter()
  } finally {
    loading.value = false
  }
}

// 立即巡检：触发后端 HEAD/GET 探测，耗时 5-15s，期间禁用按钮
async function refresh() {
  refreshing.value = true
  try {
    const data = await api.get('/stats/rss-health', { params: { refresh: true }, timeout: 60000 })
    rawData.value = {
      total: data.total || 0,
      ok: data.ok || 0,
      fail: data.fail || 0,
      unknown: data.unknown || 0,
      sources: data.sources || [],
    }
    const checks = rawData.value.sources
      .map((s) => s.last_check)
      .filter(Boolean)
      .sort()
    lastCheckedAt.value = checks.length ? checks[checks.length - 1] : null
    applyFilter()
  } finally {
    refreshing.value = false
  }
}

onMounted(loadData)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.rss-health-page {
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

    .actions {
      display: flex;
      align-items: center;
      gap: 16px;

      .last-check {
        font-size: 13px;
        color: $color-text-secondary;
      }
    }
  }

  .summary-row {
    margin-bottom: 16px;

    .el-col {
      margin-bottom: 12px;
    }
  }

  .summary-card {
    text-align: center;
    padding: 16px 12px;
    border-radius: $radius-md;

    .summary-label {
      font-size: 13px;
      color: $color-text-secondary;
      margin-bottom: 6px;
    }

    .summary-value {
      font-size: 26px;
      font-weight: 700;
    }

    &.is-total .summary-value { color: $color-text-primary; }
    &.is-ok .summary-value { color: $color-primary-dark; }
    &.is-fail .summary-value { color: #E05050; }
    &.is-unknown .summary-value { color: $color-text-secondary; }
  }

  .filter-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;

    .filter-input {
      max-width: 280px;
    }
  }

  .table-card {
    .url-link {
      color: $color-primary-dark;
      text-decoration: none;

      &:hover {
        text-decoration: underline;
      }
    }

    .muted {
      color: $color-text-secondary;
    }

    .error-text {
      color: #E05050;
      font-size: 12px;
    }

    // 修复建议列样式：黄色提示，与错误信息（红色）区分
    .suggestion-text {
      color: #C7781E;
      font-size: 12px;
      line-height: 1.4;
    }

    // 延迟颜色编码
    .latency-ok { color: $color-primary-dark; font-weight: 500; }
    .latency-warn { color: #E09020; }
    .latency-bad { color: #E05050; font-weight: 500; }
  }
}
</style>
