/**
 * 主色文字对比度门禁（T03588，源自 T02549 真实数据抽查）
 *
 * macaron 的主色是浅薄荷 #7ECEC1。拿它当文字或当实底，哪里都不达标：
 *   - 白字压在 #7ECEC1 上 1.83:1（壳层头像，Element Plus 写死白色）；
 *   - 链接字 #7ECEC1 压白卡 1.78:1（EP 把 .el-link--primary 指到 --el-color-primary）；
 *   - 旧 --on-primary #2D6B5F 压 #7ECEC1 也只有 3.40:1，单选按钮选中态因此不达标。
 *
 * 这里在源码层把三件事钉住：
 *   1) 6 套主题 × (--on-primary on --color-primary) 与
 *      (--color-primary-dark on 卡片/页面底) 都必须 ≥ 4.5；
 *   2) 头像、选中单选的实底字色、主色链接的规则必须写在**全主题**的顶层块里
 *      （原来只写在 [data-theme='showcase'] 内，浅色主题拿不到）；
 *   3) 壳层 Layout.vue 的头像不能再写死白色；
 * 外加一条负向对照：旧值确实不达标，否则公式或取色有问题。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/light-theme-contrast.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

const SRC = new URL('../../src/', import.meta.url)
const read = (rel) => readFileSync(new URL(rel, SRC), 'utf8')

const VARIABLES = read('styles/variables.scss')
const THEMES = read('styles/themes.scss')
const LAYOUT = read('layouts/Layout.vue')

const THEME_NAMES = ['macaron', 'enterprise', 'creative', 'showcase', 'commerce', 'portfolio']

/** 去掉注释再解析：注释里写「原来是 #fff」不算定义 */
function stripComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/[^\n]*/g, '$1')
}

/** 取顶层块；缩进的嵌套规则不算顶层（与 tag-contrast.test.mjs 同一套解析） */
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

/** variables.scss 的 :root 与 themes.scss 里命中的块按文件顺序叠加 */
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

/** 只接受「字面量」或单个 var(--x) 链，解析不到就红，避免静默拿错值去算 */
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

const contrast = (fg, bg) => {
  const [hi, lo] = [luminance(fg), luminance(bg)].sort((a, b) => b - a)
  return (hi + 0.05) / (lo + 0.05)
}

const ratioOf = (theme, fgToken, bgToken) => {
  const d = themeDecls(theme)
  const fg = resolveToken(fgToken, d)
  const bg = resolveToken(bgToken, d)
  return { fg, bg, ratio: +contrast(fg, bg).toFixed(2) }
}

