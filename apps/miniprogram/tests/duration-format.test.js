/**
 * 时长格式化单一来源（T02710 / FR-UX-501）
 *
 * 运行：node --test apps/miniprogram/tests/duration-format.test.js
 *
 * 这一单的失效形态不是「函数算错」，而是**同一件事在十几处各算一遍**：
 * mm:ss 在 5 个 wxml 里内联抄写，秒→分在 9 个 js 里各写各的，于是同一条 00:47
 * 能在不同页面显示成「47分钟」「0分47秒」「0:47」。所以除了行为断言，这里更重要
 * 的是最后两组**静态门禁**：把「模板/页面里不许再做时长算术」变成会红的测试，
 * 否则收敛完这一轮，下一个页面照样可以再抄一遍。
 */
const { test, describe } = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

const MP_ROOT = path.resolve(__dirname, '..')
const wxs = require('../utils/duration.wxs')
const durationJs = require('../utils/duration.js')
const format = require('../utils/format')

/** 已收敛到 utils 的调用点：静态门禁按这份清单逐个核对 */
const JS_SITES = [
  'pages/course/course.js',
  'pages/detail/detail.js',
  'pages/download/download.js',
  'pages/history/history.js',
  'pages/index/index.js',
  'pages/profile/profile.js',
  'components/audio-player/audio-player.js',
]
const WXML_SITES = [
  'pages/favorites/favorites.wxml',
  'pages/index/index.wxml',
  'pages/recent/recent.wxml',
  'pages/search/search.wxml',
  'components/episode-card/episode-card.wxml',
]

const read = (rel) => fs.readFileSync(path.join(MP_ROOT, rel), 'utf8')

