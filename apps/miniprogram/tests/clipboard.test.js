/**
 * utils/clipboard.js 单元测试
 *
 * 使用 Node.js 内置 node:test 运行（无需额外依赖）：
 *   node --test miniprogram/tests/clipboard.test.js
 *
 * 测试策略：mock 全局 wx 对象，验证 copyText/copySourceUrl 的分支逻辑与调用契约，
 * 不依赖微信运行时，可在 CI 中直接执行。
 *
 * copyText 三阶段重试逻辑：
 * 1. 先直接 setClipboardData（已授权场景一步成功）
 * 2. 失败后 ensurePrivacyAuthorized（触发隐私弹窗）+ 延迟 200ms 重试
 * 3. 仍失败则延迟 500ms 最后重试
 */
const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');

// 记录 wx API 调用，供断言使用
let wxCalls;
// 'success' = setClipboardData 直接成功
// 'fail-then-success' = 首次 fail，第二次（授权后重试）success
// 'always-fail' = 始终 fail
let clipboardBehavior;
// 'authorized' = requirePrivacyAuthorize success
// 'rejected' = requirePrivacyAuthorize fail
let privacyBehavior;

const originalWx = global.wx;

function setupWxMock() {
  wxCalls = {
    setClipboardData: [],
    showModal: [],
    showToast: [],
    navigateTo: [],
    requirePrivacyAuthorize: [],
  };
  clipboardBehavior = 'success';
  privacyBehavior = 'authorized';

  global.wx = {
    setClipboardData({ data, success, fail }) {
      wxCalls.setClipboardData.push(data);
      // fail-then-success: 第 2 次调用开始返回 success
      if (clipboardBehavior === 'success') {
        success && success();
      } else if (clipboardBehavior === 'fail-then-success') {
        if (wxCalls.setClipboardData.length >= 2) {
          success && success();
        } else {
          fail && fail({ errCode: 104, errMsg: 'setClipboardData:fail privacy' });
        }
      } else {
        // always-fail
        fail && fail({ errCode: 104, errMsg: 'setClipboardData:fail privacy' });
      }
    },
    requirePrivacyAuthorize(opts) {
      wxCalls.requirePrivacyAuthorize.push(opts);
      if (privacyBehavior === 'authorized') {
        opts.success && opts.success();
      } else {
        opts.fail && opts.fail({ errMsg: 'requirePrivacyAuthorize:fail' });
      }
    },
    showModal(opts) {
      wxCalls.showModal.push(opts);
    },
    showToast(opts) {
      wxCalls.showToast.push(opts);
    },
    navigateTo(opts) {
      wxCalls.navigateTo.push(opts);
    },
  };
}

function restoreWx() {
  global.wx = originalWx;
}

// 清除 require 缓存，确保每个用例拿到干净的模块
function loadFreshClipboard() {
  delete require.cache[require.resolve('../utils/clipboard')];
  return require('../utils/clipboard');
}

