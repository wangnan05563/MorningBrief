/**
 * 队列单项管理与角标口径（T02786 / J77 验收第 4 项）
 *
 * 运行：node --test apps/miniprogram/tests/queue-management.test.js
 *
 * J77 的原缺陷是「两处队列都只能整表清空」，实现已把 removeQueueAt / moveQueueItem
 * 收敛到 services/audio.js 单源并被两个出口共用；本文件锁的是**收敛之后最容易散掉的一半**：
 * 「历史」tab 的角标以 `pendingCountOf(队列, 当前索引)` 为准，而删中间项、删当前项、
 * 把当前项上移都会同时改队列长度和索引。只测列表不测角标，就会出现
 * 「列表对了、角标还是旧数字、下一次自动连播跳到别的节目」这种三方不一致。
 *
 * 这里不重写队列逻辑：直接 require 真实的 services/audio.js，用它的 setQueue/removeQueueAt/
 * moveQueueItem 驱动真实的 utils/tab-badge.js 刷新器，最后核对下发到 wx.setTabBarBadge 的文案。
 */
const { test, describe } = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

const MP_ROOT = path.resolve(__dirname, '..')
const read = (rel) => fs.readFileSync(path.join(MP_ROOT, rel), 'utf8')

// ---- 让 services/audio.js 在 Node 里可加载：它顶部只 require，不碰播放对象 ----
const store = {}
const badgeCalls = []
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
  setTabBarBadge: (o) => { badgeCalls.push({ kind: 'set', index: o.index, text: o.text }) },
  removeTabBarBadge: (o) => { badgeCalls.push({ kind: 'remove', index: o.index }) },
  createInnerAudioContext: () => ({ onCanplay() {}, onError() {}, destroy() {} }),
  getSystemInfoSync: () => ({ SDKVersion: '2.41.0', platform: 'devtools' }),
  canIUse: () => true,
  getNetworkType: (o) => { o.success && o.success({ networkType: 'wifi' }) },
  onNetworkStatusChange: () => {},
}
global.getApp = () => ({ globalData: { baseUrl: 'http://test.local', token: '' } })
// 角标只在 tab 页可挂：默认栈顶是「历史」tab，用例里再改
let stackRoute = 'pages/history/history'
global.getCurrentPages = () => [{ route: stackRoute }]

const audio = require('../services/audio')
const { pendingCountOf, badgeText, createTabBadge } = require('../utils/tab-badge')

const FIVE = [1, 2, 3, 4, 5].map((id) => ({ id, title: `第${id}首`, audio_url: `u${id}` }))
const titles = (q) => q.map((i) => i.id).join('>')

/** 每个用例从同一条 5 项队列（id 1..5）出发，避免上一例的残留状态影响断言 */
function resetQueue(startIndex) {
  badgeCalls.length = 0
  audio.clearQueue()
  audio.setQueue(FIVE.map((e) => ({ ...e })), startIndex)
}
const pending = () => pendingCountOf(audio.getQueue(), audio.getQueueIndex())

