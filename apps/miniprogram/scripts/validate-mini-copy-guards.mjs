/**
 * J13 / J33 / J44 / J58 / J92 小程序门禁（T02544）：说法、标题与排障入口不得留坑
 *
 * 这 5 条都是「不报错、不白屏、但用户拿不到信息」的中危：
 *  - J13 排序按钮只靠图标翻转表示方向，看不出当前是「最新」还是「最早」；
 *  - J33 详情页导航标题恒为「节目详情」，从列表/队列进来不知道在听哪一集；
 *  - J44 搜索空态只有「未找到相关节目」，不给改词、调筛选或换条路的提示；
 *  - J58 WXML 文本里写了字面 `\n`，小程序不转义，用户看到反斜杠 n；
 *  - J92 版本号连点 5 次打开后端地址编辑，正式版也无守卫。
 *
 * 判据：
 *  1. history.wxml 排序 chip 有 .sort-chip-label 且含「最新/最早」；
 *  2. detail.js 定义 applyNavTitle 并调用它（≥2 处：成功 + 本机下载兜底），定义里真的调了
 *     wx.setNavigationBarTitle，且标题取自集数据而非固定串；
 *  3. search.wxml 空态含可操作提示（关键词/筛选）+ 去频道页按钮，search.js 有对应处理函数；
 *  4. pages/ 与 components/ 下所有 wxml 文本节点里不允许字面 `\n`；
 *  5. about.js 的服务器地址入口用 getEnvVersion 正向白名单（develop/trial）守卫，
 *     且 showServerUrlEditor 只被 onVersionTap 调用。
 *
 * 局限：只做文本模式定位，不解析 WXML/AST；样式是否把文字裁掉不在范围内。
 *
 * 运行：node apps/miniprogram/scripts/validate-mini-copy-guards.mjs
 * 自测（证伪样本）：node --test apps/miniprogram/tests/validate-mini-copy-guards.test.mjs
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

const FILES = {
  historyWxml: 'pages/history/history.wxml',
  detailJs: 'pages/detail/detail.js',
  searchWxml: 'pages/search/search.wxml',
  searchJs: 'pages/search/search.js',
  aboutJs: 'pages/about/about.js',
  serverDiscovery: 'utils/server-discovery.js',
}

const stripComments = (src) => src.replace(/<!--[\s\S]*?-->/g, '')

/** 从 openIdx 之后第一处 </view> 截出的窗口（用于判断某个按钮块里有没有文字节点） */
function windowAfter(src, marker, size = 600) {
  const i = src.indexOf(marker)
  if (i < 0) return ''
  const end = src.indexOf('</view>', i)
  return src.slice(i, end < 0 ? i + size : Math.min(end + 7, i + size))
}

function wxmlFiles() {
  const out = []
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const p = join(dir, name)
      if (statSync(p).isDirectory()) walk(p)
      else if (name.endsWith('.wxml')) out.push({ file: relative(ROOT, p).replace(/\\/g, '/'), src: readFileSync(p, 'utf8') })
    }
  }
  for (const sub of ['pages', 'components']) walk(join(ROOT, sub))
  return out
}

