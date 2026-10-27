/**
 * 状态标签（el-tag）对比度门禁（T03331）
 *
 * EP 的 `.el-tag.el-tag--success`（0,2,0）把 --el-color-success（本项目的粉彩）
 * 当正文色，配 light-9 浅底：马卡龙主题实测 1.14–1.82:1，默认 primary 1.37:1。
 * 这里把同一笔账先在源码层算一遍：
 *
 *   1) 6 套主题 × 5 类（success/warning/danger/info/primary）的 `--tag-*` token
 *      逐条解析 var 链；底色带 alpha 的（showcase rgba 12%）按 --color-bg-card
 *      合成后再算，四类正文都必须 ≥ 4.5；
 *   2) default / plain / dark 三种 effect 都要过：plain 的底色是
 *      --el-fill-color-blank（页面底），dark 与 default 共用同一对 token；
 *   3) global.scss 必须真的把三种变体接到 --tag-* 上，且选择器带 html 前缀
 *      （el-tag.css 按需注入，同权重会被加载顺序压掉）；
 *   4) 负向对照：粉彩正文压浅底必须 < 4.5，否则公式有问题。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/tag-contrast.test.mjs
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
const TYPES = ['success', 'warning', 'danger', 'info', 'primary']
const VARIANTS = ['default', 'plain', 'dark']

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

/** 把 variables.scss 的 :root 与指定主题块按文件顺序叠加：后出现的同名 token 覆盖前面的 */
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

const parseRgba = (value) => {
  const m = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i.exec(value)
  if (!m) return null
  return { rgb: [m[1], m[2], m[3]].map(Number), alpha: m[4] === undefined ? 1 : Number(m[4]) }
}

/**
 * 标签底色可能是 12% 半透明（showcase），浏览器里实际显示的是它与卡片底的合成色。
 * 不透的十六进制原样返回，避免把合成公式用错对象。
 */
