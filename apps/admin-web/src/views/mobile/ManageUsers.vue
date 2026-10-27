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
          收听 {{ metricText(u.total_listen_count, meta.total_listen_count) }} · {{ metricText(u.total_listen_duration, meta.total_listen_duration) }} · 注册 {{ fmtDate(u.created_at) }}
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

    <!-- T02909：停用/启用终端用户写在 category=user，此前没有读口。
         移动端就是用户管理的落地页，审计要挂在同一页 -->
    <AuditTrail category="user" guide="user-audit" title="最近启停审计" :limit="5" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listUsers, toggleUserStatus } from '../../api/users'
import { ElMessage } from '../../utils/message'
import { dangerConfirm } from '../../utils/dangerConfirm'
import { metricText } from '../../utils/format'
import AuditTrail from '../../components/AuditTrail.vue'

const keyword = ref('')
const list = ref([])
const loading = ref(false)
// 累计收听是「用户注册以来」的 lifetime 口径，单位与起点均来自后端 meta（T02708）
const meta = ref({})

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
    meta.value = data.meta || {}
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function toggle(u) {
  const next = u.disabled ? 0 : 1
  const action = next ? '禁用' : '启用'
  const ok = await dangerConfirm({
    action: `${action}用户`,
    target: `「${u.nickname || u.openid}」`,
    scope: '用户 1 个',
    lines: next
      ? ['禁用后该用户无法登录管理端与小程序，进行中的会话会在下次校验时失效。']
      : ['启用后该用户可以重新登录。'],
    irreversible: next
      ? '禁用可随时改回启用，但禁用期间的访问不会被补回。'
      : '启用可随时改回禁用。',
    confirmLabel: `确认${action}`,
  })
  if (!ok) return // 取消
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
  background: var(--m-surface);
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
  color: var(--m-text);
  display: flex;
  align-items: center;
  gap: 8px;
}

.m-users__meta {
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

.m-badge--on {
  color: var(--m-success);
  background: var(--m-success-soft);
}

.m-badge--off {
  color: var(--m-danger);
  background: var(--m-danger-soft);
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
  background: var(--m-solid-primary);
  color: var(--m-on-solid);
}

.m-btn--danger {
  background: var(--m-surface);
  color: var(--m-danger);
  border: 1px solid var(--m-danger-line);
}

.m-btn--ghost {
  background: var(--m-surface);
  border: 1px solid var(--m-border);
  color: var(--m-text);
}

.m-empty {
  text-align: center;
  color: var(--m-text-sub);
  padding: 40px 0;
  font-size: 14px;
}
</style>
