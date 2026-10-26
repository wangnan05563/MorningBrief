/**
 * 移动端主题令牌门禁（T02839）
 *
 * `/m/*` 外壳与 12 个视图此前颜色全部硬编码浅色：换到暗色主题时整页仍是白底，
 * 次级文字 #8a8f99 压 #fff 只有 3.25:1。改完靠 `nfr04-compat.spec.js` 的
 * 对比度/白底孤岛测量兜底，但那是 e2e，跑一段要 20s；这里用源码扫描把
 * 「又有人写死一个 #fff」挡在更便宜的一层。
 *
 * 允许保留的只有 box-shadow 里的 rgba：投影在暗色下本来就看不见，
 * 且不构成文字背景，不参与对比度。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/mobile-theme-tokens.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, it } from 'node:test'

const SRC = new URL('../../src/', import.meta.url)
const read = (rel) => readFileSync(new URL(rel, SRC), 'utf8')

const MOBILE_DIR = fileURLToPath(new URL('views/mobile/', SRC))
const MOBILE_VIEWS = readdirSync(MOBILE_DIR)
  .filter((f) => f.endsWith('.vue'))
  .sort()
const LAYOUT = 'layouts/MobileLayout.vue'
const FILES = [LAYOUT, ...MOBILE_VIEWS.map((f) => `views/mobile/${f}`)]

const VARIABLES = read('styles/variables.scss')
const THEMES = read('styles/themes.scss')

/** 去掉 HTML / CSS / JS 注释后再扫：注释里写「原来是 #fff」不算违规 */
function stripComments(text) {
  return text
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    // 行注释前面必须有空白或行首，避免把 https:// 当成注释吃掉半行
    .replace(/(^|\s)\/\/[^\n]*/g, '$1')
}

const HEX_RE = /#[0-9a-fA-F]{3,8}\b/g
const RGB_RE = /\brgba?\([^)]*\)/g

/**
 * 找出写死颜色的行。返回 `{ line, token }`，file 由调用方补。
 * 只扫样式值：box-shadow 行的 rgba 放过（见文件头说明）。
 */
export function collectColorLiterals(source) {
  const hits = []
  stripComments(source)
    .split('\n')
    .forEach((text, i) => {
      const tokens = [...(text.match(HEX_RE) || []), ...(text.match(RGB_RE) || [])]
      for (const token of tokens) {
        if (token.startsWith('rgb') && /box-shadow\s*:/.test(text)) continue
        hits.push({ line: i + 1, token })
      }
    })
  return hits
}

describe('移动端颜色必须走主题令牌（T02839）', () => {
  it('扫得到真实的移动端文件（不是空集合）', () => {
    assert.ok(MOBILE_VIEWS.length >= 12, `只扫到 ${MOBILE_VIEWS.length} 个移动端视图`)
    assert.ok(FILES.every((rel) => read(rel).length > 200))
  })

  it('13 个移动端文件里没有写死的颜色', () => {
    const offenders = FILES.flatMap((rel) =>
      collectColorLiterals(read(rel)).map((h) => `${rel}:${h.line} ${h.token}`),
    )
    assert.deepEqual(
      offenders,
      [],
      '移动端又出现了写死颜色，暗色主题会重新变白/变糊：\n      ' + offenders.join('\n      '),
    )
  })

  it('负向对照：样例里的 #fff 会被抓到，box-shadow 的 rgba 不误报', () => {
    const sample = `
      .a { background: #fff; }
      /* 注释里的 #1f2329 不算 */
      .b { box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04); }
      .c { color: rgba(0, 0, 0, 0.6); }
    `
    const hits = collectColorLiterals(sample).map((h) => h.token)
    assert.deepEqual(hits, ['#fff', 'rgba(0, 0, 0, 0.6)'])
  })

  it('移动端引用的每个 --m-* 都有定义（拼错不会被静默忽略）', () => {
    const defined = new Set(
      [...VARIABLES.matchAll(/(--m-[a-z0-9-]+)\s*:/g), ...THEMES.matchAll(/(--m-[a-z0-9-]+)\s*:/g)].map(
        (m) => m[1],
      ),
    )
    const used = new Set(
      FILES.flatMap((rel) => [...read(rel).matchAll(/var\((--m-[a-z0-9-]+)/g)].map((m) => m[1])),
    )
    const missing = [...used].filter((name) => !defined.has(name))
    assert.deepEqual(missing, [], `这些令牌没有定义：${missing.join(', ')}`)
    // 反向也钉住：定义层里至少要有壳层背景/卡片/文字三件套
    for (const name of ['--m-bg', '--m-surface', '--m-text', '--m-text-sub']) {
      assert.ok(defined.has(name), `${name} 没定义`)
    }
  })

  it('移动端不借用 Element Plus 变量（它的次级文字 #909399 在浅色下只有 3:1）', () => {
    const offenders = FILES.filter((rel) => /var\(--el-/.test(read(rel)))
    assert.deepEqual(
      offenders,
      [],
      '这些文件还在用 --el-* 变量，移动端对比度不受 --m-* 约束：\n      ' + offenders.join('\n      '),
    )
  })

  it('壳层三段跟随主题，而不是自己一套浅色', () => {
    const layout = read(LAYOUT)
    assert.match(layout, /\.m-app\s*\{[^}]*background:\s*var\(--m-bg\)/)
    assert.match(layout, /\.m-app\s*\{[^}]*color:\s*var\(--m-text\)/)
    assert.match(layout, /\.m-appbar\s*\{[^}]*background:\s*var\(--m-surface\)/)
    assert.match(layout, /\.m-tabbar\s*\{[^}]*background:\s*var\(--m-surface\)/)
  })

  // 这一条来自实测：禁用态把底色改浅后仍沿用 on-solid 深字，showcase 下只有 1.09:1
  it('一键全部审批的禁用态有自己的一对可读配色', () => {
    const rule = /\.m-btn--approve-all:disabled\s*\{([^}]*)\}/.exec(read('views/mobile/ReviewList.vue'))
    assert.ok(rule, '找不到 .m-btn--approve-all:disabled 规则')
    assert.match(rule[1], /color:\s*var\(--m-success\)/)
    assert.match(rule[1], /background:\s*var\(--m-success-soft\)/)
  })

  it('六个主题都定义了移动端令牌（showcase 反相成亮底深字）', () => {
    const blocks = [...THEMES.matchAll(/\[data-theme='([a-z]+)'\]\s*\{/g)].map((m) => m[1])
    assert.ok(blocks.length >= 6, `只找到 ${blocks.length} 套主题`)
    const showcase = /\[data-theme='showcase'\]\s*\{([\s\S]*?)\n\}/.exec(THEMES)
    assert.ok(showcase, '找不到 showcase 主题块')
    assert.match(showcase[1], /--m-on-solid:\s*var\(--on-primary\)/)
    assert.match(showcase[1], /--m-solid-primary:\s*var\(--color-primary\)/)
  })
})
