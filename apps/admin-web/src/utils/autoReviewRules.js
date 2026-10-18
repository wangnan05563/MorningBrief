/**
 * 自动审批命中规则的展示口径（T02492 / FR-UX-204）
 *
 * 后端把每次自动通过写成的结构化 JSON 有两代格式：
 * - 旧：`["content_safe", ...]`（只有命中项，看不出这次少查了什么）
 * - 新：`{"matched_rules": [...], "skipped_rules": [...]}`
 * 另有失败/护栏形态 `{"failed_rules": [...]}`、`{"guard": "no_enforced_rule"}`。
 * 两处消费方（自动审批配置页的历史表、移动端审核详情）都走这里，避免各写一遍漂移。
 */

const RULE_LABELS = {
  content_safe: '内容安全检测',
  steps_first_success: '步骤一次成功',
  keyword_whitelist: '关键词白名单',
  audiobook_consistency: '听书一致性校验',
}

export function ruleLabel(name) {
  return RULE_LABELS[name] || name
}

/**
 * 把 trigger_reason / auto_trigger_reason 原文转成一句人能读的话。
 * 解析不出结构时原样返回，历史记录不会因为新格式而变成空白。
 *
 * @param {string|null|undefined} raw JSON 字符串
 * @param {string} fallback 空值时的占位文案
 * @returns {string}
 */
export function formatTriggerReason(raw, fallback = '-') {
  if (!raw) return fallback
  let data
  try {
    data = JSON.parse(raw)
  } catch {
    return String(raw)
  }
  if (Array.isArray(data)) {
    return data.map(ruleLabel).join('、') || fallback
  }
  const parts = []
  if (data.matched_rules?.length) {
    parts.push('命中：' + data.matched_rules.map(ruleLabel).join('、'))
  }
  if (data.skipped_rules?.length) {
    parts.push('跳过：' + data.skipped_rules.map(ruleLabel).join('、'))
  }
  // failed_rules 是后端写的整句原因，不再套规则名映射
  if (data.failed_rules?.length) {
    parts.push('未通过：' + data.failed_rules.join('；'))
  }
  if (data.guard === 'no_enforced_rule') {
    parts.push('护栏拦截：无生效校验')
  }
  return parts.length ? parts.join(' / ') : String(raw)
}
