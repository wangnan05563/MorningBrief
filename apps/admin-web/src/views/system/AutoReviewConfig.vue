<template>
  <div class="page-container auto-review-page">
    <!-- 顶部工具栏（T00811：移除与导航栏重复的页面标题） -->
    <div class="toolbar">
      <IconButton
        label="刷新"
        desc="重新加载配置、统计与历史"
        :icon="Refresh"
        :loading="loadingAll"
        @click="loadAll"
      />
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
                开启后，工作流完成时按下方校验逐项检查，全部命中的稿件将跳过人工审核直接发布
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

        <el-divider content-position="left">
          触发条件（默认全部校验；关闭即跳过，至少保留一条）
        </el-divider>

        <el-form-item>
          <div class="switch-row">
            <div class="switch-meta">
              <span class="switch-label">内容安全检测通过</span>
              <span class="text-muted">
                要求 rewrite 步骤的微信 msgSecCheck 结果为 safe
              </span>
              <span v-if="!form.require_content_safe" class="skip-warn">
                已关闭：本项不再检查，命中即放行
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
              <span v-if="!form.require_steps_first_success" class="skip-warn">
                已关闭：本项不再检查，命中即放行
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
            <IconButton
              label="添加"
              desc="将输入的关键词加入白名单"
              :icon="Plus"
              @click="addKeyword"
            />
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
            <span v-if="!form.keyword_whitelist.length" class="skip-warn">
              未配置关键词：本项不检查
            </span>
          </div>
        </el-form-item>

        <!-- T02492 / FR-UX-204：护栏提示——生效/跳过的校验一眼可见 -->
        <el-form-item v-if="form.enabled">
          <div class="rule-summary">
            <span class="text-muted">本次生效：</span>
            <el-tag v-for="r in enforcedNow" :key="r" size="small" type="success" effect="plain">
              {{ ruleLabel(r) }}
            </el-tag>
            <span v-if="!enforcedNow.length" class="skip-warn">
              无（三条校验全部关闭，不能开启）
            </span>
            <template v-if="skippedNow.length">
              <span class="text-muted">跳过：</span>
              <el-tag v-for="r in skippedNow" :key="r" size="small" type="danger" effect="plain">
                {{ ruleLabel(r) }}
              </el-tag>
            </template>
          </div>
        </el-form-item>

        <!-- 风险确认：首次开启或跳过项发生变化时必须重新勾选 -->
        <el-form-item v-if="form.enabled && needsAck">
          <el-checkbox v-model="riskAck" data-testid="risk-ack">
            我已确认风险：勾选后，命中剩余校验的稿件将<b>不经人工审核自动发布</b>
            <template v-if="skippedNow.length">
              ，且{{ skippedNow.map(ruleLabel).join('、') }}已被跳过
            </template>
            。
          </el-checkbox>
          <div v-if="config?.risk_acknowledged_at" class="ack-history text-muted">
            上次确认：{{ formatTime(config.risk_acknowledged_at) }}（{{ config.risk_acknowledged_by || '未知' }}）
          </div>
        </el-form-item>

        <el-form-item>
          <IconButton
            type="primary"
            :loading="saving"
            label="保存配置"
            desc="保存自动审批规则配置"
            :icon="Check"
            @click="saveConfig"
          />
        </el-form-item>
      </el-form>
    </div>

    <!-- 统计指标卡片 -->
      <div class="stats-section" v-loading="loadingStats">
        <el-row :gutter="16">
          <!-- 响应式栅格：窄视口(<1200)自动 2 列，避免 4 列卡片被压得过窄（原 span=6 固定四列）
               在 1366 屏 + 125% 缩放等场景下被挤压换行/文字截断 -->
          <el-col :xs="12" :sm="12" :md="12" :lg="6">
          <div class="card-soft stat-card">
            <div class="stat-header">
              <el-icon class="stat-icon"><DataLine /></el-icon>
              <span class="stat-title">总尝试</span>
            </div>
            <div class="stat-value">{{ stats?.total ?? 0 }}</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="12" :md="12" :lg="6">
          <div class="card-soft stat-card">
            <div class="stat-header">
              <el-icon class="stat-icon success-icon"><CircleCheck /></el-icon>
              <span class="stat-title">成功数</span>
            </div>
            <div class="stat-value">{{ stats?.success_count ?? 0 }}</div>
            <div class="stat-detail">成功率 {{ formatPercent(stats?.success_rate) }}</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="12" :md="12" :lg="6">
          <div class="card-soft stat-card">
            <div class="stat-header">
              <el-icon class="stat-icon fail-icon"><CircleClose /></el-icon>
              <span class="stat-title">失败数</span>
            </div>
            <div class="stat-value">{{ stats?.failed_count ?? 0 }}</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="12" :md="12" :lg="6">
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
            <span v-if="row.success">{{ formatTriggerReason(row.trigger_reason) }}</span>
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
            <IconButton
              v-if="!row.success && row.review_id"
              size="small"
              type="primary"
              link
              :loading="retryingStat === row.workflow_id"
              label="重试"
              desc="重新执行该失败的自动审批"
              :icon="Refresh"
              @click="retryStat(row)"
            />
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无审批记录" :image-size="90" /></template>
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
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useDraft } from '../../composables/useDraft'
import { Refresh, Setting, Plus, DataLine, CircleCheck, CircleClose, Timer, List, WarningFilled, Check } from '@element-plus/icons-vue'
// 提示必须走统一出口：直接从 element-plus 取 ElMessage 会绕过 2 秒去重与
// 「隐藏期间不入 DOM」的窗口守卫（FR-UX-301/303）
import { ElMessage, ElMessageBox } from '../../utils/message'
import {
  getAutoReviewConfig,
  updateAutoReviewConfig,
  getAutoReviewStats,
  listAutoReviewHistory,
  retryFailedAutoReview,
} from '../../api/autoReview'
import { ruleLabel, formatTriggerReason } from '../../utils/autoReviewRules'

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
// T00828：断点续录——表单变化自动持久化，重新进入恢复
const { apply: applyDraft, track: trackDraft, commit: commitDraft } = useDraft('auto-review-config')
const enableDraft = trackDraft(form)
const keywordInput = ref('')

