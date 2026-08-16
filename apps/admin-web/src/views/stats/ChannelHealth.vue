<template>
  <div class="page-container channel-health-page">
    <!-- 顶部操作区：标题 + 回溯天数切换 -->
    <div class="top-bar">
      <span class="page-title">频道素材健康度</span>
      <el-radio-group v-model="rangeDays" @change="loadData">
        <el-radio-button :value="7">近 7 天</el-radio-button>
        <el-radio-button :value="14">近 14 天</el-radio-button>
        <el-radio-button :value="30">近 30 天</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 汇总卡片：healthy / warning / critical / total -->
    <el-row :gutter="16" class="summary-row">
      <el-col v-for="s in summaryCards" :key="s.key" :xs="12" :sm="6">
        <el-card shadow="hover">
          <div class="summary-card" :class="s.cls">
            <div class="summary-label">{{ s.label }}</div>
            <div class="summary-value">{{ s.value }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 频道卡片网格：每卡片含基础信息 + mini 折线图 -->
    <div v-loading="loading" class="channel-grid">
      <el-empty v-if="!loading && channels.length === 0" description="暂无频道数据" />

      <el-row :gutter="16">
        <el-col
          v-for="ch in channels"
          :key="ch.channel_id"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
        >
          <el-card shadow="hover" class="channel-card">
            <!-- 卡片头：频道名 + 健康徽章 -->
            <div class="card-header">
              <div class="channel-name">
                <span class="name-text" :title="ch.name">{{ ch.name }}</span>
                <el-tag v-if="!ch.is_active" size="small" type="info">未激活</el-tag>
              </div>
              <el-tag :type="statusTagType(ch.health_status)" size="small" effect="light">
                {{ statusLabel(ch.health_status) }}
              </el-tag>
            </div>

            <!-- 关键指标四宫格 -->
            <div class="metric-grid">
              <div class="metric-item">
                <div class="metric-label">今日待改写</div>
                <div class="metric-value">{{ ch.today_pending }}</div>
              </div>
              <div class="metric-item">
                <div class="metric-label">区间入库</div>
                <div class="metric-value">{{ ch.range_total }}</div>
              </div>
              <div class="metric-item">
                <div class="metric-label">RSS 源</div>
                <div class="metric-value">{{ ch.rss_source_count }}</div>
              </div>
              <div class="metric-item">
                <div class="metric-label">关键词</div>
                <div class="metric-value">{{ ch.keyword_count }}</div>
              </div>
            </div>

            <!-- mini 折线图：近 N 天每日入库数 -->
            <div class="trend-area">
              <div class="trend-title">每日入库趋势</div>
              <div class="trend-canvas">
                <Line
                  v-if="ch.daily_trend && ch.daily_trend.length > 0"
                  :data="buildTrendData(ch.daily_trend, ch.health_status)"
                  :options="trendOptions"
                />
                <el-empty v-else :image-size="40" description="无数据" />
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
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
  Filler,
  Tooltip,
} from 'chart.js'
import api from '../../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip)

const rangeDays = ref(7)
const loading = ref(false)
const summary = ref({ healthy: 0, warning: 0, critical: 0, total: 0 })
const channels = ref([])

// 汇总卡片配置：cls 用于按状态染色，便于一眼识别整体健康度
const summaryCards = computed(() => [
  { key: 'healthy', label: '健康', value: summary.value.healthy, cls: 'is-healthy' },
  { key: 'warning', label: '警告', value: summary.value.warning, cls: 'is-warning' },
  { key: 'critical', label: '严重', value: summary.value.critical, cls: 'is-critical' },
  { key: 'total', label: '频道总数', value: summary.value.total, cls: 'is-total' },
])

// mini 折线图配置：隐藏图例和坐标轴标签，仅保留 tooltip，紧凑展示
const trendOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: { mode: 'index', intersect: false },
  },
  scales: {
    x: { display: false },
    y: { display: false, beginAtZero: true },
  },
  elements: { point: { radius: 2, hoverRadius: 4 } },
}

// 按健康状态映射折线颜色：与卡片徽章一致，方便视觉关联
function buildTrendData(dailyTrend, status) {
  const colorMap = {
    healthy: '#7ECEC1',
    warning: '#FFB84D',
    critical: '#FF6B6B',
  }
  const color = colorMap[status] || '#7ECEC1'
  return {
    labels: dailyTrend.map((d) => d.date),
    datasets: [
      {
        data: dailyTrend.map((d) => d.count),
        borderColor: color,
        backgroundColor: `${color}33`,
        fill: true,
        tension: 0.4,
        pointBackgroundColor: color,
      },
    ],
  }
}

function statusTagType(status) {
  // el-tag 的 type 映射：critical 用 danger，warning 用 warning，healthy 用 success
  if (status === 'critical') return 'danger'
  if (status === 'warning') return 'warning'
  return 'success'
}

function statusLabel(status) {
  if (status === 'critical') return '严重'
  if (status === 'warning') return '警告'
  return '健康'
}

async function loadData() {
  loading.value = true
  try {
    const data = await api.get('/stats/channel-health', { params: { range_days: rangeDays.value } })
    channels.value = data.channels || []
    summary.value = data.summary || { healthy: 0, warning: 0, critical: 0, total: 0 }
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.channel-health-page {
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

  .summary-row {
    margin-bottom: 16px;

    .el-col {
      margin-bottom: 12px;
    }
  }

  .summary-card {
    text-align: center;
    padding: 16px 12px;
    border-radius: $radius-md;

    .summary-label {
      font-size: 13px;
      color: $color-text-secondary;
      margin-bottom: 6px;
    }

    .summary-value {
      font-size: 26px;
      font-weight: 700;
    }

    // 按状态染色：与 el-tag 颜色体系一致
    &.is-healthy .summary-value { color: $color-primary-dark; }
    &.is-warning .summary-value { color: #E09020; }
    &.is-critical .summary-value { color: #E05050; }
    &.is-total .summary-value { color: $color-text-primary; }
  }

  .channel-grid {
    min-height: 200px;
  }

  .channel-card {
    margin-bottom: 16px;

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
      gap: 8px;

      .channel-name {
        display: flex;
        align-items: center;
        gap: 6px;
        min-width: 0;

        .name-text {
          font-size: 15px;
          font-weight: 600;
          color: $color-text-primary;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          max-width: 140px;
        }
      }
    }

    .metric-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      margin-bottom: 12px;

      .metric-item {
        background: $color-bg;
        border-radius: $radius-sm;
        padding: 8px 10px;
        text-align: center;

        .metric-label {
          font-size: 11px;
          color: $color-text-secondary;
          margin-bottom: 2px;
        }

        .metric-value {
          font-size: 18px;
          font-weight: 600;
          color: $color-text-primary;
        }
      }
    }

    .trend-area {
      .trend-title {
        font-size: 12px;
        color: $color-text-secondary;
        margin-bottom: 4px;
      }

      .trend-canvas {
        height: 80px;
      }
    }
  }
}
</style>
