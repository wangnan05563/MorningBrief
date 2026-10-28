/**
 * FR-UX-302 小程序侧门禁（T02534 / M3-D）：失败态必须与空态分成两支，且失败态自带重试
 *
 * 为什么只能静态守：这类缺陷运行时一个异常都不会抛——toast 一闪、页面落到「暂无××」，
 * 用户把「这次没取到」读成「确实没有」。评审的 7 条（J4/J11/J16/J38/J39/J47/J106）
 * 全部是这个形状，且分散在 8 个页面，靠人肉复查必然回潮。
 *
 * 判据（逐页）：
 *  1. wxml 有 <load-error>，且绑定 bind:retry="onRetryLoad" —— 失败态自带重试；
 *  2. 该元素的分支条件引用本页的错误字段（wx:if / wx:elif），而不是无条件的常显块；
 *  3. 同页 js 定义了 onRetryLoad，且方法体里真的重新发起取数（调本页的 loader）；
 *  4. 同页 js 的 catch 分支把错误写进该字段（只有 toast 不算）；
 *  5. 写错误的那个方法（catch 里写了该字段）必须同时清空该字段（`field: ''`）——
 *     否则重试成功之后失败态还挂在页面上。只数文件里出现了几次 `field: ''` 太松：
 *     同一个字段在别的入口也清，漏掉成功路径照样会绿。
 *  6. 全站禁止 `{{error || '…'}}` 这种「错误冒充空态标题」的写法（J4 的原形）；
 *  7. 页面仍保留独立的空态（empty-state 或「暂无/还没有/未找到」文案），
 *     防止「一刀切把空态删掉、全部报失败」的另一种撒谎。
 *
 * 局限（如实声明）：只做文本抽取与配对，不解析 WXML 语法树；分支先后顺序、
 * 同页多个 load-error 的具体落点不在能力范围内；动态绑定的 retry 值不检查。
 *
 * 运行：node apps/miniprogram/scripts/validate-error-vs-empty.mjs
 * 自测（证伪样本）：node --test apps/miniprogram/tests/validate-error-vs-empty.test.mjs
 */
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

/**
 * 逐页契约。field 是页面 data 里承载失败原文的字段；
 * reload 是失败态重试时应重新走的取数方法（允许有多个候选，命中其一即可）。
 */
const PAGES = [
  { page: 'pages/index/index', field: 'error', reload: ['initData', 'loadPreferred'], note: 'J4' },
  { page: 'pages/history/history', field: 'loadError', reload: ['loadHistory'], note: 'J16' },
  { page: 'pages/search/search', field: 'loadError', reload: ['doSearch'], note: 'J39' },
  { page: 'pages/channels/channels', field: 'loadError', reload: ['loadChannels'], note: 'J47' },
  { page: 'pages/course/course', field: 'error', reload: ['loadChapters'], note: 'J106' },
  { page: 'pages/recent/recent', field: 'loadError', reload: ['loadRecent'], note: 'J106' },
  { page: 'pages/favorites/favorites', field: 'loadError', reload: ['loadFavorites'], note: 'J106' },
  {
    page: 'pages/preferred-settings/preferred-settings',
    field: 'loadError',
    reload: ['loadChannels'],
    note: 'J106',
  },
  { page: 'pages/download/download', field: 'loadError', reload: ['refresh'], note: 'J106' },
]

