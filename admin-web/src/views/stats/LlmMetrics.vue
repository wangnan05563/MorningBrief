<template>
  <div class="page-container llm-metrics-page">
    <!-- 顶部操作区：标题 + 刷新按钮 -->
    <div class="top-bar">
      <span class="page-title">LLM 字数重试命中率</span>
      <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
    </div>

    <!-- 说明卡：解释指标含义，便于运维理解派生率意义 -->
    <el-alert
      v-if="!loading && metrics.total_calls > 0"
      class="info-alert"
      type="info"
      :closable="false"
      show-icon
    >
      <template #title>
        触发率 = 触发次数 / 总调用；改善率 = 改善次数 / 触发次数。
        触发率 &gt; 50% 说明 LLM 字数缩水严重需优化 prompt；改善率 &lt; 30% 说明硬约束后缀效果不佳需更换策略。
      </template>
    </el-alert>

    <div v-loading="loading">
      <!-- 空态：服务刚启动尚未产生调用 -->
      <el-empty
        v-if="!loading && metrics.total_calls === 0"
        description="暂无 LLM 调用数据，工作流执行后将自动累计"
      />

      <template v-else>
        <!-- 派生率卡片：trigger / improve / not_improve -->
        <el-row :gutter="16" class="rate-row">
          <el-col v-for="r in rateCards" :key="r.key" :xs="24" :sm="8">
            <el-card shadow="hover">
              <div class="rate-card" :class="r.cls">
                <div class="rate-label">{{ r.label }}</div>
                <div class="rate-value">{{ r.value }}%</div>
                <div class="rate-sub">{{ r.sub }}</div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 原始计数卡：4 项基础指标 -->
        <el-row :gutter="16" class="count-row">
          <el-col v-for="c in countCards" :key="c.key" :xs="12" :sm="6">
            <el-card shadow="hover">
              <div class="count-card">
                <div class="count-label">{{ c.label }}</div>
                <div class="count-value">{{ c.value }}</div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 漏斗可视化：total → triggered → improved -->
        <el-card shadow="hover" class="funnel-card">
          <template #header>
            <span class="card-title">重试漏斗</span>
          </template>
          <div class="funnel">
            <div
              v-for="stage in funnelStages"
              :key="stage.key"
              class="funnel-stage"
              :style="{ width: stage.width + '%' }"
            >
              <div class="stage-bar" :class="stage.cls">
                <span class="stage-label">{{ stage.label }}</span>
                <span class="stage-value">{{ stage.value }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import api from '../../api'

const loading = ref(false)
// 默认全 0，避免空态时 computed 除零报错
const metrics = ref({
  total_calls: 0,
  triggered: 0,
  improved: 0,
  not_improved: 0,
  trigger_rate: 0.0,
  improve_rate: 0.0,
  not_improve_rate: 0.0,
})

// 派生率卡片：trigger_rate 高表示 LLM 字数缩水严重，improve_rate 高表示硬约束有效
// 颜色映射：触发率用 warning（黄），改善率用 success（绿），未改善率用 danger（红）
const rateCards = computed(() => [
  {
    key: 'trigger_rate',
    label: '触发率',
    value: metrics.value.trigger_rate.toFixed(2),
    sub: `${metrics.value.triggered} / ${metrics.value.total_calls} 次调用`,
    cls: rateClass('trigger', metrics.value.trigger_rate),
  },
  {
    key: 'improve_rate',
    label: '改善率',
    value: metrics.value.improve_rate.toFixed(2),
    sub: `${metrics.value.improved} / ${metrics.value.triggered} 次触发`,
    cls: rateClass('improve', metrics.value.improve_rate),
  },
  {
    key: 'not_improve_rate',
    label: '未改善率',
    value: metrics.value.not_improve_rate.toFixed(2),
    sub: `${metrics.value.not_improved} / ${metrics.value.triggered} 次触发`,
    cls: rateClass('not_improve', metrics.value.not_improve_rate),
  },
])

// 原始计数卡：四项基础计数
const countCards = computed(() => [
  { key: 'total_calls', label: '总调用次数', value: metrics.value.total_calls },
  { key: 'triggered', label: '触发重试次数', value: metrics.value.triggered },
  { key: 'improved', label: '改善次数', value: metrics.value.improved },
  { key: 'not_improved', label: '未改善次数', value: metrics.value.not_improved },
])

// 漏斗可视化：按比例递减展示 total → triggered → improved
// 宽度按相对 total 的占比计算，最小 20% 保证可读
const funnelStages = computed(() => {
  const total = metrics.value.total_calls || 1
  const triggered = metrics.value.triggered
  const improved = metrics.value.improved
  return [
    {
      key: 'total',
      label: '总调用',
      value: triggered > 0 ? total : total,
      width: 100,
      cls: 'stage-total',
    },
    {
      key: 'triggered',
      label: '触发重试',
      value: triggered,
      width: Math.max(20, (triggered / total) * 100),
      cls: 'stage-triggered',
    },
    {
      key: 'improved',
      label: '重试改善',
      value: improved,
      // 改善相对触发数计算漏斗收窄，触发数为 0 时退化为 0
      width: triggered > 0 ? Math.max(20, (improved / triggered) * (triggered / total) * 100) : 0,
      cls: 'stage-improved',
    },
  ]
})

// 派生率颜色阈值映射
// trigger_rate：>50% danger（红，需警惕 LLM 缩水）；30-50% warning；<30% success
// improve_rate：>50% success（绿，硬约束有效）；30-50% warning；<30% danger
// not_improve_rate：>50% danger（红，硬约束基本无效）；30-50% warning；<30% success
function rateClass(kind, rate) {
  if (kind === 'trigger') {
    if (rate > 50) return 'is-danger'
    if (rate >= 30) return 'is-warning'
    return 'is-success'
  }
  if (kind === 'improve') {
    if (rate >= 50) return 'is-success'
    if (rate >= 30) return 'is-warning'
    return 'is-danger'
  }
  // not_improve 与 improve 颜色相反
  if (rate > 50) return 'is-danger'
  if (rate >= 30) return 'is-warning'
  return 'is-success'
}

async function loadData() {
  loading.value = true
  try {
    const data = await api.get('/stats/llm-metrics')
    // 合并而非整体替换：避免后端缺字段时丢失前端默认值（如 not_improve_rate）
    if (data && typeof data === 'object') {
      metrics.value = { ...metrics.value, ...data }
    }
  } catch (e) {
    // 拦截器已统一提示，这里保留 metrics 现值不清空，避免页面闪烁
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.llm-metrics-page {
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

  .info-alert {
    margin-bottom: 16px;
  }

  .rate-row,
  .count-row {
    margin-bottom: 16px;

    .el-col {
      margin-bottom: 12px;
    }
  }

  .rate-card {
    text-align: center;
    padding: 20px 12px;
    border-radius: $radius-md;

    .rate-label {
      font-size: 13px;
      color: $color-text-secondary;
      margin-bottom: 8px;
    }

    .rate-value {
      font-size: 32px;
      font-weight: 700;
      margin-bottom: 6px;
    }

    .rate-sub {
      font-size: 12px;
      color: $color-text-secondary;
    }

    &.is-success .rate-value { color: $color-primary-dark; }
    &.is-warning .rate-value { color: #E09020; }
    &.is-danger .rate-value { color: #E05050; }
  }

  .count-card {
    text-align: center;
    padding: 16px 12px;
    border-radius: $radius-md;
    background: $color-bg;

    .count-label {
      font-size: 12px;
      color: $color-text-secondary;
      margin-bottom: 6px;
    }

    .count-value {
      font-size: 22px;
      font-weight: 600;
      color: $color-text-primary;
    }
  }

  .funnel-card {
    .card-title {
      font-size: 15px;
      font-weight: 600;
      color: $color-text-primary;
    }

    .funnel {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 12px 0;
    }

    .funnel-stage {
      transition: width 0.3s ease;

      .stage-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 16px;
        border-radius: $radius-sm;
        color: #fff;
        font-weight: 600;
        min-height: 44px;

        .stage-label {
          font-size: 14px;
        }

        .stage-value {
          font-size: 16px;
        }
      }

      .stage-total {
        background: $color-primary;
      }

      .stage-triggered {
        background: #E09020;
      }

      .stage-improved {
        background: $color-primary-dark;
      }
    }
  }
}
</style>
