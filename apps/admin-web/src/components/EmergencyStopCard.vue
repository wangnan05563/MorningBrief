<template>
  <div class="m-alert">
    <div v-if="loading && !m" class="m-empty">加载中…</div>

    <div v-else>
      <!-- 三态：停服 / 正常 / 状态未知。未知态此前被当成「正常」渲染（绿色横幅），是 T02489 的核心缺陷 -->
      <div class="m-alert__banner" :class="`m-alert__banner--${state}`">
        <div class="m-alert__status">{{ bannerTitle }}</div>

        <template v-if="state === 'unknown'">
          <div class="m-alert__sub">维护态接口读取失败：{{ loadError || '未知原因' }}</div>
          <div class="m-alert__sub">请重试确认状态后再执行停服 / 恢复操作。</div>
        </template>

        <template v-else-if="state === 'on'">
          <div class="m-alert__sub" v-if="m.reason">原因：{{ m.reason }}</div>
          <div class="m-alert__sub" v-if="m.by">操作人：{{ m.by }} · {{ fmtDate(m.at) }}</div>
          <div class="m-alert__sub m-alert__elapsed">已停服：{{ elapsed }}</div>
        </template>

        <div v-else class="m-alert__sub">未处于维护态，新任务可正常触发。</div>
      </div>

      <p class="m-alert__tip">
        应急停服将<b>暂停所有新任务触发</b>（返回 409），不影响已在执行中的任务；恢复后自动放行。
        该操作仅超级管理员可用，且必须填写原因。
        <b>停服不会自动到期恢复</b>，必须在这里手动解除。
      </p>

      <button v-if="state === 'unknown'" class="m-btn m-btn--primary m-btn--block" :disabled="loading" @click="reload">
        {{ loading ? '读取中…' : '重新读取状态' }}
      </button>

      <template v-else>
        <button
          v-if="state === 'off'"
          class="m-btn m-btn--danger m-btn--block"
          :disabled="submitting"
          @click="stop"
        >{{ submitting ? '提交中…' : '应急停服' }}</button>
        <button
          v-else
          class="m-btn m-btn--primary m-btn--block"
          :disabled="submitting"
          @click="resume"
        >{{ submitting ? '提交中…' : '解除应急停服' }}</button>
      </template>

      <!-- INT-UX-06：审计一直有写（操作者 + 原因），但唯一的审计接口按 category='db_admin'
           过滤，停服写的是 category='mobile'，值班在外面停完服回头查不到是谁、因为什么。
           这条列表把「谁 / 何时 / 因为什么」就地读出来。 -->
      <section class="m-alert__audit" data-guide="emergency-audit">
        <div class="m-alert__audit-title">停服 / 恢复记录</div>
        <div v-if="auditError" class="m-alert__audit-empty">记录读取失败：{{ auditError }}</div>
        <div v-else-if="!audit.length" class="m-alert__audit-empty">暂无记录</div>
        <ol v-else class="m-alert__audit-list" data-guide="emergency-audit-list">
          <li v-for="it in audit" :key="it.key" class="m-alert__audit-item">
            <span :class="['m-alert__audit-action', `m-alert__audit-action--${it.action}`]">
              {{ it.action === 'emergency_stop' ? '停服' : '恢复' }}
            </span>
            <span class="m-alert__audit-who">{{ it.operator || '未知操作人' }} · {{ fmtDate(it.at) }}</span>
            <div v-if="it.reason" class="m-alert__audit-reason">原因：{{ it.reason }}</div>
          </li>
        </ol>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  getMaintenanceStatus,
  emergencyStop,
  emergencyResume,
  getEmergencyAudit,
} from '../api/mobile'
import { ElMessage } from '../utils/message'
import { dangerConfirm, dangerConfirmWithReason } from '../utils/dangerConfirm'

// T02613：这份卡片原来长在移动端页 /m/manage/alert 上，PC 后台要停服得先切移动布局或掏手机，
// 高危动作的操作路径反而最长。抽成组件后由移动端页与 PC 系统维护页共用同一套逻辑与文案，
// 两端确认强度因此天然一致（改一端必漏另一端，共用一份才有意义）。
// 状态口令两端一致：停服要逐字输入「停服」，解除要逐字输入「解除停服」。
const STOP_CONFIRM_WORD = '停服'
const RESUME_CONFIRM_WORD = '解除停服'

