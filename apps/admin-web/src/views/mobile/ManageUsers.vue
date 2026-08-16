<template>
  <div class="m-users">
    <div class="m-users__search">
      <el-input
        v-model="keyword"
        placeholder="搜索昵称 / openid"
        clearable
        size="default"
        @keyup.enter="reload"
        @clear="reload"
      />
      <button class="m-btn m-btn--ghost m-users__searchbtn" @click="reload">搜索</button>
    </div>

    <div v-if="loading && !list.length" class="m-empty">加载中…</div>
    <div v-else-if="!list.length" class="m-empty">暂无用户</div>

    <div v-for="u in list" :key="u.id" class="m-users__item">
      <div class="m-users__info">
        <div class="m-users__name">
          {{ u.nickname || '匿名用户' }}
          <span class="m-badge" :class="u.disabled ? 'm-badge--off' : 'm-badge--on'">
            {{ u.disabled ? '已禁用' : '正常' }}
          </span>
        </div>
        <div class="m-users__meta">openid：{{ mask(u.openid) }}</div>
        <div class="m-users__meta">
          收听 {{ fmt(u.total_listen_count) }} 次 · {{ fmt(u.total_listen_duration) }} 秒 · 注册 {{ fmtDate(u.created_at) }}
        </div>
      </div>
      <button
        class="m-btn m-btn--sm"
        :class="u.disabled ? 'm-btn--primary' : 'm-btn--danger'"
        @click="toggle(u)"
      >
        {{ u.disabled ? '启用' : '禁用' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listUsers, toggleUserStatus } from '../../api/users'
import { ElMessage, ElMessageBox } from '../../utils/message'

const keyword = ref('')
const list = ref([])
const loading = ref(false)

const fmt = (v) => (v == null ? 0 : Number(v).toLocaleString('zh-CN'))
const mask = (s) =>
  !s ? '-' : s.length > 12 ? s.slice(0, 6) + '****' + s.slice(-4) : s

function fmtDate(iso) {
  if (!iso) return '-'
  return iso.slice(0, 10)
}

async function reload() {
  loading.value = true
  try {
    const data = await listUsers({ keyword: keyword.value || undefined, page: 1, size: 50 })
    list.value = data.list || []
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function toggle(u) {
  const next = u.disabled ? 0 : 1
  const action = next ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(
      `确认${action}用户「${u.nickname || u.openid}」？`,
      '二次确认',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }
    )
  } catch {
    return // 取消
  }
  try {
    await toggleUserStatus(u.id, next)
    u.disabled = next
    ElMessage.success(`已${action}`)
  } catch {
    // 拦截器已提示
  }
}

onMounted(reload)
</script>

<style scoped>
.m-users {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.m-users__search {
  display: flex;
  gap: 8px;
}

.m-users__searchbtn {
  flex: 0 0 auto;
  height: 32px;
  padding: 0 16px;
}

.m-users__item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-users__info {
  flex: 1;
  min-width: 0;
}

.m-users__name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2329;
  display: flex;
  align-items: center;
  gap: 8px;
}

.m-users__meta {
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

.m-badge--on {
  color: #67c23a;
  background: #f0f9eb;
}

.m-badge--off {
  color: #f56c6c;
  background: #fef0f0;
}

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

.m-btn--primary {
  background: var(--el-color-primary, #409eff);
  color: #fff;
}

.m-btn--danger {
  background: #fff;
  color: #f56c6c;
  border: 1px solid #fbc4c4;
}

.m-btn--ghost {
  background: #fff;
  border: 1px solid #dcdfe6;
  color: #4e5969;
}

.m-empty {
  text-align: center;
  color: #b0b4bb;
  padding: 40px 0;
  font-size: 14px;
}
</style>
