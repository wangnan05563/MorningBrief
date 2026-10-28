/**
 * 表单断点续录（T00828：配置页中途切换页面/保存状态后再次进入，保留未提交输入）
 *
 * 为什么自建而非手写 localStorage：配置页表单结构各异（ref/reactive、多 tab 嵌套），
 * 统一封装「恢复 / 自动持久化 / 提交清除」三件套，页面只关心接入点，避免重复代码。
 *
 * 用法：
 *   const { hasDraft, apply, track, commit, discard } = useDraft('ai-config')
 *   const { changed } = apply(llmForm)      // 页面初始化时恢复草稿（深合并已有字段），changed = 与服务器值不同的项数
 *   track(llmForm, { excludePaths: ['api_key'] })  // 监听变化防抖持久化（排除敏感字段）
 *   commit()                                // 保存成功 / 重置后清除草稿
 *   await discard(llmForm)                  // 用户选择「丢弃草稿」：表单回填服务器值并删除本机草稿
 *
 * 约束：仅本地状态保持（localStorage），不自动提交；不改动既有保存/重置逻辑。
 */
import { ref, watch, onBeforeUnmount, nextTick } from 'vue'

const PREFIX = 'mb_draft_'
const SAVE_DELAY = 400

function isRefValue(v) {
  return v && typeof v === 'object' && '__v_isRef' in v
}

/** 递归深合并 draft 到 target：只覆盖 target 已有的字段（嵌套对象逐层合并，数组整体替换） */
function deepMerge(target, draft) {
  if (!draft || typeof draft !== 'object' || typeof target !== 'object') return
  for (const k of Object.keys(draft)) {
    if (!(k in target)) continue
    const tv = target[k]
    const dv = draft[k]
    if (tv && dv && typeof tv === 'object' && typeof dv === 'object' && !Array.isArray(tv) && !Array.isArray(dv)) {
      deepMerge(tv, dv)
    } else {
      target[k] = dv
    }
  }
}

/** 按排除路径（'a.b.c'）递归删除草稿中的敏感字段，避免密钥明文落盘 localStorage */
function sanitize(obj, excludePaths) {
  if (!excludePaths?.length) return obj
  const out = Array.isArray(obj) ? [...obj] : { ...obj }
  for (const path of excludePaths) {
    const segs = path.split('.')
    let cur = out
    let ok = true
    for (let i = 0; i < segs.length - 1; i++) {
      if (!cur || typeof cur !== 'object') { ok = false; break }
      cur = cur[segs[i]]
    }
    if (ok && cur && typeof cur === 'object') delete cur[segs[segs.length - 1]]
  }
  return out
}

function cloneValue(v) {
  if (Array.isArray(v)) return v.map(cloneValue)
  if (v && typeof v === 'object') {
    const out = {}
    for (const k of Object.keys(v)) out[k] = cloneValue(v[k])
    return out
  }
  return v
}

/** 统计两棵表单树之间不同的叶子路径数（数组整体比较），用于横幅上的「N 项与服务器值不同」 */
export function countChangedPaths(baseline, merged) {
  let count = 0
  const walk = (a, b) => {
    if (Array.isArray(a) || Array.isArray(b)) {
      if (JSON.stringify(a) !== JSON.stringify(b)) count++
      return
    }
    if (a && b && typeof a === 'object' && typeof b === 'object') {
      for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) walk(a[k], b[k])
      return
    }
    if (a !== b) count++
  }
  walk(baseline, merged)
  return count
}

export function useDraft(key) {
  const storageKey = PREFIX + key
  const hasDraft = ref(false)
  // 恢复时的基线（服务端值）与差异项数：丢弃草稿靠基线回填，横幅靠差异数决定是否出现
  const changedCount = ref(0)
  let baseline = null
  let saveTimer = null

  /** 恢复草稿到表单（仅合并 target 已有字段；无草稿返回 null） */
  function apply(target) {
    const obj = isRefValue(target) ? target.value : target
    if (!obj || typeof obj !== 'object') return null
    let raw = null
    try {
      raw = localStorage.getItem(storageKey)
    } catch {
      return null
    }
    if (!raw) return null
    try {
      const draft = JSON.parse(raw)
      if (!draft || typeof draft !== 'object') return null
      baseline = cloneValue(obj)
      deepMerge(obj, draft)
      hasDraft.value = true
      changedCount.value = countChangedPaths(baseline, obj)
      return { draft, changed: changedCount.value }
    } catch {
      return null
    }
  }

  /** 监听表单变化，防抖持久化（卸载时兜底 flush）。
   *  返回 enable()：初始化（服务端加载 + 草稿恢复）完成后调用才真正持久化，
   *  避免初始化赋值被误当成用户草稿写入 localStorage。 */
  function track(target, { excludePaths = [] } = {}) {
    const obj = isRefValue(target) ? target.value : target
    if (!obj || typeof obj !== 'object') return () => {}
    let enabled = false
    const flush = () => {
      try {
        localStorage.setItem(storageKey, JSON.stringify(sanitize(obj, excludePaths)))
      } catch {
        // localStorage 不可用（禁用/满）时静默降级：断点续录失效但不阻断页面
      }
    }
    watch(
      target,
      () => {
        if (!enabled) return
        clearTimeout(saveTimer)
        saveTimer = setTimeout(flush, SAVE_DELAY)
      },
      { deep: true },
    )
    onBeforeUnmount(() => {
      clearTimeout(saveTimer)
      if (enabled) flush()
    })
    return () => {
      enabled = true
    }
  }

  /** 是否存在本地草稿但不合并进表单（T02487：配置加载失败时须「默认不恢复」，只能提示） */
  function peek() {
    try {
      return Boolean(localStorage.getItem(storageKey))
    } catch {
      return false
    }
  }

  /** 保存成功 / 重置后清除草稿，避免旧输入干扰下次进入 */
  function commit() {
    try {
      localStorage.removeItem(storageKey)
    } catch {
      // 忽略移除失败（无害）
    }
    hasDraft.value = false
    changedCount.value = 0
    baseline = null
  }

  /** 用户选择「丢弃草稿」：表单回填恢复前的服务器值，同时删除本机草稿。
   *  返回被丢弃的差异项数。回填会触发 deep watch，必须作废它安排的防抖写入，
   *  否则服务器值会被当成新草稿再存一次，下次进入又冒出来。 */
  async function discard(target) {
    const obj = isRefValue(target) ? target.value : target
    if (!obj || typeof obj !== 'object' || !baseline) {
      commit()
      return 0
    }
    const restored = countChangedPaths(baseline, obj)
    clearTimeout(saveTimer)
    deepMerge(obj, baseline)
    // 等这一轮 deep watch 回调跑完再清存储；回调里安排的防抖定时器一并作废
    await nextTick()
    clearTimeout(saveTimer)
    try {
      localStorage.removeItem(storageKey)
    } catch {
      // 忽略移除失败（无害）
    }
    hasDraft.value = false
    changedCount.value = 0
    baseline = null
    return restored
  }

  return { hasDraft, changedCount, apply, peek, track, commit, discard }
}
