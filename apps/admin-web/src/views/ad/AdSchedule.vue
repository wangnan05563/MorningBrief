<template>
  <div data-guide="ads-schedule-page" class="page-container ad-schedule">
    <div class="toolbar">
      <!-- T00811：移除与导航栏重复的页面标题，仅保留月份选择 -->
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
      <!-- D25（FR-UX-302）：拉取失败时日历整块撤下。留着它只会满屏「—」，
           而「—」在本页的意思恰恰是「该日无排期」——把接口故障说成没排期，
           正是这一批缺陷的母题。错误态自带重试，不依赖会被 document.hidden 吞掉的 toast。 -->
      <ListLoadError
        v-if="loadError"
        :message="loadError"
        :retrying="retrying"
        @retry="retryLoadSchedule"
      />

      <!-- 图例：帮助用户快速识别三个广告位的颜色含义（文案取自枚举字典，T02504） -->
      <div v-else class="legend">
        <div v-for="p in positionOptions" :key="p.value" class="legend-item">
          <span class="legend-dot" :class="`dot-${p.value}`"></span>
          <span>{{ p.label }}（{{ p.value }}）</span>
        </div>
      </div>

      <!-- T02544 / D83：整月没有排期时，日历满屏「—」与「接口失败」在视觉上无从区分。
           加载成功但确为空，就明说空，并给出下一步（去投放规则新建） -->
      <div
        v-if="!loadError && !loading && !hasMonthData"
        data-guide="ads-month-empty"
        class="month-empty-hint"
      >
        {{ selectedMonth }} 暂无排期。可到「广告 → 投放规则」新建投放，或切换月份查看其他排期。
      </div>

      <el-calendar v-if="!loadError" data-guide="ads-schedule-calendar" v-model="calendarDate" v-loading="loading">
        <template #date-cell="{ data }">
          <div class="date-cell" :class="{ 'other-month': data.type !== 'current-month' }">
            <div class="date-num">{{ data.day.split('-').slice(2).join('') }}</div>
            <div class="slots">
              <div
                v-for="pos in positionValues"
                :key="pos"
                class="slot"
                :class="[`slot-${pos}`, slotStateClass(data.day, pos)]"
              >
                <span class="slot-label">{{ enumLabel(AD_POSITION, pos) }}</span>
                <span v-if="getSlotMaterial(data.day, pos)" class="slot-name">
                  {{ getSlotMaterial(data.day, pos).material_name }}
                </span>
                <span v-else class="slot-empty">—</span>
                <!-- T02602：四态由服务端派生，待投放/已过期也要与「今天在播」区分开 -->
                <span
                  v-if="slotStatusTag(data.day, pos)"
                  class="slot-status-tag"
                  :class="`slot-status-tag--${slotStatusTag(data.day, pos).tone}`"
                >
                  {{ slotStatusTag(data.day, pos).label }}
                </span>
                <!-- T02927：角标可点开冲突清单，列出全部重叠投放并支持就地停用其一。
                     重叠已不允许新建，能出现在这里的多半是历史数据——光「看见」
                     不够，还要能当场处置，否则运营只能去投放规则页逐条比对。 -->
                <el-popover
                  v-if="slotConflicts(data.day, pos).length > 0"
                  trigger="click"
                  placement="top"
                  :width="320"
                  popper-class="slot-conflict-popover"
                >
                  <template #reference>
                    <span
                      class="slot-conflict"
                      :data-guide="`ads-conflict-${data.day}-${pos}`"
                    >+{{ slotConflicts(data.day, pos).length }} 条重叠</span>
                  </template>
                  <div class="conflict-panel">
                    <div class="conflict-panel__title">
                      {{ enumLabel(AD_POSITION, pos) }}位 · {{ data.day }} 当天有
                      {{ slotEntries(data.day, pos).length }} 条投放重叠
                    </div>
                    <div
                      v-for="item in slotEntries(data.day, pos)"
                      :key="item.id"
                      class="conflict-panel__row"
                      :data-placement-id="item.id"
                    >
                      <div class="conflict-panel__meta">
                        <span class="conflict-panel__name">{{ item.material_name }}</span>
                        <span class="conflict-panel__range">{{ item.start_date }} ~ {{ item.end_date }}</span>
                      </div>
                      <span
                        class="conflict-panel__status"
                        :class="`conflict-panel__status--${placementStatusMeta(item.status).tone}`"
                      >{{ placementStatusMeta(item.status).label }}</span>
                      <el-button
                        v-if="item.enabled === 1"
                        link
                        type="danger"
                        size="small"
                        :loading="disablingIds.includes(item.id)"
                        @click="disableFromConflict(item)"
                      >停用</el-button>
                    </div>
                    <div class="conflict-panel__hint">
                      同一广告位当天只应有一条启用中的投放；停用后该投放不再播出
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </div>
        </template>
      </el-calendar>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import dayjs from 'dayjs'