export function validate(overrides = {}) {
  const files = {}
  for (const [key, rel] of Object.entries(FILES)) {
    files[key] = overrides[key] != null ? overrides[key] : readFileSync(join(ROOT, rel), 'utf8')
  }
  const scanned = overrides.wxmlScan || wxmlFiles()

  const errors = []
  const facts = []

  // 1. J13 排序按钮的文字
  const sortChip = windowAfter(stripComments(files.historyWxml), 'onToggleSort', 800)
  if (!sortChip) {
    errors.push('history.wxml 找不到 onToggleSort 按钮：排序入口结构变了，门禁需同步（J13）')
  } else {
    // 只看文字节点：aria-label 里也写着「最新/最早」，拿整块文本判断会被读屏属性蒙混过关
    const sortLabel = (/<text class="sort-chip-label">([\s\S]*?)<\/text>/.exec(sortChip) || [])[1] || ''
    if (!sortLabel) {
      errors.push('history.wxml 排序按钮没有 .sort-chip-label：方向只靠图标翻转（J13）')
    } else if (!sortLabel.includes('最新') || !sortLabel.includes('最早')) {
      errors.push('history.wxml 排序按钮的文字节点没有同时覆盖「最新/最早」（J13）')
    }
    if (!errors.some((e) => e.includes('J13'))) {
      facts.push('history 排序：图标旁有「最新/最早」文字')
    }
  }

  // 2. J33 详情页标题
  const navCall = /applyNavTitle\(episode\)\s*\{([\s\S]*?)\n {2}\},/.exec(files.detailJs)
  if (!navCall) {
    errors.push('detail.js 没有 applyNavTitle(episode) 定义：导航标题仍会恒定（J33）')
  } else {
    if (!navCall[1].includes('wx.setNavigationBarTitle')) {
      errors.push('detail.js applyNavTitle 没有真正设置导航标题（J33）')
    }
    if (!/episode\.title/.test(navCall[1])) {
      errors.push('detail.js applyNavTitle 没有从节目数据取标题：等于把「节目详情」换个写法（J33）')
    }
  }
  const navUses = (files.detailJs.match(/this\.applyNavTitle\(/g) || []).length
  if (navUses < 2) {
    errors.push(`detail.js 只有 ${navUses} 处调用 applyNavTitle（应 ≥2：正常加载 + 本机下载兜底，J33）`)
  }
  if (!errors.some((e) => e.includes('J33'))) {
    facts.push(`detail 标题：applyNavTitle 取节目数据，${navUses} 处调用（正常 + 兜底）`)
  }

  // 3. J44 搜索空态
  const searchSrc = stripComments(files.searchWxml)
  const emptyBlock = (() => {
    const i = searchSrc.indexOf('class="empty-state"')
    if (i < 0) return ''
    const end = searchSrc.indexOf('</view>', i)
    return end < 0 ? '' : searchSrc.slice(i, end)
  })()
  if (!emptyBlock) {
    errors.push('search.wxml 找不到空态块：空态结构变了，门禁需同步（J44）')
  } else {
    if (!emptyBlock.includes('empty-hint')) {
      errors.push('search.wxml 空态没有 .empty-hint：只说「未找到」不给出路（J44）')
    }
    if (!/关键词|筛选/.test(emptyBlock)) {
      errors.push('search.wxml 空态的提示没有提到改关键词或调筛选（J44）')
    }
    const goChannels = /bindtap="(onGoChannels)"/.exec(emptyBlock)
    if (!emptyBlock.includes('empty-action') || !goChannels) {
      errors.push('search.wxml 空态没有去频道页的按钮（.empty-action + bindtap，J44）')
    } else {
      const handler = goChannels[1]
      if (!new RegExp(`\\b${handler}\\(`).test(files.searchJs)) {
        errors.push(`search.js 没有 ${handler} 处理函数：空态按钮点了没反应（J44）`)
      } else if (!files.searchJs.includes('/pages/channels/channels')) {
        errors.push('search.js 的空态按钮没有指向频道页（J44）')
      }
    }
    if (!errors.some((e) => e.includes('J44'))) {
      facts.push('search 空态：提示改词/调筛选 + 去频道页出口')
    }
  }

  // 4. J58 字面 \n
  const literalNewline = scanned.filter(({ src }) => stripComments(src).includes('\\n'))
  if (literalNewline.length) {
    for (const item of literalNewline) {
      errors.push(`${item.file} 文本里有字面 \\n：WXML 不转义，用户会看到反斜杠 n（J58）`)
    }
  } else {
    facts.push(`WXML 扫描：${scanned.length} 个文件均无字面 \\n`)
  }

  // 5. J92 排障入口守卫
  const about = stripComments(files.aboutJs)
  if (!/getEnvVersion/.test(about)) {
    errors.push('about.js 没有引入 getEnvVersion：版本号连点入口无环境判定（J92）')
  }
  const envList = (/const EDIT_ENV_VERSIONS = \[([^\]]*)\]/.exec(about) || [])[1] || ''
  if (!/'develop'/.test(envList) || !/'trial'/.test(envList) || /'release'/.test(envList)) {
    errors.push("about.js 缺少 develop/trial 正向白名单（EDIT_ENV_VERSIONS），或把 release 也放进来了（J92）")
  }
  const tapBody = (() => {
    const i = about.indexOf('onVersionTap()')
    if (i < 0) return ''
    const end = about.indexOf('showServerUrlEditor()', i)
    return end < 0 ? about.slice(i, i + 600) : about.slice(i, end)
  })()
  if (!/indexOf\(getEnvVersion\(\)\)\s*<\s*0\)\s*return/.test(tapBody)) {
    errors.push('about.js onVersionTap 在计数前没有「非开发/体验版直接 return」守卫（J92）')
  }
  const editorCalls = (about.match(/this\.showServerUrlEditor\(/g) || []).length
  if (editorCalls !== 1) {
    errors.push(`about.js 有 ${editorCalls} 处 this.showServerUrlEditor 调用（应恰好 1 处，全在 onVersionTap 内，J92）`)
  }
  if (!/module\.exports[\s\S]*getEnvVersion/.test(files.serverDiscovery)) {
    errors.push('utils/server-discovery.js 没有导出 getEnvVersion：守卫与自动探测会各写一份判定（J92）')
  }
  if (!errors.some((e) => e.includes('J92'))) {
    facts.push('about 排障入口：仅 develop/trial 生效，正式版连点无反应')
  }

  return { errors, facts }
}

const isCli = process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href
if (isCli) {
  const { errors, facts } = validate()
  if (errors.length) {
    for (const e of errors) console.error(`  ✗ ${e}`)
    console.error(`[validate-mini-copy-guards] ${errors.length} 项不一致`)
    process.exit(1)
  }
  for (const f of facts) console.log(`  ✓ ${f}`)
  console.log('[validate-mini-copy-guards] 通过（排序文字/详情标题/搜索空态/WXML 换行/排障入口守卫）')
}
