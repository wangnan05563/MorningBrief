/**
 * T02798（FR-UX-702 / J27 第二半）：缓冲态不得伪装成可播放
 *
 * 工单原文：显示菊花时禁用 seek/倍速等操作入口或给出对应提示。
 * 本环境无微信开发者工具，WXML 的 `disabled="{{isWaiting}}"` 由 validate-ux604 静态守住；
 * 这里锁的是 JS 侧兜底（detail.js 的三个 handler）——因为「模板 disabled 了但 JS 没护栏」
 * 与「JS 有护栏但模板没禁用」是两种不同的坏状态，只测一边会全绿。
 *
 * 测试策略与 detail-listen-delta.test.js 一致：从真实源码里按方法名提取函数体，
 * new Function 注入依赖后在 mock this 上执行。改坏源码（含删护栏、把护栏接到别的字段）
 * 都会让这里红，而不是测一份手写镜像逻辑。
 *
 * 运行：node --test apps/miniprogram/tests/detail-waiting-guard.test.js
 */
const { test, describe } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const DETAIL_JS = path.join(__dirname, '..', 'pages', 'detail', 'detail.js');
const DETAIL_WXML = path.join(__dirname, '..', 'pages', 'detail', 'detail.wxml');
const src = fs.readFileSync(DETAIL_JS, 'utf8');

/** 提取真实方法体（去掉 `onXxx(args) {` 与收尾 `  }`），找不到就抛，避免空体假绿 */
function bodyOf(name) {
  const m = src.match(new RegExp(name + '\\s*\\((?:[^)]*)\\)\\s*\\{([\\s\\S]*?)\\n  \\}'));
  if (!m) throw new Error('detail.js 里找不到方法 ' + name + '（护栏被整段删除或改名？）');
  assert.ok(m[1].trim().length > 0, name + ' 方法体为空');
  return m[1];
}

const RATE_OPTIONS = (src.match(/const RATE_OPTIONS = \[([\s\S]*?)\]/)[1])
  .split(',').map((s) => parseFloat(s.trim())).filter((n) => !Number.isNaN(n));

/**
 * mock 运行环境：记录 seek / 倍速 / toast / setData 的实际发生，供断言「有没有被拦住」
 */
function makeEnv(overrides = {}) {
  const calls = { seek: [], setRate: [], toast: [], setData: [] };
  const data = Object.assign(
    { isWaiting: false, currentTime: 30, currentTimeText: '00:30', duration: 300, currentRate: 1.0, isPlaying: true },
    overrides,
  );
  const page = {
    data,
    isCurrentEpisode: () => true,
    formatTime: (sec) => 'T' + sec,
    setData(obj) {
      calls.setData.push(obj);
      Object.assign(data, obj);
    },
  };
  const injected = {
    getApp: () => ({ globalData: { player: { paused: false } } }),
    wx: { showToast: (o) => calls.toast.push(o.title) },
    seek: (pos) => calls.seek.push(pos),
    getPlaybackRate: () => data.currentRate,
    setPlaybackRate: (r) => calls.setRate.push(r),
    trackEvent: () => {},
    RATE_OPTIONS,
  };
  return { page, calls, injected };
}

/** 把方法体编译成可在 mock this 上执行的函数 */
function compile(name, args) {
  // eslint-disable-next-line no-new-func
  return new Function(...args, bodyOf(name));
}

describe('detail.onSeekInput：缓冲中不更新拖动预览', () => {
  const fn = compile('onSeekInput', ['e']);

  test('缓冲中：不 setData，进度条仍显示真实位置（不出现「已经跳过去了」的错觉）', () => {
    const { page, calls, injected } = makeEnv({ isWaiting: true });
    fn.call(page, { detail: { value: 240 } }, ...Object.values(injected));
    assert.deepEqual(calls.setData, [], '缓冲期间仍改写了 currentTime：等于伪装成可播放');
    assert.strictEqual(page.data.currentTime, 30);
  });

  test('正常态：照旧预览拖动位置', () => {
    const { page, calls, injected } = makeEnv();
    fn.call(page, { detail: { value: 240 } }, ...Object.values(injected));
    assert.strictEqual(calls.setData.length, 1);
    assert.strictEqual(page.data.currentTime, 240);
    assert.strictEqual(page.data.currentTimeText, 'T240');
  });
});

