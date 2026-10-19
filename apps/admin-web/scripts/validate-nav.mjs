/**
 * 导航一致性构建期校验（T02500 / FR-UX-401）
 *
 * 校验的是「引用指向是否存在」，不是内容好不好：
 * - 引导步骤（GUIDE_STEPS）的路由键与 `[aria-label="…"]` 选择器必须命中真实路由/真实标签；
 * - 引导步骤的锚点契约（T02502）：每步只允许一个选择器，且必须是视图里显式存在的
 *   `[data-guide="x"]` / `[aria-label="x"]`——多选择器兜底链与裸类选择器一律报错；
 * - 帮助文档里「进入「X」」这类菜单指引必须对应真实存在的菜单项；
 * - 侧栏分组（groupConfig）与路由 meta.group 必须互相闭合；
 * - 移动端手写的 tab / 管理入口 `to` 必须能匹配到真实路由；
 * - 菜单项必须有 title 与 icon，且图标名真实存在（图标名写错是静默不渲染，不会报错）；
 * - 关于页不得残留 `example.com` 占位外链（T02503 / FR-UX-404）：只查链接位置
 *   （`href=` / `href:` / `window.open(`），输入框示例值与正文说明不算；
 * - 关于页开源清单的版本号必须与 `package.json` / `backend/requirements.txt` 逐条对上——
 *   手抄清单一定漂移（M101：漂移的清单比没有清单更误导）；
 * - 枚举字典（T02504 / FR-UX-405）：`src/constants/enums.js` 的键集合必须与
 *   `backend/app/models` 里的 `class X(str, Enum)` 成员逐值对上（双向），且页面里不得再
 *   出现同一枚举的第二份「值 → 文案」映射——四份映射必然漂成四种说法，移动端还抄过
 *   一个后端根本不存在的值，于是状态直接漏出英文原值。
 *
 * 之所以是构建期而不是运行时：这些错全部发生在「文案/选择器」层面，运行时只会表现为
 * 引导气泡指错元素、帮助文档把人带不到页面、菜单少一项——用户说不清、测试也测不出。
 *
 * 实现取向：只做静态文本抽取（正则 + 括号配对），不引 Vue 编译器、不引第三方解析依赖。
 * 代价是「只取数组字面量起始的那一段」——这也是现有代码的写法（数组均为静态字面量）。
 * 动态绑定的 label（`:label="…"`）无法静态校验，明确跳过、不假装查过。
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const SRC = resolve(dirname(fileURLToPath(import.meta.url)), '../src')

const read = (rel) => readFileSync(join(SRC, rel), 'utf8')

/** 从 `from` 处的 `[`/`{` 开始做括号配对（跳过字符串内的括号），返回字面量文本 */
function literalAt(text, from) {
  const open = text[from]
  const close = open === '[' ? ']' : '}'
  let depth = 0
  let quote = null
  for (let i = from; i < text.length; i += 1) {
    const ch = text[i]
    if (quote) {
      if (ch === '\\') i += 1
      else if (ch === quote) quote = null
      continue
    }
    if (ch === '"' || ch === "'" || ch === '`') quote = ch
    else if (ch === open) depth += 1
    else if (ch === close) {
      depth -= 1
      if (depth === 0) return text.slice(from, i + 1)
    }
  }
  throw new Error(`括号未配对：起始偏移 ${from}`)
}

function walk(dir, acc = [], exts = ['.vue']) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) walk(p, acc, exts)
    else if (exts.some((e) => name.endsWith(e))) acc.push(p)
  }
  return acc
}

/** 取 `<script>` 段（.vue 的 template/style 里的大括号是 CSS 与插值，扫它们只会造误报） */
function scriptPart(text) {
  const m = /<script[^>]*>([\s\S]*?)<\/script>/.exec(text)
  return m ? m[1] : text
}

/**
 * 取对象字面量的「顶层键」：跳过字符串内的括号，只认深度 1 的 `key:`。
 * 返回 `[{ key, stringValue, objectValue }]`——`stringValue` 用于区分「枚举 → 文案」映射
 * （值是字符串）与计数/结果对象（值是数字）；`objectValue` 认字典自己的写法
 * （`{ queued: { label: '排队中', type: 'info' } }`），页面里抄这种映射同样会漂。
 */
