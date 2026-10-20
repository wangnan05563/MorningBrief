/**
 * 使用记录开关单元测试（T02513 / J99）
 *
 * 隐私政策第七条第 4 条从此有了实现，所以这条链路必须被测：
 *  1. 老用户 storage 里没有 usageTracking 字段 → 默认记录（不能因为字段缺失就静默关掉统计）；
 *  2. usageTracking:false → track / trackPageView / trackEvent 三个入口全部不出事件
 *     （三个函数共用 track()，若哪天有人给某个入口开了旁路，这里会红）；
 *  3. setTrackingEnabled 是即时生效的覆盖通道（设置页拨开关的当下就生效，不等冷启动）；
 *  4. 生效期间不再逐条读 storage（事件量大的页面上每条 getStorageSync 是白付的成本）——
 *     这一条同时锁住「缓存语义」，避免有人把 isEnabled() 改成每次直读。
 *
 * 运行：node --test apps/miniprogram/tests/usage-tracking.test.js
 */
const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');

let store;
let storageReads;
let logged;
let realWarn;
let tracker;

function loadTracker() {
  // 缓存字段 _enabled 在模块作用域里，跨用例必须重新 require 才能回到初始态
  const p = require.resolve('../utils/tracker');
  delete require.cache[p];
  delete require.cache[require.resolve('../services/constants')];
  return require(p);
}

beforeEach(() => {
  store = {};
  storageReads = 0;
  logged = [];
  global.wx = {
    getStorageSync(key) {
      storageReads += 1;
      return store[key];
    },
  };
  realWarn = console.warn;
  console.warn = (...args) => logged.push(args);
  tracker = loadTracker();
});

afterEach(() => {
  console.warn = realWarn;
  delete global.wx;
});

describe('使用记录开关', () => {
  test('缺省（老用户没有该字段）照常记录', () => {
    store.news_settings = { defaultRate: 1.0 };
    tracker.trackEvent('player', 'play');
    assert.equal(logged.length, 1);
    assert.match(logged[0][0], /\[tracker\]/);
  });

  test('关闭后三个入口都不出事件', () => {
    store.news_settings = { usageTracking: false };
    tracker.track('a');
    tracker.trackPageView('pages/index/index');
    tracker.trackEvent('player', 'pause');
    assert.equal(logged.length, 0, `关闭后仍产生了 ${logged.length} 条记录`);
  });

  test('setTrackingEnabled 即时生效，优先于 storage 里的值', () => {
    store.news_settings = { usageTracking: true };
    tracker.setTrackingEnabled(false);
    assert.equal(tracker.isEnabled(), false);
    tracker.trackEvent('settings', 'change_rate');
    assert.equal(logged.length, 0);

    tracker.setTrackingEnabled(true);
    tracker.trackEvent('settings', 'change_rate');
    assert.equal(logged.length, 1);
  });

  test('判定结果会缓存，不会每条事件都读 storage', () => {
    store.news_settings = { usageTracking: true };
    for (let i = 0; i < 20; i += 1) tracker.trackEvent('player', 'seek');
    assert.equal(logged.length, 20);
    assert.equal(storageReads, 1, `storage 被读了 ${storageReads} 次，缓存语义被破坏`);
  });

  test('storage 抛异常时按「记录」兜底（不能因为读失败就静默丢统计）', () => {
    global.wx.getStorageSync = () => {
      throw new Error('storage unavailable');
    };
    tracker.setTrackingEnabled(true);
    assert.equal(tracker.isEnabled(), true);
  });
});
