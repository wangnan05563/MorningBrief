/**
 * 底部导航门禁自测（T02510 / FR-UX-601，M6）
 *
 * 门禁的价值 = 它会不会红。所以本文件不测「通过」，而是逐条证伪：
 * 每一条规则都构造一个真实会犯的坏样本（T02323 评审里的 J1/J12/J19 + 本单新加的
 * 角标挂载点），断言它被点名；同时断言 golden 样本干净——
 * 否则「测试通过」只说明 fixture 恰好没触发规则。
 *
 * 另外两条防误报断言（误报会让门禁被绕过，等同没有门禁）：
 *  - `routeMap` 值写成 `/pages/x/x`（带前导斜杠）不算未注册；
 *  - `bindtap="{{ state==='a' ? 'onA' : 'onB' }}"` 里的方法名算已绑定（detail 页
 *    onDownloadCancel 就是这个写法，早先被误判成死入口）。
 *
 * 运行：node --test apps/miniprogram/tests/validate-tabbar.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { checkFacts, collectFacts, validate } from '../scripts/validate-tabbar.mjs'

const ICONS = [
  'images/tab/home.png',
  'images/tab/home-active.png',
  'images/tab/history.png',
  'images/tab/history-active.png',
]

/** golden 样本：一个「已经修好」的最小小程序，所有规则都必须放行 */
function golden() {
  return {
    appJsonRaw: JSON.stringify({
      pages: ['pages/index/index', 'pages/history/history', 'pages/queue/queue'],
      tabBar: {
        list: [
          {
            pagePath: 'pages/index/index',
            text: '今日',
            iconPath: ICONS[0],
            selectedIconPath: ICONS[1],
          },
          {
            pagePath: 'pages/history/history',
            text: '历史',
            iconPath: ICONS[2],
            selectedIconPath: ICONS[3],
          },
        ],
      },
    }),
    pageTexts: {
      index: {
        js: `Page({
  data: {},
  onShow() { this.refreshBadge(); },
  onTapSearch() { wx.navigateTo({ url: '/pages/queue/queue' }); },
})`,
        wxml: `<view class="page">
  <view class="search" bindtap="onTapSearch" aria-label="搜索"></view>
</view>`,
        json: `{
  "navigationBarTitleText": "今日节目"
}`,
      },
      history: {
        js: `Page({
  data: {},
  onShow() {},
  onTapEntry(e) {
    const routeMap = { queue: '/pages/queue/queue' };
    const key = e.currentTarget.dataset.key;
    wx.navigateTo({ url: routeMap[key] });
  },
  onOpenQueue() {},
})`,
        wxml: `<view class="page">
  <view class="item" data-key="queue" bindtap="onTapEntry"><text>播放队列</text></view>
  <view class="chip" bindtap="onOpenQueue"></view>
</view>`,
        json: `{
  "navigationBarTitleText": "历史节目"
}`,
      },
      queue: {
        js: `Page({
  data: {},
  onLoad() {},
  onTapBack() { wx.navigateBack(); },
})`,
        wxml: `<view class="page"><view bindtap="onTapBack"><text>返回</text></view></view>`,
        json: `{
  "navigationBarTitleText": "播放队列"
}`,
      },
    },
    badgeFacts: {
      historyIndex: 1,
      routes: { 'pages/index/index': 0, 'pages/history/history': 1 },
    },
    files: new Set(ICONS),
  }
}

/** 跑门禁：返回错误文案数组 */
function errorsOf(mutate = () => {}) {
  const fx = golden()
  mutate(fx)
  return checkFacts(collectFacts(fx)).errors
}

/** 断言「有一条错误包含指定片段」，并回传该条供进一步断言 */
function expectError(errors, snippet) {
  const hit = errors.find((e) => e.includes(snippet))
  assert.ok(hit, `期望门禁点名「${snippet}」，实际错误：\n${errors.join('\n') || '（无）'}`)
  return hit
}

describe('golden 样本必须干净', () => {
  test('正常配置零错误（否则后面的断言全是在跟噪音搏斗）', () => {
    assert.deepEqual(errorsOf(), [])
  })

  test('真实仓库通过门禁', async () => {
    const { errors } = await validate()
    assert.deepEqual(errors, [])
  })
})

