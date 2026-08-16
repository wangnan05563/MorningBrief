<template>
  <div class="m-fb">
    <div class="m-fb__tabs">
      <button
        v-for="t in tabs"
        :key="t.value"
        class="m-fb__tab"
        :class="{ 'm-fb__tab--active': status === t.value }"
        @click="switchTab(t.value)"
      >
        {{ t.label }}
      </button>
    </div>

    <div v-if="loading && !list.length" class="m-empty">加载中…</div>
    <div v-else-if="!list.length" class="m-empty">暂无反馈</div>

    <div v-for="f in list" :key="f.id" class="m-fb__item">
      <div class="m-fb__head">
        <span class="m-fb__cat">{{ f.category || '未分类' }}</span>
        <span class="m-badge" :class="statusClass(f.status)">{{ statusLabel[f.status] || f.status }}</span>
      </div>
      <div class="m-fb__content">{{ f.content }}</div>
      <div class="m-fb__meta">
        <span v-if="f.contact">联系方式：{{ f.contact }}</span>
        <span>{{ fmtDate(f.created_at) }}</span>
      </div>
      <div class="m-fb__actions" v-if="f.status !== 'resolved'">
        <button class="m-btn m-btn--primary m-btn--sm" @click="advance(f)">
          标记为{{ nextLabel(f.status) }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listFeedbacks, updateFeedbackStatus } from '../../api/feedbacks'
import { ElMessage } from '../../utils/message'

const tabs = [
  { label: '全部', value: '' },
  { label: '待处理', value: 'pending' },
  { label: '处理中', value: 'processed' },
  { label: '已解决', value: 'resolved' },
]

const status = ref('')
const list = ref([])
const loading = ref(false)

const statusLabel = { pending: '待处理', processed: '处理中', resolved: '已解决' }
const statusClass = (s) =>
  ({ pending: 'm-badge--warn', processed: 'm-badge--info', resolved: 'm-badge--on' }[s] || 'm-badge--info')

const nextMap = { pending: 'processed', processed: 'resolved' }
const nextLabel = (s) => ({ pending: '处理中', processed: '已解决' }[s] || '')

const fmtDate = (iso) => (iso ? iso.slice(0, 16).replace('T', ' ') : '-')

async function reload() {
  loading.value = true
  try {
    const data = await listFeedbacks({
      status: status.value || undefined,
      page: 1,
      size: 50,
    })
    list.value = data.list || []
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function switchTab(v) {
  if (status.value === v) return
  status.value = v
  reload()
}

async function advance(f) {
  const next = nextMap[f.status]
  if (!next) return
  try {
    await updateFeedbackStatus(f.id, next)
    f.status = next
    ElMessage.success('状态已更新')
  } catch {
    // 拦截器已提示
  }
}

onMounted(reload)
</script>

<style scoped>
.m-fb {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.m-fb__tabs {
  display: flex;
  gap: 8px;
}

.m-fb__tab {
  flex: 1;
  height: 34px;
  border-radius: 8px;
  border: 1px solid #ebedf0;
  background: #fff;
  font-size: 13px;
  color: #4e5969;
  cursor: pointer;
}

.m-fb__tab--active {
  background: var(--el-color-primary, #409eff);
  color: #fff;
  border-color: var(--el-color-primary, #409eff);
}

.m-fb__item {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-fb__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.m-fb__cat {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
}

.m-fb__content {
  font-size: 13px;
  color: #4e5969;
  line-height: 1.6;
  margin: 8px 0;
}

.m-fb__meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #8a8f99;
}

.m-fb__actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}

.m-badge {
  font-size: 11px;
  border-radius: 4px;
  padding: 1px 6px;
  font-weight: 500;
}

.m-badge--on { color: #67c23a; background: #f0f9eb; }
.m-badge--warn { color: #e6a23c; background: #fdf6ec; }
.m-badge--info { color: #409eff; background: #ecf5ff; }

.m-btn {
  height: 46px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}

.m-btn--sm {
  height: 34px;
  padding: 0 16px;
  font-size: 14px;
}

.m-btn--primary {
  background: var(--el-color-primary, #409eff);
  color: #fff;
}

.m-empty {
  text-align: center;
  color: #b0b4bb;
  padding: 40px 0;
  font-size: 14px;
}
</style>
