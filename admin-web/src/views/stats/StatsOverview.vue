<template>
  <div class="page-container stats-page">
    <!-- 顶部操作区：日期选择 -->
    <div class="top-bar">
      <span class="page-title">数据统计</span>
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

    <!-- 指标卡片：5 个核心指标横向铺开 -->
    <el-row :gutter="16" class="metric-row">
      <el-col v-for="m in metrics" :key="m.key" :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
        <el-card shadow="hover">
          <div class="metric-card">
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
        <Line v-if="hasTrend" :data="trendData" :options="trendOptions" />
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

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

// 概览数据：当日汇总
const overview = ref({})
// 默认查今日，避免空日期引发后端默认行为不一致
const selectedDate = ref(dayjs().format('YYYY-MM-DD'))

// 指标卡片配置：label 为中文，key 与后端字段保持一致
const metrics = computed(() => [
  { key: 'dau', label: 'DAU', value: formatNum(overview.value.dau) },
  { key: 'play_count', label: '播放量', value: formatNum(overview.value.play_count) },
  // 后端完播率为 0~1 小数，展示时需乘 100 转百分比
  { key: 'completion_rate', label: '完播率(%)', value: formatRate(overview.value.completion_rate) },
  { key: 'avg_listen_duration', label: '平均收听(分钟)', value: overview.value.avg_listen_duration ?? '-' },
  { key: 'ad_impression', label: '广告曝光', value: formatNum(overview.value.ad_impression) },
])

// 趋势查询参数
const metric = ref('dau')
const range = ref('7d')
const trend = ref({ dates: [], values: [] })

const hasTrend = computed(() => trend.value.dates && trend.value.dates.length > 0)

// 中文标题映射：用于图例与空状态切换
const metricLabelMap = {
  dau: 'DAU',
  play_count: '播放量',
  completion_rate: '完播率(%)',
}
const metricLabel = computed(() => metricLabelMap[metric.value] || '')

// 适配 Chart.js 数据结构：薄荷青主线 + 半透明填充
const trendData = computed(() => ({
  labels: trend.value.dates,
  datasets: [
    {
      label: metricLabel.value,
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

// 数字加千分位，避免大数字阅读吃力
function formatNum(n) {
  if (n === null || n === undefined) return '-'
  return Number(n).toLocaleString('zh-CN')
}

// 完播率：后端 0~1 小数 → 百分比，保留 1 位小数
function formatRate(v) {
  if (v === null || v === undefined) return '-'
  return (Number(v) * 100).toFixed(1)
}

async function loadOverview() {
  overview.value = await api.get('/stats/overview', { params: { date: selectedDate.value } })
}

async function loadTrend() {
  trend.value = await api.get('/stats/trend', { params: { metric: metric.value, range: range.value } })
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
