/**
 * 政策文本单一来源（T02690 / 方案 A）
 *
 * 用户协议与隐私政策的正文只维护一份：小程序 `pages/{agreement,privacy}/*.js` 里的
 * `data.sections` 常量（V1.3 · FR-SUP-11）。本脚本把它们渲染成 `docs/legal/*.md`，
 * 供仓库内检索与审阅；`npm run test:unit` 里的 legal-docs-consistency 用例逐字比对两侧，
 * 任一侧改动而另一侧没跟上就红——避免「小程序改了、文档还是旧承诺」。
 *
 * 用法：
 *   node scripts/legal-docs.mjs           # 检查是否一致（不一致时打印差异并 rc=1）
 *   node scripts/legal-docs.mjs --write   # 由小程序常量重新生成 docs/legal/*.md
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const ROOT = fileURLToPath(new URL('..', import.meta.url))

export const LEGAL_DOCS = [
  {
    key: 'terms',
    doc: 'docs/legal/用户协议.md',
    page: 'apps/miniprogram/pages/agreement/agreement.js',
    file: 'apps/miniprogram/pages/agreement/agreement.wxml',
  },
  {
    key: 'privacy',
    doc: 'docs/legal/隐私政策.md',
    page: 'apps/miniprogram/pages/privacy/privacy.js',
    file: 'apps/miniprogram/pages/privacy/privacy.wxml',
  },
]

/** 在小程序 Page() 定义的沙箱里取 data.sections（不引入 wxml 渲染差异） */
export function extractSections(source) {
  let captured = null
  const sandbox = { Page: (def) => { captured = def } }
  // 小程序页面文件是仓库内静态常量、无 import 与副作用，只调用一次 Page({...})；
  // 用 vm 隔离作用域是为了正确处理正文里的 // 注释与字符串拼接，不做任何外部输入求值。
  vm.runInNewContext(source, sandbox, { timeout: 1000, filename: 'miniprogram-page.js' })
  if (!captured || !captured.data) throw new Error('未找到 Page({ data }) 定义')
  const { title, sections } = captured.data
  if (!title || !Array.isArray(sections) || !sections.length) throw new Error('data.title / data.sections 缺失')
  return { title, sections: sections.map((s) => ({ title: s.title, content: s.content })) }
}

export function renderMarkdown({ title, sections }, meta) {
  const head = [
    `# ${title}`,
    '',
    `> 单一来源：\`${meta.page}\`（V1.3 · FR-SUP-11）。`,
    '> 改文本请改小程序常量后运行 `node scripts/legal-docs.mjs --write` 重新生成本文件；',
    '> `npm run test:unit` 的 legal-docs-consistency 用例会逐字比对两侧，任一侧漂移即红。',
    '> 后台（admin-web）关于页不设政策入口，本目录仅供审阅与追溯（T02690 裁决）。',
    '',
  ]
  const body = []
  for (const s of sections) {
    body.push(`## ${s.title}`, '', s.content.trim(), '')
  }
  return head.concat(body).join('\n').replace(/\n{3,}/g, '\n\n').trimEnd() + '\n'
}

/** 把 md 反解成 { title, sections }：只认 `## ` 小节，正文取到下一个 `## ` 为止 */
export function parseMarkdown(text) {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const h1 = lines.find((l) => l.startsWith('# '))
  const sections = []
  let cur = null
  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (cur) sections.push({ title: cur.title, content: cur.lines.join('\n').trim() })
      cur = { title: line.slice(3).trim(), lines: [] }
    } else if (cur) {
      cur.lines.push(line)
    }
  }
  if (cur) sections.push({ title: cur.title, content: cur.lines.join('\n').trim() })
  return { title: h1 ? h1.slice(2).trim() : '', sections }
}

export function readDoc(rel) {
  return readFileSync(ROOT + rel, 'utf8')
}

/** 期望的 md 内容（由小程序常量渲染） */
export function buildDocs() {
  return LEGAL_DOCS.map((m) => {
    const src = readFileSync(ROOT + m.page, 'utf8')
    return { ...m, expected: renderMarkdown(extractSections(src), m) }
  })
}

/** 逐字比对：返回不一致项（空数组 = 一致） */
export function compareAll(built = buildDocs()) {
  const diffs = []
  for (const item of built) {
    let actual = ''
    try {
      actual = readDoc(item.doc)
    } catch {
      diffs.push({ doc: item.doc, reason: '文件不存在', expected: item.expected })
      continue
    }
    const a = parseMarkdown(actual)
    const e = parseMarkdown(item.expected)
    if (a.title !== e.title) diffs.push({ doc: item.doc, reason: `标题不一致：md「${a.title}」≠ 小程序「${e.title}」` })
    const at = a.sections.map((s) => s.title)
    const et = e.sections.map((s) => s.title)
    if (at.join('|') !== et.join('|')) {
      diffs.push({ doc: item.doc, reason: `小节不一致：md[${at.join('、')}] ≠ 小程序[${et.join('、')}]` })
    }
    for (const sec of e.sections) {
      const hit = a.sections.find((s) => s.title === sec.title)
      if (hit && hit.content !== sec.content) {
        diffs.push({ doc: item.doc, reason: `「${sec.title}」正文不一致` })
      }
    }
  }
  return diffs
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]
if (isMain) {
  const built = buildDocs()
  if (process.argv.includes('--write')) {
    for (const item of built) {
      const target = ROOT + item.doc
      mkdirSync(dirname(target), { recursive: true })
      writeFileSync(target, item.expected, 'utf8')
      console.log(`已写入 ${item.doc}（${item.expected.length} 字符）`)
    }
  } else {
    const diffs = compareAll(built)
    if (!diffs.length) {
      console.log(`政策文本一致：${built.length} 份文档与小程序常量逐字相同`)
    } else {
      for (const d of diffs) console.error(`✖ ${d.doc}：${d.reason}`)
      console.error('修复：node scripts/legal-docs.mjs --write')
      process.exit(1)
    }
  }
}
