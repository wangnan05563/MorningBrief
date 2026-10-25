/**
 * J69 分页重置口径（T02762）：切频道/换排序/下拉刷新必须回到第 1 页，
 * 而「从详情页返回」不得把已翻的页清掉。
 *
 * 运行：node --test apps/miniprogram/tests/history-pagination-reset.test.js
 *
 * 为什么锁这两页：J69 的失效形态是**分页游标和过滤条件不同步**——
 * 切频道时 page 还停在 4，请求就变成「新频道的第 4 页」，用户看到的是空列表；
 * 反过来，早期 recent 页每次 onShow 都重置第 1 页，「听完一集回去找刚才那集」
 * 翻的页全白翻。两个方向都只有一行代码的差别，却都是回归高发点。
 *
 * 这里不复制页面逻辑：把真实页面模块 require 进来（api / local-data 的出口在页面
 * 加载前换成假实现），再按 Page 配置造实例，直接调它的生命周期与事件方法，
 * 断言它下发了什么请求、data 变成什么。页面逻辑改坏，这里就红。
 *
 * 注意 history.js 的 loadHistory 开头有 `if (this.data.loading) return`，而 T00599 的
 * 骨架控制器有 600ms 最短展示：不等它收起就发下一个动作，会被这道 guard 静默吃掉，
 * 用例就变成「什么都没测」。所以每个动作前后都 idle(p)（它同时会断言前提成立）。
 */
const { test, describe } = require('node:test')
const assert = require('node:assert')
const path = require('path')

const MP_ROOT = path.resolve(__dirname, '..')

const SIZE = 20
const TOTAL = 60

// ---- wx 运行时桩：页面与其依赖（services/audio、utils/tab-badge）在 Node 里可加载 ----
const store = {}
global.wx = {
  getStorageSync: (k) => (k in store ? store[k] : ''),
  setStorageSync: (k, v) => { store[k] = v },
  removeStorageSync: (k) => { delete store[k] },
  getStorageInfoSync: () => ({ keys: Object.keys(store) }),
  setStorage: (o) => { store[o.key] = o.data; o.success && o.success() },
  request: (o) => { o.success && o.success({ statusCode: 200, data: { code: 0, data: null } }) },
  getBackgroundAudioManager: () => ({
    onPlay() {}, onPause() {}, onEnded() {}, onError() {}, onTimeUpdate() {},
    onWaiting() {}, onCanplay() {}, onPrev() {}, onNext() {}, play() {}, pause() {},
    seek() {}, stop() {},
  }),
  getFileSystemManager: () => ({ removeSavedFile: () => {}, readFile: () => {}, access: () => {} }),
  env: { USER_DATA_PATH: '/tmp' },
  showToast: () => {},
  hideToast: () => {},
  showModal: () => {},
  showLoading: () => {},
  hideLoading: () => {},
  setTabBarBadge: () => {},
  removeTabBarBadge: () => {},
  navigateTo: () => {},
  createInnerAudioContext: () => ({ onCanplay() {}, onError() {}, destroy() {} }),
  getSystemInfoSync: () => ({ SDKVersion: '2.41.0', platform: 'devtools' }),
  canIUse: () => true,
  getNetworkType: (o) => { o.success && o.success({ networkType: 'wifi' }) },
  onNetworkStatusChange: () => {},
  stopPullDownRefresh: () => {},
}
global.getApp = () => ({ globalData: { baseUrl: 'http://test.local', token: '', preferredChannelsChanged: 0 } })
global.getCurrentPages = () => [{ route: 'pages/history/history' }]
global.Component = () => {}
global.App = () => {}

// ---- 依赖出口在页面 require 之前替换：页面用 `const { fetchHistory } = require(...)` 解构 ----
const api = require('../services/api')
const localData = require('../services/local-data')
const audio = require('../services/audio')

let historyCalls = []
let preferredIds = []