describe('copyText', () => {
  beforeEach(setupWxMock);
  afterEach(restoreWx);

  test('已授权场景：直接 setClipboardData 成功，不调 requirePrivacyAuthorize', async () => {
    clipboardBehavior = 'success';
    const { copyText } = loadFreshClipboard();
    const ok = await copyText('https://example.com/a');
    assert.strictEqual(ok, true);
    assert.deepStrictEqual(wxCalls.setClipboardData, ['https://example.com/a']);
    // 已授权场景不应触发隐私授权流程
    assert.strictEqual(wxCalls.requirePrivacyAuthorize.length, 0);
  });

  test('首次失败 + 隐私授权成功 + 重试成功 → 返回 true', async () => {
    clipboardBehavior = 'fail-then-success';
    privacyBehavior = 'authorized';
    const { copyText } = loadFreshClipboard();
    const ok = await copyText('https://example.com/b');
    assert.strictEqual(ok, true);
    // 应调用 2 次 setClipboardData（首次失败 + 重试成功）
    assert.strictEqual(wxCalls.setClipboardData.length, 2);
    // 首次失败后应调 requirePrivacyAuthorize
    assert.strictEqual(wxCalls.requirePrivacyAuthorize.length, 1);
  });

  test('始终失败 + 隐私授权被拒 → 返回 false（3 次重试）', async () => {
    clipboardBehavior = 'always-fail';
    privacyBehavior = 'rejected';
    const { copyText } = loadFreshClipboard();
    const ok = await copyText('https://example.com/c');
    assert.strictEqual(ok, false);
    // 三阶段重试：首次 + 授权后 200ms + 最后 500ms
    assert.strictEqual(wxCalls.setClipboardData.length, 3);
    assert.strictEqual(wxCalls.requirePrivacyAuthorize.length, 1);
  });

  test('始终失败 + 隐私授权成功 → 返回 false（授权后仍复制失败）', async () => {
    clipboardBehavior = 'always-fail';
    privacyBehavior = 'authorized';
    const { copyText } = loadFreshClipboard();
    const ok = await copyText('https://example.com/d');
    assert.strictEqual(ok, false);
    assert.strictEqual(wxCalls.setClipboardData.length, 3);
    assert.strictEqual(wxCalls.requirePrivacyAuthorize.length, 1);
  });
});

describe('copySourceUrl', () => {
  beforeEach(setupWxMock);
  afterEach(restoreWx);

  test('复制成功 → 弹 modal 引导用户去浏览器打开，不跳转 fallback 页', async () => {
    clipboardBehavior = 'success';
    const { copySourceUrl } = loadFreshClipboard();

    const result = await copySourceUrl('https://news.example.com/article/1');

    assert.strictEqual(result, true);
    assert.strictEqual(wxCalls.showModal.length, 1);
    assert.strictEqual(wxCalls.showModal[0].title, '链接已复制');
    assert.ok(wxCalls.showModal[0].content.includes('浏览器'));
    // 成功路径不应跳转 fallback 页
    assert.strictEqual(wxCalls.navigateTo.length, 0);
  });

  test('复制失败 → 跳转 webview fallback 页并带上编码后的 url 与 fallback=1', async () => {
    clipboardBehavior = 'always-fail';
    privacyBehavior = 'rejected';
    const { copySourceUrl } = loadFreshClipboard();

    const url = 'https://news.example.com/article/中文?t=1';
    const result = await copySourceUrl(url);

    assert.strictEqual(result, false);
    // 失败路径不应弹 modal（避免误导用户以为复制成功）
    assert.strictEqual(wxCalls.showModal.length, 0);
    // 应跳转 fallback 页，url 已 encodeURIComponent 编码
    assert.strictEqual(wxCalls.navigateTo.length, 1);
    const navUrl = wxCalls.navigateTo[0].url;
    assert.ok(navUrl.includes('fallback=1'), '跳转地址须包含 fallback=1 标记');
    assert.ok(navUrl.includes(encodeURIComponent(url)), '跳转地址须包含编码后的原始 url');
    assert.ok(navUrl.startsWith('/pages/webview/webview?url='), '跳转到 webview 页');
  });

  test('含特殊字符的链接也能正确编码跳转', async () => {
    clipboardBehavior = 'always-fail';
    privacyBehavior = 'rejected';
    const { copySourceUrl } = loadFreshClipboard();

    const url = 'https://example.com/p?q=a&b=c#frag';
    await copySourceUrl(url);

    const navUrl = wxCalls.navigateTo[0].url;
    // 编码后原始 url 中的 & 已转为 %26，不会与路由参数分隔符 & 混淆
    const match = navUrl.match(/url=([^&]+)&fallback=1$/);
    assert.ok(match, '路由应包含 url 与 fallback=1 参数且 url 中无裸 &');
    assert.strictEqual(decodeURIComponent(match[1]), url);
  });
});