function topLevelKeys(literal) {
  const out = []
  let depth = 0
  let quote = null
  for (let i = 0; i < literal.length; i += 1) {
    const ch = literal[i]
    if (quote) {
      if (ch === '\\') i += 1
      else if (ch === quote) quote = null
      continue
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      quote = ch
      continue
    }
    if (ch === '{' || ch === '[' || ch === '(') {
      depth += 1
      continue
    }
    if (ch === '}' || ch === ']' || ch === ')') {
      depth -= 1
      continue
    }
    if (depth === 1 && /[A-Za-z_$]/.test(ch)) {
      const word = /^[A-Za-z_$][\w$]*/.exec(literal.slice(i))[0]
      const rest = /^\s*:\s*/.exec(literal.slice(i + word.length))
      if (rest) {
        const valueStart = i + word.length + rest[0].length
        const next = literal[valueStart]
        out.push({ key: word, stringValue: /["'`]/.test(next), objectValue: next === '{' })
      }
      i += word.length - 1
    }
  }
  return out
}

/** 收集组件标签块：`<IconButton ... label="新增频道" ...>` 里的静态属性 */
function tagBlocks(text, tagName) {
  const out = []
  const re = new RegExp(`<${tagName}(?=[\\s>/])`, 'g')
  let m
  while ((m = re.exec(text))) {
    const start = m.index
    let quote = null
    for (let i = start; i < text.length; i += 1) {
      const ch = text[i]
      if (quote) {
        if (ch === '\\') i += 1
        else if (ch === quote) quote = null
        continue
      }
      if (ch === '"' || ch === "'" || ch === '`') quote = ch
      // 属性值里的 `>`（如 `@click="(n) => x(n)"`）不算标签结束，靠 quote 状态跳过
      else if (ch === '>') {
        out.push(text.slice(start, i + 1))
        break
      }
    }
  }
  return out
}

function attrValue(block, attr) {
  const m = new RegExp(`(?:^|\\s)${attr}="([^"]*)"`).exec(block)
  return m ? m[1] : null
}

/**
 * 从路由源码里取 routes 数组的字面量文本（不执行、不 eval：
 * `component: () => import('...')` 一旦被求值就会真去解析模块，纯静态扫描更安全也更省事）。
 */
function routesLiteralText() {
  const text = read('router/index.js')
  const head = 'const routes = ['
  return literalAt(text, text.indexOf(head) + head.length - 1)
}

/** 解析 `meta: { title: 'x', hidden: true }`：只认字符串与布尔字面量 */
function readMeta(entryBody) {
  const i = entryBody.indexOf('meta:')
  if (i < 0) return {}
  const brace = entryBody.indexOf('{', i)
  if (brace < 0) return {}
  const literal = literalAt(entryBody, brace)
  const meta = {}
  for (const m of literal.matchAll(/(\w+):\s*'([^']*)'|(\w+):\s*(true|false)/g)) {
    if (m[1]) meta[m[1]] = m[2]
    else meta[m[3]] = m[4] === 'true'
  }
  return meta
}

/**
 * 展开路由表：本项目的 routes 只有两层（顶层 + 一个 children 数组），
 * 子路径一律相对父路径。按源码顺序扫描：遇到「带 children 的绝对路径」就切换父路径。
 */
function collectRoutes(literal) {
  const marks = [...literal.matchAll(/path:\s*'([^']+)'/g)]
  const out = []
  let parent = ''
  for (let i = 0; i < marks.length; i += 1) {
    const start = marks[i].index
    const end = i + 1 < marks.length ? marks[i + 1].index : literal.length
    const body = literal.slice(start, end)
    const raw = marks[i][1]
    const path = raw.startsWith('/') ? raw : `${parent.replace(/\/$/, '')}/${raw}`
    if (raw.startsWith('/') && /children:\s*\[/.test(body)) parent = raw
    out.push({ path, meta: readMeta(body) })
  }
  return out
}

/**
 * 路由文件头部的「菜单分组」注释里列出的分组名。
 * 注释本身是给人看的，但它一旦被改（加菜单忘了同步注释）就成了误导——所以也纳入校验。
 * 只取缩进的条目行（`*   分组名  - …`），说明行（`* 文字`）不算。
 */
function groupNamesInHeaderComment(routerText) {
  const start = routerText.indexOf('菜单分组')
  if (start < 0) return []
  const block = routerText.slice(start, routerText.indexOf('*/', start))
  return [...block.matchAll(/^\s*\*\s{2,}(\S.*?)\s*-\s/gm)].map((m) => m[1].trim())
}

/**
 * 占位外链检测（T02503 / FR-UX-404 / ACC-UX-401）。
 *
 * 只匹配「链接位置」：模板里的 `href="…"`、对象里的 `href: '…'`、`window.open('…')`。
 * 输入框的 `placeholder="https://cdn.example.com"`、帮助正文里的示例域名是合法用法，
 * 因此不做全文 grep——全文匹配会在 CosConfig / Tunnel / Notification / Help 里全是误报，
 * 误报的门禁等于没有门禁。
 */
const PLACEHOLDER_PATTERNS = [
  /href\s*=\s*"[^"]*example\.com[^"]*"/gi,
  /href\s*:\s*['"][^'"]*example\.com[^'"]*['"]/gi,
  /window\.open\(\s*['"][^'"]*example\.com/gi,
]

function collectPlaceholderLinks() {
  const out = []
  for (const file of walk(SRC, [], ['.vue', '.js'])) {
    const rel = file.slice(SRC.length + 1).replace(/\\/g, '/')
    const text = readFileSync(file, 'utf8')
    for (const re of PLACEHOLDER_PATTERNS) {
      for (const m of text.matchAll(re)) out.push({ from: rel, text: m[0].slice(0, 90) })
    }
  }
  return out
}

/**
 * 前端枚举字典（src/constants/enums.js，T02504 / FR-UX-405）。
 * 解析不出来时返回 null（前端单独构建、字典文件尚未创建的场景），对账改为跳过并说明。
 */
function readEnumDictionary() {
  let text
  try {
    text = read('constants/enums.js')
  } catch {
    return null
  }
  const dicts = new Map()
  let backendOf = new Map()
  for (const m of text.matchAll(/export const ([A-Z][\w]*)\s*=\s*\{/g)) {
    const literal = literalAt(text, text.indexOf('{', m.index))
    const keys = topLevelKeys(literal).map((e) => e.key)
    if (m[1] === 'BACKEND_ENUM_OF') {
      backendOf = new Map(
        [...literal.matchAll(/([A-Z][\w]*):\s*(?:'([^']+)'|null)/g)].map((x) => [x[1], x[2] ?? null]),
      )
      continue
    }
    if (keys.length) dicts.set(m[1], keys)
  }
  return { dicts, backendOf }
}

/**
 * 后端模型里的枚举定义：`class WorkflowStatus(str, Enum):` 下的 `queued = "queued"` 成员。
 * 读不到 backend（脱离 monorepo 单独构建前端）时返回 null，跳过比对而不是失败。
 */
function readBackendEnums() {
  const dir = resolve(SRC, '../../../backend/app/models')
  let files
  try {
    files = walk(dir, [], ['.py'])
  } catch {
    return null
  }
  const out = new Map()
  for (const file of files) {
    let current = null
    for (const line of readFileSync(file, 'utf8').split(/\r?\n/)) {
      const cls = /^class\s+(\w+)\s*\([^)]*Enum[^)]*\):/.exec(line)
      if (cls) {
        current = cls[1]
        out.set(current, [])
        continue
      }
      if (current === null) continue
      if (/^\S/.test(line)) {
        current = null
        continue
      }
      const member = /^\s{4}(\w+)\s*=\s*"([^"]+)"/.exec(line)
      if (member) out.get(current).push(member[2])
    }
  }
  return out
}

/**
 * 枚举映射重复声明检测（T02504 / FR-UX-405）。
 *
 * 「后端枚举 → 前端文案」一旦被抄第二份，两份必然漂移——本仓库里同一个 WorkflowStatus
 * 曾有 4 份映射（成功/已完成、运行中/执行中、排队中/等待中），移动端还抄了个后端
 * 根本不存在的 `finished`，于是已完成任务在手机上直接漏出英文原值。
 * 这两类形态都只靠人眼是查不出来的（文案对不上不是报错），所以做成构建期门禁：
 * - 键集合 ⊂ 某枚举值集（≥2 个键）→ 重复声明，必须 import 字典；值写成字符串
 *   （`{ queued: '排队中' }`）或对象（`{ queued: { label, type } }`）都算——后者正是字典
 *   自己的形状，WorkflowDetail 曾这样抄过第二份素材状态，与素材库页漂成两套文案；
 * - ≥3 个键命中某枚举、且只有 1 个键不在值集里 → 该键是幻影值，永远不会命中。
 * 只扫 `<script>` 段：CSS 与模板插值里的大括号造误报，误报的门禁等于没有门禁。
 */
const ENUM_DUP_MIN_KEYS = 2
const ENUM_PHANTOM_MIN_HITS = 3
const ENUM_PHANTOM_MAX_UNKNOWN = 1

export function collectEnumDuplicates(dicts, srcDir = SRC) {
  const dupes = []
  const phantoms = []
  const entries = [...dicts.entries()].map(([name, keys]) => [name, new Set(keys)])
  for (const file of walk(srcDir, [], ['.vue', '.js'])) {
    const rel = file.slice(srcDir.length + 1).replace(/\\/g, '/')
    if (rel === 'constants/enums.js') continue
    const raw = readFileSync(file, 'utf8')
    const text = scriptPart(raw)
    // 报错里的行号要能直接跳进 .vue，所以补回「<script> 之前的行数」
    const tag = /<script[^>]*>/.exec(raw)
    const lineOffset = tag && tag.index > 0 ? raw.slice(0, tag.index + tag[0].length).split('\n').length - 1 : 0
    for (let i = text.indexOf('{'); i >= 0; i = text.indexOf('{', i + 1)) {
      let literal
      try {
        literal = literalAt(text, i)
      } catch {
        continue
      }
      const entries0 = topLevelKeys(literal)
      // 只把「键 → 字符串」或「键 → 对象」的映射当候选：`{ success: 3, failed: 1 }`
      // 这类计数对象不是枚举映射（误报的门禁等于没有门禁）
      if (!entries0.length || !entries0.every((e) => e.stringValue || e.objectValue)) continue
      const keys = entries0.map((e) => e.key)
      if (keys.length < ENUM_DUP_MIN_KEYS) continue
      for (const [name, values] of entries) {
        const known = keys.filter((k) => values.has(k))
        const unknown = keys.filter((k) => !values.has(k))
        if (!known.length) continue
        const where = `${rel}:${lineOffset + text.slice(0, i).split('\n').length}`
        if (!unknown.length && known.length >= ENUM_DUP_MIN_KEYS) {
          dupes.push({ name, where, keys: known })
        } else if (
          unknown.length <= ENUM_PHANTOM_MAX_UNKNOWN &&
          known.length >= ENUM_PHANTOM_MIN_HITS
        ) {
          phantoms.push({ name, where, keys: unknown })
        }
      }
    }
  }
  return { dupes, phantoms }
}

/** 关于页开源清单：`{ name: 'x', version: '1.2.3', … }` 的字面量条目 */
function readLicenseTable(aboutText) {
  const head = 'const licenses = ['
  const i = aboutText.indexOf(head)
  if (i < 0) return []
  const literal = literalAt(aboutText, i + head.length - 1)
  return [...literal.matchAll(/\{\s*name:\s*'([^']+)',\s*version:\s*'([^']+)'/g)].map((m) => ({
    name: m[1],
    version: m[2],
  }))
}

/** npm 清单：dependencies + devDependencies（关于页那张表按这两段列前端依赖） */
function readNpmManifest() {
  const pkgPath = resolve(SRC, '../package.json')
  const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'))
  return { ...pkg.dependencies, ...pkg.devDependencies }
}

/** PEP 503 名字归一：大小写与 `_`/`-` 混用在 PyPI 里等价（PyMuPDF ↔ pymupdf） */
function normPyName(name) {
  return name.toLowerCase().replace(/_/g, '-')
}

/**
 * 后端清单：`backend/requirements.txt` 的 `name[extras]==pin` 行。
 *
 * 读不到时返回 null——本门禁跑在 admin-web 的构建里，脱离 monorepo（单独打包前端、
 * 只做前端 CI）时不应该因为「对账不了后端」直接构建失败，改为在输出里说明。
 */
function readPyManifest() {
  const reqPath = resolve(SRC, '../../../backend/requirements.txt')
  let text
  try {
    text = readFileSync(reqPath, 'utf8')
  } catch {
    return null
  }
  const pins = new Map()
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/#.*$/, '').trim()
    const m = /^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?==([A-Za-z0-9][A-Za-z0-9.\-_]*)/.exec(line)
    if (m) pins.set(normPyName(m[1]), { name: m[1], version: m[2] })
  }
  return pins
}

/** semver range → 版本主体（`^1.2.0` / `~1.2` / `>=1.2.0` 都去掉前置操作符再比） */
function versionCore(v) {
  return String(v).replace(/^[\^~>=<]+/, '').replace(/^v/, '').replace(/\.+$/, '')
}

export async function collectFacts() {
  const routerText = read('router/index.js')
  const routes = collectRoutes(routesLiteralText())

  const guideModule = await import(pathToFileURL(join(SRC, 'guide/guideConfig.js')).href)
  const guideSteps = guideModule.GUIDE_STEPS

  const layoutText = read('layouts/Layout.vue')
  const groupConfigLiteral = literalAt(
    layoutText,
    layoutText.indexOf('const groupConfig = [') + 'const groupConfig = '.length,
  )
  const groups = []
  for (const m of groupConfigLiteral.matchAll(/\{\s*name:\s*'([^']+)',\s*icon:\s*'([^']+)'\s*\}/g)) {
    groups.push({ name: m[1], icon: m[2] })
  }

  const ariaLabels = new Set()
  const dataGuides = new Set()
  for (const file of walk(SRC)) {
    const text = readFileSync(file, 'utf8')
    for (const m of text.matchAll(/[\s"]aria-label="([^"{]+)"/g)) ariaLabels.add(m[1])
    for (const m of text.matchAll(/data-guide="([^"{]+)"/g)) dataGuides.add(m[1])
    for (const block of tagBlocks(text, 'IconButton')) {
      const label = attrValue(block, 'label')
      if (label && !label.includes('${')) ariaLabels.add(label)
    }
  }

  const helpText = read('views/help/Help.vue')
  const helpLiteral = literalAt(helpText, helpText.indexOf('const docSections = [') + 'const docSections = '.length)
  const helpIds = [...helpLiteral.matchAll(/^\s*id:\s*'([^']+)'/gm)].map((m) => m[1])
  // 只把「像菜单指引」的「」当作菜单引用：`进入「X」`、`侧边栏「X」`，或 `「X」页面`。
  // 帮助文档里大量「X」是按钮/弹窗名（「审核通过」「驳回」「重试」），按菜单口径校验会全是误报。
  const menuRefs = [
    ...helpText.matchAll(/(?:侧边栏|进入|打开|切换到|位于)\s*「([^」]+)」/g),
    ...helpText.matchAll(/「([^」]+)」\s*页面/g),
  ].map((m) => m[1])

  const mobileTargets = []
  for (const rel of ['layouts/MobileLayout.vue', 'views/mobile/ManageHome.vue']) {
    const text = read(rel)
    for (const m of text.matchAll(/to:\s*['"]([^'"]+)['"]/g)) mobileTargets.push({ from: rel, to: m[1] })
  }

  const aboutText = read('views/about/About.vue')
  const aboutHrefs = [...aboutText.matchAll(/href:\s*'([^']+)'/g)]
    .map((m) => m[1])
    .filter((h) => h.startsWith('/') && !h.startsWith('/docs'))

  const dependencyTable = readLicenseTable(aboutText)
  const npmManifest = readNpmManifest()
  const pyManifest = readPyManifest()

  const enumDictionary = readEnumDictionary()
  const backendEnums = readBackendEnums()
  const enumDuplicates = enumDictionary ? collectEnumDuplicates(enumDictionary.dicts) : null

  return {
    routes,
    guideSteps,
    groups,
    ariaLabels,
    dataGuides,
    helpIds,
    menuRefs,
    mobileTargets,
    aboutHrefs,
    commentGroups: groupNamesInHeaderComment(routerText),
    placeholderLinks: collectPlaceholderLinks(),
    dependencyTable,
    npmManifest,
    pyManifest,
    enumDictionary,
    backendEnums,
    enumDuplicates,
  }
}

function matchRoute(routes, path) {
  const want = path.split('/')
  return routes.some((r) => {
    if (!r.path.includes(':')) return r.path === path
    const seg = r.path.split('/')
    if (seg.length !== want.length) return false
    return seg.every((s, i) => s.startsWith(':') || s === want[i])
  })
}

/**
 * 锚点契约（T02502）：一个引导步骤选择器 → 错误说明（无错返回 null）。
 *
 * 判据只有一条：选择器必须「自己就能说明指哪个元素」。
 * - `[data-guide="x"]` / `[aria-label="x"]`：显式锚点，视图里存在才算数；
 * - 含空格/组合符的选择器（`.top-bar .el-button`）：位置兜底。真实锚点缺失时它会静默
 *   命中另一个元素——T02500 的「引导指错元素」正是这样藏住的，比落空更坏；
 * - 裸类：允许全页唯一的布局/组件根类（下面的清单），其余（`.el-table`、`.el-tabs`、
 *   各视图自己的 `.xxx-page`）可能命中错误实例或随重构漂移，必须打 data-guide。
 * 兜底链（一步写多个选择器）同样禁止：宁可这一步落空（浮层带 data-guide-missing，
 * 门禁与运行时审计都能发现），也不要指错。
 */
const PAGE_UNIQUE_CLASSES = new Set(['.page-container', '.el-upload'])

function anchorProblem(sel, path, f) {
  const guide = /^\[data-guide="([^"]+)"\]$/.exec(sel)
  if (guide) {
    return f.dataGuides.has(guide[1])
      ? null
      : `引导步骤选择了视图里不存在的锚点：${path} → ${sel}；没有任何元素带 data-guide="${guide[1]}"（视图重构时锚点被删/改名），气泡会落空居中`
  }
  const aria = /^\[aria-label="([^"]+)"\]$/.exec(sel)
  if (aria) {
    return f.ariaLabels.has(aria[1])
      ? null
      : `引导步骤选择了不存在的 aria-label：${path} → ${sel}；页面上没有任何元素带这个标签，气泡会退到通用容器并指错元素`
  }
  if (/[\s>]/.test(sel)) {
    return `引导步骤禁止位置兜底：${path} → ${sel}；组合选择器会在真实锚点缺失时静默命中另一个元素（T02500 抓到的缺陷形态），请给目标元素打 data-guide`
  }
  if (PAGE_UNIQUE_CLASSES.has(sel)) return null
  return `引导步骤禁止未打显式锚点的裸类：${path} → ${sel}；该类的实例数不受约束（同页可能有多个），请给目标元素打 data-guide`
}

/**
 * 依赖清单对账（T02503 / FR-UX-404）：关于页那张手抄的开源声明表 ↔ 两份真实清单。
 *
 * 三个漂移方向都要报，缺一个就等于没对账：
 * - 表里有、清单里没有 → 依赖早已移除，用户却以为系统带了它（还捎带着许可声明是假的）；
 * - 清单里有、表里没有 → 新增依赖忘了声明，合规清单少了实际在分发的包；
 * - 两边都有但版本不同 → 表是旧的（这一类最常见：升级只改清单，没人回头改表）。
 * `requirements.txt` 读不到时只跳过对后端依赖的判定，不失败——前端单独构建的环境里
 * 「无法对账」不是错误，谎报「依赖已移除」才是错误。
 */
function checkDependencies(f) {
  const errors = []
  const table = f.dependencyTable
  if (!table) return { errors, skipped: true } // 调用方没给这一项（例如只校验导航的测试夹具）
  const npm = f.npmManifest ?? {}
  const py = f.pyManifest instanceof Map ? f.pyManifest : null
  if (!table.length) {
    return { errors: ['关于页开源清单（licenses）解析为空：数组写法被改动，门禁无法逐条对账'], skipped: false }
  }

  const byName = new Map()
  for (const row of table) {
    const key = normPyName(row.name)
    if (byName.has(key)) errors.push(`关于页开源清单重复列出 ${row.name}：同一依赖出现两次，Modal 会显示两条`)
    else byName.set(key, row)
  }

  for (const row of table) {
    const key = normPyName(row.name)
    const npmRange = Object.prototype.hasOwnProperty.call(npm, row.name) ? npm[row.name] : null
    const pyPin = py?.get(key)?.version ?? null
    if (npmRange === null && pyPin === null) {
      if (py === null) continue // 后端清单不可用时无法判定后端依赖
      errors.push(
        `关于页开源清单列了 ${row.name}（${row.version}），但 package.json 与 backend/requirements.txt 都没有：` +
          `依赖已移除/改名而清单没删，用户会看到不存在的开源声明`,
      )
      continue
    }
    const listed = versionCore(row.version)
    const actual = npmRange !== null ? versionCore(npmRange) : versionCore(pyPin)
    const source = npmRange !== null ? 'package.json' : 'backend/requirements.txt'
    if (listed !== actual) {
      errors.push(
        `关于页开源清单的 ${row.name} 版本是 ${row.version}，但 ${source} 里是 ${npmRange !== null ? npmRange : pyPin}：` +
          `手抄清单与真实依赖漂移（升版本时只改了清单）`,
      )
    }
  }

  for (const name of Object.keys(npm)) {
    if (!byName.has(normPyName(name))) {
      errors.push(`package.json 依赖 ${name}（${npm[name]}）没有列入关于页开源清单：新增依赖忘了同步合规声明`)
    }
  }
  if (py) {
    for (const [key, pin] of py) {
      if (!byName.has(key)) {
        errors.push(`backend/requirements.txt 依赖 ${pin.name}（${pin.version}）没有列入关于页开源清单`)
      }
    }
  }
  return { errors, skipped: false }
}

/**
 * 枚举对账（T02504 / FR-UX-405）：字典 ↔ 后端模型 ↔ 页面里的重复映射。
 * 后端模型读不到时跳过值集比对（脱离 monorepo 的前端构建），重复映射检测照做。
 */
export function checkEnums(f) {
  const errors = []
  const dict = f.enumDictionary
  if (!dict) return { errors, skipped: true }
  const backend = f.backendEnums
  for (const [name, values] of dict.dicts) {
    const cls = dict.backendOf.get(name)
    if (!cls || !backend) continue
    const defined = backend.get(cls)
    if (!defined) {
      errors.push(
        `枚举字典 ${name} 声明对应后端枚举 ${cls}，但在 backend/app/models 里找不到该定义：` +
          `枚举已改名/删除，字典是过期的`,
      )
      continue
    }
    const missing = defined.filter((v) => !values.includes(v))
    const extra = values.filter((v) => !defined.includes(v))
    if (missing.length) {
      errors.push(
        `枚举字典 ${name} 缺少后端 ${cls} 的值：${missing.join('、')}；` +
          `后端能返回这些值，页面上会直接漏出英文原值（FR-UX-405「填了不显示」）`,
      )
    }
    if (extra.length) {
      errors.push(`枚举字典 ${name} 列了后端 ${cls} 没有的值：${extra.join('、')}；这条映射永远不会命中`)
    }
  }
  for (const d of f.enumDuplicates?.dupes ?? []) {
    errors.push(
      `${d.where} 重复声明了 ${d.name} 的映射（${d.keys.join('、')}）；` +
        `同一枚举两处文案必然漂移，请改为 import src/constants/enums.js（T02504 / FR-UX-405）`,
    )
  }
  for (const p of f.enumDuplicates?.phantoms ?? []) {
    errors.push(
      `${p.where} 的映射含 ${p.name} 里不存在的值：${p.keys.join('、')}；` +
        `后端不会返回它，这些分支永远走不到，而对应的真实值会漏出英文原值（T02504）`,
    )
  }
  return { errors, skipped: false, backendSkipped: !backend }
}

export function checkFacts(f) {
  const errors = []
  const menuTitles = new Set(f.routes.map((r) => r.meta.title).filter(Boolean))
  const groupNames = new Set(f.groups.map((g) => g.name))

  for (const [path, steps] of Object.entries(f.guideSteps)) {
    if (!matchRoute(f.routes, path)) {
      errors.push(`引导配置的路由不存在：GUIDE_STEPS['${path}']`)
    }
    for (const step of steps || []) {
      const selectors = step.s || []
      if (selectors.length > 1) {
        errors.push(
          `引导步骤一步只允许一个选择器：${path} → ${selectors.join(' , ')}（标题「${step.t}」）；` +
            `多选择器兜底链让上一步的错指被下一步掩盖`,
        )
      }
      for (const sel of selectors) {
        const problem = anchorProblem(sel, path, f)
        if (problem) errors.push(`${problem}（标题「${step.t}」）`)
      }
    }
  }

  for (const ref of f.menuRefs) {
    if (!menuTitles.has(ref) && !groupNames.has(ref)) {
      errors.push(`帮助文档指向不存在的菜单：「${ref}」（既不是路由标题也不是分组名）`)
    }
  }

  for (const t of f.mobileTargets) {
    if (!matchRoute(f.routes, t.to)) errors.push(`移动端入口指向不存在的路由：${t.from} → ${t.to}`)
  }

  for (const h of f.aboutHrefs) {
    if (!matchRoute(f.routes, h)) errors.push(`关于页菜单项指向不存在的路由：${h}`)
  }

  for (const p of f.placeholderLinks ?? []) {
    errors.push(
      `占位外链残留在链接位置：${p.from} → ${p.text}；` +
        `example.com 会原样出厂，用户点开的是与自己无关的保留域名（FR-UX-404）`,
    )
  }

  const visible = f.routes.filter((r) => r.meta.group && !r.meta.hidden)
  for (const r of visible) {
    if (!groupNames.has(r.meta.group)) {
      errors.push(`路由 meta.group「${r.meta.group}」没有对应分组配置（${r.path}）：该菜单项不会出现在侧栏`)
    }
  }
  for (const g of f.groups) {
    if (!visible.some((r) => r.meta.group === g.name)) {
      errors.push(`分组「${g.name}」下没有任何可见菜单项：侧栏会显示空分组头`)
    }
  }
  // 分组注释与 meta.group 同步：注释多/少一个分组，读代码的人就会以为菜单存在或漏配
  const missingInComment = f.groups.map((g) => g.name).filter((n) => !f.commentGroups.includes(n))
  const extraInComment = f.commentGroups.filter((n) => !groupNames.has(n))
  if (missingInComment.length) errors.push(`路由头部「菜单分组」注释缺少分组：${missingInComment.join('、')}`)
  if (extraInComment.length) errors.push(`路由头部「菜单分组」注释列出不存在的分组：${extraInComment.join('、')}`)
  for (const r of f.routes.filter((x) => !x.meta.hidden && x.meta.title && x.path !== '/')) {
    if (r.path.startsWith('/m')) continue
    if (!r.meta.group) errors.push(`路由 ${r.path} 有标题但没有 meta.group：无法归入侧栏分组`)
    if (!r.meta.icon && !r.meta.hidden) {
      errors.push(`路由 ${r.path}（${r.meta.title}）没有 meta.icon：菜单项图标为空`)
    }
  }

  const iconNames = new Set()
  for (const r of f.routes) if (r.meta.icon) iconNames.add(r.meta.icon)
  for (const g of f.groups) iconNames.add(g.icon)

  const dep = checkDependencies(f)
  errors.push(...dep.errors)

  const enumResult = checkEnums(f)
  errors.push(...enumResult.errors)

  return {
    errors,
    iconNames: [...iconNames],
    depsSkipped: !!dep.skipped,
    enumsSkipped: !!enumResult.skipped,
    enumBackendSkipped: !!enumResult.backendSkipped,
  }
}

/** Element Plus 图标名校验：包体积大（>1000 个组件），只在显式请求时加载 */
async function checkIconNames(iconNames) {
  const errors = []
  try {
    const mod = await import('@element-plus/icons-vue')
    const known = new Set(Object.keys(mod))
    for (const name of iconNames) if (!known.has(name)) errors.push(`图标名不存在于 @element-plus/icons-vue：${name}`)
  } catch {
    // 离线环境可能加载不了整包；图标项不是本单主口径，跳过并在输出里说明
    return { skipped: true }
  }
  return { errors, skipped: false }
}

export async function validate({ includeIcons = false } = {}) {
  const facts = await collectFacts()
  const { errors, iconNames, depsSkipped, enumsSkipped, enumBackendSkipped } = checkFacts(facts)
  const iconResult = includeIcons ? await checkIconNames(iconNames) : { errors: [], skipped: true }
  return {
    facts,
    errors,
    iconErrors: iconResult.errors,
    iconsSkipped: iconResult.skipped,
    depsSkipped,
    enumsSkipped,
    enumBackendSkipped,
  }
}

const isCli = process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href
if (isCli) {
  const includeIcons = process.argv.includes('--icons')
  const {
    errors,
    iconErrors,
    iconsSkipped,
    depsSkipped,
    enumsSkipped,
    enumBackendSkipped,
    facts,
  } = await validate({ includeIcons })
  const all = [...errors, ...iconErrors]
  const py = facts.pyManifest
  const enumCount = facts.enumDictionary?.dicts.size ?? 0
  console.log(
    `[validate-nav] 路由 ${facts.routes.length} 条 · 引导 ${Object.keys(facts.guideSteps).length} 页 · ` +
      `aria-label ${facts.ariaLabels.size} 个 · 分组 ${facts.groups.length} 个 · 帮助章节 ${facts.helpIds.length} 篇 · ` +
      `开源清单 ${facts.dependencyTable.length} 项（npm ${Object.keys(facts.npmManifest).length} + ` +
      `pip ${py ? py.size : '—'}）· 枚举字典 ${enumCount} 份`,
  )
  if (iconsSkipped && includeIcons) console.log('[validate-nav] 图标名单加载失败，已跳过该项')
  if (depsSkipped) console.log('[validate-nav] 未提供依赖清单，跳过开源清单对账')
  if (enumsSkipped) console.log('[validate-nav] 未找到 src/constants/enums.js，跳过枚举对账')
  else if (enumBackendSkipped) console.log('[validate-nav] 读不到 backend/app/models，跳过枚举值集比对')
  if (all.length) {
    for (const e of all) console.error(`  ✗ ${e}`)
    console.error(`[validate-nav] ${all.length} 项不一致`)
    process.exit(1)
  }
  console.log('[validate-nav] 通过')
}
