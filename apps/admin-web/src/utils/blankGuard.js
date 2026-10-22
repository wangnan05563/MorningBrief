/**
 * C56 / FR-UX-202：素材关键列「非空 → 空白」的前端预检。
 *
 * 后端 `PUT /materials/{id}` 有同名护栏（`_reject_blanking_critical_field`），
 * 这里是**提交前**的那一道：让运营在点保存时就看到「哪一列要被清空、后果是什么」，
 * 而不是等服务端拒绝。两处的字段口径必须一致，所以抽成模块级常量供门禁断言。
 *
 * 之所以抽成纯函数而不是留在 `MaterialLibrary.vue` 里：视图内的循环 + ref 取值
 * 只能靠字符串断言，字符串断言认不出「定义改了名但引用没改」这类破坏（变异探针实测）。
 */

/** 与后端 `_BLANK_CRITICAL_REASONS` 同一批列；label 用于提示文案。 */
export const BLANK_CRITICAL_FIELDS = {
  content: { label: '正文', reason: '正文清空后该素材无法进入改写流程' },
  source: { label: '来源', reason: '来源（书名）是讲书稿的按书聚合键，清空后整本书会从书单候选中消失' },
}

/**
 * @param {Record<string, any>} original 打开编辑弹窗时的原值快照
 * @param {Record<string, any>} current 即将提交的表单值
 * @returns {{field: string, label: string, reason: string} | null}
 */
export function findBlankedCriticalField(original, current) {
  for (const [field, meta] of Object.entries(BLANK_CRITICAL_FIELDS)) {
    // 与后端 PUT 的 exclude_unset 同一语义：表单里根本没有这个键＝没提交＝不改，不算清空
    if (!(field in (current ?? {}))) continue
    const before = String(original?.[field] ?? '').trim()
    const now = String(current?.[field] ?? '').trim()
    // 只拦「原本有内容、现在没了」；原值本就为空的行必须继续可编辑，
    // 否则会把防护做成新的 bug（历史导入的空正文素材彻底改不动）。
    if (before && !now) return { field, ...meta }
  }
  return null
}

export function blankedFieldMessage(hit) {
  return `${hit.label}不能清空：${hit.reason}`
}