describe('删除单项后的口径：列表、待播数、连播目标三者一致', () => {
  test('删当前条之后的一项：待播数 -1，连播目标不变', () => {
    resetQueue(1)
    assert.strictEqual(pending(), 3)
    const nextBefore = audio.getQueue()[2].id
    const r = audio.removeQueueAt(3)
    assert.strictEqual(r.removedCurrent, false)
    assert.strictEqual(titles(r.queue), '1>2>3>5')
    assert.strictEqual(r.index, 1, '删后面的项不该动当前条索引')
    assert.strictEqual(pendingCountOf(r.queue, r.index), 2)
    assert.strictEqual(r.queue[r.index + 1].id, nextBefore, '删掉第 4 首后，下一首要还是原来的第 3 首')
  })

  test('删当前条之前的一项：索引顺延，待播数不变', () => {
    resetQueue(2)
    const before = pending()
    const r = audio.removeQueueAt(0)
    assert.strictEqual(titles(r.queue), '2>3>4>5')
    assert.strictEqual(r.index, 1, '前面的项被删，当前条索引必须跟着左移，否则播错歌')
    assert.strictEqual(r.queue[r.index].id, 3, '当前条还是原来那首')
    assert.strictEqual(pendingCountOf(r.queue, r.index), before, '删当前条之前的项不该改变待播数')
  })

  test('删当前条：不打断播放，索引顺延到下一项，待播数随之少 1', () => {
    resetQueue(2)
    const r = audio.removeQueueAt(2)
    assert.strictEqual(r.removedCurrent, true)
    assert.strictEqual(titles(r.queue), '1>2>4>5')
    assert.strictEqual(r.index, 2, '顺延后应指向原来的下一首')
    assert.strictEqual(r.queue[r.index].id, 4)
    assert.strictEqual(pendingCountOf(r.queue, r.index), 1)
  })

  test('删的是末条当前项：索引取最后一项，不越界、不出负数', () => {
    resetQueue(4)
    const r = audio.removeQueueAt(4)
    assert.strictEqual(r.index, 3)
    assert.strictEqual(pendingCountOf(r.queue, r.index), 0)
    assert.strictEqual(badgeText(pendingCountOf(r.queue, r.index)), '', '没有待播时不该挂角标')
  })

  test('删到空队列：索引 -1 且待播数 0（不是负数）', () => {
    resetQueue(0)
    while (audio.getQueue().length) audio.removeQueueAt(0)
    assert.deepStrictEqual(audio.getQueue(), [])
    assert.strictEqual(audio.getQueueIndex(), -1)
    assert.strictEqual(pending(), 0)
  })

  test('越界索引：返回 null 且队列原样（不能静默改坏队列）', () => {
    resetQueue(1)
    assert.strictEqual(audio.removeQueueAt(99), null)
    assert.strictEqual(audio.removeQueueAt(-1), null)
    assert.strictEqual(titles(audio.getQueue()), '1>2>3>4>5')
    assert.strictEqual(audio.getQueueIndex(), 1)
  })
})

describe('上移/下移后的口径', () => {
  test('把当前条上移一位：索引跟着走，待播数 +1', () => {
    resetQueue(2)
    assert.strictEqual(pending(), 2)
    assert.strictEqual(audio.moveQueueItem(2, 1), true)
    assert.strictEqual(audio.getQueueIndex(), 1, '当前条被移动后索引必须重定位')
    assert.strictEqual(titles(audio.getQueue()), '1>3>2>4>5')
    assert.strictEqual(audio.getQueue()[1].id, 3)
    assert.strictEqual(pending(), 3, '当前条前移 = 后面多一条待播')
  })

  test('把当前条下移一位：待播数 -1，且移动的确实是它自己', () => {
    resetQueue(2)
    assert.strictEqual(audio.moveQueueItem(2, 3), true)
    assert.strictEqual(audio.getQueueIndex(), 3)
    assert.strictEqual(audio.getQueue()[3].id, 3)
    assert.strictEqual(pending(), 1)
  })

  test('把后面的项插到当前条之前：当前条索引右移，待播数少 1，连播目标不变', () => {
    resetQueue(2)
    assert.strictEqual(audio.moveQueueItem(4, 1), true)
    assert.strictEqual(titles(audio.getQueue()), '1>5>2>3>4')
    assert.strictEqual(audio.getQueueIndex(), 3, '别的项插到前面，当前条索引要右移，否则角标与连播同时错位')
    assert.strictEqual(audio.getQueue()[3].id, 3, '当前条还是第 3 首')
    assert.strictEqual(audio.getQueue()[4].id, 4, '下一首还是紧跟其后的第 4 首')
    assert.strictEqual(pending(), 1)
  })

  test('原地移动 / 越界：不生效，且不改坏队列与索引', () => {
    resetQueue(1)
    assert.strictEqual(audio.moveQueueItem(2, 2), false)
    assert.strictEqual(audio.moveQueueItem(1, 9), false)
    assert.strictEqual(audio.moveQueueItem(-1, 1), false)
    assert.strictEqual(titles(audio.getQueue()), '1>2>3>4>5')
    assert.strictEqual(audio.getQueueIndex(), 1)
  })
})