describe('J1 · tab 必须有文字', () => {
  test('text 缺失被点名', () => {
    const errs = errorsOf((fx) => {
      const app = JSON.parse(fx.appJsonRaw)
      delete app.tabBar.list[0].text
      fx.appJsonRaw = JSON.stringify(app)
    })
    expectError(errs, '缺少 text')
  })

  test('text 为空白串同样算缺失', () => {
    const errs = errorsOf((fx) => {
      const app = JSON.parse(fx.appJsonRaw)
      app.tabBar.list[1].text = '  '
      fx.appJsonRaw = JSON.stringify(app)
    })
    expectError(errs, '缺少 text')
  })

  test('两个 tab 同名被点名', () => {
    const errs = errorsOf((fx) => {
      const app = JSON.parse(fx.appJsonRaw)
      app.tabBar.list[1].text = '今日'
      fx.appJsonRaw = JSON.stringify(app)
    })
    expectError(errs, '与 tab 1 重复')
  })

  test('tab 文案与页面标题漂移（首页 vs 今日节目）被点名', () => {
    const errs = errorsOf((fx) => {
      const app = JSON.parse(fx.appJsonRaw)
      app.tabBar.list[0].text = '首页'
      fx.appJsonRaw = JSON.stringify(app)
    })
    expectError(errs, '与页面标题「今日节目」对不上')
  })

  test('pagePath 未注册在 pages 里被点名', () => {
    const errs = errorsOf((fx) => {
      const app = JSON.parse(fx.appJsonRaw)
      app.tabBar.list[0].pagePath = 'pages/home/home'
      fx.appJsonRaw = JSON.stringify(app)
    })
    expectError(errs, 'pagePath 未在 app.json.pages 中注册')
  })

  test('三件套缺 json 被点名', () => {
    const errs = errorsOf((fx) => {
      fx.pageTexts.history.json = null
    })
    expectError(errs, 'pages/history/history.json 缺失')
  })

  test('图标文件不存在被点名（路径写错是静默不显示）', () => {
    const errs = errorsOf((fx) => {
      fx.files.delete(ICONS[2])
    })
    expectError(errs, 'iconPath 指向的文件不存在')
  })

  test('tab 数量超出微信允许区间被点名', () => {
    const errs = errorsOf((fx) => {
      const app = JSON.parse(fx.appJsonRaw)
      app.tabBar.list = []
      fx.appJsonRaw = JSON.stringify(app)
    })
    expectError(errs, '微信要求 2~5')
  })
})

describe('角标挂载点与 tabBar 顺序绑定', () => {
  test('前面插入一个 tab 后 HISTORY_TAB_INDEX 未跟着改 → 点名「挂错 tab」', () => {
    const errs = errorsOf((fx) => {
      const app = JSON.parse(fx.appJsonRaw)
      app.pages.unshift('pages/discover/discover')
      app.tabBar.list.unshift({
        pagePath: 'pages/discover/discover',
        text: '发现',
        iconPath: ICONS[0],
        selectedIconPath: ICONS[1],
      })
      fx.appJsonRaw = JSON.stringify(app)
      fx.pageTexts.discover = {
        js: 'Page({ onShow() {} })',
        wxml: '<view></view>',
        json: '{"navigationBarTitleText":"发现"}',
      }
      fx.badgeFacts = {
        historyIndex: 1,
        routes: { 'pages/index/index': 0, 'pages/history/history': 1 },
      }
    })
    expectError(errs, '角标会挂错 tab')
  })

  test('TAB_ROUTES 下标与 tabBar 顺序不一致被点名', () => {
    const errs = errorsOf((fx) => {
      fx.badgeFacts = {
        historyIndex: 1,
        routes: { 'pages/index/index': 1, 'pages/history/history': 1 },
      }
    })
    expectError(errs, "TAB_ROUTES['pages/index/index']=1")
  })

  test('TAB_ROUTES 里残留已降级为非 tab 的页面被点名', () => {
    const errs = errorsOf((fx) => {
      fx.badgeFacts = {
        historyIndex: 1,
        routes: { 'pages/index/index': 0, 'pages/history/history': 1, 'pages/queue/queue': 2 },
      }
    })
    expectError(errs, '已不是 tabBar 页')
  })

  test('缺 utils/tab-badge.js 时记为跳过而不是假装查过', () => {
    const fx = golden()
    fx.badgeFacts = null
    const { errors, notes } = checkFacts(collectFacts(fx))
    assert.deepEqual(errors, [])
    assert.ok(notes.some((n) => n.includes('跳过角标挂载点校验')))
  })
})

