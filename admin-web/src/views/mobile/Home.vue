<template>
  <div class="m-home">
    <section class="m-section">
      <h3 class="m-section__title">今日关键指标</h3>
      <div class="m-grid">
        <div v-for="c in cards" :key="c.label" class="m-card">
          <div class="m-card__value">{{ c.value }}</div>
          <div class="m-card__label">{{ c.label }}</div>
        </div>
      </div>
    </section>

    <section class="m-section">
      <div class="m-row" @click="goReview">
        <span class="m-row__label">待我审批</span>
        <span class="m-row__value">{{ pendingCount }} <span class="m-arrow">›</span></span>
      </div>
      <div class="m-row" @click="goMessage">
        <span class="m-row__label">未读消息</span>
        <span class="m-row__value">
          {{ msgReady ? unreadCount : '建设中' }} <span class="m-arrow">›</span>
        </span>
      </div>
    </section>

    <p v-if="!msgReady" class="m-tip">
      消息中心依赖后端运营收件箱接口（SRS INT-M101），当前为占位。
    </p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getDashboardSummary } from '../../api/mobile'

const router = useRouter()

const metrics = ref({})
const pendingCount = ref(0)
const unreadCount = ref(0)
// 后端运营收件箱接口（INT-M101）已实现，首页未读走聚合接口
const msgReady = ref(true)

const fmt = (v) => (v == null ? '-' : Number(v).toLocaleString('zh-CN'))

const cards = computed(() => [
  { label: 'DAU', value: fmt(metrics.value.dau) },
  { label: '播放量', value: fmt(metrics.value.play_count) },
  {
    label: '完播率',
    value: metrics.value.completion_rate != null ? metrics.value.completion_rate + '%' : '-',
  },
  { label: '平均收听(分)', value: metrics.value.avg_listen_duration ?? '-' },
])

async function load() {
  const data = await getDashboardSummary().catch(() => ({
    today: {},
    pending_review: 0,
    unread_message: 0,
  }))
  metrics.value = data.today || {}
  pendingCount.value = data.pending_review ?? 0
  unreadCount.value = data.unread_message ?? 0
}

function goReview() {
  router.push('/m/review')
}
function goMessage() {
  router.push('/m/message')
}

onMounted(load)
</script>

<style scoped>
.m-home {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.m-section__title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 10px;
  color: #1f2329;
}

.m-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.m-card {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-card__value {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-color-primary, #409eff);
}

.m-card__label {
  margin-top: 4px;
  font-size: 12px;
  color: #8a8f99;
}

.m-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-radius: 12px;
  padding: 16px 14px;
  margin-bottom: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-row__label {
  font-size: 15px;
  color: #1f2329;
}

.m-row__value {
  font-size: 15px;
  color: #409eff;
  font-weight: 600;
}

.m-arrow {
  color: #c0c4cc;
  margin-left: 2px;
}

.m-tip {
  font-size: 12px;
  color: #b0b4bb;
  line-height: 1.6;
  padding: 0 4px;
}
</style>
