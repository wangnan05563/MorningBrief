/**
 * 引导状态管理（T00863 → T02502 可用性改造）
 *
 * 模块级单例：任何组件调用 useGuide() 拿到同一份状态。
 * 存储：localStorage 记录「已引导」的菜单路径，初次访问仅弹一次。
 *
 * 为什么自动跳过自动化环境：E2E/Playwright 每次全新会话 localStorage 为空，
 * 若首访必弹引导遮罩会挡住被测按钮；用 navigator.webdriver 标记跳过，
 * 真实浏览器不受影响。演示模式（?guide=demo）可强制打开用于人工/自动化验收。
 * T02502 补充：用户主动发起的播放（帮助页重放、右下角常驻按钮）传 force 绕开该守卫——
 * 「用户点了」是明确意图，守卫的目的是防止自动弹层干扰测试，不是禁止人工唤起。
 */
import { ref } from 'vue'

const active = ref(false)
const steps = ref([])
const stepIndex = ref(0)
const autoPlay = ref(true)
const currentPath = ref('')
// 帮助页「播放引导」登记的跨菜单重放目标（T02502 / FR-UX-403）
const pendingReplay = ref('')

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

function markUndone(path) {
  const map = loadMap()
  delete map[path]
  saveMap(map)
}

/**
 * 帮助页点「播放引导」：跨菜单重放必须等目标页渲染完再开（否则锚点还没挂载），
 * 所以这里只登记目标路径，由 Layout 的路由 watch 落地后消费。
 */
function requestReplay(path) {
  pendingReplay.value = path
}

// 消费登记：命中即清空并返回 true，调用方据此决定是「强制重放」还是「首访引导」
function takeReplay(path) {
  if (pendingReplay.value !== path) return false
  pendingReplay.value = ''
  return true
}

function open(path, cfgSteps, opts = {}) {
  // force：用户在帮助页主动点「播放引导」——这是明确意图，自动化守卫不该拦
  // （否则 e2e 无法验证「引导可从帮助页重新唤起」这条需求）
  if (isAutomated && !forcedDemo && !opts.force) return
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

// 「跳过」与「完成」同样记账（T02502 / FR-UX-403）：
// 跳过表达的是「我不要这个菜单的引导」，若不 markDone，用户每次进入该页都会再弹一次，
// 引导从帮助变成骚扰，且「跳过」比「完成」更常被点——等于绝大多数用户永远关不掉。
function skip() {
  markDone(currentPath.value)
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
    pendingReplay,
    isDone,
    markDone,
    markUndone,
    requestReplay,
    takeReplay,
    open,
    close,
    next,
    prev,
    skip,
    finish,
    toggleAuto,
  }
}
