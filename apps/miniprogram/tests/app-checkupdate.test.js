/**
 * app.js —— checkUpdate 版本判定（T00575）单元测试
 *
 * 背景：原实现 `typeof __wxConfig !== 'undefined' && __wxConfig.envVersion !== 'release'` 依赖未公开字段，
 * 字段缺失时 `undefined !== 'release'` 成立 → 正式版更新检查被静默跳过；字段整体缺失时又反向放行。
 * 改进后改用 `utils/server-discovery.getEnvVersion()`，并明确「非 release 才跳过；release / 未知都注册」。
 *
 * 本测试用最小 stub 加载 app.js（捕获 App({...}) 注册的对象），直接调 checkUpdate 断言真实分支行为。
 *
 * 运行：node --test miniprogram/tests/app-checkupdate.test.js
 */
const { test, describe, afterEach } = require('node:test');
const assert = require('node:assert');

/** 记录每次 getUpdateManager 调用，用于断言是否注册了更新管理器 */
let updateManagerCalls = 0;

/** 装最小 wx / App stub；envVersion 决定 getEnvVersion() 的返回值 */
function bootApp({ envVersion, platform }) {
  updateManagerCalls = 0;
  const noop = () => {};
  global.wx = {
    getAccountInfoSync: envVersion === null
      ? undefined
      : () => ({ miniProgram: { envVersion } }),
    getDeviceInfo: () => ({ platform: platform || 'ios' }),
    getSystemInfoSync: () => ({ platform: platform || 'ios' }),
    getStorageSync: () => '',
    setStorage: noop,
    removeStorageSync: noop,
    getUpdateManager: () => {
      updateManagerCalls += 1;
      return { onCheckForUpdate: noop, onUpdateReady: noop, onUpdateFailed: noop };
    },
    request: noop,
    onError: noop,
    getPrivacySetting: (opts) => { if (opts && opts.success) opts.success({ needAuthorization: false }); },
    onNeedPrivacyAuthorization: undefined,
    login: noop,
    getBackgroundAudioManager: () => ({}),
  };
  delete global.__wxConfig;
  let appInstance = null;
  global.App = (opts) => { appInstance = opts; };
  global.getApp = () => appInstance;
  delete require.cache[require.resolve('../app')];
  require('../app');
  return appInstance;
}

afterEach(() => {
  delete global.__wxConfig;
});

describe('app.checkUpdate 版本判定（T00575）', () => {
  test('正式版 release → 注册更新管理器', () => {
    bootApp({ envVersion: 'release' }).checkUpdate();
    assert.strictEqual(updateManagerCalls, 1);
  });

  test('开发版 develop → 跳过（不注册）', () => {
    bootApp({ envVersion: 'develop' }).checkUpdate();
    assert.strictEqual(updateManagerCalls, 0);
  });

  test('体验版 trial → 跳过（不注册）', () => {
    bootApp({ envVersion: 'trial' }).checkUpdate();
    assert.strictEqual(updateManagerCalls, 0);
  });

  test('版本未知（两处都取不到）→ 仍注册（宁可多查、不漏更新）', () => {
    // getAccountInfoSync 返回 undefined 且无 __wxConfig → getEnvVersion() === ''
    bootApp({ envVersion: undefined }).checkUpdate();
    assert.strictEqual(updateManagerCalls, 1);
  });

  test('官方 API 缺失但 __wxConfig.envVersion=release → 回退判定后注册', () => {
    const app = bootApp({ envVersion: null }); // 无 getAccountInfoSync
    global.__wxConfig = { envVersion: 'release' };
    app.checkUpdate();
    assert.strictEqual(updateManagerCalls, 1);
  });

  test('官方 API 缺失且 __wxConfig 存在但无 envVersion → 视为未知，仍注册（原实现会静默跳过）', () => {
    const app = bootApp({ envVersion: null });
    global.__wxConfig = {};
    app.checkUpdate();
    assert.strictEqual(updateManagerCalls, 1);
  });
});
