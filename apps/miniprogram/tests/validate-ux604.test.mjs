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

/**
 * 构造坏样本。必须验证「替换真的发生了」：
 * 锚点正则在文件里命中 0 次时，String.replace 原样返回，门禁吃到的还是仓库的好代码，
 * 于是这条证伪用例永远绿——比没有用例更糟，因为它假装查过了。
 * （本单第一版就中过这个坑：KEEP_KEYS 里的 SETTINGS 不是最后一项，
 * 带 `(?=\];)` 的锚点没命中，用例照样「通过」。）
 */
function mutate(rel, re, to) {
  const src = read(rel)
  assert.ok(re.test(src), `坏样本没构造成功：${rel} 里找不到锚点 ${re}`)
  const out = src.replace(re, to)
  assert.notEqual(out, src, `坏样本没改动 ${rel}`)
  return out
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

describe('J80 / T02787 清除缓存：白名单分类 ↔ 接线 ↔ 文案 三处同源', () => {
  test('确认文案写回「将清除本地缓存（保留登录信息与设置）」被抓', () =>
    expectHit(
      {
        'pages/settings/settings.js': mutate(
          'pages/settings/settings.js',
          /content:\n\s*'只清可再生[\s\S]*?提出请求。',/,
          "content: '将清除本地缓存（保留登录信息与设置），确定继续？',",
        ),
      },
      'J80',
    ))

  test('清除动作写回「KEEP_KEYS 之外全删」的黑名单被抓（J80 的事故那一行）', () =>
    expectHit(
      {
        'pages/settings/settings.js': mutate(
          'pages/settings/settings.js',
          /const removed = clearCacheKeys\(info\.keys, \(key\) => wx\.removeStorageSync\(key\)\);/,
          'const removed = []; info.keys.forEach((key) => { if (KEEP_KEYS.indexOf(key) === -1) { wx.removeStorageSync(key); removed.push(key); } });',
        ),
      },
      'T02787',
    ))

  test('分类表 KEEP_KEYS 漏掉设置 key 被抓（清缓存会把用户设置一起抹掉）', () =>
    expectHit(
      { 'services/storage-keys.js': mutate('services/storage-keys.js', /  STATIC\.SETTINGS,\n/, '') },
      'J80',
    ))

  test('settings.js 不再引用 storage-keys 单源被抓（删哪些又回到页面自己说了算）', () =>
    expectHit(
      {
        'pages/settings/settings.js': mutate(
          'pages/settings/settings.js',
          /const \{ STATIC: STORAGE_KEYS, clearCacheKeys \} = require\('\.\.\/\.\.\/services\/storage-keys'\);/,
          "const STORAGE_KEY_SETTINGS = 'news_settings';",
        ),
      },
      'T02787',
    ))

  test('页面里写死 storage key 字面量被抓（新增散 key 会让白名单列不全）', () =>
    expectHit(
      { 'pages/search/search.js': mutate('pages/search/search.js', /wx\.getStorageSync\(STORAGE_KEY_HISTORY\)/, "wx.getStorageSync('search_history')") },
      'T02787',
    ))

  test('constants.js 重新导出第二份设置 key 被抓（分类表不再等于全集）', () =>
    expectHit(
      { 'services/constants.js': mutate('services/constants.js', /\n\];|\n\};/, ',\n  STORAGE_KEY_SETTINGS: \'news_settings\',\n};') },
      'T02787',
    ))

  test('tracker.js 不再从单源读设置 key 被抓（开关会读一个没人写的 key）', () =>
    expectHit(
      {
        'utils/tracker.js': mutate(
          'utils/tracker.js',
          /const STORAGE_KEY_SETTINGS = require\('\.\.\/services\/storage-keys'\)\.STATIC\.SETTINGS;/,
          "const STORAGE_KEY_SETTINGS = 'news_settings';",
        ),
      },
      'J99',
    ))

  test('清缓存不再毁数据却仍用红色「仍要清除」吓用户被抓（文案与实现脱钩）', () =>
    expectHit(
      { 'pages/settings/settings.js': mutate('pages/settings/settings.js', /confirmText: '清除',/, "confirmText: '仍要清除',") },
      'T02787',
    ))

  test('行下说明写回「清除本机存的收藏…」被抓（实现改了、说明还在承诺删数据）', () =>
    expectHit(
      {
        'pages/settings/settings.wxml': mutate(
          'pages/settings/settings.wxml',
          /<text>只清除可再生的技术缓存[\s\S]*?不删除服务器数据。<\/text>/,
          '<text>清除本机存的收藏、播放进度与历史、偏爱频道、下载/搜索/反馈记录；保留登录信息与本设置页的开关。只影响本机，不删除服务器数据。</text>',
        ),
      },
      'T02787',
    ))

  test('行下说明整条删掉被抓（影响面只在弹窗里说，进页读不到）', () =>
    expectHit(
      {
        'pages/settings/settings.wxml': mutate(
          'pages/settings/settings.wxml',
          /<view class="list-caption">\s*<text>只清除可再生的技术缓存[\s\S]*?<\/text>\s*<\/view>\n/,
          '',
        ),
      },
      'T02787',
    ))
})

