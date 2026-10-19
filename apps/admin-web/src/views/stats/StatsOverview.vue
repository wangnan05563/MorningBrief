<template>
  <div data-guide="stats-page" class="page-container stats-page" v-loading="loading">
    <!-- 顶部操作区：日期选择（T00811：移除与导航栏重复的页面标题） -->
    <div class="top-bar">
      <el-date-picker
        v-model="selectedDate"
        type="date"
        :clearable="false"
        format="YYYY-MM-DD"
        value-format="YYYY-MM-DD"
        placeholder="选择日期"
        @change="loadOverview"
      />
    </div>

    <!-- T02496（FR-UX-302）：概览请求失败要说清「没取到」，不能让 5 个「-」看着像当天真的全是 0 -->
    <ListLoadError
      v-if="overviewError"
      :message="overviewError"
      :retrying="retryingOverview"
      @retry="retryOverview"
    />

    <!-- 指标卡片：5 个核心指标横向铺开 -->
    <el-row :gutter="16" class="metric-row">
      <el-col v-for="m in metrics" :key="m.key" :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
        <el-card shadow="hover">
          <div data-guide="stats-metric-card" class="metric-card">
            <div class="metric-label">{{ m.label }}</div>
            <div class="metric-value">{{ m.value }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 趋势图卡片：指标 + 时间范围切换 -->
    <el-card class="trend-card" shadow="never">
      <div class="trend-header">
        <span class="trend-title">趋势分析</span>
        <div class="trend-controls">
          <!-- 指标切换：仅这 3 个指标有意义做趋势 -->
          <el-radio-group v-model="metric" @change="loadTrend">
            <el-radio-button value="dau">DAU</el-radio-button>
            <el-radio-button value="play_count">播放量</el-radio-button>
            <el-radio-button value="completion_rate">完播率</el-radio-button>
          </el-radio-group>
          <el-radio-group v-model="range" @change="loadTrend">
            <el-radio-button value="7d">7 天</el-radio-button>
            <el-radio-button value="30d">30 天</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <div class="trend-canvas">
        <!-- T02496（FR-UX-302）：失败态优先于空态；空档期（values 全为 null）不画 0 折线 -->
        <ListLoadError
          v-if="trendError"
          :message="trendError"
          :retrying="retryingTrend"
          @retry="retryTrend"
        />
        <Line v-else-if="hasTrend" :data="trendData" :options="trendOptions" />
        <el-empty v-else description="暂无趋势数据" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Line } from 'vue-chartjs'
// 按需注册 Chart.js 组件，避免一次性引入全量包
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import dayjs from 'dayjs'
import api from '../../api'
import ListLoadError from '../../components/ListLoadError.vue'
import { metricLabel, metricValue } from '../../utils/format'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

// 概览数据：当日汇总
const overview = ref({})
// 默认查今日，避免空日期引发后端默认行为不一致
const selectedDate = ref(dayjs().format('YYYY-MM-DD'))

// 指标卡片：键序取自响应本身，名称、单位与换算取自 meta（FR-UX-501 / T02506），
// 页面不再抄一份「平均收听(分钟)」「完播率(%)」——抄一次就漂移一次。
// meta 缺失时仍然渲染卡片但显示 '-'（宁可空着，也不把秒当分钟猜一个单位）
const metrics = computed(() =>
  Object.keys(overview.value)
    .filter((key) => key !== 'meta')
    .map((key) => {
      const meta = overview.value.meta?.[key]
      return { key, label: metricLabel(meta), value: metricValue(overview.value[key], meta) }
    }),
)

// 趋势查询参数
const metric = ref('dau')
const range = ref('7d')
const trend = ref({ dates: [], values: [] })

// T02496（FR-UX-302）：后端现在对没有记录的日期返回 null（而不是补 0），
// 因此「有没有趋势」要看实际数据点，而不是 dates 长度——dates 恒等于区间天数，
// 用它判断会让空档期画出一条贴着 0 的折线，被读成「这些天都是 0」。
const hasTrend = computed(() =>
  (trend.value.values || []).some((v) => v !== null && v !== undefined),
)

// 趋势曲线名称同样取自 meta（FR-UX-501 / T02506）；
// Y 轴刻度换算（0~1 → %）属 FR-UX-502 / T02507，本单不动数值口径
const trendMeta = computed(() => trend.value.meta?.[metric.value])
const chartLabel = computed(() => trendMeta.value?.label || '')

// 适配 Chart.js 数据结构：薄荷青主线 + 半透明填充
const trendData = computed(() => ({
  labels: trend.value.dates,
  datasets: [
    {
      label: chartLabel.value,
      data: trend.value.values,
      borderColor: '#7ECEC1',
      backgroundColor: 'rgba(126, 206, 193, 0.18)',
      fill: true,
      tension: 0.4,
      pointBackgroundColor: '#7ECEC1',
      pointRadius: 3,
      pointHoverRadius: 5,
    },
  ],
}))

const trendOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: { mode: 'index', intersect: false },
  },
  scales: {
    y: { beginAtZero: true },
  },
}

const loading = ref(false)
// T02496（FR-UX-302）：概览/趋势各自的失败态与重试标志
const overviewError = ref('')
const trendError = ref('')
const retryingOverview = ref(false)
const retryingTrend = ref(false)

async function loadOverview() {
  loading.value = true
  try {
    overview.value = await api.get('/stats/overview', { params: { date: selectedDate.value } })
    overviewError.value = ''
  } catch (e) {
    // 拦截器已弹 toast，这里补页内错误态：5 张卡片全是「-」不叫失败告知
    overviewError.value = e?.message || '统计概览加载失败'
  } finally {
    loading.value = false
  }
}

async function loadTrend() {
  try {
    // 失败时保留上一份数据（图上仍是旧曲线），但错误态必须显示出来
    trend.value = await api.get('/stats/trend', { params: { metric: metric.value, range: range.value } })
    trendError.value = ''
  } catch (e) {
    trendError.value = e?.message || '趋势数据加载失败'
  }
}

async function retryOverview() {
  retryingOverview.value = true
  try {
    await loadOverview()
  } finally {
    retryingOverview.value = false
  }
}

async function retryTrend() {
  retryingTrend.value = true
  try {
    await loadTrend()
  } finally {
    retryingTrend.value = false
  }
}

onMounted(() => {
  loadOverview()
  loadTrend()
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.stats-page {
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
  }

  .metric-row {
    margin-bottom: 16px;

    .el-col {
      margin-bottom: 12px;
    }
  }

  .trend-card {
    .trend-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 16px;

      .trend-title {
        font-size: 16px;
        font-weight: 600;
        color: $color-text-primary;
      }

      .trend-controls {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }
    }

    .trend-canvas {
      height: 360px;
    }
  }
}
</style>