describe('主色文字对比度门禁（T03588）', () => {
  it('6 套主题：--on-primary 压 --color-primary ≥ 4.5:1', () => {
    const failures = []
    const table = []
    for (const theme of THEME_NAMES) {
      const { fg, bg, ratio } = ratioOf(theme, '--on-primary', '--color-primary')
      table.push(`${theme} ${fg} on ${bg} = ${ratio}:1`)
      if (ratio < 4.5) failures.push(table[table.length - 1])
    }
    assert.deepEqual(failures, [], '主色实底上的文字不达 AA：\n      ' + table.join('\n      '))
  })

  it('6 套主题：--color-primary-dark 当文字，在卡片与页面底上都要 ≥ 4.5:1', () => {
    const failures = []
    const table = []
    for (const theme of THEME_NAMES) {
      for (const bgToken of ['--color-bg-card', '--color-bg']) {
        const { fg, bg, ratio } = ratioOf(theme, '--color-primary-dark', bgToken)
        table.push(`${theme} ${fg} on ${bg} = ${ratio}:1`)
        if (ratio < 4.5) failures.push(table[table.length - 1])
      }
    }
    assert.deepEqual(failures, [], '主色链接文字不达 AA：\n      ' + table.join('\n      '))
  })

  it('头像与选中单选的实底字色走全主题顶层规则，不再锁在 showcase 里', () => {
    const blocks = topLevelBlocks(THEMES)
    const solid = blocks.find((b) =>
      b.selector.includes('.el-avatar') &&
      b.selector.includes('.el-radio-button__original-radio:checked + .el-radio-button__inner'),
    )
    assert.ok(solid, '没找到覆盖头像 + 单选按钮选中态的全主题顶层规则')
    assert.match(
      solid.body.join('\n'),
      /color:\s*var\(--on-primary\)\s*!important/,
      '实底字色没吃 --on-primary（白字压浅主色会回到 1.83:1）',
    )

    const showcase = blocks.find((b) => b.selector === "[data-theme='showcase']")
    assert.ok(showcase, 'showcase 主题块没了')
    assert.doesNotMatch(
      showcase.body.join('\n'),
      /\.el-avatar\s*\{/,
      '头像规则又写回了 showcase 块内，浅色主题会再次拿不到',
    )
  })

  it('主色链接改用 --color-primary-dark，选中单选的标签字改用 --color-text-primary', () => {
    const blocks = topLevelBlocks(THEMES)
    const link = blocks.find((b) => b.selector.includes('.el-link.el-link--primary'))
    assert.ok(link, '没找到 .el-link.el-link--primary 的全主题规则')
    assert.match(
      link.body.join('\n'),
      /color:\s*var\(--color-primary-dark\)/,
      '主色链接没改吃 --color-primary-dark（浅薄荷当文字只有 1.78:1）',
    )

    const radioLabel = blocks.find((b) => b.selector.includes('.el-radio__input.is-checked + .el-radio__label'))
    assert.ok(radioLabel, '没找到选中单选标签的全主题规则')
    assert.match(
      radioLabel.body.join('\n'),
      /color:\s*var\(--color-text-primary\)\s*!important/,
      '选中单选的标签字没改吃 --color-text-primary',
    )
  })

  it('壳层头像不再写死白色', () => {
    assert.match(LAYOUT, /\.user-avatar\s*\{[^}]*color:\s*var\(--on-primary\)/s, '壳层 .user-avatar 没吃 --on-primary')
    assert.doesNotMatch(LAYOUT, /\.user-avatar\s*\{[^}]*color:\s*white/s, '壳层 .user-avatar 又写死了白色')
  })

  it('浅色主题：EP 次级文字/占位符改吃 --color-text-secondary，六主题都 ≥ 4.5:1', () => {
    const light = ['macaron', 'enterprise', 'creative', 'commerce', 'portfolio']
    const blocks = topLevelBlocks(THEMES)
    const mapped = blocks.find(
      (b) =>
        light.every((t) => b.selector.includes(`[data-theme='${t}']`)) &&
        b.body.join('\n').includes('--el-text-color-secondary'),
    )
    assert.ok(mapped, '没找到浅色主题的 --el-text-color-secondary 映射块')
    assert.ok(!mapped.selector.includes('showcase'), '映射块不要把 showcase 也圈进来（它有自己的一套深色取值）')

    const failures = []
    const table = []
    for (const theme of THEME_NAMES) {
      for (const token of ['--el-text-color-secondary', '--el-text-color-placeholder']) {
        for (const bgToken of ['--color-bg-card', '--color-bg']) {
          const { fg, bg, ratio } = ratioOf(theme, token, bgToken)
          table.push(`${theme} ${token} ${fg} on ${bg} = ${ratio}:1`)
          if (ratio < 4.5) failures.push(table[table.length - 1])
        }
      }
    }
    assert.deepEqual(failures, [], '次级文字/占位符不达 AA：\n      ' + table.join('\n      '))
  })

  it('Tab 选中态 / 分页选中页 / 复选框选中标签 / 下拉选中项也走语义 token', () => {
    assert.match(THEMES, /html \.el-tabs__item\.is-active,\s*html \.el-tabs__item:hover\s*\{[^}]*var\(--color-primary-dark\)/, 'Tab 选中/悬浮仍是主色文字')
    assert.match(
      THEMES,
      /html \.el-pagination \.el-pager li\.is-active,\s*html \.el-pagination\.is-background \.el-pager li\.is-active\s*\{[^}]*background-color:\s*var\(--color-primary\)[^}]*color:\s*var\(--on-primary\)/,
      '分页选中页没改成「主色实底 + --on-primary」',
    )
    assert.match(THEMES, /html \.el-pagination \.el-pager li:hover,\s*html \.el-pagination\.is-background \.el-pager li:not\(\.is-disabled\):hover\s*\{[^}]*var\(--color-primary-dark\)/, '分页悬浮仍是主色文字')
    assert.match(
      THEMES,
      /html \.el-checkbox__input\.is-checked \+ \.el-checkbox__label\s*\{[^}]*var\(--color-text-primary\)/,
      '复选框选中标签仍是主色文字',
    )
    assert.match(
      THEMES,
      /html \.el-select-dropdown__item\.is-selected\s*\{[^}]*var\(--color-primary-dark\)/,
      '下拉选中项仍是主色文字',
    )
  })

  it('负向对照：浅薄荷主色上的白字/旧 --on-primary 确实不达标', () => {
    assert.ok(contrast('#FFFFFF', '#7ECEC1') < 4.5, '白字 on 浅薄荷竟然算达标，公式有问题')
    assert.ok(contrast('#2D6B5F', '#7ECEC1') < 4.5, '旧 --on-primary 竟然算达标，门禁等于没测到东西')
    assert.ok(contrast('#1B4A42', '#7ECEC1') >= 4.5, '新 --on-primary 反而不达标')
  })

  it('已接进 npm run test:unit', () => {
    const pkg = JSON.parse(readFileSync(new URL('../../package.json', import.meta.url), 'utf8'))
    assert.match(
      pkg.scripts['test:unit'],
      /tests\/unit\/light-theme-contrast\.test\.mjs/,
      '门禁没接进 test:unit，日常单测不会跑它',
    )
  })
})
