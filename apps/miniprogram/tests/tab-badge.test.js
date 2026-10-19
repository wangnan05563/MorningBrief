/**
 * 底部导航角标单元测试（T02510 / FR-UX-601 需求项②的小程序侧）
 *
 * 锁定四件事（都是本单里最容易写错、运行时又看不出来的点）：
 *  1. 计数口径 = 「当前条之后还剩几条」，队列空 → 撤角标而不是挂 "0"；
 *  2. 非 tabBar 页面调用 wx.setTabBarBadge 会 fail → 先判定当前栈顶，不是 tab 页就跳过，
 *     等下一个 tab 页 onShow 再补挂（不能在这里硬调，也不能因此报错）；
 *  3. 文案去重：同一数字不重复下发（onShow + 队列变更两个触发源会重叠）；
 *     下发 fail 时必须清缓存，否则重试被去重短路、角标永远挂不上；
 *  4. 折叠：>99 显示 "99+"，且不超过微信建议的 4 字符。
 *
 * 计数来源用构造参数注入，不把 services/audio（会碰 wx.createInnerAudioContext）
 * 拉进测试环境。
 *
 * 运行：node --test apps/miniprogram/tests/tab-badge.test.js
 */
const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');

const {
  HISTORY_TAB_INDEX,
  TAB_ROUTES,
  BADGE_FOLD_AT,
  pendingCountOf,
  badgeText,
  currentTabIndex,
  createTabBadge,
} = require('../utils/tab-badge');

let calls;
let failNextCall;

beforeEach(() => {
  calls = [];
  failNextCall = false;
  global.wx = {
    setTabBarBadge: (o) => {
      calls.push({ kind: 'set', index: o.index, text: o.text });
      if (failNextCall && o.fail) o.fail({ errMsg: 'setTabBarBadge:fail not TabBar page' });
    },
    removeTabBarBadge: (o) => {
      calls.push({ kind: 'remove', index: o.index });
      if (failNextCall && o.fail) o.fail({ errMsg: 'removeTabBarBadge:fail not TabBar page' });
    },
  };
});

afterEach(() => {
  delete global.wx;
  delete global.getCurrentPages;
});

/** 把栈顶设成某个路由（null 表示页面栈为空） */
function stackTop(route) {
  global.getCurrentPages = () => (route === null ? [] : [{ route }]);
}

describe('计数口径', () => {
  test('当前条之后的都算待播；当前条本身不算', () => {
    assert.equal(pendingCountOf(['a', 'b', 'c', 'd'], 1), 2);
  });

  test('index = -1（队列里有内容但没定位到当前条）时整队算待播', () => {
    assert.equal(pendingCountOf(['a', 'b'], -1), 2);
  });

  test('播到末条 → 0（不是负数）', () => {
    assert.equal(pendingCountOf(['a', 'b'], 1), 0);
    assert.equal(pendingCountOf(['a'], 5), 0);
  });

  test('空队列 / 非数组 → 0', () => {
    assert.equal(pendingCountOf([], 0), 0);
    assert.equal(pendingCountOf(null, 0), 0);
    assert.equal(pendingCountOf(undefined, undefined), 0);
  });
});

describe('角标文案', () => {
  test('0 表示不显示（空串，由调用方撤角标）', () => {
    assert.equal(badgeText(0), '');
    assert.equal(badgeText(-3), '');
  });

  test('99 与 99+ 的边界：第 100 条才折叠', () => {
    assert.equal(badgeText(BADGE_FOLD_AT), '99');
    assert.equal(badgeText(BADGE_FOLD_AT + 1), '99+');
    assert.equal(badgeText(5000), '99+');
    assert.ok(badgeText(5000).length <= 4, '微信建议角标文案不超过 4 个字符');
  });
});

