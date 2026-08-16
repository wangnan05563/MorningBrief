<template>
  <div class="m-alert">
    <div v-if="loading" class="m-empty">加载中…</div>

    <div v-else>
      <div class="m-alert__banner" :class="m.enabled ? 'm-alert__banner--on' : 'm-alert__banner--off'">
        <div class="m-alert__status">{{ m.enabled ? '系统处于维护 / 应急停服态' : '生产运行正常' }}</div>
        <div class="m-alert__sub" v-if="m.enabled && m.reason">原因：{{ m.reason }}</div>
        <div class="m-alert__sub" v-if="m.enabled && m.by">操作人：{{ m.by }} · {{ fmtDate(m.at) }}</div>
      </div>

      <p class="m-alert__tip">
        应急停服将<b>暂停所有新任务触发</b>（返回 409），不影响已在执行中的任务；恢复后自动放行。
        该操作仅超级管理员可用，且必须填写原因。
      </p>

      <button
        v-if="!m.enabled"
        class="m-btn m-btn--danger m-btn--block"
        @click="stop"
      >应急停服</button>
      <button
        v-else
        class="m-btn m-btn--primary m-btn--block"
        @click="resume"
      >解除应急停服</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getMaintenanceStatus, emergencyStop, emergencyResume } from '../../api/mobile'
import { ElMessage, ElMessageBox } from '../../utils/message'

const m = ref({ enabled: false, reason: null, by: null, at: null })
const loading = ref(false)

const fmtDate = (iso) => (iso ? iso.slice(0, 16).replace('T', ' ') : '-')

async function reload() {
  loading.value = true
  try {
    m.value = await getMaintenanceStatus().catch(() => ({ enabled: false }))
  } finally {
    loading.value = false
  }
}

async function stop() {
  let reason = ''
  try {
    const { value } = await ElMessageBox.prompt('请填写应急停服原因（必填）', '二次确认', {
      inputType: 'textarea',
      confirmButtonText: '确认停服',
      cancelButtonText: '取消',
      inputValidator: (v) => (v && v.trim() ? true : '原因不能为空'),
    })
    reason = v.trim()
  } catch {
    return // 取消
  }
  try {
    m.value = await emergencyStop({ reason })
    ElMessage.success('已应急停服')
  } catch {
    // 拦截器已提示
  }
}

async function resume() {
  try {
    await ElMessageBox.confirm('确认解除应急停服并恢复新任务触发？', '二次确认', {
      type: 'warning', confirmButtonText: '确认恢复', cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    m.value = await emergencyResume()
    ElMessage.success('已恢复生产')
  } catch {
    // 拦截器已提示
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

.m-alert__status {
  font-size: 16px;
  font-weight: 700;
}

.m-alert__banner--on .m-alert__status { color: #f56c6c; }
.m-alert__banner--off .m-alert__status { color: #67c23a; }

.m-alert__sub {
  font-size: 12px;
  color: #8a8f99;
  margin-top: 6px;
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

.m-empty {
  text-align: center;
  color: #b0b4bb;
  padding: 40px 0;
  font-size: 14px;
}
</style>
