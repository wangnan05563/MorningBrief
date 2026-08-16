<template>
  <div class="page-container auto-review-page">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <h2 class="page-title">自动审批</h2>
      <el-button :icon="Refresh" :loading="loadingAll" @click="loadAll">
        刷新
      </el-button>
    </div>

    <!-- 配置区域 -->
    <div class="config-section card-soft">
      <div class="section-header">
        <el-icon class="header-icon"><Setting /></el-icon>
        <span>规则配置</span>
        <el-tag v-if="config?.updated_at" size="small" type="info" effect="plain">
          上次更新：{{ formatTime(config.updated_at) }}（{{ config.updated_by || '未知' }}）
        </el-tag>
      </div>

      <el-form
        :model="form"
        label-position="top"
        v-loading="loadingConfig"
        class="config-form"
      >
        <!-- 总开关 -->
        <el-form-item>
          <div class="switch-row">
            <div class="switch-meta">
              <span class="switch-label">启用自动审批</span>
              <span class="text-muted">
                开启后，工作流完成时自动检查规则，全部命中则自动通过并发布节目
              </span>
            </div>
            <!-- active-value/inactive-value 显式声明，与后端 bool 字段一致 -->
            <el-switch
              v-model="form.enabled"
              :active-value="true"
              :inactive-value="false"
            />
          </div>
        </el-form-item>

        <el-divider content-position="left">触发条件（全部命中才自动通过）</el-divider>

        <el-form-item>
          <div class="switch-row">
            <div class="switch-meta">
              <span class="switch-label">内容安全检测通过</span>
              <span class="text-muted">
                要求 rewrite 步骤的微信 msgSecCheck 结果为 safe
              </span>
            </div>
            <el-switch
              v-model="form.require_content_safe"
              :active-value="true"
              :inactive-value="false"
            />
          </div>
        </el-form-item>

        <el-form-item>
          <div class="switch-row">
            <div class="switch-meta">
              <span class="switch-label">工作流步骤一次成功</span>
              <span class="text-muted">
                要求前 4 步（crawl/rewrite/tts/stitch）全部一次成功，无重试记录
              </span>
            </div>
            <el-switch
              v-model="form.require_steps_first_success"
              :active-value="true"
              :inactive-value="false"
            />
          </div>
        </el-form-item>

        <el-form-item label="关键词白名单（可选）">
          <div class="keyword-input-wrap">
            <el-input
              v-model="keywordInput"
              placeholder="输入关键词后按回车添加（留空表示不启用此规则）"
              @keyup.enter="addKeyword"
            />
            <el-button :icon="Plus" @click="addKeyword">添加</el-button>
          </div>
          <div class="keyword-tags">
            <el-tag
              v-for="(kw, idx) in form.keyword_whitelist"
              :key="idx"
              closable
              @close="removeKeyword(idx)"
              class="keyword-tag"
            >
              {{ kw }}
            </el-tag>
            <span v-if="!form.keyword_whitelist.length" class="text-muted">
              未配置关键词，该规则不启用
            </span>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveConfig">
            保存配置
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 统计指标卡片 -->
    <div class="stats-section" v-loading="loadingStats">
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="card-soft stat-card">
            <div class="stat-header">
              <el-icon class="stat-icon"><DataLine /></el-icon>
              <span class="stat-title">总尝试</span>
            </div>
            <div class="stat-value">{{ stats?.total ?? 0 }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="card-soft stat-card">
            <div class="stat-header">
              <el-icon class="stat-icon success-icon"><CircleCheck /></el-icon>
              <span class="stat-title">成功数</span>
            </div>
            <div class="stat-value">{{ stats?.success_count ?? 0 }}</div>
            <div class="stat-detail">成功率 {{ formatPercent(stats?.success_rate) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="card-soft stat-card">
            <div class="stat-header">
              <el-icon class="stat-icon fail-icon"><CircleClose /></el-icon>
              <span class="stat-title">失败数</span>
            </div>
            <div class="stat-value">{{ stats?.failed_count ?? 0 }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="card-soft stat-card">
            <div class="stat-header">
              <el-icon class="stat-icon time-icon"><Timer /></el-icon>
              <span class="stat-title">节省时间</span>
            </div>
            <div class="stat-value">{{ formatDuration(stats?.total_time_saved_sec) }}</div>
            <div class="stat-detail">平均 {{ formatDuration(stats?.avg_time_saved_sec) }}</div>
          </div>
        </el-col>
      </el-row>

      <!-- 日期范围选择 -->
      <div class="date-range-bar">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          @change="loadStats"
        />
        <span class="text-muted">
          统计区间：{{ stats?.start_date }} 至 {{ stats?.end_date }}
        </span>
      </div>

      <!-- 失败原因分布 -->
      <div v-if="stats?.fail_distribution?.length" class="card-soft fail-dist-card">
        <div class="section-header">
          <el-icon class="header-icon"><WarningFilled /></el-icon>
          <span>失败原因分布（Top 5）</span>
        </div>
        <ul class="fail-dist-list">
          <li v-for="(item, idx) in stats.fail_distribution" :key="idx">
            <span class="fail-reason">{{ item.reason || '未知原因' }}</span>
            <el-tag size="small" type="danger">{{ item.count }} 次</el-tag>
          </li>
        </ul>
      </div>
    </div>

    <!-- 执行历史表格 -->
    <div class="history-section card-soft">
      <div class="section-header">
        <el-icon class="header-icon"><List /></el-icon>
        <span>执行历史</span>
        <el-radio-group v-model="historyFilter" size="small" @change="loadHistory">
          <el-radio-button :value="null">全部</el-radio-button>
          <el-radio-button :value="true">仅成功</el-radio-button>
          <el-radio-button :value="false">仅失败</el-radio-button>
        </el-radio-group>
      </div>

      <el-table
        :data="history.list"
        v-loading="loadingHistory"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="workflow_id" label="工作流 ID" min-width="160" show-overflow-tooltip />
        <el-table-column prop="review_id" label="审核 ID" width="100" />
        <el-table-column label="结果" width="100">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small">
              {{ row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="触发原因" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.success">{{ formatRules(row.trigger_reason) }}</span>
            <span v-else class="text-error">{{ row.error_message || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="节省时间" width="120">
          <template #default="{ row }">
            {{ row.time_saved_sec != null ? formatDuration(row.time_saved_sec) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="时间" min-width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.success && row.review_id"
              size="small"
              type="primary"
              link
              @click="retryStat(row)"
            >
              重试
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="historyPage"
        v-model:page-size="historySize"
        :total="history.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="loadHistory"
        @size-change="loadHistory"
        class="pagination"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Refresh, Setting, Plus, DataLine, CircleCheck, CircleClose, Timer, List, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAutoReviewConfig,
  updateAutoReviewConfig,
  getAutoReviewStats,
  listAutoReviewHistory,
  retryFailedAutoReview,
} from '../../api/autoReview'

// 配置数据
const config = ref(null)
const loadingConfig = ref(true)
const saving = ref(false)

// 表单数据
const form = reactive({
  enabled: false,
  require_content_safe: true,
  require_steps_first_success: true,
  keyword_whitelist: [],
})
const keywordInput = ref('')

// 统计数据
const stats = ref(null)
const loadingStats = ref(true)
const dateRange = ref(null)

// 历史数据
const history = ref({ total: 0, list: [] })
const loadingHistory = ref(true)
const historyPage = ref(1)
const historySize = ref(20)
const historyFilter = ref(null)

const loadingAll = ref(false)

// 加载配置
async function loadConfig() {
  loadingConfig.value = true
  try {
    const res = await getAutoReviewConfig()
    config.value = res
    form.enabled = res.enabled
    form.require_content_safe = res.require_content_safe
    form.require_steps_first_success = res.require_steps_first_success
    form.keyword_whitelist = res.keyword_whitelist || []
  } catch (err) {
    ElMessage.error('加载配置失败：' + (err.message || '未知错误'))
  } finally {
    loadingConfig.value = false
  }
}

// 保存配置
async function saveConfig() {
  saving.value = true
  try {
    const res = await updateAutoReviewConfig({
      enabled: form.enabled,
      require_content_safe: form.require_content_safe,
      require_steps_first_success: form.require_steps_first_success,
      keyword_whitelist: form.keyword_whitelist,
    })
    config.value = res
    ElMessage.success('配置已保存，下次工作流创建审核记录时按新配置判定')
  } catch (err) {
    ElMessage.error('保存失败：' + (err.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

// 关键词管理
function addKeyword() {
  const kw = keywordInput.value.trim()
  if (!kw) return
  if (form.keyword_whitelist.includes(kw)) {
    ElMessage.warning('关键词已存在')
    return
  }
  form.keyword_whitelist.push(kw)
  keywordInput.value = ''
}

function removeKeyword(idx) {
  form.keyword_whitelist.splice(idx, 1)
}

// 加载统计
async function loadStats() {
  loadingStats.value = true
  try {
    const params = {}
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await getAutoReviewStats(params)
    stats.value = res
  } catch (err) {
    ElMessage.error('加载统计失败：' + (err.message || '未知错误'))
  } finally {
    loadingStats.value = false
  }
}

// 加载历史
async function loadHistory() {
  loadingHistory.value = true
  try {
    const params = {
      page: historyPage.value,
      size: historySize.value,
    }
    if (historyFilter.value !== null) {
      params.success = historyFilter.value
    }
    const res = await listAutoReviewHistory(params)
    history.value = res
  } catch (err) {
    ElMessage.error('加载历史失败：' + (err.message || '未知错误'))
  } finally {
    loadingHistory.value = false
  }
}

// 重试失败的自动审批
async function retryStat(row) {
  try {
    await ElMessageBox.confirm(
      `确认重试 workflow_id=${row.workflow_id} 的自动审批？仅当审核记录仍为 pending 时才会执行。`,
      '重试确认',
      { type: 'warning', confirmButtonText: '确认重试', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  try {
    const res = await retryFailedAutoReview(row.id)
    if (res.auto_approved) {
      ElMessage.success('重试成功，节目已自动发布')
    } else {
      ElMessage.warning('重试未触发自动审批：' + (res.reason || '不满足条件'))
    }
    // 刷新统计与历史
    await Promise.all([loadStats(), loadHistory()])
  } catch (err) {
    ElMessage.error('重试失败：' + (err.message || '未知错误'))
  }
}

// 加载全部
async function loadAll() {
  loadingAll.value = true
  await Promise.all([loadConfig(), loadStats(), loadHistory()])
  loadingAll.value = false
}

// 格式化辅助函数
function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function formatPercent(rate) {
  if (rate == null) return '-'
  return (rate * 100).toFixed(1) + '%'
}

function formatDuration(sec) {
  if (sec == null) return '-'
  if (sec < 60) return `${sec} 秒`
  if (sec < 3600) return `${Math.floor(sec / 60)} 分 ${sec % 60} 秒`
  return `${Math.floor(sec / 3600)} 时 ${Math.floor((sec % 3600) / 60)} 分`
}

function formatRules(reasonJson) {
  if (!reasonJson) return '-'
  try {
    const rules = JSON.parse(reasonJson)
    if (Array.isArray(rules)) {
      return rules.join('、')
    }
    return reasonJson
  } catch {
    return reasonJson
  }
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.auto-review-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
}

.section-header .header-icon {
  font-size: 18px;
  color: var(--el-color-primary);
}

.switch-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding: 8px 0;
}

.switch-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.switch-label {
  font-weight: 500;
}

.text-muted {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.text-error {
  color: var(--el-color-danger);
}

.keyword-input-wrap {
  display: flex;
  gap: 8px;
  width: 100%;
}

.keyword-tags {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.keyword-tag {
  max-width: 240px;
}

.date-range-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 16px 0;
}

.stat-card {
  padding: 16px;
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.stat-icon {
  font-size: 20px;
  color: var(--el-color-primary);
}

.success-icon {
  color: var(--el-color-success);
}

.fail-icon {
  color: var(--el-color-danger);
}

.time-icon {
  color: var(--el-color-warning);
}

.stat-title {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
}

.stat-detail {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.fail-dist-card {
  margin-top: 16px;
  padding: 16px;
}

.fail-dist-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.fail-dist-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.fail-dist-list li:last-child {
  border-bottom: none;
}

.fail-reason {
  color: var(--el-color-danger);
  font-size: 13px;
}

.history-section {
  padding: 16px;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