describe('duration.wxs 是唯一事实源', () => {
  test('utils/format.js 是转发而不是第二份实现', () => {
    // 逻辑层只能 require .js 镜像；一旦有人在 format.js 里另写一遍 mm:ss，
    // 这两个引用就会分叉，本条立刻红
    assert.strictEqual(format.time, durationJs.time)
    assert.strictEqual(format.cn, durationJs.cn)
    assert.strictEqual(format.minutes, durationJs.minutes)
    assert.strictEqual(format.splitHoursMinutes, durationJs.splitHoursMinutes)
  })

  test('duration.js 与 duration.wxs 逐字节一致（双文件镜像纪律）', () => {
    // 模板只能引 .wxs、逻辑层只能引 .js，两边靠「逐字节相同的同一份实现」保同源；
    // 只改一边就会在这里红——改法：编辑 duration.wxs 后整份复制到 duration.js
    assert.strictEqual(read('utils/duration.js'), read('utils/duration.wxs'))
  })

  test('时长模块保持 Node 可直接 require 的 ES5 子集', () => {
    // 注释里会出现「没有 padStart」这类说明，先剥掉注释再断言，否则是自己在跟自己过不去。
    // 两个镜像都要查：JS 侧虽然支持 ES6，但保持与 WXS 同一份内容就都不许越界
    for (const rel of ['utils/duration.wxs', 'utils/duration.js']) {
      const src = read(rel)
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/^\s*\/\/.*$/gm, '')
      // 模板侧只能吃 WXS；写成 ES6 语法会在真机上编译失败，而 Node 这边照样绿
      assert.doesNotMatch(src, /=>|const |let |\$\{/, rel + ' 只能用 ES5：WXS 不支持箭头函数/模板字符串')
      assert.doesNotMatch(src, /padStart|padEnd/, rel + ' 没有 padStart，补零必须手写')
      // WXS 连 Number()/isFinite() 都没有（Unexpected token '('），镜像里也不许出现
      assert.doesNotMatch(src, /Number\(|isFinite|parseFloat\(/, rel + ' 用了 WXS 不支持的全局（见 duration.wxs 头注释「语法限制」）')
    }
  })
})

describe('mm:ss（进度条 / 列表时长）', () => {
  test('常规值补零到两位分钟', () => {
    assert.strictEqual(wxs.time(0), '00:00')
    assert.strictEqual(wxs.time(47), '00:47')
    assert.strictEqual(wxs.time(600), '10:00')
    assert.strictEqual(wxs.time(3661), '61:01')
    assert.strictEqual(wxs.time(59.9), '00:59', '秒向下取整，不四舍五入到 60')
  })

  test('脏值不再分裂成 NaN:NaN 或空串', () => {
    for (const bad of [null, undefined, NaN, -5, 'abc', {}]) {
      assert.strictEqual(wxs.time(bad), '00:00', String(bad))
    }
  })
})

describe('中文时长与分钟数', () => {
  test('cn：< 1 小时说分钟，整点不说「0分钟」', () => {
    assert.strictEqual(wxs.cn(0), '0分钟')
    assert.strictEqual(wxs.cn(47 * 60), '47分钟')
    assert.strictEqual(wxs.cn(3600), '1小时')
    assert.strictEqual(wxs.cn(3900), '1小时5分钟')
  })

  test('minutes 用四舍五入（累计收听口径），floorMinutes 用向下取整（定时口径）', () => {
    assert.strictEqual(wxs.minutes(92), 2)
    assert.strictEqual(wxs.minutes(20), 0)
    assert.strictEqual(wxs.floorMinutes(119), 1)
    assert.strictEqual(wxs.floorMinutes(0), 0)
  })

  test('splitHoursMinutes 只做拆分，文案由页面自己拼', () => {
    assert.deepStrictEqual(wxs.splitHoursMinutes(5400), { hours: 1, minutes: 30 })
    assert.deepStrictEqual(wxs.splitHoursMinutes(3600), { hours: 1, minutes: 0 })
    assert.deepStrictEqual(wxs.splitHoursMinutes(90), { hours: 0, minutes: 1 })
  })
})

describe('formatDuration 分发', () => {
  test('三种 style 各自落到唯一实现', () => {
    assert.strictEqual(format.formatDuration(65, { style: 'mmss' }), '01:05')
    assert.strictEqual(format.formatDuration(65, { style: 'cn' }), '1分钟')
    assert.strictEqual(format.formatDuration(65, { style: 'minutes' }), 1)
    assert.strictEqual(format.formatDuration(65), '01:05', '不传 style 默认 mm:ss')
  })

  test('未知 style 直接抛错，不静默回退成另一种口径', () => {
    assert.throws(() => format.formatDuration(1, { style: 'hourglass' }), /未知 style/)
  })

  test('emptyText 保留「无时长就不显示」的调用点（下载列表）', () => {
    assert.strictEqual(format.formatDuration(0, { emptyText: '' }), '')
    assert.strictEqual(format.formatDuration(5, { emptyText: '' }), '00:05')
  })
})

describe('累计收听：单位口径与后端契约挂钩', () => {
  test('个人中心读的是自带单位的 total_listen_seconds，并声明换算依据', () => {
    const js = read('pages/profile/profile.js')
    assert.match(js, /stats\.total_listen_seconds/, '没读后端下发的秒值字段')
    assert.match(js, /durationFormat\.minutes\(totalListenDuration\)/, '「收听分钟」必须走唯一换算')
    // 后端字段一旦改名/改单位，这里先红，而不是界面上安静地差 60 倍
    const api = fs.readFileSync(path.join(MP_ROOT, '../../backend/app/routers/api/users.py'), 'utf8')
    assert.match(api, /"total_listen_seconds":/, 'C 端接口不再下发 total_listen_seconds，分钟口径就失去依据')
    const model = fs.readFileSync(path.join(MP_ROOT, '../../backend/app/models/user.py'), 'utf8')
    assert.match(model, /total_listen_duration[\s\S]{0,120}累计收听时长（秒）/, 'DB 列的单位注释不再声明「秒」')
  })
})

describe('跨页面显示一致：把真实页面模块加载起来跑同一条 sec', () => {
  /**
   * 验收口径「播放页、课程页、历史、下载列表在同一条目上显示的时长完全一致」
   * 不能靠读源码的 regex 冒充：只有真的 require 出页面的那个格式化函数、喂同一个值，
   * 才能在「某页偷偷改回自己算」时红。页面模块顶部会调 Page()/Component()，这里用桩接住。
   */
  const MMSS_SITES = {
    'pages/course/course.js': '_fmtDur',
    'pages/history/history.js': '_formatDuration',
    'pages/detail/detail.js': 'formatTime',
    'pages/download/download.js': '_fmtDur',
    'components/audio-player/audio-player.js': 'formatTime',
  }

  const moduleCache = new Map()

  const loadHook = (rel, key, kind) => {
    if (!moduleCache.has(rel)) {
      const prev = { Page: global.Page, Component: global.Component, getApp: global.getApp, wx: global.wx }
      let captured
      global.wx = global.wx || {}
      for (const name of ['getStorageSync', 'setStorageSync', 'getSystemInfoSync', 'createInnerAudioContext']) {
        if (typeof global.wx[name] !== 'function') global.wx[name] = () => ({})
      }
      for (const name of ['showToast', 'hideToast', 'showLoading', 'hideLoading', 'navigateTo', 'navigateBack', 'setTabBarBadge', 'removeTabBarBadge']) {
        if (typeof global.wx[name] !== 'function') global.wx[name] = () => {}
      }
      global.getApp = global.getApp || (() => ({ globalData: {} }))
      global.Page = (o) => { captured = o }
      global.Component = (o) => { captured = kind === 'component' ? (o.methods || o) : o }
      try {
        require(path.join(MP_ROOT, rel))
      } finally {
        global.Page = prev.Page
        global.Component = prev.Component
        global.getApp = prev.getApp
        global.wx = prev.wx
      }
      assert.ok(captured, `${rel} 没把配置交给 Page()/Component()，桩没接住`)
      moduleCache.set(rel, captured)
    }
    const captured = moduleCache.get(rel)
    assert.ok(typeof captured[key] === 'function', `${rel} 里取不到 ${key}()，调用点被改名或删除`)
    return captured[key]
  }

  test('同一 sec 值在四处 mm:ss 调用点输出逐字相同', () => {
    const fns = Object.entries(MMSS_SITES).map(([rel, key]) => ({
      rel,
      fn: loadHook(rel, key, rel.startsWith('components/') ? 'component' : 'page'),
    }))
    for (const sec of [0, 5, 47, 65, 599, 600, 905, 3600, 3661, 7325, null, undefined, -3, 'abc']) {
      const expected = Number(sec) > 0 ? wxs.time(sec) : '00:00'
      // 下载列表是「无时长就不显示」的白名单：0 值给空串，其余仍与其他站点同字
      const expectedFor = (rel) => (rel === 'pages/download/download.js' && !(Number(sec) > 0) ? '' : expected)
      for (const { rel, fn } of fns) {
        assert.strictEqual(fn.call({ data: {} }, sec), expectedFor(rel),
          `${rel} 在 sec=${String(sec)} 上与其他页面不一致`)
      }
    }
  })

  test('详情页中文时长与其他口径同源（秒向下取整到分）', () => {
    const cn = loadHook('pages/detail/detail.js', 'formatDuration', 'page')
    for (const sec of [0, 59, 60, 65, 3600, 3900]) {
      assert.strictEqual(cn.call({ data: {} }, sec), wxs.cn(sec))
    }
  })
})

describe('静态门禁：页面与模板不再自己做时长算术', () => {
  /** 秒↔分↔时 的换算表达式：这一类只允许出现在 utils 下 */
  const DURATION_MATH = [
    /Math\.floor\([^)]*\/\s*60/,
    /Math\.round\([^)]*\/\s*60/,
    /%\s*60\b/,
  ]

  test('js 调用点：无换算残留，且确实 require 了 utils/format', () => {
    for (const rel of JS_SITES) {
      const src = read(rel)
      for (const re of DURATION_MATH) {
        assert.doesNotMatch(src, re, `${rel} 仍在自己算时长：${re}`)
      }
      assert.match(src, /require\('\.\.\/\.\.\/utils\/format'\)/, `${rel} 应改为调用 utils/format`)
      assert.match(src, /durationFormat\./, `${rel} 引了模块却没调用`)
    }
  })

  test('wxml 调用点：内联 wxs 不再算时长，统一引共享模块', () => {
    for (const rel of WXML_SITES) {
      const src = read(rel)
      assert.match(src, /<wxs module="dur" src="\.\.\/\.\.\/utils\/duration\.wxs"/, `${rel} 没接共享 WXS`)
      assert.doesNotMatch(src, /Math\.floor\(s \/ 60\)/, `${rel} 还留着内联 mm:ss`)
      assert.doesNotMatch(src, /fmt\.time\(/, `${rel} 还在引用旧的内联时长模块`)
      assert.match(src, /dur\.time\(/, `${rel} 模板没有真正调用共享时长函数`)
    }
  })

  test('全仓 pages/ 与 components/ 目录级扫描：时长算术命中数为 0', () => {
    // 上面两条按清单点名，清单本身可能被绕过（新页面没登记）；这条是兜底的面扫描
    const hits = []
    const walk = (dir) => {
      for (const entry of fs.readdirSync(path.join(MP_ROOT, dir), { withFileTypes: true })) {
        const rel = path.posix.join(dir, entry.name)
        if (entry.isDirectory()) {
          walk(rel)
          continue
        }
        if (!/\.(js|wxml)$/.test(entry.name)) continue
        const src = fs.readFileSync(path.join(MP_ROOT, rel), 'utf8')
        for (const re of DURATION_MATH) {
          const line = src.split('\n').findIndex((l) => re.test(l))
          if (line >= 0) hits.push(`${rel}:${line + 1} ${re}`)
        }
      }
    }
    walk('pages')
    walk('components')
    assert.deepStrictEqual(hits, [], '这些位置还在自己换算时长，请改调 utils/format 或 utils/duration.wxs')
  })
})
