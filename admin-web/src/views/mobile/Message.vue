<template>
  <div class="m-msg">
    <div class="m-msg__bar">
      <span class="m-msg__count">未读 {{ unreadCount }}</span>
      <button class="m-msg__action" :disabled="unreadCount === 0" @click="markAll">
        全部已读
      </button>
    </div>

    <div v-if="loading" class="m-msg__empty">加载中…</div>
    <div v-else-if="list.length === 0" class="m-msg__empty">暂无消息</div>

    <div
      v-for="m in list"
      :key="m.id"
      class="m-msg__item"
      :class="{ 'm-msg__item--unread': !m.read }"
      @click="open(m)"
    >
      <span class="m-msg__dot" :class="'m-msg__dot--' + m.level"></span>
      <div class="m-msg__body">
        <div class="m-msg__title">
          <span class="m-msg__tag">{{ typeLabel[m.msg_type] || m.msg_type }}</span>
          {{ m.title }}
        </div>
        <div v-if="m.body" class="m-msg__text">{{ m.body }}</div>
        <div class="m-msg__time">{{ formatTime(m.created_at) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getInbox, markRead } from '../../api/mobile'
import { ElMessage } from '../../utils/message'

const list = ref([])
const unreadCount = ref(0)
const loading = ref(false)

const typeLabel = { review: '审批', alert: '告警', system: '系统' }

const levelClass = { info: 'info', warning: 'warning', critical: 'critical' }

async function load() {
  loading.value = true
  try {
    const data = await getInbox({ page: 1, page_size: 20 })
    list.value = data.items || []
    unreadCount.value = data.unread_count ?? 0
  } finally {
    loading.value = false
  }
}

async function markAll() {
  await markRead({ mark_all: true })
  ElMessage.success('已全部标记已读')
  await load()
}

async function open(m) {
  if (m.read) {
    // 已读项若带深链可跳转（如审批详情）
    return
  }
  await markRead({ message_ids: [m.id] })
  m.read = true
  unreadCount.value = Math.max(0, unreadCount.value - 1)
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(load)
</script>

<style scoped>
.m-msg {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-msg__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 2px 6px;
}

.m-msg__count {
  font-size: 13px;
  color: #8a8f99;
}

.m-msg__action {
  font-size: 13px;
  color: var(--el-color-primary, #409eff);
  background: none;
  border: none;
  cursor: pointer;
}

.m-msg__action:disabled {
  color: #c0c4cc;
  cursor: not-allowed;
}

.m-msg__empty {
  text-align: center;
  color: #b0b4bb;
  font-size: 14px;
  padding: 40px 0;
}

.m-msg__item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-msg__item--unread {
  border-left: 3px solid var(--el-color-primary, #409eff);
}

.m-msg__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
  flex: 0 0 auto;
  background: #c0c4cc;
}

.m-msg__dot--warning {
  background: #e6a23c;
}

.m-msg__dot--critical {
  background: #f56c6c;
}

.m-msg__body {
  flex: 1;
  min-width: 0;
}

.m-msg__title {
  font-size: 15px;
  color: #1f2329;
  display: flex;
  align-items: center;
  gap: 6px;
}

.m-msg__tag {
  font-size: 11px;
  color: #fff;
  background: var(--el-color-primary, #409eff);
  border-radius: 4px;
  padding: 1px 5px;
}

.m-msg__text {
  font-size: 13px;
  color: #8a8f99;
  margin-top: 4px;
  line-height: 1.5;
}

.m-msg__time {
  font-size: 11px;
  color: #b0b4bb;
  margin-top: 6px;
}
</style>
