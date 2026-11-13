/**
 * J33 课程分支回归（T02544）：详情页拿到的 channelId 来自页面参数，恒为字符串，
 * 而频道元信息表按数字主键写入。查找若只做 Map.get(id)，课程频道会被判成 news，
 * isCourse 恒为 false —— 章节标题、合规提示、chapter_finish 埋点全部失效。
 *
 * 运行：node --test apps/miniprogram/tests/channel-meta-lookup.test.js
 */
const { test } = require('node:test')
const assert = require('node:assert')
const path = require('path')

const MP_ROOT = path.resolve(__dirname, '..')
const store = {}
const channels = [
  { id: 1, name: '科技前沿', channel_type: 'news' },
  { id: 101, name: '三体精读', channel_type: 'course' },
]

global.wx = {
  getStorageSync: (k) => (k in store ? store[k] : ''),
  setStorageSync: (k, v) => { store[k] = v },
  removeStorageSync: (k) => { delete store[k] },
  getStorageInfoSync: () => ({ keys: Object.keys(store) }),
  setStorage: (o) => { store[o.key] = o.data; o.success && o.success() },
  request: (o) => {
    const data = o.url.indexOf('/channels') >= 0 ? { list: channels } : null
    o.success && o.success({ statusCode: 200, data: { code: 0, data } })
  },
  getSystemInfoSync: () => ({ SDKVersion: '2.41.0', platform: 'devtools' }),
  canIUse: () => true,
  getNetworkType: (o) => { o.success && o.success({ networkType: 'wifi' }) },
  onNetworkStatusChange: () => {},
}
global.getApp = () => ({ globalData: { baseUrl: 'http://test.local', token: '' } })

const api = require(path.join(MP_ROOT, 'services', 'api'))

test('字符串 channelId 也能查到课程频道（页面参数恒为字符串）', async () => {
  await api.fetchChannels()
  const meta = api.getChannelMeta('101')
  assert.ok(meta, 'getChannelMeta("101") 不应为空')
  assert.strictEqual(meta.name, '三体精读')
  assert.strictEqual(api.channelType('101'), 'course')
  assert.strictEqual(api.channelType(101), 'course')
})

test('未知频道与空值仍回落 news/null', async () => {
  await api.fetchChannels()
  assert.strictEqual(api.channelType('999'), 'news')
  assert.strictEqual(api.channelType(999), 'news')
  assert.strictEqual(api.getChannelMeta(''), null)
  assert.strictEqual(api.getChannelMeta(null), null)
})
