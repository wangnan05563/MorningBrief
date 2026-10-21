/**
 * element-plus 的测试替身（仅供 tests/unit/feedback-queue.test.mjs 使用）
 *
 * 为什么必须替身而不是真包：`utils/message.js` 的全部语义都发生在「要不要把这条提示
 * 交给 ElMessage」这一步，用真组件的话，node 里没有 DOM 会直接抛错，
 * 而且断言会变成「element-plus 渲染得对」而不是「队列决策得对」。
 *
 * 记录的是**调用层**事实：第 4 节 toast 次数、聚合文案、confirm/prompt 是否被回放。
 */
export const __state = {
  toasts: [],
  boxes: [],
  closeAllCalls: 0,
  loadingCalls: 0,
}

export function __reset() {
  __state.toasts = []
  __state.boxes = []
  __state.closeAllCalls = 0
  __state.loadingCalls = 0
}

function record(options) {
  const text = typeof options === 'string' ? options : options?.message
  const type = (options && typeof options === 'object' && options.type) || 'info'
  __state.toasts.push({ type, text, duration: options?.duration })
  return { close() {} }
}

const typed = (type) => (...args) => record({ ...(typeof args[0] === 'object' ? args[0] : { message: args[0] }), type })

export const ElMessage = Object.assign(record, {
  success: typed('success'),
  error: typed('error'),
  warning: typed('warning'),
  info: typed('info'),
  loading: (...args) => {
    __state.loadingCalls += 1
    record(args[0])
    return { close() {} }
  },
  closeAll: () => {
    __state.closeAllCalls += 1
  },
})

export const ElMessageBox = {
  alert: (...args) => {
    __state.boxes.push({ kind: 'alert', text: typeof args[0] === 'string' ? args[0] : args[0]?.message })
    return Promise.resolve()
  },
  confirm: (...args) => {
    __state.boxes.push({ kind: 'confirm', text: typeof args[0] === 'string' ? args[0] : args[0]?.message })
    return Promise.resolve()
  },
  prompt: (...args) => {
    __state.boxes.push({ kind: 'prompt', text: typeof args[0] === 'string' ? args[0] : args[0]?.message })
    return Promise.resolve({ value: '' })
  },
}
