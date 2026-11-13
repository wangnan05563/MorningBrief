/**
 * 时长格式化单一来源（T02710 / FR-UX-501）
 *
 * 这个文件同时被三个地方消费：
 * - 小程序模板侧：`<wxs module="dur" src="../../utils/duration.wxs" />` 后调 `dur.time(x)`；
 * - 小程序逻辑层：`utils/duration.js` 是本文件的**逐字节镜像**，`utils/format.js` require 的是那份。
 *   逻辑层模块系统不认 .wxs（`require('./duration.wxs')` 会报
 *   `module 'utils/duration.wxs.js' is not defined`，2026-11-09 真机复现）；
 * - Node / 测试：`tests/duration-format.test.js` 直接 require 本文件并断言，同时锁两文件同步。
 * 之所以写成 WXS 而不是普通 js，是为了让「模板里的那次换算」和「JS 里的那次换算」
 * 是同一份代码——此前 mm:ss 在 5 个 wxml 里各抄一遍、秒→分在 9 个 js 里各算一遍，
 * 同一条时长能显示成「00:47」「0分47秒」「47秒」三种样子。
 *
 * ⚠️ 双文件镜像纪律：只编辑本文件（duration.wxs 是编辑源），改完整份复制到
 * utils/duration.js；测试用「逐字节一致」断言锁住，任何一边单独改动都会红。
 *
 * 语法限制：WXS 只支持 ES5 的一个更小子集——没有模板字符串、没有 padStart，
 * 也没有 Number()/parseFloat() 与 isFinite() 这些全局（可用全局只有 Math、JSON、
 * getDate、getRegExp、console；写 `Number(` 会直接报 WXML 编译错误
 * `Unexpected token '('`，2026-11-09 真机复现）。故数字归一走下方 normalizeSec：
 * 「乘 1 转型 + NaN 自反判 + Infinity 除自判」，不依赖任何受限全局；补零照旧手写。
 * 内部互相调用走文件级 var，不依赖 `module.exports.xxx` 的自引用（真机 WXS 作用域
 * 与 Node 不完全一致，少一分侥幸少一分麻烦）。
 * 也正因如此本文件必须保持「Node 能直接 require」——tests/duration-format.test.js 会真的加载它并断言。
 */

/**
 * 无效输入归一：NaN / 非正数统一落 0，与旧口径 Number(x) + isFinite 逐值等价
 * （null→0、''→0 被 <=0 拦下；undefined/'abc'/'{}'→NaN 被自反判拦下）。
 * 不用 Number()/isFinite()：WXS 解析器不认识它们（见文件头「语法限制」）。
 */
function normalizeSec(sec) {
  var n = sec * 1
  if (n !== n) return 0      // NaN：NaN !== NaN 是唯一可靠的 NaN 判定
  if (n / n !== 1) return 0  // ±Infinity：Infinity/Infinity 是 NaN；有限非零数 n/n 恒为 1（0 的 0/0 也是 NaN，随后同样落 0）
  if (n <= 0) return 0
  return n
}

function floorMinutes(sec) {
  return Math.floor(normalizeSec(sec) / 60)
}

module.exports = {
  /**
   * 秒 → "mm:ss"（进度条、列表时长用）。
   * 无效值（null / NaN / 负数）统一落到 '00:00'，不再出现 'NaN:NaN' 与空串两种口径。
   */
  time: function (sec) {
    var n = Math.floor(normalizeSec(sec))
    var m = Math.floor(n / 60)
    var s = Math.floor(n % 60)
    return (m < 10 ? '0' + m : '' + m) + ':' + (s < 10 ? '0' + s : '' + s)
  },

  /**
   * 秒 → 中文时长（"47分钟" / "1小时5分钟" / "2小时"），整段时长展示用。
   */
  cn: function (sec) {
    var total = floorMinutes(sec)
    var hours = Math.floor(total / 60)
    var minutes = total % 60
    if (hours <= 0) return minutes + '分钟'
    return minutes > 0 ? hours + '小时' + minutes + '分钟' : hours + '小时'
  },

  /**
   * 秒 → 分钟数（向下取整）。定时/倒计时文案按分钟说话。
   */
  floorMinutes: floorMinutes,

  /**
   * 秒 → 分钟数（四舍五入），个人中心「累计收听 N 分钟」用：
   * 后端 total_listen_seconds 是秒，界面按分钟显示，换算只允许发生在这一处。
   */
  minutes: function (sec) {
    return Math.round(normalizeSec(sec) / 60)
  },

  /**
   * 秒 → { hours, minutes }（分钟向下取整后再拆，秒被丢弃）。
   * 拆分口径由这里唯一决定，页面只负责拼自己的文案（「1时半」vs「1小时30分钟后停止」）。
   */
  splitHoursMinutes: function (sec) {
    var total = floorMinutes(sec)
    return { hours: Math.floor(total / 60), minutes: total % 60 }
  }
}
