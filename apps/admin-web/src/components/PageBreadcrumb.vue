<template>
  <!-- T02512（FR-UX-603）：隐藏子页（meta.hidden 的详情/二级页）此前只有一个返回图标，
       用户看不出自己在第几层、上级叫什么。这里把「上级 › 当前页」写出来，
       上级可点且带着来源筛选（见 utils/urlState.js 的 returnTarget）。 -->
  <nav class="page-breadcrumb" data-guide="page-breadcrumb" aria-label="页面位置">
    <el-breadcrumb separator="›">
      <el-breadcrumb-item v-for="(item, i) in normalized" :key="`${i}-${item.label}`">
        <a
          v-if="item.clickable"
          class="page-breadcrumb__link"
          :href="item.href || undefined"
          data-guide="breadcrumb-parent"
          @click="onItemClick($event, item)"
        >{{ item.label }}</a>
        <span v-else class="page-breadcrumb__current" data-guide="breadcrumb-current">{{ item.label }}</span>
      </el-breadcrumb-item>
    </el-breadcrumb>
  </nav>
</template>

<script setup>
/**
 * 详情页层级提示（面包屑）。
 *
 * 只做「显示 + 把点击交给调用方」，不自己算路由：
 * 返回目标涉及 `?from=` 校验与跨端判定，逻辑集中在 `utils/urlState.js`（可 node --test 直测），
 * 组件里再算一份等于把那份口径复制进模板，正是本仓反复踩过的「多处各写一份映射」。
 *
 * `href` 只用于语义（读屏/中键打开）；实际跳转一律走 click → emit('back')，
 * 这样 router.push 的 query 编码与守卫都仍由路由层负责，避免 <a> 硬跳整页刷新。
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  /** [{ label, to?, clickable? }]；最后一项默认是当前页（不可点） */
  items: { type: Array, default: () => [] },
})
const emit = defineEmits(['back'])

const router = useRouter()

const normalized = computed(() =>
  (props.items || [])
    .filter((it) => it && it.label)
    .map((it, i, arr) => {
      const clickable = it.clickable ?? i !== arr.length - 1
      return {
        label: it.label,
        clickable,
        to: it.to || null,
        // 上级才给 href（站内地址含 base 与 query 编码都交给 router.resolve）；
        // 当前页不给，免得读屏把「你正在看的这一层」也播成可点链接
        href: clickable && it.to?.path ? safeHref(it.to) : null,
      }
    }),
)

/** resolve 对不存在的命名路由会抛错，这里只关心「能不能给出一个 href」 */
function safeHref(to) {
  try {
    return router.resolve(to).href
  } catch {
    return null
  }
}

function onItemClick(event, item) {
  if (!item.clickable) return
  // 阻止 <a> 的原生跳转：由调用方 push（带 query 编码与守卫）
  event.preventDefault()
  emit('back', item)
}
</script>

<style scoped lang="scss">
@use '../styles/variables.scss' as *;

.page-breadcrumb {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;

  :deep(.el-breadcrumb__separator) {
    margin: 0 6px;
    color: var(--el-text-color-placeholder);
  }

  .page-breadcrumb__link {
    color: var(--el-color-primary);
    cursor: pointer;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }

  .page-breadcrumb__current {
    color: var(--el-text-color-secondary);
  }
}
</style>
