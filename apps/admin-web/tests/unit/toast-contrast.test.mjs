/**
 * 全局提示（toast / alert）对比度门禁（T03330）
 *
 * e2e 那条（tests/toast-contrast.spec.js）用真实浏览器量 computed color，
 * 但跑一轮要拉 dev server；这里把同一笔账在源码层先算一遍：
 *
 *   1) `--toast-*` 的「正文/底色」在 6 套主题下逐一解析成实际色值（含 var 链），
 *      按 WCAG 公式算对比度，四类都必须 ≥ 4.5；
 *   2) global.scss 必须真的把 EP 的 message/alert/messagebox 指到这些 token 上，
 *      且选择器带 html 前缀（EP 分组件样式是按需 chunk，同权重会被加载顺序压掉）；
 *   3) 负向对照：把正文映射回粉彩 --color-success（#B5EAD7）时，这里必须算出 < 4.5。
 *      有人若把 --el-message-text-color 改回 var(--el-color-success)，第 2 条直接红。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/toast-contrast.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

const SRC = new URL('../../src/', import.meta.url)
const read = (rel) => readFileSync(new URL(rel, SRC), 'utf8')

const VARIABLES = read('styles/variables.scss')
const THEMES = read('styles/themes.scss')
const GLOBAL = read('styles/global.scss')

const THEME_NAMES = ['macaron', 'enterprise', 'creative', 'showcase', 'commerce', 'portfolio']
const TYPES = ['success', 'warning', 'error', 'info']
const EP_LIGHT_BG = {
  success: '#F0F9EB',
  warning: '#FDF6EC',
  error: '#FEF0F0',
  info: '#F4F4F5',
}

/** 去掉注释再解析：注释里写「原来是 #fff」不算定义 */
function stripComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/[^\n]*/g, '$1')
}

/**
 * 取顶层块（缩进的嵌套规则不参与 token 解析）。
 * SCSS 的顶层块在行首收尾；选择器可能跨行（`:root,` 单独一行）。
 */
function topLevelBlocks(text) {
  const blocks = []
  let pending = []
  let cur = null
  for (const raw of stripComments(text).split('\n')) {
    const line = raw.trimEnd()
    if (!cur) {
      const t = line.trim()
      if (!t) continue
      if (t.includes('{')) {
        const selector = [...pending, line.slice(0, line.indexOf('{'))].join(' ').replace(/\s+/g, ' ').trim()
        cur = { selector, body: [] }
        pending = []
      } else {
        pending.push(t)
      }
    } else if (/^\}/.test(line)) {
      blocks.push(cur)
      cur = null
    } else {
      cur.body.push(line)
    }
  }
  return blocks
}

function declsOf(body) {
  const text = Array.isArray(body) ? body.join('\n') : body
  const out = {}
  for (const m of text.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/gi)) out[m[1]] = m[2].trim()
  return out
}

/** 把 :root 与指定主题块按文件顺序叠加：后出现的同名 token 覆盖前面的 */
function themeDecls(theme) {
  const out = {}
  for (const b of topLevelBlocks(VARIABLES)) {
    if (b.selector === ':root') Object.assign(out, declsOf(b.body))
  }
  for (const b of topLevelBlocks(THEMES)) {
    if (b.selector.includes(':root') || b.selector.includes(`[data-theme='${theme}']`)) {
      Object.assign(out, declsOf(b.body))
    }
  }
  return out
}

/** 解析 var() 链：只接受单个 var(--x)，解析不到直接抛，避免静默拿字面量去算 */
function resolveToken(name, decls, seen = new Set()) {
  assert.ok(decls[name], `${name} 没有定义`)
  assert.ok(!seen.has(name), `${name} 的 var 链出现循环：${[...seen, name].join(' -> ')}`)
  seen.add(name)
  const raw = decls[name]
  const m = /^var\((--[a-z0-9-]+)\)$/i.exec(raw.trim())
  if (m) return resolveToken(m[1], decls, seen)
  return raw.trim()
}

const parseHex = (value) => {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value)
  assert.ok(m, `期望十六进制色值，拿到 ${value}`)
  const h = m[1].length === 3 ? m[1].split('').map((c) => c + c).join('') : m[1]
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16))
}