describe('tab 页判定', () => {
  test('栈顶是 tab 页 → 返回其下标', () => {
    stackTop('pages/history/history');
    assert.equal(currentTabIndex(), HISTORY_TAB_INDEX);
  });

  test('栈顶是非 tab 页（如队列页/详情页）→ -1', () => {
    stackTop('pages/queue/queue');
    assert.equal(currentTabIndex(), -1);
    stackTop('pages/detail/detail');
    assert.equal(currentTabIndex(), -1);
  });

  test('getCurrentPages 不可用或页面栈为空 → -1，不抛', () => {
    delete global.getCurrentPages;
    assert.equal(currentTabIndex(), -1);
    stackTop(null);
    assert.equal(currentTabIndex(), -1);
  });

  test('兼容 $page.route 形态的栈顶页', () => {
    global.getCurrentPages = () => [{$page: {route: 'pages/index/index'}}];
    assert.equal(currentTabIndex(), 0);
  });

  test('TAB_ROUTES 覆盖 app.json 的三个 tab（顺序由门禁校验，这里校验齐全）', () => {
    assert.deepEqual(Object.keys(TAB_ROUTES).sort(), [
      'pages/history/history',
      'pages/index/index',
      'pages/profile/profile',
    ]);
  });
});

describe('刷新器行为', () => {
  /** @returns {{badge: object, setQueue: Function}} */
  function make(queue, index) {
    let q = queue;
    let i = index;
    const badge = createTabBadge({
      getQueue: () => q,
      getQueueIndex: () => i,
    });
    return { badge, set: (nq, ni) => { q = nq; i = ni; } };
  }

  test('不在 tab 页：跳过、不碰 wx', () => {
    stackTop('pages/detail/detail');
    const { badge } = make(['a', 'b'], 0);
    assert.deepEqual(badge.refresh(), { applied: false, reason: 'not-tab-page' });
    assert.equal(calls.length, 0);
  });

  test('待播 2 条 → 在「历史」tab 挂 "2"', () => {
    stackTop('pages/index/index');
    const { badge } = make(['a', 'b', 'c'], 0);
    const r = badge.refresh();
    assert.equal(r.applied, true);
    assert.equal(r.text, '2');
    assert.deepEqual(calls, [{ kind: 'set', index: HISTORY_TAB_INDEX, text: '2' }]);
  });

  test('队列为空 → 撤角标（而不是挂 "0"）', () => {
    stackTop('pages/index/index');
    const { badge } = make([], -1);
    badge.refresh();
    assert.deepEqual(calls, [{ kind: 'remove', index: HISTORY_TAB_INDEX }]);
  });

  test('同一文案不重复下发（onShow 与队列变更两个触发源会重叠）', () => {
    stackTop('pages/index/index');
    const { badge } = make(['a', 'b'], 0);
    assert.equal(badge.refresh().applied, true);
    const again = badge.refresh();
    assert.equal(again.applied, false);
    assert.equal(again.reason, 'unchanged');
    assert.equal(calls.length, 1);
  });

  test('数字变化 → 重新下发；降到 0 时改为撤角标', () => {
    stackTop('pages/index/index');
    const { badge, set } = make(['a', 'b'], 0);
    badge.refresh();
    set(['a', 'b', 'c'], 0);
    const up = badge.refresh();
    assert.equal(up.text, '2');
    set(['a'], 0);
    const down = badge.refresh();
    assert.equal(down.applied, true);
    assert.equal(down.count, 0);
    assert.deepEqual(calls.map((c) => `${c.kind}:${c.text || ''}`), ['set:1', 'set:2', 'remove:']);
  });

  test('下发 fail → 清去重缓存，下次 onShow 会重试（否则角标永远挂不上）', () => {
    stackTop('pages/index/index');
    const { badge } = make(['a', 'b'], 0);
    failNextCall = true;
    assert.equal(badge.refresh().applied, true); // 同步返回「已下发」，失败在回调里
    failNextCall = false;
    const retry = badge.refresh();
    assert.equal(retry.applied, true, '上次失败后不应被 unchanged 短路');
    assert.equal(calls.length, 2);
  });

  test('取数抛错 → 不挂来路不明的数字，也不让页面崩', () => {
    stackTop('pages/index/index');
    const badge = createTabBadge({
      getQueue: () => {
        throw new Error('storage broken');
      },
      getQueueIndex: () => 0,
    });
    const warn = console.warn;
    console.warn = () => {};
    const r = badge.refresh();
    console.warn = warn;
    assert.deepEqual(r, { applied: false, reason: 'read-failed' });
    assert.equal(calls.length, 0);
  });

  test('reset() 后同一数字会重新下发（供页面重建场景）', () => {
    stackTop('pages/index/index');
    const { badge } = make(['a', 'b'], 0);
    badge.refresh();
    badge.reset();
    assert.equal(badge.refresh().applied, true);
    assert.equal(calls.length, 2);
  });
});