/** 造一页数据：id 与页码/频道绑定，便于断言「第几页的哪个频道」 */
function makeItems(page, channelId) {
  const cid = channelId === null || channelId === undefined ? 7 : channelId
  return Array.from({ length: SIZE }, (_, i) => ({
    id: page * 1000 + i,
    title: `频道${cid} 第${page}页 ${i + 1}`,
    channel_id: cid,
    date: '2026-10-01',
    duration: 60,
  }))
}

/** 把 Page 配置装成可调用实例（setData 浅合并，与真机一致） */
function instantiate(cfg) {
  const inst = Object.create(cfg)
  inst.data = JSON.parse(JSON.stringify(cfg.data))
  inst.setData = (obj) => { Object.assign(inst.data, obj) }
  return inst
}

const tick = () => new Promise((r) => setTimeout(r, 0))

/** 等骨架计时收起（loading 归 false），否则下一个动作会被 `if (loading) return` 吃掉 */
async function idle(p) {
  await tick()
  for (let i = 0; i < 120 && p.data.loading; i += 1) await new Promise((r) => setTimeout(r, 20))
  assert.strictEqual(p.data.loading, false, '用例前提不成立：loading 一直没收起，后续动作会被 guard 静默丢弃')
}

function capturePage(rel) {
  const captured = []
  global.Page = (cfg) => captured.push(cfg)
  const abs = path.join(MP_ROOT, rel)
  delete require.cache[abs]
  require(abs)
  assert.strictEqual(captured.length, 1, `${rel} 应只注册一个 Page`)
  return instantiate(captured[0])
}

function loadHistoryPage() {
  historyCalls = []
  api.fetchHistory = async (page, size, channelId, sortOrder) => {
    historyCalls.push({ page, size, channelId, sortOrder })
    return { list: makeItems(page, channelId), total: TOTAL }
  }
  api.fetchChannels = async () => ({ list: [{ id: 7, name: '科技' }, { id: 8, name: '财经' }] })
  localData.getPreferredChannels = () => preferredIds
  localData.getHistory = async () => ({ list: [], total: 0 })
  localData.getPlayedHistorySet = async () => new Set()
  localData.getProgress = async () => ({ position: 0 })
  audio.clearQueue()
  return capturePage('pages/history/history.js')
}

function loadRecentPage() {
  historyCalls = []
  localData.getHistory = async (page) => {
    historyCalls.push({ page })
    return { list: makeItems(page, 7), total: TOTAL }
  }
  audio.setQueue = () => {}
  return capturePage('pages/recent/recent.js')
}

