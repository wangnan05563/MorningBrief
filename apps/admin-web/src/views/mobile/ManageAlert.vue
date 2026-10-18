<template>
  <div class="m-alert">
    <div v-if="loading && !m" class="m-empty">加载中…</div>

    <div v-else>
      <!-- 三态：停服 / 正常 / 状态未知。未知态此前被当成「正常」渲染（绿色横幅），是本单核心缺陷 -->
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
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getMaintenanceStatus, emergencyStop, emergencyResume } from '../../api/mobile'
import { ElMessage, ElMessageBox } from '../../utils/message'

// null = 状态未知（读失败），绝不能退化成 { enabled: false }
const m = ref(null)
const loading = ref(false)
const submitting = ref(false)
const loadError = ref('')

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
}

async function stop() {
  if (state.value === 'unknown') {
    ElMessage.warning('状态未知，请先重新读取后再执行停服')
    return
  }
  let reason = ''
  try {
    const { value } = await ElMessageBox.prompt('请填写应急停服原因（必填）', '二次确认', {
      inputType: 'textarea',
      confirmButtonText: '确认停服',
      cancelButtonText: '取消',
      inputValidator: (v) => (v && v.trim() ? true : '原因不能为空'),
    })
    reason = (value || '').trim()
  } catch {
    return // 取消
  }
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
}

async function resume() {
  if (state.value === 'unknown') {
    ElMessage.warning('状态未知，请先重新读取后再执行恢复')
    return
  }
  try {
    await ElMessageBox.confirm('确认解除应急停服并恢复新任务触发？', '二次确认', {
      type: 'warning', confirmButtonText: '确认恢复', cancelButtonText: '取消',
    })
  } catch {
    return
  }
  submitting.value = true
  try {
    m.value = normalize(await emergencyResume())
    ElMessage.success('已恢复生产')
  } catch {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
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
  background: #fef0f0;
  border: 1px solid #fbc4c4;
}

.m-alert__banner--off {
  background: #f0f9eb;
  border: 1px solid #c2e7b0;
}

/* 未知态用警示色：既不是「一切正常」也不是「已停服」 */
.m-alert__banner--unknown {
  background: #fdf6ec;
  border: 1px solid #f3d19e;
}

.m-alert__status {
  font-size: 16px;
  font-weight: 700;
}

.m-alert__banner--on .m-alert__status { color: #f56c6c; }
.m-alert__banner--off .m-alert__status { color: #67c23a; }
.m-alert__banner--unknown .m-alert__status { color: #e6a23c; }

.m-alert__sub {
  font-size: 12px;
  color: #8a8f99;
  margin-top: 6px;
}

.m-alert__elapsed {
  font-weight: 600;
  color: #f56c6c;
}

.m-alert__tip {
  font-size: 12px;
  color: #8a8f99;
  line-height: 1.7;
  margin: 0;
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

.m-btn--primary { background: var(--el-color-primary, #409eff); color: #fff; }
.m-btn--danger { background: #f56c6c; color: #fff; }
.m-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.m-empty {
  text-align: center;
  color: #b0b4bb;
  padding: 40px 0;
  font-size: 14px;
}
</style>
