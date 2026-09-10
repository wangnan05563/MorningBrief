<template>
  <el-tooltip
    :disabled="syncSupported"
    :content="unsupportedTip"
    placement="top"
  >
    <span class="voice-sync-wrap">
      <el-button
        :icon="Refresh"
        :loading="syncing"
        :disabled="!syncSupported"
        circle
        :title="metaTitle"
        @click="onSync"
      />
      <!-- 官方同步缓存角标：绿点=当前列表来自官方同步，悬停显示同步时间 -->
      <span v-if="meta.is_custom && !props.disabled" class="voice-sync-dot" :title="metaTitle"></span>
    </span>
  </el-tooltip>

  <!-- 重置入口：仅已同步过的引擎展示，用于回退内置清单 -->
  <el-dropdown v-if="meta.is_custom && !syncing" trigger="click" @command="onCommand">
    <el-button link type="info" class="voice-sync-more">
      <el-icon><MoreFilled /></el-icon>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="reset">恢复内置清单</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
/**
 * VoiceSyncButton —— TTS 音色官方同步按钮（T00388）
 *
 * 用途：放在「音色组合」多选与各引擎「音色」下拉右侧，一键从官方接口
 * 拉取最新音色列表并持久化（后端 ai_config 表 tts_voices_cache_<provider>）。
 *
 * 支持引擎：edge（微软官方目录，无鉴权）/ tencent（DescribeVoices，TC3 签名）。
 * aliyun / kokoro / piper 无公开官方列表接口 → 按钮禁用 + tooltip 说明，
 * 明确不做伪同步。
 *
 * 事件：synced(items) —— 同步成功后把新列表抛给父组件刷新下拉。
 */
import { computed, reactive, ref, watch } from 'vue'
import { Refresh, MoreFilled } from '@element-plus/icons-vue'
import api from '../api'
import { ElMessage, ElMessageBox } from '../utils/message'

const props = defineProps({
  provider: { type: String, required: true },
  // 宿主控件（如音色组合多选）被禁用时同步按钮一并禁用
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['synced', 'meta'])

// 与后端 VOICES_SYNC_SUPPORTED 对齐
const SYNC_SUPPORTED = ['edge', 'tencent']
const PROVIDER_LABEL = {
  edge: 'Edge-TTS（微软官方目录）',
  tencent: '腾讯云（DescribeVoices 官方接口）',
  aliyun: '阿里云 NLS 无公开音色列表 API，音色清单为内置静态维护',
  kokoro: 'Kokoro 为本地离线引擎，音色清单为内置静态维护',
  piper: 'Piper 为本地离线引擎，音色清单为内置静态维护',
}

const syncing = ref(false)
const meta = reactive({ is_custom: false, synced_at: '', count: 0, source: '' })

const syncSupported = computed(() => !props.disabled && SYNC_SUPPORTED.includes(props.provider))
const unsupportedTip = computed(() => PROVIDER_LABEL[props.provider] || '该引擎不支持官方音色同步')
const metaTitle = computed(() =>
  meta.is_custom
    ? `来自官方同步：${meta.count} 个音色（${formatTime(meta.synced_at)}）`
    : '内置静态清单，点击按钮可从官方接口同步'
)

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('zh-CN', { hour12: false })
}

async function loadMeta() {
  if (!props.provider) return
  try {
    const data = await api.get('/ai/voices/meta', { params: { provider: props.provider } })
    Object.assign(meta, data || {})
    emit('meta', { ...meta })
  } catch (e) {
    // 拦截器已提示；角标静默回退为内置态
    Object.assign(meta, { is_custom: false, synced_at: '', count: 0, source: '' })
  }
}

async function onSync() {
  if (syncing.value) return
  syncing.value = true
  try {
    const data = await api.post('/ai/voices/sync', { provider: props.provider })
    const count = (data && data.count) || (data && data.items && data.items.length) || 0
    Object.assign(meta, {
      is_custom: true,
      synced_at: (data && data.synced_at) || '',
      count,
      source: (data && data.source) || '',
    })
    emit('meta', { ...meta })
    emit('synced', (data && data.items) || [])
    ElMessage.success(`已同步官方音色 ${count} 个`)
  } catch (e) {
    // 失败不中断使用：本地列表保持原样（后端同样保留原列表）
    ElMessage.error(e && e.message ? e.message : '音色同步失败，请稍后重试')
  } finally {
    syncing.value = false
  }
}

async function onCommand(cmd) {
  if (cmd !== 'reset') return
  try {
    await ElMessageBox.confirm(
      '将清除官方同步缓存，音色下拉回退为内置静态清单。已保存的音色选择不受影响。',
      '恢复内置清单',
      { type: 'warning', confirmButtonText: '恢复', cancelButtonText: '取消' }
    )
  } catch (e) {
    return
  }
  syncing.value = true
  try {
    await api.delete('/ai/voices/sync', { params: { provider: props.provider } })
    Object.assign(meta, { is_custom: false, synced_at: '', count: 0, source: '' })
    emit('meta', { ...meta })
    emit('synced', null) // null = 让父组件重新走 loadVoices 拉内置清单
    ElMessage.success('已恢复内置音色清单')
  } catch (e) {
    ElMessage.error('恢复失败，请稍后重试')
  } finally {
    syncing.value = false
  }
}

watch(() => props.provider, loadMeta, { immediate: true })
</script>

<style scoped>
.voice-sync-wrap {
  position: relative;
  display: inline-flex;
  margin-left: 8px;
  vertical-align: middle;
}

/* 右上角绿点：标识当前列表来自官方同步（而非内置清单） */
.voice-sync-dot {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-color-success);
  pointer-events: auto;
  cursor: help;
}

.voice-sync-more {
  margin-left: 4px;
  vertical-align: middle;
}
</style>
