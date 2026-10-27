<template>
  <div data-guide="maintenance-page" class="page-container maintenance-page">
    <!-- 顶部工具栏（T00811：移除与导航栏重复的页面标题） -->
    <div class="toolbar">
      <IconButton
        label="刷新状态"
        desc="重新拉取存储状态"
        :icon="Refresh"
        :loading="loadingStatus"
        @click="loadStatus"
      />
    </div>

    <!-- M71（FR-UX-302）：status 已有旧值时不能声称「数据未加载」，
         要靠 stale 把口径改成「下方为上次成功加载的数据，可能已过期」。 -->
    <ListLoadError
      v-if="statusError"
      :message="statusError"
      :retrying="retryingStatus"
      :stale="!!status"
      @retry="retryLoadStatus"
    />
    <p v-if="statusError && status && lastSuccessAt" class="status-stamp">
      上次成功获取：{{ lastSuccessAt.toLocaleTimeString() }}
    </p>

    <!-- 存储状态卡片 -->
    <!-- M71：只在真的拿到过 status 时才渲染。首次加载失败时 status 为 null，卡片会用
         `?? 0` 把「不知道」写成「数据库 0 条日志、无需清理」——错误态与假干净同时在场，
         用户读到的仍是那句断言。二次失败时 status 有旧值，卡片保留、由 stale 错误态说明过期。 -->
    <div v-if="status" class="status-section" v-loading="loadingStatus">
      <el-row :gutter="16">
        <el-col :span="8">
          <div class="card-soft stat-card">
            <div class="stat-header">
              <el-icon class="stat-icon db-icon"><Coin /></el-icon>
              <span class="stat-title">数据库</span>
            </div>
            <div class="stat-value">{{ formatMb(status?.db?.db_size_mb) }}</div>
            <div class="stat-detail">
              <span>播放日志 {{ status?.db?.playlog_count ?? 0 }} 条</span>
              <span>工作流 {{ status?.db?.workflow_count ?? 0 }} 条</span>
              <span>审核 {{ status?.db?.review_count ?? 0 }} 条</span>
              <span>黑名单 {{ status?.db?.blacklist_count ?? 0 }} 条</span>
            </div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="card-soft stat-card">
            <div class="stat-header">
              <el-icon class="stat-icon log-icon"><Document /></el-icon>
              <span class="stat-title">日志文件</span>
            </div>
            <div class="stat-value">{{ formatMb(status?.logs?.total_size_mb) }}</div>
            <div class="stat-detail">
              <span>文件数 {{ status?.logs?.file_count ?? 0 }} 个</span>
              <span v-if="status?.logs?.oldest">最早 {{ status.logs.oldest }}</span>
            </div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="card-soft stat-card">
            <div class="stat-header">
              <el-icon class="stat-icon cache-icon"><Cpu /></el-icon>
              <span class="stat-title">缓存</span>
            </div>
            <div class="stat-value">{{ status?.cache?.ttlcache_count ?? 0 }} 条</div>
            <div class="stat-detail">
              <span>PyCache {{ status?.cache?.pycache_count ?? 0 }} 目录</span>
              <span>临时文件 {{ status?.cache?.temp_files ?? 0 }} 个</span>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 三列清理卡片 -->
    <el-row :gutter="16" class="cleanup-section">
      <!-- 缓存清理 -->
      <el-col :span="8">
        <div class="card-soft cleanup-card">
          <div class="card-header">
            <el-icon class="header-icon cache-icon"><Cpu /></el-icon>
            <span>缓存清理</span>
          </div>
          <el-form data-guide="maintenance-form" :model="cacheForm" label-position="top" class="cleanup-form">
            <el-form-item label="清理目标">
              <el-select v-model="cacheForm.target" style="width: 100%">
                <el-option label="全部缓存" value="all" />
                <el-option label="TTLCache（进程内缓存）" value="ttlcache" />
                <el-option label="__pycache__ 目录" value="pycache" />
                <el-option label="临时文件" value="temp" />
              </el-select>
            </el-form-item>
            <el-form-item label="预览模式">
              <div class="dry-run-wrap">
                <el-switch v-model="cacheForm.dry_run" />
                <el-tag v-if="!cacheForm.dry_run" type="danger" size="small" effect="dark">
                  将执行真实删除
                </el-tag>
                <span v-else class="text-muted">仅预览，不实际删除</span>
              </div>
            </el-form-item>
            <el-form-item>
              <IconButton
                :type="cacheForm.dry_run ? 'primary' : 'danger'"
                :loading="cacheLoading || isTaskActive('cache')"
                :label="cacheForm.dry_run ? '预览清理' : '立即执行清理'"
                :inline-text="cacheForm.dry_run ? '预览清理' : '立即执行清理（不可恢复）'"
                :desc="cacheForm.dry_run ? '仅预览，不实际删除' : '执行真实删除，不可恢复'"
                :icon="Delete"
                @click="handleCleanup('cache')"
              />
            </el-form-item>
          </el-form>
          <TaskProgress
            v-if="tasks.cache"
            :task="tasks.cache"
            :target-label="targetLabel('cache', tasks.cache.target)"
          />
          <CleanupResult v-if="cacheResult" :result="cacheResult" />
        </div>
      </el-col>

      <!-- 数据库清理 -->
      <el-col :span="8">
        <div class="card-soft cleanup-card">
          <div class="card-header">
            <el-icon class="header-icon db-icon"><Coin /></el-icon>
            <span>数据库清理</span>
          </div>
          <el-form :model="dbForm" label-position="top" class="cleanup-form">
            <el-form-item label="清理目标">
              <el-select v-model="dbForm.target" style="width: 100%">
                <el-option label="全部清理（不含无主素材治理）" value="all" />
                <el-option label="旧播放日志" value="old_playlogs" />
                <el-option label="旧工作流记录" value="old_workflows" />
                <el-option label="旧审核记录（已完结）" value="old_reviews" />
                <el-option label="过期 JWT 黑名单" value="expired_blacklist" />
                <el-option label="旧爬虫去重记录" value="old_dedup" />
                <el-option label="旧 AI 用量日志" value="old_ai_usage" />
                <el-option label="VACUUM 压缩" value="vacuum" />
                <el-option label="指定工作流全链清理" value="workflow_chain" />
                <el-option label="无主素材解绑（保留正文）" value="orphan_materials_detach" />
                <el-option label="无主素材删除（连正文删）" value="orphan_materials_delete" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="orphanAction" label="无主素材">
              <div class="form-tip">
                指 channel_id 仍写着某个频道、但该频道已被删除的素材行（旧版删频道没有解绑留下的存量，T02598）。
                「解绑」只清空归属、正文保留并回到全局素材池；「删除」连正文一起删。
                先按「预览清理」确认条数与样例 ID，再执行。
              </div>
            </el-form-item>
            <el-form-item v-if="isWorkflowChain" label="工作流 ID">
              <el-input
                v-model="dbForm.workflow_id"
                clearable
                placeholder="粘贴工作流 ID"
              />
              <div class="form-tip">
                仅 success / failed / cancelled 状态的工作流允许清理；运行中会被拒绝
              </div>
            </el-form-item>
            <el-form-item v-if="showDbDays" label="保留天数">
              <el-input-number
                v-model="dbForm.days"
                :min="1"
                :max="365"
                style="width: 100%"
              />
              <div class="form-tip">清理超过此天数的记录（1-365）</div>
            </el-form-item>
            <el-form-item label="预览模式">
              <div class="dry-run-wrap">
                <el-switch v-model="dbForm.dry_run" />
                <el-tag v-if="!dbForm.dry_run" type="danger" size="small" effect="dark">
                  将执行真实删除
                </el-tag>
                <span v-else class="text-muted">仅预览，不实际删除</span>
              </div>
            </el-form-item>
            <el-form-item>
              <IconButton
                :type="dbForm.dry_run ? 'primary' : 'danger'"
                :loading="dbLoading || isTaskActive('database')"
                :label="dbForm.dry_run ? '预览清理' : '立即执行清理'"
                :inline-text="dbForm.dry_run ? '预览清理' : '立即执行清理（不可恢复）'"
                :desc="dbForm.dry_run ? '仅预览，不实际删除' : '执行真实删除，不可恢复'"
                :icon="Delete"
                @click="handleCleanup('database')"
              />
            </el-form-item>
          </el-form>
          <TaskProgress
            v-if="tasks.database"
            :task="tasks.database"
            :target-label="targetLabel('database', tasks.database.target)"
          />
          <CleanupResult v-if="dbResult" :result="dbResult" />
        </div>
      </el-col>

      <!-- 日志清理 -->
      <el-col :span="8">
        <div class="card-soft cleanup-card">
          <div class="card-header">
            <el-icon class="header-icon log-icon"><Document /></el-icon>
            <span>日志清理</span>
          </div>
          <el-form :model="logForm" label-position="top" class="cleanup-form">
            <el-form-item label="清理目标">
              <el-select v-model="logForm.target" style="width: 100%">
                <el-option label="全部清理" value="all" />
                <el-option label="旧日志文件（按天数）" value="old_logs" />
                <el-option label="大日志文件（>10MB）" value="large_logs" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="showLogDays" label="保留天数">
              <el-input-number
                v-model="logForm.days"
                :min="1"
                :max="365"
                style="width: 100%"
              />
              <div class="form-tip">清理超过此天数的日志文件（1-365）</div>
            </el-form-item>
            <el-form-item label="预览模式">
              <div class="dry-run-wrap">
                <el-switch v-model="logForm.dry_run" />
                <el-tag v-if="!logForm.dry_run" type="danger" size="small" effect="dark">
                  将执行真实删除
                </el-tag>
                <span v-else class="text-muted">仅预览，不实际删除</span>
              </div>
            </el-form-item>
            <el-form-item>
              <IconButton
                :type="logForm.dry_run ? 'primary' : 'danger'"
                :loading="logLoading || isTaskActive('logs')"
                :label="logForm.dry_run ? '预览清理' : '立即执行清理'"
                :inline-text="logForm.dry_run ? '预览清理' : '立即执行清理（不可恢复）'"
                :desc="logForm.dry_run ? '仅预览，不实际删除' : '执行真实删除，不可恢复'"
                :icon="Delete"
                @click="handleCleanup('logs')"
              />
            </el-form-item>
          </el-form>
          <TaskProgress
            v-if="tasks.logs"
            :task="tasks.logs"
            :target-label="targetLabel('logs', tasks.logs.target)"
          />
          <CleanupResult v-if="logResult" :result="logResult" />
        </div>
      </el-col>
    </el-row>

    <!-- T02909：清理是 irreversible 的高危动作，最近几次「谁清的、清了什么」得在本页读得到 -->
    <AuditTrail category="maintenance" guide="maintenance-audit" title="最近清理审计" />

    <!-- 使用说明 -->
    <el-alert type="info" :closable="false" show-icon class="alert-block">
      <template #title>使用说明</template>
      <ol class="usage-list">
        <li>建议先用「预览模式」查看将清理的内容，确认无误后关闭预览再执行</li>
        <li>数据库清理的「保留天数」仅对按时间清理的目标生效（VACUUM 和过期黑名单除外）</li>
        <li>审核记录仅清理已完结状态（approved/rejected/replaced），pending 状态不会被清理</li>
        <li>工作流记录仅清理已完结状态（success/failed/cancelled），running 状态不会被清理</li>
        <li>「指定工作流全链清理」按工作流 ID 删除其稿件/节目/审核/播放数据等子表，运行中的工作流会被拒绝</li>
        <li>「立即执行清理」会提交后台任务并立刻返回：这里显示任务进度，结束后自动刷新存储状态；执行期间数据库可能被锁定，其他操作会变慢</li>
        <li>VACUUM 会锁定数据库直到压缩完成，建议在低峰期执行</li>
        <li class="text-muted">注意：清理操作不可逆，请谨慎操作</li>
      </ol>
    </el-alert>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import { ElMessage } from '../../utils/message'
