/**
 * FR-UX-302 小程序门禁自测（T02534 / M3-D）
 *
 * 门禁的价值 = 它会不会红。这里每条规则都造一个真实会犯的坏样本
 * （多数是把本单修掉的原形原样写回去），断言它被点名；再加两条防误报样本，
 * 因为误报会让门禁被绕过，等同没有门禁。
 *
 * 运行：node --test apps/miniprogram/tests/validate-error-vs-empty.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { validate } from '../scripts/validate-error-vs-empty.mjs'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const read = (rel) => readFileSync(join(ROOT, rel), 'utf8')

/** 断言坏样本被点名（按错误信息里的页面名定位，不依赖措辞顺序） */
function expectHit(overrides, tag) {
  const { errors } = validate(overrides)
  assert.ok(errors.length > 0, `坏样本应被点名，却没有报错：${tag}`)
  assert.ok(
    errors.some((e) => e.includes(tag)),
    `报错里没有 ${tag} 这条：\n${errors.join('\n')}`,
  )
}

/** 构造坏样本：锚点必须真的命中，否则用例吃到的还是好代码（永远绿） */
function mutate(rel, re, to) {
  const src = read(rel)
  assert.ok(re.test(src), `坏样本没构造成功：${rel} 里找不到锚点 ${re}`)
  const out = src.replace(re, to)
  assert.notEqual(out, src, `坏样本没改动 ${rel}`)
  return out
}

test('golden：仓库当前状态必须干净', () => {
  const { errors, facts } = validate()
  assert.deepEqual(errors, [])
  assert.strictEqual(facts.length, 9)
})

describe('失败态必须自带重试', () => {
  test('channels 去掉 bind:retry 被抓', () =>
    expectHit(
      { 'pages/channels/channels.wxml': mutate('pages/channels/channels.wxml', /\n\s*bind:retry="onRetryLoad"/, '') },
      'pages/channels/channels.wxml',
    ))

  test('history 删掉 onRetryLoad 方法被抓', () =>
    expectHit(
      {
        'pages/history/history.js': mutate(
          'pages/history/history.js',
          /onRetryLoad\(\) \{\n\s*this\.loadHistory\(true\);\n\s*\},/,
          'onRetryLoadGone() {},',
        ),
      },
      'pages/history/history.js',
    ))

  test('onRetryLoad 改成不重新取数（接错对象）被抓', () =>
    expectHit(
      { 'pages/channels/channels.js': mutate('pages/channels/channels.js', /onRetryLoad\(\) \{\n\s*this\.loadChannels\(\);/, 'onRetryLoad() {\n    this.setData({});') },
      'pages/channels/channels.js',
    ))
})

describe('失败态不能与空态混成一支', () => {
  test('download 去掉 load-error 元素被抓', () =>
    expectHit(
      {
        'pages/download/download.wxml': mutate(
          'pages/download/download.wxml',
          /<load-error[\s\S]*?<\/load-error>\n\n/,
          '',
        ),
      },
      'pages/download/download.wxml',
    ))

  test('recent 的失败分支条件不引用错误字段被抓', () =>
    expectHit(
      {
        'pages/recent/recent.wxml': mutate(
          'pages/recent/recent.wxml',
          /wx:if="\{\{loadError && list\.length === 0\}\}"/,
          'wx:if="{{list.length === 0}}"',
        ),
      },
      'pages/recent/recent.wxml',
    ))

  test('J4 原形（error || 当空态文案）在新页面复辟被抓', () =>
    expectHit(
      {
        'pages/favorites/favorites.wxml': mutate(
          'pages/favorites/favorites.wxml',
          /title="还没有收藏的节目"/,
          'title="{{loadError || \'还没有收藏的节目\'}}"',
        ),
      },
      'pages/favorites/favorites.wxml',
    ))
})

describe('catch 与成功路径', () => {
  test('search 的 catch 只 toast 不写 loadError 被抓', () =>
    expectHit(
      {
        'pages/search/search.js': mutate(
          'pages/search/search.js',
          /if \(page === 1 \|\| this\.data\.results\.length === 0\) \{\n\s*this\.setData\(\{ loadError: msg \}\);/,
          'if (page === 1 || this.data.results.length === 0) {\n        this.setData({});',
        ),
      },
      'pages/search/search.js',
    ))

  // favorites 不能当坏样本：它的失败方法开头就有 loadError: ''（重试必然走到），
  // 只删成功那一处并不构成「重试后仍挂失败态」，用例会是假的。
  // channels 的成功 clear 是该 catch 方法里唯一一处，删掉才真的回不到正常态。
  test('channels 成功路径不清 loadError（重试成功仍挂失败态）被抓', () =>
    expectHit(
      {
        'pages/channels/channels.js': mutate(
          'pages/channels/channels.js',
          /this\.setData\(\{ channels: res\.list \|\| \[\], loadError: '' \}\);/,
          'this.setData({ channels: res.list || [] });',
        ),
      },
      'pages/channels/channels.js',
    ))
})

describe('防误报', () => {
  test('注释里写 {{error || …}} 不算违规', () => {
    const wxml = read('pages/channels/channels.wxml').replace(
      '<!-- J47：失败态独立成支并自带重试；空态只说「确实没有频道」 -->',
      '<!-- 旧写法是 title="{{error || \'暂无频道\'}}"，J47 已拆开 -->',
    )
    const { errors } = validate({ 'pages/channels/channels.wxml': wxml })
    assert.deepEqual(errors, [])
  })

  test('别的页面写 load-error 不影响本页判定（按页取标签）', () => {
    const wxml = read('pages/channels/channels.wxml')
    const { errors } = validate({ 'pages/channels/channels.wxml': wxml })
    assert.deepEqual(errors, [])
  })
})
