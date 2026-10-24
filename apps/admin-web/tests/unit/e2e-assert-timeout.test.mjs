/**
 * T02778：e2e 断言超时的口径门禁
 *
 * 坑长这样：`test.use({ expect: { timeout: 30000 } })` 看着像「这份 spec 的断言窗口放宽到 30s」，
 * 实际是**空选项**——Playwright 1.61 的 TestOptions 里没有 `expect` 这一项
 * （`node_modules/playwright/types/test.d.ts` 查无 ExpectOptions），传进去被静默忽略，
 * 失败日志里仍然打印 `Timeout: 5000ms`。
 *
 * 后果不是「白写一行」，而是**假失败**：断言窗口比首屏挂载短，用例单独跑绿、全量并发跑红，
 * 而失败快照里那个元素明明已经在页面上了。真凶是超时口径，不是功能没做出来。
 *
 * 正确机制只有两个：
 * - 具体断言上显式传 `{ timeout: N }`（对 `expect.poll` 无效，poll 的超时是第二参
 *   `expect.poll(fn, { timeout })`）；
 * - `expect.configure({ timeout: N })` 派生一个本文件专用的断言器（实测只作用于派生对象，
 *   不改全局默认，也不污染同 worker 的其他文件）。
 *
 * 这里守的是「别再写回空选项」与「poll 的超时别挂错位置」两条。扫描前先把注释抹成空白
 * （保留换行与位置）：注释里复述这些坑是踩坑记录，不能被门禁误杀。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/e2e-assert-timeout.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it } from 'node:test'

const TESTS_DIR = fileURLToPath(new URL('../', import.meta.url))

function listSpecs(dir) {
  const out = []
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) {
      if (name === 'unit' || name === 'helpers') continue
      out.push(...listSpecs(full))
    } else if (name.endsWith('.spec.js')) {
      out.push(full)
    }
  }
  return out
}

/** 注释抹成空格（换行保留），字符串原样保留；位置不变，行号能直接指回原文。 */
function stripComments(src) {
  let out = ''
  let i = 0
  while (i < src.length) {
    const c = src[i]
    const n = src[i + 1]
    if (c === '/' && n === '/') {
      while (i < src.length && src[i] !== '\n') {
        out += ' '
        i += 1
      }
    } else if (c === '/' && n === '*') {
      out += '  '
      i += 2
      while (i < src.length && !(src[i] === '*' && src[i + 1] === '/')) {
        out += src[i] === '\n' ? '\n' : ' '
        i += 1
      }
      if (i < src.length) {
        out += '  '
        i += 2
      }
    } else if (c === '"' || c === "'" || c === '`') {
      out += c
      i += 1
      while (i < src.length) {
        if (src[i] === '\\') {
          out += src[i] + (src[i + 1] ?? '')
          i += 2
          continue
        }
        out += src[i]
        const done = src[i] === c
        i += 1
        if (done) break
      }
    } else {
      out += c
      i += 1
    }
  }
  return out
}

/** openParen 指向 '('，返回括号内的完整实参文本（支持嵌套括号）。 */
function callArgs(src, openParen) {
  let depth = 0
  for (let i = openParen; i < src.length; i += 1) {
    if (src[i] === '(') depth += 1
    else if (src[i] === ')') {
      depth -= 1
      if (depth === 0) return src.slice(openParen + 1, i)
    }
  }
  return src.slice(openParen + 1)
}

const lineOf = (src, idx) => src.slice(0, idx).split('\n').length

const specs = listSpecs(TESTS_DIR).map((file) => {
  const raw = readFileSync(file, 'utf8')
  return { file, code: stripComments(raw) }
})

describe('T02778 断言超时口径', () => {
  it('测试目录里确实有 spec（否则下面的门禁是空的，等于没守）', () => {
    assert.ok(specs.length >= 30, `只找到 ${specs.length} 个 spec，清单口径可能坏了`)
  })

  it('不许再写 test.use({ expect: { timeout } })：Playwright 1.61 无此选项，会被静默忽略', () => {
    const offenders = []
    for (const { file, code } of specs) {
      for (let i = code.indexOf('test.use('); i !== -1; i = code.indexOf('test.use(', i + 1)) {
        const args = callArgs(code, i + 'test.use'.length)
        // 只看对象字面量顶层的 expect 键：`{ viewport: {...}, expect: {...} }` 同样要抓
        if (/(^|[{,])\s*expect\s*:/.test(args)) {
          offenders.push(`${file}:${lineOf(code, i)}: test.use({ … expect: … })`)
        }
      }
    }
    assert.deepEqual(
      offenders,
      [],
      `这些 test.use 里又写回了 expect 选项（空选项，运行时被忽略，却让人以为放宽了超时）：\n${offenders.join('\n')}`,
    )
  })

  it('expect.poll 的超时只能写在 expect.poll(fn, { timeout }) 上，不许挂在终断言上', () => {
    const offenders = []
    for (const { file, code } of specs) {
      for (let i = code.indexOf('expect.poll('); i !== -1; i = code.indexOf('expect.poll(', i + 1)) {
        const pollArgs = callArgs(code, i + 'expect.poll'.length)
        let after = i + 'expect.poll('.length + pollArgs.length + 1
        // 链式断言：跳过空白与一个或多个 .xxx 成员访问，找到第一个匹配器调用
        while (true) {
          const m = /^\s*\.\s*[A-Za-z_$][\w$]*\s*/.exec(code.slice(after))
          if (!m) break
          after += m[0].length
          if (code[after] !== '(') continue
          const matcherName = /\.\s*([A-Za-z_$][\w$]*)/.exec(m[0])?.[1] ?? ''
          const matcherArgs = callArgs(code, after)
          // 只有当它是 expect 的匹配器（to*/not 等）并且实参里带了 timeout 才算挂错
          if (/^to/.test(matcherName) && /,\s*\{\s*timeout\s*:/.test(matcherArgs)) {
            offenders.push(`${file}:${lineOf(code, i)}: expect.poll(…) 的 timeout 挂在了 .${matcherName} 的终断言上`)
          }
          after += matcherArgs.length + 2
          break
        }
      }
    }
    assert.deepEqual(
      offenders,
      [],
      `poll 的超时挂错位置了（实测写 1.2s 仍按 5s 走完）：\n${offenders.join('\n')}`,
    )
  })

  it('确实需要放宽的用例走 expect.configure 派生断言器或断言上的 { timeout }', () => {
    let configure = 0
    let perAssertion = 0
    for (const { code } of specs) {
      if (/expect\.configure\(\{\s*timeout/.test(code)) configure += 1
      if (/\.to[A-Za-z]+\([^)]*\{\s*timeout/.test(code)) perAssertion += 1
    }
    assert.ok(configure >= 1, '一份 spec 都没用 expect.configure 派生断言器：放宽口径没有落地示范')
    assert.ok(perAssertion >= 10, `断言级 timeout 几乎没有（${perAssertion} 处），多半又被删回去了`)
  })
})