import api from '../../api'
import { ElMessage } from '../../utils/message'
import { dangerConfirm } from '../../utils/dangerConfirm'
import ListLoadError from '../../components/ListLoadError.vue'
import { AD_POSITION, enumLabel, enumOptions } from '../../constants/enums'
import { buildScheduleMap } from '../../utils/scheduleMap'
import { placementStatusMeta } from '../../utils/placementStatus'

const loading = ref(false)
// D25（FR-UX-302）：页内错误态。与拦截器 toast 并存但不依赖它——toast 会消失，
// 而且页面 hidden 时会被反馈队列延后，用户回到页面时看不到「这次没加载成功」。
const loadError = ref('')
const retrying = ref(false)
// 月份选择器的值（YYYY-MM 字符串），作为月份切换的数据源
const selectedMonth = ref(dayjs().format('YYYY-MM'))
// el-calendar 的 v-model 需要 Date 对象，用当月1号作为锚点
const calendarDate = ref(dayjs().startOf('month').toDate())

const scheduleMap = ref({})

// D83（T02544）：排期表按天分桶，整月无排期时日历全是「—」；
// 用数据本身判断空月，而不是拿「—」的多少去猜
const hasMonthData = computed(() =>
  Object.keys(scheduleMap.value).some((day) => day.startsWith(selectedMonth.value)),
)

// 广告位文案与投放规则页同源（src/constants/enums.js，FR-UX-405 / T02504）
const positionOptions = enumOptions(AD_POSITION)
const positionValues = positionOptions.map((o) => o.value)

function getSlotMaterial(dayStr, pos) {
  return scheduleMap.value[dayStr]?.[pos] || null
}

// 停用/待投放/已过期状态在排期上必须可见：否则日历与投放规则页两处口径不一致
// （T02491 / D14，T02602 把后两态补齐）。status 由服务端派生，日历不再按 enabled 猜。
function slotStatus(dayStr, pos) {
  return getSlotMaterial(dayStr, pos)?.status
}

// 「生效中」不额外加标签，其余三态各自带文字与色调
function slotStatusTag(dayStr, pos) {
  const status = slotStatus(dayStr, pos)
  if (!status || status === 'active') return null
  return placementStatusMeta(status)
}

function slotStateClass(dayStr, pos) {
  const tag = slotStatusTag(dayStr, pos)
  return tag ? `slot-${tag.tone}` : ''
}

// D24：同位同日重叠的其他投放。日历只能主显一条，其余折叠进角标 + tooltip，
// 否则「看不见的冲突」会被读成「这个位子很干净」。
function slotConflicts(dayStr, pos) {
  return getSlotMaterial(dayStr, pos)?.conflicts || []
}

// 冲突面板要列出「主显那条 + 被折叠的其余投放」，并带上 id / 区间以便停用其一
function slotEntries(dayStr, pos) {
  const primary = getSlotMaterial(dayStr, pos)
  if (!primary) return []
  return [primary, ...(primary.conflicts || [])]
}

const disablingIds = ref([])

