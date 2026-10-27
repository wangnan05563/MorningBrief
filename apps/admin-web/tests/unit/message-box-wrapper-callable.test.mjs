/**
 * T03321：统一提示出口的 ElMessageBox 包装体必须可调用。
 *
 * 真机验收第一版就是死在这里：包装器写成 `Object.assign({}, _ElMessageBox)`，
 * 普通对象不可调用，`ElMessageBox(VNode, ...)` 直接 TypeError，
 * 确认框根本没弹出来（页面只在控制台里报错，用例是纯文本断言时看不出来）。
 * 所以这里既锁住导出形态，也锁住「调用方确实以函数形态在用它」。
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const read = (p) => readFileSync(resolve(ROOT, p), 'utf8')

test('ElMessageBox 包装体保持可调用，并沿用隐藏页拦截语义', () => {
  const src = read('src/utils/message.js')
  assert.match(
    src,
    /const safeElMessageBox = Object\.assign\(\s*\(\.\.\.args\) =>/,
    '包装体必须是函数：Object.assign({}, fn) 会让 ElMessageBox(...) 调用报 TypeError',
  )
  assert.match(src, /return _ElMessageBox\(\.\.\.args\)/)
  assert.match(src, /if \(_shouldBlock\(\)\) return Promise\.reject\(new Error\('页面隐藏时阻止弹窗'\)\)\s*\n\s*return _ElMessageBox/)
})

test('调用方确实以函数形态使用 ElMessageBox（否则上一条断言锁的是死代码）', () => {
  const src = read('src/utils/dangerConfirm.js')
  assert.match(src, /await ElMessageBox\(/)
})