describe('角标真的跟着队列变更走（真实队列 × 真实刷新器）', () => {
  test('删除/重排后下发的数字随之改变；删空后是撤角标而不是挂 "0"', () => {
    resetQueue(1)
    const badge = createTabBadge({ getQueue: audio.getQueue, getQueueIndex: audio.getQueueIndex })
    badge.reset()
    assert.deepStrictEqual(badge.refresh(), { applied: true, count: 3, text: '3' })
    audio.removeQueueAt(3)
    assert.deepStrictEqual(badge.refresh(), { applied: true, count: 2, text: '2' })
    audio.moveQueueItem(1, 0) // 当前条移到队首：待播数回到 3
    assert.deepStrictEqual(badge.refresh(), { applied: true, count: 3, text: '3' })
    audio.clearQueue()
    assert.strictEqual(badge.refresh().applied, true)
    assert.deepStrictEqual(badgeCalls.slice(-1), [{ kind: 'remove', index: 1 }])
  })

  test('不在 tab 页时跳过下发（等回到 tab 再补挂），而不是报错', () => {
    resetQueue(0)
    stackRoute = 'pages/queue/queue'
    try {
      const badge = createTabBadge({ getQueue: audio.getQueue, getQueueIndex: audio.getQueueIndex })
      badge.reset()
      assert.deepStrictEqual(badge.refresh(), { applied: false, reason: 'not-tab-page' })
      assert.deepStrictEqual(badgeCalls, [])
    } finally {
      stackRoute = 'pages/history/history'
    }
  })

  test('队列每次变更都通知订阅者：角标刷新有触发源', () => {
    resetQueue(1)
    const events = []
    const off = audio.onQueueChange((q, i) => events.push(`${titles(q)}@${i}`))
    audio.removeQueueAt(3)
    audio.moveQueueItem(1, 0)
    audio.clearQueue()
    off()
    assert.deepStrictEqual(events, ['1>2>3>5@1', '2>1>3>5@0', '@-1'],
      '删除/重排/清空漏发通知 = 角标停留在旧数字（J77 验收第 4 项）')
    audio.setQueue(FIVE.map((e) => ({ ...e })), 0)
    assert.strictEqual(events.length, 3, '退订之后不该再收到通知')
  })
})

describe('两处出口与角标接线（改坏任一连线都会红）', () => {
  test('queue 页与 detail modal 用同一套单源方法，而不是各自实现一遍', () => {
    for (const rel of ['pages/queue/queue.js', 'pages/detail/detail.js']) {
      const js = read(rel)
      assert.match(js, /require\('\.\.\/\.\.\/services\/audio'\)/, `${rel} 没有引用队列单源`)
      for (const fn of ['removeQueueAt', 'moveQueueItem']) {
        assert.ok(new RegExp(`\\b${fn}\\b`).test(js), `${rel} 没接 ${fn}：该出口仍然只能整表清空（J77）`)
        assert.ok(!new RegExp(`function ${fn}\\s*\\(`).test(js),
          `${rel} 自己又实现了一个 ${fn}：双实现复活，同一缺陷会在另一处再长回来（J77）`)
      }
    }
  })

  test('app.js 把队列变更接到角标刷新（否则角标只在 onShow 时才准）', () => {
    const app = read('app.js')
    assert.match(app, /onQueueChange\(\(\)\s*=>\s*refreshTabBadge\(\)\)/,
      'app.js 不再在队列变更时刷角标：删除/重排后角标停在旧数字，只有切 tab 才恢复（J77 验收第 4 项）')
  })

  test('两处列表都是可见按钮 + catchtap，不依赖长按手势', () => {
    for (const [rel, names] of [
      ['pages/queue/queue.wxml', ['onMoveItem', 'onRemoveItem']],
      ['pages/detail/detail.wxml', ['onQueueMove', 'onQueueRemove']],
    ]) {
      const wxml = read(rel)
      for (const name of names) {
        assert.ok(new RegExp(`catchtap="${name}"`).test(wxml), `${rel} 缺 catchtap="${name}"：点按钮会连带触发播放`)
      }
      assert.match(wxml, /aria-label="上移"[\s\S]*aria-label="下移"/, `${rel} 的上移/下移入口缺失或顺序异常`)
      assert.match(wxml, /aria-label="移出队列"/, `${rel} 缺「移出队列」入口`)
      assert.ok(!/longpress/.test(wxml), `${rel} 又把单项管理藏进长按手势（J77）`)
    }
  })
})