// T02492 / FR-UX-204：风险确认勾选——刻意不放进 form，避免断点续录把上次的勾选恢复出来
// （恢复即等于替管理员预先确认，护栏失效）
const riskAck = ref(false)

const RULE_ORDER = ['content_safe', 'steps_first_success', 'keyword_whitelist']

// 与后端 split_rules 同口径：关闭的开关 + 空白名单 = 该校验被显式跳过
const skippedNow = computed(() => {
  const skipped = []
  if (!form.require_content_safe) skipped.push('content_safe')
  if (!form.require_steps_first_success) skipped.push('steps_first_success')
  if (!form.keyword_whitelist.length) skipped.push('keyword_whitelist')
  return skipped
})
const enforcedNow = computed(() => RULE_ORDER.filter((r) => !skippedNow.value.includes(r)))

// 需要重新确认风险：首次开启，或跳过的校验比服务端已保存的更多（风险面扩大）
// 与服务端 ack_carried 同口径，两侧判断保持一致才不会保存被 400 打回
const needsAck = computed(() => {
  if (!form.enabled) return false
  const saved = config.value
  const savedSkipped = saved?.skipped_rules || []
  const carried = saved?.enabled && saved?.risk_acknowledged
    && skippedNow.value.every((r) => savedSkipped.includes(r))
  return !carried
})

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

// 风险面发生变化（跳过项增减 / 需要重新确认）时清空勾选，避免沿用旧确认
watch(
  () => `${needsAck.value}|${skippedNow.value.join(',')}`,
  () => { riskAck.value = false },
)

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
  // 前端预拦截与服务端护栏同口径：全关、未确认风险都不放行，
  // 让用户在当前界面就看到原因，而不是等一个 400 弹窗
  if (form.enabled && !enforcedNow.value.length) {
    ElMessage.error('三条校验全部关闭时不能开启自动审批：至少保留一条校验')
    return
  }
  if (form.enabled && needsAck.value && !riskAck.value) {
    ElMessage.error('请先勾选风险确认，再开启自动审批')
    return
  }
  saving.value = true
  try {
    const res = await updateAutoReviewConfig({
      enabled: form.enabled,
      require_content_safe: form.require_content_safe,
      require_steps_first_success: form.require_steps_first_success,
      keyword_whitelist: form.keyword_whitelist,
      risk_acknowledged: riskAck.value,
    })
    config.value = res
    ElMessage.success('配置已保存，下次工作流创建审核记录时按新配置判定')
    commitDraft()
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
const retryingStat = ref('')
async function retryStat(row) {
  retryingStat.value = row.workflow_id
  try {
    await ElMessageBox.confirm(
      `确认重试 workflow_id=${row.workflow_id} 的自动审批？仅当审核记录仍为 pending 时才会执行。`,
      '重试确认',
      { type: 'warning', confirmButtonText: '确认重试', cancelButtonText: '取消' }
    )
  } catch {
    retryingStat.value = ''
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
  } finally {
    retryingStat.value = ''
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

onMounted(async () => {
  await loadAll()
  // T00828：加载完成后恢复草稿再启用持久化
  applyDraft(form)
  enableDraft()
})
</script>

<style scoped>
.auto-review-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 规则配置、统计区与同级卡片统一内边距，避免字段/开关/按钮贴卡片边缘（T00920 布局修复） */
.config-section,
.stats-section {
  padding: 16px;
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

/* T02492：关闭即跳过的校验用告警色显式提示，避免「看起来还在检查」 */
.skip-warn {
  color: var(--el-color-warning);
  font-size: 13px;
}

.rule-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.ack-history {
  margin-top: 4px;
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
  /* 窄视口下日期选择器(固定较宽)+统计文本并排会溢出容器，允许换行 */
  flex-wrap: wrap;
}

.stat-card {
  padding: 16px;
  /* 响应式 2 列时卡片分两行，底部间距避免与下行卡片紧贴 */
  margin-bottom: 16px;
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
