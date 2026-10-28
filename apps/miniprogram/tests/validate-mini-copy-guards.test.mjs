/**
 * validate-mini-copy-guards.mjs 的证伪用例（T02544 / J13·J33·J44·J58·J92）
 *
 * 门禁永远绿就没有意义：这里逐条把真实源码副本改成坏样本，断言每种坏状态都被点名，
 * 并加两条反例（注释里提到关键词、别页有同名文字）确认不会误报。
 *
 * 运行：node --test apps/miniprogram/tests/validate-mini-copy-guards.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { validate } from '../scripts/validate-mini-copy-guards.mjs'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const PATHS = {
  historyWxml: 'pages/history/history.wxml',
  detailJs: 'pages/detail/detail.js',
  searchWxml: 'pages/search/search.wxml',
  searchJs: 'pages/search/search.js',
  aboutJs: 'pages/about/about.js',
  serverDiscovery: 'utils/server-discovery.js',
}

function baseFiles() {
  const files = {}
  for (const [key, rel] of Object.entries(PATHS)) files[key] = readFileSync(join(ROOT, rel), 'utf8')
  return files
}

function mutate(files, key, re, replacement) {
  assert.match(files[key], re, `${key} 坏样本锚点未命中：${re}`)
  files[key] = files[key].replace(re, replacement)
  return files
}

function expectHit(files, word) {
  const { errors } = validate(files)
  assert.ok(errors.some((e) => e.includes(word)), `期望抓到「${word}」，实际错误：${JSON.stringify(errors)}`)
}

describe('golden：当前源码全绿', () => {
  test('5 条判据都给出事实行', () => {
    const { errors, facts } = validate(baseFiles())
    assert.deepEqual(errors, [])
    assert.equal(facts.length, 5)
  })
})

describe('坏样本：每种坏状态都必须被抓', () => {
  test('J13 排序按钮退回纯图标（文字节点删除）', () => {
    const files = mutate(baseFiles(), 'historyWxml', /\s*<text class="sort-chip-label">[\s\S]*?<\/text>/, '')
    expectHit(files, 'J13')
  })

  test('J13 文字只写「最新」，翻转后仍是「最新」', () => {
    const files = mutate(baseFiles(), 'historyWxml', /sortOrder === 'desc' \? '最新' : '最早'/, "'最新'")
    expectHit(files, 'J13')
  })

  test('J33 applyNavTitle 形同虚设：不回写导航标题', () => {
    const files = mutate(baseFiles(), 'detailJs', /wx\.setNavigationBarTitle\(\{ title \}\);/, 'void title;')
    expectHit(files, 'J33')
  })

  test('J33 标题写死成「节目详情」（接错对象：不取集数据）', () => {
    const files = mutate(baseFiles(), 'detailJs', /const title = this\.data\.isCourse[\s\S]*?;\r?\n/, "const title = '节目详情';\n")
    expectHit(files, 'J33')
  })

  test('J33 只给正常加载设标题，本机下载兜底不设（漏一半）', () => {
    const files = mutate(baseFiles(), 'detailJs', /\s*\/\/ 兜底播放也要标题[\s\S]*?this\.applyNavTitle\(offlineEpisode\);\r?\n/, '\n')
    expectHit(files, 'J33')
  })

  test('J44 空态退回一句「未找到相关节目」', () => {
    const files = mutate(
      baseFiles(),
      'searchWxml',
      /\s*<text class="empty-title">[\s\S]*?<\/view>\r?\n(?=\s*<\/view>)/,
      '\n    <text>未找到相关节目</text>\n',
    )
    expectHit(files, 'J44')
  })

  test('J44 空态按钮接错对象：没有 onGoChannels 处理函数', () => {
    const files = mutate(baseFiles(), 'searchJs', /\s*\/\*\* J44[\s\S]*?onGoChannels\(\) \{[\s\S]*?\n  \},\r?\n/, '\n')
    expectHit(files, 'J44')
  })

  test('J58 文本节点回退成字面 \\n', () => {
    const files = baseFiles()
    files.wxmlScan = [
      { file: 'pages/download/download.wxml', src: '<text>第一句，\\n第二句</text>' },
    ]
    expectHit(files, 'J58')
  })

  test('J92 去掉 onVersionTap 的环境守卫', () => {
    const files = mutate(baseFiles(), 'aboutJs', /\s*\/\/ J92：正式版不认连续点击[^\r\n]*\r?\n\s*if \(EDIT_ENV_VERSIONS[\s\S]*?return;\r?\n/, '\n')
    expectHit(files, 'J92')
  })

  test('J92 白名单把 release 也放进来（守卫形同虚设）', () => {
    const files = mutate(baseFiles(), 'aboutJs', /const EDIT_ENV_VERSIONS = \['develop', 'trial'\];/, "const EDIT_ENV_VERSIONS = ['develop', 'trial', 'release'];")
    expectHit(files, 'J92')
  })

  test('J92 排障入口另开一处调用（绕过守卫）', () => {
    const files = mutate(
      baseFiles(),
      'aboutJs',
      /(onCopyContact\(\) \{)/,
      "onLongPressVersion() {\n    this.showServerUrlEditor();\n  },\n\n  $1",
    )
    expectHit(files, 'J92')
  })

  test('J92 版本判定各写一份：server-discovery 不再导出 getEnvVersion', () => {
    const files = mutate(baseFiles(), 'serverDiscovery', /module\.exports[\s\S]*$/, 'module.exports = { getManualBaseUrl };\n')
    expectHit(files, 'J92')
  })
})

describe('反例：不得误报', () => {
  test('注释里出现「最新/最早」不能顶替真实文字节点', () => {
    const files = baseFiles()
    files.historyWxml = files.historyWxml.replace(
      /\s*<text class="sort-chip-label">[\s\S]*?<\/text>/,
      '',
    )
    files.historyWxml = files.historyWxml.replace(
      /bindtap="onToggleSort"/,
      'bindtap="onToggleSort"\n        {{/* 最新 / 最早 由 aria-label 说明 */}}',
    )
    expectHit(files, 'J13')
  })

  test('别页（detail）也有 empty-hint 字样，不能替 search 交差', () => {
    const files = mutate(
      baseFiles(),
      'searchWxml',
      /\s*<text class="empty-title">[\s\S]*?<\/view>\r?\n(?=\s*<\/view>)/,
      '\n    <text>未找到相关节目</text>\n',
    )
    files.detailJs += '\n// empty-hint：这里只是别处的注释\n'
    expectHit(files, 'J44')
  })
})