import {
  Refresh, Coin, Document, Cpu, Delete,
} from '@element-plus/icons-vue'
import api from '../../api'
import { getMaintenanceTask } from '../../api/maintenance'
import { MAINTENANCE_TASK_STATE } from '../../constants/enums'
import ListLoadError from '../../components/ListLoadError.vue'
import AuditTrail from '../../components/AuditTrail.vue'
import { dangerConfirmWithReason } from '../../utils/dangerConfirm'
import { LONG_TASK_TIMEOUT_MS, isRequestTimeout, longTaskTimeoutText } from '../../utils/requestTimeout'

// 确认文案要给出中文对象名，英文 target 值只用于请求参数（M59）
const CATEGORY_NAMES = { cache: '缓存清理', database: '数据库清理', logs: '日志清理' }
const TARGET_LABELS = {
  all: '全部', ttlcache: 'TTLCache（进程内缓存）', pycache: '__pycache__ 目录', temp: '临时文件',
  old_playlogs: '旧播放日志', old_workflows: '旧工作流记录', old_reviews: '旧审核记录（已完结）',
  expired_blacklist: '过期 JWT 黑名单', old_dedup: '旧爬虫去重记录', old_ai_usage: '旧 AI 用量日志',
  vacuum: 'VACUUM 压缩', old_logs: '旧日志文件', large_logs: '大日志文件（>10MB）',
  workflow_chain: '指定工作流全链清理',
  orphan_materials_detach: '无主素材解绑', orphan_materials_delete: '无主素材删除',
}
const CATEGORY_TARGETS = {
  cache: ['all', 'ttlcache', 'pycache', 'temp'],
  database: ['all', 'old_playlogs', 'old_workflows', 'old_reviews', 'expired_blacklist', 'old_dedup', 'old_ai_usage', 'vacuum', 'workflow_chain',
    'orphan_materials_detach', 'orphan_materials_delete'],
  logs: ['all', 'old_logs', 'large_logs'],
}
// 不按天数执行的数据库目标（解绑/删除都只按「channel_id 悬空」这一个条件筛）
const DB_TARGETS_NO_DAYS = ['vacuum', 'expired_blacklist', 'workflow_chain',
  'orphan_materials_detach', 'orphan_materials_delete']
