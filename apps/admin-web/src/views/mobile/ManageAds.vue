<template>
  <div class="m-ads">
    <div v-if="loading && !list.length" class="m-empty">加载中…</div>
    <div v-else-if="!list.length" class="m-empty">暂无投放规则</div>

    <div v-for="p in list" :key="p.id" class="m-ads__item">
      <div class="m-ads__info">
        <div class="m-ads__name">
          {{ p.material_name || ('素材 #' + p.material_id) }}
          <span class="m-badge" :class="p.enabled ? 'm-badge--on' : 'm-badge--off'">
            {{ p.enabled ? '投放中' : '已停用' }}
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

const list = ref([])
const loading = ref(false)

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
  try {
    await updatePlacement(p.id, next)
    p.enabled = next
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
  background: #fff;
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
  color: #1f2329;
  display: flex;
  align-items: center;
  gap: 8px;
}

.m-ads__meta {
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
