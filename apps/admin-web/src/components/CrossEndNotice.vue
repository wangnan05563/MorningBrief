<template>
  <el-alert
    v-if="notice"
    class="cross-end-notice"
    type="info"
    :closable="true"
    data-guide="cross-end-notice"
    data-testid="cross-end-notice"
    @close="dismiss"
  >
    <template #title>
      <span class="cross-end-notice__text">
        已按当前{{ currentEndLabel }}视图自动切换页面。
        <router-link
          :to="link"
          class="cross-end-notice__link"
          data-testid="cross-end-notice-link"
        >
          仍要查看原页面
        </router-link>
      </span>
    </template>
  </el-alert>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  clearCrossEndNotice,
  crossEndNoticeLink,
  readCrossEndNotice,
} from '../utils/crossEndNotice'

// I59：跨端重定向后给出「换了哪一端 + 一键回原页面」的说明。
// 提示只在落点页有效——导航到别处时守卫会清掉，这里也按路由重读，保持与存储一致。
const route = useRoute()
const notice = ref(null)

function sync() {
  // sessionStorage 在浏览器里恒可用；守卫已用 try/catch 包住失败路径
  notice.value = typeof sessionStorage === 'undefined' ? null : readCrossEndNotice(sessionStorage)
}

onMounted(sync)
watch(() => route.path, sync)

const link = computed(() => crossEndNoticeLink(notice.value))
const currentEndLabel = computed(() => {
  const landed = notice.value?.landedPath || ''
  return landed === '/m' || landed.startsWith('/m/') ? '移动端' : '桌面端'
})

function dismiss() {
  if (typeof sessionStorage !== 'undefined') clearCrossEndNotice(sessionStorage)
  notice.value = null
}
</script>

<style scoped>
.cross-end-notice {
  flex: 0 0 auto;
  border-radius: 0;
}

.cross-end-notice__link {
  margin-left: 4px;
  color: var(--color-primary-dark, #1d4ed8);
  font-weight: 600;
  text-decoration: underline;
}
</style>