function targetLabel(category, target) {
  const known = (CATEGORY_TARGETS[category] || []).includes(target)
  return known ? `${TARGET_LABELS[target] || target}（${target}）` : target
}
function showDays(category, form) {
  if (category === 'cache') return false
  if (category === 'logs') return form.target !== 'large_logs'
  return !DB_TARGETS_NO_DAYS.includes(form.target)
}

const CleanupResult = {
  props: ['result'],
  setup(props) {
    return () => {
      const { cleaned, errors } = props.result
      const hasErrors = errors && errors.length > 0
      return h('div', { class: 'cleanup-result' }, [
        cleaned && cleaned.length > 0
          ? h('div', { class: 'result-success' }, [
              h('div', { class: 'result-title' }, '清理结果：'),
              ...cleaned.map((item) => h('div', { class: 'result-item' }, item)),
            ])
          : null,
        hasErrors
          ? h('div', { class: 'result-error' }, [
              h('div', { class: 'result-title' }, '错误信息：'),
              ...errors.map((item) => h('div', { class: 'result-item' }, item)),
            ])
          : null,
        !cleaned?.length && !hasErrors
          ? h('div', { class: 'result-empty' }, '无需清理')
          : null,
      ])
    }
  },
}

// 后台任务进度（T02799）：非预览执行不再等 HTTP 响应，改为「提交 → 轮询状态」。
// 轮询间隔 2s：任务本身是分钟级，2s 足够让「已提交 / 执行中 / 已完成」的状态可信，
// 又不会把这个页面变成压力源（这是任务态轮询，替代的正是原来那条挂 300s 的连接）。
const TASK_POLL_INTERVAL_MS = 2000
const TASK_TERMINAL_STATES = ['succeeded', 'failed']
const TASK_LOCK_HINT = '执行期间数据库可能被锁定，其他操作会变慢'

