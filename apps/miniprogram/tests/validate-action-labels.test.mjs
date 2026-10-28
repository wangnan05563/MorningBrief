/**
 * validate-action-labels.mjs 的证伪用例（T02536 / J112·J64·J90）
 *
 * 门禁若没有坏样本，就等于永远绿。这里逐条改坏真实源码的副本：
 *  - 每个坏样本必须被抓（错误信息点名对应判据）；
 *  - 反例（注释里出现关键词、别页的同类节点）不得误报。
 *
 * 运行：node --test apps/miniprogram/tests/validate-action-labels.test.mjs
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { validate } from '../scripts/validate-action-labels.mjs'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const FILES = [
  'detailWxml',
  'detailJs',
  'preferredWxml',
  'courseWxml',
  'queueWxml',
  'webviewWxml',
  'aboutJs',
  'downloadWxml',
  'appJson',
]
const PATHS = {
  detailWxml: 'pages/detail/detail.wxml',
  detailJs: 'pages/detail/detail.js',
  preferredWxml: 'pages/preferred-settings/preferred-settings.wxml',
  courseWxml: 'pages/course/course.wxml',
  queueWxml: 'pages/queue/queue.wxml',
  webviewWxml: 'pages/webview/webview.wxml',
  aboutJs: 'pages/about/about.js',
  downloadWxml: 'pages/download/download.wxml',
  appJson: 'app.json',
}

function baseFiles() {
  const files = {}
  for (const key of FILES) files[key] = readFileSync(join(ROOT, PATHS[key]), 'utf8')
  return files
}

function mutate(files, key, re, replacement) {
  assert.match(files[key], re, `${key} 坏样本锚点未命中：${re}`)
  files[key] = files[key].replace(re, replacement)
  return files
}

function expectHit(files, key, word) {
  const { errors } = validate(files)
  assert.ok(
    errors.some((e) => e.includes(word) && (key == null || e.includes(key))),
    `期望抓到「${word}」，实际错误：${JSON.stringify(errors)}`,
  )
  return errors
}

describe('真实源码是绿的', () => {
  test('当前 HEAD 无告警，且七类判据都有事实行', () => {
    const { errors, facts } = validate()
    assert.deepEqual(errors, [])
    assert.ok(facts.length >= 7, `事实行只有 ${facts.length} 条`)
  })
})

describe('主操作与决策失字被抓', () => {
  test('详情页某个 chip 丢掉文字标签', () =>
    expectHit(
      mutate(baseFiles(), 'detailWxml', /<text class="chip-label">队列<\/text>\r?\n/, ''),
      'detail.wxml',
      'chip-label',
    ))

  test('详情页某个 chip 连 aria-label 也没了', () =>
    expectHit(
      mutate(baseFiles(), 'detailWxml', / aria-label="打开播放队列"/, ''),
      'detail.wxml',
      'aria-label',
    ))

  test('偏爱底栏「暂不设置」回到纯图标', () => {
    const files = mutate(
      baseFiles(),
      'preferredWxml',
      /<text class="bar-label">暂不设置<\/text>\r?\n/,
      '',
    )
    expectHit(files, 'preferred-settings.wxml', '暂不设置')
  })

  test('偏爱保存按钮只留图标与角标（保存文字消失）', () => {
    const files = mutate(
      baseFiles(),
      'preferredWxml',
      /<text class="save-btn-label">[\s\S]*?<\/text>\r?\n/,
      '',
    )
    const errors = expectHit(files, 'preferred-settings.wxml', '保存')
    assert.ok(!errors.some((e) => e.includes('暂不设置')), '只该抓保存，不该牵连其它文案')
  })

  test('课程页订阅按钮回到纯图标', () =>
    expectHit(
      mutate(baseFiles(), 'courseWxml', /<text class="sub-btn-label">[\s\S]*?<\/text>\r?\n/, ''),
      'course.wxml',
      'sub-btn-label',
    ))

  test('课程页下载整门课程丢了文案', () =>
    expectHit(
      mutate(
        baseFiles(),
        'courseWxml',
        /<view class="download-all-main">\r?\n\s*<image class="download-all-icon"[^>]*\/>\n\s*<text class="download-all-label">[\s\S]*?<\/text>\r?\n(\s*)<\/view>\r?\n/,
        '',
      ),
      'course.wxml',
      '下载整门课程',
    ))

  test('队列清空回到纯垃圾桶图标', () =>
    expectHit(
      mutate(baseFiles(), 'queueWxml', /<text class="clear-btn-label">清空<\/text>\r?\n/, ''),
      'queue.wxml',
      '清空',
    ))

  test('webview 失败兜底丢掉「复制链接」文字（J105 回退）', () =>
    expectHit(
      mutate(baseFiles(), 'webviewWxml', /<text>复制链接<\/text>\r?\n/, ''),
      'webview.wxml',
      '复制链接',
    ))
})

describe('导航与宣称诚实性', () => {
  test('tabBar 少一项文字', () => {
    const files = baseFiles()
    files.appJson = files.appJson.replace(/"text": "更新",\r?\n/, '')
    assert.notEqual(files.appJson, baseFiles().appJson, 'app.json 坏样本锚点未命中')
    expectHit(files, 'app.json', 'tabBar')
  })

  test('宣称断网可听但没有本机兜底（J90 反例）', () => {
    const files = mutate(
      baseFiles(),
      'detailJs',
      /const rec = downloadStore\.getDownload\(id\);/,
      'const rec = null;',
    )
    expectHit(files, 'J90', 'J90')
  })
})

describe('防误报', () => {
  test('注释里提到离线可听不算额外宣称', () => {
    const files = mutate(
      baseFiles(),
      'downloadWxml',
      /<!-- 我的下载：离线缓存管理（FR-MC-09） -->/,
      '<!-- 我的下载：离线缓存管理（FR-MC-09）；离线收听是旧注释 -->',
    )
    const { errors } = validate(files)
    assert.deepEqual(errors, [])
  })

  test('其它页面的 chip-label 不能替详情页补文字', () => {
    const files = mutate(
      baseFiles(),
      'detailWxml',
      /<text class="chip-label">队列<\/text>\r?\n/,
      '',
    )
    // 在别处（注释外）补一个同名节点，仍然不构成详情页该 chip 的文案
    files.queueWxml = files.queueWxml.replace(
      '<view class="page-queue">',
      '<view class="page-queue"><text class="chip-label">队列</text>',
    )
    expectHit(files, 'detail.wxml', 'chip-label')
  })
})
