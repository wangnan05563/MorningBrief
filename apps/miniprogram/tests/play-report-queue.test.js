/**
 * 播放上报失败队列测试（T00637）
 *
 * 背景：小程序播放上报此前 `catch(() => {})` 静默丢弃 → 上报失败（网络抖动 / token 过期 /
 * 后端域名未加入 request 合法域名）时播放量永不增长，用户侧表现为"重新进入应用播放量还是 0"，
 * 且无任何日志可排查。本测试锁定新契约：**失败入队（同 episode 只留最新）→ 启动/回前台补发 → 成功出队**。
 *
 * 运行：node --test apps/miniprogram/tests/play-report-queue.test.js
 */
const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');

let storage;
let requestCalls;
let requestShouldFail;

function setupMocks() {
  storage = {};
  requestCalls = [];
  requestShouldFail = false;

  global.getApp = () => ({ globalData: { baseUrl: 'http://test.local', token: 'tk' } });
  global.wx = {
    getStorageSync: (k) => (k in storage ? storage[k] : ''),
    setStorageSync: (k, v) => { storage[k] = v; },
    removeStorageSync: (k) => { delete storage[k]; },
    request: (opts) => {
      requestCalls.push({ url: opts.url, data: opts.data });
      if (requestShouldFail) {
        opts.fail && opts.fail({ errMsg: 'request:fail mock' });
      } else {
        opts.success && opts.success({ statusCode: 200, data: { code: 0, data: null } });
      }
    },
    showToast: () => {},
    navigateTo: () => {},
  };
}

function restoreMocks() {
  delete global.wx;
  delete global.getApp;
}

function loadFreshApi() {
  delete require.cache[require.resolve('../services/api')];
  return require('../services/api');
}

describe('播放上报失败队列', () => {
  beforeEach(setupMocks);
  afterEach(restoreMocks);

  test('失败上报入队；同 episode 只保留最新一条', () => {
    const { queuePendingReport } = loadFreshApi();
    queuePendingReport({ episode_id: 7, position: 30, duration: 600, completed: false, listened_seconds: 30 });
    queuePendingReport({ episode_id: 7, position: 120, duration: 600, completed: false, listened_seconds: 90 });
    queuePendingReport({ episode_id: 8, position: 40, duration: 600, completed: false, listened_seconds: 40 });

    const list = storage.pending_play_reports;
    assert.strictEqual(list.length, 2, '同 episode 应覆盖而非堆积');
    const ep7 = list.find((x) => x.episode_id === 7);
    assert.strictEqual(ep7.position, 120, '应保留最新位置');
  });

  test('队列上限 50 条（防 storage 膨胀）', () => {
    const { queuePendingReport } = loadFreshApi();
    for (let i = 1; i <= 60; i += 1) {
      queuePendingReport({ episode_id: i, position: 30, duration: 600, completed: false, listened_seconds: 30 });
    }
    assert.strictEqual(storage.pending_play_reports.length, 50);
    // 保留的是最后 50 条（episode 11..60）
    assert.strictEqual(storage.pending_play_reports[0].episode_id, 11);
  });

  test('补发成功 → 队列清空并返回成功条数', async () => {
    const api = loadFreshApi();
    api.queuePendingReport({ episode_id: 7, position: 30, duration: 600, completed: false, listened_seconds: 30 });
    api.queuePendingReport({ episode_id: 8, position: 45, duration: 600, completed: false, listened_seconds: 45 });

    const ok = await api.flushPendingReports();
    assert.strictEqual(ok, 2);
    assert.deepStrictEqual(storage.pending_play_reports, []);
    assert.strictEqual(requestCalls.filter((c) => c.url.includes('/playlogs/progress')).length, 2);
  });

  test('补发仍失败 → 队列保留（下次启动再试，不丢数据）', async () => {
    const api = loadFreshApi();
    api.queuePendingReport({ episode_id: 7, position: 30, duration: 600, completed: false, listened_seconds: 30 });
    requestShouldFail = true;

    const ok = await api.flushPendingReports();
    assert.strictEqual(ok, 0);
    assert.strictEqual(storage.pending_play_reports.length, 1, '失败应保留队列');
  });

  test('空队列补发为无操作', async () => {
    const api = loadFreshApi();
    assert.strictEqual(await api.flushPendingReports(), 0);
    assert.strictEqual(requestCalls.length, 0);
  });
});