const TaskProgress = {
  props: ['task', 'targetLabel'],
  setup(props) {
    return () => {
      const task = props.task
      if (!task) return null
      const terminal = TASK_TERMINAL_STATES.includes(task.state)
      return h('div', {
        class: 'task-progress',
        'data-guide': 'maintenance-task-progress',
      }, [
        h('div', { class: 'task-progress__head' }, [
          h('span', { class: ['task-state', `is-${task.state}`] },
            MAINTENANCE_TASK_STATE[task.state]?.label || task.state),
          h('span', { class: 'task-progress__meta' },
            `目标：${props.targetLabel}`),
          task.elapsed_ms != null
            ? h('span', { class: 'task-progress__meta' },
                `已耗时 ${(task.elapsed_ms / 1000).toFixed(1)} 秒`)
            : null,
        ]),
        task.merged && !terminal
          ? h('div', { class: 'task-progress__merged' },
              '该目标已有任务在执行：这里跟踪的是同一个任务，不会再跑第二份')
          : null,
        h('div', { class: 'task-progress__hint' }, TASK_LOCK_HINT),
        task.pollError
          ? h('div', { class: 'task-progress__warn' }, task.pollError)
          : null,
        task.state === 'failed'
          ? h('div', { class: 'result-error' }, task.error || '清理任务执行失败')
          : null,
      ])
    }
  },
}

