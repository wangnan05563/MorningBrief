<template>
  <div class="page-container maintenance-page">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <h2 class="page-title">系统清理</h2>
      <el-button :icon="Refresh" :loading="loadingStatus" @click="loadStatus">
        刷新状态
      </el-button>
    </div>

    <!-- 存储状态卡片 -->
    <div class="status-section" v-loading="loadingStatus">
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
          <el-form :model="cacheForm" label-position="top" class="cleanup-form">
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
              <el-button
                :type="cacheForm.dry_run ? 'primary' : 'danger'"
                :loading="cacheLoading"
                style="width: 100%"
                @click="handleCleanup('cache')"
              >
                <el-icon><Delete /></el-icon>
                <span>{{ cacheForm.dry_run ? '预览清理' : '立即执行清理' }}</span>
              </el-button>
            </el-form-item>
          </el-form>
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
                <el-option label="全部清理" value="all" />
                <el-option label="旧播放日志" value="old_playlogs" />
                <el-option label="旧工作流记录" value="old_workflows" />
                <el-option label="旧审核记录（已完结）" value="old_reviews" />
                <el-option label="过期 JWT 黑名单" value="expired_blacklist" />
                <el-option label="旧爬虫去重记录" value="old_dedup" />
                <el-option label="旧 AI 用量日志" value="old_ai_usage" />
                <el-option label="VACUUM 压缩" value="vacuum" />
              </el-select>
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
              <el-button
                :type="dbForm.dry_run ? 'primary' : 'danger'"
                :loading="dbLoading"
                style="width: 100%"
                @click="handleCleanup('database')"
              >
                <el-icon><Delete /></el-icon>
                <span>{{ dbForm.dry_run ? '预览清理' : '立即执行清理' }}</span>
              </el-button>
            </el-form-item>
          </el-form>
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
              <el-button
                :type="logForm.dry_run ? 'primary' : 'danger'"
                :loading="logLoading"
                style="width: 100%"
                @click="handleCleanup('logs')"
              >
                <el-icon><Delete /></el-icon>
                <span>{{ logForm.dry_run ? '预览清理' : '立即执行清理' }}</span>
              </el-button>
            </el-form-item>
          </el-form>
          <CleanupResult v-if="logResult" :result="logResult" />
        </div>
      </el-col>
    </el-row>

    <!-- 使用说明 -->
    <el-alert type="info" :closable="false" show-icon class="alert-block">
      <template #title>使用说明</template>
      <ol class="usage-list">
        <li>建议先用「预览模式」查看将清理的内容，确认无误后关闭预览再执行</li>
        <li>数据库清理的「保留天数」仅对按时间清理的目标生效（VACUUM 和过期黑名单除外）</li>
        <li>审核记录仅清理已完结状态（approved/rejected/replaced），pending 状态不会被清理</li>
        <li>工作流记录仅清理已完结状态（success/failed/cancelled），running 状态不会被清理</li>
        <li>VACUUM 会锁定数据库直到压缩完成，建议在低峰期执行</li>
        <li class="text-muted">注意：清理操作不可逆，请谨慎操作</li>
      </ol>
    </el-alert>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { ElMessage } from '../../utils/message'
import { ElMessageBox } from 'element-plus'
import {
  Refresh, Coin, Document, Cpu, Delete,
} from '@element-plus/icons-vue'
import api from '../../api'

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

// 存储状态
const status = ref(null)
const loadingStatus = ref(true)

// 三个表单状态（互不干扰）
const cacheForm = ref({ target: 'all', dry_run: true })
const dbForm = ref({ target: 'all', days: 30, dry_run: true })
const logForm = ref({ target: 'old_logs', days: 7, dry_run: true })

// 清理结果
const cacheResult = ref(null)
const dbResult = ref(null)
const logResult = ref(null)

// 加载状态
const cacheLoading = ref(false)
const dbLoading = ref(false)
const logLoading = ref(false)

// VACUUM 和 expired_blacklist 不需要天数输入
const showDbDays = computed(
  () => !['vacuum', 'expired_blacklist'].includes(dbForm.value.target)
)
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
  } catch (error) {
    console.error('加载存储状态失败', error)
  } finally {
    loadingStatus.value = false
  }
}

// 执行清理
async function handleCleanup(category) {
  const formMap = { cache: cacheForm, database: dbForm, logs: logForm }
  const loadingMap = { cache: cacheLoading, database: dbLoading, logs: logLoading }
  const resultMap = { cache: cacheResult, database: dbResult, logs: logResult }

  const form = formMap[category].value
  const loading = loadingMap[category]
  const result = resultMap[category]

  // 非预览模式二次确认
  if (!form.dry_run) {
    try {
      await ElMessageBox.confirm(
        '即将执行真实删除操作，此操作不可逆，是否继续？',
        '危险操作确认',
        { type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  }

  loading.value = true
  result.value = null
  try {
    const payload = { target: form.target, dry_run: form.dry_run }
    if (category !== 'cache') {
      payload.days = form.days
    }
    const data = await api.post(`/maintenance/${category}`, payload)
    result.value = data
    const msg = form.dry_run ? '预览完成' : '清理完成'
    ElMessage.success(msg)
    // 实际执行（非 dry_run）后刷新状态
    if (!form.dry_run) {
      await loadStatus()
    }
  } catch (error) {
    const resp = error?.response?.data || error
    ElMessage.error(resp?.message || '清理失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStatus()
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