describe('J99 隐私开关三处接线 + J98 承诺不撒谎', () => {
  test('设置页没有 usageTracking 开关被抓（隐私条款第 4 条又指向不存在的控件）', () =>
    expectHit({ 'pages/settings/settings.wxml': read('pages/settings/settings.wxml').replace(/<view class="list-item list-item--captioned">\s*<text class="list-text">记录使用统计<\/text>[\s\S]*?<\/view>/, '') }, 'J99'))

  test('开关不落 setTrackingEnabled（UI 与 tracker 各自为政）被抓', () =>
    expectHit({ 'pages/settings/settings.js': read('pages/settings/settings.js').replace(/setTrackingEnabled\(value\);/, '') }, 'J99'))

  test('tracker 的 track() 不再判 isEnabled() 被抓（关掉开关照记）', () =>
    expectHit({ 'utils/tracker.js': read('utils/tracker.js').replace(/if \(!isEnabled\(\)\) return;/, '') }, 'J99'))

  test('隐私第七条写回「退出登录即可」被抓', () =>
    expectHit({ 'pages/privacy/privacy.js': mutate('pages/privacy/privacy.js', /3\) 要求删除个人信息——请注意：/, "3) 要求删除个人信息（退出登录即可）——") }, 'J98'))

  test('隐私第七条不再给出真实通道（删掉意见反馈）被抓', () =>
    expectHit({ 'pages/privacy/privacy.js': mutate('pages/privacy/privacy.js', /意见反馈/g, '联系管理员邮箱') }, 'J98'))

  test('隐私第五条写回「不会上传服务器」被抓', () =>
    expectHit(
      {
        'pages/privacy/privacy.js': mutate(
          'pages/privacy/privacy.js',
          /上面这些本机数据一项都不会被它清掉；它同样不会删除服务器上的数据。/,
          '上面这些本机数据一项都不会被它清掉；它们也不会上传服务器。',
        ),
      },
      'J98',
    ))

  test('隐私第五条写回「清除缓存只清除本机这一份」被抓（实现改了、承诺没跟着改）', () =>
    expectHit(
      {
        'pages/privacy/privacy.js': mutate(
          'pages/privacy/privacy.js',
          /「设置 → 存储管理 → 清除缓存」只清可再生的技术缓存[\s\S]*?不会删除服务器上的数据。/,
          "「设置 → 存储管理 → 清除缓存」只清除本机这一份，不会删除服务器上的数据。',",
        ),
      },
      'T02787',
    ))
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

describe('T02540 / M6 信息架构：文案与入口的回归锁', () => {
  test('J21 退出弹窗写回「确定要退出登录吗？」被抓', () => {
    const src = read('pages/profile/profile.js').replace(
      /content: '退出只清除本机缓存与下载[\s\S]*?处理。'/,
      "content: '确定要退出登录吗？'",
    )
    assert.notEqual(src, read('pages/profile/profile.js'), '坏样本没构造成功：退出弹窗文案已变化，请同步这条证伪用例')
    return expectHit({ 'pages/profile/profile.js': src }, 'J21')
  })

  test('J21 删掉删除通道「意见反馈」被抓', () =>
    expectHit(
      { 'pages/profile/profile.js': read('pages/profile/profile.js').replace('请通过「意见反馈」联系我们处理', '请等待我们后续提供自助入口') },
      'J21',
    ))

  test('J24 登录按钮退回纯图标被抓', () =>
    expectHit(
      {
        'pages/profile/profile.wxml': read('pages/profile/profile.wxml')
          .replace('class="btn-primary login-btn"', 'class="btn-primary btn-icon-only login-btn"')
          .replace('<text class="btn-label">微信一键登录</text>', ''),
      },
      'J24',
    ))

  test('J24 保存按钮删掉文字被抓', () =>
    expectHit(
      { 'pages/profile/profile.wxml': read('pages/profile/profile.wxml').replace('<text class="btn-label btn-label--confirm">保存</text>', '') },
      'J24',
    ))

  test('J66 偏爱说明不写作用面（首页/历史）被抓', () =>
    expectHit(
      { 'pages/preferred-settings/preferred-settings.wxml': read('pages/preferred-settings/preferred-settings.wxml').replace('首页与历史的频道栏末尾', '频道栏末尾') },
      'J66',
    ))

  test('J105 webview 兜底按钮退回纯图标被抓', () =>
    expectHit(
      { 'pages/webview/webview.wxml': read('pages/webview/webview.wxml').replace('class="btn-primary"', 'class="btn-primary btn-icon-only"') },
      'J105',
    ))

  test('J105 删掉「返回」可见文案被抓', () =>
    expectHit(
      { 'pages/webview/webview.wxml': read('pages/webview/webview.wxml').replace('<text>返回</text>', '') },
      'J105',
    ))

  test('J105 URL 展示区去掉高度上限/滚动被抓', () => {
    const src = read('pages/webview/webview.wxss').replace(/max-height: 240rpx;\s*overflow-y: auto;/, '')
    assert.notEqual(src, read('pages/webview/webview.wxss'), '坏样本没构造成功：.fallback-url 的限高样式已变化')
    return expectHit({ 'pages/webview/webview.wxss': src }, 'J105')
  })

  test('J69 onShow 退回每次重载被抓', () => {
    const src = read('pages/recent/recent.js').replace(/  onShow\(\) \{[\s\S]*?\n  \},/, '  onShow() {\n    this.loadRecent(true);\n  },')
    assert.notEqual(src, read('pages/recent/recent.js'), '坏样本没构造成功：recent.js 的 onShow 结构已变化')
    return expectHit({ 'pages/recent/recent.js': src }, 'J69')
  })

  test('J77 队列页删掉单项移出入口被抓', () =>
    expectHit(
      { 'pages/queue/queue.wxml': read('pages/queue/queue.wxml').replace(/catchtap="onRemoveItem"/g, '') },
      'J77',
    ))

  test('J77 详情 modal 删掉单项移出入口被抓', () =>
    expectHit(
      { 'pages/detail/detail.wxml': read('pages/detail/detail.wxml').replace(/catchtap="onQueueRemove"/g, '') },
      'J77',
    ))

  test('J77 services/audio.js 不再导出 removeQueueAt（两页只能各写一套）被抓', () =>
    expectHit(
      { 'services/audio.js': read('services/audio.js').replace(/\n  removeQueueAt,/, '') },
      'J77',
    ))

  test('J77 队列变更不再实时刷角标（只在 tab 页 onShow 补挂）被抓', () =>
    expectHit(
      { 'app.js': mutate('app.js', /onQueueChange\(\(\)\s*=>\s*refreshTabBadge\(\)\)/, 'onQueueChange(() => {})') },
      'J77',
    ))

  test('J77 把角标接线只写进注释也照样被抓（门禁读的是去注释后的代码）', () =>
    expectHit(
      { 'app.js': mutate('app.js', /onQueueChange\(\(\)\s*=>\s*refreshTabBadge\(\)\)/, '// onQueueChange(() => refreshTabBadge())') },
      'J77',
    ))

  test('J14 历史页删掉「我的播放记录」出口被抓', () =>
    expectHit(
      { 'pages/history/history.wxml': read('pages/history/history.wxml').replace(/我的播放记录/g, '最近') },
      'J14',
    ))

  test('J12 队列 chip 退回纯图标被抓', () =>
    expectHit(
      { 'pages/history/history.wxml': read('pages/history/history.wxml').replace('<text class="queue-chip-label">队列</text>', '') },
      'J12',
    ))

  test('J20 个人中心第二层退回 secondList 内嵌列表被抓', () =>
    expectHit(
      { 'pages/profile/profile.wxml': read('pages/profile/profile.wxml').replace('<view class="card second-panel">', '<view class="card second-panel" wx:for="{{secondList}}">') },
      'J20',
    ))
})

describe('T02542 / M7：长任务收尾与逐菜单缺陷', () => {
  test('J27 删掉缓冲中节点被抓', () =>
    expectHit(
      { 'pages/detail/detail.wxml': read('pages/detail/detail.wxml').replace(/<view class="waiting-tip"[\s\S]*?缓冲中…<\/view>/, '') },
      'J27',
    ))

  test('J28 删掉课程章节坐标被抓', () =>
    expectHit(
      { 'pages/detail/detail.wxml': read('pages/detail/detail.wxml').replace(/\{\{chapterLabel\}\}/g, '') },
      'J28',
    ))

  test('J32 删掉失败态重试入口被抓', () =>
    expectHit(
      { 'pages/detail/detail.wxml': read('pages/detail/detail.wxml').replace('bindtap="onRetryLoad"', '') },
      'J32',
    ))

  test('J59 离线兜底接回远端 URL（断网仍失败）被抓', () =>
    expectHit(
      { 'pages/detail/detail.js': read('pages/detail/detail.js').replace('audio_url: rec.localPath', 'audio_url: rec.audio_url') },
      'J59',
    ))

  test('J73 已下架退回纯降透明度被抓', () =>
    expectHit(
      { 'pages/favorites/favorites.wxml': read('pages/favorites/favorites.wxml').replace('>已下架</text>', '></text>') },
      'J73',
    ))

  test('J81 检查更新退回固定 2s「已是最新」被抓', () => {
    const src = read('pages/settings/settings.js')
      .replace('检查超时，请稍后重试', '已是最新版本')
      .replace('}, 8000)', '}, 2000)')
    assert.notEqual(src, read('pages/settings/settings.js'), '坏样本没构造成功：onCheckUpdate 的兜底文案/时长已变化')
    return expectHit({ 'pages/settings/settings.js': src }, 'J81')
  })
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
