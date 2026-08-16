<template>
  <div class="m-mine">
    <div class="m-mine__header">
      <div class="m-mine__avatar">{{ initial }}</div>
      <div>
        <div class="m-mine__name">{{ userStore.username || '—' }}</div>
        <div class="m-mine__role">{{ roleLabel }}</div>
      </div>
    </div>

    <div class="m-row" @click="goPc">
      <span class="m-row__label">切换到 PC 完整后台</span>
      <span class="m-arrow">›</span>
    </div>

    <button class="m-btn m-btn--danger" @click="onLogout">退出登录</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const userStore = useUserStore()

const initial = computed(() => (userStore.username || '?').charAt(0).toUpperCase())
const roleLabel = computed(() => (userStore.isAdmin ? '管理员' : '运营人员'))

function goPc() {
  router.push('/review')
}

async function onLogout() {
  await userStore.logout()
  router.replace('/m/login')
}
</script>

<style scoped>
.m-mine {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.m-mine__header {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border-radius: 12px;
  padding: 18px 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-mine__avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--el-color-primary, #409eff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
}

.m-mine__name {
  font-size: 16px;
  font-weight: 600;
  color: #1f2329;
}

.m-mine__role {
  font-size: 12px;
  color: #8a8f99;
  margin-top: 2px;
}

.m-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-radius: 12px;
  padding: 16px 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  font-size: 15px;
  color: #1f2329;
}

.m-arrow {
  color: #c0c4cc;
}

.m-btn {
  height: 46px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}

.m-btn--danger {
  background: #fff;
  color: #f56c6c;
  border: 1px solid #fbc4c4;
}
</style>
