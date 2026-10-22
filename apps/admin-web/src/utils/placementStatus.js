/**
 * 投放状态展示字典（T02602）。
 *
 * 四态由服务端按「开关 + 日期闭区间」派生后随列表/排期下发，
 * 前端只做文案与色调映射，不再各自按 enabled 猜一遍——
 * 否则 12 月排期和过期投放都会被显示成「投放中」，与 C 端真实播放不一致。
 */
export const PLACEMENT_STATUS_META = {
  disabled: { label: '已停用', tone: 'off' },
  pending: { label: '待投放', tone: 'pending' },
  active: { label: '生效中', tone: 'on' },
  expired: { label: '已过期', tone: 'expired' },
}

export function placementStatusMeta(status) {
  return PLACEMENT_STATUS_META[status] || { label: '状态未知', tone: 'expired' }
}
