/**
 * 导航一致性构建期校验（T02500 / FR-UX-401）
 *
 * 校验的是「引用指向是否存在」，不是内容好不好：
 * - 引导步骤（GUIDE_STEPS）的路由键与 `[aria-label="…"]` 选择器必须命中真实路由/真实标签；
 * - 帮助文档里「进入「X」」这类菜单指引必须对应真实存在的菜单项；
 * - 侧栏分组（groupConfig）与路由 meta.group 必须互相闭合；
 * - 移动端手写的 tab / 管理入口 `to` 必须能匹配到真实路由；
 * - 菜单项必须有 title 与 icon，且图标名真实存在（图标名写错是静默不渲染，不会报错）。
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

function walk(dir, acc = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) walk(p, acc)
    else if (name.endsWith('.vue')) acc.push(p)
  }
  return acc
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
  for (const file of walk(SRC)) {
    const text = readFileSync(file, 'utf8')
    for (const m of text.matchAll(/[\s"]aria-label="([^"{]+)"/g)) ariaLabels.add(m[1])
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

  return {
    routes,
    guideSteps,
    groups,
    ariaLabels,
    helpIds,
    menuRefs,
    mobileTargets,
    aboutHrefs,
    commentGroups: groupNamesInHeaderComment(routerText),
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

export function checkFacts(f) {
  const errors = []
  const menuTitles = new Set(f.routes.map((r) => r.meta.title).filter(Boolean))
  const groupNames = new Set(f.groups.map((g) => g.name))

  for (const [path, steps] of Object.entries(f.guideSteps)) {
    if (!matchRoute(f.routes, path)) {
      errors.push(`引导配置的路由不存在：GUIDE_STEPS['${path}']`)
    }
    for (const step of steps || []) {
      for (const sel of step.s || []) {
        const m = /^\[aria-label="([^"]+)"\]$/.exec(sel)
        if (m && !f.ariaLabels.has(m[1])) {
          errors.push(
            `引导步骤选择了不存在的 aria-label：${path} → ${sel}（标题「${step.t}」）；` +
              `页面上没有任何元素带这个标签，气泡会退到通用容器并指错元素`,
          )
        }
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

  return { errors, iconNames: [...iconNames] }
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
  const { errors, iconNames } = checkFacts(facts)
  const iconResult = includeIcons ? await checkIconNames(iconNames) : { errors: [], skipped: true }
  return { facts, errors, iconErrors: iconResult.errors, iconsSkipped: iconResult.skipped }
}

const isCli = process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href
if (isCli) {
  const includeIcons = process.argv.includes('--icons')
  const { errors, iconErrors, iconsSkipped, facts } = await validate({ includeIcons })
  const all = [...errors, ...iconErrors]
  console.log(
    `[validate-nav] 路由 ${facts.routes.length} 条 · 引导 ${Object.keys(facts.guideSteps).length} 页 · ` +
      `aria-label ${facts.ariaLabels.size} 个 · 分组 ${facts.groups.length} 个 · 帮助章节 ${facts.helpIds.length} 篇`,
  )
  if (iconsSkipped && includeIcons) console.log('[validate-nav] 图标名单加载失败，已跳过该项')
  if (all.length) {
    for (const e of all) console.error(`  ✗ ${e}`)
    console.error(`[validate-nav] ${all.length} 项不一致`)
    process.exit(1)
  }
  console.log('[validate-nav] 通过')
}
