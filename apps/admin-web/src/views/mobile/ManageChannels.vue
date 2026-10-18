<template>
  <div class="m-ch">
    <div v-if="loading && !list.length" class="m-empty">加载中…</div>
    <div v-else-if="!list.length" class="m-empty">暂无频道</div>

    <div v-for="c in list" :key="c.id" class="m-ch__item">
      <div class="m-ch__info">
        <div class="m-ch__name">
          {{ c.name }}
          <span class="m-badge" :class="c.is_active ? 'm-badge--on' : 'm-badge--off'">
            {{ c.is_active ? '启用' : '停用' }}
          </span>
        </div>
        <div class="m-ch__desc">{{ c.description || '暂无描述' }}</div>
        <div class="m-ch__meta" v-if="c.schedule_time">定时：{{ c.schedule_time }}</div>
      </div>
      <button
        class="m-btn m-btn--sm"
        :class="c.is_active ? 'm-btn--danger' : 'm-btn--primary'"
        @click="toggle(c)"
      >
        {{ c.is_active ? '停用' : '启用' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listChannels, updateChannel } from '../../api/channels'
import { ElMessage } from '../../utils/message'
import { dangerConfirm } from '../../utils/dangerConfirm'

const list = ref([])
const loading = ref(false)

async function reload() {
  loading.value = true
  try {
    const data = await listChannels(false)
    list.value = Array.isArray(data) ? data : (data.list || [])
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function toggle(c) {
  const next = c.is_active ? 0 : 1
  if (!next) {
    // 停用是线上影响动作：该频道 queued 任务会被取消、内容停止产出（I42）
    const ok = await dangerConfirm({
      action: '停用频道',
      target: `频道「${c.name || c.id}」`,
      scope: '该频道下排队中的工作流任务会被取消，新内容不再产出',
      lines: ['C 端该频道页面将不再更新。'],
      irreversible: '被取消的排队任务不会自动恢复，重新启用后需要手工重跑。',
      confirmLabel: '确认停用',
    })
    if (!ok) return
  }
  try {
    await updateChannel(c.id, { is_active: next })
    c.is_active = next
    ElMessage.success(next ? '已启用' : '已停用')
  } catch {
    // 拦截器已提示
  }
}

onMounted(reload)
</script>

<style scoped>
.m-ch {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-ch__item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-ch__info {
  flex: 1;
  min-width: 0;
}

.m-ch__name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2329;
  display: flex;
  align-items: center;
  gap: 8px;
}

.m-ch__desc {
  font-size: 12px;
  color: #8a8f99;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-ch__meta {
  font-size: 12px;
  color: #8a8f99;
  margin-top: 4px;
}

.m-badge {
  font-size: 11px;
  border-radius: 4px;
  padding: 1px 6px;
  font-weight: 500;
}

.m-badge--on { color: #67c23a; background: #f0f9eb; }
.m-badge--off { color: #f56c6c; background: #fef0f0; }

.m-btn {
  height: 46px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}

.m-btn--sm {
  flex: 0 0 auto;
  height: 34px;
  padding: 0 14px;
  font-size: 14px;
}

.m-btn--primary { background: var(--el-color-primary, #409eff); color: #fff; }
.m-btn--danger { background: #fff; color: #f56c6c; border: 1px solid #fbc4c4; }

.m-empty {
  text-align: center;
  color: #b0b4bb;
  padding: 40px 0;
  font-size: 14px;
}
</style>
