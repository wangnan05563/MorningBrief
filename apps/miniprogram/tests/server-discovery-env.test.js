/**
 * utils/server-discovery.js —— 运行版本判定与「配置后端地址」弹窗门控（T00571）单元测试
 *
 * 背景：正式版启动不应弹出「配置后端地址」引导，只有开发模式才允许。
 * 原实现用未公开的 `__wxConfig.envVersion` 单一判定 + 反推式弹窗条件，
 * 版本信息取不到时会默认放行弹窗。本测试锁住改进后的口径：
 *   1. getEnvVersion —— 官方 API 优先、__wxConfig 回退、都取不到返回 ''
 *   2. isDevelopMode —— 只有 develop / 开发者工具为 true；trial / release / 未知 为 false
 *   3. discoverServer —— 非开发模式零打扰：直接返回预置兜底地址，不探测、不弹窗
 *
 * 运行：node --test miniprogram/tests/server-discovery-env.test.js
 */
const { test, describe, afterEach } = require('node:test');
const assert = require('node:assert');

const PROD = 'https://win-20260220ins.tailbca47.ts.net/news/api/v1';

/** 构造最小 wx stub；envVersion / platform 决定运行环境 */
function installWx({ envVersion, platform, accountInfoThrows, modalLog, requestLog }) {
  const wx = {
    request: (opts) => { if (requestLog) requestLog.push(opts.url); if (opts.fail) opts.fail({ errMsg: 'request:fail' }); },
    showModal: (opts) => { if (modalLog) modalLog.push(opts); if (opts.success) opts.success({ confirm: false }); },
    showToast: () => {},
    getStorageSync: () => '',
    setStorage: () => {},
    removeStorageSync: () => {},
    getLocalIPAddress: (opts) => { if (opts && opts.fail) opts.fail({ errMsg: 'fail' }); },
    getDeviceInfo: () => ({ platform: platform || 'ios' }),
    getSystemInfoSync: () => ({ platform: platform || 'ios' }),
  };
  if (envVersion) {
    wx.getAccountInfoSync = accountInfoThrows
      ? () => { throw new Error('getAccountInfoSync not supported'); }
      : () => ({ miniProgram: { envVersion } });
  }
  global.wx = wx;
  // __wxConfig 仅在显式需要回退时注入
  if (envVersion === '__wxconfig__') {
    delete wx.getAccountInfoSync;
    global.__wxConfig = { envVersion: 'develop' };
  } else if (envVersion === '__wxconfig_release__') {
    delete wx.getAccountInfoSync;
    global.__wxConfig = { envVersion: 'release' };
  } else {
    delete global.__wxConfig;
  }
  return wx;
}

afterEach(() => {
  delete global.__wxConfig;
});

describe('server-discovery.getEnvVersion（T00571 版本判定）', () => {
  test('优先取官方 API wx.getAccountInfoSync().miniProgram.envVersion', () => {
    installWx({ envVersion: 'develop' });
    const sd = require('../utils/server-discovery');
    assert.strictEqual(sd.getEnvVersion(), 'develop');
  });

  test('官方 API 不可用时回退 __wxConfig.envVersion', () => {
    installWx({ envVersion: '__wxconfig_release__' });
    const sd = require('../utils/server-discovery');
    assert.strictEqual(sd.getEnvVersion(), 'release');
    assert.strictEqual(sd.isRelease(), true);
  });

  test('官方 API 抛错时回退 __wxConfig.envVersion', () => {
    installWx({ envVersion: 'release', accountInfoThrows: true });
    global.__wxConfig = { envVersion: 'trial' };
    const sd = require('../utils/server-discovery');
    assert.strictEqual(sd.getEnvVersion(), 'trial');
    assert.strictEqual(sd.isRelease(), false);
  });

  test('两处都取不到 → 空串（未知，按最保守策略处理）', () => {
    installWx({ envVersion: '' });
    const sd = require('../utils/server-discovery');
    assert.strictEqual(sd.getEnvVersion(), '');
  });
});

describe('server-discovery.isDevelopMode（T00571 弹窗门控口径）', () => {
  test('开发版 develop → true', () => {
    installWx({ envVersion: 'develop' });
    assert.strictEqual(require('../utils/server-discovery').isDevelopMode(), true);
  });

  test('开发者工具（platform=devtools）→ true', () => {
    installWx({ envVersion: 'trial', platform: 'devtools' });
    assert.strictEqual(require('../utils/server-discovery').isDevelopMode(), true);
  });

  test('体验版 trial → false（不允许弹窗）', () => {
    installWx({ envVersion: 'trial' });
    assert.strictEqual(require('../utils/server-discovery').isDevelopMode(), false);
  });

  test('正式版 release → false（不允许弹窗）', () => {
    installWx({ envVersion: 'release' });
    assert.strictEqual(require('../utils/server-discovery').isDevelopMode(), false);
  });

  test('版本信息未知 → false（安全侧默认：不弹窗）', () => {
    installWx({ envVersion: '' });
    const sd = require('../utils/server-discovery');
    assert.strictEqual(sd.getEnvVersion(), '');
    assert.strictEqual(sd.isDevelopMode(), false);
  });
});

describe('server-discovery.discoverServer（T00571 非开发模式零打扰）', () => {
  test('正式版：直接返回预置兜底地址，不发起任何探测请求、不弹窗', async () => {
    const modalLog = [];
    const requestLog = [];
    installWx({ envVersion: 'release', modalLog, requestLog });
    const sd = require('../utils/server-discovery');
    const result = await sd.discoverServer();
    assert.strictEqual(result, PROD);
    assert.strictEqual(modalLog.length, 0);
    assert.strictEqual(requestLog.length, 0);
  });

  test('体验版：同样零打扰，直接走兜底地址', async () => {
    const modalLog = [];
    const requestLog = [];
    installWx({ envVersion: 'trial', modalLog, requestLog });
    const sd = require('../utils/server-discovery');
    assert.strictEqual(await sd.discoverServer(), PROD);
    assert.strictEqual(modalLog.length, 0);
    assert.strictEqual(requestLog.length, 0);
  });

  test('版本信息未知：默认走兜底地址，不弹窗', async () => {
    const modalLog = [];
    installWx({ envVersion: '', modalLog });
    const sd = require('../utils/server-discovery');
    assert.strictEqual(await sd.discoverServer(), PROD);
    assert.strictEqual(modalLog.length, 0);
  });
});