const luminance = (hex) => {
  const [r, g, b] = parseHex(hex).map((v) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contrast(fg, bg) {
  const [hi, lo] = [luminance(fg), luminance(bg)].sort((a, b) => b - a)
  return (hi + 0.05) / (lo + 0.05)
}

const ratioOf = (theme, type) => {
  const d = themeDecls(theme)
  const fg = resolveToken(`--toast-${type}-fg`, d)
  const bg = resolveToken(`--toast-${type}-bg`, d)
  return { fg, bg, ratio: +contrast(fg, bg).toFixed(2) }
}

describe('全局提示对比度门禁（T03330）', () => {
  it('6 套主题 × 4 类 toast 的正文对比度 ≥ 4.5:1', () => {
    const failures = []
    const table = []
    for (const theme of THEME_NAMES) {
      for (const type of TYPES) {
        const { fg, bg, ratio } = ratioOf(theme, type)
        table.push(`${theme}/${type} ${fg} on ${bg} = ${ratio}:1`)
        if (ratio < 4.5) failures.push(table[table.length - 1])
      }
    }
    assert.deepEqual(failures, [], '这些组合不达 AA：\n      ' + table.join('\n      '))
  })

  it('每套主题都定义了四类 toast 的底色/描边/正文（漏定义会在这里红，而不是回退到粉彩）', () => {
    for (const theme of THEME_NAMES) {
      const d = themeDecls(theme)
      for (const type of TYPES) {
        for (const part of ['bg', 'border', 'fg']) {
          assert.ok(d[`--toast-${type}-${part}`], `${theme} 缺少 --toast-${type}-${part}`)
        }
      }
    }
  })

  it('showcase 的 toast 底色是深色（暗色页里不能出现浅色孤岛）', () => {
    for (const type of TYPES) {
      const { bg } = ratioOf('showcase', type)
      assert.ok(luminance(bg) < 0.2, `showcase/${type} 的底色 ${bg} 仍是浅色`)
    }
  })

  it('EP 的 message/alert/messagebox 都指向 --toast-*，正文不再取 --el-color-* 粉彩', () => {
    for (const type of TYPES) {
      const msg = new RegExp(
        `html\\s+\\.el-message--${type}\\s*\\{[^}]*--el-message-text-color:\\s*var\\(--toast-${type}-fg\\)`,
      )
      assert.match(GLOBAL, msg, `.el-message--${type} 没把正文指到 --toast-${type}-fg`)

      const alert = new RegExp(
        `html\\s+\\.el-alert--${type}\\.is-light\\s*\\{[^}]*background-color:\\s*var\\(--toast-${type}-bg\\)[^}]*color:\\s*var\\(--toast-${type}-fg\\)`,
      )
      assert.match(GLOBAL, alert, `.el-alert--${type}.is-light 没走 toast token`)

      const desc = new RegExp(
        `html\\s+\\.el-alert--${type}\\.is-light[\\s\\S]*?\\.el-alert__description\\s*\\{[^}]*color:\\s*var\\(--toast-${type}-fg\\)`,
      )
      assert.match(GLOBAL, desc, `.el-alert--${type} 的描述文字没走 toast token`)

      const icon = new RegExp(
        `html\\s+\\.el-message-box__status\\.el-message-box-icon--${type}\\s*\\{[^}]*color:\\s*var\\(--toast-${type}-fg\\)`,
      )
      assert.match(GLOBAL, icon, `消息框 ${type} 图标没走 toast token`)
    }
    // 反向：谁把正文改回 --el-color-* / --color-* 粉彩，这里直接红
    assert.doesNotMatch(
      GLOBAL,
      /--el-message-text-color:\s*var\(--el-color-/,
      '正文又指回了 --el-color-*（粉彩底色的同一个变量），对比度会再次跌到 1.x:1',
    )
  })

  it('负向对照：粉彩正文压 EP 浅底确实不达标，强色达标', () => {
    assert.ok(contrast('#B5EAD7', EP_LIGHT_BG.success) < 4.5, '粉彩 success 竟然算达标，公式有问题')
    assert.ok(contrast('#FFE5B4', EP_LIGHT_BG.warning) < 4.5, '粉彩 warning 竟然算达标，公式有问题')
    assert.ok(contrast('#1F6B45', EP_LIGHT_BG.success) >= 4.5, '强色 success 反而不达标')
    assert.ok(contrast('#8A5A00', EP_LIGHT_BG.warning) >= 4.5, '强色 warning 反而不达标')
  })

  // 门禁不接线等于没有：日常跑的是 npm run test:unit，文件不在里面就没人会碰它
  it('已接进 npm run test:unit', () => {
    const pkg = JSON.parse(readFileSync(new URL('../../package.json', import.meta.url), 'utf8'))
    assert.match(
      pkg.scripts['test:unit'],
      /tests\/unit\/toast-contrast\.test\.mjs/,
      '门禁没接进 test:unit，日常单测不会跑它',
    )
  })
})
