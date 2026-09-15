/**
 * 加载态控制器（T00599）：最短骨架展示 + 慢加载分级提示 + 超时重试。
 *
 * 为什么不是「先播固定 N 秒动画」（T00595 评估结论）：
 * - 固定时长会把「1.5 秒就绪」的首屏强行拖长，体感更慢；
 * - 固定时长与真实耗时解耦，掩盖接口变慢，破坏可观测性。
 * 因此这里只做三件**下限保护 + 分级提示**的事：
 *   1. **最短展示 minMs（默认 600ms）**：数据早于阈值到达也保持骨架到阈值，消除「骨架一闪」；
 *   2. **慢加载提示 slowMs（默认 2000ms）**：超过则提示「网络较慢，正在加载…」；
 *   3. **超时重试 timeoutMs（默认 8000ms）**：仍在加载则给出「重试」入口（页面渲染按钮）。
 *
 * 用法（页面内）：
 *   const { createLoadingController } = require('../../utils/loading');
 *   // onLoad / 数据拉取前
 *   this._lc = createLoadingController({ setData: this.setData.bind(this) });
 *   this._lc.start();
 *   ...await fetch...
 *   this._lc.finish();   // 成功：等到最短展示时长后收起骨架
 *   this._lc.fail();     // 失败：立即收起（错误态由页面自己渲染）
 *   // onUnload
 *   this._lc && this._lc.cancel();
 */

const DEFAULT_MIN_MS = 600;
const DEFAULT_SLOW_MS = 2000;
const DEFAULT_TIMEOUT_MS = 8000;

/** 加载态三元组：每次 setData 都发完整状态（不发增量），避免页面残留上一次的提示态 */
const STATE_LOADING = { loading: true, loadingSlow: false, loadingTimedOut: false };
const STATE_SLOW = { loading: true, loadingSlow: true, loadingTimedOut: false };
const STATE_TIMEOUT = { loading: true, loadingSlow: false, loadingTimedOut: true };
const STATE_DONE = { loading: false, loadingSlow: false, loadingTimedOut: false };

/**
 * @param {object} options
 * @param {Function} options.setData 页面 setData（必传）
 * @param {number} [options.minMs] 最短骨架展示时长
 * @param {number} [options.slowMs] 慢加载提示阈值
 * @param {number} [options.timeoutMs] 超时重试阈值
 * @param {object} [options.timers] 计时器实现（单测注入假计时器）
 * @param {Function} [options.now] 取当前时间（单测注入）
 */
function createLoadingController(options) {
  const opts = options || {};
  const setData = opts.setData;
  if (typeof setData !== 'function') {
    throw new Error('createLoadingController 需要 setData');
  }
  const timers = opts.timers || {
    setTimeout: (fn, ms) => setTimeout(fn, ms),
    clearTimeout: (t) => clearTimeout(t),
  };
  const now = opts.now || (() => Date.now());
  const minMs = typeof opts.minMs === 'number' ? opts.minMs : DEFAULT_MIN_MS;
  const slowMs = typeof opts.slowMs === 'number' ? opts.slowMs : DEFAULT_SLOW_MS;
  const timeoutMs = typeof opts.timeoutMs === 'number' ? opts.timeoutMs : DEFAULT_TIMEOUT_MS;

  let startedAt = 0;
  let active = false;
  let slowTimer = null;
  let timeoutTimer = null;
  let closeTimer = null;

  function clearTimers() {
    if (slowTimer) { timers.clearTimeout(slowTimer); slowTimer = null; }
    if (timeoutTimer) { timers.clearTimeout(timeoutTimer); timeoutTimer = null; }
  }

  function clearCloseTimer() {
    if (closeTimer) { timers.clearTimeout(closeTimer); closeTimer = null; }
  }

  /** 进入加载态（重复调用会重置计时，用于下拉刷新/重试） */
  function start() {
    clearTimers();
    clearCloseTimer();
    active = true;
    startedAt = now();
    setData({ ...STATE_LOADING });
    slowTimer = timers.setTimeout(() => {
      if (active) setData({ ...STATE_SLOW });
    }, slowMs);
    timeoutTimer = timers.setTimeout(() => {
      if (!active) return;
      // 超时：保留骨架（loading 仍为 true），额外给出重试入口
      setData({ ...STATE_TIMEOUT });
    }, timeoutMs);
  }

  /**
   * 成功结束。
   * @param {boolean} [immediate] true = 立即收起（本地即刻决策、无网络等待的场景，
   *   不应被最短展示时长拖住，如「未设置偏爱频道」直接出引导）；默认 false 走最短展示保护
   * @returns {number} 还需等待的毫秒数（immediate 或已过阈值时为 0）
   */
  function finish(immediate) {
    const elapsed = now() - startedAt;
    const remain = immediate ? 0 : Math.max(0, minMs - elapsed);
    clearTimers();
    const close = () => {
      active = false;
      closeTimer = null;
      setData({ ...STATE_DONE });
    };
    if (active && remain > 0) {
      closeTimer = timers.setTimeout(close, remain);
      return remain;
    }
    close();
    return 0;
  }

  /** 失败结束：立即收起骨架（错误态/空态由页面自行渲染，不占用最短展示时长） */
  function fail() {
    clearTimers();
    clearCloseTimer();
    active = false;
    setData({ ...STATE_DONE });
  }

  /** 页面卸载清理（避免在已卸载页面上 setData） */
  function cancel() {
    clearTimers();
    clearCloseTimer();
    active = false;
  }

  /** 是否仍在加载态（供页面在异步回调里判断是否已被取消/重试覆盖） */
  function isLoading() {
    return active;
  }

  return { start, finish, fail, cancel, isLoading };
}

module.exports = {
  createLoadingController,
  DEFAULT_MIN_MS,
  DEFAULT_SLOW_MS,
  DEFAULT_TIMEOUT_MS,
};
