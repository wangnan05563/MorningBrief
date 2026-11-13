/**
 * 时长格式化（页面 JS 入口，T02710 / FR-UX-501）
 *
 * 这里只有一层转发：真正的换算在 `duration.js`/`duration.wxs`（同一份实现的镜像，
 * 逻辑层模块系统不认 .wxs，只能 require 镜像的 .js；模板侧用的则是 .wxs 那份）。
 * 分成两个文件是因为小程序模板只能引 WXS、页面 JS 习惯引 CommonJS 模块，
 * 而**唯一的事实源必须是同一个**——否则「JS 改了、模板没改」会立刻产生两端不一致，
 * 正是本单要消除的形态。tests/duration-format.test.js 锁住这条转发与镜像关系。
 */
const duration = require('./duration.js')

/**
 * @param {number} sec 秒
 * @param {{style?: 'mmss' | 'cn' | 'minutes', emptyText?: string}} [opts]
 *        style 默认 'mmss'；emptyText 覆盖无效值的显示（默认按 style 各自的零值口径）
 * @returns {string|number} 'mm:ss' / 'X小时Y分钟' / 分钟数
 */
function formatDuration(sec, opts) {
  const style = (opts && opts.style) || 'mmss'
  const emptyText = opts && opts.emptyText
  if (emptyText !== undefined && !(Number(sec) > 0)) return emptyText
  if (style === 'minutes') return duration.minutes(sec)
  if (style === 'cn') return duration.cn(sec)
  if (style === 'mmss') return duration.time(sec)
  throw new Error('formatDuration: 未知 style ' + style)
}

module.exports = {
  time: duration.time,
  cn: duration.cn,
  minutes: duration.minutes,
  floorMinutes: duration.floorMinutes,
  splitHoursMinutes: duration.splitHoursMinutes,
  formatDuration,
}
