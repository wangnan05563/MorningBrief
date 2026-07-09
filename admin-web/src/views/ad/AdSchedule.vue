<template>
  <div class="page-container ad-schedule">
    <div class="toolbar">
      <h2 class="page-title">排期日历</h2>
      <el-date-picker
        v-model="selectedMonth"
        type="month"
        value-format="YYYY-MM"
        placeholder="选择月份"
        :clearable="false"
        @change="onMonthChange"
      />
    </div>

    <div class="card-soft calendar-card">
      <!-- 图例：帮助用户快速识别三个广告位的颜色含义 -->
      <div class="legend">
        <div class="legend-item">
          <span class="legend-dot dot-head"></span>
          <span>开头（head）</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot dot-mid"></span>
          <span>中间（mid）</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot dot-tail"></span>
          <span>结尾（tail）</span>
        </div>
      </div>

      <el-calendar v-model="calendarDate" v-loading="loading">
        <template #date-cell="{ data }">
          <div class="date-cell" :class="{ 'other-month': data.type !== 'current-month' }">
            <div class="date-num">{{ data.day.split('-').slice(2).join('') }}</div>
            <div class="slots">
              <div
                v-for="pos in ['head', 'mid', 'tail']"
                :key="pos"
                class="slot"
                :class="`slot-${pos}`"
              >
                <span class="slot-label">{{ POSITION_LABEL[pos] }}</span>
                <span v-if="getSlotMaterial(data.day, pos)" class="slot-name">
                  {{ getSlotMaterial(data.day, pos).material_name }}
                </span>
                <span v-else class="slot-empty">—</span>
              </div>
            </div>
          </div>
        </template>
      </el-calendar>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import dayjs from 'dayjs'
import api from '../../api'

const loading = ref(false)
// 月份选择器的值（YYYY-MM 字符串），作为月份切换的数据源
const selectedMonth = ref(dayjs().format('YYYY-MM'))
// el-calendar 的 v-model 需要 Date 对象，用当月1号作为锚点
const calendarDate = ref(dayjs().startOf('month').toDate())

const scheduleMap = ref({})

// 广告位中文映射，与投放规则页保持一致
const POSITION_LABEL = { head: '开头', mid: '中间', tail: '结尾' }

function getSlotMaterial(dayStr, pos) {
  return scheduleMap.value[dayStr]?.[pos] || null
}

async function fetchSchedule(monthStr) {
  loading.value = true
  try {
    const data = await api.get('/ads/schedule', {
      params: { month: monthStr },
    })
    // 后端返回 { placements: [{material_name, position, start_date, end_date}] }
    // 转换为前端所需 { "YYYY-MM-DD": { head: {material_name}, mid:..., tail:... } }
    const map = {}
    if (data.placements) {
      for (const p of data.placements) {
        const start = new Date(p.start_date)
        const end = new Date(p.end_date)
        // 投放区间内每一天都填入该广告位素材
        // 用显式重新赋值更新 d：SonarQube S2189 无法识别 d.setDate() 这类原地方法调用为循环变量被修改
        const ONE_DAY_MS = 24 * 60 * 60 * 1000
        for (let d = new Date(start); d <= end; d = new Date(d.getTime() + ONE_DAY_MS)) {
          const dateKey = d.toISOString().slice(0, 10)
          if (!map[dateKey]) map[dateKey] = {}
          map[dateKey][p.position] = { material_name: p.material_name }
        }
      }
    }
    scheduleMap.value = map
  } finally {
    loading.value = false
  }
}

// 月份选择器变化时：同步日历到所选月份，并触发 watch 重新加载
function onMonthChange(monthStr) {
  if (!monthStr) return
  // 保留当前日期，仅切换到目标月份，避免日历跳回1号
  const target = dayjs(monthStr + '-01')
  calendarDate.value = target.toDate()
}

// 日历日期变化时（含点 prev/next 按钮）：同步月份选择器并重新加载排期
// immediate 保证首屏即拉取当月数据
watch(
  calendarDate,
  (newDate) => {
    const m = dayjs(newDate).format('YYYY-MM')
    if (m !== selectedMonth.value) {
      selectedMonth.value = m
    }
    fetchSchedule(m)
  },
  { immediate: true }
)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.ad-schedule {
  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .page-title {
      font-size: 20px;
      font-weight: 700;
      color: $color-text-primary;
    }
  }

  .calendar-card {
    padding: 16px;
  }

  .legend {
    display: flex;
    gap: 20px;
    margin-bottom: 12px;
    padding: 8px 12px;
    background: $color-bg;
    border-radius: $radius-sm;

    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: $color-text-secondary;
    }

    .legend-dot {
      width: 12px;
      height: 12px;
      border-radius: 3px;

      &.dot-head {
        background: rgba(126, 206, 193, 0.5); // 薄荷青
      }
      &.dot-mid {
        background: rgba(255, 211, 224, 0.8); // 蜜桃粉
      }
      &.dot-tail {
        background: rgba(199, 206, 234, 0.7); // 浅紫
      }
    }
  }

  .date-cell {
    height: 100%;
    min-height: 80px;
    padding: 4px;
    display: flex;
    flex-direction: column;

    .date-num {
      font-size: 13px;
      font-weight: 600;
      color: $color-text-primary;
      margin-bottom: 4px;
    }

    .slots {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .slot {
      font-size: 11px;
      line-height: 1.4;
      display: flex;
      align-items: center;
      gap: 2px;
      padding: 2px 4px;
      border-radius: $radius-sm;
      overflow: hidden;

      .slot-label {
        color: $color-text-secondary;
        flex-shrink: 0;
        font-weight: 500;
      }

      .slot-name {
        color: $color-text-primary;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .slot-empty {
        color: $color-text-secondary;
      }

      // 三个广告位用马卡龙色系小标签区分，与图例颜色对应
      &.slot-head {
        background: rgba(126, 206, 193, 0.15); // 薄荷青
      }
      &.slot-mid {
        background: rgba(255, 211, 224, 0.5); // 蜜桃粉
      }
      &.slot-tail {
        background: rgba(199, 206, 234, 0.4); // 浅紫
      }
    }

    // 非当月日期弱化显示
    &.other-month {
      .date-num,
      .slot-label,
      .slot-name,
      .slot-empty {
        opacity: 0.4;
      }
    }
  }

  // 调整 el-calendar 内部样式以适配自定义日期格内容
  :deep(.el-calendar) {
    --el-calendar-border-color: #{$color-border};
  }

  :deep(.el-calendar-day) {
    height: auto;
    min-height: 90px;
    padding: 4px;

    &:hover {
      background: rgba(181, 234, 215, 0.15);
    }
  }

  :deep(.el-calendar-table__row td.is-selected) {
    background: rgba(181, 234, 215, 0.2);

    .date-num {
      color: $color-primary-dark;
    }
  }

  :deep(.el-calendar__header) {
    padding: 8px 12px;
  }

  :deep(.el-calendar__title) {
    color: $color-text-primary;
    font-weight: 600;
  }
}
</style>