/** 空态必须还在：组件形式或页面里自己写的 .empty-state + 「暂无/还没有/未找到」 */
const EMPTY_HINT_RE = /(?:<empty-state|class="[^"]*empty-state)|(?:暂无|还没有|未找到|尚未)/
/** J4 原形：把错误原文当空态标题用 */
const ERROR_AS_EMPTY_RE = /\{\{\s*(?:error|loadError)\s*\|\|/

const rel = (p, ext) => `${p}.${ext}`

function readAll(overrides) {
  const files = {}
  for (const { page } of PAGES) {
    for (const ext of ['js', 'wxml']) {
      const key = rel(page, ext)
      const fromOverride = overrides[key]
      files[key] = typeof fromOverride === 'string' ? fromOverride : readFileSync(join(ROOT, key), 'utf8')
    }
  }
  return files
}

/** 取某个方法体（两空格缩进定义 → 下一个同缩进定义之前）；找不到返回 '' */
function methodBody(src, name) {
  const start = src.search(new RegExp(`^ {2}(?:async )?${name}\\s*\\(`, 'm'))
  if (start < 0) return ''
  const rest = src.slice(start)
  const next = /\n {2}(?:async )?[A-Za-z_$][\w$]*\s*\(/.exec(rest.slice(1))
  return next ? rest.slice(0, next.index + 1) : rest
}

/** 取 <load-error ...> 开标签（到 `>` 为止；组件内没有嵌套的 >） */
function loadErrorTag(wxml) {
  const m = /<load-error\b[^>]*>/.exec(wxml)
  return m ? m[0] : ''
}

/** catch 块里写了哪些字段：`catch (e) { ... field: ... }`（粗粒度 600 字符窗口） */
function catchWritesField(js, field) {
  const re = new RegExp(`catch\\s*\\([^)]*\\)\\s*\\{[\\s\\S]{0,600}?\\b${field}\\s*:`, 'g')
  return re.test(js)
}

/**
 * 写错误的那个方法必须自己清空错误字段。
 * 只看文件级出现次数会漏：同一字段在别的方法里也清，成功路径漏了照样绿。
 */
function catchMethodClearsField(js, field) {
  const defs = [...js.matchAll(/^ {2}(?:async )?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{/gm)]
  for (const m of defs) {
    const body = methodBody(js, m[1])
    if (!/catch\s*\(/.test(body)) continue
    if (!catchWritesField(body, field)) continue
    if (!new RegExp(`\\b${field}\\s*:\\s*''`).test(body)) return false
  }
  return true
}

export function validate(overrides = {}) {
  const files = readAll(overrides)
  const errors = []
  const facts = []

  for (const { page, field, reload, note } of PAGES) {
    const wxml = files[rel(page, 'wxml')].replace(/<!--[\s\S]*?-->/g, '')
    const js = files[rel(page, 'js')]
    const tag = loadErrorTag(wxml)

    if (!tag) {
      errors.push(`${page}.wxml 没有 <load-error>：失败仍会落到空态（${note}）`)
      continue
    }
    if (!/bind:?retry="onRetryLoad"/.test(tag)) {
      errors.push(`${page}.wxml 的 <load-error> 没绑 bind:retry="onRetryLoad"：失败态不自带重试（${note}）`)
    }
    const cond = /wx:(?:if|elif)="\{\{([^}]*)\}\}"/.exec(tag)
    if (!cond) {
      errors.push(`${page}.wxml 的 <load-error> 没有 wx:if / wx:elif 条件：会与列表/空态同时出现（${note}）`)
    } else if (!new RegExp(`\\b${field}\\b`).test(cond[1])) {
      errors.push(`${page}.wxml 的 <load-error> 条件没引用 ${field}：失败态与页面状态对不上（${note}）`)
    }

    const retryBody = methodBody(js, 'onRetryLoad')
    if (!retryBody) {
      errors.push(`${page}.js 没有 onRetryLoad：模板重试按钮点了没反应（${note}）`)
    } else if (!reload.some((fn) => new RegExp(`this\\.${fn}\\s*\\(`).test(retryBody))) {
      errors.push(`${page}.js 的 onRetryLoad 没有重新取数（期望调用 ${reload.join(' / ')}）（${note}）`)
    }

    if (!catchWritesField(js, field)) {
      errors.push(`${page}.js 的 catch 分支没写 ${field}：失败只 toast，界面照样落到空态（${note}）`)
    }

    const cleared = (js.match(new RegExp(`\\b${field}\\s*:\\s*''`, 'g')) || []).length
    if (cleared < 1) {
      errors.push(`${page}.js 从不清空 ${field}：一次失败后这个页面再也回不到正常态（${note}）`)
    } else if (!catchMethodClearsField(js, field)) {
      errors.push(`${page}.js 写 ${field} 的那个方法没有在成功路径清空它：重试成功后失败态还挂着（${note}）`)
    }

    if (!EMPTY_HINT_RE.test(wxml)) {
      errors.push(`${page}.wxml 找不到独立空态：把「没有内容」也一起报成失败同样不诚实（${note}）`)
    }

    facts.push(`${page}: ${field} → onRetryLoad(${reload.join('|')})`)
  }

  // J4 原形：错误原文当空态标题（跨页全量禁用）
  for (const { page } of PAGES) {
    const wxml = files[rel(page, 'wxml')].replace(/<!--[\s\S]*?-->/g, '')
    if (ERROR_AS_EMPTY_RE.test(wxml)) {
      errors.push(`${page}.wxml 用 {{error || …}} 当空态文案：网络异常又被说成「内容没有」（J4 原形）`)
    }
  }

  return { errors, facts }
}

const isCli = process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href
if (isCli) {
  const { errors, facts } = validate()
  if (errors.length) {
    for (const e of errors) console.error(`  ✗ ${e}`)
    console.error(`[validate-error-vs-empty] ${errors.length} 项不一致`)
    process.exit(1)
  }
  for (const f of facts) console.log(`  ✓ ${f}`)
  console.log(`[validate-error-vs-empty] 通过（${PAGES.length} 页：失败态/空态分家 + 失败态自带重试）`)
}
