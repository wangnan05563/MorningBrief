/**
 * FR-UX-604 门禁自测（T02513）
 *
 * 门禁的价值 = 它会不会红，所以这里的主角不是「通过」而是「证伪」：
 * 每条规则都构造一个真实会犯的坏样本（多为把本单修掉的句子原样写回去），
 * 断言它被点名；再补两条防误报断言，因为误报会让门禁被绕过、等同没有门禁：
 *  - 被禁的句子写在 `//` 注释里不算违规（本单会在注释里保留旧句子作考古线索）；
 *  - 动态绑定 `bindtap="{{ cond ? 'onA' : 'onB' }}"` 不参与「方法必须存在」判定。
 *
 * golden 用仓库真实文件：门禁同时是本单的回归锁——
 * 后续重构只要把 pendingChannelId 的读侧、或把开关的三处接线弄丢一条，这里立刻红。
 *
 * 运行：node --test apps/miniprogram/tests/validate-ux604.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { validate } from '../scripts/validate-ux604.mjs'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const read = (rel) => readFileSync(join(ROOT, rel), 'utf8')

/** 断言坏样本被点名（按错误信息里的编号定位，避免依赖措辞顺序） */
async function expectHit(overrides, tag) {
  const { errors } = await validate(overrides)
  assert.ok(errors.length > 0, `坏样本应被点名，却没有报错：${tag}`)
  assert.ok(
    errors.some((e) => e.includes(tag)),
    `报错里没有 ${tag} 这条：\n${errors.join('\n')}`,
  )
}

test('golden：仓库当前状态必须干净（门禁红在真实代码上=本单没修完）', async () => {
  const { errors } = await validate()
  assert.deepEqual(errors, [])
})

describe('J45/J48 页名与两页职责说明', () => {
  test('页名写回「我的频道」被抓', () =>
    expectHit({ 'pages/channels/channels.json': read('pages/channels/channels.json').replace('"全部频道"', '"我的频道"') }, 'J45'))

  test('说明里删掉「偏爱」二字被抓', () =>
    expectHit({ 'pages/channels/channels.wxml': read('pages/channels/channels.wxml').replace(/偏爱频道/g, '偏好频道') }, 'J48'))

  test('反向入口 onGoChannels 丢失被抓', () =>
    expectHit({ 'pages/preferred-settings/preferred-settings.wxml': read('pages/preferred-settings/preferred-settings.wxml').replace(/bindtap="onGoChannels"/g, '') }, 'onGoChannels'))

  test('两页只在一边写说明（preferred 侧不提订阅）被抓', () => {
    const src = read('pages/preferred-settings/preferred-settings.wxml').replace(/订阅/g, '推送')
    assert.ok(!/订阅/.test(src), '坏样本没构造成功：本页已不再出现「订阅」，这条证伪用例需要重写')
    return expectHit({ 'pages/preferred-settings/preferred-settings.wxml': src }, 'J48')
  })
})

describe('J46 跨页切换契约：写侧、读侧、定位三处缺一不可', () => {
  test('首页读侧 _consumePendingChannel 被删被抓', () =>
    expectHit({ 'pages/index/index.js': read('pages/index/index.js').replace(/_consumePendingChannel/g, 'readPendingChannel') }, 'J46'))

  test('只剩 onShow 一处调用（loadChannels 那次被重构掉）被抓', () => {
    // 去掉 loadChannels 里的那次调用（它是 catch 之前的最后一行）
    const src = read('pages/index/index.js').replace(/this\._consumePendingChannel\(\);\r?\n(\s*\} catch)/, '$1')
    assert.notEqual(src, read('pages/index/index.js'), '坏样本没构造成功：loadChannels 里的调用点样式变了')
    return expectHit({ 'pages/index/index.js': src }, 'J46')
  })

  test('写侧两处赋值一起丢（只删 channels.js 时 app.js 还在，不算断）', () =>
    expectHit(
      {
        'pages/channels/channels.js': read('pages/channels/channels.js').replace(/app\.globalData\.pendingChannelId = id;/, ''),
        'app.js': read('app.js').replace(/this\.globalData\.pendingChannelId = channelId;/, ''),
      },
      'J46',
    ))

  test('胶囊定位（scroll-into-view / 锚点 id）丢失被抓', () =>
    expectHit({ 'pages/index/index.wxml': read('pages/index/index.wxml').replace(/ scroll-into-view="\{\{scrollIntoViewId\}\}"/, '') }, 'J46'))

  test('锚点 id 换成频道 id（「全部」的 id 是 null，拼出无效锚点）被抓', () =>
    expectHit({ 'pages/index/index.wxml': read('pages/index/index.wxml').replace('id="pill-{{index}}"', 'id="pill-{{item.id}}"') }, 'J46'))

  test('读侧不再拦截非 news 频道（课程/有声书被塞进今日列表）被抓', () => {
    const src = read('pages/index/index.js').replace(
      /if \(skin\.normalizeType\(target\.channel_type\) !== 'news'\) \{[\s\S]*?\n {4}\}/,
      '',
    )
    assert.notEqual(src, read('pages/index/index.js'), '坏样本没构造成功：跨类型拦截块样式变了')
    return expectHit({ 'pages/index/index.js': src }, 'J46')
  })
})

