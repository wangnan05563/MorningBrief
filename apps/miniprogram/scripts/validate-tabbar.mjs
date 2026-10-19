/**
 * 小程序底部导航一致性构建期校验（T02510 / FR-UX-601，M6）
 *
 * 校验的是「导航契约是否成立」，不是界面好不好看：
 * - `tabBar.list` 每项必须声明非空 `text`（T02323 J1：三个 tab 曾只有图标，用户靠图形猜）；
 *   且 tab 文案必须与该页 `navigationBarTitleText` 同族（互为包含）——「首页」tab 里挂着
 *   「今日节目」标题这类漂移，运行时不报错，只会让用户对不上号；
 * - `tabBar.list[].pagePath` 必须在 `pages` 中注册，页面 `.js/.wxml/.json` 三件套齐；
 *   图标（`iconPath`/`selectedIconPath`）文件必须真的存在——图标路径写错是静默不显示；
 * - tab 数量在微信允许的 2~5 之间；
 * - 角标挂载点：`utils/tab-badge.js` 的 `HISTORY_TAB_INDEX` 与 `TAB_ROUTES` 下标必须与
 *   `app.json tabBar.list` 顺序逐项对上。T02510 把队列待播角标挂在「历史」tab，
 *   有人往 tabBar 前面插一个 tab 时，必须让门禁红，而不是角标静默挂错位置；
 * - 死入口：页面 js 的 `Page({ onXxx })` 方法必须能在同页 wxml 的 bind/catch 前缀事件绑定里
 *   出现，或在 js 内被 `this.onXxx` 引用——J12 的首页队列入口就是这么死的
 *   （`index.js` 定义了 `onOpenQueue`，wxml 里从没绑过，用户点不到）；
 * - 死路由键：页面 js 里 `const xxxMap = { key: '/pages/…' }` 的每个 key，必须在同页 wxml
 *   的 `data-key="key"` 里出现（T00726 把五项并入第二层 Tab 后，`routeMap` 里剩了五个
 *   永远不会命中的键，没人发现）；映射值指向未注册页面也一并点名（navigateTo 必失败）；
 * - 合规入口不藏在条件分支：`data-key` ∈ {privacy, agreement, feedback} 的行必须不在
 *   任何带 `wx:if`/`wx:elif`/`wx:else` 的元素内（J19：整张卡曾在 `wx:else` 里，
 *   游客读不到《隐私政策》，而首启就要弹隐私授权）；
 * - 需要「带文字入口」的页面（`LABELED_ENTRY_PAGES`，当前是队列页）必须存在一个 `data-key`
 *   行，其路由映射指向该页、且行内有非空 `<text>` 文案——纯图标 chip 不算。
 *   只断言「有字符串引用」的守卫永远不会红，这条才是 J12 的回归点。
 *
 * 为什么放在构建期而不是运行时：这些错在运行时全部静默——缺 `text` 只是不显示文字，
 * 死方法只是「点不到」，藏进登录分支只是「看不到」，没有任何异常可捕获。
 *
 * 实现取向：与 `apps/admin-web/scripts/validate-nav.mjs` 一致——只做静态文本抽取
 * （括号配对 + 标签栈），不引 WXML 编译器、不引第三方解析依赖。
 * 明确的局限（遇到即跳过并在输出里说明，不假装查过）：
 *   动态绑定里以变量形式给出的方法名（`bindtap="{{fn}}"`）、动态属性名（`:data-key="x"`）、
 *   运行时拼出的路由、
 *   跨页 `getCurrentPages()` 跳转、以及非 `Page({ … })` 直写的页面工厂形式。
 *
 * 豁免：被点名的方法上一行写一条 gate-allow 块注释（内容为「原因」），例如确实由
 * 组件回调触发的入口。
 */
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

/** 微信 tabBar 允许的下数 */
const TAB_MIN = 2
const TAB_MAX = 5

/**
 * 页面路径归一：`app.json.pages` 写的是 `pages/x/x`，而 js 里 navigateTo 的 url
 * 惯例带前导斜杠（`/pages/x/x`）。不归一就会把每一条正常路由误报成「未注册」——
 * 门禁一旦长期红在误报上，就等于没有门禁。
 */
