/**
 * services/audio.js —— HLS 启用判定与预检（T00572）单元测试
 *
 * 背景：微信客户端会把 BackgroundAudioManager 的每次加载失败渲染成客户端原生提示
 * 「该内容因网络或其他原因暂时无法播放」，小程序侧无法拦截。改进策略是
 * 「预检拦截 + 失败即熔断降级」，本测试锁住其中的两个关键判定：
 *   1. shouldUseHls —— HLS 启用条件（含开发者工具、会话熔断两个回退分支）
 *   2. probeHls    —— m3u8 预检结果解析（含失败开放语义）
 *
 * 运行：node --test miniprogram/tests/audio-hls-guard.test.js
 *
 * 测试策略：audio.js 是依赖 wx / getApp 的服务模块，顶层不便直接 require，
 * 故先用最小 wx stub 占位（仅需 getStorageSync / request），再取导出函数断言。
 */
const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');

// 最小 wx stub：audio.js 模块顶层只读取存储，其余为惰性调用
global.wx = Object.assign(global.wx || {}, {
  getStorageSync: () => ({}),
  request: () => {},
});

const audio = require('../services/audio');

describe('audio.shouldUseHls（T00572 HLS 启用条件）', () => {
  test('三条件齐备（有 hls_url + 非工具 + 未熔断）才启用 HLS', () => {
    assert.strictEqual(
      audio.shouldUseHls({ hasHls: true, devTools: false, disabled: false }), true);
  });

  test('无 hls_url 一律不用 HLS', () => {
    assert.strictEqual(
      audio.shouldUseHls({ hasHls: false, devTools: false, disabled: false }), false);
  });

  test('开发者工具不用 HLS（工具不支持，errCode 10001）', () => {
    assert.strictEqual(
      audio.shouldUseHls({ hasHls: true, devTools: true, disabled: false }), false);
  });

  test('本会话已被熔断时不用 HLS（避免重复触发原生失败提示）', () => {
    assert.strictEqual(
      audio.shouldUseHls({ hasHls: true, devTools: false, disabled: true }), false);
  });

  test('异常入参不抛错且回退不用 HLS', () => {
    assert.strictEqual(audio.shouldUseHls(null), false);
    assert.strictEqual(audio.shouldUseHls(undefined), false);
    assert.strictEqual(audio.shouldUseHls({}), false);
  });
});

describe('audio.probeHls（T00572 m3u8 预检）', () => {
  const realRequest = global.wx.request;

  afterEach(() => {
    global.wx.request = realRequest;
  });

  /** 让下一次 wx.request 按给定响应触发 success */
  function stubSuccess(statusCode, data) {
    global.wx.request = (opts) => opts.success({ statusCode, data });
  }

  test('HTTP 200 且正文以 #EXTM3U 开头 → 可用', async () => {
    stubSuccess(200, '#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:6.0,\nseg0.ts\n');
    assert.strictEqual(await audio.probeHls('https://x.com/a/index.m3u8'), true);
  });

  test('HTTP 206 部分内容同样视为可用', async () => {
    stubSuccess(206, '#EXTM3U\n');
    assert.strictEqual(await audio.probeHls('https://x.com/a/index.m3u8'), true);
  });

  test('HTTP 404 → 不可用（预检拦截，不交给原生播放器）', async () => {
    stubSuccess(404, '');
    assert.strictEqual(await audio.probeHls('https://x.com/a/index.m3u8'), false);
  });

  test('HTTP 200 但正文不是 m3u8（如返回 HTML 错误页）→ 不可用', async () => {
    stubSuccess(200, '<html><body>403 Forbidden</body></html>');
    assert.strictEqual(await audio.probeHls('https://x.com/a/index.m3u8'), false);
  });

  test('网络失败（fail 回调）→ 不可用', async () => {
    global.wx.request = (opts) => opts.fail({ errMsg: 'request:fail timeout' });
    assert.strictEqual(await audio.probeHls('https://x.com/a/index.m3u8'), false);
  });

  test('空 URL → 不可用，且不发起请求', async () => {
    let called = false;
    global.wx.request = () => { called = true; };
    assert.strictEqual(await audio.probeHls(''), false);
    assert.strictEqual(called, false);
  });

  test('探测能力本身不可用（wx.request 抛错）→ 失败开放，不阻断 HLS', async () => {
    global.wx.request = () => { throw new Error('request is not supported'); };
    assert.strictEqual(await audio.probeHls('https://x.com/a/index.m3u8'), true);
  });
});
