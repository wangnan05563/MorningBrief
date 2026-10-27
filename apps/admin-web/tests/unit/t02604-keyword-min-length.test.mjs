/**
 * T02604：关键词白名单长度护栏的前端接线。
 *
 * 后端是唯一来源（app/core/keyword_guard.py），阈值随配置接口的 keyword_limits 下发。
 * 这里守三件事：判定语义与后端一致、界面不自己抄一份数字、短词确实被拦。
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { filterTooShort, keywordTooShort, minLengthHint } from '../../src/utils/keywordGuard.js'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const read = (p) => readFileSync(resolve(ROOT, p), 'utf8')

// 与后端 limits_payload() 同形的两份数：汉字 2、纯英文 3
const LIMITS = { min_length: 2, ascii_min_length: 3, rule: 'substring' }

test('短词判定与后端同口径：混排词看是否含非 ASCII', () => {
  assert.equal(keywordTooShort('中', LIMITS), true, '单字汉字必须拦（实测命中 82/83 篇）')
  assert.equal(keywordTooShort('AI', LIMITS), true, '两字母英文词必须拦（EA/OK 全是内嵌误命中）')
  assert.equal(keywordTooShort('时政', LIMITS), false, '两字汉字词是有效粒度，不能顺手拦掉')
  assert.equal(keywordTooShort('PS5', LIMITS), false, '3 字母词实测零内嵌，拦掉就是过度收紧')
  assert.equal(keywordTooShort('人工智能', LIMITS), false)
  assert.equal(keywordTooShort('OpenAI', LIMITS), false)
  assert.equal(keywordTooShort('AI审核', LIMITS), false, '含汉字的短串按汉字口径放行')
})

test('配置没加载完时一律判不拦（拿不到数就不能误拦）', () => {
  assert.equal(keywordTooShort('中', null), false)
  assert.deepEqual(filterTooShort(['中', 'AI', '时政'], null), [])
  assert.deepEqual(filterTooShort(['时政', '中', 'AI'], LIMITS), ['中', 'AI'])
})

test('提示语的量词随词形变，数取自下发值', () => {
  assert.equal(minLengthHint('中', LIMITS), '至少 2 个字')
  assert.equal(minLengthHint('AI', LIMITS), '至少 3 个字母')
})

test('界面只读 keyword_limits，不自己抄阈值', () => {
  const vue = read('src/views/system/AutoReviewConfig.vue')
  assert.match(vue, /config\.value\?\.keyword_limits/, '阈值要从配置接口读')
  assert.match(vue, /from '\.\.\/\.\.\/utils\/keywordGuard'/, '判定要在 utils 里，页面不重写一份')
  assert.doesNotMatch(vue, /min_length\s*[<>]=?\s*\d/, '页面里出现字面量阈值就是两侧漂移的开始')
  assert.doesNotMatch(vue, /ascii_min_length\s*[<>]=?\s*\d/)

  const guard = read('src/utils/keywordGuard.js')
  assert.doesNotMatch(guard, /\b(min_length|ascii_min_length)\s*[<>=!]==?\s*\d/,
    '前端不允许固化后端 thresholds，否则改一边就悄悄分叉')
})

test('添加与展示都按同一份判定走', () => {
  const vue = read('src/views/system/AutoReviewConfig.vue')
  assert.match(vue, /if \(keywordTooShort\(kw\)\)[\s\S]{0,220}return/, '拦住后不能再 push')
  assert.match(vue, /:type="keywordTooShort\(kw\) \? 'danger' : 'primary'"/, '存量短词要标红，不能装成有效词')
  assert.match(vue, /shortKeywords\.length/, '页内要点名是哪几个词过短')
  assert.match(vue, /按子串包含匹配/)
})

test('后端 thresholds 与前端读到的字段名对得上', () => {
  const py = read('../../backend/app/core/keyword_guard.py')
  assert.match(py, /"min_length": MIN_LENGTH_NON_ASCII/)
  assert.match(py, /"ascii_min_length": MIN_LENGTH_ASCII/)
  assert.match(py, /"rule": "substring"/, '口径字段名变了，前端 placeholder 会静默空掉')
})

test('本文件用的那份数就是后端现值（后端改阈值，这里必须跟着红一次）', () => {
  const py = read('../../backend/app/core/keyword_guard.py')
  const nonAscii = Number(py.match(/MIN_LENGTH_NON_ASCII = (\d+)/)[1])
  const ascii = Number(py.match(/MIN_LENGTH_ASCII = (\d+)/)[1])
  assert.equal(LIMITS.min_length, nonAscii, '后端汉字下限已改，测试夹具与提示文案要一起复核')
  assert.equal(LIMITS.ascii_min_length, ascii, '后端英文下限已改，测试夹具与提示文案要一起复核')
  assert.ok(ascii > nonAscii, '英文下限必须高于汉字，否则 2 字母词又放进来了')
})

test('回车添加不能被浏览器隐式提交吃掉（真机验收时实测到会整页刷新）', () => {
  const vue = read('src/views/system/AutoReviewConfig.vue')
  const formTag = vue.match(/<el-form[\s\S]*?>/)[0]
  assert.match(
    formTag,
    /@submit\.prevent/,
    '本页只有一个文本输入框，回车会触发原生表单提交（URL 变成 ?）并整页刷新，' +
      '刚加进白名单还没保存的关键词会被刷掉——验收步骤 4 实测到过',
  )
})