describe('J12 · 死入口与纯图标入口', () => {
  test('js 定义了 onXxx 但 wxml 从未绑定 → 死入口', () => {
    const errs = errorsOf((fx) => {
      fx.pageTexts.index.wxml = '<view class="page"></view>'
    })
    expectError(errs, '方法 onTapSearch() 既没在同页 wxml 里绑定')
  })

  test('js 内部 this.onXxx 调用算活引用', () => {
    const errs = errorsOf((fx) => {
      fx.pageTexts.index.wxml = '<view class="page"></view>'
      fx.pageTexts.index.js = `Page({
  onShow() { this.onTapSearch(); },
  onTapSearch() {},
})`
    })
    assert.equal(errs.filter((e) => e.includes('onTapSearch')).length, 0)
  })

  test('gate-allow 注释可豁免，且必须写明原因', () => {
    const errs = errorsOf((fx) => {
      fx.pageTexts.index.wxml = '<view class="page"></view>'
      fx.pageTexts.index.js = `Page({
  onShow() {},
  /* gate-allow: 由父组件回调触发，暂无 wxml 宿主 */
  onTapSearch() {},
})`
    })
    assert.equal(errs.filter((e) => e.includes('onTapSearch')).length, 0)
  })

  test('生命周期方法不参与死入口判定', () => {
    const errs = errorsOf((fx) => {
      fx.pageTexts.index.wxml = '<view class="page"></view>'
      fx.pageTexts.index.js = `Page({
  onShow() {},
  onPullDownRefresh() {},
  onReachBottom() {},
})`
    })
    assert.deepEqual(errs, [])
  })

  test('三元动态绑定里的方法名算已绑定（防误报）', () => {
    const errs = errorsOf((fx) => {
      fx.pageTexts.queue.js = `Page({
  data: { downloadState: 'downloading' },
  onDownloadCancel() {},
  onDownloadTap() {},
})`
      fx.pageTexts.queue.wxml =
        `<view bindtap="{{ downloadState === 'downloading' ? 'onDownloadCancel' : 'onDownloadTap' }}"><text>下载</text></view>`
    })
    assert.deepEqual(errs, [])
  })

  test('纯变量动态绑定无法静态判定：不报错也不假装查过', () => {
    const errs = errorsOf((fx) => {
      fx.pageTexts.queue.js = `Page({ onTapFoo() {} })`
      fx.pageTexts.queue.wxml = '<view bindtap="{{handler}}"><text>x</text></view>'
    })
    // 静态拿不到方法名 → 该页没有字符串引用 → 按规则报死入口（宁可报出来让人确认）
    expectError(errs, '方法 onTapFoo()')
  })

  test('进入队列页的入口没有可见文案（纯图标 chip）被点名', () => {
    const errs = errorsOf((fx) => {
      fx.pageTexts.history.wxml = `<view class="page">
  <view class="item" data-key="queue" bindtap="onTapEntry"><image src="/images/icons/list.png" /></view>
  <view class="chip" bindtap="onOpenQueue"></view>
</view>`
    })
    expectError(errs, '没有可见文案')
  })

  test('data-key 入口存在但文案为空字符串同样算没有文案', () => {
    const errs = errorsOf((fx) => {
      fx.pageTexts.history.wxml = `<view class="page">
  <view class="item" data-key="queue" bindtap="onTapEntry"><text>   </text></view>
  <view class="chip" bindtap="onOpenQueue"></view>
</view>`
    })
    expectError(errs, '没有可见文案')
  })
})

describe('死路由键（T00726 残留形态）', () => {
  test('routeMap 里有键、同页 wxml 没有对应 data-key → 死键', () => {
    const errs = errorsOf((fx) => {
      fx.pageTexts.history.js = `Page({
  data: {},
  onTapEntry(e) {
    const routeMap = { queue: '/pages/queue/queue', favorites: '/pages/queue/queue' };
    wx.navigateTo({ url: routeMap[e.currentTarget.dataset.key] });
  },
  onOpenQueue() {},
})`
    })
    expectError(errs, 'routeMap 里的 favorites')
    // queue 键仍有效，不该被连带误报
    assert.equal(errs.filter((e) => e.includes('routeMap 里的 queue')).length, 0)
  })

  test('routeMap 指向未在 pages 注册的路由 → 点名（navigateTo 必失败）', () => {
    const errs = errorsOf((fx) => {
      const app = JSON.parse(fx.appJsonRaw)
      app.pages = app.pages.filter((p) => p !== 'pages/queue/queue')
      fx.appJsonRaw = JSON.stringify(app)
    })
    expectError(errs, '未在 app.json.pages 注册（navigateTo 必然失败）')
  })

  test('带前导斜杠的路由不算未注册（防误报）', () => {
    // golden 里 routeMap.queue 写的是 '/pages/queue/queue'，pages 写的是 'pages/queue/queue'
    assert.deepEqual(errorsOf(), [])
  })

  test('同页完全没有 data-key 时记为跳过（不误伤非入口型页面）', () => {
    const fx = golden()
    fx.pageTexts.history.wxml = '<view class="page"><text>历史</text></view>'
    const { errors, notes } = checkFacts(collectFacts(fx))
    assert.equal(errors.filter((e) => e.includes('死键')).length, 0)
    assert.ok(notes.some((n) => n.includes('跳过死键检查')))
    // 但入口消失本身要被别条规则看见：onTapEntry/onOpenQueue 都不再被绑定
    expectError(errors, '死入口')
  })
})

