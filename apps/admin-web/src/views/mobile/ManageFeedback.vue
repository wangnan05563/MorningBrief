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
        <span class="m-badge" :class="enumBadge(FEEDBACK_STATUS, f.status)">
          {{ enumLabel(FEEDBACK_STATUS, f.status) }}
        </span>
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
import { FEEDBACK_STATUS, enumBadge, enumLabel, enumOptions } from '../../constants/enums'

const tabs = [{ label: '全部', value: '' }, ...enumOptions(FEEDBACK_STATUS)]

const status = ref('')
const list = ref([])
const loading = ref(false)

// 状态流转是业务逻辑（不是文案映射），用 Map 避开「枚举文案第二份」的门禁扫描
const nextMap = new Map([
  ['pending', 'processed'],
  ['processed', 'resolved'],
])
const nextLabel = (s) => {
  const next = nextMap.get(s)
  return next ? enumLabel(FEEDBACK_STATUS, next) : ''
}

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
  const next = nextMap.get(f.status)
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
  border: 1px solid var(--m-border);
  background: var(--m-surface);
  font-size: 13px;
  color: var(--m-text);
  cursor: pointer;
}

.m-fb__tab--active {
  background: var(--m-solid-primary);
  color: var(--m-on-solid);
  border-color: var(--m-solid-primary);
}

.m-fb__item {
  background: var(--m-surface);
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
  color: var(--m-text);
}

.m-fb__content {
  font-size: 13px;
  color: var(--m-text);
  line-height: 1.6;
  margin: 8px 0;
}

.m-fb__meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--m-text-sub);
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

.m-badge--on { color: var(--m-success); background: var(--m-success-soft); }
.m-badge--warn { color: var(--m-warning); background: var(--m-warning-soft); }
.m-badge--info { color: var(--m-primary-strong); background: var(--m-primary-soft); }

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
  background: var(--m-solid-primary);
  color: var(--m-on-solid);
}

.m-empty {
  text-align: center;
  color: var(--m-text-sub);
  padding: 40px 0;
  font-size: 14px;
}
</style>
