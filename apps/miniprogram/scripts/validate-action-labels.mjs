/**
 * J112 / J64 / J90 小程序门禁（T02536 / M4）：主操作、终局决策、破坏性操作不得只剩图标
 *
 * 为什么必须静态守：T00384 的「图标即按钮」被逐页无差别套用，wxml 里 aria-label 齐全，
 * 读屏没问题，但 sighted 用户看不出「保存」和「暂不设置」的区别。这类回退不会报错、
 * 不会让测试变红，只能靠人眼发现——人工复查必然回潮，所以把「可见文字」写进门禁。
 *
 * 判据：
 *  1. 详情页 6 个 action-chip 每个都有 .chip-label（倍速/收藏/队列/文稿/下载/睡眠）；
 *  2. 偏爱设置底栏有可见的「全选/全不选」「暂不设置」「保存」文字（J64 的终局决策）；
 *  3. 课程页订阅按钮、继续学习/从头播放、下载整门课程都有可见文字；
 *  4. 播放队列的「清空」是破坏性操作，必须有可见文字；
 *  5. webview 失败兜底的「复制链接/返回」保留文字（J105 不回退）；
 *  6. 原生 tabBar 每个 item 都有 text（导航层不得变纯图标）；
 *  7. J90 诚实性联动：凡宣称「断网/离线可听」，详情页必须真的实现了本机下载兜底
 *     （downloadStore.getDownload + audio_url: rec.localPath + offlinePlayback），
 *     否则文案又是一句空承诺。
 *
 * 局限：只做文本块定位与关键字配对，不解析 WXML 语法树；标签的可见性（display:none
 * 等）不在能力范围内；文字是否被样式裁掉也不检查。
 *
 * 运行：node apps/miniprogram/scripts/validate-action-labels.mjs
 * 自测（证伪样本）：node --test apps/miniprogram/tests/validate-action-labels.test.mjs
 */
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

