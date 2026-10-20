/**
 * URL ↔ 组件状态双向绑定（T02511 / FR-UX-602）
 *
 * 纯逻辑在 `utils/urlState.js`（可 node --test 直测），这里只负责与 vue/vue-router 接线。
 *
 * 用法（见 views/review/ReviewList.vue）：
 *   const { readFromUrl, pushToUrl, invalid } = useUrlState(SPECS, () => ({
 *     tab: activeTab.value, page: page.value, size: size.value,
 *   }), { onExternalChange: applyFromUrl })
 *   // 状态变更后显式调 pushToUrl()（切 tab / 翻页 / 改 size 的地方各调一次）
 *
 * **不做「深度 watch 自动回写」**：列表页还有 loading / selectedRows / total 等一堆响应式状态，
 * 自动 watch 快照容易在无关变更时也写 URL（`router.replace` 抖动 + 地址栏闪烁）。
 * 显式调用换来的是「哪一处会改 URL」可以一眼看清，改代码时不会忘记同步。
 *
 * 为什么用 `router.replace` 而不是 `push`：
 * 翻页/切 tab 是「同一份列表的不同视图」，push 会让后退键变成「回看自己刚才看过的每一页」，
 * 用户想离开这一页要按十几次后退。replace 保住「刷新/分享/收藏都回到同一状态」这条真需求，
 * 放弃的是本来就没价值的历史项。需要前进后退的历史由页面自身的「返回列表」承担（FR-UX-603）。
 */
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { readUrlState, writeUrlQuery, isQueryDirty } from '../utils/urlState'

/**
 * @param {object} specs   参数规格（见 utils/urlState.js）
 * @param {() => object} source  当前状态快照（必须返回普通对象，便于比较）
 * @param {object} options
 * @param {(values:object)=>void} [options.onExternalChange] 地址栏被外部改动（手改 URL / 前进后退）时回调
 */
export function useUrlState(specs, source, options = {}) {
  const route = useRoute()
  const router = useRouter()

  /** 最近一次读取时被判定非法并已回落默认值的参数（页面可据此提示「地址里的 xx 参数无效」） */
  const invalid = ref([])

  // 自己刚写进 URL 的值：用于区分「我写的 query 变化」和「别人（用户/其他组件）改的」
  let lastWritten = null

  /** 从当前 URL 读一次状态（首屏初始化用） */
  function readFromUrl() {
    const { values, invalid: bad } = readUrlState(route.query, specs)
    invalid.value = bad
    return values
  }

  /** 把当前状态写回 URL（等于默认值的参数会被省略） */
  function pushToUrl() {
    const values = source()
    if (!isQueryDirty(route.query, specs, values)) return
    const query = writeUrlQuery(route.query, specs, values)
    lastWritten = { query, values }
    router
      .replace({ query })
      // replace 会被同路由导航守卫取消（NavigationFailure），不是错误；
      // 但懒加载分块拉取失败会 reject，这里静默并留 console 痕迹，避免 Uncaught in promise
      .catch((err) => console.warn('[urlState] URL 回写被拒绝（已静默处理）:', err?.message || err))
  }

  watch(
    () => route.query,
    (q) => {
      // 自己写回的 query 变化不需要再驱动一次加载，否则会形成 replace → watch → 加载 的回环
      if (lastWritten && sameFlat(lastWritten.query, q)) return
      const { values, invalid: bad } = readUrlState(q, specs)
      invalid.value = bad
      if (typeof options.onExternalChange === 'function') options.onExternalChange(values)
    },
  )

  return { readFromUrl, pushToUrl, invalid }
}

/** 浅比较两个 query（值统一按字符串比，vue-router 会把数组原样带着） */
function sameFlat(a, b) {
  const ka = Object.keys(a || {})
  const kb = Object.keys(b || {})
  if (ka.length !== kb.length) return false
  return ka.every((k) => String(a[k]) === String((b || {})[k]))
}