describe('J19 · 合规入口不得藏在条件分支里', () => {
  const withPrivacy = (fx, wxml) => {
    fx.pageTexts.history.wxml = wxml
  }

  test('隐私政策入口在 wx:if 分支内被点名', () => {
    const errs = errorsOf((fx) => {
      withPrivacy(
        fx,
        `<view class="page">
  <view class="item" data-key="queue" bindtap="onTapEntry"><text>播放队列</text></view>
  <block wx:if="{{userInfo}}">
    <view class="item" data-key="privacy" bindtap="onTapEntry"><text>隐私政策</text></view>
  </block>
</view>`,
      )
    })
    expectError(errs, '落在条件分支里')
  })

  test('wx:else 分支同样被点名', () => {
    const errs = errorsOf((fx) => {
      withPrivacy(
        fx,
        `<view class="page">
  <view class="item" data-key="queue" bindtap="onTapEntry"><text>播放队列</text></view>
  <view wx:if="{{a}}"><text>A</text></view>
  <view wx:else class="item" data-key="agreement" bindtap="onTapEntry"><text>用户协议</text></view>
</view>`,
      )
    })
    expectError(errs, 'data-key="agreement"')
  })

  test('wx:for 列表不算条件分支（列表页常见写法，报了就成噪音）', () => {
    const errs = errorsOf((fx) => {
      withPrivacy(
        fx,
        `<view class="page">
  <view class="item" data-key="queue" bindtap="onTapEntry"><text>播放队列</text></view>
  <view wx:for="{{list}}" class="item" data-key="privacy" bindtap="onTapEntry"><text>隐私政策</text></view>
</view>`,
      )
    })
    assert.equal(errs.filter((e) => e.includes('条件分支')).length, 0)
  })

  test('分支未命中时用户拿不到入口，正是 J19 的形态：登录态外层 block 也要算', () => {
    const errs = errorsOf((fx) => {
      withPrivacy(
        fx,
        `<view class="page">
  <block wx:if="{{userInfo}}">
    <view class="item" data-key="queue" bindtap="onTapEntry"><text>播放队列</text></view>
  </block>
  <block wx:else>
    <view class="item" data-key="feedback" bindtap="onTapEntry"><text>意见反馈</text></view>
  </block>
</view>`,
      )
    })
    expectError(errs, 'data-key="feedback"')
  })
})

describe('抽取器本身的边界', () => {
  test('app.json 缺失 → 记为跳过，不抛异常', () => {
    const { errors, notes } = checkFacts(collectFacts({ appJsonRaw: null }))
    assert.deepEqual(errors, [])
    assert.ok(notes.some((n) => n.includes('未找到 app.json')))
  })

  test('app.json 语法坏 → 点名解析失败并跳过', () => {
    const { errors, notes } = checkFacts(collectFacts({ appJsonRaw: '{ oops' }))
    assert.deepEqual(errors, [])
    assert.ok(notes.some((n) => n.includes('app.json 解析失败')))
  })

  test('缺 tabBar → 直接点名底部导航不存在', () => {
    const fx = golden()
    const app = JSON.parse(fx.appJsonRaw)
    delete app.tabBar
    fx.appJsonRaw = JSON.stringify(app)
    expectError(checkFacts(collectFacts(fx)).errors, '缺少 tabBar.list')
  })

  test('页面 js 非 Page({...}) 直写形式 → 跳过死入口检查', () => {
    const fx = golden()
    fx.pageTexts.queue.js = `const opts = {}; Page(opts)`
    const { errors, notes } = checkFacts(collectFacts(fx))
    assert.equal(errors.filter((e) => e.includes('queue.js')).length, 0)
    assert.ok(notes.some((n) => n.includes('非 Page')))
  })
})
