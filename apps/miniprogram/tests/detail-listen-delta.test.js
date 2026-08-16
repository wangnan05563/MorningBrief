/**
 * pages/detail/detail.js#_calcListenDelta 单元测试
 *
 * 使用 Node.js 内置 node:test 运行（无需额外依赖）：
 *   node --test miniprogram/tests/detail-listen-delta.test.js
 *
 * 测试策略：detail.js 是依赖 wx/getApp 等运行时的 Page 模块，无法在 Node 中直接 require。
 * 这里从 detail.js 源码中用正则提取 _calcListenDelta 方法体字符串，
 * 用 new Function 包装成可调用函数，在 mock 的 this 上下文上执行——保证测试的是真实源码
 * （方法体被修改时测试会真实反映），而非手写一份镜像逻辑。
 *
 * 设计背景：detail.js#_onTimeUpdate 5s 节流上报时调用 this._calcListenDelta(ct)，
 * 此前该方法从未实现，真机调试每 5s 抛一次 "e._calcListenDelta is not a function"。
 */
const { test, describe } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

/**
 * 从 detail.js 源码中提取 _calcListenDelta 方法体（函数体内部代码）
 * new Function 期望 statements，不能直接吃函数声明
 * @returns {string} 方法体内部代码（不含 _calcListenDelta(ct) { ... } 包裹）
 */
function loadCalcListenDeltaSource() {
  const detailPath = path.join(__dirname, '..', 'pages', 'detail', 'detail.js');
  const src = fs.readFileSync(detailPath, 'utf8');
  // 匹配方法声明到方法结束 "  }," 之间的函数体
  const m = src.match(/_calcListenDelta\(ct\) \{([\s\S]*?)\n  \}/);
  if (!m) {
    throw new Error('未在 detail.js 中找到 _calcListenDelta 方法，请确认该方法已存在');
  }
  return m[1];
}

/**
 * 构造 mock this：data + 闭包标志 + setData，模拟 Page 实例
 * setData 直接更新 data 引用，模拟微信 Page 的浅合并行为
 */
function makeFakePage() {
  const data = { lastListenStartTs: 0 };
  return {
    data,
    _lastListenDeltaInited: false,
    setData(obj) {
      Object.assign(data, obj);
    },
  };
}

// 真实方法体（从 detail.js 提取）
const methodSource = loadCalcListenDeltaSource();

describe('detail._calcListenDelta', () => {
  test('首次调用：记录基准 position 并返回 0（避免断点续播误算）', () => {
    // 模拟用户从 120 秒断点续播进来，首次 _calcListenDelta(120) 不应算"听了 120 秒"
    const fakePage = makeFakePage();
    // eslint-disable-next-line no-new-func
    const fn = new Function('ct', methodSource);
    const delta = fn.call(fakePage, 120);
    assert.strictEqual(delta, 0);
    assert.strictEqual(fakePage.data.lastListenStartTs, 120, '首次应记录 ct 作为下次基准');
    assert.strictEqual(fakePage._lastListenDeltaInited, true);
  });

  test('正常前进：返回 ct - lastListenStartTs', () => {
    const fakePage = makeFakePage();
    // eslint-disable-next-line no-new-func
    const fn = new Function('ct', methodSource);
    fn.call(fakePage, 100); // 首次：记录基准 100
    const delta = fn.call(fakePage, 105);
    assert.strictEqual(delta, 5);
    assert.strictEqual(fakePage.data.lastListenStartTs, 105);
  });

  test('用户 seek 后退：返回 0（避免负累加影响 User.total_listen_duration）', () => {
    const fakePage = makeFakePage();
    // eslint-disable-next-line no-new-func
    const fn = new Function('ct', methodSource);
    fn.call(fakePage, 200); // 首次：记录 200
    const delta = fn.call(fakePage, 100); // seek 退到 100
    assert.strictEqual(delta, 0, 'seek 后退必须返回 0 而非负数');
    // 基准仍更新到 100：避免下次再算成 100-200=-100 重复触发负数兜底
    assert.strictEqual(fakePage.data.lastListenStartTs, 100);
  });

  test('缓冲中未前进：返回 0', () => {
    const fakePage = makeFakePage();
    // eslint-disable-next-line no-new-func
    const fn = new Function('ct', methodSource);
    fn.call(fakePage, 300); // 首次
    const delta = fn.call(fakePage, 300); // ct 不变
    assert.strictEqual(delta, 0);
  });

  test('切歌后 _lastListenDeltaInited 重置：下次首次仍返回 0', () => {
    const fakePage = makeFakePage();
    // eslint-disable-next-line no-new-func
    const fn = new Function('ct', methodSource);
    fn.call(fakePage, 50);
    fn.call(fakePage, 55);
    // 模拟 _syncToEpisode 中的重置
    fakePage._lastListenDeltaInited = false;
    fakePage.data.lastListenStartTs = 0;
    const delta = fn.call(fakePage, 10); // 新节目从 10 秒开始
    assert.strictEqual(delta, 0, '切歌后首次必须返回 0，不应沿用旧 lastListenStartTs');
    assert.strictEqual(fakePage.data.lastListenStartTs, 10);
  });
});
