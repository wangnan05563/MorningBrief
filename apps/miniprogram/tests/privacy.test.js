/**
 * privacy 协调器单元测试（T00609）
 *
 * 覆盖：队列 + 防重入、官方按钮路径（带 buttonId）/ 兜底路径（无 buttonId）/ 拒绝扇出、
 * 重复授权后队列清空、再入授权。
 *
 * 运行：node --test apps/miniprogram/tests/privacy.test.js
 */
const { test, describe } = require('node:test');
const assert = require('node:assert');

const { createPrivacyCoordinator } = require('../utils/privacy');

function makeResolved() {
  const resolved = [];
  return {
    resolved,
    resolve() {
      return (r) => resolved.push(r);
    },
  };
}

describe('createPrivacyCoordinator（隐私授权协调器）', () => {
  test('首个请求触发弹窗，后续请求仅排队（防重入）', () => {
    const c = createPrivacyCoordinator();
    assert.deepStrictEqual(c.needPrivacy(() => {}), { shown: true });
    assert.deepStrictEqual(c.needPrivacy(() => {}), { shown: false });
    assert.strictEqual(c.isShowing(), true);
    assert.strictEqual(c.pendingCount(), 2);
  });

  test('官方按钮路径：全部挂起请求以 agree + buttonId 放行', () => {
    const c = createPrivacyCoordinator();
    const r1 = makeResolved();
    const r2 = makeResolved();
    c.needPrivacy(r1.resolve());
    c.needPrivacy(r2.resolve());
    const n = c.agreeViaButton('agree-btn');
    assert.strictEqual(n, 2);
    assert.deepStrictEqual(r1.resolved, [{ event: 'agree', buttonId: 'agree-btn' }]);
    assert.deepStrictEqual(r2.resolved, [{ event: 'agree', buttonId: 'agree-btn' }]);
    assert.strictEqual(c.isShowing(), false, '授权完成后弹窗态复位');
  });

  test('兜底路径：wx.showModal 同意 → resolve 无 buttonId（非按钮类 API 可用）', () => {
    const c = createPrivacyCoordinator();
    const r = makeResolved();
    c.needPrivacy(r.resolve());
    c.agreeFallback();
    assert.deepStrictEqual(r.resolved, [{ event: 'agree' }]);
  });

  test('拒绝：全部按 disagree 放行', () => {
    const c = createPrivacyCoordinator();
    const r1 = makeResolved();
    const r2 = makeResolved();
    c.needPrivacy(r1.resolve());
    c.needPrivacy(r2.resolve());
    c.reject();
    assert.deepStrictEqual(r1.resolved, [{ event: 'disagree' }]);
    assert.deepStrictEqual(r2.resolved, [{ event: 'disagree' }]);
  });

  test('授权完成后可再次进入（重试场景）', () => {
    const c = createPrivacyCoordinator();
    c.needPrivacy(() => {});
    c.reject();
    assert.deepStrictEqual(c.needPrivacy(() => {}), { shown: true }, '拒绝后新请求应重新弹窗');
  });

  test('agreeViaButton 未传 buttonId 时用默认值 agree-btn', () => {
    const c = createPrivacyCoordinator();
    const r = makeResolved();
    c.needPrivacy(r.resolve());
    c.agreeViaButton();
    assert.strictEqual(r.resolved[0].buttonId, 'agree-btn');
  });
});