// 存储状态
const status = ref(null)
const loadingStatus = ref(true)
// M71（FR-UX-302）：状态接口失败要能在页内看见。此前 catch 只 console.error，
// status 为 null 时三卡显示 `-` 与「0 条 / 0 个」＝「数据库很干净、无需清理」；
// 二次刷新失败时更糟：旧数值继续挂着且没有任何过期标记。
const statusError = ref('')
const retryingStatus = ref(false)
const lastSuccessAt = ref(null)

// 三个表单状态（互不干扰）
const cacheForm = ref({ target: 'all', dry_run: true })
const dbForm = ref({ target: 'all', days: 30, dry_run: true, workflow_id: '' })
const logForm = ref({ target: 'old_logs', days: 7, dry_run: true })

// 清理结果
const cacheResult = ref(null)
const dbResult = ref(null)
const logResult = ref(null)

// 加载状态
const cacheLoading = ref(false)
const dbLoading = ref(false)
const logLoading = ref(false)

// 后台任务状态（每个分类各自跟踪；同一 target 重复提交由后端合并）
const tasks = ref({ cache: null, database: null, logs: null })
const taskTimers = { cache: null, database: null, logs: null }

function isTaskActive(category) {
  const task = tasks.value[category]
  return !!task && !TASK_TERMINAL_STATES.includes(task.state)
}

function scheduleTaskPoll(category, taskId) {
  clearTimeout(taskTimers[category])
  taskTimers[category] = setTimeout(() => pollTask(category, taskId), TASK_POLL_INTERVAL_MS)
}