describe('history：过滤条件变了就必须回到第 1 页', () => {
  test('onLoad 首屏请求第 1 页（全部频道）', async () => {
    preferredIds = []
    const p = loadHistoryPage()
    p.onLoad()
    await idle(p)
    assert.deepStrictEqual(historyCalls[0], { page: 1, size: SIZE, channelId: null, sortOrder: 'desc' })
    assert.strictEqual(p.data.list.length, SIZE)
    p.onUnload()
  })

  test('翻两页后切频道：下一次请求是「新频道第 1 页」，不是「新频道第 3 页」', async () => {
    preferredIds = []
    const p = loadHistoryPage()
    p.onLoad()
    await idle(p)
    await p.loadHistory(false)
    await idle(p)
    await p.loadHistory(false)
    await idle(p)
    assert.strictEqual(p.data.page, 4, '前置条件：游标已翻到第 4 页')
    assert.strictEqual(p.data.list.length, SIZE * 3, '上拉应当拼接下一页，而不是把列表换成最新一页')
    assert.ok(String(p.data.list[0].id).startsWith('1'), '第 1 页的数据被顶掉了')
    assert.ok(String(p.data.list[SIZE].id).startsWith('2'), '第 2 页没接在第 1 页后面')

    historyCalls = []
    await p.onSwitchChannel({ currentTarget: { dataset: { id: 8 } } })
    assert.deepStrictEqual(
      historyCalls,
      [{ page: 1, size: SIZE, channelId: 8, sortOrder: 'desc' }],
      '切频道时 page 未重置：用户看到的是空列表（J69 原缺陷）',
    )
    assert.ok(p.data.list.every((e) => e.channel_id === 8), '列表里残留了旧频道的条目')
    assert.strictEqual(p.data.renderCount, SIZE)
    p.onUnload()
  })

  test('切到同频道不重复请求', async () => {
    preferredIds = []
    const p = loadHistoryPage()
    p.onLoad()
    await idle(p)
    await p.loadHistory(false)
    await idle(p)
    historyCalls = []
    await p.onSwitchChannel({ currentTarget: { dataset: { id: null } } })
    await idle(p)
    assert.deepStrictEqual(historyCalls, [], '重复点当前频道不该再发一轮请求')
    assert.strictEqual(p.data.page, 3, '同频道重复点击把游标打回去了')
    p.onUnload()
  })

  test('切排序回第 1 页：升序不能沿用降序翻到的游标', async () => {
    preferredIds = []
    const p = loadHistoryPage()
    p.onLoad()
    await idle(p)
    historyCalls = []
    p.setData({ page: 5 })
    await p.onToggleSort()
    await idle(p)
    assert.deepStrictEqual(historyCalls[0], { page: 1, size: SIZE, channelId: null, sortOrder: 'asc' })
    p.onUnload()
  })

  test('下拉刷新回第 1 页并清空旧列表', async () => {
    preferredIds = []
    const p = loadHistoryPage()
    p.onLoad()
    await idle(p)
    await p.loadHistory(false)
    await idle(p)
    historyCalls = []
    p.setData({ page: 6 })
    await p.onPullDownRefresh()
    await idle(p)
    assert.deepStrictEqual(historyCalls[0], { page: 1, size: SIZE, channelId: null, sortOrder: 'desc' })
    assert.ok(p.data.list.every((e) => String(e.id).startsWith('1')), '刷新后仍留着旧页的数据')
    p.onUnload()
  })

  test('「我的偏爱」未设置时不发请求，停在引导空态且游标归位', async () => {
    preferredIds = [8]
    const p = loadHistoryPage()
    p.onLoad()
    await idle(p)
    await p.loadHistory(false)
    await idle(p)
    preferredIds = [] // 用户在设置页清空了偏爱
    historyCalls = []
    await p.onSwitchChannel({ currentTarget: { dataset: { id: 'preferred' } } })
    await idle(p)
    assert.deepStrictEqual(historyCalls, [], '未设置偏爱时仍去拉全频道：空态先闪一下真列表')
    assert.strictEqual(p.data.preferredEmpty, true)
    assert.strictEqual(p.data.hasMore, false)
    assert.strictEqual(p.data.page, 1, '空态下游标没归位，设好偏爱后会直接请求第 3 页')
    p.onUnload()
  })

  test('「我的偏爱」已设置时拉全频道再本地过滤，游标仍是第 1 页', async () => {
    preferredIds = [8]
    const p = loadHistoryPage()
    p.onLoad()
    await idle(p)
    await p.loadHistory(false)
    await idle(p)
    historyCalls = []
    await p.onSwitchChannel({ currentTarget: { dataset: { id: 'preferred' } } })
    await idle(p)
    assert.deepStrictEqual(
      historyCalls[0],
      { page: 1, size: SIZE, channelId: null, sortOrder: 'desc' },
      '偏爱模式要拉全频道再本地过滤，且必须从第 1 页开始',
    )
    assert.ok(p.data.isPreferredMode)
    assert.ok(p.data.list.every((e) => e.channel_id === 8), '偏爱模式漏掉了本地过滤')
    p.onUnload()
  })

  test('上拉先把未渲染的尾部放出来，只有耗尽后才有下一页请求', async () => {
    preferredIds = []
    const p = loadHistoryPage()
    p.onLoad()
    await idle(p)
    p.setData({ renderCount: 5 }) // 已加载 20 条但只渲染了 5 条
    historyCalls = []
    p.onReachBottom()
    assert.strictEqual(p.data.renderCount, SIZE, '底部手势先把已加载的尾部放出来，而不是白跑一次网络')
    // 尾部一次耗尽（5→20 == list.length）且后端还有更多：按实现的预取分支发一次第 2 页
    assert.deepStrictEqual(historyCalls, [{ page: 2, size: SIZE, channelId: null, sortOrder: 'desc' }])
    p.onUnload()
  })

  test('后端没有更多时，上拉只渲染尾部不再发请求', async () => {
    preferredIds = []
    const p = loadHistoryPage()
    p.onLoad()
    await idle(p)
    p.setData({ renderCount: 5, hasMore: false })
    historyCalls = []
    p.onReachBottom()
    assert.strictEqual(p.data.renderCount, SIZE)
    assert.deepStrictEqual(historyCalls, [], 'hasMore=false 还继续请求同一页')
    p.onUnload()
  })

  test('从详情页返回（onShow）不清列表：翻页与滚动位置保留', async () => {
    preferredIds = []
    const p = loadHistoryPage()
    p.onLoad()
    await idle(p)
    await p.loadHistory(false)
    await idle(p)
    const before = p.data.list.length
    historyCalls = []
    p.onShow()
    await idle(p)
    assert.strictEqual(p.data.list.length, before, 'onShow 把已加载的列表重置了')
    assert.strictEqual(p.data.page, 3, 'onShow 把游标打回第 1 页')
    p.onUnload()
  })
})