const normPage = (p) => String(p || '').replace(/^\/+/, '').replace(/\/+$/, '')

/** 由框架调用、不参与「死入口」判定的页面方法 */
const LIFECYCLE = new Set([
  'onLoad',
  'onShow',
  'onHide',
  'onReady',
  'onUnload',
  'onPullDownRefresh',
  'onReachBottom',
  'onPageScroll',
  'onResize',
  'onShareAppMessage',
  'onShareTimeline',
  'onAddToFavorites',
  'onTabItemTap',
  'onRouteDone',
  'onBack',
  'data',
])

/** 合规与自助入口：不得藏在条件分支（登录态）里 */
const COMPLIANCE_KEYS = new Set(['privacy', 'agreement', 'feedback'])

/**
 * 必须存在「带文字入口」的页面目录名。
 * 队列页在此列：J12 原话是「多数用户不会知道自己有一个播放队列页」，根因是唯一入口
 * 是一枚纯图标 chip。
 */
const LABELED_ENTRY_PAGES = ['queue']

const IDENT_START = /[A-Za-z_$]/
const IDENT_BODY = /[A-Za-z0-9_$]/

/** 去掉 js 块注释与行注释（注释里的方法名、路由不该算数） */
function stripJsComments(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/(^|[^:'"`\\])\/\/[^\n]*/g, '$1')
}

/** 去掉 wxml 注释 */
function stripWxmlComments(text) {
  return text.replace(/<!--[\s\S]*?-->/g, '')
}

/**
 * 从 `from` 处的 `{`/`[` 开始做括号配对（跳过字符串与注释内的括号），返回字面量文本
 */
function literalAt(text, from, open = '{') {
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
  throw new Error(`括号未配对：起始偏移 ${from}（open=${open}）`)
}

/**
 * 取对象字面量（`{` 开头）的顶层键名。
 * 认 `key(`（方法简写）与 `key:`；`async key(` / `get key()` 取紧邻 `(`/`:` 的那个标识符。
 */
export function topLevelKeys(literal) {
  const keys = []
  let depth = 0
  let quote = null
  let pending = null
  for (let i = 0; i < literal.length; i += 1) {
    const ch = literal[i]
    if (quote) {
      if (ch === '\\') i += 1
      else if (ch === quote) quote = null
      continue
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      quote = ch
      pending = null
      continue
    }
    if (ch === '/' && (literal[i + 1] === '/' || literal[i + 1] === '*')) {
      i =
        literal[i + 1] === '/'
          ? Math.max(literal.indexOf('\n', i), i)
          : Math.max(literal.indexOf('*/', i), i) + 1
      pending = null
      continue
    }
    if (ch === '{' || ch === '[' || ch === '(') {
      depth += 1
      if (depth > 1) pending = null
      continue
    }
    if (ch === '}' || ch === ']' || ch === ')') {
      depth -= 1
      pending = null
      continue
    }
    if (depth !== 1) continue
    if (IDENT_START.test(ch)) {
      let j = i
      while (j < literal.length && IDENT_BODY.test(literal[j])) j += 1
      const word = literal.slice(i, j)
      // 只有「上一个非空字符是 { 或 ,」时 word 才是键的起点
      let k = i - 1
      while (k >= 0 && /\s/.test(literal[k])) k -= 1
      const prev = k >= 0 ? literal[k] : ''
      if (prev !== '{' && prev !== ',') {
        pending = null
        i = j - 1
        continue
      }
      let m = j
      while (m < literal.length && /\s/.test(literal[m])) m += 1
      const next = literal[m]
      if (next === ':' || next === '(') {
        keys.push(word)
        pending = null
      } else {
        pending = word // async / get / set 等修饰词：下一个标识符才是键名
      }
      i = j - 1
      continue
    }
    if (ch === ':') {
      if (pending) keys.push(pending)
      pending = null
      continue
    }
    if (!/\s/.test(ch)) pending = null
  }
  return keys
}

/** WXML 标签流：[{name, attrs, closing, selfClose, offset, end}]（end = 该标签文本结束偏移） */
export function tokenizeWxml(text) {
  const src = stripWxmlComments(text)
  const out = []
  const re = /<(\/?)([a-zA-Z][\w-]*)((?:"[^"]*"|'[^']*'|[^"'>])*)>/g
  let m
  while ((m = re.exec(src)) !== null) {
    const closing = m[1] === '/'
    out.push({
      name: m[2],
      attrs: m[3] || '',
      closing,
      selfClose: !closing && /\/\s*$/.test(m[3] || ''),
      offset: m.index,
      end: m.index + m[0].length,
      src,
    })
  }
  return out
}

/** 取该页 wxml 里所有事件绑定的方法名 */
export function wxmlBindings(tokens) {
  const names = new Set()
  for (const t of tokens) {
    if (t.closing) continue
    // 一次匹配所有 bind/catch 属性值（含 mustache），再按值形态分流：
    //   静态   bindtap="onPlay"        → 直接就是方法名
    //   三元   bindtap="{{ s==='a' ? 'onA' : 'onB' }}" → 取其中的字符串字面量
    //   变量   bindtap="{{fn}}"        → 静态无法确定，跳过（文件头已声明该局限）
    // 不枚举三元分支会把「按状态切换的入口」误判成死方法
    //（detail 页 onDownloadCancel 正是 `downloadState === 'downloading'` 的那一支）。
    const re = /(?:^|\s)(?:bind|catch)[:a-zA-Z-]*\s*=\s*"([^"]*)"/g
    let m
    while ((m = re.exec(t.attrs)) !== null) {
      const value = m[1]
      if (!value.includes('{{')) {
        names.add(value.trim())
        continue
      }
      const qre = /'([A-Za-z_$][\w$]*)'|"([A-Za-z_$][\w$]*)"/g
      let q
      while ((q = qre.exec(value)) !== null) names.add(q[1] || q[2])
    }
  }
  return names
}

/**
 * 遍历标签栈，产出带 `data-key` 的元素的上下文：
 * { dataKey, tag, conditionalAncestors, selfConditional, innerText }
 * innerText 取该元素自身的内部原文（同名单词表计配对到闭合标签）。
 */
export function walkElements(tokens) {
  const stack = []
  const rows = []
  for (let i = 0; i < tokens.length; i += 1) {
    const t = tokens[i]
    if (t.closing) {
      if (stack.length && stack[stack.length - 1].name === t.name) stack.pop()
      continue
    }
    const dataKey = /(?:^|\s)data-key\s*=\s*"([^"]+)"/.exec(t.attrs)?.[1] || null
    // `(?:=|\s|$)` 三个收尾都算：单测里 `<block wx:else>`（指令后直接到标签尾）一度漏判，
    // 漏判的后果是「合规入口藏在分支里」这条规则对最常见的写法失效
    const conditional = /(?:^|\s)wx:(?:if|elif|else)(?:=|\s|$)/.test(t.attrs)
    if (dataKey) {
      const innerText = sliceInner(t, tokens, i)
      rows.push({
        dataKey,
        tag: t.name,
        conditionalAncestors: stack.filter((s) => s.conditional).length,
        selfConditional: conditional,
        innerText,
      })
    }
    if (!t.selfClose) stack.push({ name: t.name, conditional })
  }
  return rows
}