// null = 状态未知（读失败），绝不能退化成 { enabled: false }
const m = ref(null)
const loading = ref(false)
const submitting = ref(false)
const loadError = ref('')
const audit = ref([])
const auditError = ref('')

const state = computed(() => (m.value === null ? 'unknown' : m.value.enabled ? 'on' : 'off'))
const bannerTitle = computed(() =>
  state.value === 'unknown'
    ? '维护态未知'
    : state.value === 'on'
      ? '系统处于维护 / 应急停服态'
      : '生产运行正常',
)

const fmtDate = (iso) => (iso ? iso.slice(0, 16).replace('T', ' ') : '-')

// 后端存的是本地 naive ISO（datetime.now().isoformat()），浏览器按本地时区解析即为正确时刻
const startedAt = computed(() => {
  const at = m.value?.at
  if (!at) return NaN
  const t = new Date(at).getTime()
  return Number.isFinite(t) ? t : NaN
})

const fmtElapsed = (sec) => {
  const h = Math.floor(sec / 3600)
  const min = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h) return `${h} 小时 ${min} 分 ${s} 秒`
  if (min) return `${min} 分 ${s} 秒`
  return `${s} 秒`
}

const now = ref(Date.now())
let timer = null
const elapsed = computed(() =>
  Number.isNaN(startedAt.value)
    ? '时长未知（停服记录缺少时间戳）'
    : fmtElapsed(Math.max(0, Math.floor((now.value - startedAt.value) / 1000))),
)

// 只在停服态跑秒，避免正常态下一个 1s 定时器空转
watch(
  state,
  (s) => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    if (s === 'on') {
      now.value = Date.now()
      timer = setInterval(() => {
        now.value = Date.now()
      }, 1000)
    }
  },
  { immediate: true },
)
onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const normalize = (data) => ({
  enabled: !!data?.enabled,
  reason: data?.reason ?? null,
  by: data?.by ?? null,
  at: data?.at ?? null,
})

async function reload() {
  loading.value = true
  try {
    m.value = normalize(await getMaintenanceStatus())
    loadError.value = ''
  } catch (e) {
    m.value = null
    loadError.value = e?.message || '接口调用失败'
  } finally {
    loading.value = false
  }
  await loadAudit()
}

// 记录列表读失败不拖累主状态：横幅讲「现在」，列表讲「历史上谁动的」
async function loadAudit() {
  try {
    const data = await getEmergencyAudit(10)
    audit.value = (data?.items || []).map((it, i) => ({ ...it, key: `${it.at || ''}-${it.action}-${i}` }))
    auditError.value = ''
  } catch (e) {
    audit.value = []
    auditError.value = e?.message || '接口调用失败'
  }
}

