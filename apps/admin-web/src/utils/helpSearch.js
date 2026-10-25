/**
 * 帮助文档搜索（M88 / T02763）。
 *
 * 章节正文全在 blocks 里：feature/scenario 是字符串，steps 是字符串数组，
 * config 是 [参数, 示例, 说明] 三列表格行，note 是字符串。搜索必须把它们都算进来，
 * 否则「VACUUM」「COS_SECRET_ID」这类只在正文出现的词搜不到，用户会以为文档没写。
 *
 * 图标组件与展示枚举不是文档内容，跳过——否则搜 "warning" 会命中所有带注意事项的章节。
 */
const NON_CONTENT_KEYS = new Set(['icon', 'type', 'noteType', 'id'])

export function collectSectionText(value, out = []) {
  if (typeof value === 'string') {
    out.push(value)
  } else if (Array.isArray(value)) {
    value.forEach((v) => collectSectionText(v, out))
  } else if (value && typeof value === 'object') {
    Object.entries(value).forEach(([key, v]) => {
      if (NON_CONTENT_KEYS.has(key)) return
      collectSectionText(v, out)
    })
  }
  return out
}

/** 关键词为空保留全部章节；否则标题、简介、正文任一命中即保留（忽略大小写与首尾空白） */
export function filterHelpSections(sections, keyword) {
  const list = Array.isArray(sections) ? sections : []
  const kw = String(keyword || '').trim().toLowerCase()
  if (!kw) return list
  return list.filter((section) => {
    const haystack = collectSectionText([section.title, section.intro, section.blocks])
      .join('\n')
      .toLowerCase()
    return haystack.includes(kw)
  })
}
