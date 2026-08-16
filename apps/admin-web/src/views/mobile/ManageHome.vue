<template>
  <div class="m-manage">
    <p class="m-manage__hint">移动端管理快捷入口（仅管理员），以下操作与 PC 后台数据实时同步。</p>

    <div class="m-manage__grid">
      <div
        v-for="m in modules"
        :key="m.to"
        class="m-manage__card"
        @click="go(m.to)"
      >
        <el-icon class="m-manage__icon"><component :is="m.icon" /></el-icon>
        <div class="m-manage__label">{{ m.label }}</div>
        <div class="m-manage__desc">{{ m.desc }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const modules = [
  { to: '/m/manage/users', label: '用户管理', desc: '检索 / 启停', icon: 'UserFilled' },
  { to: '/m/manage/feedback', label: '用户反馈', desc: '处理 / 流转', icon: 'ChatDotRound' },
  { to: '/m/manage/channels', label: '频道管理', desc: '启用 / 停用', icon: 'Menu' },
  { to: '/m/manage/ads', label: '广告投放', desc: '投放启停', icon: 'PictureFilled' },
  { to: '/m/manage/queue', label: '队列监控', desc: '取消 / 重试', icon: 'Operation' },
  { to: '/m/manage/alert', label: '应急停服', desc: '维护态控制', icon: 'WarningFilled' },
]

function go(to) {
  router.push(to)
}
</script>

<style scoped>
.m-manage {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.m-manage__hint {
  font-size: 12px;
  color: #8a8f99;
  line-height: 1.6;
  margin: 0;
  padding: 0 2px;
}

.m-manage__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.m-manage__card {
  background: #fff;
  border-radius: 12px;
  padding: 16px 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
}

.m-manage__icon {
  font-size: 24px;
  color: var(--el-color-primary, #409eff);
}

.m-manage__label {
  font-size: 15px;
  font-weight: 600;
  color: #1f2329;
}

.m-manage__desc {
  font-size: 12px;
  color: #8a8f99;
}
</style>