async function stop() {
  if (state.value === 'unknown') {
    ElMessage.warning('状态未知，请先重新读取后再执行停服')
    return
  }
  // T02596 + T02613：原因必填与确认词合并成一个确认框，两档强度都在同一道闸门里，
  // 拆开成两个弹窗只会让人关掉第一个再继续点第二个（连点即通过）。
  const { confirmed, reason } = await dangerConfirmWithReason({
    action: '应急停服',
    target: '生产调度（全部新任务触发）',
    scope: '调度开关 1 项（暂停新任务触发，返回 409）',
    lines: ['已在执行中的任务不受影响。', '停服不会自动到期恢复，必须手动解除。'],
    irreversible: '停服期间未触发的任务不会自动补跑。',
    reasonLabel: '停服原因（必填，会写入审计日志）',
    reasonPlaceholder: '例如：上游 TTS 全部超时，先止血',
    requireReason: true,
    confirmWord: STOP_CONFIRM_WORD,
    confirmLabel: '确认停服',
  })
  if (!confirmed) return
  submitting.value = true
  try {
    const data = await emergencyStop({ reason })
    m.value = normalize(data)
    ElMessage.success(
      data?.already ? '系统已处于停服态，本次未重复记录' : '已应急停服，新任务触发已暂停',
    )
  } catch {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
  await loadAudit()
}

async function resume() {
  if (state.value === 'unknown') {
    ElMessage.warning('状态未知，请先重新读取后再执行恢复')
    return
  }
  // T02596：恢复会立即放行新任务触发，按统一口径写明对象与停服期间的缺口
  const ok = await dangerConfirm({
    action: '解除应急停服',
    target: '生产调度（当前为停服态）',
    scope: '调度开关 1 项（恢复新任务触发）',
    lines: ['已在执行中的任务不受影响，恢复后自动放行新任务。'],
    irreversible: '停服期间未触发的任务不会自动补跑。',
    confirmWord: RESUME_CONFIRM_WORD,
    confirmLabel: '确认恢复',
  })
  if (!ok) return
  submitting.value = true
  try {
    const data = await emergencyResume()
    m.value = normalize(data)
    ElMessage.success(
      data?.already ? '系统本就是运行态，本次未重复记录' : '已恢复生产',
    )
  } catch {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
  await loadAudit()
}

onMounted(reload)
</script>

<style scoped>
.m-alert {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.m-alert__banner {
  border-radius: 12px;
  padding: 16px;
}

.m-alert__banner--on {
  background: var(--m-danger-soft);
  border: 1px solid var(--m-danger-line);
}

.m-alert__banner--off {
  background: var(--m-success-soft);
  border: 1px solid var(--m-success-line);
}

/* 未知态用警示色：既不是「一切正常」也不是「已停服」 */
.m-alert__banner--unknown {
  background: var(--m-warning-soft);
  border: 1px solid var(--m-warning-line);
}

.m-alert__status {
  font-size: 16px;
  font-weight: 700;
}

.m-alert__banner--on .m-alert__status { color: var(--m-danger); }
.m-alert__banner--off .m-alert__status { color: var(--m-success); }
.m-alert__banner--unknown .m-alert__status { color: var(--m-warning); }

.m-alert__sub {
  font-size: 12px;
  color: var(--m-text-sub);
  margin-top: 6px;
}

.m-alert__elapsed {
  font-weight: 600;
  color: var(--m-danger);
}

.m-alert__tip {
  font-size: 12px;
  color: var(--m-text-sub);
  line-height: 1.7;
  /* 提示与动作按钮同处一个块级容器里，拿不到 .m-alert 的 flex gap；
     不自己留白时，警告正文会直接贴在红色按钮上沿（PC 单行时最明显） */
  margin: 0 0 16px;
  padding: 0 2px;
}

.m-btn {
  height: 46px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}

.m-btn--block { width: 100%; }

.m-btn--primary { background: var(--m-solid-primary); color: var(--m-on-solid); }
.m-btn--danger { background: var(--m-solid-danger); color: var(--m-on-solid); }
.m-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.m-empty {
  text-align: center;
  color: var(--m-text-sub);
  padding: 40px 0;
  font-size: 14px;
}

/* 记录列表走主题变量，别再往暗色主题上贴一块不透明底色（NFR-UX-04 的坑） */
.m-alert__audit {
  border-top: 1px solid var(--m-border);
  padding-top: 12px;
}

.m-alert__audit-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--m-text);
}

.m-alert__audit-empty {
  font-size: 12px;
  color: var(--m-text-sub);
  margin-top: 8px;
}

.m-alert__audit-list {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
}

.m-alert__audit-item {
  font-size: 12px;
  color: var(--m-text-sub);
  padding: 6px 0;
  border-bottom: 1px dashed var(--m-border);
}

.m-alert__audit-item:last-child {
  border-bottom: none;
}

.m-alert__audit-action {
  font-weight: 600;
  margin-right: 6px;
}

.m-alert__audit-action--emergency_stop { color: var(--m-danger); }
.m-alert__audit-action--emergency_resume { color: var(--m-success); }

.m-alert__audit-reason {
  margin-top: 2px;
  color: var(--m-text);
  /* T03714：与 AuditTrail 的 __why 同类（值班速读的人写原因），只留 overflow-wrap：
     无空格长串照样断开，中英混排里 confirm 这类英文词不再被 break-all 从行尾硬拆 */
  overflow-wrap: anywhere;
}
</style>