describe('recent：翻页要留住，重置只留给下拉刷新', () => {
  test('首次 onShow 请求第 1 页', async () => {
    const p = loadRecentPage()
    p.onLoad()
    await p.onShow()
    assert.deepStrictEqual(historyCalls, [{ page: 1 }])
    assert.strictEqual(p.data.list.length, SIZE)
  })

  test('从详情页返回（第二次 onShow）不再重置：翻页与滚动位置保留', async () => {
    const p = loadRecentPage()
    p.onLoad()
    await p.onShow()
    await p.loadRecent(false)
    historyCalls = []
    await p.onShow()
    assert.deepStrictEqual(historyCalls, [], 'onShow 又拉第 1 页：用户翻的页白翻（J69 另一半）')
    assert.strictEqual(p.data.page, 3, '游标被 onShow 打回去了')
    assert.strictEqual(p.data.list.length, SIZE * 2, '已加载的两页被清空')
  })

  test('下拉刷新才回第 1 页', async () => {
    const p = loadRecentPage()
    p.onLoad()
    await p.onShow()
    await p.loadRecent(false)
    historyCalls = []
    await p.onPullDownRefresh()
    assert.deepStrictEqual(historyCalls, [{ page: 1 }])
    assert.ok(p.data.list.every((e) => String(e.id).startsWith('1')), '刷新后仍留着第 2 页数据')
  })

  test('上拉加载下一页：游标递增，列表拼接而不是替换', async () => {
    const p = loadRecentPage()
    p.onLoad()
    await p.onShow()
    historyCalls = []
    await p.onReachBottom()
    assert.deepStrictEqual(historyCalls, [{ page: 2 }])
    assert.strictEqual(p.data.list.length, SIZE * 2)
    assert.strictEqual(p.data.page, 3)
  })

  test('每条的 episode_id 归一化：本地历史只存 id 时点击仍能跳转', async () => {
    const p = loadRecentPage()
    localData.getHistory = async () => ({ list: [{ id: 42, title: '旧记录' }], total: 1 })
    await p.loadRecent(true)
    assert.strictEqual(p.data.list[0].episode_id, 42, '缺 episode_id 会让 wxml 的 data-id 为空')
  })

  test('到底后不再发请求（hasMore 关掉后 onReachBottom 静默）', async () => {
    const p = loadRecentPage()
    p.onLoad()
    await p.onShow()
    p.setData({ hasMore: false, loading: false })
    historyCalls = []
    await p.onReachBottom()
    assert.deepStrictEqual(historyCalls, [], '没有更多了还反复请求同一页')
  })
})