async function pollTask(category, taskId) {
  const current = tasks.value[category]
  // 任务被新提交替换或页面已离开：这一轮作废，避免旧响应覆盖新状态
  if (!current || current.task_id !== taskId) return
  try {
    const data = await getMaintenanceTask(taskId)
    tasks.value[category] = {
      ...data,
      merged: current.merged,
      pollFailures: 0,
      pollError: '',
    }
    if (TASK_TERMINAL_STATES.includes(data.state)) {
      finishTask(category, data)
      return
    }
  } catch (error) {
    // 取不到进度 ≠ 任务失败：后台照常执行，继续按间隔重试；
    // 连续失败才提示，避免一次抖动就把「正在执行」说成「出错了」。
    const failures = (current.pollFailures || 0) + 1
    tasks.value[category] = {
      ...current,
      pollFailures: failures,
      pollError: failures >= 3
        ? `已连续 ${failures} 次取不到任务进度（${error?.message || '请求失败'}）；后台任务不受影响，仍在重试`
        : '',
    }
  }
  scheduleTaskPoll(category, taskId)
}

async function finishTask(category, data) {
  const loadingRefs = { cache: cacheLoading, database: dbLoading, logs: logLoading }
  const resultRefs = { cache: cacheResult, database: dbResult, logs: logResult }
  loadingRefs[category].value = false
  if (data.state === 'succeeded') {
    resultRefs[category].value = data.result
    ElMessage.success('清理完成')
    // 任务结束再刷新存储状态：执行中就刷只会拿到被锁住的旧值
    await loadStatus()
  } else {
    ElMessage.error(data.error || '清理任务执行失败')
  }
}

// VACUUM / expired_blacklist / 指定工作流全链清理 / 无主素材治理都不按天数执行
const showDbDays = computed(
  () => !DB_TARGETS_NO_DAYS.includes(dbForm.value.target)
)
const isWorkflowChain = computed(() => dbForm.value.target === 'workflow_chain')
// 无主素材的两个治理口径（T02598）：null 表示当前目标不是无主素材
const orphanAction = computed(() => {
  const target = dbForm.value.target
  return target === 'orphan_materials_detach' || target === 'orphan_materials_delete'
    ? target.replace('orphan_materials_', '')
    : null
})
// large_logs 不需要天数输入
const showLogDays = computed(() => logForm.value.target !== 'large_logs')

// 格式化 MB 显示
function formatMb(mb) {
  if (mb == null) return '-'
  if (mb < 1) return `${(mb * 1024).toFixed(1)} KB`
  return `${mb.toFixed(2)} MB`
}

// 加载存储状态
async function loadStatus() {
  loadingStatus.value = true
  try {
    status.value = await api.get('/maintenance/status')
    statusError.value = ''
    lastSuccessAt.value = new Date()
  } catch (error) {
    // M71（FR-UX-302）：此前这里只 console.error —— status 为 null 时三卡显示 `-` 与
    // 「0 条 / 0 个」，运维读成「数据库 0 条日志、无需清理」；若是二次刷新失败，
    // 更糟的是继续展示上一次的旧数值且没有任何过期标记。
    // 现在：失败即置错误态，旧值保留但由 stale 标记说明「可能是过期的」。
    statusError.value = error?.message || '存储状态接口请求失败'
  } finally {
    loadingStatus.value = false
    retryingStatus.value = false
  }
}

// M71：重试按钮走同一条 loadStatus；成功后错误态与 spinner 一起清掉
function retryLoadStatus() {
  retryingStatus.value = true
  return loadStatus()
}