const FILES = {
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

const stripComments = (src) => src.replace(/<!--[\s\S]*?-->/g, '')

/** 取以给定缩进打开、并以同缩进闭合的 view 块 */
function blockOf(src, openTag, indent) {
  const startRe = new RegExp(`^ {${indent}}<view class="${openTag}[^"]*"[^>]*>`, 'm')
  const m = startRe.exec(src)
  if (!m) return ''
  const endRe = new RegExp(`^ {${indent}}<\\/view>`, 'm')
  const rest = src.slice(m.index + m[0].length)
  const end = endRe.exec(rest)
  return end ? rest.slice(0, end.index) : ''
}

export function validate(overrides = {}) {
  const files = {}
  for (const [key, rel] of Object.entries(FILES)) {
    files[key] = overrides[key] != null
      ? overrides[key]
      : readFileSync(join(ROOT, rel), 'utf8')
  }

  const errors = []
  const facts = []

  // 1. 详情页 6 chip
  const actionRow = blockOf(files.detailWxml, 'action-row', 6)
  if (!actionRow) {
    errors.push('detail.wxml 找不到 .action-row：主操作区结构变了，门禁需同步（J112）')
  } else {
    const chips = actionRow.split(/class="action-chip/).slice(1)
    if (chips.length !== 6) {
      errors.push(`detail.wxml action-row 应有 6 个 chip，实际 ${chips.length} 个（J112）`)
    }
    chips.forEach((chunk, i) => {
      if (!chunk.includes('class="chip-label"')) {
        errors.push(`detail.wxml 第 ${i + 1} 个 action-chip 没有 .chip-label：图标失字（J112）`)
      }
      if (!chunk.includes('aria-label=')) {
        errors.push(`detail.wxml 第 ${i + 1} 个 action-chip 没有 aria-label：读屏也失字（J112）`)
      }
    })
    facts.push(`detail 主操作区：${chips.length} 个 chip 均有可见文字 + aria-label`)
  }

  // 2. 偏爱底栏
  const bottomBar = stripComments(blockOf(files.preferredWxml, 'bottom-bar', 4))
  if (!bottomBar) {
    errors.push('preferred-settings.wxml 找不到 .bottom-bar：终局决策栏结构变了（J64）')
  } else {
    // 只看文字节点：aria-label 里也有「保存」，拿整块文本做包含判断会被读屏属性蒙混过关
    const labels = [...bottomBar.matchAll(/<text class="(?:bar-label|save-btn-label)">([\s\S]*?)<\/text>/g)]
      .map((m) => m[1])
      .join('\n')
    for (const word of ['全选', '全不选', '暂不设置', '保存']) {
      if (!labels.includes(word)) {
        errors.push(`preferred-settings.wxml 底栏文字节点里缺少「${word}」：相反动作只有图标差异（J64）`)
      }
    }
    if (!labels) {
      errors.push('preferred-settings.wxml 底栏没有文字节点（.bar-label / .save-btn-label）（J64）')
    }
    facts.push('preferred 底栏：全选/全不选、暂不设置、保存 均有可见文字')
  }

  // 3. 课程页
  const course = stripComments(files.courseWxml)
  const subBtn = (course.match(/<view\s[^>]*class="sub-btn[^"]*"[^>]*>([\s\S]*?)<\/view>/) || [''])[0]
  if (!subBtn.includes('sub-btn-label')) {
    errors.push('course.wxml 订阅按钮没有 .sub-btn-label：订阅/已订阅只靠图标（J112）')
  }
  const progressActions = blockOf(course, 'progress-actions', 6) || ''
  const progressLabels = (progressActions.match(/progress-btn-label/g) || []).length
  if (progressLabels < 2) {
    errors.push(`course.wxml 继续学习/从头播放的文字标签只有 ${progressLabels} 个（应 ≥2，J112）`)
  }
  const downloadAll = blockOf(course, 'download-all-bar', 6) || ''
  if (!downloadAll.includes('download-all-label') || !downloadAll.includes('下载整门课程')) {
    errors.push('course.wxml 下载整门课程只留了图标/计数，没有可见文案（J112）')
  }
  if (subBtn.includes('sub-btn-label') && progressLabels >= 2 && downloadAll.includes('下载整门课程')) {
    facts.push('course：订阅、继续学习/从头播放、下载整门课程 均有可见文字')
  }

  // 4. 队列清空
  const queueClear = (stripComments(files.queueWxml).match(/<view\s[^>]*class="[^"]*clear-btn[^"]*"[^>]*>([\s\S]*?)<\/view>/) || [''])[0]
  if (!queueClear.includes('clear-btn-label') || !queueClear.includes('清空')) {
    errors.push('queue.wxml 清空按钮没有可见文字：破坏性操作只剩垃圾桶图标（J112）')
  } else {
    facts.push('queue：清空按钮保留可见文字')
  }

  // 5. webview 失败兜底不回退
  const webview = stripComments(files.webviewWxml)
  for (const word of ['复制链接', '返回']) {
    if (!new RegExp(`<text>${word}</text>`).test(webview)) {
      errors.push(`webview.wxml 失败兜底缺少可见文字「${word}」：最需要指令的场景失字（J105 回退）`)
    }
  }
  if (!errors.some((e) => e.includes('webview.wxml'))) {
    facts.push('webview 失败兜底：复制链接/返回 保留文字')
  }

  // 6. 原生 tabBar 文字
  let appJson = null
  try {
    appJson = JSON.parse(files.appJson)
  } catch (e) {
    errors.push('app.json 无法解析：tabBar 文字无从校验（J112）')
  }
  if (appJson) {
    const list = (appJson.tabBar && appJson.tabBar.list) || []
    if (list.length === 0) {
      errors.push('app.json 没有 tabBar.list（J112）')
    }
    list.forEach((item, i) => {
      if (!item.text) errors.push(`app.json tabBar 第 ${i + 1} 项没有 text：导航层变成纯图标（J112）`)
    })
    if (list.every((item) => !!item.text)) {
      facts.push(`tabBar：${list.map((i) => i.text).join('/')} 均有文字`)
    }
  }

  // 7. J90 宣称与实现联动
  const claimsOffline = /无网络也能听|断网也能听|离线可听|离线收听/.test(files.aboutJs + files.downloadWxml)
  if (claimsOffline) {
    const js = files.detailJs
    const hasFallback = js.includes('downloadStore.getDownload(id)')
      && js.includes('audio_url: rec.localPath')
      && js.includes('offlinePlayback: true')
    if (!hasFallback) {
      errors.push('宣称「断网/离线可听」但 detail.js 没有本机下载兜底（getDownload + rec.localPath + offlinePlayback）：文案空承诺（J90）')
    } else {
      facts.push('J90：离线收听宣称 → 详情页本机音频兜底已接线')
    }
  }

  return { errors, facts }
}

const isCli = process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href
if (isCli) {
  const { errors, facts } = validate()
  if (errors.length) {
    for (const e of errors) console.error(`  ✗ ${e}`)
    console.error(`[validate-action-labels] ${errors.length} 项不一致`)
    process.exit(1)
  }
  for (const f of facts) console.log(`  ✓ ${f}`)
  console.log('[validate-action-labels] 通过（主操作/终局决策/破坏性操作可见文字 + J90 宣称有实现）')
}
