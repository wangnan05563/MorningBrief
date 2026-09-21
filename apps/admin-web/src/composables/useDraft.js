/**
 * 表单断点续录（T00828：配置页中途切换页面/保存状态后再次进入，保留未提交输入）
 *
 * 为什么自建而非手写 localStorage：配置页表单结构各异（ref/reactive、多 tab 嵌套），
 * 统一封装「恢复 / 自动持久化 / 提交清除」三件套，页面只关心接入点，避免重复代码。
 *
 * 用法：
 *   const { hasDraft, apply, track, commit } = useDraft('ai-config')
 *   apply(llmForm)                          // 页面初始化时恢复草稿（深合并已有字段）
 *   track(llmForm, { excludePaths: ['api_key'] })  // 监听变化防抖持久化（排除敏感字段）
 *   commit()                                // 保存成功 / 重置后清除草稿
 *
 * 约束：仅本地状态保持（localStorage），不自动提交；不改动既有保存/重置逻辑。
 */
import { ref, watch, onBeforeUnmount } from 'vue'

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

export function useDraft(key) {
  const storageKey = PREFIX + key
  const hasDraft = ref(false)
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
      deepMerge(obj, draft)
      hasDraft.value = true
      return draft
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

  /** 保存成功 / 重置后清除草稿，避免旧输入干扰下次进入 */
  function commit() {
    try {
      localStorage.removeItem(storageKey)
    } catch {
      // 忽略移除失败（无害）
    }
    hasDraft.value = false
  }

  return { hasDraft, apply, track, commit }
}
