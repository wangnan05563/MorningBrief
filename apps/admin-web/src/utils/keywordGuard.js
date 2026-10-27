/**
 * T02604：关键词白名单长度护栏的前端判定。
 *
 * 阈值不在这里写死——它由配置接口的 `keyword_limits` 下发（后端
 * `app/core/keyword_guard.py` 是唯一来源）。界面只按下发的数判定，
 * 两侧才不会漂移：改阈值只需要动后端，前端跟着变。
 */

const NON_ASCII = /[^\x00-\x7F]/

export function keywordMinLength(kw, limits) {
  return NON_ASCII.test(kw) ? limits.min_length : limits.ascii_min_length
}

/**
 * limits 为空（配置还没加载完）时一律判「不算短」：
 * 宁可不拦，也不能拿默认值误拦管理员的有效词。
 */
export function keywordTooShort(kw, limits) {
  if (!limits) return false
  return kw.length < keywordMinLength(kw, limits)
}

export function filterTooShort(words, limits) {
  return words.filter((kw) => keywordTooShort(kw, limits))
}

/** 提示语里的量词按词形走：汉字讲「个字」，纯英文讲「个字母」，数仍然来自下发值。 */
export function minLengthHint(kw, limits) {
  return `至少 ${keywordMinLength(kw, limits)} ${NON_ASCII.test(kw) ? '个字' : '个字母'}`
}