// 执行清理
async function handleCleanup(category) {
  const formMap = { cache: cacheForm, database: dbForm, logs: logForm }
  const loadingMap = { cache: cacheLoading, database: dbLoading, logs: logLoading }
  const resultMap = { cache: cacheResult, database: dbResult, logs: logResult }

  const form = formMap[category].value
  const loading = loadingMap[category]
  const result = resultMap[category]

  // 指定工作流全链清理：本地前置校验（不发请求），后续走独立端点
  const chain = category === 'database' && form.target === 'workflow_chain'
  const workflowId = chain ? form.workflow_id.trim() : ''
  if (chain && !workflowId) {
    ElMessage.error('请填写要清理的工作流 ID')
    return
  }
  // 无主素材治理（T02598）：只按「channel_id 悬空」这一个条件筛，没有天数语义
  const orphan = category === 'database' ? orphanAction.value : null

  // 非预览模式二次确认：写清删什么、保留多久、预览到多少条、能否恢复（M59）
  let cleanupReason = ''
  if (!form.dry_run) {
    const previewLines = result.value?.cleaned?.length
      ? [
          `上次预览命中 ${result.value.cleaned.length} 项，前 ${Math.min(5, result.value.cleaned.length)} 项：`,
          ...result.value.cleaned.slice(0, 5).map((line) => `· ${line}`),
          ...(result.value.cleaned.length > 5 ? ['…'] : []),
        ]
      : ['尚未做过 dry-run 预览，建议先切到「预览清理」确认影响范围。']
    const { confirmed, reason } = await dangerConfirmWithReason({
      action: '立即执行清理',
      target: chain
        ? `${CATEGORY_NAMES[category]} · ${targetLabel(category, form.target)} · 工作流 ${workflowId}`
        : `${CATEGORY_NAMES[category]} · ${targetLabel(category, form.target)}`,
      scope: chain
        ? '仅删除该工作流及其稿件/节目/审核/播放数据等子表，其他工作流不受影响'
        : orphan
          ? orphan === 'detach'
            ? '仅影响 channel_id 指向已删除频道的素材行：归属置空，正文保留并回到全局素材池；正常素材不受影响'
            : '仅影响 channel_id 指向已删除频道的素材行：连同正文一起删除；正常素材不受影响'
          : showDays(category, form)
            ? `仅保留最近 ${form.days} 天，早于该窗口的数据与文件会被删除`
            : '该目标不受天数条件约束',
      lines: previewLines,
      irreversible: orphan === 'detach'
        ? '解绑后认不回原频道：那个频道已经不存在，只能重新手动指定归属。'
        : '删除后不可恢复：SQLite 没有回收站，只能靠事先备份还原。',
      confirmLabel: '确认执行',
    })
    if (!confirmed) return
    cleanupReason = reason
  }

  if (isTaskActive(category)) {
    ElMessage.info('该目标的任务还在执行，请先看进度；重复提交会合并到同一个任务')
    return
  }

  loading.value = true
  result.value = null
  try {
    // 全链清理没有 days 语义，走独立端点；其余照旧按 target 走 /maintenance/{category}
    const url = chain ? '/maintenance/workflow-chain' : `/maintenance/${category}`
    const payload = chain
      ? { workflow_id: workflowId, dry_run: form.dry_run }
      : { target: form.target, dry_run: form.dry_run }
    if (!chain && !orphan && category !== 'cache') {
      payload.days = form.days
    }
    // 非预览才收起原因；预览不写库也不落审计，带过去也没人读
    if (cleanupReason) payload.reason = cleanupReason
    // 长任务专用超时（M62）：dry-run 预览是同步统计，仍可能超过全局 15s；
    // 非预览现在只落一条任务记录，正常毫秒级返回，这条超时退化成兜底。
    const data = await api.post(url, payload, {
      timeout: LONG_TASK_TIMEOUT_MS,
      // 超时提示由本页按「后端仍在执行」的口径自己给，拦截器再叠一条「timeout of ...」只会误导重复提交
      silent: true,
    })
    if (form.dry_run) {
      result.value = data
      ElMessage.success('预览完成')
      return
    }
    // 非预览：后端返回的是任务视图（task_id/state），清理结果要等任务结束再取
    tasks.value[category] = {
      ...data,
      merged: !!data.merged,
      pollFailures: 0,
      pollError: '',
    }
    if (data.merged) {
      ElMessage.info('该目标已有任务在执行，正在跟踪同一个任务')
    } else {
      ElMessage.success('已提交后台任务')
    }
    scheduleTaskPoll(category, data.task_id)
  } catch (error) {
    if (isRequestTimeout(error)) {
      // 关键区分：请求断开 ≠ 任务失败。VACUUM 仍在后端执行且占着写锁，
      // 这里必须明确禁止重复提交，而不是给一个「重试」按钮。
      ElMessage.error(longTaskTimeoutText())
    } else {
      const resp = error?.response?.data || error
      ElMessage.error(resp?.message || '清理失败')
    }
  } finally {
    // 后台任务仍在执行时按钮保持 loading 态，由轮询结束时解除
    if (form.dry_run || !isTaskActive(category)) loading.value = false
  }
}