describe('detail.onSeek：缓冲中不落到播放器', () => {
  const fn = compile('onSeek', ['e', 'getApp', 'wx', 'seek']);

  test('缓冲中：不调用 seek、不写 isPlaying、给出提示', () => {
    const { page, calls, injected } = makeEnv({ isWaiting: true });
    fn.call(page, { detail: { value: 240 } }, injected.getApp, injected.wx, injected.seek);
    assert.deepEqual(calls.seek, [], '缓冲期间仍把 seek 打进了播放器');
    assert.deepEqual(calls.setData, [], '缓冲期间仍改了 UI 状态');
    assert.strictEqual(calls.toast.length, 1, '缓冲中拖动应有对应提示');
    assert.match(calls.toast[0], /缓冲中/);
  });

  test('正常态：seek 落播放器并记录 seekTimestamp（防重缓冲把进度拉回）', () => {
    const { page, calls, injected } = makeEnv();
    fn.call(page, { detail: { value: 180 } }, injected.getApp, injected.wx, injected.seek);
    assert.deepEqual(calls.seek, [180]);
    assert.strictEqual(calls.setData[0].currentTime, 180);
    assert.ok(typeof calls.setData[0].seekTimestamp === 'number');
    assert.deepEqual(calls.toast, []);
  });

  test('护栏读的确实是 isWaiting：把条件换成 playError 后缓冲中就会被放行', () => {
    // 这条防的是「护栏接到别的字段上照样绿」：如果换成 playError 后仍然拦得住，
    // 说明真正的判断不是 isWaiting，上面两条缓冲用例就是假绿。
    const right = bodyOf('onSeek');
    const wrong = right.replace(/this\.data\.isWaiting/g, 'this.data.playError');
    assert.notEqual(wrong, right, 'onSeek 里的护栏写法变了，这个对照用例的替换没生效');
    // eslint-disable-next-line no-new-func
    const wrongFn = new Function('e', 'getApp', 'wx', 'seek', wrong);
    const { page, calls, injected } = makeEnv({ isWaiting: true, playError: '' });
    wrongFn.call(page, { detail: { value: 90 } }, injected.getApp, injected.wx, injected.seek);
    assert.deepEqual(calls.seek, [90], '换成 playError 仍被拦住 → 说明拦住它的不是 isWaiting，用例是假的');
  });
});

describe('detail.onCycleRate：缓冲中不改倍速', () => {
  const fn = compile('onCycleRate', ['getPlaybackRate', 'setPlaybackRate', 'wx', 'trackEvent', 'RATE_OPTIONS']);

  test('缓冲中：不写播放器倍速、不改 UI 倍速，只提示', () => {
    const { page, calls, injected } = makeEnv({ isWaiting: true, currentRate: 1.0 });
    fn.call(page, injected.getPlaybackRate, injected.setPlaybackRate, injected.wx,
      injected.trackEvent, RATE_OPTIONS);
    assert.deepEqual(calls.setRate, [], '缓冲期间仍修改了倍速');
    assert.deepEqual(calls.setData, [], '缓冲期间倍速数字仍变了：用户以为切成功');
    assert.match(calls.toast[0] || '', /缓冲中/);
  });

  test('正常态：按 RATE_OPTIONS 顺序推进并同步 UI', () => {
    const { page, calls, injected } = makeEnv({ currentRate: 1.0 });
    fn.call(page, injected.getPlaybackRate, injected.setPlaybackRate, injected.wx,
      injected.trackEvent, RATE_OPTIONS);
    assert.deepEqual(calls.setRate, [RATE_OPTIONS[2]]);
    assert.strictEqual(page.data.currentRate, RATE_OPTIONS[2]);
  });

  test('RATE_OPTIONS 取自真实源码：不能是测试自己写死的一份', () => {
    assert.deepEqual(RATE_OPTIONS, [0.75, 1, 1.25, 1.5, 2]);
  });
});

describe('WXML 侧禁用与说明（静态锁，补真机不可验的一段）', () => {
  const wxml = fs.readFileSync(DETAIL_WXML, 'utf8').replace(/<!--[\s\S]*?-->/g, '');

  test('进度 slider 缓冲时 disabled', () => {
    assert.match(wxml, /disabled="\{\{isWaiting\}\}"/);
  });

  test('倍速入口缓冲时把可访问说明换成「暂不可切换倍速」', () => {
    const m = /bindtap="onCycleRate"[\s\S]{0,120}?aria-label="([^"]*)"/.exec(wxml);
    assert.ok(m, '倍速入口找不到 aria-label');
    assert.match(m[1], /isWaiting/);
    assert.match(m[1], /暂不可切换倍速/);
  });

  test('倍速入口缓冲时有淡化态，视觉上也看得出点不动', () => {
    assert.match(wxml, /class="action-chip[^"]*\{\{isWaiting \? 'is-blocked'/);
    const wxss = fs.readFileSync(path.join(__dirname, '..', 'pages', 'detail', 'detail.wxss'), 'utf8');
    assert.match(wxss, /\.action-chip\.is-blocked\s*\{[^}]*opacity/);
  });
});
