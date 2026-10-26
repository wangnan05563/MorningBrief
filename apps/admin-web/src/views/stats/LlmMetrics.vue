<template>
  <div data-guide="llm-metrics-page" class="page-container llm-metrics-page">
    <!-- 顶部操作区：刷新按钮（T00811：移除与导航栏重复的页面标题） -->
    <div class="top-bar">
      <IconButton
        label="刷新"
        desc="重新拉取 LLM 指标数据"
        :icon="Refresh"
        :loading="loading"
        @click="loadData"
      />
    </div>

    <!-- T02508（FR-UX-503）：本页所有计数都是进程内累计，重启即清零。
         不写清起点，运维会把"攒了半个月的触发率"读成"今天的触发率"。
         放在空态之外：即使还没有调用，也要让人看到这批数字从什么时候开始算 -->
    <div data-guide="llm-metrics-scope" class="scope-note">
      <span class="scope-note__text">{{ scopeNote }}</span>
      <span v-if="uptimeNote" class="scope-note__uptime">已运行 {{ uptimeNote }}</span>
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
      <!-- 空态：服务刚启动尚未产生调用（引导据此跳过「重试率概览」一步，T02656） -->
      <el-empty
        v-if="!loading && metrics.total_calls === 0"
        data-guide="llm-metrics-empty"
        description="暂无 LLM 调用数据，工作流执行后将自动累计"
      />

      <template v-else>
        <!-- 派生率卡片：trigger / improve / not_improve -->
        <el-row data-guide="llm-metrics-rates" :gutter="16" class="rate-row">
          <el-col v-for="r in rateCards" :key="r.key" :xs="24" :sm="8">
            <el-card shadow="hover">
              <div class="rate-card" :class="r.cls">
                <div class="rate-label">{{ r.label }}</div>
                <!-- INT-UX-03 / T02526：单位随数据下发，页面不再写死 "%" -->
                <div class="rate-value">{{ r.value }}</div>
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
import dayjs from 'dayjs'
import { Refresh } from '@element-plus/icons-vue'
import { getLlmMetrics } from '../../api/stats'
import { cumulativeScopeText, uptimeText as formatUptime } from '../../utils/scope'
import { metricLabel, metricText, metricValue } from '../../utils/format'

const loading = ref(false)
// 默认全 0，避免空态时 computed 除零报错
// started_at / pid：后端 T02508 新增的累计口径字段，null 表示后端未升级（不能拿当前时间冒充起点）
const metrics = ref({
  total_calls: 0,
  triggered: 0,
  improved: 0,
  not_improved: 0,
  trigger_rate: 0.0,
  improve_rate: 0.0,
  not_improve_rate: 0.0,
  started_at: null,
  pid: null,
  // INT-UX-03 / T02526：单位与换算随数据下发；后端未升级时为空对象，页面显示 '-'
  meta: {},
})
// 本次拉取时刻：用于算「已运行多久」，取到数就冻结，不做定时器（页面不需要秒级跳动）
const fetchedAt = ref(null)

// 累计口径文案：PRD ACC-UX-501 要求「明确显示累计自 x 时间，重启清零」
// subject 说明这句口径覆盖的对象——本页所有数字（含三个派生率）都是进程内累计
const scopeNote = computed(() =>
  cumulativeScopeText({
    startedAt: metrics.value.started_at,
    pid: metrics.value.pid,
    subject: '本页全部计数与派生率',
  })
)

// 运行时长：让运维判断"这批累计值攒了多久"，样本只有 20 次调用时不必然是问题
const uptimeNote = computed(() =>
  formatUptime({ startedAt: metrics.value.started_at, now: fetchedAt.value })
)

// 派生率卡片：trigger_rate 高表示 LLM 字数缩水严重，improve_rate 高表示硬约束有效
// 颜色映射：触发率用 warning（黄），改善率用 success（绿），未改善率用 danger（红）
// 数值与单位一律走 meta（INT-UX-03 / T02526）：这三条率后端已是 0~100 的百分数
// （unit=percent、factor=1），与 overview 的 completion_rate（ratio、要 ×100）同名不同量级，
// 页面自己写死 "%" 时看不出风险；缺 meta 时显示 '-'，不猜单位。
// 阈值判定仍用原始值：rateClass 的 50/30 分界是按百分数写的业务口径，与展示换算无关。
const rateCards = computed(() => {
  const meta = metrics.value.meta || {}
  const countUnit = meta.total_calls?.display?.unit || '次'
  const rate = (key, label, subKey) => ({
    key,
    label,
    value: metricText(metrics.value[key], meta[key]),
    sub: metrics.value[subKey],
    cls: rateClass(key.replace('_rate', ''), metrics.value[key]),
  })
  return [
    rate('trigger_rate', '触发率', `${metrics.value.triggered} / ${metrics.value.total_calls} ${countUnit}调用`),
    rate('improve_rate', '改善率', `${metrics.value.improved} / ${metrics.value.triggered} ${countUnit}触发`),
    rate('not_improve_rate', '未改善率', `${metrics.value.not_improved} / ${metrics.value.triggered} ${countUnit}触发`),
  ]
})

// 原始计数卡：4 项基础指标（标签与单位取自 meta，数值走千分位分组）
const countCards = computed(() => {
  const meta = metrics.value.meta || {}
  // 缺 meta 时退回旧文案/裸数值：计数本身不含换算，不至于因为没单位就空着
  const legacy = {
    total_calls: '总调用次数',
    triggered: '触发重试次数',
    improved: '改善次数',
    not_improved: '未改善次数',
  }
  return Object.entries(legacy).map(([key, label]) => ({
    key,
    label: meta[key] ? metricLabel(meta[key]) : label,
    value: meta[key] ? metricValue(metrics.value[key], meta[key]) : metrics.value[key],
  }))
})

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
    const data = await getLlmMetrics()
    // 合并而非整体替换：避免后端缺字段时丢失前端默认值（如 not_improve_rate）
    if (data && typeof data === 'object') {
      metrics.value = { ...metrics.value, ...data }
    }
    // 仅在取数成功时冻结时刻：失败时保留上一次的值，口径不能变成"刚刚"
    fetchedAt.value = dayjs()
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

  .scope-note {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 12px;
    margin-bottom: 12px;
    padding: 8px 12px;
    border-radius: $radius-sm;
    background: $color-bg;
    font-size: 12px;
    color: $color-text-secondary;

    .scope-note__text {
      font-weight: 600;
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
    &.is-warning .rate-value { color: $text-warning-strong; }
    &.is-danger .rate-value { color: $text-danger-strong; }
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
        /* 三段条底色固定深浅、不随主题走（见 variables.scss --solid-*）：
           主题主色当底色会与 --on-primary 撞色，马卡龙末段曾 1.0:1 完全不可读 */
        color: $on-solid;
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
        background: $solid-primary;
      }

      .stage-triggered {
        background: $solid-warning;
      }

      .stage-improved {
        background: $solid-success;
      }
    }
  }
}
</style>