onMounted(() => {
  loadStatus()
})

// 离开页面就停掉轮询：任务在后端继续，但前端不再空转
onUnmounted(() => {
  Object.keys(taskTimers).forEach((key) => {
    clearTimeout(taskTimers[key])
    taskTimers[key] = null
  })
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.maintenance-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .page-title {
    font-size: 20px;
    font-weight: 700;
    color: $color-text-primary;
  }
}

.status-section {
  min-height: 120px;
}

.stat-card {
  padding: 20px 24px;
  height: 100%;

  .stat-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
  }

  .stat-icon {
    font-size: 24px;

    &.db-icon { color: $color-primary-dark; }
    &.log-icon { color: $color-secondary-dark; }
    &.cache-icon { color: $color-info; }
  }

  .stat-title {
    font-size: 15px;
    font-weight: 600;
    color: $color-text-secondary;
  }

  .stat-value {
    font-size: 28px;
    font-weight: 700;
    color: $color-text-primary;
    margin-bottom: 8px;
  }

  .stat-detail {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 13px;
    color: $color-text-secondary;
  }
}

.cleanup-section {
  margin-top: 4px;
}

.cleanup-card {
  padding: 20px 24px;
  height: 100%;

  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 600;
    color: $color-text-primary;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid $color-border;

    .header-icon {
      font-size: 20px;

      &.db-icon { color: $color-primary-dark; }
      &.log-icon { color: $color-secondary-dark; }
      &.cache-icon { color: $color-info; }
    }
  }

  .cleanup-form {
    .form-tip {
      font-size: 12px;
      color: $color-text-secondary;
      margin-top: 4px;
    }

    .dry-run-wrap {
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }
}

.cleanup-result {
  margin-top: 16px;
  padding: 12px;
  border-radius: $radius-sm;
  background: $color-bg;
  font-size: 13px;

  .result-title {
    font-weight: 600;
    margin-bottom: 6px;
    color: $color-text-primary;
  }

  .result-item {
    line-height: 1.6;
    color: $color-text-secondary;
    word-break: break-all;
  }

  .result-success {
    margin-bottom: 8px;

    .result-item {
      color: $color-primary-dark;
    }
  }

  .result-error {
    .result-item {
      color: $color-secondary-dark;
    }
  }

  .result-empty {
    color: $color-text-secondary;
    text-align: center;
    padding: 8px 0;
  }
}

.task-progress {
  margin-top: 16px;
  padding: 12px;
  border-radius: $radius-sm;
  border: 1px solid $color-border;
  background: $color-bg;
  font-size: 13px;

  .task-progress__head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }

  .task-state {
    font-weight: 600;
    color: $color-text-primary;

    &.is-running { color: $color-info; }
    &.is-succeeded { color: $color-primary-dark; }
    &.is-failed { color: $color-secondary-dark; }
  }

  .task-progress__meta {
    color: $color-text-secondary;
    font-size: 12px;
  }

  .task-progress__merged,
  .task-progress__hint {
    color: $color-text-secondary;
    font-size: 12px;
    line-height: 1.6;
  }

  .task-progress__warn {
    margin-top: 6px;
    color: $color-primary-dark;
    font-size: 12px;
    line-height: 1.6;
  }

  .result-error {
    margin-top: 6px;
    color: $color-secondary-dark;
    line-height: 1.6;
    word-break: break-all;
  }
}

.alert-block {
  border-radius: $radius-lg;

  .usage-list {
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    color: $color-text-primary;

    li {
      line-height: 1.6;
    }
  }
}

.text-muted {
  color: $color-text-secondary;
  font-size: 12px;
}
</style>