describe('J72 取消收藏入口', () => {
  test('只剩长按手势被抓', () =>
    expectHit(
      { 'pages/favorites/favorites.wxml': read('pages/favorites/favorites.wxml').replace(/catchtap="onUnfavoriteTap"/g, '') },
      'J72',
    ))

  test('入口绑到 js 里不存在的方法被抓（与 validate-tabbar 的死入口互为反向）', () =>
    expectHit(
      { 'pages/favorites/favorites.wxml': read('pages/favorites/favorites.wxml').replace('catchtap="onUnfavoriteTap"', 'catchtap="onTapRemove"') },
      'onTapRemove',
    ))
})

describe('J80 清除缓存文案 ↔ KEEP_KEYS 同源', () => {
  test('确认文案写回「将清除本地缓存（保留登录信息与设置）」被抓', () =>
    expectHit(
      {
        'pages/settings/settings.js': read('pages/settings/settings.js').replace(
          /content:\n(\s*)'会清掉本机存的[\s\S]*?不删除服务器数据。',/,
          "$1content: '将清除本地缓存（保留登录信息与设置），确定继续？',",
        ),
      },
      'J80',
    ))

  test('KEEP_KEYS 漏掉设置 key 被抓', () =>
    expectHit(
      { 'pages/settings/settings.js': read('pages/settings/settings.js').replace(/KEEP_KEYS = \[([^\]]*)\]/, "KEEP_KEYS = ['news_token', 'news_user']") },
      'J80',
    ))

  test('设置 key 不再是单源（constants 里删掉）被抓', () =>
    expectHit({ 'services/constants.js': read('services/constants.js').replace(/STORAGE_KEY_SETTINGS[^\n]*/, 'PLACEHOLDER: 1') }, 'J99'))
})

describe('J99 隐私开关三处接线 + J98 承诺不撒谎', () => {
  test('设置页没有 usageTracking 开关被抓（隐私条款第 4 条又指向不存在的控件）', () =>
    expectHit({ 'pages/settings/settings.wxml': read('pages/settings/settings.wxml').replace(/<view class="list-item list-item--captioned">\s*<text class="list-text">记录使用统计<\/text>[\s\S]*?<\/view>/, '') }, 'J99'))

  test('开关不落 setTrackingEnabled（UI 与 tracker 各自为政）被抓', () =>
    expectHit({ 'pages/settings/settings.js': read('pages/settings/settings.js').replace(/setTrackingEnabled\(value\);/, '') }, 'J99'))

  test('tracker 的 track() 不再判 isEnabled() 被抓（关掉开关照记）', () =>
    expectHit({ 'utils/tracker.js': read('utils/tracker.js').replace(/if \(!isEnabled\(\)\) return;/, '') }, 'J99'))

  test('隐私第七条写回「退出登录即可」被抓', () =>
    expectHit({ 'pages/privacy/privacy.js': read('pages/privacy/privacy.js').replace(/3\) 要求删除个人信息——请注意：/, "3) 要求删除个人信息（退出登录即可）——") }, 'J98'))

  test('隐私第七条不再给出真实通道（删掉意见反馈）被抓', () =>
    expectHit({ 'pages/privacy/privacy.js': read('pages/privacy/privacy.js').replace(/意见反馈/g, '联系管理员邮箱') }, 'J98'))

  test('隐私第五条写回「不会上传服务器」被抓', () => {
    const src = read('pages/privacy/privacy.js').replace('只清除本机这一份，不会删除服务器上的数据', '只清除本机这一份，不会上传服务器')
    assert.notEqual(src, read('pages/privacy/privacy.js'), '坏样本没构造成功：第五条的措辞已变化，请同步这条证伪用例')
    return expectHit({ 'pages/privacy/privacy.js': src }, 'J98')
  })
})

describe('J5 浮条纠偏的两个时机', () => {
  test('缺少 pageLifetimes.show 被抓（tab 页组件常驻 → 浮条永不出现）', () =>
    expectHit({ 'components/floating-player/floating-player.js': read('components/floating-player/floating-player.js').replace(/pageLifetimes: \{[\s\S]*?\n  \},/, '') }, 'J5'))

  test('播放状态回调退回只 setData isPlaying 被抓', () =>
    expectHit(
      {
        'components/floating-player/floating-player.js': read('components/floating-player/floating-player.js').replace(
          /onPlaybackChange\(\(\) => \{\n\s*this\._refresh\(\);\n\s*\}\)/,
          "onPlaybackChange((evt) => {\n        const player = getApp().globalData.player;\n        this.setData({ isPlaying: !!(player && !player.paused) });\n      })",
        ),
      },
      'J5',
    ))
})

describe('防误报：门禁不能红在自家注释与动态绑定上', () => {
  test('被禁句子写在注释里不算违规', async () => {
    const src = read('pages/privacy/privacy.js').replace(
      "        title: '八、政策变更',",
      "        // 考古：第七节曾经写着「要求删除个人信息（退出登录即可）」，本单改掉\n        title: '八、政策变更',",
    )
    const { errors } = await validate({ 'pages/privacy/privacy.js': src })
    assert.deepEqual(errors, [])
  })

  test('动态绑定 bindtap="{{ cond ? \'onA\' : \'onB\' }}" 不参与方法存在性判定', async () => {
    const src = read('pages/favorites/favorites.wxml').replace(
      'catchtap="onUnfavoriteTap"',
      "catchtap=\"{{ removing ? 'noopHandler' : 'onUnfavoriteTap' }}\"",
    )
    const { errors } = await validate({ 'pages/favorites/favorites.wxml': src })
    assert.ok(!errors.some((e) => e.includes('noopHandler')), errors.join('\n'))
  })
})
