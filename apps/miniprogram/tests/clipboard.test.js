/**
 * utils/clipboard.js 单元测试（T00618 重写：手势安全的隐私授权流程）
 *
 * 运行：node --test apps/miniprogram/tests/clipboard.test.js
 *
 * 新契约（替代此前"延迟重试"策略——该策略的所有复制调用都脱离用户手势链，
 * 会被微信拒绝，表现为"复制失败"）：
 * 1. 先**同步尝试一次**复制（处于本次点击的手势链内）→ 成功即返回；
 * 2. 失败且属隐私原因（errCode 104 / api scope not declared）→ 登记"授权后动作"
 *    （app.registerPostPrivacyAction）并触发一次授权；用户点官方「同意并继续」时，
 *    该动作在**按钮的手势链内**执行 → 复制成功；
 * 3. 非隐私原因（系统异常）→ 直接失败，不弹授权（避免无意义弹窗）；
 * 4. 用户拒绝 → 动作作废（resolve false），返回失败，由调用方给可操作兜底。
 */
const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');

let wxCalls;
let clipboardBehavior;   // 'success' | 'privacy-fail-then-success' | 'system-fail' | 'privacy-always-fail'
let privacyBehavior;     // 'authorized' | 'rejected'
let appStub;

/** 模拟 app：登记授权后动作 + 在"官方同意按钮的手势链内"执行 */
function makeAppStub() {
  const app = {
    globalData: { privacyAuthorized: false },
    _actions: [],
    registerPostPrivacyAction(fn) {
      return new Promise((resolve) => app._actions.push({ fn, resolve }));
    },
    clearPostPrivacyActions() {
      app._actions.splice(0).forEach((a) => a.resolve(false));
    },
    /** 测试用：模拟用户在隐私弹窗点「同意并继续」——框架在该按钮手势链内执行动作 */
    runActionsInGesture() {
      app._actions.splice(0).forEach(({ fn, resolve }) => {
        Promise.resolve(fn()).then((ok) => resolve(!!ok));
      });
    },
  };
  return app;
}

function setupMock() {
  wxCalls = { setClipboardData: [], showModal: [], showToast: [], navigateTo: [], requirePrivacyAuthorize: [] };
  clipboardBehavior = 'success';
  privacyBehavior = 'authorized';
  appStub = makeAppStub();

  global.getApp = () => appStub;

  global.wx = {
    setClipboardData({ data, success, fail }) {
      wxCalls.setClipboardData.push(data);
      const n = wxCalls.setClipboardData.length;
      if (clipboardBehavior === 'success') return success && success();
      if (clipboardBehavior === 'privacy-fail-then-success') {
        // 第 1 次（点击时的同步尝试）失败；第 2 次（授权后动作）成功
        return n >= 2
          ? (success && success())
          : (fail && fail({ errCode: 104, errMsg: 'setClipboardData:fail privacy permission is not authorized' }));
      }
      if (clipboardBehavior === 'system-fail') {
        return fail && fail({ errCode: 5, errMsg: 'setClipboardData:fail 系统错误' });
      }
      return fail && fail({ errCode: 104, errMsg: 'setClipboardData:fail privacy' });
    },
    requirePrivacyAuthorize(opts) {
      wxCalls.requirePrivacyAuthorize.push(opts);
      if (privacyBehavior === 'authorized') {
        // 真实顺序：用户点官方同意按钮 → 手势链内执行动作 → 授权回调成功
        appStub.runActionsInGesture();
        opts.success && opts.success();
      } else {
        opts.fail && opts.fail({ errMsg: 'requirePrivacyAuthorize:fail' });
      }
    },
    showModal(opts) { wxCalls.showModal.push(opts); },
    showToast(opts) { wxCalls.showToast.push(opts); },
    navigateTo(opts) { wxCalls.navigateTo.push(opts); },
  };
}

function restoreMock() {
  delete global.wx;
  delete global.getApp;
}

function loadFreshClipboard() {
  delete require.cache[require.resolve('../utils/clipboard')];
  return require('../utils/clipboard');
}