// 历史重叠数据的就地处置：复用的正是投放规则页那条 enabled 开关（T02491 / D14），
// 停用后后端会失效生效投放缓存，C 端下一期起不再播出。
async function disableFromConflict(item) {
  const ok = await dangerConfirm({
    action: '停用投放',
    target: `素材「${item.material_name}」`,
    scope: `生效区间 ${item.start_date} ~ ${item.end_date}`,
    lines: [
      '停用后，之后新生成的节目不再插入该广告；生效投放缓存同步失效。',
      '已经生成好的节目里广告是拼在音频里的，停用不会把它们里面的广告去掉。',
    ],
    irreversible: '启停可随时回退，不影响已生成的节目数据。',
    confirmLabel: '确认停用',
  })
  if (!ok) return
  disablingIds.value = [...disablingIds.value, item.id]
  try {
    await api.put(`/ads/placements/${item.id}`, { enabled: 0 })
    ElMessage.success('已停用该投放')
    // 重新拉取排期：冲突角标与主显要随停用一起消失，不能留在界面上说「还在重叠」
    await fetchSchedule(selectedMonth.value)
  } catch {
    // 失败提示由拦截器负责；界面保持原样，不假装已停用
  } finally {
    disablingIds.value = disablingIds.value.filter((id) => id !== item.id)
  }
}

async function fetchSchedule(monthStr) {
  loading.value = true
  try {
    const data = await api.get('/ads/schedule', {
      params: { month: monthStr },
    })
    // 后端返回 { placements: [{material_name, position, start_date, end_date, enabled}] }
    // 整形逻辑在 utils/scheduleMap（D24：重叠投放必须可见，不能后写覆盖前写）
    scheduleMap.value = buildScheduleMap(data.placements)
    loadError.value = ''
  } catch (e) {
    // D25：失败时**必须清掉上月数据**。此前 catch 都不写，scheduleMap 保留上一月份，
    // 切到新月份后满屏「—」＝「本月无排期」的误读；清掉之后再由错误态接管渲染。
    scheduleMap.value = {}
    loadError.value = e?.message || '排期接口请求失败'
  } finally {
    loading.value = false
    retrying.value = false
  }
}

// D25：重试按「当前所选月份」重新发起，而不是让用户自己去切一次月份
function retryLoadSchedule() {
  retrying.value = true
  return fetchSchedule(selectedMonth.value)
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

  .month-empty-hint {
    margin-bottom: 12px;
    padding: 8px 12px;
    color: $color-text-secondary;
    background: $color-bg;
    border-radius: $radius-sm;
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

      // 已停用：整格灰化 + 显式标签，避免「日历上看着在排、实际不播」
      &.slot-off {
        .slot-name,
        .slot-label {
          opacity: 0.45;
        }

        .slot-name {
          text-decoration: line-through;
        }
      }

      // 待投放：开关是开的，但与今天无关（T02602）
      &.slot-pending {
        .slot-name {
          opacity: 0.7;
        }
      }

      // 已过期：区间已结束，同样不是「今天在播」
      &.slot-expired {
        .slot-name {
          opacity: 0.55;
        }
      }

      .slot-status-tag {
        flex-shrink: 0;
        margin-left: auto;
        font-size: 10px;
        line-height: 1.2;
        color: $color-danger;

        &--pending {
          color: #b88230;
        }

        &--expired {
          color: $color-text-secondary;
        }
      }

      // D24：重叠角标。不能只在 hover Tooltip 里说——不悬停就看不见，等于没说
      .slot-conflict {
        flex-shrink: 0;
        margin-left: 4px;
        padding: 0 4px;
        font-size: 10px;
        line-height: 1.4;
        border-radius: 6px;
        // $color-warning 是 var() 不是色值，rgba() 编译不过，与 DatabaseAdmin 同法直接用作底色
        color: #5b3d00;
        background: $color-warning;
        cursor: pointer;
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

// 冲突面板内容被 Teleport 到 body，不能挂在 .ad-schedule 下面；
// scoped 属性仍随父组件编译，样式照常生效
.conflict-panel {
  font-size: 12px;

  &__title {
    margin-bottom: 8px;
    font-weight: 600;
    color: $color-text-primary;
  }

  &__row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    border-top: 1px solid var(--el-border-color-lighter);
  }

  &__meta {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  &__name {
    color: $color-text-primary;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__range {
    font-size: 11px;
    color: $color-text-secondary;
  }

  &__status {
    flex-shrink: 0;
    color: var(--el-color-success-dark, #529b2e);

    &--pending {
      color: #b88230;
    }

    &--off,
    &--expired {
      color: $color-text-secondary;
    }
  }

  &__hint {
    margin-top: 6px;
    color: $color-text-secondary;
  }
}
</style>
