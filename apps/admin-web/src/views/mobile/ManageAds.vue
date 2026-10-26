<template>
  <div class="m-ads">
    <div v-if="loading && !list.length" class="m-empty">加载中…</div>
    <div v-else-if="!list.length" class="m-empty">暂无投放规则</div>

    <div v-for="p in list" :key="p.id" class="m-ads__item">
      <div class="m-ads__info">
        <div class="m-ads__name">
          {{ p.material_name || ('素材 #' + p.material_id) }}
          <!-- T02602：四态由服务端派生，启用但未开始/已结束不能再显示成「投放中」 -->
          <span class="m-badge" :class="`m-badge--${statusTone(p.status)}`">
            {{ statusLabel(p.status) }}
          </span>
        </div>
        <div class="m-ads__meta" v-if="p.position">位置：{{ p.position }}</div>
        <div class="m-ads__meta">
          周期：{{ p.start_date || '—' }} ~ {{ p.end_date || '—' }}
        </div>
      </div>
      <button
        class="m-btn m-btn--sm"
        :class="p.enabled ? 'm-btn--danger' : 'm-btn--primary'"
        @click="toggle(p)"
      >
        {{ p.enabled ? '停用' : '启用' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listPlacements, updatePlacement } from '../../api/ads'
import { ElMessage } from '../../utils/message'
import { dangerConfirm } from '../../utils/dangerConfirm'
import { placementStatusMeta } from '../../utils/placementStatus'

const list = ref([])
const loading = ref(false)

const statusLabel = (status) => placementStatusMeta(status).label
const statusTone = (status) => placementStatusMeta(status).tone

async function reload() {
  loading.value = true
  try {
    const data = await listPlacements({ page: 1, size: 50 })
    list.value = data.list || []
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function toggle(p) {
  const next = p.enabled ? 0 : 1
  // 启停直接改变线上曝光，与用户禁用有确认的口径对齐（I45）
  const ok = await dangerConfirm({
    action: next ? '启用广告投放' : '停用广告投放',
    target: `投放「${p.material_name || p.id}」`,
    scope: next
      ? '之后新生成的节目在排期区间内恢复插入该广告'
      : '之后新生成的节目不再插入该广告，已排期不变',
    irreversible: '广告是生成节目时拼进音频的：停用不会去掉已生成节目里的广告。',
    confirmLabel: next ? '确认启用' : '确认停用',
  })
  if (!ok) return
  try {
    const data = await updatePlacement(p.id, next)
    p.enabled = data.enabled
    // 服务端派生状态直接落位：重新启用已过期的投放应显示「已过期」而非「投放中」（T02602）
    p.status = data.status
    ElMessage.success(next ? '已启用投放' : '已停用投放')
  } catch {
    // 拦截器已提示
  }
}

onMounted(reload)
</script>

<style scoped>
.m-ads {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-ads__item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--m-surface);
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-ads__info {
  flex: 1;
  min-width: 0;
}

.m-ads__name {
  font-size: 15px;
  font-weight: 600;
  color: var(--m-text);
  display: flex;
  align-items: center;
  gap: 8px;
}

.m-ads__meta {
  font-size: 12px;
  color: var(--m-text-sub);
  margin-top: 4px;
}

.m-badge {
  font-size: 11px;
  border-radius: 4px;
  padding: 1px 6px;
  font-weight: 500;
}

.m-badge--on { color: var(--m-success); background: var(--m-success-soft); }
.m-badge--off { color: var(--m-danger); background: var(--m-danger-soft); }
.m-badge--pending { color: var(--m-warning); background: var(--m-warning-soft); }
.m-badge--expired { color: var(--m-text-sub); background: var(--m-bg); }

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

.m-btn--primary { background: var(--m-solid-primary); color: var(--m-on-solid); }
.m-btn--danger { background: var(--m-surface); color: var(--m-danger); border: 1px solid var(--m-danger-line); }

.m-empty {
  text-align: center;
  color: var(--m-text-sub);
  padding: 40px 0;
  font-size: 14px;
}
</style>