describe('copyText', () => {
  beforeEach(setupMock);
  afterEach(restoreMock);

  test('一次点击同步复制成功：仅 1 次调用、不触发任何授权', async () => {
    const { copyText } = loadFreshClipboard();
    const ok = await copyText('107038953@qq.com');
    assert.strictEqual(ok, true);
    assert.deepStrictEqual(wxCalls.setClipboardData, ['107038953@qq.com']);
    assert.strictEqual(wxCalls.requirePrivacyAuthorize.length, 0);
  });

  test('隐私未授权：首次失败 → 授权后以「官方按钮手势链内」的第二次调用成功', async () => {
    clipboardBehavior = 'privacy-fail-then-success';
    const { copyText } = loadFreshClipboard();
    const ok = await copyText('107038953@qq.com');
    assert.strictEqual(ok, true);
    assert.strictEqual(wxCalls.setClipboardData.length, 2, '同步尝试 1 次 + 授权后动作 1 次');
    assert.strictEqual(wxCalls.requirePrivacyAuthorize.length, 1, '只弹一次隐私授权');
  });

  test('用户拒绝授权 → 返回 false，登记的动作被作废（不再复制）', async () => {
    clipboardBehavior = 'privacy-fail-then-success';
    privacyBehavior = 'rejected';
    const { copyText } = loadFreshClipboard();
    const ok = await copyText('107038953@qq.com');
    assert.strictEqual(ok, false);
    assert.strictEqual(wxCalls.setClipboardData.length, 1, '只发生点击时的同步尝试');
    assert.strictEqual(appStub._actions.length, 0, '动作已被清空');
  });

  test('非隐私原因失败（系统异常）→ 直接失败，不弹授权', async () => {
    clipboardBehavior = 'system-fail';
    const { copyText } = loadFreshClipboard();
    const ok = await copyText('x@y.com');
    assert.strictEqual(ok, false);
    assert.strictEqual(wxCalls.setClipboardData.length, 1);
    assert.strictEqual(wxCalls.requirePrivacyAuthorize.length, 0, '系统异常不应触发隐私弹窗');
  });

  test('授权后动作仍失败 → 返回 false（不做脱离手势链的重试）', async () => {
    clipboardBehavior = 'privacy-always-fail';
    const { copyText } = loadFreshClipboard();
    const ok = await copyText('x@y.com');
    assert.strictEqual(ok, false);
    assert.strictEqual(wxCalls.setClipboardData.length, 2, '同步尝试 + 授权后动作，各 1 次，无延迟重试');
    assert.strictEqual(wxCalls.requirePrivacyAuthorize.length, 1);
  });

  test('空文本 → 直接 false，不调用任何 API', async () => {
    const { copyText } = loadFreshClipboard();
    assert.strictEqual(await copyText(''), false);
    assert.strictEqual(wxCalls.setClipboardData.length, 0);
  });
});

describe('isPrivacyFailure（纯函数判定）', () => {
  beforeEach(setupMock);
  afterEach(restoreMock);

  test('errCode 104 判为隐私失败', () => {
    const { isPrivacyFailure } = loadFreshClipboard();
    assert.strictEqual(isPrivacyFailure({ errCode: 104, errMsg: 'x' }), true);
  });

  test('errMsg 含 scope is not declared 判为隐私失败（后台缺声明）', () => {
    const { isPrivacyFailure } = loadFreshClipboard();
    assert.strictEqual(
      isPrivacyFailure({ errCode: 5, errMsg: 'setClipboardData:fail api scope is not declared in the privacy agreement' }),
      true,
    );
  });

  test('其他错误不算隐私失败', () => {
    const { isPrivacyFailure } = loadFreshClipboard();
    assert.strictEqual(isPrivacyFailure({ errCode: 5, errMsg: '系统错误' }), false);
    assert.strictEqual(isPrivacyFailure(null), false);
  });
});

describe('copySourceUrl', () => {
  beforeEach(setupMock);
  afterEach(restoreMock);

  test('复制成功 → 弹 modal 引导用户去浏览器打开，不跳转 fallback 页', async () => {
    const { copySourceUrl } = loadFreshClipboard();
    const ok = await copySourceUrl('https://news.example.com/article/1');
    assert.strictEqual(ok, true);
    assert.strictEqual(wxCalls.showModal.length, 1);
    assert.strictEqual(wxCalls.showModal[0].title, '链接已复制');
    assert.ok(wxCalls.showModal[0].content.includes('浏览器'));
    assert.strictEqual(wxCalls.navigateTo.length, 0);
  });

  test('复制失败 → 跳转 webview fallback 页并带上编码后的 url 与 fallback=1', async () => {
    clipboardBehavior = 'privacy-always-fail';
    privacyBehavior = 'rejected';
    const { copySourceUrl } = loadFreshClipboard();
    const ok = await copySourceUrl('https://news.example.com/article/中文?t=1');
    assert.strictEqual(ok, false);
    assert.strictEqual(wxCalls.navigateTo.length, 1);
    assert.ok(wxCalls.navigateTo[0].url.includes('fallback=1'));
    assert.ok(wxCalls.navigateTo[0].url.includes(encodeURIComponent('中文')));
  });
});
