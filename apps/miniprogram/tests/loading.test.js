/**
 * loading 控制器单元测试（T00599）
 *
 * 用注入的假计时器（可手动 tick）验证三个阈值的**边界行为**，避免依赖真实时钟导致 flaky：
 *  - 最短展示：数据早到也要等满 minMs 才收起；晚到则立即收起；
 *  - 慢加载：超过 slowMs 出现提示，正常结束时提示关闭；
 *  - 超时：超过 timeoutMs 出现重试态（loading 保持 true）；
 *  - 失败：立即收起，不被最短展示时长拖住；
 *  - 生命周期：cancel 后计时器全部失效（不再 setData）。
 *
 * 运行：node --test apps/miniprogram/tests/loading.test.js
 */
const { test, describe } = require('node:test');
const assert = require('node:assert');

const { createLoadingController } = require('../utils/loading');

/** 假计时器：手动推进时间，同步触发回调 */
function fakeTimers() {
  let seq = 0;
  let clock = 0;
  const queue = new Map(); // id -> {at, fn}
  return {
    clock: () => clock,
    setTimeout(fn, ms) {
      const id = ++seq;
      queue.set(id, { at: clock + ms, fn });
      return id;
    },
    clearTimeout(id) {
      queue.delete(id);
    },
    /** 推进时间并执行到期的回调 */
    tick(ms) {
      clock += ms;
      for (const [id, item] of [...queue.entries()]) {
        if (item.at <= clock) {
          queue.delete(id);
          item.fn();
        }
      }
    },
    pending() {
      return queue.size;
    },
  };
}

function makeController(overrides) {
  const states = [];
  const t = fakeTimers();
  const ctl = createLoadingController({
    setData: (d) => states.push({ ...d, _clock: t.clock() }),
    timers: { setTimeout: t.setTimeout, clearTimeout: t.clearTimeout },
    now: t.clock,
    ...(overrides || {}),
  });
  return { ctl, states, t, last: () => states[states.length - 1] };
}

describe('createLoadingController（加载态控制器）', () => {
  test('start 立即进入骨架态（loading=true，无提示）', () => {
    const { ctl, last } = makeController();
    ctl.start();
    assert.deepStrictEqual(last(), { loading: true, loadingSlow: false, loadingTimedOut: false, _clock: 0 });
  });

  test('数据 200ms 早到：等到 600ms 最短展示后才收起骨架', () => {
    const { ctl, states, t, last } = makeController();
    ctl.start();
    t.tick(200);
    const remain = ctl.finish();
    assert.strictEqual(remain, 400, '剩余等待应为 600-200');
    assert.strictEqual(states.filter((s) => s.loading === false).length, 0);
    t.tick(399);
    assert.strictEqual(states.filter((s) => s.loading === false).length, 0, '未到阈值不应收起');
    t.tick(1);
    assert.strictEqual(last().loading, false, '到 600ms 收起');
  });

  test('数据 1500ms 晚到：立即收起（不额外等待）', () => {
    const { ctl, t, last } = makeController();
    ctl.start();
    t.tick(1500);
    const remain = ctl.finish();
    assert.strictEqual(remain, 0);
    assert.strictEqual(last().loading, false);
  });

  test('慢加载：超过 slowMs 出现提示，正常结束清掉提示', () => {
    const { ctl, t, last } = makeController();
    ctl.start();
    t.tick(2000);
    assert.strictEqual(last().loadingSlow, true, '2s 应出现慢加载提示');
    assert.strictEqual(last().loadingTimedOut, false);
    t.tick(1000);
    ctl.finish();
    assert.strictEqual(last().loading, false);
    assert.strictEqual(last().loadingSlow, false, '完成后提示必须清掉');
  });

  test('超时：超过 timeoutMs 出现重试态且骨架保持', () => {
    const { ctl, t, last } = makeController();
    ctl.start();
    t.tick(8000);
    assert.strictEqual(last().loadingTimedOut, true);
    assert.strictEqual(last().loading, true, '超时后骨架保持，等待用户重试');
    assert.strictEqual(last().loadingSlow, false, '超时态取代慢提示，避免两条提示叠加');
  });

  test('失败：立即收起且不占用最短展示时长', () => {
    const { ctl, t, last } = makeController();
    ctl.start();
    t.tick(100);
    ctl.fail();
    assert.strictEqual(last().loading, false);
    assert.strictEqual(last().loadingTimedOut, false);
    assert.strictEqual(last().loadingSlow, false);
  });

  test('重试：start 重置计时与全部提示态', () => {
    const { ctl, t, last } = makeController();
    ctl.start();
    t.tick(8000);
    assert.strictEqual(last().loadingTimedOut, true);
    ctl.start();
    assert.strictEqual(last().loadingTimedOut, false);
    assert.strictEqual(last().loadingSlow, false);
    assert.strictEqual(last().loading, true);
  });

  test('cancel：清理计时器，之后不再 setData', () => {
    const { ctl, states, t } = makeController();
    ctl.start();
    const before = states.length;
    ctl.cancel();
    assert.strictEqual(ctl.isLoading(), false);
    t.tick(10000);
    assert.strictEqual(states.length, before, 'cancel 后不应再有 setData');
  });

  test('自定义阈值', () => {
    const { ctl, t, last } = makeController({ minMs: 100, slowMs: 50, timeoutMs: 200 });
    ctl.start();
    t.tick(50);
    assert.strictEqual(last().loadingSlow, true);
    t.tick(150);
    assert.strictEqual(last().loadingTimedOut, true);
  });

  test('finish(true) 立即收起：本地即刻决策不被最短展示时长拖住', () => {
    const { ctl, t, last } = makeController();
    ctl.start();
    t.tick(50);
    const remain = ctl.finish(true);
    assert.strictEqual(remain, 0);
    assert.strictEqual(last().loading, false, '立即收起');
  });

  test('缺 setData 时抛错（防误用）', () => {
    assert.throws(() => createLoadingController({}), /需要 setData/);
  });
});