function composite(value, baseHex) {
  const rgba = parseRgba(value)
  if (!rgba) return value
  const base = parseHex(baseHex)
  const out = rgba.rgb.map((v, i) => Math.round(v * rgba.alpha + base[i] * (1 - rgba.alpha)))
  return '#' + out.map((v) => v.toString(16).padStart(2, '0')).join('')
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

/** plain 变体的底色由 EP 设成 --el-fill-color-blank（本项目映射到页面底色） */
function bgTokenOf(type, variant) {
  return variant === 'plain' ? '--el-fill-color-blank' : `--tag-${type}-bg`
}

const ratioOf = (theme, type, variant) => {
  const d = themeDecls(theme)
  const card = resolveToken('--color-bg-card', d)
  const fg = resolveToken(`--tag-${type}-fg`, d)
  const bg = composite(resolveToken(bgTokenOf(type, variant), d), card)
  return { fg, bg, ratio: +contrast(fg, bg).toFixed(2) }
}

describe('状态标签对比度门禁（T03331）', () => {
  it('6 套主题 × 5 类 × 3 种 effect 的正文对比度 ≥ 4.5:1', () => {
    const failures = []
    const table = []
    for (const theme of THEME_NAMES) {
      for (const type of TYPES) {
        for (const variant of VARIANTS) {
          const { fg, bg, ratio } = ratioOf(theme, type, variant)
          table.push(`${theme}/${type}/${variant} ${fg} on ${bg} = ${ratio}:1`)
          if (ratio < 4.5) failures.push(table[table.length - 1])
        }
      }
    }
    assert.deepEqual(failures, [], '这些组合不达 AA：\n      ' + table.join('\n      '))
  })

  it('每套主题都定义了五类标签的底色/描边/正文（漏定义会在这里红，而不是回退到粉彩）', () => {
    for (const theme of THEME_NAMES) {
      const d = themeDecls(theme)
      for (const type of TYPES) {
        for (const part of ['bg', 'border', 'fg']) {
          assert.ok(d[`--tag-${type}-${part}`], `${theme} 缺少 --tag-${type}-${part}`)
        }
      }
    }
  })

  it('showcase 的标签底色合成后仍是深色（暗色页里不能出现浅色孤岛）', () => {
    for (const type of TYPES) {
      for (const variant of ['default', 'dark']) {
        const { bg } = ratioOf('showcase', type, variant)
        assert.ok(luminance(bg) < 0.2, `showcase/${type}/${variant} 的底色 ${bg} 仍是浅色`)
      }
    }
  })

  it('global.scss 把 default/plain/dark 三种 effect 都接到 --tag-*，选择器带 html 前缀', () => {
    for (const type of TYPES) {
      const base = new RegExp(
        `html\\s+\\.el-tag\\.el-tag--${type}\\s*\\{[^}]*--el-tag-text-color:\\s*var\\(--tag-${type}-fg\\)[^}]*--el-tag-bg-color:\\s*var\\(--tag-${type}-bg\\)[^}]*--el-tag-border-color:\\s*var\\(--tag-${type}-border\\)`,
      )
      assert.match(GLOBAL, base, `.el-tag--${type} 没把正文/底色/描边指到 --tag-${type}-*`)

      const plain = new RegExp(
        `html\\s+\\.el-tag\\.el-tag--plain\\.el-tag--${type}\\s*\\{[^}]*--el-tag-bg-color:\\s*var\\(--el-fill-color-blank\\)`,
      )
      assert.match(GLOBAL, plain, `plain ${type} 标签没保住「页面底」的观感`)

      const dark = new RegExp(
        `html\\s+\\.el-tag\\.el-tag--dark\\.el-tag--${type}\\s*\\{[^}]*--el-tag-bg-color:\\s*var\\(--tag-${type}-bg\\)[^}]*--el-tag-border-color:\\s*var\\(--tag-${type}-border\\)`,
      )
      assert.match(GLOBAL, dark, `dark ${type} 标签没走 --tag-${type}-*，粉彩实底 + 白字会回来`)
    }
    // 反向：谁把正文改回 --el-color-* / --color-* 粉彩，这里直接红
    assert.doesNotMatch(
      GLOBAL,
      /--el-tag-text-color:\s*var\(--el-color-/,
      '标签正文又指回了 --el-color-*（粉彩），对比度会再次跌到 1.x:1',
    )
  })

  it('showcase 的 .el-tag--* 直接声明的 color 也取 token，不再写死亮色字面量', () => {
    for (const type of TYPES) {
      const literal = new RegExp(`\\.el-tag--${type}\\s*\\{[^}]*color:\\s*var\\(--tag-${type}-fg\\)`)
      assert.match(THEMES, literal, `themes.scss 的 .el-tag--${type} 没消费 --tag-${type}-fg`)
    }
  })

  it('负向对照：粉彩正文压浅底确实不达标，强色达标', () => {
    assert.ok(contrast('#B5EAD7', '#F0F9EB') < 4.5, '粉彩 success 竟然算达标，公式有问题')
    assert.ok(contrast('#FFE5B4', '#FDF6EC') < 4.5, '粉彩 warning 竟然算达标，公式有问题')
    assert.ok(contrast('#7ECEC1', '#B5EAD7') < 4.5, '粉彩 primary 正文压主色浅底竟然算达标')
    assert.ok(contrast('#1F6B45', '#F0F9EB') >= 4.5, '强色 success 反而不达标')
    assert.ok(contrast('#2D6B5F', '#B5EAD7') >= 4.5, '强色 primary 反而不达标')
  })

  // 门禁不接线等于没有：日常跑的是 npm run test:unit，文件不在里面就没人会碰它
  it('已接进 npm run test:unit', () => {
    const pkg = JSON.parse(readFileSync(new URL('../../package.json', import.meta.url), 'utf8'))
    assert.match(
      pkg.scripts['test:unit'],
      /tests\/unit\/tag-contrast\.test\.mjs/,
      '门禁没接进 test:unit，日常单测不会跑它',
    )
  })
})