/** 取元素内部原文：按同名标签计数找到配对闭合点 */
function sliceInner(open, tokens, openAt) {
  if (open.selfClose) return ''
  let level = 0
  for (let j = openAt + 1; j < tokens.length; j += 1) {
    const u = tokens[j]
    if (u.name !== open.name) continue
    if (u.closing) {
      if (level === 0) return open.src.slice(open.end, u.offset)
      level -= 1
    } else if (!u.selfClose) {
      level += 1
    }
  }
  // 未配对（模板写坏）：退化为「到文件末尾」，让别的检查去管
  return open.src.slice(open.end)
}

/** 豁免名单：gate-allow 块注释（内容为「原因」）之后紧跟的方法名 */
export function allowedByName(js) {
  const set = new Set()
  const re = /\/\*\s*gate-allow:\s*([\s\S]*?)\*\//g
  let m
  while ((m = re.exec(js)) !== null) {
    const after = js.slice(m.index + m[0].length, m.index + m[0].length + 200)
    const name = /^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*[(:]/.exec(after)?.[1]
    if (name) set.add(name)
  }
  return set
}

/** 从 js 源码抽 `Page({...})` 字面量；非该写法返回 null（调用方记 note 后跳过） */
function pageLiteral(js) {
  const m = /\bPage\s*\(\s*\{/.exec(js)
  if (!m) return null
  return literalAt(js, js.indexOf('{', m.index), '{')
}

/** 抽 `const xxxMap = { key: '/pages/…' }` 形式的页面路径映射表 */
function pagePathMaps(js) {
  const out = []
  const re = /const\s+([A-Za-z_$][\w$]*Map)\s*=\s*\{/g
  let m
  while ((m = re.exec(js)) !== null) {
    const braceAt = js.indexOf('{', m.index + m[0].length - 1)
    const literal = literalAt(js, braceAt, '{')
    const entries = []
    const kre = /([A-Za-z_$][\w$]*)\s*:\s*'(\/?pages\/[^']+)'/g
    let k
    while ((k = kre.exec(literal)) !== null) entries.push({ key: k[1], path: k[2] })
    if (entries.length) out.push({ name: m[1], entries })
  }
  return out
}

/** 读页面三件套 */
function readPage(dir) {
  const base = join(ROOT, 'pages', dir, `${dir}.`)
  const read = (ext) => (existsSync(base + ext) ? readFileSync(base + ext, 'utf8') : null)
  return { dir, js: read('js'), wxml: read('wxml'), json: read('json') }
}

/** `utils/tab-badge.js` 的挂载常量 */
function tabBadgeFacts() {
  const p = join(ROOT, 'utils', 'tab-badge.js')
  if (!existsSync(p)) return null
  const src = readFileSync(p, 'utf8')
  const idx = /const\s+HISTORY_TAB_INDEX\s*=\s*(\d+)/.exec(src)?.[1]
  const routesBlock = /const\s+TAB_ROUTES\s*=\s*\{/.exec(src)
  const routes = {}
  if (routesBlock) {
    const literal = literalAt(src, src.indexOf('{', routesBlock.index), '{')
    const re = /'([^']+)'\s*:\s*(\d+)/g
    let m
    while ((m = re.exec(literal)) !== null) routes[m[1]] = Number(m[2])
  }
  return { historyIndex: idx === undefined ? null : Number(idx), routes }
}

/**
 * 抽取全部事实（不判定），供 `checkFacts` 与单测共用。
 * @param {object} [overrides] 单测用：`{appJsonRaw, pageTexts: {dir:{js,wxml,json}}, badgeFacts, files}`
 */
export function collectFacts(overrides = {}) {
  const notes = []
  const appJsonRaw =
    overrides.appJsonRaw !== undefined
      ? overrides.appJsonRaw
      : existsSync(join(ROOT, 'app.json'))
        ? readFileSync(join(ROOT, 'app.json'), 'utf8')
        : null

  let appJson = null
  if (appJsonRaw === null) {
    notes.push('未找到 app.json，跳过底部导航校验')
  } else {
    try {
      appJson = JSON.parse(appJsonRaw)
    } catch (e) {
      notes.push(`app.json 解析失败：${e.message}`)
    }
  }

  const loadPage = (dir) => {
    const injected = overrides.pageTexts?.[dir]
    if (injected) return { dir, js: null, wxml: null, json: null, ...injected }
    return readPage(dir)
  }

  const tabPaths = appJson?.tabBar?.list?.map((t) => t.pagePath).filter(Boolean) || []
  const tabBarPages = tabPaths.map((p) => loadPage(p.split('/').pop()))
  const allPages = (appJson?.pages || []).map((p) => loadPage(p.split('/').pop()))

  return {
    notes,
    appJson,
    tabBarPages,
    allPages,
    badge: overrides.badgeFacts !== undefined ? overrides.badgeFacts : tabBadgeFacts(),
    exists: (rel) =>
      overrides.files ? overrides.files.has(rel) : existsSync(join(ROOT, rel)),
  }
}

/** 判定：返回逐条可读的错误（不返回警告之外的分类） */
export function checkFacts(f) {
  const errors = []
  const notes = [...f.notes]
  const { appJson } = f
  if (!appJson) return { errors, notes, facts: f }

  const declaredPages = Array.isArray(appJson.pages) ? appJson.pages : []
  const declared = new Set(declaredPages.map(normPage))
  if (!declaredPages.length) errors.push('app.json: pages 为空，小程序无法启动')

  const list = appJson.tabBar?.list
  if (!Array.isArray(list)) {
    errors.push('app.json: 缺少 tabBar.list（底部导航不存在）')
    return { errors, notes, facts: f }
  }
  if (list.length < TAB_MIN || list.length > TAB_MAX) {
    errors.push(`app.json: tabBar 下标数 ${list.length}，微信要求 ${TAB_MIN}~${TAB_MAX}`)
  }

  const seenText = new Map()
  list.forEach((item, i) => {
    const at = `tabBar.list[${i}]（${item.pagePath || '未声明 pagePath'}）`
    if (!item.pagePath) {
      errors.push(`${at}: 缺少 pagePath`)
    } else if (!declared.has(normPage(item.pagePath))) {
      errors.push(`${at}: pagePath 未在 app.json.pages 中注册（点击 tab 白屏）`)
    }

    const text = typeof item.text === 'string' ? item.text.trim() : ''
    if (!text) {
      errors.push(`${at}: 缺少 text——底部导航只有图标，用户只能靠图形猜（T02323 J1）`)
    } else if (seenText.has(text)) {
      errors.push(`${at}: text「${text}」与 tab ${seenText.get(text) + 1} 重复`)
    } else {
      seenText.set(text, i)
    }

    const dir = item.pagePath?.split('/').pop()
    const pg = dir ? f.tabBarPages.find((p) => p.dir === dir) : null
    if (pg) {
      for (const [ext, label] of [
        ['js', '逻辑'],
        ['wxml', '模板'],
        ['json', '配置'],
      ]) {
        if (!pg[ext]) errors.push(`${at}: 页面文件 pages/${dir}/${dir}.${ext} 缺失（${label}）`)
      }
      // tab 文案与页面标题必须同族，否则「首页 tab / 今日节目标题」这类漂移无人发现
      const title = pg.json ? /"navigationBarTitleText"\s*:\s*"([^"]*)"/.exec(pg.json)?.[1] : ''
      if (text && title && !title.includes(text) && !text.includes(title)) {
        errors.push(
          `${at}: text「${text}」与页面标题「${title}」对不上——tab 文案应是页面标题的一部分（或反之）`,
        )
      }
    }

    for (const key of ['iconPath', 'selectedIconPath']) {
      if (!item[key]) continue
      if (!f.exists(item[key])) errors.push(`${at}: ${key} 指向的文件不存在：${item[key]}`)
    }
  })

  // 角标挂载点与 tabBar 顺序绑定
  if (!f.badge) {
    notes.push('未找到 utils/tab-badge.js，跳过角标挂载点校验')
  } else {
    const historyAt = list.findIndex((t) => (t.pagePath || '').endsWith('/history'))
    if (f.badge.historyIndex === null || f.badge.historyIndex === undefined) {
      errors.push('utils/tab-badge.js: 读不到 HISTORY_TAB_INDEX 常量')
    } else if (historyAt < 0) {
      errors.push('app.json: tabBar 里没有 history 页，但 tab-badge 仍要往它挂角标')
    } else if (f.badge.historyIndex !== historyAt) {
      errors.push(
        `utils/tab-badge.js: HISTORY_TAB_INDEX=${f.badge.historyIndex}，但「历史」在 tabBar.list[${historyAt}]——角标会挂错 tab`,
      )
    }
    list.forEach((t, i) => {
      const declared = f.badge.routes[t.pagePath]
      if (declared === undefined) {
        notes.push(`tab-badge.TAB_ROUTES 未登记 ${t.pagePath}（切到该 tab 不会刷新角标）`)
        return
      }
      if (declared !== i) {
        errors.push(
          `utils/tab-badge.js: TAB_ROUTES['${t.pagePath}']=${declared} 与 tabBar.list[${i}] 顺序不一致`,
        )
      }
    })
    for (const route of Object.keys(f.badge.routes)) {
      if (!list.some((t) => t.pagePath === route)) {
        errors.push(`utils/tab-badge.js: TAB_ROUTES 里的 ${route} 已不是 tabBar 页`)
      }
    }
  }

  // 逐页：死入口 / 死路由键 / 合规入口 / 文字入口
  for (const pg of f.allPages) {
    if (!pg.js || !pg.wxml) {
      notes.push(`pages/${pg.dir}: 缺 js 或 wxml，跳过该页入口校验（三件套问题另见上）`)
      continue
    }
    const cleanJs = stripJsComments(pg.js)
    const tokens = tokenizeWxml(pg.wxml)
    const bindings = wxmlBindings(tokens)
    const rows = walkElements(tokens)
    const allowed = allowedByName(pg.js)

    const literal = pageLiteral(cleanJs)
    if (!literal) {
      notes.push(`pages/${pg.dir}: 非 Page({ … }) 直写形式，跳过死入口检查`)
    } else {
      const methods = topLevelKeys(literal).filter((k) => /^on[A-Z]/.test(k) && !LIFECYCLE.has(k))
      for (const name of methods) {
        if (allowed.has(name)) continue
        const usedHere = new RegExp(`this\\.${name}\\b`).test(cleanJs)
        if (!bindings.has(name) && !usedHere) {
          errors.push(
            `pages/${pg.dir}/${pg.dir}.js: 方法 ${name}() 既没在同页 wxml 里绑定，也没被 this.${name} 调用——死入口，用户点不到（T02323 J12 同类）`,
          )
        }
      }
    }

    for (const map of pagePathMaps(cleanJs)) {
      const declaredKeys = new Set(rows.map((r) => r.dataKey))
      if (!declaredKeys.size) {
        notes.push(`pages/${pg.dir}: ${map.name} 存在但该页没有 data-key 用法，跳过死键检查`)
        continue
      }
      for (const { key, path } of map.entries) {
        if (!declared.has(normPage(path))) {
          errors.push(
            `pages/${pg.dir}: ${map.name}.${key} → ${path} 未在 app.json.pages 注册（navigateTo 必然失败）`,
          )
        }
        if (!declaredKeys.has(key)) {
          errors.push(
            `pages/${pg.dir}/${pg.dir}.js: ${map.name} 里的 ${key}（${path}）在同页 wxml 没有 data-key="${key}"——永远不会命中的死键`,
          )
        }
        const dirOfPath = path.split('/').pop()
        if (LABELED_ENTRY_PAGES.includes(dirOfPath)) {
          const hit = rows.find(
            (r) => r.dataKey === key && /<text[^>]*>\s*[^\s<][^<]*<\/text>/s.test(r.innerText),
          )
          if (!hit) {
            errors.push(
              `pages/${pg.dir}: 进入 ${path} 的入口 data-key="${key}" 没有可见文案——纯图标入口，用户不知道有这一页（T02323 J12）`,
            )
          }
        }
      }
    }

    for (const row of rows) {
      if (!COMPLIANCE_KEYS.has(row.dataKey)) continue
      if (row.conditionalAncestors > 0 || row.selfConditional) {
        errors.push(
          `pages/${pg.dir}/${pg.dir}.wxml: data-key="${row.dataKey}" 的入口落在条件分支里——分支未命中（例如未登录）时用户拿不到合规与自助入口（T02323 J19）`,
        )
      }
    }
  }

  return { errors, notes, facts: f }
}

export async function validate(overrides = {}) {
  const facts = collectFacts(overrides)
  const { errors, notes } = checkFacts(facts)
  return { errors, notes, facts }
}

const isCli =
  process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href
if (isCli) {
  const { errors, notes, facts } = await validate()
  const list = facts.appJson?.tabBar?.list || []
  const texts = list.map((t) => t.text || '∅').join('/')
  console.log(
    `[validate-tabbar] tabBar ${list.length} 项（${texts}） · 注册页 ${(facts.appJson?.pages || []).length} 个 · ` +
      `角标挂载 ${facts.badge ? `历史 tab[${facts.badge.historyIndex}]` : '—'}`,
  )
  for (const n of notes) console.log(`[validate-tabbar] 跳过：${n}`)
  if (errors.length) {
    for (const e of errors) console.error(`  ✗ ${e}`)
    console.error(`[validate-tabbar] ${errors.length} 项不一致`)
    process.exit(1)
  }
  console.log('[validate-tabbar] 通过')
}
