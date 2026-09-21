/**
 * 引导状态管理（T00863）
 *
 * 模块级单例：任何组件调用 useGuide() 拿到同一份状态。
 * 存储：localStorage 记录「已引导」的菜单路径，初次访问仅弹一次。
 *
 * 为什么自动跳过自动化环境：E2E/Playwright 每次全新会话 localStorage 为空，
 * 若首访必弹引导遮罩会挡住被测按钮；用 navigator.webdriver 标记跳过，
 * 真实浏览器不受影响。演示模式（?guide=demo）可强制打开用于人工/自动化验收。
 */
import { ref } from 'vue'

const active = ref(false)
const steps = ref([])
const stepIndex = ref(0)
const autoPlay = ref(true)
const currentPath = ref('')

const STORAGE_KEY = 'mb_guide_done'

const isAutomated = typeof navigator !== 'undefined' && navigator.webdriver === true
const forcedDemo =
  typeof location !== 'undefined' && new URLSearchParams(location.search).get('guide') === 'demo'

function loadMap() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

function saveMap(map) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map))
  } catch {
    // 存储不可用时静默失败：仅失去「只引导一次」记忆，不影响使用
  }
}

function isDone(path) {
  return loadMap()[path] === 1
}

function markDone(path) {
  const map = loadMap()
  map[path] = 1
  saveMap(map)
}

function open(path, cfgSteps) {
  if (isAutomated && !forcedDemo) return
  if (!cfgSteps || cfgSteps.length === 0) return
  currentPath.value = path
  steps.value = cfgSteps
  stepIndex.value = 0
  // 默认手动步进：自动播放节奏快，默认开启会让用户来不及阅读；需要时在浮层点开关启用
  autoPlay.value = false
  active.value = true
}

function close() {
  active.value = false
  steps.value = []
  autoPlay.value = true
}

function next() {
  if (stepIndex.value < steps.value.length - 1) stepIndex.value += 1
  else finish()
}

function prev() {
  if (stepIndex.value > 0) stepIndex.value -= 1
}

function skip() {
  close()
}

function finish() {
  markDone(currentPath.value)
  close()
}

function toggleAuto() {
  autoPlay.value = !autoPlay.value
}

export function useGuide() {
  return {
    active,
    steps,
    stepIndex,
    autoPlay,
    currentPath,
    isDone,
    markDone,
    open,
    close,
    next,
    prev,
    skip,
    finish,
    toggleAuto,
  }
}
