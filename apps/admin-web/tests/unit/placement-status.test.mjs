/**
 * T02602：投放四态的展示字典。
 *
 * 状态码由服务端派生（enabled + 日期闭区间），前端只做映射；
 * 这里钉住四态文案互不混同，未知状态不伪装成正常态。
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

import { PLACEMENT_STATUS_META, placementStatusMeta } from '../../src/utils/placementStatus.js'

test('四态各自有独立文案与色调', () => {
  assert.deepEqual(PLACEMENT_STATUS_META.disabled, { label: '已停用', tone: 'off' })
  assert.deepEqual(PLACEMENT_STATUS_META.pending, { label: '待投放', tone: 'pending' })
  assert.deepEqual(PLACEMENT_STATUS_META.active, { label: '生效中', tone: 'on' })
  assert.deepEqual(PLACEMENT_STATUS_META.expired, { label: '已过期', tone: 'expired' })
  const labels = Object.values(PLACEMENT_STATUS_META).map((m) => m.label)
  assert.equal(new Set(labels).size, 4, '四态文案不能重复，否则界面无法区分')
})

test('未知/缺失状态显示「状态未知」，不冒充生效中', () => {
  assert.equal(placementStatusMeta('bogus').label, '状态未知')
  assert.equal(placementStatusMeta(undefined).label, '状态未知')
  assert.notEqual(placementStatusMeta(undefined).tone, 'on')
})
