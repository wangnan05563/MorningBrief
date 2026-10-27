/**
 * 「我的」第二层入口收敛回归（T02735 / J20）
 *
 * T02540 已把内嵌列表改成「一张入口卡」，但留下两个运行期缺陷，静态门禁看不出来：
 *  1. secondEntry 只在用户点第二层页签时才填 —— 首屏默认选中「最近」却渲染成一张空白可点卡片，
 *     点了也没反应（goSecondPage 拿到空 url 直接 return）；
 *  2. 跳转目标同时存在 secondPage 与 secondEntry.url 两份状态，改一处忘另一处就是「点不动」。
 *
 * 这里不读源码猜行为：真的把 pages/profile/profile.js 加载起来（Page() 用桩接住），
 * 在 Node 里跑 onLoad / onSecondTab / goSecondPage，断言 wx.navigateTo 实际拿到的 url。
 *
 * 运行：node --test apps/miniprogram/tests/profile-second-entry.test.js
 */
const { test, describe, before, beforeEach } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const MP_ROOT = path.resolve(__dirname, '..');
const PAGE_REL = 'pages/profile/profile.js';
const APP_JSON = JSON.parse(fs.readFileSync(path.join(MP_ROOT, 'app.json'), 'utf8'));
const WXML = fs.readFileSync(path.join(MP_ROOT, 'pages/profile/profile.wxml'), 'utf8');

const normPage = (p) => String(p || '').replace(/^\/+/, '').replace(/\/+$/, '');

let pageConfig;

/** 第二层页签的 data-tab（只取 tab-bar-sub 到 second-panel 之间） */
function secondTabKeys() {
  const start = WXML.indexOf('tab-bar-sub');
  const end = WXML.indexOf('second-panel');
  assert.ok(start >= 0 && end > start, 'profile.wxml 里定位不到第二层页签区域');
  return [...WXML.slice(start, end).matchAll(/data-tab="([A-Za-z0-9_]+)"/g)].map((m) => m[1]);
}

before(() => {
  const prev = { Page: global.Page, Component: global.Component, getApp: global.getApp, wx: global.wx };
  let captured;
  const noop = () => {};
  global.wx = {
    getStorageSync: () => '',
    setStorageSync: noop,
    removeStorageSync: noop,
    getSystemInfoSync: () => ({ platform: 'devtools', windowWidth: 375 }),
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    createInnerAudioContext: () => ({ onError: noop, onEnded: noop, destroy: noop }),
    showToast: noop,
    hideToast: noop,
    showLoading: noop,
    hideLoading: noop,
    showModal: noop,
    navigateTo: noop,
    reLaunch: noop,
    setTabBarBadge: noop,
    removeTabBarBadge: noop,
    getUpdateManager: () => ({ onCheckForUpdate: noop, onUpdateReady: noop, onUpdateFailed: noop, applyUpdate: noop }),
  };
  global.getApp = () => ({ globalData: {} });
  global.Page = (o) => { captured = o; };
  global.Component = (o) => o.methods || o;
  try {
    require(path.join(MP_ROOT, PAGE_REL));
  } finally {
    global.Page = prev.Page;
    global.Component = prev.Component;
    global.getApp = prev.getApp;
    global.wx = prev.wx;
  }
  assert.ok(captured, `${PAGE_REL} 没把配置交给 Page()，桩没接住`);
  pageConfig = captured;
});

let calls;
let navigateFail;

beforeEach(() => {
  calls = [];
  navigateFail = false;
  global.wx = Object.assign({}, global.wx, {
    navigateTo: (o) => {
      calls.push({ kind: 'navigateTo', url: o.url });
      if (navigateFail && o.fail) o.fail({ errMsg: 'navigateTo:fail' });
    },
    reLaunch: (o) => { calls.push({ kind: 'reLaunch', url: o.url }); },
  });
});

/** 造一个独立的页面实例：data 深拷贝，setData 合成，方法原样 */
function newPage() {
  const inst = Object.assign({}, pageConfig, {
    data: JSON.parse(JSON.stringify(pageConfig.data)),
    setData(obj) { Object.assign(this.data, obj); },
  });
  return inst;
}

function tapSecond(page, tab) {
  page.onSecondTab({ currentTarget: { dataset: { tab } } });
}

describe('首屏就有入口（空白可点卡片不得复现）', () => {
  test('onLoad 之后 secondEntry 已填好，且指向「最近」整页', () => {
    const p = newPage();
    p.onLoad();
    assert.ok(p.data.secondEntry, 'onLoad 后 secondEntry 仍为 null：首屏是一张空白可点卡片');
    assert.ok(p.data.secondEntry.text && p.data.secondEntry.text.trim(), '入口卡没有文案');
    assert.equal(normPage(p.data.secondEntry.url), 'pages/recent/recent');
  });

  test('首屏直接点入口能跳到「最近」整页', () => {
    const p = newPage();
    p.onLoad();
    p.goSecondPage();
    assert.deepEqual(calls, [{ kind: 'navigateTo', url: '/pages/recent/recent' }]);
  });

  test('navigateTo 失败时用同一 url 降级 reLaunch（不落到空地址）', () => {
    const p = newPage();
    p.onLoad();
    navigateFail = true;
    p.goSecondPage();
    assert.deepEqual(calls.map((c) => c.kind), ['navigateTo', 'reLaunch']);
    assert.equal(calls[1].url, calls[0].url);
    assert.equal(normPage(calls[1].url), 'pages/recent/recent');
  });
});

describe('五枚页签各自落到自己的整页', () => {
  const tabKeys = secondTabKeys();

  test('wxml 里的第二层页签正好五项（多/少都说明口径变了）', () => {
    assert.deepEqual(
      [...tabKeys].sort(),
      ['channels', 'downloads', 'favorites', 'preferred', 'recent'],
    );
  });

  for (const tab of ['recent', 'favorites', 'channels', 'downloads', 'preferred']) {
    test(`点「${tab}」→ 入口指向 ${tab} 自己的注册页面，且 goSecondPage 跳过去`, () => {
      const p = newPage();
      p.onLoad();
      tapSecond(p, tab);
      assert.ok(p.data.secondEntry, `${tab} 没有入口（空白卡片）`);
      const target = normPage(p.data.secondEntry.url);
      assert.ok(
        APP_JSON.pages.map(normPage).includes(target),
        `${tab} 的入口指向未注册页面 ${target}：navigateTo 必然失败`,
      );
      const stem = tab.endsWith('s') ? tab.slice(0, -1) : tab;
      assert.ok(target.includes(stem), `${tab} 的入口指向了 ${target}（接错对象）`);
      calls = [];
      p.goSecondPage();
      assert.deepEqual(calls, [{ kind: 'navigateTo', url: '/'.concat(target) }]);
    });
  }
});

describe('状态单源与未知页签', () => {
  test('data 里不再有 secondPage（跳转目标只有 secondEntry.url 一处）', () => {
    assert.ok(!('secondPage' in pageConfig.data), 'secondPage 又回到了 data：跳转目标成了两份状态');
  });

  test('未知页签不保留上一页签的入口（宁可空也不跳错页）', () => {
    const p = newPage();
    p.onLoad();
    tapSecond(p, 'favorites');
    tapSecond(p, 'no-such-tab');
    assert.equal(p.data.secondEntry, null);
    p.goSecondPage();
    assert.deepEqual(calls, []);
  });

  test('重复点当前页签不重算、不清空入口', () => {
    const p = newPage();
    p.onLoad();
    const before = p.data.secondEntry;
    tapSecond(p, p.data.secondTab);
    assert.deepEqual(p.data.secondEntry, before);
  });
});
