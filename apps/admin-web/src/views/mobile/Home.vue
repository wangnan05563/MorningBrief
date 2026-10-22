<template>
  <div class="m-home">
    <!-- I15（FR-UX-302）：外勤首屏。此前 `.catch(() => ({today:{},pending_review:0,unread_message:0}))`
         把「取不到」直接铺成「DAU -、待审 0、未读 0」的正常空态，网断时外勤会误判
         「今天没有要审的」。失败时两块都撤下（0 本身就是一种声称），换成带重试的页内错误态。 -->
    <ListLoadError
      v-if="loadError"
      :message="loadError"
      :retrying="retrying"
      @retry="retryLoad"
    />

    <section v-if="!loadError" class="m-section">
      <h3 class="m-section__title">今日关键指标</h3>
      <div class="m-grid">
        <div v-for="c in cards" :key="c.label" class="m-card">
          <div class="m-card__value">{{ c.value }}</div>
          <div class="m-card__label">{{ c.label }}</div>
        </div>
      </div>
    </section>

    <section v-if="!loadError" class="m-section">
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
import ListLoadError from '../../components/ListLoadError.vue'
import { metricLabel, metricValue } from '../../utils/format'

const router = useRouter()

const metrics = ref({})
const pendingCount = ref(0)
const unreadCount = ref(0)
// I15（FR-UX-302）：失败与「今天真的没有数据」必须可区分——外勤首屏此前用
// `.catch(() => ({...0}))` 把接口故障铺成正常空态。
const loadError = ref('')
const retrying = ref(false)
// 后端运营收件箱接口（INT-M101）已实现，首页未读走聚合接口
const msgReady = ref(true)

// 卡片顺序、名称与单位换算全部取自 dashboard-summary 里的 meta
// （与 PC 统计页同源，FR-UX-501 / T02506）：此前这里把后端的秒值直接标成「(分)」、
// 完播率又不乘 100，与 PC 卡片各错各的。
// 首页只铺这 4 张卡（版式选择）；名称与单位换算仍取自 meta，不在这里重写
const CARD_KEYS = ['dau', 'play_count', 'completion_rate', 'avg_listen_duration']
const cards = computed(() =>
  CARD_KEYS.map((key) => {
    const meta = metrics.value.meta?.[key]
    return { key, label: metricLabel(meta), value: metricValue(metrics.value[key], meta) }
  }),
)

async function load() {
  try {
    // I15：失败**不再**回落成 `{today:{}, pending_review:0, unread_message:0}`。
    // 那个兜底把接口故障渲染成「今天 DAU 没有、待审 0、未读 0」的正常空态，
    // 外勤在地铁里网断时会直接判成「今天没有要审的」——恰好漏掉最该处理的队列。
    const data = await getDashboardSummary()
    metrics.value = data.today || {}
    pendingCount.value = data.pending_review ?? 0
    unreadCount.value = data.unread_message ?? 0
    loadError.value = ''
  } catch (e) {
    metrics.value = {}
    pendingCount.value = 0
    unreadCount.value = 0
    loadError.value = e?.message || '首页聚合接口请求失败'
  } finally {
    retrying.value = false
  }
}

function retryLoad() {
  retrying.value = true
  return load()
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
